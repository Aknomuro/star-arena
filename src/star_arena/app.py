"""Le seul point de démarrage de la fenêtre ; jamais exécuté à l'import."""
from pathlib import Path
import os
import sys
import asyncio

from star_arena.network.replica import CampaignReplica
from star_arena.web import BrowserBridge, BrowserStore, WebMultiplayer, encode_campaign, poll_browser
from star_arena.presentation.audio import SoundEffects
from star_arena.presentation.audio_settings import AudioSettings, load_settings, save_settings
from star_arena.presentation.music import MusicManager
from star_arena.systems.admin import apply_cheat
from star_arena import __version__
from star_arena.config import BACKGROUND_FPS_LIMIT, FPS_LIMIT, GALAXY_SEED, WINDOW_SIZE, default_save_path
from star_arena.domain.galaxy import new_campaign
from star_arena.domain.models import BattleReport, Campaign, Point
from star_arena.persistence import load_campaign, save_campaign
from star_arena.presentation.camera import Camera
from star_arena.systems.simulation import Simulation
from star_arena.systems.economy import yard_order, transfer
from star_arena.systems.planets import build
from star_arena.presentation.system_view import pick_planet
from star_arena.systems.combat import auto_resolve
from star_arena.systems.tactical import BattleEngine

HELP = "F7 : qualité · F10 : admin · F8 : son · Clic : sélectionner · Clic droit : déplacer · Tab : flotte · Espace : pause · Molette : zoom · Souris hors centre : caméra · Glisser milieu : carte · F : centrer · F5/F9 : sauvegarde"


class Application:
    def __init__(self, pygame, renderer, save_path: Path) -> None:
        self.audio = SoundEffects()
        self.music = MusicManager()
        self.audio_settings = AudioSettings()
        self.audio_settings_path = None
        self.audio_settings_error = ''
        self.settings_open = False
        self.needs_audio_unlock = sys.platform=="emscripten"
        self.browser = None
        self.browser_store = None
        self.reduced_quality = sys.platform=="emscripten"
        self.order_request = None
        self.order_page = 0
        self.admin_open = False
        self.sound_projectiles = set()
        self.sound_effects = set()
        self.sound_event = None
        self.sound_mode = None
        self.sound_counts = {}
        self.sound_battle_id = None
        self.sound_known_events = set()
        self.pg = pygame
        self.renderer = renderer
        self.save_path = save_path
        self.camera = Camera()
        self.simulation: Simulation | CampaignReplica | None = None
        self.mode = "menu"
        self.faction = 0
        self.selected_system = 0
        self.selected_fleet = -1
        self.paused = False
        self.speed = 1
        self.planet_queue_page = 0
        self.selected_planet = -1
        self.system_category = 'economy'
        self.system_camera = Camera(center=(0.,0.),scale=.65,bounds=(-500.,-500.,500.,500.))
        self.last_system_click = (-1,-1000)
        self.queue_page = 0
        self.economy_panel = True
        self.running = True
        self.focused = True
        self.battle: BattleEngine | None = None
        self.battle_controls = None
        self.report: BattleReport | None = None
        self.report_page = 0
        if sys.platform == 'emscripten':
            self.mp = WebMultiplayer()
        else:
            from star_arena.network.controller import Multiplayer
            self.mp = Multiplayer(self)
        self.message = "60 systèmes, trois factions, routes et occupation des systèmes neutres. Choisissez une faction puis commencez."

    def _change_mode(self, mode: str) -> None:
        self.mode = mode
        # Ne pas appliquer les zones de clic de l'ancien écran aux événements suivants.
        self.renderer.buttons.clear()
        self.renderer.fleet_points.clear()

    def begin(self, campaign: Campaign, *, view_only: bool=False) -> None:
        self.order_request=None
        self.admin_open = False
        self.simulation = CampaignReplica(campaign) if view_only else Simulation(campaign)
        self.battle = self.battle_controls = self.report = None
        self.faction = campaign.player
        self.selected_fleet = next((f.id for f in campaign.fleets.values() if f.owner == campaign.player and f.ships), -1)
        self.selected_system = next((s.id for s in campaign.systems.values() if s.owner == campaign.player and s.capital), 0)
        points = [s.position for s in campaign.systems.values()]
        self.camera = Camera(center=campaign.systems[self.selected_system].position,
                             bounds=(min(p[0] for p in points)-250, min(p[1] for p in points)-250,
                                     max(p[0] for p in points)+250, max(p[1] for p in points)+250))
        left=min(p[0] for p in points); right=max(p[0] for p in points)
        top=min(p[1] for p in points); bottom=max(p[1] for p in points)
        self.camera.center=((left+right)/2,(top+bottom)/2)
        self.camera.scale=max(.12,min(.58,840/(right-left+200),540/(bottom-top+200)))
        self._change_mode("galaxy")
        self.paused = False
        self.speed = 1
        self.message = HELP

    def action(self, action: str) -> None:
        self.audio.play('click')
        if sys.platform == 'emscripten' and action in ('save', 'load') and self.browser_store is None:
            self.message = 'Stockage navigateur indisponible. Exportez votre campagne JSON avant de fermer.'
            return
        if self.browser_store is not None and action == 'save' and self.simulation is None:
            self.message = 'Aucune campagne à sauvegarder. Commencez ou importez une campagne.'
            return
        if action == 'web_admin':
            if self.mp.client is not None:
                self.message = 'Admin désactivé en multijoueur.'
                return
            self.admin_open = not self.admin_open
            self.renderer.buttons.clear()
            return
        if action == 'web_export':
            try:
                if self.browser is None or self.simulation is None:
                    raise ValueError('Aucune campagne à exporter.')
                if self.mode == 'battle':
                    raise ValueError('Terminer la bataille RTS avant l’export.')
                self.browser.call('download', encode_campaign(self.simulation.campaign))
                self.message = 'Export JSON demandé au navigateur ; vérifiez vos téléchargements.'
            except (OSError, ValueError, RecursionError) as error:
                self.message = 'Export impossible : ' + str(error)
            return
        if self.browser_store is not None and action in ('save', 'load') and self.mode == 'battle':
            self.message = 'Terminer la bataille RTS avant de sauvegarder ou charger.'
            return
        if action.startswith('mp_'):
            self.multiplayer_action(action)
            return
        if self.mp.client is not None and (action.startswith('admin:') or action in ('start','load')):
            self.message='Action solo/admin désactivée pendant une session multijoueur.'
            return
        if self.mp.active:
            if self.network_action(action): return
        if action=='quality_toggle':
            self.reduced_quality=not self.reduced_quality
            if self.battle is not None: self.battle.reduced_quality=self.reduced_quality
            self.message='Qualité réduite : effets limités, rotations regroupées.' if self.reduced_quality else 'Qualité desktop rétablie.'
        elif action=='order_cancel':
            self.order_request=None
            self.renderer.buttons.clear()
        elif action.startswith('order_page:'):
            self.order_page=max(0,self.order_page+int(action.split(':')[1]))
        elif action.startswith('order_confirm:'):
            _,mode,*target=action.split(':')
            self.confirm_move(mode,int(target[0]) if target else None)
        elif action in ('audio_test_effects','audio_test_music'):
            channel='effects' if action=='audio_test_effects' else 'music'
            if self.audio_settings.gain(channel)<=0:
                self.message='Test impossible : son coupé, canal désactivé ou volume nul. Vérifiez F8 et les volumes.'
            else:
                self.configure_audio(persist=False)
                if self.audio.error:
                    self.message='Périphérique audio indisponible : '+self.audio.error
                elif channel=='effects':
                    self.audio.play('complete')
                    self.message='Test effet demandé. Confirmez le son à l’écoute.'
                else:
                    self.music.retry_device()
                    self.update_music(0.)
                    self.message='Test musique demandé pour cette vue. Confirmez le son à l’écoute.'
        elif action=='audio_settings':
            self.settings_open=True
            self.renderer.buttons.clear()
            self.renderer.fleet_points.clear()
        elif action=='audio_settings_close':
            self.settings_open=False
            self.renderer.buttons.clear()
        elif action.startswith('audio_volume:'):
            _,channel,change=action.split(':')
            if channel not in ('master','music','effects') or change not in ('-1','1'):
                return
            key=channel+'_volume'
            setattr(self.audio_settings,key,round(max(0.,min(1.,getattr(self.audio_settings,key)+int(change)*.1)),2))
            self.configure_audio()
        elif action in ('music_toggle','effects_toggle'):
            key='music_enabled' if action=='music_toggle' else 'effects_enabled'
            setattr(self.audio_settings,key,not getattr(self.audio_settings,key))
            self.configure_audio()
        elif action == 'admin_close':
            self.admin_open = False
            self.renderer.buttons.clear()
        elif action == 'sound_toggle':
            self.audio_settings.muted=not self.audio_settings.muted
            self.configure_audio()
            self.message='Tous les sons sont coupés (F8).' if self.audio_settings.muted else 'Son rétabli selon vos préférences.'
            if self.audio.error:
                self.message='Audio indisponible : '+self.audio.error
        elif action.startswith('admin:'):
            if not self.admin_open or self.simulation is None:
                return
            command=action.split(':')[1]
            if command=='win':
                if self.mode!='battle' or self.battle is None or self.battle.finished:
                    self.message='Ce cheat nécessite une bataille RTS en cours.'
                else:
                    for record in self.battle.engagement.initial:
                        if record.owner!=self.battle.player:
                            ship=self.battle.ships[record.id]
                            if record.id in self.battle.units:
                                self.battle.damage(record.id,ship.hull+ship.shield)
                            else:
                                ship.receive_damage(ship.hull+ship.shield)
                    self.battle.advance(.1)
                    self.battle_action('battle_return')
                    self.message='ADMIN : forces ennemies éliminées, résultat appliqué.'
                    self.simulation.campaign.log(self.message)
            else:
                self.message=apply_cheat(self.simulation.campaign,command,self.selected_system)
        elif action == "quit":
            self.running = False
        elif action.startswith("faction:"):
            self.faction = int(action.split(":")[1])
        elif action == "start":
            self.begin(new_campaign(self.faction, GALAXY_SEED))
        elif action == "resume" and self.simulation:
            self.faction = self.simulation.campaign.player
            self._change_mode("galaxy")
            self.message = "Simulation en pause." if self.paused else HELP
        elif action == "menu":
            self._change_mode("menu")
            self.message = ("Campagne suspendue. Reprendre conserve l'état ; Nouvelle campagne le remplace sans sauvegarde automatique."
                            if self.simulation is not None else "Choisissez une faction puis commencez une campagne.")
        elif action == "load":
            try:
                campaign = self.browser_store.load() if self.browser_store is not None else load_campaign(self.save_path)
                self.begin(campaign)
                self.message = "Campagne rechargée, y compris les trajets en cours."
            except (OSError, ValueError, RecursionError) as error:
                self.message = f"Chargement impossible : {error}"
        elif action == "enter_battle" and self.simulation is not None:
            pending = self.simulation.campaign.pending
            if pending is not None and self.simulation.campaign.player in (pending.attacker, pending.defender):
                from star_arena.presentation.battle_input import BattleControls

                self.battle = BattleEngine(self.simulation.campaign, pending)
                self.battle.reduced_quality=self.reduced_quality
                self.battle_controls = BattleControls(self.pg, self.battle)
                self._change_mode("battle")
        elif action == "auto_battle" and self.simulation is not None:
            self.report = auto_resolve(self.simulation.campaign)
            self.report_page = 0
            self._change_mode("report")
        elif action == "show_report" and self.simulation is not None and self.simulation.campaign.reports:
            self.report = self.simulation.campaign.reports[0]
            self.report_page = 0
            self._change_mode("report")
        elif action.startswith("report_page:") and self.report is not None:
            last = max(0, (len(self.report.cruisers) - 1) // 6)
            self.report_page = max(0, min(last, self.report_page + int(action.split(":")[1])))
        elif action == "report_return" and self.simulation is not None:
            if self.report is not None:
                self.selected_system = self.report.system_id
            selected = self.simulation.campaign.fleets.get(self.selected_fleet)
            if selected is None or selected.destroyed:
                self.selected_fleet = next((f.id for f in self.simulation.campaign.fleets.values()
                                            if f.owner == self.simulation.campaign.player and f.ships), -1)
            self.battle = self.battle_controls = None
            self._change_mode("galaxy")
            self.message = "Rapport enregistré. Les pertes, dégâts et territoires sont conservés."
        elif self.simulation is not None:
            if action=='system_open':
                self.open_system(self.selected_system)
            elif action=='system_return':
                self._change_mode('galaxy')
            elif action.startswith('category:'):
                self.system_category=action.split(':')[1]
            elif action.startswith('planet_queue:'):
                self.planet_queue_page=max(0,self.planet_queue_page+int(action.split(':')[1]))
            elif action.startswith('planet_build:'):
                self.message=build(self.simulation.campaign,self.selected_system,self.selected_planet,
                                   action.split(':')[1],self.simulation.campaign.player) or 'Construction commandée.'
                if self.message=='Construction commandée.': self.audio.play("complete")
            elif action.startswith("queue_page:"):
                self.queue_page = max(0, self.queue_page + int(action.split(":")[1]))
            elif action == "panel":
                self.economy_panel = not self.economy_panel
            elif action == "capital":
                capital = next((s for s in self.simulation.campaign.systems.values()
                                if s.capital and s.owner == self.simulation.campaign.player), None)
                if capital:
                    self.camera.center = capital.position
            elif action == "yard" or action.startswith("build:"):
                self.message = yard_order(self.simulation.campaign, self.selected_system,
                                          self.simulation.campaign.player,
                                          action.split(":")[1] if ":" in action else None) or "Commande acceptée."
                if self.message=="Commande acceptée.": self.audio.play("complete")
            elif action in ("split", "merge", "transfer_one"):
                c = self.simulation.campaign
                source = c.fleets.get(self.selected_fleet)
                if source is not None:
                    target = next((f for f in c.fleets_at(source.system_id)
                                   if f.owner == c.player and f.id != source.id and f.ships), None)
                    ids = [source.ships[-1].id] if source.ships and action != "merge" else None
                    if action != "split" and target is None:
                        self.message = "Aucune autre flotte alliée immobile dans ce système."
                    else:
                        self.message = transfer(c, source.id, None if action == "split" else target.id,
                                                c.player, ids) or "Vaisseaux transférés sans duplication."
            elif action == "pause":
                self.paused = not self.paused
                self.message = "Simulation en pause." if self.paused else HELP
            elif action.startswith("speed:"):
                self.speed = int(action.split(":")[1])
            elif action.startswith("fleet:"):
                fleet_id = int(action.split(":")[1])
                fleet = self.simulation.campaign.fleets.get(fleet_id)
                if fleet is None or fleet.owner != self.simulation.campaign.player:
                    return
                self.selected_fleet = fleet_id
                self.selected_system = fleet.system_id
            elif action == "move":
                self.request_move(self.selected_system)
            elif action == "save":
                try:
                    if self.browser_store is not None:
                        self.browser_store.save(self.simulation.campaign)
                        self.message = 'Campagne enregistrée dans le stockage local du navigateur. Export JSON conseillé.'
                    else:
                        save_campaign(self.simulation.campaign, self.save_path)
                        self.message = "Campagne sauvegardée : " + str(self.save_path)
                except (OSError, ValueError, RecursionError) as error:
                    self.message = f"Sauvegarde refusée : {error}"

    def multiplayer_action(self,action):
        if sys.platform == 'emscripten':
            self.message = 'Multijoueur Web en préparation'
            return
        if action in ('mp_menu','mp_create_form','mp_join_form','mp_lobby'):
            if action=='mp_menu' and self.mp.client:
                self._change_mode('mp_lobby' if not self.mp.active else 'menu')
            else: self._change_mode(action)
        elif action=='mp_solo':
            if self.mp.client is None: self._change_mode('menu')
        elif action=='mp_host': self.mp.launch(self.mp.host())
        elif action=='mp_load_host': self.mp.launch(self.mp.host(load=True))
        elif action=='mp_join': self.mp.launch(self.mp.join())
        elif action=='mp_join_fresh': self.mp.launch(self.mp.join(fresh=True))
        elif action=='mp_leave': self.mp.request_leave()
        elif action=='mp_save_leave': self.mp.request_leave(save=True)
        elif action in ('mp_copy_invite','mp_copy_personal'):
            value=self.mp.server.authority.invite if action=='mp_copy_invite' and self.mp.server else self.mp.private_invite
            try:
                self.pg.scrap.init(); self.pg.scrap.put(self.pg.SCRAP_TEXT,value.encode('utf-8')+b'\0')
                self.mp.status='Clé copiée : transmettre uniquement au joueur invité.'
            except (AttributeError,self.pg.error): self.mp.status='Copie indisponible ; relever la clé affichée.'
        elif action=='mp_start': self.mp.send('start')
        elif action.startswith('mp_field:'): self.mp.focus=action.split(':')[1]
        elif action.startswith('mp_faction:'): self.mp.send('faction',{'faction':int(action.split(':')[1])})
        elif action.startswith('mp_size:'): self.mp.send('size',{'size':int(action.split(':')[1])})
        elif action.startswith('mp_reinvite:'): self.mp.send('reinvite',{'participant':action.split(':')[1]})

    def network_action(self,action):
        c=self.simulation.campaign if self.simulation else None
        if action=='enter_battle':
            self.message='RTS interactif réservé au solo ; utiliser la résolution automatique de l’hôte.'
        elif action=='auto_battle': self.mp.send('auto_battle')
        elif action=='save': self.mp.send('save')
        elif action=='pause': self.mp.send('pause')
        elif action.startswith('speed:'): self.mp.send('speed',{'speed':int(action.split(':')[1])})
        elif action=='yard' or action.startswith('build:'):
            args={'system':self.selected_system}
            if ':' in action: args['model']=action.split(':')[1]
            self.mp.send('yard',args)
        elif action.startswith('planet_build:'):
            self.mp.send('building',{'system':self.selected_system,'planet':self.selected_planet,'kind':action.split(':')[1]})
        elif action in ('split','merge','transfer_one'):
            source=c.fleets.get(self.selected_fleet) if c else None
            if source is None or not source.ships:
                self.message='Sélectionnez une flotte.'
            else:
                target=next((f for f in c.fleets_at(source.system_id) if f.owner==c.player and f.id!=source.id and f.ships and f.status=='permanent'),None)
                if action!='split' and target is None:
                    self.message='Aucune flotte alliée cible sur place.'
                else:
                    self.mp.send('transfer',{'source':source.id,'destination':None if action=='split' else target.id,
                                            'ships':None if action=='merge' else [source.ships[-1].id]})
        else: return False
        return True

    def multiplayer_event(self,event):
        pg=self.pg
        if self._ui_click(event): return
        if event.type==getattr(pg,'TEXTINPUT',-110):
            value=self.mp.fields.get(self.mp.focus,'')
            self.mp.fields[self.mp.focus]=''.join(c for c in value+event.text if c.isprintable())[:128]
        elif event.type==pg.KEYDOWN:
            if event.key==pg.K_ESCAPE:
                self._change_mode('menu' if self.mp.active else 'mp_menu')
            elif event.key==getattr(pg,'K_v',-113) and getattr(event,'mod',0)&getattr(pg,'KMOD_CTRL',0):
                try:
                    pg.scrap.init(); raw=pg.scrap.get(pg.SCRAP_TEXT) or b''
                    value=raw.decode('utf-8',errors='ignore').rstrip('\0')
                    self.mp.fields[self.mp.focus]=''.join(c for c in self.mp.fields.get(self.mp.focus,'')+value if c.isprintable())[:128]
                except (AttributeError,pg.error): self.mp.status='Collage indisponible.'
            elif event.key==getattr(pg,'K_BACKSPACE',-111):
                self.mp.fields[self.mp.focus]=self.mp.fields.get(self.mp.focus,'')[:-1]
            elif event.key==getattr(pg,'K_TAB',-112):
                fields=['name','party','bind','port','seed'] if self.mode=='mp_create_form' else ['name','address','port','invite','reconnect']
                self.mp.focus=fields[(fields.index(self.mp.focus)+1)%len(fields)] if self.mp.focus in fields else fields[0]

    def open_system(self, system_id: int) -> None:
        if self.simulation is None or system_id not in self.simulation.campaign.systems:
            return
        self.selected_system=system_id
        self.selected_planet=self.simulation.campaign.systems[system_id].planets[0].id
        self.system_camera=Camera(center=(0.,0.),scale=.65,bounds=(-500.,-500.,500.,500.))
        self._change_mode('system')
        self.message='Clic planète : gérer · Molette : zoom · Échap : galaxie. Production livrée en orbite dans une flotte permanente.'

    def advance_campaign(self, dt: float) -> None:
        if self.mp.active: return
        """Même porte d'entrée testable pour pause, focus, menus et accélération."""
        if self.order_request is None and not self.admin_open and not self.settings_open and self.focused and self.mode in ("galaxy","system") and not self.paused and self.simulation is not None:
            selected=self.simulation.campaign.fleets.get(self.selected_fleet)
            merge_target=selected.merge_target if selected else None
            merge_mode=selected.arrival_mode if selected else None
            self.simulation.advance(dt * self.speed)
            if selected and selected.navigation_state=='merged' and merge_target in self.simulation.campaign.fleets:
                self.selected_fleet=merge_target
                self.selected_system=self.simulation.campaign.fleets[merge_target].system_id
                self.message=f'Fusion terminée : flotte {merge_target} sélectionnée.'
            elif selected and merge_mode=='merge' and selected.navigation_state=='arrived' and selected.arrival_mode=='move':
                self.message='Flotte arrivée sans fusion : cible indisponible.'
            if self.mode=='system' and self.simulation.campaign.pending is not None:
                self.selected_system=self.simulation.campaign.pending.system_id
                self._change_mode('galaxy')

    def request_move(self, destination: int) -> None:
        if self.simulation is None: return
        c=self.simulation.campaign
        error=self.simulation.movement_error(self.selected_fleet,destination,c.player)
        if error:
            self.message=error; return
        allies=[f for f in c.fleets_at(destination) if f.owner==c.player and f.ships
                and f.status=='permanent' and f.id!=self.selected_fleet]
        if allies:
            self.order_request=(self.selected_fleet,destination)
            self.order_page=0
            self.renderer.buttons.clear(); self.renderer.fleet_points.clear()
        else:
            self.move_to(destination)

    def confirm_move(self, mode: str, target: int | None=None) -> None:
        if not self.order_request or not self.simulation: return
        if mode not in ("move","reinforce","merge") or (mode=="merge" and target is None): return
        source,destination=self.order_request
        c=self.simulation.campaign
        if self.mp.active:
            args={'fleet':source,'destination':destination,'mode':mode}
            if target is not None: args['target']=target
            self.mp.send('move',args)
            self.order_request=None; self.renderer.buttons.clear()
            self.message='Ordre envoyé à l’hôte ; en attente de validation.'
            return
        error=self.simulation.order_move(source,destination,c.player)
        if not error:
            fleet=c.fleets[source]
            fleet.arrival_mode=mode; fleet.merge_target=target
            self.simulation.finish_arrival(fleet)
            if fleet.navigation_state=="merged" and target in c.fleets:
                self.selected_fleet=target
            self.audio.play('order')
        self.message=error or 'Ordre confirmé ; source conservée, trajet automatique.'
        self.order_request=None
        self.renderer.buttons.clear()

    def destination_at(self, point) -> int | None:
        """Un clic droit sur une icône décalée vise son système, jamais une sélection."""
        if not self.simulation: return None
        c=self.simulation.campaign
        for uid,xy in self.renderer.fleet_points.items():
            f=c.fleets.get(uid)
            if f and f.travel is None and (point[0]-xy[0])**2+(point[1]-xy[1])**2<=18**2:
                return f.system_id
        return self.pick_system(point)

    def move_to(self, system_id: int) -> None:
        if self.simulation is None:
            return
        if self.mp.active:
            self.mp.send('move',{'fleet':self.selected_fleet,'destination':system_id})
            self.message='Déplacement envoyé à l’hôte.'
            return
        error = self.simulation.order_move(self.selected_fleet, system_id, self.simulation.campaign.player)
        self.message = error or "Ordre reçu. Itinéraire automatique calculé."
        if not error:
            self.audio.play("order")

    def battle_action(self, action: str) -> None:
        if self.battle is None or self.battle_controls is None:
            return
        controls = self.battle_controls
        if action == "battle_pause":
            controls.paused = not controls.paused
        elif action == "battle_menu":
            controls.menu = True
        elif action == "battle_resume":
            controls.menu = False
        elif action == "battle_select_all":
            controls.select_all()
        elif action == "battle_attack_move":
            controls.attack_pending = True
            controls.message = "Cliquez sur la destination de l'attaque-déplacement."
        elif action.startswith("battle_formation:"):
            controls.set_formation(int(action.split(":")[1]))
        elif action in ("battle_return", "battle_withdraw"):
            if action == "battle_withdraw":
                self.battle.withdraw()
            if self.battle.finished:
                self.report = self.battle.commit()
                self.report_page = 0
                self._change_mode("report")

    def configure_audio(self, persist: bool = True) -> None:
        if self.needs_audio_unlock:
            return
        prefs=self.audio_settings
        active=not prefs.muted
        # Le mixer est partagé ; la musique peut fonctionner sans les effets.
        if active and (prefs.music_enabled or prefs.effects_enabled):
            ready=self.audio.set_enabled(True)
            if ready and self.music.failed:
                self.music.retry_device()
        self.audio.set_volume(.4*prefs.gain('effects'))
        if not active or not prefs.effects_enabled:
            self.audio.set_enabled(False)
        self.music.configure(active and prefs.music_enabled,prefs.gain('music'))
        if persist and (self.audio_settings_path is not None or self.browser_store is not None):
            try:
                if self.browser_store is not None:
                    self.browser_store.save_preferences(prefs)
                else:
                    save_settings(prefs,self.audio_settings_path)
                self.audio_settings_error=''
            except (OSError,ValueError,RecursionError) as error:
                self.audio_settings_error='Préférences non enregistrées : '+str(error)

    def update_music(self, dt: float) -> None:
        category=self.mode if self.mode in ('menu','galaxy','system','battle') else 'galaxy'
        token=None
        result=None
        if self.mode=='report':
            result=self.report
        elif self.mode=='battle' and self.battle is not None and self.battle.finished:
            result=self.battle
        if result is not None and self.simulation is not None and result.winner is not None:
            category='victory' if result.winner==self.simulation.campaign.player else 'defeat'
            token=result.id if self.mode=='report' else self.battle.engagement.id
        started=getattr(self.audio,'last_started',None)
        pg=getattr(self.audio,'backend',None)
        self.music.ducking=bool(started is not None and pg is not None and pg.time.get_ticks()-started<300)
        self.music.request(category,token)
        self.music.suspend(not self.focused)
        self.music.update(dt)

    def feedback(self) -> None:
        """Observer les événements visuels ; aucune dépendance audio dans la simulation."""
        if self.mode=='battle' and self.battle is not None:
            battle_id=id(self.battle)
            if self.sound_battle_id!=battle_id:
                self.sound_counts={}; self.sound_battle_id=battle_id
            for name,count in self.battle.event_counts.items():
                if count>self.sound_counts.get(name,0):
                    self.audio.play(name)
            self.sound_counts=dict(self.battle.event_counts)
        else:
            self.sound_counts={}; self.sound_battle_id=None
        if self.mode=='report' and self.sound_mode!='report':
            self.audio.play('complete')
        self.sound_mode=self.mode
        if self.simulation:
            events=set(self.simulation.campaign.events)
            if any('terminé' in e or 'achevée' in e for e in events-self.sound_known_events):
                self.audio.play('complete')
            self.sound_known_events=events

    def _ui_click(self, event) -> bool:
        if event.type == self.pg.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.renderer.buttons:
                if button.rect.collidepoint(event.pos):
                    if button.enabled:
                        self.action(button.action)
                    return True
        return False

    def pick_system(self, point: Point) -> int | None:
        if self.simulation is None:
            return None
        c = self.simulation.campaign
        best, best_distance = None, 25**2
        for system in c.systems.values():
            x, y = self.camera.screen(system.position)
            distance = (x - point[0])**2 + (y - point[1])**2
            if distance <= best_distance:
                best, best_distance = system.id, distance
        return best

    def event(self, event) -> None:
        pg = self.pg
        if self.needs_audio_unlock and event.type in (pg.KEYDOWN,pg.MOUSEBUTTONDOWN):
            self.needs_audio_unlock=False
            self.configure_audio(persist=False)
        if event.type == pg.QUIT:
            self.running = False
            return
        if event.type in (pg.WINDOWFOCUSLOST, pg.WINDOWMINIMIZED):
            self.audio.stop()
            self.music.suspend(True)
            self.focused = False
            if self.battle_controls is not None:
                self.battle_controls.drag_start = self.battle_controls.drag_end = None
                self.battle_controls.s_pressed_at = None
            return
        if event.type == pg.WINDOWFOCUSGAINED:
            self.focused = True
            return
        if not self.focused:
            return
        if event.type==pg.KEYDOWN and event.key==getattr(pg,'K_F7',-102):
            self.action('quality_toggle')
            return
        if event.type==pg.KEYDOWN and event.key==getattr(pg,'K_F8',-100):
            self.action('sound_toggle')
            return
        if event.type==pg.KEYDOWN and event.key==getattr(pg,'K_F10',-101):
            if self.mp.client is not None:
                self.message='F10 désactivé en multijoueur.'
                return
            self.admin_open=not self.admin_open
            self.renderer.buttons.clear()
            self.renderer.fleet_points.clear()
            if self.battle_controls is not None:
                self.battle_controls.drag_start=self.battle_controls.drag_end=None
                self.battle_controls.s_pressed_at=None
                self.battle_controls.attack_pending=False
            return
        if self.order_request is not None:
            if event.type==pg.KEYDOWN and event.key==pg.K_ESCAPE:
                self.action('order_cancel')
            else:
                self._ui_click(event)
            return
        if self.settings_open:
            if event.type==pg.KEYDOWN and event.key==pg.K_ESCAPE:
                self.action('audio_settings_close')
            else:
                self._ui_click(event)
            return
        if self.admin_open:
            if event.type==pg.KEYDOWN and event.key==pg.K_ESCAPE:
                self.action('admin_close')
            else:
                self._ui_click(event)
            return
        if self.mode.startswith('mp_'):
            self.multiplayer_event(event)
            return
        if self.mode == "battle" and self.battle_controls is not None:
            self.battle_controls.handle(event, self)
            return
        if self.mode=='system':
            if event.type==pg.KEYDOWN:
                if event.key==pg.K_ESCAPE: self.action('system_return')
                elif event.key==pg.K_SPACE: self.action('pause')
                elif event.key==pg.K_F5: self.action('save')
                elif event.key==pg.K_F9: self.action('load')
                elif event.key in (pg.K_1,pg.K_2,pg.K_3): self.action("speed:"+str((1,2,4)[event.key-pg.K_1]))
            elif self._ui_click(event):
                return
            elif event.type==pg.MOUSEBUTTONDOWN and event.button==1 and pg.Rect(self.system_camera.viewport).collidepoint(event.pos):
                pid=pick_planet(self.simulation.campaign,self.selected_system,self.system_camera,event.pos)
                if pid is not None:
                    self.selected_planet=pid
                    self.audio.play("click")
            elif event.type==pg.MOUSEWHEEL and pg.Rect(self.system_camera.viewport).collidepoint(pg.mouse.get_pos()):
                self.system_camera.zoom(1.12**max(-3,min(3,event.y)),pg.mouse.get_pos())
            elif event.type==pg.MOUSEMOTION and event.buttons[1] and pg.Rect(self.system_camera.viewport).collidepoint(event.pos):
                self.system_camera.pan(*event.rel)
            return
        if self.mode == "report":
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.action("report_return")
            elif event.type == pg.KEYDOWN and event.key == pg.K_F5:
                self.action("save")
            else:
                self._ui_click(event)
            return
        if self.mode == "galaxy" and self.simulation is not None and self.simulation.campaign.pending is not None:
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.action("menu")
            elif event.type == pg.KEYDOWN and event.key == pg.K_F5:
                self.action("save")
            else:
                self._ui_click(event)
            return
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_F9:
                self.action("load")
            elif event.key == pg.K_ESCAPE:
                self.action("resume" if self.mode == "menu" and self.simulation else "menu")
            elif self.mode == "menu":
                if event.key in (pg.K_1, pg.K_2, pg.K_3):
                    self.faction = event.key - pg.K_1
                elif event.key == pg.K_RETURN:
                    self.action("start")
            elif self.simulation is not None:
                if event.key == pg.K_SPACE:
                    self.action("pause")
                elif event.key == pg.K_F5:
                    self.action("save")
                elif event.key == pg.K_f:
                    self.camera.center = self.simulation.campaign.systems[self.selected_system].position
                elif event.key in (pg.K_1, pg.K_2, pg.K_3):
                    self.action("speed:"+str((1,2,4)[event.key-pg.K_1]))
                elif event.key == pg.K_TAB:
                    ids = [f.id for f in self.simulation.campaign.fleets.values() if f.owner == self.simulation.campaign.player and f.ships]
                    if ids:
                        index = ids.index(self.selected_fleet) if self.selected_fleet in ids else -1
                        self.action(f"fleet:{ids[(index + 1) % len(ids)]}")
        elif event.type == pg.MOUSEBUTTONDOWN:
            if event.button == 1:
                for button in self.renderer.buttons:
                    if button.rect.collidepoint(event.pos):
                        if button.enabled:
                            self.action(button.action)
                        return
            if self.mode != "galaxy" or self.simulation is None or not pg.Rect(self.camera.viewport).collidepoint(event.pos):
                return
            if event.button == 1:
                c = self.simulation.campaign
                for fleet_id, position in self.renderer.fleet_points.items():
                    if c.fleets[fleet_id].owner == c.player and pg.Vector2(position).distance_to(event.pos) <= 13:
                        self.action(f"fleet:{fleet_id}")
                        return
            system_id = self.destination_at(event.pos) if event.button==3 else self.pick_system(event.pos)
            if system_id is not None:
                if event.button == 3:
                    self.request_move(system_id)
                elif event.button == 1:
                    now=pg.time.get_ticks()
                    previous,when=self.last_system_click
                    self.last_system_click=(system_id,now)
                    self.selected_system = system_id
                    self.audio.play("click")
                    if previous==system_id and now-when<=350:
                        self.open_system(system_id)
                        self.last_system_click=(-1,-1000)
                        return
                    # Sélection de système distincte : la source ne change que par clic sur une flotte.
        elif self.mode == "galaxy":
            if event.type == pg.MOUSEWHEEL and pg.Rect(self.camera.viewport).collidepoint(pg.mouse.get_pos()):
                self.camera.zoom(1.12 ** max(-3, min(3, event.y)), pg.mouse.get_pos())
            elif event.type == pg.MOUSEMOTION and event.buttons[1] and pg.Rect(self.camera.viewport).collidepoint(event.pos):
                self.camera.pan(*event.rel)


    def update_pointer_camera(self, dt: float) -> None:
        if (not self.focused or self.settings_open or self.admin_open or self.order_request is not None
                or self.simulation is None or self.mode not in ('galaxy','system','battle')):
            return
        mouse = self.pg.mouse
        if not mouse.get_focused() or any(mouse.get_pressed()):
            return
        position = mouse.get_pos()
        if any(button.rect.collidepoint(position) for button in self.renderer.buttons):
            return
        if self.mode == 'battle':
            controls = self.battle_controls
            if controls is None or controls.menu or self.battle.finished:
                return
            camera = controls.camera
        elif self.mode == 'system':
            camera = self.system_camera
        else:
            if self.simulation.campaign.pending is not None:
                return
            # La minimap superposée reste utilisable sans déplacer la vue principale.
            if self.pg.Rect((28,548,210,130)).collidepoint(position):
                return
            camera = self.camera
        camera.follow_pointer(position, dt)


async def run_game(on_boot=None) -> int:
    # Surface SDL classique ; audio facultatif initialisé uniquement au lancement manuel.
    os.environ.setdefault("SDL_RENDER_DRIVER", "software")
    try:
        import pygame
    except ImportError:
        print("Pygame CE manque. Installez les dépendances avec : python -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    if not getattr(pygame, "IS_CE", False):
        print("Ce projet nécessite pygame-ce, pas la distribution pygame classique.", file=sys.stderr)
        return 1
    if on_boot:
        on_boot('pygame', 'Pygame ' + pygame.version.ver + ' / ' + sys.platform)
    from star_arena.presentation.renderer import Renderer

    try:
        pygame.display.init()
        pygame.font.init()
        pygame.key.start_text_input()
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption(f"STAR ARENA: GALACTIC CONQUEST — Python {__version__}")
        screen.fill((9, 15, 26))
        pygame.display.flip()
        if on_boot:
            on_boot('display', 'Affichage 1280×800 créé ; initialisation de l’interface')
        await asyncio.sleep(0)
        save_path = default_save_path()
        app = Application(pygame, Renderer(screen), save_path)
        app.audio = SoundEffects(pygame)
        app.music = MusicManager(pygame)
        app.audio_settings_path = None if sys.platform == 'emscripten' else save_path.parent.parent/'settings'/'audio.json'
        try:
            if sys.platform == 'emscripten':
                import platform
                app.browser = BrowserBridge(platform.window)
                app.browser_store = BrowserStore(app.browser)
                app.audio_settings = app.browser_store.load_preferences()
            else:
                app.audio_settings = load_settings(app.audio_settings_path)
        except FileNotFoundError:
            pass
        except (OSError,ValueError,RecursionError) as error:
            app.audio_settings_error='Configuration audio ignorée : '+str(error)
        except (AttributeError, ImportError) as error:
            app.message = 'Pont navigateur indisponible : ' + str(error)
        if not app.needs_audio_unlock:
            app.configure_audio(persist=False)
        # Afficher une première fois même si le canvas n'a pas encore le focus clavier.
        app.renderer.draw(app)
        pygame.display.flip()
        if on_boot:
            on_boot('menu', 'Menu principal STAR ARENA affiché')
        await asyncio.sleep(0)
        clock = pygame.time.Clock()
        render_elapsed = 1 / FPS_LIMIT
        while app.running:
            was_focused = app.focused
            dt = min(clock.tick(0 if sys.platform=="emscripten" else FPS_LIMIT if was_focused else BACKGROUND_FPS_LIMIT) / 1000.0, 0.1)
            for event in pygame.event.get():
                app.event(event)
                if not app.running:
                    break
            if not app.running:
                break
            app.mp.poll()
            if sys.platform == 'emscripten':
                poll_browser(app)
            app.update_pointer_camera(dt)
            if app.order_request is None and not app.admin_open and not app.settings_open and app.focused and was_focused and app.mode in ("galaxy","system") and not app.paused and app.simulation is not None:
                app.advance_campaign(dt)
            elif app.order_request is None and not app.admin_open and not app.settings_open and app.focused and was_focused and app.mode == "battle" and app.battle_controls is not None:
                app.battle_controls.update(dt)
                if not app.battle_controls.menu and not app.battle_controls.paused:
                    app.battle.advance(dt)
            app.update_music(dt)
            render_elapsed += dt
            if app.focused and (sys.platform != 'emscripten' or render_elapsed >= 1 / FPS_LIMIT):
                app.feedback()
                app.renderer.draw(app)
                pygame.display.flip()
                if app.browser is not None:
                    app.browser.call('frame',app.mode)
                render_elapsed %= 1 / FPS_LIMIT
            await asyncio.sleep(0)
    except pygame.error as error:
        if sys.platform == 'emscripten':
            raise
        print(f"Initialisation ou affichage Pygame impossible : {error}", file=sys.stderr)
        return 1
    finally:
        if "app" in locals():
            if app.mp.task and not app.mp.task.done():
                app.mp.task.cancel()
                await asyncio.gather(app.mp.task,return_exceptions=True)
            await app.mp.close()
        pygame.quit()
    return 0


def main() -> int:
    """Entrée desktop ; la coroutine est aussi utilisable par un lanceur Web coopératif."""
    return asyncio.run(run_game())
