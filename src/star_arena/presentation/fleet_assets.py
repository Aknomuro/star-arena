"""Catalogue et géométrie des sprites, testables sans importer Pygame."""
from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
import struct
import zlib


@dataclass(frozen=True)
class FleetPalette:
    slug: str
    body: tuple[int, int, int]
    accent: tuple[int, int, int]


PALETTES = {
    0: FleetPalette("republic", (236, 245, 252), (64, 175, 237)),
    1: FleetPalette("empire", (65, 70, 80), (235, 75, 83)),
    2: FleetPalette("alliance", (238, 230, 210), (244, 149, 56)),
}
VISUAL_LENGTHS = {"fighter": 42, "corvette": 72, "cruiser": 112}
MIN_LENGTHS = {"fighter": 12, "corvette": 22, "cruiser": 34}
MAX_PNG_BYTES = 8_000_000
MAX_PNG_PIXELS = 4_000_000


def display_extent(model: str, zoom: float) -> int:
    if not isfinite(zoom) or zoom <= 0:
        raise ValueError("Zoom invalide.")
    return max(MIN_LENGTHS[model], round(VISUAL_LENGTHS[model] * min(zoom, 1.4)))


def fit_dimensions(size: tuple[int, int], maximum: int) -> tuple[int, int]:
    width, height = size
    if width <= 0 or height <= 0 or maximum <= 0:
        raise ValueError("Dimensions de sprite invalides.")
    factor = maximum / max(width, height)
    return max(1, round(width * factor)), max(1, round(height * factor))


def png_dimensions(path: Path) -> tuple[int, int]:
    """Lire 33 octets avant tout décodage pour borner la taille d'une image réelle."""
    if not 33 <= path.stat().st_size <= MAX_PNG_BYTES:
        raise ValueError("Fichier PNG vide ou trop volumineux.")
    with path.open("rb") as stream:
        header = stream.read(33)
    if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[8:16] != b"\x00\x00\x00\rIHDR":
        raise ValueError("En-tête PNG invalide.")
    if zlib.crc32(header[12:29]) != struct.unpack(">I", header[29:33])[0]:
        raise ValueError("En-tête PNG corrompu.")
    width, height = struct.unpack(">II", header[16:24])
    if not 1 <= width <= 4096 or not 1 <= height <= 4096 or width * height > MAX_PNG_PIXELS:
        raise ValueError("Dimensions PNG trop grandes.")
    return width, height


class SpriteCatalog:
    def __init__(self, root: Path, available: set[Path] | None = None) -> None:
        self.root = root
        self.metadata: dict[Path, dict] = {}
        self.manifest_error: str | None = None
        manifest = root / "manifest.json"
        if manifest.is_file():
            try:
                if manifest.stat().st_size > 32_000:
                    raise ValueError("Manifest de sprites trop volumineux.")
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if data.get("schema_version") != 1 or not isinstance(data.get("entries"), list) or len(data["entries"]) > 9:
                    raise ValueError("Manifest de sprites invalide.")
                entries = {}
                slugs = {p.slug for p in PALETTES.values()}
                for entry in data["entries"]:
                    if (entry["faction"] not in slugs or entry["class"] not in VISUAL_LENGTHS
                            or entry["file"] != f"{entry['faction']}/{entry['class']}.png"
                            or entry.get("forward", "right") not in ("up", "right", "down", "left")):
                        raise ValueError("Affectation de sprite invalide.")
                    path = root / entry["file"]
                    if path in entries:
                        raise ValueError("Affectation de sprite dupliquée.")
                    entries[path] = entry
                self.metadata = entries
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
                self.manifest_error = str(error)
        exists = (lambda path: path in available) if available is not None else Path.is_file
        self.paths: dict[tuple[int, str], Path | None] = {}
        self.candidates: dict[tuple[int, str], tuple[Path, ...]] = {}
        for owner, palette in PALETTES.items():
            for model in VISUAL_LENGTHS:
                candidates = root / palette.slug / f"{model}.png", root / f"{model}.png"
                self.candidates[owner, model] = tuple(path for path in candidates if exists(path))
                self.paths[owner, model] = next(iter(self.candidates[owner, model]), None)

    def inventory(self) -> list[dict]:
        return [{"faction": PALETTES[owner].slug, "class": model,
                 "expected": f"{PALETTES[owner].slug}/{model}.png",
                 "available": str(path.relative_to(self.root)).replace("\\", "/") if path is not None else None,
                 "dedicated": path is not None and path.parent != self.root,
                 "source_file": self.metadata.get(path, {}).get("source_file"),
                 "forward": self.metadata.get(path, {}).get("forward", "right")}
                for (owner, model), path in self.paths.items()]

    def orientation_offset(self, path: Path) -> int:
        """Normaliser le cap natif sans réécrire les pixels du fichier source."""
        forward = self.metadata.get(path, {}).get("forward", "right")
        return {"up": -90, "right": 0, "down": 90, "left": 180}[forward]
