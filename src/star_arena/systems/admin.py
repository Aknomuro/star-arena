"""Commandes de développement explicites, sans console exécutable ni dépendance graphique."""
from star_arena.domain.models import Campaign, Fleet, SHIP_TYPES
from star_arena.systems.planets import new_unit


def apply_cheat(c: Campaign, command: str, system_id: int) -> str:
    if c.pending is not None:
        return "Terminez le conflit avant d'utiliser un cheat de campagne."
    if command == 'resources':
        r=c.resources[c.player]
        r.credits=min(1e15,r.credits+10000)
        r.minerals=min(1e15,r.minerals+10000)
        message='+10 000 crédits et minerais.'
    elif command == 'fleet':
        system=c.systems.get(system_id)
        if system is None or system.owner!=c.player:
            return 'Sélectionnez un système que vous contrôlez.'
        c.next_fleet_id=max(c.next_fleet_id,max(c.fleets,default=0)+1)
        ships=[new_unit(c,model,'permanent') for model in
               ('cruiser','corvette','corvette','fighter','fighter','fighter','fighter','fighter')]
        fleet=Fleet(c.next_fleet_id,c.player,system_id,ships)
        c.fleets[fleet.id]=fleet
        c.next_fleet_id+=1
        message=f'Flotte admin {fleet.id} créée dans {system.name}.'
    elif command == 'repair':
        units=[u for f in c.fleets.values() if f.owner==c.player for u in f.ships]
        units += [u for s in c.systems.values() for p in s.planets
                  if p.owner==c.player and p.occupier is None
                  for u in p.militia+[b.unit for b in p.orbitals if b.unit]]
        for u in units:
            if u.alive:
                _,u.hull,u.shield=SHIP_TYPES[u.model]
        message='Coques et boucliers alliés restaurés ; les épaves restent détruites.'
    elif command == 'queues':
        for s in c.systems.values():
            if s.owner!=c.player:
                continue
            for job in s.queue:
                job.remaining=min(job.remaining,1.)
            for p in s.planets:
                if p.owner==c.player and p.occupier is None:
                    for job in p.jobs:
                        job.remaining=min(job.remaining,1.)
        message='Commandes payées accélérées : au plus 1 seconde par commande (hors pénurie).'
    else:
        return 'Commande admin inconnue.'
    c.log('ADMIN : '+message)
    return message
