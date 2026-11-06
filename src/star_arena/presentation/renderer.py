from collections import Counter, OrderedDict
from dataclasses import dataclass
from math import atan2, cos, sin
from random import Random
import sys

import pygame
try:
    import pygame.gfxdraw
except ImportError:
    pass  # Certains runtimes Web n’incluent pas cette extension optionnelle.
from star_arena.presentation.art import Painter
from star_arena.presentation.camera import GalaxyGeometry

from star_arena.systems.economy import income, SHIP_COSTS, YARD_COSTS
from star_arena.systems.navigation import remaining_time
from star_arena import __version__
from star_arena.config import TEXT_CACHE_ENTRIES, TEXT_CACHE_PIXELS
from star_arena.domain.models import FACTIONS, SHIP_TYPES

BG = (9, 15, 26)
PANEL = (15, 26, 41)
BORDER = (40, 68, 91)
TEXT = (219, 230, 240)
MUTED = (143, 166, 184)


@dataclass
class Button:
    action: str
    rect: pygame.Rect
    enabled: bool


class Renderer:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.painter = Painter(pygame)
        self._wrap_cache = OrderedDict()
        self.reduced=False
        self._minimap_key = None
        self._minimap_surface = None
        self._galaxy_geometry = GalaxyGeometry()
        self._route_key = None
        self._route_surface = None
        self.fonts = {size: (pygame.font.Font(None, size) if sys.platform == 'emscripten'
                            else pygame.font.SysFont("segoeui,dejavusans,arial", size))
                      for size in (14, 16, 18, 24, 38)}
        self.buttons: list[Button] = []
        self.fleet_points: dict[int, tuple[int, int]] = {}
        self._text_cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()
        self._text_pixels = 0
        self._mouse_position = (0, 0)
        self.battle_renderer = None
        self.background = pygame.Surface(surface.get_size())
        self.background.fill(BG)
        rng = Random(1969)
        haze=pygame.Surface((320,200))
        haze.fill(BG)
        for cx,cy,color in ((85,75,(17,24,43)),(230,105,(21,23,41)),(155,150,(12,29,38))):
            for radius in range(70,0,-3):
                weight=(70-radius)/70
                mixed=tuple(round(BG[i]+(color[i]-BG[i])*weight) for i in range(3))
                pygame.draw.ellipse(haze,mixed,(cx-radius,cy-radius//2,radius*2,radius))
        self.background.blit(pygame.transform.smoothscale(haze,surface.get_size()),(0,0))
        for _ in range(270):
            color = rng.choice(((36, 54, 73), (55, 76, 94), (92, 112, 129)))
            pygame.draw.circle(self.background, color, (rng.randrange(1280), rng.randrange(800)), rng.choice((1,1,1,2)))

    def _fit_text(self, value: str, size: int, width: int | None) -> str:
        font = self.fonts[size]
        if width is None or font.size(value)[0] <= width:
            return value
        ellipsis = "…"
        if width < font.size(ellipsis)[0]:
            return ""
        low, high = 0, len(value)
        while low < high:
            middle = (low + high + 1) // 2
            if font.size(value[:middle] + ellipsis)[0] <= width:
                low = middle
            else:
                high = middle - 1
        return value[:low] + ellipsis

    def text(self, value: str, x: int, y: int, size: int = 16, color=TEXT, width: int | None = None) -> None:
        # Cache borné : les horloges et messages variables ne peuvent pas l'agrandir sans limite.
        key = (value, size, tuple(color), width)
        rendered = self._text_cache.get(key)
        if rendered is None:
            fitted = self._fit_text(value, size, width)
            if not fitted:
                return
            rendered = self.fonts[size].render(fitted, True, color)
            self._text_cache[key] = rendered
            self._text_pixels += rendered.get_width() * rendered.get_height()
            while len(self._text_cache) > (128 if self.reduced else TEXT_CACHE_ENTRIES) or self._text_pixels > (1_000_000 if self.reduced else TEXT_CACHE_PIXELS):
                _, expired = self._text_cache.popitem(last=False)
                self._text_pixels -= expired.get_width() * expired.get_height()
        else:
            self._text_cache.move_to_end(key)
        self.surface.blit(rendered, (x, y))

    def wrapped(self, value: str, x: int, y: int, width: int, lines: int = 3, color=TEXT) -> int:
        key=(value,width,lines)
        output=self._wrap_cache.get(key)
        if output is None:
            output: list[str] = []
            for paragraph in value.split("\n"):
                line = ""
                for word in paragraph.split():
                    if line and self.fonts[16].size(line + " " + word)[0] > width:
                        output.append(line)
                        line = word
                    else:
                        line = f"{line} {word}".strip()
                output.append(line)
            self._wrap_cache[key]=output
            if len(self._wrap_cache)>128: self._wrap_cache.popitem(last=False)
        for i, line in enumerate(output[:lines]):
            self.text(line, x, y + i * 22, color=color, width=width)
        return min(len(output), lines) * 22

    def panel(self, rect: tuple[int, int, int, int]) -> None:
        self.painter.panel(self.surface,rect)

    def circle(self,*args,**kwargs):
        self.painter.circle(*args,**kwargs)

    def button(self, action: str, title: str, rect: tuple[int, int, int, int], enabled: bool = True, active: bool = False) -> None:
        area = pygame.Rect(rect)
        hovered = enabled and area.collidepoint(self._mouse_position)
        fill = (26, 58, 77) if hovered or active else (18, 36, 52)
        pygame.draw.rect(self.surface, fill, area, border_radius=6)
        pygame.draw.rect(self.surface, (62, 165, 191) if active else BORDER, area, 1, border_radius=6)
        self.text(title, area.x + 11, area.y + (area.h - 22) // 2, color=TEXT if enabled else (81, 99, 116), width=area.w - 20)
        self.buttons.append(Button(action, area, enabled))

    def draw(self, app) -> None:
        self.reduced=app.reduced_quality
        self.painter.quality(app.reduced_quality)
        self.buttons.clear()
        self.fleet_points.clear()
        self._mouse_position = pygame.mouse.get_pos()
        self.surface.blit(self.background, (0, 0))
        if app.audio_settings.muted:
            self.text('SON COUPÉ · F8',20,2,14,(245,183,90))
        elif app.audio.error:
            self.text('AUDIO INDISPONIBLE · Paramètres audio',20,2,14,(245,130,100))
        if app.mode.startswith('mp_'):
            from star_arena.presentation.multiplayer_view import draw_multiplayer
            draw_multiplayer(self,app)
        elif app.mode == "menu":
            if app.mp.active:
                from star_arena.presentation.multiplayer_view import draw_session_menu
                draw_session_menu(self,app)
            else: self.menu(app)
        elif app.mode == "battle":
            if self.battle_renderer is None:
                from star_arena.presentation.battle_renderer import BattleRenderer

                self.battle_renderer = BattleRenderer(self)
            self.battle_renderer.draw(app)
        elif app.mode == "system":
            from star_arena.presentation.system_view import draw_system
            draw_system(self, app)
        elif app.mode == "report":
            self.report(app)
        else:
            self.galaxy(app)
            if app.simulation.campaign.pending is not None:
                self.engagement(app)
        if app.mp.active:
            status='Connexion interrompue — état figé' if not app.mp.client.connected else 'Session suspendue — joueur absent' if app.mp.state['paused'] else 'LAN · instantanés de l’hôte'
            self.text(status,260,2,14,(230,183,90))
        if app.admin_open:
            self.admin(app)
        if app.settings_open:
            self.audio_settings(app)
        if app.order_request is not None:
            self.order_menu(app)

    def order_menu(self, app):
        self.buttons.clear(); self.fleet_points.clear()
        source,destination=app.order_request; c=app.simulation.campaign
        self.panel((300,150,680,535))
        self.text(f'ORDRE À LA FLOTTE {source}',330,175,24)
        self.text('Destination : '+c.systems[destination].name,330,216,18)
        self.button('order_confirm:move','Déplacement simple',(330,255,620,36))
        self.button('order_confirm:reinforce','Renfort — conserver les flottes séparées',(330,299,620,36))
        allies=sorted((f for f in c.fleets_at(destination) if f.owner==c.player and f.id!=source
                       and f.ships and f.status=='permanent'),key=lambda f:f.id)
        page=min(app.order_page,max(0,(len(allies)-1)//4))
        for i,fleet in enumerate(allies[page*4:page*4+4]):
            self.button(f'order_confirm:merge:{fleet.id}',f'Fusion à l’arrivée avec flotte {fleet.id} ({len(fleet.ships)} unités)',(330,355+i*43,620,36))
        self.button('order_page:-1','‹',(807,540,62,30),page>0)
        self.button('order_page:1','›',(886,540,62,30),(page+1)*4<len(allies))
        self.text('Clic gauche : sélectionner · Clic droit : ordonner',330,583,16)
        self.button('order_cancel','Annuler — garder la source sélectionnée',(330,628,620,36))

    def audio_settings(self, app) -> None:
        self.buttons.clear()
        self.fleet_points.clear()
        self.panel((300,110,680,600))
        self.text('PARAMÈTRES AUDIO',330,132,38)
        self.button('quality_toggle','F7 : '+('qualité réduite' if app.reduced_quality else 'qualité desktop'),(330,205,620,27))
        self.text('F8 : couper / rétablir tous les sons · Échap : fermer',330,180,16)
        prefs=app.audio_settings
        for i,(key,title) in enumerate((('master','Volume principal'),('music','Volume musique'),('effects','Volume effets'))):
            y=238+i*58
            self.text(f'{title} : {getattr(prefs,key+"_volume"):.0%}',330,y+7,18)
            self.button('audio_volume:'+key+':-1','−',(809,y,62,40))
            self.button('audio_volume:'+key+':1','+',(886,y,62,40))
        self.button('music_toggle','Musique : '+('ACTIVÉE' if prefs.music_enabled else 'DÉSACTIVÉE'),(330,423,620,38))
        self.button('effects_toggle','Effets : '+('ACTIVÉS' if prefs.effects_enabled else 'DÉSACTIVÉS'),(330,469,620,38))
        self.button('sound_toggle','Son général : '+('COUPÉ (F8)' if prefs.muted else 'ACTIF (F8)'),(330,515,620,38))
        self.button('audio_test_effects','Tester effets',(330,559,300,32))
        self.button('audio_test_music','Tester musique',(645,559,305,32))
        count=sum(row['present'] and row['valid_header'] for row in app.music.available.values())
        self.text(f'Pistes présentes : {count}/6 · Mixer : {app.audio.format or 'indisponible'}',330,595,14,width=620)
        error=app.audio_settings_error or app.audio.error or next(iter(app.music.errors.values()),'')
        self.wrapped(error or app.message,330,616,620,1)
        if app.audio.devices:
            self.text('Sorties : '+', '.join(app.audio.devices),330,635,14,width=620)
        self.button('audio_settings_close','Retour au jeu',(330,651,620,39))

    def admin(self, app) -> None:
        self.buttons.clear()
        self.fleet_points.clear()
        self.panel((300,110,680,600))
        self.text('ADMIN — CHEATS',330,132,38)
        self.text('Simulation suspendue · F10 / Échap : fermer · F8 : son',330,191,16)
        campaign=app.simulation.campaign if app.simulation else None
        allowed=campaign is not None and campaign.pending is None
        options=(('resources','+10 000 crédits et minerais'),
                 ('fleet','Créer une flotte dans le système sélectionné'),
                 ('repair','Réparer toutes les unités alliées vivantes'),
                 ('queues','Accélérer les commandes déjà payées'))
        for i,(command,title) in enumerate(options):
            self.button('admin:'+command,title,(330,235+i*49,620,41),allowed)
        self.button('admin:win','Éliminer les ennemis de la bataille RTS',(330,439,620,41),
                    app.mode=='battle' and app.battle is not None and not app.battle.finished)
        self.button('audio_settings','Paramètres audio : musique, effets et volumes',(330,491,620,39))
        self.wrapped(app.message,330,545,620,3)
        if app.audio.error:
            self.text('Audio indisponible : fonctionnement silencieux.',330,612,14)
        self.button('admin_close','Reprendre (F10)',(330,651,620,39))

    def menu(self, app) -> None:
        self.panel((245, 110, 790, 580))
        self.text("S T A R  A R E N A", 290, 145, 38)
        self.text("GALACTIC CONQUEST", 292, 198, 24, (71, 194, 230))
        self.text(f"Campagne et batailles RTS / Pygame CE — {__version__}", 292, 242, color=MUTED)
        self.text("F7 : qualité · F10 : admin · F8 : son", 292, 271, 14, MUTED)
        self.text("CHOISISSEZ VOTRE FACTION", 292, 295, 18)
        for i, faction in enumerate(FACTIONS):
            self.button(f"faction:{i}", faction.name, (292 + i * 237, 333, 225, 44), active=app.faction == i)
        self.wrapped(FACTIONS[app.faction].description, 292, 397, 690, color=FACTIONS[app.faction].color)
        self.button("start", "Nouvelle campagne", (292, 453, 335, 44))
        self.button("load", "Charger (F9)", (645, 453, 335, 44))
        self.button("resume", "Reprendre la campagne", (292, 512, 335, 44), app.simulation is not None)
        self.button("quit", "Quitter", (645, 512, 335, 44))
        self.button("audio_settings", "Paramètres audio", (292, 565, 335, 36))
        self.button("mp_menu", "Multijoueur Web en préparation" if sys.platform == 'emscripten' else "Multijoueur PC / LAN", (645, 565, 335, 36))
        self.wrapped(app.message, 292, 611, 690, lines=2, color=MUTED)

    def galaxy(self, app) -> None:
        c = app.simulation.campaign
        player = FACTIONS[c.player]
        self.panel((16, 16, 1248, 78))
        self.text("STAR ARENA", 32, 27, 24, player.color)
        count = sum(s.owner == c.player for s in c.systems.values())
        self.text(f"{player.name} · {count}/{len(c.systems)} systèmes · {int(c.time) // 60:02}:{int(c.time) % 60:02}", 32, 61, 14)
        stock = c.resources[c.player]
        credits, minerals = income(c, c.player)
        self.text(f"Crédits {stock.credits:.0f} (+{credits}/s)", 360, 27, 16)
        self.text(f"Minerais {stock.minerals:.0f} (+{minerals}/s)", 360, 57, 16)
        self.button("pause", "Reprendre" if app.paused else "Pause", (690, 33, 112, 40), active=app.paused)
        for i, speed in enumerate((1, 2, 4)):
            self.button(f"speed:{speed}", f"×{speed}", (812 + i * 57, 33, 50, 40), active=app.speed == speed)
        self.button("save", "Sauver", (994, 33, 107, 40),not app.mp.active or app.mp.is_host)
        self.button("menu", "Menu", (1113, 33, 130, 40))
        old_clip = self.surface.get_clip()
        self.surface.set_clip(app.camera.viewport)
        selected = c.fleets.get(app.selected_fleet)
        system_points = self._galaxy_geometry.project(c, app.camera)
        route_edges={tuple(sorted(edge)) for edge in zip(selected.itinerary,selected.itinerary[1:])} if selected else set()
        if self._route_key != self._galaxy_geometry.key:
            vx,vy,vw,vh=app.camera.viewport
            layer=pygame.Surface((vw,vh),pygame.SRCALPHA)
            for a,b in self._galaxy_geometry.edges:
                p,q=system_points[a],system_points[b]
                pygame.draw.aaline(layer,(34,60,82),(p[0]-vx,p[1]-vy),(q[0]-vx,q[1]-vy))
            self._route_surface=layer
            self._route_key=self._galaxy_geometry.key
        self.surface.blit(self._route_surface,app.camera.viewport[:2])
        for a, b in self._galaxy_geometry.edges:
            highlighted = selected is not None and selected.travel is None and selected.system_id in (a, b)
            if (a,b) in route_edges or highlighted:
                color = (250,210,100) if (a,b) in route_edges else (69,134,158)
                pygame.draw.aaline(self.surface, color, system_points[a], system_points[b])
        visible = pygame.Rect(app.camera.viewport).inflate(120, 120)
        hovered=app.pick_system(self._mouse_position)
        for system in c.systems.values():
            point = system_points[system.id]
            if not visible.collidepoint(point):
                continue
            color = FACTIONS[system.owner].color if system.owner is not None else MUTED
            if system.owner is not None and not app.reduced_quality:
                self.painter.glow(self.surface,point,color,36 if system.capital else 28)
            self.circle(self.surface, (18, 36, 51), point, 15)
            self.circle(self.surface, color, point, 9)
            self.circle(self.surface, (220, 240, 250), (point[0] - 2, point[1] - 2), 2)
            if system.capital:
                self.circle(self.surface, color, point, 16, 1)
            if system.shipyard or system.richness==4:
                pygame.draw.rect(self.surface,color,(point[0]-3,point[1]-20,6,3))
            if system.id==hovered:
                self.circle(self.surface,(130,165,185),point,20,1)
            if system.id == app.selected_system:
                self.circle(self.surface, (244, 231, 170), point, 24, 2)
            if app.camera.scale>=.35 or system.capital or system.id in (app.selected_system,hovered) or system.shipyard:
                self.text(system.name, point[0] - self.fonts[14].size(system.name)[0] // 2, point[1] + 28, 14, color)
        stacks: dict[int, int] = {}
        for fleet in c.fleets.values():
            if fleet.destroyed:
                continue
            x, y = app.camera.screen(fleet.position(c.systems))
            angle = 0.0
            if fleet.travel is not None:
                a, b = c.systems[fleet.travel.origin].position, c.systems[fleet.travel.destination].position
                angle = atan2(b[1] - a[1], b[0] - a[0])
            else:
                index = stacks.get(fleet.system_id, 0)
                stacks[fleet.system_id] = index + 1
                x += 22 + 18 * index
                y -= 16
            if not visible.collidepoint(x, y):
                continue
            self.fleet_points[fleet.id] = (x, y)
            points = [(x + cos(angle + a) * r, y + sin(angle + a) * r) for a, r in ((0, 10), (2.5, 8), (-2.5, 8))]
            pygame.draw.polygon(self.surface, FACTIONS[fleet.owner].color, points)
            if fleet.id == app.selected_fleet:
                self.circle(self.surface, (245, 231, 160), (x, y), 15, 1)
            self.text(str(len(fleet.ships)), x + 12, y - 9, 14, FACTIONS[fleet.owner].color)
        self.surface.set_clip(old_clip)
        self.sidebar(app)
        self.minimap(app)
        if selected and selected.itinerary:
            self.panel((250,550,635,130))
            state={'transit':'En transit','engaged':'Engagée','arrived':'Arrivée','blocked':'Bloquée'}.get(selected.navigation_state,'En attente')
            eta=remaining_time(c,selected)
            final=c.systems[selected.final_destination].name
            self.text(f'{state} · Destination : {final} · ETA : {eta:.1f}s simulées',265,560,16,width=600)
            self.wrapped('Trajet : '+' → '.join(c.systems[i].name for i in selected.itinerary),265,588,600,3)
            if selected.travel:
                self.text(f'Segment {selected.segment_index+1}/{len(selected.itinerary)-1} : {selected.travel.progress:.0%}',265,655,14)

        for i, faction in enumerate(FACTIONS):
            self.circle(self.surface, faction.color, (31 + i * 290, 703), 4)
            self.text(faction.name, 43 + i * 290, 692, 14, faction.color)
        self.panel((16, 731, 1248, 55))
        self.wrapped(app.message, 30, 739, 1218, 2)

    def sidebar(self, app) -> None:
        c = app.simulation.campaign
        self.panel((912, 110, 352, 605))
        system = c.systems[app.selected_system]
        self.text(system.name + (" · Capitale" if system.capital else ""), 930, 128, 24, width=315)
        self.text(FACTIONS[system.owner].name if system.owner is not None else "Système neutre", 930, 164, color=MUTED)
        neighbors = ", ".join(c.systems[i].name for i in c.neighbors(system.id))
        self.wrapped("Routes : " + neighbors, 930, 194, 313, 2, MUTED)
        self.button("system_open", "Vue détaillée (double-clic)", (930, 690, 314, 24))
        self.button("panel", "Flottes" if app.economy_panel else "Économie / chantier", (930, 235, 208, 30))
        if app.economy_panel:
            self.economy(app, system)
            return
        self.text("", 930, 249, 18)
        fleets = sorted((f for f in c.fleets.values() if f.owner == c.player and f.ships), key=lambda f: f.id)
        selected_index = next((i for i, f in enumerate(fleets) if f.id == app.selected_fleet), 0)
        page = selected_index // 2
        if len(fleets) > 2:
            previous = fleets[(selected_index - 1) % len(fleets)].id
            following = fleets[(selected_index + 1) % len(fleets)].id
            self.button(f"fleet:{previous}", "‹", (1151, 245, 42, 29))
            self.button(f"fleet:{following}", "›", (1201, 245, 42, 29))
        for i, fleet in enumerate(fleets[page * 2:page * 2 + 2]):
            title = f"Flotte {fleet.id} · {len(fleet.ships)} vaisseaux"
            self.button(f"fleet:{fleet.id}", title, (930, 279 + i * 42, 314, 35), active=fleet.id == app.selected_fleet)
        fleet = c.fleets.get(app.selected_fleet)
        y = 279 + min(2, len(fleets)) * 42 + 5
        if fleet is not None:
            location = c.systems[fleet.system_id].name
            if fleet.travel is not None:
                t = fleet.travel
                location = f"Vers {c.systems[t.destination].name} · {max(0, t.duration - t.elapsed):.1f} s"
                pygame.draw.rect(self.surface, BORDER, (930, y + 26, 312, 4))
                pygame.draw.rect(self.surface, FACTIONS[fleet.owner].color, (930, y + 26, round(312 * t.progress), 4))
            self.text(location, 930, y, color=MUTED, width=312)
            counts = Counter(ship.model for ship in fleet.ships)
            for i, (model, amount) in enumerate(counts.items()):
                self.text(f"{amount} × {SHIP_TYPES[model][0]}", 930, y + 42 + i * 22)
            allowed = not app.simulation.movement_error(fleet.id, system.id, c.player)
            self.button("move", "Occuper / déplacer vers ce système", (930, y + 120, 314, 39), allowed)
        self.button("split", "Détacher le dernier vaisseau", (930, 530, 314, 29))
        self.button("transfer_one", "Transférer le dernier vers une alliée", (930, 563, 314, 29))
        self.button("merge", "Fusionner vers une flotte alliée", (930, 596, 314, 29))
        self.button("show_report", "Dernier rapport de bataille", (930, 654, 314, 30), bool(c.reports))


    def economy(self, app, system) -> None:
        c = app.simulation.campaign
        owned = system.owner == c.player and c.pending is None
        self.text(f"Richesse : {system.richness}/4 · +4 crédits/s", 930, 278, 16)
        self.text(f"Minerais : +{(system.richness-1)*2}/s si contrôlé", 930, 302, 16)
        self.text(f"Chantier naval : niveau {system.shipyard}/3", 930, 332, 18)
        if system.shipyard < 3:
            a, b = YARD_COSTS[system.shipyard+1]
            self.button("yard", f"{'Construire' if not system.shipyard else 'Améliorer'} : {a} C / {b} M",
                        (930, 363, 314, 32), owned)
        for i, (model, (a, b, duration, level)) in enumerate(SHIP_COSTS.items()):
            y = 402+i*44
            self.text(f"{SHIP_TYPES[model][0]} · N{level} · {duration} s", 930, y, 14)
            self.text(f"{a} crédits / {b} minerais", 930, y+19, 14, MUTED)
            self.button(f"build:{model}", "Produire", (1140, y, 104, 35),
                        owned and system.shipyard >= level and len(system.queue) < 20)
        self.text(f"File : {len(system.queue)}/20", 930, 540, 16)
        page = min(app.queue_page, max(0, (len(system.queue)-1)//2))
        self.button("queue_page:-1", "‹", (1150, 536, 42, 26), page > 0)
        self.button("queue_page:1", "›", (1200, 536, 42, 26), (page+1)*2 < len(system.queue))
        for i, job in enumerate(system.queue[page*2:page*2+2]):
            total = SHIP_COSTS[job.model][2]
            eta = sum(j.remaining for j in system.queue[:page*2+i+1])
            self.text(f"{page*2+i+1}. {SHIP_TYPES[job.model][0]} · sortie {eta:.0f}s · {(1-job.remaining/total)*100:.0f}%",
                      930, 565+i*23, 14)
        fleets = [f for f in c.fleets_at(system.id) if f.ships]
        self.text(f"Sur place : {len(fleets)} flottes / {sum(len(f.ships) for f in fleets)} unités", 930, 617, 14)
        for i, event in enumerate(c.events[:2]):
            self.text(event, 930, 646+i*24, 14, MUTED, width=310)

    def minimap(self, app) -> None:
        c = app.simulation.campaign
        self.panel((28, 548, 210, 130))
        left, top, right, bottom = app.camera.bounds
        def point(p):
            return (round(36+(p[0]-left)/(right-left)*194), round(556+(p[1]-top)/(bottom-top)*112))
        key=(id(c),tuple((s.id,s.position,s.owner,s.capital) for s in c.systems.values()),frozenset(c.routes),app.camera.bounds)
        if key!=self._minimap_key:
            base=pygame.Surface((210,130),pygame.SRCALPHA)
            for a,b in c.routes:
                p,q=point(c.systems[a].position),point(c.systems[b].position)
                pygame.draw.aaline(base,BORDER,(p[0]-28,p[1]-548),(q[0]-28,q[1]-548))
            for system in c.systems.values():
                color=MUTED if system.owner is None else FACTIONS[system.owner].color
                p=point(system.position)
                self.circle(base,color,(p[0]-28,p[1]-548),3 if system.capital else 2)
            self._minimap_key=key; self._minimap_surface=base
        self.surface.blit(self._minimap_surface,(28,548))
        vx,vy,vw,vh=app.camera.viewport
        a=point(app.camera.world((vx,vy))); b=point(app.camera.world((vx+vw,vy+vh)))
        clip=self.surface.get_clip(); self.surface.set_clip((28,548,210,130))
        pygame.draw.rect(self.surface,(112,143,162),(a[0],a[1],max(1,b[0]-a[0]),max(1,b[1]-a[1])),1)
        self.surface.set_clip(clip)
        self.circle(self.surface, TEXT, point(app.camera.center), 5, 1)
        self.button("capital", "Centrer capitale", (28, 511, 210, 30))

    def engagement(self, app) -> None:
        c = app.simulation.campaign
        pending = c.pending
        self.buttons.clear()
        self.panel((310, 190, 660, 410))
        if app.mp.active:
            self.text("RTS interactif : solo · Les autres joueurs attendent le résultat commun.",340,577,14,width=600)
        self.text("CONFLIT ORBITAL", 340, 214, 38)
        self.text(c.systems[pending.system_id].name, 340, 275, 24)
        self.wrapped(f"{FACTIONS[pending.attacker].name} attaque {FACTIONS[pending.defender].name}.", 340, 320, 600, 2)
        self.text(f"{len(pending.initial)} vaisseaux engagés · Campagne suspendue", 340, 372)
        self.button("enter_battle", "Commander la bataille RTS", (340, 416, 600, 42), not app.mp.active and c.player in (pending.attacker, pending.defender))
        self.button("auto_battle", "Résolution automatique par l’hôte" if app.mp.active else "Résolution automatique", (340, 474, 600, 42),not app.mp.active or app.mp.is_host or c.player in (pending.attacker,pending.defender))
        self.button("save", "Sauvegarder avant la bataille", (340, 532, 600, 42))

    def report(self, app) -> None:
        report = app.report
        c = app.simulation.campaign
        self.panel((120, 44, 1040, 710))
        self.text("RAPPORT DE BATAILLE", 150, 65, 38)
        self.text(c.systems[report.system_id].name, 150, 126, 24)
        winner = FACTIONS[report.winner].name if report.winner is not None else "Égalité"
        self.text("Vainqueur : " + winner, 150, 171, 18)
        if report.retreat:
            self.text("Retraite volontaire : le combat a été concédé.", 150, 203, color=MUTED)
        self.text("FACTION", 150, 247, 18)
        self.text("ENGAGÉS", 610, 247, 18)
        self.text("DÉTRUITS", 735, 247, 18)
        self.text("SURVIVANTS", 860, 247, 18)
        self.text("CAPTURÉS", 1020, 247, 18)
        for row, owner in enumerate((report.attacker, report.defender)):
            y = 289 + row * 40
            self.text(FACTIONS[owner].name, 150, y, 18, FACTIONS[owner].color)
            for x, counts in ((610, report.engaged), (735, report.destroyed), (860, report.survivors), (1020, report.captured)):
                self.text(str(counts[owner]), x, y, 18)
        result = "Territoire conservé."
        if report.previous_owner != report.new_owner:
            result = ("Système conquis par " + FACTIONS[report.new_owner].name + ".") if report.new_owner is not None else "Système redevenu neutre."
        self.wrapped(result, 150, 383, 970, 2)
        self.text("ÉTAT DES CROISEURS", 150, 435, 18)
        current_ids = {s.id for f in c.fleets.values() for s in f.ships}
        start = app.report_page * 6
        for i, cruiser in enumerate(report.cruisers[start:start + 6]):
            state = ("Détruit" if cruiser.hull <= 0 else "Capturé" if cruiser.id not in current_ids
                     else f"Coque {cruiser.hull:.0f} · Bouclier {cruiser.shield:.0f}")
            self.text(f"#{cruiser.id} · {FACTIONS[cruiser.owner].name} · {state}", 150, 473 + i * 26, 16, width=970)
        if len(report.cruisers) > 6:
            self.button("report_page:-1", "‹", (950, 430, 75, 29), app.report_page > 0)
            self.button("report_page:1", "›", (1040, 430, 75, 29), start + 6 < len(report.cruisers))
        self.button("report_return", "Retour à la galaxie", (150, 684, 590, 42))
        self.button("save", "Sauvegarder (F5)", (760, 684, 370, 42))
        self.wrapped(app.message if app.message.startswith("Sauvegarde") or app.message.startswith("Campagne sauvegardée") else "", 150, 732, 970, 1, MUTED)
