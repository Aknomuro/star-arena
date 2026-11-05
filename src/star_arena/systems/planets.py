"""Développement planétaire, installations persistantes et garnisons non transférables."""
from star_arena.domain.planet_generation import ensure_planets, planet_position
from star_arena.domain.models import Building, BuildJob, Campaign, Fleet, Planet, Ship, SHIP_TYPES
from star_arena.domain.planet_stats import PLANET_TYPES, GROUND, STATIONS, STATION_COSTS, DEFENSES


def station(p: Planet) -> Building | None:
    return next((b for b in p.orbitals if b.kind == 'station'), None)


def station_level(p: Planet) -> int:
    b=station(p)
    return b.level if b and b.unit and b.unit.alive else 0


def orbital_capacity(p: Planet) -> int:
    return 2 + min(2, station_level(p)//2)


def resistance(p: Planet) -> int:
    return p.ground.get('recruit',0)+p.ground.get('barracks',0)*3+p.ground.get('garrison',0)*5


def energy_balance(p: Planet) -> int:
    return 3+p.ground.get('power',0)*6-sum(p.ground.get(k,0) for k in ('mine','industry'))-sum(b.level for b in p.orbitals if b.unit and b.unit.alive)


def planet_income(p: Planet) -> tuple[float,float]:
    factor = 1 if energy_balance(p)>=0 else .5
    return (p.ground.get('trade',0)*3+p.ground.get('industry',0)*2)*factor, p.ground.get('mine',0)*p.richness*2*factor


def maintenance(p: Planet) -> int:
    return sum(STATIONS[b.level][7] if b.kind=='station' else 1 for b in p.orbitals if b.unit and b.unit.alive)


def build_spec(p: Planet, kind: str) -> tuple[int,int,int,int]:
    if kind in GROUND:
        level=p.ground.get(kind,0)+1
        return level, GROUND[kind][1]*level, GROUND[kind][2]*level, GROUND[kind][3]*level
    if kind=='station':
        b=station(p)
        level=(b.level if b.unit and not b.unit.alive else b.level+1) if b else 1
        a,m,t=STATION_COSTS.get(level,(0,0,0))
        return level,a,m,t
    if kind in DEFENSES:
        b=next((b for b in p.orbitals if b.kind==kind),None)
        level = (b.level if b.unit and not b.unit.alive else b.level+1) if b else 1
        spec=DEFENSES[kind]
        return level,spec[1]*level,spec[2]*level,spec[3]*level
    return 0,0,0,0


def build(c: Campaign, system_id: int, planet_id: int, kind: str, owner: int) -> str:
    s=c.systems.get(system_id)
    p=next((p for p in s.planets if p.id==planet_id),None) if s else None
    if c.pending or p is None or s.owner!=owner or p.owner!=owner or p.occupier is not None:
        return 'Une planète contrôlée, sans conflit ni occupation, est nécessaire.'
    level,a,m,t=build_spec(p,kind)
    maximum=4 if kind=='station' else 3 if kind in GROUND else 1
    if not level or level>maximum or any(j.kind==kind for j in p.jobs):
        return 'Construction inconnue, niveau maximal ou commande déjà en cours.'
    if p.kind=='gas' and kind in ('mine','industry','recruit','barracks','garrison'):
        return 'Cette installation au sol est impossible sur une géante gazeuse.'
    if kind in GROUND:
        reserved=set(p.ground)|{j.kind for j in p.jobs if j.kind in GROUND}
        if kind not in reserved and len(reserved)>=p.capacity:
            return 'Tous les emplacements au sol sont réservés ou occupés.'
    elif kind!='station':
        reserved={b.kind for b in p.orbitals if b.kind!='station'}|{j.kind for j in p.jobs if j.kind in DEFENSES}
        if kind not in reserved and len(reserved)>=orbital_capacity(p):
            return 'Tous les emplacements orbitaux sont réservés ou occupés.'
    r=c.resources[owner]
    if r.credits<a or r.minerals<m:
        return 'Crédits ou minerais insuffisants.'
    r.credits-=a; r.minerals-=m
    p.jobs.append(BuildJob(kind,level,float(t)))
    c.log(f'{p.name} : construction commandée.')
    return ''


def new_unit(c: Campaign, model: str, status: str) -> Ship:
    c.next_ship_id=max(c.next_ship_id,max((u.id for f in c.fleets.values() for u in f.ships),default=0)+1)
    _,hull,shield=SHIP_TYPES[model]
    result=Ship(c.next_ship_id,model,hull,shield,status)
    c.next_ship_id+=1
    return result


def defensive_units(c: Campaign, system_id: int, owner: int) -> list[Ship]:
    units=[]
    for p in c.systems[system_id].planets:
        if p.owner!=owner or p.occupier is not None:
            continue
        units.extend(b.unit for b in p.orbitals if b.unit and b.unit.alive)
        units.extend(u for u in p.militia if u.alive)
    return units


def prepare_garrison(c: Campaign, system_id: int) -> None:
    s=c.systems[system_id]
    if s.owner is None or any(f.status=='garrison' for f in c.fleets_at(system_id)):
        return
    units=defensive_units(c,system_id,s.owner)
    if units:
        c.next_fleet_id=max(c.next_fleet_id,max(c.fleets,default=0)+1)
        c.fleets[c.next_fleet_id]=Fleet(c.next_fleet_id,s.owner,system_id,units,status='garrison')
        c.next_fleet_id+=1


def finish_garrison(c: Campaign, system_id: int, winner: int | None) -> None:
    for f in list(c.fleets_at(system_id)):
        if f.status!='garrison':
            continue
        if winner is not None and winner!=f.owner:
            for u in f.ships:
                u.hull=0.; u.shield=0.
        del c.fleets[f.id]
    for p in c.systems[system_id].planets:
        p.militia[:]=[u for u in p.militia if u.alive]
        p.militia_clock=0.


def begin_occupation(c: Campaign, system_id: int) -> None:
    s=c.systems[system_id]
    for p in s.planets:
        if p.owner==s.owner:
            p.occupier=None; p.occupation=0.
        elif resistance(p)>0 and p.owner is not None:
            p.occupier=s.owner
            p.occupation=float(10+resistance(p)*5)
            p.jobs.clear()
        else:
            p.owner=s.owner; p.occupier=None; p.occupation=0.
            p.jobs.clear(); p.militia.clear()


def support(units: list[Ship], dt: float) -> None:
    """Version abstraite de la même réparation et régénération utilisée en RTS."""
    hull_rate=sum((STATIONS[int(u.model[-1])][6] if u.model.startswith('station') else 8. if u.model=='repair' else 0.) for u in units if u.alive)
    shield_rate=sum(12. for u in units if u.alive and u.model=='shield')
    for u in units:
        if u.alive:
            _,h,s=SHIP_TYPES[u.model]
            u.hull=min(h,u.hull+hull_rate*dt)
            u.shield=min(s,u.shield+shield_rate*dt)


def update_planets(c: Campaign, dt: float=1.) -> None:
    if c.pending:
        return
    for s in c.systems.values():
        for p in s.planets:
            if p.owner!=s.owner and p.occupier!=s.owner:
                begin_occupation(c,s.id)
            if p.occupier is not None:
                occupying=any(f.owner==p.occupier and f.ships and f.status=='permanent' for f in c.fleets_at(s.id))
                if occupying:
                    p.occupation=max(0.,p.occupation-dt)
                    if p.occupation<=0:
                        p.owner=p.occupier; p.occupier=None
                        p.militia.clear()
                        c.log(f'{p.name} : occupation achevée.')
                continue
            if p.owner is None:
                continue
            station_completed = False
            if p.jobs:
                j=p.jobs[0]
                j.remaining=max(0.,j.remaining-dt*(1 if energy_balance(p)>=0 else .5))
                if j.remaining<=0:
                    if j.kind in GROUND:
                        p.ground[j.kind]=j.level
                    else:
                        old=next((b for b in p.orbitals if b.kind==j.kind),None)
                        model=f'station{j.level}' if j.kind=='station' else j.kind
                        unit=new_unit(c,model,'orbital')
                        if old and old.unit and old.unit.alive:
                            _,h,sh=SHIP_TYPES[old.unit.model]
                            unit.hull*=old.unit.hull/h
                            unit.shield*=old.unit.shield/sh if sh else 0
                        if old: p.orbitals.remove(old)
                        p.orbitals.append(Building(j.kind,j.level,unit))
                        station_completed = j.kind=='station'
                    p.jobs.pop(0)
                    label=GROUND[j.kind][0] if j.kind in GROUND else STATIONS[j.level][0] if j.kind=='station' else DEFENSES[j.kind][0]
                    c.log(f'{p.name} : {label} terminé (niveau {j.level}).')
            level=station_level(p)
            if level and not station_completed:
                p.militia_clock+=dt
                desired={'fighter':STATIONS[level][4], 'corvette':STATIONS[level][5]}
                for model,amount in desired.items():
                    if sum(u.model==model and u.alive for u in p.militia)<amount:
                        delay=20 if model=='fighter' else 35
                        a,m=(25,10) if model=='fighter' else (60,30)
                        r=c.resources[p.owner]
                        if p.militia_clock>=delay and r.credits>=a and r.minerals>=m:
                            r.credits-=a; r.minerals-=m
                            p.militia.append(new_unit(c,model,'militia'))
                            p.militia_clock=0.
                        break
                else:
                    p.militia_clock=0.


def ai_planets(c: Campaign, human_factions=None) -> None:
    for owner in range(3):
        if owner in (human_factions if human_factions is not None else {c.player}):
            continue
        sites=sorted((s for s in c.systems.values() if s.owner==owner),key=lambda s:(not s.capital,s.id))
        for s in sites[:3]:
            p=next((p for p in s.planets if p.owner==owner and p.occupier is None and p.kind!='gas'),s.planets[0])
            if p.jobs:
                continue
            frontier=any(c.systems[n].owner not in (None,owner) for n in c.neighbors(s.id))
            b=station(p)
            choices=[]
            if not b or not b.unit.alive:
                choices.append('station')
            if energy_balance(p)<1 and p.ground.get('power',0)<3:
                choices.append('power')
            if 'mine' not in p.ground:
                choices.append('mine')
            if frontier and not any(b.kind=='laser' for b in p.orbitals):
                choices.append('laser')
            if 'barracks' not in p.ground:
                choices.append('barracks')
            if b and b.level<4:
                choices.append('station')
            if 'trade' not in p.ground:
                choices.append('trade')
            # Un emplacement impossible ne bloque pas toutes les autres décisions.
            for kind in choices:
                if not build(c,s.id,p.id,kind,owner):
                    break
