"""Shared habitat, climate and solid geometry. No graphics dependency (also used by server)."""
from functools import lru_cache
import random

BIOMES = ('meadow','forest','desert','coast','swamp','cave','badlands','mountain',
          'volcano','snow','sky','crystal','ancient_forest','deepsea','dragon_valley','legendary_ruins')
# The original 4x4 sanctuary keeps its exact world coordinates for existing
# saves. The remaining country-themed spaces fill the eastern columns and the
# southern row. Coordinates are (column, row) in the 1280x1600 zone grid.
RESERVE_COLUMNS, RESERVE_ROWS = 10, 5
RESERVE_GRID_POSITIONS = ([(c, r) for r in range(4) for c in range(4)] +
                          [(c, r) for r in range(4) for c in range(4, 10)] +
                          [(c, 4) for c in range(10)])
RESERVE_ZONE_BIOMES = list(BIOMES) + [
 'forest','ancient_forest','cave','coast','snow','mountain','desert','swamp',
 'forest','badlands','coast','snow','volcano','desert','mountain','forest',
 'swamp','deepsea','crystal','mountain','forest','desert','snow','coast',
 'cave','ancient_forest','dragon_valley','badlands','coast','forest','snow','mountain',
 'desert','dragon_valley'
]
RESERVE_GRID_TO_INDEX = {pos: index for index, pos in enumerate(RESERVE_GRID_POSITIONS)}

# Country spaces share the same world grid as the sanctuary, but each gets a
# distinct, readable landmark.  These keys are consumed by Scenery so gameplay
# geometry stays independent from visual decoration.
COUNTRY_LANDMARKS = {
    16: ('rice_terrace', 'Teras Sawah'), 17: ('torii', 'Gerbang Torii'),
    18: ('pagoda', 'Pagoda Bambu'), 19: ('temple', 'Kuil Monsun'),
    20: ('pyramid', 'Piramida Giza'), 21: ('acropolis', 'Akropolis'),
    22: ('colosseum', 'Colosseum'), 23: ('eiffel', 'Menara Eiffel'),
    24: ('castle', 'Kastel Dataran Tinggi'), 25: ('stave_church', 'Gereja Fjord'),
    26: ('geyser', 'Geyser Aurora'), 27: ('acacia', 'Pohon Akasia'),
    28: ('mountain_peak', 'Puncak Kilimanjaro'), 29: ('baobab', 'Pohon Baobab'),
    30: ('statue', 'Patung Penjaga Amazon'), 31: ('ruins', 'Reruntuhan Andes'),
    32: ('cenote', 'Cenote'), 33: ('maple_cabin', 'Pondok Maple'),
    34: ('redwood', 'Redwood Raksasa'), 35: ('uluru', 'Batu Uluru'),
    36: ('meeting_house', 'Rumah Māori'), 37: ('balloons', 'Balon Cappadocia'),
    38: ('kasbah', 'Kasbah Atlas'), 39: ('stupa', 'Stupa Himalaya'),
    40: ('thai_temple', 'Kuil Teratai'), 41: ('island_huts', 'Rumah Panggung'),
    42: ('palace', 'Istana Korea'), 43: ('chalet', 'Chalet Alpen'),
    44: ('windmill', 'Kincir Angin'), 45: ('table_mountain', 'Table Mountain'),
    46: ('iceberg', 'Gunung Es Aurora'), 47: ('lighthouse', 'Mercusuar Azores'),
    48: ('observatory', 'Observatorium Atacama'), 49: ('glacier', 'Gletser Patagonia'),
}

def reserve_index_at(x, y):
    col = max(0, min(RESERVE_COLUMNS - 1, int(x // 1280)))
    row = max(0, min(RESERVE_ROWS - 1, int(y // 1600)))
    return RESERVE_GRID_TO_INDEX.get((col, row), 0)
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
SCENE_BIOMES={'outdoors':'meadow','market':'meadow','forest':'forest','coast':'coast','mountain':'mountain','house':'meadow','bedroom':'meadow','dungeon_hub':'crystal','local_dungeon':'cave'}

def biome_at(scene,x=0,y=0):
    if scene=='reserve':return RESERVE_ZONE_BIOMES[reserve_index_at(x,y)]
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

@lru_cache(maxsize=64)
def reserve_layout(index):
    biome=RESERVE_ZONE_BIOMES[index];col,row=RESERVE_GRID_POSITIONS[index]
    landmark=COUNTRY_LANDMARKS.get(index)
    neighbors = RESERVE_GRID_TO_INDEX
    gates=[]
    for side,dc,dr,x,y in [('west',-1,0,80,800),('east',1,0,1200,800),
                           ('north',0,-1,640,220),('south',0,1,640,1500)]:
        if (col+dc,row+dr) in neighbors or (index==0 and side=='west'):
            gates.append((side,x,y))
    walls=border(1280,120,1600,[(s,y if s in ('west','east') else x) for s,x,y in gates])
    # Every gate opens onto one continuous local junction at (640, 800). Each
    # zone then grows its own service street from that junction. That keeps all
    # 50 maps connected at their shared borders while varying the village plan.
    presets=((360,610,72),(420,410,68),(860,430,76),(880,1130,68),
             (390,1130,76),(640,420,64),(640,1130,80),(360,850,68),
             (920,850,76),(480,535,72))
    hub_x,hub_y,road_w=presets[index%len(presets)]
    if index==0:hub_x,hub_y,road_w=360,625,76
    junction=(640,800)
    def road_between(a,b,width=road_w):
        x1,y1=a;x2,y2=b;result=[]
        if x1!=x2:result.append((min(x1,x2),y1-width//2,abs(x2-x1),width))
        if y1!=y2:result.append((x2-width//2,min(y1,y2),width,abs(y2-y1)))
        return result
    paths=[]
    for side,x,y in gates:
        paths.extend(road_between((x,y),junction))
    # Town square and service lane form an L-shaped, walkable cluster whose
    # location changes by biome and zone instead of repeating one template.
    # Place the service street well away from the central gate junction. The
    # building sprites are much taller than their collision footprints, so a
    # nearby hotel can visually crowd (or physically block) the exit approach.
    service_y=hub_y+550 if hub_y<=800 else max(400,hub_y-530)
    paths.extend(road_between(junction,(hub_x,hub_y+18)))
    service_path_y=min(hub_y+14,service_y-road_w//2)
    paths.extend([(hub_x-road_w//2,service_path_y,road_w,abs(service_y-hub_y)+24),
                  (hub_x-310,service_y-road_w//2,620,road_w)])
    # Alternate between a compact plaza, a loop street, and a second garden
    # lane. These are branches of the same connected road network.
    if index%3==1:
        for side_x in (hub_x-205,hub_x+205):
            paths.append((side_x-road_w//2,min(800,service_y),road_w,abs(service_y-800)+road_w//2))
            paths.append((min(side_x,hub_x)-road_w//2,service_y-road_w//2,
                          abs(hub_x-side_x)+road_w,road_w))
    elif index%3==2:
        spur_x=hub_x+(205 if index%2 else -205)
        paths.extend(road_between((hub_x,service_y),(spur_x,service_y+145),road_w-8))
        paths.append((spur_x-90,service_y+145-road_w//2,180,road_w-8))
    restaurant_x,hotel_x=((hub_x-260,hub_x+260) if index%2==0 else
                          (hub_x+260,hub_x-260))
    buildings=[('center',hub_x,hub_y),('restaurant',restaurant_x,service_y),
               ('hotel',hotel_x,service_y)]
    water=[];bridges=[];ice=[];lava=[];landmark_rect=None
    # Pool sites are selected away from roads, buildings and the landmark, so
    # bridges and shore paths never cover service entrances or gate approaches.
    pool_candidates=[(165,260,220,150),(895,350,220,150),(165,1260,220,150),
                     (895,1260,220,150),(190,570,190,145),(900,570,190,145)]
    rng=random.Random(8100+index)
    rng.shuffle(pool_candidates)
    building_clear=[(x-118,y-158,236,270) for _,x,y in buildings]
    for candidate in pool_candidates:
        if len(water)+len(ice)+len(lava)>= (3 if biome in ('coast','deepsea','swamp','sky') else 2):break
        exclusion=paths+building_clear
        if any(overlaps(candidate,r) for r in exclusion):continue
        if any(overlaps(candidate,r) for r in water+ice+lava):continue
        if biome in ('snow','mountain'):ice.append(candidate)
        elif biome=='volcano':lava.append(candidate)
        elif biome in ('meadow','forest','ancient_forest','swamp','desert','coast','deepsea','cave','crystal','dragon_valley','legendary_ruins','sky'):
            water.append(candidate)
    # Broken cliff shelves make rocky regions distinct and create side passages.
    if biome in ('cave','badlands','mountain','dragon_valley','legendary_ruins'):
        walls += [(135,285,250,54),(135,339,54,205),(895,310,250,54),(1091,364,54,190)]
    if biome=='crystal':walls += [(170,300,230,46),(880,440,230,46)]
    def shoreline(rect):
        x,y,w,h=rect
        return [(x+24,y,w-48,24),(x,y+24,w,h-48),(x+24,y+h-24,w-48,24)]
    water=[r for area in water for r in shoreline(area)]
    lava=[r for area in lava for r in shoreline(area)]
    ice=[r for area in ice for r in shoreline(area)]
    if landmark:
        candidates=[(960,430),(320,430),(960,1220),(320,1220),(980,880),(300,880),
                    (820,300),(460,1320)]
        for lx,ly in candidates[index%len(candidates):]+candidates[:index%len(candidates)]:
            candidate=(lx-82,ly-142,164,152)
            if any(overlaps(candidate,r) for r in paths+building_clear+water+ice+lava+walls):continue
            landmark_rect=candidate
            break
        if landmark_rect is None:landmark_rect=(960,548,152,104)
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
        if landmark_rect: exclusions.append(landmark_rect)
        if any(overlaps(visual,r) for r in exclusions) or any(overlaps(footprint,r) for r in solids):continue
        if any(abs(x-p[1])<95 and abs(y-p[2])<100 for p in props):continue
        kind='tree' if leafy and rng.random()<.8 else 'rock'
        if biome in ('crystal','legendary_ruins'):kind='crystal' if rng.random()<.6 else 'pillar'
        if biome=='desert':kind='cactus' if rng.random()<.65 else 'rock'
        if biome=='volcano':kind='rock'
        props.append((kind,x,y,rng.randrange(4)))
        solids.append(footprint)
    if landmark:
        lx,ly=landmark_rect[0]+82,landmark_rect[1]+142
        # The landmark is a proper solid prop: trainers and Pokémon cannot
        # walk through it, while the front remains visible as an attraction.
        props.append(('landmark',lx,ly,index))
        solids.append((lx-54,ly-24,108,30))
    if biome in ('forest','ancient_forest','swamp'):
        for x in range(95,1200,85):
            if 540<x<740:continue
            for y in (205,1572):
                props.append(('tree',x,y,1));solids.append((x-23,y-20,46,32))
    return dict(biome=biome,paths=paths,walls=walls,water=water,bridges=bridges,ice=ice,lava=lava,
                gates=gates,buildings=buildings,props=props,solids=solids,
                service_hub=(hub_x,hub_y),road_style=index%3,landmark_rect=landmark_rect)

@lru_cache(maxsize=64)
def reserve_solids(index):
    col,row=RESERVE_GRID_POSITIONS[index];ox=col*1280;oy=row*1600
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
    elif scene=='dungeon_hub':
        paths=[(90,365,1100,150),(580,240,120,310)]
        props=[('rock',360,302,0),('crystal',920,300,0),('rock',370,585,1),('crystal',920,585,1)]
    elif scene=='local_dungeon':
        paths=[(260,355,760,200),(580,225,120,210)]
        props=[('rock',300,290,0),('rock',980,295,1),('crystal',310,590,0),('rock',970,580,2)]
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
