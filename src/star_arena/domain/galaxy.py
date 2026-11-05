"""Galaxie arrondie reproductible ; géométrie historique disponible pour les anciennes fixtures."""
from random import Random

from star_arena.config import FACTION_CAPITALS
from star_arena.domain.models import Campaign, Fleet, SHIP_TYPES, Ship, StarSystem

NAMES = (
    "Sol", "Vega", "Altair", "Deneb", "Arcturus",
    "Sirius", "Orion", "Néréis", "Rigel", "Antarès",
    "Éridan", "Lyra", "Aldébaran", "Procyon", "Nova",
)


def new_campaign(player: int = 0, seed: int = 42, system_count: int = 60, layout: str = "round") -> Campaign:
    if type(player) is not int or player not in range(3):
        raise ValueError("La faction doit être comprise entre 0 et 2.")
    if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
        raise ValueError("La graine doit être un entier entre 0 et 2147483647.")
    if system_count not in (15, 30, 60, 100):
        raise ValueError("Tailles disponibles : 15, 30, 60 ou 100.")
    if layout not in ("round","legacy"):
        raise ValueError("Forme de galaxie inconnue.")
    rng = Random(seed)
    columns = {15: 5, 30: 6, 60: 10, 100: 10}[system_count]
    rows = system_count // columns
    systems = {}
    for i in range(system_count):
        name = NAMES[i % len(NAMES)] + (f" {i // len(NAMES) + 1}" if i >= 15 else "")
        systems[i] = StarSystem(i, name, ((i % columns - (columns-1)/2) * 310 + rng.uniform(-38, 38),
                                        (i // columns - (rows-1)/2) * 310 + rng.uniform(-38, 38)),
                                richness=rng.choice((1, 1, 2, 3, 4)))
    routes = set()
    for i in systems:
        if i % columns < columns - 1:
            routes.add((i, i + 1))
        # Deux liaisons par frontière : des passages stratégiques, jamais d'isolat.
        if i + columns < system_count and (i % columns in (1, columns-2) or system_count == 15):
            routes.add((i, i + columns))
    if system_count == 15:
        routes.update({(1, 7), (3, 9), (5, 11), (8, 14)})
    capitals = FACTION_CAPITALS if system_count == 15 else (0, columns-1, system_count-columns//2)
    if layout=="round":
        from star_arena.domain.galaxy_layout import round_layout
        routes=round_layout(systems,capitals,rng)
    fleets = {}
    ship_id = 1
    for owner, capital in enumerate(capitals):
        systems[capital].owner = owner
        systems[capital].capital = True
        systems[capital].richness = 4
        ships = []
        for model in ("cruiser", "corvette", "corvette", "fighter", "fighter", "fighter", "fighter", "fighter"):
            _, hull, shield = SHIP_TYPES[model]
            ships.append(Ship(ship_id, model, hull, shield))
            ship_id += 1
        fleets[owner + 1] = Fleet(owner + 1, owner, capital, ships)
    campaign = Campaign(player, seed, systems, routes, fleets)
    from star_arena.domain.planet_generation import ensure_planets
    ensure_planets(campaign)
    campaign.log("Campagne créée. Explorez les systèmes neutres.")
    return campaign
