"""V0.3.3 : logique, géométrie, caches et préparation Web sans Pygame."""
from dataclasses import asdict
from math import hypot, sqrt
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import inspect
import unittest
from test_warfare import temporary_directory, pending_campaign
from star_arena.domain.galaxy import new_campaign
from star_arena.domain.models import Fleet, Ship, Travel
from star_arena.app import Application, run_game
from star_arena.persistence import save_campaign, load_campaign
from star_arena.systems.economy import NoEconomy
from star_arena.systems.navigation import RoutePlanner, find_path, remaining_time
from star_arena.systems.simulation import Simulation
from star_arena.systems.planets import build, update_planets
from star_arena.systems.battlefield import generate_battlefield
from star_arena.systems.tactical import BattleEngine
from star_arena.presentation.quality import DESKTOP, REDUCED
from star_arena.presentation.ship_sprites import SurfaceCache

class Rect:
    def __init__(self,value): self.value=value
    def collidepoint(self,p):
        x,y,w,h=self.value
        return x<=p[0]<x+w and y<=p[1]<y+h

class Vector:
    def __init__(self,p): self.p=p
    def distance_to(self,q): return hypot(self.p[0]-q[0],self.p[1]-q[1])


def fake_pg():
    return SimpleNamespace(QUIT='quit',KEYDOWN='keydown',WINDOWFOCUSLOST='lost',
        WINDOWMINIMIZED='minimized',WINDOWFOCUSGAINED='gained',MOUSEBUTTONDOWN='down',
        K_ESCAPE='escape',Rect=Rect,Vector2=Vector,time=SimpleNamespace(get_ticks=lambda:500))


class RoundGalaxyTests(unittest.TestCase):
    def test_round_connected_reproducible_all_sizes(self):
        for size in (15,30,60,100):
            c=new_campaign(system_count=size)
            reached={0}
            for _ in c.systems:
                for a,b in c.routes:
                    if a in reached or b in reached: reached.update((a,b))
            self.assertEqual(len(reached),size)
            points=[s.position for s in c.systems.values()]
            width=max(x for x,y in points)-min(x for x,y in points)
            height=max(y for x,y in points)-min(y for x,y in points)
            self.assertTrue(.65<width/height<1.5)
            radius=1300*sqrt(size/60)
            self.assertTrue(all(hypot(x,y/.92)<=radius+1e-6 for x,y in points))
            self.assertEqual(asdict(c),asdict(new_campaign(system_count=size)))
            self.assertEqual(len({s.name for s in c.systems.values()}),size)
            ids=[u.id for f in c.fleets.values() for u in f.ships]
            self.assertEqual(len(ids),len(set(ids)))

    def test_capitals_and_routes_do_not_cross(self):
        c=new_campaign(); capitals=[s.id for s in c.systems.values() if s.capital]
        self.assertTrue(all(c.distance(a,b)>1800 for a in capitals for b in capitals if a!=b))
        def orient(p,q,r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
        for a,b in c.routes:
            p,q=c.systems[a].position,c.systems[b].position
            for x,y in c.routes:
                if len({a,b,x,y})<4: continue
                r,s=c.systems[x].position,c.systems[y].position
                self.assertFalse(orient(p,q,r)*orient(p,q,s)<0 and orient(r,s,p)*orient(r,s,q)<0)

    def test_route_cache_avoids_repeated_search_and_invalidates(self):
        c=new_campaign(); planner=RoutePlanner(c)
        path=planner.find(0,20)
        self.assertGreater(len(path),2)
        for _ in range(100): self.assertEqual(planner.find(0,20),path)
        self.assertEqual(planner.searches,1)
        c.routes.remove(tuple(sorted(path[:2])))
        planner.find(0,20)
        self.assertEqual(planner.searches,2)
        for i in range(200): planner.find(i%60,i//60)
        self.assertLessEqual(len(planner.cache),128)

    def test_old_map_save_positions_and_routes_preserved(self):
        c=new_campaign(system_count=15,layout='legacy')
        with temporary_directory() as folder:
            path=Path(folder)/'old.json'; save_campaign(c,path)
            self.assertEqual(asdict(c),asdict(load_campaign(path)))


class OrderInputTests(unittest.TestCase):
    def setUp(self):
        self.c=new_campaign(); self.c.next_ai_at=1e9
        self.target=self.c.neighbors(0)[0]
        s=self.c.systems[self.target]; s.owner=0
        for p in s.planets: p.owner=0
        self.c.fleets[4]=Fleet(4,0,self.target,[Ship(25,'fighter',100,60)])
        self.c.fleets[5]=Fleet(5,0,self.target,[Ship(26,'fighter',100,60)])
        self.c.next_ship_id=27; self.c.next_fleet_id=6
        self.renderer=SimpleNamespace(buttons=[],fleet_points={})
        self.app=Application(fake_pg(),self.renderer,Path('unused.json'))
        self.app.begin(self.c); self.app.simulation=Simulation(self.c,NoEconomy())
        self.app.selected_fleet=1

    def advance_to_arrival(self):
        count=round(remaining_time(self.c,self.c.fleets[1])*10)+3
        for _ in range(count): self.app.advance_campaign(.1)

    def test_left_system_click_does_not_replace_source(self):
        xy=self.app.camera.screen(self.c.systems[self.target].position)
        self.app.event(SimpleNamespace(type='down',button=1,pos=xy))
        self.assertEqual(self.app.selected_fleet,1)
        self.assertEqual(self.app.selected_system,self.target)

    def test_right_click_fleet_icon_opens_choice_preserves_source(self):
        x,y=self.app.camera.screen(self.c.systems[self.target].position)
        self.renderer.fleet_points={4:(x+40,y-16)}
        self.app.event(SimpleNamespace(type='down',button=3,pos=(x+40,y-16)))
        self.assertEqual(self.app.selected_fleet,1)
        self.assertEqual(self.app.order_request,(1,self.target))
        self.assertIsNone(self.c.fleets[1].travel)

    def test_move_and_reinforce_keep_units_separate(self):
        self.app.request_move(self.target)
        self.app.confirm_move('reinforce')
        self.advance_to_arrival()
        self.assertEqual(len(self.c.fleets[1].ships),8)
        self.assertEqual(len(self.c.fleets[4].ships),1)
        self.assertEqual(self.c.fleets[1].system_id,self.target)
        self.assertIsNone(self.c.fleets[1].travel)

    def test_merge_selection_persists_and_keeps_damage_and_identity(self):
        unit=self.c.fleets[1].ships[-1]; unit.receive_damage(70)
        self.app.request_move(self.target); self.app.confirm_move('merge',5)
        with temporary_directory() as folder:
            path=Path(folder)/'order.json'; save_campaign(self.c,path)
            loaded=load_campaign(path)
        self.assertEqual(loaded.fleets[1].merge_target,5)
        self.assertEqual(loaded.fleets[1].arrival_mode,'merge')
        self.advance_to_arrival()
        self.assertEqual(len(self.c.fleets[5].ships),9)
        self.assertEqual(self.app.selected_fleet,5)
        self.assertFalse(self.c.fleets[1].ships)
        self.assertIs(next(u for u in self.c.fleets[5].ships if u.id==unit.id),unit)
        self.assertEqual((unit.hull,unit.shield),(90,0))
        ids=[u.id for f in self.c.fleets.values() for u in f.ships]
        self.assertEqual(len(ids),len(set(ids)))

    def test_merge_in_same_system_finishes_immediately(self):
        self.c.fleets[4].system_id=0
        self.app.request_move(0); self.app.confirm_move('merge',4)
        self.assertFalse(self.c.fleets[1].ships)
        self.assertEqual(len(self.c.fleets[4].ships),9)
        self.assertEqual(self.app.selected_fleet,4)

    def test_merge_cancels_if_target_has_left(self):
        self.app.request_move(self.target); self.app.confirm_move('merge',4)
        other=self.c.neighbors(self.target)[0]
        self.c.fleets[4].travel=Travel(self.target,other,0,10000)
        self.advance_to_arrival()
        self.assertEqual(len(self.c.fleets[1].ships),8)
        self.assertEqual(len(self.c.fleets[4].ships),1)

    def test_empty_enemy_destination_and_transit_redirect(self):
        neutral=next(i for i in self.c.systems if self.c.systems[i].owner is None)
        self.app.request_move(neutral)
        self.assertIsNotNone(self.c.fleets[1].travel)
        position=self.c.fleets[1].position(self.c.systems)
        self.app.request_move(self.target); self.app.confirm_move('move')
        self.assertEqual(position,self.c.fleets[1].position(self.c.systems))

    def test_enemy_defender_still_triggers_engagement(self):
        self.c.systems[self.target].owner=1
        self.c.fleets[2].system_id=self.target
        self.c.fleets[4].system_id=0; self.c.fleets[5].system_id=0
        self.app.request_move(self.target)
        for _ in range(round(remaining_time(self.c,self.c.fleets[1])*10)+3):
            self.app.advance_campaign(.1)
            if self.c.pending: break
        self.assertIsNotNone(self.c.pending)
        self.assertEqual(self.c.pending.system_id,self.target)


class ContextAndWebTests(unittest.TestCase):
    def test_contextual_planets_and_built_structures_use_real_units(self):
        c=pending_campaign(); c.pending=None
        system=c.systems[1]
        p=system.planets[0]; p.owner=1; system.owner=1
        self.assertEqual(build(c,1,p.id,'station',1),'')
        for _ in range(30): c.time+=1; update_planets(c)
        self.assertEqual(build(c,1,p.id,'laser',1),'')
        for _ in range(25): c.time+=1; update_planets(c)
        from star_arena.systems.combat import create_engagement
        e=create_engagement(c,c.fleets[1],0,1)
        before=asdict(c)
        field=generate_battlefield(c,e)
        self.assertEqual(asdict(c),before)
        self.assertEqual({v.id for v in field.planets},{p.id for p in system.planets})
        self.assertEqual(field,generate_battlefield(c,e))
        b=BattleEngine(c,e)
        for building in p.orbitals:
            uid=building.unit.id
            self.assertIn(uid,b.units)
            self.assertEqual((b.units[uid].x,b.units[uid].y),field.structures[uid])
            self.assertIs(b.units[uid].ship,building.unit)
            planet=field.planets[0]
            self.assertLess(hypot(b.units[uid].x-planet.x,b.units[uid].y-planet.y),260)
        for x,y,r in field.asteroids:
            self.assertTrue(all(hypot(x-u,y-v)>r+90 for u,v in field.structures.values()))

    def test_dense_five_planet_defenses_are_separated(self):
        from star_arena.domain.models import Planet, Building
        from star_arena.systems.planets import new_unit
        from star_arena.domain.ship_stats import COMBAT_STATS
        from star_arena.systems.combat import create_engagement
        c=pending_campaign(); c.pending=None; system=c.systems[1]; system.owner=1
        system.planets=[]
        for i in range(5):
            p=Planet(11+i,'Planète '+str(i),'rocky',1,8.,3,6)
            for kind,model,level in (('station','station4',4),('laser','laser',1),('heavy','heavy',1),('repair','repair',1),('shield','shield',1)):
                p.orbitals.append(Building(kind,level,new_unit(c,model,'orbital')))
            system.planets.append(p)
        e=create_engagement(c,c.fleets[1],0,1)
        field=generate_battlefield(c,e)
        ships={u.id:u for p in system.planets for b in p.orbitals if (u:=b.unit)}
        self.assertEqual(len(field.structures),25)
        for a,xy in field.structures.items():
            for b,other in field.structures.items():
                if a>=b: continue
                minimum=COMBAT_STATS[ships[a].model].radius+COMBAT_STATS[ships[b].model].radius+18
                self.assertGreaterEqual(hypot(xy[0]-other[0],xy[1]-other[1])+1e-6,minimum)

    def test_quality_changes_effects_not_combat_stats(self):
        c=pending_campaign(); b=BattleEngine(c,c.pending)
        before=[(u.ship.id,u.ship.model,u.ship.hull,u.ship.shield) for u in b.units.values()]
        b.reduced_quality=True
        for i in range(100): b._effect(i,0,0,'impact',.2,5)
        self.assertEqual(len(b.effects),REDUCED.max_effects)
        self.assertEqual(before,[(u.ship.id,u.ship.model,u.ship.hull,u.ship.shield) for u in b.units.values()])
        self.assertLess(REDUCED.angle_step**-1,DESKTOP.angle_step**-1)
        self.assertEqual(REDUCED.debris,0)

    def test_surface_cache_shrinks_and_is_bounded(self):
        class Surface:
            def get_width(self): return 100
            def get_height(self): return 100
        cache=SurfaceCache(10,100000)
        for i in range(10): cache.put(i,Surface())
        cache.resize(2,15000)
        self.assertLessEqual(cache.pixels,15000)
        self.assertLessEqual(len(cache.items),2)

    def test_cooperative_entry_and_minimal_export_scope(self):
        self.assertTrue(inspect.iscoroutinefunction(run_game))
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('prepare_web',root/'tools/prepare_web.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        files=module.files_for_web(root)
        self.assertTrue(any(p.name=='main.py' for p in files))
        self.assertEqual(sum(p.suffix=='.png' for p in files),9)
        self.assertEqual(sum(p.suffix=='.wav' for p in files),6)
        self.assertTrue(all('.venv' not in p.parts and 'saves' not in p.parts for p in files))
        self.assertLess(sum(p.stat().st_size for p in files),3_000_000)
        with temporary_directory() as folder:
            destination=Path(folder)/'stage'
            self.assertEqual(module.stage(root,destination),len(files))
            self.assertEqual((destination/'main.py').read_bytes(),(root/'main.py').read_bytes())
            (destination/'main.py').write_text('keep',encoding='utf-8')
            with self.assertRaises(ValueError): module.stage(root,destination)
            self.assertEqual((destination/'main.py').read_text(encoding='utf-8'),'keep')

    def test_optional_antialias_backend_falls_back_without_surface_creation(self):
        from star_arena.presentation.art import Painter
        calls=[]
        pg=SimpleNamespace(draw=SimpleNamespace(circle=lambda *args: calls.append(args)))
        painter=Painter(pg)
        painter.circle(object(),(100,120,140),(12.2,14.8),9.4,1)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][2],(12,15))
