"""Positions de formation communes aux commandes RTS et au déploiement."""
from math import ceil, sqrt

FORMATIONS = ("line", "wedge", "compact")
FORMATION_NAMES = ("Ligne", "Coin", "Compacte")


def offsets(count: int, formation: str = "compact") -> list[tuple[float, float]]:
    if formation not in FORMATIONS:
        raise ValueError("Formation inconnue.")
    result = []
    columns = max(1, ceil(sqrt(count)))
    for i in range(count):
        if formation == "line":
            result.append((-(i // 12) * 110.0, (i % 12 - (min(count, 12) - 1) / 2) * 96.0))
        elif formation == "wedge":
            rank = (i + 1) // 2
            result.append((-rank * 94.0, rank * 94.0 * (1 if i % 2 else -1)))
        else:
            result.append(((i % columns - (columns - 1) / 2) * 104.0,
                           (i // columns - (ceil(count / columns) - 1) / 2) * 104.0))
    return result
