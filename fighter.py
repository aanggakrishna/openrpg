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
from combat_rules import EMOJI, VARIANTS, skill, fighter_loadout

# Skills leave a short-lived tactical mark on the stage.  The marks are
# deliberately local and expire after seven seconds, so real-time movement
# remains important instead of turning every battle into a permanent hazard.
ARENA_MARKS={
    'fire': ('🔥', 'RUMPUT TERBAKAR', 'burn'),
    'water': ('💧', 'GENANGAN AIR', 'water'),
    'electric': ('⚡', 'AIR TERSETRUM', 'charged'),
    'ground': ('🪨', 'DINDING BATU', 'wall'),
    'rock': ('🪨', 'DINDING BATU', 'wall'),
    'grass': ('🌿', 'SEMAK PERLINDUNGAN', 'bush'),
    'ice': ('❄️', 'LANTAI ES', 'ice'),
    'flying': ('🌪️', 'ARUS ANGIN', 'gust'),
}

class FighterMixin:
    def update_battle(self,dt):
        b=self.battle
        if b and b.get('matchup_tip_timer',0)>0:
            b['matchup_tip_timer']=max(0,b['matchup_tip_timer']-dt)
        if b and b.get('ko_anim'):
            ko=b['ko_anim'];ko['timer']=max(0,ko['timer']-dt)
            for impact in b.get('impacts',[]):impact['timer']=max(0,impact['timer']-dt)
            b['impacts']=[impact for impact in b.get('impacts',[]) if impact['timer']>0]
            if ko['timer']<=0:
                b.pop('ko_anim',None)
                if ko.get('next_pokemon') is not None and not b.get('result'):
                    self.switch_battle_pokemon(ko['next_pokemon'],True)
                elif (ko.get('owner')=='player' and b.get('result')
                      and (b.get('trainer') or {}).get('rocket_event')
                      and b.get('player_hp',0)<=0 and not b.get('rocket_win_cutin')):
                    b['rocket_win_cutin']={'timer':2.35,'duration':2.35}
            return
        super().update_battle(dt)
        if self.battle:
            for key in ('fruit_speed_timer', 'fruit_double_timer'):
                self.battle[key] = max(0.0, self.battle.get(key, 0.0) - dt)
        if self.battle and self.battle.get('result'):
            self.update_shots(dt)

    def pokemon_data(self,ident):
        if ident is None:
            return None
        return super().pokemon_data(ident) or pokemon_db.detail(ident)

    def prepare_battle(self):
        super().prepare_battle()
        b=self.battle
        if not b:return
        b.setdefault('shots',[]);b.setdefault('impacts',[]);b.setdefault('cooldowns',[])
        # Old saves and interrupted battles can carry a list or a dict.  The
        # cooldown table must be a dict before combat starts.
        if not isinstance(b['cooldowns'],dict): b['cooldowns']={}
        b.setdefault('arena_effects',[]);b.setdefault('arena_combo','')
        b.setdefault('guard',100.0);b.setdefault('player_vx',0.0);b.setdefault('enemy_vy',0.0)
        b.setdefault('guard_break',0.0);b.setdefault('enemy_decision',.6)
        b.setdefault('player_stun_timer',0.0);b.setdefault('enemy_stun_timer',0.0)
        b['api_moves']=[m['name'] for m in pokemon_db.loadout(b['player_id'])[:3]]
        b['matchup_tip']=self.matchup_tips(b['player_id'],b['wild_id'])
        b['matchup_tip_timer']=5.8 if b['matchup_tip'] else 0.0
        self.refresh_battle_difficulty()
        if b.get('player_max'):
            b['environment_mods']={
                str(b['player_id']):self.environment_modifiers(b['player_id']),
                str(b['wild_id']):self.environment_modifiers(b['wild_id']),
            }

    def matchup_tips(self,attacker_id,defender_id):
        """Give a short, offline-only reminder based on the real type chart."""
        defender=self.pokemon_data(defender_id) or {}
        attacker=self.pokemon_data(attacker_id) or {}
        defense=tuple(t.get('type',{}).get('name','normal') for t in defender.get('types',[]))
        target=defender.get('name','opponent').title()
        result=[]
        for move in pokemon_db.loadout(attacker_id):
            attack_type=move['type']['name']
            factor=pokemon_db.effectiveness(attack_type,defense)
            label=f"{attack_type.title()} → {target}: ×{factor:g}"
            if factor>=2:
                result.append((0,EMOJI.get(attack_type,'✨'),self.words(f"Kuat · {label}",f"Strong · {label}")))
            elif factor==0:
                result.append((1,EMOJI.get(attack_type,'✨'),self.words(f"Tak mempan · {label}",f"No effect · {label}")))
            elif factor<=.5:
                result.append((2,EMOJI.get(attack_type,'✨'),self.words(f"Ditahan · {label}",f"Resisted · {label}")))
        if not result:
            for move in pokemon_db.loadout(defender_id):
                attack_type=move['type']['name']
                factor=pokemon_db.effectiveness(attack_type,
                    tuple(t.get('type',{}).get('name','normal') for t in attacker.get('types',[])))
                if factor>=2:
                    result.append((3,EMOJI.get(attack_type,'✨'),self.words(
                        f"Waspada · serangan {attack_type.title()} lawan ×{factor:g}",
                        f"Watch out · enemy {attack_type.title()} move ×{factor:g}")))
                    break
        if not result:
            for move in pokemon_db.loadout(attacker_id):
                attack_type=move['type']['name']
                factor=pokemon_db.effectiveness(attack_type,defense)
                if factor==1:
                    result.append((4,EMOJI.get(attack_type,'✨'),self.words(
                        f"Netral · {attack_type.title()} → {target}: ×1",
                        f"Neutral · {attack_type.title()} → {target}: ×1")))
                    break
        if not result:
            result.append((5,'✨',self.words('Kuat ×2 · ditahan ×½ · kebal ×0',
                                             'Strong ×2 · resisted ×½ · immune ×0')))
        result.sort(key=lambda item:item[0])
        return [(emoji,text) for _,emoji,text in result[:2]]

    def refresh_battle_difficulty(self):
        b=self.battle
        if not b:return
        player_level=self.pokemon_level(int(b['player_id']))
        enemy_level=max(1,int(b.get('wild_level',5)))
        gap=enemy_level-player_level
        b['level_gap']=gap
        if gap<=-10:label=self.words('MUDAH','EASY')
        elif gap<=7:label=self.words('SEIMBANG','BALANCED')
        elif gap<=17:label=self.words('SULIT','HARD')
        else:label=self.words('ELITE','ELITE')
        b['difficulty_label']=label
        # Wild encounters explicitly store trainer=None, so normalize optional
        # encounter records before inspecting their metadata.
        trainer=b.get('trainer') or {}
        wild=b.get('wild') or {}
        if trainer.get('local_dungeon'):
            tier=max(1,int(b.get('dungeon_tier',1)))
            boss=bool(b.get('dungeon_is_boss'))
            b['enemy_power_factor']=min(1.85,(1.38+tier*.018) if not boss else (1.62+tier*.025))
            b['enemy_reflex_factor']=min(1.55,(1.08+tier*.018) if not boss else (1.22+tier*.025))
            b['difficulty_label']=self.words('BOSS · SANGAT SULIT','BOSS · VERY HARD') if boss else self.words('DUNGEON · SULIT','DUNGEON · HARD')
        elif wild.get('is_boss'):
            b['enemy_power_factor']=1.68
            b['enemy_reflex_factor']=1.28
            b['difficulty_label']=self.words('BOSS · SANGAT SULIT','BOSS · VERY HARD')
        else:
            b['enemy_power_factor']=max(.8,min(1.28,1+gap*.006))
            b['enemy_reflex_factor']=max(.62,min(1.28,1+gap*.009))

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
        return fighter_loadout(moves)[0]

    def ultimate_for(self,ident):
        moves=pokemon_db.loadout(ident)
        if moves:
            detail=self.pokemon_data(ident) or {}
            native_types=[row.get('type',{}).get('name') for row in detail.get('types',[])]
            # The third regular skill is often a coverage move (frequently
            # Normal), which made many unrelated Pokémon show the same star
            # ultimate. Use the strongest real STAB move for the Pokémon's
            # own type(s), favoring its primary type when powers are close.
            move_options, generated_ultimate=fighter_loadout(moves)
            candidates=[move for move in move_options if move.get('type') in native_types]
            if candidates:
                primary=native_types[0] if native_types else None
                move=max(candidates,key=lambda item:(item.get('power',0)+(8 if item.get('type')==primary else 0)))
            else:
                move=generated_ultimate
            ultimate=dict(move)
            ultimate.update(style='beam',range=1100,cooldown=12.0,ultimate=True,
                            power=min(150,max(100,int(ultimate['power']*1.25))))
            return ultimate
        skills=self.skills_for(ident)
        return dict(skills[-1],style='beam',range=1100,cooldown=12.0,ultimate=True,
                    power=min(150,max(100,int(skills[-1]['power']*1.25)))) if skills else None

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
        # PokéAPI height is in decimetres. Scale proportionally with soft
        # bounds so tiny and enormous species read differently without
        # becoming invisible or covering the whole arena.
        height_dm=(self.pokemon_data(ident) or {}).get('height',10)
        height_m=max(.1,float(height_dm)/10)
        return int(round(max(44,min(112,68*height_m**.42))))

    def activate_arena_effect(self, shot, target):
        """Create a 7 second stage effect after an elemental skill connects."""
        b=self.battle
        if not b or shot.get('type') not in ARENA_MARKS or shot.get('arena_marked'):
            return
        shot['arena_marked']=True
        move_type=shot['type']; emoji,label,kind=ARENA_MARKS[move_type]
        owner=shot['owner']
        # Grass is placed around its caster to make a usable hiding spot;
        # every other mark forms where the hit landed.
        if kind=='bush':
            x=b[owner+'_x']; y=b.get(owner+'_y',0)
        else:
            x=b[target+'_x']; y=b.get(target+'_y',0)
        effects=b.setdefault('arena_effects',[])
        combo=''
        water=next((effect for effect in effects if effect.get('kind') in ('water','charged') and effect.get('timer',0)>0),None)
        fire=next((effect for effect in effects if effect.get('kind')=='burn' and effect.get('timer',0)>0),None)
        if move_type=='electric' and water:
            kind,label,emoji='charged','AIR TERSETRUM','⚡'
            x,y=water['x'],water['y']; combo='💧 + ⚡  AIR TERSETRUM!'
            water['timer']=0
        elif move_type=='ice' and water:
            kind,label,emoji='ice','AIR MEMBEKU','🧊'
            x,y=water['x'],water['y']; combo='💧 + ❄️  LANTAI ES!'
            water['timer']=0
        elif move_type=='flying' and fire:
            kind,label,emoji='wildfire','API MENYEBAR','🔥'
            x,y=fire['x'],fire['y']; combo='🔥 + 🌪️  API MENYEBAR!'
            fire['timer']=0
        elif move_type=='fire' and any(effect.get('kind')=='bush' and effect.get('timer',0)>0 for effect in effects):
            kind,label,emoji='wildfire','SEMAK TERBAKAR','🔥'
            combo='🌿 + 🔥  SEMAK TERBAKAR!'
        effect={'type':move_type,'kind':kind,'label':label,'emoji':emoji,'owner':owner,
                'x':float(x),'y':float(y),'timer':7.0,'duration':7.0,'tick':1.0,
                'radius':165 if kind in ('burn','wildfire','charged') else 128}
        effects[:] = [entry for entry in effects if entry.get('timer',0)>0 and entry.get('kind')!=kind]
        effects.append(effect)
        # Keep the scene legible on small displays: at most three marks can
        # coexist.  The newest effect always wins if the stage is crowded.
        if len(effects)>3: del effects[:-3]
        b['arena_combo']=combo
        b['arena_combo_timer']=2.4 if combo else 0
        b['phase']=combo or f'{emoji} {label} · 7 dtk'
        if kind=='gust':
            direction=1 if owner=='player' else -1
            b[target+'_x']=max(55,min(1225,b[target+'_x']+direction*105))

    def update_arena_effects(self,dt):
        b=self.battle
        if not b:return
        b['arena_combo_timer']=max(0.0,b.get('arena_combo_timer',0)-dt)
        active=[]
        for effect in b.get('arena_effects',[]):
            effect['timer']-=dt; effect['tick']-=dt
            if effect['timer']<=0: continue
            if effect['kind'] in ('burn','wildfire','charged') and effect['tick']<=0:
                effect['tick']+=1.0
                for target in ('player','enemy'):
                    distance=math.hypot(b[target+'_x']-effect['x'],b.get(target+'_y',0)-effect['y'])
                    if distance>effect['radius']: continue
                    # The caster is also endangered by their own fire and
                    # electric water, so positioning has real consequences.
                    damage=3 if effect['kind']=='charged' else 2
                    hpkey='player_hp' if target=='player' else 'wild_hp'
                    b[hpkey]=max(0,b[hpkey]-damage)
                    b['hit_flash' if target=='player' else 'enemy_flash']=.14
                    if target=='player': self.save_battle_player_hp()
                    if b[hpkey]<=0 and not b.get('ko_anim'):
                        ident=b['player_id'] if target=='player' else b['wild_id']
                        b['ko_anim']={'owner':target,'pokemon_id':ident,'timer':.82 if target=='player' else 1.0,
                                      'duration':.82 if target=='player' else 1.0,'next_pokemon':None}
                        b['shots']=[]
                        if target=='enemy': self._win_battle()
                        else: b['result']=self.words('Tim KO / Esc kembali','Team KO / Esc to return')
            active.append(effect)
        b['arena_effects']=active

    def draw_arena_effects(self,b,ground=606):
        """Render stage marks behind fighters, with a timer and clear icon."""
        for effect in b.get('arena_effects',[]):
            x=int(effect['x']); y=int(ground+effect.get('y',0))
            radius=int(effect.get('radius',128)*(0.76+0.24*min(1,effect['timer'])))
            kind=effect['kind']; color=COLORS.get(effect.get('type'),retro.GOLD)
            overlay=pg.Surface((radius*2+12,72),pg.SRCALPHA)
            if kind in ('water','charged','ice'):
                fill=(70,163,231,105) if kind!='ice' else (197,239,255,120)
                pg.draw.ellipse(overlay,fill,(6,19,radius*2,43))
                for index in range(4):
                    yy=30+index*8
                    pg.draw.arc(overlay,(224,250,255,185),(18+index*13,yy,radius*2-36,16),.2,2.7,2)
                if kind=='charged':
                    for index in range(5):
                        px=24+index*(radius*2-44)//4
                        pg.draw.line(overlay,(255,234,90,225),(px,24),(px-8,54),3)
            elif kind in ('burn','wildfire'):
                pg.draw.ellipse(overlay,(229,78,43,72),(6,24,radius*2,36))
                for index in range(7):
                    px=18+index*(radius*2-28)//6; height=18+(index%3)*9
                    pg.draw.polygon(overlay,(255,161,56,210),[(px,57),(px+8,57),(px+4,57-height)])
            elif kind=='wall':
                pg.draw.rect(overlay,(112,105,100,240),(radius-22,5,44,62))
                for yy in range(11,64,16): pg.draw.line(overlay,(177,167,148,220),(radius-19,yy),(radius+19,yy),3)
            elif kind=='bush':
                for index in range(6):
                    px=18+index*(radius*2-36)//5
                    pg.draw.circle(overlay,(74,152+(index%2)*22,78,225),(px,48-(index%3)*8),20)
            elif kind=='gust':
                for index in range(4):
                    yy=20+index*13
                    pg.draw.arc(overlay,(206,242,255,190),(16,yy,radius*2-30,18),.2,2.8,3)
            self.canvas.blit(overlay,(x-radius-6,y-64))
            if effect['timer']>0:
                self.emoji(effect['emoji'],(x,y-82),26)
                self.text(f"{effect['timer']:.0f}s",x,y-108,retro.CREAM,self.tiny,True)

    def fighter_speed(self,ident,who='player'):
        detail=self.pokemon_data(ident) or {}
        speed=(self.battle_stat(who, 'speed', 70) if self.battle and
               ident == self.battle.get('wild_id' if who == 'enemy' else 'player_id') else
               next((int(row.get('base_stat',70)) for row in detail.get('stats',[])
                     if row.get('stat',{}).get('name')=='speed'),70))
        base=206 if who=='player' else 166
        result=max(125,min(270,base+(speed-70)*.52))
        if who=='player' and self.battle and self.battle.get('fruit_speed_timer',0)>0:
            result*=1.35
        return result

    def spawn_jump_dust(self,who,ident,floor_y):
        b=self.battle
        if not b or self.life.reduced_motion:return
        detail=self.pokemon_data(ident) or {}
        weight_kg=max(.1,float(detail.get('weight',100))/10)
        count=3+min(10,int(math.log10(weight_kg+1)*3.2))
        rng=self.pokemon_rng
        for _ in range(count):
            b.setdefault('dust_particles',[]).append({
                'x':b[who+'_x']+rng.uniform(-14,14),'y':606+floor_y+rng.uniform(-2,2),
                'vx':rng.uniform(-62,62),'vy':rng.uniform(-105,-32),
                'ttl':rng.uniform(.22,.48),'duration':.48,
                'size':rng.uniform(3.5,6.5)+min(3,math.log10(weight_kg+1)*.7)})

    def skill_key(self,ident,slot):return f'{ident}:{slot}'

    def can_attack(self):
        b=self.battle
        return bool(b and 'wild_hp' in b and not any(b.get(k) for k in ('result','intro','capture','ultimate_cutin','boss_intro','boss_evolution','ko_anim')) and not self.needs_depleted() and b.get('player_stun_timer',0)<=0 and b.get('player_cooldown',0)<=0)

    def boss_evolution_target(self, pokemon_id):
        """Return a real next-stage species from the bundled Pokédex chain."""
        species = self.pokedex.species.get(int(pokemon_id)) or pokemon_db.species(int(pokemon_id))
        if not species:
            return None
        chain_url = species.get('evolution_chain', {}).get('url', '')
        try:
            chain_id = int(chain_url.rstrip('/').split('/')[-1])
        except (AttributeError, TypeError, ValueError):
            return None
        chain = self.pokedex.evolution.get(chain_id) or pokemon_db.evolution(chain_id)
        if not chain:
            return None

        def locate(link):
            try:
                current_id = int(link.get('species', {}).get('url', '').rstrip('/').split('/')[-1])
            except (TypeError, ValueError, AttributeError):
                current_id = -1
            if current_id == int(pokemon_id):
                return link
            for child in link.get('evolves_to', []):
                found = locate(child)
                if found:
                    return found
            return None

        node = locate(chain.get('chain', {}))
        children = (node or {}).get('evolves_to', [])
        options = []
        for child in children:
            try:
                ident = int(child['species']['url'].rstrip('/').split('/')[-1])
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            if 1 <= ident <= 1025 and ident != int(pokemon_id):
                options.append((ident, child['species'].get('name', f'Pokémon #{ident}')))
        return self.pokemon_rng.choice(options) if options else None

    def trigger_boss_evolution(self):
        """Give a boss one chance to evolve at critical HP, restoring its phase."""
        b = self.battle
        if not b or b.get('boss_phase_checked') or b.get('wild_max', 0) <= 0:
            return False
        is_boss = bool(b.get('dungeon_is_boss') or (b.get('wild') or {}).get('is_boss'))
        if not is_boss or b.get('wild_hp', 0) / b['wild_max'] > .25:
            return False
        b['boss_phase_checked'] = True
        if self.pokemon_rng.random() >= .58:
            b['phase'] = self.words('Boss bertahan di fase terakhirnya!', 'The boss holds its final form!')
            return False
        evolved = self.boss_evolution_target(b['wild_id'])
        if not evolved:
            b['phase'] = self.words('Boss mengerahkan kekuatan terakhirnya!', 'The boss unleashes its final strength!')
            return False
        old_id, new_id = b['wild_id'], int(evolved[0])
        b['wild_id'] = new_id
        if isinstance(b.get('wild'), dict):
            b['wild']['id'] = new_id
        b['wild_level'] = min(100, int(b.get('wild_level', 5)) + 5)
        b['boss_phase'] = 2
        b['boss_evolved'] = True
        b['boss_evolution'] = {'from': old_id, 'to': new_id, 'name': evolved[1],
                               'timer': 3.2, 'duration': 3.2}
        b.pop('wild_appearance', None)
        b['enemy_x'], b['enemy_y'] = 930.0, 0.0
        b['enemy_vx'], b['enemy_vy'] = 0.0, 0.0
        b['enemy_cooldown'], b['enemy_ai_timer'] = 1.0, .45
        b['enemy_guard_timer'], b['enemy_stun_timer'] = 0.0, 0.0
        b['shots'] = []
        self.pokedex.request(new_id)
        self.pokedex.request_animation(new_id)
        self.pokedex.request_cry(new_id)
        self.prepare_battle()
        b['wild_hp'] = b['wild_max']
        b['enemy_stat_multiplier'] = min(2.25, b.get('enemy_stat_multiplier', 1.0) * 1.15)
        b['wild_max'] = max(1, round(b['wild_max'] * 1.15))
        b['wild_hp'] = b['wild_max']
        b['enemy_power_factor'] = min(2.0, b.get('enemy_power_factor', 1.0) * 1.12)
        b['phase'] = self.words('FASE 2 · Boss berevolusi dan pulih penuh!',
                                'PHASE 2 · The boss evolved and fully recovered!')
        b.setdefault('impacts', []).append({'x': b['enemy_x'], 'y': b.get('enemy_y', 0),
                                            'timer': .75, 'duration': .75,
                                            'color': retro.GOLD, 'emoji': '✨'})
        self.queue_pokemon_cry(new_id)
        return True

    def pokemon_attack(self,heavy=False):
        if not self.can_attack():return
        move={'name':'Strike','type':'fighting','power':30,'accuracy':100,'emoji':'🥊','style':'melee','range':78,'cooldown':.45,'ultimate':False}
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
        move=self.ultimate_for(b['player_id'])
        if not move or b.get('super_meter',0)<100 or b['cooldowns'].get(self.skill_key(b['player_id'],'ultimate'),0)>0:return
        b['super_meter']=0;b['player_cooldown']=.8
        b['cooldowns'][self.skill_key(b['player_id'],'ultimate')]=move['cooldown']
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
        length=max(1,math.hypot(tx-x,ty-y));speed=1320 if move.get('ultimate') else 700 if move.get('stun_chance') else 455
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
                b.setdefault('copied_skills',{})[source_id]=fighter_loadout(copied)[0]
                if name=='transform':b[owner+'_appearance']=target_id
        elif name=='teleport':
            b[owner+'_x']=max(65,min(1215,b[owner+'_x']+(-230 if b[owner+'_x']<640 else 230)))
        elif name in ('recover','purify','rest','heal pulse'):
            key='player_hp' if owner=='player' else 'wild_hp';maximum=b['player_max' if owner=='player' else 'wild_max']
            b[key]=min(maximum,b[key]+max(8,int(maximum*.2)))
            if owner=='player':self.save_battle_player_hp()
        elif name!='splash':
            if owner=='player':b['guard']=min(100,b.get('guard',0)+35)
            else:b['enemy_guard_timer']=1.5
        if owner=='player':b['super_meter']=min(100,b['super_meter']+8)

    def physics(self,who,dt,axis,jump=False,hold=False,down=False):
        b=self.battle;ident=b['player_id' if who=='player' else 'wild_id']
        x=b[who+'_x'];y=b[who+'_y'];vy=b.get(who+'_vy',0)
        target_speed=axis*self.fighter_speed(ident,who)
        vx=b.get(who+'_vx',0)
        acceleration=1600 if axis else 1900
        for effect in b.get('arena_effects',[]):
            if math.hypot(x-effect['x'],y-effect.get('y',0)) > effect.get('radius',128):
                continue
            if effect['kind'] in ('water','charged'):
                target_speed*=.62
            elif effect['kind']=='ice':
                # Ice keeps momentum, so changing direction takes longer.
                acceleration=min(acceleration,430)
        vx+=max(-acceleration*dt,min(acceleration*dt,target_speed-vx))
        x=max(55,min(1225,x+vx*dt))
        for effect in b.get('arena_effects',[]):
            if effect['kind']=='wall' and effect.get('owner')!=who and abs(x-effect['x'])<34:
                x=b[who+'_x'];vx=0
                break
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
            weight_kg=max(.1,float((self.pokemon_data(ident) or {}).get('weight',100))/10)
            jump_scale=max(.82,min(1.08,1.08-math.log10(weight_kg+1)*.075))
            vy=-610*jump_scale;grounded=False
            self.spawn_jump_dust(who,ident,0 if support is None else support)
            b[who+'_coyote']=0
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
                if crossed:
                    y=min(crossed);vy=0
                    self.spawn_jump_dust(who,ident,y)
            y=max(-315,min(0,y))
        b[who+'_x']=x;b[who+'_y']=y;b[who+'_vy']=vy;b[who+'_vx']=vx

    def update_fighter_sim(self,dt,keys):
        b=self.battle
        for timer in ('player_cooldown','special_cooldown','type_cooldown','enemy_cooldown','hit_flash','enemy_flash','block_flash','attack_flash','enemy_attack_flash','enemy_guard_timer','guard_break','player_stun_timer','enemy_stun_timer'):
            b[timer]=max(0,b.get(timer,0)-dt)
        dust=[]
        for puff in b.setdefault('dust_particles',[]):
            puff['ttl']-=dt
            puff['x']+=puff['vx']*dt;puff['y']+=puff['vy']*dt
            puff['vy']+=125*dt
            if puff['ttl']>0:dust.append(puff)
        b['dust_particles']=dust
        self.update_arena_effects(dt)
        if b.get('ko_anim') or b.get('result'):
            return
        for key in b['cooldowns']:b['cooldowns'][key]=max(0,b['cooldowns'][key]-dt)
        b['jump_buffer']=max(0,b.get('jump_buffer',0)-dt)
        guarding=keys[pg.K_s] and b['guard']>0 and not b['guard_break'] and b['player_stun_timer']<=0
        b['guarding']=guarding
        b['guard']=max(0,min(100,b['guard']+(-19 if guarding else 16)*dt))
        if b['guard']<=0:b['guard_break']=1.4
        axis=int(keys[pg.K_RIGHT])-int(keys[pg.K_LEFT])
        if b['player_stun_timer']>0:axis=0
        self.physics('player',dt,axis*.35 if guarding else axis,b.get('jump_buffer',0)>0 and b['player_stun_timer']<=0,keys[pg.K_UP] and b['player_stun_timer']<=0,keys[pg.K_DOWN])
        b['player_facing']=1 if b['enemy_x']>=b['player_x'] else -1
        b['enemy_decision']=max(0,b.get('enemy_decision',.5)-dt)
        if b['enemy_decision']==0 and b['enemy_stun_timer']<=0:
            gap=abs(b['player_x']-b['enemy_x']);direction=1 if b['player_x']>b['enemy_x'] else -1
            level_gap=b.get('level_gap',0)
            attack_weight=max(3,min(10,6+level_gap*.12))
            guard_weight=max(1,min(4,2-level_gap*.06))
            action=self.pokemon_rng.choices(('approach','attack','guard','retreat','jump'),
                (5 if gap>400 else 1,attack_weight,guard_weight,1,1))[0]
            b['enemy_action']=action
            low=max(.3,min(.85,.7-level_gap*.009));high=max(low+.16,min(1.15,1.02-level_gap*.01))
            b['enemy_decision']=self.pokemon_rng.uniform(low,high)/b.get('enemy_reflex_factor',1)
            b['enemy_axis']=direction if action=='approach' else -direction if action=='retreat' else 0
            if action=='guard':b['enemy_guard_timer']=.7
            if action=='attack' and b['enemy_cooldown']<=0:
                moves=self.skills_for(b['wild_id'])
                if moves:
                    move=self.pokemon_rng.choice(moves)
                    if gap<=move['range']:
                        self.cast_move('enemy',move)
                        cooldown_scale=max(.68,min(1.22,1-(level_gap*.009)))
                        b['enemy_cooldown']=self.pokemon_rng.uniform(1.3,2.2)*cooldown_scale
                    else:b['enemy_axis']=direction
        self.physics('enemy',dt,0 if b['enemy_stun_timer']>0 else b.get('enemy_axis',0),b.get('enemy_action')=='jump' and b['enemy_stun_timer']<=0,True)
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
                direction_length=max(1,math.hypot(shot['vx'],shot['vy']))
                end=(shot['sx']+shot['vx']/direction_length*shot['range'],
                     shot['sy']+shot['vy']/direction_length*shot['range'])
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
                landed=self.apply_hit(shot,target)
                duration=.72 if shot.get('ultimate') and landed else .35
                b['impacts'].append({'x':shot['x'],'y':shot['y'],'timer':duration,'duration':duration,
                                     'ultimate':bool(shot.get('ultimate') and landed),'type':shot['type'],
                                     'color':COLORS.get(shot['type'],retro.GOLD),'emoji':shot['emoji']})
                if shot.get('ultimate') and landed:
                    self.play_ultimate_impact(shot['type'])
                if b.get('ko_anim'):
                    remaining.clear()
                    break
            elif not expired:remaining.append(shot)
            else:b['impacts'].append({'x':shot['x'],'y':shot['y'],'timer':.18,'color':retro.MUTED,'emoji':'💨'})
        b['shots']=remaining
        for impact in b['impacts']:impact['timer']-=dt
        b['impacts']=[i for i in b['impacts'] if i['timer']>0]

    def apply_hit(self,shot,target):
        b=self.battle
        if b.get('result'):return False
        if self.pokemon_rng.random()*100>shot['accuracy']:
            b['phase']='MISS';return False
        defending=b['guarding'] if target=='player' else b.get('enemy_guard_timer',0)>0
        ident=b['player_id' if target=='player' else 'wild_id']
        attacker=self.pokemon_data(shot['source_id']);defender=self.pokemon_data(ident)
        factor=pokemon_db.effectiveness(shot['type'],tuple(t['type']['name'] for t in (defender or {}).get('types',[])))
        attacker_side='enemy' if shot['owner']=='enemy' else 'player'
        defender_side='player' if target=='player' else 'enemy'
        attack_stat='attack' if shot.get('damage_class')=='physical' else 'special-attack'
        defense_stat='defense' if shot.get('damage_class')=='physical' else 'special-defense'
        power=shot['power'];damage=max(4,int(power*.16+self.battle_stat(attacker_side,attack_stat,50)*.045-self.battle_stat(defender_side,defense_stat,50)*.025))
        attacker_level=(int(b.get('wild_level',5)) if shot['source_id']==b.get('wild_id') else self.pokemon_level(int(shot['source_id'])))
        defender_level=(int(b.get('wild_level',5)) if ident==b.get('wild_id') else self.pokemon_level(int(ident)))
        level_factor=max(.8,min(1.35,1+(attacker_level-defender_level)*.009))
        damage=int(damage*level_factor)
        if target=='player':damage=int(damage*b.get('enemy_power_factor',1))
        elif shot['owner']=='player' and b.get('fruit_double_timer',0)>0:
            damage*=2
        mods=b.get('environment_mods',{})
        attack_mod=mods.get(str(shot['source_id']),{}).get('attack',0)
        defense_mod=mods.get(str(ident),{}).get('defense',0)
        damage=int(damage*(1+attack_mod/100)/max(.5,1+defense_mod/100))
        damage=int(damage*factor)
        if factor == 0:
            b['phase']=self.words('TIDAK MEMPAN','NO EFFECT')
            return True
        if target=='player' and getattr(self.life,'godmode',False):
            b['phase']='GOD MODE · serangan ditahan' if self.life.language=='id' else 'GOD MODE · attack blocked'
            b['impacts'].append({'x':b['player_x'],'y':b.get('player_y',0),'timer':.35,
                                 'color':retro.GOLD,'emoji':'🛡️'})
            b['block_flash']=.28
            return True
        if shot['ultimate']:damage=int(damage*1.9)
        # A grass-created bush hides its owner while they stay within it.
        sheltered=any(effect.get('kind')=='bush' and effect.get('owner')==target
                      and math.hypot(b[target+'_x']-effect['x'],b.get(target+'_y',0)-effect.get('y',0))<=effect.get('radius',128)
                      for effect in b.get('arena_effects',[]))
        if sheltered: damage=max(1,int(damage*.72))
        if defending:
            damage=max(1,int(damage*(.40 if shot.get('ultimate') else .15)));b['block_flash']=.22
            if target=='player':b['guard']=max(0,b['guard']-12)
        hpkey='player_hp' if target=='player' else 'wild_hp'
        b[hpkey]=max(0,b[hpkey]-damage)
        b['hit_flash' if target=='player' else 'enemy_flash']=.24
        b['super_meter']=min(100,b['super_meter']+(7 if target=='player' else 13))
        stunned=False
        if shot.get('stun_chance') and not defending and self.pokemon_rng.random()<shot['stun_chance']:
            b[target+'_stun_timer']=self.pokemon_rng.uniform(1.0,3.0)
            stunned=True
        self.play_hit_cry(ident)
        b['phase']=('STUN! ' if stunned else 'BLOCK ' if defending else '')+f'-{damage} HP'
        self.activate_arena_effect(shot,target)
        if target=='player':
            self.save_battle_player_hp()
            if b['player_hp']<=0:
                living=[i for i in self.active_pokemon_team() if i!=ident and self.life.pokemon_health.get(str(i),0)>0]
                b['ko_anim']={'owner':'player','pokemon_id':ident,'timer':.82,'duration':.82,
                              'next_pokemon':living[0] if living else None}
                b['shots']=[]
                name=(self.pokemon_data(ident) or {}).get('name','Pokémon').title()
                b['phase']=self.words(f'{name} tumbang!',f'{name} fainted!')
                if not living:b['result']=self.words('Tim KO / Esc kembali','Team KO / Esc to return')
        elif self.trigger_boss_evolution():
            return True
        elif b['wild_hp']<=0:
            b['ko_anim']={'owner':'enemy','pokemon_id':ident,'timer':1.0,'duration':1.0,'next_pokemon':None}
            b['shots']=[]
            self._win_battle()
        return True

    def draw_fight_vfx(self,b):
        for shot in b.get('shots',[]):
            color=COLORS.get(shot['type'],retro.GOLD)
            if shot['age']<shot['windup']:
                radius=int(10+shot['age']/shot['windup']*18)
                pg.draw.circle(self.canvas,color,(int(shot['sx']),int(shot['sy'])),radius,2)
                continue
            # Large moves look physically large: move power and ultimate
            # status both scale the emoji/projectile rather than using one
            # fixed icon size for every attack.
            power=max(20,int(shot.get('power',50)))
            size=int(26+min(46,power*.32))
            if shot['ultimate']: size=max(92,int(size*1.65))
            if shot['style']=='beam':
                pg.draw.line(self.canvas,(255,248,220),(shot['sx'],shot['sy']),(shot['x'],shot['y']),20 if shot['ultimate'] else 4)
                pg.draw.line(self.canvas,color,(shot['sx'],shot['sy']),(shot['x'],shot['y']),12 if shot['ultimate'] else 4)
            for i,(x,y) in enumerate(shot['trail']):
                pg.draw.circle(self.canvas,color,(int(x),int(y)),max(1,i//2))
            self.emoji(shot['emoji'],(shot['x'],shot['y']),size)
            if shot.get('stun_chance'):self.emoji('❔',(shot['x'],shot['y']-20),20)
            if shot['style']=='area':
                for offset in (-35,35):self.emoji(shot['emoji'],(shot['x']+offset,shot['y']+math.sin(self.frame*.2+offset)*24),size//2)
        for impact in b.get('impacts',[]):
            p=1-impact['timer']/max(.01,impact.get('duration',.35));center=(int(impact['x']),int(impact['y']))
            if impact.get('ultimate'):
                radius=24+int(160*p)
                pg.draw.circle(self.canvas,impact['color'],center,radius,7)
                pg.draw.circle(self.canvas,(255,246,203),center,max(8,radius//2),4)
                for index in range(12):
                    angle=index*math.tau/12+p*.7;inner=radius*.72;outer=radius+38
                    pg.draw.line(self.canvas,impact['color'],
                                 (int(center[0]+math.cos(angle)*inner),int(center[1]+math.sin(angle)*inner)),
                                 (int(center[0]+math.cos(angle)*outer),int(center[1]+math.sin(angle)*outer)),6)
                self.emoji(impact['emoji'],center,int(62+38*math.sin(p*math.pi)))
            else:
                pg.draw.circle(self.canvas,impact['color'],center,max(2,int(12+p*35)),3)
                self.emoji(impact['emoji'],center,int(25+p*20))
    def draw_pokemon_battle(self):
        b=self.battle
        if not b:return
        super().draw_pokemon_battle()
        if b.get('boss_evolution'):
            self.draw_boss_evolution(b,b['boss_evolution'])
            return
        if b.get('intro') or b.get('ultimate_cutin') or b.get('boss_intro'):return
        for i,m in enumerate(self.skills_for(b['player_id'])):
            x=56+i*163;y=154
            self.box((x,y,153,77),retro.PANEL)
            self.emoji(m['emoji'],(x+23,y+23),23)
            cooldown=b.get('cooldowns',{}).get(self.skill_key(b['player_id'],i),0)
            self.text(('Q','W','E')[i]+' / '+(f'{cooldown:.1f}s' if cooldown else 'READY'),x+44,y+13,retro.GOLD if not cooldown else retro.MUTED,self.tiny)
            label=m['name']
            if self.tiny.size(label)[0]>143:label=label[:19]
            self.text(label,x+7,y+44,retro.CREAM,self.tiny)
        ult_cooldown=b.get('cooldowns',{}).get(self.skill_key(b['player_id'],'ultimate'),0)
        self.text('R / '+(f'{ult_cooldown:.1f}s' if ult_cooldown else f"ULT {int(b.get('super_meter',0))}%"),544,244,retro.GOLD if not ult_cooldown and b.get('super_meter',0)>=100 else retro.MUTED,self.tiny)
        self.text('S GUARD',57,244,retro.MUTED,self.tiny)
        retro.meter(self.canvas,(113,246,180,9),b.get('guard',100),100,(108,194,246))
        for row,ident in enumerate(self.active_pokemon_team()):
            self.text(f"{row+1} / {(self.pokemon_data(ident) or {}).get('name',str(ident)).title()}  HP {self.life.pokemon_health.get(str(ident),0)}",57,685+row*23,retro.GREEN,self.small)

    def draw_boss_evolution(self,b,animation):
        """Cinematic mid-fight evolution with a clean full-health phase reset."""
        elapsed=animation['duration']-animation['timer']
        old_id,new_id=animation['from'],animation['to']
        detail=self.pokemon_data(new_id) or {}
        types=[row.get('type',{}).get('name') for row in detail.get('types',[])]
        accent=COLORS.get(types[0],retro.GOLD) if types else retro.GOLD
        self.canvas.fill((12,15,34))
        for index in range(16):
            angle=index*math.tau/16+elapsed*.42
            reach=1200 if index%2 else 900
            start=(640+math.cos(angle)*90,390+math.sin(angle)*42)
            end=(640+math.cos(angle)*reach,390+math.sin(angle)*reach*.55)
            pg.draw.line(self.canvas,(36,43,71),start,end,3)
        veil=pg.Surface((1280,800),pg.SRCALPHA);veil.fill((*accent,42));self.canvas.blit(veil,(0,0))
        self.text(self.words('EVOLUSI BOSS','BOSS EVOLUTION'),640,130,retro.GOLD,self.big,True)
        self.text(self.words('FASE 2 · HP DIPULIHKAN','PHASE 2 · HP RESTORED'),640,184,retro.CREAM,self.small,True)
        old_sprite=self.pokemon_surface(old_id,245)
        new_sprite=self.pokemon_surface(new_id,270)
        reveal=max(0.0,min(1.0,(elapsed-1.55)/.95))
        if reveal<1 and old_sprite:
            spin=(elapsed*850)%360
            old_sprite=pg.transform.rotozoom(old_sprite,spin,.82+.18*math.sin(elapsed*10)**2)
            self.canvas.blit(old_sprite,old_sprite.get_rect(center=(640,412)))
        if reveal>0 and new_sprite:
            alpha=int(255*min(1,reveal*2))
            new_sprite=new_sprite.copy();new_sprite.set_alpha(alpha)
            new_sprite=pg.transform.rotozoom(new_sprite,(1-reveal)*180,.45+.55*reveal)
            self.canvas.blit(new_sprite,new_sprite.get_rect(center=(640,412)))
        old_name=(self.pokemon_data(old_id) or {}).get('name','Pokémon').title()
        self.text(f"{old_name}  →  {animation.get('name',detail.get('name','Pokémon')).title()}",
                  640,585,retro.CREAM,self.medium,True)
        self.text(self.words('BOSS RECOVER PENUH · LEBIH KUAT','BOSS FULLY HEALED · POWER INCREASED'),
                  640,635,accent,self.small,True)

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
