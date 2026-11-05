"""Tests admin et audio avec backend simulé, sans SDL ni périphérique sonore."""
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_warfare import temporary_directory, pending_campaign
from star_arena.domain.galaxy import new_campaign
from star_arena.domain.models import SHIP_TYPES
from star_arena.systems.admin import apply_cheat
from star_arena.app import Application
from star_arena.persistence import save_campaign, load_campaign
from star_arena.presentation.audio import SoundEffects, TONES, make_pcm, SAMPLE_RATE


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.c=new_campaign()

    def test_resources_only_player_and_roundtrip(self):
        before=asdict(self.c.resources[1])
        apply_cheat(self.c,'resources',0)
        self.assertEqual(self.c.resources[0].credits,10600)
        self.assertEqual(self.c.resources[0].minerals,10350)
        self.assertEqual(asdict(self.c.resources[1]),before)
        with temporary_directory() as folder:
            path=Path(folder)/'admin.json'
            save_campaign(self.c,path)
            self.assertEqual(asdict(load_campaign(path)),asdict(self.c))

    def test_spawn_ownership_unique_ids_and_real_stats(self):
        apply_cheat(self.c,'fleet',0); apply_cheat(self.c,'fleet',0)
        ids=[u.id for f in self.c.fleets.values() for u in f.ships]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(self.c.fleets),5)
        for ship in self.c.fleets[4].ships:
            self.assertEqual((ship.hull,ship.shield),SHIP_TYPES[ship.model][1:])
            self.assertEqual(ship.status,'permanent')
        before=asdict(self.c)
        apply_cheat(self.c,'fleet',9)
        self.assertEqual(asdict(self.c),before)

    def test_repair_does_not_resurrect_or_touch_enemy(self):
        ship=self.c.fleets[1].ships[0]
        dead=self.c.fleets[1].ships[1]
        ship.receive_damage(900); dead.receive_damage(999999)
        enemy=self.c.fleets[2].ships[0]; enemy.receive_damage(900)
        enemy_state=(enemy.hull,enemy.shield)
        apply_cheat(self.c,'repair',0)
        self.assertEqual((ship.hull,ship.shield),(1500,800))
        self.assertFalse(dead.alive)
        self.assertEqual((enemy.hull,enemy.shield),enemy_state)

    def test_pending_campaign_cheats_refused(self):
        c=pending_campaign(); before=asdict(c)
        for command in ('fleet','resources','queues','repair'):
            apply_cheat(c,command,0)
        self.assertEqual(asdict(c),before)

    def test_admin_commands_require_open_panel_and_pause_world(self):
        app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.begin(self.c); before=asdict(self.c)
        app.action('admin:resources')
        self.assertEqual(asdict(self.c),before)
        app.admin_open=True
        app.advance_campaign(.1)
        self.assertEqual(asdict(self.c),before)
        app.action('admin:resources')
        self.assertEqual(self.c.resources[0].credits,10600)
        app.action('admin_close'); app.advance_campaign(.1)
        self.assertEqual(self.c.time,.1)

    def test_queues_remain_paid_real_and_sequential(self):
        from star_arena.systems.economy import yard_order, GalacticEconomy
        yard_order(self.c,0,0); yard_order(self.c,0,0,'fighter'); yard_order(self.c,0,0,'fighter')
        credits=self.c.resources[0].credits; initial=len(self.c.fleets[1].ships)
        apply_cheat(self.c,'queues',0)
        self.assertEqual(self.c.resources[0].credits,credits)
        self.assertEqual(len(self.c.fleets[1].ships),initial)
        GalacticEconomy().update(self.c,1)
        self.assertEqual(len(self.c.fleets[1].ships),initial+1)
        self.assertEqual(len(self.c.systems[0].queue),1)

    def test_f10_f8_and_escape_routing_without_pygame(self):
        pg=SimpleNamespace(QUIT=0,KEYDOWN=1,WINDOWFOCUSLOST=2,WINDOWMINIMIZED=3,
                           WINDOWFOCUSGAINED=4,MOUSEBUTTONDOWN=5,K_F8=108,K_F10=110,K_ESCAPE=27)
        backend=SimpleNamespace(mixer=FakeMixer(),error=RuntimeError,time=SimpleNamespace(get_ticks=lambda:0))
        app=Application(pg,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.begin(self.c); app.audio=SoundEffects(backend)
        app.audio_settings.muted=True
        app.event(SimpleNamespace(type=1,key=110))
        self.assertTrue(app.admin_open)
        app.event(SimpleNamespace(type=1,key=108))
        self.assertTrue(app.audio.enabled)
        app.event(SimpleNamespace(type=1,key=27))
        self.assertFalse(app.admin_open)
        app.event(SimpleNamespace(type=2))
        self.assertFalse(app.focused)
        self.assertEqual(backend.mixer.stopped,1)

    def test_admin_victory_applies_real_losses_once(self):
        from star_arena.systems.tactical import BattleEngine
        c=pending_campaign()
        app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.begin(c); app.battle=BattleEngine(c,c.pending)
        app.battle_controls=SimpleNamespace()
        app.mode='battle'; app.admin_open=True
        app.action('admin:win')
        self.assertEqual(app.mode,'report')
        self.assertEqual(app.report.winner,c.player)
        self.assertTrue(c.fleets[2].destroyed)
        before=asdict(c); app.action('admin:win')
        self.assertEqual(asdict(c),before)


class FakeSound:
    def __init__(self): self.plays=0; self.volume=None
    def set_volume(self,volume): self.volume=volume
    def play(self): self.plays+=1


class FakeMixer:
    def __init__(self): self.initialized=None; self.created=[]; self.stopped=0; self.fail=False
    def get_init(self): return self.initialized
    def init(self,**kwargs):
        if self.fail: raise RuntimeError('Pas de périphérique audio')
        self.initialized=(kwargs['frequency'],kwargs['size'],kwargs['channels'])
    def set_num_channels(self,n): self.channels=n
    def stop(self): self.stopped+=1
    def Sound(self,**kwargs):
        result=FakeSound(); self.created.append((kwargs,result)); return result


class AudioTests(unittest.TestCase):
    def backend(self):
        self.now=0
        return SimpleNamespace(mixer=FakeMixer(),error=RuntimeError,
                               time=SimpleNamespace(get_ticks=lambda:self.now))

    def test_no_audio_init_until_explicit_enable(self):
        backend=self.backend(); audio=SoundEffects(backend)
        audio.play('laser')
        self.assertIsNone(backend.mixer.initialized)
        self.assertEqual(backend.mixer.created,[])

    def test_pcm_is_bounded_deterministic_and_contains_signal(self):
        for name,spec in TONES.items():
            raw=make_pcm(name)
            self.assertEqual(len(raw),round(SAMPLE_RATE*spec[0])*2)
            self.assertLess(len(raw),13000)
            self.assertEqual(raw,make_pcm(name))
            self.assertTrue(any(raw))

    def test_cache_volume_rate_limit_and_mute(self):
        backend=self.backend(); audio=SoundEffects(backend)
        self.assertTrue(audio.set_enabled(True))
        audio.play('laser'); audio.play('laser')
        self.assertEqual(len(backend.mixer.created),1)
        sound=backend.mixer.created[0][1]
        self.assertEqual(sound.plays,1); self.assertLessEqual(sound.volume,.25)
        self.now=120; audio.play('laser')
        self.assertEqual(sound.plays,2)
        audio.set_enabled(False); self.now=250; audio.play('laser')
        self.assertEqual(sound.plays,2)
        self.assertEqual(backend.mixer.stopped,1)

    def test_device_failure_keeps_game_silent(self):
        backend=self.backend(); backend.mixer.fail=True
        audio=SoundEffects(backend)
        self.assertFalse(audio.set_enabled(True))
        audio.play('explosion')
        self.assertTrue(audio.error)
        self.assertEqual(backend.mixer.created,[])
