"""V0.4.1 : stockage et routage navigateur avec pont injecté, sans Pygame ni navigateur."""
import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from test_warfare import temporary_directory, pending_campaign
from star_arena.app import Application, run_game
from star_arena.config import MAX_SAVE_BYTES, default_save_path
from star_arena.domain.galaxy import new_campaign
from star_arena.presentation.audio_settings import AudioSettings
from star_arena.web import BrowserStore, WebMultiplayer, encode_campaign, decode_text, poll_browser

ROOT=Path(__file__).resolve().parents[1]


class Bridge:
    def __init__(self):
        self.values={}; self.events=[]; self.downloads=[]; self.fail=False

    def call(self, operation, *args):
        if self.fail and operation in ('read','write'):
            raise ValueError('QuotaExceededError ou stockage refusé')
        if operation=='read': return self.values.get(args[0])
        if operation=='write':
            key,value,expected=args
            if self.values.get(key)!=expected: raise ValueError('Conflit entre onglets')
            self.values[key]=value
        elif operation=='poll': return self.events.pop(0) if self.events else None
        elif operation=='download': self.downloads.append(args[0])


class BrowserPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.bridge=Bridge(); self.store=BrowserStore(self.bridge)
        self.c=new_campaign(system_count=15)

    def test_roundtrip_preserves_moving_fleet_and_damage(self):
        from star_arena.systems.simulation import Simulation
        sim=Simulation(self.c)
        fleet=self.c.fleets[1]
        fleet.ships[0].hull-=7
        sim.order_move(fleet.id,self.c.neighbors(fleet.system_id)[0],fleet.owner)
        sim.advance(.2)
        self.store.save(self.c)
        restored=BrowserStore(self.bridge).load()
        self.assertEqual(encode_campaign(restored),encode_campaign(self.c))
        self.assertIsNotNone(restored.fleets[1].travel)

    def test_missing_campaign_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'Aucune campagne'): self.store.load()

    def test_storage_denied_and_quota_do_not_replace_save(self):
        self.store.save(self.c); original=dict(self.bridge.values)
        self.c.time=5; self.bridge.fail=True
        with self.assertRaises(ValueError): self.store.save(self.c)
        with self.assertRaises(ValueError): self.store.load()
        self.assertEqual(self.bridge.values,original)

    def test_corrupt_existing_save_is_preserved(self):
        self.bridge.values['campaign']='{broken'
        with self.assertRaises(ValueError): self.store.save(self.c)
        self.assertEqual(self.bridge.values['campaign'],'{broken')

    def test_other_tab_write_is_not_silently_overwritten(self):
        self.store.save(self.c)
        other=BrowserStore(self.bridge); other.load(); self.store.load()
        self.c.time=1; other.save(self.c)
        self.c.time=2
        with self.assertRaisesRegex(ValueError,'Conflit'): self.store.save(self.c)
        self.assertEqual(other.load().time,1)

    def test_malformed_oversize_and_duplicate_json_rejected(self):
        raw=encode_campaign(self.c)
        for bad in ('x'*(MAX_SAVE_BYTES+1),'{"version":5,"version":5}',raw.replace('"time":0.0','"time":NaN'),'{"version":999}'):
            # Certaines campagnes représentent le zéro comme entier.
            if bad==raw: bad='{"time":NaN}'
            with self.assertRaises((ValueError,RecursionError)): decode_text(bad)

    def test_audio_preferences_separate_and_corrupt_preserved(self):
        prefs=AudioSettings(music_volume=.2,muted=True)
        self.store.save(self.c); original=self.bridge.values['campaign']
        self.store.save_preferences(prefs)
        self.assertEqual(BrowserStore(self.bridge).load_preferences(),prefs)
        self.assertEqual(self.bridge.values['campaign'],original)
        self.bridge.values['audio']='{"version":999}'
        with self.assertRaises(ValueError): BrowserStore(self.bridge).save_preferences(prefs)
        self.assertEqual(self.bridge.values['audio'],'{"version":999}')


class BrowserRoutingTests(unittest.TestCase):
    def setUp(self):
        self.renderer=SimpleNamespace(buttons=[],fleet_points={})
        with patch('sys.platform','emscripten'):
            self.app=Application(None,self.renderer,Path('unused.json'))
        self.app.browser=Bridge(); self.app.browser_store=BrowserStore(self.app.browser)

    def test_web_controller_never_imports_desktop_controller(self):
        import builtins
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name.startswith('star_arena.network.') and not name.endswith('replica'):
                raise AssertionError('Import réseau desktop depuis Web')
            return original(name,*args,**kwargs)
        with patch('sys.platform','emscripten'),patch('builtins.__import__',side_effect=guarded):
            app=Application(None,self.renderer,Path('unused.json'))
            self.assertIsInstance(app.mp,WebMultiplayer)
            app.action('mp_host')
            self.assertEqual(app.mode,'menu')
            self.assertIn('préparation',app.message)
            self.assertEqual(default_save_path(),Path('saves/campaign.json'))

    def test_browser_save_and_load_route_without_filesystem(self):
        self.app.begin(new_campaign(system_count=15))
        with patch('star_arena.app.save_campaign',side_effect=AssertionError),patch('star_arena.app.load_campaign',side_effect=AssertionError):
            self.app.action('save'); self.app.simulation.campaign.time=12
            self.app.action('load')
        self.assertEqual(self.app.simulation.campaign.time,0)

    def test_export_and_import_use_same_engine_and_do_not_autosave(self):
        self.app.begin(new_campaign(system_count=15))
        self.app.action('web_export')
        raw=self.app.browser.downloads[0]
        self.app.browser.events.append({'action':'import','text':raw})
        poll_browser(self.app)
        self.assertEqual(encode_campaign(self.app.simulation.campaign),raw)
        self.assertEqual(self.app.mode,'galaxy')
        self.assertNotIn('campaign',self.app.browser.values)

    def test_invalid_import_retains_active_campaign(self):
        self.app.begin(new_campaign(system_count=15)); original=self.app.simulation
        self.app.browser.events.append({'action':'import','text':'{"version":999}'})
        poll_browser(self.app)
        self.assertIs(self.app.simulation,original)
        self.assertIn('Navigateur',self.app.message)

    def test_export_remains_available_when_storage_is_denied(self):
        self.app.begin(new_campaign(system_count=15))
        self.app.browser.fail=True
        self.app.action('save')
        self.assertIn('refusée',self.app.message)
        self.app.action('web_export')
        self.assertEqual(len(self.app.browser.downloads),1)
        self.assertEqual(decode_text(self.app.browser.downloads[0]).seed,42)

    def test_import_and_save_blocked_during_tactical_battle(self):
        self.app.begin(pending_campaign()); original=self.app.simulation
        self.app.mode='battle'
        self.app.browser.events.append({'action':'import','text':encode_campaign(new_campaign(system_count=15))})
        poll_browser(self.app); self.app.action('save'); self.app.action('web_export')
        self.assertIs(self.app.simulation,original)
        self.assertNotIn('campaign',self.app.browser.values)
        self.assertEqual(self.app.browser.downloads,[])

    def test_no_audio_initialization_before_gesture(self):
        self.app.audio.set_enabled=lambda *args: self.fail('Audio initialisé avant geste')
        self.app.configure_audio()
        self.assertTrue(self.app.needs_audio_unlock)

    def test_bridge_unavailable_never_falls_back_to_pc_save(self):
        self.app.browser_store=None
        with patch('sys.platform','emscripten'),patch('star_arena.app.load_campaign',side_effect=AssertionError):
            self.app.action('load')
        self.assertIn('indisponible',self.app.message)

    def test_cooperative_loop_has_zero_sleep_and_no_web_system_exit(self):
        import inspect
        self.assertIn('await asyncio.sleep(0)',inspect.getsource(run_game))
        tree=ast.parse((ROOT/'main.py').read_text(encoding='utf-8'))
        guarded=[n for n in ast.walk(tree) if isinstance(n,ast.If) and "sys.platform != 'emscripten'" in ast.unparse(n.test)]
        self.assertTrue(guarded)


class WebPackageTests(unittest.TestCase):
    def setUp(self):
        import sys
        self.paths=patch.object(sys,'path',[str(ROOT/'tools'),*sys.path]); self.paths.start()
        import prepare_web, check_web_build
        self.package=prepare_web; self.build=check_web_build

    def tearDown(self): self.paths.stop()

    def test_inventory_has_actual_assets_no_lan_or_private_paths(self):
        result=self.package.inventory(ROOT)
        self.assertEqual(result['sprites'],9); self.assertEqual(result['music_tracks'],6)
        names=[row['path'] for row in result['files']]
        self.assertIn('web/browser.js',names)
        self.assertNotIn('src/star_arena/network/runtime.py',names)
        self.assertFalse(any(p.startswith(('saves/','settings/','.venv/')) for p in names))
        raw=self.package.web_bytes(ROOT,ROOT/'assets/ships/manifest.json')
        self.assertNotIn(b'source_directory',raw)
        self.assertNotIn(b'C:',raw)
        self.assertFalse(result['export_executed']); self.assertFalse(result['browser_tested'])

    def test_stage_rejects_extra_private_file_before_copy(self):
        with temporary_directory() as folder:
            dest=Path(folder)/'app'; dest.mkdir()
            private=dest/'secret.txt'; private.write_text('keep')
            with self.assertRaises(ValueError): self.package.stage(ROOT,dest)
            self.assertEqual(private.read_text(),'keep')
            self.assertFalse((dest/'main.py').exists())

    def test_build_verifier_synthetic_archive_and_root_path_rejection(self):
        # Archive fixture uniquement : ceci n'est pas un build WASM ni une preuve navigateur.
        with temporary_directory() as folder:
            dest=Path(folder)
            index=dest/'index.html'; index.write_text('<script src="https://cdn.example/pythons.js"></script>')
            with zipfile.ZipFile(dest/'arena.apk','w') as archive:
                for source in self.package.files_for_web(ROOT):
                    archive.writestr('assets/'+source.relative_to(ROOT).as_posix(),self.package.web_bytes(ROOT,source))
            self.assertEqual(self.build.check(dest),len(self.package.files_for_web(ROOT)))
            self.assertTrue((dest/'.nojekyll').is_file())
            index.write_text('<script src="/root.js"></script>')
            with self.assertRaisesRegex(ValueError,'racine'): self.build.check(dest)

    def test_staging_is_not_mistaken_for_browser_build(self):
        with temporary_directory() as folder:
            with self.assertRaisesRegex(ValueError,'index.html'): self.build.check(Path(folder))

    def test_build_verifier_rejects_private_archive_member(self):
        with temporary_directory() as folder:
            dest=Path(folder); (dest/'index.html').write_text('<html></html>')
            with zipfile.ZipFile(dest/'arena.apk','w') as archive:
                archive.writestr('assets/settings/network_reconnect.json','private')
            with self.assertRaisesRegex(ValueError,'inattendu'): self.build.check(dest)

    def test_galaxy_projection_cache_invalidation_without_graphics(self):
        from star_arena.presentation.camera import GalaxyGeometry, Camera
        c=new_campaign(); camera=Camera(); geometry=GalaxyGeometry()
        first=geometry.project(c,camera)
        self.assertIs(geometry.project(c,camera),first)
        c.systems[0].owner=1
        self.assertIs(geometry.project(c,camera),first)
        camera.pan(10,20)
        second=geometry.project(c,camera)
        self.assertIsNot(second,first)
        camera.zoom(1.2,(200,200))
        self.assertIsNot(geometry.project(c,camera),second)


if __name__=='__main__': unittest.main()
