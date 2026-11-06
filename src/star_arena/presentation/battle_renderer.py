"""Rendu RTS logiciel, appelé seulement pendant un lancement manuel du jeu."""
from collections import Counter
from math import cos, degrees, pi, sin
from pathlib import Path
from star_arena.config import project_root

import pygame

from star_arena.domain.models import FACTIONS, SHIP_TYPES
from star_arena.presentation.fleet_assets import PALETTES, display_extent
from star_arena.presentation.ship_sprites import ShipSprites
from star_arena.systems.formations import FORMATION_NAMES


class BattleRenderer:
    def __init__(self, renderer) -> None:
        self.ui = renderer
        directory = project_root() / "assets" / "ships"
        self.ship_sprites = ShipSprites(pygame, directory)
        self.ship_sprites.preload()

    def draw(self, app) -> None:
        ui = self.ui
        surface = ui.surface
        battle, controls = app.battle, app.battle_controls
        camera = controls.camera
        previous_clip = surface.get_clip()
        surface.set_clip(camera.viewport)
        visible = pygame.Rect(camera.viewport).inflate(400, 400)
        for planet in battle.environment.planets:
            point=camera.screen((planet.x,planet.y)); radius=max(8,round(planet.radius*camera.scale))
            if visible.collidepoint(point):
                if not app.reduced_quality:
                    ui.circle(surface,(35,54,73),point,max(radius+8,round((planet.radius+110)*camera.scale)),1)
                ui.painter.planet(surface,point,radius,planet.kind)
                ui.text(planet.name,point[0]-65,point[1]+radius+8,14,width=180)
        for ax, ay, radius in battle.asteroids:
            point = camera.screen((ax, ay))
            if visible.collidepoint(point):
                r = max(3, round(radius * camera.scale))
                points = [(point[0] + cos(i * pi / 4) * r * (0.82 if i % 2 else 1),
                           point[1] + sin(i * pi / 4) * r * (0.82 if i % 2 else 1)) for i in range(8)]
                pygame.draw.polygon(surface, (42, 48, 58), points)
                pygame.draw.polygon(surface, (88, 96, 109), points, 1)
        for shot in battle.projectiles:
            point = camera.screen((shot.x, shot.y))
            if visible.collidepoint(point):
                tail = camera.screen((shot.x - shot.vx * 0.025, shot.y - shot.vy * 0.025))
                pygame.draw.line(surface, FACTIONS[shot.owner].color, tail, point, 2)
        for unit in battle.living():
            point = camera.screen((unit.x, unit.y))
            if not visible.collidepoint(point):
                continue
            extent = max(22, round(unit.radius*2*camera.scale)) if unit.ship.status=="orbital" else display_extent(unit.ship.model, camera.scale)
            radius = max(5, round(extent / 2.7))
            palette = PALETTES[unit.owner]
            color = palette.accent
            if unit.ship.id in controls.selected:
                ui.circle(surface, (133, 255, 204), point, radius + 7, 2)
            image = None if unit.ship.status=="orbital" else self.ship_sprites.get(unit.owner, unit.ship.model, extent, degrees(unit.angle), reduced=app.reduced_quality)
            if unit.ship.status == 'orbital':
                ui.circle(surface, palette.body, point, radius)
                ui.circle(surface, color, point, radius, 2)
                pygame.draw.rect(surface, color, (point[0]-radius//2,point[1]-radius//2,radius,radius), 2)
                ui.text(SHIP_TYPES[unit.ship.model][0], point[0]-60, point[1]+radius+10, 14, width=155)
            elif image is not None:
                surface.blit(image, image.get_rect(center=point))
                ui.circle(surface, color, point, radius + 3, 1)
            else:
                shape = ((1.5, 0), (-1, -0.8), (-0.6, 0), (-1, 0.8))
                if unit.ship.model == "cruiser":
                    shape = ((1.5, 0), (0.5, -0.7), (-1, -0.7), (-1.2, 0), (-1, 0.7), (0.5, 0.7))
                elif unit.ship.model == "corvette":
                    shape = ((1.4, 0), (0, -0.8), (-1, -0.6), (-1, 0.6), (0, 0.8))
                points = [(point[0] + (x * cos(unit.angle) - y * sin(unit.angle)) * radius,
                           point[1] + (x * sin(unit.angle) + y * cos(unit.angle)) * radius) for x, y in shape]
                pygame.draw.polygon(surface, palette.body, points)
                pygame.draw.polygon(surface, color, points, 2)
                # Un marquage de faction net sur une coque claire ou sombre.
                stern = (point[0] - cos(unit.angle) * radius * 0.5, point[1] - sin(unit.angle) * radius * 0.5)
                bow = (point[0] + cos(unit.angle) * radius * 0.65, point[1] + sin(unit.angle) * radius * 0.65)
                pygame.draw.line(surface, color, stern, bow, 2)
            hull_max, shield_max = SHIP_TYPES[unit.ship.model][1:]
            width = max(22, radius * 2)
            x, y = point[0] - width // 2, point[1] - radius - 12
            pygame.draw.rect(surface, (42, 52, 65), (x, y, width, 3))
            pygame.draw.rect(surface, (107, 223, 143), (x, y, round(width * unit.ship.hull / hull_max), 3))
            pygame.draw.rect(surface, (85, 160, 240), (x, y - 5, round(width * unit.ship.shield / shield_max), 2))
        for effect in (battle.effects[-32:] if app.reduced_quality else battle.effects):
            if app.reduced_quality and effect.kind=="debris": continue
            point = camera.screen((effect.x, effect.y))
            if not visible.collidepoint(point):
                continue
            fraction = effect.life / effect.duration
            radius = max(2, round(effect.radius * camera.scale * (1.4 - fraction * 0.4)))
            if effect.kind == "debris":
                pygame.draw.line(surface, (145, 130, 102), point, (point[0] + radius, point[1] - radius), 2)
            else:
                color = (80, 170, 235) if effect.kind == "shield" else (255, 161, 77)
                color = tuple(round(c * fraction) for c in color)
                ui.circle(surface, color, point, radius, 2)
        if controls.drag_start is not None and controls.drag_end is not None:
            start, end = controls.drag_start, controls.drag_end
            rect = pygame.Rect(start, (end[0] - start[0], end[1] - start[1]))
            rect.normalize()
            pygame.draw.rect(surface, (107, 229, 198), rect, 1)
        surface.set_clip(previous_clip)
        ui.panel((16, 16, 1248, 70))
        system = battle.campaign.systems[battle.engagement.system_id]
        ui.text(f"BATAILLE DE {system.name.upper()}", 32, 28, 24)
        counts = Counter(s.owner for s in battle.engagement.initial if battle.ships[s.id].alive)
        ui.text(f"{FACTIONS[battle.player].name} : {counts[battle.player]} unités · {int(battle.elapsed)} s", 32, 58, 14)
        ui.button("battle_pause", "Reprendre" if controls.paused else "Pause", (1000, 30, 110, 40))
        ui.button("battle_menu", "Menu (Échap)", (1120, 30, 127, 40))
        ui.panel((16, 600, 1248, 184))
        chosen = [u for u in battle.living(battle.player) if u.ship.id in controls.selected]
        ui.text(f"{len(chosen)} UNITÉS SÉLECTIONNÉES", 32, 612, 18)
        ui.text(f"Coques {sum(u.ship.hull for u in chosen):.0f} · Boucliers {sum(u.ship.shield for u in chosen):.0f}", 32, 642)
        ui.wrapped(controls.message, 32, 669, 730, 2)
        ui.text("Clic / rectangle · Maj : sélection · Clic droit : ordre · A : attaque-déplacement", 32, 724, 14)
        ui.text("ZQSD / flèches : caméra · S bref : arrêt · H : tenir · Ctrl+1–9 : groupes", 32, 749, 14)
        for i, name in enumerate(FORMATION_NAMES):
            ui.button(f"battle_formation:{i}", name, (836 + i * 135, 615, 126, 34), active=controls.formation == ("line", "wedge", "compact")[i])
        ui.button("battle_select_all", "Toute la flotte", (836, 661, 393, 35))
        ui.button("battle_attack_move", "Attaque-déplacement (A)", (836, 706, 393, 35))
        if battle.finished:
            ui.buttons.clear()
            ui.panel((350, 220, 580, 240))
            label = "ÉGALITÉ" if battle.winner is None else ("VICTOIRE" if battle.winner == battle.player else "DÉFAITE")
            ui.text(label, 382, 247, 38)
            ui.wrapped("Les pertes et dégâts seront conservés. Consultez le rapport avant de reprendre la campagne.", 382, 310, 510, 3)
            ui.button("battle_return", "Voir le rapport de bataille", (382, 398, 510, 40))
        elif controls.menu:
            ui.buttons.clear()
            ui.panel((350, 230, 580, 250))
            ui.text("BATAILLE EN PAUSE", 382, 253, 24)
            ui.button("battle_resume", "Reprendre", (382, 310, 510, 42))
            ui.button("battle_withdraw", "Se replier et quitter la bataille", (382, 370, 510, 42))
            ui.text("Le repli conserve les dégâts et concède le combat.", 382, 440, 14)
