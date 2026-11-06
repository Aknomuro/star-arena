"""Compatibilité graphique simulée : aucune importation Pygame, image ou fenêtre réelle."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from star_arena.presentation.art import Painter


class GraphicsError(Exception):
    pass


class Surface:
    def __init__(self,size=(1280,800),flags=0):
        self.size=size; self.flags=flags; self.blits=[]; self.fills=[]; self.blit_error=None

    def get_width(self): return self.size[0]
    def get_height(self): return self.size[1]
    def get_rect(self,**kwargs): return kwargs
    def fill(self,color): self.fills.append(color)
    def blit(self,*args,**kwargs):
        if self.blit_error: raise self.blit_error
        self.blits.append((args,kwargs))


class Backend:
    error=GraphicsError
    SRCALPHA=1
    BLEND_RGBA_MULT=2

    def __init__(self):
        self.calls=[]; self.images=[]; self.scales=[]; self.gfx_calls=0; self.aa_calls=0
        self.gfx_error=None; self.aa_error=None; self.scale_error=None
        self.gfxdraw=SimpleNamespace(aacircle=self.aacircle)
        self.draw=SimpleNamespace(circle=self.primitive('circle'),line=self.primitive('line'),
                                  polygon=self.primitive('polygon'),ellipse=self.primitive('ellipse'),
                                  rect=self.primitive('rect'),aaline=self.aaline)
        self.transform=SimpleNamespace(smoothscale=self.smoothscale)

    def primitive(self,name):
        def draw(*args,**kwargs): self.calls.append((name,args,kwargs))
        return draw

    def Surface(self,size,flags=0):
        image=Surface(size,flags); self.images.append(image); return image

    def smoothscale(self,image,size):
        if self.scale_error: raise self.scale_error
        self.scales.append((image,size)); return Surface(size,self.SRCALPHA)

    def aacircle(self,*args):
        self.gfx_calls+=1
        if self.gfx_error: raise self.gfx_error

    def aaline(self,*args):
        self.aa_calls+=1
        if self.aa_error: raise self.aa_error


class GraphicsCompatibilityTests(unittest.TestCase):
    def web_painter(self,backend):
        with patch('sys.platform','emscripten'):
            return Painter(backend)

    def test_web_never_calls_importable_but_broken_gfxdraw(self):
        pg=Backend(); pg.gfx_error=GraphicsError("Parameter 'renderer' is invalid")
        painter=self.web_painter(pg); target=Surface()
        painter.circle(target,(18,36,51),(120,140),15)
        self.assertEqual(pg.gfx_calls,0)
        self.assertEqual(len(pg.scales),1)
        self.assertEqual(len(target.blits),1)
        self.assertEqual(pg.images[0].size,(68,68))

    def test_desktop_failure_draws_base_and_disables_only_failed_capability(self):
        pg=Backend(); pg.gfx_error=GraphicsError("Parameter 'renderer' is invalid")
        painter=Painter(pg); target=Surface()
        with self.assertWarnsRegex(RuntimeWarning,'gfxdraw.aacircle'):
            painter.circle(target,(18,36,51),(120,140),15)
        self.assertEqual(pg.calls[0][0],'circle')
        self.assertEqual(painter.compatibility_errors['gfxdraw.aacircle'],str(pg.gfx_error))
        painter.circle(target,(18,36,51),(120,140),15)
        painter.circle(target,(18,36,51),(170,190),15)
        self.assertEqual(pg.gfx_calls,1)
        self.assertEqual(len(pg.scales),1)
        self.assertEqual(len(target.blits),2)
        self.assertTrue(painter._line_aa)

    def test_desktop_working_antialias_is_preserved(self):
        pg=Backend(); painter=Painter(pg)
        painter.circle(Surface(),(100,120,140),(12.2,14.8),15,3)
        self.assertEqual(pg.gfx_calls,2)
        self.assertEqual(len(pg.images),0)
        self.assertEqual(pg.calls[0][1][2],(12,15))

    def test_unexpected_gfx_errors_are_not_hidden(self):
        for error in (GraphicsError('Invalid color argument'),RuntimeError('unexpected bug'),TypeError('bad API call')):
            with self.subTest(error=str(error)):
                pg=Backend(); pg.gfx_error=error; painter=Painter(pg)
                with self.assertRaises(type(error)):
                    painter.circle(Surface(),(1,2,3),(0,0),12)
                self.assertEqual(painter.compatibility_errors,{})
                self.assertIsNotNone(painter._gfx_circle)

    def test_aaline_known_failure_falls_back_once(self):
        pg=Backend(); pg.aa_error=GraphicsError("Parameter 'renderer' is invalid")
        painter=Painter(pg)
        with self.assertWarnsRegex(RuntimeWarning,'draw.aaline'):
            painter.line(Surface(),(1,2,3),(0,0),(10,20),antialias=True)
        painter.line(Surface(),(1,2,3),(0,0),(10,20),antialias=True)
        self.assertEqual(pg.aa_calls,1)
        self.assertEqual([name for name,*_ in pg.calls],['line','line'])
        self.assertIsNotNone(painter._gfx_circle)

    def test_unexpected_aaline_failure_propagates(self):
        pg=Backend(); pg.aa_error=GraphicsError('Surface was quit')
        painter=Painter(pg)
        with self.assertRaisesRegex(GraphicsError,'Surface was quit'):
            painter.line(Surface(),(1,2,3),(0,0),(10,20),antialias=True)
        self.assertEqual(pg.calls,[])

    def test_missing_optional_aaline_uses_standard_line(self):
        pg=Backend(); del pg.draw.aaline
        painter=Painter(pg)
        painter.line(Surface(),(1,2,3),(0,0),(10,20),antialias=True)
        self.assertEqual([name for name,*_ in pg.calls],['line'])

    def test_line_polygon_ellipse_preserve_rgba_without_gfx(self):
        pg=Backend(); pg.gfx_error=AssertionError('gfxdraw must not run')
        painter=self.web_painter(pg); target=Surface(); color=(20,40,60,80)
        painter.line(target,color,(0,0),(10,20),2)
        painter.polygon(target,color,[(0,0),(10,0),(0,10)],1)
        painter.ellipse(target,color,(0,0,30,20),2)
        self.assertEqual([name for name,*_ in pg.calls],['line','polygon','ellipse'])
        self.assertTrue(all(args[1]==color for _,args,_ in pg.calls))
        self.assertEqual(pg.gfx_calls,0)

    def test_transparent_circle_uses_clear_alpha_surface(self):
        pg=Backend(); painter=self.web_painter(pg); target=Surface()
        painter.circle(target,(20,40,60,80),(25,35),12,2)
        self.assertEqual(pg.images[0].flags,pg.SRCALPHA)
        self.assertEqual(pg.images[0].fills,[(0,0,0,0)])
        self.assertEqual(pg.calls[0][1][1],(20,40,60,80))
        self.assertEqual(pg.calls[0][1][-1],4)
        self.assertEqual(target.blits[0][0][1],{'center':(25,35)})

    def test_transparent_panels_glows_planets_do_not_use_gfx(self):
        pg=Backend(); pg.gfx_error=AssertionError('gfxdraw must not run')
        painter=self.web_painter(pg); target=Surface()
        painter.panel(target,(0,0,120,80))
        painter.glow(target,(100,100),(50,80,120),20)
        painter.planet(target,(100,100),20,'rocky')
        self.assertEqual(pg.gfx_calls,0)
        self.assertTrue(all(image.flags==pg.SRCALPHA for image in pg.images))
        self.assertEqual(len(target.blits),3)
        mask_blits=[kw for image in pg.images for _,kw in image.blits if 'special_flags' in kw]
        self.assertEqual(mask_blits,[{'special_flags':pg.BLEND_RGBA_MULT}])

    def test_supersampling_cache_and_temporary_sizes_are_bounded(self):
        pg=Backend(); painter=self.web_painter(pg); target=Surface()
        for i in range(100): painter.circle(target,(i,60,80),(i,100),45)
        self.assertLessEqual(len(painter.circles.items),48)
        self.assertLessEqual(painter.circles.pixels,250_000)
        self.assertLessEqual(max(max(image.size) for image in pg.images),200)
        painter.quality(True)
        self.assertLessEqual(len(painter.circles.items),24)
        self.assertLessEqual(painter.circles.pixels,100_000)
        before=len(pg.images)
        painter.circle(target,(20,40,60),(0,0),1000)
        self.assertEqual(len(pg.images),before)
        self.assertEqual(pg.calls[-1][1][3],1000)

    def test_failed_optional_smoothscale_falls_back_to_draw(self):
        pg=Backend(); pg.scale_error=GraphicsError("Parameter 'renderer' is invalid")
        painter=self.web_painter(pg)
        with self.assertWarnsRegex(RuntimeWarning,'circle.smoothscale'):
            painter.circle(Surface(),(20,40,60),(10,20),15)
        painter.circle(Surface(),(20,40,60),(10,20),15)
        self.assertFalse(painter._supersampling)
        self.assertEqual(pg.calls[-1][1][2],(10,20))
        self.assertEqual(len(pg.images),1)

    def test_unexpected_scaling_and_target_blit_errors_propagate(self):
        pg=Backend(); pg.scale_error=GraphicsError('Out of memory')
        painter=self.web_painter(pg)
        with self.assertRaisesRegex(GraphicsError,'Out of memory'):
            painter.circle(Surface(),(20,40,60),(10,20),15)
        pg.scale_error=None; target=Surface(); target.blit_error=GraphicsError("Parameter 'renderer' is invalid")
        with self.assertRaises(GraphicsError):
            painter.circle(target,(20,40,60),(10,20),15)


if __name__=='__main__': unittest.main()
