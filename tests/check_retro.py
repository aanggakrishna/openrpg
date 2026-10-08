"""Headless retro UI regression with mock Pokemon and isolated save/shell.
Run: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python tests/check_retro.py
"""
from pathlib import Path
import sys
import tempfile
import random
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pygame as pg
from main import Game, ROOT
from state import Life
from pokedex import PokedexClient

# Disable worker/network in this check; use deterministic mock Pokemon data.
with tempfile.TemporaryDirectory() as folder, patch.object(PokedexClient, '_work', lambda self: None):
    g = Game(Path(folder), Path(folder)/'save.json', shell='/bin/sh')
    try:
        g.life = Life()
        g.pokedex.catalog = []
        for ident, name, kind in ((1,'bulbasaur','grass'),(4,'charmander','fire'),
                                  (7,'squirtle','water'),(15,'beedrill','bug')):
            detail = {'id':ident,'name':name,'height':7,'weight':69,'base_experience':64,
                      'stats':[{'base_stat':50,'stat':{'name':key}} for key in
                               ('hp','attack','defense','special-attack','special-defense','speed')],
                      'types':[{'slot':1,'type':{'name':kind,'url':''}}],
                      'abilities':[], 'moves':[], 'sprites':{}}
            g.pokedex.details[ident] = detail
            g.pokedex.catalog.append({'id': ident, 'name': name})
            sprite = pg.Surface((96,96), pg.SRCALPHA)
            pg.draw.rect(sprite, (90,170,110), (20,24,56,56))
            pg.draw.rect(sprite, (24,31,48), (28,40,8,8))
            g.poke_surfaces[ident] = sprite
            g.poke_battle_surfaces[ident] = pg.transform.scale(sprite, (136,136))
        for method in ('request','request_move','request_animation','request_cry',
                       'request_species','request_evolution','request_item'):
            setattr(g.pokedex, method, lambda *args, **kwargs: None)
        g.pokemon_rng = random.Random()
        g.life.pokemon_caught = [1,4,7]
        g.life.pokemon_party = [1,4,7]
        g.life.pokemon_active = [1,4,7]
        g.life.pokemon_health = {'1':100, '4':100, '7':100}
        g.dex_detail = g.pokemon_data(1)
        g.toast_until = 0
        g.encounter_target = {'id':15, 'level':5}
        assert g.pokemon_surface(2000) is None
        assert max(g.fruit_font.render('🍎', True, (255,255,255)).get_size()) <= 18
        output = ROOT/'artifacts/retro'
        output.mkdir(parents=True, exist_ok=True)
        for mode in ('title','game','inventory','shop','weather','help','pause','dex','center','map','terminal','encounter','pokemon_info'):
            g.mode = mode
            g.draw()
            assert all(0 <= r.left < r.right <= 1280 and 0 <= r.top < r.bottom <= 800 for r,_ in g.buttons), mode
            pg.image.save(g.canvas, output/f'{mode}.png')
        for scene in ('outdoors','forest','market','house','bedroom','coast','mountain','reserve'):
            g.mode='game';g.life.scene=scene;g.life.x=640;g.life.y=800 if scene=='reserve' else 500
            g.draw()
        g.life.scene='reserve'
        g.pokemon_rng.seed(7)
        g.begin_pokemon_battle(15)
        b=g.battle
        assert b is not None
        b['intro']=None
        b['player_hp']=b['player_max']=1000
        hp=b['player_hp']
        attacks=0
        for _ in range(720):
            previous=b.get('enemy_attack_flash',0)
            g.update_battle(1/60)
            attacks += b.get('enemy_attack_flash',0)>previous
        assert b['player_hp']<hp and attacks>=2, b
        b['super_meter']=100
        g._set_battle_vfx('grass','Ultimate Daun',ultimate=True,emoji='🌿')
        b['fruits']=[{'x':500,'emoji':'🍎','kind':'health','life':10}]
        b['vfx']['timer'] *= .45
        g.draw();pg.image.save(g.canvas,output/'battle.png')
        timer=b['vfx']['timer'];g.update_battle(.05)
        assert b['vfx']['timer']<timer
        g.switch_battle_pokemon(4)
        assert b['player_id']==4
        # A late hit with no VFX must also resolve safely.
        b['trainer']={'name':'Check','paid':True,'defeated':False}
        b['opponent_lineup']=[15,7];b['opponent_index']=0;b['vfx']=None
        g._win_battle()
        assert b.get('next_opponent_timer') is not None
        g.begin_pokemon_battle(15)
        b=g.battle;b['intro']=None;b['time_left']=.01
        g.update_battle(.02)
        assert b['timeout'] and b['time_left']==0
        b['wild_hp']=0
        g.life.bag['Pokeball']=1
        g.pokemon_catch()
        assert b['capture']['phase']=='throw'
        phases=set()
        for _ in range(90):
            if g.battle is None:
                break
            phases.add(b['capture']['phase'])
            g.draw()
            g.update_capture(.05)
        assert {'throw','absorb','shake','success'} <= phases
        assert 15 in g.life.pokemon_caught and g.battle is None
        assert len(g.life.pokemon_active)==len(set(g.life.pokemon_active))
        # A KO target has a high chance, never an automatic catch. Failed
        # throws return to the battle and allow another ball to be tried.
        g.begin_pokemon_battle(15)
        b=g.battle; b['intro']=None; b['wild_hp']=0; b['result']='Menang'; b['timeout']=False
        g.life.bag['Pokeball']=2
        with patch.object(g.pokemon_rng, 'randrange', return_value=99):
            g.pokemon_catch()
        assert not b['capture']['success'] and '90%' in b['phase']
        for _ in range(80):
            g.update_capture(.05)
            if b['capture'] is None:
                break
        assert b['capture'] is None and g.battle is b
        with patch.object(g.pokemon_rng, 'randrange', return_value=0):
            g.pokemon_catch()
        assert b['capture']['success']
        for size in ((960,600),(1600,1000)):
            g.window=pg.display.set_mode(size)
            g.mode='title';g.draw()
        print(f'Retro: 13 UI modes, 8 scenes, capture, timeout, AI ({attacks} attacks), ultimate, team switch, trainer round, resize: OK')
    finally:
        g.terminal.close()
        pg.quit()
