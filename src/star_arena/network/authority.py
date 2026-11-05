"""Autorité de campagne, sans rendu ni socket. Mutations séquentielles uniquement."""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import secrets
from tempfile import NamedTemporaryFile

from star_arena.domain.galaxy import new_campaign
from star_arena.persistence import campaign_payload, decode
from star_arena.systems.simulation import Simulation
from star_arena.systems.economy import yard_order, transfer
from star_arena.systems.planets import build
from star_arena.systems.combat import auto_resolve
from star_arena.network.protocol import integer, text, keys, dumps, loads, PROTOCOL


def digest(token): return hashlib.sha256(token.encode('utf-8')).hexdigest()


@dataclass
class Participant:
    id: str
    name: str
    faction: int
    reconnect_hash: str
    online: bool=True
    sequence: int=0


class Authority:
    def __init__(self,name='Partie LAN',host_name='Hôte',size=60,seed=42):
        self.name=text(name,40); self.size=integer(size,15,100); self.seed=integer(seed,0,2**31-1)
        if size not in (15,30,60,100): raise ValueError('Taille de galaxie invalide.')
        self.session_id=secrets.token_hex(16); self.invite=secrets.token_urlsafe(24)
        self.members={}; self.campaign=None; self.simulation=None; self.started=False
        self.paused=False; self.speed=1; self.revision=0
        host,token=self.join(host_name,self.invite)
        self.host_id=host.id; self.host_token=token

    def join(self,name,invite='',reconnect=''):
        name=text(name,24)
        if reconnect:
            found=next((m for m in self.members.values() if secrets.compare_digest(m.reconnect_hash,digest(reconnect))),None)
            if found is None or found.online: raise ValueError('Clé de reconnexion invalide ou place déjà connectée.')
            found.online=True; self.revision+=1
            return found,reconnect
        if not secrets.compare_digest(invite,self.invite): raise ValueError('Invitation invalide.')
        if self.started or len(self.members)>=3: raise ValueError('Salon fermé ou complet.')
        faction=next(i for i in range(3) if i not in {m.faction for m in self.members.values()})
        token=secrets.token_urlsafe(32)
        member=Participant(secrets.token_hex(8),name,faction,digest(token))
        self.members[member.id]=member; self.revision+=1
        return member,token

    def disconnect(self,uid):
        if uid in self.members:
            self.members[uid].online=False; self.revision+=1

    def command(self,uid,sequence,command,args):
        m=self.members.get(uid)
        if m is None or not m.online: raise ValueError('Participant non connecté.')
        sequence=integer(sequence,1,2**53-1)
        if sequence<=m.sequence: raise ValueError('Commande répétée ou périmée.')
        m.sequence=sequence
        owner=m.faction
        if command=='faction':
            keys(args,('faction',)); faction=integer(args['faction'],0,2)
            if self.started or any(p.id!=uid and p.faction==faction for p in self.members.values()):
                raise ValueError('Faction déjà attribuée ou partie commencée.')
            m.faction=faction
        elif command=='size':
            keys(args,('size',))
            if uid!=self.host_id or self.started or self.campaign is not None or args['size'] not in (15,30,60,100): raise ValueError('Réglage réservé à l’hôte du salon.')
            self.size=integer(args['size'],15,100)
        elif command=='reinvite':
            keys(args,('participant',))
            if uid!=self.host_id or self.started: raise ValueError('Réinvitation réservée à l’hôte du salon.')
            member=self.members.get(text(args['participant'],32))
            if member is None or member.online or member.id==self.host_id: raise ValueError('Place non disponible pour réinvitation.')
            token=secrets.token_urlsafe(32); member.reconnect_hash=digest(token)
            self.revision+=1
            return {'message':'Nouvelle clé personnelle à transmettre au joueur concerné.', 'reconnect':token,'participant':member.id}
        elif command=='start':
            keys(args,())
            if uid!=self.host_id or self.started or not 2<=len(self.members)<=3 or not all(p.online for p in self.members.values()):
                raise ValueError('Deux ou trois joueurs connectés requis ; démarrage réservé à l’hôte.')
            if self.campaign is None: self.campaign=new_campaign(owner,seed=self.seed,system_count=self.size)
            self.campaign.player=owner
            self.simulation=Simulation(self.campaign,human_factions={p.faction for p in self.members.values()})
            self.started=True
        else:
            if not self.started or self.campaign is None: raise ValueError('La campagne n’a pas commencé.')
            if not all(p.online for p in self.members.values()): raise ValueError('Session suspendue : un joueur est déconnecté.')
            c=self.campaign; error=''
            if command=='move':
                keys(args,('fleet','destination'),('mode','target'))
                fleet=integer(args['fleet'],1); destination=integer(args['destination'])
                mode=args.get('mode','move'); target=args.get('target')
                if mode not in ('move','reinforce','merge'): raise ValueError('Ordre d’arrivée inconnu.')
                if mode=='merge':
                    target=integer(target,1); f=c.fleets.get(target)
                    if f is None or f.owner!=owner or f.system_id!=destination or f.travel or f.status!='permanent' or f.id==fleet:
                        raise ValueError('Cible de fusion invalide.')
                elif target is not None: raise ValueError('Cible superflue.')
                error=self.simulation.order_move(fleet,destination,owner)
                if not error:
                    f=c.fleets[fleet]; f.arrival_mode=mode; f.merge_target=target
                    self.simulation.finish_arrival(f)
            elif command=='yard':
                keys(args,('system',),('model',))
                model=args.get('model')
                if model is not None: model=text(model,16)
                error=yard_order(c,integer(args['system']),owner,model)
            elif command=='building':
                keys(args,('system','planet','kind'))
                error=build(c,integer(args['system']),integer(args['planet']),text(args['kind'],20),owner)
            elif command=='transfer':
                keys(args,('source','destination'),('ships',))
                destination=args['destination']
                if destination is not None: destination=integer(destination,1)
                ships=args.get('ships')
                if ships is not None:
                    if not isinstance(ships,list) or not 1<=len(ships)<=256 or any(type(i) is not int for i in ships) or len(set(ships))!=len(ships):
                        raise ValueError('Sélection d’unités invalide.')
                    ships=[integer(i,1) for i in ships]
                error=transfer(c,integer(args['source'],1),destination,owner,ships)
            elif command=='auto_battle':
                keys(args,())
                if c.pending is None or (owner not in (c.pending.attacker,c.pending.defender) and uid!=self.host_id):
                    raise ValueError('Seul un camp engagé ou l’hôte peut demander la résolution.')
                auto_resolve(c)
            elif command in ('pause','speed'):
                if uid!=self.host_id: raise ValueError('Réglage de simulation réservé à l’hôte.')
                if command=='pause':
                    keys(args,()); self.paused=not self.paused
                else:
                    keys(args,('speed',)); speed=integer(args['speed'],1,4)
                    if speed not in (1,2,4): raise ValueError('Vitesse invalide.')
                    self.speed=speed
            else: raise ValueError('Commande inconnue ; cheats et RTS interactif indisponibles en multijoueur.')
            if error: raise ValueError(error)
        self.revision+=1
        return 'Commande validée par l’hôte.'

    def advance(self,dt):
        if self.started and not self.paused and all(m.online for m in self.members.values()):
            self.simulation.advance(dt*self.speed); self.revision+=1

    def snapshot(self):
        return {'type':'state','protocol':PROTOCOL,'session':self.session_id,'name':self.name,
                'revision':self.revision,'started':self.started,'size':self.size,'seed':self.seed,'host':self.host_id,
                'paused':self.paused or any(not m.online for m in self.members.values()),'speed':self.speed,
                'participants':[{'id':m.id,'name':m.name,'faction':m.faction,'online':m.online} for m in self.members.values()],
                'campaign':campaign_payload(self.campaign) if self.campaign else None,
                'battle_mode':'Résolution automatique autoritaire ; RTS interactif solo uniquement.'}

    def save(self,path: Path):
        if self.campaign is None: raise ValueError('Aucune campagne à sauvegarder.')
        value={'multiplayer_version':1,'protocol':PROTOCOL,'name':self.name,'session':self.session_id,
               'host':self.host_id,'size':self.size,'participants':[asdict(m) for m in self.members.values()],
               'campaign':campaign_payload(self.campaign)}
        encoded=dumps(value)
        if len(encoded.encode('utf-8'))>2_100_000: raise ValueError('Sauvegarde multijoueur trop volumineuse.')
        if path.exists(): self.load(path) # préserver un format inconnu
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False,suffix='.tmp') as stream:
                temporary=Path(stream.name); stream.write(encoded)
            temporary.replace(path)
        finally:
            if temporary: temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls,path):
        with Path(path).open('rb') as stream: raw=stream.read(2_100_001)
        if len(raw)>2_100_000: raise ValueError('Sauvegarde multijoueur trop volumineuse.')
        v=loads(raw.decode('utf-8'))
        if type(v.get('multiplayer_version')) is not int or v['multiplayer_version']!=1 or type(v.get('protocol')) is not int or v['protocol']!=PROTOCOL: raise ValueError('Version multijoueur incompatible.')
        result=cls(v['name'],'Hôte',v['size']); result.session_id=text(v['session'],64)
        members=v['participants']
        if not isinstance(members,list) or not 2<=len(members)<=3: raise ValueError('Attributions invalides.')
        result.members={}
        for p in members:
            keys(p,('id','name','faction','reconnect_hash','online','sequence'))
            if type(p['online']) is not bool: raise ValueError('État de participant invalide.')
            m=Participant(text(p['id'],32),text(p['name'],24),integer(p['faction'],0,2),text(p['reconnect_hash'],64),False,integer(p['sequence'],0,2**53-1))
            if len(m.reconnect_hash)!=64 or any(c not in '0123456789abcdef' for c in m.reconnect_hash): raise ValueError('Empreinte invalide.')
            if m.id in result.members or any(other.faction==m.faction for other in result.members.values()): raise ValueError('Attribution dupliquée.')
            result.members[m.id]=m
        result.host_id=v['host']
        if result.host_id not in result.members: raise ValueError('Hôte inconnu.')
        result.host_token=secrets.token_urlsafe(32)
        result.members[result.host_id].reconnect_hash=digest(result.host_token)
        result.campaign=decode(v['campaign']); result.seed=result.campaign.seed; result.size=len(result.campaign.systems); result.started=False
        return result
