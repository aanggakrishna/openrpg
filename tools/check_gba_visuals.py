"""Render deterministic review images using the existing local Pokemon cache."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import tempfile
from unittest.mock import patch
import pygame as pg
from main import Game, ROOT
from pokedex import PokedexClient
from state import Life

output=ROOT/'artifacts/gba-review'
output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as folder, patch.object(PokedexClient,'_work',lambda self:None):
    g=Game(Path(folder),Path(folder)/'save.json',shell='/bin/sh')
    try:
        g.life=Life(pokemon_caught=[25,4],pokemon_party=[25,4],pokemon_active=[25,4])
        g.life.weather_override='Cerah';g.life.minutes=12*60;g.life.advance_time(0)
        for ident in (25,4):
            cache=ROOT/'.openrpg/pokedex'
            g.pokedex.details[ident]=json.loads((cache/f'{ident}.json').read_text())
            sprite=pg.image.load(cache/f'{ident}.png').convert_alpha()
            g.poke_surfaces[ident]=g.fit_pokemon_sprite(sprite,96)
            g.poke_battle_surfaces[ident]=g.fit_pokemon_sprite(sprite,160)
        g.begin();g.toast_until=0
        for scene in ('outdoors','market','house','bedroom','forest','coast','local_dungeon'):
            g.mode='game';g.life.scene=scene;g.life.x=640;g.life.y=600
            g.draw();pg.image.save(g.canvas,output/f'{scene}.png')
        g.begin_pokemon_battle(4);g.battle['intro']=None
        g.draw();pg.image.save(g.canvas,output/'battle.png')
        contact=pg.Surface((640,384));contact.fill((225,238,214))
        for row,direction in enumerate(('down','up','left','right')):
            for col,frame in enumerate((0,7,14,21)):
                g.art.character(contact,col*160+80,row*96+90,0,2,frame,True,direction)
        pg.image.save(contact,output/'walking.png')
        print(f'Review images: {output}')
    finally:
        g.terminal.close();pg.quit()
