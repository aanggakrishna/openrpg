"""Authoritative 20 Hz battles; no display, audio or client supplied damage."""
import math
import secrets
from collections import deque
import random
import pokemon_db
from combat_rules import skill


def creature(ident, level, boss=False):
    data = pokemon_db.detail(ident) or {}
    stats = {s['stat']['name']: s['base_stat'] for s in data.get('stats', [])}
    hp = int((40 + stats.get('hp', 50) * .65 + level * 3) * (2.5 if boss else 1))
    moves = pokemon_db.loadout(ident)
    return dict(id=ident, name=data.get('name', str(ident)).title(), level=level, hp=hp, maximum=hp,
                attack=stats.get('attack', 50) + level * 2, defense=stats.get('defense', 50) + level,
                moves=[skill(m, i == 2) for i, m in enumerate(moves)], boss=boss)


class Battle:
    def __init__(self, teams, tier=0, rng=None):
        self.rng = rng or random.Random()
        self.ident = secrets.token_hex(8)
        self.events = deque(maxlen=32)
        self.sequence = 0
        self.tier = tier
        self.stage = 0
        self.remaining = 60.0 if not tier else 180.0
        self.intro = 3.0
        self.result = None
        self.age = 0.0
        self.shots = []
        self.effects = []
        self.weather = self.rng.choice(['sun', 'rain', 'snow', 'wind'])
        self.arena = self.rng.choice(['grass', 'water', 'rock', 'sky'])
        self.platforms = [(230, 100, 490), (455, 110, 405), (715, 110, 465), (930, 110, 385)]
        self.active_bots = []
        self.fighters = {}
        for index, (uid, team) in enumerate(teams.items()):
            self.fighters[uid] = self.fighter(team, 160 + index * 780, index if not tier else 0)
        if tier:
            self.wave()

    def emit(self,kind,**data):
        self.sequence+=1;self.events.append(dict(seq=self.sequence,kind=kind,**data))

    @staticmethod
    def fighter(team, x, side):
        return dict(team=team, slot=next((i for i,c in enumerate(team) if c['hp']>0),0), x=float(x), y=570., vy=0., side=side, facing=1 if side == 0 else -1,
                    energy=25., guard=False, cooldowns=[0., 0., 0., 0.], keys={}, input_age=0., ai=0.)

    def wave(self):
        self.fighters = {k:v for k,v in self.fighters.items() if not k.startswith('bot:')}
        self.active_bots = []
        base = (self.tier - 1) * 10
        counts = [5, 3, 3, 1]
        # Bosses are chosen from high base-stat species, at the tier's top level.
        for i in range(counts[self.stage]):
            level = base + (10 if self.stage == 3 else self.stage * 3 + self.rng.randint(1, 3))
            ident = self.rng.choice([149, 248, 373, 445, 635, 706, 887]) if self.stage == 3 else self.rng.choice([19, 41, 74, 95, 123, 215, 328, 443])
            self.fighters[f'bot:{i}'] = self.fighter([creature(ident, level, self.stage == 3)], 720+i*70, 1)
            attackers = 1 if self.stage == 3 else min(3, self.stage + 1)
            if len(self.active_bots) < attackers:
                self.active_bots.append(f'bot:{i}')
        self.remaining = 180.
        self.intro = 3.

    def control(self, uid, keys):
        if uid in self.fighters:
            f = self.fighters[uid]
            f['keys'] = {k:bool(keys.get(k)) for k in ('left','right','up','guard','a','s','d','f','1','2','3')}
            f['input_age'] = 0.

    def hit(self, attacker, target, power, ultimate=False):
        f, g = self.fighters[attacker], self.fighters[target]
        p, q = f['team'][f['slot']], g['team'][g['slot']]
        if q['hp'] <= 0:
            return
        damage = max(2, int(power * .20 * (p['attack'] + 80) / (q['defense'] + 80)))
        if p.get('boss'): damage = int(damage * 1.3)
        if g['guard']: damage = max(1, int(damage * .18))
        q['hp'] = max(0, q['hp'] - damage)
        self.emit('hit',pokemon=q['id'])
        f['energy'] = min(100, f['energy'] + (0 if ultimate else 7))
        self.effects.append(dict(x=g['x'], y=g['y']-35, text='BLOCK' if g['guard'] else str(damage), ttl=.5))
        if q['hp'] == 0:
            # Dungeon enemies enter one at a time. Keep later enemies visible
            # in the arena, but never let all of them attack together.
            if target in self.active_bots:
                self.active_bots.remove(target)
                attackers = 1 if self.stage == 3 else min(3, self.stage + 1)
                upcoming = next((uid for uid,v in self.fighters.items()
                                 if uid.startswith('bot:') and uid not in self.active_bots
                                 and v['team'][v['slot']]['hp'] > 0), None)
                if upcoming is not None and len(self.active_bots) < attackers:
                    self.active_bots.append(upcoming)
            live = next((i for i,c in enumerate(g['team']) if c['hp'] > 0), None)
            if live is not None:
                g['slot'] = live
                g['cooldowns'] = [1.]*4

    def attack(self, uid, slot):
        f = self.fighters[uid]; p = f['team'][f['slot']]
        if f['cooldowns'][slot] > 0 or (slot == 3 and f['energy'] < 100): return
        enemies = [(k,v) for k,v in self.fighters.items() if v['side'] != f['side'] and v['team'][v['slot']]['hp'] > 0]
        if not enemies: return
        target, g = min(enemies, key=lambda kv: math.hypot(kv[1]['x']-f['x'], kv[1]['y']-f['y']))
        move = dict(name='Punch',power=42,range=85,cooldown=.55,emoji='🥊',accuracy=100,type='normal',style='melee')
        if slot and p['moves']: move = p['moves'][min(slot-1,len(p['moves'])-1)]
        f['cooldowns'][slot] = move['cooldown']
        self.emit('attack',type=move['type'],ultimate=slot==3,pokemon=p['id'])
        if slot == 3:
            f['energy'] = 0
            self.effects.append(dict(x=640,y=230,text=p['name']+' — '+move['name'],ttl=.8,ultimate=p['id']))
        dx, dy = g['x']-f['x'], g['y']-f['y']; distance = max(1, math.hypot(dx,dy))
        f['facing'] = 1 if dx >= 0 else -1
        self.effects.append(dict(x=f['x']+f['facing']*30,y=f['y']-35,text=move['emoji'],ttl=.25))
        if self.rng.random()*100 > move['accuracy']:
            self.effects.append(dict(x=f['x'],y=f['y']-65,text='MISS',ttl=.5)); return
        power = move['power'] * (1.8 if slot == 3 else 1)
        favored = {'sun':'fire','rain':'water','snow':'ice','wind':'flying'}[self.weather]
        if move['type'] in (favored,self.arena): power *= 1.15
        if not slot or move['style'] == 'melee':
            if distance <= (85 if not slot else move['range']): self.hit(uid,target,power,slot==3)
            return
        self.shots.append(dict(owner=uid,side=f['side'],x=f['x'],y=f['y']-30,vx=dx/distance*420,vy=dy/distance*420,
                               remaining=move['range'],emoji=move['emoji'],power=power,ultimate=slot==3))

    def tick(self, dt):
        if self.result: return
        self.age += dt
        if self.intro > 0:
            self.intro -= dt; return
        self.remaining -= dt
        for uid,f in self.fighters.items():
            p = f['team'][f['slot']]
            if p['hp'] <= 0: continue
            f['input_age'] += dt
            if f['input_age'] > .7: f['keys'] = {}
            if uid.startswith('bot:'):
                if self.tier and uid not in self.active_bots:
                    # Staggered dungeon encounter: reserve this fighter's AI
                    # until the currently active enemy is defeated.
                    f['guard'] = True
                    continue
                f['ai'] -= dt
                if f['ai'] <= 0:
                    targets = [v for v in self.fighters.values() if v['side'] == 0 and v['team'][v['slot']]['hp'] > 0]
                    if targets:
                        target = min(targets, key=lambda v: abs(v['x']-f['x']))
                        dx = target['x']-f['x']
                        f['keys'] = dict(left=dx < -100,right=dx > 100,up=target['y'] < f['y']-50 or self.rng.random()<.15,
                                         guard=self.rng.random()<.14,a=abs(dx)<90,s=True,d=self.rng.random()<.4,f=True)
                    f['ai'] = self.rng.uniform(.25,.65)
            keys = f['keys']; f['guard'] = bool(keys.get('guard'))
            for i in range(3):
                if keys.get(str(i+1)) and i < len(f['team']) and f['team'][i]['hp'] > 0: f['slot'] = i
            movement = int(keys.get('right',False))-int(keys.get('left',False))
            if movement: f['facing'] = movement
            f['x'] = max(40,min(1240,f['x']+movement*(90 if f['guard'] else 230)*dt))
            grounded = f['y'] >= 570 or any(x-12 <= f['x'] <= x+w+12 and abs(f['y']-y)<1 for x,w,y in self.platforms)
            if keys.get('up') and grounded: f['vy'] = -465
            old_y = f['y']; f['vy'] += 1150*dt; f['y'] += f['vy']*dt
            if f['vy'] >= 0:
                for x,w,y in self.platforms:
                    if x-10 <= f['x'] <= x+w+10 and old_y <= y <= f['y']: f['y']=y;f['vy']=0
            if f['y'] >= 570: f['y']=570;f['vy']=0
            f['energy'] = min(100, f['energy']+dt*4)
            f['cooldowns'] = [max(0,c-dt) for c in f['cooldowns']]
            for i,k in enumerate(('a','s','d','f')):
                if keys.get(k) and not f['guard']: self.attack(uid,i)
        for shot in list(self.shots):
            shot['x'] += shot['vx']*dt; shot['y'] += shot['vy']*dt;shot['remaining'] -= 420*dt
            hit = False
            for uid,f in self.fighters.items():
                if f['side'] != shot['side'] and f['team'][f['slot']]['hp'] > 0 and math.hypot(f['x']-shot['x'], f['y']-30-shot['y'])<28:
                    self.hit(shot['owner'],uid,shot['power'],shot['ultimate']);hit=True;break
            if hit or shot['remaining'] <= 0: self.shots.remove(shot)
        self.effects = [dict(e,ttl=e['ttl']-dt) for e in self.effects if e['ttl']>dt]
        sides = {f['side'] for f in self.fighters.values() if any(p['hp']>0 for p in f['team'])}
        if self.tier and sides == {0} and self.stage < 3:
            self.stage += 1;self.shots.clear();self.wave();return
        if len(sides) <= 1 or self.remaining <= 0:
            winner = next(iter(sides)) if len(sides)==1 else None
            if self.remaining <= 0 and not self.tier:
                score = {side:sum(p['hp']/p['maximum'] for f in self.fighters.values() if f['side']==side for p in f['team']) for side in (0,1)}
                winner = None if abs(score[0]-score[1])<.001 else max(score,key=score.get)
            drops=[]
            if self.tier and winner == 0 and self.stage == 3:
                level=self.tier*10
                table=[('Potion',max(1,level//10)),('Poké Ball',max(1,level//20))]
                if level >= 20: table.append(('Rare Candy',1))
                if level >= 50: table.append(('Star Piece',1))
                drops=[self.rng.choice(table)]
            self.result = dict(winner=winner, drops=drops, message='Victory' if self.tier and winner==0 else 'Battle finished')

    def snapshot(self):
        return dict(id=self.ident,events=list(self.events),fighters={uid:{k:v for k,v in f.items() if k not in ('keys','input_age','ai')} for uid,f in self.fighters.items()},
                    remaining=round(self.remaining,1),intro=round(self.intro,1),stage=self.stage,tier=self.tier,
                    shots=self.shots,effects=self.effects,platforms=self.platforms,weather=self.weather,arena=self.arena,
                    active_bots=self.active_bots,result=self.result)
