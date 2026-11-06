"""Primitives sobres avec contours adoucis ; surfaces statiques mises en cache et bornées."""
from star_arena.presentation.ship_sprites import SurfaceCache
import sys
import warnings

PLANET_COLORS={'rocky':(148,143,126),'desert':(220,176,100),'ice':(159,217,240),
               'ocean':(66,143,220),'gas':(186,151,209),'industrial':(153,163,173)}


class Painter:
    def __init__(self,pg):
        self.pg=pg
        self.panels=SurfaceCache(32,3_000_000)
        self.planets=SurfaceCache(64,1_000_000)
        self.halos=SurfaceCache(32,500_000)
        self.circles=SurfaceCache(48,250_000)
        self.compatibility_errors={}
        # SDL_gfx peut être importable mais inutilisable dans le build WASM de Pygbag.
        self._prefer_circle_surface=sys.platform=='emscripten'
        self._gfx_circle=None if self._prefer_circle_surface else getattr(getattr(pg,'gfxdraw',None),'aacircle',None)
        self._line_aa=callable(getattr(pg.draw,'aaline',None))
        self._supersampling=callable(getattr(pg,'Surface',None)) and callable(getattr(getattr(pg,'transform',None),'smoothscale',None))
        self.reduced=False

    def quality(self,reduced):
        if reduced==self.reduced: return
        self.reduced=reduced
        self.panels.resize(16 if reduced else 32,1_500_000 if reduced else 3_000_000)
        self.planets.resize(32 if reduced else 64,500_000 if reduced else 1_000_000)
        self.halos.resize(16 if reduced else 32,200_000 if reduced else 500_000)
        self.circles.resize(24 if reduced else 48,100_000 if reduced else 250_000)

    def _renderer_fallback(self, feature, error):
        # Seule l'incompatibilité SDL effectivement reproduite est récupérable ici.
        if str(error).strip().lower() != "parameter 'renderer' is invalid":
            raise error
        self.compatibility_errors[feature]=str(error)
        warnings.warn(feature+' indisponible : '+str(error)+' ; repli logiciel actif.',RuntimeWarning,stacklevel=3)

    def _circle_surface(self,surface,color,xy,r,width):
        if not self._supersampling or not 3<=r<=(24 if self.reduced else 48) or width<0:
            return False
        key=(tuple(color),r,width)
        image=self.circles.get(key)
        if image is None:
            size=r*2+4
            try:
                large=self.pg.Surface((size*2,size*2),self.pg.SRCALPHA)
                large.fill((0,0,0,0))
                self.pg.draw.circle(large,color,(size,size),r*2,width*2)
                image=self.pg.transform.smoothscale(large,(size,size))
            except self.pg.error as error:
                self._renderer_fallback('circle.smoothscale',error)
                self._supersampling=False
                return False
            self.circles.put(key,image)
        # Une erreur sur la surface cible n'est pas une option graphique défaillante.
        surface.blit(image,image.get_rect(center=xy))
        return True

    def circle(self,surface,color,point,radius,width=0):
        pg=self.pg; xy=(round(point[0]),round(point[1])); r=max(1,round(radius))
        if self._prefer_circle_surface and self._circle_surface(surface,color,xy,r,width):
            return
        pg.draw.circle(surface,color,xy,r,width)
        if callable(self._gfx_circle) and width>=0:
            try:
                self._gfx_circle(surface,*xy,r,color)
                if width>1 and r>width:
                    self._gfx_circle(surface,*xy,r-width,color)
            except pg.error as error:
                self._renderer_fallback('gfxdraw.aacircle',error)
                self._gfx_circle=None
                self._prefer_circle_surface=True
                # Le cercle de base est déjà affiché ; les appels suivants utiliseront le cache AA.

    def line(self,surface,color,start,end,width=1,*,antialias=False):
        if antialias and width==1 and self._line_aa:
            try:
                return self.pg.draw.aaline(surface,color,start,end)
            except self.pg.error as error:
                self._renderer_fallback('draw.aaline',error)
                self._line_aa=False
        return self.pg.draw.line(surface,color,start,end,width)

    def polygon(self,surface,color,points,width=0):
        return self.pg.draw.polygon(surface,color,points,width)

    def ellipse(self,surface,color,rect,width=0):
        return self.pg.draw.ellipse(surface,color,rect,width)

    def panel(self,surface,rect):
        pg=self.pg; x,y,w,h=rect
        key=(w,h)
        image=self.panels.get(key)
        if image is None:
            image=pg.Surface((w,h),pg.SRCALPHA)
            pg.draw.rect(image,(4,10,20,110),(2,3,w-2,h-3),border_radius=11)
            pg.draw.rect(image,(15,26,41,242),(0,0,w-2,h-3),border_radius=9)
            pg.draw.rect(image,(49,76,96,210),(0,0,w-2,h-3),1,border_radius=9)
            self.panels.put(key,image)
        surface.blit(image,(x,y))

    def glow(self,surface,point,color,radius):
        pg=self.pg; r=max(8,round(radius)); key=(tuple(color),r)
        image=self.halos.get(key)
        if image is None:
            image=pg.Surface((r*2+2,r*2+2),pg.SRCALPHA)
            for i in range(7,0,-1):
                pg.draw.circle(image,(*color,7+(7-i)*4),(r+1,r+1),max(1,r*i//7))
            self.halos.put(key,image)
        surface.blit(image,(round(point[0])-r-1,round(point[1])-r-1))

    def planet(self,surface,point,radius,kind):
        pg=self.pg; r=max(4,min(160,round(radius))); key=(kind,r)
        image=self.planets.get(key)
        if image is None:
            # Suréchantillonnage local uniquement ; aucune surface plein écran multipliée.
            size=(r*2+4)*2; center=size//2
            large=pg.Surface((size,size),pg.SRCALPHA)
            base=PLANET_COLORS[kind]
            pg.draw.circle(large,tuple(round(c*.55) for c in base),(center,center),r*2)
            pg.draw.circle(large,base,(center-r//4,center-r//4),max(1,round(r*1.7)))
            pg.draw.circle(large,tuple(min(255,round(c*1.18)) for c in base),(center-r//2,center-r//2),max(1,r))
            # Un masque circulaire propre évite tout débordement des aplats de lumière.
            mask=pg.Surface((size,size),pg.SRCALPHA)
            pg.draw.circle(mask,(255,255,255,255),(center,center),r*2)
            large.blit(mask,(0,0),special_flags=pg.BLEND_RGBA_MULT)
            image=pg.transform.smoothscale(large,(size//2,size//2))
            self.planets.put(key,image)
        surface.blit(image,image.get_rect(center=(round(point[0]),round(point[1]))))
