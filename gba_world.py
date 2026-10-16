"""FireRed scenery assembled from native metatiles. Gameplay geometry stays shared."""
from pathlib import Path
import pygame as pg

ROOT = Path(__file__).resolve().parent / 'assets/gba/environment'

def walking_pose(facing, frame, walking):
    """FireRed sAnim_Go*: three facing poses, two steps per direction.

    East is the mirrored west animation, never an unrelated fourth frame.
    """
    poses = {'down':(0,3,0,4), 'up':(1,5,1,6),
             'left':(2,7,2,8), 'right':(2,7,2,8)}
    return poses[facing][int(frame//7)%4 if walking else 0], facing=='right'

class GBAWorld:
    def __init__(self):
        self.atlases={name:pg.image.load(ROOT/f'{name}.png').convert_alpha()
                      for name in ('pallet_town','viridian_city','cave','generic_building_1')}
        self.objects={name:pg.image.load(ROOT/f'{name}.png').convert_alpha()
                      for name in ('home','lab','center','mart','hotel','restaurant','tree','rock')}
        self.interiors={name:pg.image.load(ROOT/f'interior_{name}.png').convert_alpha()
                        for name in ('center','restaurant','hotel')}
        self.arenas={}
        self.cache={}

    def tile(self, ident, size=32, atlas='pallet_town'):
        key=(atlas,ident,size)
        if key not in self.cache:
            source=self.atlases[atlas].subsurface((ident%16*16,ident//16*16,16,16))
            self.cache[key]=pg.transform.scale(source,(size,size))
        return self.cache[key]

    def fill(self, target, rect, ident=1, size=32, atlas='pallet_town'):
        rect=pg.Rect(rect); old=target.get_clip();target.set_clip(rect.clip(old))
        tile=self.tile(ident,size,atlas)
        for y in range(rect.top,rect.bottom,size):
            for x in range(rect.left,rect.right,size):target.blit(tile,(x,y))
        target.set_clip(old)

    def grid(self,target,rows,x,y,size=32,atlas='pallet_town'):
        for row,items in enumerate(rows):
            for col,ident in enumerate(items):
                target.blit(self.tile(ident,size,atlas),(x+col*size,y+row*size))

    def object(self,target,name,x,y,width):
        key=(name,width)
        if key not in self.cache:
            source=self.objects[name]
            self.cache[key]=pg.transform.scale(source,(width,round(width*source.get_height()/source.get_width())))
        img=self.cache[key];target.blit(img,img.get_rect(midbottom=(round(x),round(y))))

    def ground(self,target,biome):
        tile=261 if biome in ('desert','coast','badlands') else 366 if biome in ('snow','sky') else 1
        self.fill(target,target.get_rect(),tile)
        if biome in ('cave','volcano','crystal','legendary_ruins','dragon_valley'):
            self.fill(target,target.get_rect(),657,atlas='cave')

    def path(self,target,rect,biome):
        if biome in ('cave','volcano','crystal','legendary_ruins','dragon_valley'):
            self.fill(target,rect,641,atlas='cave')
        else:
            self.fill(target,rect,261 if biome in ('desert','badlands') else 217)

    def tree(self,target,x,y,width=96):
        self.object(target,'tree',x,y,width)

    def rock(self,target,x,y,size=48):
        self.object(target,'rock',x,y,size)

    def building(self,target,kind,x,y,width=196):
        self.object(target,kind,x,y-16,width)
        self.fill(target,(x-22,y-24,44,24),217,22)

    def water(self,target,rect,kind='water'):
        rect=pg.Rect(rect)
        self.fill(target,rect,299)
        if kind in ('ice','lava'):
            wash=pg.Surface(rect.size,pg.SRCALPHA)
            wash.fill((207,243,255,160) if kind=='ice' else (241,87,33,185))
            target.blit(wash,rect)
        pg.draw.rect(target,(83,117,130),rect,3)

    def bridge(self,target,rect):
        self.fill(target,rect,355)
        pg.draw.rect(target,(128,112,73),rect,3)

    def gate(self,target,x,y,side,biome):
        # Keep openings and the original solid posts aligned; GBA posts/signs
        # mark the passage without painting an impassable wall across it.
        if side in ('east','west'):
            for yy in (y-70,y+58):target.blit(self.tile(237,32),(x-16,yy-16))
        else:
            for xx in (x-67,x+67):
                self.fill(target,(xx-15,y-70,30,90),237,30)
        target.blit(self.tile(3,28),(x-14,y-44))

    def walls(self,target,rects,biome):
        for rect in rects:
            if biome in ('mountain','cave','volcano','badlands'):
                self.fill(target,rect,120)
                continue
            rect=pg.Rect(rect);old=target.get_clip();target.set_clip(rect.clip(old))
            for y in range(rect.top,rect.bottom,48):
                for x in range(rect.left,rect.right,48):
                    self.tree(target,x+24,y+48,48)
            target.set_clip(old)

    def outdoors(self,target,scenery):
        self.ground(target,'meadow')
        scenery.local_overlay(target,'outdoors')
        # Door coordinates continue to line up with the game's interaction zones.
        self.object(target,'home',385,342,176)
        self.object(target,'restaurant',930,338,176)
        self.grid(target,[[234,235,235,235,235,235,235,236]],800,338,32)
        self.grid(target,[[234,235,235,235,235,235,235,236]],800,426,32)
        for x,y in ((112,340),(550,310),(708,270),(1120,360),(225,515),(365,640)):
            target.blit(self.tile(4,24),(x,y))
        self.grid(target,[[354,355,356]],264,581,32)

    def forest(self,target,scenery):
        self.ground(target,'forest');scenery.local_overlay(target,'forest')
        for x,y in ((260,500),(480,280),(820,590),(1110,330)):
            target.blit(self.tile(4,24),(x,y))

    def market(self,target,scenery):
        self.ground(target,'meadow')
        self.fill(target,(210,185,870,442),366)
        scenery.local_overlay(target,'market')
        for name,x,y in (('mart',417,332),('restaurant',906,332)):
            self.object(target,name,x,y,194)
        self.fill(target,(218,665,820,24),235,24)

    def interior(self,target,scene):
        if scene in ('center','restaurant','hotel'):
            target.blit(self.interiors[scene], (0, 0))
            return
        target.fill((29,48,52))
        atlas='generic_building_1'
        self.fill(target,(188,153,904,537),4,48,atlas)
        self.fill(target,(188,153,904,100),32,48,atlas)
        self.fill(target,(596,610,88,60),7,32,atlas)
        if scene=='house':
            self.grid(target,[[48,49,50,51,52,53]],204,195,48,atlas)
            self.grid(target,[[76,77],[84,85]],539,335,75,atlas)
            self.grid(target,[[75,78]],842,388,80,atlas)
        else:
            self.grid(target,[[24,25],[40,41]],284,216,88,atlas)
            self.grid(target,[[96,97,98,99]],804,227,60,atlas)
        for x in (730,1020):self.grid(target,[[71],[87]],x,250,32,atlas)

    @staticmethod
    def service_anchors(scene):
        """Pixel-space NPC, exit, and arrival points for the compiled GBA maps."""
        return {
            # Map origins and 4x GBA metatiles correspond to the exported rooms.
            'center': {'npc': (640, 260), 'exit': (640, 648), 'entry': (640, 580)},
            'restaurant': {'npc': (792, 540), 'exit': (576, 680), 'entry': (576, 610)},
            'hotel': {'npc': (448, 370), 'exit': (384, 680), 'entry': (384, 610)},
        }[scene]

    def arena(self,target,style):
        if style not in self.arenas:
            full=pg.Surface((1280,800))
            colors={
                'meadow':((132,192,214),(219,231,180),(100,143,81)),
                'water':((112,183,203),(183,217,197),(45,119,153)),
                'cave':((34,48,67),(65,78,87),(53,62,68)),
                'volcano':((57,43,50),(107,67,55),(58,54,57)),
                'sky':((104,179,216),(190,224,230),(140,186,197)),
            }
            sky,horizon,terrain=colors.get(style,colors['meadow'])
            for y in range(0,594,18):
                blend=y/594
                band=tuple(round(sky[i]*(1-blend)+horizon[i]*blend) for i in range(3))
                pg.draw.rect(full,band,(0,y,1280,18))
            # Distant ridges and sky/cloud silhouettes frame the battlefield.
            if style in ('meadow','water'):
                pg.draw.polygon(full,(83,131,102) if style=='meadow' else (83,155,168),
                                ((0,465),(115,382),(240,441),(400,354),(560,457),(730,370),
                                 (880,444),(1050,350),(1190,433),(1280,386),(1280,590),(0,590)))
                pg.draw.polygon(full,(116,155,107) if style=='meadow' else (96,176,171),
                                ((0,505),(180,424),(350,494),(535,415),(710,512),(925,433),
                                 (1100,492),(1280,420),(1280,590),(0,590)))
                for x in (150,465,820,1080):
                    pg.draw.ellipse(full,(225,239,222),(x,120+(x%3)*27,150,34))
                    pg.draw.ellipse(full,(225,239,222),(x+27,105+(x%3)*27,100,43))
            elif style in ('cave','volcano'):
                rock=(26,35,47) if style=='cave' else (42,37,44)
                pg.draw.polygon(full,rock,((0,0),(145,0),(245,170),(330,118),(425,275),
                                           (555,190),(650,310),(780,162),(890,252),(1010,118),
                                           (1130,222),(1220,70),(1280,96),(1280,520),(0,520)))
                for x in (150,365,830,1090):
                    pg.draw.polygon(full,(55,174,183) if style=='cave' else (224,86,51),
                                    ((x,300),(x+22,360),(x+12,412),(x-12,412),(x-21,360)))
                    pg.draw.polygon(full,(160,231,221) if style=='cave' else (255,171,65),
                                    ((x,318),(x+6,374),(x,395),(x-6,374)))
            else:
                for x,y in ((80,390),(340,300),(690,420),(1000,320),(1200,430)):
                    pg.draw.ellipse(full,(232,242,231),(x,y,190,37))
                    pg.draw.ellipse(full,(232,242,231),(x+34,y-22,106,58))
                pg.draw.polygon(full,(101,145,157),((0,540),(210,485),(365,534),(540,474),
                                (725,540),(910,476),(1100,530),(1280,485),(1280,594),(0,594)))
            floor_atlas='cave' if style in ('cave','volcano') else 'pallet_town'
            floor_tile=657 if floor_atlas=='cave' else 299 if style=='water' else 366 if style=='sky' else 1
            self.fill(full,(0,580,1280,220),floor_tile,atlas=floor_atlas)
            seam={'meadow':(115,153,82),'water':(137,219,217),'cave':(99,117,123),
                  'volcano':(231,99,50),'sky':(216,237,232)}.get(style,(115,153,82))
            pg.draw.line(full,seam,(0,594),(1280,594),7)
            if style=='water':
                for x in range(30,1280,128):
                    pg.draw.arc(full,(185,236,231),(x,577,82,31),.2,2.9,3)
            elif style=='volcano':
                for x in range(90,1280,290):
                    pg.draw.lines(full,(234,112,56),False,((x,625),(x+36,648),(x+19,677),(x+70,704)),4)
            self.arenas[style]=full
        target.blit(self.arenas[style],(0,0))
