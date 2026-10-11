"""Cached pixel-art scenery using complete bundled sprites and shared map geometry."""
import random
import pygame as pg
from world_regions import (BIOMES, PALETTES, reserve_layout, scene_layout,
                           online_solids, DUNGEON_BIOMES, COUNTRY_LANDMARKS)

class Scenery:
    def __init__(self, art):
        self.art=art
        self.trees={i:pg.transform.scale(art.nature.subsurface((i*32,0,32,32)),(104,104)) for i in range(10)}
        self.textures={}
        for biome,palette in PALETTES.items():
            tile=pg.Surface((48,48));tile.fill(palette[0]);rng=random.Random(410+BIOMES.index(biome))
            for _ in range(35):
                x,y=rng.randrange(24)*2,rng.randrange(24)*2
                color=tuple(max(0,min(255,v+rng.choice((-8,-4,5,8)))) for v in palette[0])
                pg.draw.rect(tile,color,(x,y,2*rng.randrange(1,3),2))
            if biome in ('meadow','forest','swamp','ancient_forest'):
                for x,y in ((8,12),(30,38)):
                    c=tuple(max(0,v-15) for v in palette[0]);pg.draw.lines(tile,c,False,[(x-2,y-2),(x,y),(x+2,y-4)],2)
            self.textures[biome]=tile
        self.scene_layers={}

    def ground(self,surface,biome):
        texture=self.textures[biome]
        for y in range(0,surface.get_height(),48):
            for x in range(0,surface.get_width(),48):surface.blit(texture,(x,y))

    def path(self,surface,rect,biome):
        r=pg.Rect(rect);color=PALETTES[biome][1]
        pg.draw.rect(surface,color,r)
        rng=random.Random(r.x*17+r.y*3+r.w)
        for _ in range(max(1,r.w*r.h//280)):
            x=rng.randrange(r.left,r.right);y=rng.randrange(r.top,r.bottom)
            pg.draw.rect(surface,tuple(max(0,v-13) for v in color),(x,y,4,2))

    def pool(self,surface,rect,biome,kind='water',outline=True):
        r=pg.Rect(rect);pal=PALETTES[biome]
        water=(174,215,226) if kind=='ice' else pal[4]
        if kind=='lava':water=(220,74,36)
        edge=(231,235,216) if kind=='ice' else pal[2]
        # A stepped shore follows exactly the same rectangular area used for collision.
        if outline:
            pg.draw.rect(surface,edge,r.inflate(12,12));pg.draw.rect(surface,pal[3],r.inflate(6,6),3)
        pg.draw.rect(surface,water,r)
        rng=random.Random(r.x*7+r.y)
        for _ in range(r.w*r.h//400):
            x=rng.randrange(r.left+5,r.right-8);y=rng.randrange(r.top+4,r.bottom-4)
            c=(250,175,61) if kind=='lava' else tuple(min(255,v+30) for v in water)
            pg.draw.line(surface,c,(x,y),(min(r.right-3,x+rng.randrange(5,18)),y),2)
        if kind=='ice':
            for i in range(4):
                x=r.left+20+i*(r.w-40)//4
                pg.draw.lines(surface,(228,244,242),False,[(x,r.bottom-12),(x+38,r.centery),(x+20,r.top+10)],2)
        if biome=='deepsea' and kind=='water':
            for x in range(r.left+20,r.right-20,48):
                pg.draw.lines(surface,(91,166,140),False,[(x,r.bottom-5),(x-5,r.bottom-22),(x+5,r.bottom-36)],4)

    def pools(self,surface,rects,biome,kind='water'):
        for rect in rects:
            r=pg.Rect(rect);edge=(231,235,216) if kind=='ice' else PALETTES[biome][2]
            pg.draw.rect(surface,edge,r.inflate(12,12))
            pg.draw.rect(surface,PALETTES[biome][3],r.inflate(6,6))
        for rect in rects:self.pool(surface,rect,biome,kind,False)

    def bridge(self,surface,rect):
        r=pg.Rect(rect);pg.draw.rect(surface,(72,59,49),r)
        for x in range(r.left,r.right,14):
            pg.draw.rect(surface,(174,134,82),(x+1,r.top+4,12,r.h-8))
            pg.draw.line(surface,(219,177,113),(x+2,r.top+6),(x+10,r.top+6),2)
        for y in (r.top,r.bottom-4):
            pg.draw.rect(surface,(89,67,48),(r.left,y,r.w,4))
            for x in range(r.left,r.right,42):pg.draw.rect(surface,(222,179,117),(x,y-4,6,9))

    def rock(self,surface,x,y,biome,size=48):
        dark=PALETTES[biome][2];light=tuple(min(255,c+30) for c in dark)
        x,y=int(x),int(y);w=size;h=int(size*.72)
        points=[(x-w//2,y-4),(x-w//2,y-h//2),(x-w//4,y-h),(x+w//4,y-h),
                (x+w//2,y-h//2),(x+w//2,y),(x-w//4,y+4)]
        pg.draw.polygon(surface,tuple(max(0,c-22) for c in dark),points)
        pg.draw.polygon(surface,dark,[(a,b-3) for a,b in points])
        pg.draw.polygon(surface,light,[(x-w//2+4,y-h//2),(x-w//4,y-h+3),(x+w//4,y-h+3),(x+5,y-h//2)])
        if biome in ('snow','mountain'):pg.draw.lines(surface,(235,242,236),False,points[1:4],5)

    def walls(self,surface,rects,biome):
        pal=PALETTES[biome]
        for rect in rects:
            r=pg.Rect(rect);pg.draw.rect(surface,tuple(max(0,c-25) for c in pal[2]),r)
            pg.draw.rect(surface,pal[2],r,4)
            old=surface.get_clip();surface.set_clip(r)
            for y in range(r.top+28,r.bottom+28,30):
                for x in range(r.left+24,r.right+24,42):self.rock(surface,x,y,biome,48)
            surface.set_clip(old)
            pg.draw.line(surface,pal[3],r.topleft,(r.right,r.top),3)

    def gate(self,surface,x,y,side,biome):
        pal=PALETTES[biome];wood=biome in ('forest','meadow','swamp','ancient_forest')
        material=(114,84,56) if wood else pal[2]
        if side in ('east','west'):
            for y0 in (y-78,y+50):
                pg.draw.rect(surface,(32,42,48),(x-18,y0-10,36,38))
                pg.draw.rect(surface,material,(x-15,y0-10,30,34))
                pg.draw.rect(surface,pal[3],(x-18,y0-12,36,8))
            pg.draw.line(surface,pal[1],(x,y-44),(x,y+44),3)
            pg.draw.polygon(surface,pal[3],[(x-10,y-8),(x+10,y),(x-10,y+8)])
        else:
            for x0 in (x-78,x+50):
                pg.draw.rect(surface,(32,42,48),(x0-3,y-70,34,90))
                pg.draw.rect(surface,material,(x0,y-70,28,90))
                for yy in range(y-65,y+20,18):pg.draw.line(surface,pal[3],(x0+3,yy),(x0+24,yy),2)
            pg.draw.rect(surface,(32,42,48),(x-86,y-84,172,22))
            pg.draw.rect(surface,material,(x-84,y-82,168,16))
            pg.draw.rect(surface,pal[3],(x-86,y-85,172,5))
            pg.draw.rect(surface,pal[1],(x-26,y-84,52,20))
        # Small lanterns make every entrance readable at night.
        for xx in (x-50,x+50):
            pg.draw.rect(surface,(247,192,91),(xx-3,y-24,6,8))

    def prop(self,surface,prop,biome):
        kind,x,y,variant=prop;pal=PALETTES[biome]
        if kind=='tree':
            choices=(4,5,6) if biome in ('snow','mountain') else (0,1,3) if biome in ('forest','ancient_forest','swamp') else (0,7,8,9)
            sprite=self.trees[choices[variant%len(choices)]]
            pg.draw.ellipse(surface,tuple(max(0,c-20) for c in pal[0]),(x-36,y-8,72,16))
            surface.blit(sprite,(x-52,y-100))
        elif kind=='rock':self.rock(surface,x,y,biome,56)
        elif kind=='cactus':
            pg.draw.rect(surface,(42,90,62),(x-9,y-65,18,65))
            pg.draw.lines(surface,(64,126,74),False,[(x-25,y-40),(x-25,y-20),(x+23,y-20),(x+23,y-50)],10)
            pg.draw.line(surface,(146,168,94),(x-3,y-60),(x-3,y-4),3)
        elif kind=='crystal':
            for dx,h in ((-16,35),(0,68),(19,40)):
                pg.draw.polygon(surface,(86,193,197),[(x+dx-12,y-8),(x+dx-10,y-h),(x+dx,y-h-12),(x+dx+10,y-h),(x+dx+12,y-8)])
                pg.draw.line(surface,(215,245,230),(x+dx,y-h-10),(x+dx,y-10),3)
        elif kind=='landmark':
            self.landmark(surface,x,y,variant,biome)
        else:
            pg.draw.rect(surface,pal[2],(x-18,y-60,36,60))
            pg.draw.rect(surface,pal[3],(x-23,y-66,46,10))
            for yy in range(y-50,y-5,12):pg.draw.line(surface,pal[1],(x-13,yy),(x+13,yy),2)

    def landmark(self,surface,x,y,index,biome):
        """Draw a compact pixel landmark for a country region.

        The shapes deliberately use the game's tiny-pixel palette and the
        bundled CC0 terrain/building colors, so country zones read as places
        rather than imported artwork from a second visual style.
        """
        style,_=COUNTRY_LANDMARKS.get(index,('ruins','Landmark'))
        x,y=int(x),int(y)
        dark=(35,42,53); stone=PALETTES[biome][2]; light=PALETTES[biome][3]
        earth=PALETTES[biome][1]; green=(71,125,70); gold=(239,191,82)
        def rect(color,box,outline=True):
            pg.draw.rect(surface,dark,pg.Rect(box).inflate(6,6)) if outline else None
            pg.draw.rect(surface,color,box)
        def roof(points,color=(177,69,58)):
            pg.draw.polygon(surface,dark,points);pg.draw.polygon(surface,color,[(a,b-3) for a,b in points])
        # Water and rock landmarks.
        if style in ('cenote','geyser','iceberg','glacier'):
            if style=='cenote':
                pg.draw.ellipse(surface,dark,(x-68,y-72,136,72));pg.draw.ellipse(surface,(43,134,169),(x-60,y-68,120,58))
                pg.draw.ellipse(surface,(113,210,213),(x-35,y-55,70,18))
            elif style=='geyser':
                self.rock(surface,x,y,biome,66)
                for dx,h in ((-14,58),(0,88),(15,52)):pg.draw.line(surface,(210,245,250),(x+dx,y-28),(x+dx+5,y-h),7)
            else:
                color=(184,231,239) if style=='iceberg' else (156,211,231)
                pg.draw.polygon(surface,dark,[(x-67,y-12),(x-34,y-94),(x+5,y-122),(x+66,y-12)])
                pg.draw.polygon(surface,color,[(x-60,y-15),(x-30,y-87),(x+3,y-114),(x+59,y-15)])
                pg.draw.polygon(surface,(232,250,249),[(x-30,y-87),(x+3,y-114),(x+5,y-35)])
            return
        # Distinct large natural formations.
        if style in ('rice_terrace','mountain_peak','uluru','table_mountain','redwood','baobab','acacia'):
            if style=='rice_terrace':
                for step in range(4):
                    yy=y-22-step*20;ww=118-step*18
                    rect((83,142+step*9,75),(x-ww//2,yy,ww,17))
                    pg.draw.line(surface,(211,188,113),(x-ww//2+8,yy+12),(x+ww//2-8,yy+12),2)
            elif style in ('mountain_peak','table_mountain'):
                pts=[(x-72,y-8),(x-30,y-95),(x-8,y-138),(x+25,y-80),(x+70,y-8)]
                if style=='table_mountain':pts=[(x-75,y-8),(x-48,y-82),(x+45,y-82),(x+75,y-8)]
                pg.draw.polygon(surface,dark,pts);pg.draw.polygon(surface,stone,[(a,b-4) for a,b in pts])
                pg.draw.polygon(surface,light,pts[1:3]+[(x+8,y-38)])
            elif style=='uluru':
                pg.draw.ellipse(surface,dark,(x-77,y-90,154,92));pg.draw.ellipse(surface,(186,85,55),(x-70,y-85,140,84))
                pg.draw.line(surface,(237,142,82),(x-42,y-64),(x+24,y-80),5)
            else:
                trunk=(103,75,50); crown=(65,117,65)
                if style=='baobab':
                    rect(trunk,(x-20,y-105,40,100));pg.draw.ellipse(surface,crown,(x-74,y-158,148,75))
                elif style=='redwood':
                    rect(trunk,(x-17,y-160,34,155));pg.draw.ellipse(surface,(52,102,62),(x-50,y-230,100,125))
                else:
                    rect(trunk,(x-12,y-90,24,85));pg.draw.ellipse(surface,crown,(x-73,y-148,146,74))
            return
        # World monuments and buildings.
        if style=='pyramid':
            roof([(x-82,y-6),(x,y-145),(x+82,y-6)],(206,172,93))
            pg.draw.line(surface,(242,209,132),(x,y-137),(x,y-13),3)
        elif style=='eiffel':
            pg.draw.line(surface,dark,(x-62,y-5),(x,y-155),8);pg.draw.line(surface,dark,(x+62,y-5),(x,y-155),8)
            for yy,ww in ((y-35,84),(y-70,57),(y-108,31)):pg.draw.line(surface,gold,(x-ww//2,yy),(x+ww//2,yy),5)
        elif style=='windmill':
            rect((225,213,176),(x-20,y-110,40,105));pg.draw.line(surface,dark,(x,y-92),(x,y-170),5)
            for dx,dy in ((0,-33),(33,0),(0,33),(-33,0)):pg.draw.line(surface,(226,205,156),(x,y-136),(x+dx,y-136+dy),10)
        elif style=='lighthouse':
            rect((237,230,208),(x-24,y-140,48,132));rect((201,76,62),(x-29,y-151,58,18));pg.draw.rect(surface,(255,234,145),(x-10,y-143,20,12))
        elif style=='balloons':
            for dx,dy,c in ((-38,-67),(13,-105),(51,-55)):
                pg.draw.circle(surface,dark,(x+dx,y+dy),24);pg.draw.circle(surface,c,(x+dx,y+dy-3),20)
                pg.draw.line(surface,dark,(x+dx,y+dy+18),(x+dx,y+dy+42),3)
            rect((136,89,54),(x+3,y-46,20,11))
        elif style in ('torii','pagoda','thai_temple','stupa','palace','temple','acropolis','kasbah','ruins'):
            if style=='torii':
                rect((183,56,45),(x-50,y-118,16,112));rect((183,56,45),(x+34,y-118,16,112));rect((207,75,54),(x-72,y-130,144,20))
            elif style in ('pagoda','thai_temple','palace'):
                for tier in range(3):
                    yy=y-25-tier*38;ww=118-tier*25
                    roof([(x-ww//2,yy),(x,y-45-tier*38),(x+ww//2,yy)],(183,70,54) if tier<2 else gold)
                rect((156,111,70),(x-15,y-62,30,58))
            elif style=='stupa':
                rect((209,177,100),(x-62,y-20,124,18));pg.draw.circle(surface,gold,(x,y-62),42);pg.draw.line(surface,gold,(x,y-102),(x,y-142),6)
            else:
                rect(stone,(x-66,y-68,132,62));
                for dx in (-45,-15,15,45):rect(light,(x+dx-7,y-105,14,42))
                if style=='acropolis':roof([(x-78,y-106),(x,y-148),(x+78,y-106)],light)
                if style=='kasbah':roof([(x-66,y-68),(x-39,y-126),(x-10,y-68)],earth)
        elif style in ('colosseum','castle','stave_church','maple_cabin','meeting_house','island_huts','chalet'):
            rect((151,111,73),(x-70,y-74,140,68));roof([(x-80,y-76),(x,y-135),(x+80,y-76)],(135,66,54))
            if style=='colosseum':
                for dx in (-45,-15,15,45):pg.draw.arc(surface,dark,(x+dx-9,y-48,18,28),math.pi,math.tau,3)
            elif style=='castle':
                for dx in (-56,32):rect(stone,(x+dx,y-126,24,120))
            elif style=='stave_church':pg.draw.line(surface,dark,(x,y-126),(x,y-171),5)
        elif style in ('statue','observatory'):
            rect(stone,(x-48,y-38,96,32));
            if style=='statue':
                pg.draw.circle(surface,(183,192,182),(x,y-103),22);rect((183,192,182),(x-18,y-82,36,48));pg.draw.line(surface,(183,192,182),(x-18,y-75),(x-50,y-110),9)
            else:
                pg.draw.ellipse(surface,(205,215,212),(x-58,y-117,116,80));pg.draw.arc(surface,dark,(x-58,y-117,116,80),0,math.pi,4)
        else:
            # A small recognizable archaeological structure for remaining sites.
            rect(stone,(x-66,y-62,132,56));roof([(x-74,y-64),(x,y-125),(x+74,y-64)],light)

    def building(self,surface,kind,x,y):
        self.art.grid(surface,'tiny-town',[[52,53,53,55,53,53,54],[64,65,65,65,65,65,66],
            [72,73,73,73,73,73,75],[84,73,84,85,73,84,73]],x-98,y-138,28)
        if kind!='center':
            roof=pg.Surface((196,48),pg.SRCALPHA)
            roof.fill((58,105,180,110) if kind=='hotel' else (213,170,57,85))
            surface.blit(roof,(x-98,y-138))
        color={'center':(212,78,83),'restaurant':(222,163,83),'hotel':(94,151,192)}[kind]
        pg.draw.rect(surface,(34,47,57),(x-30,y-149,60,22));pg.draw.rect(surface,color,(x-27,y-146,54,16))
        if kind=='center':
            pg.draw.circle(surface,(247,239,211),(x,y-138),7);pg.draw.line(surface,color,(x-7,y-138),(x+7,y-138),3)
        elif kind=='hotel':pg.draw.rect(surface,(245,234,198),(x-5,y-143,10,10))
        else:
            pg.draw.rect(surface,(245,234,198),(x-10,y-140,20,5));pg.draw.line(surface,(245,234,198),(x,y-145),(x,y-137),2)
        # Door apron is outside the solid facade, and remains reachable.
        pg.draw.rect(surface,(211,188,140),(x-22,y-26,44,26))

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
                if index == 0:
                    # The starter sanctuary uses a muted, locally matched grass
                    # tuft instead of the bright flower atlas tile, which stood
                    # out against this meadow's ground palette.
                    grass=PALETTES[biome][0]
                    light=tuple(min(255,c+9) for c in grass)
                    shade=tuple(max(0,c-11) for c in grass)
                    pg.draw.line(surface,shade,(x-3,y),(x-1,y-4),2)
                    pg.draw.line(surface,light,(x,y),(x+1,y-5),2)
                    pg.draw.line(surface,shade,(x+3,y),(x+4,y-3),2)
                else:
                    self.art.tile(surface,'tiny-town',2,x,y,18)
            elif biome=='snow':pg.draw.rect(surface,(242,247,238),(x,y,5,3))
        for kind,x,y in layout['buildings']:self.building(surface,kind,x,y)
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
