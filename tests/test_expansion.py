"""Validation V0.3 : simulation uniquement, sans Pygame."""
from dataclasses import asdict
import json
from pathlib import Path
import unittest
from test_warfare import temporary_directory, payload
from star_arena.domain.galaxy import new_campaign
from star_arena.domain.models import Resources
from star_arena.systems.economy import GalacticEconomy, SHIP_COSTS, income, yard_order, transfer
from star_arena.systems.simulation import Simulation
from star_arena.systems.combat import create_engagement
from star_arena.systems.tactical import BattleEngine
from star_arena.persistence import save_campaign, load_campaign, decode

class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.c = new_campaign()
        self.s = self.c.systems[0]

    def rich(self):
        self.c.resources[0] = Resources(10000, 10000)

    def test_connected_sizes_and_reproducible(self):
        for count in (15,30,60,100):
            c = new_campaign(system_count=count)
            reached = {0}
            for _ in c.systems:
                for a,b in c.routes:
                    if a in reached or b in reached:
                        reached.update((a,b))
            self.assertEqual(len(reached), count)
            self.assertEqual(asdict(c), asdict(new_campaign(system_count=count)))
            self.assertEqual(len({s.name for s in c.systems.values()}), count)
        self.assertNotEqual(asdict(self.c), asdict(new_campaign(seed=43)))

    def test_capitals_far_apart_and_unique_ids(self):
        capitals = [s.id for s in self.c.systems.values() if s.capital]
        self.assertEqual(len(capitals), 3)
        self.assertTrue(all(self.c.distance(a,b)>1200 for a in capitals for b in capitals if a!=b))
        ids = [s.id for f in self.c.fleets.values() for s in f.ships]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(any(s.owner is None and s.richness==4 for s in self.c.systems.values()))

    def test_fixed_income_fraction_and_pause(self):
        e=GalacticEconomy(); before=self.c.resources[0].credits
        e.update(self.c,.4); self.assertEqual(self.c.resources[0].credits,before)
        e.update(self.c,.6); self.assertEqual(self.c.resources[0].credits,before+4)
        sim=Simulation(self.c); sim.advance(0)
        self.assertEqual(self.c.resources[0].credits,before+4)

    def test_speeds_two_and_four(self):
        values=[]
        for speed in (1,2,4):
            c=new_campaign(); sim=Simulation(c)
            for _ in range(30): sim.advance(speed/30)
            values.append((c.time,c.resources[0].credits))
        self.assertEqual(values,[(1.,604.),(2.,608.),(4.,616.)])

    def test_yard_build_upgrade_and_limits(self):
        self.rich()
        for level in (1,2,3):
            self.assertEqual(yard_order(self.c,0,0),"")
            self.assertEqual(self.s.shipyard,level)
        before=asdict(self.c.resources[0])
        self.assertTrue(yard_order(self.c,0,0))
        self.assertEqual(asdict(self.c.resources[0]),before)
        self.assertTrue(yard_order(self.c,1,0))

    def test_insufficient_resources_and_required_level(self):
        self.c.resources[0]=Resources(0,0)
        self.assertTrue(yard_order(self.c,0,0))
        self.rich(); yard_order(self.c,0,0)
        self.assertTrue(yard_order(self.c,0,0,'cruiser'))
        self.c.resources[0]=Resources(79,35)
        self.assertTrue(yard_order(self.c,0,0,'fighter'))
        self.assertEqual(self.c.resources[0].credits,79)

    def test_queue_paid_and_sequential(self):
        self.rich(); yard_order(self.c,0,0)
        before=self.c.resources[0].credits
        for _ in range(2): self.assertEqual(yard_order(self.c,0,0,'fighter'),"")
        self.assertEqual(self.c.resources[0].credits,before-160)
        initial=len(self.c.fleets[1].ships); e=GalacticEconomy()
        e.update(self.c,7); self.assertEqual(len(self.c.fleets[1].ships),initial)
        e.update(self.c,1); self.assertEqual(len(self.c.fleets[1].ships),initial+1)
        self.assertEqual(self.s.queue[0].remaining,8)
        e.update(self.c,8); self.assertEqual(len(self.c.fleets[1].ships),initial+2)

    def test_production_new_fleet_and_monotonic_ids(self):
        self.rich(); yard_order(self.c,0,0); yard_order(self.c,0,0,'fighter')
        self.c.fleets[1].system_id=1; self.c.systems[1].owner=0
        GalacticEconomy().update(self.c,8)
        fleet=self.c.fleets_at(0)[0]
        self.assertGreater(fleet.id,3); self.assertGreater(fleet.ships[0].id,24)
        ship_id=fleet.ships[0].id; fleet.ships.clear()
        yard_order(self.c,0,0,'fighter'); GalacticEconomy().update(self.c,8)
        self.assertGreater(fleet.ships[0].id,ship_id)

    def test_split_transfer_merge_preserve_objects_damage(self):
        source=self.c.fleets[1]; source.ships[-1].receive_damage(70)
        original={s.id:(s,s.hull,s.shield) for s in source.ships}
        uid=source.ships[-1].id
        self.assertEqual(transfer(self.c,1,None,0,[uid]),"")
        dest=self.c.next_fleet_id-1
        self.assertEqual(transfer(self.c,1,dest,0,[source.ships[-1].id]),"")
        self.assertEqual(transfer(self.c,dest,1,0),"")
        self.assertEqual(len(source.ships),8)
        for s in source.ships:
            self.assertIs(s,original[s.id][0]); self.assertEqual((s.hull,s.shield),original[s.id][1:])
        self.assertTrue(transfer(self.c,1,2,0))

    def test_economic_ai_pays_and_produces_all_classes(self):
        c=self.c; c.resources[1]=Resources(10000,10000)
        e=GalacticEconomy(); sim=Simulation(c,e)
        c.next_ai_at=999999 # isolate economic AI from movement / player conflict
        for _ in range(2500): sim.advance(.1)
        made=[u for f in c.fleets.values() if f.owner==1 for u in f.ships if u.id>24]
        self.assertEqual({u.model for u in made},set(SHIP_COSTS))
        self.assertLess(c.resources[1].credits,10000+4*c.time)
        self.assertTrue(all(r.credits>=0 and r.minerals>=0 for r in c.resources.values()))

    def test_produced_ship_real_tactical_participant(self):
        self.rich(); yard_order(self.c,0,0); yard_order(self.c,0,0,'fighter')
        GalacticEconomy().update(self.c,8)
        ship=self.c.fleets[1].ships[-1]
        attacker=self.c.fleets[1]; attacker.system_id=1
        self.c.systems[1].owner=1; self.c.fleets[2].system_id=1
        create_engagement(self.c,attacker,0,1)
        b=BattleEngine(self.c,self.c.pending)
        self.assertIs(b.units[ship.id].ship,ship)

    def test_save_roundtrip_economy_queue_and_travel(self):
        self.rich(); yard_order(self.c,0,0); yard_order(self.c,0,0,'fighter')
        e=GalacticEconomy(); e.update(self.c,8)
        yard_order(self.c,0,0,'fighter'); e.update(self.c,2.4)
        Simulation(self.c).order_move(1,1,0)
        with temporary_directory() as folder:
            path=Path(folder)/'campaign.json'
            save_campaign(self.c,path); loaded=load_campaign(path)
            self.assertEqual(asdict(self.c),asdict(loaded))
            e.update(self.c,5.6); e.update(loaded,5.6)
            self.assertEqual(asdict(self.c),asdict(loaded))

    def test_legacy_migration_backed_up(self):
        for version in (1,2):
            c=new_campaign(system_count=15, layout="legacy"); data=payload(c); data['version']=version
            for s in data['systems']:
                for key in ('richness','shipyard','queue','yard_owner'): s.pop(key)
            with temporary_directory() as folder:
                path=Path(folder)/'old.json'; text=json.dumps(data); path.write_text(text,encoding='utf-8')
                migrated=load_campaign(path); save_campaign(migrated,path)
                self.assertEqual(path.with_name(path.name+f'.v{version}.bak').read_text(encoding='utf-8'),text)
                self.assertEqual(len(load_campaign(path).systems),15)

    def test_conquest_cancels_paid_hostile_queue(self):
        self.rich(); yard_order(self.c,0,0); yard_order(self.c,0,0,'fighter')
        self.s.owner=1; self.c.time=1; GalacticEconomy().update(self.c,1)
        self.assertEqual(self.s.queue,[])

    def test_bad_economy_rejected(self):
        with temporary_directory() as folder:
            path=Path(folder)/'c.json'; save_campaign(self.c,path)
            data=json.loads(path.read_text(encoding='utf-8'))
            data['resources']['0']['minerals']=-1
            with self.assertRaises(ValueError): decode(data)

    def test_application_pause_menu_and_focus_stop_production(self):
        from types import SimpleNamespace
        from star_arena.app import Application
        app = Application(None, SimpleNamespace(buttons=[], fleet_points={}), Path("unused.json"))
        app.begin(self.c)
        self.rich(); yard_order(self.c,0,0); yard_order(self.c,0,0,"fighter")
        before = asdict(self.c)
        app.action("pause")
        for _ in range(30): app.advance_campaign(.1)
        self.assertEqual(asdict(self.c), before)
        app.action("pause"); app.action("menu")
        app.advance_campaign(.1); self.assertEqual(asdict(self.c), before)
        app.action("resume"); app.focused=False
        app.advance_campaign(.1); self.assertEqual(asdict(self.c), before)
        app.focused=True; app.action("speed:4")
        for _ in range(5): app.advance_campaign(.1)
        self.assertEqual(self.c.time,2)
        self.assertEqual(self.s.queue[0].remaining,6)

    def test_queue_limit_and_wrong_owner_preserve_stocks(self):
        self.rich(); yard_order(self.c,0,0)
        for _ in range(20): self.assertEqual(yard_order(self.c,0,0,"fighter"), "")
        before = asdict(self.c)
        self.assertTrue(yard_order(self.c,0,0,"fighter"))
        self.assertTrue(yard_order(self.c,0,1,"fighter"))
        self.assertEqual(asdict(self.c),before)
