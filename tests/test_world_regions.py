"""Real reachability and climate checks for shared render/collision geometry."""
import unittest
from collections import deque
from world_regions import (BIOMES, CLIMATES, reserve_layout, overlaps, weather_for,
                           scene_layout, online_step, online_solids)

class WorldRegionsTests(unittest.TestCase):
    def test_all_region_services_and_gates_are_reachable(self):
        for index,biome in enumerate(BIOMES):
            with self.subTest(biome=biome):
                layout=reserve_layout(index)
                def clear(x,y):
                    return 28<=x<=1252 and 155<=y<=1572 and not any(overlaps((x-12,y-12,24,14),r) for r in layout['solids'])
                origin=(640,800);self.assertTrue(clear(*origin))
                seen={origin};todo=deque([origin])
                while todo:
                    x,y=todo.popleft()
                    for dx,dy in ((24,0),(-24,0),(0,24),(0,-24)):
                        p=(x+dx,y+dy)
                        if p not in seen and clear(*p):seen.add(p);todo.append(p)
                for label,x,y in layout['buildings']+layout['gates']:
                    self.assertTrue(any((px-x)**2+(py-y)**2<70**2 for px,py in seen),(biome,label,x,y))

    def test_water_blocks_bridge_and_ice_do_not(self):
        l=reserve_layout(0)
        self.assertTrue(any(overlaps((250,320,24,14),r) for r in l['solids']))
        self.assertFalse(any(overlaps((250,410,24,14),r) for r in l['solids']))
        snow=reserve_layout(9)
        self.assertFalse(any(overlaps((260,390,24,14),r) for r in snow['solids']))

    def test_local_landmarks_block_and_bridges_match_rendered_paths(self):
        for scene in ('forest','coast','mountain'):
            layout=scene_layout(scene)
            for _,x,y,_ in layout['props']:
                self.assertTrue(any(overlaps((x-12,y-12,24,14),r) for r in layout['solids']))
        outdoors=scene_layout('outdoors')
        self.assertEqual(outdoors['bridges'],[(930,568,288,56)])
        self.assertFalse(any(overlaps((1040,585,24,14),r) for r in outdoors['solids']))
        self.assertTrue(any(overlaps((1040,510,24,14),r) for r in outdoors['solids']))

    def test_weather_matches_every_habitat(self):
        for i,b in enumerate(BIOMES):
            for hour in range(24):
                args=('reserve',i%4*1280+640,i//4*1600+800,4,hour)
                self.assertIn(weather_for(*args),CLIMATES[b][0])
                self.assertIn(weather_for(*args,override='Salju'),CLIMATES[b][0])
        self.assertNotEqual(CLIMATES['desert'],CLIMATES['snow'])

    def test_online_walls_stop_players(self):
        for room in ('gym','hall','dungeon:1','dungeon:10'):
            x,y=600.,450.
            for _ in range(200):x,y=online_step(room,x,y,0,-1,.05)
            self.assertGreaterEqual(y,247)
            self.assertFalse(any(overlaps((x-12,y-12,24,14),r) for r in online_solids(room)))
        x,y=420,350
        for _ in range(30):x,y=online_step('gym',x,y,1,0,.05)
        self.assertLess(x,425)

if __name__=='__main__':unittest.main()
