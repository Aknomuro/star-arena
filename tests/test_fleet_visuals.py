"""Catalogue, ratio et caches avec objets factices ; aucune image créée ni Pygame."""
from io import BytesIO
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from star_arena.presentation.fleet_assets import PALETTES, SpriteCatalog, display_extent, fit_dimensions, png_dimensions
from star_arena.presentation.ship_sprites import ShipSprites, SurfaceCache


class BackendError(RuntimeError):
    pass


class FakeImage:
    def __init__(self, size, backend):
        self.size = size
        self.backend = backend

    def get_size(self):
        return self.size

    def get_width(self):
        return self.size[0]

    def get_height(self):
        return self.size[1]

    def convert_alpha(self):
        self.backend.conversions += 1
        return self


class FakeBackend:
    error = BackendError

    def __init__(self, sizes):
        self.sizes = {str(path): size for path, size in sizes.items()}
        self.loads = []
        self.scales = []
        self.rotations = []
        self.conversions = 0
        self.broken = set()
        self.image = SimpleNamespace(load=self.load)
        self.transform = SimpleNamespace(smoothscale=self.scale, rotozoom=self.rotate)

    def load(self, path):
        self.loads.append(path)
        if path in self.broken:
            raise BackendError("Erreur de décodage simulée")
        return FakeImage(self.sizes[path], self)

    def scale(self, image, size):
        self.scales.append(size)
        return FakeImage(size, self)

    def rotate(self, image, angle, scale):
        self.rotations.append(angle)
        return FakeImage(image.get_size(), self)


class MemoryHeader:
    """En-tête en mémoire uniquement ; aucun fichier .png n'est écrit."""
    def __init__(self, width, height):
        chunk = b"IHDR" + struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        self.data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + chunk + struct.pack(">I", zlib.crc32(chunk))

    def stat(self):
        return SimpleNamespace(st_size=len(self.data))

    def open(self, mode):
        return BytesIO(self.data)


class VisualPipelineTests(unittest.TestCase):
    def library(self, sizes):
        root = Path("virtual-assets/ships")
        backend = FakeBackend(sizes)
        catalog = SpriteCatalog(root, set(sizes))
        return ShipSprites(backend, root, catalog=catalog, inspect=lambda path: sizes[path]), backend

    def test_nine_faction_class_slots_and_missing_fallback(self):
        catalog = SpriteCatalog(Path("virtual-assets/ships"), set())
        self.assertEqual(len(catalog.inventory()), 9)
        self.assertTrue(all(row["available"] is None for row in catalog.inventory()))

    def test_dedicated_png_has_priority_over_generic(self):
        root = Path("virtual-assets/ships")
        specific, generic = root / "republic/fighter.png", root / "fighter.png"
        catalog = SpriteCatalog(root, {specific, generic})
        self.assertEqual(catalog.paths[0, "fighter"], specific)
        self.assertEqual(catalog.paths[1, "fighter"], generic)

    def test_missing_sprite_returns_none_without_loading(self):
        library, backend = self.library({})
        self.assertIsNone(library.get(0, "fighter", 42, 0))
        self.assertEqual(backend.loads, [])

    def test_ratio_preserved_landscape_and_portrait(self):
        self.assertEqual(fit_dimensions((300, 100), 90), (90, 30))
        self.assertEqual(fit_dimensions((100, 300), 90), (30, 90))
        self.assertEqual(fit_dimensions((200, 100), 42), (42, 21))

    def test_class_sizes_distinct_at_each_zoom(self):
        for zoom in (0.1, 0.35, 0.58, 1, 1.4):
            lengths = [display_extent(model, zoom) for model in ("fighter", "corvette", "cruiser")]
            self.assertLess(lengths[0], lengths[1])
            self.assertLess(lengths[1], lengths[2])

    def test_png_header_dimensions_without_decoding(self):
        self.assertEqual(png_dimensions(MemoryHeader(640, 320)), (640, 320))

    def test_large_header_rejected_before_decoding(self):
        with self.assertRaises(ValueError):
            png_dimensions(MemoryHeader(8000, 8000))

    def test_corrupt_header_rejected(self):
        header = MemoryHeader(100, 100)
        header.data = header.data[:-1] + bytes([header.data[-1] ^ 1])
        with self.assertRaises(ValueError):
            png_dimensions(header)

    def test_one_disk_load_and_one_alpha_conversion_per_path(self):
        path = Path("virtual-assets/ships/republic/fighter.png")
        library, backend = self.library({path: (200, 100)})
        first = library.get(0, "fighter", 42, 0)
        self.assertIs(library.get(0, "fighter", 42, 0), first)
        library.get(0, "fighter", 70, 45)
        self.assertEqual(backend.loads, [str(path)])
        self.assertEqual(backend.conversions, 1)

    def test_generic_original_shared_between_factions(self):
        path = Path("virtual-assets/ships/fighter.png")
        library, backend = self.library({path: (200, 100)})
        for owner in range(3):
            library.get(owner, "fighter", 42, 0)
        self.assertEqual(len(backend.loads), 1)

    def test_rotations_reuse_scaled_image_and_wrap_angles(self):
        path = Path("virtual-assets/ships/republic/fighter.png")
        library, backend = self.library({path: (200, 100)})
        first = library.get(0, "fighter", 42, 0)
        library.get(0, "fighter", 42, 0.5)
        library.get(0, "fighter", 42, 1.0)
        self.assertEqual(backend.rotations, [0.0, -0.5, -1.0])
        self.assertEqual(backend.scales, [(42, 21)])
        self.assertIs(library.get(0, "fighter", 42, 360), first)

    def test_broken_dedicated_sprite_uses_generic_once(self):
        specific = Path("virtual-assets/ships/republic/fighter.png")
        generic = Path("virtual-assets/ships/fighter.png")
        library, backend = self.library({specific: (200, 100), generic: (200, 100)})
        backend.broken.add(str(specific))
        for angle in (0, 10, 20):
            self.assertIsNotNone(library.get(0, "fighter", 42, angle))
        self.assertEqual(backend.loads.count(str(specific)), 1)
        self.assertEqual(backend.loads.count(str(generic)), 1)
        self.assertIn(specific, library.errors)

    def test_large_original_reduced_once_with_ratio(self):
        path = Path("virtual-assets/ships/republic/cruiser.png")
        library, backend = self.library({path: (2048, 1024)})
        library.get(0, "cruiser", 112, 0)
        self.assertEqual(library.originals[path].get_size(), (512, 256))
        self.assertEqual(backend.scales, [(512, 256), (112, 56)])

    def test_caches_bounded_by_entries_and_pixels(self):
        backend = FakeBackend({})
        cache = SurfaceCache(2, 150)
        for i in range(10):
            cache.put((i,), FakeImage((10, 10), backend))
            self.assertLessEqual(len(cache.items), 2)
            self.assertLessEqual(cache.pixels, 150)
        self.assertIsNotNone(cache.get((9,)))
        self.assertIsNone(cache.get((0,)))

    def test_faction_palettes_match_requested_contrast(self):
        self.assertGreater(min(PALETTES[0].body), 220)
        self.assertGreater(PALETTES[0].accent[2], PALETTES[0].accent[0])
        self.assertLess(max(PALETTES[1].body), 100)
        self.assertGreater(PALETTES[1].accent[0], PALETTES[1].accent[2])
        self.assertGreater(min(PALETTES[2].body), 200)
        self.assertGreater(PALETTES[2].accent[0], PALETTES[2].accent[1])


if __name__ == "__main__":
    unittest.main()
