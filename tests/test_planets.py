"""Tests planétaires purs : aucune fenêtre et aucun import de Pygame."""
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_warfare import temporary_directory
from star_arena.app import Application
from star_arena.domain.galaxy import new_campaign
from star_arena.domain.models import Resources, SHIP_TYPES
from star_arena.domain.planet_stats import STATIONS
from star_arena.systems.planets import (build, build_spec, station, update_planets, resistance,
    prepare_garrison, defensive_units, planet_position, ai_planets, energy_balance)
from star_arena.systems.economy import GalacticEconomy, income, yard_order, transfer
from star_arena.systems.simulation import Simulation
from star_arena.systems.combat import create_engagement, resolve_engagement, auto_resolve
from star_arena.systems.tactical import BattleEngine
from star_arena.persistence import save_campaign, load_campaign, decode
from star_arena.presentation.system_view import pick_planet


class PlanetTests(unittest.TestCase):
    def setUp(self):
        self.c=new_campaign(layout="legacy")
        self.p=self.c.systems[0].planets[0]
        self.p.kind='rocky'; self.p.capacity=6
        self.c.resources[0]=Resources(100000,100000)
        self.c.resources[1]=Resources(100000,100000)

    def tick(self, count):
        for _ in range(count):
            self.c.time+=1
            update_planets(self.c)

    def construct(self, kind):
        self.assertEqual(build(self.c,0,self.p.id,kind,0),'')
        self.tick(200)

    def attack(self):
        attacker=self.c.fleets[2]
        origin=self.c.neighbors(0)[0]
        attacker.system_id=0
        return create_engagement(self.c,attacker,origin,0)

    def test_generation_count_ids_owners_and_reproducibility(self):
        c=new_campaign(seed=99)
        ids=[]
        for s in c.systems.values():
            self.assertTrue(1<=len(s.planets)<=5)
            for p in s.planets:
                ids.append(p.id)
                self.assertEqual(p.owner,s.owner)
                self.assertTrue(2<=p.capacity<=6)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(asdict(c),asdict(new_campaign(seed=99)))

    def test_open_view_and_return_does_not_mutate_campaign(self):
        app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.begin(self.c); before=asdict(self.c); sim=app.simulation
        app.open_system(0)
        self.assertEqual(app.mode,'system')
        self.assertIs(app.simulation,sim)
        self.assertEqual(asdict(self.c),before)
        self.assertEqual(pick_planet(self.c,0,app.system_camera,app.system_camera.screen(planet_position(0))),self.p.id)
        app.action('system_return')
        self.assertEqual(app.mode,'galaxy'); self.assertEqual(asdict(self.c),before)

    def test_slots_include_pending_commands(self):
        self.p.capacity=2
        self.assertEqual(build(self.c,0,self.p.id,'mine',0),'')
        self.assertEqual(build(self.c,0,self.p.id,'trade',0),'')
        before=asdict(self.c)
        self.assertTrue(build(self.c,0,self.p.id,'power',0))
        self.assertEqual(asdict(self.c),before)
        self.assertEqual(build(self.c,0,self.p.id,'laser',0),'')
        self.assertEqual(build(self.c,0,self.p.id,'missile',0),'')
        self.assertTrue(build(self.c,0,self.p.id,'heavy',0))

    def test_cost_time_upgrade_and_planet_type(self):
        r=self.c.resources[0]
        self.assertEqual(build(self.c,0,self.p.id,'mine',0),'')
        self.assertEqual((r.credits,r.minerals),(99880,99935))
        self.tick(14); self.assertNotIn('mine',self.p.ground)
        self.tick(1); self.assertEqual(self.p.ground['mine'],1)
        self.assertEqual(build(self.c,0,self.p.id,'mine',0),'')
        self.assertEqual(self.p.jobs[0].remaining,30)
        self.tick(30); self.assertEqual(self.p.ground['mine'],2)
        self.p.kind='gas'
        self.assertTrue(build(self.c,0,self.p.id,'barracks',0))

    def test_station_levels_are_sequential_and_have_effects(self):
        self.assertEqual(build_spec(self.p,'station')[0],1)
        self.assertEqual(build(self.c,0,self.p.id,'station',0),'')
        self.assertTrue(build(self.c,0,self.p.id,'station',0))
        self.tick(29); self.assertIsNone(station(self.p))
        self.tick(1); self.assertEqual(station(self.p).level,1)
        for level in (2,3,4):
            self.construct('power') if self.p.ground.get('power',0)<3 else None
            self.construct('station')
            self.assertEqual(station(self.p).level,level)
        self.assertTrue(build(self.c,0,self.p.id,'station',0))
        self.assertGreater(STATIONS[4][1],STATIONS[1][1])
        self.assertGreater(STATIONS[4][3],STATIONS[1][3])
        self.assertGreater(STATIONS[4][6],STATIONS[1][6])
        self.assertGreater(STATIONS[4][7],STATIONS[1][7])

    def test_militia_delayed_paid_and_bounded(self):
        self.assertEqual(build(self.c,0,self.p.id,'station',0),'')
        self.tick(30)
        self.assertEqual(self.p.militia,[])
        self.tick(19); self.assertEqual(len(self.p.militia),0)
        self.tick(1); self.assertEqual(len(self.p.militia),1)
        self.tick(60); self.assertEqual(len(self.p.militia),2)
        self.assertTrue(all(u.status=='militia' for u in self.p.militia))
        ids=[u.id for u in self.p.militia]
        self.tick(100); self.assertEqual([u.id for u in self.p.militia],ids)
        self.p.militia.pop(); before=self.c.resources[0].credits
        self.tick(20); self.assertEqual(len(self.p.militia),2)
        self.assertEqual(self.c.resources[0].credits,before-25)
        self.assertNotIn(self.p.militia[-1].id,ids)

    def test_station_and_platform_are_real_stationary_tactical_units(self):
        self.construct('station'); self.construct('laser')
        e=self.attack(); b=BattleEngine(self.c,e)
        uid=station(self.p).unit.id
        self.assertIn(uid,b.units)
        self.assertIs(b.units[uid].ship,station(self.p).unit)
        self.assertTrue(any(u.ship.model=='laser' for u in b.units.values()))
        before=(b.units[uid].x,b.units[uid].y)
        b.command([uid],'move',(50,50)); b.advance(.1)
        self.assertEqual((b.units[uid].x,b.units[uid].y),before)

    def test_garrison_cannot_move_transfer_or_duplicate(self):
        self.construct('station')
        self.attack(); g=next(f for f in self.c.fleets.values() if f.status=='garrison')
        before=asdict(self.c)
        self.assertTrue(Simulation(self.c).order_move(g.id,1,0))
        self.assertTrue(transfer(self.c,g.id,1,0))
        prepare_garrison(self.c,0)
        self.assertEqual(asdict(self.c),before)
        self.assertEqual(sum(f.status=='garrison' for f in self.c.fleets.values()),1)

    def test_damage_and_destruction_persist_after_commit_and_disk(self):
        self.construct('station'); self.construct('laser')
        e=self.attack(); b=BattleEngine(self.c,e)
        station_unit=station(self.p).unit
        b.damage(station_unit.id,station_unit.shield+80)
        laser=next(x.unit for x in self.p.orbitals if x.kind=='laser')
        b.damage(laser.id,999999)
        for f in self.c.fleets_at(0):
            if f.owner==1:
                for u in f.ships: b.damage(u.id,999999)
        b.advance(.04); b.commit()
        self.assertFalse(laser.alive)
        self.assertLess(station_unit.hull,SHIP_TYPES[station_unit.model][1])
        self.assertFalse(any(f.status=='garrison' for f in self.c.fleets.values()))
        with temporary_directory() as folder:
            path=Path(folder)/'defenses.json'
            save_campaign(self.c,path); c=load_campaign(path)
            self.assertEqual(asdict(c),asdict(self.c))
            self.assertEqual(next(x.unit.hull for x in c.systems[0].planets[0].orbitals if x.kind=='laser'),0)
        self.tick(100)
        self.assertFalse(laser.alive)
        self.assertEqual(build(self.c,0,self.p.id,'laser',0),'')
        self.tick(30)
        replacement=next(x.unit for x in self.p.orbitals if x.kind=='laser')
        self.assertTrue(replacement.alive); self.assertNotEqual(replacement.id,laser.id)

    def test_unfortified_battle_has_no_free_station(self):
        e=self.attack()
        self.assertFalse(any(s.model.startswith('station') for s in e.initial))

    def test_auto_resolution_includes_and_persists_defenses(self):
        self.construct('station'); self.construct('laser')
        e=self.attack()
        uid=station(self.p).unit.id
        self.assertIn(uid,{u.id for u in e.initial})
        report=auto_resolve(self.c)
        self.assertTrue(report.automatic)
        self.assertFalse(any(f.status=='garrison' for f in self.c.fleets.values()))
        self.assertLessEqual(station(self.p).unit.hull,SHIP_TYPES[station(self.p).unit.model][1])
        all_ids=[u.id for f in self.c.fleets.values() for u in f.ships]
        self.assertEqual(len(all_ids),len(set(all_ids)))

    def test_defended_empty_system_triggers_battle_on_arrival(self):
        self.construct('station')
        self.c.fleets[1].ships.clear()
        enemy=self.c.fleets[2]; enemy.system_id=1
        self.c.systems[1].owner=1
        sim=Simulation(self.c); self.assertEqual(sim.order_move(enemy.id,0,1),'')
        for _ in range(100):
            sim.advance(.1)
            if self.c.pending: break
        self.assertIsNotNone(self.c.pending)
        self.assertTrue(any(s.model.startswith('station') for s in self.c.pending.initial))

    def test_economic_bonuses_only_once_and_shortage_effect(self):
        before=income(self.c,0)
        self.construct('mine'); self.construct('trade')
        after=income(self.c,0)
        self.assertEqual(after,(before[0]+3,before[1]+self.p.richness*2))
        self.construct('station'); self.construct('laser'); self.construct('repair')
        self.assertLess(energy_balance(self.p),0)
        self.assertEqual(income(self.c,0)[1],before[1]+self.p.richness)
        self.construct('power'); self.assertGreaterEqual(energy_balance(self.p),0)
        self.assertEqual(income(self.c,0)[1],before[1]+self.p.richness*2)

    def test_shipyard_still_uses_permanent_fleet(self):
        self.construct('station')
        self.assertEqual(yard_order(self.c,0,0),'')
        self.assertEqual(yard_order(self.c,0,0,'fighter'),'')
        before=len(self.c.fleets[1].ships)
        GalacticEconomy().update(self.c,8)
        self.assertEqual(len(self.c.fleets[1].ships),before+1)
        self.assertEqual(self.c.fleets[1].ships[-1].status,'permanent')

    def test_siege_requires_presence_and_survives_save(self):
        self.construct('barracks')
        e=self.attack()
        for f in self.c.fleets_at(0):
            if f.owner==0:
                for u in f.ships: u.receive_damage(999999)
        resolve_engagement(self.c,e,1)
        self.assertEqual(self.c.systems[0].owner,1)
        self.assertEqual(self.p.owner,0)
        self.assertGreater(self.p.occupation,0)
        self.tick(3); remaining=self.p.occupation
        self.c.fleets[2].system_id=1
        self.c.systems[1].owner=1
        self.tick(5); self.assertEqual(self.p.occupation,remaining)
        self.c.fleets[2].system_id=0
        with temporary_directory() as folder:
            path=Path(folder)/'siege.json'; save_campaign(self.c,path)
            loaded=load_campaign(path)
            self.assertEqual(asdict(self.c),asdict(loaded))
        self.tick(100)
        self.assertEqual(self.p.owner,1); self.assertIsNone(self.p.occupier)

    def test_pending_save_rebinds_garrison_units(self):
        self.construct('station'); self.attack()
        with temporary_directory() as folder:
            path=Path(folder)/'pending.json'; save_campaign(self.c,path)
            loaded=load_campaign(path)
            self.assertEqual(asdict(self.c),asdict(loaded))
            p=loaded.systems[0].planets[0]
            g=next(f for f in loaded.fleets.values() if f.status=='garrison')
            self.assertIs(station(p).unit,next(u for u in g.ships if u.id==station(p).unit.id))
            b=BattleEngine(loaded,loaded.pending)
            b.damage(station(p).unit.id,100)
            self.assertLess(station(p).unit.shield,SHIP_TYPES[station(p).unit.model][2])

    def test_strategic_ai_builds_using_resources_and_time(self):
        s=next(s for s in self.c.systems.values() if s.owner==1)
        p=s.planets[0]
        before=self.c.resources[1].credits
        ai_planets(self.c)
        self.assertTrue(p.jobs or any(x.jobs for x in s.planets))
        self.assertLess(self.c.resources[1].credits,before)
        self.assertFalse(any(x.orbitals for x in s.planets))
        self.tick(100)
        self.assertTrue(any(station(x) for x in s.planets))

    def test_legacy_v3_migrates_and_archive_preserves_source(self):
        with temporary_directory() as folder:
            path=Path(folder)/'v3.json'; save_campaign(self.c,path)
            data=json.loads(path.read_text(encoding='utf-8')); data['version']=3
            for s in data['systems']: s.pop('planets')
            text=json.dumps(data); path.write_text(text,encoding='utf-8')
            c=load_campaign(path)
            self.assertTrue(all(s.planets for s in c.systems.values()))
            self.assertFalse(any(p.orbitals for s in c.systems.values() for p in s.planets))
            save_campaign(c,path)
            self.assertEqual(path.with_name(path.name+'.v3.bak').read_text(encoding='utf-8'),text)

    def test_invalid_duplicate_planet_and_militia_status_rejected(self):
        self.construct('station')
        with temporary_directory() as folder:
            path=Path(folder)/'c.json'; save_campaign(self.c,path)
            data=json.loads(path.read_text(encoding='utf-8'))
            p=data['systems'][0]['planets'][0]
            p['militia'][0]['status']='permanent'
            with self.assertRaises(ValueError): decode(data)

    def test_support_structures_have_physical_effects(self):
        self.construct('power'); self.construct('station'); self.construct('repair'); self.construct('shield')
        b=BattleEngine(self.c,self.attack())
        sources=[u for u in b.living(0) if u.ship.status=='orbital']
        fighter=next(u for u in b.living(0) if u.ship.model=='fighter')
        fighter.x=1300; fighter.y=1000
        for i,u in enumerate(sources): u.x=1300+i*60; u.y=1000
        fighter.ship.hull=40; fighter.ship.shield=0
        b.advance(.1)
        self.assertGreater(fighter.ship.hull,40)
        self.assertGreater(fighter.ship.shield,0)

    def test_station_deploys_before_large_permanent_reserves(self):
        from star_arena.domain.models import Ship
        self.construct('station')
        fleet=self.c.fleets[1]
        for _ in range(60):
            uid=self.c.next_ship_id; self.c.next_ship_id+=1
            fleet.ships.append(Ship(uid,'fighter',100,60))
        b=BattleEngine(self.c,self.attack())
        self.assertIn(station(self.p).unit.id,b.units)
        self.assertLessEqual(len(b.living(0)),48)

    def test_real_rts_defense_finishes_and_commits_once(self):
        self.assertEqual(build(self.c,0,self.p.id,'station',0),'')
        self.tick(30)
        self.c.fleets[1].ships.clear()
        self.c.fleets[2].ships[:]=self.c.fleets[2].ships[-1:]
        b=BattleEngine(self.c,self.attack())
        for _ in range(700):
            b.advance(.1)
            if b.finished: break
        self.assertTrue(b.finished)
        self.assertEqual(b.winner,0)
        report=b.commit(); snapshot=asdict(self.c)
        self.assertIs(b.commit(),report)
        self.assertEqual(asdict(self.c),snapshot)
        self.assertFalse(any(f.status=='garrison' for f in self.c.fleets.values()))

    def test_defense_weapon_roles_and_radar_range(self):
        from star_arena.domain.ship_stats import damage_multiplier
        self.assertGreater(damage_multiplier('laser','fighter'),damage_multiplier('laser','cruiser'))
        self.assertGreater(damage_multiplier('missile','cruiser'),damage_multiplier('missile','fighter'))
        self.construct('radar')
        self.c.fleets[1].ships[:]=self.c.fleets[1].ships[-1:]
        self.c.fleets[2].ships[:]=self.c.fleets[2].ships[-1:]
        b=BattleEngine(self.c,self.attack())
        fighter=next(u for u in b.living(0) if u.ship.model=='fighter')
        radar=next(u for u in b.living(0) if u.ship.model=='radar')
        enemy=b.living(1)[0]
        fighter.x=1300.; fighter.y=1000.; fighter.order='hold'; fighter.cooldowns=[0.]
        radar.x=1320.; radar.y=1000.
        enemy.x=1600.; enemy.y=1000.
        b.advance(.1)
        self.assertTrue(fighter.radar)
        self.assertTrue(any(shot.owner==0 and shot.damage==6.25 for shot in b.projectiles))

    def test_planet_construction_obeys_system_view_pause_and_speed(self):
        app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.begin(self.c); app.open_system(0)
        app.action('planet_build:mine')
        app.action('pause'); before=asdict(self.c)
        app.advance_campaign(.1); self.assertEqual(asdict(self.c),before)
        app.action('pause'); app.action('speed:4')
        for _ in range(5): app.advance_campaign(.1)
        self.assertEqual(self.p.jobs[0].remaining,13.)

    def test_forged_station_level_skip_rejected_on_load(self):
        self.assertEqual(build(self.c,0,self.p.id,'station',0),'')
        with temporary_directory() as folder:
            path=Path(folder)/'c.json'; save_campaign(self.c,path)
            data=json.loads(path.read_text(encoding='utf-8'))
            data['systems'][0]['planets'][0]['jobs'][0]['level']=4
            with self.assertRaises(ValueError): decode(data)
