"""Inventaire des vrais fichiers et en-têtes PNG, sans import ni décodage Pygame."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "src"))
    from star_arena.presentation.fleet_assets import SpriteCatalog, png_dimensions

    root = project / "assets" / "ships"
    catalog = SpriteCatalog(root)
    rows = catalog.inventory()
    present = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".png":
            continue
        row = {"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": path.stat().st_size}
        try:
            row["dimensions"] = png_dimensions(path)
            row["header_valid"] = True
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            entry = catalog.metadata.get(path, {})
            row["matches_imported_source"] = row["sha256"] == entry["sha256"] if "sha256" in entry else None
            with path.open("rb") as stream:
                header = stream.read(33)
            row["png_color_type"] = header[25]
            row["alpha_channel_declared"] = header[25] in (4, 6)
        except (OSError, ValueError) as error:
            row["header_valid"] = False
            row["error"] = str(error)
        present.append(row)
    result = {
        "scope": "Fichiers présents dans assets/ships et en-têtes seulement ; aucun décodage d'image",
        "png_files_present": len(present), "files": present, "slots": rows,
        "missing_slots": sum(row["available"] is None for row in rows),
        "dedicated_slots_available": sum(row["dedicated"] for row in rows),
        "manifest_error": catalog.manifest_error,
        "pygame_imported": "pygame" in sys.modules, "graphics_executed": False,
        "images_generated": False,
    }
    if args.report:
        (project / "docs" / "SHIP_ASSETS_0_2_1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
