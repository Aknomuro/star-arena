"""Lancement manuel depuis le dossier du projet, sans installation du paquet."""
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    import asyncio
    from star_arena.app import run_game

    result = asyncio.run(run_game())
    # Sur Pygbag asyncio.run programme la coroutine sans attendre sa fin.
    if sys.platform != 'emscripten':
        raise SystemExit(result)
