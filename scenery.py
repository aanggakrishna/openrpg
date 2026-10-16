"""Cached pixel-art scenery using complete bundled sprites and shared map geometry."""
import math
import random
import pygame as pg
from world_regions import (BIOMES, PALETTES, reserve_layout, scene_layout,
                           online_solids, DUNGEON_BIOMES, COUNTRY_LANDMARKS)

class Scenery:
    def __init__(self, art):
        self.art=art
        self.scene_layers={}

    def ground(self,surface,biome):
        self.art.gba.ground(surface,biome)

    def path(self,surface,rect,biome):
        self.art.gba.path(surface,rect,biome)

    def pool(self,surface,rect,biome,kind='water',outline=True):
        self.art.gba.water(surface,rect,kind)

    def pools(self,surface,rects,biome,kind='water'):
        for rect in rects:
            self.pool(surface,rect,biome,kind)

    def bridge(self,surface,rect):
        self.art.gba.bridge(surface,rect)

    def rock(self,surface,x,y,biome,size=48):
        self.art.gba.rock(surface,x,y,size)

    def walls(self,surface,rects,biome):
        self.art.gba.walls(surface,rects,biome)

    def gate(self,surface,x,y,side,biome):
        self.art.gba.gate(surface,x,y,side,biome)

    def prop(self,surface,prop,biome):
        kind,x,y,variant=prop
        if kind=='tree':
            self.art.gba.tree(surface,x,y,88)
        elif kind=='landmark':
            self.landmark(surface,x,y,variant,biome)
        else:
            self.art.gba.rock(surface,x,y,56)

    def landmark(self,surface,x,y,index,biome):
        name='lab' if index%3==0 else 'hotel' if index%3==1 else 'home'
        self.art.gba.object(surface,name,x,y,144)

    def building(self,surface,kind,x,y,biome='meadow'):
        self.art.gba.building(surface,kind,x,y)

    def reserve(self,index):
        layout=reserve_layout(index);biome=layout['biome'];surface=pg.Surface((1280,1600)).convert()
        self.ground(surface,biome)
        for r in layout['paths']:self.path(surface,r,biome)
        for kind in ('water','ice','lava'):
            self.pools(surface,layout[kind],biome,kind)
        for r in layout['bridges']:self.bridge(surface,r)
        self.walls(surface,layout['walls'],biome)
        # No random atlas fragments: only complete flowers and rock/tree assets.
        rng=random.Random(101+index)
        for _ in range(80):
            x,y=rng.randrange(65,1200),rng.randrange(240,1490)
            if any(pg.Rect(r).inflate(18,18).collidepoint(x,y) for r in layout['solids']+layout['paths']):continue
            if biome in ('meadow','forest','ancient_forest'):
                surface.blit(self.art.gba.tile(4,18),(x,y))
            elif biome=='snow':pg.draw.rect(surface,(242,247,238),(x,y,5,3))
        for kind,x,y in layout['buildings']:self.building(surface,kind,x,y,biome)
        for side,x,y in layout['gates']:self.gate(surface,x,y,side,biome)
        return surface

    def local_overlay(self,surface,scene):
        l=scene_layout(scene);b=l['biome']
        for r in l['paths']:self.path(surface,r,b)
        for r in l['water']:self.pool(surface,r,b)
        for r in l['ice']:self.pool(surface,r,b,'ice')
        for r in l['lava']:self.pool(surface,r,b,'lava')
        for r in l['bridges']:self.bridge(surface,r)
        self.walls(surface,l['walls'],b)
        for prop in l['props']:self.prop(surface,prop,b)
        for side,x,y in l['gates']:self.gate(surface,x,y,side,b)
        if scene=='outdoors':self.gate(surface,160,610,'north','meadow')
        # Lamps at crossings; these are flat ground markings, not hidden blockers.
        for x in (90,1170):
            pg.draw.rect(surface,(187,166,104),(x,440,10,10))
            pg.draw.rect(surface,(249,216,136),(x+2,442,6,6))

    def interior(self,surface,scene):
        # Wainscoting, door frame and runner make both rooms feel connected.
        for x in range(205,1080,32):
            pg.draw.rect(surface,(139,115,86),(x,252,24,6))
        pg.draw.rect(surface,(115,98,83),(596,590,88,58))
        for y in range(596,646,8):pg.draw.line(surface,(206,180,123),(601,y),(679,y),2)
        self.gate(surface,640,665,'north','meadow')
        if scene=='house':
            pg.draw.rect(surface,(115,98,83),(980,259,72,18))
            pg.draw.rect(surface,(213,191,133),(984,260,64,4))

    def online(self,room):
        width=3200 if room=='hall' else 1280
        biome='crystal' if room=='gym' else 'mountain' if room=='hall' else DUNGEON_BIOMES[(int(room.split(':')[-1])-1)%10]
        surface=pg.Surface((width,800)).convert();self.ground(surface,biome)
        for r in ((40,350,width-80,210),(200,230,120,410)):self.path(surface,r,biome)
        self.walls(surface,[(0,190,width,45),(0,640,width,65),(0,190,40,515),(width-40,190,40,515)],biome)
        if room=='hall':
            for i,x in enumerate(range(300,3100,280)):
                pg.draw.rect(surface,(29,30,42),(x-60,235,120,100))
                self.gate(surface,x,315,'north','cave')
                for xx in (x-115,x+115):self.rock(surface,xx,300,'mountain',60)
        else:
            self.building(surface,'center',250,325)
            self.gate(surface,1150,390,'east',biome)
            for x in (500,720,940):self.prop(surface,('crystal' if room=='gym' else 'rock',x,275,0),biome)
            for r in online_solids(room)[4:]:
                if r[0] in (425,1000):pg.draw.rect(surface,(140,156,162),r)
            if room!='gym':self.pool(surface,(1050,340,100,90),biome,'lava' if biome=='volcano' else 'water')
        return surface
