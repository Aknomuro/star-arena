"""Économie fixe et construction payante, sans dépendance graphique."""
from typing import Protocol
from star_arena.systems.planets import planet_income, maintenance, energy_balance, update_planets, ai_planets
from star_arena.domain.models import Campaign, Fleet, Production, SHIP_TYPES, Ship

# crédits, minerais, durée en secondes, niveau requis
SHIP_COSTS = {"fighter": (80, 35, 8, 1), "corvette": (240, 120, 22, 2), "cruiser": (700, 380, 55, 3)}
YARD_COSTS = {1: (200, 100), 2: (350, 180), 3: (600, 320)}
QUEUE_LIMIT = 20

class EconomySystem(Protocol):
    def update(self, campaign: Campaign, dt: float) -> None: ...

class NoEconomy:
    def update(self, campaign: Campaign, dt: float) -> None:
        pass

def income(c: Campaign, owner: int) -> tuple[int, int]:
    systems = [s for s in c.systems.values() if s.owner == owner]
    planets = [p for s in systems for p in s.planets if p.owner==owner and p.occupier is None]
    bonuses = [planet_income(p) for p in planets]
    return len(systems)*4+sum(v[0] for v in bonuses)-sum(maintenance(p) for p in planets), sum(max(0,s.richness-1)*2 for s in systems)+sum(v[1] for v in bonuses)

def yard_order(c: Campaign, system_id: int, owner: int, model: str | None = None) -> str:
    s = c.systems.get(system_id)
    if c.pending or s is None or s.owner != owner:
        return "Un système contrôlé sans conflit est nécessaire."
    if model is None:
        if s.shipyard >= 3:
            return "Chantier déjà au niveau maximal."
        credits, minerals = YARD_COSTS[s.shipyard + 1]
    else:
        if model not in SHIP_COSTS:
            return "Classe inconnue."
        credits, minerals, duration, level = SHIP_COSTS[model]
        if s.shipyard < level or len(s.queue) >= QUEUE_LIMIT:
            return "Niveau de chantier insuffisant ou file pleine (20)."
    stock = c.resources[owner]
    if stock.credits < credits or stock.minerals < minerals:
        return "Crédits ou minerais insuffisants."
    stock.credits -= credits
    stock.minerals -= minerals
    if s.yard_owner != owner:
        s.queue.clear()
    s.yard_owner = owner
    if model is None:
        s.shipyard += 1
        c.log(f"{s.name} : chantier niveau {s.shipyard}.")
    else:
        s.queue.append(Production(model, float(duration)))
    return ""

def transfer(c: Campaign, source_id: int, destination_id: int | None, owner: int,
             ship_ids: list[int] | None = None) -> str:
    source = c.fleets.get(source_id)
    if c.pending or source is None or source.owner != owner or source.travel or source.status != "permanent" or not source.ships:
        return "Une flotte alliée immobile et sans conflit est nécessaire."
    ids = {s.id for s in source.ships} if ship_ids is None else set(ship_ids)
    if not ids or not ids <= {s.id for s in source.ships}:
        return "Sélection de vaisseaux invalide."
    destination = c.fleets.get(destination_id) if destination_id is not None else None
    if destination_id is not None and (destination is None or destination is source or destination.owner != owner
            or destination.status != "permanent" or destination.travel or destination.system_id != source.system_id):
        return "Les flottes doivent être alliées dans le même système."
    if destination is None:
        c.next_fleet_id = max(c.next_fleet_id, max(c.fleets, default=0) + 1)
        destination = Fleet(c.next_fleet_id, owner, source.system_id)
        c.fleets[destination.id] = destination
        c.next_fleet_id += 1
    destination.ships.extend(s for s in source.ships if s.id in ids)
    source.ships[:] = [s for s in source.ships if s.id not in ids]
    return ""

class GalacticEconomy:
    def __init__(self,human_factions=None):
        self.human_factions=human_factions

    def update(self, c: Campaign, dt: float) -> None:
        c.economy_remainder += dt
        while c.economy_remainder + 1e-9 >= 1:
            c.economy_remainder = max(0., c.economy_remainder - 1)
            update_planets(c)
            for owner in range(3):
                credits, minerals = income(c, owner)
                c.resources[owner].credits = max(0., c.resources[owner].credits + credits)
                c.resources[owner].minerals += minerals
                balance=sum(energy_balance(p) for s in c.systems.values() if s.owner==owner
                            for p in s.planets if p.owner==owner and p.occupier is None)
                c.resources[owner].energy=max(0.,c.resources[owner].energy+balance)
            for s in c.systems.values():
                if s.yard_owner != s.owner:
                    s.queue.clear()
                    s.yard_owner = s.owner
                if s.owner is None or not s.queue:
                    continue
                job = s.queue[0]
                job.remaining = max(0., job.remaining - (1 + .15*sum(p.ground.get("industry",0) for p in s.planets
                                                         if p.owner==s.owner and p.occupier is None and energy_balance(p)>=0)))
                if job.remaining > 0:
                    continue
                c.next_ship_id = max(c.next_ship_id, max((u.id for f in c.fleets.values() for u in f.ships), default=0) + 1)
                _, hull, shield = SHIP_TYPES[job.model]
                fleets = [f for f in c.fleets_at(s.id) if f.owner == s.owner and f.status == "permanent"]
                if not fleets:
                    c.next_fleet_id = max(c.next_fleet_id, max(c.fleets, default=0) + 1)
                    fleet = Fleet(c.next_fleet_id, s.owner, s.id)
                    c.fleets[fleet.id] = fleet
                    c.next_fleet_id += 1
                else:
                    fleet = min(fleets, key=lambda f: f.id)
                fleet.ships.append(Ship(c.next_ship_id, job.model, hull, shield))
                c.next_ship_id += 1
                s.queue.pop(0)
                c.log(f"{s.name} : {SHIP_TYPES[job.model][0]} terminé, flotte {fleet.id}.")
            if int(c.time) % 6 == 0:
                self.ai(c)
                ai_planets(c,self.human_factions)

    def ai(self, c: Campaign) -> None:
        for owner in range(3):
            if owner in (self.human_factions if self.human_factions is not None else {c.player}):
                continue
            sites = sorted((s for s in c.systems.values() if s.owner == owner),
                           key=lambda s: (not s.capital, -s.richness, s.id))
            for s in sites[:2]:
                if s.shipyard == 0:
                    yard_order(c, s.id, owner)
                elif not s.queue:
                    if s.shipyard < 3 and c.resources[owner].credits > 650:
                        yard_order(c, s.id, owner)
                    available = [m for m, spec in SHIP_COSTS.items() if spec[3] <= s.shipyard]
                    yard_order(c, s.id, owner, available[(int(c.time) // 6 + owner) % len(available)])
