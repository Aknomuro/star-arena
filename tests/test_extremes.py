"""Cas limites V0.2.1 ; aucune fenêtre ni bibliothèque graphique."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from star_arena.domain.galaxy import new_campaign
from star_arena.domain.models import Fleet, Ship
from star_arena.persistence import decode, load_campaign, save_campaign
from star_arena.systems.combat import create_engagement, resolve_engagement
from star_arena.systems.simulation import Simulation
from star_arena.systems.tactical import BattleEngine
from test_warfare import payload, pending_campaign, temporary_directory


def arriving(sim, fleet_id, destination):
    error = sim.order_move(fleet_id, destination, sim.campaign.fleets[fleet_id].owner)
    if error:
        raise AssertionError(error)
    fleet = sim.campaign.fleets[fleet_id]
    fleet.travel.elapsed = fleet.travel.duration - 0.01


class ExtremeBattleTests(unittest.TestCase):
    def test_one_ship_per_fleet_natural_fight(self):
        c = pending_campaign()
        c.pending = None
        for fleet_id in (1, 2):
            c.fleets[fleet_id].ships[:] = c.fleets[fleet_id].ships[-1:]
        create_engagement(c, c.fleets[1], 0, 1)
        b = BattleEngine(c, c.pending)
        b.asteroids.clear()
        for owner, x in ((0, 800), (1, 1000)):
            unit = b.living(owner)[0]
            unit.x, unit.y = x, 1000
            unit.angle = 0 if owner == 0 else 3.141592653589793
        for _ in range(450):
            b.advance(1 / 30)
            if b.finished:
                break
        self.assertTrue(b.finished)
        report = b.commit()
        self.assertEqual(sum(report.engaged.values()), 2)
        self.assertGreaterEqual(sum(report.destroyed.values()), 1)
        self.assertEqual(payload(c), payload(decode(payload(c))))

    def test_no_survivors_draw_no_conquest_and_save(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        owner = c.systems[c.pending.system_id].owner
        for unit in b.living():
            b.damage(unit.ship.id, 100000)
        b.advance(1 / 30)
        self.assertTrue(b.finished)
        self.assertIsNone(b.winner)
        report = b.commit()
        self.assertEqual(sum(report.survivors.values()), 0)
        self.assertEqual(sum(report.destroyed.values()), 16)
        self.assertEqual(c.systems[report.system_id].owner, owner)
        with temporary_directory() as directory:
            path = Path(directory) / "draw.json"
            save_campaign(c, path)
            restored = load_campaign(path)
        self.assertTrue(restored.fleets[1].destroyed and restored.fleets[2].destroyed)
        self.assertEqual(payload(c), payload(restored))

    def test_all_fleets_destroyed_campaign_still_loads(self):
        c = new_campaign(system_count=15, layout="legacy")
        for fleet in c.fleets.values():
            fleet.ships.clear()
        restored = decode(payload(c))
        self.assertTrue(all(f.destroyed for f in restored.fleets.values()))
        self.assertNotEqual(Simulation(restored).order_move(1, 1, 0), "")

    def test_200_ships_in_reserve_waves_all_destroyed(self):
        c = pending_campaign()
        c.pending = None
        for owner, fleet_id in ((0, 1), (1, 2)):
            c.fleets[fleet_id].ships[:] = [Ship(100 + owner * 100 + i, "fighter", 100, 60) for i in range(100)]
        create_engagement(c, c.fleets[1], 0, 1)
        b = BattleEngine(c, c.pending)
        self.assertEqual(len(b.living()), 96)
        for _ in range(5):
            for unit in b.living():
                b.damage(unit.ship.id, 100000)
            b.advance(1 / 30)
            self.assertLessEqual(len(b.living()), 96)
            if b.finished:
                break
        self.assertTrue(b.finished)
        self.assertEqual(len(b.units), 200)
        report = b.commit()
        self.assertEqual(sum(report.destroyed.values()), 200)
        self.assertEqual(sum(report.survivors.values()), 0)
        self.assertEqual(payload(c), payload(decode(payload(c))))

    def test_damage_and_ids_survive_repeated_disk_roundtrips(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        survivor = c.fleets[1].ships[0]
        b.damage(survivor.id, survivor.shield + 123.4567)
        for unit in b.living(1):
            b.damage(unit.ship.id, 100000)
        b.advance(1 / 30)
        b.commit()
        expected = payload(c)
        with temporary_directory() as directory:
            path = Path(directory) / "damaged.json"
            for _ in range(3):
                save_campaign(c, path)
                c = load_campaign(path)
                self.assertEqual(expected, payload(c))
        ids = [s.id for f in c.fleets.values() for s in f.ships]
        self.assertEqual(len(ids), len(set(ids)))

    def test_neutral_contested_system_claimed_by_defender_winner(self):
        c = pending_campaign()
        c.systems[c.pending.system_id].owner = None
        for ship in c.fleets[1].ships:
            ship.receive_damage(100000)
        report = resolve_engagement(c, c.pending, 1)
        self.assertEqual(c.systems[report.system_id].owner, 1)
        decode(payload(c))


class SimultaneousArrivalTests(unittest.TestCase):
    def test_all_allied_arrivals_join_same_engagement(self):
        c = new_campaign(system_count=15, layout="legacy")
        target = 1
        c.systems[target].owner = 1
        c.fleets[2].system_id = target
        c.fleets[4] = Fleet(4, 0, 0, [Ship(25, "fighter", 100, 60)])
        sim = Simulation(c)
        arriving(sim, 1, target)
        arriving(sim, 4, target)
        sim.advance(0.1)
        self.assertIsNotNone(c.pending)
        self.assertIn(25, {s.id for s in c.pending.initial})
        self.assertEqual(c.fleets[4].system_id, target)
        self.assertIsNone(c.fleets[4].travel)
        decode(payload(c))

    def test_two_simultaneous_factions_neutral_system(self):
        c = new_campaign(system_count=15, layout="legacy")
        c.fleets[1].system_id, c.fleets[2].system_id = 1, 3
        c.systems[1].owner, c.systems[3].owner = 0, 1
        sim = Simulation(c)
        arriving(sim, 1, 2)
        arriving(sim, 2, 2)
        sim.advance(0.1)
        self.assertEqual(len(c.pending.initial), 16)
        self.assertEqual({s.owner for s in c.pending.initial}, {0, 1})
        self.assertEqual(payload(c), payload(decode(payload(c))))

    def test_third_faction_waits_without_losing_its_trip(self):
        c = new_campaign(system_count=15, layout="legacy")
        for fleet_id, origin in ((1, 1), (2, 3), (3, 7)):
            c.fleets[fleet_id].system_id = origin
            c.systems[origin].owner = c.fleets[fleet_id].owner
        sim = Simulation(c)
        for fleet_id in (1, 2, 3):
            arriving(sim, fleet_id, 2)
        sim.advance(0.1)
        self.assertIsNotNone(c.fleets[3].travel)
        self.assertEqual(c.fleets[3].travel.elapsed, c.fleets[3].travel.duration)
        decode(payload(c))
        b = BattleEngine(c, c.pending)
        for unit in b.living(1):
            b.damage(unit.ship.id, 100000)
        b.advance(1 / 30)
        b.commit()
        sim.advance(0.1)
        self.assertIsNotNone(c.pending)
        self.assertIn(2, {c.pending.attacker, c.pending.defender})
        decode(payload(c))

    def test_other_system_arrival_preserved_when_first_battle_pauses(self):
        c = new_campaign(system_count=15, layout="legacy")
        c.systems[1].owner = 1
        c.fleets[2].system_id = 1
        c.fleets[3].system_id = 7
        c.systems[7].owner = 2
        c.systems[8].owner = 0
        c.fleets[4] = Fleet(4, 0, 8, [Ship(25, "fighter", 100, 60)])
        sim = Simulation(c)
        arriving(sim, 1, 1)
        arriving(sim, 3, 8)
        sim.advance(0.1)
        self.assertIsNotNone(c.pending)
        self.assertIsNotNone(c.fleets[3].travel)
        self.assertEqual(c.fleets[3].travel.elapsed, c.fleets[3].travel.duration)
        decode(payload(c))

    def test_save_mid_trip_then_advance_same_result(self):
        c = new_campaign(system_count=15, layout="legacy")
        sim = Simulation(c)
        sim.order_move(1, 1, 0)
        sim.advance(0.17)
        with temporary_directory() as directory:
            path = Path(directory) / "travel.json"
            save_campaign(c, path)
            loaded = load_campaign(path)
        continued = Simulation(loaded)
        for _ in range(50):
            sim.advance(0.1)
            continued.advance(0.1)
        self.assertEqual(payload(c), payload(loaded))


if __name__ == "__main__":
    unittest.main()
