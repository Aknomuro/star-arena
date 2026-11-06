"""Lancement manuel depuis le dossier du projet, sans installation du paquet."""
from pathlib import Path
import sys
import asyncio
import importlib
import json
import traceback


def boot_report(phase, message):
    """Disponible avant tout import du jeu, y compris si cet import échoue."""
    if sys.platform != 'emscripten':
        return
    print('[STAR ARENA boot]', phase, message)
    try:
        import platform
        payload = json.dumps([phase, str(message)], ensure_ascii=True)
        platform.window.eval('window.starArenaBoot && window.starArenaBoot.step(...' + payload + ')')
    except Exception:
        traceback.print_exc()  # Le diagnostic ne doit jamais empêcher le lancement.


async def bootstrap():
    try:
        boot_report('python', 'Python ' + sys.version.split()[0] + ' : main.py exécuté')
        root = Path(__file__).resolve().parent
        # PC : src/star_arena ; archive Web : star_arena directement à la racine.
        sys.path.insert(0, str(root))
        if (root / 'src').is_dir():
            sys.path.insert(0, str(root / 'src'))
        boot_report('imports', 'Import du moteur STAR ARENA')
        # Le préchargeur Pygbag ne doit pas tenter d'installer le paquet local depuis PyPI.
        module = importlib.import_module('star_arena.app')
        result = await module.run_game(on_boot=boot_report)
        if result:
            boot_report('error', 'Le jeu a quitté le démarrage avec le code ' + str(result) + '. Consulter la console Python/WASM.')
        return result
    except Exception:
        detail = traceback.format_exc()
        boot_report('error', detail)
        if sys.platform != 'emscripten':
            raise
        return 1

if __name__ == "__main__" or sys.platform == 'emscripten':
    result = asyncio.run(bootstrap())
    # Sur Pygbag asyncio.run programme la coroutine sans attendre sa fin.
    if sys.platform != 'emscripten':
        raise SystemExit(result)
