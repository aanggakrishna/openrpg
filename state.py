"""Small persistent life simulation, independent of rendering."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import random

ITEMS = ("Sayur", "Ikan", "Telur", "Makanan", "Daging", "Kulit", "Kayu", "Obat", "Tombak", "Busur", "Panah", "Pokeball")
BUY = {"Makanan": 24, "Obat": 35, "Tombak": 80, "Busur": 160, "Panah": 3, "Pokeball": 12}
SELL = {"Sayur": 9, "Ikan": 15, "Telur": 12, "Makanan": 16, "Daging": 20, "Kulit": 25, "Kayu": 6}
WEAPONS = {"Tombak": {"damage": 28, "reach": 88, "cooldown": .55},
           "Busur": {"damage": 24, "reach": 390, "cooldown": .7}}


@dataclass
class Life:
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
    version: int = 3

    def __post_init__(self):
        for item in ITEMS:
            self.bag.setdefault(item, 0)

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
        self.minutes += minutes
        while self.minutes >= 1440:
            self.minutes -= 1440
            self.day += 1
        hour_id = self.day * 24 + self.hour
        if hour_id != self.weather_hour:
            self.weather_hour = hour_id
            block = (hour_id - 8) // 3
            self.weather = random.Random(block + 304).choices(
                ("Cerah", "Hujan", "Salju", "Berawan"), weights=(5, 2, 1, 2))[0]
        if self.weather_override:
            self.weather = self.weather_override

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
        if not self.market_open:
            return "Market buka pukul 06:00–22:00. Tekan T untuk maju satu jam."
        if item not in prices or quantity < 1:
            return "Barang tidak tersedia."
        if buying:
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
        return f"Menjual {quantity} {item.lower()}: +{total} koin."

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
            return "Benih ditanam. Tekan E lagi untuk menyiram."
        if crop["stage"] == "planted":
            crop.update(stage="growing", ready=self.elapsed + 45)
            self.complete("Berkebun")
            return "Sudah disiram! Sayur siap dipanen dalam 45 detik."
        if crop["stage"] == "growing":
            return f"Tumbuh... sekitar {max(1, int(crop['ready'] - self.elapsed))} detik lagi."
        crop["stage"] = "empty"
        self.bag["Sayur"] += 2
        self.boost("Senang", 8)
        return "Panen berhasil! +2 sayur masuk ke tas."

    def cook(self):
        for item in ("Daging", "Ikan", "Sayur", "Telur"):
            if self.bag[item] > 0:
                self.bag[item] -= 1
                self.bag["Makanan"] += 1
                self.complete("Memasak")
                return f"Memasak {item.lower()}. +1 makanan. Bawa ke meja makan!"
        return "Bahan habis. Panen sayur, memancing, atau ambil telur dahulu."

    def eat(self):
        if self.bag["Makanan"] <= 0:
            return "Belum ada makanan. Masak di dapur dahulu."
        self.bag["Makanan"] -= 1
        self.boost("Kenyang", 38)
        self.boost("Energi", 8)
        self.complete("Makan")
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
        return "Ayam senang! +2 telur masuk ke tas."

    def save(self, path: Path):
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
            state.character = int(state.character) % 3
            state.x, state.y = float(state.x), float(state.y)
            if set(state.stats) != {"Kenyang", "Minum", "Energi", "Senang"} or len(state.crops) != 6:
                raise ValueError("invalid save")
            for value in state.stats.values():
                float(value)
            for key in ("Sayur", "Ikan", "Telur", "Makanan"):
                state.bag[key] = max(0, int(state.bag[key]))
            state.health = max(0, min(100, float(state.health)))
            state.money = max(0, int(state.money))
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
                setattr(state, field_name, list(dict.fromkeys(max(1, int(value)) for value in values))[:1025])
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
