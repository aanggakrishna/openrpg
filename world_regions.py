"""Shared habitat, climate and solid geometry. No graphics dependency (also used by server)."""
from functools import lru_cache
import random

BIOMES = ('meadow','forest','desert','coast','swamp','cave','badlands','mountain',
          'volcano','snow','sky','crystal','ancient_forest','deepsea','dragon_valley','legendary_ruins')
# ground / path / stone / highlight / water; limited palettes preserve pixel-art readability.
PALETTES = {
 'meadow':((112,163,83),(205,177,118),(103,117,86),(201,217,144),(50,133,165)),
 'forest':((53,104,66),(147,126,84),(68,86,67),(139,176,94),(43,107,126)),
 'desert':((216,187,123),(233,207,151),(166,124,79),(249,227,177),(57,151,166)),
 'coast':((212,199,150),(238,218,174),(126,144,136),(249,238,191),(38,130,167)),
 'swamp':((66,99,75),(156,146,96),(68,91,84),(151,173,110),(48,99,103)),
 'cave':((64,70,85),(113,108,112),(68,76,94),(148,158,180),(51,95,139)),
 'badlands':((168,119,82),(213,164,108),(120,84,69),(231,185,122),(63,128,147)),
 'mountain':((126,147,136),(184,185,163),(86,106,121),(213,220,205),(69,138,166)),
 'volcano':((75, 60,64),(125,101,89),(61, 60,75),(178,129,98),(230, 90,41)),
 'snow':((211,227,225),(177,205,211),(115,147,164),(245,249,236),(78,145,178)),
 'sky':((130,178,162),(208,217,180),(118,150,164),(239,243,211),(92,160,196)),
 'crystal':((95,90,127),(146,137,163),(78,79,114),(192,183,224),(84,146,165)),
 'ancient_forest':((44,82,60),(129,117,78),(62,80,63),(134,159,86),(38,99, 90)),
 'deepsea':((51,105,131),(178,181,145),(65,106,131),(152,215,218),(29,83,130)),
 'dragon_valley':((121, 90,94),(176,139,112),(90,79,101),(216,166,138),(72,121,154)),
 'legendary_ruins':((109,108,137),(189,175,148),(83,88,117),(234,214,160),(92,137,171)),
}
# Auto weather never produces tropical snow or rain inside caves.
CLIMATES = {
 'meadow':(('Cerah','Berawan','Hujan'),(6,3,2)),
 'forest':(('Cerah','Berawan','Hujan'),(3,4,5)),
 'desert':(('Cerah','Berawan'),(9,1)),
 'coast':(('Cerah','Berawan','Hujan'),(6,2,3)),
 'swamp':(('Berawan','Hujan'),(4,6)),
 'cave':(('Cerah',),(1,)), 'badlands':(('Cerah','Berawan'),(8,2)),
 'mountain':(('Cerah','Berawan','Salju'),(3,4,3)),
 'volcano':(('Cerah','Berawan'),(7,3)), 'snow':(('Salju','Berawan','Cerah'),(8,2,1)),
 'sky':(('Cerah','Berawan'),(5,5)), 'crystal':(('Cerah',),(1,)),
 'ancient_forest':(('Berawan','Hujan','Cerah'),(5,4,1)),
 'deepsea':(('Cerah',),(1,)), 'dragon_valley':(('Berawan','Cerah','Hujan'),(5,3,2)),
 'legendary_ruins':(('Cerah','Berawan'),(6,4)),
}
HABITAT_TYPES = {
 'meadow':('normal','grass','fairy'), 'forest':('grass','bug','flying'),
 'desert':('ground','rock','fire'), 'coast':('water','flying'),
 'swamp':('water','poison','bug'), 'cave':('rock','ground','ghost','dark','steel'),
 'badlands':('ground','rock','fighting'), 'mountain':('rock','ice','fighting','electric'),
 'volcano':('fire','rock'), 'snow':('ice',), 'sky':('flying','electric'),
 'crystal':('psychic','steel','fairy','ghost'), 'ancient_forest':('grass','bug','fairy'),
 'deepsea':('water',), 'dragon_valley':('dragon',), 'legendary_ruins':('psychic','dragon','fairy','steel'),
}
DUNGEON_BIOMES=('cave','forest','swamp','badlands','snow','volcano','crystal','sky','dragon_valley','legendary_ruins')
SCENE_BIOMES={'outdoors':'meadow','market':'meadow','forest':'forest','coast':'coast','mountain':'mountain','house':'meadow','bedroom':'meadow'}

def biome_at(scene,x=0,y=0):
    if scene=='reserve':return BIOMES[max(0,min(3,int(y//1600)))*4+max(0,min(3,int(x//1280)))]
    return SCENE_BIOMES.get(scene,'meadow')

def weather_for(scene,x,y,day,hour,override=''):
    biome=biome_at(scene,x,y)
    return climate_at(biome,(day*24+hour)//3,override)

@lru_cache(maxsize=256)
def climate_at(biome,block,override=''):
    choices,weights=CLIMATES[biome]
    if override and override in choices:return override
    seed=block*97+BIOMES.index(biome)*31
    return random.Random(seed).choices(choices,weights=weights)[0]

def overlaps(a,b):
    return a[0]<b[0]+b[2] and a[0]+a[2]>b[0] and a[1]<b[1]+b[3] and a[1]+a[3]>b[1]

def contains(rect,x,y):return rect[0]<=x<rect[0]+rect[2] and rect[1]<=y<rect[1]+rect[3]

def gate_posts(x,y,side):
    if side in ('west','east'):return [(x-15,y-78,30,28),(x-15,y+50,30,28)]
    return [(x-78,y-20,28,40),(x+50,y-20,28,40)]

def border(w,top,bottom,openings):
    """Solid 40px masonry, with explicit 144px openings at entrances."""
    result=[]
    for side,lo,hi in [('north',0,w),('south',0,w),('west',top,bottom),('east',top,bottom)]:
        gaps=sorted((coord-76,coord+76) for s,coord in openings if s==side)
        cursor=lo
        for a,b in gaps+[(hi,hi)]:
            if a>cursor:
                if side=='north':result.append((cursor,top,a-cursor,40))
                elif side=='south':result.append((cursor,bottom-40,a-cursor,40))
                elif side=='west':result.append((0,cursor,40,a-cursor))
                else:result.append((w-40,cursor,40,a-cursor))
            cursor=max(cursor,b)
    return result

@lru_cache(maxsize=24)
def reserve_layout(index):
    biome=BIOMES[index];row,col=divmod(index,4)
    gates=[]
    for side,valid,x,y in [('west',col>0 or index==0,80,800),('east',col<3,1200,800),
                           ('north',row>0,640,220),('south',row<3,640,1500)]:
        if valid:gates.append((side,x,y))
    walls=border(1280,120,1600,[(s,y if s in ('west','east') else x) for s,x,y in gates])
    paths=[(596,155,88,1417),(28,756,1224,88),(222,1038,840,64),
           (222,800,56,270),(1002,800,56,270)]
    buildings=[('center',640,955),('restaurant',250,1070),('hotel',1030,1070)]
    if index==0:buildings.append(('center',160,690));paths.append((132,690,56,110))
    water=[];bridges=[];ice=[];lava=[]
    if biome in ('meadow','forest','ancient_forest','swamp','desert','coast','deepsea'):
        water=[(140,300,300,240),(830,1190,280,220)]
        if biome in ('coast','deepsea','swamp'):water += [(865,290,250,300),(160,1190,290,200)]
        # A timber bridge divides the collision rectangles: its deck is walkable.
        water[0:1]=[(140,300,300,96),(140,452,300,88)]
        bridges=[(120,396,340,56)]
    if biome in ('snow','mountain'):ice=[(145,300,300,230),(850,1220,270,185)]
    if biome=='volcano':lava=[(135,300,310,210),(845,295,275,280),(185,1210,260,230)]
    if biome in ('cave','crystal','dragon_valley','legendary_ruins'):water=[(150,1220,285,185)]
    if biome=='sky':water=[(110,300,350,250),(820,300,335,250),(160,1220,260,200)]
    # Broken cliff shelves make rocky regions distinct and create side passages.
    if biome in ('cave','badlands','mountain','dragon_valley','legendary_ruins'):
        walls += [(140,290,300,64),(140,354,64,240),(865,350,280,64),(1081,414,64,175)]
    if biome=='crystal':walls += [(180,300,240,48),(860,430,260,48)]
    def shoreline(rect):
        x,y,w,h=rect
        return [(x+24,y,w-48,24),(x,y+24,w,h-48),(x+24,y+h-24,w-48,24)]
    water=[r for area in water for r in shoreline(area)]
    lava=[r for area in lava for r in shoreline(area)]
    ice=[r for area in ice for r in shoreline(area)]
    solids=walls+water+lava
    for kind,x,y in buildings:solids.append((x-100,y-140,200,114))
    for side,x,y in gates:solids+=gate_posts(x,y,side)
    props=[];rng=random.Random(8081+index*103)
    leafy=biome in ('meadow','forest','swamp','ancient_forest','snow','mountain','coast')
    count=54 if biome in ('forest','ancient_forest') else 32
    for _ in range(count*8):
        if len(props)>=count:break
        x=rng.randrange(85,1195);y=rng.randrange(280,1470)
        footprint=(x-23,y-20,46,32)
        visual=(x-55,y-105,110,116)
        # Never decorate the route, bridge landing, service apron, or an entrance.
        exclusions=paths+bridges+ice+[(x-125,y-155,250,220) for _,x,y in buildings]
        if any(overlaps(visual,r) for r in exclusions) or any(overlaps(footprint,r) for r in solids):continue
        if any(abs(x-p[1])<95 and abs(y-p[2])<100 for p in props):continue
        kind='tree' if leafy and rng.random()<.8 else 'rock'
        if biome in ('crystal','legendary_ruins'):kind='crystal' if rng.random()<.6 else 'pillar'
        if biome=='desert':kind='cactus' if rng.random()<.65 else 'rock'
        if biome=='volcano':kind='rock'
        props.append((kind,x,y,rng.randrange(4)))
        solids.append(footprint)
    if biome in ('forest','ancient_forest','swamp'):
        for x in range(95,1200,85):
            if 540<x<740:continue
            for y in (205,1572):
                props.append(('tree',x,y,1));solids.append((x-23,y-20,46,32))
    return dict(biome=biome,paths=paths,walls=walls,water=water,bridges=bridges,ice=ice,lava=lava,
                gates=gates,buildings=buildings,props=props,solids=solids)

@lru_cache(maxsize=24)
def reserve_solids(index):
    ox=(index%4)*1280;oy=(index//4)*1600
    return tuple((x+ox,y+oy,w,h) for x,y,w,h in reserve_layout(index)['solids'])

@lru_cache(maxsize=16)
def scene_layout(scene):
    biome=SCENE_BIOMES.get(scene,'meadow');gates=[];water=[];ice=[];lava=[];bridges=[];paths=[];props=[]
    if scene=='outdoors':
        gates=[('west',60,405),('east',1220,405),('north',640,180)]
        paths=[(0,373,1280,64),(610,155,60,250)]
        # A single pond with a boardwalk crossing; draw and collide against the
        # same stepped shoreline so the old atlas pond cannot peek through.
        water=[(930,477,288,91),(930,624,288,44)]
        bridges=[(930,568,288,56)]
    elif scene=='forest':
        gates=[('east',1220,405),('north',650,177)]
        paths=[(0,373,1280,64),(618,155,64,420)]
        water=[(90,470,125,110),(1040,505,125,110)]
        props=[('rock',270,301,0),('rock',742,262,1),('rock',931,534,2),('rock',447,620,3)]
    elif scene=='market':
        gates=[('west',60,405)];paths=[(0,373,1280,64),(610,405,66,245)]
        water=[(80,540,90,70)]
    elif scene=='coast':
        gates=[('west',60,410)];paths=[(0,380,570,60),(260,475,815,60),(490,420,80,90)]
        water=[(580,205,610,230),(620,570,490,72)]
        props=[('rock',420,270,0),('rock',440,550,1),('rock',1140,500,2)]
    elif scene=='mountain':
        gates=[('south',640,640)];paths=[(610,175,60,489),(260,530,790,60)]
        ice=[(90,320,180,155),(950,290,190,130)]
        props=[('tree',350,260,0),('tree',790,270,1),('tree',1135,500,2)]
    walls=border(1280,135,710,[(s,y if s in ('east','west') else x) for s,x,y in gates])
    solids=walls+water+lava
    solids += [(x-23,y-20,46,32) for _,x,y,_ in props]
    for s,x,y in gates:solids+=gate_posts(x,y,s)
    return dict(biome=biome,gates=gates,paths=paths,walls=walls,water=water,ice=ice,
                lava=lava,bridges=bridges,props=props,solids=solids)

@lru_cache(maxsize=16)
def online_solids(room):
    width=3200 if room=='hall' else 1280
    walls=[(0,190,width,45),(0,640,width,60),(0,190,40,510),(width-40,190,40,510)]
    if room=='gym':return tuple(walls+[(425,305,28,120),(1000,305,28,120),(135,245,225,55)])
    if room=='hall':return tuple(walls+[(x-78,235,28,95) for x in range(300,3100,280)]+[(x+50,235,28,95) for x in range(300,3100,280)])
    return tuple(walls+[(130,245,230,55),(1050,340,100, 90)])

def online_step(room,x,y,dx,dy,dt):
    length=max(1,(dx*dx+dy*dy)**.5);speed=220*min(dt,.1)/length
    for axis,delta in ((0,dx*speed),(1,dy*speed)):
        nx=x+delta if axis==0 else x;ny=y+delta if axis==1 else y
        if not any(overlaps((nx-12,ny-12,24,14),r) for r in online_solids(room)):x,y=nx,ny
    return max(55,min(3150 if room=='hall' else 1220,x)),max(247,min(620,y))
