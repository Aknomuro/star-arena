from star_arena.systems.navigation import find_path, set_order, continue_order, arrived, RoutePlanner
from math import isfinite
from random import Random
from star_arena.systems.planets import prepare_garrison, begin_occupation, defensive_units

from star_arena.config import AI_INTERVAL, MAX_SIMULATION_STEPS, SIMULATION_STEP, TRAVEL_SPEED
from star_arena.domain.models import Campaign, Fleet, Travel
from star_arena.systems.combat import auto_resolve, create_engagement, military_power
from star_arena.systems.economy import EconomySystem, GalacticEconomy, transfer


class Simulation:
    def __init__(self, campaign: Campaign, economy: EconomySystem | None = None, human_factions: set[int] | None = None) -> None:
        self.human_factions = set(human_factions) if human_factions is not None else {campaign.player}
        self.campaign = campaign
        self.planner = RoutePlanner(campaign)
        self.economy = economy if economy is not None else GalacticEconomy(self.human_factions)

    @property
    def accumulator(self) -> float:
        return self.campaign.step_remainder

    @accumulator.setter
    def accumulator(self, value: float) -> None:
        self.campaign.step_remainder = value

    def movement_error(self, fleet_id: int, destination: int, owner: int) -> str:
        """Validation commune à l'interface et aux ordres, sans modifier l'état."""
        c = self.campaign
        if c.pending is not None:
            return "Résolvez d'abord le conflit orbital."
        fleet = c.fleets.get(fleet_id)
        if fleet is None or fleet.owner != owner:
            return "Sélectionnez une de vos flottes."
        if fleet.status != "permanent":
            return "Les garnisons ne peuvent pas quitter leur système."
        if fleet.destroyed:
            return "Cette flotte a été détruite."
        origin=fleet.travel.destination if fleet.travel else fleet.system_id
        if not self.planner.find(origin,destination):
            return "Aucune route valide vers ce système."
        return ""

    def order_move(self, fleet_id: int, destination: int, owner: int) -> str:
        """Chaîne vide en cas de succès, message français sinon."""
        error = self.movement_error(fleet_id, destination, owner)
        if error:
            return error
        c = self.campaign
        fleet = c.fleets[fleet_id]
        system = c.systems[destination]
        error=set_order(c,fleet,destination)
        if error: return error
        c.log(f"Flotte {fleet.id} en route vers {system.name}.")
        return ""

    def advance(self, dt: float) -> None:
        if self.campaign.pending is not None:
            return
        if not isfinite(dt) or dt <= 0:
            return
        # Aucun rattrapage massif après une fenêtre bloquée ou déplacée.
        self.accumulator += min(dt, MAX_SIMULATION_STEPS * SIMULATION_STEP)
        steps = min(MAX_SIMULATION_STEPS, int((self.accumulator + 1e-9) / SIMULATION_STEP))
        self.accumulator = max(0.0, self.accumulator - steps * SIMULATION_STEP)
        for _ in range(steps):
            self._tick(SIMULATION_STEP)
            if self.campaign.pending is not None:
                self.accumulator = 0.0
                break

    def _tick(self, dt: float) -> None:
        c = self.campaign
        c.time = round(c.time + dt, 9)
        for fleet in sorted(c.fleets.values(),key=lambda f:f.id):
            continue_order(c,fleet,self.planner)
            self.finish_arrival(fleet)
        self.economy.update(c, dt)
        arrivals: dict[int, list[tuple[Fleet, Travel]]] = {}
        # Avancer toutes les horloges avant qu'un conflit suspende la campagne.
        for fleet in sorted(c.fleets.values(), key=lambda item: item.id):
            travel = fleet.travel
            if travel is None:
                continue
            travel.elapsed = min(travel.duration, travel.elapsed + dt)
            if travel.elapsed >= travel.duration:
                arrivals.setdefault(travel.destination, []).append((fleet, travel))
        for destination in sorted(arrivals):
            self._arrive_group(arrivals[destination])
            if c.pending is not None:
                return
        if c.time + 1e-9 >= c.next_ai_at:
            # Reprendre un état ancien sans lancer une rafale de décisions IA.
            c.next_ai_at = max(c.next_ai_at + AI_INTERVAL, c.time + AI_INTERVAL)
            self._expand_ai()

    def _arrive_group(self, arrivals: list[tuple[Fleet, Travel]]) -> None:
        c = self.campaign
        target = c.systems[arrivals[0][1].destination]
        for fleet, _ in arrivals:
            fleet.system_id = target.id
            fleet.travel = None
            arrived(fleet, target.id)
        if target.owner is not None and any(f.owner != target.owner for f, _ in arrivals):
            prepare_garrison(c, target.id)
        forces = sorted((f for f in c.fleets_at(target.id) if f.ships), key=lambda f: f.id)
        owners = {f.owner for f in forces}
        if len(owners) > 1:
            defender = target.owner if target.owner in owners else forces[0].owner
            attacker, travel = next((f, t) for f, t in arrivals if f.owner != defender)
            # Le RTS reste à deux camps : un tiers attend à l'arrivée, sans perdre
            # sa route ni ses vaisseaux, puis sera traité après ce conflit.
            for other, previous_trip in arrivals:
                if other.owner not in (attacker.owner, defender):
                    other.system_id = previous_trip.origin
                    other.travel = previous_trip
                    other.segment_index=max(0,other.segment_index-1)
                    other.navigation_state="transit"
            if target.owner not in owners:
                target.owner = defender  # Priorité d'occupation V0.2, stable par ID.
            engagement = create_engagement(c, attacker, travel.origin, defender)
            if not self.human_factions.intersection((engagement.attacker,engagement.defender)):
                auto_resolve(c)
            return
        for fleet, _ in arrivals:
            # Seul l'arrêt final revendique un système sans défense. Le transit ne colonise rien.
            if target.owner!=fleet.owner and (fleet.final_destination is None or fleet.final_destination==target.id):
                target.owner=fleet.owner
                if target.yard_owner!=target.owner:
                    target.queue.clear(); target.yard_owner=target.owner
                begin_occupation(c,target.id)
                c.log(f'{target.name} occupé par la flotte {fleet.id}.')
            else:
                c.log(f'Flotte {fleet.id} arrivée à {target.name}.')
            continue_order(c,fleet,self.planner)
            self.finish_arrival(fleet)

    def finish_arrival(self, fleet):
        c=self.campaign
        if fleet.navigation_state=='arrived':
            if fleet.arrival_mode=='merge':
                target_fleet=c.fleets.get(fleet.merge_target)
                error=transfer(c,fleet.id,fleet.merge_target,fleet.owner) if target_fleet else 'Flotte cible absente.'
                if error:
                    c.log(f'Flotte {fleet.id} arrivée ; fusion annulée : cible indisponible.')
                else:
                    c.log(f'Fusion de la flotte {fleet.id} vers {fleet.merge_target}, sans création d’unité.')
                    from star_arena.systems.navigation import clear_order
                    clear_order(fleet,'merged')
            elif fleet.arrival_mode=='reinforce':
                c.log(f'Renfort {fleet.id} arrivé, flotte conservée séparément.')
            fleet.arrival_mode='move'; fleet.merge_target=None

    def _expand_ai(self) -> None:
        c = self.campaign
        rng = Random(c.seed + int(c.time * 10))
        for fleet in sorted(c.fleets.values(), key=lambda item: item.id):
            if fleet.owner in self.human_factions or fleet.travel is not None or fleet.destroyed or fleet.status != "permanent" or fleet.navigation_state in ("engaged","blocked"):
                continue
            options = c.neighbors(fleet.system_id)
            neutral = [i for i in options if c.systems[i].owner is None]
            friendly = [i for i in options if c.systems[i].owner == fleet.owner]
            vulnerable = [i for i in options if c.systems[i].owner not in (None, fleet.owner)
                          and military_power(fleet.ships) > 1.15 * (sum(military_power(f.ships) for f in c.fleets_at(i) if f.owner != fleet.owner)
                            + military_power(defensive_units(c, i, c.systems[i].owner)))]
            important = [i for i in friendly if (c.systems[i].capital or c.systems[i].shipyard)
                         and any(c.systems[n].owner not in (None, fleet.owner) for n in c.neighbors(i))]
            here = c.systems[fleet.system_id]
            if (here.capital or here.shipyard) and any(c.systems[n].owner not in (None, fleet.owner)
                                                     for n in options):
                # Maintenir une garnison lorsque les voisins menacent une base industrielle.
                allies = [f for f in c.fleets_at(here.id) if f.owner == fleet.owner and f.ships]
                if len(allies) == 1 and len(fleet.ships) < 4:
                    continue
            choices = vulnerable or important or neutral or friendly
            if choices:
                self.order_move(fleet.id, rng.choice(choices), fleet.owner)
