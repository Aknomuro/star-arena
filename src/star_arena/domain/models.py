from dataclasses import dataclass, field
from math import hypot, isfinite
from star_arena.domain.planet_stats import ORBITAL_TYPES

Point = tuple[float, float]
Color = tuple[int, int, int]


@dataclass(frozen=True)
class Faction:
    id: int
    name: str
    color: Color
    description: str


FACTIONS = (
    Faction(0, "République stellaire", (65, 188, 239), "Explorateurs et défenseurs des mondes libres."),
    Faction(1, "Empire galactique", (242, 104, 104), "Une flotte unie sous une autorité impériale."),
    Faction(2, "Alliance des mondes", (238, 183, 74), "Une coalition de systèmes indépendants."),
)


@dataclass
class StarSystem:
    id: int
    name: str
    position: Point
    owner: int | None = None
    capital: bool = False
    richness: int = 1
    shipyard: int = 0
    queue: list["Production"] = field(default_factory=list)
    yard_owner: int | None = None
    planets: list["Planet"] = field(default_factory=list)


@dataclass
class Production:
    model: str
    remaining: float


@dataclass
class Resources:
    credits: float = 600.0
    minerals: float = 350.0
    energy: float = 0.0


@dataclass
class Ship:
    id: int
    model: str
    hull: float
    shield: float
    status: str = "permanent"

    @property
    def alive(self) -> bool:
        return self.hull > 0

    def receive_damage(self, amount: float) -> float:
        """Dégâts effectifs, bouclier avant coque ; aucun retour à la vie."""
        if not isfinite(amount):
            raise ValueError("Les dégâts doivent être finis.")
        if not self.alive or amount <= 0:
            return 0.0
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        hit = min(self.hull, amount - absorbed)
        self.hull -= hit
        return absorbed + hit


SHIP_TYPES = {
    "fighter": ("Chasseur", 100.0, 60.0),
    "corvette": ("Corvette", 480.0, 220.0),
    "cruiser": ("Croiseur", 1500.0, 800.0),
}

SHIP_TYPES.update(ORBITAL_TYPES)


@dataclass
class Building:
    kind: str
    level: int
    unit: Ship | None = None


@dataclass
class BuildJob:
    kind: str
    level: int
    remaining: float


@dataclass
class Planet:
    id: int
    name: str
    kind: str
    owner: int | None
    population: float
    richness: int
    capacity: int
    ground: dict[str, int] = field(default_factory=dict)
    orbitals: list[Building] = field(default_factory=list)
    jobs: list[BuildJob] = field(default_factory=list)
    militia: list[Ship] = field(default_factory=list)
    militia_clock: float = 0.0
    occupier: int | None = None
    occupation: float = 0.0


@dataclass
class Travel:
    origin: int
    destination: int
    elapsed: float
    duration: float

    @property
    def progress(self) -> float:
        return min(1.0, max(0.0, self.elapsed / self.duration))


@dataclass
class Fleet:
    id: int
    owner: int
    system_id: int
    ships: list[Ship] = field(default_factory=list)
    travel: Travel | None = None
    status: str = "permanent"
    final_destination: int | None = None
    itinerary: list[int] = field(default_factory=list)
    segment_index: int = 0
    navigation_state: str = 'idle'
    arrival_mode: str = 'move'
    merge_target: int | None = None

    @property
    def destroyed(self) -> bool:
        return not self.ships

    def position(self, systems: dict[int, StarSystem]) -> Point:
        if self.travel is None:
            return systems[self.system_id].position
        a = systems[self.travel.origin].position
        b = systems[self.travel.destination].position
        t = self.travel.progress
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


@dataclass
class Campaign:
    player: int
    seed: int
    systems: dict[int, StarSystem]
    routes: set[tuple[int, int]]
    fleets: dict[int, Fleet]
    time: float = 0.0
    next_ai_at: float = 6.0
    events: list[str] = field(default_factory=list)
    step_remainder: float = 0.0
    pending: "Engagement | None" = None
    reports: list["BattleReport"] = field(default_factory=list)
    next_engagement_id: int = 1
    resources: dict[int, Resources] = field(default_factory=lambda: {i: Resources() for i in range(3)})
    economy_remainder: float = 0.0
    next_ship_id: int = 25
    next_fleet_id: int = 4

    def neighbors(self, system_id: int) -> list[int]:
        return sorted(b if a == system_id else a for a, b in self.routes if system_id in (a, b))

    def fleets_at(self, system_id: int) -> list[Fleet]:
        return [f for f in self.fleets.values() if f.travel is None and f.system_id == system_id]

    def log(self, message: str) -> None:
        self.events.insert(0, f"[{int(self.time) // 60:02}:{int(self.time) % 60:02}] {message}")
        del self.events[12:]

    def distance(self, a: int, b: int) -> float:
        p, q = self.systems[a].position, self.systems[b].position
        return hypot(p[0] - q[0], p[1] - q[1])


@dataclass(frozen=True)
class EngagedShip:
    id: int
    fleet_id: int
    owner: int
    model: str
    hull: float
    shield: float


@dataclass
class Engagement:
    id: int
    system_id: int
    origin: int
    attacker: int
    defender: int
    initial: list[EngagedShip]


@dataclass
class BattleReport:
    id: int
    system_id: int
    attacker: int
    defender: int
    winner: int | None
    previous_owner: int | None
    new_owner: int | None
    engaged: dict[int, int]
    destroyed: dict[int, int]
    survivors: dict[int, int]
    captured: dict[int, int]
    cruisers: list[EngagedShip]
    automatic: bool = False
    retreat: bool = False
