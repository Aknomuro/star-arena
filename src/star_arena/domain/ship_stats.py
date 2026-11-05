"""Caractéristiques tactiques ; les coques/boucliers historiques restent dans models."""
from dataclasses import dataclass
from star_arena.domain.planet_stats import STATIONS, DEFENSES


@dataclass(frozen=True)
class ShipStats:
    damage: float
    cooldown: float
    reach: float
    projectile_speed: float
    speed: float
    turn_rate: float
    radius: float
    turrets: int


COMBAT_STATS = {
    "fighter": ShipStats(5.0, 0.24, 260.0, 800.0, 145.0, 4.5, 12.0, 1),
    "corvette": ShipStats(13.0, 0.60, 390.0, 720.0, 90.0, 2.5, 22.0, 2),
    "cruiser": ShipStats(30.0, 1.25, 560.0, 650.0, 48.0, 1.0, 36.0, 4),
}

for level, spec in STATIONS.items():
    COMBAT_STATS[f"station{level}"] = ShipStats(18.+level*4, 1., 600.+level*35, 720., 0., 0., 44.+level*5, spec[3])
for kind, spec in DEFENSES.items():
    COMBAT_STATS[kind] = ShipStats(spec[6], 1., spec[7], 800., 0., 0., 26., 1)


def damage_multiplier(source: str, target: str) -> float:
    if source == "laser" and target == "fighter":
        return 2.5
    if source == "missile" and target in ("cruiser", "corvette"):
        return 2.4
    if source == "heavy" and target not in ("fighter",):
        return 1.5
    if source == "fighter" and target == "fighter":
        return 1.25
    if source == "corvette" and target == "fighter":
        return 1.55
    if source == "cruiser" and target in ("corvette", "cruiser"):
        return 1.30
    return 1.0
