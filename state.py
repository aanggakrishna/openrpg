"""Small persistent life simulation, independent of rendering."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import random
from world_regions import weather_for

ITEMS = ("Sayur", "Ikan", "Telur", "Makanan", "Daging", "Kulit", "Kayu", "Obat", "Tombak", "Busur", "Panah", "Pokeball")
BUY = {"Makanan": 24, "Obat": 35, "Tombak": 80, "Busur": 160, "Panah": 3, "Pokeball": 12}
SELL = {"Sayur": 9, "Ikan": 15, "Telur": 12, "Makanan": 16, "Daging": 20, "Kulit": 25, "Kayu": 6}
WEAPONS = {"Tombak": {"damage": 28, "reach": 88, "cooldown": .55},
           "Busur": {"damage": 24, "reach": 390, "cooldown": .7}}


@dataclass
class Life:
    player_name: str = "Adventurer"
    gender: str = "male"
    music_volume: float = 1.0
    effects_volume: float = 1.0
    cry_volume: float = 1.0
    reduced_motion: bool = False
    gacha_tickets: int = 0
    quest_bonus_day: int = 0
    quest_archive: list = field(default_factory=list)
    saved_at: str = ""
    character: int = 0
    scene: str = "outdoors"
    x: float = 490
    y: float = 490
    day: int = 1
    minutes: float = 480
    elapsed: float = 0
    stats: dict = field(default_factory=lambda: {"Kenyang": 85.0, "Minum": 85.0, "Energi": 90.0, "Senang": 80.0})
    bag: dict = field(default_factory=lambda: {"Sayur": 3, "Ikan": 0, "Telur": 1, "Makanan": 2, "Pokeball": 5})
    crops: list = field(default_factory=lambda: [{"stage": "empty", "ready": 0} for _ in range(6)])
    fed_at: float = -1000
    accomplishments: list = field(default_factory=list)
    health: float = 100
    money: int = 150
    trainer_xp: int = 0
    trainer_level: int = 1
    weapon: str = ""
    mounted: bool = False
    horse_x: float = 1075
    horse_y: float = 459
    horse_scene: str = "outdoors"
    weather: str = "Cerah"
    weather_hour: int = -1
    weather_override: str = ""
    animals: list = field(default_factory=list)
    kills: int = 0
    deaths: int = 0
    pokemon_party: list = field(default_factory=lambda: [1])
    pokemon_active: list = field(default_factory=lambda: [1])
    pokemon_caught: list = field(default_factory=lambda: [1])
    pokemon_seen: list = field(default_factory=lambda: [1])
    pokemon_levels: dict = field(default_factory=lambda: {"1": 5})
    pokemon_xp: dict = field(default_factory=lambda: {"1": 0})
    pokemon_health: dict = field(default_factory=lambda: {"1": 100})
    daily_quests: list = field(default_factory=list)
    quest_day: int = 0
    language: str = "id"
    version: int = 4

    def __post_init__(self):
        for item in ITEMS:
            self.bag.setdefault(item, 0)
        self.ensure_daily_quests()

    @staticmethod
    def daily_quest_pool():
        return [
            {"action": action, "target": target, "title": title, "title_en": en,
             "reward": coins, "group": group, "emoji": emoji}
            for action,target,title,en,coins,group,emoji in [
                ("plant",3,"Tanam 3 benih","Plant 3 seeds",20,"home","🌱"),
                ("water",3,"Siram 3 tanaman","Water 3 crops",20,"home","💧"),
                ("harvest",2,"Panen 2 sayur","Harvest 2 vegetables",30,"home","🥕"),
                ("feed",1,"Rawat ayam dan ambil telur","Feed chickens and collect eggs",25,"home","🥚"),
                ("cook",2,"Masak 2 makanan","Cook 2 meals",30,"home","🍳"),
                ("explore",2,"Kunjungi 2 tempat berbeda","Visit 2 different locations",25,"explore","🧭"),
                ("fish",1,"Tangkap 1 ikan","Catch 1 fish",35,"explore","🐟"),
                ("wood",2,"Kumpulkan 2 kayu","Collect 2 wood",25,"explore","🪵"),
                ("sell",3,"Jual 3 hasil tani","Sell 3 farm goods",35,"extra","🪙"),
                ("eat",1,"Nikmati masakan sendiri","Eat a home-cooked meal",15,"extra","🍲"),
                ("catch",1,"Tangkap 1 Pokémon","Catch 1 Pokémon",45,"extra","⭐"),
                ("battle",1,"Menangkan 1 duel","Win 1 battle",40,"extra","🥊"),
            ]]

    def ensure_daily_quests(self):
        if self.quest_day == self.day and self.daily_quests:
            return
        # Completed rewards survive a day change until claimed.
        for quest in self.daily_quests:
            if not quest.get("claimed") and quest.get("progress",0) >= quest["target"]:
                self.quest_archive.append(dict(quest, day=self.quest_day))
        rng = random.Random(self.day * 7919 + sum(map(ord,self.player_name)))
        pool = self.daily_quest_pool()
        self.daily_quests = [dict(rng.choice([q for q in pool if q["group"] == group]),
                                 progress=0, claimed=False, notified=False, visited=[])
                             for group in ("home","explore","extra")]
        self.quest_day = self.day

    def record_daily_quest(self, action, amount=1, unique=None):
        self.ensure_daily_quests()
        completed = []
        for quest in self.daily_quests:
            if quest["action"] != action or quest["claimed"]:
                continue
            if unique is not None:
                if unique in quest.setdefault("visited",[]):
                    continue
                quest["visited"].append(unique)
            before = quest.get("progress",0)
            quest["progress"] = min(quest["target"], before + amount)
            if before < quest["target"] <= quest["progress"]:
                completed.append(quest)
        return completed

    def claim_quest(self, quest):
        if quest.get("claimed") or quest.get("progress",0) < quest["target"]:
            return 0
        quest["claimed"] = True
        self.money += quest["reward"]
        return quest["reward"]

    def claim_daily_bonus(self):
        if self.quest_bonus_day == self.day or not all(q.get("claimed") for q in self.daily_quests):
            return False
        self.quest_bonus_day = self.day
        self.gacha_tickets += 1
        self.money += 25
        return True

    @property
    def hour(self):
        return int(self.minutes // 60)

    @property
    def daylight(self):
        return 6 <= self.hour < 18

    @property
    def period(self):
        return "Pagi" if 6 <= self.hour < 10 else "Siang" if 10 <= self.hour < 16 else "Sore" if 16 <= self.hour < 18 else "Malam"

    @property
    def market_open(self):
        return 6 <= self.hour < 22

    def advance_time(self, minutes):
        previous_day = self.day
        self.minutes += minutes
        while self.minutes >= 1440:
            self.minutes -= 1440
            self.day += 1
        if self.day != previous_day:
            self.ensure_daily_quests()
        self.weather_hour = self.day * 24 + self.hour
        self.weather = weather_for(self.scene,self.x,self.y,self.day,self.hour,self.weather_override)

    def skip_hour(self):
        self.advance_time(60)
        self.elapsed += 46.1538
        self.grow_crops()

    def grow_crops(self):
        for crop in self.crops:
            if crop["stage"] == "growing" and self.elapsed >= crop["ready"]:
                crop["stage"] = "ripe"

    def tick(self, dt, moving=False):
        self.elapsed += dt
        self.advance_time(dt * 1.3)
        for name, rate in (("Kenyang", .035), ("Minum", .05), ("Energi", .045 if moving else .014), ("Senang", .012)):
            self.stats[name] = max(0, self.stats[name] - dt * rate)
        self.grow_crops()
        if self.stats["Kenyang"] <= 0 or self.stats["Minum"] <= 0:
            self.health = max(0, self.health - dt * .5)

    def equip(self, weapon):
        if weapon and self.bag.get(weapon, 0) <= 0:
            return f"Belum membawa {weapon.lower()}. Beli di market dahulu."
        self.weapon = weapon
        return f"Senjata dipasang: {weapon or 'tanpa senjata'}."

    def heal(self):
        if self.bag["Obat"] <= 0:
            return "Tidak ada obat. Beli dari Sari di market."
        if self.health >= 100:
            return "Kesehatan sudah penuh."
        self.bag["Obat"] -= 1
        self.health = min(100, self.health + 45)
        return "Obat dipakai. Kesehatan +45."

    def trade(self, item, buying, quantity=1):
        prices = BUY if buying else SELL
        if not self.market_open and item != "Pokeball":
            return "Market buka pukul 06:00–22:00. Tekan T untuk maju satu jam."
        if item not in prices or quantity < 1:
            return "Barang tidak tersedia."
        if buying:
            if item == "Pokeball" and self.bag.get(item, 0) + quantity > 10:
                return "Poké Ball: kapasitas tas 10. / Bag limit: 10."
            total = prices[item] * quantity
            if self.money < total:
                return "Uang belum cukup. Jual hasil kebun atau peternakan."
            if item in WEAPONS and self.bag[item]:
                return f"Anda sudah memiliki {item.lower()}."
            self.money -= total
            self.bag[item] += quantity
            return f"Membeli {quantity} {item.lower()}: -{total} koin."
        if self.bag.get(item, 0) < quantity:
            return "Barang di tas tidak cukup."
        self.bag[item] -= quantity
        total = prices[item] * quantity
        self.money += total
        self.record_daily_quest("sell", quantity)
        return f"Menjual {quantity} {item.lower()}: +{total} koin."

    def restaurant_meal(self):
        if self.money < 10:
            return "Uang belum cukup untuk makan."
        self.money -= 10
        self.boost("Kenyang", 58)
        self.boost("Energi", 24)
        self.health = min(100, self.health + 12)
        return "Makan selesai · kenyang +58, energi +24, HP +12."

    def restaurant_drink(self):
        if self.money < 5:
            return "Uang belum cukup untuk minum."
        self.money -= 5
        self.boost("Minum", 62)
        return "Minuman disajikan · minum +62."

    def hotel_stay(self):
        if self.money < 15:
            return "Uang belum cukup untuk menginap."
        self.money -= 15
        self.advance_time(480)
        self.elapsed += 369.23
        for name in self.stats:
            self.stats[name] = 100
        self.health = 100
        self.grow_crops()
        return "Menginap selesai · seluruh kebutuhan dan HP pulih setelah tidur 8 jam."

    def respawn(self):
        self.scene, self.x, self.y = "bedroom", 370, 460
        self.health = 100
        self.mounted = False
        self.deaths += 1
        for name in self.stats:
            self.stats[name] = max(60, self.stats[name])

    def boost(self, name, amount):
        self.stats[name] = min(100, self.stats[name] + amount)

    def complete(self, task):
        if task not in self.accomplishments:
            self.accomplishments.append(task)

    def garden(self, index):
        crop = self.crops[index]
        if crop["stage"] == "empty":
            crop["stage"] = "planted"
            self.record_daily_quest("plant")
            return "Benih ditanam. Tekan E lagi untuk menyiram."
        if crop["stage"] == "planted":
            crop.update(stage="growing", ready=self.elapsed + 45)
            self.complete("Berkebun")
            self.record_daily_quest("water")
            return "Sudah disiram! Sayur siap dipanen dalam 45 detik."
        if crop["stage"] == "growing":
            return f"Tumbuh... sekitar {max(1, int(crop['ready'] - self.elapsed))} detik lagi."
        crop["stage"] = "empty"
        self.bag["Sayur"] += 2
        self.boost("Senang", 8)
        self.record_daily_quest("harvest", 2)
        return "Panen berhasil! +2 sayur masuk ke tas."

    def cook(self):
        for item in ("Daging", "Ikan", "Sayur", "Telur"):
            if self.bag[item] > 0:
                self.bag[item] -= 1
                self.bag["Makanan"] += 1
                self.complete("Memasak")
                self.record_daily_quest("cook")
                return f"Memasak {item.lower()}. +1 makanan. Bawa ke meja makan!"
        return "Bahan habis. Panen sayur, memancing, atau ambil telur dahulu."

    def eat(self):
        if self.bag["Makanan"] <= 0:
            return "Belum ada makanan. Masak di dapur dahulu."
        self.bag["Makanan"] -= 1
        self.boost("Kenyang", 38)
        self.boost("Energi", 8)
        self.complete("Makan")
        self.record_daily_quest("eat")
        return "Makan di meja. Kenyang +38, energi +8."

    def feed(self):
        if self.elapsed - self.fed_at < 40:
            return "Ayam masih kenyang. Kembali sebentar lagi."
        if self.bag["Sayur"] <= 0:
            return "Butuh 1 sayur untuk memberi makan ayam."
        self.bag["Sayur"] -= 1
        self.bag["Telur"] += 2
        self.fed_at = self.elapsed
        self.boost("Senang", 12)
        self.complete("Merawat ayam")
        self.record_daily_quest("feed")
        return "Ayam senang! +2 telur masuk ke tas."

    def save(self, path: Path):
        from datetime import datetime
        self.saved_at = datetime.now().isoformat(timespec="seconds")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            state = cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})
            if state.scene not in ("outdoors", "house", "bedroom", "forest", "market", "reserve", "coast", "mountain"):
                raise ValueError("invalid scene")
            state.character = int(state.character) % 9
            state.x, state.y = float(state.x), float(state.y)
            if set(state.stats) != {"Kenyang", "Minum", "Energi", "Senang"} or len(state.crops) != 6:
                raise ValueError("invalid save")
            for value in state.stats.values():
                float(value)
            for key in ("Sayur", "Ikan", "Telur", "Makanan"):
                state.bag[key] = max(0, int(state.bag[key]))
            state.health = max(0, min(100, float(state.health)))
            state.money = max(0, int(state.money))
            if state.language not in ("id", "en"):
                state.language = "id"
            for key in ITEMS:
                state.bag[key] = max(0, int(state.bag.get(key, 0)))
            if not isinstance(raw.get("bag"), dict) or "Pokeball" not in raw["bag"]:
                state.bag["Pokeball"] = 5
            if state.weapon not in WEAPONS or not state.bag.get(state.weapon, 0):
                state.weapon = ""
            if not isinstance(state.animals, list):
                state.animals = []
            for field_name in ("pokemon_party", "pokemon_caught", "pokemon_seen"):
                values = getattr(state, field_name)
                if not isinstance(values, list):
                    raise ValueError("invalid pokedex")
                limit = 10000
                setattr(state, field_name, list(dict.fromkeys(max(1, int(value)) for value in values))[:limit])
            if int(raw.get("version", 3)) < 4:
                state.pokemon_party = list(dict.fromkeys(state.pokemon_party + state.pokemon_caught))
            state.version = 4
            if not state.pokemon_party:
                state.pokemon_party = [1]
            active = raw.get("pokemon_active", state.pokemon_party[:3])
            if not isinstance(active, list):
                active = state.pokemon_party[:3]
            state.pokemon_active = [ident for ident in dict.fromkeys(max(1, int(value)) for value in active)
                                    if ident in state.pokemon_party][:3]
            if not state.pokemon_active:
                state.pokemon_active = state.pokemon_party[:1]
            if not isinstance(state.pokemon_levels, dict):
                state.pokemon_levels = {}
            if not isinstance(state.pokemon_xp, dict):
                state.pokemon_xp = {}
            if not isinstance(state.pokemon_health, dict):
                state.pokemon_health = {}
            for pokemon_id in set(state.pokemon_caught + state.pokemon_party):
                key = str(int(pokemon_id))
                state.pokemon_levels[key] = max(1, min(100, int(state.pokemon_levels.get(key, 5))))
                state.pokemon_xp[key] = max(0, int(state.pokemon_xp.get(key, 0)))
                state.pokemon_health[key] = max(0, int(state.pokemon_health.get(key, 100)))
            state.bag["Pokeball"] = max(0, state.bag.get("Pokeball", 5))
            return state
        except (OSError, ValueError, TypeError, KeyError):
            return cls()
