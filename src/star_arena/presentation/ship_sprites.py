"""Chargeur de sprites avec backend injecté : les tests n'importent pas Pygame."""
from collections import OrderedDict
from pathlib import Path

from star_arena.presentation.quality import profile
from star_arena.presentation.fleet_assets import SpriteCatalog, fit_dimensions, png_dimensions


class SurfaceCache:
    def __init__(self, entries: int, pixels: int) -> None:
        self.entries = entries
        self.budget = pixels
        self.pixels = 0
        self.items: OrderedDict[tuple, object] = OrderedDict()

    def get(self, key):
        value = self.items.get(key)
        if value is not None:
            self.items.move_to_end(key)
        return value

    def put(self, key, surface) -> None:
        previous = self.items.pop(key, None)
        if previous is not None:
            self.pixels -= previous.get_width() * previous.get_height()
        self.items[key] = surface
        self.pixels += surface.get_width() * surface.get_height()
        while len(self.items) > self.entries or self.pixels > self.budget:
            _, removed = self.items.popitem(last=False)
            self.pixels -= removed.get_width() * removed.get_height()

    def resize(self, entries: int, pixels: int):
        self.entries=entries; self.budget=pixels
        while len(self.items)>entries or self.pixels>pixels:
            _,surface=self.items.popitem(last=False)
            self.pixels-=surface.get_width()*surface.get_height()


class ShipSprites:
    def __init__(self, backend, root: Path, *, catalog: SpriteCatalog | None = None,
                 inspect=png_dimensions) -> None:
        self.backend = backend
        self.catalog = catalog if catalog is not None else SpriteCatalog(root)
        self.inspect = inspect
        self.reduced=False
        self.originals: dict[Path, object | None] = {}
        self.errors: dict[Path, str] = {}
        self.scaled = SurfaceCache(64, 2_000_000)
        self.rotations = SurfaceCache(256, 4_000_000)

    def _load(self, path: Path):
        if path not in self.originals:
            try:
                expected = self.inspect(path)
                image = self.backend.image.load(str(path)).convert_alpha()
                if image.get_size() != expected:
                    raise ValueError("Dimensions décodées différentes de l'en-tête PNG.")
                maximum = min(512, max(expected))
                size = fit_dimensions(expected, maximum)
                self.originals[path] = self.backend.transform.smoothscale(image, size) if size != expected else image
            except (OSError, ValueError, self.backend.error) as error:
                self.originals[path] = None
                self.errors[path] = str(error)
        return self.originals[path]

    def preload(self):
        for path in set(self.catalog.paths.values()):
            if path is not None: self._load(path)

    def get(self, owner: int, model: str, extent: int, angle_degrees: float, reduced: bool = False):
        if reduced!=self.reduced:
            self.reduced=reduced
            self.scaled.resize(32 if reduced else 64,500_000 if reduced else 2_000_000)
            self.rotations.resize(128 if reduced else 256,1_000_000 if reduced else 4_000_000)
        quality=profile(reduced)
        if quality.size_step>1: extent=max(1,round(extent/quality.size_step)*quality.size_step)
        for path in self.catalog.candidates.get((owner, model), ()):
            original = self._load(path)
            if original is None:
                continue
            size = fit_dimensions(original.get_size(), extent)
            # Demi-degré : le mouvement n'est plus réduit à des sauts de 15 degrés.
            angle = round(round((angle_degrees % 360)/quality.angle_step)*quality.angle_step*2) % 720
            key = path, size, angle
            rotated = self.rotations.get(key)
            if rotated is not None:
                return rotated
            base_key = path, size
            scaled = self.scaled.get(base_key)
            if scaled is None:
                scaled = self.backend.transform.smoothscale(original, size)
                self.scaled.put(base_key, scaled)
            native_offset = self.catalog.orientation_offset(path)
            rotated = self.backend.transform.rotozoom(scaled, native_offset - angle / 2, 1.0)
            self.rotations.put(key, rotated)
            return rotated
        return None
