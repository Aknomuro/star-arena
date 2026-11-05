"""Vue de gestion : dessin vectoriel et entrées injectées, sans chargement de campagne."""
from math import hypot
from star_arena.domain.models import FACTIONS, SHIP_TYPES
from star_arena.domain.planet_stats import PLANET_TYPES, GROUND, DEFENSES, STATIONS
from star_arena.systems.planets import planet_position, planet_income, resistance, orbital_capacity, energy_balance, build_spec

COLORS={'rocky':(148,143,126),'desert':(220,176,100),'ice':(159,217,240),
        'ocean':(66,143,220),'gas':(186,151,209),'industrial':(153,163,173)}
CATEGORIES={'economy':'ÉCO.','defense':'DÉFENSE','production':'PROD.','militia':'MILICES'}
EFFECTS={'mine':'Minerais selon la richesse', 'power':'Énergie locale +6/niveau',
         'trade':'Crédits +3/s/niveau','industry':'Crédits +2/s ; chantier +15%/niveau',
         'recruit':'Résistance +1/niveau','barracks':'Résistance +3/niveau','garrison':'Résistance +5/niveau'}


def pick_planet(campaign, system_id, camera, point):
    for i,p in enumerate(campaign.systems[system_id].planets):
        x,y=camera.screen(planet_position(i))
        if hypot(point[0]-x,point[1]-y)<=max(12,18*camera.scale)+6:
            return p.id
    return None


def draw_system(ui, app) -> None:
    pg=app.pg; c=app.simulation.campaign; s=c.systems[app.selected_system]
    camera=app.system_camera
    ui.panel((16,16,1248,78))
    ui.text(f'SYSTÈME {s.name.upper()}',32,27,24)
    r=c.resources[c.player]
    ui.text(f'Crédits {r.credits:.0f} · Minerais {r.minerals:.0f} · Énergie {r.energy:.0f}',32,62,14)
    ui.button('pause','Reprendre' if app.paused else 'Pause',(680,33,110,40))
    for i,speed in enumerate((1,2,4)):
        ui.button(f'speed:{speed}',f'×{speed}',(800+i*52,33,46,40),active=app.speed==speed)
    ui.button('save','Sauver',(962,33,100,40))
    ui.button('system_return','Galaxie (Échap)',(1072,33,173,40))
    clip=ui.surface.get_clip(); ui.surface.set_clip(camera.viewport)
    star=camera.screen((0,0))
    ui.circle(ui.surface,(255,205,105),star,max(7,round(28*camera.scale)))
    ui.circle(ui.surface,(235,147,70),star,max(10,round(36*camera.scale)),2)
    for i,p in enumerate(s.planets):
        radius=round((90+i*64)*camera.scale)
        ui.circle(ui.surface,(39,59,80),star,max(1,radius),1)
        xy=camera.screen(planet_position(i)); size=max(9,round(18*camera.scale))
        ui.painter.planet(ui.surface,xy,size,p.kind)
        color=(143,166,184) if p.owner is None else FACTIONS[p.owner].color
        ui.circle(ui.surface,color,xy,size+4,2)
        if p.id==app.selected_planet:
            ui.circle(ui.surface,(245,232,170),xy,size+8,1)
        ui.text(p.name,xy[0]-45,xy[1]+size+10,14,width=170)
        if p.owner==c.player:
            for index,b in enumerate(p.orbitals):
                ox,oy=xy[0]+size+12+index*9,xy[1]-size-5
                ui.circle(ui.surface,color if b.unit and b.unit.alive else (110,70,70),(ox,oy),3)
    ui.surface.set_clip(clip)
    p=next((p for p in s.planets if p.id==app.selected_planet),s.planets[0])
    ui.panel((912,110,352,605))
    ui.text(p.name,930,126,24,width=313)
    ui.text(PLANET_TYPES[p.kind][0],930,163,16)
    known=p.owner==c.player and p.occupier is None
    owner='Neutre' if p.owner is None else FACTIONS[p.owner].name
    ui.text(owner if known else owner+' · Informations limitées',930,187,14,width=313)
    for i,(key,title) in enumerate(CATEGORIES.items()):
        ui.button('category:'+key,title,(922+i*83,229,80,31),active=key==app.system_category)
    if not known:
        if p.occupier==c.player:
            total=10+resistance(p)*5
            progress=max(0.,min(1.,1-p.occupation/total))
            ui.text(f'Occupation : {progress:.0%} · {p.occupation:.0f} s',930,284,16)
            pg.draw.rect(ui.surface,(40,68,91),(930,310,310,6))
            pg.draw.rect(ui.surface,(110,200,160),(930,310,round(310*progress),6))
            ui.wrapped('Une flotte permanente doit rester sur place pour poursuivre le siège.',930,324,310,3)
        else:
            ui.wrapped('Développement réservé aux planètes contrôlées. Reconnaissance limitée au type et au propriétaire.',930,284,310,4)
        return
    if app.system_category=='production':
        ui.economy(app,s)
    else:
        if app.system_category=='economy': kinds=('mine','power','trade','industry')
        elif app.system_category=='militia': kinds=('recruit','barracks','garrison')
        else: kinds=('station',*DEFENSES)
        for i,kind in enumerate(kinds):
            level,a,m,t=build_spec(p,kind)
            maximum=4 if kind=='station' else 3 if kind in GROUND else 1
            name=GROUND[kind][0] if kind in GROUND else STATIONS[min(level,4)][0] if kind=='station' else DEFENSES[kind][0]
            y=274+i*43
            ui.text(f'{name} · N{min(level,maximum)}',930,y,14,width=210)
            ui.text(f'{a} C / {m} M · {t}s',930,y+19,14,(143,166,184),width=210)
            ui.button('planet_build:'+kind,'Bâtir / +',(1145,y,99,36),level<=maximum and not any(j.kind==kind for j in p.jobs))
        y=274+len(kinds)*43+10
        if app.system_category=='economy':
            a,m=planet_income(p)
            ui.text(f'Bonus : +{a:g} C/s · +{m:g} M/s',930,y,14)
            ui.text(f'Équilibre énergétique local : {energy_balance(p):+}',930,y+23,14)
        elif app.system_category=='militia':
            ui.text(f'Résistance terrestre : {resistance(p)}',930,y,16)
            ui.text(f'Milice orbitale : {len(p.militia)} unités',930,y+25,16)
            ui.wrapped('Reconstitution payante : 20s/chasseur (25 C, 10 M), 35s/corvette (60 C, 30 M).',930,y+55,310,3)
        reserved_ground=len(set(p.ground)|{j.kind for j in p.jobs if j.kind in GROUND})
        ui.text(f'Sol {reserved_ground}/{p.capacity} · Orbite {sum(b.kind!="station" for b in p.orbitals)}/{orbital_capacity(p)} + station',930,598,14)
        page=min(app.planet_queue_page,max(0,(len(p.jobs)-1)//2))
        ui.button('planet_queue:-1','‹',(1150,674,42,27),page>0)
        ui.button('planet_queue:1','›',(1200,674,42,27),(page+1)*2<len(p.jobs))
        for i,j in enumerate(p.jobs[page*2:page*2+2]):
            name=GROUND[j.kind][0] if j.kind in GROUND else 'Station' if j.kind=='station' else DEFENSES[j.kind][0]
            ui.text(f'{name} N{j.level} : {j.remaining:.0f}s',930,623+i*23,14,width=310)
        ui.text('Pop. '+str(int(p.population))+' · Richesse '+str(p.richness),930,679,14,width=210)
    if p.orbitals:
        ui.panel((28,595,850,86))
        for i,b in enumerate(p.orbitals):
            u=b.unit
            label=SHIP_TYPES[u.model][0]
            state='DÉTRUITE — reconstruire' if not u.alive else f'Coque {u.hull:.0f} · Bouclier {u.shield:.0f}'
            if b.kind in ('laser','missile','heavy'):
                state+=' · Arme spécialisée, tir automatique'
            elif b.kind=='shield':
                state+=' · Boucliers alliés +12/s à portée'
            elif b.kind=='repair':
                state+=' · Coques alliées +8/s à portée'
            elif b.kind=='radar':
                state+=' · Portée alliée +20% à proximité'
            if b.kind=='station':
                spec=STATIONS[b.level]
                state+=f' · {spec[3]} tourelles · milice {spec[4]}C/{spec[5]}CV · réparation {spec[6]:g}/s'
            ui.text(label+' : '+state,38,598+i*16,14,width=825)
    fleets=[f for f in c.fleets_at(s.id) if f.status=='permanent' and f.ships]
    ui.text(f'Orbite du système : {len(fleets)} flottes, {sum(len(f.ships) for f in fleets)} unités permanentes',28,689,14)
    ui.panel((16,731,1248,55)); ui.wrapped(app.message,30,739,1218,2)
    ground=', '.join(f'{GROUND[k][0]} N{v}' for k,v in p.ground.items()) or 'aucun'
    ui.text('Bâtiments : '+ground,28,706,14,width=860)
