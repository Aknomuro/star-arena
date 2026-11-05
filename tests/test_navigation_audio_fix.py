"""V0.3.2 : navigation et audio sans affichage ni périphérique sonore."""
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import unittest
import wave
from test_warfare import temporary_directory
from test_admin_audio import FakeMixer
from test_music import backend
from star_arena.app import Application
from star_arena.domain.galaxy import new_campaign
from star_arena.systems.navigation import find_path, remaining_time
from star_arena.systems.simulation import Simulation
from star_arena.systems.economy import NoEconomy
from star_arena.systems.combat import resolve_engagement
from star_arena.systems.tactical import BattleEngine
from star_arena.persistence import load_campaign, save_campaign
from star_arena.presentation.audio import SoundEffects, make_pcm
from star_arena.presentation.music import inventory, MusicManager


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.c=new_campaign(system_count=15, layout="legacy")
        self.c.routes={(i,i+1) for i in range(14)}
        for i,s in self.c.systems.items(): s.position=(i*130.,0.)
        self.c.next_ai_at=1e9
        self.sim=Simulation(self.c,NoEconomy())
        self.f=self.c.fleets[1]

    def advance(self,seconds):
        for _ in range(round(seconds*10)): self.sim.advance(.1)

    def test_direct_and_multi_segment_no_intermediate_conquest(self):
        self.assertEqual(find_path(self.c,0,3),[0,1,2,3])
        self.assertEqual(self.sim.order_move(1,3,0),'')
        self.assertEqual(remaining_time(self.c,self.f),6)
        self.advance(6.1)
        self.assertEqual(self.f.system_id,3)
        self.assertIsNone(self.f.travel)
        self.assertEqual(self.f.navigation_state,'arrived')
        self.assertIsNone(self.c.systems[1].owner)
        self.assertIsNone(self.c.systems[2].owner)
        self.assertEqual(self.c.systems[3].owner,0)
        self.assertEqual(len(self.f.ships),8)

    def test_weighted_shortest_time_not_fewest_edges(self):
        self.c.routes={(0,1),(1,3),(0,2),(2,3)}|{(i,i+1) for i in range(3,14)}
        self.c.systems[1].position=(10000.,0.)
        self.c.systems[2].position=(130.,0.)
        self.assertEqual(find_path(self.c,0,3),[0,2,3])

    def test_unreachable_order_preserves_old_course(self):
        self.sim.order_move(1,3,0); self.advance(.7)
        self.c.routes.remove((8,9))
        before=asdict(self.f)
        self.assertTrue(self.sim.order_move(1,10,0))
        self.assertEqual(asdict(self.f),before)

    def test_retarget_in_flight_keeps_position_and_progress(self):
        self.sim.order_move(1,3,0); self.advance(.7)
        position=self.f.position(self.c.systems); segment=asdict(self.f.travel)
        self.assertEqual(self.sim.order_move(1,0,0),'')
        self.assertEqual(self.f.position(self.c.systems),position)
        self.assertEqual(asdict(self.f.travel),segment)
        self.assertEqual(self.f.itinerary,[0,1,0])
        self.advance(3.4)
        self.assertEqual(self.f.system_id,0)
        self.assertEqual(self.f.navigation_state,'arrived')

    def test_blocked_route_reload_and_recovery(self):
        self.sim.order_move(1,3,0)
        self.c.routes.remove((1,2)); self.advance(2.1)
        self.assertEqual(self.f.system_id,1)
        self.assertEqual(self.f.navigation_state,'blocked')
        self.assertEqual(remaining_time(self.c,self.f),float('inf'))
        with temporary_directory() as folder:
            path=Path(folder)/'blocked.json'; save_campaign(self.c,path)
            loaded=load_campaign(path)
            self.assertEqual(asdict(loaded),asdict(self.c))
        self.c.routes.add((1,2)); self.advance(4.1)
        self.assertEqual(self.f.system_id,3)

    def test_save_in_transit_then_same_result(self):
        self.sim.order_move(1,3,0); self.advance(2.7)
        with temporary_directory() as folder:
            path=Path(folder)/'transit.json'; save_campaign(self.c,path)
            loaded=load_campaign(path)
        self.assertEqual(asdict(self.c),asdict(loaded))
        other=Simulation(loaded,NoEconomy())
        for _ in range(40):
            self.sim.advance(.1); other.advance(.1)
        self.assertEqual(asdict(self.c),asdict(loaded))

    def test_engagement_suspends_then_victory_resumes(self):
        self.c.systems[1].owner=1; self.c.fleets[2].system_id=1
        self.sim.order_move(1,3,0); self.advance(2.1)
        self.assertIsNotNone(self.c.pending)
        self.assertEqual(self.f.navigation_state,'engaged')
        with temporary_directory() as folder:
            path=Path(folder)/'engaged.json'; save_campaign(self.c,path)
            self.assertEqual(asdict(load_campaign(path)),asdict(self.c))
        before=asdict(self.f); self.advance(1)
        self.assertEqual(asdict(self.f),before)
        for ship in self.c.fleets[2].ships: ship.receive_damage(999999)
        resolve_engagement(self.c,self.c.pending,0)
        self.advance(4.1)
        self.assertEqual(self.f.system_id,3)
        self.assertEqual(self.f.navigation_state,'arrived')

    def test_defeat_cancels_remaining_order_and_retreats(self):
        self.c.systems[1].owner=1; self.c.fleets[2].system_id=1
        self.sim.order_move(1,3,0); self.advance(2.1)
        resolve_engagement(self.c,self.c.pending,1)
        self.assertIsNone(self.f.final_destination)
        self.assertEqual(self.f.itinerary,[])
        self.assertEqual(self.f.navigation_state,'cancelled')
        self.assertEqual(self.f.travel.destination,0)

    def test_enemy_without_defense_is_crossed_without_annexation(self):
        self.c.systems[1].owner=1
        self.sim.order_move(1,3,0); self.advance(6.1)
        self.assertEqual(self.c.systems[1].owner,1)
        self.assertEqual(self.f.system_id,3)

    def test_removed_next_edge_replans_without_teleport(self):
        self.c.routes.update({(1,5),(3,6)})
        self.sim.order_move(1,3,0)
        self.c.routes.remove((1,2))
        self.advance(2.)
        self.assertEqual(self.f.system_id,1)
        self.assertEqual(self.f.travel.origin,1)
        self.assertEqual(self.f.travel.destination,5)
        self.assertEqual(self.f.itinerary[:2],[0,1])
        self.assertEqual(self.f.segment_index,1)
        self.assertEqual(self.f.travel.elapsed,0)

    def test_removed_committed_edge_can_save_and_finish_current_leg(self):
        self.sim.order_move(1,3,0); self.advance(.7)
        self.c.routes.remove((0,1))
        with temporary_directory() as folder:
            path=Path(folder)/'committed.json'; save_campaign(self.c,path)
            loaded=load_campaign(path)
        self.assertEqual(asdict(self.c),asdict(loaded))
        self.advance(5.4)
        self.assertEqual(self.f.system_id,3)

    def test_v4_travel_migrates_without_reset_and_is_backed_up(self):
        import json
        self.sim.order_move(1,1,0); self.advance(.7)
        with temporary_directory() as folder:
            path=Path(folder)/'v4.json'; save_campaign(self.c,path)
            data=json.loads(path.read_text(encoding='utf-8')); data['version']=4
            for f in data['fleets']:
                for key in ('itinerary','final_destination','segment_index','navigation_state'): f.pop(key)
            original=json.dumps(data); path.write_text(original,encoding='utf-8')
            loaded=load_campaign(path)
            self.assertAlmostEqual(loaded.fleets[1].travel.elapsed,.7)
            self.assertEqual(loaded.fleets[1].itinerary,[0,1])
            save_campaign(loaded,path)
            self.assertEqual(path.with_name(path.name+'.v4.bak').read_text(encoding='utf-8'),original)

    def test_pause_and_speed_control_entire_itinerary(self):
        for speed in (1,2,4):
            c=new_campaign(system_count=15, layout="legacy"); c.routes={(i,i+1) for i in range(14)}
            for i,s in c.systems.items(): s.position=(i*130.,0.)
            c.next_ai_at=1e9
            app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
            app.begin(c); app.simulation=Simulation(c,NoEconomy())
            app.simulation.order_move(1,3,0); app.paused=True
            app.advance_campaign(.1); self.assertEqual(c.time,0)
            app.paused=False; app.speed=speed
            for _ in range(30): app.advance_campaign(1/30)
            self.assertEqual(c.time,float(speed))
            self.assertEqual(c.fleets[1].segment_index,speed//2)


class AudioFixTests(unittest.TestCase):
    def test_stereo_negotiated_rate_and_cache(self):
        pg=backend(); pg.mixer.initialized=(48000,-16,2)
        audio=SoundEffects(pg)
        self.assertTrue(audio.set_enabled(True))
        audio.play('laser')
        data=pg.mixer.created[0][0]['buffer']
        self.assertEqual(len(data),round(.12*48000)*4)
        self.assertEqual(data[:2],data[2:4])
        self.assertFalse(audio.error)

    def test_existing_real_wav_files_have_valid_pcm_content(self):
        root=Path(__file__).resolve().parents[1]/'assets/audio/music'
        rows=inventory(root)
        self.assertEqual(len(rows),6)
        contents=[]
        for row in rows.values():
            self.assertTrue(row['valid_header'])
            with wave.open(str(root/row['file']),'rb') as stream:
                self.assertEqual(stream.getnchannels(),1)
                self.assertEqual(stream.getsampwidth(),2)
                self.assertEqual(stream.getframerate(),11025)
                data=stream.readframes(stream.getnframes())
                self.assertEqual(len(data),stream.getnframes()*2)
                self.assertTrue(any(data))
                contents.append(data)
        self.assertEqual(len(set(contents)),6)

    def test_actual_wav_path_loaded_by_fake_music_backend(self):
        pg=backend(); music=MusicManager(pg)
        music.request('menu'); music.update(.1)
        self.assertTrue(pg.mixer.music.loads[0].endswith('main_menu.wav'))
        self.assertEqual(pg.mixer.music.plays,[{'loops':-1}])

    def test_audio_test_buttons_obey_mute_and_device_failure(self):
        pg=backend(); app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.audio=SoundEffects(pg); app.music=MusicManager(pg)
        app.audio_settings.muted=True
        app.action('audio_test_effects')
        self.assertEqual(pg.mixer.created,[])
        app.audio_settings.muted=False; app.action('audio_test_music')
        self.assertTrue(pg.mixer.music.loads)
        pg.mixer.initialized=None; pg.mixer.fail=True
        app.action('audio_test_effects')
        self.assertIn('indisponible',app.message)

    def test_short_lived_combat_events_are_not_lost_between_frames(self):
        from test_warfare import pending_campaign
        c=pending_campaign(); b=BattleEngine(c,c.pending)
        app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        calls=[]; app.audio=SimpleNamespace(play=calls.append)
        app.simulation=SimpleNamespace(campaign=c); app.mode='battle'; app.battle=b
        b.event_counts['laser']=5; b.event_counts['explosion']=2
        b.projectiles.clear(); b.effects.clear()
        app.feedback(); self.assertIn('laser',calls); self.assertIn('explosion',calls)
        calls.clear(); app.feedback()
        self.assertNotIn('laser',calls)

    def test_completion_events_not_only_latest_journal_entry(self):
        c=new_campaign(); app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.begin(c); calls=[]; app.audio=SimpleNamespace(play=calls.append)
        app.feedback(); calls.clear()
        c.log('Chasseur terminé.'); c.log('Flotte en route.')
        app.feedback(); self.assertIn('complete',calls)

    def test_music_ducks_for_effects_without_changing_preferences(self):
        pg=backend(); music=MusicManager(pg)
        music.request('battle')
        for _ in range(10): music.update(.2)
        full=pg.mixer.music.volumes[-1]
        music.ducking=True
        for _ in range(5): music.update(.2)
        self.assertAlmostEqual(pg.mixer.music.volumes[-1],full*.3)
        self.assertEqual(music.volume,.28)
        music.ducking=False
        for _ in range(5): music.update(.2)
        self.assertAlmostEqual(pg.mixer.music.volumes[-1],full)
