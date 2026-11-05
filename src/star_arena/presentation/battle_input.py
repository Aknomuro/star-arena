"""Entrées RTS isolées des commandes galactiques ; Pygame est injecté par l'app."""
from math import hypot

from star_arena.config import BATTLE_SIZE
from star_arena.presentation.camera import Camera
from star_arena.systems.formations import FORMATIONS, FORMATION_NAMES


class BattleControls:
    def __init__(self, pygame, engine) -> None:
        self.pg = pygame
        self.engine = engine
        self.camera = Camera((1600.0, 1000.0), 0.36, (16, 96, 1248, 490), (0, 0, *BATTLE_SIZE))
        self.selected: set[int] = set()
        self.groups: dict[int, set[int]] = {}
        self.formation = "compact"
        self.attack_pending = False
        self.drag_start = None
        self.drag_end = None
        self.menu = False
        self.paused = False
        self.s_pressed_at: int | None = None
        self.message = "Sélectionnez vos vaisseaux. Clic droit : déplacer ou attaquer."

    def pick(self, position):
        wx, wy = self.camera.world(position)
        candidates = [u for u in self.engine.living()
                      if hypot(u.x - wx, u.y - wy) <= u.radius + 6 / self.camera.scale]
        return min(candidates, key=lambda u: (u.x - wx)**2 + (u.y - wy)**2) if candidates else None

    def select_all(self) -> None:
        self.selected = {u.ship.id for u in self.engine.living(self.engine.player)}

    def set_formation(self, index: int) -> None:
        self.formation = FORMATIONS[index]
        units = [u for u in self.engine.living(self.engine.player) if u.ship.id in self.selected]
        if units:
            center = sum(u.x for u in units) / len(units), sum(u.y for u in units) / len(units)
            self.engine.command(self.selected, "move", center, formation=self.formation)
        self.message = "Formation : " + FORMATION_NAMES[index]

    def handle(self, event, app) -> None:
        pg = self.pg
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            self.menu = not self.menu
            self.drag_start = None
            self.attack_pending = False
            self.s_pressed_at = None
            return
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for button in app.renderer.buttons:
                if button.rect.collidepoint(event.pos):
                    if button.enabled:
                        app.battle_action(button.action)
                    return
        if self.menu or self.engine.finished:
            return
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_SPACE:
                self.paused = not self.paused
            elif event.key == pg.K_a:
                self.attack_pending = True
                self.message = "Attaque-déplacement : clic gauche sur la destination."
            elif event.key == pg.K_s:
                self.s_pressed_at = pg.time.get_ticks()
            elif event.key == pg.K_h:
                self.engine.command(self.selected, "hold")
                self.message = "Tenir la position."
            elif pg.K_1 <= event.key <= pg.K_9:
                group = event.key - pg.K_0
                if event.mod & pg.KMOD_CTRL:
                    self.groups[group] = set(self.selected)
                    self.message = f"Groupe {group} mémorisé."
                else:
                    self.selected = self.groups.get(group, set()) & {u.ship.id for u in self.engine.living(self.engine.player)}
            elif event.key in (pg.K_F5, pg.K_F9):
                self.message = "Sauvegarde et chargement disponibles depuis la galaxie, après la bataille."
        elif event.type == pg.KEYUP and event.key == pg.K_s:
            if self.s_pressed_at is not None and pg.time.get_ticks() - self.s_pressed_at < 180:
                self.engine.command(self.selected, "stop")
                self.message = "Arrêt des unités sélectionnées."
            self.s_pressed_at = None
        elif event.type == pg.MOUSEBUTTONDOWN and pg.Rect(self.camera.viewport).collidepoint(event.pos):
            point = self.camera.world(event.pos)
            if event.button == 1:
                if self.attack_pending:
                    self.engine.command(self.selected, "attack_move", point, formation=self.formation)
                    self.attack_pending = False
                    self.message = "Attaque-déplacement."
                else:
                    self.drag_start = self.drag_end = event.pos
            elif event.button == 3:
                self.attack_pending = False
                target = self.pick(event.pos)
                if target is not None and target.owner != self.engine.player:
                    self.engine.command(self.selected, "attack", target=target.ship.id)
                    self.message = "Concentration des tirs sur la cible."
                else:
                    self.engine.command(self.selected, "move", point, formation=self.formation)
                    self.message = "Déplacement en formation."
        elif event.type == pg.MOUSEBUTTONUP and event.button == 1 and self.drag_start is not None:
            shift = bool(pg.key.get_mods() & pg.KMOD_SHIFT)
            start = self.drag_start
            if hypot(event.pos[0] - start[0], event.pos[1] - start[1]) > 6:
                rect = pg.Rect(start, (event.pos[0] - start[0], event.pos[1] - start[1]))
                rect.normalize()
                found = {u.ship.id for u in self.engine.living(self.engine.player) if rect.collidepoint(self.camera.screen((u.x, u.y)))}
                self.selected = self.selected | found if shift else found
            else:
                unit = self.pick(event.pos)
                found = {unit.ship.id} if unit is not None and unit.owner == self.engine.player else set()
                self.selected = self.selected ^ found if shift else found
            self.drag_start = self.drag_end = None
        elif event.type == pg.MOUSEMOTION:
            if self.drag_start is not None:
                self.drag_end = event.pos
            if event.buttons[1] and pg.Rect(self.camera.viewport).collidepoint(event.pos):
                self.camera.pan(*event.rel)
        elif event.type == pg.MOUSEWHEEL and pg.Rect(self.camera.viewport).collidepoint(pg.mouse.get_pos()):
            self.camera.zoom(1.12 ** max(-3, min(3, event.y)), pg.mouse.get_pos())

    def update(self, dt: float) -> None:
        self.selected.intersection_update(u.ship.id for u in self.engine.living(self.engine.player))
        if self.menu:
            return
        pg = self.pg
        keys = pg.key.get_pressed()
        down_s = keys[pg.K_s] and self.s_pressed_at is not None and pg.time.get_ticks() - self.s_pressed_at >= 180
        dx = int(bool(keys[pg.K_d] or keys[pg.K_RIGHT])) - int(bool(keys[pg.K_q] or keys[pg.K_LEFT]))
        dy = int(bool(down_s or keys[pg.K_DOWN])) - int(bool(keys[pg.K_z] or keys[pg.K_UP]))
        length = hypot(dx, dy)
        if length:
            self.camera.pan(-dx / length * 700 * dt * self.camera.scale, -dy / length * 700 * dt * self.camera.scale)
