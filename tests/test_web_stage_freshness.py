"""Staging Web périmé : tests de fichiers légers, sans exportateur ni Pygame."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

from test_warfare import temporary_directory

ROOT=Path(__file__).resolve().parents[1]


def load_tool(name):
    spec=importlib.util.spec_from_file_location('arena_'+name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class StageFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.tool=load_tool('prepare_web')

    def clone_sources(self,root):
        for source in self.tool.files_for_web(ROOT):
            target=root/source.relative_to(ROOT)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())

    def test_refresh_rebuilds_arena_and_preserves_entire_old_copy(self):
        with temporary_directory() as folder:
            root=Path(folder); self.clone_sources(root)
            dest=root/'web_build/arena'
            old_art=dest/'src/star_arena/presentation/art.py'
            old_art.parent.mkdir(parents=True)
            old_art.write_text('gfx.aacircle(surface, *xy, r, color)')
            (dest/'build/web').mkdir(parents=True)
            (dest/'build/web/index.html').write_text('old build')
            (dest/'settings').mkdir()
            (dest/'settings/private.json').write_text('preserve me')
            result=self.tool.refresh_stage(root,dest)
            backup=root/result['previous_stage_preserved']
            self.assertEqual((backup/'src/star_arena/presentation/art.py').read_text(),'gfx.aacircle(surface, *xy, r, color)')
            self.assertEqual((backup/'build/web/index.html').read_text(),'old build')
            self.assertEqual((backup/'settings/private.json').read_text(),'preserve me')
            self.assertFalse((dest/'src').exists())
            self.assertFalse((dest/'build').exists())
            self.assertFalse((dest/'settings').exists())
            self.assertEqual((dest/'star_arena/presentation/art.py').read_bytes(),(root/'src/star_arena/presentation/art.py').read_bytes())
            self.assertEqual(result['verified_files'],len(self.tool.files_for_web(root)))

    def test_verify_detects_modified_file_without_overwriting_it(self):
        with temporary_directory() as folder:
            dest=Path(folder)/'stage'; self.tool.stage(ROOT,dest)
            path=dest/'star_arena/presentation/art.py'; path.write_text('old gfx.aacircle')
            with self.assertRaisesRegex(ValueError,'Ancienne copie'):
                self.tool.verify_stage(ROOT,dest)
            self.assertEqual(path.read_text(),'old gfx.aacircle')

    def test_verify_rejects_stale_build_or_extra_private_file(self):
        with temporary_directory() as folder:
            dest=Path(folder)/'stage'; self.tool.stage(ROOT,dest)
            (dest/'settings').mkdir(); private=dest/'settings/private.json'; private.write_text('preserve me')
            with self.assertRaisesRegex(ValueError,'non isolé'):
                self.tool.verify_stage(ROOT,dest)
            self.assertEqual(private.read_text(),'preserve me')

    def test_refresh_refuses_noncanonical_target_without_moving_files(self):
        with temporary_directory() as folder:
            root=Path(folder); dest=root/'outside'; dest.mkdir()
            (dest/'keep.txt').write_text('keep')
            with self.assertRaisesRegex(ValueError,'réservé'):
                self.tool.refresh_stage(root,dest)
            self.assertEqual((dest/'keep.txt').read_text(),'keep')

    def test_compiled_archive_containing_old_art_is_rejected(self):
        with temporary_directory() as folder:
            dest=Path(folder)
            (dest/'index.html').write_text('<html><script src="https://cdn.example/pythons.js"></script></html>')
            old_art=b'gfx.aacircle(surface, *xy, r, color)\n'
            with zipfile.ZipFile(dest/'arena.apk','w') as archive:
                for source in self.tool.files_for_web(ROOT):
                    relative=self.tool.web_path(ROOT,source).as_posix()
                    data=old_art if relative=='star_arena/presentation/art.py' else self.tool.web_bytes(ROOT,source)
                    archive.writestr('assets/'+relative,data)
            info=load_tool('prepare_web_output').prepare(dest)
            self.assertEqual(info['art_sha256'],hashlib.sha256(old_art).hexdigest())
            self.assertIn('source_commit',info)
            with patch.object(sys,'path',[str(ROOT/'tools'),*sys.path]):
                check=load_tool('check_web_build')
                with self.assertRaisesRegex(ValueError,'Contenu inattendu'):
                    check.check(dest,require_startup=True)


if __name__=='__main__': unittest.main()
