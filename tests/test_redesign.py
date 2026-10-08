"""Behavior checks for the redesigned profile, rewards and fighter flow."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import time
import unittest
from unittest.mock import patch
import pygame as pg
from main import Game,ROOT
from state import Life
import pokemon_db

class RedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.game=Game(Path(cls.temp.name),save_path=Path(cls.temp.name)/'save.json',shell='/bin/sh')
        cls.game.profile_root=Path(cls.temp.name)/'profiles'
        cls.game.profile_root.mkdir()
    @classmethod
    def tearDownClass(cls):
        cls.game.terminal.close();pg.quit();cls.temp.cleanup()

    def test_empty_countdown_audio_is_rejected(self):
        import wave
        path = Path(self.temp.name) / 'empty.wav'
        with wave.open(str(path), 'wb') as audio:
            audio.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        self.assertFalse(Game.valid_countdown_audio(path))
        with wave.open(str(path), 'wb') as audio:
            audio.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
            audio.writeframes(b'\0\0' * 2205)
        self.assertTrue(Game.valid_countdown_audio(path))

    def test_battle_intro_tts_weather_and_environment_stats(self):
        g=self.game;g.life=Life(language='en',pokemon_party=[7],pokemon_active=[7]);g.begin_pokemon_battle(4);b=g.battle
        self.assertIn(b['battle_weather'],('Cerah','Berawan','Hujan','Salju','Badai'))
        self.assertIn(b['arena_style'],('meadow','water','cave','sky'))
        # Lock one known pairing so both buffs and debuffs are deterministic.
        b['arena_style']='water';b['battle_weather']='Hujan';g.prepare_battle()
        player_mod=b['environment_mods'][str(b['player_id'])]
        enemy_mod=b['environment_mods'][str(b['wild_id'])]
        self.assertGreater(player_mod['attack'],0)  # Squirtle benefits from rain/water.
        self.assertLess(enemy_mod['attack'],0)  # Charmander is weakened by rain/water.
        g.draw()
        b['intro']['step']='enemy';g.draw()  # The alternating second reveal uses its own modifiers.
        # Play the formerly crash-prone cue only after validating its WAV frames.
        audio_root=ROOT/'.openrpg/countdown-tts'
        for cue,filename in (('READY','en-ready-complete.wav'),('3','en-3.wav'),('2','en-2.wav'),('1','en-1.wav')):
            path=audio_root/filename
            self.assertTrue(Game.valid_countdown_audio(path))
            g.countdown_tts_sounds['en',cue]=pg.mixer.Sound(str(path))
        b['intro']={'step':'READY','index':2,'timer':0,'cue_requested':False}
        for _ in range(900):
            g.update_battle(1/60)
            if not b.get('intro'):break
            time.sleep(.004)
        self.assertIsNone(b.get('intro'))

    def test_01_new_profile_keyboard_and_terminal(self):
        g=self.game;g.draw()
        g.handle(pg.event.Event(pg.KEYDOWN,key=pg.K_RETURN,mod=0))
        self.assertEqual(g.mode,'profiles')
        path=Path(self.temp.name)/'slot-1.json'
        g.select_profile(path,None);g.draw()
        g.handle(pg.event.Event(pg.TEXTINPUT,text='Aruna'))
        g.handle(pg.event.Event(pg.KEYDOWN,key=pg.K_RETURN,mod=0));g.draw()
        self.assertEqual(g.wizard['step'],1)
        g.select_gender('female');g.next_setup();g.wizard['style']=8;g.draw()
        g.next_setup();g.draw();g.next_setup();g.draw()
        self.assertEqual(g.life.player_name,'Aruna')
        self.assertEqual(g.life.character,8)
        self.assertTrue(3<=g.pokemon_level(g.life.pokemon_active[0])<=5)
        self.assertTrue(path.exists())
        g.open_phone();g.draw()
        self.assertEqual(g.mode,'terminal')
        g.terminal.send(b"printf 'RPG_TERMINAL_OK\\n'\n")
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            g.terminal.poll()
            if any('RPG_TERMINAL_OK' in line for line in g.terminal.screen.display):break
            time.sleep(.02)
        self.assertTrue(any('RPG_TERMINAL_OK' in line for line in g.terminal.screen.display))
        g.back();self.assertTrue(g.terminal.running)

    def test_02_quest_claim_and_rollover(self):
        l=Life();q=l.daily_quests[0];old=l.money
        l.record_daily_quest(q['action'],q['target'])
        self.assertEqual(l.money,old)
        l.advance_time(1440)
        self.assertEqual(len(l.quest_archive),1)
        q=l.quest_archive[0]
        self.assertEqual(l.claim_quest(q),q['reward'])
        self.assertEqual(l.claim_quest(q),0)
        for q in l.daily_quests:q['progress']=q['target'];l.claim_quest(q)
        self.assertTrue(l.claim_daily_bonus());self.assertFalse(l.claim_daily_bonus())
        self.assertEqual(l.gacha_tickets,1)

    def test_03_collection_and_ball_capacity(self):
        l=Life(pokemon_party=list(range(1,30)),pokemon_caught=list(range(1,31)),pokemon_active=[1,2,3])
        path=Path(self.temp.name)/'collection.json';l.save(path)
        loaded=Life.load(path)
        self.assertEqual(len(loaded.pokemon_party),29) # Sold/historical species must not return.
        l.bag['Pokeball']=10;money=l.money;l.trade('Pokeball',True)
        self.assertEqual(l.money,money);self.assertEqual(l.bag['Pokeball'],10)

    def test_04_center_heal_and_team_swap(self):
        g=self.game;g.life=Life(pokemon_party=[1,4,7,25],pokemon_active=[1,4,7]);g.life.scene='reserve';g.life.x=160;g.life.y=690
        g.open_pokemon_center();g.draw();g.collection_select(3);g.assign_slot(1)
        self.assertEqual(g.life.pokemon_active,[1,25,7])
        for i in g.life.pokemon_active:g.life.pokemon_health[str(i)]=1
        cost=g.center_cost();money=g.life.money
        self.assertTrue(5<=cost<=20);g.heal_pokemon_party()
        self.assertEqual(g.life.money,money-cost)
        self.assertEqual(g.center_cost(),0)
        g.draw();pg.image.save(g.canvas,str(ROOT/'artifacts/redesign-center.png'))

    def test_05_combat_gravity_projectiles_and_ai(self):
        g=self.game;g.life=Life();g.begin_pokemon_battle(4);b=g.battle;b['intro']=None;b['platforms']=[]
        for ident in (1,4):
            path=ROOT/f'.openrpg/pokedex/{ident}.png'
            if path.exists():g.poke_surfaces[ident]=pg.image.load(path).convert_alpha()
        y=[]
        for n in range(120):
            g.physics('player',1/60,0,n==0,n<15)
            y.append(b['player_y'])
        self.assertLess(min(y),-60);self.assertEqual(y[-1],0)
        b['enemy_x']=b['player_x']+400;hp=b['wild_hp'];g.pokemon_attack()
        for n in range(60):g.update_shots(1/60)
        self.assertEqual(b['wild_hp'],hp)
        b['player_cooldown']=0;g.pokemon_type_attack(0)
        self.assertTrue(b['shots'])
        self.assertEqual(b['wild_hp'],hp) # Damage must wait for impact.
        for n in range(90):g.update_shots(1/60)
        self.assertLess(b['wild_hp'],hp)
        g.draw();pg.image.save(g.canvas,str(ROOT/'artifacts/redesign-battle.png'))
        g.begin_pokemon_battle(4);b=g.battle;b['intro']=None;b['platforms']=[]
        b['player_hp']=b['player_max']=1000
        hp=b['player_hp'];g.pokemon_rng.seed(10)
        for n in range(900):g.update_battle(1/60)
        self.assertLess(b['player_hp'],hp)
        self.assertAlmostEqual(b['time_left'],45,places=2)
        b['super_meter']=100;b['player_cooldown']=0;g.pokemon_ultimate();g.draw()
        pg.image.save(g.canvas,str(ROOT/'artifacts/redesign-ultimate.png'))
        self.assertIsNotNone(b.get('ultimate_cutin'))

    def test_06_real_learnsets(self):
        for ident in (1,4,7,25,132,149,202,235,360,771,789,790,1025):
            moves=pokemon_db.loadout(ident);learned={m['move']['name'] for m in pokemon_db.detail(ident)['moves']}
            self.assertEqual(len(moves),3)
            self.assertTrue(all(m['name'] in learned for m in moves))
        self.assertEqual(pokemon_db.effectiveness('electric',('ground',)),0)

    def test_07_invitation_roll_once_and_decline(self):
        g=self.game;g.life=Life();g.mode='game';g.fishing=None;g.battle=None;g.encounter_grace=0
        actor={'id':'test','name':'Test NPC','scene':'outdoors','x':g.life.x+60,'y':g.life.y,'team':[4],'level':5,'cooldown':0}
        g.route_trainers=[actor];g.reserve_trainers=[]
        with patch.object(g.pokemon_rng,'random',return_value=.8) as roll:
            for _ in range(60):g.update_challenges(1/60)
            self.assertEqual(roll.call_count,1)
            self.assertEqual(g.mode,'game')
        actor.pop('challenge_roll');g.encounter_grace=0
        with patch.object(g.pokemon_rng,'random',return_value=.1):g.update_challenges(1/60)
        self.assertEqual(g.mode,'invitation');g.decline_invitation()
        self.assertEqual(g.mode,'game');self.assertGreater(g.encounter_grace,0)

if __name__=='__main__':unittest.main()
