"""Navigation souris : tests légers sans Pygame ni fenêtre."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_polish_web import Rect
from star_arena.app import Application
from star_arena.domain.galaxy import new_campaign
from star_arena.presentation.camera import Camera


class PointerCameraTests(unittest.TestCase):
    def camera(self):
        return Camera(scale=1.,viewport=(0,0,800,600))

    def test_invisible_center_square_stays_still(self):
        c=self.camera()
        for point in ((400,300),(250,150),(550,450)):
            c.follow_pointer(point,1)
        self.assertEqual(c.center,(0.,0.))

    def test_direction_and_progressive_speed(self):
        near=self.camera(); edge=self.camera()
        near.follow_pointer((600,300),.1); edge.follow_pointer((799,300),.1)
        self.assertGreater(near.center[0],0)
        self.assertGreater(edge.center[0],near.center[0])
        edge.follow_pointer((0,0),1)
        self.assertLess(edge.center[0],0); self.assertLess(edge.center[1],0)

    def test_outside_map_and_zero_time_do_not_move(self):
        c=self.camera()
        for point in ((-1,300),(800,300),(400,600)):
            c.follow_pointer(point,1)
        c.follow_pointer((799,300),0)
        self.assertEqual(c.center,(0.,0.))

    def test_diagonal_speed_and_world_bounds(self):
        c=self.camera(); c.follow_pointer((799,599),1)
        self.assertLessEqual((c.center[0]**2+c.center[1]**2)**.5,520.00001)
        c.follow_pointer((799,599),100)
        self.assertEqual(c.center,(1200.,1000.))

    def test_frame_rate_independence(self):
        a=self.camera(); b=self.camera()
        for _ in range(30): a.follow_pointer((799,300),1/30)
        for _ in range(60): b.follow_pointer((799,300),1/60)
        self.assertAlmostEqual(a.center[0],b.center[0])

    def test_screen_speed_preserved_at_different_zooms(self):
        a=self.camera(); b=self.camera(); b.scale=.5
        a.follow_pointer((799,300),.1); b.follow_pointer((799,300),.1)
        self.assertAlmostEqual(a.center[0],b.center[0]*b.scale)

    def test_application_guards_and_system_camera(self):
        state={'pos':(890,300),'pressed':(False,False,False),'focus':True}
        mouse=SimpleNamespace(get_pos=lambda:state['pos'],get_pressed=lambda:state['pressed'],get_focused=lambda:state['focus'])
        renderer=SimpleNamespace(buttons=[],fleet_points={})
        app=Application(SimpleNamespace(mouse=mouse,Rect=Rect),renderer,Path('unused.json'))
        app.begin(new_campaign()); initial=app.camera.center
        app.update_pointer_camera(.1)
        self.assertGreater(app.camera.center[0],initial[0])
        for field,value in (('settings_open',True),('admin_open',True),('focused',False),('order_request',(1,2)),('mode','menu')):
            old=getattr(app,field); setattr(app,field,value); before=app.camera.center
            app.update_pointer_camera(.1); self.assertEqual(app.camera.center,before)
            setattr(app,field,old)
        for key,value in (('pressed',(True,False,False)),('focus',False)):
            old=state[key]; state[key]=value; before=app.camera.center
            app.update_pointer_camera(.1); self.assertEqual(app.camera.center,before); state[key]=old
        renderer.buttons=[SimpleNamespace(rect=Rect((880,280,20,40)))]
        before=app.camera.center; app.update_pointer_camera(.1)
        self.assertEqual(app.camera.center,before)
        renderer.buttons=[]; state['pos']=(40,600)
        app.update_pointer_camera(.1); self.assertEqual(app.camera.center,before)
        app.mode='system'; state['pos']=(890,300); before=app.system_camera.center
        app.update_pointer_camera(.1); self.assertGreater(app.system_camera.center[0],before[0])


if __name__=='__main__': unittest.main()
