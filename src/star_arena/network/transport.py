"""Transport WebSocket asyncio borné, RFC 6455 sans compression ni dépendance externe.
Le serveur est destiné au LAN. Aucun NAT, pare-feu ou routeur n'est configuré ici.
"""
import asyncio
import base64
import hashlib
import os
import secrets
import struct
import time
from typing import Protocol
from urllib.parse import urlsplit

GUID='258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
MAX_STATE=2_100_000
MAX_COMMAND=16_384


class Transport(Protocol):
    async def send(self, text: str) -> None: ...
    async def recv(self) -> str: ...
    async def close(self) -> None: ...


def accept_key(key):
    return base64.b64encode(hashlib.sha1((key+GUID).encode('ascii')).digest()).decode('ascii')


async def headers(reader):
    try:
        raw=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),5)
    except (asyncio.LimitOverrunError,asyncio.IncompleteReadError) as error:
        raise ValueError('En-tête WebSocket incomplet ou trop long.') from error
    if len(raw)>8192: raise ValueError('En-tête WebSocket trop long.')
    lines=raw.decode('ascii').split('\r\n')
    values={}
    for line in lines[1:]:
        if not line: continue
        if ':' not in line: raise ValueError('En-tête invalide.')
        key,value=line.split(':',1); key=key.lower().strip()
        if key in values: raise ValueError('En-tête dupliqué.')
        values[key]=value.strip()
    if values.get('upgrade','').lower()!='websocket' or 'upgrade' not in [part.strip() for part in values.get('connection','').lower().split(',')]:
        raise ValueError('Mise à niveau WebSocket requise.')
    return lines[0],values


class WebSocket:
    def __init__(self,reader,writer,*,client=False,limit=MAX_STATE):
        self.reader=reader; self.writer=writer; self.client=client; self.limit=limit
        self.lock=asyncio.Lock(); self.closed=False; self.window=time.monotonic(); self.frames=0; self.last_received=time.monotonic()

    async def frame(self,opcode,data):
        if self.closed or self.writer.is_closing(): raise ConnectionError('Connexion fermée.')
        mask=secrets.token_bytes(4) if self.client else b''
        length=len(data); head=bytes([0x80|opcode])
        if length<126: head+=bytes([(0x80 if mask else 0)|length])
        elif length<65536: head+=bytes([(0x80 if mask else 0)|126])+struct.pack('!H',length)
        else: head+=bytes([(0x80 if mask else 0)|127])+struct.pack('!Q',length)
        if mask: data=bytes(value^mask[i%4] for i,value in enumerate(data))
        async with self.lock:
            self.writer.write(head+mask+data)
            await asyncio.wait_for(self.writer.drain(),3)

    async def send(self,text):
        data=text.encode('utf-8')
        if len(data)>MAX_STATE: raise ValueError('Message réseau trop volumineux.')
        await self.frame(1,data)

    async def recv(self):
        fragments=bytearray(); pending=False
        while True:
            first,second=await self.reader.readexactly(2)
            now=time.monotonic(); self.last_received=now
            if now-self.window>=1: self.window=now; self.frames=0
            self.frames+=1
            if self.frames>120: raise ValueError('Trop de trames réseau.')
            final=bool(first&128); opcode=first&15; masked=bool(second&128); size=second&127
            if first&112 or masked==self.client: raise ValueError('Trame WebSocket invalide.')
            if size==126: size=struct.unpack('!H',await self.reader.readexactly(2))[0]
            elif size==127: size=struct.unpack('!Q',await self.reader.readexactly(8))[0]
            if size>self.limit or len(fragments)+size>self.limit: raise ValueError('Message trop volumineux.')
            if opcode>=8 and (not final or size>125): raise ValueError('Trame de contrôle invalide.')
            mask=await self.reader.readexactly(4) if masked else b''
            data=await self.reader.readexactly(size)
            if mask: data=bytes(value^mask[i%4] for i,value in enumerate(data))
            if opcode==8: raise ConnectionError('Le correspondant a fermé la connexion.')
            if opcode==9: await self.frame(10,data); continue
            if opcode==10: continue
            if opcode==1:
                if pending: raise ValueError('Message fragmenté imbriqué.')
                fragments.extend(data); pending=not final
            elif opcode==0 and pending:
                fragments.extend(data); pending=not final
            else: raise ValueError('Seuls les messages texte sont acceptés.')
            if final: return bytes(fragments).decode('utf-8')

    async def close(self):
        if self.closed: return
        try: await self.frame(8,struct.pack('!H',1000))
        except (OSError,ConnectionError,asyncio.TimeoutError): pass
        self.closed=True; self.writer.close()
        try: await asyncio.wait_for(self.writer.wait_closed(),1)
        except (OSError,asyncio.TimeoutError): pass


async def accept_websocket(reader,writer):
    start,h=await headers(reader)
    if start!='GET /star-arena HTTP/1.1' or h.get('sec-websocket-version')!='13':
        raise ValueError('Protocole WebSocket incompatible.')
    key=h.get('sec-websocket-key','')
    if len(base64.b64decode(key,validate=True))!=16: raise ValueError('Clé WebSocket invalide.')
    writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept_key(key)+'\r\n\r\n').encode('ascii'))
    await asyncio.wait_for(writer.drain(),3)
    return WebSocket(reader,writer,limit=MAX_COMMAND)


async def connect_websocket(url):
    value=urlsplit(url)
    if value.scheme not in ('ws','wss') or value.username or value.password or value.query or value.fragment:
        raise ValueError('Adresse WebSocket invalide.')
    if not value.hostname or value.path not in ('','/star-arena'): raise ValueError('Adresse de salon invalide.')
    port=value.port or (443 if value.scheme=='wss' else 80)
    reader,writer=await asyncio.wait_for(asyncio.open_connection(value.hostname,port,ssl=True if value.scheme=='wss' else None,limit=MAX_STATE+1024),5)
    try:
        key=base64.b64encode(os.urandom(16)).decode('ascii')
        host_header='['+value.hostname+']' if ':' in value.hostname else value.hostname
        writer.write((f'GET /star-arena HTTP/1.1\r\nHost: {host_header}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode('ascii'))
        await asyncio.wait_for(writer.drain(),3)
        start,h=await headers(reader)
        if not start.startswith('HTTP/1.1 101 ') or h.get('sec-websocket-accept')!=accept_key(key):
            raise ValueError('Réponse WebSocket invalide.')
        return WebSocket(reader,writer,client=True)
    except BaseException:
        writer.close()
        await writer.wait_closed()
        raise
