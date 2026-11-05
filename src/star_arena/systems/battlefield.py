"""Configuration tactique contextuelle, calculée une seule fois par engagement."""
from dataclasses import dataclass
from math import cos, sin, pi, hypot
from random import Random
from star_arena.domain.ship_stats import COMBAT_STATS


@dataclass(frozen=True)
class PlanetBackdrop:
    id: int
    name: str
    kind: str
    owner: int | None
    x: float
    y: float
    radius: float


@dataclass
class Battlefield:
    planets: list[PlanetBackdrop]
    structures: dict[int,tuple[float,float]]
    asteroids: list[tuple[float,float,float]]


def generate_battlefield(campaign,engagement):
    s=campaign.systems[engagement.system_id]
    rng=Random(campaign.seed ^ (s.id*104729+773))
    left=engagement.defender==campaign.player
    count=len(s.planets)
    planets=[]; structures={}; occupied=[]
    for i,p in enumerate(s.planets):
        x=(1070 if left else 2130)+(i%2)*(-110 if left else 110)
        y=1000 if count==1 else 280+i*1440/(count-1)
        radius=70+min(30,p.population*3)
        planets.append(PlanetBackdrop(p.id,p.name,p.kind,p.owner,x,y,radius))
        for index,b in enumerate(p.orbitals):
            if b.unit is None or not b.unit.alive: continue
            angle=(index*.95)+(0 if left else pi)
            r=radius+110
            body=COMBAT_STATS[b.unit.model].radius
            for attempt in range(30):
                a=angle+attempt*.37
                px=max(100.,min(3100.,x+cos(a)*r))
                py=max(100.,min(1900.,y+sin(a)*r))
                if all(hypot(px-u,py-v)>=body+size+18 for u,v,size in occupied):
                    break
            structures[b.unit.id]=(px,py)
            occupied.append((px,py,body))
    cells=[(1500+(i%3)*160,250+(i//3)*300) for i in range(15)]
    asteroids=[]
    for x,y in rng.sample(cells,9+s.richness):
        x+=rng.uniform(-25,25); y+=rng.uniform(-25,25); r=rng.uniform(30,55)
        if all(hypot(x-u,y-v)>r+90 for u,v in structures.values()):
            asteroids.append((x,y,r))
    return Battlefield(planets,structures,asteroids)
