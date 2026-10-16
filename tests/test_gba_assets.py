"""Offline regression tests for the GBA environment / original Pokemon split."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from types import SimpleNamespace
import random
import pygame as pg
from gba_world import GBAWorld, walking_pose
from main import Game
from art import RESERVE_ZONES
from world_regions import reserve_layout
from fighter import FighterMixin

class GBAAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init();pg.display.set_mode((1280,800))

    def test_walk_never_changes_direction(self):
        for direction,poses in [('down',[0,3,0,4]),('up',[1,5,1,6]),
                                ('left',[2,7,2,8]),('right',[2,7,2,8])]:
            actual=[walking_pose(direction,f,True) for f in (0,7,14,21)]
            self.assertEqual([p for p,_ in actual],poses)
            self.assertEqual([flip for _,flip in actual],[direction=='right']*4)
            self.assertEqual(walking_pose(direction,99,False),(poses[0],direction=='right'))

    def test_pokemon_uses_original_cache_not_gba(self):
        original=pg.Surface((96,96));original.fill((12,80,200))
        fake=SimpleNamespace(poke_animations={},poke_surfaces={25:original},
                             poke_battle_surfaces={},pokemon_render_cache={},frame=0)
        result=Game.pokemon_surface(fake,25,96)
        self.assertEqual(result.get_at((40,40)),original.get_at((40,40)))

    def test_animated_pokemon_still_advances(self):
        first=pg.Surface((96,96));first.fill('red')
        second=pg.Surface((96,96));second.fill('blue')
        fake=SimpleNamespace(poke_animations={25:[(first,100),(second,100)]},
                             poke_surfaces={},poke_battle_surfaces={},
                             pokemon_render_cache={},frame=0)
        a=Game.pokemon_surface(fake,25,96)
        fake.frame=7
        b=Game.pokemon_surface(fake,25,96)
        self.assertNotEqual(a.get_at((40,40)),b.get_at((40,40)))

    def test_environment_and_arenas_render_offline(self):
        world=GBAWorld();canvas=pg.Surface((1280,800))
        for biome in ('meadow','coast','cave','snow'):
            world.ground(canvas,biome)
            self.assertNotEqual(canvas.get_at((640,400)),pg.Color('black'))
        for style in ('meadow','water','cave','volcano','sky'):
            world.arena(canvas,style)
        for name in world.objects:
            world.object(canvas,name,640,600,96)
        for scene in ('house','bedroom','center','restaurant','hotel'):
            world.interior(canvas,scene)
            self.assertNotEqual(canvas.get_at((640,400)),pg.Color('black'))

    def test_all_sanctuary_buildings_and_service_signs_are_separated(self):
        for index, zone in enumerate(RESERVE_ZONES):
            layout=reserve_layout(index)
            buildings=layout['buildings']
            footprints=[]
            signs=[]
            for kind,x,y in buildings:
                width={'center':196,'hotel':196,'restaurant':196}[kind]
                height=width
                # gba_world.objects are 1:1 sprites. Anchor as the renderer
                # does (midbottom at y-16) and verify actual pixels do not stack.
                footprints.append((kind,pg.Rect(x-width//2,y-16-height,width,height)))
                sign_y=y-114 if kind=='center' else y-59
                signs.append((kind,pg.Rect(x-92,sign_y-3,184,24)))
            for left in range(len(footprints)):
                for right in range(left+1,len(footprints)):
                    self.assertFalse(footprints[left][1].colliderect(footprints[right][1]),
                                     f"zone {index} buildings overlap: {footprints[left][0]} / {footprints[right][0]}")
            for left in range(len(signs)):
                for right in range(left+1,len(signs)):
                    self.assertFalse(signs[left][1].colliderect(signs[right][1]),
                                     f"zone {index} signs overlap: {signs[left][0]} / {signs[right][0]}")
            for side,x,y in layout['gates']:
                gate_sign=pg.Rect(x-110,y-33,220,24)
                for kind,sign in signs:
                    self.assertFalse(gate_sign.colliderect(sign),
                                     f"zone {index} {side} gate sign overlaps {kind} sign")

    def test_arena_hazard_is_telegraphed_and_damages_once(self):
        battle={'result':'','arena_style':'cave','ambient_hazards':[],
                'hazard_timer':0,'player_x':90,'enemy_x':1190,'player_y':0,
                'enemy_y':0,'player_hp':100,'player_max':100,'wild_hp':100,
                'wild_max':100,'player_id':25,'wild_id':4}
        fake=SimpleNamespace(battle=battle,pokemon_rng=random.Random(2),
                             life=SimpleNamespace(godmode=False),
                             save_battle_player_hp=lambda:None,
                             words=lambda a,b:a,_win_battle=lambda:None)
        FighterMixin.update_ambient_hazards(fake,0)
        hazard=battle['ambient_hazards'][0]
        self.assertEqual(hazard['phase'],'warning')
        FighterMixin.update_ambient_hazards(fake,2)
        hazard=battle['ambient_hazards'][0]
        self.assertEqual(hazard['phase'],'active')
        battle['player_x']=hazard['x']
        hp=battle['player_hp']
        FighterMixin.update_ambient_hazards(fake,1.4)
        self.assertLess(battle['player_hp'],hp)
        hp=battle['player_hp']
        FighterMixin.update_ambient_hazards(fake,.01)
        self.assertEqual(battle['player_hp'],hp)

if __name__=='__main__':unittest.main()
