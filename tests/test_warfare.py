"""Tests de logique uniquement : stdlib, sans Pygame, affichage ou audio."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from star_arena.domain.galaxy import new_campaign
from star_arena.domain.models import SHIP_TYPES, Ship
from star_arena.persistence import decode, load_campaign, save_campaign
from star_arena.systems.combat import auto_resolve, create_engagement
from star_arena.systems.formations import FORMATIONS, offsets
from star_arena.systems.simulation import Simulation
from star_arena.systems.tactical import BattleEngine
from star_arena.presentation.battle_input import BattleControls
from star_arena.app import Application


def pending_campaign(player=0):
    c = new_campaign(player, system_count=15, layout="legacy")
    attacker, defender = c.fleets[1], c.fleets[2]
    origin = attacker.system_id
    target = c.neighbors(origin)[0]
    c.systems[target].owner = 1
    defender.system_id = target
    attacker.system_id = target
    create_engagement(c, attacker, origin, 1)
    return c


def payload(c):
    return json.loads(json.dumps({
        "version": 2, "player": c.player, "seed": c.seed,
        "systems": [asdict(s) for s in c.systems.values()], "routes": sorted(c.routes),
        "fleets": [asdict(f) for f in c.fleets.values()], "time": c.time,
        "next_ai_at": c.next_ai_at, "events": c.events, "step_remainder": c.step_remainder,
        "next_engagement_id": c.next_engagement_id,
        "pending": asdict(c.pending) if c.pending else None,
        "reports": [asdict(r) for r in c.reports],
    }))


def temporary_directory():
    return TemporaryDirectory(prefix="star-arena-logic-", dir=Path(__file__).resolve().parent)


class DamageTests(unittest.TestCase):
    def test_shield_before_hull(self):
        ship = Ship(1, "fighter", 100, 60)
        self.assertEqual(ship.receive_damage(40), 40)
        self.assertEqual((ship.hull, ship.shield), (100, 20))

    def test_overflow_and_destruction(self):
        ship = Ship(1, "fighter", 100, 60)
        ship.receive_damage(80)
        self.assertEqual((ship.hull, ship.shield), (80, 0))
        ship.receive_damage(10000)
        self.assertFalse(ship.alive)
        self.assertEqual(ship.hull, 0)

    def test_dead_ship_never_returns(self):
        ship = Ship(1, "fighter", 0, 0)
        self.assertEqual(ship.receive_damage(-100), 0)
        self.assertEqual(ship.hull, 0)

    def test_nonfinite_damage_rejected(self):
        with self.assertRaises(ValueError):
            Ship(1, "fighter", 100, 60).receive_damage(float("nan"))


class CampaignTests(unittest.TestCase):
    def test_original_galaxy(self):
        c = new_campaign(system_count=15, layout="legacy")
        self.assertEqual((len(c.systems), len(c.routes), len(c.fleets)), (15, 26, 3))
        ids = [s.id for f in c.fleets.values() for s in f.ships]
        self.assertEqual(len(ids), 24)
        self.assertEqual(len(set(ids)), 24)

    def test_original_movement_and_neutral_occupation(self):
        c = new_campaign(system_count=15, layout="legacy")
        sim = Simulation(c)
        target = c.neighbors(0)[0]
        self.assertEqual(sim.order_move(1, target, 0), "")
        for _ in range(100):
            sim.advance(0.1)
        self.assertIsNone(c.fleets[1].travel)
        self.assertEqual(c.fleets[1].system_id, target)
        self.assertEqual(c.systems[target].owner, 0)

    def test_enemy_undefended_occupation(self):
        c = new_campaign(system_count=15, layout="legacy")
        target = c.neighbors(0)[0]
        c.systems[target].owner = 1
        sim = Simulation(c)
        self.assertEqual(sim.order_move(1, target, 0), "")
        c.fleets[1].travel.elapsed = c.fleets[1].travel.duration - 0.01
        sim.advance(0.1)
        self.assertEqual(c.systems[target].owner, 0)
        self.assertIsNone(c.pending)

    def test_enemy_defended_creates_engagement(self):
        c = new_campaign(system_count=15, layout="legacy")
        target = c.neighbors(0)[0]
        c.systems[target].owner = 1
        c.fleets[2].system_id = target
        sim = Simulation(c)
        sim.order_move(1, target, 0)
        c.fleets[1].travel.elapsed = c.fleets[1].travel.duration - 0.01
        sim.advance(0.1)
        self.assertIsNotNone(c.pending)
        self.assertEqual(len(c.pending.initial), 16)
        before = c.time
        sim.advance(0.5)
        self.assertEqual(c.time, before)

    def test_ai_encounter_automatically_resolved(self):
        c = new_campaign(2)
        target = c.neighbors(0)[0]
        c.systems[target].owner = 1
        c.fleets[2].system_id = target
        sim = Simulation(c)
        sim.order_move(1, target, 0)
        c.fleets[1].travel.elapsed = c.fleets[1].travel.duration - 0.01
        sim.advance(0.1)
        self.assertIsNone(c.pending)
        self.assertEqual(len(c.reports), 1)
        self.assertTrue(c.reports[0].automatic)

    def test_original_ai_expands(self):
        c = new_campaign(system_count=15, layout="legacy")
        sim = Simulation(c)
        for _ in range(120):
            sim.advance(0.1)
        self.assertGreater(sum(s.owner == 1 for s in c.systems.values()), 1)

    def test_destruction_prevents_orders(self):
        c = new_campaign(system_count=15, layout="legacy")
        c.fleets[1].ships.clear()
        self.assertNotEqual(Simulation(c).order_move(1, c.neighbors(0)[0], 0), "")


class BattleTests(unittest.TestCase):
    def test_two_complete_fleets_finish_a_real_battle(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        b.asteroids.clear()
        for owner, x in ((0, 1250), (1, 1950)):
            for i, unit in enumerate(b.living(owner)):
                unit.x, unit.y = x, 650 + i * 100
        b.command([u.ship.id for u in b.living(0)], "attack_move", (2200, 1000))
        for _ in range(1800):
            b.advance(1 / 30)
            if b.finished:
                break
        self.assertTrue(b.finished)
        report = b.commit()
        self.assertEqual(sum(report.engaged.values()), 16)
        self.assertGreater(sum(report.destroyed.values()), 0)
        self.assertEqual(sum(report.destroyed.values()) + sum(report.survivors.values()) + sum(report.captured.values()), 16)

    def test_attack_move_keeps_its_mission_while_fighting(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        unit, enemy = b.living(0)[0], b.living(1)[0]
        unit.x, unit.y, enemy.x, enemy.y = 500, 1000, 700, 1000
        b.command([unit.ship.id], "attack_move", (1000, 1000))
        destination = unit.destination
        b.advance(0.2)
        self.assertEqual(unit.order, "attack_move")
        self.assertEqual(unit.destination, destination)

    def test_natural_rts_victory_then_conquest(self):
        c = pending_campaign()
        c.pending = None
        c.fleets[1].ships[:] = c.fleets[1].ships[:3]
        c.fleets[2].ships[:] = c.fleets[2].ships[-1:]
        create_engagement(c, c.fleets[1], 0, 1)
        b = BattleEngine(c, c.pending)
        b.asteroids.clear()
        for i, unit in enumerate(b.living(0)):
            unit.x, unit.y = 650, 850 + i * 100
        enemy = b.living(1)[0]
        enemy.x, enemy.y = 1000, 1000
        b.command([u.ship.id for u in b.living(0)], "attack", target=enemy.ship.id)
        for _ in range(900):
            b.advance(1 / 30)
            if b.finished:
                break
        self.assertTrue(b.finished, "La bataille doit finir par les tirs réels.")
        self.assertEqual(b.winner, 0)
        report = b.commit()
        self.assertEqual(report.destroyed[1], 1)
        self.assertEqual(c.systems[report.system_id].owner, 0)

    def test_active_limit_reserves_and_no_resurrection(self):
        c = pending_campaign()
        c.pending = None
        for owner, fleet_id in ((0, 1), (1, 2)):
            c.fleets[fleet_id].ships[:] = [Ship(25 + owner * 60 + i, "fighter", 100, 60) for i in range(60)]
        create_engagement(c, c.fleets[1], 0, 1)
        b = BattleEngine(c, c.pending)
        self.assertEqual(len(b.living()), 96)
        self.assertEqual(len(b.reserves), 24)
        dead_ids = [u.ship.id for u in b.living(0)[:3]]
        for uid in dead_ids:
            b.damage(uid, 100000)
        b.advance(1 / 30)
        self.assertEqual(len(b.living(0)), 48)
        self.assertTrue(all(not b.units[uid].ship.alive for uid in dead_ids))
        b.withdraw()
        b.commit()
        self.assertEqual(len(c.fleets[1].ships), 57)

    def test_uses_original_ship_objects_and_ids(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        for f in (c.fleets[1], c.fleets[2]):
            for ship in f.ships:
                self.assertIs(b.units[ship.id].ship, ship)

    def test_projectiles_deal_real_damage(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        b.asteroids.clear()
        source = b.units[c.fleets[1].ships[0].id]
        target = b.units[c.fleets[2].ships[-1].id]
        source.x, source.y, target.x, target.y = 500, 1000, 650, 1000
        b.command([source.ship.id], "attack", target=target.ship.id)
        source.cooldowns = [0.0] * len(source.cooldowns)
        before = target.ship.hull + target.ship.shield
        for _ in range(30):
            b.advance(1 / 30)
        self.assertLess(target.ship.hull + target.ship.shield, before)

    def test_losses_survivors_conquest_and_idempotent_commit(self):
        c = pending_campaign()
        initial_ids = {s.id for f in c.fleets.values() for s in f.ships}
        b = BattleEngine(c, c.pending)
        surviving = c.fleets[1].ships[0]
        b.damage(surviving.id, surviving.shield + 75)
        dead = c.fleets[1].ships[-1].id
        b.damage(dead, 100000)
        for ship in c.fleets[2].ships:
            b.damage(ship.id, 100000)
        b.advance(1 / 30)
        self.assertTrue(b.finished)
        report = b.commit()
        self.assertIs(b.commit(), report)
        self.assertEqual(len(c.reports), 1)
        self.assertEqual(c.systems[report.system_id].owner, 0)
        self.assertTrue(c.fleets[2].destroyed)
        ids = [s.id for f in c.fleets.values() for s in f.ships]
        self.assertNotIn(dead, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids).issubset(initial_ids))
        self.assertEqual(surviving.hull, SHIP_TYPES["cruiser"][1] - 75)

    def test_retreat_preserves_damage_and_uses_real_route(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        ship = c.fleets[1].ships[0]
        b.damage(ship.id, 100)
        b.withdraw()
        report = b.commit()
        self.assertTrue(report.retreat)
        self.assertEqual(report.winner, 1)
        self.assertEqual(c.fleets[1].travel.destination, 0)
        self.assertEqual(ship.shield, 700)

    def test_no_refuge_means_captured_not_duplicated(self):
        c = pending_campaign(1)
        b = BattleEngine(c, c.pending)
        b.withdraw()
        report = b.commit()
        self.assertEqual(report.destroyed[1], 0)
        self.assertEqual(report.captured[1], 8)
        self.assertEqual(report.survivors[1], 0)
        self.assertTrue(c.fleets[2].destroyed)

    def test_auto_reproducible_and_no_free_units(self):
        a, b = pending_campaign(2), pending_campaign(2)
        before = {s.id for f in a.fleets.values() for s in f.ships}
        self.assertEqual(asdict(auto_resolve(a)), asdict(auto_resolve(b)))
        ids = [s.id for f in a.fleets.values() for s in f.ships]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids).issubset(before))

    def test_formations_and_commands(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        ids = [s.id for s in c.fleets[1].ships]
        for formation in FORMATIONS:
            self.assertEqual(len(set(offsets(8, formation))), 8)
            b.command(ids, "move", (800, 1000), formation=formation)
            self.assertTrue(all(b.units[i].order == "move" for i in ids))
        b.command(ids, "hold")
        self.assertTrue(all(b.units[i].order == "hold" for i in ids))
        enemy_id = c.fleets[2].ships[0].id
        before = b.units[enemy_id].order
        b.command([enemy_id], "stop")
        self.assertEqual(b.units[enemy_id].order, before)

    def test_asteroid_nonpenetration(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        unit = b.units[c.fleets[1].ships[0].id]
        b.asteroids = [(unit.x, unit.y, 50)]
        b.advance(1 / 30)
        ax, ay, radius = b.asteroids[0]
        self.assertGreaterEqual((unit.x - ax)**2 + (unit.y - ay)**2, (radius + unit.radius)**2)

    def test_invalid_duplicate_roster_rejected(self):
        c = pending_campaign()
        c.pending.initial.append(c.pending.initial[0])
        with self.assertRaises(ValueError):
            BattleEngine(c, c.pending)


class SaveTests(unittest.TestCase):
    def test_after_battle_and_empty_fleets(self):
        c = pending_campaign()
        auto_resolve(c)
        with temporary_directory() as directory:
            path = Path(directory) / "campaign.json"
            save_campaign(c, path)
            loaded = load_campaign(path)
        self.assertEqual(payload(c), payload(loaded))
        self.assertTrue(any(f.destroyed for f in loaded.fleets.values()))

    def test_pending_battle_roundtrip(self):
        c = pending_campaign()
        self.assertEqual(payload(c), payload(decode(payload(c))))

    def test_travel_and_fraction_preserved(self):
        c = new_campaign(system_count=15, layout="legacy")
        sim = Simulation(c)
        sim.order_move(1, c.neighbors(0)[0], 0)
        sim.advance(0.15)
        loaded = decode(payload(c))
        self.assertEqual(asdict(c.fleets[1].travel), asdict(loaded.fleets[1].travel))
        self.assertAlmostEqual(loaded.step_remainder, 0.05)

    def test_legacy_version_one_migrates_without_rewards(self):
        c = new_campaign(system_count=15, layout="legacy")
        old = payload(c)
        old["version"] = 1
        for field in ("pending", "reports", "next_engagement_id", "step_remainder"):
            old.pop(field)
        loaded = decode(old)
        self.assertEqual([asdict(f) for f in c.fleets.values()], [asdict(f) for f in loaded.fleets.values()])
        self.assertIsNone(loaded.pending)
        self.assertEqual(loaded.reports, [])

    def test_duplicate_ship_rejected(self):
        data = payload(new_campaign(system_count=15, layout="legacy"))
        data["fleets"][0]["ships"].append(data["fleets"][0]["ships"][0])
        with self.assertRaises(ValueError):
            decode(data)

    def test_corrupt_pending_roster_rejected(self):
        data = payload(pending_campaign())
        data["pending"]["initial"][0]["id"] = 999999
        with self.assertRaises(ValueError):
            decode(data)

    def test_mid_battle_save_refused(self):
        c = pending_campaign()
        b = BattleEngine(c, c.pending)
        b.damage(c.fleets[1].ships[0].id, 5)
        with temporary_directory() as directory:
            with self.assertRaises(ValueError):
                save_campaign(c, Path(directory) / "campaign.json")

    def test_incompatible_file_preserved(self):
        with temporary_directory() as directory:
            path = Path(directory) / "campaign.json"
            original = '{"version":99}'
            path.write_text(original, encoding="utf-8")
            with self.assertRaises(ValueError):
                save_campaign(new_campaign(system_count=15, layout="legacy"), path)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_no_pygame_imported(self):
        self.assertFalse(any(name == "pygame" or name.startswith("pygame.") for name in sys.modules))


class InputRoutingTests(unittest.TestCase):
    """Événements factices uniquement, aucune bibliothèque graphique importée."""
    def setUp(self):
        self.clock_ms = 0
        values = dict(QUIT=0, KEYDOWN=1, KEYUP=2, WINDOWFOCUSLOST=3, WINDOWMINIMIZED=4,
                      WINDOWFOCUSGAINED=5, MOUSEBUTTONDOWN=6, MOUSEBUTTONUP=7,
                      MOUSEMOTION=8, MOUSEWHEEL=9, K_ESCAPE=27, K_SPACE=32, K_a=97,
                      K_s=115, K_h=104, K_0=48, K_1=49, K_9=57, K_F5=1005,
                      K_F9=1009, KMOD_CTRL=64, KMOD_SHIFT=1)
        self.pg = SimpleNamespace(**values, time=SimpleNamespace(get_ticks=lambda: self.clock_ms))
        self.c = pending_campaign()
        self.b = BattleEngine(self.c, self.c.pending)
        self.controls = BattleControls(self.pg, self.b)
        renderer = SimpleNamespace(buttons=[], fleet_points={})
        self.app = Application(self.pg, renderer, Path("unused-save-path.json"))
        self.app.simulation = Simulation(self.c)
        self.app.mode = "battle"
        self.app.battle = self.b
        self.app.battle_controls = self.controls
        self.controls.select_all()

    def key(self, key, mod=0, release=False):
        self.app.event(SimpleNamespace(type=self.pg.KEYUP if release else self.pg.KEYDOWN, key=key, mod=mod))

    def test_groups_do_not_change_galactic_speed(self):
        self.app.speed = 4
        ids = set(self.controls.selected)
        self.key(self.pg.K_1, self.pg.KMOD_CTRL)
        self.controls.selected.clear()
        self.key(self.pg.K_1)
        self.assertEqual(self.controls.selected, ids)
        self.assertEqual(self.app.speed, 4)

    def test_escape_only_opens_battle_menu(self):
        self.key(self.pg.K_ESCAPE)
        self.assertTrue(self.controls.menu)
        self.assertEqual(self.app.mode, "battle")
        self.key(self.pg.K_ESCAPE)
        self.assertFalse(self.controls.menu)

    def test_stop_and_hold_commands(self):
        self.b.command(self.controls.selected, "move", (900, 1000))
        self.key(self.pg.K_s)
        self.clock_ms = 80
        self.key(self.pg.K_s, release=True)
        self.assertTrue(all(self.b.units[uid].order == "stop" for uid in self.controls.selected))
        self.key(self.pg.K_h)
        self.assertTrue(all(self.b.units[uid].order == "hold" for uid in self.controls.selected))

    def test_held_s_does_not_stop_units(self):
        self.b.command(self.controls.selected, "move", (900, 1000))
        self.key(self.pg.K_s)
        self.clock_ms = 300
        self.key(self.pg.K_s, release=True)
        self.assertTrue(all(self.b.units[uid].order == "move" for uid in self.controls.selected))

    def test_battle_save_key_does_not_write_or_load(self):
        original_campaign = self.app.simulation.campaign
        self.key(self.pg.K_F9)
        self.key(self.pg.K_F5)
        self.assertIs(self.app.simulation.campaign, original_campaign)
        self.assertIn("Sauvegarde", self.controls.message)


if __name__ == "__main__":
    unittest.main()
