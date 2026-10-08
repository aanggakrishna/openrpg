"""Headless multiplayer service and combat contract checks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import random
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from online_server import World,make_server
from online_combat import Battle,creature

class OnlineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.world=World(str(Path(self.temp.name)/'server.db'))
        self.a=self.world.connect(dict(name='Alice',roster={'1':8,'4':9},active=[1],money=100))
        self.b=self.world.connect(dict(name='Bob',roster={'7':8,'25':9},active=[7],money=80))
        self.u=self.a['me'];self.v=self.b['me']
    def tearDown(self):self.world.db.close();self.temp.cleanup()
    def test_chat_presence_and_pvp(self):
        self.world.action(self.u,dict(action='chat',text='Hello'))
        self.assertEqual(self.world.snapshot(self.v)['chat'][0]['text'],'Hello')
        self.world.action(self.u,dict(action='pvp',target=self.v['id']))
        offer=next(iter(self.world.offers));self.world.action(self.v,dict(action='reply',offer=offer,accept=True))
        battle=next(iter(self.world.matches.values()))['battle'];battle.intro=0
        a,b=battle.fighters.values();b['x']=a['x']+55
        before=b['team'][0]['hp'];battle.control(self.u['id'],{'a':True});battle.tick(.05)
        self.assertLess(b['team'][0]['hp'],before)
        self.world.action(self.u,dict(action='leave_battle'));self.world.tick(.05)
        self.assertEqual(battle.result['winner'],1)
    def test_atomic_trade_and_replay(self):
        self.world.action(self.u,dict(action='trade',target=self.v['id'],give=4,want=25,price=15))
        offer=next(iter(self.world.offers));self.world.action(self.v,dict(action='reply',offer=offer,accept=True))
        self.assertEqual((self.u['money'],self.v['money']),(115,65))
        self.assertIn('4',self.v['roster']);self.assertNotIn('4',self.u['roster']);self.assertIn('25',self.u['roster'])
        with self.assertRaises(ValueError):self.world.action(self.v,dict(action='reply',offer=offer,accept=True))
        again=self.world.connect(dict(token=self.a['token']))
        self.assertEqual(again['me']['money'],115)
    def test_dungeon_lock_waves_and_progress(self):
        with self.assertRaises(ValueError):self.world.action(self.u,dict(action='room',room='dungeon:2'))
        self.world.action(self.u,dict(action='room',room='dungeon:1'));self.world.action(self.u,dict(action='ready'));self.world.action(self.u,dict(action='raid'))
        battle=next(iter(self.world.matches.values()))['battle']
        maximum=0
        for stage in range(4):
            self.assertEqual(battle.stage,stage);battle.intro=0
            for uid,f in battle.fighters.items():
                if uid.startswith('bot:'):
                    c=f['team'][0]
                    if stage<3:maximum=max(maximum,c['maximum']);self.assertLessEqual(c['level'],9)
                    else:self.assertEqual(c['level'],10);self.assertGreater(c['maximum'],maximum)
                    c['hp']=0
            self.world.tick(.05)
        self.assertEqual(self.u['unlocked'],2);self.assertEqual(self.u['money'],150)
    def test_real_http_two_clients(self):
        server=make_server('127.0.0.1',0,self.world);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            for account in (self.a,self.b):
                req=Request(url+'/action',data=json.dumps({'action':'poll'}).encode(),headers={'Authorization':'Bearer '+account['token']})
                with urlopen(req) as r:data=json.load(r)
                self.assertEqual(len(data['players']),2)
        finally:server.shutdown();server.server_close()
    def test_melee_range_gravity_and_deadline(self):
        battle=Battle({'a':[creature(1,5)],'b':[creature(7,5)]},rng=random.Random(2));battle.intro=0
        before=battle.fighters['b']['team'][0]['hp'];battle.attack('a',0);self.assertEqual(battle.fighters['b']['team'][0]['hp'],before)
        f=battle.fighters['a'];f['y']=350;f['vy']=0
        for _ in range(80):battle.tick(.05)
        self.assertEqual(f['y'],570)
        battle.remaining=.02;battle.tick(.05);self.assertIsNotNone(battle.result)

    def test_dungeon_enemies_attack_one_at_a_time(self):
        battle=Battle({'a':[creature(1,5)]},tier=1,rng=random.Random(4));battle.intro=0
        bots=[uid for uid in battle.fighters if uid.startswith('bot:')]
        self.assertEqual(battle.active_bots,['bot:0'])
        # Repeated ticks cannot produce attacks from waiting bots.
        for _ in range(30):battle.tick(.05)
        self.assertEqual(battle.active_bots,['bot:0'])
        battle.hit('a','bot:0',999)
        self.assertEqual(battle.active_bots,['bot:1'])

    def test_dungeon_attacker_count_and_boss_drop(self):
        battle=Battle({'a':[creature(1,90)]},tier=1,rng=random.Random(8));battle.intro=0
        self.assertEqual(len(battle.active_bots),1)
        battle.stage=1;battle.wave();self.assertEqual(len(battle.active_bots),2)
        battle.stage=2;battle.wave();self.assertEqual(len(battle.active_bots),3)
        battle.stage=3;battle.wave();battle.intro=0;self.assertEqual(len(battle.active_bots),1)
        for uid in list(battle.fighters):
            if uid.startswith('bot:'):battle.fighters[uid]['team'][0]['hp']=0
        battle.tick(.01)
        self.assertIsNotNone(battle.result)
        self.assertTrue(battle.result['drops'])

if __name__=='__main__':unittest.main()
