"""Render online screens and exercise keyboard/lazy-area integration."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import unittest
import pygame as pg
from main import Game,RARE_POKEMON_IDS
from art import RESERVE_ZONES
from online_server import World
from online_combat import Battle,creature
import pokemon_db

class OnlineUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();root=Path(cls.temp.name)
        cls.game=Game(root,save_path=root/'save.json',shell='/bin/sh');cls.game.playing=True
        cls.world=World(':memory:')
        cls.a=cls.world.connect(dict(name='Alice',roster={'1':5,'4':6},active=[1],money=100))
        cls.b=cls.world.connect(dict(name='Bob',roster={'7':5},active=[7],money=100))
    @classmethod
    def tearDownClass(cls):
        cls.game.terminal.close();pg.quit();cls.world.db.close();cls.temp.cleanup()
    def test_render_online_screens(self):
        g=self.game;g.online_state=self.world.snapshot(self.a['me']);g.trade_target=self.b['me']['id']
        for mode in ('online_connect','online_room','online_center','online_trade'):
            g.set_mode(mode);g.draw();self.assertGreater(len(g.buttons),0)
        battle=Battle({self.a['me']['id']:[creature(1,5)],self.b['me']['id']:[creature(7,5)]})
        battle.intro=0;battle.attack(self.a['me']['id'],1)
        g.online_state['battle']=battle.snapshot();g.set_mode('online_room');g.draw()
    def test_text_input_does_not_trigger_actions(self):
        g=self.game;g.set_mode('online_connect');g.online_edit('url','')
        for c in 'http://my-server:8765':
            g.handle(pg.event.Event(pg.TEXTINPUT,text=c))
        self.assertEqual(g.mode,'online_connect')
        g.handle(pg.event.Event(pg.KEYDOWN,key=pg.K_RETURN));self.assertEqual(g.online_url,'http://my-server:8765')
    def test_keyboard_buttons(self):
        g=self.game;g.set_mode('online_connect');g.draw()
        g.handle(pg.event.Event(pg.KEYDOWN,key=pg.K_DOWN));self.assertEqual(g.nav_index,1)
        g.handle(pg.event.Event(pg.KEYDOWN,key=pg.K_RETURN));self.assertEqual(g.online_input,'code')
        g.handle(pg.event.Event(pg.KEYDOWN,key=pg.K_ESCAPE))
    def test_all_species_have_habitats_and_only_current_area_spawns(self):
        catalog=pokemon_db.catalog();ids={int(e['id']) for e in catalog}
        self.assertEqual(ids,set(range(1,1026)))
        pools=[set() for _ in RESERVE_ZONES]
        for ident in ids:pools[(12+ident%4) if ident in RARE_POKEMON_IDS else (ident*7+3)%16].add(ident)
        self.assertEqual(set.union(*pools),ids)
        g=self.game;g.life.scene='reserve'
        for index,zone in enumerate(RESERVE_ZONES):
            g.life.x=zone['x']+640;g.life.y=zone['y']+800;g.spawn_map_pokemon()
            self.assertLessEqual(len(g.wild_pokemon),13)
            self.assertTrue(all(p.get('zone',0)==index for p in g.wild_pokemon))
            self.assertEqual(len(g.reserve_trainers),1)

if __name__=='__main__':unittest.main()
