"""Contrôleur asynchrone de l'interface : aucune socket ni tâche à l'import."""
import asyncio
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from star_arena.network.authority import Authority
from star_arena.network.runtime import HostServer, Client
from star_arena.network.protocol import text
from star_arena.persistence import decode
from star_arena.network.replica import CampaignReplica


class Multiplayer:
    def __init__(self,app):
        self.app=app; self.server=None; self.client=None; self.task=None; self.commands=set()
        self.fields={'name':'Joueur','party':'Partie LAN','address':'192.168.1.10','bind':'0.0.0.0',
                     'port':'8765','seed':'42','invite':'','reconnect':''}
        self.focus='name'; self.status='PC/LAN · WebRTC non implémenté.'
        self.state=None; self.last_revision=None; self.profile_error=''; self.private_invite=''
        self.save_path=app.save_path.with_name('multiplayer.json')
        self.profile_path=app.save_path.parent.parent/'settings'/'network_reconnect.json'

    @property
    def active(self):
        return self.client is not None and self.state is not None and self.state.get('started',False)

    @property
    def is_host(self):
        return bool(self.client and self.state and self.client.participant==self.state.get('host'))

    def profiles(self):
        try:
            with self.profile_path.open('rb') as stream: raw=stream.read(32769)
            if len(raw)>32768: raise ValueError('Profils trop volumineux.')
            value=json.loads(raw.decode('utf-8'))
            if not isinstance(value,dict) or len(value)>16: raise ValueError('Profils invalides.')
            for url,profile in value.items():
                if not isinstance(url,str) or len(url)>200 or not isinstance(profile,dict): raise ValueError('Profil invalide.')
                text(profile.get('session'),64); text(profile.get('token'),128)
            return value
        except FileNotFoundError: return {}

    def remember(self,url):
        temporary=None
        try:
            values=self.profiles()
            values[url]={'session':self.client.session,'token':self.client.reconnect}
            if len(values)>16: values.pop(next(iter(values)))
            self.profile_path.parent.mkdir(parents=True,exist_ok=True)
            with NamedTemporaryFile('w',encoding='utf-8',dir=self.profile_path.parent,delete=False) as stream:
                temporary=Path(stream.name); json.dump(values,stream,ensure_ascii=False)
            temporary.replace(self.profile_path)
        except (OSError,ValueError,TypeError,RecursionError) as error:
            self.profile_error='Clé de reconnexion non enregistrée : '+str(error)
        finally:
            if temporary: temporary.unlink(missing_ok=True)

    def launch(self,coroutine):
        if self.task and not self.task.done():
            coroutine.close(); self.status='Connexion ou fermeture déjà en cours.'; return
        self.status='Connexion ou chargement en cours…'
        self.task=asyncio.create_task(self.guarded(coroutine))

    def request_leave(self,save=False):
        previous=self.task
        async def stop():
            if previous and not previous.done():
                previous.cancel(); await asyncio.gather(previous,return_exceptions=True)
            await self.guarded(self.leave(save))
        self.task=asyncio.create_task(stop())

    async def guarded(self,coroutine):
        try: await coroutine
        except (OSError,ValueError,KeyError,TypeError,asyncio.TimeoutError,ConnectionError,RecursionError) as error:
            self.status='Erreur réseau : '+str(error)[:180]
            if self.client and not self.client.connected: await self.client.close(); self.client=None
            if self.server and self.client is None: await self.server.close(); self.server=None

    async def host(self,load=False):
        if self.client or self.server: raise ValueError('Quittez la session actuelle.')
        if sys.platform=="emscripten": raise ValueError('Hébergement navigateur indisponible dans cette version.')
        port=int(self.fields['port'])
        if not 1<=port<=65535: raise ValueError('Port entre 1 et 65535 requis.')
        authority=Authority.load(self.save_path) if load else Authority(self.fields['party'],self.fields['name'],seed=int(self.fields['seed']))
        self.server=HostServer(authority,self.save_path)
        await self.server.start(self.fields['bind'],port)
        self.client=Client()
        local='127.0.0.1' if self.fields['bind']=='0.0.0.0' else '::1' if self.fields['bind']=='::' else self.fields['bind']
        local='['+local+']' if ':' in local else local
        await self.client.connect(f'ws://{local}:{port}/star-arena',self.fields['name'],reconnect=authority.host_token)
        self.status='Salon ouvert. Transmettez votre IP LAN, le port et l’invitation.'
        self.app._change_mode('mp_lobby')

    async def join(self,fresh=False):
        if sys.platform=="emscripten": raise ValueError("Client navigateur non livré : utiliser la version PC/LAN.")
        if self.client: await self.client.close(); self.client=None
        self.state=None; self.last_revision=None
        if self.server: raise ValueError('Quittez le serveur local avant de rejoindre ailleurs.')
        port=int(self.fields['port'])
        if not 1<=port<=65535: raise ValueError('Port invalide.')
        address=text(self.fields['address'],100)
        if '/' in address or '@' in address: raise ValueError('Entrer une IP ou un nom local, sans URL.')
        address='['+address.strip('[]')+']' if ':' in address else address
        url=f'ws://{address}:{port}/star-arena'
        reconnect=self.fields['reconnect']
        if not reconnect and not fresh:
            try: reconnect=self.profiles().get(url,{}).get('token','')
            except (OSError,ValueError,TypeError): reconnect=''
        self.client=Client()
        await self.client.connect(url,self.fields['name'],self.fields['invite'],reconnect)
        self.remember(url)
        self.status='Connecté ; l’hôte contrôle la simulation.'
        self.app._change_mode('mp_lobby')

    def send(self,command,args=None):
        if not self.client or not self.client.connected:
            self.status='Session non connectée.'; return
        async def submit():
            try:
                result=await self.client.command(command,args)
                self.status=result['message']; self.app.message=self.status
                if result.get('reconnect'):
                    self.private_invite=result['reconnect']
                    self.status+=' Place : '+result['participant']
            except (OSError,ValueError,KeyError,TypeError) as error:
                self.status='Commande refusée : '+str(error)
        self.status='Commande envoyée à l’hôte…'; self.app.message=self.status
        task=asyncio.create_task(submit()); self.commands.add(task)
        task.add_done_callback(self.commands.discard)

    def poll(self):
        if not self.client: return
        if self.client.error: self.status=self.client.error
        snapshot=self.client.latest
        if snapshot is None or snapshot is self.state: return
        self.state=snapshot
        if not snapshot['started']: return
        if self.last_revision==snapshot['revision']: return
        self.last_revision=snapshot['revision']
        try:
            member=next(p for p in snapshot['participants'] if p['id']==self.client.participant)
            faction=member['faction']
            if type(faction) is not int or faction not in range(3): raise ValueError('Faction invalide.')
            campaign=decode(snapshot['campaign']); campaign.player=faction
            first=self.app.mode.startswith('mp_')
            old_report=self.app.simulation.campaign.reports[0].id if self.app.simulation and self.app.simulation.campaign.reports else None
            if first:
                self.app.begin(campaign,view_only=True)
            else:
                self.app.simulation=CampaignReplica(campaign)
                if self.app.selected_system not in campaign.systems: self.app.selected_system=next(iter(campaign.systems))
            self.app.paused=snapshot['paused']; self.app.speed=snapshot['speed']
            if campaign.pending and self.app.mode=='system': self.app._change_mode('galaxy')
            if campaign.reports and campaign.reports[0].id!=old_report:
                self.app.report=campaign.reports[0]; self.app.report_page=0; self.app._change_mode('report')
            elif self.app.mode=='report' and self.app.report:
                self.app.report=next((r for r in campaign.reports if r.id==self.app.report.id),campaign.reports[0] if campaign.reports else None)
        except (ValueError,KeyError,TypeError,StopIteration) as error:
            self.status='État serveur invalide : '+str(error)

    async def close(self):
        if self.client: await self.client.close()
        if self.server: await self.server.close()
        for task in tuple(self.commands): task.cancel()
        if self.commands: await asyncio.gather(*tuple(self.commands),return_exceptions=True)
        self.client=None; self.server=None; self.state=None; self.last_revision=None

    async def leave(self,save=False):
        if save and self.client and self.is_host:
            result=await self.client.command('save')
            if not result.get('ok'): raise ValueError(result['message'])
        await self.close()
        self.app.simulation=None; self.app.battle=None; self.app.report=None; self.app.order_request=None
        self.app._change_mode('mp_menu'); self.status='Session quittée.'
