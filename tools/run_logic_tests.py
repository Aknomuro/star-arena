"""Un seul processus de tests purs : aucun import de Pygame ni création de fenêtre."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
import unittest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    from star_arena import __version__
    started = perf_counter()
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    pygame_imported = any(name == "pygame" or name.startswith("pygame.") for name in sys.modules)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "tests_run": result.testsRun,
        "project_version": __version__,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "elapsed_seconds": round(perf_counter() - started, 4),
        "pygame_imported": pygame_imported, "graphics_executed": False,
        "success": result.wasSuccessful() and not pygame_imported,
        "details": [{"test": str(test), "traceback": trace} for test, trace in result.failures + result.errors],
    }
    if args.report:
        directory = root / "docs"
        directory.mkdir(exist_ok=True)
        filename = "LOGIC_TESTS_" + __version__.replace(".", "_") + ".json"
        (directory / filename).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
