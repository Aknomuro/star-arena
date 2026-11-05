"""Engagements, résolution abstraite et application unique des pertes à la campagne."""
from star_arena.systems.navigation import clear_order
from collections import Counter
from star_arena.systems.planets import prepare_garrison, finish_garrison, begin_occupation, support
from random import Random

from star_arena.config import TRAVEL_SPEED
from star_arena.domain.models import BattleReport, Campaign, EngagedShip, Engagement, Fleet, Ship, Travel
from star_arena.domain.ship_stats import COMBAT_STATS, damage_multiplier


def military_power(ships: list[Ship]) -> float:
    return sum((s.hull + s.shield) ** 0.5 * COMBAT_STATS[s.model].damage * COMBAT_STATS[s.model].turrets
               / COMBAT_STATS[s.model].cooldown for s in ships if s.alive)


def create_engagement(campaign: Campaign, fleet: Fleet, origin: int, defender: int) -> Engagement:
    if campaign.pending is not None:
        raise ValueError("Un engagement est déjà en attente.")
    prepare_garrison(campaign, fleet.system_id)
    initial = [EngagedShip(ship.id, other.id, other.owner, ship.model, ship.hull, ship.shield)
               for other in sorted(campaign.fleets_at(fleet.system_id), key=lambda f: f.id)
               if other.owner in (fleet.owner, defender) for ship in other.ships if ship.alive]
    if {item.owner for item in initial} != {fleet.owner, defender}:
        raise ValueError("Deux forces opposées sont nécessaires.")
    if len({s.id for s in initial}) != len(initial):
        raise ValueError("Identifiants de vaisseaux dupliqués.")
    engagement = Engagement(campaign.next_engagement_id, fleet.system_id, origin, fleet.owner, defender, initial)
    campaign.next_engagement_id += 1
    campaign.pending = engagement
    for other in campaign.fleets_at(fleet.system_id):
        if other.final_destination is not None and other.owner in (fleet.owner,defender):
            other.navigation_state="engaged"
    campaign.log(f"Conflit orbital à {campaign.systems[fleet.system_id].name}.")
    return engagement


def engaged_ships(campaign: Campaign, engagement: Engagement) -> dict[int, Ship]:
    expected = {item.id: item for item in engagement.initial}
    if len(expected) != len(engagement.initial):
        raise ValueError("Identifiants de bataille dupliqués.")
    found = {}
    for fleet_id in {item.fleet_id for item in engagement.initial}:
        fleet = campaign.fleets.get(fleet_id)
        if fleet is None or fleet.travel is not None or fleet.system_id != engagement.system_id:
            raise ValueError("Flotte engagée absente ou déplacée.")
        for ship in fleet.ships:
            record = expected.get(ship.id)
            if record is None or ship.id in found or record.fleet_id != fleet.id or record.owner != fleet.owner or record.model != ship.model:
                raise ValueError("Composition de bataille incohérente.")
            found[ship.id] = ship
    if found.keys() != expected.keys():
        raise ValueError("Un vaisseau engagé est absent.")
    return found


def resolve_engagement(campaign: Campaign, engagement: Engagement, winner: int | None,
                       *, automatic: bool = False, retreat: bool = False) -> BattleReport:
    for report in campaign.reports:
        if report.id == engagement.id:
            return report
    if campaign.pending is None or campaign.pending.id != engagement.id:
        raise ValueError("Cet engagement n'est plus actif.")
    if winner not in (None, engagement.attacker, engagement.defender):
        raise ValueError("Vainqueur invalide.")
    ships = engaged_ships(campaign, engagement)
    if winner is not None and not any(ships[s.id].alive for s in engagement.initial if s.owner == winner):
        raise ValueError("Une faction sans survivants ne peut pas gagner.")
    for f in campaign.fleets_at(engagement.system_id):
        if f.status == 'garrison' and winner is not None and f.owner != winner:
            for u in f.ships:
                u.hull=0.; u.shield=0.
    owners = (engagement.attacker, engagement.defender)
    engaged = dict(Counter(item.owner for item in engagement.initial))
    destroyed = {owner: sum(not ships[item.id].alive for item in engagement.initial if item.owner == owner) for owner in owners}
    captured = dict.fromkeys(owners, 0)
    system = campaign.systems[engagement.system_id]
    previous_owner = system.owner
    if winner is not None:
        # Un défenseur victorieux doit aussi pouvoir occuper un système contesté
        # resté neutre, notamment après le chargement d'un tel engagement.
        system.owner = winner
        if system.yard_owner != system.owner:
            system.queue.clear()
            system.yard_owner = system.owner
    for fleet_id in sorted({item.fleet_id for item in engagement.initial}):
        fleet = campaign.fleets[fleet_id]
        if fleet.status == "garrison":
            continue
        fleet.ships[:] = [ship for ship in fleet.ships if ship.alive]
        if not fleet.ships:
            clear_order(fleet,"destroyed")
            fleet.travel = None  # La flotte vide reste dans l'historique de campagne.
            continue
        losing = (winner is not None and fleet.owner != winner) or (winner is None and fleet.owner == engagement.attacker)
        if not losing:
            continue
        clear_order(fleet,"cancelled")
        refuges = [i for i in campaign.neighbors(system.id) if campaign.systems[i].owner == fleet.owner]
        destination = engagement.origin if engagement.origin in refuges else (refuges[0] if refuges else None)
        if destination is None:
            captured[fleet.owner] += len(fleet.ships)
            fleet.ships.clear()
        else:
            duration = max(2.0, campaign.distance(system.id, destination) / TRAVEL_SPEED)
            fleet.travel = Travel(system.id, destination, 0.0, duration)
    survivors = {owner: engaged[owner] - destroyed[owner] - captured[owner] for owner in owners}
    cruisers = [EngagedShip(item.id, item.fleet_id, item.owner, item.model, ships[item.id].hull, ships[item.id].shield)
                for item in engagement.initial if item.model == "cruiser"]
    report = BattleReport(engagement.id, system.id, *owners, winner, previous_owner, system.owner,
                          engaged, destroyed, survivors, captured, cruisers, automatic, retreat)
    campaign.reports.insert(0, report)
    del campaign.reports[20:]
    finish_garrison(campaign, system.id, winner)
    campaign.pending = None
    if winner is not None:
        begin_occupation(campaign, system.id)
    campaign.log(f"Bataille terminée à {system.name} : {sum(destroyed.values())} détruits, {sum(survivors.values())} survivants.")
    return report


def auto_resolve(campaign: Campaign) -> BattleReport:
    engagement = campaign.pending
    if engagement is None:
        raise ValueError("Aucun engagement à résoudre.")
    ships = engaged_ships(campaign, engagement)
    rng = Random(campaign.seed ^ (engagement.id * 1_000_003))
    teams = {owner: [ships[s.id] for s in engagement.initial if s.owner == owner]
             for owner in (engagement.attacker, engagement.defender)}
    for _ in range(180):
        alive = {owner: [s for s in team if s.alive] for owner, team in teams.items()}
        if not all(alive.values()):
            break
        for team in alive.values():
            support(team, 1.)
        hits: dict[int, float] = {}
        for owner, team in alive.items():
            enemies = alive[engagement.defender if owner == engagement.attacker else engagement.attacker]
            for ship in team:
                stats = COMBAT_STATS[ship.model]
                target = max(enemies, key=lambda s: damage_multiplier(ship.model, s.model) + rng.random() * 0.3)
                damage = stats.damage * stats.turrets / stats.cooldown * (1.1 if any(u.model=="radar" and u.alive for u in team) else 1.) * damage_multiplier(ship.model, target.model) * rng.uniform(0.85, 1.15)
                hits[target.id] = hits.get(target.id, 0.0) + damage
        for ship_id, damage in hits.items():
            ships[ship_id].receive_damage(damage)
    powers = {owner: military_power(team) for owner, team in teams.items()}
    winner = None if not any(powers.values()) else max((engagement.defender, engagement.attacker), key=lambda owner: powers[owner])
    return resolve_engagement(campaign, engagement, winner, automatic=True)
