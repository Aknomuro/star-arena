"""Génération déterministe des planètes, sans construire de défense gratuite."""
from math import cos, sin
from random import Random
from star_arena.domain.models import Campaign, Planet
from star_arena.domain.planet_stats import PLANET_TYPES


def ensure_planets(c: Campaign) -> None:
    for s in c.systems.values():
        if s.planets:
            continue
        rng = Random(c.seed ^ (s.id*104729+7919))
        for index in range(rng.randint(1,5)):
            kind = rng.choice(tuple(PLANET_TYPES))
            s.planets.append(Planet(s.id*10+index+1, f'{s.name} {index+1}', kind, s.owner,
                                    float(rng.randint(1,8)), PLANET_TYPES[kind][1], rng.randint(2,6)))


def planet_position(index: int) -> tuple[float,float]:
    radius = 90 + index*64
    angle = .6+index*2.25
    return cos(angle)*radius, sin(angle)*radius
