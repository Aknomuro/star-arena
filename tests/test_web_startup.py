"""Démarrage Web : chemins, propagation d'erreurs et diagnostics, sans Pygame."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_warfare import temporary_directory
from star_arena.config import project_root

ROOT=Path(__file__).resolve().parents[1]


def load_tool(name):
    path=ROOT/('main.py' if name=='entry' else 'tools/'+name+'.py')
    spec=importlib.util.spec_from_file_location('arena_'+name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class WebStartupTests(unittest.TestCase):
    def test_flat_package_visible_before_entry_runs(self):
        tool=load_tool('prepare_web')
        with temporary_directory() as folder:
            dest=Path(folder)/'app'; tool.stage(ROOT,dest)
            self.assertTrue((dest/'star_arena/app.py').is_file())
            self.assertTrue((dest/'assets/ships/republic/fighter.png').is_file())
            self.assertTrue((dest/'web/browser.js').is_file())
            self.assertFalse((dest/'src').exists())
            self.assertFalse((dest/'star_arena/network/runtime.py').exists())
            # importlib peut résoudre le paquet sans exécuter main.py ou importer Pygame.
            from importlib.machinery import PathFinder
            self.assertIsNotNone(PathFinder.find_spec('star_arena',[str(dest)]))

    def test_resources_resolve_for_pc_and_flat_web(self):
        self.assertEqual(project_root(),ROOT)
        with patch('star_arena.config.__file__',str(ROOT/'flat/star_arena/config.py')):
            self.assertEqual(project_root(),ROOT/'flat')

    def test_bootstrap_catches_app_import_failure_before_pygame(self):
        entry=load_tool('entry'); reports=[]
        with patch.object(entry,'boot_report',side_effect=lambda *args:reports.append(args)),patch('sys.platform','emscripten'),patch.object(entry.importlib,'import_module',side_effect=ModuleNotFoundError('demonstrated import failure')):
            self.assertEqual(asyncio.run(entry.bootstrap()),1)
        self.assertEqual(reports[-1][0],'error')
        self.assertIn('ModuleNotFoundError',reports[-1][1])

    def test_bootstrap_awaits_game_and_preserves_callback(self):
        entry=load_tool('entry'); calls=[]
        async def fake_game(on_boot):
            calls.append('game'); on_boot('menu','fake menu test'); return 0
        with patch.object(entry,'boot_report',side_effect=lambda *args:calls.append(args)),patch.object(entry.importlib,'import_module',return_value=SimpleNamespace(run_game=fake_game)):
            self.assertEqual(asyncio.run(entry.bootstrap()),0)
        self.assertIn(('menu','fake menu test'),calls)

    def test_python_error_is_encoded_for_js_not_interpolated_as_code(self):
        entry=load_tool('entry'); expressions=[]
        platform=SimpleNamespace(window=SimpleNamespace(eval=expressions.append))
        with patch('sys.platform','emscripten'),patch.dict('sys.modules',{'platform':platform}):
            entry.boot_report('error','quote " and newline\n')
        self.assertIn(json.dumps(['error','quote " and newline\n']),expressions[0])

    def test_build_diagnostic_is_before_runtime_and_idempotent(self):
        tool=load_tool('prepare_web_output')
        with temporary_directory() as folder:
            dest=Path(folder); index=dest/'index.html'
            index.write_text('<html><script src="https://cdn.example/pythons.js"></script></html>')
            result=tool.prepare(dest); first=index.read_bytes(); tool.prepare(dest)
            self.assertTrue(result['boot_script_before_runtime'])
            self.assertEqual(index.read_bytes(),first)
            self.assertEqual((dest/'star-arena-boot.js').read_bytes(),(ROOT/'web/boot.js').read_bytes())

    def test_browser_test_is_forbidden_outside_github_runner(self):
        tool=load_tool('web_browser_smoke')
        with patch.dict('os.environ',{'GITHUB_ACTIONS':'false'}):
            with self.assertRaisesRegex(SystemExit,'runner'):
                tool.main()


if __name__=='__main__': unittest.main()
