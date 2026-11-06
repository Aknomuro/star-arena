"""Réglages légers de cette première version Python."""
import os
import sys
from pathlib import Path

WINDOW_SIZE = (1280, 800)
FPS_LIMIT = 30
BACKGROUND_FPS_LIMIT = 10
SIMULATION_STEP = 0.1
MAX_SIMULATION_STEPS = 5
AI_INTERVAL = 6.0
GALAXY_SEED = 42
TRAVEL_SPEED = 65.0
FACTION_CAPITALS = (0, 4, 12)
SAVE_VERSION = 5
MAX_SAVE_BYTES = 2_000_000
TEXT_CACHE_ENTRIES = 256
TEXT_CACHE_PIXELS = 2_000_000
BATTLE_SIZE = (3200.0, 2000.0)
BATTLE_STEP = 1 / 30
TACTICAL_AI_INTERVAL = 0.35
ACTIVE_UNITS_PER_SIDE = 48
MAX_PROJECTILES = 256
MAX_EFFECTS = 100


def project_root() -> Path:
    """Racine des ressources, avec ou sans le préfixe src du développement PC."""
    parent = Path(__file__).resolve().parent.parent
    return parent.parent if parent.name == 'src' else parent


def default_save_path() -> Path:
    """Préserver les saves locales ; ne jamais écrire dans site-packages."""
    if sys.platform == 'emscripten':
        return Path('saves/campaign.json')  # Identifiant uniquement : stockage via BrowserStore.
    root = project_root()
    if (root / "src" / "star_arena" / "app.py").is_file():
        return root / "saves" / "campaign.json"
    base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home()
    return base / "StarArena" / "saves" / "campaign.json"
