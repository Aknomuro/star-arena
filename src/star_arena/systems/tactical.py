"""Bataille RTS pure Python : aucun import de Pygame, de fenêtre ou d'audio."""
from dataclasses import dataclass, field
from star_arena.systems.battlefield import generate_battlefield
from math import atan2, cos, hypot, isfinite, pi, sin
from random import Random

from star_arena.config import ACTIVE_UNITS_PER_SIDE, BATTLE_SIZE, BATTLE_STEP, MAX_EFFECTS, MAX_PROJECTILES, TACTICAL_AI_INTERVAL
from star_arena.domain.models import BattleReport, Campaign, Engagement, Point, Ship, SHIP_TYPES
from star_arena.domain.ship_stats import COMBAT_STATS, damage_multiplier
from star_arena.systems.combat import engaged_ships, resolve_engagement
from star_arena.domain.planet_stats import STATIONS
from star_arena.systems.formations import offsets
from star_arena.systems.spatial import SpatialGrid


@dataclass
class Unit:
    ship: Ship
    fleet_id: int
    owner: int
    x: float
    y: float
    angle: float
    order: str = "guard"
    destination: Point | None = None
    target: int | None = None
    vx: float = 0.0
    vy: float = 0.0
    scan_in: float = 0.0
    cooldowns: list[float] = field(default_factory=list)
    weapon_targets: list[int] = field(default_factory=list)
    radar: bool = False

    @property
    def radius(self) -> float:
        return COMBAT_STATS[self.ship.model].radius


@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    target: int
    owner: int
    damage: float
    life: float = 3.0


@dataclass
class Effect:
    x: float
    y: float
    owner: int
    kind: str
    life: float
    duration: float
    radius: float


class BattleEngine:
    def __init__(self, campaign: Campaign, engagement: Engagement) -> None:
        if campaign.pending is None or campaign.pending.id != engagement.id:
            raise ValueError("Engagement absent de la campagne.")
        self.campaign = campaign
        self.engagement = engagement
        self.player = campaign.player
        self.ships = engaged_ships(campaign, engagement)
        self.initial_by_id = {s.id: s for s in engagement.initial}
        self.units: dict[int, Unit] = {}
        self.reserves = list(engagement.initial)
        self.projectiles: list[Projectile] = []
        self.effects: list[Effect] = []
        self.grid = SpatialGrid()
        self.rng = Random(campaign.seed + engagement.id * 7919)
        self.environment=generate_battlefield(campaign,engagement)
        self.asteroids=self.environment.asteroids
        self.reduced_quality=False
        self.event_counts = dict.fromkeys(("laser","impact","shield","explosion"),0)
        self.elapsed = 0.0
        self.accumulator = 0.0
        self.ai_in = 0.0
        self.finished = False
        self.winner: int | None = None
        self.retreated = False
        self.report: BattleReport | None = None
        self._deploy()
        self.grid.rebuild(self.units.values())

    def _deploy(self) -> None:
        if not self.reserves: return
        for owner in (self.engagement.attacker, self.engagement.defender):
            active = sum(u.ship.alive and u.owner == owner for u in self.units.values())
            pending = sorted((s for s in self.reserves if s.owner == owner),
                             key=lambda s: (self.ships[s.id].status != "orbital", s.id))
            side = 0 if owner == self.player else 1
            slots = offsets(min(ACTIVE_UNITS_PER_SIDE, len(pending)), "compact")
            added = 0
            for record in pending:
                if active >= ACTIVE_UNITS_PER_SIDE:
                    break
                if record.id in self.units:
                    raise ValueError("Un vaisseau ne peut pas être redéployé.")
                ox, oy = slots[added]
                stats = COMBAT_STATS[record.model]
                unit = Unit(self.ships[record.id], record.fleet_id, owner,
                            (560 if side == 0 else 2640) + ox, 1000 + oy, 0.0 if side == 0 else pi)
                if unit.ship.status == 'orbital':
                    fallback=(1300. if side==0 else 1900.,1000.)
                    unit.x,unit.y=self.environment.structures.get(unit.ship.id,fallback)
                    unit.order = 'hold'
                unit.scan_in = (record.id % 7) * 0.04
                unit.cooldowns = [self.rng.uniform(0, stats.cooldown) for _ in range(stats.turrets)]
                self.units[record.id] = unit
                self.reserves.remove(record)
                active += 1
                added += 1

    def living(self, owner: int | None = None) -> list[Unit]:
        return [u for u in self.units.values() if u.ship.alive and (owner is None or u.owner == owner)]

    def safe_destination(self, point: Point, radius: float) -> Point:
        x = min(BATTLE_SIZE[0] - 70, max(70.0, point[0]))
        y = min(BATTLE_SIZE[1] - 70, max(70.0, point[1]))
        for ax, ay, ar in self.asteroids:
            dx, dy = x - ax, y - ay
            distance = hypot(dx, dy)
            minimum = ar + radius + 24
            if distance < minimum:
                dx, dy = (dx / distance, dy / distance) if distance > 0.001 else (1.0, 0.0)
                x, y = ax + dx * minimum, ay + dy * minimum
        return x, y

    def command(self, ids, order: str, point: Point | None = None, target: int | None = None,
                formation: str = "compact") -> None:
        if self.finished or order not in ("move", "attack", "attack_move", "stop", "hold"):
            return
        selected = sorted((u for uid in set(ids) if (u := self.units.get(uid)) is not None
                           and u.ship.alive and u.owner == self.player and u.ship.status != "orbital"), key=lambda u: (-u.radius, u.ship.id))
        if point is not None and not all(isfinite(n) for n in point):
            return
        enemy = self.units.get(target) if target is not None else None
        if order == "attack" and (enemy is None or not enemy.ship.alive or enemy.owner == self.player):
            return
        slots = offsets(len(selected), formation)
        for i, unit in enumerate(selected):
            unit.order = order
            unit.target = target if order == "attack" else None
            unit.weapon_targets.clear()
            unit.scan_in = 0.0
            destination = point or (unit.x, unit.y)
            unit.destination = self.safe_destination((destination[0] + slots[i][0], destination[1] + slots[i][1]), unit.radius) if order in ("move", "attack_move") else None

    def advance(self, dt: float) -> None:
        if self.finished or not isfinite(dt) or dt <= 0:
            return
        self.accumulator += min(dt, 0.2)
        steps = min(6, int((self.accumulator + 1e-9) / BATTLE_STEP))
        self.accumulator = max(0.0, self.accumulator - steps * BATTLE_STEP)
        for _ in range(steps):
            self._tick(BATTLE_STEP)
            if self.finished:
                break

    def _score(self, source: Unit, target: Unit) -> float:
        return (damage_multiplier(source.ship.model, target.ship.model) * 500
                - hypot(source.x - target.x, source.y - target.y)
                + (1 - target.ship.hull / self.engagement_hull(target.ship.id)) * 70)

    def engagement_hull(self, uid: int) -> float:
        return self.initial_by_id[uid].hull

    def _update_ai(self) -> None:
        enemies = self.living(self.player)
        if not enemies:
            return
        allied_cruisers = [u for u in self.living() if u.owner != self.player and u.ship.model == "cruiser"]
        for unit in self.living():
            if unit.owner == self.player:
                continue
            nearby = [v for v in self.grid.near(unit.x, unit.y, 900) if v.owner != unit.owner]
            candidates = nearby or enemies
            target = max(candidates, key=lambda other: self._score(unit, other))
            if unit.ship.model == "corvette" and allied_cruisers:
                anchor = min(allied_cruisers, key=lambda u: (u.x - unit.x)**2 + (u.y - unit.y)**2)
                threats = [v for v in self.grid.near(anchor.x, anchor.y, 650) if v.owner != unit.owner]
                if threats:
                    target = max(threats, key=lambda other: self._score(unit, other))
                elif hypot(unit.x - anchor.x, unit.y - anchor.y) > 220:
                    unit.order = "move"
                    unit.destination = self.safe_destination((anchor.x - 110, anchor.y + (unit.ship.id % 3 - 1) * 130), unit.radius)
                    continue
            unit.order = "attack"
            unit.target = target.ship.id

    def _tick(self, dt: float) -> None:
        self.elapsed += dt
        self._deploy()
        self.grid.rebuild(self.units.values())
        self.ai_in -= dt
        if self.ai_in <= 0:
            self.ai_in = TACTICAL_AI_INTERVAL
            self._update_ai()
        living = self.living()
        for unit in living:
            unit.radar = False
        # Les bâtiments de soutien agissent physiquement dans leur rayon (stations : réparation).
        for unit in living:
            if unit.ship.status != 'orbital':
                continue
            nearby=[other for other in self.grid.near(unit.x,unit.y,COMBAT_STATS[unit.ship.model].reach)
                    if other.owner==unit.owner]
            if unit.ship.model=='radar':
                for other in nearby:
                    other.scan_in=min(other.scan_in,.05)
                    other.radar=True
            if unit.ship.model in ('shield','repair') or unit.ship.model.startswith('station'):
                # Appliquer uniquement les sources réellement à portée, sans soins à distance globale.
                for other in nearby:
                    _,h,sh = SHIP_TYPES[other.ship.model]
                    if unit.ship.model=='shield':
                        other.ship.shield=min(sh,other.ship.shield+12*dt)
                    else:
                        rate=8. if unit.ship.model=='repair' else STATIONS[int(unit.ship.model[-1])][6]
                        other.ship.hull=min(h,other.ship.hull+rate*dt)
        for unit in living:
            self._update_unit(unit, dt)
        remaining = []
        for shot in self.projectiles:
            shot.life -= dt
            target = self.units.get(shot.target)
            if shot.life <= 0 or target is None or not target.ship.alive:
                continue
            nx, ny = shot.x + shot.vx * dt, shot.y + shot.vy * dt
            dx, dy = nx - shot.x, ny - shot.y
            length2 = dx * dx + dy * dy
            t = min(1.0, max(0.0, ((target.x - shot.x) * dx + (target.y - shot.y) * dy) / length2)) if length2 else 0.0
            if hypot(shot.x + t * dx - target.x, shot.y + t * dy - target.y) <= target.radius:
                self.damage(target.ship.id, shot.damage)
            else:
                shot.x, shot.y = nx, ny
                remaining.append(shot)
        self.projectiles = remaining
        for effect in self.effects:
            effect.life -= dt
        self.effects[:] = [e for e in self.effects if e.life > 0]
        owners_alive = {s.owner for s in self.engagement.initial if self.ships[s.id].alive}
        if len(owners_alive) <= 1:
            self.finished = True
            self.winner = next(iter(owners_alive), None)

    def _update_unit(self, unit: Unit, dt: float) -> None:
        stats = COMBAT_STATS[unit.ship.model]
        reach = stats.reach * (1.2 if unit.radar else 1.)
        unit.scan_in -= dt
        target = self.units.get(unit.target) if unit.target is not None else None
        if target is not None and not target.ship.alive:
            target = None
            unit.target = None
            if unit.order == "attack":
                unit.order = "guard"
        if target is not None and unit.order != "attack" and hypot(target.x - unit.x, target.y - unit.y) > reach + 140:
            target = None
            unit.target = None
        if unit.scan_in <= 0:
            unit.scan_in = 0.30 + (unit.ship.id % 5) * 0.025
            candidates = sorted((v for v in self.grid.near(unit.x, unit.y, reach + 140) if v.owner != unit.owner),
                                key=lambda v: self._score(unit, v), reverse=True)
            if target is None and candidates:
                target = candidates[0]
                if unit.order != "move":
                    unit.target = target.ship.id
            if unit.order == "attack" and target is not None:
                unit.weapon_targets = [target.ship.id] * stats.turrets
            else:
                unit.weapon_targets = [candidates[i % len(candidates)].ship.id for i in range(stats.turrets)] if candidates else []
        moving_to = unit.destination if unit.order in ("move", "attack_move") else None
        if target is not None and unit.order in ("attack", "guard", "attack_move"):
            distance = hypot(target.x - unit.x, target.y - unit.y)
            if unit.order == "attack" or distance < reach + 140:
                if distance > reach * 0.78:
                    moving_to = (target.x, target.y)
                else:
                    moving_to = None
        self._move(unit, moving_to, dt)
        for i in range(stats.turrets):
            unit.cooldowns[i] = max(0.0, unit.cooldowns[i] - dt)
            uid = unit.weapon_targets[i] if i < len(unit.weapon_targets) else None
            enemy = self.units.get(uid)
            if enemy is None or not enemy.ship.alive or unit.cooldowns[i] > 0 or len(self.projectiles) >= MAX_PROJECTILES:
                continue
            distance = hypot(enemy.x - unit.x, enemy.y - unit.y)
            if distance <= reach:
                lead = distance / stats.projectile_speed
                angle = atan2(enemy.y + enemy.vy * lead - unit.y, enemy.x + enemy.vx * lead - unit.x)
                self.event_counts["laser"] += 1
                self.projectiles.append(Projectile(unit.x, unit.y, cos(angle) * stats.projectile_speed,
                                                   sin(angle) * stats.projectile_speed, uid, unit.owner,
                                                   stats.damage * damage_multiplier(unit.ship.model, enemy.ship.model)))
                unit.cooldowns[i] = stats.cooldown

    def _move(self, unit: Unit, goal: Point | None, dt: float) -> None:
        stats = COMBAT_STATS[unit.ship.model]
        if unit.ship.status == "orbital":
            unit.vx = unit.vy = 0.
            return
        dx, dy = (goal[0] - unit.x, goal[1] - unit.y) if goal else (0.0, 0.0)
        distance = hypot(dx, dy)
        vx, vy = (dx / distance * stats.speed, dy / distance * stats.speed) if distance > 12 else (0.0, 0.0)
        for other in self.grid.near(unit.x, unit.y, unit.radius + 90):
            if other is unit:
                continue
            ox, oy = unit.x - other.x, unit.y - other.y
            d = hypot(ox, oy)
            spacing = unit.radius + other.radius + 12
            if d <= 0.001:
                angle = ((min(unit.ship.id, other.ship.id) * 37 + max(unit.ship.id, other.ship.id) * 17) % 360) * pi / 180
                angle += 0 if unit.ship.id < other.ship.id else pi
                ox, oy, d = cos(angle), sin(angle), 1.0
            if 0.001 < d < spacing:
                vx += ox / d * (spacing - d) * 3
                vy += oy / d * (spacing - d) * 3
        for ax, ay, ar in self.asteroids:
            ox, oy = unit.x - ax, unit.y - ay
            d = hypot(ox, oy)
            safe = ar + unit.radius + 55
            if 0.001 < d < safe:
                side = 1 if unit.ship.id % 2 else -1
                vx += (ox / d - oy / d * side) * (safe - d) * 4
                vy += (oy / d + ox / d * side) * (safe - d) * 4
        speed = min(stats.speed, hypot(vx, vy))
        if speed > 0.01:
            desired = atan2(vy, vx)
            delta = (desired - unit.angle + pi) % (2 * pi) - pi
            unit.angle += max(-stats.turn_rate * dt, min(stats.turn_rate * dt, delta))
            # Ralentir les gros demi-tours au lieu de glisser latéralement.
            speed *= max(0.15, cos(delta))
            unit.vx, unit.vy = cos(unit.angle) * speed, sin(unit.angle) * speed
        else:
            unit.vx = unit.vy = 0.0
            if unit.order in ("move", "attack_move") and goal is not None and distance <= 12:
                unit.order = "guard"
                unit.destination = None
        unit.x = max(60.0, min(BATTLE_SIZE[0] - 60, unit.x + unit.vx * dt))
        unit.y = max(60.0, min(BATTLE_SIZE[1] - 60, unit.y + unit.vy * dt))
        for ax, ay, ar in self.asteroids:
            ox, oy = unit.x - ax, unit.y - ay
            d = hypot(ox, oy)
            if d < ar + unit.radius:
                nx, ny = (ox / d, oy / d) if d > 0.001 else (1.0, 0.0)
                unit.x, unit.y = ax + nx * (ar + unit.radius + 1), ay + ny * (ar + unit.radius + 1)

    def damage(self, uid: int, amount: float) -> None:
        unit = self.units.get(uid)
        if unit is None or not unit.ship.alive:
            return
        shielded = unit.ship.shield > 0
        self.event_counts["shield" if shielded else "impact"] += 1
        unit.ship.receive_damage(amount)
        self._effect(unit.x, unit.y, unit.owner, "shield" if shielded else "impact", 0.25, unit.radius + 5)
        if not unit.ship.alive:
            self.event_counts["explosion"] += 1
            self._effect(unit.x, unit.y, unit.owner, "explosion", 0.7, unit.radius * 2)
            for i in range(0 if self.reduced_quality else 3):
                self._effect(unit.x + cos(i * 2.1) * unit.radius, unit.y + sin(i * 2.1) * unit.radius,
                             unit.owner, "debris", 1.2, 5)

    def _effect(self, x: float, y: float, owner: int, kind: str, life: float, radius: float) -> None:
        if len(self.effects) < (32 if self.reduced_quality else MAX_EFFECTS):
            self.effects.append(Effect(x, y, owner, kind, life, life, radius))

    def withdraw(self) -> None:
        if not self.finished:
            self.finished = True
            self.retreated = True
            self.winner = self.engagement.defender if self.player == self.engagement.attacker else self.engagement.attacker

    def commit(self) -> BattleReport:
        if not self.finished:
            raise ValueError("La bataille n'est pas terminée.")
        if self.report is None:
            self.report = resolve_engagement(self.campaign, self.engagement, self.winner, retreat=self.retreated)
        return self.report
