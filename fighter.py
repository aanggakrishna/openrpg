"""Real-time fighter simulation: buffered jumps, telegraphs and aimed projectiles."""
import math
import pygame as pg
import retro
import pokemon_db
COLORS={'fire':(255,111,60),'water':(83,191,250),'grass':(117,230,113),'electric':(255,218,74),
        'ice':(166,239,255),'ground':(220,172,102),'rock':(190,159,110),'ghost':(174,128,240),
        'psychic':(249,126,201),'poison':(203,117,234),'flying':(161,219,246),'dark':(169,153,197),
        'fairy':(255,174,227),'steel':(192,213,230),'bug':(174,212,98),'dragon':(133,136,255)}
ARENA_TYPES={'meadow':({'grass','bug'},{'fire'}),'water':({'water','ice','electric'},{'fire','ground'}),
             'cave':({'ground','rock','steel'},{'water','grass'}),'sky':({'flying','electric','dragon'},{'ground','rock'})}
WEATHER_TYPES={'Cerah':({'fire','flying'},{'water'}),'Berawan':({'normal','bug','poison'},{'fire'}),
               'Hujan':({'water','electric'},{'fire'}),'Salju':({'ice'},{'fire','grass'}),
               'Badai':({'electric','flying'},{'ground'})}
WEATHER_EMOJI={'Cerah':'☀','Berawan':'☁','Hujan':'🌧','Salju':'❄','Badai':'⛈'}
EMOJI={'normal':'⭐','fire':'🔥','water':'💧','grass':'🍃','electric':'⚡','ice':'❄️','ground':'🪨',
       'rock':'🪨','ghost':'👻','psychic':'🔮','poison':'☠️','flying':'🌪️','dark':'🌙','fairy':'✨','steel':'⚙️','bug':'🐛','dragon':'🐉','fighting':'🥊'}
VARIANTS={'wood':'🪵','branch':'🪵','leaf':'🍃','seed':'🌱','vine':'🌿','solar':'☀️','rain':'🌧️',
          'storm':'⛈️','thunder':'⚡','blizzard':'🌨️','snow':'❄️','bubble':'🫧','surf':'🌊','wave':'🌊',
          'swift':'⭐','meteor':'☄️','moon':'🌙','web':'🕸️','wind':'🌪️','sand':'🏜️','mud':'🟤','petal':'🌸'}

def skill(move,ultimate=False):
    typ=move['type']['name']; name=move['name'];power=move.get('power') or 50
    status=move.get('damage_class',{}).get('name')=='status'
    melee=move.get('damage_class',{}).get('name')=='physical' and any(w in name for w in ('punch','kick','tackle','scratch','bite','slash','headbutt','claw','chop'))
    area=any(w in name for w in ('quake','surf','storm','blizzard','discharge','explosion'))
    beam=any(w in name for w in ('beam','flame','breath','pump'))
    emoji=next((v for k,v in VARIANTS.items() if k in name),EMOJI.get(typ,'💥'))
    return {'name':name.replace('-',' ').title(),'type':typ,'power':min(140,power),'accuracy':move.get('accuracy') or 100,
            'emoji':emoji,'style':'status' if status else 'area' if area else 'beam' if beam else 'melee' if melee else 'projectile',
            'range':150 if melee else 410 if area else 610 if beam else 750,
            'cooldown':12 if ultimate else round(1.4+power/65+(0.7 if area else 0),1),'ultimate':ultimate}

class FighterMixin:
    def update_battle(self,dt):
        super().update_battle(dt)
        if self.battle and self.battle.get('result'):
            self.update_shots(dt)

    def pokemon_data(self,ident):
        return super().pokemon_data(ident) or pokemon_db.detail(ident)

    def prepare_battle(self):
        super().prepare_battle()
        b=self.battle
        if not b:return
        b.setdefault('shots',[]);b.setdefault('impacts',[]);b.setdefault('cooldowns',{})
        b.setdefault('guard',100.0);b.setdefault('player_vx',0.0);b.setdefault('enemy_vy',0.0)
        b.setdefault('guard_break',0.0);b.setdefault('enemy_decision',.6)
        b['api_moves']=[m['name'] for m in pokemon_db.loadout(b['player_id'])[:2]]
        if b.get('player_max'):
            b['environment_mods']={
                str(b['player_id']):self.environment_modifiers(b['player_id']),
                str(b['wild_id']):self.environment_modifiers(b['wild_id']),
            }

    def environment_modifiers(self,ident):
        """Small, visible attack/defence shifts from stage affinity and weather."""
        data=self.pokemon_data(ident) or {}
        types={row.get('type',{}).get('name') for row in data.get('types',[])}
        favored,unfavored=ARENA_TYPES.get(self.battle.get('arena_style'),(set(),set()))
        weather_favored,weather_unfavored=WEATHER_TYPES.get(self.battle.get('battle_weather'),(set(),set()))
        attack=10 if types & favored else -7 if types & unfavored else 0
        attack+=10 if types & weather_favored else -8 if types & weather_unfavored else 0
        # Defense gets a smaller stage/weather affinity bonus; bad conditions
        # lower it so either fighter can show both buffs and debuffs.
        defense=6 if types & favored else -5 if types & unfavored else 0
        defense+=5 if types & weather_favored else -6 if types & weather_unfavored else 0
        return {'attack':max(-15,min(20,attack)), 'defense':max(-11,min(11,defense))}

    def skills_for(self,ident):
        if self.battle and ident in self.battle.get('copied_skills',{}):
            return self.battle['copied_skills'][ident]
        moves=pokemon_db.loadout(ident)
        if not moves:
            d=self.pokemon_data(ident) or {}
            moves=[self.pokedex.moves[e['move']['name']] for e in d.get('moves',[]) if e['move']['name'] in self.pokedex.moves and self.pokedex.moves[e['move']['name']].get('power')]
        if not moves:
            return []
        while len(moves)<3:moves=moves+[moves[-1]]
        return [skill(moves[0]),skill(moves[1]),skill(moves[2],True)]

    def random_battle_platforms(self):
        # A connected route: each ledge is within one regular jump of its neighbor.
        height=-58
        result=[]
        for index in range(8):
            if index:height=max(-194,min(-58,height+self.pokemon_rng.choice((-34,-34,0,34))))
            result.append({'x':150+index*138+self.pokemon_rng.randint(-12,12),
                           'width':self.pokemon_rng.randint(90,122),'height':height})
        return result

    def fighter_size(self,ident):
        height=(self.pokemon_data(ident) or {}).get('height',7)
        return int(max(48,min(98,48+math.sqrt(height)*9)))

    def skill_key(self,ident,slot):return f'{ident}:{slot}'

    def can_attack(self):
        b=self.battle
        return bool(b and 'wild_hp' in b and not any(b.get(k) for k in ('result','intro','capture','ultimate_cutin')) and not self.needs_depleted() and b.get('player_cooldown',0)<=0)

    def pokemon_attack(self,heavy=False):
        if not self.can_attack():return
        move={'name':'Strike','type':'fighting','power':30,'accuracy':100,'emoji':'🥊','style':'melee','range':113,'cooldown':.45,'ultimate':False}
        self.cast_move('player',move)
        self.battle['attack_flash']=.22
        self.battle['player_cooldown']=.45

    def pokemon_type_attack(self,slot=0):
        if not self.can_attack():return
        b=self.battle;moves=self.skills_for(b['player_id'])
        if not moves:return
        key=self.skill_key(b['player_id'],slot)
        if b['cooldowns'].get(key,0)>0:return
        move=moves[slot];b['cooldowns'][key]=move['cooldown'];b['player_cooldown']=.34
        self.cast_move('player',move)

    def pokemon_ultimate(self):
        if not self.can_attack():return
        b=self.battle;moves=self.skills_for(b['player_id'])
        if not moves or b.get('super_meter',0)<100 or b['cooldowns'].get(self.skill_key(b['player_id'],2),0)>0:return
        move=moves[2]
        b['super_meter']=0;b['player_cooldown']=.8
        b['cooldowns'][self.skill_key(b['player_id'],2)]=move['cooldown']
        b['ultimate_cutin']={'timer':1.0,'duration':1.0,'move_type':move['type'],'move_name':move['name'],
                            'emoji':move['emoji'],'pokemon_id':b['player_id'],'move':move}
        self.queue_pokemon_cry(b['player_id']);self.play_battle_sound('ultimate_charge',.65)

    def _resolve_ultimate(self,cutin):
        if self.battle and not self.battle.get('result'):self.cast_move('player',cutin['move'])

    def cast_move(self,owner,move):
        b=self.battle;target='enemy' if owner=='player' else 'player'
        source_id=b['player_id' if owner=='player' else 'wild_id']
        target_id=b['wild_id' if owner=='player' else 'player_id']
        x=b[owner+'_x'];y=606+b[owner+'_y']-self.fighter_size(source_id)*.5
        if move['style']=='status':
            self.apply_status(owner,move,source_id,target_id,x,y)
            return
        tx=b[target+'_x'];ty=606+b[target+'_y']-self.fighter_size(target_id)*.5
        length=max(1,math.hypot(tx-x,ty-y));speed=620 if move['style']=='beam' else 455
        shot=dict(move,owner=owner,x=x,y=y,sx=x,sy=y,vx=(tx-x)/length*speed,vy=(ty-y)/length*speed,
                  age=0,windup=.20 if owner=='player' else .42,travel=0,source_id=source_id,trail=[])
        b.setdefault('shots',[]).append(shot)
        b['phase']=move['name']
        self.play_type_sound(move['type'],move['ultimate'])
        if owner=='enemy':b['enemy_attack_flash']=.42
        else:b['attack_flash']=.20

    def apply_status(self,owner,move,source_id,target_id,x,y):
        b=self.battle;name=move['name'].lower()
        b['phase']=move['name']
        b.setdefault('impacts',[]).append({'x':x,'y':y,'timer':.35,'color':COLORS.get(move['type'],retro.GOLD),'emoji':move['emoji']})
        self.play_type_sound(move['type'],move['ultimate'])
        if name in ('transform','sketch'):
            copied=pokemon_db.loadout(target_id)
            if copied:
                b.setdefault('copied_skills',{})[source_id]=[skill(copied[0]),skill(copied[1]),skill(copied[2],True)]
                if name=='transform':b[owner+'_appearance']=target_id
        elif name=='teleport':
            b[owner+'_x']=max(65,min(1215,b[owner+'_x']+(-230 if b[owner+'_x']<640 else 230)))
        elif name in ('recover','purify','rest','heal pulse'):
            key='player_hp' if owner=='player' else 'wild_hp';maximum=b['player_max' if owner=='player' else 'wild_max']
            b[key]=min(maximum,b[key]+max(8,int(maximum*.2)))
            if owner=='player':self.life.pokemon_health[str(source_id)]=b[key]
        elif name!='splash':
            if owner=='player':b['guard']=min(100,b.get('guard',0)+35)
            else:b['enemy_guard_timer']=1.5
        if owner=='player':b['super_meter']=min(100,b['super_meter']+8)

    def physics(self,who,dt,axis,jump=False,hold=False,down=False):
        b=self.battle;ident=b['player_id' if who=='player' else 'wild_id']
        x=b[who+'_x'];y=b[who+'_y'];vy=b.get(who+'_vy',0)
        target_speed=axis*(240 if who=='player' else 175)
        vx=b.get(who+'_vx',0)
        acceleration=1600 if axis else 1900
        vx+=max(-acceleration*dt,min(acceleration*dt,target_speed-vx))
        x=max(55,min(1225,x+vx*dt))
        types={t['type']['name'] for t in (self.pokemon_data(ident) or {}).get('types',[])}
        can_dive='ground' in types or ('water' in types and b.get('arena_style')=='water')
        if who=='player' and y>=0 and (down and can_dive or y>0):
            b[who+'_x']=x;b[who+'_vx']=vx;b[who+'_vy']=0
            b[who+'_y']=min(26,y+80*dt) if down and can_dive else max(0,y-90*dt)
            return
        support=0 if y>=0 else next((p['height'] for p in b['platforms'] if abs(y-p['height'])<2 and abs(x-p['x'])<p['width']/2+5),None)
        grounded=support is not None and vy>=0 and not down
        b[who+'_coyote']=.1 if grounded else max(0,b.get(who+'_coyote',0)-dt)
        if jump and b[who+'_coyote']>0:
            vy=-610;grounded=False;b[who+'_coyote']=0
            if who=='player':b['jump_buffer']=0
        if grounded:vy=0;y=support
        else:
            gravity=1550 if vy>0 else 1280
            if not hold and vy< -230:vy=-230
            types={t['type']['name'] for t in (self.pokemon_data(ident) or {}).get('types',[])}
            if who=='player' and hold and 'flying' in types and b['super_meter']>0 and y< -35:
                vy=max(-170,vy-1600*dt);b['super_meter']=max(0,b['super_meter']-2*dt)
            else:vy=min(780,vy+gravity*dt)
            old=y;y+=vy*dt
            if vy>=0:
                surfaces=[0]+[p['height'] for p in b['platforms'] if abs(x-p['x'])<p['width']/2+5 and not down]
                crossed=[height for height in surfaces if old<=height<=y]
                if crossed:y=min(crossed);vy=0
            y=max(-315,min(0,y))
        b[who+'_x']=x;b[who+'_y']=y;b[who+'_vy']=vy;b[who+'_vx']=vx

    def update_fighter_sim(self,dt,keys):
        b=self.battle
        for timer in ('player_cooldown','special_cooldown','type_cooldown','enemy_cooldown','hit_flash','enemy_flash','block_flash','attack_flash','enemy_attack_flash','enemy_guard_timer','guard_break'):
            b[timer]=max(0,b.get(timer,0)-dt)
        for key in b['cooldowns']:b['cooldowns'][key]=max(0,b['cooldowns'][key]-dt)
        b['jump_buffer']=max(0,b.get('jump_buffer',0)-dt)
        guarding=(keys[pg.K_LSHIFT] or keys[pg.K_RSHIFT]) and b['guard']>0 and not b['guard_break']
        b['guarding']=guarding
        b['guard']=max(0,min(100,b['guard']+(-19 if guarding else 16)*dt))
        if b['guard']<=0:b['guard_break']=1.4
        axis=int(keys[pg.K_RIGHT])-int(keys[pg.K_LEFT])
        self.physics('player',dt,axis*.35 if guarding else axis,b.get('jump_buffer',0)>0,keys[pg.K_UP],keys[pg.K_DOWN])
        b['player_facing']=1 if b['enemy_x']>=b['player_x'] else -1
        b['enemy_decision']=max(0,b.get('enemy_decision',.5)-dt)
        if b['enemy_decision']==0:
            gap=abs(b['player_x']-b['enemy_x']);direction=1 if b['player_x']>b['enemy_x'] else -1
            action=self.pokemon_rng.choices(('approach','attack','guard','retreat','jump'),(5 if gap>400 else 1,6,2,1,1))[0]
            b['enemy_action']=action;b['enemy_decision']=self.pokemon_rng.uniform(.45,.95)
            b['enemy_axis']=direction if action=='approach' else -direction if action=='retreat' else 0
            if action=='guard':b['enemy_guard_timer']=.7
            if action=='attack' and b['enemy_cooldown']<=0:
                moves=self.skills_for(b['wild_id'])
                if moves:
                    move=self.pokemon_rng.choice(moves[:2])
                    if gap<=move['range']:
                        self.cast_move('enemy',move);b['enemy_cooldown']=self.pokemon_rng.uniform(1.3,2.2)
                    else:b['enemy_axis']=direction
        self.physics('enemy',dt,b.get('enemy_axis',0),b.get('enemy_action')=='jump',True)
        self.update_shots(dt)

    def update_shots(self,dt):
        b=self.battle;remaining=[]
        for shot in b.get('shots',[]):
            shot['age']+=dt
            if shot['age']<shot['windup']:
                remaining.append(shot);continue
            target='enemy' if shot['owner']=='player' else 'player'
            ident=b['wild_id' if target=='enemy' else 'player_id'];size=self.fighter_size(ident)
            rect=pg.Rect(b[target+'_x']-size*.35,606+b[target+'_y']-size,size*.7,size)
            old=(shot['x'],shot['y'])
            if shot['style']=='melee':
                direction=1 if shot['vx']>=0 else -1
                end=(shot['sx']+direction*shot['range'],shot['sy'])
                hit=bool(rect.clipline(old,end));shot['x'],shot['y']=end
                expired=True
            else:
                shot['trail'].append(old);shot['trail']=shot['trail'][-8:]
                shot['x']+=shot['vx']*dt;shot['y']+=shot['vy']*dt
                shot['travel']+=math.hypot(shot['vx'],shot['vy'])*dt
                radius=44 if shot['ultimate'] or shot['style']=='area' else 12
                hit=bool(rect.inflate(radius,radius).clipline(old,(shot['x'],shot['y'])))
                expired=shot['travel']>=shot['range'] or shot['age']>3.5
            if hit:
                self.apply_hit(shot,target)
                b['impacts'].append({'x':shot['x'],'y':shot['y'],'timer':.35,'color':COLORS.get(shot['type'],retro.GOLD),'emoji':shot['emoji']})
            elif not expired:remaining.append(shot)
            else:b['impacts'].append({'x':shot['x'],'y':shot['y'],'timer':.18,'color':retro.MUTED,'emoji':'💨'})
        b['shots']=remaining
        for impact in b['impacts']:impact['timer']-=dt
        b['impacts']=[i for i in b['impacts'] if i['timer']>0]

    def apply_hit(self,shot,target):
        b=self.battle
        if b.get('result'):return
        if self.pokemon_rng.random()*100>shot['accuracy']:
            b['phase']='MISS';return
        defending=b['guarding'] if target=='player' else b.get('enemy_guard_timer',0)>0
        ident=b['player_id' if target=='player' else 'wild_id']
        attacker=self.pokemon_data(shot['source_id']);defender=self.pokemon_data(ident)
        factor=pokemon_db.effectiveness(shot['type'],tuple(t['type']['name'] for t in (defender or {}).get('types',[])))
        power=shot['power'];damage=max(4,int(power*.16+self.base_stat(attacker,'special-attack',50)*.045-self.base_stat(defender,'special-defense',50)*.025))
        mods=b.get('environment_mods',{})
        attack_mod=mods.get(str(shot['source_id']),{}).get('attack',0)
        defense_mod=mods.get(str(ident),{}).get('defense',0)
        damage=int(damage*(1+attack_mod/100)/max(.5,1+defense_mod/100))
        damage=int(damage*factor)
        if shot['ultimate']:damage=int(damage*1.9)
        if defending:
            damage=int(damage*.25) if factor==0 else max(1,int(damage*.25));b['block_flash']=.22
            if target=='player':b['guard']=max(0,b['guard']-12)
        hpkey='player_hp' if target=='player' else 'wild_hp'
        b[hpkey]=max(0,b[hpkey]-damage)
        b['hit_flash' if target=='player' else 'enemy_flash']=.24
        b['super_meter']=min(100,b['super_meter']+(7 if target=='player' else 13))
        self.play_hit_cry(ident)
        b['phase']=('BLOCK ' if defending else '')+f'-{damage} HP'
        if target=='player':
            self.life.pokemon_health[str(ident)]=b['player_hp']
            if b['player_hp']<=0:
                living=[i for i in self.active_pokemon_team() if i!=ident and self.life.pokemon_health.get(str(i),0)>0]
                if living:self.switch_battle_pokemon(living[0],True)
                else:b['result']=self.words('Tim KO / Esc kembali','Team KO / Esc to return')
        elif b['wild_hp']<=0:self._win_battle()

    def draw_fight_vfx(self,b):
        for shot in b.get('shots',[]):
            color=COLORS.get(shot['type'],retro.GOLD)
            if shot['age']<shot['windup']:
                radius=int(10+shot['age']/shot['windup']*18)
                pg.draw.circle(self.canvas,color,(int(shot['sx']),int(shot['sy'])),radius,2)
                continue
            size=54 if shot['ultimate'] else 25
            if shot['style']=='beam':pg.draw.line(self.canvas,color,(shot['sx'],shot['sy']),(shot['x'],shot['y']),8 if shot['ultimate'] else 4)
            for i,(x,y) in enumerate(shot['trail']):
                pg.draw.circle(self.canvas,color,(int(x),int(y)),max(1,i//2))
            self.emoji(shot['emoji'],(shot['x'],shot['y']),size)
            if shot['style']=='area':
                for offset in (-35,35):self.emoji(shot['emoji'],(shot['x']+offset,shot['y']+math.sin(self.frame*.2+offset)*24),size//2)
        for impact in b.get('impacts',[]):
            p=1-impact['timer']/.35
            pg.draw.circle(self.canvas,impact['color'],(int(impact['x']),int(impact['y'])),max(2,int(12+p*35)),3)
            self.emoji(impact['emoji'],(impact['x'],impact['y']),int(25+p*20))

    def draw_pokemon_battle(self):
        super().draw_pokemon_battle()
        b=self.battle
        if not b or b.get('intro') or b.get('ultimate_cutin'):return
        for i,m in enumerate(self.skills_for(b['player_id'])):
            x=56+i*163;y=154
            self.box((x,y,153,77),retro.PANEL)
            self.emoji(m['emoji'],(x+23,y+23),23)
            cooldown=b.get('cooldowns',{}).get(self.skill_key(b['player_id'],i),0)
            self.text(('S','D','F')[i]+' / '+(f'{cooldown:.1f}s' if cooldown else f"{int(b.get('super_meter',0))}%" if i==2 and b.get('super_meter',0)<100 else 'READY'),x+44,y+13,retro.GOLD if not cooldown else retro.MUTED,self.tiny)
            label=m['name']
            if self.tiny.size(label)[0]>143:label=label[:19]
            self.text(label,x+7,y+44,retro.CREAM,self.tiny)
        self.text('GUARD',57,244,retro.MUTED,self.tiny)
        retro.meter(self.canvas,(113,246,180,9),b.get('guard',100),100,(108,194,246))
        for row,ident in enumerate(self.active_pokemon_team()):
            self.text(f"{row+1} / {(self.pokemon_data(ident) or {}).get('name',str(ident)).title()}  HP {self.life.pokemon_health.get(str(ident),0)}",57,685+row*23,retro.GREEN,self.small)

    def draw_ultimate_cutin(self,b,cutin):
        progress=1-cutin['timer']/cutin['duration'];accent=COLORS.get(cutin['move_type'],retro.GOLD)
        self.canvas.fill((9,14,32))
        for i in range(22):
            y=(i*51+(0 if self.life.reduced_motion else progress*500))%800
            pg.draw.line(self.canvas,accent,(0,y),(1280,y-160),2 if i%3 else 5)
        pg.draw.polygon(self.canvas,accent,[(0,225),(1280,115),(1280,550),(0,660)])
        pg.draw.polygon(self.canvas,(20,29,57),[(0,244),(1280,137),(1280,528),(0,638)])
        sprite=self.pokemon_surface(cutin['pokemon_id'],285)
        if sprite:
            slide=int(65*(1-min(1,progress*5))**3)
            self.canvas.blit(sprite,sprite.get_rect(center=(330-slide,417)))
        self.text('LIMIT BREAK',730,253,retro.GOLD,self.big,True)
        self.text((self.pokemon_data(cutin['pokemon_id']) or {}).get('name','Pokémon').upper(),730,326,retro.CREAM,self.medium,True)
        self.text(cutin['move_name'],740,395,accent,self.medium,True)
        self.emoji(cutin['emoji'],(1030,442),88)
        self.text('U L T I M A T E',740,486,retro.CREAM,self.font,True)
        pg.draw.rect(self.canvas,accent,(0,758,int(1280*progress),5))
