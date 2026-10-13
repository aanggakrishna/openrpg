"""Gym, dungeon corridor and multiplayer interface for the Pygame client."""
import hashlib
import json
import math
from pathlib import Path
import queue
import time
import traceback
import pygame as pg
import retro
import pokemon_db
from online_client import OnlineClient

ROOT=Path(__file__).resolve().parent
C,G,M,GOLD=retro.CREAM,retro.GREEN,retro.MUTED,retro.GOLD
ONLINE_ELEMENT_COLORS={'fire':(255,116,64),'water':(79,190,255),'ground':(208,158,95),'rock':(190,159,110),
                       'flying':(150,218,255),'grass':(117,230,113),'bug':(174,212,98),'electric':(255,218,74),
                       'ice':(166,239,255),'psychic':(249,126,201),'ghost':(174,128,240),'dragon':(133,136,255)}


from world_regions import online_step

class OnlineMixin:
    def __init__(self,*args,**kwargs):
        self.net=None;self.online_state={};self.online_error='';self.online_input=None;self.online_input_text=''
        self.online_url='http://127.0.0.1:8765';self.online_code='';self.online_target=0;self.trade_give=0;self.trade_want=0;self.trade_price=0
        self.online_images={};self.online_scaled_images={};self.online_team_page=0;self.media_prune_timer=0.;self.online_terminal=False;self.online_last_hp={};self.online_audio_id=None;self.online_audio_seq=0;self.online_audio_result=False;self.online_visual_positions={}
        self.online_battle_help_id=None;self.online_battle_help_until=0.
        self.online_battle_error_log_at={}
        self.online_guard_click=False
        self.online_room_background=None;self.online_room_background_key=None
        super().__init__(*args,**kwargs)
        try:self.online_url=json.loads((ROOT/'.openrpg/online/preferences.json').read_text()).get('url',self.online_url)
        except (OSError,ValueError):pass
        # A server URL is safe to persist in preferences; the room code is
        # kept in the local, git-ignored access file created during setup.
        try:
            for line in (ROOT/'.openrpg/online/server-access.env').read_text().splitlines():
                if line.startswith('OPENRPG_JOIN_CODE='):
                    self.online_code=line.split('=',1)[1].strip()
                    break
        except OSError:
            pass

    def back(self):
        if self.online_terminal:
            self.online_terminal=False;self.set_mode('online_room');pg.key.stop_text_input();pg.key.set_repeat();return
        super().back()

    def quit(self):
        if self.net:self.net.close()
        super().quit()

    def stations(self):
        result=super().stations()
        if self.life.scene=='outdoors':result.append(('dungeon_hub',640,180,self.words('Hub utara · Gym & dungeon','North hub · Gym & dungeon')))
        if self.life.scene=='dungeon_hub':
            result.extend([('online_gym',145,435,self.words('Gym Online · ke kiri','Online Gym · left')),
                           ('local_dungeon',1135,435,self.words('Dungeon lokal · ke kanan','Local dungeon · right')),
                           ('outside',640,628,self.words('Kembali ke rumah','Return home'))])
        if self.life.scene=='local_dungeon':
            result.extend([('dungeon_start',640,267,self.words('Mulai / lanjut dungeon','Start / continue dungeon')),
                           ('dungeon_hub',640,625,self.words('Kembali ke hub','Return to hub'))])
        return result

    def obstacles(self,scene=None):
        result=super().obstacles(scene)
        if (scene or self.life.scene)=='outdoors':result=[r for r in result if not r.colliderect(pg.Rect(602,145,76,175))]
        return result

    def outdoors(self):
        super().outdoors()
        self.art.scenery.gate(self.canvas,640,180,"north","meadow")
        self.box((547,154,185,40),retro.PANEL)
        self.text('HUB UTARA / E',640,174,G,self.small,True)

    def interact(self):
        super().interact()

    def online_edit(self,field,value):
        self.online_input=field;self.online_input_text=str(value);pg.key.start_text_input()

    def connect_online(self):
        if self.net:self.net.close()
        self.save_current()
        identity=hashlib.sha256((self.online_url+'|'+str(self.save_path)).encode()).hexdigest()[:24]
        self.online_credentials=ROOT/'.openrpg/online'/f'{identity}.json'
        token=''
        try:token=json.loads(self.online_credentials.read_text()).get('token','')
        except (OSError,ValueError):pass
        profile=dict(token=token,join_code=self.online_code,name=self.life.player_name,character=self.life.character,
                     roster={str(i):self.life.pokemon_levels.get(str(i),5) for i in self.life.pokemon_party},active=self.active_pokemon_team(),money=self.life.money,
                     trainer_xp=getattr(self.life,'trainer_xp',0),trainer_level=getattr(self.life,'trainer_level',1))
        try:self.net=OnlineClient(self.online_url,profile)
        except ValueError as exc:self.online_error=str(exc);return
        self.online_state={};self.online_error=self.words('Menghubungkan...','Connecting...');self.set_mode('online_room')

    def online_send(self,action,**kwargs):
        if self.net and self.net.connected:self.net.send(action,**kwargs)
        else:self.online_error=self.words('Belum terhubung','Not connected')

    def online_use_skill(self,slot):
        self.online_send('skill',slot=slot)

    def online_switch(self,slot):
        self.online_send('switch',slot=slot)

    def online_toggle_guard(self):
        self.online_guard_click=not self.online_guard_click

    def leave_online(self):
        if self.net:self.net.close();self.net=None
        self.online_state={};self.online_input=None;pg.key.stop_text_input();self.set_mode('game')

    def online_people(self):
        me=self.online_state.get('me',{}).get('id')
        return [p for p in self.online_state.get('players',[]) if p['id']!=me]

    def online_invite(self,kind):
        people=self.online_people()
        if not people:self.online_error=self.words('Belum ada pemain lain di ruangan ini','No other players in this room');return
        target=people[self.online_target%len(people)]['id']
        if kind=='pvp':self.online_send('pvp',target=target)
        else:
            self.trade_target=target;self.trade_give=0;self.trade_want=0;self.trade_price=0;self.set_mode('online_trade')

    def online_enter(self):
        room=self.online_state.get('room','gym');me=self.online_state.get('me',{})
        player=next((p for p in self.online_state.get('players',[]) if p['id']==me.get('id')),None)
        if not player:return
        x=player['x']
        if room=='gym':
            if x>1050:self.online_send('room',room='hall')
            elif x<400:self.set_mode('online_center')
            else:self.online_invite('pvp')
        elif room=='hall':
            if x<130:self.online_send('room',room='gym')
            else:
                tier=max(1,min(10,round((x-300)/280)+1));self.online_send('room',room=f'dungeon:{tier}')
        else:
            if x<450:self.set_mode('online_center')
            else:self.online_send('ready')

    def handle(self,event):
        if self.mode.startswith('online_'):
            if event.type==pg.QUIT:self.leave_online();self.quit();return
            if self.online_input:
                if event.type==pg.TEXTINPUT:self.online_input_text+=''.join(c for c in event.text if c.isprintable());self.online_input_text=self.online_input_text[:160]
                if event.type==pg.KEYDOWN:
                    if event.key==pg.K_BACKSPACE:self.online_input_text=self.online_input_text[:-1]
                    elif event.key in (pg.K_RETURN,pg.K_ESCAPE):
                        if event.key==pg.K_RETURN:
                            if self.online_input=='chat':self.online_send('chat',text=self.online_input_text)
                            elif self.online_input=='url':self.online_url=self.online_input_text.strip()
                            elif self.online_input=='code':self.online_code=self.online_input_text
                            elif self.online_input=='price':self.trade_price=min(100000,int(self.online_input_text)) if self.online_input_text.isdigit() else 0
                        self.online_input=None;pg.key.stop_text_input()
                return
            if event.type==pg.KEYDOWN:
                if event.key==pg.K_b and self.mode=='online_room' and not self.online_state.get('battle'):
                    self.online_terminal=True;self.open_phone();return
                if event.key==pg.K_ESCAPE:
                    if self.mode=='online_room':self.leave_online()
                    elif self.mode=='online_connect':self.set_mode('game')
                    else:self.set_mode('online_room')
                    return
                if self.mode=='online_room' and self.online_state.get('battle'):
                    skill_slots={pg.K_a:0,pg.K_q:1,pg.K_w:2,pg.K_e:3,pg.K_r:4}
                    if event.key in skill_slots:
                        self.online_use_skill(skill_slots[event.key]);return
                    if event.key in (pg.K_1,pg.K_2,pg.K_3):
                        self.online_switch(event.key-pg.K_1);return
                if self.mode=='online_room' and event.key==pg.K_t:self.online_edit('chat','');return
                if self.mode=='online_room' and event.key==pg.K_e and not self.online_state.get('battle'):self.online_enter();return
            if event.type==pg.MOUSEBUTTONDOWN and event.button==1:
                for rect,callback in list(self.buttons):
                    if rect.collidepoint(self.mouse()):callback();return
            if event.type==pg.KEYDOWN and (self.mode!='online_room' or event.key in (pg.K_TAB,pg.K_RETURN)):
                if event.key in (pg.K_TAB,pg.K_RIGHT,pg.K_DOWN):self.nav_index=(self.nav_index+1)%max(1,len(self.buttons));return
                if event.key in (pg.K_LEFT,pg.K_UP):self.nav_index=(self.nav_index-1)%max(1,len(self.buttons));return
                if event.key==pg.K_RETURN and self.buttons:self.buttons[self.nav_index%len(self.buttons)][1]();return
            return
        super().handle(event)

    def update(self,dt):
        if self.net:
            while True:
                try:kind,data=self.net.events.get_nowait()
                except queue.Empty:break
                if kind in ('connected','state'):
                    self.online_state=data
                    self.online_audio(data.get('battle'))
                    feedback={'heal':self.words('Tim pulih. Biaya 5 koin.','Team healed. Paid 5 coins.'),
                              'trade':self.words('Tawaran dikirim. Menunggu persetujuan.','Offer sent. Waiting for acceptance.'),
                              'pvp':self.words('Tantangan dikirim.','Challenge sent.'),'active':self.words('Tim aktif diperbarui.','Active team updated.'),
                              'reply':self.words('Pilihan diproses.','Response processed.'),'room':'','raid':'','ready':'','chat':'',
                              'skill':self.words('Skill digunakan.','Skill used.')}
                    if data.get('_action') in feedback:self.online_error=feedback[data['_action']]
                    if kind=='connected':
                        self.online_credentials.parent.mkdir(parents=True,exist_ok=True)
                        self.online_credentials.write_text(json.dumps({'token':data['token']}));self.online_credentials.chmod(0o600)
                        (self.online_credentials.parent/'preferences.json').write_text(json.dumps({'url':self.online_url}))
                        self.online_error=''
                else:self.online_error=str(data)
            keys=pg.key.get_pressed();enabled=self.mode=='online_room' and not self.online_input
            if not self.online_state.get('battle'):self.online_guard_click=False
            self.net.keys={name:bool(enabled and (keys[key] or (name=='guard' and self.online_guard_click)))
                           for name,key in [('left',pg.K_LEFT),('right',pg.K_RIGHT),('up',pg.K_UP),('down',pg.K_DOWN),('a',pg.K_a),('q',pg.K_q),('w',pg.K_w),('e',pg.K_e),('r',pg.K_r),('guard',pg.K_s),('1',pg.K_1),('2',pg.K_2),('3',pg.K_3)]}
        if self.mode.startswith('online_') or self.online_terminal:
            self.frame+=dt*60;self.terminal.poll();self.load_pokemon_events()
            return
        if self.life.scene=='reserve' and self.mode=='game':
            from art import RESERVE_ZONES
            zone=RESERVE_ZONES.index(self.reserve_zone_at(self.life.x,self.life.y))
            if getattr(self,'loaded_reserve_zone',None)!=zone:self.spawn_map_pokemon()
        super().update(dt)
        self.media_prune_timer+=dt
        if self.media_prune_timer>3 and self.mode=='game':
            self.media_prune_timer=0;self.trim_area_media()

    def trim_area_media(self):
        keep=set(self.active_pokemon_team()) | {p['id'] for p in self.wild_pokemon}
        caches=[self.poke_surfaces,self.poke_battle_surfaces,self.poke_animations,self.pokemon_sounds,
                self.pokedex.sprites,self.pokedex.animated,self.pokedex.cries,self.pokedex.details]
        identifiers=list(dict.fromkeys(ident for cache in caches for ident in cache))
        count=len(identifiers)
        for ident in identifiers:
            if count<=48:break
            if ident not in keep:
                for cache in caches:cache.pop(ident,None)
                count-=1
        # These are in-memory textures only. Downloaded files stay on disk.
        while len(self.art.reserve_chunks)>2:self.art.reserve_chunks.pop(next(iter(self.art.reserve_chunks)))

    def online_audio(self,battle):
        if not battle:return
        try:
            battle_id=battle.get('id')
            if battle_id!=self.online_audio_id:
                self.online_audio_id=battle_id;self.online_audio_seq=0;self.online_audio_result=False
                for fighter in battle.get('fighters',{}).values():
                    for creature in fighter.get('team',[]):
                        if creature.get('id') is not None:self.pokedex.request_cry(creature['id'])
            for event in battle.get('events',[]):
                sequence=event.get('seq',0)
                if sequence<=self.online_audio_seq:continue
                self.online_audio_seq=sequence
                if event.get('kind')=='attack':
                    self.play_type_sound(event.get('type','normal'),event.get('ultimate',False))
                    if event.get('ultimate') and event.get('pokemon') is not None:self.play_pokemon_cry(event['pokemon'])
                elif event.get('kind')=='hit':
                    if event.get('ultimate'):self.play_ultimate_impact(event.get('type','normal'))
                    if event.get('pokemon') is not None:self.play_pokemon_cry(event['pokemon'])
            if battle.get('result') and not self.online_audio_result:
                self.online_audio_result=True;self.play_battle_sound('victory',.4)
        except Exception:
            # Audio is optional; a server event or a missing sound must never
            # take down the game loop during a live PvP match.
            self.log_online_battle_error('audio')

    def log_online_battle_error(self,source):
        """Persist unexpected PvP client errors so a recoverable match can be diagnosed."""
        now=time.monotonic()
        if now-self.online_battle_error_log_at.get(source,0)<5:return
        self.online_battle_error_log_at[source]=now
        try:
            path=Path.home()/'.openrpg'/'online'/'client-errors.log'
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('a',encoding='utf-8') as stream:
                stream.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] {source}\n')
                stream.write(traceback.format_exc())
        except OSError:
            pass

    def online_sprite(self,ident,x,y,size=70,flip=False,angle=0):
        if ident not in self.online_images:
            try:
                loaded=pg.image.load(str(ROOT/'assets/pokemon-sprites'/f'{ident}.png')).convert_alpha()
                bounds=loaded.get_bounding_rect()
                if bounds.width and bounds.height:loaded=loaded.subsurface(bounds)
                scale=min(1,160/max(loaded.get_size()))
                self.online_images[ident]=pg.transform.scale(loaded,(max(1,round(loaded.get_width()*scale)),max(1,round(loaded.get_height()*scale))))
            except (pg.error,FileNotFoundError):self.online_images[ident]=None
            while len(self.online_images)>40:self.online_images.pop(next(iter(self.online_images)))
        image=self.online_images[ident]
        if image:
            key=(ident,int(size),bool(flip))
            scaled=self.online_scaled_images.get(key)
            if scaled is None:
                scale=size/max(image.get_size())
                scaled=pg.transform.scale(image,(max(1,int(image.get_width()*scale)),max(1,int(image.get_height()*scale))))
                if flip:scaled=pg.transform.flip(scaled,True,False)
                self.online_scaled_images[key]=scaled
                while len(self.online_scaled_images)>120:self.online_scaled_images.pop(next(iter(self.online_scaled_images)))
            if angle:scaled=pg.transform.rotate(scaled,angle)
            self.canvas.blit(scaled,scaled.get_rect(midbottom=(int(x),int(y))))

    def online_position(self,key,x,y):
        old=self.online_visual_positions.get(key,(x,y))
        if math.hypot(x-old[0],y-old[1])>350:old=(x,y)
        value=(old[0]+(x-old[0])*.3,old[1]+(y-old[1])*.3)
        self.online_visual_positions[key]=value
        while len(self.online_visual_positions)>40:self.online_visual_positions.pop(next(iter(self.online_visual_positions)))
        return value

    def draw_world(self):
        if self.mode.startswith('online_'):
            self.canvas.fill((11,18,37));return
        super().draw_world()

    def overlay(self):
        if not self.mode.startswith('online_'):return super().overlay()
        self.buttons=[]
        if self.mode=='online_connect':self.draw_online_connect()
        elif self.mode=='online_trade':self.draw_online_trade()
        elif self.mode=='online_center':self.draw_online_center()
        elif self.online_state.get('battle'):self.draw_online_battle()
        else:self.draw_online_room()
        if self.online_error:self.text(self.online_error[:115],40,734,GOLD,self.small)
        if self.online_input:
            self.box((70,635,1140,82),retro.PANEL)
            self.text(self.online_input.upper()+' / Enter: OK / Esc: cancel',90,643,G,self.small)
            self.text(('*'*len(self.online_input_text) if self.online_input=='code' else self.online_input_text)[-95:]+'_',90,671,C,self.small)

    def draw_online_connect(self):
        self.box((170,120,940,545),retro.PANEL)
        self.text('ONLINE GYM',640,172,GOLD,self.big,True)
        self.text(self.words('Satu dunia bersama teman','A shared world with friends'),640,220,C,self.font,True)
        self.button(self.online_url,(240,270,800,52),lambda:self.online_edit('url',self.online_url))
        self.button(self.words('Kode server (opsional)','Server code (optional)'),(240,340,390,48),lambda:self.online_edit('code',self.online_code))
        self.button(self.words('Hubungkan','Connect'),(650,340,390,48),self.connect_online)
        self.text(self.words('Pertama masuk: salin tim dan koin ke profil server.','First connection: copy your collection and coins to a server profile.'),225,425,M,self.small)
        self.text(self.words('Progres online tersimpan di server, terpisah dari offline.','Online progress is saved on the server, separate from offline.'),225,453,M,self.small)
        self.text('Chat / PvP / Trade / Co-op dungeons Lv.1–100',225,498,G,self.font)
        self.button(self.words('Kembali','Back'),(440,560,400,48),lambda:self.set_mode('game'))

    def online_room_backdrop(self,room):
        """Bake static tile layers once per room; only players/UI animate."""
        if self.online_room_background_key==room and self.online_room_background is not None:
            return self.online_room_background
        surface=self.art.scenery.online(room)
        self.online_room_background=surface
        self.online_room_background_key=room
        return surface

    def draw_online_room(self):
        state=self.online_state;me=state.get('me',{});room=state.get('room','gym')
        own=next((p for p in state.get('players',[]) if p['id']==me.get('id')),{'x':240})
        camera=max(0,min(1920,own['x']-640)) if room=='hall' else 0
        backdrop=self.online_room_backdrop(room)
        self.canvas.blit(backdrop,(-int(camera),0))
        self.box((25,25,1230,100),retro.PANEL)
        title='ONLINE GYM' if room=='gym' else 'DUNGEON ROAD' if room=='hall' else 'DUNGEON '+room.split(':')[-1]
        self.text(title,48,43,GOLD,self.big);self.text(f"{me.get('name','...')}   $ {me.get('money',0)}   Trainer Lv.{me.get('trainer_level',1)} XP {me.get('trainer_xp',0)}   Tier {me.get('unlocked',1)}/10",48,90,G,self.small)
        if room=='gym':pg.draw.line(self.canvas,(74,102,125),(0,450),(1280,450),3)
        if room=='gym':
            pg.draw.rect(self.canvas,(52,74,91),(470,290,500,210),5)
            pg.draw.rect(self.canvas,(108,152,145),(490,310,460,170),2)
            pg.draw.circle(self.canvas,(74,102,125),(720,395),86,4)
            pg.draw.line(self.canvas,(74,102,125),(635,395),(805,395),4)
            pg.draw.circle(self.canvas,G,(720,395),22,4)
            for x in (415,1020):
                for y in (280,340,400):pg.draw.rect(self.canvas,(59,76,102),(x,y,22,38))
            self.text('TRAIN / TRADE / CHALLENGE',720,475,M,self.small,True)
        elif room.startswith('dungeon:'):
            tier=int(room.split(':')[1])
            self.box((390,535,500,72),(20,27,43),7)
            self.text(f'DUNGEON {tier:02}  ·  DEPTH {tier*10}',640,555,GOLD,self.font,True)
            self.text('1–3  /  4–6  /  7–9  /  BOSS Lv.10',640,584,C,self.small,True)
        if room=='hall':
            for i in range(10):
                x=int(300+i*280-camera)
                if -160<x<1400:
                    unlocked=i+1<=me.get('unlocked',1)
                    self.box((x-90,175,180,140),retro.PANEL)
                    self.text(f'Lv.{i*10+1}–{i*10+10}',x,208,G if unlocked else M,self.font,True)
                    self.text('E / ENTER' if unlocked else 'LOCKED',x,252,GOLD if unlocked else M,self.small,True)
            self.button('GYM',(35,140,140,42),lambda:self.online_send('room',room='gym'))
        else:
            self.box((120,205,260,100),retro.PANEL)
            self.text('POKEMON CENTER',250,237,G,self.font,True);self.text('E / TEAM + HEAL $5',250,274,M,self.small,True)
            if room=='gym':
                self.box((1040,240,220,70),retro.PANEL);self.text('DUNGEONS > E',1150,270,GOLD,self.small,True)
                self.button('Dungeons >',(1030,140,215,44),lambda:self.online_send('room',room='hall'))
            else:
                self.text(self.words('3 gelombang + bos / sampai 4 pemain','3 waves + boss / up to 4 players'),650,180,G,self.font,True)
                self.button('Ready',(770,220,170,44),lambda:self.online_send('ready'))
                self.button('Start raid',(965,220,215,44),lambda:self.online_send('raid'))
                self.button('< Road',(1030,140,215,44),lambda:self.online_send('room',room='hall'))
        for p in state.get('players',[]):
            px,py=self.online_position(room+p['id'],p['x'],p['y']);x=px-camera
            if -60<x<1340:
                self.art.character(self.canvas,x,py,p['character'],2,self.frame,p.get('moving',False),p.get('facing','down'))
                self.text(p['name']+(' READY' if p['ready'] else ''),x,py-55,G if p['id']==me.get('id') else C,self.small,True)
        people=self.online_people();target=people[self.online_target%len(people)] if people else None
        self.button((target['name'] if target else 'No players')+' >',(480,135,235,43),self.next_online_target)
        self.button('PvP',(735,135,115,43),lambda:self.online_invite('pvp'))
        self.button('Trade',(870,135,130,43),lambda:self.online_invite('trade'))
        self.button('Center',(270,135,185,43),lambda:self.set_mode('online_center'))
        self.box((25,530,555,143),retro.PANEL)
        for i,c in enumerate(state.get('chat',[])[-4:]):self.text((c['name']+': '+c['text'])[:67],40,540+i*28,C,self.small)
        if room=='gym' and not state.get('offers'):
            self.box((615,515,630,157),retro.PANEL)
            self.text('🏆 ONLINE LEADERBOARD · VICTORIES',632,528,GOLD,self.small)
            board=state.get('leaderboard',[])
            if not board:
                self.text('Play PvP or a raid to enter the board.',640,563,M,self.small)
            for index,row in enumerate(board[:5]):
                marker='★' if row.get('name')==me.get('name') else f'{index+1:02}'
                self.text(f"{marker}  {row.get('name','Trainer')[:18]}   ·   W {row.get('wins',0)}   ·   Lv.{row.get('level',1)}",
                          636,554+index*22,G if row.get('name')==me.get('name') else C,self.tiny)
        self.button('T / Chat',(30,680,210,40),lambda:self.online_edit('chat',''))
        self.button('Leave',(1050,680,200,40),self.leave_online)
        self.text('Arrows: move / E: use / T: chat / B: terminal / Tab+Enter',260,690,M,self.small)
        offers=state.get('offers',[])
        if offers:
            offer=offers[0];incoming=offer['to']==me.get('id')
            self.box((615,515,630,157),retro.PANEL)
            title=offer['name']+' / '+offer['kind'].upper()
            if offer['kind']=='trade':title+=f" #{offer['give']} > #{offer['want']} / ${offer['price']}"
            self.text(title[:67],632,530,GOLD,self.small)
            if offer['kind']=='trade':self.online_sprite(offer['give'],680,620,50)
            if incoming:self.button('Accept',(740,583,200,48),lambda:self.online_send('reply',offer=offer['id'],accept=True))
            self.button('Decline / Cancel',(960,583,250,48),lambda:self.online_send('reply',offer=offer['id'],accept=False))

    def next_online_target(self):self.online_target+=1

    def draw_online_trade(self):
        me=self.online_state.get('me',{});roster=list(me.get('roster',{}))
        self.text('TRADE OFFER',640,110,GOLD,self.big,True)
        if self.trade_want:self.online_sprite(self.trade_want,840,355,140)
        if not roster:self.button('Back',(400,600,400,50),lambda:self.set_mode('online_room'));return
        ident=int(roster[self.trade_give%len(roster)])
        self.online_sprite(ident,420,355,140)
        self.button(f'Give: #{ident} >',(250,390,350,50),lambda:setattr(self,'trade_give',self.trade_give+1))
        self.button(f'Request species #: {self.trade_want}',(660,390,380,50),lambda:self.cycle_trade_want())
        self.text(self.words('0 = tanpa pertukaran Pokemon','0 = no Pokemon requested'),660,452,M,self.small)
        self.button(f'Price: ${self.trade_price}',(400,495,480,48),lambda:self.online_edit('price',self.trade_price))
        self.text(self.words('Penerima membayar harga ini. 0 = gratis.','Recipient pays this price. 0 = free.'),400,555,G,self.small)
        self.button('Send offer',(310,600,300,50),lambda:self.submit_trade(ident))
        self.button('Back',(660,600,300,50),lambda:self.set_mode('online_room'))

    def cycle_trade_want(self):
        target=next((p for p in self.online_state.get('players',[]) if p['id']==self.trade_target),{})
        options=[0]+[int(i) for i in target.get('roster',{})]
        self.trade_want=options[(options.index(self.trade_want)+1)%len(options)] if self.trade_want in options else 0

    def submit_trade(self,ident):
        self.online_send('trade',target=self.trade_target,give=ident,want=self.trade_want,price=self.trade_price);self.set_mode('online_room')

    def draw_online_center(self):
        me=self.online_state.get('me',{});roster=list(me.get('roster',{}));active=me.get('active',[])
        self.text('POKEMON CENTER',640,85,GOLD,self.big,True)
        self.text(self.words('Pilih hingga 3 Pokemon aktif','Select up to 3 active Pokemon'),640,135,C,self.font,True)
        page=self.online_team_page%max(1,math.ceil(len(roster)/8))
        for i,key in enumerate(roster[page*8:page*8+8]):
            ident=int(key);x=150+(i%4)*260;y=210+(i//4)*160
            self.online_sprite(ident,x+100,y+75,70)
            self.button(f"{'*' if ident in active else ''} #{ident} Lv.{me['roster'][key]} HP{round(me.get('health',{}).get(key,1)*100)}%",(x,y+85,235,48),lambda ident=ident:self.toggle_online_team(ident))
        self.button('<',(160,590,100,48),lambda:setattr(self,'online_team_page',max(0,page-1)))
        self.button('>',(280,590,100,48),lambda:setattr(self,'online_team_page',page+1))
        self.button('Heal team $5',(410,590,300,48),lambda:self.online_send('heal'))
        self.button('Back',(740,590,350,48),lambda:self.set_mode('online_room'))
        self.text(f"$ {me.get('money',0)} / Trainer XP {me.get('trainer_xp',0)} / {len(active)}/3 active",640,665,G,self.font,True)

    def toggle_online_team(self,ident):
        active=list(self.online_state.get('me',{}).get('active',[]))
        if ident in active:
            if len(active)>1:active.remove(ident)
        elif len(active)<3:active.append(ident)
        else:self.online_error=self.words('Keluarkan satu anggota dahulu','Remove a member first');return
        self.online_send('active',active=active)

    def draw_online_battle(self):
        try:
            self._draw_online_battle()
        except Exception:
            self.log_online_battle_error('render')
            self.buttons=[]
            self.canvas.fill((22,31,55))
            self.box((250,220,780,300),retro.PANEL)
            self.text(self.words('Terjadi kendala saat menampilkan PvP.',
                                 'The PvP screen encountered a problem.'),640,280,GOLD,self.font,True)
            self.text(self.words('Game tetap berjalan. Kembali ke room dan coba sambungkan ulang.',
                                 'The game is still running. Return to the room and reconnect.'),640,330,C,self.small,True)
            self.text(self.words('Detail tersimpan di ~/.openrpg/online/client-errors.log',
                                 'Details saved to ~/.openrpg/online/client-errors.log'),640,370,M,self.tiny,True)
            self.button(self.words('Kembali ke room','Return to room'),(440,430,400,52),
                        lambda:self.online_send('leave_battle'))

    def _draw_online_battle(self):
        b=self.online_state['battle'];me=self.online_state.get('me',{});own=b['fighters'].get(me.get('id'))
        if self.online_battle_help_id!=b['id']:
            self.online_battle_help_id=b['id'];self.online_battle_help_until=time.monotonic()+20.
        self.canvas.fill((22,31,55));pg.draw.rect(self.canvas,(55,71,87),(0,570,1280,200))
        for i in range(7):
            x=i*210-80;y=300+(i%3)*32
            pg.draw.polygon(self.canvas,(33,49,72),[(x,570),(x+105,y),(x+230,570)])
        if b['weather'] in ('rain','snow'):
            for i in range(55):
                x=(i*137+int(self.frame*2))%1280;y=(i*83+int(self.frame*4))%570
                pg.draw.line(self.canvas,(95,132,164),(x,y),(x-3,y+9),1 if b['weather']=='rain' else 3)
        for x,w,y in b['platforms']:pg.draw.rect(self.canvas,(161,132,82),(x,y,w,16));pg.draw.rect(self.canvas,(80,66,57),(x+10,y+16,w-20,570-y))
        # The server owns these seven-second marks; every online client draws
        # the same water, fire, stone wall, bush, ice and wind state.
        for effect in b.get('arena_effects',[]):
            x,y=int(effect['x']),int(effect['y']);radius=int(effect.get('radius',128))
            mark=pg.Surface((radius*2+12,76),pg.SRCALPHA);kind=effect['kind']
            if kind in ('water','charged','ice'):
                fill=(73,169,236,110) if kind!='ice' else (201,242,255,125)
                pg.draw.ellipse(mark,fill,(6,22,radius*2,45))
                for index in range(4):pg.draw.arc(mark,(227,251,255,185),(18+index*13,30+index*8,radius*2-36,16),.2,2.7,2)
                if kind=='charged':
                    for index in range(5):
                        px=24+index*(radius*2-44)//4;pg.draw.line(mark,(255,235,93,230),(px,24),(px-8,57),3)
            elif kind in ('burn','wildfire'):
                pg.draw.ellipse(mark,(230,81,45,78),(6,27,radius*2,38))
                for index in range(7):
                    px=18+index*(radius*2-28)//6;height=18+(index%3)*9
                    pg.draw.polygon(mark,(255,163,56,215),[(px,60),(px+8,60),(px+4,60-height)])
            elif kind=='wall':
                pg.draw.rect(mark,(112,105,100,245),(radius-22,6,44,65))
                for yy in range(12,68,16):pg.draw.line(mark,(177,167,148,225),(radius-19,yy),(radius+19,yy),3)
            elif kind=='bush':
                for index in range(6):pg.draw.circle(mark,(74,152+(index%2)*22,78,228),(18+index*(radius*2-36)//5,51-(index%3)*8),20)
            elif kind=='gust':
                for index in range(4):pg.draw.arc(mark,(206,242,255,195),(16,20+index*13,radius*2-30,18),.2,2.8,3)
            self.canvas.blit(mark,(x-radius-6,y-64))
            glyph=self.emoji_font.render(effect['emoji'],False,C);glyph=pg.transform.scale(glyph,(25,25))
            self.canvas.blit(glyph,glyph.get_rect(center=(x,y-84)))
            self.text(f"{effect['label']} {effect['timer']:.0f}s",x,y-109,C,self.tiny,True)
        # Mirror the local fight HUD: equal-height framed HP panels, charge
        # meters below the player's HP, a centered top timer, and a clear
        # arena/status strip underneath the panels.
        foe=next((fighter for uid,fighter in b['fighters'].items()
                  if own and uid!=me.get('id') and fighter['side']!=own['side']),None)
        self.box((50,24,490,148),(32,51,48),14)
        self.box((740,24,490,148),(32,51,48),14)
        if own:
            player=own['team'][own['slot']]
            self.text(player['name'][:22],76,36,C,self.medium)
            self.text(f"ONLINE · Lv.{player.get('level',1)}",443,52,M,self.tiny,True)
            self._fight_bar(76,77,440,player['hp'],player['maximum'],left=True)
            self.text('ULTIMATE',76,120,GOLD,self.tiny)
            pg.draw.rect(self.canvas,(18,27,44),(151,123,365,8))
            pg.draw.rect(self.canvas,GOLD,(151,123,int(365*max(0,min(100,own.get('energy',0)))/100),8))
            self.text('S · GUARD',76,140,(158,204,233),self.tiny)
            self.buttons.append((pg.Rect(70,132,445,26),self.online_toggle_guard))
            pg.draw.rect(self.canvas,(55,71,87),(151,143,170,8))
            if own.get('guard') or self.online_guard_click:
                pg.draw.rect(self.canvas,(108,194,246),(151,143,170,8))
        if foe:
            enemy=foe['team'][foe['slot']]
            self.text(enemy['name'][:22],764,36,C,self.medium)
            self.text(f"Lv.{enemy.get('level',1)}",1158,52,M,self.tiny,True)
            self._fight_bar(764,77,440,enemy['hp'],enemy['maximum'],left=False)
        self.box((558,24,164,42),(32,51,48),12)
        seconds=max(0,math.ceil(b['remaining']))
        self.text(f"{seconds//60:02}:{seconds%60:02}",640,45,GOLD,self.medium,True)
        self.box((400,174,480,52),(25,38,58),10,retro.EDGE)
        self.text(f"{b['weather'].upper()} · {b['arena'].upper()} ARENA",640,188,G,self.tiny,True)
        self.text((f"STAGE {b['stage']+1}/4" if b['tier'] else 'PLAYER VS PLAYER'),640,209,C,self.tiny,True)
        for uid,f in b['fighters'].items():
            f=dict(f);f['x'],f['y']=self.online_position(b['id']+uid,f['x'],f['y'])
            p=f['team'][f['slot']];size=105 if p.get('boss') else 70
            if p['hp']>0:
                statuses=f.get('effects',{})
                angle=(self.frame*8)%360 if statuses.get('confuse',0)>0 else 0
                self.online_sprite(p['id'],f['x'],f['y'],size,f['facing']>0,angle)
                # Match the local game's transparent, per-status fighter overlays.
                overlay=pg.Surface((size+54,size+50),pg.SRCALPHA);cx=(size+54)//2;cy=(size+50)//2
                def status_icon(value,px,py,scale=30,alpha=210):
                    glyph=self.emoji_font.render(value,False,C);glyph=pg.transform.scale(glyph,(scale,scale));glyph.set_alpha(alpha)
                    overlay.blit(glyph,glyph.get_rect(center=(px,py)))
                if f.get('stun',0)>0:status_icon('⚡',cx,10,28)
                if statuses.get('freeze',0):
                    pg.draw.ellipse(overlay,(167,230,255,112),(22,18,size+10,size+18));status_icon('🧊',cx,cy,46,145)
                if statuses.get('entomb',0):
                    for ox,oy in ((-25,18),(0,27),(25,17)):status_icon('🪨',cx+ox,cy+oy,34,145)
                if statuses.get('bind',0):status_icon('🌿',cx-20,cy,37,180);status_icon('🕸️',cx+22,cy-6,34,170)
                if statuses.get('burn',0):status_icon('🔥',cx-24,cy+18,31);status_icon('🔥',cx+25,cy+15,28,190)
                if statuses.get('poison',0):status_icon('☠️',cx,cy-5,31,185)
                if statuses.get('slow',0):status_icon('🐌',cx,cy+20,29,185)
                if statuses.get('confuse',0):status_icon('😵‍💫',cx,10,31)
                if statuses.get('fear',0):status_icon('👻',cx,10,30,185)
                if statuses.get('blind',0):status_icon('🌫️',cx,cy,47,135)
                if statuses.get('armor_break',0):status_icon('💥',cx,10,27);status_icon('🛡️',cx,cy+16,32,120)
                if statuses.get('intimidate',0) or statuses.get('charm',0):status_icon('📉',cx,10,26)
                if f.get('stun',0)>0 or statuses:
                    self.canvas.blit(overlay,(int(f['x']-overlay.get_width()/2),int(f['y']-size/2-overlay.get_height()/2)))
                if statuses.get('confuse',0):
                    mark=self.emoji_font.render('❔',False,C);mark=pg.transform.scale(mark,(34,34))
                    self.canvas.blit(mark,mark.get_rect(center=(int(f['x']),int(f['y']-size-20))))
            else:self.text('KO',f['x'],f['y']-30,GOLD,self.font,True)
            self.text(f"{p['name']} Lv.{p['level']}",f['x'],f['y']-size-33,C,self.small,True)
            if uid in b.get('active_bots',[]):
                self.text('ACTIVE',f['x'],f['y']-size-52,GOLD,self.tiny,True)
            elif uid.startswith('bot:') and p['hp'] > 0:
                self.text('WAITING',f['x'],f['y']-size-52,M,self.tiny,True)
            pg.draw.rect(self.canvas,(55,55,65),(f['x']-40,f['y']-size-10,80,5))
            pg.draw.rect(self.canvas,G if f['side']==0 else (242,105,110),(f['x']-40,f['y']-size-10,80*p['hp']/p['maximum'],5))
            if f['guard']:pg.draw.circle(self.canvas,(94,187,230),(int(f['x']),int(f['y']-32)),42,2)
        for shot in b['shots']:
            glyph=self.emoji_font.render(shot['emoji'],False,C)
            size=66 if shot.get('ultimate') else int(26+min(42,float(shot.get('power',50))*.32))
            glyph=pg.transform.scale(glyph,(size,size))
            if shot.get('ultimate'):
                color=ONLINE_ELEMENT_COLORS.get(shot.get('type'),GOLD)
                start=(shot['x']-shot['vx']*.08,shot['y']-shot['vy']*.08);end=(shot['x'],shot['y'])
                pg.draw.line(self.canvas,(255,247,214),start,end,20);pg.draw.line(self.canvas,color,start,end,12)
            self.canvas.blit(glyph,glyph.get_rect(center=(int(shot['x']),int(shot['y']))))
        for e in b['effects']:
            if e.get('blast'):
                color=ONLINE_ELEMENT_COLORS.get(e.get('type'),GOLD);progress=1-max(0,e['ttl'])/.7
                radius=20+int(115*progress);center=(int(e['x']),int(e['y']))
                pg.draw.circle(self.canvas,color,center,radius,5)
                pg.draw.circle(self.canvas,(255,246,203),center,max(6,radius//2),3)
                for index in range(10):
                    angle=index*math.tau/10;end=(int(center[0]+math.cos(angle)*(radius+30)),int(center[1]+math.sin(angle)*(radius+30)))
                    pg.draw.line(self.canvas,color,center,end,4)
                boom=self.emoji_font.render(e['text'],False,C);size=int(45+70*progress);boom=pg.transform.scale(boom,(size,size))
                self.canvas.blit(boom,boom.get_rect(center=center))
            elif e.get('ultimate') and not e.get('cutin'):
                self.box((330,155,620,110),retro.PANEL);self.online_sprite(e['ultimate'],395,255,86);self.text(e['text'][:42],740,205,GOLD,self.font,True)
            else:self.text(e['text'],e['x'],e['y'],GOLD,self.small,True)
        if own:
            p=own['team'][own['slot']]
            self.text(f"{p['name']} / HP {p['hp']}/{p['maximum']}",35,35,C,self.font)
            self.text('S · GUARD',35,65,(158,204,233),self.tiny)
            pg.draw.rect(self.canvas,(55,71,87),(112,67,180,8))
            if own.get('guard'):
                pg.draw.rect(self.canvas,(108,194,246),(112,67,180,8))
            # Older online servers may send only the cooldown slots they use.
            # Normalize to all five action slots (basic, Q, W, E, ultimate).
            cooldowns=list(own.get('cooldowns') or [])
            cooldowns=(cooldowns+[0.] * 5)[:5]
            basic={'name':self.words('Pukulan','Punch'),'emoji':'🥊'}
            actions=[('A',basic,cooldowns[0])]
            actions.extend((key,move,cooldowns[i+1]) for i,(key,move) in enumerate(zip('QWE',p['moves'])))
            actions.append(('R',p.get('ultimate') or {},cooldowns[4]))
            for i,(key,move,cooldown) in enumerate(actions):
                x=25+i*250;y=614
                self.box((x,y,236,62),retro.PANEL)
                self.buttons.append((pg.Rect(x,y,236,62),lambda slot=i:self.online_use_skill(slot)))
                self.text(key,x+13,y+8,GOLD if cooldown<=0 else M,self.font,True)
                glyph=move.get('emoji','✨');self.text(glyph,x+48,y+7,C,self.font)
                label=move.get('name','Ultimate')
                if key=='Q' and move.get('effect_label'):label=move['effect_label']+' · '+label
                if len(label)>25:label=label[:23]+'…'
                suffix=(f'{cooldown:.1f}s' if cooldown>0 else
                        ('READY' if key!='R' or own.get('energy',0)>=100 else 'CHARGING'))
                self.text(f'{label}  {suffix}',x+79,y+10,G if cooldown<=0 else M,self.small)
            # The same team-switch keys as local combat, shown as compact
            # square portraits with a per-Pokémon health bar.
            for row,member in enumerate(own.get('team',[])[:3]):
                x=25+row*82;y=690
                active=row==own.get('slot',0)
                self.box((x,y,58,54),retro.PANEL,5,GOLD if active else retro.EDGE)
                self.buttons.append((pg.Rect(x,y,58,54),lambda slot=row:self.online_switch(slot)))
                self.online_sprite(member['id'],x+29,y+27,43,False)
                self.text(str(row+1),x+7,y+4,GOLD,self.tiny,True)
                pg.draw.rect(self.canvas,(55,71,87),(x-2,y+57,62,8))
                ratio=max(0,min(1,member.get('hp',0)/max(1,member.get('maximum',1))))
                pg.draw.rect(self.canvas,G if ratio>.35 else (242,105,110),(x-2,y+57,int(62*ratio),8))
                self.text(f"{member.get('hp',0)}/{member.get('maximum',1)}",x+29,y+75,M,self.tiny,True)
        if time.monotonic()<self.online_battle_help_until:
            self.box((300,715,630,72),retro.PANEL,10,retro.EDGE)
            self.text(self.words('← → gerak · ↑ lompat/panjat · S tahan',
                                 '← → move · ↑ jump/climb · S guard'),640,727,C,self.tiny,True)
            self.text(self.words('A dekat · Q stun · W dekat · E jauh · R ultimate · 1–3 ganti Pokémon',
                                 'A close · Q stun · W close · E ranged · R ultimate · 1–3 switch Pokémon'),
                      640,747,G,self.tiny,True)
            self.text(self.words('Escape · keluar dari pertarungan',
                                 'Escape · leave the battle'),640,767,M,self.tiny,True)
        if b['intro']>0:self.text(str(math.ceil(b['intro'])),640,300,GOLD,self.big,True)
        if b['result']:
            self.box((400,300,480,135),retro.PANEL)
            result=b['result'];won=own and result['winner']==own['side']
            self.text('VICTORY' if won else 'DRAW' if result['winner'] is None else 'DEFEAT',640,330,GOLD,self.big,True)
            drops=result.get('drops',[])
            if drops:self.text('DROP: '+', '.join(f'{name} x{count}' for name,count in drops),640,355,G,self.small,True)
            self.button('Return to room',(440,370,400,48),lambda:self.online_send('leave_battle'))
        else:self.button('Forfeit',(1010,744,235,38),lambda:self.online_send('leave_battle'))
        cutin=next((e for e in reversed(b['effects']) if e.get('cutin')),None)
        if cutin:
            progress=max(0,min(1,1-cutin['ttl']/.82));accent=ONLINE_ELEMENT_COLORS.get(cutin.get('type'),GOLD)
            overlay=pg.Surface((1280,760),pg.SRCALPHA);overlay.fill((8,13,31,242));self.canvas.blit(overlay,(0,0))
            pg.draw.polygon(self.canvas,accent,[(0,190),(1280,70),(1280,560),(0,680)])
            pg.draw.polygon(self.canvas,(11,18,37),[(0,220),(1280,105),(1280,520),(0,635)])
            self.online_sprite(cutin['ultimate'],335,560,285,False)
            self.text('ULTIMATE!',820,190,GOLD,self.big,True)
            self.text(cutin.get('text','Pokémon Ultimate')[-42:],820,255,C,self.font,True)
            glyph=self.emoji_font.render(cutin.get('emoji','💥'),False,C);size=int(90+38*math.sin(progress*math.pi));glyph=pg.transform.scale(glyph,(size,size))
            self.canvas.blit(glyph,glyph.get_rect(center=(820,365)))
            style=cutin.get('ultimate_style','beam')
            if style=='area':
                for radius in (64,104,146):pg.draw.circle(self.canvas,accent,(1030,365),radius,4)
            elif style=='rush':
                for index in range(6):pg.draw.line(self.canvas,accent,(920,390+index*24),(1180,315+index*24),6)
            elif style=='barrage':
                for index in range(8):
                    mini=self.emoji_font.render(cutin.get('emoji','💥'),False,C);mini=pg.transform.scale(mini,(30,30))
                    self.canvas.blit(mini,mini.get_rect(center=(910+(index%4)*72,340+(index//4)*65)))
            elif style=='wave':
                for index in range(4):pg.draw.arc(self.canvas,accent,(900,305+index*22,275,90),.1,math.pi-.1,5)
