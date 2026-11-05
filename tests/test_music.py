"""Audio V0.3.1 : backend simulé, fixtures temporaires, aucun périphérique réel."""
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_warfare import temporary_directory
from test_admin_audio import FakeMixer
from star_arena.presentation.audio import SoundEffects
from star_arena.presentation.audio_settings import AudioSettings, decode_settings, load_settings, save_settings
from star_arena.presentation.music import MusicManager, TRACKS, inventory
from star_arena.app import Application


class FakeMusic:
    def __init__(self):
        self.loads=[]; self.plays=[]; self.volumes=[]; self.stops=0
        self.pauses=0; self.resumes=0; self.bad=False
    def load(self,path):
        self.loads.append(path)
        if self.bad: raise RuntimeError('Codec indisponible')
    def play(self,**kwargs): self.plays.append(kwargs)
    def set_volume(self,value): self.volumes.append(value)
    def stop(self): self.stops+=1
    def pause(self): self.pauses+=1
    def unpause(self): self.resumes+=1


def backend():
    mixer=FakeMixer(); mixer.initialized=(22050,-16,1); mixer.music=FakeMusic()
    return SimpleNamespace(mixer=mixer,error=RuntimeError,time=SimpleNamespace(get_ticks=lambda:0))


class MusicTests(unittest.TestCase):
    def make_manager(self,folder):
        root=Path(folder)
        for name in TRACKS.values():
            # En-tête de fixture seulement : le backend simulé ne décode rien.
            (root/name).write_bytes(b'OggS-fixture-no-real-audio')
        pg=backend()
        return MusicManager(pg,root),pg

    def settle(self,m):
        for _ in range(12): m.update(.2)

    def test_scene_changes_loop_and_progressive_fade(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder)
            m.request('menu'); self.settle(m)
            self.assertEqual(pg.mixer.music.plays,[{'loops':-1}])
            self.assertAlmostEqual(pg.mixer.music.volumes[-1],.28)
            m.request('galaxy'); m.update(.2)
            self.assertEqual(len(pg.mixer.music.loads),1)
            self.assertTrue(0<pg.mixer.music.volumes[-1]<.28)
            self.settle(m)
            self.assertEqual(Path(pg.mixer.music.loads[-1]).name,'galaxy.ogg')
            self.assertEqual(len(pg.mixer.music.loads),2)
            self.assertIn(0.,pg.mixer.music.volumes)

    def test_same_scene_and_selection_do_not_restart(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder)
            for _ in range(100):
                m.request('system'); m.update(.1)
            self.assertEqual(len(pg.mixer.music.loads),1)
            self.assertEqual(len(pg.mixer.music.plays),1)

    def test_results_once_and_new_report_has_new_token(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder)
            m.request('victory',7); self.settle(m)
            for _ in range(20): m.request('victory',7); m.update(.1)
            self.assertEqual(pg.mixer.music.plays,[{'loops':0}])
            m.request('victory',8); self.settle(m)
            self.assertEqual(len(pg.mixer.music.loads),2)
            m.request('defeat',9); self.settle(m)
            self.assertEqual(pg.mixer.music.plays[-1],{'loops':0})

    def test_mute_and_volume_without_reload(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder)
            m.request('battle'); self.settle(m)
            m.configure(True,.16); m.update(.1)
            self.assertAlmostEqual(pg.mixer.music.volumes[-1],.16)
            m.configure(False,.16); m.update(.1)
            self.assertEqual(pg.mixer.music.volumes[-1],0)
            m.configure(True,.16); m.update(.1)
            self.assertAlmostEqual(pg.mixer.music.volumes[-1],.16)
            self.assertEqual(len(pg.mixer.music.loads),1)

    def test_missing_empty_and_invalid_files_stay_silent(self):
        with temporary_directory() as folder:
            root=Path(folder)
            (root/'galaxy.ogg').write_bytes(b'')
            (root/'battle.ogg').write_bytes(b'not-an-ogg')
            rows=inventory(root)
            self.assertFalse(rows['menu']['present'])
            self.assertFalse(rows['galaxy']['ogg_header'])
            self.assertFalse(rows['battle']['ogg_header'])
            pg=backend(); m=MusicManager(pg,root)
            for category in ('menu','galaxy','battle','system'):
                m.request(category); self.settle(m)
            self.assertEqual(pg.mixer.music.loads,[])
            self.assertEqual(pg.mixer.music.plays,[])
            self.assertFalse(m.failed)

    def test_corrupt_decode_not_retried_each_frame(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder); pg.mixer.music.bad=True
            m.request('menu'); self.settle(m)
            self.settle(m)
            self.assertEqual(len(pg.mixer.music.loads),1)
            self.assertIn('menu',m.errors)
            self.assertEqual(pg.mixer.music.plays,[])

    def test_focus_pause_resume_without_restart(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder)
            m.request('menu'); self.settle(m)
            m.suspend(True); m.suspend(True); m.update(.1)
            self.assertEqual(pg.mixer.music.pauses,1)
            m.suspend(False); m.update(.1)
            self.assertEqual(pg.mixer.music.resumes,1)
            self.assertEqual(len(pg.mixer.music.plays),1)

    def test_unavailable_device_no_initialization_or_retry_loop(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder); pg.mixer.initialized=None
            m.request('menu'); self.settle(m)
            self.assertEqual(pg.mixer.music.loads,[])
            self.assertIsNone(pg.mixer.initialized)
            def fail(): raise RuntimeError('Périphérique perdu')
            pg.mixer.get_init=fail
            m.update(.1); self.assertTrue(m.failed)
            m.update(.1); self.assertIn('device',m.errors)

    def test_invalid_dt_and_volume_are_bounded(self):
        with temporary_directory() as folder:
            m,pg=self.make_manager(folder)
            m.request('menu')
            for dt in (-1,float('nan'),float('inf')): m.update(dt)
            self.assertEqual(pg.mixer.music.loads,[])
            m.configure(True,float('nan')); self.assertEqual(m.volume,0)
            m.configure(True,9); self.assertEqual(m.volume,1)
            m.update(1000); self.assertLessEqual(m.level,1)


class PreferenceTests(unittest.TestCase):
    def app(self):
        app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        pg=backend()
        app.audio=SoundEffects(pg); app.music=MusicManager(pg)
        return app,pg

    def test_master_music_and_effects_gains_are_independent(self):
        app,pg=self.app()
        app.audio_settings=AudioSettings(.5,.4,.8)
        app.configure_audio(False)
        self.assertAlmostEqual(app.music.volume,.2)
        self.assertAlmostEqual(app.audio.volume,.16)
        app.audio.play('click')
        self.assertAlmostEqual(pg.mixer.created[-1][1].volume,.16)
        app.action('music_toggle')
        self.assertFalse(app.music.enabled)
        self.assertTrue(app.audio.enabled)
        app.action('effects_toggle')
        self.assertFalse(app.audio.enabled)

    def test_master_mute_restores_individual_preferences(self):
        app,pg=self.app()
        app.audio_settings.music_enabled=False
        app.configure_audio(False)
        app.action('sound_toggle')
        self.assertTrue(app.audio_settings.muted)
        self.assertFalse(app.audio.enabled)
        self.assertFalse(app.music.enabled)
        app.action('sound_toggle')
        self.assertFalse(app.audio_settings.muted)
        self.assertTrue(app.audio.enabled)
        self.assertFalse(app.music.enabled)

    def test_music_only_initializes_shared_mixer(self):
        app,pg=self.app(); pg.mixer.initialized=None
        app.audio_settings.effects_enabled=False
        app.configure_audio(False)
        self.assertIsNotNone(pg.mixer.get_init())
        self.assertFalse(app.audio.enabled)
        self.assertTrue(app.music.enabled)

    def test_preference_roundtrip_separate_from_campaign(self):
        with temporary_directory() as folder:
            app,pg=self.app(); app.audio_settings_path=Path(folder)/'settings'/'audio.json'
            app.action('audio_volume:music:-1')
            app.action('music_toggle')
            loaded=load_settings(app.audio_settings_path)
            self.assertEqual(asdict(loaded),asdict(app.audio_settings))
            self.assertFalse((Path(folder)/'campaign.json').exists())

    def test_invalid_configuration_preserved(self):
        with temporary_directory() as folder:
            path=Path(folder)/'audio.json'
            path.write_text('{"version":999}',encoding='utf-8')
            original=path.read_bytes()
            with self.assertRaises(ValueError): save_settings(AudioSettings(),path)
            self.assertEqual(path.read_bytes(),original)
        for bad in (-1,1.1,True,float('nan')):
            values=asdict(AudioSettings()); values['music_volume']=bad
            with self.assertRaises(ValueError): decode_settings({'version':1,'audio':values})

    def test_configuration_failure_reported_without_blocking(self):
        with temporary_directory() as folder:
            app,pg=self.app(); app.audio_settings_path=Path(folder)/'audio.json'
            app.audio_settings_path.write_text('broken',encoding='utf-8')
            app.action('audio_volume:master:-1')
            self.assertTrue(app.audio_settings_error)
            self.assertAlmostEqual(app.audio_settings.master_volume,.7)

    def test_device_initialization_failure_does_not_crash(self):
        app,pg=self.app(); pg.mixer.initialized=None; pg.mixer.fail=True
        app.configure_audio(False); app.update_music(.1)
        self.assertFalse(app.audio.enabled)
        self.assertTrue(app.audio.error)
        self.assertEqual(pg.mixer.music.plays,[])

    def test_scene_mapping_and_same_result_between_battle_and_report(self):
        app,pg=self.app()
        app.mode='system'; app.update_music(.1)
        self.assertEqual(app.music.desired,('system',None))
        app.simulation=SimpleNamespace(campaign=SimpleNamespace(player=0))
        app.mode='battle'
        app.battle=SimpleNamespace(finished=True,winner=0,engagement=SimpleNamespace(id=9))
        app.update_music(.1)
        self.assertEqual(app.music.desired,('victory',9))
        app.mode='report'; app.report=SimpleNamespace(winner=0,id=9)
        app.update_music(.1)
        self.assertEqual(app.music.desired,('victory',9))
        app.report=SimpleNamespace(winner=1,id=10); app.update_music(.1)
        self.assertEqual(app.music.desired,('defeat',10))

    def test_open_settings_preserves_campaign_and_pause(self):
        from star_arena.domain.galaxy import new_campaign
        app,pg=self.app(); app.begin(new_campaign()); before=asdict(app.simulation.campaign)
        app.action('audio_settings'); app.advance_campaign(.1)
        self.assertEqual(before,asdict(app.simulation.campaign))
        app.action('audio_settings_close'); app.advance_campaign(.1)
        self.assertEqual(app.simulation.campaign.time,.1)
