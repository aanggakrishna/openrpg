"""OpenRPG multiplayer service. Run: python online_server.py --port 8765."""
import argparse
from collections import deque
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from online_combat import Battle, creature


class World:
    def __init__(self, database, join_code=''):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS accounts (token TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.users = {t:json.loads(b) for t,b in self.db.execute('SELECT token,body FROM accounts')}
        self.presence = {}
        self.chat = deque(maxlen=100)
        self.offers = {}
        self.matches = {}
        self.join_code = join_code
        self.closed = threading.Event()

    def save(self):
        with self.db:
            self.db.executemany('INSERT OR REPLACE INTO accounts VALUES (?,?)',[(k,json.dumps(v)) for k,v in self.users.items()])

    def connect(self, body):
        if not secrets.compare_digest(str(body.get('join_code','')),self.join_code): raise ValueError('Incorrect server code')
        token = str(body.get('token',''))
        key = hashlib.sha256(token.encode()).hexdigest()
        if token and key not in self.users: raise ValueError('Unknown profile token. Select the original server/profile.')
        if not token:
            if len(self.users)>=1000: raise ValueError('Server account limit reached')
            token = secrets.token_urlsafe(32);key=hashlib.sha256(token.encode()).hexdigest()
            roster = body.get('roster',{})
            if not isinstance(roster,dict): raise ValueError('Invalid roster')
            roster = {str(int(i)):max(1,min(100,int(lv))) for i,lv in roster.items() if str(i).isdigit() and 1<=int(i)<=1025}
            if not roster: raise ValueError('Bring at least one Pokemon')
            active = [int(i) for i in body.get('active',[]) if str(i) in roster][:3] or [int(next(iter(roster)))]
            items={str(k):max(0,min(999,int(v))) for k,v in body.get('items',{}).items() if str(k) and str(v).isdigit()}
            self.users[key] = dict(id=secrets.token_hex(8),name=str(body.get('name','Trainer'))[:18],character=max(0,min(8,int(body.get('character',0)))),
                                   roster=roster,active=active,money=max(0,min(100000,int(body.get('money',0)))),items=items,
                                   trainer_xp=max(0,min(999999,int(body.get('trainer_xp',0)))),
                                   trainer_level=max(1,min(100,int(body.get('trainer_level',1)))),unlocked=1)
            self.save()
        u=self.users[key]
        self.leave_match(u['id']);self.cancel_offers(u['id'])
        self.presence[u['id']] = dict(room='gym',x=240.,y=410.,last=time.monotonic(),match=None,ready=False,keys={},chat_at=0,offer_at=0)
        return dict(token=token, **self.snapshot(u))

    def user(self, uid):
        return next((u for u in self.users.values() if u['id']==uid),None)

    def auth(self, token):
        u=self.users.get(hashlib.sha256(token.encode()).hexdigest())
        if not u or u['id'] not in self.presence: raise ValueError('Disconnected. Reconnect to the server.')
        self.presence[u['id']]['last']=time.monotonic()
        return u

    def snapshot(self,u):
        p=self.presence[u['id']]
        people=[]
        for uid,v in self.presence.items():
            if v['room']==p['room']:
                other=self.user(uid)
                people.append(dict(id=uid,name=other['name'],character=other['character'],active=other['active'],roster=other['roster'],x=v['x'],y=v['y'],ready=v['ready'],moving=bool(any(v['keys'].values())),facing=v.get('facing','down')))
        match=self.matches.get(p['match'])
        return dict(me=u,room=p['room'],players=people,chat=[c for c in self.chat if c['room']==p['room']][-7:],
                    offers=[dict(o,id=k) for k,o in self.offers.items() if u['id'] in (o['from'],o['to'])],
                    battle=match['battle'].snapshot() if match else None)

    def cancel_offers(self,uid):
        self.offers={k:o for k,o in self.offers.items() if uid not in (o['from'],o['to'])}

    def busy(self,uid):
        return bool(self.presence[uid]['match'])

    def start(self, ids, tier=0):
        teams={uid:[creature(i,self.user(uid)['roster'][str(i)]) for i in self.user(uid)['active']] for uid in ids}
        for uid,team in teams.items():
            for c in team:c['hp']=round(c['maximum']*self.user(uid).get('health',{}).get(str(c['id']),1))
            if not any(c['hp']>0 for c in team):raise ValueError('A team has fainted. Visit the Pokemon Center ($5).')
        mid=secrets.token_hex(8)
        self.matches[mid]=dict(battle=Battle(teams,tier),ids=ids,paid=False)
        for uid in ids:
            self.presence[uid]['match']=mid
            self.presence[uid]['ready']=False
            self.cancel_offers(uid)

    def action(self,u,b):
        uid=u['id'];p=self.presence[uid];kind=b.get('action','poll')
        if kind=='input':
            keys=b.get('keys',{})
            if not isinstance(keys,dict):raise ValueError('Invalid input')
            p['keys']={k:bool(keys.get(k)) for k in ('left','right','up','down')}
            if p['match']:self.matches[p['match']]['battle'].control(uid,keys)
        elif kind=='chat':
            if time.monotonic()-p['chat_at'] < .7:raise ValueError('Please slow down')
            msg=''.join(c for c in str(b.get('text','')) if c.isprintable())[:160].strip()
            if msg:self.chat.append(dict(room=p['room'],name=u['name'],text=msg));p['chat_at']=time.monotonic()
        elif kind=='room':
            if self.busy(uid):raise ValueError('Finish or leave the battle first')
            room=str(b.get('room','gym'))
            if room not in ('gym','hall'):
                if not room.startswith('dungeon:'):raise ValueError('Unknown room')
                tier=int(room.split(':')[1])
                if not 1<=tier<=10 or tier>u['unlocked']:raise ValueError('Clear the previous dungeon first')
            if sum(v['room']==room for v in self.presence.values())>=16:raise ValueError('Room is full')
            p.update(room=room,x=240.,y=410.,ready=False,keys={});self.cancel_offers(uid)
        elif kind in ('pvp','trade'):
            if self.busy(uid):raise ValueError('Already in a battle')
            target=str(b.get('target',''));v=self.presence.get(target)
            if target==uid or not v or v['room']!=p['room'] or v['match']:raise ValueError('Player is unavailable')
            if time.monotonic()-p['offer_at']<2:raise ValueError('Wait before another invitation')
            self.cancel_offers(uid)
            offer=dict(kind=kind,**{'from':uid,'to':target},name=u['name'],expires=time.monotonic()+45)
            if kind=='trade':
                give=int(b.get('give',0));want=int(b.get('want',0));price=int(b.get('price',0))
                if str(give) not in u['roster'] or price<0 or price>100000:raise ValueError('Invalid trade')
                if want and str(want) not in self.user(target)['roster']:raise ValueError('Requested Pokemon unavailable')
                offer.update(give=give,want=want,price=price)
            self.offers[secrets.token_hex(8)]=offer;p['offer_at']=time.monotonic()
        elif kind=='reply':
            oid=str(b.get('offer',''));o=self.offers.get(oid)
            if not o or uid not in (o['from'],o['to']):raise ValueError('Offer expired')
            if not b.get('accept'):self.offers.pop(oid);return
            if uid!=o['to']:raise ValueError('Only recipient can accept')
            other=self.user(o['from']);v=self.presence.get(other['id'])
            if not v or v['room']!=p['room'] or v['match'] or p['match']:raise ValueError('Player unavailable')
            if o['kind']=='pvp':self.start([other['id'],uid])
            else:
                give,want,price=str(o['give']),str(o['want']),o['price']
                if give not in other['roster'] or give in u['roster'] or (o['want'] and (want not in u['roster'] or want in other['roster'])):raise ValueError('Ownership changed or species already owned')
                if u['money']<price:raise ValueError('Not enough coins')
                if (len(other['roster'])==1 and not o['want']) or (len(u['roster'])==1 and o['want'] and give==want):raise ValueError('Keep at least one Pokemon')
                u['roster'][give]=other['roster'].pop(give)
                if o['want']:other['roster'][want]=u['roster'].pop(want)
                give_health=other.setdefault('health',{}).pop(give,1)
                want_health=u.setdefault('health',{}).pop(want,1) if o['want'] else 1
                u['health'][give]=give_health
                if o['want']:other['health'][want]=want_health
                u['money']-=price;other['money']+=price
                for account in (u,other):
                    account['active']=[i for i in account['active'] if str(i) in account['roster']] or [int(next(iter(account['roster'])))]
                self.save();self.cancel_offers(uid);self.cancel_offers(other['id'])
        elif kind=='active':
            if self.busy(uid):raise ValueError('Finish battle first')
            active=list(dict.fromkeys(int(i) for i in b.get('active',[])))
            if not 1<=len(active)<=3 or any(str(i) not in u['roster'] for i in active):raise ValueError('Select 1 to 3 owned Pokemon')
            u['active']=active;self.save()
        elif kind=='heal':
            if self.busy(uid):raise ValueError('Use the center outside battle')
            # Health carries between runs until this paid recovery.
            if u['money']<5:raise ValueError('Healing costs 5 coins')
            u['money']-=5;u['health']={};self.save()
        elif kind=='ready':
            if not p['room'].startswith('dungeon:') or self.busy(uid):raise ValueError('Enter a dungeon lobby first')
            p['ready']=not p['ready']
        elif kind=='raid':
            if not p['room'].startswith('dungeon:') or self.busy(uid):raise ValueError('Enter a dungeon first')
            ids=[i for i,v in self.presence.items() if v['room']==p['room'] and v['ready'] and not v['match']]
            if uid not in ids:raise ValueError('Mark Ready first; only ready players join')
            if len(ids)>4:raise ValueError('Maximum four players per raid')
            self.start(ids,int(p['room'].split(':')[1]))
        elif kind=='leave_battle':self.leave_match(uid)
        elif kind=='disconnect':
            self.leave_match(uid);self.cancel_offers(uid);self.presence.pop(uid,None)
        elif kind!='poll':raise ValueError('Unknown action')

    def leave_match(self,uid):
        p=self.presence.get(uid)
        if not p:return
        match=self.matches.get(p['match'])
        if match:
            f=match['battle'].fighters.get(uid)
            if f and not match['battle'].result:
                for c in f['team']:c['hp']=0
            p['match']=None

    def tick(self,dt):
        now=time.monotonic()
        for uid,p in list(self.presence.items()):
            if now-p['last']>15:
                self.leave_match(uid);self.cancel_offers(uid);del self.presence[uid];continue
            if not p['match'] and now-p['last']<.8:
                keys=p['keys'];dx=int(keys.get('right',False))-int(keys.get('left',False));dy=int(keys.get('down',False))-int(keys.get('up',False))
                if dx or dy:p['facing']='right' if dx>0 else 'left' if dx<0 else 'down' if dy>0 else 'up'
                length=max(1,(dx*dx+dy*dy)**.5)
                p['x']=max(55,min(3150 if p['room']=='hall' else 1220,p['x']+dx/length*220*dt))
                p['y']=max(235,min(620,p['y']+dy/length*220*dt))
        self.offers={k:o for k,o in self.offers.items() if o['expires']>now}
        for mid,m in list(self.matches.items()):
            battle=m['battle'];battle.tick(dt)
            if battle.result and not m['paid']:
                for uid in m['ids']:
                    u=self.user(uid);f=battle.fighters.get(uid)
                    if f:
                        u.setdefault('health',{}).update({str(c['id']):c['hp']/c['maximum'] for c in f['team']})
                    if f and battle.result['winner']==f['side'] and uid in self.presence and self.presence[uid]['match']==mid:
                        u['money']+=30 if not battle.tier else 50*battle.tier
                        gain=25 if not battle.tier else 80*battle.tier
                        xp=u.get('trainer_xp',0)+gain;level=u.get('trainer_level',1)
                        while level<100 and xp>=level*100:
                            xp-=level*100;level+=1
                        u['trainer_xp'],u['trainer_level']=xp,level
                        for name,count in battle.result.get('drops',[]):
                            u.setdefault('items',{})[name]=u.setdefault('items',{}).get(name,0)+count
                        for c in f['team']:u['roster'][str(c['id'])]=min(100,u['roster'][str(c['id'])]+(2 if battle.tier else 1))
                        if battle.tier:u['unlocked']=max(u['unlocked'],min(10,battle.tier+1))
                m['paid']=True;self.save()
            if not any(p['match']==mid for p in self.presence.values()):del self.matches[mid]

    def run(self):
        last=time.monotonic()
        while not self.closed.wait(.025):
            now=time.monotonic();elapsed=min(1.,now-last);last=now
            with self.lock:
                while elapsed>0:
                    step=min(.05,elapsed);self.tick(step);elapsed-=step


def make_server(host,port,world):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Never log bearer tokens or chat.
        def cors(self):
            self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
            self.send_header('Access-Control-Max-Age','600')
        def do_OPTIONS(self):
            self.send_response(204);self.cors();self.send_header('Content-Length','0');self.end_headers()
        def do_GET(self):
            self.respond(200,dict(name='OpenRPG',protocol=1)) if self.path=='/health' else self.respond(404,dict(error='Not found'))
        def respond(self,status,data):
            payload=json.dumps(data).encode();self.send_response(status);self.cors();self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers()
            try:self.wfile.write(payload)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=65536:raise ValueError('Invalid request size')
                self.connection.settimeout(5)
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('Invalid request')
                with world.lock:
                    if self.path=='/connect':result=world.connect(body)
                    elif self.path=='/action':
                        u=world.auth(self.headers.get('Authorization','').removeprefix('Bearer '));world.action(u,body)
                        result=world.snapshot(u) if u['id'] in world.presence else {'disconnected':True}
                    else:self.respond(404,{'error':'Not found'});return
                self.respond(200,result)
            except (ValueError,KeyError,TypeError,OverflowError) as e:self.respond(400,{'error':str(e)})
            except Exception:
                import traceback;traceback.print_exc();self.respond(500,{'error':'Server error'})
    return ThreadingHTTPServer((host,port),Handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--database',default='.openrpg/server.sqlite3');parser.add_argument('--join-code',default=os.environ.get('OPENRPG_JOIN_CODE',''))
    args=parser.parse_args();Path(args.database).parent.mkdir(parents=True,exist_ok=True)
    world=World(args.database,args.join_code);server=make_server(args.host,args.port,world)
    threading.Thread(target=world.run,daemon=True).start()
    print(f'OpenRPG server listening on {args.host}:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:world.closed.set();server.server_close();world.db.close()

if __name__=='__main__':main()
