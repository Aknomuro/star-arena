"""Réseau V0.4 : loopback réel et logique d'autorité, sans Pygame."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from star_arena.network.authority import Authority
from star_arena.network.runtime import HostServer, Client
from star_arena.network.protocol import loads, dumps, PROTOCOL
from star_arena.network.transport import connect_websocket
from star_arena.persistence import decode


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder=TemporaryDirectory(prefix='arena-net-',dir=Path(__file__).parent)
        self.path=Path(self.folder.name)/'multiplayer.json'
        self.authority=Authority('Test local','Hôte',15)
        self.server=HostServer(self.authority,self.path)
        await self.server.start('127.0.0.1',0)
        self.url=f'ws://127.0.0.1:{self.server.port}/star-arena'
        self.host=await Client().connect(self.url,'Hôte',reconnect=self.authority.host_token)
        self.guest=await Client().connect(self.url,'Invité',invite=self.authority.invite)
        self.clients=[self.host,self.guest]
        await self.wait_for(lambda:self.host.latest and len(self.host.latest['participants'])==2)

    async def asyncTearDown(self):
        for client in self.clients: await client.close()
        await self.server.close()
        self.folder.cleanup()

    async def wait_for(self,predicate):
        async with asyncio.timeout(3):
            while not predicate(): await asyncio.sleep(.01)

    async def start_game(self):
        response=await self.host.command('start')
        self.assertTrue(response['ok'],response['message'])
        await self.wait_for(lambda:self.guest.latest and self.guest.latest['started'])

    async def test_real_loopback_lobby_factions_and_start_authority(self):
        self.assertNotEqual(self.host.participant,self.guest.participant)
        response=await self.guest.command('faction',{'faction':0})
        self.assertFalse(response['ok'])
        self.assertFalse((await self.guest.command('start'))['ok'])
        await self.start_game()
        data=self.guest.latest
        self.assertEqual(len(data['participants']),2)
        self.assertEqual(len(decode(data['campaign']).systems),15)
        raw=dumps(data)
        self.assertNotIn(self.host.reconnect,raw)
        self.assertNotIn(self.guest.reconnect,raw)
        self.assertNotIn(self.authority.invite,raw)
        self.assertEqual(self.authority.simulation.human_factions,{0,1})

    async def test_move_resources_and_build_commands_are_synchronized(self):
        await self.start_game()
        c=self.authority.campaign
        own=c.fleets[2]; destination=c.neighbors(own.system_id)[0]
        reply=await self.guest.command('move',{'fleet':2,'destination':destination})
        self.assertTrue(reply['ok'],reply['message'])
        await self.wait_for(lambda:any(f['id']==2 and f['travel'] for f in self.guest.latest['campaign']['fleets']))
        self.assertIsNotNone(own.travel)
        stock=c.resources[1].credits
        capital=next(s.id for s in c.systems.values() if s.capital and s.owner==1)
        reply=await self.guest.command('yard',{'system':capital})
        self.assertTrue(reply['ok'],reply['message'])
        self.assertLessEqual(c.resources[1].credits,stock-199)
        self.assertEqual(c.systems[capital].shipyard,1)
        self.assertTrue((await self.guest.command('yard',{'system':capital,'model':'fighter'}))['ok'])
        await self.wait_for(lambda:self.guest.latest['campaign']['systems'][capital]['queue'])
        self.assertEqual(self.guest.latest['campaign']['resources']['1']['credits'],c.resources[1].credits)

    async def test_enemy_commands_admin_and_owner_injection_rejected(self):
        await self.start_game()
        before=len(self.authority.campaign.fleets[1].ships)
        self.assertFalse((await self.guest.command('move',{'fleet':1,'destination':1}))['ok'])
        self.assertFalse((await self.guest.command('yard',{'system':0}))['ok'])
        self.assertFalse((await self.guest.command('admin:resources'))['ok'])
        self.assertFalse((await self.guest.command('move',{'fleet':2,'destination':1,'owner':0}))['ok'])
        self.assertEqual(len(self.authority.campaign.fleets[1].ships),before)

    async def test_disconnect_reconnect_same_seat_and_prevent_takeover(self):
        await self.start_game()
        uid=self.guest.participant; token=self.guest.reconnect
        with self.assertRaises(ValueError):
            await Client().connect(self.url,'Usurpateur',reconnect=token)
        await self.guest.close()
        await self.wait_for(lambda:not self.authority.members[uid].online)
        before=self.authority.campaign.time
        await asyncio.sleep(.23)
        self.assertEqual(self.authority.campaign.time,before)
        with self.assertRaises(ValueError):
            await Client().connect(self.url,'Usurpateur',reconnect='invalide')
        client=await Client().connect(self.url,'Retour',reconnect=token)
        self.clients.append(client)
        self.assertEqual(client.participant,uid)
        await self.wait_for(lambda:self.authority.campaign.time>before)

    async def test_host_save_load_and_reconnect_guest(self):
        await self.start_game()
        self.assertFalse((await self.guest.command('save'))['ok'])
        self.assertTrue((await self.host.command('save'))['ok'])
        loaded=Authority.load(self.path)
        self.assertEqual(set(loaded.members),set(self.authority.members))
        self.assertEqual(asdict(loaded.campaign),asdict(decode(json.loads(self.path.read_text(encoding='utf-8'))['campaign'])))
        self.assertFalse(any(m.online for m in loaded.members.values()))
        restored=loaded.members[self.guest.participant]
        member,_=loaded.join('Retour',reconnect=self.guest.reconnect)
        self.assertEqual(member.id,restored.id)

    async def test_invalid_auth_and_json_duplicate_refused(self):
        with self.assertRaises(ValueError):
            await Client().connect(self.url,'Indésirable',invite='faux')
        with self.assertRaises(ValueError): loads('{"type":"x","type":"y"}')
        socket=await connect_websocket(self.url)
        await socket.send(dumps({'type':'hello','protocol':999,'build':'0.4.0','name':'X','invite':self.authority.invite,'reconnect':''}))
        result=loads(await socket.recv())
        self.assertEqual(result['type'],'error')
        await socket.close()

    async def test_third_player_unique_faction_and_full_lobby(self):
        third=await Client().connect(self.url,'Troisième',invite=self.authority.invite)
        self.clients.append(third)
        await self.wait_for(lambda:self.host.latest and len(self.host.latest['participants'])==3)
        self.assertEqual({p['faction'] for p in self.host.latest['participants']},{0,1,2})
        with self.assertRaises(ValueError): await Client().connect(self.url,'Quatrième',invite=self.authority.invite)
        await self.start_game()
        self.assertEqual(self.authority.simulation.human_factions,{0,1,2})

    async def test_host_resolves_battle_once_for_both_clients(self):
        from star_arena.systems.combat import create_engagement
        await self.start_game(); await self.host.command('pause')
        c=self.authority.campaign; target=c.neighbors(0)[0]
        c.fleets[1].system_id=target; c.fleets[2].system_id=target; c.systems[target].owner=1
        create_engagement(c,c.fleets[1],0,1)
        self.authority.revision+=1; self.server.broadcast()
        initial={u.id for f in c.fleets.values() for u in f.ships}
        reply=await self.guest.command('auto_battle')
        self.assertTrue(reply['ok'],reply['message'])
        await self.wait_for(lambda:self.host.latest['campaign']['reports'] and self.guest.latest['campaign']['reports'])
        self.assertEqual(self.host.latest['campaign']['reports'],self.guest.latest['campaign']['reports'])
        self.assertIsNone(c.pending)
        self.assertTrue(c.reports[0].automatic)
        after={u.id for f in c.fleets.values() for u in f.ships}
        self.assertTrue(after<=initial)
        self.assertFalse((await self.guest.command('auto_battle'))['ok'])
        self.assertEqual(len(c.reports),1)

    async def test_human_factions_are_not_driven_by_ai(self):
        await self.start_game()
        for _ in range(100): self.authority.advance(.1)
        c=self.authority.campaign
        self.assertIsNone(c.fleets[1].travel); self.assertIsNone(c.fleets[2].travel)
        self.assertTrue(all(s.shipyard==0 and all(not p.jobs for p in s.planets) for s in c.systems.values() if s.owner in (0,1)))

    async def test_reinvite_invalidates_old_personal_key(self):
        uid=self.guest.participant; old=self.guest.reconnect
        await self.guest.close(); await self.wait_for(lambda:not self.authority.members[uid].online)
        result=await self.host.command('reinvite',{'participant':uid})
        self.assertTrue(result['ok'])
        with self.assertRaises(ValueError): await Client().connect(self.url,'Ancien',reconnect=old)
        client=await Client().connect(self.url,'Invité',reconnect=result['reconnect'])
        self.clients.append(client); self.assertEqual(client.participant,uid)

    async def test_rate_limit_disconnects_spam_without_mutating_campaign(self):
        for _ in range(31): await self.guest.command('not_a_command')
        await self.wait_for(lambda:not self.guest.connected)
        self.assertIsNone(self.authority.campaign)
        self.assertIn('30 commandes',self.guest.error)

    async def test_oversized_hello_rejected_before_claiming_seat(self):
        socket=await connect_websocket(self.url)
        await socket.send('x'*20000)
        try:
            reply=loads(await socket.recv())
            self.assertEqual(reply['type'],'error')
        except (OSError,ConnectionError,asyncio.IncompleteReadError): pass
        await socket.close()
        self.assertEqual(len(self.authority.members),2)

    async def test_planet_station_construction_is_authoritative_and_in_snapshot(self):
        await self.start_game()
        c=self.authority.campaign; c.next_ai_at=1e9
        system=next(s for s in c.systems.values() if s.capital and s.owner==1)
        planet=system.planets[0]; credits=c.resources[1].credits
        reply=await self.guest.command('building',{'system':system.id,'planet':planet.id,'kind':'station'})
        self.assertTrue(reply['ok'],reply['message'])
        self.assertLess(c.resources[1].credits,credits)
        self.assertFalse(planet.orbitals)
        for _ in range(311): self.authority.advance(.1)
        self.assertTrue(planet.orbitals)
        self.server.broadcast()
        await self.wait_for(lambda: self.guest.latest['campaign']['systems'][system.id]['planets'][0]['orbitals'])
        unit=self.guest.latest['campaign']['systems'][system.id]['planets'][0]['orbitals'][0]['unit']
        self.assertEqual(unit['status'],'orbital')
        self.assertGreater(unit['hull'],0)

    async def test_non_host_human_battle_waits_for_authorized_resolution(self):
        from star_arena.systems.economy import NoEconomy
        await self.start_game()
        c=self.authority.campaign; c.next_ai_at=1e9
        self.authority.simulation.economy=NoEconomy()
        origin=c.fleets[2].system_id; target=c.neighbors(origin)[0]
        c.systems[target].owner=2; c.fleets[3].system_id=target
        self.assertEqual(self.authority.simulation.order_move(2,target,1),'')
        for _ in range(1000):
            self.authority.advance(.1)
            if c.pending: break
        self.assertIsNotNone(c.pending)
        self.assertEqual((c.pending.attacker,c.pending.defender),(1,2))
        self.assertFalse(c.reports)
        self.assertTrue((await self.guest.command('auto_battle'))['ok'])
        self.assertIsNone(c.pending)

    async def test_loaded_server_resumes_same_participants_over_websocket(self):
        await self.start_game(); await self.host.command('pause')
        self.assertTrue((await self.host.command('save'))['ok'])
        old_id=self.guest.participant; guest_token=self.guest.reconnect
        saved=json.loads(self.path.read_text(encoding='utf-8'))['campaign']
        await self.server.close()
        self.authority=Authority.load(self.path)
        self.server=HostServer(self.authority,self.path)
        await self.server.start('127.0.0.1',0)
        url=f'ws://127.0.0.1:{self.server.port}/star-arena'
        host=await Client().connect(url,'Hôte',reconnect=self.authority.host_token)
        guest=await Client().connect(url,'Retour',reconnect=guest_token)
        self.clients.extend((host,guest))
        self.assertEqual(guest.participant,old_id)
        self.assertTrue((await host.command('start'))['ok'])
        await self.wait_for(lambda:guest.latest and guest.latest['started'])
        self.assertEqual(guest.latest['campaign']['resources'],saved['resources'])
        self.assertEqual(guest.latest['campaign']['systems'],saved['systems'])

    async def test_silent_connection_is_expired_without_waiting_real_timeout(self):
        import time
        peer=next(p for p in self.server.peers if p.uid==self.guest.participant)
        peer.transport.last_received=time.monotonic()-20
        await self.wait_for(lambda:not self.authority.members[self.guest.participant].online)
        await self.wait_for(lambda:not self.guest.connected)

    async def test_host_shutdown_informs_clients(self):
        await self.server.close()
        await self.wait_for(lambda:not self.guest.connected)
        self.assertIn('hôte',self.guest.error)


class AuthorityAndReplicaTests(unittest.TestCase):
    def make_started(self):
        a=Authority(size=15); guest,token=a.join('Invité',a.invite)
        a.command(a.host_id,1,'start',{})
        return a,guest

    def test_purchase_and_replay_cannot_double_spend(self):
        a,guest=self.make_started(); c=a.campaign
        capital=next(s.id for s in c.systems.values() if s.owner==guest.faction)
        c.resources[guest.faction].credits=200; c.resources[guest.faction].minerals=100
        a.command(guest.id,1,'yard',{'system':capital})
        self.assertEqual(c.resources[guest.faction].credits,0)
        with self.assertRaises(ValueError): a.command(guest.id,1,'yard',{'system':capital})
        with self.assertRaises(ValueError): a.command(guest.id,2,'yard',{'system':capital})
        self.assertEqual(c.systems[capital].shipyard,1)
        self.assertEqual(c.resources[guest.faction].minerals,0)

    def test_replica_never_advances_or_mutates_shared_world(self):
        from types import SimpleNamespace
        from star_arena.app import Application
        a,guest=self.make_started()
        app=Application(None,SimpleNamespace(buttons=[],fleet_points={}),Path('unused.json'))
        app.mode='mp_lobby'
        app.mp.client=SimpleNamespace(participant=guest.id,error='',connected=True,latest=loads(dumps(a.snapshot())))
        app.mp.poll()
        before=asdict(app.simulation.campaign); authoritative=asdict(a.campaign)
        app.advance_campaign(.4)
        with self.assertRaises(RuntimeError): app.simulation.advance(.4)
        self.assertEqual(asdict(app.simulation.campaign),before)
        sent=[]; app.mp.send=lambda name,args=None: sent.append((name,args))
        app.action('yard'); app.action('admin:resources'); app.action('start')
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0][0],'yard')
        self.assertEqual(asdict(a.campaign),authoritative)
        self.assertEqual(asdict(app.simulation.campaign),before)
        self.assertIsNone(app.battle)

    def test_custom_galaxy_settings_and_loaded_geometry_are_preserved(self):
        a=Authority(size=30,seed=123)
        a.join('Invité',a.invite)
        a.command(a.host_id,1,'start',{})
        self.assertEqual((len(a.campaign.systems),a.campaign.seed),(30,123))
        self.assertEqual(a.snapshot()['seed'],123)
        with TemporaryDirectory(prefix='arena-net-seed-',dir=Path(__file__).parent) as folder:
            path=Path(folder)/'m.json'; a.save(path); loaded=Authority.load(path)
            loaded.join('Hôte',reconnect=loaded.host_token)
            with self.assertRaises(ValueError): loaded.command(loaded.host_id,2,'size',{'size':60})
            self.assertEqual((len(loaded.campaign.systems),loaded.seed),(30,123))

    def test_snapshot_validation_rejects_bad_participants_and_flags(self):
        from star_arena.network.protocol import validate_state
        a,guest=self.make_started(); state=a.snapshot()
        state['participants'][1]['faction']=0
        with self.assertRaises(ValueError): validate_state(state,a.session_id)
        state=a.snapshot(); state['paused']='yes'
        with self.assertRaises(ValueError): validate_state(state,a.session_id)
        with self.assertRaises(ValueError): loads('{"value":NaN}')

    def test_slow_peer_snapshots_are_coalesced_and_reliable_queue_bounded(self):
        from star_arena.network.runtime import Peer
        peer=Peer(None)
        for i in range(100): peer.enqueue(dumps({'type':'state','revision':i}))
        self.assertEqual(loads(peer.state)['revision'],99)
        self.assertEqual(len(peer.messages),0)
        for i in range(16): peer.enqueue({'type':'ack','sequence':i})
        with self.assertRaises(ValueError): peer.enqueue({'type':'ack','sequence':17})


class TransportWireTests(unittest.IsolatedAsyncioTestCase):
    async def test_known_handshake_and_masked_hello_vector(self):
        from star_arena.network.transport import accept_key, WebSocket
        self.assertEqual(accept_key('dGhlIHNhbXBsZSBub25jZQ=='),'s3pPLMBiTxaQ9kYGzzhZRbK+xOo=')
        reader=asyncio.StreamReader()
        reader.feed_data(bytes.fromhex('81 85 37 fa 21 3d 7f 9f 4d 51 58'))
        socket=WebSocket(reader,None)
        self.assertEqual(await socket.recv(),'Hello')

    async def test_server_rejects_unmasked_client_frame(self):
        from star_arena.network.transport import WebSocket
        reader=asyncio.StreamReader(); reader.feed_data(b'\x81\x02hi')
        with self.assertRaises(ValueError): await WebSocket(reader,None).recv()
