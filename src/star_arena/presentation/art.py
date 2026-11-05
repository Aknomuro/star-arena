"""Primitives sobres avec contours adoucis ; surfaces statiques mises en cache et bornées."""
from star_arena.presentation.ship_sprites import SurfaceCache

PLANET_COLORS={'rocky':(148,143,126),'desert':(220,176,100),'ice':(159,217,240),
               'ocean':(66,143,220),'gas':(186,151,209),'industrial':(153,163,173)}


class Painter:
    def __init__(self,pg):
        self.pg=pg
        self.panels=SurfaceCache(32,3_000_000)
        self.planets=SurfaceCache(64,1_000_000)
        self.halos=SurfaceCache(32,500_000)
        self.reduced=False

    def quality(self,reduced):
        if reduced==self.reduced: return
        self.reduced=reduced
        self.panels.resize(16 if reduced else 32,1_500_000 if reduced else 3_000_000)
        self.planets.resize(32 if reduced else 64,500_000 if reduced else 1_000_000)
        self.halos.resize(16 if reduced else 32,200_000 if reduced else 500_000)

    def circle(self,surface,color,point,radius,width=0):
        pg=self.pg; xy=(round(point[0]),round(point[1])); r=max(1,round(radius))
        pg.draw.circle(surface,color,xy,r,width)
        gfx=getattr(pg,"gfxdraw",None)
        if gfx is not None:
            gfx.aacircle(surface,*xy,r,color)
            if width>1 and r>width:
                gfx.aacircle(surface,*xy,r-width,color)

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
