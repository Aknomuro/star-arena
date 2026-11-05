"""Serveur LAN et client asyncio ; instantanés coalescés, affichage jamais attendu."""
import asyncio
from collections import deque
from pathlib import Path
import time
from star_arena.network.protocol import loads, dumps, keys, text, integer, PROTOCOL, BUILD, validate_state
from star_arena.network.transport import accept_websocket, connect_websocket


class Peer:
    def __init__(self,transport):
        self.transport=transport; self.messages=deque(); self.state=None; self.wake=asyncio.Event()
        self.task=None
        self.uid=None; self.count=0; self.window=time.monotonic()

    def enqueue(self,message):
        if isinstance(message,str) or message.get('type')=='state': self.state=message
        else:
            if len(self.messages)>=16: raise ValueError('Client trop lent.')
            self.messages.append(message)
        self.wake.set()

    async def writer(self):
        while True:
            await self.wake.wait()
            while self.messages or self.state:
                message=self.messages.popleft() if self.messages else self.state
                if message is self.state: self.state=None
                await self.transport.send(message if isinstance(message,str) else dumps(message))
            self.wake.clear()


class HostServer:
    def __init__(self,authority,save_path: Path):
        self.authority=authority; self.save_path=save_path; self.server=None
        authority.disconnect(authority.host_id)
        self.peers=set(); self.tasks=set(); self.clock_task=None; self.port=None; self.closed=False
        self.connections=0

    async def start(self,host='127.0.0.1',port=0):
        self.server=await asyncio.start_server(self.handle,host,port,limit=8192)
        self.port=self.server.sockets[0].getsockname()[1]
        self.clock_task=asyncio.create_task(self.clock())
        return self.port

    def broadcast(self):
        state=dumps(self.authority.snapshot())
        for peer in tuple(self.peers): peer.enqueue(state)

    async def clock(self):
        frames=0
        while not self.closed:
            await asyncio.sleep(.1)
            for peer in tuple(self.peers):
                if time.monotonic()-peer.transport.last_received>15 and peer.task:
                    peer.task.cancel()
            self.authority.advance(.1); frames+=1
            if frames%3==0: self.broadcast()

    async def handle(self,reader,writer):
        task=asyncio.current_task(); self.tasks.add(task); self.connections+=1
        peer=None; sender=None; transport=None
        try:
            if self.connections>12: raise ValueError('Trop de connexions simultanées.')
            transport=await accept_websocket(reader,writer)
            hello=loads(await asyncio.wait_for(transport.recv(),5))
            keys(hello,('type','protocol','build','name','invite','reconnect'))
            if hello['type']!='hello' or type(hello['protocol']) is not int or hello['protocol']!=PROTOCOL or hello['build']!=BUILD:
                raise ValueError('Version du protocole ou du jeu incompatible.')
            invitation=hello['invite']; reconnect=hello['reconnect']
            if not isinstance(invitation,str) or len(invitation)>128 or not isinstance(reconnect,str) or len(reconnect)>128:
                raise ValueError('Clé d’accès invalide.')
            member,token=self.authority.join(text(hello['name'],24),invitation,reconnect)
            peer=Peer(transport); peer.uid=member.id; peer.task=task; self.peers.add(peer)
            await transport.send(dumps({'type':'welcome','protocol':PROTOCOL,'participant':member.id,
                'reconnect':token,'sequence':member.sequence,'session':self.authority.session_id}))
            sender=asyncio.create_task(peer.writer())
            sender.add_done_callback(lambda done: task.cancel() if not done.cancelled() and done.exception() else None)
            self.broadcast()
            while True:
                message=loads(await transport.recv())
                now=time.monotonic()
                if now-peer.window>=1: peer.window=now; peer.count=0
                peer.count+=1
                if peer.count>30: raise ValueError('Limite de 30 commandes par seconde dépassée.')
                keys(message,('type','sequence','command','args'))
                if message['type']!='command': raise ValueError('Message inconnu.')
                seq=integer(message['sequence'],1,2**53-1)
                previous_revision=self.authority.revision
                try:
                    command=text(message['command'],24)
                    if command=='save':
                        keys(message['args'],())
                        m=self.authority.members[member.id]
                        if member.id!=self.authority.host_id or seq<=m.sequence: raise ValueError('Sauvegarde réservée à l’hôte ; commande périmée.')
                        m.sequence=seq
                        self.authority.save(self.save_path)
                        result='Campagne multijoueur sauvegardée sur l’hôte.'
                    else: result=self.authority.command(member.id,seq,command,message['args'])
                    peer.enqueue({'type':'ack','sequence':seq,'ok':True,**(result if isinstance(result,dict) else {'message':result})})
                except (ValueError,KeyError,TypeError,OSError) as error:
                    peer.enqueue({'type':'ack','sequence':seq,'ok':False,'message':str(error)[:180]})
                if self.authority.revision!=previous_revision: self.broadcast()
        except (ValueError,KeyError,TypeError,UnicodeError,OSError,ConnectionError,asyncio.TimeoutError,asyncio.IncompleteReadError,RecursionError) as error:
            if transport:
                try: await transport.send(dumps({'type':'error','message':str(error)[:180]}))
                except (OSError,ConnectionError,asyncio.TimeoutError): pass
        finally:
            if sender:
                sender.cancel()
                await asyncio.gather(sender,return_exceptions=True)
            if peer:
                self.peers.discard(peer); self.authority.disconnect(peer.uid)
                if not self.closed: self.broadcast()
            if transport: await transport.close()
            else:
                writer.close()
                try: await writer.wait_closed()
                except OSError: pass
            self.tasks.discard(task); self.connections-=1

    async def close(self):
        if self.closed: return
        self.closed=True
        if self.server: self.server.close()
        if self.clock_task:
            self.clock_task.cancel(); await asyncio.gather(self.clock_task,return_exceptions=True)
        for peer in tuple(self.peers):
            try: await peer.transport.send(dumps({'type':'closed','message':'L’hôte a fermé la session.'}))
            except (OSError,ConnectionError,asyncio.TimeoutError): pass
            await peer.transport.close()
        current=asyncio.current_task()
        for task in tuple(self.tasks):
            if task is not current: task.cancel()
        await asyncio.gather(*(t for t in tuple(self.tasks) if t is not current),return_exceptions=True)
        if self.server: await asyncio.wait_for(self.server.wait_closed(),3)


class Client:
    def __init__(self):
        self.transport=None; self.participant=None; self.reconnect=''; self.session=''
        self.sequence=0; self.latest=None; self.error=''; self.message=''; self.connected=False
        self.reader_task=None; self.heartbeat_task=None; self.waiting={}; self.closing=False

    async def connect(self,url,name,invite='',reconnect='',factory=connect_websocket):
        self.transport=await factory(url)
        try:
            await self.transport.send(dumps({'type':'hello','protocol':PROTOCOL,'build':BUILD,'name':name,'invite':invite,'reconnect':reconnect}))
            welcome=loads(await asyncio.wait_for(self.transport.recv(),5))
            if welcome.get('type')!='welcome': raise ValueError(welcome.get('message','Connexion refusée.'))
            keys(welcome,('type','protocol','participant','reconnect','sequence','session'))
            if type(welcome['protocol']) is not int or welcome['protocol']!=PROTOCOL: raise ValueError('Protocole incompatible.')
            self.participant=text(welcome['participant'],32); self.reconnect=text(welcome['reconnect'],128)
            self.session=text(welcome['session'],64); self.sequence=integer(welcome['sequence'],0,2**53-1)
            self.connected=True; self.closing=False
            self.reader_task=asyncio.create_task(self.reader()); self.heartbeat_task=asyncio.create_task(self.heartbeat())
            return self
        except BaseException:
            await self.transport.close(); raise

    async def reader(self):
        try:
            while True:
                value=loads(await asyncio.wait_for(self.transport.recv(),15))
                kind=value.get('type')
                if kind=='state':
                    validate_state(value,self.session)
                    self.latest=value
                elif kind=='ack':
                    keys(value,('type','sequence','ok','message'),('reconnect','participant'))
                    seq=integer(value['sequence'],1,2**53-1)
                    if type(value['ok']) is not bool: raise ValueError('Accusé invalide.')
                    self.message=text(value['message'],180)
                    if 'reconnect' in value: text(value['reconnect'],128); text(value.get('participant'),32)
                    future=self.waiting.pop(seq,None)
                    if future and not future.done(): future.set_result(value)
                elif kind in ('closed','error'):
                    keys(value,('type','message'))
                    self.error=text(value.get('message'),180); break
                else: raise ValueError('Message serveur inconnu.')
        except (OSError,ConnectionError,ValueError,KeyError,TypeError,asyncio.IncompleteReadError,asyncio.TimeoutError,RecursionError) as error:
            if not self.closing: self.error='Connexion interrompue : '+str(error)[:150]
        finally:
            self.connected=False
            for future in self.waiting.values():
                if not future.done(): future.set_result({'ok':False,'message':'Connexion interrompue.'})
            self.waiting.clear()
            if self.heartbeat_task: self.heartbeat_task.cancel()
            if self.transport: await self.transport.close()

    async def heartbeat(self):
        try:
            while self.connected:
                await asyncio.sleep(5)
                if hasattr(self.transport,'frame'): await self.transport.frame(9,b'arena')
        except (OSError,ConnectionError,asyncio.TimeoutError):
            self.error='Connexion perdue.'; self.connected=False

    async def command(self,name,args=None):
        if not self.connected: return {'ok':False,'message':'Non connecté.'}
        if len(self.waiting)>=16: return {'ok':False,'message':'Trop de commandes en attente.'}
        self.sequence+=1; seq=self.sequence
        future=asyncio.get_running_loop().create_future(); self.waiting[seq]=future
        try:
            await self.transport.send(dumps({'type':'command','sequence':seq,'command':name,'args':args if args is not None else {}}))
            return await asyncio.wait_for(future,5)
        except (OSError,ConnectionError,asyncio.TimeoutError) as error:
            return {'ok':False,'message':'Commande non confirmée : '+str(error)[:100]}
        finally: self.waiting.pop(seq,None)

    async def close(self):
        self.closing=True; self.connected=False
        if self.transport: await self.transport.close()
        tasks=[t for t in (self.reader_task,self.heartbeat_task) if t]
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks,return_exceptions=True)
