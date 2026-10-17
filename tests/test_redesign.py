"""Behavior checks for the redesigned profile, rewards and fighter flow."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import time
import math
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
        # Gender is intentionally not part of profile setup. Choose the default
        # trainer portrait, set the world sprite, and complete the partner reveal.
        g.next_setup();self.assertEqual(g.wizard['step'],2)
        g.wizard['style']=8;g.draw()
        g.next_setup();self.assertEqual(g.mode,'starter_reveal')
        g.update(5.3);self.assertEqual(g.mode,'setup')
        g.next_setup();g.draw()
        self.assertEqual(g.life.player_name,'Aruna')
        self.assertEqual(g.life.character,8)
        self.assertEqual(g.life.gender,'unspecified')
        self.assertTrue(1<=g.pokemon_level(g.life.pokemon_active[0])<=3)
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

    def test_service_rooms_are_walkable_and_return_to_their_door(self):
        g=self.game;g.life=Life(scene='market',x=700,y=610);g.mode='game'
        g.open_service_interior('restaurant')
        self.assertEqual((g.life.scene,g.mode),('restaurant','game'))
        self.assertEqual((g.life.service_return_scene,g.life.service_return_x,g.life.service_return_y),
                         ('market',700,610))
        g.draw()
        self.assertNotEqual(g.canvas.get_at((640,400)),pg.Color('black'))
        save_path=Path(self.temp.name)/'service-room.json';g.life.save(save_path)
        loaded=Life.load(save_path)
        self.assertEqual((loaded.scene,loaded.service_return_scene),('restaurant','market'))
        npc=next(row for row in g.stations() if row[0]=='service_npc')
        g.life.x,g.life.y=npc[1],npc[2]
        g.interact_selected()
        self.assertEqual(g.mode,'service_interior')
        g.draw();self.assertGreater(len(g.buttons),0)
        g.back();self.assertEqual((g.life.scene,g.mode),('restaurant','game'))
        door=next(row for row in g.stations() if row[0]=='service_exit')
        g.life.x,g.life.y=door[1],door[2]
        g.interact_selected()
        self.assertEqual((g.life.scene,g.mode),("market","game"))
        self.assertLess(math.hypot(g.life.x-700,g.life.y-610),40)

    def test_background_music_reuses_one_stream_and_stops_on_track_change(self):
        g=self.game;g._music_key=None
        with patch('main.pg.mixer.get_init',return_value=True), patch('main.pg.mixer.music') as music:
            self.assertTrue(g.start_background_music(Path('meadow.ogg'),'outdoors:meadow',.28))
            self.assertFalse(g.start_background_music(Path('meadow.ogg'),'outdoors:meadow',.28))
            self.assertTrue(g.start_background_music(Path('center.ogg'),'center',.28,fade_ms=650))
            self.assertEqual(music.stop.call_count,2)
            self.assertEqual(music.load.call_count,2)
            self.assertEqual(music.play.call_count,2)

    def test_pokemon_center_pokeball_purchase_and_capacity(self):
        g=self.game;g.life=Life(money=200);g.life.bag['Pokeball']=5
        g.buy_center_pokeballs()
        self.assertEqual(g.life.bag['Pokeball'],10)
        self.assertEqual(g.life.money,140)
        # Partial purchase fits the remaining capacity instead of rejecting it.
        g.life.bag['Pokeball']=8;g.buy_center_pokeballs()
        self.assertEqual(g.life.bag['Pokeball'],10)
        self.assertEqual(g.life.money,116)
        g.buy_center_pokeballs()
        self.assertEqual(g.life.bag['Pokeball'],10)
        self.assertEqual(g.life.money,116)
        g.life.bag['Pokeball']=5;g.life.money=10;g.buy_center_pokeballs()
        self.assertEqual(g.life.bag['Pokeball'],5)
        self.assertEqual(g.life.money,10)

    def test_service_animation_defers_meal_until_table_scene_finishes(self):
        g=self.game;g.life=Life(scene='restaurant',money=80)
        g.service_interior_kind='restaurant';g.mode='service_interior'
        before=dict(g.life.stats);money=g.life.money
        g.hospitality_order('meal')
        self.assertEqual(g.mode,'service_animation')
        self.assertEqual(g.life.money,money)
        self.assertEqual(g.life.stats,before)
        for _ in range(160):g.update_service_animation(.05)
        self.assertEqual(g.mode,'game')
        self.assertEqual(g.life.money,money-10)
        self.assertEqual(g.life.stats['Kenyang'],min(100,before['Kenyang']+58))

    def test_hotel_service_animation_sleeps_before_advancing_world_time(self):
        # Start in the public space just south of the receptionist's desk.
        g=self.game;g.life=Life(scene='hotel',x=448,y=450,money=80,stats={'Kenyang':25,'Minum':30,'Energi':20,'Senang':40})
        g.service_interior_kind='hotel';g.mode='service_interior'
        g.life.service_return_scene='market';g.life.service_return_x=700;g.life.service_return_y=610
        day,minutes,money=g.life.day,g.life.minutes,g.life.money
        g.hospitality_order('hotel')
        self.assertEqual((g.life.day,g.life.minutes,g.life.money),(day,minutes,money))
        phases=set()
        for _ in range(420):
            if g.service_animation:phases.add(g.service_animation['phase'])
            g.update_service_animation(.05)
            self.assertFalse(160 <= g.life.x <= 595 and 355 <= g.life.y <= 443,
                             'the scripted route must stay out of the reception desk footprint')
        self.assertTrue({'walk','fade_room','sleep','wake','return_walk'} <= phases)
        self.assertEqual(g.mode,'game')
        self.assertAlmostEqual(g.life.x,384)
        self.assertAlmostEqual(g.life.y,610)
        self.assertEqual(g.nearest()[0],'service_exit')
        self.assertEqual(g.life.money,money-15)
        self.assertEqual(g.life.stats['Energi'],100)
        self.assertNotEqual((g.life.day,g.life.minutes),(day,minutes))
        g.interact_selected()
        self.assertEqual(g.life.scene,'market')
        self.assertLess(math.hypot(g.life.x-700,g.life.y-610),40)

    def test_saved_hotel_counter_position_is_recovered_to_the_door(self):
        g=self.game;g.life=Life(scene='hotel',x=238,y=365)
        g.terrain_location=None;g.mode='game'
        g.ensure_walkable_position()
        self.assertEqual((g.life.x,g.life.y),g.art.gba.service_anchors('hotel')['entry'])
        self.assertEqual(g.nearest()[0],'service_exit')

    def test_center_heal_and_ball_flight_apply_only_after_animation(self):
        g=self.game;g.life=Life(scene='center',money=200,pokemon_party=[1,4],pokemon_active=[1,4])
        g.service_interior_kind='center';g.mode='service_interior'
        for ident in g.life.pokemon_active:g.life.pokemon_health[str(ident)]=1
        money=g.life.money
        g.heal_pokemon_party()
        self.assertEqual(g.mode,'service_animation')
        self.assertEqual(g.life.money,money)
        self.assertEqual(g.life.pokemon_health['1'],1)
        for _ in range(120):g.update_service_animation(.05)
        self.assertEqual(g.mode,'service_interior')
        self.assertLess(g.life.money,money)
        self.assertGreater(g.life.pokemon_health['1'],1)

        g.mode='service_interior';g.life.bag['Pokeball']=5;money=g.life.money
        g.buy_center_pokeballs()
        self.assertEqual(g.mode,'service_animation')
        self.assertEqual(g.life.bag['Pokeball'],5)
        self.assertEqual(g.life.money,money)
        for _ in range(80):g.update_service_animation(.05)
        self.assertEqual(g.mode,'service_interior')
        self.assertEqual(g.life.bag['Pokeball'],10)
        self.assertEqual(g.life.money,money-60)

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
        # The AI can now stun the player; isolate this ultimate-cutin check
        # from the preceding long combat simulation.
        b['player_stun_timer']=0
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
