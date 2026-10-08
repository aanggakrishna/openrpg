"""Profile flow, keyboard navigation, daily rewards and collection management."""
from pathlib import Path
import json
import math
import random
import shutil
import time
import pygame as pg
import retro
import pokemon_db
from state import Life, BUY
from wildlife import Wildlife
from art import PLAYER_STYLES, RESERVE_CENTERS
ROOT = Path(__file__).resolve().parent
STARTERS = (1,4,7,25,37,43,54,58,60,66,74,92,133,152,155,158,179,187,252,255,258,280,387,390,393,403)
C, G, M, GOLD = retro.CREAM, retro.GREEN, retro.MUTED, retro.GOLD

class FlowMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile_root = ROOT / '.openrpg/profiles'
        self.profile_root.mkdir(parents=True, exist_ok=True)
        try:
            prefs=json.loads((ROOT/'.openrpg/preferences.json').read_text())
            for key in ('language','music_volume','effects_volume','cry_volume','reduced_motion'):
                if key in prefs:setattr(self.life,key,prefs[key])
        except (OSError,ValueError):pass
        self.playing = False
        self.nav_index = 0
        self.nav_mode = None
        self.keyboard_focus = True
        self.center_page = 0
        self.center_query = ""
        self.center_search = False
        self.assigning_slot = False
        self.reward = None
        self.invitation = None
        self.encounter_grace = 12.0
        self.daily_page = 0
        self.wizard = {}
        self.profile_action = 'load'
        self.profile_return = 'title'
        self.asset_loading_ids = []

    def words(self, indonesian, english):
        return indonesian if self.life.language == 'id' else english

    def save_current(self):
        if self.playing:
            self.life.save(self.save_path)
            self.saved_toast_at = time.monotonic()

    def button(self, label, rect, callback, active=False):
        super().button(label, rect, callback, active)
        if not label:
            self.box(rect,retro.PANEL)
        if self.keyboard_focus and len(self.buttons)-1 == self.nav_index:
            r = pg.Rect(rect).inflate(6,6)
            pg.draw.rect(self.canvas, G, r, 2)
            pg.draw.rect(self.canvas, GOLD, (r.x-5,r.centery-4,5,8))

    def set_mode(self, mode):
        self.mode = mode
        self.nav_mode = None
        self.buttons = []

    def profile_slots(self):
        paths = [ROOT / '.openrpg/save.json'] + [self.profile_root / f'slot-{i}.json' for i in range(1,5)]
        result=[]
        for path in paths:
            try:
                data=json.loads(path.read_text()) if path.exists() else None
            except (OSError,ValueError):
                data=None
            result.append((path,data))
        return result

    def open_profiles(self, action):
        self.profile_action=action
        self.profile_return=self.mode
        self.set_mode('profiles')

    def select_profile(self, path, data):
        if self.profile_action == 'new':
            if data or path.exists():
                self.notify(self.words('Slot sudah terisi. Pilih slot kosong.','Occupied slot. Please select an empty slot.'))
                return
            self.wizard={'path':path,'name':'','gender':'male','style':0,'step':0}
            self.set_mode('setup')
            pg.key.start_text_input()
            return
        if not data:
            self.notify(self.words('Slot kosong.','Empty slot.'))
            return
        self.save_current()
        self.save_path=path
        if int(data.get('version',3))<4:
            backup=ROOT/'.openrpg/backups'/f'{path.stem}-before-adventure-{time.time_ns()}.json'
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,backup)
        self.life=Life.load(path)
        self.activate_profile()

    def activate_profile(self):
        self.playing=True
        self._music_key=None
        self.selected=self.life.character
        self.wildlife=Wildlife(self.life)
        self.wild_pokemon=[]
        self.reserve_trainers=[]
        for trainer in self.route_trainers:
            trainer.update(defeated=False,paid=False,cooldown=0)
        self.battle=None
        self.fishing=None
        self.dead_active=False
        self.dead_timer=0
        self.center_selected=0
        self.center_page=0
        self.last_save=self.life.elapsed
        self.last_location=(self.life.scene,int(self.life.x//1280),int(self.life.y//1600))
        self.encounter_grace=15
        # Cache the active team and the three Pokémon used in the sanctuary
        # entrance before showing the world. Remaining species stay on-demand.
        self.asset_loading_ids = list(dict.fromkeys(
            self.active_pokemon_team() + [1, 15, 16]))
        for ident in self.asset_loading_ids:
            self.pokedex.request(ident)
        self.set_mode('asset_loading')
        pg.key.stop_text_input()
        self.notify(self.words('B terminal · J misi harian · E interaksi · P Pokédex','B terminal · J daily quests · E interact · P Pokédex'))

    def asset_loading_progress(self):
        statuses = [self.pokedex.media_status.get(ident, 'loading') for ident in self.asset_loading_ids]
        ready = sum(status == 'ready' for status in statuses)
        settled = sum(status in ('ready', 'failed') for status in statuses)
        return ready, settled, len(statuses), statuses

    def retry_missing_sprites(self):
        for ident in self.asset_loading_ids:
            if self.pokedex.media_status.get(ident) == 'failed':
                self.pokedex.request(ident)

    def continue_after_asset_loading(self):
        _, _, _, statuses = self.asset_loading_progress()
        failed = sum(status == 'failed' for status in statuses)
        self.set_mode('game')
        if failed:
            self.notify(self.words(
                f'{failed} sprite belum terunduh. Periksa internet; Pokémon lain akan dimuat saat ditemukan.',
                f'{failed} sprites could not be downloaded. Check your connection; other Pokémon load when encountered.'))

    def draw_asset_loading(self):
        self.canvas.fill((12, 19, 38))
        self.text(self.words('MENYIAPKAN DUNIA POKÉMON', 'PREPARING THE POKÉMON WORLD'), 640, 178, GOLD, self.big, True)
        self.text(self.words('Mengunduh sprite tim dan area awal. Pokémon lain dimuat saat ditemukan.',
                             'Downloading your team and starting-area sprites. Other Pokémon load as you find them.'),
                  640, 238, C, self.small, True)
        ready, settled, total, statuses = self.asset_loading_progress()
        self.text(self.words(f'Sprite siap {ready}/{total}', f'Sprites ready {ready}/{total}'), 640, 313, G, self.medium, True)
        pg.draw.rect(self.canvas, retro.PANEL, (300, 350, 680, 26))
        width = round(672 * (ready / max(1, total)))
        if width:
            pg.draw.rect(self.canvas, G, (304, 354, width, 18))
        for index, (ident, status) in enumerate(zip(self.asset_loading_ids, statuses)):
            detail = self.pokemon_data(ident) or {}
            name = detail.get('name', f'Pokémon #{ident}').title()
            mark = {'ready': '✓', 'failed': '×', 'loading': '…'}.get(status, '…')
            color = G if status == 'ready' else retro.RED if status == 'failed' else M
            self.text(f'{mark}  {name}', 365 + (index % 2) * 300, 414 + (index // 2) * 39, color, self.small)
        if settled == total and ready < total:
            failed_ids = [ident for ident, status in zip(self.asset_loading_ids, statuses) if status == 'failed']
            first_error = self.pokedex.media_errors.get(failed_ids[0], '') if failed_ids else ''
            if failed_ids:
                failed_name = (self.pokemon_data(failed_ids[0]) or {}).get('name', f'#{failed_ids[0]}').title()
                detail = f'{failed_name}: {first_error}'[:112]
                self.text(detail, 640, 526, retro.RED, self.tiny, True)
            self.text(self.words('Sebagian sprite gagal dimuat. Coba lagi atau lanjut tanpa sprite tersebut.',
                                 'Some sprites failed to load. Retry or continue without them.'),
                      640, 557, retro.GOLD, self.small, True)
        self.button(self.words('Coba lagi', 'Retry'), (330, 640, 260, 56), self.retry_missing_sprites,
                    settled == total and ready < total)
        self.button(self.words('Lewati dan mulai', 'Skip and start'), (690, 640, 260, 56),
                    self.continue_after_asset_loading, True)

    def begin(self):
        if self.playing:
            self.set_mode('game')
        elif self.save_path.exists():
            self.activate_profile()
        else:
            self.open_profiles('new')

    def manual_save(self):
        if not self.playing:
            self.notify(self.words('Mulai atau muat permainan dahulu.','Start or load a game first.'))
            return
        self.save_current()
        self.notify(self.words('Permainan tersimpan.','Game saved.'))

    def next_setup(self):
        w=self.wizard
        if w['step']==0 and not w['name'].strip():
            self.notify(self.words('Isi nama petualang dahulu.','Enter your adventurer name.'))
            return
        w['step']+=1
        pg.key.stop_text_input()
        self.nav_mode=None
        if w['step']==3:
            w['starter']=random.SystemRandom().choice(STARTERS)
            w['level']=random.SystemRandom().randint(3,5)
            self.pokedex.request(w['starter'])
            self.play_pokemon_cry(w['starter'])
        elif w['step']>3:
            self.save_current()
            ident=w['starter']; key=str(ident)
            self.life=Life(player_name=w['name'].strip(),gender=w['gender'],character=w['style'],language=self.life.language,
                           music_volume=self.life.music_volume,effects_volume=self.life.effects_volume,cry_volume=self.life.cry_volume,reduced_motion=self.life.reduced_motion,
                           pokemon_party=[ident],pokemon_caught=[ident],pokemon_seen=[ident],pokemon_active=[ident],
                           pokemon_levels={key:w['level']},pokemon_xp={key:0},pokemon_health={key:100})
            self.save_path=w['path']
            self.activate_profile()
            self.save_current()

    def title(self):
        self.canvas.fill((12,19,38))
        for i in range(52):
            x=(i*127)%1280; y=(i*83)%800
            pg.draw.rect(self.canvas,(36,54,82),(x,y,3,3))
        self.text('OPENRPG',85,116,GOLD,self.logo_font)
        self.text('A LITTLE LIFE. A BIG ADVENTURE.',90,209,G,self.medium)
        self.text(self.words('Berkebun. Bertarung. Berkarya.','Grow. Battle. Create.'),90,266,C,self.font)
        for i,style in enumerate((0,2,3)):
            self.art.character(self.canvas,190+i*145,518,style,4,self.frame,True,'down')
        self.text('01 / ADVENTURE BEGINS HERE',90,625,M,self.small)
        options=[(self.words('Permainan baru','New Game'),lambda:self.open_profiles('new')),
                 (self.words('Muat permainan','Load Game'),lambda:self.open_profiles('load')),
                 (self.words('Simpan permainan','Save Game'),self.manual_save),
                 (self.words('Pengaturan','Settings'),self.open_settings)]
        if self.playing:
            options.insert(0,(self.words('Lanjutkan','Continue'),lambda:self.set_mode('game')))
        for i,(label,callback) in enumerate(options):
            self.button(label,(760,222+i*73,405,58),callback,i==0)
        self.text('ARROWS / ENTER     •     MOUSE',760,657,M,self.small)
        if time.monotonic()<self.toast_until:
            self.text(self.toast[:100],90,736,G,self.small)

    def draw_profiles(self):
        self.text(self.words('PILIH PROFIL','CHOOSE PROFILE'),110,80,GOLD,self.big)
        self.text(self.words('Save lama tetap tersedia. Slot baru memiliki perjalanan sendiri.','Your original save is preserved. Each slot has its own adventure.'),110,143,M,self.small)
        for i,(path,data) in enumerate(self.profile_slots()):
            y=195+i*89
            name=(data or {}).get('player_name') or self.words('Petualang lama','Legacy adventurer')
            label=f'{i+1:02}   '+(name if data else self.words('Slot kosong — mulai baru','Empty slot — start fresh'))
            self.button(label,(110,y,530,65),lambda p=path,d=data:self.select_profile(p,d))
            if data:
                self.text(f"Day {data.get('day',1)} / {data.get('scene','outdoors')} / ${data.get('money',0)}",675,y+8,G,self.small)
                self.text(data.get('saved_at','')[:19],675,y+34,M,self.small)
        self.button(self.words('Kembali','Back'),(930,695,240,48),lambda:self.set_mode(self.profile_return))

    def draw_setup(self):
        w=self.wizard;step=w['step']
        self.text(self.words('PETUALANG BARU','NEW ADVENTURER'),110,80,GOLD,self.big)
        names=[self.words('Nama','Name'),self.words('Gender','Gender'),self.words('Penampilan','Appearance'),self.words('Partner acak','Random partner')]
        for i,name in enumerate(names):
            self.text(f'{i+1:02} {name}',110+i*275,158,G if i<=step else M,self.font)
        if step==0:
            self.text(self.words('Siapa namamu?','What is your name?'),160,280,C,self.medium)
            self.box((160,345,920,78),retro.PANEL)
            self.text(w['name']+('|' if int(self.frame/30)%2 else ''),185,369,G,self.medium)
            self.text(self.words('Maksimal 18 karakter','Up to 18 characters'),160,450,M,self.small)
        elif step==1:
            for i,(value,id_name,en_name) in enumerate((('male','Laki-laki','Male'),('female','Perempuan','Female'))):
                self.button(self.words(id_name,en_name),(240+i*420,325,360,85),lambda v=value:self.select_gender(v),w['gender']==value)
        elif step==2:
            choices=(0,1,3,4,5) if w['gender']=='male' else (2,6,7,8)
            for i,style in enumerate(choices):
                x=110+i*215
                self.button('',(x,295,195,190),lambda st=style:w.update(style=st))
                if w['style']==style:pg.draw.rect(self.canvas,G,(x+2,297,191,186),2)
                self.text(PLAYER_STYLES[style],x+97,453,C,self.small,True)
                self.art.character(self.canvas,x+98,413,style,3,self.frame,True,'down')
            self.text('Ninja Adventure / Pixel-Boy + AAA / CC0',110,535,M,self.small)
        else:
            ident=w['starter'];d=self.pokemon_data(ident) or pokemon_db.detail(ident) or {}
            sprite=self.pokemon_surface(ident,180)
            if sprite:self.canvas.blit(sprite,sprite.get_rect(center=(400,395)))
            self.text(d.get('name',f'#{ident}').title(),630,315,GOLD,self.big)
            self.text(f"LEVEL {w['level']}",635,382,G,self.medium)
            self.text(' / '.join(t['type']['name'].upper() for t in d.get('types',[])),635,430,C,self.font)
            self.text(self.words('Partner pertamamu siap menjelajah!','Your first partner is ready to explore!'),635,478,M,self.small)
        self.button(self.words('Mulai petualangan','Start adventure') if step==3 else self.words('Lanjut','Continue'),(870,655,300,57),self.next_setup,True)
        self.button(self.words('Batal','Cancel'),(110,655,200,57),lambda:self.set_mode('title'))

    def select_gender(self,value):
        self.wizard.update(gender=value,style=0 if value=='male' else 2)

    def collection_select(self,index):
        self.center_search=False
        pg.key.stop_text_input()
        self.center_selected=index
        self.assigning_slot=True
        self.nav_index=1+min(8,len(self.filtered_collection()[self.center_page*8:self.center_page*8+8]))
        ident=self.center_pokemon_id()
        self.pokedex.request(ident); self.pokedex.request_species(ident)

    def assign_slot(self,slot):
        ident=self.center_pokemon_id();active=self.life.pokemon_active
        if ident in active:
            old=active.index(ident)
            if slot<len(active):active[old],active[slot]=active[slot],active[old]
        elif slot<len(active):active[slot]=ident
        elif len(active)<3:active.append(ident)
        self.assigning_slot=False
        self.save_current()
        self.center_message=self.words('Tim aktif diperbarui.','Active team updated.')

    def center_cost(self):
        missing=0
        for ident in self.life.pokemon_active:
            d=self.pokemon_data(ident) or pokemon_db.detail(ident)
            maximum=self.base_stat(d,'hp',45)+self.pokemon_level(ident)*2
            missing+=max(0,maximum-self.life.pokemon_health.get(str(ident),maximum))
        return min(20,max(5,math.ceil(missing/12))) if missing else 0

    def heal_pokemon_party(self):
        cost=self.center_cost()
        if self.life.money<cost:
            self.center_message=self.words('Uang belum cukup. Istirahat di rumah atau jual hasil tani.','Not enough coins. Rest at home or sell farm goods.')
            return
        self.life.money-=cost
        for ident in self.life.pokemon_active:
            d=self.pokemon_data(ident) or pokemon_db.detail(ident)
            self.life.pokemon_health[str(ident)]=self.base_stat(d,'hp',45)+self.pokemon_level(ident)*2
        self.center_message=self.words(f'Tim pulih! Biaya {cost} koin.',f'Team restored! Cost: {cost} coins.')
        self.save_current();self.play_action_sound('pickup-rare',.3)

    def buy_center_pokeballs(self):
        remaining=max(0,10-int(self.life.bag.get('Pokeball',0)))
        quantity=min(5,remaining)
        if quantity<=0:
            self.center_message=self.words('Tas sudah penuh: maksimal 10 Poké Ball.','Bag is full: maximum 10 Poké Balls.')
            self.play_action_sound('not-enough-money',.25)
            return
        self.trade('Pokeball',True,quantity)

    def open_pokemon_center(self):
        if self.life.scene!='reserve' or min(math.hypot(self.life.x-x,self.life.y-y) for x,y in RESERVE_CENTERS)>150:
            self.notify(self.words('Dekati Pokémon Center untuk perawatan.','Approach a Pokémon Center for service.'));return
        self.center_selected=0;self.center_page=0;self.assigning_slot=False;self.center_query='';self.center_search=False
        self.center_message=self.words('Pilih koleksi, lalu pilih slot aktif.','Select a Pokémon, then choose an active slot.')
        self.set_mode('center')

    def draw_center(self):
        self.canvas.fill((12,19,38))
        self.text('POKÉMON CENTER',65,47,GOLD,self.big)
        self.text(self.center_message[:100],65,107,G,self.small)
        self.button(self.words('Cari: ','Search: ')+self.center_query+('|' if self.center_search else ''),(65,152,473,40),self.search_collection)
        collection=self.filtered_collection()
        entries=collection[self.center_page*8:self.center_page*8+8]
        for i,ident in enumerate(entries):
            x=65+(i%2)*245;y=207+(i//2)*101
            d=self.pokemon_data(ident) or pokemon_db.detail(ident) or {}
            self.pokedex.request(ident) if ident not in self.poke_surfaces else None
            self.button('',(x,y,228,87),lambda idx=self.life.pokemon_party.index(ident):self.collection_select(idx))
            if ident==self.center_pokemon_id():pg.draw.rect(self.canvas,G,(x+2,y+2,224,83),2)
            spr=self.pokemon_surface(ident,55)
            if spr:self.canvas.blit(spr,spr.get_rect(center=(x+36,y+42)))
            self.text(d.get('name',f'#{ident}').title(),x+71,y+21,C,self.small)
            self.text(f'Lv.{self.pokemon_level(ident)}',x+71,y+48,G,self.small)
        self.text(self.words('TIM AKTIF / PILIH SLOT','ACTIVE TEAM / CHOOSE SLOT'),605,155,C,self.medium)
        for slot in range(3):
            ident=self.life.pokemon_active[slot] if slot<len(self.life.pokemon_active) else None
            d=(self.pokemon_data(ident) or pokemon_db.detail(ident) or {}) if ident else {}
            self.button('',(610,210+slot*99,590,81),lambda sl=slot:self.assign_slot(sl))
            self.text(f"{slot+1}   {d.get('name',self.words('Kosong','Empty')).title()}",632,227+slot*99,C,self.font)
            if ident:self.text(f"HP {min(self.life.pokemon_health.get(str(ident),0),self.base_stat(d,'hp',45)+self.pokemon_level(ident)*2)}   /   Lv.{self.pokemon_level(ident)}",665,258+slot*99,G,self.small)
        ident=self.center_pokemon_id()
        self.text(self.words('Pilihan: ','Selected: ')+(self.pokemon_data(ident) or pokemon_db.detail(ident) or {}).get('name',str(ident)).title(),610,530,G,self.font)
        selected=self.pokemon_data(ident) or {}
        self.text(' / '.join(t['type']['name'].upper() for t in selected.get('types',[]))+f'   Lv.{self.pokemon_level(ident)}',610,555,M,self.small)
        self.text(' / '.join(m['name'] for m in self.skills_for(ident)[:2])[:64],610,649,G,self.small)
        balls=int(self.life.bag.get('Pokeball',0));quantity=min(5,max(0,10-balls))
        self.text(self.words(f'Poké Ball {balls}/10  ·  Uang {self.life.money} koin',
                             f'Poké Balls {balls}/10  ·  Money {self.life.money} coins'),65,548,M,self.small)
        purchase_label=(self.words(f'Beli {quantity} Poké Ball · {quantity*BUY["Pokeball"]} koin',
                                   f'Buy {quantity} Poké Balls · {quantity*BUY["Pokeball"]} coins')
                        if quantity else self.words('Kapasitas Poké Ball penuh','Poké Ball capacity full'))
        self.button(purchase_label,(65,575,473,45),self.buy_center_pokeballs,quantity>0)
        self.button(self.words('Pulihkan tim','Heal team')+f' / ${self.center_cost()}',(610,575,285,50),self.heal_pokemon_party)
        self.button(self.words('Evolusi','Evolve')+' / $10',(915,575,285,50),self.evolve_selected)
        self.button('<',(65,632,75,45),lambda:self.page_center(-1))
        self.text(f'{self.center_page+1} / {max(1,math.ceil(len(self.filtered_collection())/8))}',160,645,M,self.small)
        self.button('>',(290,632,75,45),lambda:self.page_center(1))
        self.button(self.words('Aktifkan / keluarkan','Add / remove active'),(610,687,285,50),self.toggle_active_pokemon)
        self.button(self.words('Kembali','Back')+' / Esc',(915,687,285,50),self.back)

    def filtered_collection(self):
        if not self.center_query:return self.life.pokemon_party
        names={e['id']:e['name'] for e in self.pokedex.catalog}
        query=self.center_query.strip().lower()
        return [ident for ident in self.life.pokemon_party if query in names.get(ident,'') or query==str(ident)]

    def search_collection(self):
        self.center_search=True
        pg.key.start_text_input()

    def page_center(self,delta):
        self.center_page=(self.center_page+delta)%max(1,math.ceil(len(self.filtered_collection())/8))
        self.nav_index=0

    def check_daily_quest_rewards(self):
        for q in self.life.daily_quests:
            if q.get('progress',0)>=q['target'] and not q.get('notified') and not q.get('claimed'):
                q['notified']=True
                self.notify(self.words('Misi selesai! J untuk klaim hadiah.','Quest complete! Press J to claim your reward.'))

    def claim_daily(self,q):
        amount=self.life.claim_quest(q)
        if not amount:return
        self.show_reward(f'+{amount} COINS','daily_quests')

    def claim_bonus(self):
        if self.life.claim_daily_bonus():self.show_reward('+25 COINS / +1 GACHA TICKET','daily_quests')

    def show_reward(self,label,back,ident=None):
        self.reward={'label':label,'back':back,'pokemon':ident,'started':time.monotonic()}
        self.save_current();self.play_action_sound('pickup-rare',.4);self.set_mode('reward')

    def open_gacha(self):
        if self.life.gacha_tickets<1:
            self.notify(self.words('Selesaikan semua daily untuk tiket.','Complete all daily quests to earn a ticket.'));return
        self.life.gacha_tickets-=1
        pool=random.SystemRandom().choices((STARTERS,(147,246,280,443,633),(133,447,371)),weights=(80,15,5))[0]
        ident=random.SystemRandom().choice(pool)
        duplicate=ident in self.life.pokemon_party
        if not duplicate:
            self.life.pokemon_party.append(ident)
            self.life.pokemon_caught=list(dict.fromkeys(self.life.pokemon_caught+[ident]))
            self.life.pokemon_seen=list(dict.fromkeys(self.life.pokemon_seen+[ident]))
            self.life.pokemon_levels[str(ident)]=random.randint(3,5)
            self.life.pokemon_health[str(ident)]=100
        else:
            self.life.money+=40
        self.pokedex.request(ident)
        self.show_reward(self.words('Duplikat: +40 koin','Duplicate: +40 coins') if duplicate else self.words('Partner baru!','New partner!'),'daily_quests',ident)
        self.play_pokemon_cry(ident)

    def draw_daily_quests(self):
        self.canvas.fill((12,19,38));self.life.ensure_daily_quests()
        self.text(self.words('PAPAN MISI HARIAN','DAILY QUEST BOARD'),70,60,GOLD,self.big)
        self.text(f'DAY {self.life.day:02}   /   ${self.life.money}   /   TICKETS {self.life.gacha_tickets}',75,125,G,self.font)
        quests=self.life.daily_quests+[q for q in self.life.quest_archive if not q.get('claimed')]
        pages=max(1,math.ceil(len(quests)/3));self.daily_page=min(self.daily_page,pages-1)
        for i,q in enumerate(quests[self.daily_page*3:self.daily_page*3+3]):
            y=185+i*133
            self.box((70,y,1140,112),retro.PANEL)
            self.emoji(q.get('emoji','⭐'),(120,y+53),42)
            title=q['title'] if self.life.language=='id' else q.get('title_en',q['title'])
            self.text(title,169,y+21,C,self.font)
            self.text(f"{q.get('progress',0)} / {q['target']}    +{q['reward']} coins",170,y+59,M,self.small)
            retro.meter(self.canvas,(565,y+67,250,12),q.get('progress',0),q['target'],G)
            ready=q.get('progress',0)>=q['target']
            label=self.words('Diambil','Claimed') if q['claimed'] else self.words('Klaim','Claim') if ready else self.words('Belum selesai','In progress')
            self.button(label,(904,y+29,277,54),lambda quest=q:self.claim_daily(quest),ready and not q['claimed'])
        self.button(self.words('Bonus semua misi','All quests bonus'),(70,608,355,52),self.claim_bonus)
        self.button(f'GACHA / {self.life.gacha_tickets} TICKET',(445,608,355,52),self.open_gacha)
        self.text('80% starter / 15% uncommon / 5% special',445,678,M,self.tiny)
        self.text(self.words('Duplikat ditukar 40 koin.','Duplicates convert to 40 coins.'),445,701,M,self.tiny)
        self.button(self.words('Kembali','Back'),(960,690,250,48),self.back)
        if pages>1:self.button(f'{self.daily_page+1}/{pages} >',(70,690,250,48),lambda:setattr(self,'daily_page',(self.daily_page+1)%pages))

    def emoji(self,value,center,size):
        icon=self.emoji_font.render(value,True,C)
        ratio=size/max(icon.get_size())
        icon=pg.transform.scale(icon,(max(1,int(icon.get_width()*ratio)),max(1,int(icon.get_height()*ratio))))
        self.canvas.blit(icon,icon.get_rect(center=center))

    def draw_reward(self):
        r=self.reward;t=time.monotonic()-r['started'];self.canvas.fill((12,19,38))
        for i in range(32):
            angle=i*math.tau/32+t*.3;radius=125+(i%4)*30+min(1,t)*65
            pg.draw.rect(self.canvas,GOLD if i%2 else G,(640+math.cos(angle)*radius,352+math.sin(angle)*radius,5,5))
        self.text(self.words('HADIAH DITERIMA','REWARD CLAIMED'),640,126,GOLD,self.big,True)
        ident=r.get('pokemon')
        if ident:
            sprite=self.pokemon_surface(ident,170)
            if sprite:self.canvas.blit(sprite,sprite.get_rect(center=(640,348)))
            d=self.pokemon_data(ident) or pokemon_db.detail(ident) or {}
            self.text(d.get('name',f'#{ident}').title(),640,493,C,self.medium,True)
        else:self.emoji('🎁',(640,345),100)
        self.text(r['label'],640,556,G,self.medium,True)
        self.button(self.words('Lanjut','Continue'),(465,662,350,55),lambda:self.set_mode(r['back']),True)

    def draw_invitation(self):
        inv=self.invitation
        self.canvas.fill((12,19,38))
        trainer=inv.get('trainer');pokemon=inv.get('wild')
        opponent_id=int(pokemon['id']) if pokemon else int((trainer or {}).get('team',[1])[0])
        opponent_detail=self.pokemon_data(opponent_id) or pokemon_db.detail(opponent_id) or {}
        opponent_name=opponent_detail.get('name',f'Pokémon #{opponent_id}').title()
        title=(trainer['name'] if trainer else opponent_name)
        self.text(self.words('TANTANGAN BARU','A NEW CHALLENGER'),640,72,GOLD,self.big,True)
        self.text(title,640,125,C,self.medium,True)
        self.text(self.words('Ingin bertarung? Kamu boleh menolak.','Ready for a battle? You can decline.'),640,165,M,self.small,True)

        # Rival card: show the actual Pokémon sprite, even when an NPC trainer
        # initiated the challenge. Missing media gets requested from PokéAPI.
        self.box((126,205,358,330),retro.PANEL,10,retro.MUTED)
        self.text(self.words('POKÉMON LAWAN','OPPONENT POKÉMON'),305,230,retro.GOLD,self.small,True)
        if opponent_id not in self.poke_surfaces:
            self.pokedex.request(opponent_id)
        rival_sprite=self.pokemon_surface(opponent_id,174)
        if rival_sprite:
            rival_sprite=rival_sprite.copy()
            rival_sprite=pg.transform.flip(rival_sprite,True,False)
            self.canvas.blit(rival_sprite,rival_sprite.get_rect(center=(305,356)))
        else:
            self.text('…',305,355,C,self.big,True)
        opponent_level=pokemon.get('level',5) if pokemon else (trainer or {}).get('level',5)
        opponent_types=' · '.join(t['type']['name'].title() for t in opponent_detail.get('types',[]))
        self.text(opponent_name,305,465,C,self.font,True)
        self.text(self.words(f'Lv. {opponent_level}',f'Lv. {opponent_level}')+'  ·  '+(opponent_types or self.words('Memuat tipe…','Loading types…')),
                  305,499,retro.GREEN,self.tiny,True)

        # Show the player's whole active lineup (at most three) so the player
        # can see which team will enter the battle before accepting.
        team=self.active_pokemon_team()[:3]
        self.box((524,205,630,330),retro.PANEL,10,retro.MUTED)
        self.text(self.words('TIM AKTIF ANDA','YOUR ACTIVE TEAM'),839,230,retro.GOLD,self.small,True)
        card_w=184;gap=17;total=len(team)*card_w+max(0,len(team)-1)*gap
        start_x=839-total/2
        for i,ident in enumerate(team):
            x=int(start_x+i*(card_w+gap));y=257
            self.box((x,y,card_w,248),retro.INK,8,retro.MUTED)
            if ident not in self.poke_surfaces:
                self.pokedex.request(ident)
            sprite=self.pokemon_surface(ident,112)
            if sprite:
                self.canvas.blit(sprite,sprite.get_rect(center=(x+card_w//2,y+77)))
            detail=self.pokemon_data(ident) or pokemon_db.detail(ident) or {}
            member_name=detail.get('name',f'Pokémon #{ident}').title()
            self.text(f'{i+1}. {member_name}',x+card_w//2,y+151,C,self.tiny,True)
            level=self.pokemon_level(ident)
            hp=self.life.pokemon_health.get(str(ident),0)
            maximum=self.base_stat(detail,'hp',45)+level*2
            self.text(f'Lv. {level}  ·  HP {min(hp,maximum)}/{maximum}',x+card_w//2,y+179,retro.GREEN,self.tiny,True)
            member_types=' / '.join(t['type']['name'].upper() for t in detail.get('types',[]))
            if member_types:self.text(member_types,x+card_w//2,y+209,retro.MUTED,self.tiny,True)

        self.text(self.words('Satu Pokémon akan turun lebih dulu; tim aktif maksimal 3.','One Pokémon enters first; active team limit is 3.'),640,568,M,self.tiny,True)
        self.button(self.words('Terima','Accept'),(300,630,310,58),self.accept_invitation,True)
        self.button(self.words('Tolak','Decline'),(670,630,310,58),self.decline_invitation)

    def accept_invitation(self):
        inv=self.invitation;self.encounter_grace=25
        if inv.get('trainer'):self.begin_pokemon_battle(inv['trainer']['team'][0],trainer=inv['trainer'])
        else:self.begin_pokemon_battle(inv['wild']['id'],wild=inv['wild'])
        if self.mode!='battle':self.set_mode('game')
        self.invitation=None

    def decline_invitation(self):
        self.invitation=None;self.encounter_grace=25;self.set_mode('game')

    def update_challenges(self,dt):
        self.encounter_grace=max(0,self.encounter_grace-dt)
        if self.mode!='game' or self.encounter_grace or self.needs_depleted() or self.fishing:return
        actors=[(t,'trainer') for t in self.route_trainers+self.reserve_trainers if (t.get('scene','reserve')==self.life.scene)]
        if self.life.scene=='reserve':actors += [(p,'wild') for p in self.wild_pokemon]
        for actor,kind in actors:
            if kind=='wild':actor['cooldown']=max(0,actor.get('cooldown',0)-dt)
            distance=math.hypot(actor['x']-self.life.x,actor['y']-self.life.y)
            if distance>360:
                actor.pop('challenge_roll',None);actor.pop('approaching',None);continue
            if distance<240 and 'challenge_roll' not in actor and actor.get('cooldown',0)<=0:
                actor['challenge_roll']=self.pokemon_rng.random()<.3
                actor['approaching']=actor['challenge_roll']
            if actor.get('approaching'):
                if distance>75:
                    step=min(distance,95*dt)
                    nx=actor['x']+(self.life.x-actor['x'])/distance*step
                    ny=actor['y']+(self.life.y-actor['y'])/distance*step
                    if not any(o.collidepoint(nx,ny) for o in self.obstacles()):
                        actor['x'],actor['y']=nx,ny
                    else:
                        actor['approaching']=False;actor['cooldown']=30
                else:
                    actor['approaching']=False;actor['cooldown']=45
                    self.invitation={kind:actor};self.set_mode('invitation');return

    def overlay(self):
        custom={'profiles':self.draw_profiles,'setup':self.draw_setup,'reward':self.draw_reward,
                'invitation':self.draw_invitation,'asset_loading':self.draw_asset_loading}
        if self.mode in custom:
            self.buttons=[];self.canvas.fill((12,19,38));custom[self.mode]()
        else:super().overlay()

    def draw(self):
        if self.nav_mode!=self.mode:
            self.dex_menu_focus=False
            self.nav_index=0;self.nav_mode=self.mode;self.keyboard_focus=True
        super().draw()

    def handle(self,event):
        if event.type==pg.MOUSEMOTION:self.keyboard_focus=False
        if event.type==pg.MOUSEBUTTONDOWN and event.button==1:
            for i,(rect,_) in enumerate(self.buttons):
                if rect.collidepoint(self.mouse()):self.nav_index=i;break
        if self.mode=='center' and self.center_search:
            if event.type==pg.TEXTINPUT:
                self.center_query=(self.center_query+event.text.lower())[:24];self.center_page=0;return
            if event.type==pg.KEYDOWN:
                if event.key==pg.K_BACKSPACE:
                    self.center_query=self.center_query[:-1];self.center_page=0;return
                if event.key in (pg.K_RETURN,pg.K_ESCAPE):
                    self.center_search=False;pg.key.stop_text_input();self.nav_index=1;return
        if self.mode=='setup' and self.wizard.get('step')==0:
            if event.type==pg.TEXTINPUT:
                self.wizard['name']=''.join(c for c in self.wizard['name']+event.text if c.isprintable())[:18];return
            if event.type==pg.KEYDOWN:
                if event.key==pg.K_BACKSPACE:
                    self.wizard['name']=self.wizard['name'][:-1]
                elif event.key in (pg.K_RETURN,pg.K_KP_ENTER):
                    self.next_setup()
                elif event.key==pg.K_ESCAPE:
                    self.set_mode('title');pg.key.stop_text_input()
                # Consume every key while editing the name so letters that are
                # also game shortcuts cannot activate menus or leave setup.
                return
        if self.mode=='battle' and event.type==pg.KEYDOWN and self.battle and any(self.battle.get(k) for k in ('ultimate_cutin','capture')) and event.key!=pg.K_ESCAPE:
            return
        if self.mode=='battle' and event.type==pg.KEYDOWN and event.key==pg.K_UP and self.battle:
            self.battle['jump_buffer']=.14
        if self.mode=='invitation' and event.type==pg.KEYDOWN and event.key==pg.K_ESCAPE:
            self.decline_invitation();return
        menus=self.mode not in ('terminal','phone','game','battle','dead','evolution')
        if event.type==pg.KEYDOWN and menus:
            if self.mode in ('dex','map') and event.key==pg.K_TAB:
                self.dex_menu_focus=not getattr(self,'dex_menu_focus',False);return
            custom_arrows=self.mode in ('map','dex') and not getattr(self,'dex_menu_focus',False)
            if not custom_arrows and event.key in (pg.K_UP,pg.K_DOWN,pg.K_LEFT,pg.K_RIGHT,pg.K_TAB):
                if self.buttons:
                    self.nav_index=min(self.nav_index,len(self.buttons)-1)
                    origin=self.buttons[self.nav_index][0].center
                    dx,dy={pg.K_LEFT:(-1,0),pg.K_RIGHT:(1,0),pg.K_UP:(0,-1),pg.K_DOWN:(0,1),pg.K_TAB:(0,1)}[event.key]
                    choices=[]
                    for i,(rect,_) in enumerate(self.buttons):
                        x,y=rect.center;forward=(x-origin[0])*dx+(y-origin[1])*dy
                        side=abs((x-origin[0])*dy-(y-origin[1])*dx)
                        if forward>1:choices.append((forward+side*2,i))
                    self.nav_index=min(choices)[1] if choices else (self.nav_index+(1 if dx+dy>0 else -1))%len(self.buttons)
                    self.keyboard_focus=True;self.play_action_sound('ui-click',.16)
                return
            if not custom_arrows and event.key in (pg.K_RETURN,pg.K_KP_ENTER):
                if self.buttons:
                    self.buttons[min(self.nav_index,len(self.buttons)-1)][1]()
                    self.play_action_sound('ui-confirm',.22)
                return
            if self.mode in ('profiles','setup','reward') and event.key==pg.K_ESCAPE:
                self.set_mode(self.reward['back'] if self.mode=='reward' else 'title');pg.key.stop_text_input();return
        super().handle(event)

    def update(self,dt):
        if self.mode == 'asset_loading':
            self.frame += dt * 60
            self.terminal.poll();self.load_pokemon_events();self.load_countdown_audio()
            ready, settled, total, statuses = self.asset_loading_progress()
            if settled == total and ready == total:
                self.continue_after_asset_loading()
            return
        if not self.playing and self.mode in ('title','settings','profiles','setup'):
            self.frame+=dt*60
            self.terminal.poll();self.load_pokemon_events();self.load_countdown_audio()
            self.update_location_audio()
            return
        before=getattr(self,'last_location',None)
        super().update(dt)
        after=(self.life.scene, int(self.life.x//1280),int(self.life.y//1600))
        if before is not None and before!=after:self.life.record_daily_quest('explore',unique=str(after))
        self.last_location=after
        self.update_challenges(dt)

    def quit(self):
        self.save_current();self.running=False

    def set_audio(self,key,delta):
        setattr(self.life,key,round(max(0,min(1,getattr(self.life,key)+delta)),1))
        if pg.mixer.get_init():pg.mixer.music.set_volume(.28*self.life.music_volume)
        self.save_preferences();self.save_current()

    def save_preferences(self):
        path=ROOT/'.openrpg/preferences.json'
        tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps({key:getattr(self.life,key) for key in ('language','music_volume','effects_volume','cry_volume','reduced_motion')}))
        tmp.replace(path)

    def set_language(self,language):
        super().set_language(language);self.save_preferences()

    def toggle_motion(self):
        self.life.reduced_motion=not self.life.reduced_motion
        self.save_preferences();self.save_current()

    def draw_settings(self):
        self.canvas.fill((12,19,38))
        self.text(self.words('PENGATURAN','SETTINGS'),110,75,GOLD,self.big)
        self.button('Bahasa Indonesia',(110,170,500,65),lambda:self.set_language('id'),self.life.language=='id')
        self.button('English',(650,170,500,65),lambda:self.set_language('en'),self.life.language=='en')
        for i,(key,label) in enumerate((('music_volume',self.words('Musik','Music')),('effects_volume',self.words('Efek suara','Sound effects')),('cry_volume','Pokémon cry'))):
            y=290+i*85
            self.text(label,110,y+14,C,self.font)
            self.button('-', (650,y,75,50),lambda k=key:self.set_audio(k,-.1))
            value=getattr(self.life,key)
            self.text(f'{int(value*100)}%',840,y+26,G,self.medium,True)
            self.button('+',(1050,y,75,50),lambda k=key:self.set_audio(k,.1))
        self.button(self.words('Kurangi kilatan','Reduce flashes')+(' / ON' if self.life.reduced_motion else ' / OFF'),(110,580,580,55),self.toggle_motion)
        self.button(self.words('Kembali','Back'),(870,690,280,50),self.back)

    def play_action_sound(self,sound_name,volume=.42):
        return super().play_action_sound(sound_name,volume*self.life.effects_volume)

    def play_battle_sound(self,sound_name,volume=.52):
        return super().play_battle_sound(sound_name,volume*self.life.effects_volume)

    def play_pokemon_cry(self,ident):
        sound=self.pokemon_sounds.get(int(ident))
        if sound:sound.set_volume(self.life.cry_volume)
        return super().play_pokemon_cry(ident)

    def hud(self,station):
        super().hud(station)
        if self.playing and time.monotonic()-getattr(self,'saved_toast_at',0)<2:
            self.text(self.words('TERSIMPAN','SAVED'),1178,665,G,self.tiny,True)

    def evolve_selected(self):
        if self.life.money<10:
            self.center_message=self.words('Evolusi membutuhkan 10 koin.','Evolution service costs 10 coins.')
            return
        super().evolve_selected()

    def finish_evolution(self):
        was_active=self.evolution_anim is not None
        super().finish_evolution()
        if was_active:
            self.life.money=max(0,self.life.money-10)
            self.save_current()
