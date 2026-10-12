"""OpenRPG — a small, playable Python life RPG with a real shell terminal."""
from __future__ import annotations

import argparse
import copy
from io import BytesIO
import math
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import threading
import time
import wave

import pygame as pg
import retro
from PIL import Image
import pokemon_db

from state import Life, BUY, SELL, WEAPONS
from terminal import ShellTerminal
from art import (RPGArt, RESERVE_WIDTH, RESERVE_HEIGHT, RESERVE_ZONE_W, RESERVE_ZONE_H,
                 RESERVE_ZONES, RESERVE_CENTERS, RESERVE_COLUMNS, RESERVE_ROWS,
                 RESERVE_LEVEL_REQUIREMENTS)
from i18n import translate

# Legendary and mythical species are deliberately weighted toward late-game
# sanctuaries rather than mixed into ordinary roaming encounters.
RARE_POKEMON_IDS = {144,145,146,150,151,243,244,245,249,250,251,377,378,379,380,381,382,383,384,385,386,480,481,482,483,484,485,486,487,488,489,490,491,492,493,494,638,639,640,641,642,643,644,645,646,647,648,649,716,717,718,719,720,721,785,786,787,788,789,790,791,792,800,801,802,805,806,807,808,809,888,889,890,891,892,894,895,896,897,898,905,1001,1002,1003,1004,1007,1008,1009,1010,1011,1012,1013,1014,1015,1016,1017,1024,1025}
from wildlife import Wildlife, SPECIES, hunting_time
from environment import Environment, OUTSIDE
from world_regions import (BIOMES, HABITAT_TYPES, biome_at, reserve_index_at,
                           RESERVE_GRID_POSITIONS, reserve_layout, scene_layout, weather_for, DUNGEON_BIOMES)
from world_features import (COLLECTION_COSMETICS, HOME_DECOR, EVENTS, EVENT_NAMES_ID, NPC_SCHEDULES,
                            PUZZLES, SECRETS, STORIES, WEATHER_TYPES)
from pokedex import PokedexClient

ROOT = Path(__file__).resolve().parent
W, H = 1280, 800
INK, CREAM, MUTED, GREEN = retro.INK, retro.CREAM, retro.MUTED, retro.GREEN
BATTLE_WEATHER_EMOJI = {"Cerah":"☀", "Berawan":"☁", "Hujan":"🌧", "Salju":"❄", "Badai":"⛈"}
TYPE_MOVES = {
    "normal": ("Hantaman Bintang", (231, 224, 193), "burst"), "fire": ("Sembur Api", (245, 102, 48), "fire"),
    "water": ("Arus Hydro", (72, 167, 245), "water"), "electric": ("Petir Kilat", (255, 221, 55), "electric"),
    "grass": ("Tebasan Daun", (97, 205, 93), "leaf"), "ice": ("Badai Salju", (156, 231, 247), "ice"),
    "fighting": ("Pukulan Aura", (226, 115, 64), "strike"), "poison": ("Kabut Racun", (181, 91, 195), "poison"),
    "ground": ("Gempa Bumi", (204, 164, 87), "earth"), "flying": ("Angin Topan", (171, 201, 233), "wind"),
    "psychic": ("Gelombang Psikis", (239, 104, 165), "psychic"), "bug": ("Kawanan Serangga", (162, 190, 67), "bug"),
    "rock": ("Runtuhan Batu", (174, 152, 105), "rock"), "ghost": ("Bola Bayangan", (136, 107, 204), "ghost"),
    "dragon": ("Napas Naga", (119, 109, 229), "dragon"), "dark": ("Gelombang Gelap", (94, 82, 94), "dark"),
    "steel": ("Tebasan Baja", (164, 181, 194), "steel"), "fairy": ("Sinar Peri", (241, 155, 208), "fairy"),
}
CHARACTERS = [("Nara", "Penggemar kebun dan udara pagi", (204, 122, 87)),
              ("Bima", "Petualang yang suka memancing", (89, 139, 160)),
              ("Ayu", "Pencinta rumah, hewan, dan coding", (161, 119, 172))]
TYPE_EMOJI = {"normal": "💥", "fire": "🔥", "water": "💧", "electric": "⚡", "grass": "🍃",
              "ice": "❄️", "fighting": "👊", "poison": "☠️", "ground": "🪨", "flying": "🌪️",
              "psychic": "🔮", "bug": "🐛", "rock": "🪨", "ghost": "👻", "dragon": "🐉",
              "dark": "🌑", "steel": "⚙️", "fairy": "✨"}
ULTIMATE_EMOJI = {"normal": "✨", "fire": "🔥", "water": "🌊", "electric": "⚡", "grass": "🌿",
                  "ice": "❄️", "fighting": "💥", "poison": "☠️", "ground": "🌋", "flying": "🌪️",
                  "psychic": "🔮", "bug": "🐞", "rock": "🪨", "ghost": "👻", "dragon": "🐉",
                  "dark": "🌑", "steel": "⚙️", "fairy": "✨"}
GATE_TRIALS = {
    "meadow": (
        {"name": ("Sulur Penjaga", "Guardian Vines"), "hint": ("Sulur menutup jalan. Gunakan tipe Api, Terbang, atau Serangga untuk membuka jalur.", "Vines block the path. Use Fire, Flying, or Bug to clear it."), "types": ("fire", "flying", "bug"), "action": ("membakar dan menyibak sulur", "burning and parting the vines"), "motion": "vine", "sound": "fire"},
        {"name": ("Jembatan Akar", "Root Bridge"), "hint": ("Akar rapuh melintasi jurang. Tipe Rumput atau Tanah dapat menahannya.", "A fragile root bridge spans the gap. Grass or Ground can stabilize it."), "types": ("grass", "ground", "rock"), "action": ("menguatkan jembatan akar", "reinforcing the root bridge"), "motion": "earth", "sound": "earth"}),
    "forest": (
        {"name": ("Dinding Sulur", "Vine Wall"), "hint": ("Sulur hutan menghalangi pintu. Tipe Api, Terbang, atau Serangga bisa menyingkirkannya.", "Forest vines block the gate. Fire, Flying, or Bug can clear them."), "types": ("fire", "flying", "bug"), "action": ("membuka jalan di antara sulur", "opening a path through the vines"), "motion": "vine", "sound": "fire"},
        {"name": ("Pohon Tumbang", "Fallen Tree"), "hint": ("Batang besar menutup jalan. Tipe Api, Petarung, atau Baja dapat menyingkirkannya.", "A fallen trunk blocks the way. Fire, Fighting, or Steel can clear it."), "types": ("fire", "fighting", "steel"), "action": ("memindahkan batang tumbang", "moving the fallen trunk"), "motion": "log", "sound": "earth"}),
    "ancient_forest": (
        {"name": ("Akar Kuno", "Ancient Roots"), "hint": ("Akar kuno melilit gerbang. Tipe Api, Terbang, atau Serangga dapat membukanya.", "Ancient roots coil around the gate. Fire, Flying, or Bug can clear them."), "types": ("fire", "flying", "bug"), "action": ("menyingkap akar kuno", "parting the ancient roots"), "motion": "vine", "sound": "fire"},
        {"name": ("Gerbang Lumut", "Moss Gate"), "hint": ("Pintu batu tertutup lumut tebal. Tipe Air atau Es dapat membersihkannya.", "A stone door is sealed with thick moss. Water or Ice can wash it clean."), "types": ("water", "ice", "grass"), "action": ("membersihkan gerbang lumut", "cleaning the moss gate"), "motion": "water", "sound": "water"}),
    "coast": (
        {"name": ("Arus Selat", "Channel Crossing"), "hint": ("Arus deras memisahkan jalan. Menyeberanglah bersama Pokémon tipe Air, Terbang, atau Es.", "A strong current splits the path. Cross with a Water, Flying, or Ice Pokémon."), "types": ("water", "flying", "ice"), "action": ("menyeberangi arus di atas punggungnya", "crossing the current on its back"), "motion": "surf", "sound": "water"},
        {"name": ("Pusaran Pasang", "Tidal Whirlpool"), "hint": ("Pusaran menjaga gerbang. Tipe Air, Listrik, atau Rumput dapat menenangkan arus.", "A whirlpool guards the gate. Water, Electric, or Grass can calm the current."), "types": ("water", "electric", "grass"), "action": ("menenangkan pusaran pasang", "calming the tidal whirlpool"), "motion": "surf", "sound": "water"}),
    "deepsea": (
        {"name": ("Palung Arus", "Trench Current"), "hint": ("Arus bawah laut terlalu kuat untuk dilalui sendiri. Gunakan tipe Air, Terbang, atau Es.", "The deep current is too strong to cross alone. Use Water, Flying, or Ice."), "types": ("water", "flying", "ice"), "action": ("menyelam lalu mengantar trainer", "diving and carrying the Trainer across"), "motion": "surf", "sound": "water"},
        {"name": ("Karang Penjaga", "Reef Barrier"), "hint": ("Karang menutup lorong. Tipe Air, Rumput, atau Petarung dapat membuka celah aman.", "A reef blocks the passage. Water, Grass, or Fighting can open a safe gap."), "types": ("water", "grass", "fighting"), "action": ("membuka celah di antara karang", "opening a safe gap through the reef"), "motion": "rock", "sound": "earth"}),
    "desert": (
        {"name": ("Runtuhan Pasir", "Sandfall"), "hint": ("Batu tertimbun pasir menutup gerbang. Tipe Tanah, Air, atau Petarung dapat membersihkannya.", "Sand-buried rocks block the gate. Ground, Water, or Fighting can clear them."), "types": ("ground", "water", "fighting"), "action": ("menggali dan meruntuhkan batu", "digging through the rockfall"), "motion": "rock", "sound": "earth"},
        {"name": ("Badai Pasir", "Sandstorm Gap"), "hint": ("Angin pasir menutup celah. Tipe Terbang, Baja, atau Batu dapat menahan hembusannya.", "A sandstorm seals the pass. Flying, Steel, or Rock can brace against it."), "types": ("flying", "steel", "rock"), "action": ("membelah badai pasir", "parting the sandstorm"), "motion": "wind", "sound": "wind"}),
    "badlands": (
        {"name": ("Longsor Batu", "Rockslide"), "hint": ("Longsor menutup pintu. Tipe Petarung, Tanah, atau Baja dapat menghancurkan batu.", "A rockslide blocks the entrance. Fighting, Ground, or Steel can break through."), "types": ("fighting", "ground", "steel"), "action": ("menghancurkan longsoran batu", "smashing through the rockslide"), "motion": "rock", "sound": "earth"},
        {"name": ("Jurang Retak", "Cracked Ravine"), "hint": ("Jurang memutus jalan. Tipe Terbang, Batu, atau Naga dapat membawa trainer melintasinya.", "A ravine breaks the path. Flying, Rock, or Dragon can carry the Trainer across."), "types": ("flying", "rock", "dragon"), "action": ("melompati jurang bersama trainer", "leaping the ravine with the Trainer"), "motion": "fly", "sound": "wind"}),
    "swamp": (
        {"name": ("Rawa Dalam", "Deep Bog"), "hint": ("Lumpur rawa terlalu dalam. Tipe Air, Tanah, atau Rumput dapat membuat lintasan.", "The bog is too deep. Water, Ground, or Grass can make a safe path."), "types": ("water", "ground", "grass"), "action": ("membuat lintasan di rawa", "making a path through the bog"), "motion": "mud", "sound": "water"},
        {"name": ("Kabut Beracun", "Poison Miasma"), "hint": ("Kabut beracun menyelimuti pintu. Tipe Racun, Baja, atau Psikis dapat menetralkannya.", "Poisonous mist covers the gate. Poison, Steel, or Psychic can neutralize it."), "types": ("poison", "steel", "psychic"), "action": ("menetralisir kabut rawa", "neutralizing the swamp mist"), "motion": "mist", "sound": "wind"}),
    "cave": (
        {"name": ("Batu Runtuh", "Cave-in"), "hint": ("Batu besar menutup lorong. Tipe Petarung, Tanah, Batu, atau Baja dapat menghancurkannya.", "Huge boulders block the tunnel. Fighting, Ground, Rock, or Steel can break them."), "types": ("fighting", "ground", "rock", "steel"), "action": ("menghancurkan batu penghalang", "breaking the blocking boulders"), "motion": "rock", "sound": "earth"},
        {"name": ("Kristal Gema", "Resonant Crystal"), "hint": ("Kristal bergetar menutup pintu. Tipe Listrik, Baja, atau Psikis dapat memecah resonansinya.", "A resonant crystal seals the door. Electric, Steel, or Psychic can disrupt it."), "types": ("electric", "steel", "psychic"), "action": ("memecah resonansi kristal", "breaking the crystal resonance"), "motion": "crystal", "sound": "punch"}),
    "mountain": (
        {"name": ("Tebing Terjal", "Cliff Pass"), "hint": ("Jalan terputus di tebing. Tipe Terbang, Batu, atau Petarung dapat menyeberangkan trainer.", "The cliff trail is broken. Flying, Rock, or Fighting can get the Trainer across."), "types": ("flying", "rock", "fighting"), "action": ("membawa trainer melewati tebing", "carrying the Trainer over the cliff"), "motion": "fly", "sound": "wind"},
        {"name": ("Longsor Puncak", "Summit Rockfall"), "hint": ("Batu menghalangi jalur puncak. Tipe Tanah, Petarung, atau Baja dapat membersihkannya.", "Rocks block the summit route. Ground, Fighting, or Steel can clear them."), "types": ("ground", "fighting", "steel"), "action": ("membuka jalur di longsor", "clearing the summit rockfall"), "motion": "rock", "sound": "earth"}),
    "volcano": (
        {"name": ("Aliran Lava", "Lava Flow"), "hint": ("Lava menutup gerbang. Tipe Air, Tanah, atau Batu dapat membuat jalur aman.", "Lava blocks the gate. Water, Ground, or Rock can make a safe path."), "types": ("water", "ground", "rock"), "action": ("mendinginkan lava dan membuka jalan", "cooling the lava and opening a path"), "motion": "lava", "sound": "water"},
        {"name": ("Semburan Uap", "Steam Vent"), "hint": ("Uap panas menyembur dari celah. Tipe Air, Es, atau Terbang dapat melewatinya.", "Hot steam blasts from the cracks. Water, Ice, or Flying can get through."), "types": ("water", "ice", "flying"), "action": ("menembus semburan uap", "crossing the steam vents"), "motion": "steam", "sound": "water"}),
    "snow": (
        {"name": ("Dinding Es", "Ice Wall"), "hint": ("Dinding es menutup jalur. Tipe Api, Petarung, atau Baja dapat membukanya.", "An ice wall blocks the route. Fire, Fighting, or Steel can break it."), "types": ("fire", "fighting", "steel"), "action": ("mencairkan dinding es", "melting the ice wall"), "motion": "ice", "sound": "fire"},
        {"name": ("Celah Badai Salju", "Blizzard Pass"), "hint": ("Badai salju menutup jembatan. Tipe Api, Batu, atau Terbang dapat menuntun trainer.", "A blizzard hides the bridge. Fire, Rock, or Flying can guide the Trainer."), "types": ("fire", "rock", "flying"), "action": ("menuntun trainer melintasi badai salju", "guiding the Trainer through the blizzard"), "motion": "snow", "sound": "wind"}),
    "sky": (
        {"name": ("Arus Angin", "Wind Current"), "hint": ("Angin kencang memutus jembatan. Tipe Terbang, Listrik, atau Psikis bisa menyeberang.", "Strong winds break the bridge. Flying, Electric, or Psychic can cross."), "types": ("flying", "electric", "psychic"), "action": ("terbang melintasi arus angin", "flying across the wind current"), "motion": "fly", "sound": "wind"},
        {"name": ("Pulau Awan", "Cloud Gap"), "hint": ("Celah awan terlalu lebar untuk dilompati. Tipe Terbang, Naga, atau Es dapat mengantar trainer.", "The cloud gap is too wide to jump. Flying, Dragon, or Ice can carry the Trainer."), "types": ("flying", "dragon", "ice"), "action": ("terbang di atas pulau awan", "flying above the cloud gap"), "motion": "fly", "sound": "wind"}),
    "crystal": (
        {"name": ("Gerbang Kristal", "Crystal Gate"), "hint": ("Dinding kristal menghalangi pintu. Tipe Baja, Petarung, atau Tanah dapat memecahkannya.", "A crystal wall blocks the gate. Steel, Fighting, or Ground can shatter it."), "types": ("steel", "fighting", "ground"), "action": ("memecahkan dinding kristal", "shattering the crystal wall"), "motion": "crystal", "sound": "punch"},
        {"name": ("Prisma Cahaya", "Prism Lock"), "hint": ("Prisma mengunci gerbang dengan cahaya. Tipe Psikis, Peri, atau Listrik dapat menyelaraskannya.", "A prism locks the gate with light. Psychic, Fairy, or Electric can align it."), "types": ("psychic", "fairy", "electric"), "action": ("menyelaraskan prisma gerbang", "aligning the gate prism"), "motion": "crystal", "sound": "wind"}),
    "dragon_valley": (
        {"name": ("Gerbang Naga Beku", "Frozen Dragon Gate"), "hint": ("Es naga menyegel jalur. Tipe Es, Peri, atau Naga dapat membukanya.", "Dragon ice seals the pass. Ice, Fairy, or Dragon can open it."), "types": ("ice", "fairy", "dragon"), "action": ("membuka segel es naga", "breaking the dragon-ice seal"), "motion": "ice", "sound": "fire"},
        {"name": ("Jurang Naga", "Dragon Ravine"), "hint": ("Jurang dalam memutus jalan. Tipe Terbang, Naga, atau Batu dapat mengantar trainer.", "A deep ravine breaks the path. Flying, Dragon, or Rock can carry the Trainer."), "types": ("flying", "dragon", "rock"), "action": ("terbang melintasi jurang naga", "flying across the dragon ravine"), "motion": "fly", "sound": "wind"}),
    "legendary_ruins": (
        {"name": ("Segel Reruntuhan", "Ruin Seal"), "hint": ("Segel kuno menutup pintu. Tipe Psikis, Hantu, Baja, atau Peri dapat membukanya.", "An ancient seal locks the gate. Psychic, Ghost, Steel, or Fairy can open it."), "types": ("psychic", "ghost", "steel", "fairy"), "action": ("membuka segel kuno", "opening the ancient seal"), "motion": "seal", "sound": "wind"},
        {"name": ("Pilar Reruntuhan", "Ruin Pillar"), "hint": ("Pilar batu runtuh menutup jalan. Tipe Petarung, Tanah, atau Baja dapat membersihkannya.", "A fallen stone pillar blocks the way. Fighting, Ground, or Steel can clear it."), "types": ("fighting", "ground", "steel"), "action": ("menggeser pilar reruntuhan", "moving the ruin pillar"), "motion": "rock", "sound": "earth"})}


class LegacyGame:
    def __init__(self, project, save_path=None, shell=None):
        pg.init()
        self.window = pg.display.set_mode((W, H), pg.RESIZABLE)
        try:
            pg.mixer.init()
        except pg.error:
            pass
        pg.display.set_caption("OpenRPG · 8-BIT ADVENTURE")
        self.canvas = pg.Surface((W, H))
        self.battle_flash = pg.Surface((W, H), pg.SRCALPHA)
        self.clock = pg.time.Clock()
        self.font = retro.font(24)
        self.small = retro.font(20)
        self.tiny = retro.font(16)
        self.big = retro.font(48)
        self.logo_font = retro.font(80)
        self.medium = retro.font(32)
        self.emoji_font = retro.IconFont(38)
        self.fruit_font = retro.IconFont(18)
        self.ultimate_font = retro.IconFont(84)
        # Decode the local NPC-versus portrait once at startup.
        self.trainer_versus_sprites = []
        self.trainer_versus_surface_cache = {}
        for versus_portrait in sorted((ROOT / "assets" / "trainers").glob("*.png")):
            try:
                image = pg.image.load(versus_portrait).convert_alpha()
                name = versus_portrait.stem.removeprefix("VS")
                self.trainer_versus_sprites.append({"name": name, "image": image})
            except (OSError, pg.error):
                continue
        self.trainer_versus_sprite = (self.trainer_versus_sprites[0]["image"]
                                      if self.trainer_versus_sprites else None)
        self.mono = pg.font.SysFont("Menlo,DejaVu Sans Mono,monospace", 13)
        self.cell_w = self.mono.size("M")[0]
        self.cell_h = self.mono.get_linesize()
        self.terminal_area = pg.Rect((W - self.cell_w * 132) // 2, 123, self.cell_w * 132, self.cell_h * 36)
        self.save_path = save_path or ROOT / ".openrpg/save.json"
        self.life = Life.load(self.save_path)
        self.terminal = ShellTerminal(project, shell=shell)
        # PC and phone are two interfaces to one live PTY/session.
        self.phone_terminal = self.terminal
        self.pokedex = PokedexClient(ROOT / ".openrpg/pokedex")
        self.art = RPGArt()
        self.wildlife = Wildlife(self.life)
        self.environment = Environment()
        self.attack_cooldown = 0
        self.attack_flash = 0
        self.projectiles = []
        self.shop_npc = "Sari"
        self.shop_greeting = ""
        self.secret_puzzle = ""
        self.secret_feedback = ""
        self.shop_tab = "buy"
        self.sell_pokemon_pending = None
        self.daily_rewarded_today = 0
        self.facing = "down"
        self.mode = "title"
        self.settings_return_mode = "title"
        self.selected = self.life.character
        self.running = True
        self.toast = "Selamat datang! Ikuti jalan menuju rumah."
        self.toast_until = time.monotonic() + 8
        self.fishing = None
        self.buttons = []
        self.last_save = 0
        self.frame = 0
        self.moving = False
        self.phone_input = ""
        self.phone_complete = False
        self.dex_query = ""
        self.dex_page = 0
        self.dex_selected = 1
        self.dex_type_filter = "all"
        self.dex_sprite = None
        self.pokemon_rng = random.Random()
        self.ensure_farm_drops()
        self.pokemon_encounter_clock = 0.0
        self.battle = None
        self.gate_trial = None
        self.encounter_target = None
        self.encounter_choice = 0
        self.interaction_choices = []
        self.pokemon_sounds = {}
        self.battle_sounds = {}
        self.action_sounds = {}
        self.pending_action_sounds = []
        self._tts_queue = []
        self._tts_lock = threading.Lock()
        self._tts_worker_running = False
        self.countdown_tts_dir = ROOT / ".openrpg" / "countdown-tts"
        self.countdown_tts_sounds = {}
        self.countdown_tts_pending = []
        self.countdown_tts_lock = threading.Lock()
        self.countdown_tts_loading = True
        self.countdown_tts_channel = None
        self.hospitality_kind = "restaurant"
        self.last_hit_cry = 0.0
        self._last_pokemon_cry = (None, 0.0)
        self._music_key = None
        self._last_battle_track = None
        self._market_ambience = None
        self._market_ambience_channel = None
        self._forest_ambience = None
        self._forest_ambience_channel = None
        self.footstep_timer = 0.0
        self.door_close_timer = 0.0
        self.dead_active = False
        self.dead_timer = 0.0
        if pg.mixer.get_init():
            pg.mixer.set_num_channels(16)
            self.countdown_tts_channel = pg.mixer.Channel(8)
            for sound_name in ("fire", "water", "earth", "wind", "leaf", "punch", "ultimate_charge", "ultimate_explosion"):
                try:
                    self.battle_sounds[sound_name] = pg.mixer.Sound(str(ROOT / "assets" / "audio" / "sfx" / f"{sound_name}.ogg"))
                except (pg.error, OSError):
                    pass
            try:
                self.battle_sounds["victory"] = self.make_victory_sound()
            except (pg.error, ValueError):
                pass
            try:
                self._market_ambience = pg.mixer.Sound(str(ROOT / "assets" / "audio" / "ambience" / "market_crowd.ogg"))
                self._market_ambience_channel = pg.mixer.Channel(7)
                self._market_ambience_channel.set_volume(.10)
                self._forest_ambience_channel = pg.mixer.Channel(6)
                pg.mixer.music.set_volume(.28)
            except (pg.error, OSError):
                self._market_ambience = None
        self.battle_sprite = None
        self.team_sprite = None
        self.reserve_camera = (0, 0)
        self.world_canvas = pg.Surface((W, 592)).convert()
        self.map_center = [RESERVE_WIDTH / 2, RESERVE_HEIGHT / 2]
        self.map_zoom = 1.0
        self.map_zone_rects = []
        self.poke_surfaces = {}
        self.poke_battle_surfaces = {}
        self.poke_animations = {}
        # Reuse rasterized sprites and emoji across frames instead of copying,
        # resizing, and pixelating the same surfaces at 60 FPS.
        self.pokemon_render_cache = {}
        self.home_board_requested = set()
        self.emoji_render_cache = {}
        self.pokeball_surface = None
        self.pokemon_cache_events = []
        self.dex_detail = None
        self.wild_pokemon = []
        self.map_requested_pokemon = set()
        self.reserve_trainers = []
        self.route_trainers = [
            {"id": "street-adi", "name": "Adi", "scene": "outdoors", "x": 690.0, "y": 390.0, "team": [19], "level": 6, "target": (850, 410), "defeated": False, "paid": False, "cooldown": 0},
            {"id": "street-ina", "name": "Ina", "scene": "forest", "x": 700.0, "y": 430.0, "team": [43], "level": 11, "target": (880, 420), "defeated": False, "paid": False, "cooldown": 0},
            {"id": "street-bayu", "name": "Bayu", "scene": "market", "x": 700.0, "y": 410.0, "team": [58], "level": 16, "target": (920, 410), "defeated": False, "paid": False, "cooldown": 0},
            {"id": "rival-mira", "name": "Mira · Rival", "scene": "outdoors", "x": 930.0, "y": 510.0,
             "team": self.rival_loadout()["team"],
             "level": self.rival_loadout()["level"],
             "target": (820, 520), "defeated": False, "paid": False, "cooldown": 0, "rival": True},
        ]
        portrait_names = [entry["name"] for entry in self.trainer_versus_sprites
                          if entry["name"] != getattr(self.life, "trainer_versus_name", "")]
        if portrait_names:
            for trainer in self.route_trainers:
                if trainer.get("rival"):
                    continue
                portrait_name = self.pokemon_rng.choice(portrait_names)
                trainer["name"] = portrait_name
                trainer["trainer_versus_name"] = portrait_name
        self.center_selected = 0
        self.center_type_filter = "all"
        self.center_message = "Pilih Pokémon untuk diperiksa."
        self.evolution_anim = None
        self.fight_type_vfx = None
        self.phone_unread = False
        self.phone_status = "Tuliskan prompt untuk OpenCode. Enter mengirimkannya."
        self.terminal_cache = pg.Surface(self.terminal_area.size)
        self.terminal_cache.fill((17, 22, 25))
        self.terminal.screen.dirty.update(range(36))
        self.prepare_countdown_audio()
        pg.key.set_repeat()
        pg.scrap.init()

    def text(self, text, x, y, color=INK, font=None, center=False):
        surface = (font or self.font).render(self.tr(text), False, color)
        self.canvas.blit(surface, surface.get_rect(center=(x, y)) if center else (x, y))

    def box(self, rect, color, radius=10, border=None):
        retro.panel(self.canvas, rect, color, border)

    def draw_bag_icon(self, x, y, size=24):
        unit = max(2, size // 6)
        left, top = int(x - 3 * unit), int(y - 2 * unit)
        pg.draw.rect(self.canvas, (213, 169, 97), (left, top + unit, 6 * unit, 5 * unit))
        pg.draw.rect(self.canvas, (242, 213, 151), (left + unit, top, 4 * unit, 2 * unit))
        pg.draw.rect(self.canvas, (116, 76, 52), (left + unit, top + 2 * unit, 4 * unit, unit))
        pg.draw.rect(self.canvas, (88, 63, 45), (left + 2 * unit, top + 4 * unit, 2 * unit, unit))

    def draw_pokedex_icon(self, x, y, size=24):
        unit = max(2, size // 6)
        left, top = int(x - 3 * unit), int(y - 3 * unit)
        pg.draw.rect(self.canvas, (215, 75, 77), (left, top, 6 * unit, 6 * unit))
        pg.draw.rect(self.canvas, (248, 224, 182), (left + unit, top + unit, 4 * unit, 4 * unit))
        pg.draw.rect(self.canvas, (58, 80, 76), (left + 2 * unit, top + 2 * unit, 2 * unit, 2 * unit))
        pg.draw.rect(self.canvas, (255, 255, 239), (left + unit, top + 2 * unit, unit, unit))

    def draw_item_icon(self, item, x, y):
        """Small, consistent pixel-art inventory icons; x/y are icon centers."""
        x, y = int(x), int(y)
        dark, cream, green, red = (54, 48, 39), (239, 218, 165), (123, 183, 89), (211, 79, 76)
        if item == "Sayur":
            pg.draw.polygon(self.canvas, green, [(x, y + 9), (x - 9, y - 1), (x - 5, y - 9), (x + 2, y - 4), (x + 8, y - 8), (x + 8, y + 1)])
            pg.draw.line(self.canvas, dark, (x, y + 9), (x + 1, y - 5), 2)
        elif item == "Ikan":
            pg.draw.ellipse(self.canvas, (91, 171, 192), (x - 9, y - 5, 15, 10))
            pg.draw.polygon(self.canvas, (69, 132, 157), [(x + 5, y), (x + 11, y - 6), (x + 11, y + 6)])
            pg.draw.circle(self.canvas, dark, (x - 5, y - 1), 1)
        elif item in ("Telur", "Makanan"):
            pg.draw.ellipse(self.canvas, cream if item == "Telur" else (203, 157, 90), (x - 6, y - 9, 12, 18))
            if item == "Makanan":
                pg.draw.rect(self.canvas, dark, (x - 5, y + 3, 10, 2))
        elif item == "Daging":
            pg.draw.circle(self.canvas, (176, 92, 76), (x, y), 8)
            pg.draw.circle(self.canvas, cream, (x + 5, y + 5), 3)
            pg.draw.rect(self.canvas, dark, (x - 1, y - 8, 2, 5))
        elif item == "Kulit":
            pg.draw.polygon(self.canvas, (188, 167, 116), [(x, y - 10), (x + 7, y - 2), (x + 4, y + 9), (x - 3, y + 7), (x - 7, y - 2)])
            pg.draw.line(self.canvas, cream, (x, y - 6), (x, y + 6), 2)
        elif item == "Kayu":
            pg.draw.rect(self.canvas, (157, 107, 65), (x - 8, y - 6, 16, 12))
            pg.draw.rect(self.canvas, (221, 174, 104), (x - 5, y - 4, 10, 8), 2)
        elif item == "Obat":
            pg.draw.rect(self.canvas, (104, 178, 183), (x - 7, y - 5, 14, 13))
            pg.draw.rect(self.canvas, cream, (x - 4, y - 9, 8, 4))
            pg.draw.rect(self.canvas, (225, 231, 218), (x - 2, y - 2, 4, 7))
            pg.draw.rect(self.canvas, (225, 231, 218), (x - 4, y, 8, 3))
        elif item == "Tombak":
            pg.draw.line(self.canvas, (148, 103, 61), (x - 7, y + 9), (x + 5, y - 7), 3)
            pg.draw.polygon(self.canvas, (208, 216, 207), [(x + 2, y - 5), (x + 10, y - 10), (x + 7, y - 1)])
        elif item == "Busur":
            pg.draw.arc(self.canvas, (164, 116, 65), (x - 9, y - 10, 17, 20), -1.35, 1.35, 3)
            pg.draw.line(self.canvas, cream, (x + 2, y - 8), (x + 2, y + 8), 1)
        elif item == "Panah":
            pg.draw.line(self.canvas, (163, 112, 67), (x - 9, y + 7), (x + 7, y - 7), 2)
            pg.draw.polygon(self.canvas, (215, 222, 211), [(x + 7, y - 7), (x + 10, y - 10), (x + 9, y - 4)])
        elif item == "Pokeball":
            pg.draw.circle(self.canvas, (218, 76, 79), (x, y), 9)
            pg.draw.rect(self.canvas, (244, 237, 216), (x - 8, y, 16, 7))
            pg.draw.line(self.canvas, dark, (x - 8, y), (x + 8, y), 2)
            pg.draw.circle(self.canvas, cream, (x, y), 3)
            pg.draw.circle(self.canvas, dark, (x, y), 3, 1)

    def button(self, label, rect, callback, active=False):
        label = self.tr(label)
        rect = pg.Rect(rect)
        hover = rect.collidepoint(self.mouse())
        self.box(rect, retro.GOLD if active or hover else retro.PANEL, 9)
        font = self.font if self.font.size(label)[0] <= rect.w - 20 else self.small
        self.text(label, *rect.center, INK if active or hover else CREAM, font, center=True)
        self.buttons.append((rect, callback))

    def mouse(self):
        x, y = pg.mouse.get_pos()
        sw, sh = self.window.get_size()
        scale = min(sw / W, sh / H)
        return ((x - (sw - W * scale) / 2) / scale, (y - (sh - H * scale) / 2) / scale)

    def notify(self, message):
        self.toast, self.toast_until = self.tr(message), time.monotonic() + 5

    def tr(self, value):
        return translate(value, self.life.language)

    def sprite(self, x, y, index=None, scale=1, walking=False):
        self.art.character(self.canvas, x, y, self.life.character if index is None else index,
                           scale, self.frame, walking, self.facing,
                           attacking=self.attack_flash > 0 and index is None)

    def npcs(self):
        # Stall keepers take turns. Their small route offsets make the market
        # feel inhabited while keeping each merchant available predictably.
        result = []
        routes = {"Sari": (415, 350, "Woman"), "Budi": (902, 350, "Hunter"),
                  "Joy": (673, 594, "OldMan")}
        for name, (start, end, service) in NPC_SCHEDULES.items():
            if not start <= self.life.hour < end:
                continue
            # Keep old schedule names harmless during development upgrades.
            # Saves/builds may still refer to Danu after the merchant became Joy.
            name = {"Danu": "Joy"}.get(name, name)
            route = routes.get(name)
            if route is None:
                continue
            x, y, style = route
            x += math.sin(self.life.elapsed / (6 + len(name))) * 13
            result.append((name, x, y, style, service))
        return result

    def current_biome_index(self):
        if self.life.scene == "reserve":
            return reserve_index_at(self.life.x, self.life.y)
        return BIOMES.index(biome_at(self.life.scene, self.life.x, self.life.y))

    def secret_world_position(self, biome=None):
        if self.life.scene != "reserve":
            return None
        index = self.current_biome_index()
        biome = biome or biome_at("reserve", self.life.x, self.life.y)
        x, y, icon = SECRETS[biome]
        zone = RESERVE_ZONES[index]
        return index, zone["x"] + x, zone["y"] + y, icon

    def update_world_events(self):
        if self.mode != "game" or self.life.scene not in OUTSIDE:
            return
        event = self.life.world_event
        if event and self.life.elapsed >= float(event.get("ends", 0)):
            self.life.world_event = {}
            self.life.world_event_next = self.life.elapsed + self.pokemon_rng.uniform(70, 115)
            self.notify(self.words("Event dunia telah berakhir.", "The world event has ended."))
            self.save_current()
            return
        if event or self.life.elapsed < float(self.life.world_event_next):
            return
        biome = biome_at(self.life.scene, self.life.x, self.life.y)
        title, icon = self.pokemon_rng.choice(EVENTS[biome])
        if self.life.language == "id":
            title = EVENT_NAMES_ID.get(title, title)
        if self.life.scene == "reserve":
            zone = self.reserve_zone_at(self.life.x, self.life.y)
            bounds = (zone["x"] + 70, zone["y"] + 170,
                      zone["x"] + RESERVE_ZONE_W - 70, zone["y"] + RESERVE_ZONE_H - 50)
            zone_index = RESERVE_ZONES.index(zone)
        else:
            bounds = (55, 165, 1225, 650)
            zone_index = -1
        x = y = 0
        for _ in range(35):
            x = max(bounds[0], min(bounds[2], self.life.x + self.pokemon_rng.randint(-240, 240)))
            y = max(bounds[1], min(bounds[3], self.life.y + self.pokemon_rng.randint(-190, 190)))
            if not any(rect.colliderect(pg.Rect(x - 16, y - 16, 32, 26)) for rect in self.obstacles()):
                break
        self.life.world_event = {"title": title, "icon": icon, "biome": biome,
                                 "scene": self.life.scene, "zone": zone_index,
                                 "x": int(x), "y": int(y), "ends": self.life.elapsed + 45}
        self.life.world_event_next = self.life.elapsed + 90
        self.notify(self.words(f"EVENT DUNIA: {title}! Cari penandanya sebelum waktunya habis.",
                               f"WORLD EVENT: {title}! Find its marker before time runs out."))
        self.save_current()

    def draw_world_event(self):
        event = self.life.world_event
        if not event or event.get("scene") != self.life.scene:
            return
        if self.life.scene == "reserve":
            zone = self.reserve_zone_at(self.life.x, self.life.y)
            if event.get("zone") != RESERVE_ZONES.index(zone):
                return
            cam_x, cam_y = getattr(self, "reserve_camera", (0, 0))
            x, y = event["x"] - cam_x, event["y"] - cam_y + 135
        else:
            x, y = event["x"], event["y"] + 135
        pulse = 30 + int(4 * math.sin(self.frame / 5))
        pg.draw.circle(self.canvas, retro.GOLD, (int(x), int(y)), pulse, 3)
        pg.draw.circle(self.canvas, (244, 210, 111), (int(x), int(y)), 5)
        glyph = self.emoji_font.render(event["icon"], True, CREAM)
        glyph = pg.transform.scale(glyph, (44, 44))
        self.canvas.blit(glyph, glyph.get_rect(center=(int(x), int(y) - 15)))
        label = event["title"] + " · E"
        size = self.small.size(label)
        self.box((x-size[0]/2-8, y+24, size[0]+16, 26), CREAM, 5)
        self.text(label, x, y+28, center=True, font=self.tiny)

    def draw_player_cosmetic(self, x, y):
        cosmetic = self.life.active_cosmetic
        if not cosmetic:
            return
        if cosmetic == "leaf-crown":
            pg.draw.polygon(self.canvas, (111, 189, 94), [(x-15,y-48),(x-8,y-58),(x-2,y-48),(x+6,y-61),(x+10,y-47),(x+16,y-55),(x+17,y-43),(x-15,y-43)])
            pg.draw.line(self.canvas, (210, 233, 133), (x-13,y-43), (x+15,y-43), 3)
        elif cosmetic == "trail-cloak":
            pg.draw.polygon(self.canvas, (131, 79, 55), [(x-13,y-40),(x+13,y-40),(x+19,y-6),(x,y+1),(x-18,y-7)])
            pg.draw.line(self.canvas, (229, 185, 112), (x,y-33), (x,y-10), 2)
        elif cosmetic in ("star-aura", "legend-aura"):
            color = (118, 218, 203) if cosmetic == "star-aura" else retro.GOLD
            radius = 25 if cosmetic == "star-aura" else 34
            pg.draw.ellipse(self.canvas, color, (x-radius,y-53-radius//2,radius*2,53+radius), 2 if cosmetic == "legend-aura" else 1)
            for index in range(4 if cosmetic == "star-aura" else 7):
                angle = self.frame / 16 + index * math.tau / (4 if cosmetic == "star-aura" else 7)
                px, py = int(x+math.cos(angle)*radius), int(y-24+math.sin(angle)*26)
                pg.draw.rect(self.canvas, color, (px-2,py-2,5,5))

    def label(self, text, x, y):
        text = self.tr(text)
        size = self.small.size(text)
        self.box((x - size[0] / 2 - 12, y - 4, size[0] + 24, 27), CREAM, 6)
        self.text(text, x, y + 10, font=self.small, center=True)

    def stations(self):
        if self.life.scene == "outdoors":
            result = [("home", 350, 350, "Masuk rumah"), ("ranch", 905, 350, "Beri makan ayam"),
                      ("pond", 963, 615, "Memancing"), ("bench", 312, 616, "Duduk & bersantai"),
                      ("reserve", 160, 610, "Portal langsung ke suaka Pokémon"),
                      ("forest", 43, 405, "Ke hutan di kiri"), ("market", 1237, 405, "Ke market di kanan")]
            crop_index = self.nearest_crop_index()
            result.append(("garden", 642, 475, self.crop_interaction_label(crop_index)))
            result.extend((f"drop:{index}", drop["x"], drop["y"], self.farm_drop_label(drop))
                          for index, drop in enumerate(self.life.farm_drops) if not drop.get("taken"))
            if self.life.horse_scene == "outdoors" and not self.life.mounted:
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            if self.life.world_event.get("scene") == "outdoors": result.append(("world_event", self.life.world_event["x"], self.life.world_event["y"], self.life.world_event["title"] + " · E"))
            return result
        if self.life.scene == "forest":
            result = [("farm", 1237, 405, "Kembali ke rumah"), ("wood", 645, 555, "Kumpulkan kayu"),
                      ("reserve", 650, 177, "Jelajahi suaka Pokémon ke utara"),
                      ("restaurant", 300, 475, "Restoran hutan · makan & minum"),
                      ("hotel", 980, 475, "Penginapan hutan · pulihkan kebutuhan")]
            if self.life.horse_scene == "forest" and not self.life.mounted:
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            if self.life.world_event.get("scene") == "forest": result.append(("world_event", self.life.world_event["x"], self.life.world_event["y"], self.life.world_event["title"] + " · E"))
            return result
        if self.life.scene == "reserve":
            result = [("forest", 92, 800, "Kembali ke hutan")]
            zone = self.reserve_zone_at(self.life.x, self.life.y)
            zone_index = RESERVE_ZONES.index(zone)
            layout_buildings = {kind: (zone["x"] + x, zone["y"] + y)
                                for kind, x, y in reserve_layout(zone_index)["buildings"]}
            biome = biome_at("reserve", self.life.x, self.life.y)
            secret = self.secret_world_position(biome)
            if secret and biome not in self.life.discovered_secrets:
                _, sx, sy, _ = secret
                result.append(("secret", sx, sy, "Tempat rahasia · E"))
            if "restaurant" in layout_buildings:
                x, y = layout_buildings["restaurant"]
                result.append(("restaurant", x, y, "Restoran · makan & minum"))
            if "hotel" in layout_buildings:
                x, y = layout_buildings["hotel"]
                result.append(("hotel", x, y, "Hotel · tidur & pulihkan kebutuhan"))
            zone_centers = [(x, y) for x, y in RESERVE_CENTERS
                            if zone["x"] <= x < zone["x"] + RESERVE_ZONE_W
                            and zone["y"] <= y < zone["y"] + RESERVE_ZONE_H]
            if not zone_centers:
                zone_centers = [(zone["x"] + RESERVE_ZONE_W // 2,
                                 zone["y"] + RESERVE_ZONE_H // 2 + 155)]
            result.extend(("center", x, y, "Pokémon Center · periksa, pulihkan, evolusi")
                          for x, y in zone_centers)
            result.extend(("gate:" + gate["direction"], gate["x"], gate["y"],
                           ("Gerbang · " + gate["target"]["name"] if gate["boss_defeated"]
                            else "Kalahkan boss Pokémon dulu"))
                          for gate in self.reserve_gates())
            if not self.life.mounted and self.life.horse_scene == "reserve":
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            event = self.life.world_event
            if event and event.get("scene") == "reserve" and event.get("zone") == RESERVE_ZONES.index(zone):
                result.append(("world_event", event["x"], event["y"], event["title"] + " · E"))
            return result
        if self.life.scene == "coast":
            result = [("reserve", 50, 410, "Kembali ke suaka"), ("restaurant", 280, 500, "Restoran pantai · makan & minum"),
                      ("hotel", 1050, 500, "Hotel pantai · pulihkan kebutuhan")]
            if self.life.world_event.get("scene") == "coast": result.append(("world_event", self.life.world_event["x"], self.life.world_event["y"], self.life.world_event["title"] + " · E"))
            return result
        if self.life.scene == "mountain":
            result = [("reserve", 640, 640, "Kembali ke suaka"), ("restaurant", 290, 560, "Restoran gunung · makan & minum"),
                      ("hotel", 1000, 560, "Hotel gunung · pulihkan kebutuhan")]
            if self.life.world_event.get("scene") == "mountain": result.append(("world_event", self.life.world_event["x"], self.life.world_event["y"], self.life.world_event["title"] + " · E"))
            return result
        if self.life.scene == "market":
            result = [("farm", 43, 405, "Kembali ke rumah")]
            result += [("restaurant", 700, 610, "Restoran · makan & minum"),
                       ("hotel", 960, 610, "Hotel · tidur & pulihkan kebutuhan")]
            result += [("npc_" + name, x, y + 25, f"Bicara dengan {name}") for name, x, y, _, _ in self.npcs()]
            if self.life.world_event.get("scene") == "market": result.append(("world_event", self.life.world_event["x"], self.life.world_event["y"], self.life.world_event["title"] + " · E"))
            if self.life.horse_scene == "market" and not self.life.mounted:
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            return result
        if self.life.scene in ("dungeon_hub", "local_dungeon"):
            event = self.life.world_event
            if event and event.get("scene") == self.life.scene:
                return [("world_event", event["x"], event["y"], event["title"] + " · E")]
            return []
        if self.life.scene == "house":
            return [("outside", 640, 662, "Keluar rumah"), ("kitchen", 356, 306, "Masak makanan"),
                    ("water", 247, 308, "Minum air"), ("table", 596, 453, "Makan di meja"),
                    ("sofa", 888, 475, "Bersantai"), ("home_decor", 680, 282, "Atur dekorasi rumah · E"),
                    ("room", 1015, 235, "Masuk kamar")]
        return [("living", 640, 662, "Ke ruang keluarga"), ("bed", 370, 414, "Tidur & pulihkan energi"),
                ("pc", 899, 369, "Gunakan PC · terminal asli")]

    def reserve_gates(self):
        """Return neighboring biome gates around the player's current region."""
        zone_index = reserve_index_at(self.life.x, self.life.y)
        zone = RESERVE_ZONES[zone_index]
        cleared_bosses = {int(value) for value in self.life.reserve_space_bosses
                          if str(value).lstrip("-").isdigit()}
        col, row = RESERVE_GRID_POSITIONS[zone_index]
        grid_to_index = {position: index for index, position in enumerate(RESERVE_GRID_POSITIONS)}
        gates = []
        for direction, dc, dr in (("utara", 0, -1), ("selatan", 0, 1),
                                  ("barat", -1, 0), ("timur", 1, 0)):
            nc, nr = col + dc, row + dr
            target_index = grid_to_index.get((nc, nr))
            if target_index is None:
                continue
            target = RESERVE_ZONES[target_index]
            if direction == "utara":
                x, y = zone["x"] + RESERVE_ZONE_W // 2, zone["y"] + 220
            elif direction == "selatan":
                x, y = zone["x"] + RESERVE_ZONE_W // 2, zone["y"] + RESERVE_ZONE_H - 100
            elif direction == "barat":
                x, y = zone["x"] + 80, zone["y"] + RESERVE_ZONE_H // 2
            else:
                x, y = zone["x"] + RESERVE_ZONE_W - 80, zone["y"] + RESERVE_ZONE_H // 2
            gates.append({"direction": direction, "x": x, "y": y, "target": target,
                          "col": nc, "row": nr,
                          "required_level": RESERVE_LEVEL_REQUIREMENTS[target_index],
                          "boss_defeated": zone_index in cleared_bosses,
                          # A cleared neighboring sanctuary stays reachable as
                          # a return route, even if the current team's level
                          # later drops after a Team Rocket theft.
                          "return_route_open": target_index in cleared_bosses})
        return gates

    def reserve_boss_threshold(self, zone_index):
        key = str(int(zone_index))
        thresholds = self.life.reserve_space_boss_thresholds
        if key not in thresholds:
            thresholds[key] = self.pokemon_rng.randint(1, 5)
            self.save_current()
        return max(1, min(5, int(thresholds[key])))

    def player_progress_level(self):
        # Space access is permanent progression. Rocket can temporarily steal
        # a Pokémon from the party, but its saved level remains in this map.
        levels = [self.pokemon_level(ident) for ident in self.life.pokemon_party]
        levels.extend(max(1, min(100, int(level)))
                      for level in self.life.pokemon_levels.values()
                      if str(level).lstrip("-").isdigit())
        return max(levels, default=1)

    def missing_sanctuary_guardians(self):
        cleared = set()
        for value in self.life.reserve_space_bosses:
            try:
                index = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(RESERVE_ZONES):
                cleared.add(index)
        # Space Lv.50 is the final sanctuary cell. Its western neighbor is
        # the gate guardian that must be defeated to make that route reachable.
        final_gate_guardian = max(0, len(RESERVE_ZONES) - 2)
        return [] if final_gate_guardian in cleared else [final_gate_guardian]

    def local_dungeon_name(self, tier):
        names = (("Gua Tanah", "Earth Cave"), ("Gua Batu", "Stone Cave"),
                 ("Gua Api", "Fire Cave"), ("Gua Hutan", "Forest Cave"),
                 ("Gua Air", "Water Cave"), ("Gua Salju", "Snow Cave"),
                 ("Gua Kristal", "Crystal Cave"), ("Gua Angin", "Wind Cave"),
                 ("Lembah Naga", "Dragon Valley"),
                 ("Reruntuhan Legendaris", "Legendary Ruins"))
        if 1 <= tier <= len(names):
            return names[tier - 1][self.life.language == "en"]
        return self.words("Dunia Pasca-Kemenangan", "Postgame World")

    @staticmethod
    def local_dungeon_level(tier):
        return min(100, 50 + int(tier) * 5)

    def local_dungeon_status(self):
        if self.missing_sanctuary_guardians():
            return self.words("TERKUNCI · BUKA GATE SPACE LV.50", "LOCKED · OPEN THE LV.50 GATE")
        tier = max(1, int(self.life.local_dungeon_tier))
        if tier > 10:
            return self.words("SEMUA DUNGEON SELESAI · EKSPLORASI BEBAS",
                              "ALL DUNGEONS CLEARED · FREE EXPLORATION")
        name = self.local_dungeon_name(tier).upper()
        return f"{name} · LV.{self.local_dungeon_level(tier)}"

    def local_dungeon_round_label(self, index, total):
        total = max(1, int(total))
        if index >= total - 1:
            return self.words(f"BOSS · {index + 1}/{total}", f"BOSS · {index + 1}/{total}")
        return self.words(f"PENJAGA · {index + 1}/{total}", f"GUARDIAN · {index + 1}/{total}")

    def start_local_dungeon(self):
        if self.missing_sanctuary_guardians():
            guardian = RESERVE_ZONES[self.missing_sanctuary_guardians()[0]]
            guardian_level = min(100, max(10, RESERVE_LEVEL_REQUIREMENTS[self.missing_sanctuary_guardians()[0]] + 5))
            self.notify(self.words(f"Kalahkan penjaga {guardian['name']} Lv.{guardian_level} untuk membuka space Suaka Lv.50.",
                                   f"Defeat the {guardian['name']} Lv.{guardian_level} guardian to open Sanctuary space Lv.50."))
            return
        tier = max(1, min(11, int(self.life.local_dungeon_tier)))
        if tier > 10:
            self.notify(self.words("Kamu telah menaklukkan seluruh dungeon. Dunia tetap terbuka untuk dijelajahi!",
                                   "You conquered every dungeon. The world remains open to explore!"))
            return
        if self.needs_depleted():
            self.notify(self.words("Pulihkan kondisi trainer sebelum memasuki dungeon.",
                                   "Restore the Trainer's condition before entering the dungeon."))
            return
        active = self.active_pokemon_team()
        if not any(self.life.pokemon_health.get(str(ident), 1) > 0 for ident in active):
            self.notify(self.words("Tim aktif perlu dipulihkan di Pokémon Center.",
                                   "Heal your active team at a Pokémon Center first."))
            return
        biome = DUNGEON_BIOMES[tier - 1]
        wanted_types = set(HABITAT_TYPES[biome])
        type_index = pokemon_db.type_catalog()
        pool = [ident for ident, types in type_index.items()
                if set(types) & wanted_types and ident not in RARE_POKEMON_IDS]
        if not pool:
            pool = list(type_index) or [1]
        opponent_count = self.pokemon_rng.randint(1, 3)
        lineup = []
        for _ in range(opponent_count):
            choices = [ident for ident in pool if not lineup or ident != lineup[-1]]
            lineup.append(self.pokemon_rng.choice(choices or pool))
        max_level = self.local_dungeon_level(tier)
        levels = [max_level if index == opponent_count - 1 else
                  max(max_level - 4, max_level - opponent_count + index - 1)
                  for index in range(opponent_count)]
        trainer = {"name": self.words(f"Penjaga {self.local_dungeon_name(tier)}",
                                       f"{self.local_dungeon_name(tier)} Guardian"),
                   "level": 1, "team": [lineup[0]], "paid": False,
                   "local_dungeon": True, "dungeon_tier": tier}
        self.begin_pokemon_battle(lineup[0], trainer=trainer)
        if not self.battle:
            return
        self.battle["opponent_lineup"] = lineup
        self.battle["dungeon_enemy_levels"] = levels
        # Each dungeon foe gets a full minute; the shared battle clock scales
        # with the randomized lineup length (one to three foes).
        self.battle["time_left"] = 60.0 * opponent_count
        self.battle["wild_level"] = levels[0]
        self.battle.pop("wild_hp", None)
        self.battle.pop("wild_max", None)
        self.battle["dungeon_tier"] = tier
        self.battle["dungeon_biome"] = biome
        self.battle["dungeon_round_label"] = self.local_dungeon_round_label(0, opponent_count)
        if opponent_count == 1:
            self.battle["boss_intro"] = {"timer": 2.6, "duration": 2.6}
        trainer["level"] = max_level
        self.prepare_battle()
        self.battle["dungeon_round_label"] = self.local_dungeon_round_label(0, opponent_count)
        if self.battle.get("dungeon_is_boss"):
            self.battle["intro"] = None
        self.battle["phase"] = self.words(
            f"{self.local_dungeon_name(tier)} · Bagian 1: kalahkan penjaga pertama.",
            f"{self.local_dungeon_name(tier)} · Section 1: defeat the first guardian.")
        self.life.complete("Dungeon lokal")
        self.save_current()

    def travel_reserve_gate(self, direction):
        gate = next((item for item in self.reserve_gates() if item["direction"] == direction), None)
        if not gate:
            return
        if not gate["boss_defeated"] and not gate["return_route_open"]:
            zone = RESERVE_ZONES[reserve_index_at(self.life.x, self.life.y)]
            required_boss = min(100, max(10, RESERVE_LEVEL_REQUIREMENTS[RESERVE_ZONES.index(zone)] + 5))
            self.notify(f"Gerbang terkunci. Kalahkan Pokémon penjaga Lv.{required_boss} di {zone['name']} dulu.")
            return
        target = gate["target"]
        target_index = RESERVE_ZONES.index(target)
        # Odd numbered sanctuaries host Team Rocket encounters. Traversal
        # trials belong to the even numbered destinations, after their
        # preceding boss gate has opened.
        if target_index % 2 == 1 and target_index not in self.life.reserve_gate_trials:
            self.open_reserve_gate_trial(target_index, direction)
            return
        self.enter_reserve_gate_target(target, direction)

    def reserve_gate_trial_spec(self, target_index):
        zone = RESERVE_ZONES[int(target_index)]
        options = GATE_TRIALS.get(zone["biome"], GATE_TRIALS["meadow"])
        variant = (int(target_index) + int(target_index) // 3) % len(options)
        return options[variant]

    def open_reserve_gate_trial(self, target_index, direction):
        spec = self.reserve_gate_trial_spec(target_index)
        allowed = set(spec["types"])
        catalog = pokemon_db.type_catalog()
        # The player chooses from the whole healthy collection. A wrong choice
        # is a meaningful experiment, rather than the UI revealing the answer
        # by filtering incompatible Pokémon away.
        candidates = [int(ident) for ident in self.life.pokemon_party
                      if self.life.pokemon_health.get(str(ident), 100) > 0]
        self.gate_trial = {"target_index": int(target_index), "direction": direction,
                           "spec": spec, "allowed": allowed, "candidates": candidates,
                           "selected": 0, "phase": "choose", "timer": 0.0,
                           "feedback": "", "mistakes": 0}
        for ident in candidates:
            self.pokedex.request(ident)
        self.play_action_sound("gate", .32)
        self.mode = "gate_trial"

    def select_gate_trial_pokemon(self, offset):
        trial = self.gate_trial
        if not trial or trial["phase"] != "choose" or not trial["candidates"]:
            return
        trial["selected"] = (trial["selected"] + int(offset)) % len(trial["candidates"])

    def begin_gate_trial_action(self):
        trial = self.gate_trial
        if not trial or trial["phase"] != "choose":
            return
        if not trial["candidates"]:
            spec = trial["spec"]
            needed = ", ".join(kind.title() for kind in spec["types"])
            self.notify(self.words(f"Rintangan ini perlu Pokémon tipe {needed}. Tangkap atau pulihkan salah satunya, lalu coba lagi.",
                                   f"This obstacle needs a {needed} Pokémon. Catch or heal one, then try again."))
            return
        ident = trial["candidates"][trial["selected"]]
        pokemon_types = set(pokemon_db.type_catalog().get(int(ident), ()))
        if not trial["allowed"].intersection(pokemon_types):
            self.life.health = max(0, float(self.life.health) - 10)
            trial["mistakes"] += 1
            trial["feedback"] = self.words(
                "Pokémon tidak cocok dengan rintangan ini. -10 HP, coba lagi.",
                "That Pokémon does not suit this obstacle. -10 HP, try again.")
            self.play_action_sound("wildlife-hurt", .42)
            self.save_current()
            return
        trial.update(phase="action", timer=0.0, pokemon_id=ident)
        self.pokedex.request(ident)
        sound = trial["spec"].get("sound", "gate")
        self.play_action_sound(sound, .55)

    def update_gate_trial(self, dt):
        trial = self.gate_trial
        if not trial or trial["phase"] != "action":
            return
        trial["timer"] += max(0.0, float(dt))
        if trial["timer"] >= 2.8:
            target_index = trial["target_index"]
            target = RESERVE_ZONES[target_index]
            if target_index not in self.life.reserve_gate_trials:
                self.life.reserve_gate_trials.append(target_index)
                self.life.reserve_gate_trials.sort()
            direction = trial["direction"]
            self.gate_trial = None
            self.mode = "game"
            self.enter_reserve_gate_target(target, direction)

    def cancel_gate_trial(self):
        self.gate_trial = None
        self.mode = "game"
        self.play_action_sound("ui-back", .2)

    def enter_reserve_gate_target(self, target, direction):
        if direction == "timur":
            x, y = target["x"] + 115, target["y"] + RESERVE_ZONE_H // 2
        elif direction == "barat":
            x, y = target["x"] + RESERVE_ZONE_W - 115, target["y"] + RESERVE_ZONE_H // 2
        elif direction == "selatan":
            x, y = target["x"] + RESERVE_ZONE_W // 2, target["y"] + 290
        else:
            x, y = target["x"] + RESERVE_ZONE_W // 2, target["y"] + RESERVE_ZONE_H - 180
        self.life.x, self.life.y = x, y
        self.life.advance_time(0)
        self.terrain_location=None
        self.ensure_walkable_position()
        if self.life.mounted:
            self.life.horse_x, self.life.horse_y = x, y
        self.projectiles.clear()
        self.spawn_map_pokemon()
        self.save_current()
        self.notify(f"Memasuki {target['name']} · {target['biome']} · Pokémon lebih langka dan kuat")

    def obstacles(self, scene=None):
        scene = scene or self.life.scene
        trees = self.art.tree_obstacles(scene)
        if scene == "reserve":
            index = reserve_index_at(self.life.x,self.life.y)
            return list(self.art.region_obstacles(index))
        if scene in ("dungeon_hub", "local_dungeon"):
            return trees + [pg.Rect(r) for r in scene_layout(scene)["solids"]]
        if scene in OUTSIDE:
            trees += [pg.Rect(r) for r in scene_layout(scene)["solids"]]
            service_points={"outdoors":((780,590),(880,620)),"forest":((300,475),(980,475)),
                            "market":((700,610),(960,610)),"coast":((280,500),(1050,500)),"mountain":((290,560),(1000,560))}
            trees += [pg.Rect(x-38,y-30,76,40) for x,y in service_points.get(scene,())]
        if scene == "outdoors":
            return trees + [pg.Rect(181, 170, 340, 132), pg.Rect(824, 176, 217, 118), pg.Rect(930, 477, 288, 91), pg.Rect(1026, 568, 192, 100)]
        if scene == "forest":
            return trees
        if scene == "reserve":
            return trees + [pg.Rect(288, 288, 192, 144), pg.Rect(1792, 1120, 192, 144), pg.Rect(78, 566, 158, 105)]
        if scene == "coast":
            return trees
        if scene == "mountain":
            return trees
        if scene == "market":
            return trees + [pg.Rect(320, 220, 194, 112), pg.Rect(809, 220, 194, 112), pg.Rect(576, 493, 194, 83)]
        if scene == "house":
            return [pg.Rect(204, 194, 301, 71), pg.Rect(539, 335, 150, 75), pg.Rect(832, 388, 207, 49)]
        return [pg.Rect(284, 216, 176, 150), pg.Rect(804, 227, 253, 98)]

    def ensure_walkable_position(self):
        if self.life.scene not in OUTSIDE:return
        region=reserve_index_at(self.life.x,self.life.y) if self.life.scene=="reserve" else None
        key=(self.life.scene,region)
        if getattr(self,"terrain_location",None)==key:return
        self.terrain_location=key
        obstacles=self.obstacles()
        def clear(x,y):
            return not any(pg.Rect(x-12,y-12,24,14).colliderect(r) for r in obstacles)
        if clear(self.life.x,self.life.y):return
        ox,oy=(RESERVE_GRID_POSITIONS[region][0]*RESERVE_ZONE_W,
               RESERVE_GRID_POSITIONS[region][1]*RESERVE_ZONE_H) if region is not None else (0,0)
        ymax=1572 if region is not None else 664
        for radius in range(24,1700,24):
            for dx,dy in ((0,1),(1,0),(-1,0),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                x=self.life.x+dx*radius;y=self.life.y+dy*radius
                if ox+40<=x<=ox+1240 and oy+160<=y<=oy+ymax and clear(x,y):
                    self.life.x,self.life.y=x,y
                    return

    def nearest(self):
        found = min(self.stations(), key=lambda s: math.hypot(s[1] - self.life.x, s[2] - self.life.y), default=None)
        if found is None:
            return None
        radius = self.interaction_radius(found[0])
        return found if math.hypot(found[1] - self.life.x, found[2] - self.life.y) < radius else None

    @staticmethod
    def interaction_radius(action):
        if action == "garden":
            return 175
        if action == "world_event":
            return 190
        if action.startswith("drop:"):
            return 140
        return 81

    def nearest_crop_index(self):
        return min(range(len(self.life.crops)), key=lambda i: math.hypot(
            580 + i % 3 * 62 - self.life.x, 440 + i // 3 * 69 - self.life.y))

    def ensure_farm_drops(self):
        if int(getattr(self.life, "farm_drop_day", 0)) == int(self.life.day) and self.life.farm_drops:
            return
        rng = random.Random(int(self.life.day) * 7919 + sum(map(ord, self.life.player_name)))
        locations = [(245, 570), (485, 635), (715, 660), (775, 535), (1080, 490), (520, 535)]
        rng.shuffle(locations)
        kinds = [("🍎", "apple"), ("🍊", "citrus"), ("🍇", "berry"), ("🍄", "mushroom")]
        self.life.farm_drops = [
            {"x": x, "y": y, "emoji": emoji, "kind": kind, "taken": False}
            for (x, y), (emoji, kind) in zip(locations[:3], (rng.choice(kinds) for _ in range(3)))
        ]
        self.life.farm_drop_day = int(self.life.day)

    def farm_drop_label(self, drop):
        names = {"apple": ("Apel · pulihkan HP", "Apple · restore HP"),
                 "citrus": ("Jeruk · pulihkan haus", "Citrus · restore thirst"),
                 "berry": ("Beri · pulihkan energi", "Berry · restore energy"),
                 "mushroom": ("Jamur · pulihkan mood", "Mushroom · restore mood")}
        name = self.words(*names.get(drop.get("kind"), ("Buah", "Fruit")))
        return self.words(f"Item jatuh · {name}", f"Dropped item · {name}")

    def collect_farm_drop(self, index):
        if not 0 <= index < len(self.life.farm_drops):
            return
        drop = self.life.farm_drops[index]
        if drop.get("taken"):
            return
        effects = {"apple": ("HP", 18), "citrus": ("Minum", 18),
                   "berry": ("Energi", 18), "mushroom": ("Senang", 18)}
        stat, amount = effects.get(drop.get("kind"), ("Senang", 12))
        if stat == "HP":
            self.life.health = min(100, self.life.health + amount)
        else:
            self.life.boost(stat, amount)
        drop["taken"] = True
        self.play_action_sound("pickup-item", .3)
        label = self.farm_drop_label(drop).split("·", 1)[-1].strip()
        self.notify(self.words(f"Dipungut: {label} · {stat} +{amount}.",
                               f"Collected: {label} · {stat} +{amount}."))
        self.save_current()

    def crop_interaction_label(self, index):
        crop = self.life.crops[index]
        stage = crop.get("stage", "empty")
        if stage == "empty":
            action = self.words("Tanam benih", "Plant seeds")
        elif stage == "planted":
            action = self.words("Siram bibit", "Water seedlings")
        elif stage == "growing":
            remaining = max(1, int(crop.get("ready", self.life.elapsed) - self.life.elapsed))
            action = self.words(f"Tumbuh · {remaining} dtk lagi", f"Growing · {remaining}s left")
        else:
            action = self.words("Panen sayur", "Harvest crops")
        return self.words(f"Kebun · {action}", f"Garden · {action}")

    def nearby_interactions(self):
        """Collect every nearby target that can respond to the interact key."""
        choices = []
        for station in self.stations():
            distance = math.hypot(station[1] - self.life.x, station[2] - self.life.y)
            radius = self.interaction_radius(station[0])
            if distance < radius:
                action = station[0]
                if action.startswith("gate:") or action in ("farm", "forest", "market", "outside", "home", "room", "living", "reserve", "coast", "mountain", "dungeon_hub", "local_dungeon", "dungeon_start", "online_gym"):
                    category = self.words("Pintu / gerbang", "Door / gate")
                elif action == "world_event":
                    category = self.words("Item / event", "Item / event")
                elif action.startswith("crop") or action in ("garden", "wood", "ranch", "pond"):
                    category = self.words("Item / kegiatan", "Item / activity")
                elif action.startswith("drop:"):
                    category = self.words("Item", "Item")
                elif action.startswith("npc_"):
                    category = self.words("NPC", "NPC")
                else:
                    category = self.words("Tempat / objek", "Place / object")
                choices.append({"kind": "station", "station": station,
                                "label": station[3], "category": category, "distance": distance})

        # World events are drawn independently of the station layer. Register
        # the live event directly as a fallback so every outdoor scene (notably
        # local dungeons) remains collectible even if its station list changes.
        event = self.life.world_event
        if (event and event.get("scene") == self.life.scene and
                not any(choice.get("station", (None,))[0] == "world_event" for choice in choices)):
            distance = math.hypot(event["x"] - self.life.x, event["y"] - self.life.y)
            if distance < self.interaction_radius("world_event"):
                choices.append({"kind": "station",
                                "station": ("world_event", event["x"], event["y"], event["title"] + " · E"),
                                "label": event["title"] + " · E",
                                "category": self.words("Event / drop", "Event / drop"),
                                "distance": distance})

        for pokemon in self.wild_pokemon:
            if pokemon.get("state") == "hide":
                continue
            distance = math.hypot(pokemon["x"] - self.life.x, pokemon["y"] - self.life.y)
            if distance <= 155:
                detail = self.pokemon_data(pokemon["id"]) or {}
                name = detail.get("name", f"Pokémon #{pokemon['id']}").title()
                label = (f"BOSS · {name} · Lv.{pokemon.get('level', 5)}" if pokemon.get("is_boss")
                         else f"{name} · Lv.{pokemon.get('level', 5)}")
                choices.append({"kind": "pokemon", "pokemon": pokemon,
                                "label": label,
                                "category": "Pokémon", "distance": distance})

        trainers = self.reserve_trainers + [t for t in self.route_trainers
                                             if t.get("scene") == self.life.scene]
        for trainer in trainers:
            if trainer.get("cooldown", 0) > 0 or not trainer.get("team"):
                continue
            if (trainer.get("rocket_event") and trainer.get("rocket_behavior") == "ambush"
                    and not trainer.get("rocket_revealed")):
                continue
            distance = math.hypot(trainer["x"] - self.life.x, trainer["y"] - self.life.y)
            if distance <= 112:
                choices.append({"kind": "trainer", "trainer": trainer,
                                "label": self.words(f"Tantang {trainer['name']}", f"Challenge {trainer['name']}"),
                                "category": self.words("Pelatih", "Trainer"), "distance": distance})
        choices.sort(key=lambda choice: (choice.get("station", (None,))[0] != "world_event",
                                         choice["distance"], choice["kind"], choice["label"]))
        return choices[:8]

    def choose_interaction(self, choice):
        self.interaction_choices = []
        self.mode = "game"
        if choice["kind"] == "pokemon":
            self.open_pokemon_encounter(choice["pokemon"])
        elif choice["kind"] == "trainer":
            self.invite_trainer(choice["trainer"])
        else:
            self.interact_selected(choice)

    def invite_trainer(self, trainer):
        """Show the VS cut-in and invitation before any trainer duel starts."""
        if trainer.get("rival"):
            trainer["story_line"] = self.rival_loadout()["line"]
        self.invitation={"trainer":trainer,"cutin_started":time.monotonic()}
        if trainer.get("rocket_event"):
            self.invitation["rocket_video"] = True
            self.start_rocket_video()
        self.set_mode("invitation")

    def draw_interaction_picker(self):
        self.text(self.words("PILIH INTERAKSI", "CHOOSE INTERACTION"), 245, 194, retro.GOLD, self.medium)
        self.text(self.words("Ada beberapa objek di dekatmu. Pilih yang ingin digunakan.",
                             "Several objects are nearby. Choose what to interact with."),
                  245, 229, MUTED, self.small)
        for index, choice in enumerate(self.interaction_choices):
            y = 270 + index * 43
            label = f"{choice['category']}   ·   {choice['label']}"
            self.button(label, (245, y, 788, 37),
                        lambda target=choice: self.choose_interaction(target), index == 0)
        self.button(self.words("Batal · Esc", "Cancel · Esc"), (245, 635, 788, 38), self.back)

    def transition(self, scene, x, y):
        old_scene = self.life.scene
        if old_scene != scene:
            if scene in ("house", "bedroom") or old_scene in ("house", "bedroom"):
                self.play_action_sound("door-wood-open", .35)
                self.door_close_timer = .28
            else:
                self.play_action_sound("gate", .32)
        if self.life.mounted and scene not in OUTSIDE:
            self.toggle_mount()
        self.life.scene, self.life.x, self.life.y = scene, x, y
        self.life.discover_biome()
        self.life.advance_time(0)
        self.terrain_location=None
        self.ensure_walkable_position()
        if self.life.mounted:
            self.life.horse_scene, self.life.horse_x, self.life.horse_y = scene, x, y
        self.fishing = None
        self.projectiles.clear()
        self.save_current()

    def interact(self):
        self.interact_selected()

    def interact_selected(self, chosen=None):
        if self.fishing:
            age = time.monotonic() - self.fishing
            if 2.5 <= age <= 4.2:
                self.life.bag["Ikan"] += 1
                self.life.boost("Senang", 14)
                self.life.complete("Memancing")
                self.life.record_daily_quest("fish", 1)
                self.play_action_sound("fishing-bite", .45)
                self.queue_action_sound("fishing-reel", .18, .45)
                self.notify("Dapat ikan! +1 ikan. Bisa dimasak di dapur.")
                self.tutorial_advance("fish")
            else:
                self.play_action_sound("ui-error", .35)
                self.notify("Terlalu cepat! Tunggu tulisan TARIK muncul.")
            self.fishing = None
            return
        if chosen is None:
            choices = self.nearby_interactions()
            if len(choices) > 1:
                self.interaction_choices = choices
                self.mode = "interaction_picker"
                self.play_action_sound("menu-open", .24)
                return
            if choices:
                chosen = choices[0]
            else:
                station = None
        if chosen and chosen["kind"] == "pokemon":
            self.open_pokemon_encounter(chosen["pokemon"])
            return
        if chosen and chosen["kind"] == "trainer":
            self.invite_trainer(chosen["trainer"])
            return
        station = chosen["station"] if chosen else self.nearest()
        if not station:
            self.play_action_sound("ui-error", .32)
            self.notify(self.words("Dekati objek yang ingin dipakai lalu tekan E.",
                                   "Move near an object and press E to interact."))
            return
        action = station[0]
        if action.startswith("drop:"):
            self.collect_farm_drop(int(action.split(":", 1)[1]))
            return
        if action == "garden":
            action = f"crop{self.nearest_crop_index()}"
        if action == "secret":
            biome = biome_at(self.life.scene, self.life.x, self.life.y)
            self.secret_puzzle = biome
            self.secret_feedback = ""
            self.mode = "secret_puzzle"
            return
        if action == "online_gym":
            self.set_mode("online_connect")
            return
        if action == "dungeon_hub":
            self.transition("dungeon_hub", 640, 555)
            return
        if action == "local_dungeon":
            missing = self.missing_sanctuary_guardians()
            if missing:
                guardian = RESERVE_ZONES[missing[0]]
                guardian_level = min(100, max(10, RESERVE_LEVEL_REQUIREMENTS[missing[0]] + 5))
                self.notify(self.words(
                    f"Dungeon terkunci · kalahkan penjaga {guardian['name']} Lv.{guardian_level} untuk membuka space Suaka Lv.50.",
                    f"Dungeon locked · defeat the {guardian['name']} Lv.{guardian_level} guardian to open Sanctuary space Lv.50."))
                return
            self.transition("local_dungeon", 640, 565)
            return
        if action == "dungeon_start":
            self.start_local_dungeon()
            return
        if action == "world_event":
            event = self.life.world_event
            if not event:
                return
            bonus = 30 + max(0, BIOMES.index(event["biome"])) * 3
            self.life.money += bonus
            self.life.gacha_tickets += int(self.pokemon_rng.random() < .35)
            self.life.bag["Makanan"] = min(99, self.life.bag.get("Makanan", 0) + 1)
            self.life.world_event = {}
            self.life.world_event_next = self.life.elapsed + self.pokemon_rng.uniform(75, 120)
            self.life.record_daily_quest("event", 1)
            self.play_action_sound("pickup-rare", .35)
            self.notify(self.words(f"Event selesai! +{bonus} koin · makanan +1.",
                                   f"Event complete! +{bonus} coins · food +1."))
            self.save_current()
            return
        if action == "home_decor":
            if self.life.scene == "house":
                self.open_overlay("home_decor")
            return
        if action in ("restaurant", "hotel"):
            self.play_action_sound("menu-open", .32)
            self.hospitality_kind = action
            self.mode = "hospitality"
            return
        if action.startswith("gate:"):
            self.travel_reserve_gate(action.split(":", 1)[1])
            return
        if action in ("reserve", "coast", "mountain"):
            if action == "reserve" and self.life.tutorial_active:
                objective = self.tutorial_objective()
                if objective and objective[0] != "enter_reserve":
                    self.notify(self.words(f"Selesaikan tutorial dulu: {objective[1]}.",
                                           f"Finish the tutorial first: {objective[2]}."))
                    return
                self.tutorial_advance("enter_reserve")
            x, y = {"reserve": (100, 800), "coast": (70, 410), "mountain": (640, 620)}[action]
            self.transition(action, x, y)
            if action == "reserve":
                self.life.complete("Menjelajah suaka")
                self.spawn_map_pokemon()
            self.notify({"reserve": "Suaka terbuka: jelajahi area luas untuk bertemu Pokémon.",
                         "coast": "Pantai pasang surut. Pokémon bisa ditemui di sini juga.",
                         "mountain": "Pegunungan kabut. Perhatikan jalan berbatu."}[action])
            return
        if action == "forest":
            self.transition("forest", 650, 237)
            return
        if action == "coast" or action == "mountain" or (action == "reserve" and self.life.scene != "forest"):
            x, y = {"coast": (60, 410), "mountain": (640, 650), "reserve": (100, 800)}[action]
            self.transition(action, x, y)
            if action == "reserve":
                self.spawn_map_pokemon()
            return
        if action in ("forest", "market"):
            self.transition(action, 1190 if action == "forest" else 90, 410)
            self.notify("Hutan: singa berburu 06–10 dan 16–20. Bawa senjata!" if action == "forest" else "Market: buka 06:00–22:00. Dekati NPC, lalu E.")
            return
        if action == "farm":
            self.transition("outdoors", 85 if self.life.scene == "forest" else 1185, 410)
            return
        if action == "horse":
            self.toggle_mount()
            return
        if action == "center":
            self.play_action_sound("menu-open", .32)
            self.mode = "center"
            self.center_selected = 0
            self.center_message = "Selamat datang! Kami bisa memeriksa dan memulihkan timmu."
            for pokemon_id in self.life.pokemon_party[:8]:
                self.pokedex.request(pokemon_id)
                self.pokedex.request_species(pokemon_id)
            return
        if action == "wood":
            if self.attack_cooldown <= 0:
                self.life.record_daily_quest("wood")
                self.life.bag["Kayu"] += 1
                self.attack_cooldown = 1.5
                self.play_action_sound("axe-chop", .45)
                self.play_action_sound("pickup-item", .25)
                self.notify("Mengumpulkan ranting: +1 kayu. Bisa dijual di market.")
            return
        if action.startswith("npc_"):
            if not self.life.market_open:
                self.notify("NPC sedang istirahat. Market buka 06:00–22:00. T: maju 1 jam.")
                return
            self.shop_npc = action[4:]
            self.life.record_daily_quest("talk", 1, unique=self.shop_npc)
            lines = {
                "Sari": ("Hujan membuat petualang cepat lapar. Bawa bekal sebelum masuk gua.", "Rain makes travelers hungry. Pack food before entering a cave."),
                "Budi": ("Bawa senjata yang cocok dengan habitat. Jangan ganggu Pokémon yang sedang bersembunyi.", "Bring a weapon suited to the habitat. Leave hiding Pokémon alone."),
                "Joy": ("Barang hasil panen dan temuan langka selalu punya pembeli.", "Harvests and rare finds always have a buyer."),
            }
            self.shop_greeting = self.words(*lines.get(self.shop_npc, ("Selamat datang!", "Welcome!")))
            self.shop_tab = "sell" if self.shop_npc == "Joy" else "buy"
            self.sell_pokemon_pending = None
            self.play_action_sound("shop-bell", .32)
            self.mode = "shop"
            return
        if action == "home":
            self.transition("house", 640, 608)
            self.tutorial_advance("enter_home")
        elif action == "outside":
            self.transition("outdoors", 350, 389)
        elif action == "room":
            self.transition("bedroom", 640, 608)

        elif action == "living":
            self.transition("house", 1015, 290)
        elif action.startswith("crop"):
            crop = self.life.crops[int(action[-1])]
            stage = crop["stage"]
            result = self.life.garden(int(action[-1]))
            if stage == "empty":
                self.play_action_sound("seed-plant", .45)
            elif stage == "planted":
                self.play_action_sound("watering", .35)
            elif stage == "ripe":
                self.play_action_sound("harvest-pop", .5)
                self.play_action_sound("pickup-item", .25)
            else:
                self.play_action_sound("ui-error", .25)
            self.notify(result)
            if stage == "empty" and crop["stage"] == "planted": self.tutorial_advance("plant")
            elif stage == "planted" and crop["stage"] == "growing": self.tutorial_advance("water")
            elif stage == "ripe" and crop["stage"] == "empty": self.tutorial_advance("harvest")
        elif action == "ranch":
            fed_at = self.life.fed_at
            result = self.life.feed()
            if self.life.fed_at != fed_at:
                self.play_action_sound("chicken", .28)
                self.queue_action_sound("egg-collect", .24, .4)
            else:
                self.play_action_sound("ui-error", .25)
            self.notify(result)
            if self.life.fed_at != fed_at: self.tutorial_advance("egg")
        elif action == "pond":
            self.fishing = time.monotonic()
            self.play_action_sound("fishing-cast", .42)
            self.notify("Umpan dilempar. Tunggu ikan menggigit...")
        elif action == "kitchen":
            food_before = self.life.bag["Makanan"]
            self.notify(self.life.cook())
            if self.life.bag["Makanan"] > food_before:
                self.play_action_sound("door-wood-open", .24)
                self.queue_action_sound("stove-on", .28, .25)
                self.queue_action_sound("cook-sizzle", .48, .48)
                self.queue_action_sound("door-wood-close", .8, .22)
            else:
                self.play_action_sound("ui-error", .25)
        elif action == "table":
            food_before = self.life.bag["Makanan"]
            self.notify(self.life.eat())
            if self.life.bag["Makanan"] < food_before:
                self.play_action_sound("eat", .42)
                self.tutorial_advance("eat")
            else:
                self.play_action_sound("ui-error", .25)
        elif action == "water":
            self.life.boost("Minum", 45)
            self.play_action_sound("drink", .38)
            self.notify("Segelas air segar. Minum +45.")
            self.tutorial_advance("drink")
        elif action in ("bench", "sofa"):
            self.life.boost("Senang", 20)
            self.life.boost("Energi", 10)
            self.life.complete("Bersantai")
            self.notify("Tarik napas, nikmati hari. Senang +20, energi +10.")
        elif action == "bed":
            self.life.day += 1
            self.life.ensure_daily_quests()
            self.life.minutes = 420
            self.life.elapsed += 60
            self.life.boost("Energi", 100)
            self.life.health = 100
            for ident in self.life.pokemon_active:
                self.life.pokemon_health[str(ident)] = self.base_stat(self.pokemon_data(ident), "hp", 45) + self.pokemon_level(ident) * 2
            self.life.boost("Senang", 12)
            self.life.advance_time(0)
            self.life.grow_crops()
            self.play_action_sound("sleep", .34)
            self.notify("Selamat pagi! Energi pulih. Kebun juga terus tumbuh.")
            self.tutorial_advance("sleep")
        elif action == "pc":
            self.terminal.start()
            self.mode = "terminal"
            self.life.complete("Menggunakan PC")
            pg.key.start_text_input()
            pg.key.set_repeat(350, 35)

    def resolve_secret_puzzle(self, choice):
        biome = self.secret_puzzle
        puzzle = PUZZLES.get(biome)
        if not puzzle:
            self.mode = "game"
            return
        if int(choice) != puzzle[2]:
            self.secret_feedback = self.words("Belum tepat. Coba baca petunjuknya lagi.", "Not quite. Read the clue and try again.")
            self.play_action_sound("ui-error", .25)
            return
        self.life.discovered_secrets = list(dict.fromkeys(self.life.discovered_secrets + [biome]))
        reward = 35 + self.current_biome_index() * 4
        self.life.money += reward
        self.life.gacha_tickets += 1
        self.life.record_daily_quest("secret", 1, unique=biome)
        self.mode = "game"
        self.secret_puzzle = ""
        self.secret_feedback = ""
        self.play_action_sound("pickup-rare", .38)
        self.notify(self.words(f"Teka-teki terpecahkan! +{reward} koin dan 1 tiket gacha.",
                               f"Puzzle solved! +{reward} coins and 1 gacha ticket."))
        self.save_current()

    def toggle_mount(self):
        if self.life.mounted:
            self.play_action_sound("step-wood", .28)
            self.life.mounted = False
            self.life.horse_scene = self.life.scene
            self.life.horse_x, self.life.horse_y = self.life.x, self.life.y
            self.notify("Turun dari kuda. Kuda menunggu di sini.")
        elif self.life.scene == self.life.horse_scene and math.hypot(self.life.x - self.life.horse_x, self.life.y - self.life.horse_y) < 85:
            self.play_action_sound("step-grass", .3)
            self.life.mounted = True
            self.notify("Naik kuda! Bergerak lebih cepat. R untuk turun.")
        else:
            self.notify("Dekati kuda dahulu. Ia berada di " + {"outdoors": "peternakan", "forest": "hutan", "market": "market"}.get(self.life.horse_scene, "peternakan") + ".")

    def attack(self):
        weapon = self.life.weapon
        if not weapon or self.life.bag.get(weapon, 0) <= 0:
            self.notify("Berburu harus membawa senjata. Beli dari Budi di market, pasang di tas (I).")
            return
        if self.life.scene != "forest":
            self.notify("Berburu dilakukan di hutan. Jalan ke kiri dari rumah.")
            return
        if self.attack_cooldown > 0:
            return
        spec = WEAPONS[weapon]
        self.play_action_sound("attack-swing", .32)
        direction = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[self.facing]
        if weapon == "Busur":
            if self.life.bag["Panah"] <= 0:
                self.notify("Panah habis. Beli dari Budi di market.")
                return
            self.life.bag["Panah"] -= 1
            self.projectiles.append({"x": self.life.x, "y": self.life.y - 18, "dx": direction[0], "dy": direction[1], "travel": 0})
        else:
            candidates = []
            for animal in self.wildlife.living:
                dx, dy = animal["x"] - self.life.x, animal["y"] - self.life.y
                distance = math.hypot(dx, dy)
                if distance < spec["reach"] and (distance < 35 or (dx * direction[0] + dy * direction[1]) / max(1, distance) > .2):
                    candidates.append((distance, animal))
            if candidates:
                animal = min(candidates, key=lambda c: c[0])[1]
                old_hp = animal["hp"]
                self.notify(self.wildlife.hit(animal, spec["damage"]))
                if animal["hp"] < old_hp:
                    self.play_action_sound("wildlife-hurt", .44)
                    self.play_wildlife_call(animal["species"])
                    if animal["hp"] <= 0: self.tutorial_advance("hunt")
        self.attack_cooldown = spec["cooldown"]
        self.attack_flash = .22

    def respawn(self):
        # Only player state changes. The terminal object and its process are untouched.
        self.life.respawn()
        self.fishing = None
        self.projectiles.clear()
        self.battle = None
        self.back()
        self.save_current()
        self.notify("Anda tumbang dan bangun di tempat tidur. Terminal / AI tetap berjalan.")
        self.dead_active = False
        self.dead_timer = 0.0

    def start_dead_screen(self):
        self.dead_active = True
        self.dead_timer = 5.0
        self.play_action_sound("jingle-fail", .32)
        self.mode = "dead"
        self.battle = None
        self.fishing = None
        self.projectiles.clear()
        if self.countdown_tts_channel:
            self.countdown_tts_channel.stop()

    def draw_dead_screen(self):
        veil = pg.Surface((W, H), pg.SRCALPHA)
        veil.fill((12, 10, 18, 225))
        self.canvas.blit(veil, (0, 0))
        self.box((280, 185, 720, 430), (23, 26, 43), 12, retro.RED)
        self.text("DEAD", W // 2, 270, retro.RED, self.logo_font, True)
        self.text("Anda akan terbangun di kasur dalam", W // 2, 365, CREAM, self.medium, True)
        self.text(f"{max(1, math.ceil(self.dead_timer))}", W // 2, 445, retro.GOLD, self.big, True)
        self.text("Terminal dan pekerjaan OpenCode tetap berjalan.", W // 2, 525, GREEN, self.small, True)

    def skip_hour(self):
        self.play_action_sound("ui-click", .18)
        self.life.skip_hour()
        self.fishing = None
        self.wildlife.update(.1, self.obstacles("forest"), player_active=False)
        self.notify(f"Waktu +1 jam: {self.life.hour:02}:{int(self.life.minutes % 60):02} · {self.life.period} · {self.life.weather}.")

    def set_weather(self, weather):
        self.life.weather_override = "" if weather == "Otomatis" else weather
        self.life.weather_hour = -1
        self.life.advance_time(0)
        self.back()
        self.notify("Cuaca: " + self.life.weather + (" (otomatis)" if weather == "Otomatis" else "."))

    def trade(self, item, buying, quantity=1):
        quantity_before = self.life.bag.get(item, 0)
        self.notify(self.life.trade(item, buying, quantity))
        changed = self.life.bag.get(item, 0) != quantity_before
        if changed:
            self.play_action_sound("buy" if buying else "sell-coins", .34)
            objective = self.tutorial_objective() if self.life.tutorial_active else None
            if buying and item in WEAPONS and objective and objective[0] == "buy_weapon":
                self.life.equip(item)
                if item == "Busur": self.life.bag["Panah"] = max(3, self.life.bag.get("Panah", 0))
                self.notify(self.words(f"{item} dibeli dan langsung dipasang. Sekarang berburu di hutan.",
                                       f"{item} bought and equipped. Now hunt in the forest."))
                self.tutorial_advance("buy_weapon")
            elif not buying and item in ("Sayur", "Telur"):
                self.tutorial_advance("sell_farm")
            elif not buying and item in ("Daging", "Kulit"):
                self.tutorial_advance("sell_hunt")
        else:
            self.play_action_sound("not-enough-money", .25)
        self.save_current()

    def use_healing_item(self):
        health_before = self.life.health
        message = self.life.heal()
        self.notify(message)
        success = self.life.health > health_before
        self.play_action_sound("pickup-item" if success else "ui-error", .32 if success else .22)

    def eat_from_bag(self):
        food_before = self.life.bag["Makanan"]
        message = self.life.eat()
        self.notify(message)
        success = self.life.bag["Makanan"] < food_before
        self.play_action_sound("eat" if success else "ui-error", .35 if success else .22)

    def pokemon_sale_value(self, pokemon_id):
        detail = self.pokemon_data(pokemon_id) or {}
        level = self.pokemon_level(pokemon_id)
        base_xp = int(detail.get("base_experience", 60))
        return max(20, min(450, base_xp // 3 + level * 4))

    def sell_party_pokemon(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        if self.shop_npc != "Joy" or not self.life.market_open:
            self.notify("Pokémon hanya bisa dijual kepada Joy saat market buka.")
            self.sell_pokemon_pending = None
            return
        if pokemon_id not in self.life.pokemon_party:
            self.notify("Pokémon itu tidak lagi ada di party.")
            self.sell_pokemon_pending = None
            return
        if len(self.life.pokemon_party) <= 1:
            self.notify("Simpan setidaknya satu Pokémon di party.")
            self.sell_pokemon_pending = None
            return
        if pokemon_id in self.life.pokemon_active:
            self.notify("Keluarkan Pokémon dari tim aktif di Pokémon Center sebelum menjualnya.")
            self.sell_pokemon_pending = None
            return
        if self.sell_pokemon_pending != pokemon_id:
            self.sell_pokemon_pending = pokemon_id
            self.notify("Tekan KONFIRMASI di kartu Pokémon untuk menyelesaikan penjualan.")
            return
        value = self.pokemon_sale_value(pokemon_id)
        detail = self.pokemon_data(pokemon_id) or {}
        name = detail.get("name", f"Pokémon #{pokemon_id}").title()
        self.life.pokemon_party.remove(pokemon_id)
        self.life.pokemon_active = [ident for ident in self.life.pokemon_active if ident != pokemon_id]
        self.life.money += value
        self.life.record_daily_quest("sell", 1)
        self.save_current()
        self.sell_pokemon_pending = None
        self.center_selected = min(self.center_selected, len(self.life.pokemon_party) - 1)
        self.notify(f"{name} dijual kepada Joy seharga {value} koin.")
        self.play_action_sound("sell-coins", .4)

    def check_daily_quest_rewards(self):
        for quest in self.life.daily_quests:
            if quest.get("claimed") and not quest.get("notified"):
                quest["notified"] = True
                self.daily_rewarded_today += quest["reward"]
                self.notify(f"MISI SELESAI: {quest['title']} · +{quest['reward']} koin!")
                self.save_current()

    def spawn_map_pokemon(self):
        if not self.pokedex.catalog:
            self.pokedex.request_catalog()
            self.notify("Memuat daftar Pokémon dari PokéAPI. Coba lagi sebentar.")
            return
        entries = self.pokedex.catalog
        current_zone = self.reserve_zone_at(self.life.x, self.life.y)
        self.loaded_reserve_zone = RESERVE_ZONES.index(current_zone)
        self.wild_pokemon = []
        self.map_requested_pokemon.clear()
        by_id = {entry["id"]: entry for entry in entries}
        # Each region gets species that fit its terrain. Levels rise as the
        # player travels farther from the original sanctuary entrance.
        biome_ids = [
            [1, 4, 7, 16, 25, 39, 52, 133, 152, 187],
            [10, 13, 43, 46, 69, 123, 152, 187, 265, 285, 511, 540, 810, 906],
            [27, 28, 50, 51, 74, 95, 111, 231, 328, 331, 551],
            [7, 54, 60, 72, 79, 90, 98, 120, 129, 130, 183, 194, 223, 270, 278, 320, 349, 370, 456, 501, 592, 656],
            [43, 60, 69, 72, 183, 194, 316, 453, 590, 710, 751],
            [41, 74, 95, 104, 208, 246, 293, 302, 337, 338, 374, 599],
            [27, 50, 51, 74, 95, 111, 328, 331, 449, 450, 551, 550],
            [37, 58, 66, 74, 77, 95, 125, 142, 246, 443, 371, 610],
            [4, 5, 6, 37, 58, 77, 126, 136, 218, 323, 485, 631],
            [86, 87, 124, 220, 221, 225, 361, 459, 582, 613, 712],
            [16, 21, 83, 142, 149, 198, 333, 357, 381, 384, 385],
            [63, 92, 201, 302, 337, 338, 374, 436, 524, 599, 703, 800],
            [1, 3, 46, 102, 154, 182, 251, 465, 492, 640, 721, 801],
            [7, 9, 72, 73, 131, 199, 260, 382, 484, 593, 594, 730],
            [147, 148, 149, 230, 330, 334, 373, 380, 384, 445, 483, 780, 887],
            [150, 151, 249, 250, 251, 382, 383, 384, 385, 386, 493, 800, 807, 888, 1007, 1024],
        ]
        # Every PokéAPI species belongs to one rotating habitat pool. The
        # familiar, biome-specific species remain common; the wider pool lets
        # the complete catalogue appear over future encounters and restocks.
        roaming_pools = [[] for _ in RESERVE_ZONES]
        types_by_id=pokemon_db.type_catalog()
        for entry in entries:
            ident=int(entry.get("id",0));types=types_by_id.get(ident,())
            # Include every actual region, not just the original 16 biome
            # constants. Country-themed spaces reuse those biome palettes, so
            # assigning by the old BIOMES index left their pools empty and
            # forced the Bulbasaur fallback in every country zone.
            candidates=[i for i,region in enumerate(RESERVE_ZONES)
                        if set(types)&set(HABITAT_TYPES[region["biome"]])]
            if ident in RARE_POKEMON_IDS:
                advanced=[i for i in candidates if i>=8]
                candidates=advanced or [15]
            if candidates:
                # Each species can appear in matching habitats; cache media only on encounter.
                for i in candidates:roaming_pools[i].append(entry)
        self.pokemon_habitat_pools=roaming_pools
        # Put familiar, already-cached sprites in the entrance clearing first.
        for pokemon_id, (x, y), starter_level in zip((1, 15, 16), ((265, 665), (700, 880), (1060, 665)), (2, 3, 3)):
            item = by_id.get(pokemon_id)
            if item and self.loaded_reserve_zone == 0 and not any(r.colliderect(pg.Rect(x-14,y-14,28,20)) for r in self.obstacles("reserve")):
                self.wild_pokemon.append({"id": pokemon_id, "x": float(x), "y": float(y), "home_x": float(x), "home_y": float(y),
                                          "moving": False, "state": "idle", "timer": self.pokemon_rng.uniform(1, 4), "vx": 0, "vy": 0, "level": starter_level, "requested": False})
                self.pokedex.request(pokemon_id)
        self.reserve_trainers = []
        for index, zone in enumerate(RESERVE_ZONES):
            if index != self.loaded_reserve_zone:
                continue
            zone_ids = (biome_ids[index] if index < len(biome_ids)
                        else [entry["id"] for entry in roaming_pools[index]])
            if not zone_ids:
                zone_ids = [1]
            pool = [by_id[i] for i in zone_ids if i in by_id and set(types_by_id.get(i,())) & set(HABITAT_TYPES[zone["biome"]])]
            if not pool:
                pool = roaming_pools[index] or [by_id[1]]
            # Keep the space's maximum-level Pokémon scarce: one encounter
            # occupies that tier, while every other encounter stays below it.
            encounter_count = 8 + (2 if index >= 8 else 0)
            space_max_level = max(5, RESERVE_LEVEL_REQUIREMENTS[index])
            max_level_slot = self.pokemon_rng.randrange(encounter_count)
            for slot in range(encounter_count):
                for attempt in range(50):
                    x = self.pokemon_rng.randint(zone["x"] + 110, zone["x"] + RESERVE_ZONE_W - 110)
                    y = self.pokemon_rng.randint(zone["y"] + 180, zone["y"] + RESERVE_ZONE_H - 150)
                    if math.hypot(x - 100, y - 800) < 180 and index == 0:
                        continue
                    if any(math.hypot(p["x"] - x, p["y"] - y) < 105 for p in self.wild_pokemon):
                        continue
                    if any(rect.colliderect(pg.Rect(x-14,y-14,28,20)) for rect in self.obstacles("reserve")):
                        continue
                    break
                else:
                    continue
                choices = pool
                if roaming_pools[index] and self.pokemon_rng.random() < .24:
                    choices = roaming_pools[index]
                rare_chance = min(.72, max(0.0, (index - 5) * .075))
                if index >= 5 and self.pokemon_rng.random() < rare_chance:
                    rare = [entry for entry in roaming_pools[index] if entry.get("id", 0) in RARE_POKEMON_IDS]
                    if rare:
                        choices = rare
                weather_multipliers = WEATHER_TYPES.get(self.life.weather, {})
                weighted = []
                for candidate in choices:
                    candidate_types = types_by_id.get(int(candidate.get("id", 0)), ())
                    multiplier = max([weather_multipliers.get(kind, 1.0) for kind in candidate_types] or [1.0])
                    weighted.append(multiplier)
                item = self.pokemon_rng.choices(choices, weights=weighted, k=1)[0]
                is_rare = int(item["id"]) in RARE_POKEMON_IDS
                is_top_level = slot == max_level_slot
                lv = (space_max_level if is_top_level else
                      self.pokemon_rng.randint(1, max(1, space_max_level - 1)))
                self.wild_pokemon.append({"id": item["id"], "x": float(x), "y": float(y), "home_x": float(x), "home_y": float(y),
                                          "moving": False, "state": "idle", "timer": self.pokemon_rng.uniform(1, 4), "vx": 0, "vy": 0,
                                          "level": lv, "requested": False, "zone": index, "rare": is_rare or is_top_level,
                                          "top_level": is_top_level})
            # Generate trainers only for the active sanctuary zone.
            trainer_styles = ("Hunter", "Woman", "Boy", "Villager4", "Cavegirl", "OldMan")
            available_ids = list(dict.fromkeys(int(entry["id"]) for entry in pool)) or [1]
            portrait_names = [entry["name"] for entry in self.trainer_versus_sprites
                              if entry["name"] != getattr(self.life, "trainer_versus_name", "")]
            for trainer_slot in range(3):
                trainer_x = trainer_y = None
                for _ in range(50):
                    candidate_x = self.pokemon_rng.randint(zone["x"] + 180, zone["x"] + RESERVE_ZONE_W - 180)
                    candidate_y = self.pokemon_rng.randint(zone["y"] + 250, zone["y"] + RESERVE_ZONE_H - 180)
                    feet = pg.Rect(candidate_x - 14, candidate_y - 14, 28, 20)
                    if index == 0 and math.hypot(candidate_x - 100, candidate_y - 800) < 250:
                        continue
                    if any(rect.colliderect(feet) for rect in self.obstacles("reserve")):
                        continue
                    if any(math.hypot(p["x"] - candidate_x, p["y"] - candidate_y) < 85
                           for p in self.wild_pokemon if p.get("zone") == index):
                        continue
                    trainer_x, trainer_y = candidate_x, candidate_y
                    break
                if trainer_x is None:
                    continue
                team_size = min(len(available_ids), self.pokemon_rng.randint(1, 3))
                team = self.pokemon_rng.sample(available_ids, team_size)
                level = self.pokemon_rng.randint(max(1, space_max_level - 2), space_max_level)
                trainer_name = (self.pokemon_rng.choice(portrait_names) if portrait_names else
                                f"Trainer {trainer_slot + 1}")
                self.reserve_trainers.append({
                    "id": f"reserve-{index}-trainer-{trainer_slot}", "name": trainer_name,
                    "x": float(trainer_x), "y": float(trainer_y), "team": team,
                    "level": level, "zone": index, "target": (float(trainer_x), float(trainer_y)),
                    "cooldown": self.pokemon_rng.uniform(1, 8), "defeated": False,
                    "paid": False, "trainer_style": trainer_styles[(index + trainer_slot) % len(trainer_styles)],
                    "trainer_versus_name": trainer_name})
            # Team Rocket visits odd-numbered sanctuaries. After a theft, the
            # pair relocates to the next odd sanctuary so the player can win
            # their Pokémon back there.
            stolen_records = getattr(self.life, "rocket_stolen_pokemon", [])
            rematch_zone = None
            if stolen_records:
                last_zone = max(int(record.get("zone", 0)) for record in stolen_records)
                rematch_zone = ((last_zone + 2) if last_zone % 2 == 0 else (last_zone + 1)) % len(RESERVE_ZONES)
            rocket_is_here = (index == rematch_zone if rematch_zone is not None
                              else index % 2 == 0)
            if rocket_is_here:
                rocket_ids = ((109, 24, 110), (52, 202, 109))
                rocket_names = ("Team Rocket · Jessie", "Team Rocket · James")
                rocket_styles = ("Woman", "Hunter")
                for rocket_slot in range(2):
                    rx = ry = None
                    for _ in range(60):
                        candidate_x = self.pokemon_rng.randint(zone["x"] + 190, zone["x"] + RESERVE_ZONE_W - 190)
                        candidate_y = self.pokemon_rng.randint(zone["y"] + 250, zone["y"] + RESERVE_ZONE_H - 180)
                        feet = pg.Rect(candidate_x - 14, candidate_y - 14, 28, 20)
                        if any(rect.colliderect(feet) for rect in self.obstacles("reserve")):
                            continue
                        if any(math.hypot(candidate_x - other["x"], candidate_y - other["y"]) < 90
                               for other in self.reserve_trainers):
                            continue
                        rx, ry = candidate_x, candidate_y
                        break
                    if rx is None:
                        continue
                    roster = [ident for ident in rocket_ids[rocket_slot] if ident in by_id]
                    if not roster:
                        roster = [int(available_ids[0])]
                    team_size=max(1,min(3,len(self.active_pokemon_team())))
                    team=roster[:team_size]
                    behavior = self.pokemon_rng.choice(("ambush", "challenge", "chase", "appear"))
                    for ident in roster:
                        self.pokedex.request(ident)
                    self.reserve_trainers.append({
                        "id": f"team-rocket-{index}-{rocket_slot}", "name": rocket_names[rocket_slot],
                        "x": float(rx), "y": float(ry), "team": team,
                        "rocket_roster": roster,
                        "level": max(5, min(100, RESERVE_LEVEL_REQUIREMENTS[index] + 2)),
                        "zone": index, "target": (float(rx), float(ry)), "cooldown": 0,
                        "defeated": False, "paid": False, "rocket_event": True,
                        "rocket_member": rocket_slot, "trainer_style": rocket_styles[rocket_slot],
                        "rocket_behavior": behavior, "rocket_revealed": behavior != "ambush",
                        "rocket_triggered": False})
            # After two local victories, reveal a high-level guardian Pokémon.
            # Defeating it is the key that opens neighboring spaces.
            wins = int(self.life.reserve_space_wins.get(str(index), 0))
            boss_threshold = self.reserve_boss_threshold(index)
            if wins >= boss_threshold and index not in self.life.reserve_space_bosses:
                boss_id = next((ident for ident in reversed(zone_ids) if ident in by_id), zone_ids[-1])
                boss_x, boss_y = zone["x"] + RESERVE_ZONE_W // 2, zone["y"] + 505
                self.wild_pokemon.append({"id": int(boss_id), "x": float(boss_x), "y": float(boss_y),
                    "home_x": float(boss_x), "home_y": float(boss_y), "moving": False,
                    "state": "idle", "timer": 1.0, "vx": 0, "vy": 0,
                    "level": min(100, max(10, RESERVE_LEVEL_REQUIREMENTS[index] + 5)),
                    "requested": False, "zone": index, "rare": True, "top_level": True,
                    "is_boss": True})
                self.pokedex.request(int(boss_id))

    def active_pokemon_team(self):
        team = [int(ident) for ident in self.life.pokemon_active if int(ident) in self.life.pokemon_party][:3]
        return team or [int(ident) for ident in self.life.pokemon_party[:3]] or [1]

    def random_battle_platforms(self):
        """Scatter climbable rock ledges across the player's side of each arena."""
        platforms = []
        attempts = 0
        target_count = self.pokemon_rng.randint(4, 7)
        while len(platforms) < target_count and attempts < 30:
            attempts += 1
            x = self.pokemon_rng.randint(150, 1150)
            if any(abs(x - item["x"]) < 52 for item in platforms):
                continue
            platforms.append({"x": x, "width": self.pokemon_rng.randint(68, 138),
                              "height": self.pokemon_rng.choice((-58, -92, -126, -160, -194))})
        return platforms

    def begin_pokemon_battle(self, pokemon_id, trainer=None, wild=None):
        if self.needs_depleted():
            self.notify("Kebutuhan habis: gerak melambat dan duel terkunci. Makan, minum, atau tidur dulu.")
            return
        pokemon_id = int(pokemon_id)
        team = self.active_pokemon_team()
        living = [ident for ident in team if self.life.pokemon_health.get(str(ident), 1) > 0]
        if not living:
            self.notify("Semua Pokémon aktif kehabisan HP. Pulihkan tim di Pokémon Center.")
            return
        opponent_lineup = [pokemon_id]
        if trainer and (trainer.get("rival") or int(trainer.get("level", 0)) > 20 or trainer.get("is_boss")):
            opponent_lineup = list(dict.fromkeys(int(ident) for ident in trainer.get("team", [])[:3]))
            if not trainer.get("rival"):
                backup_ids = [6, 25, 58, 74, 143, 149, 130, 94]
                for ident in backup_ids:
                    if len(opponent_lineup) >= 3:
                        break
                    if ident not in opponent_lineup:
                        opponent_lineup.append(ident)
            if pokemon_id in opponent_lineup:
                opponent_lineup.remove(pokemon_id)
            opponent_lineup.insert(0, pokemon_id)
            opponent_lineup = opponent_lineup[:3]
        if trainer and trainer.get("rocket_event"):
            # Match Rocket's team to the player's battle-ready active Pokémon,
            # not to their full collection. Dead or unselected partners do not
            # inflate the enemy lineup, so a new player gets a fair 1v1.
            team_size=max(1,min(3,len(living)))
            rocket_roster=trainer.get("rocket_roster",trainer.get("team",[]))
            opponent_lineup=list(dict.fromkeys(int(ident) for ident in rocket_roster))[:team_size]
            if not opponent_lineup:
                opponent_lineup=[pokemon_id]
            trainer["team"]=opponent_lineup[:]
        self.life.pokemon_seen = list(dict.fromkeys(self.life.pokemon_seen + [pokemon_id]))
        self.save_current()
        habitat=biome_at(self.life.scene,self.life.x,self.life.y)
        arena_style=("water" if habitat in ("coast","swamp","deepsea") else "sky" if habitat=="sky"
                     else "cave" if habitat in ("cave","crystal","volcano","dragon_valley") else "meadow")
        battle_weather=weather_for(self.life.scene,self.life.x,self.life.y,self.life.day,self.life.hour,self.life.weather_override)
        self.battle = {"wild_id": pokemon_id, "opponent_lineup": opponent_lineup, "opponent_index": 0,
                       "music_track": ("team_rocket_motto.mp3" if trainer and trainer.get("rocket_event")
                                       else self.choose_battle_music()),
                       "player_id": living[0], "player_lineup": team, "phase": "Memuat Pokémon…",
                       "player_x": 350.0, "enemy_x": 760.0, "player_y": 0.0, "enemy_y": 0.0,
                       "player_vy": 0.0, "player_facing": 1, "player_cooldown": 0.0,
                       "enemy_cooldown": 1.4, "enemy_ai_timer": .6, "enemy_action": "approach",
                       "enemy_target_x": 760.0, "enemy_target_y": 0.0, "enemy_guard_timer": 0.0,
                       "special_cooldown": 0.0, "hit_flash": 0.0,
                       "enemy_flash": 0.0, "block_flash": 0.0, "attack_flash": 0.0,
                       "attack_heavy": False, "type_cooldown": 0.0, "super_meter": 0.0,
                       "result": "", "trainer": trainer, "wild": wild,
                       "reserve_zone": (reserve_index_at(self.life.x, self.life.y)
                                       if self.life.scene == "reserve" and (wild is not None or
                                          (trainer and trainer.get("rocket_event"))) else None),
                       "trainer_condition": self.trainer_condition_multiplier(),
                       "wild_level": wild.get("level", 5) if wild else (trainer.get("level", 5) if trainer else 5), "vfx": None,
                       "time_left": 60.0 * (len(opponent_lineup) if trainer and trainer.get("rocket_event") else 1),
                       "timeout": False, "fruit_timer": self.pokemon_rng.uniform(3.0, 6.0),
                       "fruits": [],
                       "platforms": self.random_battle_platforms(),
                       "arena_style": arena_style, "battle_weather": battle_weather, "api_moves": [],
                       "intro": {"step": "player", "timer": 1.35, "index": 0, "cry_requested": False, "cry_played": False},
                       "rewarded": False}
        if trainer and trainer.get("rival"):
            self.battle["story_caption"] = f"MIRA · {self.rival_loadout()['line']}"
            self.battle["story_caption_timer"] = 4.5
        if (wild or {}).get("is_boss"):
            self.battle["boss_intro"] = {"timer": 2.6, "duration": 2.6}
            self.battle["intro"] = None
        self.battle_sprite = self.team_sprite = None
        self.pokedex.request(pokemon_id)
        self.pokedex.request(self.battle["player_id"])
        self.pokedex.request_animation(pokemon_id)
        self.pokedex.request_animation(self.battle["player_id"])
        self.pokedex.request_cry(pokemon_id)
        self.pokedex.request_cry(self.battle["player_id"])
        self.mode = "battle"
        self.life.complete("Pertarungan Pokémon")
        if self.pokemon_data(pokemon_id) and self.pokemon_data(self.battle["player_id"]):
            self.prepare_battle()

    def pokemon_data(self, pokemon_id):
        if pokemon_id is None:
            return None
        try:
            return self.pokedex.details.get(int(pokemon_id))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def base_stat(detail, name, default):
        if not detail:
            return default
        for item in detail.get("stats", []):
            if item.get("stat", {}).get("name") == name:
                return int(item.get("base_stat", default))
        return default

    def trainer_condition_multiplier(self):
        """Average trainer health and needs into a battle stat multiplier."""
        condition_values = [float(self.life.health)]
        condition_values.extend(float(value) for value in self.life.stats.values())
        return max(.25, min(1.0, sum(condition_values) / max(1, len(condition_values)) / 100.0))

    def save_battle_player_hp(self):
        """Persist battle HP on the Pokémon's normal, unscaled HP scale."""
        b = self.battle
        if not b or not b.get("player_max") or not b.get("raw_player_max"):
            return
        key = str(b["player_id"])
        ratio = max(0.0, min(1.0, b.get("player_hp", 0) / b["player_max"]))
        self.life.pokemon_health[key] = round(b["raw_player_max"] * ratio)

    def battle_stat(self, side, name, default):
        """Read a Pokémon stat with the PvE opponent's adaptive bonus applied."""
        if not self.battle:
            return default
        ident = self.battle.get("player_id" if side == "player" else "wild_id")
        detail = self.pokemon_data(ident) or {}
        value = self.base_stat(detail, name, default)
        if side == "player":
            value = max(1, round(value * self.battle.get("trainer_condition", 1.0)))
        else:
            value += int(self.battle.get("enemy_stat_bonus", {}).get(name, 0))
            value = round(value * self.battle.get("enemy_stat_multiplier", 1.0))
        return value

    def finish_battle(self, message):
        if self.countdown_tts_channel:
            self.countdown_tts_channel.stop()
        battle = self.battle or {}
        trainer = battle.get("trainer")
        wild = battle.get("wild")
        if wild in self.wild_pokemon and wild.get("state") == "challenged":
            wild["state"] = "flee"
            wild["timer"] = 2.0
            away = math.atan2(wild["y"] - self.life.y, wild["x"] - self.life.x)
            wild["vx"], wild["vy"] = math.cos(away), math.sin(away)
        lineup = battle.get("opponent_lineup", [battle.get("wild_id")])
        complete = battle.get("opponent_index", len(lineup) - 1) >= len(lineup) - 1
        dungeon_reward = None
        rocket_chase_alert = None
        rocket_event = bool(trainer and trainer.get("rocket_event"))
        if trainer and complete and battle.get("wild_hp", 1) <= 0 and battle.get("player_hp", 0) > 0:
            if not trainer.get("paid"):
                reward = 35 + trainer.get("level", 5) * 3
                self.life.money += reward
                trainer["paid"] = True
                message = f"{trainer['name']} kalah! +{reward} koin dan Pokémon mendapat pengalaman. " + message
            trainer["defeated"] = True
            trainer["cooldown"] = 35
            if rocket_event:
                stolen = list(getattr(self.life, "rocket_stolen_pokemon", []))
                if stolen:
                    returned_names = []
                    for record in stolen:
                        ident = int(record["id"])
                        if ident not in self.life.pokemon_party:
                            self.life.pokemon_party.append(ident)
                        if ident not in self.life.pokemon_caught:
                            self.life.pokemon_caught.append(ident)
                        detail = self.pokemon_data(ident) or {}
                        level = max(1, min(100, int(record.get("level", 5))))
                        self.life.pokemon_levels[str(ident)] = level
                        self.life.pokemon_health[str(ident)] = max(1, self.base_stat(detail, "hp", 45) + level * 2)
                        if len(self.life.pokemon_active) < 3 and ident not in self.life.pokemon_active:
                            self.life.pokemon_active.append(ident)
                        returned_names.append((detail.get("name", f"#{ident}")).title())
                    self.life.rocket_stolen_pokemon = []
                    names = ", ".join(returned_names)
                    message = self.words(f"Team Rocket dikalahkan! Pokémon yang dicuri kembali: {names}. ",
                                         f"Team Rocket was defeated! Stolen Pokémon returned: {names}. ") + message
            if trainer.get("rival"):
                self.life.rival_wins = int(getattr(self.life, "rival_wins", 0)) + 1
                stage = self.life.rival_wins
                loadout = self.rival_loadout()
                trainer["level"] = loadout["level"]
                trainer["team"] = loadout["team"]
                if stage % 3 == 0:
                    self.life.gacha_tickets += 1
                    message = self.words(f"Rival Mira kalah untuk ke-{stage} kalinya! Ia akan kembali lebih kuat. +1 tiket gacha. ",
                                         f"Rival Mira lost for the {stage}th time! She will return stronger. +1 gacha ticket. ") + message
                else:
                    message = self.words(f'Mira: "{loadout["line"]}" · tantangan berikutnya lebih kuat. ',
                                         f'Mira: "{loadout["line"]}" · the next challenge will be stronger. ') + message
            self.save_current()
        elif rocket_event and battle.get("player_hp", 1) <= 0:
            lost_id = int(battle.get("player_id", 0))
            if lost_id in self.life.pokemon_party and len(self.life.pokemon_party) > 1:
                records = list(getattr(self.life, "rocket_stolen_pokemon", []))
                records.append({"id": lost_id,
                                "zone": int(battle.get("reserve_zone", trainer.get("zone", 0))),
                                "level": self.pokemon_level(lost_id)})
                self.life.rocket_stolen_pokemon = records[-20:]
                self.life.pokemon_party.remove(lost_id)
                self.life.pokemon_caught = [ident for ident in self.life.pokemon_caught if ident != lost_id]
                self.life.pokemon_active = [ident for ident in self.life.pokemon_active if ident != lost_id]
                self.life.pokemon_health.pop(str(lost_id), None)
                if not self.life.pokemon_active:
                    self.life.pokemon_active = self.life.pokemon_party[:1]
                detail = self.pokemon_data(lost_id) or {}
                name = detail.get("name", f"Pokémon #{lost_id}").title()
                zone = int(battle.get("reserve_zone", trainer.get("zone", 0)))
                next_zone = ((zone + 2) if zone % 2 == 0 else (zone + 1)) % len(RESERVE_ZONES)
                next_name = RESERVE_ZONES[next_zone]["name"]
                message = self.words(f"Team Rocket membawa {name}! Tantang mereka kembali di {next_name} untuk mendapatkannya lagi. ",
                                     f"Team Rocket took {name}! Challenge them again in {next_name} to get it back. ") + message
                rocket_chase_alert = {
                    "id": lost_id,
                    "name": name,
                    "zone": next_name,
                    "stolen": True,
                }
                self.save_current()
            else:
                message = self.words("Team Rocket menang, tetapi Pokémon terakhirmu berhasil kabur dan tidak bisa dicuri. ",
                                     "Team Rocket won, but your last Pokémon escaped and cannot be stolen. ") + message
                zone = int(battle.get("reserve_zone", trainer.get("zone", 0)))
                next_zone = ((zone + 2) if zone % 2 == 0 else (zone + 1)) % len(RESERVE_ZONES)
                rocket_chase_alert = {
                    "id": lost_id,
                    "name": (self.pokemon_data(lost_id) or {}).get("name", f"Pokémon #{lost_id}").title(),
                    "zone": RESERVE_ZONES[next_zone]["name"],
                    "stolen": False,
                }
        if rocket_event:
            rocket_zone = int(trainer.get("zone", battle.get("reserve_zone", 0)))
            self.reserve_trainers = [npc for npc in self.reserve_trainers
                                     if not (npc.get("rocket_event") and int(npc.get("zone", -1)) == rocket_zone)]
        zone_index = battle.get("reserve_zone")
        if zone_index is not None and battle.get("space_battle_wins") is not None:
            zone = RESERVE_ZONES[int(zone_index)]
            wins = int(self.life.reserve_space_wins.get(str(zone_index), 0))
            if battle.get("space_boss_just_unlocked"):
                message += f" Boss {zone['name']} muncul!"
            elif int(zone_index) not in self.life.reserve_space_bosses:
                threshold = self.reserve_boss_threshold(zone_index)
                message += f" Kemenangan space: {wins}/{threshold} sebelum boss muncul."
        if battle.get("space_boss_defeated_now"):
            zone = RESERVE_ZONES[int(battle["reserve_zone"])]
            message += f" Boss Pokémon Lv.{battle.get('wild_level', 5)} dikalahkan! Gerbang dari {zone['name']} kini terbuka."
        if trainer and trainer.get("local_dungeon"):
            won = bool(complete and battle.get("wild_hp", 1) <= 0 and battle.get("player_hp", 0) > 0)
            if won:
                tier = int(battle.get("dungeon_tier", trainer.get("dungeon_tier", 1)))
                if tier not in self.life.local_dungeon_cleared:
                    self.life.local_dungeon_cleared.append(tier)
                    self.life.local_dungeon_cleared.sort()
                self.life.local_dungeon_tier = max(int(self.life.local_dungeon_tier), tier + 1)
                self.life.money += 150 + tier * 50
                self.life.gacha_tickets += 1
                dungeon_reward = {
                    "title": self.words("DUNGEON DITAKLUKKAN!", "DUNGEON CLEARED!"),
                    "details": [
                        self.words(f"+{150 + tier * 50} koin", f"+{150 + tier * 50} coins"),
                        self.words("+1 Tiket Gacha", "+1 Gacha Ticket"),
                        self.words(f"Gerbang Dungeon Lv.{self.local_dungeon_level(tier + 1)} terbuka",
                                   f"Dungeon Lv.{self.local_dungeon_level(tier + 1)} gate unlocked") if tier < 10 else
                        self.words("Semua dungeon selesai · semua Pokémon terbuka!", "All dungeons cleared · all Pokémon unlocked!")
                    ],
                }
                message += self.words(
                    f"Dungeon Lv.{self.local_dungeon_level(tier)} ditaklukkan! Hadiah {150 + tier * 50} koin + 1 tiket gacha. Pintu dungeon berikutnya terbuka.",
                    f"Lv.{self.local_dungeon_level(tier)} dungeon cleared! Reward: {150 + tier * 50} coins + 1 gacha ticket. The next dungeon is open.")
                if tier >= 10:
                    all_ids = list(pokemon_db.type_catalog())
                    self.life.pokemon_caught = list(dict.fromkeys(self.life.pokemon_caught + all_ids))
                    self.life.pokemon_seen = list(dict.fromkeys(self.life.pokemon_seen + all_ids))
                    self.life.local_dungeon_champion = True
                    self.award_trainer_xp(10000)
                    message += self.words(" SEMUA 1025 SPESIES TERBUKA · KAMU MENANG! Jelajahi dunia sepuasnya.",
                                          " ALL 1,025 SPECIES UNLOCKED · YOU WIN! Keep exploring the world.")
            self.save_current()
        self.battle = None
        self.mode = "game"
        if (battle.get("space_boss_just_unlocked") or battle.get("space_boss_defeated_now")) and self.life.scene == "reserve":
            self.spawn_map_pokemon()
        if dungeon_reward:
            self.show_reward(message, "game", details=dungeon_reward["details"],
                             title=dungeon_reward["title"])
        elif rocket_chase_alert:
            name=rocket_chase_alert["name"]
            zone=rocket_chase_alert["zone"]
            if rocket_chase_alert["stolen"]:
                details=[
                    self.words(f"Team Rocket membawa {name}.",f"Team Rocket stole {name}."),
                    self.words(f"Mereka kabur ke {zone}.",f"They escaped to {zone}."),
                    self.words("Kalahkan mereka di sana untuk mendapatkan Pokémonmu kembali.",
                               "Defeat them there to get your Pokémon back."),
                ]
            else:
                details=[
                    self.words(f"{name} berhasil lolos dan tetap menjadi milikmu.",
                               f"{name} escaped and is still yours."),
                    self.words(f"Team Rocket kabur ke {zone}.",f"Team Rocket fled to {zone}."),
                    self.words("Tantang mereka lagi di suaka itu.","Challenge them again in that sanctuary."),
                ]
            self.show_reward(self.words("TEAM ROCKET KABUR!","TEAM ROCKET ESCAPED!"),"game",
                             ident=rocket_chase_alert["id"],details=details,
                             title=self.words("KEJAR MEREKA!","CHASE THEM!"))
        else:
            self.notify(message)

    def pokemon_level(self, pokemon_id):
        return max(1, min(100, int(self.life.pokemon_levels.get(str(int(pokemon_id)), 5))))

    def award_pokemon_xp(self, pokemon_id, amount):
        key = str(int(pokemon_id))
        level = self.pokemon_level(pokemon_id)
        xp = int(self.life.pokemon_xp.get(key, 0)) + int(amount)
        leveled = False
        while level < 100 and xp >= level * 18:
            xp -= level * 18
            level += 1
            leveled = True
        self.life.pokemon_levels[key], self.life.pokemon_xp[key] = level, xp
        return leveled, level

    def award_trainer_xp(self, amount):
        """Award account XP; every level-scaled XP threshold raises the trainer."""
        amount = max(0, int(amount))
        self.life.trainer_xp_bank = int(getattr(self.life, "trainer_xp_bank", 0)) + amount
        xp = int(getattr(self.life, "trainer_xp", 0)) + amount
        level = max(1, int(getattr(self.life, "trainer_level", 1)))
        leveled = False
        while level < 100 and xp >= level * 100:
            xp -= level * 100
            level += 1
            leveled = True
        self.life.trainer_xp, self.life.trainer_level = xp, level
        return leveled, level

    def closest_pokemon(self, max_distance=150, include_hidden=False):
        candidates = [p for p in self.wild_pokemon if include_hidden or p.get("state") != "hide"]
        candidates = [p for p in candidates if math.hypot(p["x"] - self.life.x, p["y"] - self.life.y) <= max_distance]
        return min(candidates, key=lambda p: math.hypot(p["x"] - self.life.x, p["y"] - self.life.y), default=None) if candidates else None

    def closest_trainer(self, max_distance=112):
        trainers = self.reserve_trainers + [t for t in self.route_trainers if t["scene"] == self.life.scene]
        nearby = [t for t in trainers if t.get("cooldown", 0) <= 0
                  and not (t.get("rocket_event") and t.get("rocket_behavior", "challenge") == "challenge")
                  and not (t.get("rocket_event") and t.get("rocket_behavior") == "ambush"
                           and not t.get("rocket_revealed"))
                  and math.hypot(t["x"] - self.life.x, t["y"] - self.life.y) <= max_distance]
        return min(nearby, key=lambda t: math.hypot(t["x"] - self.life.x, t["y"] - self.life.y), default=None)

    def attack_nearby_pokemon(self):
        # A trainer standing beside the player takes priority over nearby
        # wildlife so Space opens the same VS invitation as the interaction key.
        trainer = self.closest_trainer()
        if trainer:
            self.invite_trainer(trainer)
            return
        if self.life.scene == "reserve":
            pokemon = self.closest_pokemon(155)
            if pokemon:
                self.open_pokemon_encounter(pokemon)
                return
        if self.life.scene == "reserve" and self.closest_pokemon(150, include_hidden=True):
            self.notify("Ada gerakan di semak! Dekati pelan-pelan atau coba serang saat Pokémon terlihat.")
            return
        self.attack()

    def open_pokemon_encounter(self, pokemon):
        self.encounter_target = pokemon
        self.encounter_choice = 0
        self.pokedex.request(pokemon["id"])
        self.pokedex.request_species(pokemon["id"])
        self.play_pokemon_cry(pokemon["id"])
        self.mode = "encounter"

    def play_pokemon_cry(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        sound = self.pokemon_sounds.get(pokemon_id)
        if sound:
            # Prevent a cry loaded asynchronously from playing twice in one moment.
            last_id, last_at = self._last_pokemon_cry
            if last_id == pokemon_id and time.monotonic() - last_at < .45:
                return True
            sound.play()
            self._last_pokemon_cry = (pokemon_id, time.monotonic())
            return True
        self.pokedex.request_cry(pokemon_id)
        return False

    def queue_pokemon_cry(self, pokemon_id):
        """Play a cached cry now, or play it when the async PokéAPI request finishes."""
        pokemon_id = int(pokemon_id)
        if self.play_pokemon_cry(pokemon_id):
            return True
        if self.battle:
            self.battle["queued_cry"] = pokemon_id
        return False

    def play_battle_sound(self, sound_name, volume=0.52):
        sound = self.battle_sounds.get(sound_name)
        if sound:
            sound.set_volume(volume)
            sound.play()

    def play_action_sound(self, sound_name, volume=0.42):
        """Load small local action sounds only when an action first needs them."""
        if not pg.mixer.get_init():
            return
        choices = {
            "wildlife-hurt": ("hurt_01.ogg", "hurt_02.ogg"),
            "lion-call": ("roar_01.ogg", "roar_02.ogg"),
        }.get(sound_name)
        if choices:
            filename = self.pokemon_rng.choice(choices)
        else:
            filename = {
                "chicken": "chicken.ogg", "wildlife-hurt": "hurt_01.ogg",
                "cook-sizzle": "cook-sizzle.wav", "stove-on": "stove-on.ogg",
                "attack-swing": "scythe-swish.wav", "grunt_01": "grunt_01.ogg",
                "grunt_02": "grunt_02.ogg", "fire": "fire.ogg", "water": "water.ogg",
                "earth": "earth.ogg", "wind": "wind.ogg", "punch": "punch.ogg",
                "sleep": "sleep.wav",
            }.get(sound_name, f"{sound_name}.wav")
        path = ROOT / "assets" / "audio" / "sfx" / "actions" / filename
        if not path.is_file():
            path = ROOT / "assets" / "audio" / "sfx" / filename
        if not path.is_file():
            return
        try:
            sound = self.action_sounds.get(filename)
            if sound is None:
                sound = pg.mixer.Sound(str(path))
                self.action_sounds[filename] = sound
            sound.set_volume(volume)
            sound.play()
        except (pg.error, OSError):
            return

    def queue_action_sound(self, sound_name, delay, volume=0.42):
        self.pending_action_sounds.append((time.monotonic() + delay, sound_name, volume))

    def play_wildlife_call(self, species):
        if species == "Singa":
            self.play_action_sound("lion-call", .28)
        elif species in ("Hyena", "Babi hutan"):
            self.play_action_sound("grunt_01", .22)
        elif species == "Gajah":
            self.play_action_sound("grunt_02", .24)

    def play_type_sound(self, move_type, ultimate=False):
        sound_name = {
            "fire": "fire", "water": "water", "ground": "earth", "rock": "earth",
            "flying": "wind", "grass": "leaf", "bug": "leaf", "ice": "water",
            "electric": "ultimate_charge", "psychic": "ultimate_charge", "ghost": "ultimate_charge",
            "dragon": "fire", "poison": "ultimate_charge", "fairy": "ultimate_charge",
            "steel": "punch", "fighting": "punch", "normal": "punch", "dark": "wind",
        }.get(move_type, "punch")
        self.play_battle_sound(sound_name, .62 if ultimate else .42)

    def play_ultimate_impact(self, move_type):
        """Play a CC0 blast together with the matching elemental sound."""
        self.play_battle_sound("ultimate_explosion", .72)
        self.play_type_sound(move_type, True)

    @staticmethod
    def valid_countdown_audio(path):
        # A interrupted OS speech renderer can leave a valid header with no PCM.
        # SDL_mixer may accept that file but crash when its empty Sound is played.
        try:
            with wave.open(str(path), "rb") as audio:
                frames = audio.getnframes()
                return (frames > 0 and len(audio.readframes(frames)) ==
                        frames * audio.getnchannels() * audio.getsampwidth())
        except (OSError, EOFError, wave.Error):
            return False

    def prepare_countdown_audio(self):
        """Pre-render free OS TTS words to WAV so each cue can drive its own text."""
        def worker():
            try:
                self.countdown_tts_dir.mkdir(parents=True, exist_ok=True)
                cues = {
                    "id": (("READY", "Siap"), ("3", "Tiga"), ("2", "Dua"), ("1", "Satu")),
                    "en": (("READY", "Ready"), ("3", "Three"), ("2", "Two"), ("1", "One")),
                }
                for language, entries in cues.items():
                    for key, phrase in entries:
                        path = self.countdown_tts_dir / f"{language}-{key.lower()}.wav"
                        if not self.valid_countdown_audio(path):
                            # Keep earlier cache files intact; repair into a separate file.
                            path = self.countdown_tts_dir / f"{language}-{key.lower()}-complete.wav"
                        if not self.valid_countdown_audio(path):
                            try:
                                if sys.platform == "darwin":
                                    command = ["say", "-o", str(path), "--file-format=WAVE",
                                               "--data-format=LEI16@22050", "-r", "165", phrase]
                                elif sys.platform.startswith("win"):
                                    safe_path = str(path).replace("'", "''")
                                    safe_phrase = phrase.replace("'", "''")
                                    script = ("Add-Type -AssemblyName System.Speech; "
                                              "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                                              f"$s.SetOutputToWaveFile('{safe_path}'); $s.Speak('{safe_phrase}'); $s.Dispose()")
                                    command = ["powershell", "-NoProfile", "-Command", script]
                                else:
                                    engine = shutil.which("espeak-ng") or shutil.which("espeak")
                                    if not engine:
                                        continue
                                    command = [engine, "-s", "165", "-w", str(path), phrase]
                                subprocess.run(command, stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL, timeout=20, check=True)
                            except (OSError, subprocess.SubprocessError):
                                continue
                        if self.valid_countdown_audio(path):
                            with self.countdown_tts_lock:
                                self.countdown_tts_pending.append((language, key, path))
            finally:
                self.countdown_tts_loading = False

        threading.Thread(target=worker, name="openrpg-countdown-tts", daemon=True).start()

    def load_countdown_audio(self):
        if not pg.mixer.get_init():
            return
        with self.countdown_tts_lock:
            pending, self.countdown_tts_pending = self.countdown_tts_pending, []
        for language, key, path in pending:
            try:
                if not self.valid_countdown_audio(path):
                    continue
                sound = pg.mixer.Sound(str(path))
                if sound.get_length() > 0:
                    self.countdown_tts_sounds[language, key] = sound
            except (pg.error, OSError):
                pass

    @staticmethod
    def make_victory_sound():
        """Short, locally generated 8-bit fanfare; no download or paid asset."""
        import array
        sample_rate = pg.mixer.get_init()[0]
        channels = pg.mixer.get_init()[2]
        notes = ((784, .12), (988, .12), (1175, .12), (1568, .32))
        samples = array.array("h")
        for frequency, duration in notes:
            count = int(sample_rate * duration)
            for index in range(count):
                envelope = min(1.0, index / 160, (count - index) / 350)
                value = int(7500 * envelope * (1 if math.sin(math.tau * frequency * index / sample_rate) >= 0 else -1))
                samples.extend([value] * channels)
        return pg.mixer.Sound(buffer=samples.tobytes())

    def speak_free_tts(self, phrase, rate=235):
        """Use the installed OS speech synthesizer asynchronously (free, offline)."""
        if sys.platform == "darwin":
            command = ["say", "-r", str(rate), phrase]
        elif sys.platform.startswith("win"):
            script = "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak($args[0])"
            command = ["powershell", "-NoProfile", "-Command", script, phrase]
        elif shutil.which("espeak"):
            command = ["espeak", phrase]
        elif shutil.which("spd-say"):
            command = ["spd-say", phrase]
        else:
            return
        with self._tts_lock:
            self._tts_queue.append(command)
            if self._tts_worker_running:
                return
            self._tts_worker_running = True
        threading.Thread(target=self._tts_worker, daemon=True).start()

    def _tts_worker(self):
        while True:
            with self._tts_lock:
                if not self._tts_queue:
                    self._tts_worker_running = False
                    return
                command = self._tts_queue.pop(0)
            try:
                subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=4, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def rival_loadout(self):
        """Progress Mira's dialogue and team as the player wins rematches."""
        stage = max(0, int(getattr(self.life, "rival_wins", 0)))
        teams = ((25, 19), (25, 19, 58), (26, 20, 59), (26, 59, 133),
                 (26, 59, 135), (26, 149, 135), (150, 149, 135))
        lines_id = (
            "Aku baru mulai berlatih. Ayo bertarung dengan sportif!",
            "Aku melatih timku sejak duel terakhir. Kali ini aku siap!",
            "Kita makin kuat bersama. Aku ingin lihat perkembanganmu!",
            "Aku menemukan strategi baru. Jangan lengah kali ini!",
            "Perjalanan kita panjang, tapi aku belum menyerah. Ayo!",
            "Rival sepertimu membuatku berkembang. Tunjukkan kemampuanmu!",
            "Pertarungan terakhir kita! Mari berikan yang terbaik!",
        )
        lines_en = (
            "I'm just getting started. Let's have a fair battle!",
            "I've trained my team since our last duel. I'm ready!",
            "We've both grown stronger. Let's see how far you've come!",
            "I found a new strategy. Stay sharp this time!",
            "We've come a long way, but I'm not giving up. Let's go!",
            "A rival like you helped me grow. Show me what you've got!",
            "Our final showdown! Let's give it everything!",
        )
        index = min(stage, len(teams) - 1)
        lines = lines_id if self.life.language == "id" else lines_en
        return {"stage": stage, "team": list(teams[index]),
                "level": min(75, 8 + stage * 3), "line": lines[index]}

    def needs_depleted(self):
        return any(self.life.stats.get(key, 0) <= 0 for key in ("Kenyang", "Minum", "Energi"))

    def play_hit_cry(self, pokemon_id):
        now = time.monotonic()
        if now - self.last_hit_cry < .65:
            return
        self.last_hit_cry = now
        self.play_battle_sound("punch", .22)
        self.queue_pokemon_cry(pokemon_id)

    def hospitality_order(self, option):
        if option == "meal":
            message = self.life.restaurant_meal()
        elif option == "drink":
            message = self.life.restaurant_drink()
        else:
            message = self.life.hotel_stay()
        self.notify(message)
        if message.startswith(("Makan selesai", "Minuman disajikan", "Menginap selesai")):
            self.play_action_sound({"meal": "eat", "drink": "drink"}.get(option, "sleep"), .36)
            self.mode = "game"

    def draw_hospitality(self):
        restaurant = self.hospitality_kind == "restaurant"
        self.text("RESTORAN · PEMULIHAN" if restaurant else "HOTEL · ISTIRAHAT",
                  242, 183, CREAM, self.medium)
        self.text(f"Koin {self.life.money} · kebutuhan kosong membuat gerak lambat dan duel terkunci.",
                  245, 230, GREEN, self.small)
        if restaurant:
            self.button("Makan hangat · 10 koin", (245, 292, 788, 56),
                        lambda: self.hospitality_order("meal"), True)
            self.button("Minum segar · 5 koin", (245, 361, 788, 56),
                        lambda: self.hospitality_order("drink"))
            self.text("Makan memulihkan kenyang, energi, dan sedikit kesehatan.",
                      245, 445, MUTED, self.small)
        else:
            self.button("Menginap 8 jam · 15 koin", (245, 292, 788, 56),
                        lambda: self.hospitality_order("hotel"), True)
            self.text("Tidur memulihkan seluruh kebutuhan dan HP. Waktu dunia maju 8 jam.",
                      245, 374, MUTED, self.small)
        self.button("Kembali · Esc", (245, 592, 788, 44), self.back)

    def choose_encounter_battle(self):
        pokemon = self.encounter_target
        if not pokemon:
            self.mode = "game"
            return
        pokemon["state"] = "challenged"
        self.begin_pokemon_battle(pokemon["id"], wild=pokemon)

    def show_encounter_info(self):
        if self.encounter_target:
            self.pokedex.request(self.encounter_target["id"])
            self.pokedex.request_species(self.encounter_target["id"])
            self.mode = "pokemon_info"

    def update_reserve_pokemon(self, dt):
        obstacles = self.obstacles("reserve")
        for pokemon in self.wild_pokemon:
            if pokemon.get("is_boss"):
                # The guardian waits in place; it does not flee or hide.
                pokemon["moving"] = False
                if not pokemon.get("requested") and math.hypot(pokemon["x"]-self.life.x, pokemon["y"]-self.life.y) < 1400:
                    self.pokedex.request(pokemon["id"])
                    pokemon["requested"] = True
                continue
            if pokemon.get("approaching") or abs(pokemon["x"]-self.life.x)>1400 or abs(pokemon["y"]-self.life.y)>1700:
                continue
            pokemon["timer"] = max(0, pokemon.get("timer", 0) - dt)
            dx, dy = self.life.x - pokemon["x"], self.life.y - pokemon["y"]
            distance = math.hypot(dx, dy)
            if pokemon.get("state") == "hide":
                if pokemon["timer"] <= 0 or distance > 330:
                    pokemon["state"], pokemon["timer"] = "idle", self.pokemon_rng.uniform(1, 3)
                continue
            if distance < 225 and pokemon.get("state") != "flee":
                if distance < 135 and self.pokemon_rng.random() < .26:
                    pokemon["state"] = "hide"
                    pokemon["timer"] = self.pokemon_rng.uniform(2.5, 5.5)
                    continue
                angle = math.atan2(pokemon["y"] - self.life.y, pokemon["x"] - self.life.x)
                pokemon["vx"], pokemon["vy"] = math.cos(angle), math.sin(angle)
                pokemon["state"], pokemon["timer"] = "flee", self.pokemon_rng.uniform(1.3, 2.2)
            elif pokemon["timer"] <= 0 and pokemon.get("state") in ("idle", "wander"):
                if pokemon.get("state") == "wander":
                    pokemon["state"] = "idle"
                    pokemon["timer"] = self.pokemon_rng.uniform(1.2, 3.5)
                else:
                    angle = self.pokemon_rng.random() * math.tau
                    pokemon["vx"], pokemon["vy"] = math.cos(angle), math.sin(angle)
                    pokemon["state"] = "wander"
                    pokemon["timer"] = self.pokemon_rng.uniform(1.4, 4.0)
            if pokemon.get("state") == "flee" and pokemon["timer"] <= 0:
                pokemon["state"] = "idle"
                pokemon["timer"] = self.pokemon_rng.uniform(2, 4)
            if pokemon.get("state") in ("wander", "flee"):
                speed = 132 if pokemon["state"] == "flee" else 34
                old_x, old_y = pokemon["x"], pokemon["y"]
                pokemon["x"] += pokemon["vx"] * speed * dt
                pokemon["y"] += pokemon["vy"] * speed * dt
                zone = RESERVE_ZONES[pokemon.get("zone", 0)]
                pokemon["x"] = max(zone["x"] + 45, min(zone["x"] + RESERVE_ZONE_W - 45, pokemon["x"]))
                pokemon["y"] = max(zone["y"] + 115, min(zone["y"] + RESERVE_ZONE_H - 55, pokemon["y"]))
                rect = pg.Rect(pokemon["x"] - 14, pokemon["y"] - 14, 28, 20)
                if any(rect.colliderect(o) for o in obstacles):
                    pokemon["x"], pokemon["y"] = old_x, old_y
                    pokemon["vx"], pokemon["vy"] = -pokemon["vy"], pokemon["vx"]
                pokemon["moving"] = True
            else:
                pokemon["moving"] = False
            if not pokemon.get("requested") and distance < 1000:
                self.pokedex.request(pokemon["id"])
                pokemon["requested"] = True

    def update_trainers(self, dt):
        for trainer in self.reserve_trainers + self.route_trainers:
            if trainer.get("approaching"):
                continue
            trainer["cooldown"] = max(0, trainer.get("cooldown", 0) - dt)
            if "scene" in trainer and trainer["scene"] != self.life.scene:
                continue
            if "scene" not in trainer and self.life.scene != "reserve":
                continue
            if trainer.get("id") == "arena-champion":
                continue
            if trainer.get("cooldown", 0) > 0:
                continue
            tx, ty = trainer.get("target", (trainer["x"], trainer["y"]))
            dx, dy = tx - trainer["x"], ty - trainer["y"]
            distance = math.hypot(dx, dy)
            if distance < 12:
                if "scene" not in trainer or trainer["scene"] == "reserve":
                    zone = RESERVE_ZONES[trainer.get("zone", 0)]
                    min_x, max_x = zone["x"] + 180, zone["x"] + RESERVE_ZONE_W - 150
                    min_y, max_y = zone["y"] + 250, zone["y"] + RESERVE_ZONE_H - 180
                    trainer["target"] = (self.pokemon_rng.randint(min_x, max_x), self.pokemon_rng.randint(min_y, max_y))
                else:
                    trainer["target"] = (self.pokemon_rng.randint(500, 1040), self.pokemon_rng.randint(370, 445))
                continue
            speed = 24 if not trainer.get("defeated") else 14
            trainer["x"] += dx / distance * speed * dt
            trainer["y"] += dy / distance * speed * dt

    def pokemon_attack(self, heavy=False):
        b = self.battle
        if self.needs_depleted():
            if b:
                b["phase"] = "Kebutuhan habis · duel terkunci sampai makan, minum, atau tidur."
            return
        if not b or "wild_hp" not in b or b.get("result") or b.get("player_cooldown", 0) > 0:
            return
        if heavy and b.get("special_cooldown", 0) > 0:
            b["phase"] = "Jurus masih mengisi tenaga. Dekati lawan atau tahan S untuk bertahan."
            return
        enemy = self.pokemon_data(b["wild_id"])
        team = self.pokemon_data(b["player_id"])
        b["player_cooldown"] = 0.72 if heavy else 0.34
        if heavy:
            b["special_cooldown"] = 2.4
        b["attack_flash"] = .22 if not heavy else .36
        b["attack_heavy"] = heavy
        gap_x = abs(b["enemy_x"] - b["player_x"])
        gap_y = abs(b.get("enemy_y", 0) - b.get("player_y", 0))
        guarded = b.get("enemy_guard_timer", 0) > 0
        hit = gap_x <= 155 and gap_y <= 72 and self.pokemon_rng.randrange(100) < (54 if guarded else 92)
        self._set_battle_vfx("normal", "👊 Hantaman", emoji="👊")
        if not hit:
            b["vfx"]["target_x"] = b["player_x"] + b["player_facing"] * min(118, gap_x)
            b["vfx"]["target_y"] = 500 + b.get("player_y", 0) - 18
            b["phase"] = "Pukulan meleset · dekati lawan dengan panah."
            return
        damage = max(9, self.base_stat(team, "attack", 49) // (4 if heavy else 7))
        if heavy:
            damage = int(damage * 1.7)
        damage = max(1, damage - self.base_stat(enemy, "defense", 49) // 30)
        enemy_types = tuple(item["type"]["name"] for item in enemy.get("types", []))
        effectiveness = pokemon_db.effectiveness("normal", enemy_types)
        damage = int(damage * effectiveness)
        if effectiveness == 0:
            b["phase"] = "Tidak mempan! Tipe Ghost kebal terhadap serangan Normal."
            return
        if guarded:
            damage = max(1, int(damage * .45))
        b["wild_hp"] = max(0, b["wild_hp"] - damage)
        b["enemy_flash"] = .24
        b["phase"] = (f"Lawan menangkis! Jurus hanya −{damage} HP." if guarded else
                       f"{('Jurus' if heavy else 'Pukulan')} kena! −{damage} HP.")
        b["super_meter"] = min(100, b.get("super_meter", 0) + (16 if heavy else 12))
        if b["wild_hp"] <= 0:
            self._win_battle()

    def _set_battle_vfx(self, move_type, move_name, ultimate=False, emoji=None):
        b = self.battle
        profile = TYPE_MOVES.get(move_type, TYPE_MOVES["normal"])
        self.play_type_sound(move_type, ultimate=ultimate)
        b["vfx"] = {"type": profile[2], "color": profile[1], "name": move_name,
                    "timer": 1.85 if ultimate else .48, "duration": 1.85 if ultimate else .48,
                    "ultimate": ultimate, "emoji": emoji or TYPE_EMOJI.get(move_type, "💥"),
                    "start_x": b["player_x"], "start_y": 500 + b.get("player_y", 0),
                    "target_x": b["enemy_x"], "target_y": 500 + b.get("enemy_y", 0)}
        b["phase"] = f"{move_name}!"

    def pokemon_type_attack(self, slot=0):
        b = self.battle
        if self.needs_depleted():
            if b:
                b["phase"] = "Kebutuhan habis · duel terkunci sampai makan, minum, atau tidur."
            return
        if not b or "wild_hp" not in b or b.get("result") or b.get("type_cooldown", 0) > 0:
            return
        team, enemy = self.pokemon_data(b["player_id"]), self.pokemon_data(b["wild_id"])
        if not team or not enemy:
            return
        move_names = b.get("api_moves", [])
        move_name = move_names[slot] if slot < len(move_names) else None
        move = self.pokedex.moves.get(move_name) if move_name else None
        if move_name and not move:
            self.pokedex.request_move(move_name)
        types = team.get("types", [])
        move_type = (move or {}).get("type", {}).get("name") or (types[slot % len(types)]["type"]["name"] if types else "normal")
        api_name = (move or {}).get("names", [])
        localized = next((item["name"] for item in api_name if item.get("language", {}).get("name") == "en"), None)
        move_name = (localized or (move_name.replace("-", " ").title() if move_name else TYPE_MOVES.get(move_type, TYPE_MOVES["normal"])[0]))
        b["type_cooldown"] = 1.45
        b["player_cooldown"] = .28
        self._set_battle_vfx(move_type, f"{TYPE_EMOJI.get(move_type, '💥')} {move_name}")
        category = (move or {}).get("damage_class", {}).get("name", "special")
        close_moves = ("punch", "kick", "tackle", "scratch", "bite", "wing-attack", "slash", "headbutt")
        if category == "physical" and (move_type in ("fighting", "normal") or any(token in (move_name or "") for token in close_moves)):
            reach = 205
        elif category == "status":
            reach = 330
        elif category == "physical":
            reach = 390
        else:
            reach = 610
        distance = math.hypot(b["enemy_x"] - b["player_x"], b.get("enemy_y", 0) - b.get("player_y", 0))
        accuracy = (move or {}).get("accuracy") or 86
        guarded = b.get("enemy_guard_timer", 0) > 0
        hit = distance <= reach and self.pokemon_rng.randrange(100) < (accuracy * (.56 if guarded else 1))
        if not hit:
            b["vfx"]["target_x"] = b["enemy_x"] + self.pokemon_rng.choice((-1, 1)) * 48
            b["vfx"]["target_y"] = 500 + b.get("enemy_y", 0) + self.pokemon_rng.choice((-1, 1)) * 42
            b["phase"] = f"{move_name} meleset · jangkauan {reach}."
            return
        attack = self.base_stat(team, "special-attack", 55)
        defense = self.base_stat(enemy, "special-defense", 55)
        power = (move or {}).get("power") or 55
        damage = max(8, int((attack * power / 100 + self.pokemon_level(b["player_id"]) * .7) - defense * .08))
        opposing = tuple(entry["type"]["name"] for entry in enemy.get("types", []))
        effectiveness = pokemon_db.effectiveness(move_type, opposing)
        damage = int(damage * effectiveness)
        if effectiveness == 0:
            b["phase"] = f"Tidak mempan! {move_name} tidak bisa mengenai tipe lawan."
            return
        if guarded:
            damage = max(1, int(damage * .45))
            b["phase"] = f"Lawan menangkis {move_name}! −{damage} HP."
        elif effectiveness >= 2:
            b["phase"] = f"Sangat efektif ×{effectiveness:g}! {move_name} −{damage} HP!"
        elif effectiveness <= .5:
            b["phase"] = f"Kurang efektif ×{effectiveness:g}. {move_name} −{damage} HP."
        b["wild_hp"] = max(0, b["wild_hp"] - damage)
        b["enemy_flash"] = .32
        b["super_meter"] = min(100, b.get("super_meter", 0) + 25)
        if b["wild_hp"] <= 0:
            self._win_battle()

    def pokemon_ultimate(self):
        b = self.battle
        if self.needs_depleted():
            if b:
                b["phase"] = "Kebutuhan habis · duel terkunci sampai makan, minum, atau tidur."
            return
        if not b or "wild_hp" not in b or b.get("result"):
            return
        if b.get("super_meter", 0) < 100:
            b["phase"] = f"Ultimate belum penuh · {int(b.get('super_meter', 0))}% (serang untuk mengisi)."
            return
        team, enemy = self.pokemon_data(b["player_id"]), self.pokemon_data(b["wild_id"])
        if not team or not enemy:
            return
        ultimate_move = next((move for move in pokemon_db.loadout(b["player_id"])[2:3]), None)
        types = team.get("types", [])
        move_type = ((ultimate_move or {}).get("type", {}).get("name") or
                     (types[0]["type"]["name"] if types else "normal"))
        ultimate_emoji = TYPE_EMOJI.get(move_type, ULTIMATE_EMOJI.get(move_type, "✨"))
        move_name = ultimate_emoji + " Ultimate " + ((ultimate_move or {}).get("name", "").replace("-", " ").title() or
                                                       TYPE_MOVES.get(move_type, TYPE_MOVES["normal"])[0])
        b["super_meter"] = 0
        b["player_cooldown"] = .9
        b["ultimate_cutin"] = {"timer": .78, "duration": .78, "move_type": move_type,
                                "move_name": move_name, "emoji": ultimate_emoji,
                                "pokemon_id": b["player_id"]}
        b["phase"] = f"ULTIMATE! {move_name}"
        self.play_battle_sound("ultimate_charge", .7)
        self.queue_pokemon_cry(b["player_id"])

    def _resolve_ultimate(self, cutin):
        b = self.battle
        if not b or b.get("result"):
            return
        team, enemy = self.pokemon_data(b["player_id"]), self.pokemon_data(b["wild_id"])
        if not team or not enemy:
            return
        self._set_battle_vfx(cutin["move_type"], cutin["move_name"], ultimate=True,
                             emoji=cutin["emoji"])
        damage = max(30, int(self.base_stat(team, "special-attack", 55) * .95 + self.pokemon_level(b["player_id"]) * 2))
        effectiveness = pokemon_db.effectiveness(cutin["move_type"],
            tuple(item["type"]["name"] for item in enemy.get("types", [])))
        damage = int(damage * effectiveness)
        if effectiveness == 0:
            b["phase"] = f"Ultimate tidak mempan terhadap tipe lawan · ×0."
            return
        if b.get("enemy_guard_timer", 0) > 0:
            damage = int(damage * .72)
        elif effectiveness >= 2:
            b["phase"] = f"Ultimate sangat efektif ×{effectiveness:g}! −{damage} HP!"
        elif effectiveness <= .5:
            b["phase"] = f"Ultimate ditahan ×{effectiveness:g} · −{damage} HP."
        b["wild_hp"] = max(0, b["wild_hp"] - damage)
        b["enemy_flash"] = .55
        if b["wild_hp"] <= 0:
            self._win_battle()

    def _win_battle(self):
        b = self.battle
        if (b.get("ko_anim") or {}).get("owner") != "enemy":
            b["ko_anim"] = {"owner": "enemy", "pokemon_id": int(b["wild_id"]),
                            "timer": 1.0, "duration": 1.0, "next_pokemon": None}
        self.queue_pokemon_cry(b["player_id"])
        trainer = b.get("trainer")
        zone_index = b.get("reserve_zone")
        if trainer is None and zone_index is not None and b.get("wild") is not None and not b.get("wild", {}).get("is_boss") and not b.get("space_progress_recorded"):
            key = str(int(zone_index))
            wins = min(5, int(self.life.reserve_space_wins.get(key, 0)) + 1)
            self.life.reserve_space_wins[key] = wins
            b["space_progress_recorded"] = True
            b["space_battle_wins"] = wins
            threshold = self.reserve_boss_threshold(zone_index)
            b["space_boss_threshold"] = threshold
            if wins >= threshold and zone_index not in self.life.reserve_space_bosses:
                b["space_boss_just_unlocked"] = True
        if (trainer is None and zone_index is not None and (b.get("wild") or {}).get("is_boss")
                and zone_index not in self.life.reserve_space_bosses):
            self.life.reserve_space_bosses.append(int(zone_index))
            b["space_boss_defeated_now"] = True
            if b.get("wild") in self.wild_pokemon:
                self.wild_pokemon.remove(b["wild"])
        lineup = b.get("opponent_lineup", [b["wild_id"]])
        has_next = bool(trainer and b.get("opponent_index", 0) + 1 < len(lineup))
        if not has_next and not b.get("victory_announced"):
            b["victory_announced"] = True
            if not (trainer and trainer.get("rocket_event")):
                self.play_battle_sound("victory", .55)
                self.speak_free_tts("Menang!" if self.life.language == "id" else "Victory!")
        if has_next:
            b["result"] = f"Ronde {b['opponent_index'] + 1}/{len(lineup)} dimenangkan · lawan berikutnya bersiap…"
            effect_time = (b.get("vfx") or {}).get("timer", 0.0)
            b["next_opponent_timer"] = max(1.25, effect_time + .12)
            b["lineup_complete"] = False
        else:
            b["result"] = "Menang! Esc untuk ambil hadiah dan kembali." if trainer else "Menang! O / 2 untuk menangkap · Esc untuk selesai"
            b["lineup_complete"] = True
            if not b.get("victory_cutin_shown"):
                b["victory_cutin_shown"] = True
                if trainer and trainer.get("rocket_event"):
                    b["rocket_defeat_cutin"] = {
                        "timer": 2.35,"duration": 2.35,
                        "image": random.choice(self.rocket_loss_surfaces) if self.rocket_loss_surfaces else None,
                        "sound_played": False,
                    }
                else:
                    b["victory_cutin"] = {"timer": 2.8, "duration": 2.8,
                                           "pokemon_id": int(b["player_id"]),
                                           "trainer_name": getattr(self.life, "trainer_versus_name", "")}
        b["phase"] = "Lawan tumbang!"
        if not b.get("rewarded"):
            leveled, level = self.award_pokemon_xp(b["player_id"], max(12, b.get("wild_level", 5) * 3))
            trainer_leveled, trainer_level = self.award_trainer_xp(max(20, b.get("wild_level", 5) * 5))
            b["rewarded"] = True
            if not b.get("daily_battle_recorded"):
                self.life.record_daily_quest("battle", 1)
                b["daily_battle_recorded"] = True
            if leveled:
                b["phase"] = f"Naik level! {self.pokemon_data(b['player_id'])['name'].title()} sekarang Lv. {level}."
            if trainer_leveled:
                b["phase"] = f"Trainer naik ke Lv.{trainer_level}! XP disimpan untuk evolusi."
            self.save_current()

    def advance_trainer_opponent(self):
        b = self.battle
        if not b:
            return
        index = b.get("opponent_index", 0) + 1
        lineup = b.get("opponent_lineup", [])
        if index >= len(lineup):
            b["next_opponent_timer"] = None
            return
        b["opponent_index"] = index
        b["wild_id"] = int(lineup[index])
        if (b.get("trainer") or {}).get("local_dungeon"):
            b["wild_level"] = int(b.get("dungeon_enemy_levels", [])[index])
            b["dungeon_round_label"] = self.local_dungeon_round_label(
                index, len(lineup))
        else:
            b["wild_level"] = min(100, int((b.get("trainer") or {}).get("level", 20)) + index * 2)
        b.pop("wild_hp", None)
        b.pop("wild_max", None)
        b["result"] = ""
        b["rewarded"] = False
        b["next_opponent_timer"] = None
        b["phase"] = f"Ronde {index + 1}/{len(lineup)} · lawan berikutnya!"
        b["enemy_x"], b["enemy_y"] = 930.0, 0.0
        b["enemy_cooldown"] = 1.4
        b["vfx"] = None
        self.life.pokemon_seen = list(dict.fromkeys(self.life.pokemon_seen + [b["wild_id"]]))
        self.pokedex.request(b["wild_id"])
        self.pokedex.request_animation(b["wild_id"])
        self.pokedex.request_cry(b["wild_id"])
        if self.pokemon_data(b["wild_id"]) and self.pokemon_data(b["player_id"]):
            self.prepare_battle()
        if (b.get("trainer") or {}).get("local_dungeon"):
            b["dungeon_round_label"] = self.local_dungeon_round_label(
                index, len(lineup))
            if index >= len(lineup) - 1:
                b["boss_intro"] = {"timer": 2.6, "duration": 2.6}
            b["phase"] = self.words(f"Lawan berikutnya · {b['dungeon_round_label']}",
                                     f"Next encounter · {b['dungeon_round_label']}")

    def pokemon_catch(self):
        if not self.battle or "wild_hp" not in self.battle:
            return
        if self.battle.get("trainer"):
            self.battle["phase"] = "Tantangan pelatih: kalahkan lawan atau tekan Esc untuk mundur."
            return
        if self.battle.get("capture"):
            return
        if self.battle.get("result") and self.battle["wild_hp"] > 0 and not self.battle.get("timeout"):
            return
        # Low HP improves the odds, while species rarity from the local
        # PokéAPI database makes rare encounters meaningfully harder to catch.
        hp_ratio = self.battle["wild_hp"] / max(1, self.battle["wild_max"])
        base_chance = min(90, 25 + int(65 * (1 - hp_ratio)))
        rarity, rarity_factor = self.capture_rarity(self.battle["wild_id"])
        chance = max(4, min(90, round(base_chance * rarity_factor)))
        if self.life.bag["Pokeball"] <= 0:
            self.battle["phase"] = "Poké Ball habis. Beli di market."
            return
        self.life.bag["Pokeball"] -= 1
        self.battle["capture"] = {
            "phase": "throw", "timer": 0.0, "duration": .72,
            "success": self.pokemon_rng.randrange(100) < chance,
            "start_x": self.battle["player_x"] + 25,
            "target_x": self.battle["enemy_x"],
        }
        self.battle["phase"] = f"Poké Ball dilempar! {rarity} · peluang {chance}%"

    def capture_rarity(self, pokemon_id):
        """Return a display tier and catch chance multiplier for a species."""
        try:
            pokemon_id = int(pokemon_id)
        except (TypeError, ValueError):
            return self.words("Umum", "Common"), 1.0
        wild = self.battle.get("wild") if self.battle else None
        marked_rare = isinstance(wild, dict) and bool(wild.get("rare"))
        species = pokemon_db.species(pokemon_id) or self.pokedex.species.get(pokemon_id, {})
        if species.get("is_mythical"):
            return self.words("Mitos", "Mythical"), .14
        if species.get("is_legendary"):
            return self.words("Legendaris", "Legendary"), .20
        try:
            capture_rate = int(species.get("capture_rate", 255))
        except (TypeError, ValueError):
            capture_rate = 255
        if marked_rare or pokemon_id in RARE_POKEMON_IDS:
            return self.words("Langka", "Rare"), .55
        if capture_rate <= 30:
            return self.words("Epik", "Epic"), .38
        if capture_rate <= 60:
            return self.words("Langka", "Rare"), .58
        if capture_rate <= 120:
            return self.words("Tidak umum", "Uncommon"), .82
        return self.words("Umum", "Common"), 1.0

    def update_capture(self, dt):
        b = self.battle
        capture = b.get("capture")
        if not capture:
            return False
        capture["timer"] += dt
        if capture["timer"] < capture["duration"]:
            return True
        phase = capture["phase"]
        if phase == "throw":
            capture.update(phase="absorb", timer=0.0, duration=.48)
            b["phase"] = "Pokémon tersedot ke dalam Poké Ball!"
        elif phase == "absorb":
            capture.update(phase="shake", timer=0.0, duration=.38, shakes=0)
            b["phase"] = "Bola bergoyang…"
        elif phase == "shake":
            capture["shakes"] += 1
            if capture["shakes"] < 3:
                capture["timer"] = 0.0
            elif capture["success"]:
                capture.update(phase="success", timer=0.0, duration=.72)
                b["phase"] = "Klik! Pokémon berhasil ditangkap!"
            else:
                capture.update(phase="break", timer=0.0, duration=.58)
                b["phase"] = "Oh! Pokémon berhasil keluar dari Poké Ball!"
        elif phase == "success":
            self.play_action_sound("pickup-rare", .42)
            pokemon_id = b["wild_id"]
            newly_registered = pokemon_id not in self.life.pokemon_caught
            self.life.pokemon_caught = list(dict.fromkeys(self.life.pokemon_caught + [pokemon_id]))
            self.life.record_daily_quest("catch", 1)
            collection_rewards = self.life.claim_collection_rewards() if newly_registered else []
            added_to_party = False
            if pokemon_id not in self.life.pokemon_party:
                self.life.pokemon_party.append(pokemon_id)
                added_to_party = True
                if len(self.life.pokemon_active) < 3 and pokemon_id not in self.life.pokemon_active:
                    self.life.pokemon_active.append(pokemon_id)
            self.life.pokemon_levels.setdefault(str(pokemon_id), b.get("wild_level", 5))
            self.life.pokemon_xp.setdefault(str(pokemon_id), 0)
            self.life.pokemon_health[str(pokemon_id)] = max(1, int(b.get("wild_max", 40) * .65))
            if b.get("wild") in self.wild_pokemon:
                self.wild_pokemon.remove(b["wild"])
            self.save_current()
            name = (self.pokemon_data(pokemon_id) or {}).get("name", f"Pokémon #{pokemon_id}").title()
            placement = "Masuk party." if added_to_party else "Tersimpan di koleksi."
            reward_note = " " + " / ".join(f"{badge} +{coins}" for badge, coins in collection_rewards) if collection_rewards else ""
            self.finish_battle(f"Berhasil menangkap {name}! {placement}{reward_note}")
            return True
        elif phase == "break":
            b["capture"] = None
            b["phase"] = "Pokémon lepas dari bola! Tetap bergerak dan coba lagi."
        return True

    def update_battle(self, dt):
        b = self.battle
        if not b or "wild_hp" not in b:
            return
        if b.get("story_caption_timer", 0) > 0:
            b["story_caption_timer"] = max(0.0, b["story_caption_timer"] - dt)
        # Visual effects keep animating even when their hit ends the fight.
        if b.get("vfx"):
            b["vfx"]["timer"] = max(0, b["vfx"]["timer"] - dt)
            if b["vfx"]["timer"] <= 0:
                b["vfx"] = None
        intro = b.get("intro")
        if intro:
            if not self.pokemon_data(b["player_id"]) or not self.pokemon_data(b["wild_id"]):
                return
            sequence = ("player", "enemy", "READY", "3", "2", "1")
            step = intro["step"]
            if step in ("player", "enemy"):
                if not intro.get("cry_requested"):
                    pokemon_id = b["player_id"] if step == "player" else b["wild_id"]
                    intro["cry_requested"] = True
                    if not intro.get("cry_played"):
                        intro["cry_played"] = self.play_pokemon_cry(pokemon_id)
                intro["timer"] -= dt
                if intro["timer"] > 0:
                    return
            else:
                cue = intro["step"]
                sound = self.countdown_tts_sounds.get((self.life.language, cue))
                if not intro.get("cue_started"):
                    if sound is not None and sound.get_length() <= 0:
                        sound = None
                    if sound is None:
                        if self.countdown_tts_loading:
                            return
                        # Fallback on systems without an offline TTS file renderer.
                        phrase = ({"READY": "Siap", "3": "Tiga", "2": "Dua", "1": "Satu"}
                                  if self.life.language == "id" else
                                  {"READY": "Ready", "3": "Three", "2": "Two", "1": "One"})[cue]
                        self.speak_free_tts(phrase)
                        intro["fallback_timer"] = .75
                        intro["cue_started"] = True
                        intro["fallback_cue"] = True
                        return
                    if self.countdown_tts_channel is None:
                        intro.update(cue_started=True, fallback_cue=True, fallback_timer=sound.get_length())
                        return
                    self.countdown_tts_channel.play(sound)
                    intro["cue_started"] = True
                    intro["fallback_cue"] = False
                    return
                if intro.get("fallback_cue"):
                    intro["fallback_timer"] -= dt
                    if intro["fallback_timer"] > 0:
                        return
                elif self.countdown_tts_channel and self.countdown_tts_channel.get_busy():
                    return
            next_index = intro["index"] + 1
            if next_index >= len(sequence):
                b["intro"] = None
                b["phase"] = "MULAI!"
                return
            next_step = sequence[next_index]
            intro.update(step=next_step, index=next_index,
                         timer=1.35 if next_step in ("player", "enemy") else 0.0,
                         cry_requested=False, cry_played=False, cue_started=False)
            return
        boss_intro = b.get("boss_intro")
        if boss_intro:
            boss_intro["timer"] = max(0.0, boss_intro["timer"] - dt)
            if boss_intro["timer"] <= 0:
                b.pop("boss_intro", None)
                b["phase"] = self.words("BOSS MUNCUL! Siapkan strategi terbaikmu.",
                                         "BOSS APPROACHES! Use your best strategy.")
            return
        boss_evolution = b.get("boss_evolution")
        if boss_evolution:
            boss_evolution["timer"] = max(0.0, boss_evolution["timer"] - dt)
            if boss_evolution["timer"] <= 0:
                b.pop("boss_evolution", None)
                b["phase"] = self.words("Boss berevolusi! Fase kedua dimulai.",
                                         "Boss evolved! Phase two begins.")
            return
        rocket_defeat_cutin=b.get("rocket_defeat_cutin")
        if rocket_defeat_cutin:
            previous=rocket_defeat_cutin["timer"]
            rocket_defeat_cutin["timer"]=max(0.0,previous-dt)
            elapsed=rocket_defeat_cutin["duration"]-rocket_defeat_cutin["timer"]
            if elapsed>=1.78 and not rocket_defeat_cutin.get("sound_played"):
                rocket_defeat_cutin["sound_played"]=True
                self.play_action_sound("pickup-rare",.48)
            if rocket_defeat_cutin["timer"]<=0:
                b.pop("rocket_defeat_cutin",None)
                self.play_battle_sound("victory",.55)
                self.speak_free_tts("Menang!" if self.life.language=="id" else "Victory!")
                b["victory_cutin"]={"timer":2.8,"duration":2.8,
                                     "pokemon_id":int(b["player_id"]),
                                     "trainer_name":getattr(self.life,"trainer_versus_name","")}
            return
        rocket_win_cutin=b.get("rocket_win_cutin")
        if rocket_win_cutin:
            rocket_win_cutin["timer"]=max(0.0,rocket_win_cutin["timer"]-dt)
            if rocket_win_cutin["timer"]<=0:
                self.finish_battle(self.words("Team Rocket menang!","Team Rocket won!"))
            return
        victory_cutin = b.get("victory_cutin")
        if victory_cutin:
            victory_cutin["timer"] = max(0.0, victory_cutin["timer"] - dt)
            if victory_cutin["timer"] <= 0:
                b.pop("victory_cutin", None)
            return
        if not b.get("result") and not b.get("capture"):
            b["time_left"] = max(0.0, b.get("time_left", 60.0) - dt)
            if b["time_left"] <= 0:
                b["timeout"] = True
                b["result"] = ("Waktu habis! O untuk mencoba menangkap · Esc untuk melewati duel"
                                if not b.get("trainer") else "Waktu habis! Lawan tidak dapat ditangkap · Esc untuk melewati")
                b["phase"] = "Batas waktu duel tercapai."
                return
        cutin = b.get("ultimate_cutin")
        if cutin:
            cutin["timer"] = max(0, cutin["timer"] - dt)
            if cutin["timer"] <= 0:
                b.pop("ultimate_cutin", None)
                self._resolve_ultimate(cutin)
            return
        if b.get("next_opponent_timer") is not None:
            b["next_opponent_timer"] -= dt
            if b["next_opponent_timer"] <= 0:
                self.advance_trainer_opponent()
            return
        if b.get("capture"):
            self.update_capture(dt)
            return
        if b.get("result"):
            return
        keys = pg.key.get_pressed()
        self.update_fighter_sim(dt, keys)
        # Small arena pickups have distinct tactical effects.
        b["fruit_timer"] -= dt
        if b["fruit_timer"] <= 0 and len(b.get("fruits", [])) < 2:
            fruit_drops = (
                ("health", "🍎"), ("energy", "🍇"), ("skill", "🍓"),
                ("reset", "🥝"), ("speed", "🍌"), ("double", "🍒"),
            )
            kind, emoji = self.pokemon_rng.choice(fruit_drops)
            reachable_ledge = [platform for platform in b.get("platforms", [])
                               if platform.get("height", 0) >= -150]
            if reachable_ledge and self.pokemon_rng.random() < .42:
                ledge = self.pokemon_rng.choice(reachable_ledge)
                drop_x, drop_y = int(ledge["x"]), int(ledge["height"])
            else:
                drop_x, drop_y = self.pokemon_rng.randint(180, 1140), 0
            b.setdefault("fruits", []).append({
                "x": drop_x, "y": drop_y,
                "kind": kind, "emoji": emoji})
            b["fruit_timer"] = self.pokemon_rng.uniform(6, 10)
        remaining_fruits = []
        for fruit in b.get("fruits", []):
            if abs(fruit["x"] - b["player_x"]) < 48 and abs(fruit["y"] - b.get("player_y", 0)) < 50:
                if fruit["kind"] == "health":
                    b["player_hp"] = min(b["player_max"], b["player_hp"] + 16)
                    self.save_battle_player_hp()
                    b["phase"] = f"{fruit['emoji']} Buah pemulih! +16 HP."
                elif fruit["kind"] == "energy":
                    b["super_meter"] = min(100, b.get("super_meter", 0) + 24)
                    b["phase"] = f"{fruit['emoji']} Buah energi! Ultimate +24%."
                elif fruit["kind"] == "skill":
                    b["type_cooldown"] = 0
                    b["special_cooldown"] = 0
                    for key in b.get("cooldowns", {}):
                        b["cooldowns"][key] = max(0, b["cooldowns"][key] - 2.0)
                    b["phase"] = f"{fruit['emoji']} Buah stroberi! Cooldown jurus −2 dtk."
                elif fruit["kind"] == "reset":
                    b["type_cooldown"] = b["special_cooldown"] = 0
                    b["cooldowns"] = {key: 0 for key in b.get("cooldowns", {})}
                    b["phase"] = f"{fruit['emoji']} Buah kiwi! Semua cooldown direset."
                elif fruit["kind"] == "speed":
                    b["fruit_speed_timer"] = 8.0
                    b["phase"] = f"{fruit['emoji']} Pisang kilat! Gerak +35% selama 8 dtk."
                elif fruit["kind"] == "double":
                    b["fruit_double_timer"] = 8.0
                    b["phase"] = f"{fruit['emoji']} Ceri ganda! Damage skill ×2 selama 8 dtk."
            else:
                remaining_fruits.append(fruit)
        b["fruits"] = remaining_fruits

    def load_pokemon_events(self):
        # Decode at most one downloaded image per frame. If several PokéAPI
        # requests finish together, converting every full-size sprite here
        # can freeze the game loop for multiple frames.
        for kind, value in self.pokedex.poll(limit=1):
            if kind == "catalog":
                self.notify(f"Pokédex siap: {len(value)} spesies. Gambar disimpan saat dibuka.")
                if self.life.scene == "reserve" and not self.wild_pokemon:
                    self.spawn_map_pokemon()
                continue
            if kind == "error":
                self.pokedex.requested_items.clear()
                if self.mode in ("battle", "dex", "center"):
                    self.notify(f"PokéAPI: {value['message'][:105]} · coba lagi saat daring.")
                continue
            if kind == "cry":
                if value.get("audio"):
                    try:
                        self.pokemon_sounds[value["id"]] = pg.mixer.Sound(file=BytesIO(value["audio"]))
                    except (pg.error, OSError, ValueError):
                        pass
                sound = self.pokemon_sounds.get(value["id"])
                if sound:
                    sound.set_volume(self.life.cry_volume)
                if sound and self.battle and self.battle.get("queued_cry") == value["id"]:
                    self.battle.pop("queued_cry", None)
                    self.play_pokemon_cry(value["id"])
                if sound and self.mode == "encounter" and self.encounter_target and self.encounter_target["id"] == value["id"]:
                    sound.play()
                if sound and self.mode == "battle" and self.battle and self.battle.get("intro"):
                    intro = self.battle["intro"]
                    expected = self.battle["player_id"] if intro["step"] == "player" else self.battle["wild_id"] if intro["step"] == "enemy" else None
                    if expected == value["id"] and not intro.get("cry_played"):
                        sound.play()
                        intro["cry_played"] = True
                continue
            if kind == "item":
                if value.get("image"):
                    try:
                        image = pg.image.load(BytesIO(value["image"])).convert_alpha()
                        self.pokeball_surface = pg.transform.scale(image, (48, 48))
                    except (pg.error, ValueError):
                        self.pokeball_surface = None
                continue
            if kind == "move":
                continue
            if kind == "animation":
                if value.get("image"):
                    try:
                        frames = []
                        with Image.open(BytesIO(value["image"])) as gif:
                            count = max(1, int(getattr(gif, "n_frames", 1)))
                            step = max(1, count // 12)
                            for frame_index in range(0, count, step):
                                gif.seek(frame_index)
                                source = gif.convert("RGBA")
                                ratio = min(136 / max(1, source.width), 136 / max(1, source.height))
                                size = (max(1, int(source.width * ratio)), max(1, int(source.height * ratio)))
                                source = source.resize(size, Image.Resampling.NEAREST)
                                raw = source.tobytes()
                                surface = pg.image.frombytes(raw, size, "RGBA").convert_alpha()
                                frames.append((surface, max(40, int(gif.info.get("duration", 100)))))
                        if frames:
                            self.poke_animations[value["id"]] = frames
                    except (OSError, ValueError, pg.error):
                        pass
                continue
            if kind in ("species", "evolution"):
                if kind == "species":
                    url = value["data"].get("evolution_chain", {}).get("url", "")
                    try:
                        chain_id = int(url.rstrip("/").split("/")[-1])
                        self.pokedex.request_evolution(chain_id)
                    except (ValueError, AttributeError):
                        pass
                continue
            ident = value["id"]
            if value["image"]:
                try:
                    image = pg.image.load(BytesIO(value["image"])).convert_alpha()
                    self.poke_surfaces[ident] = self.fit_pokemon_sprite(image, 96)
                    self.poke_battle_surfaces[ident] = self.fit_pokemon_sprite(image, 136)
                    for key in [key for key in self.pokemon_render_cache if key[0] == ident]:
                        del self.pokemon_render_cache[key]
                except (pg.error, ValueError):
                    pass
            detail = value["detail"]
            if self.mode == "dex" and ident == self.dex_selected:
                self.dex_detail = detail
            if self.mode == "battle" and self.battle:
                wild_id, player_id = self.battle["wild_id"], self.battle["player_id"]
                if wild_id in self.pokedex.details and player_id in self.pokedex.details:
                    self.prepare_battle()

    @staticmethod
    def fit_pokemon_sprite(surface, target_size):
        scale = target_size / max(1, surface.get_width(), surface.get_height())
        size = (max(1, round(surface.get_width() * scale)), max(1, round(surface.get_height() * scale)))
        return pg.transform.scale(surface, size)

    def pokemon_surface(self, pokemon_id, target_size=96):
        ident = int(pokemon_id)
        frames = self.poke_animations.get(ident)
        frame_index = -1
        source = None
        if frames:
            total = sum(duration for _, duration in frames)
            tick = int((self.frame / 60 * 1000) % max(1, total))
            for index, (surface, duration) in enumerate(frames):
                if tick < duration:
                    source = surface
                    frame_index = index
                    break
                tick -= duration
        if source is None:
            source = self.poke_surfaces.get(ident) if target_size <= 100 else self.poke_battle_surfaces.get(ident, self.poke_surfaces.get(ident))
        # Some PokéAPI alternate forms have no dedicated sprite. Use the
        # canonical species artwork while the form sprite is loading or when
        # the upstream form endpoint has no image, instead of drawing nothing.
        if source is None:
            detail = self.pokemon_data(ident) or {}
            species_url = detail.get("species", {}).get("url", "")
            try:
                species_id = int(species_url.rstrip("/").split("/")[-1])
            except (AttributeError, TypeError, ValueError):
                species_id = ident
            if species_id != ident:
                self.pokedex.request(species_id)
                source = (self.poke_surfaces.get(species_id) if target_size <= 100 else
                          self.poke_battle_surfaces.get(species_id, self.poke_surfaces.get(species_id)))
        if source is None:
            return None
        key = (ident, int(target_size), frame_index)
        cached = self.pokemon_render_cache.get(key)
        if cached is not None:
            return cached
        surface = source
        if max(surface.get_width(), surface.get_height()) != target_size:
            surface = self.fit_pokemon_sprite(surface, target_size)
        else:
            surface = surface.copy()
        retro.pixelate(surface, 2)
        self.pokemon_render_cache[key] = surface
        if len(self.pokemon_render_cache) > 160:
            self.pokemon_render_cache.pop(next(iter(self.pokemon_render_cache)))
        return surface

    def trainer_versus_surface(self, name=None, bounds=(500, 300)):
        """Return an aspect-fit cached trainer portrait for the requested box."""
        portraits = getattr(self, "trainer_versus_sprites", ())
        if not portraits:
            return None
        entry = next((item for item in portraits if item["name"] == name), portraits[0])
        source = entry["image"]
        width, height = max(1, int(bounds[0])), max(1, int(bounds[1]))
        key = (entry["name"], width, height)
        cache = self.trainer_versus_surface_cache
        if key not in cache:
            scale = min(width / source.get_width(), height / source.get_height())
            size = (max(1, round(source.get_width() * scale)),
                    max(1, round(source.get_height() * scale)))
            cache[key] = pg.transform.smoothscale(source, size)
        return cache[key]

    def prepare_battle(self):
        if not self.battle:
            return
        enemy = self.pokemon_data(self.battle["wild_id"])
        team = self.pokemon_data(self.battle["player_id"])
        if not enemy or not team:
            return
        b = self.battle
        # Scale opposing stats by one quarter of the player's current Pokémon.
        # Recalculate on switches and trainer rounds so the match stays fair.
        stat_defaults = {"hp": 45, "attack": 49, "defense": 49,
                         "special-attack": 55, "special-defense": 55, "speed": 70}
        condition = b.get("trainer_condition", 1.0)
        trainer = b.get("trainer") or {}
        dungeon = bool(trainer.get("local_dungeon"))
        lineup = b.get("opponent_lineup", [b.get("wild_id")])
        is_boss = ((dungeon and b.get("opponent_index", 0) >= len(lineup) - 1)
                   or bool((b.get("wild") or {}).get("is_boss")))
        tier = max(1, int(b.get("dungeon_tier", trainer.get("dungeon_tier", 1)))) if dungeon else 0
        # Dungeon enemies gain a tier-based stat boost; the final foe gets a
        # distinct boss multiplier so the encounter feels like a real climax.
        stat_scale = min(1.55, 1.22 + tier * .025) if dungeon else 1.0
        if is_boss:
            stat_scale = min(1.95, 1.58 + tier * .035)
        b["dungeon_stat_multiplier"] = stat_scale
        b["enemy_stat_multiplier"] = stat_scale
        b["dungeon_is_boss"] = is_boss
        b["enemy_stat_bonus"] = {
            name: max(1, round(self.base_stat(team, name, default) * condition * .25))
            for name, default in stat_defaults.items()
        }
        raw_wild_max = (self.base_stat(enemy, "hp", 45) + b["enemy_stat_bonus"]["hp"]
                        + int(b.get("wild_level", 5) * 2.2))
        hp_scale = min(1.55, 1.18 + tier * .037) if dungeon else 1.0
        if is_boss and dungeon:
            hp_scale = min(2.0, 1.55 + tier * .045)
        elif is_boss:
            hp_scale = 1.6
        b["wild_max"] = max(10, round(raw_wild_max * hp_scale))
        b.setdefault("wild_hp", b["wild_max"])
        b["wild_hp"] = min(b["wild_hp"], b["wild_max"])
        player_id = str(b["player_id"])
        b["raw_player_max"] = max(10, self.base_stat(team, "hp", 45) + self.pokemon_level(int(player_id)) * 2)
        old_max = b.get("player_max")
        if old_max and "player_hp" in b:
            saved_ratio = b["player_hp"] / old_max
        else:
            saved_ratio = self.life.pokemon_health.get(player_id, b["raw_player_max"]) / b["raw_player_max"]
        b["player_max"] = max(10, round(b["raw_player_max"] * condition))
        b["player_hp"] = max(0, min(b["player_max"], round(b["player_max"] * saved_ratio)))
        b["phase"] = "Hadapi lawan! Bergerak, pukul, dan blok serangannya."
        b["api_moves"] = [entry["move"]["name"] for entry in team.get("moves", [])[:2]]
        for move_name in b["api_moves"]:
            self.pokedex.request_move(move_name)
        self.battle_sprite = self.poke_surfaces.get(self.battle["wild_id"])
        self.team_sprite = self.poke_surfaces.get(self.battle["player_id"])
        self.pokedex.request_animation(b["wild_id"])
        self.pokedex.request_animation(b["player_id"])

    def switch_battle_pokemon(self, next_id, automatic=False):
        b = self.battle
        if not b:
            return False
        next_id = int(next_id)
        if next_id not in self.active_pokemon_team() or self.life.pokemon_health.get(str(next_id), 1) <= 0:
            return False
        b["player_id"] = next_id
        b.pop("player_appearance", None)
        b["player_lineup"] = self.active_pokemon_team()
        b.pop("player_hp", None)
        b.pop("player_max", None)
        b["player_cooldown"] = .8 if automatic else .45
        b["player_x"], b["player_y"] = 350.0, 0.0
        b["phase"] = ("Pokémon berikutnya maju otomatis!" if automatic else "Pokémon aktif diganti.")
        self.pokedex.request(next_id)
        self.pokedex.request_animation(next_id)
        self.pokedex.request_cry(next_id)
        if self.pokemon_data(next_id) and self.pokemon_data(b["wild_id"]):
            self.prepare_battle()
        return True

    def change_battle_pokemon(self):
        if not self.battle or self.battle.get("result"):
            return
        lineup = self.active_pokemon_team()
        available = [ident for ident in lineup if ident != self.battle["player_id"] and self.life.pokemon_health.get(str(ident), 1) > 0]
        if not available:
            self.notify("Tidak ada Pokémon aktif lain yang masih punya HP.")
            return
        current = self.battle["player_id"]
        order = lineup.index(current) if current in lineup else -1
        next_id = next((lineup[(order + offset) % len(lineup)] for offset in range(1, len(lineup) + 1)
                        if lineup[(order + offset) % len(lineup)] in available), available[0])
        self.switch_battle_pokemon(next_id)

    def submit_phone_prompt(self):
        prompt = self.phone_input.strip()
        if not prompt:
            return
        if self.phone_terminal.phone_marker:
            self.phone_status = "Tunggu respons sebelumnya selesai sebelum mengirim prompt baru."
            self.notify(self.phone_status)
            return
        command = prompt[1:].strip() if prompt.startswith("!") else "opencode run " + shlex.quote(prompt)
        self.phone_complete = False
        status = self.phone_terminal.run_from_phone(command)
        self.phone_input = ""
        self.phone_status = status
        self.notify(status)

    def open_phone(self):
        self.play_action_sound("menu-open", .24)
        self.phone_unread = False
        self.terminal.start()
        self.mode = "terminal"
        pg.key.start_text_input()
        pg.key.set_repeat(350, 35)

    def open_dex(self):
        self.play_action_sound("inventory-open", .24)
        self.dex_query = ""
        self.dex_page = 0
        self.dex_selected = 1
        self.dex_detail = self.pokemon_data(1)
        self.pokedex.request_catalog()
        self.pokedex.request(1)
        self.pokedex.request_species(1)
        self.mode = "dex"
        pg.key.start_text_input()
        pg.key.set_repeat(350, 35)

    def open_inventory(self):
        self.play_action_sound("inventory-open", .24)
        self.mode = "inventory"

    def open_pokemon_center(self):
        if self.life.scene != "reserve" or math.hypot(self.life.x - 160, self.life.y - 690) > 115:
            self.notify("Pusat Pokémon berada di bangunan putih-merah dekat pintu masuk suaka.")
            return
        self.center_selected = max(0, min(self.center_selected, len(self.life.pokemon_party) - 1))
        self.play_action_sound("menu-open", .24)
        self.center_message = "Pemeriksaan siap. Pilih anggota tim di kiri."
        for pokemon_id in self.life.pokemon_party:
            self.pokedex.request(pokemon_id)
            self.pokedex.request_species(pokemon_id)
        self.mode = "center"

    def center_pokemon_id(self):
        if not self.life.pokemon_party:
            return None
        self.center_selected %= len(self.life.pokemon_party)
        pokemon_id = int(self.life.pokemon_party[self.center_selected])
        if (self.center_type_filter != "all" and self.center_type_filter not in
                pokemon_db.type_catalog().get(pokemon_id, ())):
            return None
        return pokemon_id

    def center_filtered_party(self):
        types_by_id = pokemon_db.type_catalog()
        return [(index, int(ident)) for index, ident in enumerate(self.life.pokemon_party[:6])
                if self.center_type_filter == "all" or
                self.center_type_filter in types_by_id.get(int(ident), ())]

    def move_center_selection(self, offset):
        visible = self.center_filtered_party()
        if not visible:
            return
        positions = [index for index, _ in visible]
        try:current = positions.index(self.center_selected)
        except ValueError:current = 0
        self.center_selected = positions[max(0, min(len(positions) - 1, current + offset))]

    def toggle_active_pokemon(self):
        pokemon_id = self.center_pokemon_id()
        if pokemon_id is None:
            return
        active = self.life.pokemon_active
        if pokemon_id in active:
            if len(active) <= 1:
                self.center_message = "Sisakan minimal satu Pokémon aktif."
                return
            active.remove(pokemon_id)
            self.center_message = "Pokémon dikeluarkan dari tim aktif."
        elif len(active) >= 3:
            self.center_message = "Maksimal tiga Pokémon aktif. Keluarkan satu anggota dahulu."
            return
        else:
            active.append(pokemon_id)
            self.center_message = "Pokémon ditambahkan ke tim aktif."
        self.save_current()

    def heal_pokemon_party(self):
        for pokemon_id in self.life.pokemon_party:
            detail = self.pokemon_data(pokemon_id)
            if not detail:
                self.pokedex.request(pokemon_id)
                self.life.pokemon_health[str(pokemon_id)] = 10000
                continue
            maximum = self.base_stat(detail, "hp", 45) + self.pokemon_level(pokemon_id) * 2
            self.life.pokemon_health[str(pokemon_id)] = maximum
        self.save_current()
        self.center_message = "Tim dipulihkan penuh. Semangat, pelatih!"
        self.play_action_sound("pickup-rare", .3)

    def evolution_option(self, pokemon_id):
        species = self.pokedex.species.get(int(pokemon_id))
        if not species:
            self.pokedex.request_species(pokemon_id)
            return None
        chain_url = species.get("evolution_chain", {}).get("url", "")
        try:
            chain_id = int(chain_url.rstrip("/").split("/")[-1])
        except (ValueError, AttributeError):
            return None
        chain = self.pokedex.evolution.get(chain_id)
        if not chain:
            self.pokedex.request_evolution(chain_id)
            return None
        current_level = self.pokemon_level(pokemon_id)

        def walk(link):
            url = link.get("species", {}).get("url", "")
            try:
                current_id = int(url.rstrip("/").split("/")[-1])
            except (ValueError, AttributeError):
                current_id = -1
            if current_id == int(pokemon_id):
                for child in link.get("evolves_to", []):
                    details = child.get("evolution_details", [])
                    for condition in details:
                        trigger = condition.get("trigger", {}).get("name", "")
                        required = condition.get("min_level") or 16
                        simple_level_up = (trigger == "level-up" and condition.get("min_level")
                                           and set(condition).issubset({"trigger", "min_level"}))
                        if simple_level_up:
                            child_url = child.get("species", {}).get("url", "")
                            try:
                                return (int(child_url.rstrip("/").split("/")[-1]),
                                        child["species"]["name"], int(required))
                            except (ValueError, KeyError, AttributeError):
                                pass
                return None
            for child in link.get("evolves_to", []):
                result = walk(child)
                if result:
                    return result
            return None
        return walk(chain.get("chain", {}))

    def evolution_chain_lines(self, pokemon_id, max_chars=58):
        """Format every branch of a species' official evolution chain."""
        ident = int(pokemon_id)
        species = self.pokedex.species.get(ident) or pokemon_db.species(ident)
        if not species:
            self.pokedex.request_species(ident)
            return None
        chain_url = species.get("evolution_chain", {}).get("url", "")
        try:
            chain_id = int(chain_url.rstrip("/").split("/")[-1])
        except (ValueError, AttributeError):
            return []
        chain_data = self.pokedex.evolution.get(chain_id)
        if not chain_data:
            self.pokedex.request_evolution(chain_id)
            return None

        def name_and_id(node):
            data = node.get("species", {})
            name = data.get("name", "Pokémon").replace("-", " ").title()
            try:
                node_id = int(data.get("url", "").rstrip("/").split("/")[-1])
            except (ValueError, AttributeError):
                node_id = -1
            return name, node_id

        def requirement(child):
            details = child.get("evolution_details", [])
            if not details:
                return self.words("syarat khusus", "special condition")
            detail = details[0]
            if detail.get("min_level"):
                return f"Lv.{detail['min_level']}"
            if detail.get("item"):
                item = detail["item"].get("name", "item").replace("item-", "item #")
                return item.replace("-", " ").title()
            if detail.get("held_item"):
                item = detail["held_item"].get("name", "item").replace("item-", "item #")
                return self.words(f"pegang {item}", f"hold {item}")
            if detail.get("trigger", {}).get("name") == "trade":
                return self.words("ditukar", "trade")
            if detail.get("min_happiness") or detail.get("min_affection"):
                return self.words("persahabatan tinggi", "high friendship")
            if detail.get("known_move"):
                return self.words(f"kuasai {detail['known_move']['name'].replace('-', ' ').title()}",
                                  f"know {detail['known_move']['name'].replace('-', ' ').title()}")
            if detail.get("time_of_day"):
                return detail["time_of_day"].title()
            trigger = detail.get("trigger", {}).get("name", "")
            return trigger.replace("-", " ").title() or self.words("syarat khusus", "special condition")

        links = []

        def walk(node):
            parent_name, parent_id = name_and_id(node)
            children = node.get("evolves_to", [])
            if children:
                child_labels = []
                for child in children:
                    child_name, child_id = name_and_id(child)
                    marker = "*" if child_id == ident else ""
                    child_labels.append(f"{marker}{child_name} ({requirement(child)})")
                marker = "*" if parent_id == ident else ""
                links.append(f"{marker}{parent_name} → " + " / ".join(child_labels))
                for child in children:
                    walk(child)

        walk(chain_data.get("chain", {}))
        lines = []
        for link in links:
            words = link.split()
            line = ""
            for word in words:
                if line and len(line) + len(word) + 1 > max_chars:
                    lines.append(line)
                    line = ""
                line = (line + " " + word).strip()
            if line:
                lines.append(line)
        return lines

    def evolution_chain_paths(self, pokemon_id):
        """Return evolution paths as species IDs/names and the edge condition."""
        ident = int(pokemon_id)
        species = self.pokedex.species.get(ident) or pokemon_db.species(ident)
        if not species:
            self.pokedex.request_species(ident)
            return None
        chain_url = species.get("evolution_chain", {}).get("url", "")
        try:
            chain_id = int(chain_url.rstrip("/").split("/")[-1])
        except (ValueError, AttributeError):
            return []
        chain_data = self.pokedex.evolution.get(chain_id)
        if not chain_data:
            self.pokedex.request_evolution(chain_id)
            return None

        def species_entry(node):
            item = node.get("species", {})
            try:
                species_id = int(item.get("url", "").rstrip("/").split("/")[-1])
            except (ValueError, AttributeError):
                species_id = -1
            name = item.get("name", "Pokémon").replace("-", " ").title()
            return species_id, name

        def condition(child):
            detail = next(iter(child.get("evolution_details", [])), {})
            if detail.get("min_level"):
                return f"Lv.{detail['min_level']}"
            if detail.get("item"):
                return detail["item"].get("name", "item").replace("-", " ").title()
            if detail.get("trigger", {}).get("name") == "trade":
                return self.words("Tukar", "Trade")
            if detail.get("min_happiness") or detail.get("min_affection"):
                return self.words("Persahabatan", "Friendship")
            return self.words("Syarat khusus", "Special")

        paths = []

        def walk(node, path, incoming=""):
            entry = (*species_entry(node), incoming)
            current = path + [entry]
            children = node.get("evolves_to", [])
            if not children:
                paths.append(current)
                return
            for child in children:
                walk(child, current, condition(child))

        walk(chain_data.get("chain", {}), [])
        for path in paths:
            for species_id, _, _ in path:
                if species_id > 0:
                    self.pokedex.request(species_id)
        return paths

    def draw_evolution_chain(self, pokemon_id, x, y, width, height, max_rows=2,
                             icon_size=40, font=None):
        """Draw on-demand Pokémon sprites and labels for each evolution path."""
        paths = self.evolution_chain_paths(pokemon_id)
        font = font or self.tiny
        if paths is None:
            self.text(self.words("Memuat rantai evolusi…", "Loading evolution chain…"),
                      x, y + 4, MUTED, font)
            return
        if not paths or (len(paths) == 1 and len(paths[0]) == 1):
            self.text(self.words("Tidak berevolusi", "Does not evolve"), x, y + 4, MUTED, font)
            return

        row_height = max(1, height // max_rows)
        shown = paths[:max_rows]
        for row, path in enumerate(shown):
            top = y + row * row_height
            count = len(path)
            slot = width / max(1, count)
            size = min(icon_size, max(22, int(row_height * .56)))
            for index, (species_id, name, edge_condition) in enumerate(path):
                center_x = int(x + slot * (index + .5))
                sprite = self.pokemon_surface(species_id, size) if species_id > 0 else None
                if sprite:
                    self.canvas.blit(sprite, sprite.get_rect(center=(center_x, top + size // 2 + 1)))
                else:
                    self.box((center_x-size//2, top+2, size, size), (29, 43, 67), 3)
                    self.text("…", center_x, top+size//2-5, MUTED, font, True)
                label = name if len(name) <= 13 else name[:12] + "…"
                self.text(label, center_x, top + size + 3, CREAM, font, True)
                if index > 0:
                    self.text("›", int(x + slot * index), top + size // 2 - 5, retro.GOLD, font, True)
                    if edge_condition:
                        self.text(edge_condition[:12], center_x, top + size + 17, GREEN, font, True)
        if len(paths) > max_rows:
            self.text(f"+{len(paths)-max_rows} {self.words('cabang','branches')}",
                      x + width - 4, y + height - 14, retro.GOLD, font, True)

    def evolution_target(self, pokemon_id):
        option = self.evolution_option(pokemon_id)
        return option[:2] if option and self.pokemon_level(pokemon_id) >= option[2] else None

    def evolution_xp_cost(self, pokemon_id):
        option = self.evolution_option(pokemon_id)
        return max(40, option[2] * 4) if option else 0

    def evolve_selected(self):
        if self.evolution_anim:
            return
        pokemon_id = self.center_pokemon_id()
        if pokemon_id is None:
            return
        target = self.evolution_target(pokemon_id)
        if not target:
            detail = self.pokemon_data(pokemon_id) or {"name": "Pokémon"}
            self.center_message = f"{detail.get('name', 'Pokémon').title()} belum memenuhi syarat evolusi."
            return
        new_id, name = target
        old_detail = self.pokemon_data(pokemon_id) or {"name": f"Pokémon #{pokemon_id}"}
        self.evolution_anim = {"from": pokemon_id, "to": new_id, "name": name,
                               "old_name": old_detail.get("name", "Pokémon"), "timer": 0.0, "duration": 4.8}
        self.pokedex.request(new_id)
        self.pokedex.request_species(new_id)
        self.mode = "evolution"
        self.center_message = "Cahaya evolusi menyelimuti Pokémon…"

    def finish_evolution(self):
        animation = self.evolution_anim
        if not animation:
            return
        pokemon_id, new_id, name = animation["from"], animation["to"], animation["name"]
        # Evolution adds the new species to the collection and keeps the
        # original species owned. If the original was active, swap only its
        # active slot to the evolved form.
        self.life.pokemon_party = list(dict.fromkeys(self.life.pokemon_party + [new_id]))
        if pokemon_id in self.life.pokemon_active:
            old_slot = self.life.pokemon_active.index(pokemon_id)
            if new_id in self.life.pokemon_active:
                self.life.pokemon_active.remove(pokemon_id)
            else:
                self.life.pokemon_active[old_slot] = new_id
        self.life.pokemon_active = list(dict.fromkeys(self.life.pokemon_active))[:3]
        self.life.pokemon_caught = list(dict.fromkeys(self.life.pokemon_caught + [new_id]))
        self.life.pokemon_seen = list(dict.fromkeys(self.life.pokemon_seen + [new_id]))
        self.life.pokemon_levels.setdefault(str(new_id), self.pokemon_level(pokemon_id))
        self.life.pokemon_xp.setdefault(str(new_id), self.life.pokemon_xp.get(str(pokemon_id), 0))
        old_detail = self.pokemon_data(pokemon_id) or {}
        old_max = self.base_stat(old_detail, "hp", 45) + self.pokemon_level(pokemon_id) * 2
        new_detail = self.pokemon_data(new_id) or {}
        new_max = self.base_stat(new_detail, "hp", 45) + self.pokemon_level(new_id) * 2
        carried_hp = self.life.pokemon_health.get(str(pokemon_id), old_max)
        carried_hp = round(new_max * max(0, min(1, carried_hp / max(1, old_max))))
        self.life.pokemon_health.setdefault(str(new_id), max(1, carried_hp))
        self.save_current()
        self.center_selected = self.life.pokemon_party.index(new_id)
        self.evolution_anim = None
        self.mode = "center"
        self.play_action_sound("jingle-level-up", .4)
        self.center_message = f"Berhasil berevolusi menjadi {name.title()}!"

    def update_evolution(self, dt):
        if not self.evolution_anim:
            return
        self.evolution_anim["timer"] += min(dt, .05)
        if self.evolution_anim["timer"] >= self.evolution_anim["duration"]:
            self.finish_evolution()

    def outdoors(self):
        self.art.outdoors(self.canvas, self.life, self.frame)
        for title, x, y in [("RUMAH", 350, 363), ("PETERNAKAN", 933, 426),
                            ("KEBUN", 656, 575), ("KOLAM", 1110, 673), ("TAMAN", 300, 644),
                            ("PORTAL SUAKA · POKÉMON", 160, 576)]:
            self.label(title, x, y)

    def draw_dungeon_hub(self):
        art = self.art.scenery
        backdrop = getattr(self, "_dungeon_hub_backdrop", None)
        if backdrop is None:
            backdrop = pg.Surface((W, H)).convert()
            art.ground(backdrop, "crystal")
            art.path(backdrop, (75, 350, 1130, 195), "crystal")
            art.path(backdrop, (575, 220, 130, 310), "crystal")
            art.walls(backdrop, scene_layout("dungeon_hub")["walls"], "crystal")
            for prop in scene_layout("dungeon_hub")["props"]:
                art.prop(backdrop, prop, "crystal")
            art.gate(backdrop, 150, 435, "west", "crystal")
            art.gate(backdrop, 1130, 435, "east", "cave")
            art.gate(backdrop, 640, 625, "south", "crystal")
            pg.draw.ellipse(backdrop, (35, 38, 57), (88, 380, 125, 110))
            pg.draw.ellipse(backdrop, (53, 186, 204), (101, 389, 98, 91), 7)
            pg.draw.ellipse(backdrop, (25, 28, 42), (1065, 378, 130, 115))
            pg.draw.arc(backdrop, (121, 117, 139), (1060, 365, 140, 135), 0, math.pi, 12)
            pg.draw.ellipse(backdrop, (15, 18, 30), (1080, 399, 100, 85))
            for point in ((1120, 413), (1145, 402), (1160, 424)):
                art.rock(backdrop, *point, "cave", 22)
            self._dungeon_hub_backdrop = backdrop
        self.canvas.blit(backdrop, (0, 0))
        self.label(self.words("HUB UTARA · PERSIMPANGAN PETUALANG", "NORTH HUB · ADVENTURER CROSSROADS"), 640, 158)
        self.label(self.words("GYM ONLINE · KIRI", "ONLINE GYM · LEFT"), 150, 330)
        self.label(self.words("DUNGEON LOKAL · KANAN", "LOCAL DUNGEON · RIGHT"), 1130, 330)
        self.label(self.local_dungeon_status(), 885, 513)
        self.label(self.words("KEMBALI KE RUMAH", "RETURN HOME"), 640, 573)

    def draw_local_dungeon(self):
        tier = max(1, min(10, int(self.life.local_dungeon_tier)))
        biome = DUNGEON_BIOMES[tier - 1]
        art = self.art.scenery
        cached = getattr(self, "_local_dungeon_backdrop", None)
        if not cached or cached[0] != tier:
            backdrop = pg.Surface((W, H)).convert()
            art.ground(backdrop, biome)
            art.path(backdrop, (260, 350, 760, 205), biome)
            art.path(backdrop, (575, 210, 130, 265), biome)
            art.walls(backdrop, scene_layout("local_dungeon")["walls"], biome)
            for prop in scene_layout("local_dungeon")["props"]:
                if prop[0] == "crystal" and biome not in ("crystal", "volcano", "legendary_ruins"):
                    prop = ("rock", prop[1], prop[2], prop[3])
                art.prop(backdrop, prop, biome)
            art.gate(backdrop, 640, 275, "north", biome)
            art.gate(backdrop, 640, 625, "south", biome)
            if biome in ("coast", "swamp", "deepsea"):
                art.pool(backdrop, (865, 425, 215, 95), biome, "water")
                art.pool(backdrop, (200, 455, 125, 75), biome, "water")
            elif biome == "volcano":
                art.pool(backdrop, (865, 425, 215, 95), biome, "lava")
                art.pool(backdrop, (200, 455, 125, 75), biome, "lava")
            elif biome == "snow":
                art.pool(backdrop, (865, 425, 215, 95), biome, "ice")
            elif biome in ("forest", "dragon_valley"):
                for x, y, variant in ((410, 360, 0), (870, 365, 1), (430, 574, 2), (860, 572, 0)):
                    art.prop(backdrop, ("tree", x, y, variant), biome)
            self._local_dungeon_backdrop = (tier, backdrop)
        self.canvas.blit(self._local_dungeon_backdrop[1], (0, 0))
        name = self.local_dungeon_name(tier)
        level = self.local_dungeon_level(tier)
        self.label(self.words(f"{name.upper()} · TINGKAT {tier}/10", f"{name.upper()} · DUNGEON {tier}/10"), 640, 158)
        self.label(self.words(f"MUSUH Lv.{level - 4}–{level} · 1 / 2 / 3 · BOSS", f"FOES Lv.{level - 4}–{level} · 1 / 2 / 3 · BOSS"), 640, 478)
        self.label(self.words(f"MULAI DUNGEON · Lv.{level} · E", f"ENTER DUNGEON · Lv.{level} · E"), 640, 218)
        self.label(self.words("KEMBALI KE HUB", "RETURN TO HUB"), 640, 574)

    def forest(self):
        self.art.forest(self.canvas)
        self.label("HUTAN LIAR", 630, 159)
        self.label("RANTING / KAYU", 645, 559)
        self.label("RUMAH >", 1180, 456)

    def market(self):
        self.art.market(self.canvas)
        self.label("MARKET · 06:00–22:00", 632, 161)
        self.label("< RUMAH", 105, 455)
        for name, x, y, _, role in self.npcs():
            self.label(name + " · " + role, x, y + 55)

    def house(self):
        self.art.house(self.canvas)
        self.draw_home_furnishings()
        for title, x, y in [("RUMAH / RUANG KELUARGA", 640, 167), ("AIR", 248, 294),
                            ("DAPUR", 361, 294), ("MEJA MAKAN", 625, 577), ("SOFA", 919, 503),
                            ("KAMAR", 1015, 273), ("DEKORASI · E", 680, 265), ("E · KELUAR", 640, 679)]:
            self.label(title, x, y)

    def draw_home_furnishings(self):
        """Draw the saved home collection as small pixel-art furniture accents."""
        decor = getattr(self.life, "home_decor", {}) or {}
        wall = decor.get("wall", "")
        if wall:
            pg.draw.rect(self.canvas, (83, 57, 42), (592, 204, 73, 52))
            pg.draw.rect(self.canvas, (220, 196, 145), (597, 209, 63, 42))
            pg.draw.rect(self.canvas, (55, 70, 82), (601, 213, 55, 34))
            if wall == "wall_photo":
                pg.draw.rect(self.canvas, (246, 174, 88), (603, 215, 51, 17))
                pg.draw.rect(self.canvas, (63, 125, 102), (603, 232, 51, 13))
                pg.draw.circle(self.canvas, (255, 223, 119), (644, 221), 6)
                pg.draw.polygon(self.canvas, (27, 70, 65), [(603, 240), (620, 226), (636, 240), (648, 230), (655, 240)])
            elif wall == "route_map":
                for points in (((607, 219), (619, 225), (629, 218), (646, 230)),
                               ((609, 239), (621, 232), (638, 237), (650, 222))):
                    pg.draw.lines(self.canvas, (151, 208, 129), False, points, 2)
                for point in ((619, 225), (638, 237), (650, 222)):
                    pg.draw.rect(self.canvas, retro.GOLD, (*point, 4, 4))
            elif wall == "badge_wall":
                # A compact, live collection display: earned story badges,
                # high-stat owned Pokémon, and cleared local dungeons.
                frame = pg.Rect(548, 193, 184, 118)
                pg.draw.rect(self.canvas, (83, 57, 42), frame)
                pg.draw.rect(self.canvas, (220, 196, 145), frame.inflate(-8, -8))
                pg.draw.rect(self.canvas, (31, 43, 60), frame.inflate(-14, -14))
                self.text(self.words("PAPAN KOLEKSI", "COLLECTION BOARD"), 640, 207,
                          retro.GOLD, self.tiny, True)
                badges = list(self.life.badges)[-3:]
                for index, badge_name in enumerate(badges):
                    x = 570 + index * 27
                    pg.draw.circle(self.canvas, retro.GOLD, (x, 233), 8)
                    pg.draw.circle(self.canvas, (69, 85, 101), (x, 233), 4)
                self.text(f"{self.words('LENCANA', 'BADGES')} {len(self.life.badges)}", 618, 251,
                          CREAM, self.tiny, True)

                caught = list(dict.fromkeys(int(v) for v in self.life.pokemon_caught))
                rare_ids = [ident for ident in caught if ident in RARE_POKEMON_IDS][:3]
                # Request only owned legendary/mythical sprites for this display.
                for ident in rare_ids:
                    if ident not in self.home_board_requested:
                        self.home_board_requested.add(ident)
                        self.pokedex.request(ident)
                for index, ident in enumerate(rare_ids):
                    sprite = self.pokemon_surface(ident, 24)
                    if sprite:
                        self.canvas.blit(sprite, sprite.get_rect(center=(601 + index * 31, 276)))
                rare_caption = (self.words("POKÉMON LANGKA", "RARE POKÉMON") if rare_ids else
                                self.words("BELUM LANGKA", "NO RARE YET"))
                self.text(rare_caption, 640, 290, CREAM, self.tiny, True)
                cleared = sorted(set(int(v) for v in self.life.local_dungeon_cleared))
                trophy_count = min(5, len(cleared))
                for index in range(trophy_count):
                    x = 681 + index * 10
                    color = (retro.GOLD, (207, 220, 236), (210, 137, 88), (131, 212, 172), (197, 153, 225))[index]
                    pg.draw.arc(self.canvas, color, (x, 220, 8, 10), 3.14, 6.28, 2)
                    pg.draw.rect(self.canvas, color, (x + 2, 230, 4, 4))
                    pg.draw.rect(self.canvas, color, (x, 234, 8, 2))
                self.text(f"{self.words('TROFI', 'TROPHIES')} {len(cleared)}/10",
                          640, 303, CREAM, self.tiny, True)
            else:
                for i, color in enumerate((retro.GOLD, (122, 206, 159), (202, 105, 104))):
                    cx, cy = 614 + i * 17, 229
                    pg.draw.circle(self.canvas, color, (cx, cy), 6)
                    pg.draw.circle(self.canvas, (39, 50, 69), (cx, cy), 2)

        plant = decor.get("plant", "")
        if plant:
            pg.draw.ellipse(self.canvas, (50, 62, 48), (718, 512, 54, 12))
            pg.draw.polygon(self.canvas, (152, 88, 58), [(724, 484), (767, 484), (761, 513), (730, 513)])
            pg.draw.rect(self.canvas, (208, 133, 77), (722, 480, 48, 7))
            leaf = (95, 174, 91) if plant == "fern" else (79, 185, 113) if plant == "flower_pot" else (89, 192, 203)
            for side in (-1, 1):
                pg.draw.ellipse(self.canvas, leaf, (740 + side * 12, 455, 18, 28))
            pg.draw.rect(self.canvas, (74, 149, 82), (744, 451, 6, 32))
            if plant == "flower_pot":
                pg.draw.circle(self.canvas, (242, 123, 174), (747, 454), 7)
                pg.draw.circle(self.canvas, retro.GOLD, (747, 454), 2)
            elif plant == "crystal_lamp":
                pg.draw.polygon(self.canvas, (166, 246, 243), [(747, 441), (755, 454), (747, 467), (739, 454)])
                pg.draw.circle(self.canvas, (166, 246, 243), (747, 454), 15, 1)

        trophy = decor.get("trophy", "")
        if trophy:
            pg.draw.rect(self.canvas, (111, 75, 48), (797, 286, 118, 9))
            pg.draw.rect(self.canvas, (163, 116, 70), (802, 295, 7, 18))
            pg.draw.rect(self.canvas, (163, 116, 70), (903, 295, 7, 18))
            if trophy == "trophy_shelf":
                pg.draw.polygon(self.canvas, retro.GOLD, [(835, 263), (843, 268), (852, 263), (850, 278), (843, 283), (836, 278)])
                pg.draw.rect(self.canvas, (177, 119, 57), (838, 280, 10, 7))
            else:
                pg.draw.circle(self.canvas, (199, 62, 66), (865, 273), 11)
                pg.draw.rect(self.canvas, (244, 229, 190), (855, 272, 20, 3))
                pg.draw.circle(self.canvas, (45, 56, 75), (865, 273), 3)

        rug = decor.get("rug", "")
        if rug:
            color = (77, 117, 102) if rug == "berry_rug" else (76, 82, 143)
            pg.draw.rect(self.canvas, (65, 51, 42), (690, 540, 156, 55))
            pg.draw.rect(self.canvas, color, (695, 535, 146, 51))
            pg.draw.rect(self.canvas, (223, 194, 133), (701, 541, 134, 39), 2)
            for x in (713, 741, 769, 797, 825):
                if rug == "berry_rug":
                    pg.draw.circle(self.canvas, (171, 79, 133), (x, 560), 4)
                    pg.draw.rect(self.canvas, (109, 178, 92), (x + 2, 554, 3, 5))
                else:
                    pg.draw.rect(self.canvas, retro.GOLD, (x, 557, 5, 5))

    def home_decor_action(self, item):
        if item[0] in self.life.home_decor_owned:
            self.life.equip_home_decor(item[0])
            message = self.words(f"{item[3]} dipasang di rumah.", f"{item[2]} placed in your home.")
        else:
            if (self.life.money >= item[5] and self.life.bag.get("Kayu", 0) >= item[6]):
                self.life.buy_home_decor(item[0])
                self.life.equip_home_decor(item[0])
                message = self.words(f"{item[3]} dibeli dan dipasang.", f"{item[2]} bought and equipped.")
            else:
                message = self.words(f"Butuh ${item[5]} koin dan {item[6]} kayu.",
                                     f"Need ${item[5]} coins and {item[6]} wood.")
        self.save_current()
        self.play_action_sound("ui-confirm", .2)
        self.notify(message)

    def draw_home_decor(self):
        self.text(self.words("RUMAHKU · KOLEKSI DEKORASI", "MY HOME · DECOR COLLECTION"), 242, 183, CREAM, self.medium)
        self.text(self.words(f"Koin ${self.life.money} · Kayu {self.life.bag.get('Kayu', 0)} · beli lalu pasang per kategori",
                             f"Coins ${self.life.money} · Wood {self.life.bag.get('Kayu', 0)} · buy then equip one per slot"),
                  245, 221, GREEN, self.small)
        for index, item in enumerate(HOME_DECOR):
            col, row = index % 2, index // 2
            x, y = 232 + col * 405, 260 + row * 62
            item_id, slot, name_en, name_id, icon, price, wood = item
            owned = item_id in self.life.home_decor_owned
            equipped = self.life.home_decor.get(slot) == item_id
            title = name_id if self.life.language == "id" else name_en
            status = self.words("Dipasang", "Equipped") if equipped else self.words("Pasang", "Equip") if owned else self.words(f"Beli · ${price} · {wood} kayu", f"Buy · ${price} · {wood} wood")
            self.button(f"{icon}  {title}  ·  {slot.title()}  ·  {status}",
                        (x, y, 390, 48), lambda item=item: self.home_decor_action(item), equipped)
        self.button(self.words("Selesai · Esc", "Done · Esc"), (245, 588, 788, 45), self.back, True)

    def claim_companion_quest(self):
        reward = self.life.claim_companion_quest()
        if not reward:
            return
        self.award_trainer_xp(20)
        self.play_action_sound("pickup-rare", .35)
        self.save_current()
        self.notify(self.words(f"Misi pendamping selesai! +{reward} koin · +1 tiket gacha · ikatan makin kuat.",
                               f"Companion quest complete! +{reward} coins · +1 gacha ticket · bond strengthened."))

    def cycle_companion(self, direction=1):
        party = list(dict.fromkeys(self.life.pokemon_active or self.life.pokemon_party))
        if not party:
            return
        try:
            index = party.index(self.life.companion_id)
        except ValueError:
            index = -1
        self.life.companion_id = party[(index + direction) % len(party)]
        self.life.ensure_companion_quest()
        self.pokedex.request(self.life.companion_id)
        self.pokedex.request_animation(self.life.companion_id)
        self.save_current()

    def companion_world_position(self):
        """Keep the follower comfortably behind the trainer, with a small walk bob."""
        gap = 72 if self.moving else 64
        direction = self.facing
        dx, dy = {"left": (gap, 0), "right": (-gap, 0),
                  "up": (0, gap), "down": (0, -gap)}.get(direction, (gap, 0))
        if self.moving:
            stride = int(math.sin(self.frame / 3.2) * 3)
            if dx:
                dy += stride
            else:
                dx += stride
        return self.life.x + dx, self.life.y + dy

    def bedroom(self):
        self.art.bedroom(self.canvas)
        # Custom monitor is part of the game's interactive PC, placed on asset furniture.
        self.box((861, 192, 134, 88), (41, 49, 46), 5)
        self.box((870, 202, 116, 65), (24, 37, 33), 1)
        self.text("> " + self.terminal.shell_name, 879, 212, GREEN, self.small)
        self.text("SESSION LIVE" if self.terminal.running else "READY", 879, 238, CREAM, self.small)
        pg.draw.rect(self.canvas, (43, 52, 46), (921, 279, 14, 17))
        pg.draw.rect(self.canvas, (43, 52, 46), (907, 291, 43, 5))
        self.box((873, 304, 107, 16), (59, 62, 52), 3)
        for x in range(881, 973, 9):
            pg.draw.line(self.canvas, (157, 170, 150), (x, 309), (x, 314), 2)
        for title, x, y in [("RUMAH / KAMAR", 640, 167), ("TEMPAT TIDUR", 372, 478),
                            ("PC · TERMINAL", 929, 446), ("E · KELUAR", 640, 679)]:
            self.label(title, x, y)

    def draw_world(self):
        if self.life.scene == "reserve":
            self.draw_reserve_world()
            return
        if self.life.scene == "dungeon_hub":
            self.draw_dungeon_hub()
            self.world_characters()
            self.environment.draw(self.canvas, self.life)
            self.hud(self.nearest())
            return
        if self.life.scene == "local_dungeon":
            self.draw_local_dungeon()
            self.world_characters()
            self.environment.draw(self.canvas, self.life)
            self.hud(self.nearest())
            return
        if self.life.scene in ("coast", "mountain"):
            self.art.biome(self.canvas, self.life.scene)
            title = "PANTAI PASANG SURUT" if self.life.scene == "coast" else "PEGUNUNGAN KABUT"
            self.label(title, 640, 159)
            self.label("SUAKA  <", 100, 456)
            self.world_characters()
            self.environment.draw(self.canvas,self.life)
            station = self.nearest()
            self.hud(station)
            return
        {"outdoors": self.outdoors, "house": self.house, "bedroom": self.bedroom,
         "forest": self.forest, "market": self.market}[self.life.scene]()
        self.world_characters()
        self.environment.draw(self.canvas, self.life)
        self.hud(self.nearest())

    def world_characters(self):
        for action, x, y, _ in self.stations():
            if action not in ("restaurant", "hotel"):
                continue
            roof = (205, 116, 69) if action == "restaurant" else (79, 127, 174)
            pg.draw.ellipse(self.canvas, (62, 70, 54), (x - 46, y + 17, 92, 16))
            pg.draw.rect(self.canvas, (222, 207, 170), (x - 38, y - 30, 76, 49))
            pg.draw.rect(self.canvas, (105, 74, 54), (x - 47, y - 39, 94, 15))
            pg.draw.polygon(self.canvas, roof, [(x - 48, y - 33), (x, y - 58), (x + 48, y - 33)])
            pg.draw.rect(self.canvas, (105, 74, 54), (x - 7, y - 11, 14, 30))
            self.label("RESTORAN" if action == "restaurant" else "HOTEL", x, y - 65)
        station = self.nearest()
        if station:
            pg.draw.ellipse(self.canvas, (241, 227, 168), (station[1] - 24, station[2] - 7, 48, 17), 3)
        # Ground objects and actors are drawn by their feet, so foliage has depth.
        drawables = [(y, "tree", (x, y)) for x, y in self.art.trees.get(self.life.scene, [])]
        if self.life.scene == "forest":
            drawables += [(a["y"], "animal", a) for a in self.wildlife.living]
        elif self.life.scene == "market":
            drawables += [(npc[2], "npc", npc) for npc in self.npcs()]
        elif self.life.scene == "outdoors":
            drawables += [(drop["y"], "farm_drop", drop) for drop in self.life.farm_drops
                          if not drop.get("taken")]
        drawables += [(t["y"], "trainer", t) for t in self.route_trainers if t["scene"] == self.life.scene]
        if not self.life.mounted and self.life.scene == self.life.horse_scene:
            drawables.append((self.life.horse_y, "horse", (self.life.horse_x, self.life.horse_y)))
        if getattr(self.life, "companion_id", 0) and self.life.companion_id in self.life.pokemon_party:
            companion_x, companion_y = self.companion_world_position()
            drawables.append((companion_y - 2, "companion",
                              (int(self.life.companion_id), companion_x, companion_y)))
        drawables.append((self.life.y, "player", None))
        for _, kind, obj in sorted(drawables, key=lambda entry: entry[0]):
            if kind == "tree":
                self.art.tree(self.canvas, *obj, variant=(int(obj[0]) // 112) % 2)
            elif kind == "horse":
                self.art.animal(self.canvas, "Kuda", *obj, 65, "right", self.frame, False)
            elif kind == "npc":
                _, x, y, name, _ = obj
                self.art.character(self.canvas, x, y, 0, 1.7, self.frame, self.life.market_open, npc=name)
            elif kind == "trainer":
                trainer_style = "Woman" if obj.get("rival") else "Hunter"
                self.art.character(self.canvas, obj["x"], obj["y"], 1, 1.8, self.frame, True, "down", npc=trainer_style)
                caption = (f"{obj['name']} · Lv.{obj.get('level', 5)} · REMATCH" if obj.get("rival") and obj.get("defeated") else
                           f"{obj['name']} · RIVAL Lv.{obj.get('level', 5)}" if obj.get("rival") else
                           obj["name"] + (" · MENANG" if obj.get("defeated") else " · SPACE"))
                self.label(caption, obj["x"], obj["y"] - 42)
            elif kind == "farm_drop":
                pulse = 12 + int(2 * math.sin(self.frame / 5 + obj["x"]))
                pg.draw.ellipse(self.canvas, (72, 91, 56), (obj["x"] - 13, obj["y"] + 3, 26, 9))
                pg.draw.circle(self.canvas, retro.GOLD, (int(obj["x"]), int(obj["y"] - 9)), pulse, 2)
                glyph = self.fruit_font.render(obj["emoji"], True, CREAM)
                self.canvas.blit(glyph, glyph.get_rect(center=(int(obj["x"]), int(obj["y"] - 13))))
                if math.hypot(obj["x"] - self.life.x, obj["y"] - self.life.y) < 130:
                    self.text("E · AMBIL" if self.life.language == "id" else "E · PICK UP",
                              obj["x"], obj["y"] + 17, CREAM, self.tiny, True)
            elif kind == "animal":
                self.art.animal(self.canvas, obj["species"], obj["x"], obj["y"], SPECIES[obj["species"]]["size"], obj["facing"], self.frame, obj["moving"])
                if obj["hp"] < SPECIES[obj["species"]]["hp"]:
                    self.box((obj["x"] - 23, obj["y"] + 3, 46, 5), INK, 2)
                    self.box((obj["x"] - 23, obj["y"] + 3, max(1, 46 * obj["hp"] / SPECIES[obj["species"]]["hp"]), 5), (215, 112, 91), 2)
                if math.hypot(obj["x"] - self.life.x, obj["y"] - self.life.y) < 155:
                    self.text(obj["species"] + " · " + obj["state"], obj["x"], obj["y"] + 24, INK, self.small, True)
            elif kind == "companion":
                ident, companion_x, companion_y = obj
                image = self.pokemon_surface(ident, 46)
                if image:
                    image = pg.transform.flip(image, True, False) if self.facing == "right" else image
                    bob = int(math.sin(self.frame / 3.2) * 3) if self.moving else int(math.sin(self.frame / 10) * 1)
                    pg.draw.ellipse(self.canvas, (47, 58, 47),
                                    (int(companion_x - 16), int(companion_y - 2), 32, 7))
                    self.canvas.blit(image, image.get_rect(midbottom=(int(companion_x), int(companion_y + bob))))
            else:
                if self.life.mounted:
                    self.art.animal(self.canvas, "Kuda", self.life.x, self.life.y, 66, self.facing, self.frame, self.moving)
                self.sprite(self.life.x, self.life.y - (29 if self.life.mounted else 0), scale=1.7, walking=self.moving and not self.life.mounted)
                self.draw_player_cosmetic(self.life.x, self.life.y - (29 if self.life.mounted else 0))
                if self.life.weapon:
                    angle = {"right": 0, "down": math.pi / 2, "left": math.pi, "up": -math.pi / 2}[self.facing]
                    cx, cy = self.life.x + 13, self.life.y - (53 if self.life.mounted else 24)
                    if self.life.weapon == "Tombak":
                        dx, dy = math.cos(angle) * 41, math.sin(angle) * 41
                        pg.draw.line(self.canvas, (105, 70, 43), (cx, cy), (cx + dx, cy + dy), 4)
                        pg.draw.circle(self.canvas, (219, 225, 212), (int(cx + dx), int(cy + dy)), 4)
                    else:
                        pg.draw.arc(self.canvas, (100, 65, 40), (cx - 9, cy - 15, 19, 32), -.9, .9, 4)
                    if self.attack_flash:
                        pg.draw.circle(self.canvas, (239, 223, 163), (int(cx + math.cos(angle) * 47), int(cy + math.sin(angle) * 47)), 24, 3)
        for arrow in self.projectiles:
            pg.draw.line(self.canvas, (231, 217, 160), (arrow["x"], arrow["y"]), (arrow["x"] - arrow["dx"] * 18, arrow["y"] - arrow["dy"] * 18), 3)
        if self.fishing:
            pg.draw.line(self.canvas, (228, 215, 172), (self.life.x + 10, self.life.y - 28), (1080, 558), 2)

    def draw_reserve_world(self):
        camera_x = max(0, min(RESERVE_WIDTH - W, self.life.x - W // 2))
        camera_y = max(0, min(RESERVE_HEIGHT - 592, self.life.y - 296))
        self.reserve_camera = (int(camera_x), int(camera_y))
        self.world_canvas.fill((0, 0, 0))
        self.art.reserve(self.world_canvas, self.reserve_camera)
        station = self.nearest()
        left, top = camera_x - 120, camera_y - 140
        right, bottom = camera_x + W + 120, camera_y + 592 + 100
        drawables = [(y, "tree", (x, y)) for x, y in self.art.trees["reserve"] if left <= x <= right and top <= y <= bottom]
        zone_index=reserve_index_at(self.life.x,self.life.y)
        zone_x,zone_y=RESERVE_ZONES[zone_index]["x"],RESERVE_ZONES[zone_index]["y"]
        for prop in reserve_layout(zone_index)['props']:
            kind,x,y,variant=prop
            if left<=x+zone_x<=right and top<=y+zone_y<=bottom:
                drawables.append((y+zone_y,"scenery",(kind,x+zone_x,y+zone_y,variant)))
        drawables += [(p["y"], "pokemon", p) for p in self.wild_pokemon]
        drawables += [(t["y"], "trainer", t) for t in self.reserve_trainers]
        if not self.life.mounted and self.life.horse_scene == "reserve":
            drawables.append((self.life.horse_y, "horse", (self.life.horse_x, self.life.horse_y)))
        if getattr(self.life, "companion_id", 0) and self.life.companion_id in self.life.pokemon_party:
            companion_x, companion_y = self.companion_world_position()
            drawables.append((companion_y - 2, "companion",
                              (int(self.life.companion_id), companion_x, companion_y)))
        drawables.append((self.life.y, "player", None))
        for _, kind, obj in sorted(drawables, key=lambda item: item[0]):
            if kind=="scenery":
                pk,x,y,v=obj
                self.art.scenery.prop(self.world_canvas,(pk,int(x-camera_x),int(y-camera_y),v),RESERVE_ZONES[zone_index]["biome"])
                continue
            wx, wy = (obj[0], obj[1]) if kind in ("tree", "horse") else (obj[1], obj[2]) if kind == "companion" else (obj["x"], obj["y"]) if kind in ("pokemon", "trainer") else (self.life.x, self.life.y)
            if not (left <= wx <= right and top <= wy <= bottom):
                continue
            if (kind == "trainer" and obj.get("rocket_event")
                    and obj.get("rocket_behavior") == "ambush"
                    and not obj.get("rocket_revealed")):
                continue
            px, py = wx - camera_x, wy - camera_y
            if kind == "tree":
                world_x, world_y = obj
                zone_index = reserve_index_at(world_x, world_y)
                biome = RESERVE_ZONES[zone_index]["biome"]
                variants = {
                    "snow": (4, 5, 6, 16, 17),
                    "ancient_forest": (2, 11, 14, 20, 23),
                    "swamp": (2, 3, 12, 15, 21),
                    "forest": (0, 1, 3, 8, 10, 11, 13, 15),
                    "meadow": (0, 3, 8, 9, 10, 11, 12, 13),
                }
                tree_set = variants.get(biome, (0, 1, 3, 8, 10, 11, 12, 13))
                seed = (int(world_x // 112) * 7 + int(world_y // 112) * 11 + zone_index) % len(tree_set)
                self.art.tree(self.world_canvas, px, py, variant=tree_set[seed])
            elif kind == "pokemon":
                sprite = self.pokemon_surface(obj["id"], 86 if obj.get("is_boss") else 52)
                if sprite:
                    bob = int(math.sin(self.frame / 5 + obj["id"]) * 4) if obj.get("moving") else int(math.sin(self.frame / 13 + obj["id"]) * 2)
                    image = pg.transform.flip(sprite, True, False) if obj.get("vx", 0) >= 0 else sprite
                    if obj.get("state") != "hide":
                        if obj.get("is_boss"):
                            aura = 42 + int(3 * math.sin(self.frame / 5))
                            pg.draw.circle(self.world_canvas, retro.GOLD, (int(px), int(py - 38)), aura, 3)
                        self.world_canvas.blit(image, image.get_rect(midbottom=(int(px), int(py - 3 + bob))))
                        if obj.get("state") == "flee" and int(self.frame / 12) % 2 == 0:
                            pg.draw.circle(self.world_canvas, (244, 231, 153), (int(px), int(py - 66 + bob)), 5)
                    elif int(self.frame / 15) % 2 == 0:
                        pg.draw.circle(self.world_canvas, (179, 213, 120), (int(px), int(py - 12)), 4)
                    if math.hypot(obj["x"] - self.life.x, obj["y"] - self.life.y) < (230 if obj.get("is_boss") else 155) and obj.get("state") != "hide":
                        detail = self.pokemon_data(obj["id"]) or {}
                        name = detail.get("name", "Pokémon liar").title()
                        rarity = " · ★ BOSS" if obj.get("is_boss") else (" · ★ RARE" if obj.get("rare") else "")
                        tag = self.small.render(self.tr(f"{name} · Lv.{obj.get('level', 5)}{rarity}"), True, retro.GOLD if obj.get("is_boss") else CREAM)
                        self.world_canvas.blit(tag, tag.get_rect(center=(int(px), int(py + 11))))
            elif kind == "trainer":
                self.art.character(self.world_canvas, px, py, 1, 1.8, self.frame, True, "down",
                                   npc=obj.get("trainer_style", "Hunter"))
                caption = (("TEAM ROCKET · REMATCH" if getattr(self.life, "rocket_stolen_pokemon", []) else "TEAM ROCKET")
                           if obj.get("rocket_event") else
                           "BOSS · " + obj["name"] + (" · REMATCH" if obj.get("defeated") else "")
                           if obj.get("is_boss") else
                           obj["name"] + (" · REMATCH" if obj.get("defeated") else " · SPACE TANTANG"))
                label = self.small.render(caption, True, INK)
                back = pg.Rect(0, 0, label.get_width() + 12, label.get_height() + 7)
                back.midbottom = (int(px), int(py - 40))
                pg.draw.rect(self.world_canvas, GREEN if obj.get("defeated") else CREAM, back, border_radius=0)
                self.world_canvas.blit(label, label.get_rect(center=back.center))
                if obj.get("rocket_event"):
                    badge = pg.Rect(int(px + 14), int(py - 67), 23, 23)
                    pg.draw.rect(self.world_canvas, (183, 54, 64), badge)
                    badge_text = self.tiny.render("R", True, CREAM)
                    self.world_canvas.blit(badge_text, badge_text.get_rect(center=badge.center))
            elif kind == "horse":
                self.art.animal(self.world_canvas, "Kuda", px, py, 65, "right", self.frame, False)
            elif kind == "companion":
                ident, companion_x, companion_y = obj
                image = self.pokemon_surface(ident, 46)
                if image:
                    image = pg.transform.flip(image, True, False) if self.facing == "right" else image
                    bob = int(math.sin(self.frame / 3.2) * 3) if self.moving else int(math.sin(self.frame / 10) * 1)
                    pg.draw.ellipse(self.world_canvas, (47, 58, 47),
                                    (int(px - 16), int(py - 2), 32, 7))
                    self.world_canvas.blit(image, image.get_rect(midbottom=(int(px), int(py + bob))))
            else:
                if self.life.mounted:
                    self.art.animal(self.world_canvas, "Kuda", px, py, 66, self.facing, self.frame, self.moving)
                self.art.character(self.world_canvas, px, py - (29 if self.life.mounted else 0), self.life.character,
                                   1.7, self.frame, self.moving, self.facing)
        self.canvas.blit(self.world_canvas, (0, 135))
        self.draw_player_cosmetic(self.life.x - camera_x, self.life.y - camera_y + 135)
        sx = lambda x: x - self.reserve_camera[0]
        sy = lambda y: y - self.reserve_camera[1] + 135
        zone = self.reserve_zone_at(self.life.x, self.life.y)
        biome = biome_at("reserve", self.life.x, self.life.y)
        if biome not in self.life.discovered_secrets:
            secret = self.secret_world_position(biome)
            if secret:
                _, secret_x, secret_y, icon = secret
                px, py = sx(secret_x), sy(secret_y)
                if 0 <= px < W and 135 <= py < 727:
                    pulse = 15 + int(3 * math.sin(self.frame / 5))
                    pg.draw.circle(self.canvas, retro.GOLD, (int(px), int(py)), pulse, 2)
                    self.emoji(icon, (int(px), int(py) - 10), 32)
        self.label(zone["name"].upper(), 640, 154)
        zone_index = RESERVE_ZONES.index(zone)
        boss_wins = int(self.life.reserve_space_wins.get(str(zone_index), 0))
        if zone_index in self.life.reserve_space_bosses:
            self.label(self.words("BOSS DIKALAHKAN · GERBANG TERBUKA",
                                  "BOSS DEFEATED · GATES OPEN"), 640, 188)
        elif boss_wins < self.reserve_boss_threshold(zone_index):
            target = self.reserve_boss_threshold(zone_index)
            self.label(self.words(f"KALAHKAN POKÉMON LIAR · BOSS {boss_wins}/{target}",
                                  f"DEFEAT WILD POKÉMON · BOSS {boss_wins}/{target}"), 640, 188)
        else:
            self.label(self.words("POKÉMON BOSS MUNCUL · KALAHKAN UNTUK MEMBUKA GERBANG",
                                  "BOSS POKÉMON APPEARED · DEFEAT IT TO OPEN GATES"), 640, 188)
        for gate in self.reserve_gates():
            gx, gy = sx(gate["x"]), sy(gate["y"])
            if -80 < gx < W + 80 and 190 < gy < 592 + 135:
                required = gate["required_level"]
                if not gate["boss_defeated"] and not gate["return_route_open"]:
                    gate_label = "TERKUNCI · KALAHKAN BOSS"
                elif gate["boss_defeated"]:
                    gate_label = "GERBANG · " + gate["target"]["name"]
                else:
                    gate_label = "TERKUNCI · KALAHKAN BOSS"
                self.label(gate_label, gx, gy - 30)
        for index, (cx, cy) in enumerate(RESERVE_CENTERS):
            if -130 < sx(cx) < W + 130 and 180 < sy(cy) < H + 100:
                self.label("POKÉMON CENTER · E", sx(cx), sy(cy) - 114)
        zone = self.reserve_zone_at(self.life.x, self.life.y)
        zone_index = RESERVE_ZONES.index(zone)
        hospitality_buildings = {
            kind: (zone["x"] + x, zone["y"] + y)
            for kind, x, y in reserve_layout(zone_index)["buildings"]
            if kind in ("restaurant", "hotel")
        }
        for kind, (building_x, building_y) in hospitality_buildings.items():
            label = "RESTORAN · E" if kind == "restaurant" else "HOTEL · E"
            self.label(label, sx(building_x), sy(building_y) - 59)
        if not any(zone["x"] <= cx < zone["x"] + RESERVE_ZONE_W
                   and zone["y"] <= cy < zone["y"] + RESERVE_ZONE_H for cx, cy in RESERVE_CENTERS):
            self.label("POKÉMON CENTER · E", sx(zone["x"] + RESERVE_ZONE_W // 2),
                       sy(zone["y"] + RESERVE_ZONE_H // 2 + 155) - 114)
        self.label("ARENA TANTANGAN", sx(1280), sy(800) - 150)
        self.label("< KEMBALI", sx(92), sy(800) - 26)
        if station:
            pg.draw.ellipse(self.canvas, (241, 227, 168), (sx(station[1]) - 24, sy(station[2]) - 7, 48, 17), 3)
        view = copy.copy(self.life)
        view.x, view.y = sx(self.life.x), sy(self.life.y)
        self.environment.draw(self.canvas, view)
        self.hud(station)

    def reserve_zone_at(self, x, y):
        return RESERVE_ZONES[reserve_index_at(x, y)]

    def update_location_audio(self):
        """Switch to locally bundled music when the player changes location."""
        if not pg.mixer.get_init():
            return
        # The Team Rocket cut-in uses the soundtrack embedded in the supplied
        # video; do not replace it with the location loop until it ends.
        if self._music_key == "rocket_video":
            return
        if self.mode == "title":
            if self._music_key is not None:
                pg.mixer.music.fadeout(500)
                self._music_key = None
            return

        music_dir = ROOT / "assets" / "audio" / "music"
        scene = self.life.scene
        track = {
            "outdoors": "meadow.ogg", "house": "home.ogg", "bedroom": "bedroom.ogg",
            "forest": "forest.ogg", "market": "market.ogg", "coast": "ocean.ogg",
            "mountain": "adventure.ogg", "dungeon_hub": "mystical.ogg",
            "local_dungeon": "cavern.ogg",
        }.get(scene, "adventure.ogg")
        zone_name = ""
        if scene == "local_dungeon":
            zone_name = DUNGEON_BIOMES[min(9, max(0, int(self.life.local_dungeon_tier) - 1))]
            biome_tracks = {"cave": "cavern.ogg", "forest": "forest.ogg", "swamp": "swamp.ogg",
                            "badlands": "ruins.ogg", "snow": "snow.ogg", "volcano": "tavern.ogg",
                            "crystal": "mystical.ogg", "sky": "sky.ogg", "dragon_valley": "tavern.ogg",
                            "legendary_ruins": "cavern.ogg"}
            track = biome_tracks.get(zone_name, "cavern.ogg")
        if scene == "reserve":
            zone = self.reserve_zone_at(self.life.x, self.life.y)
            zone_name = zone["biome"]
            biome_tracks = {
                "meadow": "meadow.ogg", "forest": "forest.ogg", "desert": "desert.ogg",
                "coast": "ocean.ogg", "swamp": "swamp.ogg", "cave": "cavern.ogg",
                "badlands": "ruins.ogg", "mountain": "adventure.ogg", "volcano": "tavern.ogg",
                "snow": "snow.ogg", "sky": "sky.ogg", "crystal": "mystical.ogg",
                "ancient_forest": "fairy.ogg", "deepsea": "ocean.ogg",
                "dragon_valley": "tavern.ogg", "legendary_ruins": "cavern.ogg",
            }
            track = biome_tracks.get(zone_name, "adventure.ogg")

        if self.mode == "battle":
            track = (self.battle or {}).get("music_track", "battle.wav")
        path = music_dir / track
        music_key = f"battle:{track}" if self.mode == "battle" else f"{scene}:{zone_name}:{track}"
        if path.is_file() and music_key != self._music_key:
            try:
                pg.mixer.music.load(str(path))
                pg.mixer.music.play(-1, fade_ms=650)
                pg.mixer.music.set_volume((.36 if self.mode == "battle" else .28) * self.life.music_volume)
                self._music_key = music_key
            except pg.error:
                pass

        in_market = scene == "market" and self.mode not in ("title", "battle", "dead") and self._market_ambience is not None and self._market_ambience_channel is not None
        if in_market and not self._market_ambience_channel.get_busy():
            self._market_ambience_channel.play(self._market_ambience, loops=-1, fade_ms=500)
        elif not in_market and self._market_ambience_channel is not None and self._market_ambience_channel.get_busy():
            self._market_ambience_channel.fadeout(650)

        in_forest = scene == "forest" and self.mode not in ("title", "battle", "dead")
        if in_forest and self._forest_ambience_channel is not None:
            if self._forest_ambience is None:
                try:
                    self._forest_ambience = pg.mixer.Sound(str(ROOT / "assets" / "audio" / "ambience" / "forest_birds.ogg"))
                    self._forest_ambience_channel.set_volume(.10)
                except (pg.error, OSError):
                    self._forest_ambience = None
            if self._forest_ambience is not None and not self._forest_ambience_channel.get_busy():
                self._forest_ambience_channel.play(self._forest_ambience, loops=-1, fade_ms=700)
        elif self._forest_ambience_channel is not None and self._forest_ambience_channel.get_busy():
            self._forest_ambience_channel.fadeout(700)

    def choose_battle_music(self):
        """Pick one locally bundled battle loop, avoiding the last battle's track."""
        music_dir = ROOT / "assets" / "audio" / "music"
        candidates = [name for name in (
            "battle.wav", "adventure.ogg", "tavern.ogg", "ruins.ogg", "mystical.ogg",
            "cavern.ogg", "sky.ogg", "desert.ogg", "forest.ogg", "swamp.ogg",
            "snow.ogg", "ocean.ogg", "fairy.ogg",
        ) if (music_dir / name).is_file()]
        if not candidates:
            return "battle.wav"
        choices = [name for name in candidates if name != self._last_battle_track] or candidates
        track = self.pokemon_rng.choice(choices)
        self._last_battle_track = track
        return track

    def open_global_map(self):
        self.play_action_sound("menu-open", .24)
        if not self.pokedex.catalog:
            self.pokedex.request_catalog()
        elif not self.wild_pokemon:
            self.spawn_map_pokemon()
        if self.life.scene == "reserve":
            self.map_center[:] = [self.life.x, self.life.y]
        else:
            self.map_center[:] = [RESERVE_WIDTH / 2, RESERVE_HEIGHT / 2]
        self.map_zoom = 1.0
        self.mode = "map"

    def draw_global_map(self):
        self.canvas.fill((16, 27, 25))
        self.box((36, 22, 1208, 755), INK, 22)
        self.text("PETA DUNIA", 66, 40, CREAM, self.medium)
        scene_name = {"outdoors": "Rumah & peternakan", "house": "Rumah", "bedroom": "Kamar", "forest": "Hutan", "market": "Market", "reserve": self.reserve_zone_at(self.life.x, self.life.y)["name"], "coast": "Pantai", "mountain": "Pegunungan"}.get(self.life.scene, self.life.scene.title())
        self.text(f"{len(RESERVE_ZONES)} bioma · {len(self.pokedex.catalog)} spesies · posisi: {scene_name} · klik untuk fokus", 68, 84, MUTED, self.small)
        board = pg.Rect(66, 119, 1148, 564)
        pg.draw.rect(self.canvas, (22, 37, 34), board, border_radius=0)
        clip = self.canvas.get_clip()
        self.canvas.set_clip(board)
        self.map_zone_rects = []
        sx = board.w / RESERVE_WIDTH * self.map_zoom
        sy = board.h / RESERVE_HEIGHT * self.map_zoom
        for zone in RESERVE_ZONES:
            x = board.centerx + (zone["x"] + RESERVE_ZONE_W / 2 - self.map_center[0]) * sx
            y = board.centery + (zone["y"] + RESERVE_ZONE_H / 2 - self.map_center[1]) * sy
            rect = pg.Rect(0, 0, max(1, round(RESERVE_ZONE_W * sx)), max(1, round(RESERVE_ZONE_H * sy)))
            rect.center = (round(x), round(y))
            self.map_zone_rects.append((rect, zone))
            pg.draw.rect(self.canvas, zone["color"], rect)
            pg.draw.rect(self.canvas, (225, 229, 204), rect, 2)
            if rect.width > 78 and rect.height > 34:
                title = self.small.render(self.tr(zone["name"]), True, CREAM)
                zone_index = RESERVE_ZONES.index(zone)
                needed = RESERVE_LEVEL_REQUIREMENTS[zone_index]
                access = ("TERBUKA" if self.player_progress_level() >= needed else f"TERKUNCI · Lv.{needed}")
                access_surface = self.tiny.render(self.tr(access), True, GREEN if self.player_progress_level() >= needed else retro.GOLD)
                chip = pg.Rect(0, 0, max(title.get_width(), access_surface.get_width()) + 20,
                               title.get_height() + access_surface.get_height() + 13)
                chip.center = rect.center
                pg.draw.rect(self.canvas, (25, 43, 38), chip, border_radius=0)
                self.canvas.blit(title, title.get_rect(midtop=(rect.centerx, chip.top + 4)))
                self.canvas.blit(access_surface, access_surface.get_rect(midtop=(rect.centerx, chip.top + 7 + title.get_height())))
        # Trails and streams are visible as simple global route lines.
        for y in range(790, RESERVE_HEIGHT, RESERVE_ZONE_H // 2):
            py = board.centery + (y - self.map_center[1]) * sy
            pg.draw.line(self.canvas, (219, 165, 105), (board.left, py), (board.right, py), max(1, round(4 * self.map_zoom)))
        for x in range(1240, RESERVE_WIDTH, RESERVE_ZONE_W):
            px = board.centerx + (x - self.map_center[0]) * sx
            pg.draw.line(self.canvas, (219, 165, 105), (px, board.top), (px, board.bottom), max(1, round(4 * self.map_zoom)))
        for cx, cy in RESERVE_CENTERS:
            px = board.centerx + (cx - self.map_center[0]) * sx
            py = board.centery + (cy - self.map_center[1]) * sy
            if board.collidepoint(px, py):
                pg.draw.rect(self.canvas, (247, 224, 183), (round(px) - 5, round(py) - 5, 10, 10))
                pg.draw.rect(self.canvas, (205, 79, 75), (round(px) - 4, round(py) - 7, 8, 5))
        for wild in self.wild_pokemon:
            px = board.centerx + (wild["x"] - self.map_center[0]) * sx
            py = board.centery + (wild["y"] - self.map_center[1]) * sy
            if board.collidepoint(px, py):
                pg.draw.circle(self.canvas, (255, 243, 177), (round(px), round(py)), max(2, round(3 * min(1.5, self.map_zoom))))
        if self.life.scene == "reserve":
            px = board.centerx + (self.life.x - self.map_center[0]) * sx
            py = board.centery + (self.life.y - self.map_center[1]) * sy
            if board.collidepoint(px, py):
                pg.draw.circle(self.canvas, (255, 248, 219), (round(px), round(py)), 8)
                pg.draw.circle(self.canvas, (205, 79, 75), (round(px), round(py)), 5)
        self.canvas.set_clip(clip)
        self.box((82, 697, 1112, 47), (46, 65, 55), 12)
        self.text(f"Zoom {round(self.map_zoom * 100)}% · {len(self.wild_pokemon)} aktif · {len(self.pokedex.catalog)} spesies", 101, 710, GREEN, self.small)
        self.text("Panah geser / +/- zoom / Tab tombol / M kembali", 685, 710, CREAM, self.small)
        self.button("Jelajahi suaka", (914, 43, 194, 34), self.enter_reserve_from_map, True)
        self.button("−", (1127, 43, 34, 34), lambda: self.change_map_zoom(1 / 1.25))
        self.button("+", (1168, 43, 34, 34), lambda: self.change_map_zoom(1.25))

    def draw_tutorial_map(self):
        """A readable local route map for the life-sim onboarding sequence."""
        self.canvas.fill((14, 24, 35))
        self.box((48, 34, 1184, 712), INK, 18, retro.EDGE)
        title = self.words("PETA PETUNJUK TUTORIAL", "TUTORIAL ROUTE MAP")
        self.text(title, 82, 58, CREAM, self.medium)
        objective = self.tutorial_objective()
        if not objective:
            self.text(self.words("Tutorial selesai · petualangan bebas", "Tutorial complete · free exploration"),
                      84, 102, GREEN, self.small)
            self.button("Kembali · M / Esc", (900, 63, 280, 42), self.back, True)
            return

        # Schematic layout mirrors the actual entrances and activity areas.
        points = {
            "forest": (300, 294), "sanctuary": (300, 166), "farm": (630, 418),
            "market": (1000, 418), "house": (630, 626), "garden": (490, 394),
            "coop": (760, 360), "pond": (820, 552), "table": (535, 626),
            "kitchen": (500, 560), "bedroom": (765, 626), "hunt": (390, 294),
        }
        links = (("forest", "sanctuary"), ("forest", "farm"), ("farm", "market"),
                 ("farm", "house"), ("farm", "garden"), ("farm", "coop"),
                 ("farm", "pond"), ("house", "table"), ("house", "kitchen"),
                 ("house", "bedroom"), ("forest", "hunt"))
        for first, second in links:
            pg.draw.line(self.canvas, (135, 111, 78), points[first], points[second], 9)
            pg.draw.line(self.canvas, (211, 175, 119), points[first], points[second], 3)

        action = objective[0]
        target_node = {
            "plant": "garden", "water": "garden", "harvest": "garden", "egg": "coop",
            "fish": "pond", "sell_farm": "market", "buy_weapon": "market", "hunt": "hunt",
            "sell_hunt": "market", "enter_home": "house", "eat": "table", "sleep": "bedroom",
            "drink": "kitchen", "enter_reserve": "sanctuary",
        }.get(action, "farm")
        player_node = {"outdoors": "farm", "forest": "forest", "market": "market",
                       "house": "house", "bedroom": "bedroom", "reserve": "sanctuary"}.get(self.life.scene, "farm")
        start, goal = points[player_node], points[target_node]
        pg.draw.line(self.canvas, retro.GREEN, start, goal, 5)
        # Draw all localities as labeled map pins.
        labels = {
            "forest": ("Hutan", "Forest"), "sanctuary": ("Suaka Pokémon", "Pokémon Sanctuary"),
            "farm": ("Halaman", "Farmyard"), "market": ("Market", "Market"),
            "house": ("Rumah", "Home"), "garden": ("Kebun", "Garden"),
            "coop": ("Kandang", "Chicken coop"), "pond": ("Kolam pancing", "Fishing pond"),
            "table": ("Meja makan", "Dining table"), "kitchen": ("Dapur", "Kitchen"),
            "bedroom": ("Kamar", "Bedroom"), "hunt": ("Area berburu", "Hunting area"),
        }
        for node, (x, y) in points.items():
            is_target, is_player = node == target_node, node == player_node
            color = retro.GOLD if is_target else retro.GREEN if is_player else retro.EDGE
            pg.draw.circle(self.canvas, INK, (x, y), 17)
            pg.draw.circle(self.canvas, color, (x, y), 13)
            pg.draw.circle(self.canvas, CREAM if is_target or is_player else INK, (x, y), 5)
            label = labels[node][0 if self.life.language == "id" else 1]
            self.text(label, x, y + 22, CREAM, self.tiny, True)
        pulse = 20 + int(3 * math.sin(self.frame / 5))
        pg.draw.circle(self.canvas, retro.GOLD, points[target_node], pulse, 2)
        pg.draw.circle(self.canvas, CREAM, points[player_node], 19, 2)
        step_text = objective[1] if self.life.language == "id" else objective[2]
        self.text(self.words(f"TUJUAN · {self.life.tutorial_step+1}/{len(TUTORIAL_STEPS)}",
                             f"OBJECTIVE · {self.life.tutorial_step+1}/{len(TUTORIAL_STEPS)}"),
                  82, 690, retro.GOLD, self.small)
        self.text(step_text, 365, 690, CREAM, self.small)
        self.text(self.words("LINGKARAN EMAS = TUJUAN   ·   LINGKARAN HIJAU = KAMU",
                             "GOLD PIN = OBJECTIVE   ·   GREEN PIN = YOU"), 82, 720, GREEN, self.tiny)
        self.button("Kembali · M / Esc", (900, 63, 280, 42), self.back, True)

    def change_map_zoom(self, factor):
        self.map_zoom = max(0.55, min(3.2, self.map_zoom * factor))

    def enter_reserve_from_map(self):
        if self.life.tutorial_active:
            objective = self.tutorial_objective()
            if objective and objective[0] != "enter_reserve":
                self.notify(self.words(f"Selesaikan tutorial dulu: {objective[1]}.",
                                       f"Finish the tutorial first: {objective[2]}."))
                return
            self.tutorial_advance("enter_reserve")
        self.mode = "game"
        if self.life.scene != "reserve":
            self.transition("reserve", 100, 800)
        if not self.wild_pokemon:
            self.spawn_map_pokemon()
        self.notify(f"Suaka terbuka · {len(RESERVE_ZONES)} bioma dan habitat Pokémon tersebar di seluruh peta.")

    def tutorial_navigation(self):
        """Give a live compass hint for the current onboarding objective."""
        objective = self.tutorial_objective() if self.life.tutorial_active else None
        if not objective:
            return None
        action = objective[0]
        scene = self.life.scene
        # Each target is in the current scene's world coordinates. When the
        # objective is elsewhere, guide the player to the correct exit first.
        targets = {
            "outdoors": {
                "plant": (650, 475, "Kebun"), "water": (650, 475, "Kebun"),
                "harvest": (650, 475, "Kebun"), "egg": (905, 350, "Kandang ayam"),
                "fish": (963, 615, "Kolam"), "sell_farm": (1237, 405, "Market · keluar kanan"),
                "buy_weapon": (1237, 405, "Market · keluar kanan"),
                "hunt": (43, 405, "Hutan · keluar kiri"), "sell_hunt": (1237, 405, "Market · keluar kanan"),
                "enter_home": (350, 350, "Rumah"), "eat": (350, 350, "Rumah"),
                "sleep": (350, 350, "Rumah"), "drink": (350, 350, "Rumah"),
                "enter_reserve": (160, 610, "Gerbang Suaka · kiri bawah"),
            },
            "forest": {
                "hunt": (645, 555, "Area berburu"),
                "sell_hunt": (1237, 405, "Market · keluar kanan"),
                "sell_farm": (1237, 405, "Market · keluar kanan"),
                "buy_weapon": (1237, 405, "Market · keluar kanan"),
                "enter_reserve": (650, 177, "Gerbang Suaka · utara"),
                "enter_home": (1237, 405, "Halaman rumah · keluar kanan"),
                "eat": (1237, 405, "Rumah · keluar kanan"),
                "sleep": (1237, 405, "Rumah · keluar kanan"),
                "drink": (1237, 405, "Rumah · keluar kanan"),
            },
            "market": {
                "sell_farm": (673, 619, "Joy · jual hasil"), "sell_hunt": (673, 619, "Joy · jual hasil"),
                "buy_weapon": (902, 350, "Lapak senjata · Budi"),
                "hunt": (43, 405, "Halaman → hutan · keluar kiri"),
                "enter_home": (43, 405, "Halaman rumah · keluar kiri"),
                "eat": (43, 405, "Rumah · keluar kiri"), "sleep": (43, 405, "Rumah · keluar kiri"),
                "drink": (43, 405, "Rumah · keluar kiri"),
                "enter_reserve": (43, 405, "Halaman → gerbang suaka · keluar kiri"),
            },
            "house": {
                "eat": (596, 453, "Meja makan"), "drink": (247, 308, "Dapur · air"),
                "sleep": (1015, 235, "Pintu kamar"), "enter_reserve": (640, 662, "Keluar ke halaman"),
            },
            "bedroom": {
                "sleep": (370, 414, "Tempat tidur"), "enter_reserve": (640, 662, "Keluar ke halaman"),
            },
        }
        target = targets.get(scene, {}).get(action)
        if target is None:
            # Return to the main farm first for tasks whose destination is there.
            if scene == "bedroom":
                return self.words("Arah: keluar kamar → ruang keluarga", "Go: leave the bedroom → living room")
            if scene == "house":
                target = (640, 662, "Keluar ke halaman")
            elif scene == "forest":
                target = (1237, 405, "Halaman rumah · kanan")
            elif scene == "market":
                target = (43, 405, "Halaman rumah · kiri")
            elif scene in ("reserve", "coast", "mountain"):
                return self.words("Kembali ke halaman rumah untuk tutorial", "Return to the farm for the tutorial")
            else:
                return self.words("Ikuti jalan menuju lokasi tujuan", "Follow the path toward your objective")
        dx, dy = target[0] - self.life.x, target[1] - self.life.y
        horizontal = "KIRI" if dx < -65 else "KANAN" if dx > 65 else ""
        vertical = "ATAS" if dy < -65 else "BAWAH" if dy > 65 else ""
        arrows = {("KIRI", "ATAS"): "↖", ("KANAN", "ATAS"): "↗",
                  ("KIRI", "BAWAH"): "↙", ("KANAN", "BAWAH"): "↘",
                  ("KIRI", ""): "←", ("KANAN", ""): "→",
                  ("", "ATAS"): "↑", ("", "BAWAH"): "↓", ("", ""): "•"}
        direction = " ".join(part for part in (vertical, horizontal) if part) or "TUJUAN"
        arrow = arrows[(horizontal, vertical)]
        return self.words(f"ARAH {arrow} {direction} · {target[2]}",
                          f"GO {arrow} {direction} · {target[2]}")

    def hud(self, station):
        self.box((24, 18, 1232, 113), INK, 15)
        self.text("OPENRPG", 44, 30, CREAM, self.medium)
        location = {"outdoors": "Rumah & peternakan", "house": "Ruang keluarga", "bedroom": "Kamar", "forest": "Hutan liar", "market": "Market", "reserve": f"Suaka Pokémon · {len(RESERVE_ZONES)} bioma", "coast": "Pantai pasang surut", "mountain": "Pegunungan kabut", "dungeon_hub": "Hub utara · Gym & dungeon", "local_dungeon": self.local_dungeon_name(min(10, max(1, self.life.local_dungeon_tier)))}[self.life.scene]
        self.text(location, 45, 64, MUTED, self.tiny)
        self.text(f"${self.life.money} / {'KUDA' if self.life.mounted else 'JALAN'}", 45, 92, retro.GOLD, self.small)
        minute = int(self.life.minutes)
        self.text(f"Hari {self.life.day:02} · {minute // 60:02}:{minute % 60:02}", 230, 31, CREAM)
        self.text(self.life.period + " · " + self.life.weather, 230, 60, MUTED, self.small)
        if self.mode == "game":
            self.button("+1 jam", (230, 84, 105, 34), self.skip_hour)
        else:
            self.text("T · maju 1 jam", 230, 91, GREEN, self.small)
        values = [("HP", self.life.health)] + list(self.life.stats.items())
        for i, (name, value) in enumerate(values):
            x = 456 + i * 121
            self.text(name, x, 35, CREAM, self.small)
            self.text(str(int(value)), x + 80, 35, CREAM, self.small)
            retro.meter(self.canvas, (x, 65, 107, 12), value, 100, retro.RED if name == "HP" else GREEN)
        weapon = self.life.weapon or "Tanpa senjata"
        self.text(f"{weapon} · SPACE serang · B terminal", 456, 94, CREAM, self.tiny)
        status = "PC AKTIF" if self.terminal.running else "PROMPT JALAN" if self.phone_terminal.phone_marker else "PC SIAP"
        self.text(status, 1100, 36, GREEN if self.terminal.running or self.phone_terminal.phone_marker else MUTED, self.small)
        if self.phone_unread:
            self.text("HP · PESAN BARU", 985, 61, GREEN, self.small)
        if self.mode == "game":
            self.button("Profil · U", (792, 81, 105, 35), lambda: self.open_overlay("player_profile"))
            self.button("Misi · J", (902, 81, 105, 35), lambda: self.open_overlay("daily_quests"))
            self.button("Jurnal · L", (1012, 81, 105, 35), lambda: self.open_overlay("journal"))
            self.button("Cuaca · C", (1122, 81, 115, 35), lambda: self.open_overlay("weather"))
        objective = self.tutorial_objective() if self.life.tutorial_active else None
        if objective:
            self.box((914, 145, 342, 94), INK, 8, retro.EDGE)
            self.text(self.words(f"TUTORIAL · {self.life.tutorial_step+1}/{len(TUTORIAL_STEPS)}",
                                 f"TUTORIAL · {self.life.tutorial_step+1}/{len(TUTORIAL_STEPS)}"),
                      930, 153, retro.GOLD, self.tiny)
            objective_text = objective[1] if self.life.language == "id" else objective[2]
            self.text(objective_text, 930, 177, CREAM, self.tiny)
            self.text(self.tutorial_navigation(), 930, 203, GREEN, self.tiny)
        self.box((24, 727, 1232, 54), INK, 12)
        self.text("WASD JALAN / T +1 JAM / M PETA", 44, 743, MUTED, self.tiny)
        prompt = "E · " + station[3] if station else "< Hutan     Rumah & peternakan     Market >"
        if self.life.scene == "forest" and not station:
            prompt = "Singa: 06–10 & 16–20  /  Utara: masuk suaka Pokémon"
        if self.life.scene == "reserve":
            wild = self.closest_pokemon(155)
            trainer = self.closest_trainer(112)
            rocket = next((t for t in self.reserve_trainers
                           if t.get("rocket_event") and t.get("rocket_behavior", "challenge") == "challenge"
                           and t.get("rocket_revealed", True) and t.get("cooldown", 0) <= 0
                           and math.hypot(t["x"]-self.life.x, t["y"]-self.life.y) <= 112), None)
            if wild:
                detail = self.pokemon_data(wild["id"]) or {}
                prompt = f"E · opsi Pokémon {detail.get('name', 'Pokémon liar').title()} · Lv.{wild.get('level', 5)}"
            elif rocket:
                prompt = "E · tantang Team Rocket"
            elif trainer:
                prompt = f"Space · tantang pelatih {trainer['name']}"
            else:
                prompt = "Pokémon berkeliaran · dekati, lalu E untuk opsi"
        if self.fishing:
            age = time.monotonic() - self.fishing
            prompt = "E · TARIK SEKARANG!" if age >= 2.5 else "Tunggu ikan menggigit..."
        prompt = prompt if len(prompt) < 62 else prompt[:59] + "…"
        self.text(prompt, 648, 756, GREEN, self.small, True)
        self.button("I TAS", (982, 735, 82, 38), self.open_inventory)
        self.button("P DEX", (1068, 735, 82, 38), self.open_dex)
        self.text("F1 / ESC", 1185, 743, MUTED, self.tiny, True)
        if self.life.scene == "forest" and self.wildlife.events and time.monotonic() >= self.toast_until:
            self.text(self.wildlife.events[-1], 40, 681, CREAM, self.small)
        if self.mode not in ("center", "battle", "daily_quests", "journal") and time.monotonic() < self.toast_until:
            width = min(1170, self.font.size(self.toast)[0] + 40)
            self.box(((W - width) / 2, 672, width, 41), CREAM, 10)
            self.text(self.toast, W / 2, 692, center=True)

    def open_overlay(self, mode):
        self.play_action_sound("menu-open", .24)
        self.mode = mode

    def open_settings(self):
        self.settings_return_mode = self.mode
        self.mode = "settings"

    def set_language(self, language):
        if language not in ("id", "en"):
            return
        self.life.language = language
        self.save_current()
        self.notify("Bahasa diterapkan dan disimpan.")

    def draw_settings(self):
        self.text("Pengaturan Bahasa", 242, 183, CREAM, self.medium)
        self.text("Pilih bahasa permainan", 245, 230, MUTED, self.small)
        self.button("Bahasa Indonesia", (245, 290, 375, 110), lambda: self.set_language("id"),
                    self.life.language == "id")
        self.button("English", (658, 290, 375, 110), lambda: self.set_language("en"),
                    self.life.language == "en")
        self.text("Bahasa berlaku untuk menu, HUD, misi, Pokédex, dan pesan permainan.",
                  245, 454, MUTED, self.small)
        self.button("Kembali · Esc", (245, 592, 788, 44), self.back, True)

    def title(self):
        self.outdoors()
        veil = pg.Surface((W, H), pg.SRCALPHA)
        retro.pixelate(self.canvas, 4)
        veil.fill((12, 19, 39, 222))
        self.canvas.blit(veil, (0, 0))
        for x in range(48, W, 96):
            for y in range(32, H, 96):
                pg.draw.rect(self.canvas, retro.EDGE, (x, y, 2, 2))
        self.text("OPENRPG", W / 2 + 4, 119, retro.EDGE, self.logo_font, True)
        self.text("OPENRPG", W / 2, 115, retro.GOLD, self.logo_font, True)
        self.button("Pengaturan / Settings", (978, 31, 260, 38), self.open_settings)
        self.text("-  8-BIT ADVENTURE  -", W / 2, 57, GREEN, self.small, True)
        self.text("JELAJAHI DUNIA. LANJUTKAN IDEMU.", W / 2, 174, GREEN, self.medium, True)
        self.text("Pilih teman untuk menjalani hari", W / 2, 236, CREAM, center=True)
        for i, (name, desc, _) in enumerate(CHARACTERS):
            x = 241 + i * 270
            self.box((x, 288, 250, 228), (55, 72, 59), 15, GREEN if self.selected == i else (78, 95, 79))
            self.sprite(x + 125, 410, i, 3)
            self.text(f"0{i+1} / {name.upper()}", x + 125, 448, retro.GOLD if self.selected == i else CREAM, self.medium, True)
            words = desc.split(" dan ")
            self.text(words[0], x + 125, 478, MUTED, self.small, True)
            if len(words) > 1:
                self.text("dan " + words[1], x + 125, 497, MUTED, self.small, True)
            self.buttons.append((pg.Rect(x, 288, 250, 228), lambda i=i: self.choose(i)))
        self.button("Lanjutkan hari" if self.save_path.exists() else "Mulai kehidupan", (477, 560, 326, 54), self.begin, True)
        self.text("1 / 2 / 3 · pilih karakter     Enter · mulai", W / 2, 644, CREAM, self.small, True)
        self.text("Hutan · rumah · peternakan · market · terminal asli", W / 2, 686, MUTED, self.small, True)

    def choose(self, i):
        self.selected = i

    def begin(self):
        self.life.character = self.selected
        self.mode = "game"
        pg.key.stop_text_input()
        self.notify("WASD: jalan. Kiri: hutan. Kanan: market. E: interaksi. I: inventory.")

    def draw_gate_trial_barrier(self, motion, progress=0.0):
        """Draw a compact biome obstacle and animate it clearing during traversal."""
        center_x, ground_y = 642, 493
        clear = max(0.0, min(1.0, (progress - .36) / .48))
        if motion == "surf":
            pg.draw.rect(self.canvas, (35, 112, 163), (115, 402, 1050, 110))
            for row in range(5):
                offset = int((self.frame * 2 + row * 103) % 190)
                y = 417 + row * 19
                for x in range(120 + offset, 1170, 190):
                    pg.draw.arc(self.canvas, (108, 197, 219), (x, y, 48, 14), 0, math.pi, 2)
            if clear < 1:
                for x in (center_x - 18, center_x + 31):
                    pg.draw.circle(self.canvas, (91, 155, 173), (x, 390), 26, 4)
            for index in range(5):
                self.art.gate_effect(self.canvas, "water", 220 + index * 205,
                                     427 + int(math.sin(self.frame / 5 + index) * 9),
                                     int(self.frame / 3 + index * 2), 1.4)
        elif motion in ("rock", "earth", "log"):
            for index, x in enumerate((center_x - 43, center_x + 12, center_x - 4)):
                wobble = int(math.sin(self.frame / 5 + index) * 4 * (1 - clear))
                y = ground_y - 38 - (index % 2) * 22 + wobble
                if clear < .9:
                    if motion == "log":
                        pg.draw.rect(self.canvas, (93, 61, 42), (x - 47, y - 10, 94, 33), border_radius=11)
                        pg.draw.circle(self.canvas, (184, 129, 70), (x - 45, y + 7), 16)
                        pg.draw.circle(self.canvas, (72, 47, 37), (x - 45, y + 7), 16, 3)
                    else:
                        rock = self.art.rock_sprites[(index * 3 + int(self.frame / 16)) % len(self.art.rock_sprites)]
                        image = pg.transform.rotozoom(rock, wobble * 1.7, 1.45)
                        self.canvas.blit(image, image.get_rect(center=(x, y)))
        elif motion == "vine":
            for index, x in enumerate((center_x - 35, center_x, center_x + 36)):
                sway = int(math.sin(self.frame / 7 + index) * 12 * (1 - clear))
                pg.draw.line(self.canvas, (72, 145, 78), (x + sway, 360),
                             (x - sway, ground_y), 9)
                for y in range(380, 475, 34):
                    pg.draw.line(self.canvas, (145, 193, 92), (x + sway, y),
                                 (x + sway + (18 if index % 2 else -18), y - 10), 4)
                self.art.gate_effect(self.canvas, "plant", x + sway, 418 + index * 11,
                                     int(self.frame / 4 + index * 3), 1.45)
        elif motion in ("lava", "steam", "fire"):
            color = (232, 87, 42) if motion != "steam" else (197, 211, 211)
            pg.draw.rect(self.canvas, (83, 54, 60), (115, 445, 1050, 58))
            for index in range(15):
                x = 150 + index * 70
                y = 462 + int(math.sin(self.frame / 5 + index) * 13)
                pg.draw.circle(self.canvas, color, (x, y), 8 + index % 3 * 2)
                if motion == "lava":
                    pg.draw.circle(self.canvas, (255, 190, 72), (x + 4, y - 5), 4)
                self.art.gate_effect(self.canvas, "fire" if motion == "lava" else "smoke", x, y - 24,
                                     int(self.frame / 3 + index), 1.7)
        elif motion in ("ice", "snow"):
            for index, x in enumerate((center_x - 42, center_x, center_x + 43)):
                height = (64, 102, 77)[index]
                points = [(x - 29, ground_y), (x - 17, ground_y - height + 24),
                          (x, ground_y - height), (x + 11, ground_y - height + 31),
                          (x + 29, ground_y)]
                if clear < .9:
                    pg.draw.polygon(self.canvas, (138, 192, 215), points)
                    pg.draw.polygon(self.canvas, (217, 238, 240), points, 2)
                    self.art.gate_effect(self.canvas, "ice", x, ground_y - height // 2,
                                         int(self.frame / 4 + index * 2), 1.35)
        elif motion in ("wind", "fly"):
            for index in range(7):
                y = 362 + index * 20
                offset = int((self.frame * 4 + index * 79) % 220)
                x = 150 + offset
                pg.draw.line(self.canvas, (151, 203, 218), (x, y), (x + 82, y - 15), 3)
                self.art.gate_effect(self.canvas, "wind", x + 38, y - 7,
                                     int(self.frame / 4 + index), 1.45)
        elif motion in ("mud", "mist"):
            pg.draw.rect(self.canvas, (74, 78, 58), (134, 430, 1010, 76), border_radius=18)
            for index in range(16):
                x = 170 + index * 61
                y = 450 + int(math.sin(self.frame / 6 + index) * 12)
                pg.draw.circle(self.canvas, (119, 111, 72), (x, y), 12 + index % 3 * 4)
                if motion == "mist":
                    self.art.gate_effect(self.canvas, "smoke", x, y - 54,
                                         int(self.frame / 4 + index), 1.3)
        elif motion in ("crystal", "seal"):
            for index, x in enumerate((center_x - 42, center_x, center_x + 42)):
                top = 355 + (index % 2) * 20
                points = [(x, top), (x + 24, top + 42), (x + 8, ground_y),
                          (x - 19, ground_y - 10), (x - 29, top + 46)]
                if clear < .9:
                    pg.draw.polygon(self.canvas, (123, 144, 204), points)
                    pg.draw.polygon(self.canvas, (207, 207, 245), points, 2)
                    self.art.gate_effect(self.canvas, "ice", x, top + 51,
                                         int(self.frame / 4 + index), 1.3)
            pg.draw.circle(self.canvas, (168, 171, 226), (center_x, 414), 88, 2)
        else:
            pg.draw.rect(self.canvas, (104, 123, 109), (center_x - 40, 375, 80, 120), 4)

    def draw_gate_trial_action_fx(self, trial, pokemon_x, obstacle_x, obstacle_y):
        """Animate a readable cause-and-effect action over the local CC0 FX."""
        spec = trial["spec"]
        motion = spec["motion"]
        tick = int(self.frame / 2)
        progress = max(0.0, min(1.0, trial["timer"] / 2.8))
        if motion in ("rock", "earth", "crystal", "seal"):
            for index in range(6):
                t = (progress * 2.5 + index / 6) % 1
                x = pokemon_x + (obstacle_x - pokemon_x) * t
                y = obstacle_y - 18 - abs(math.sin(t * math.pi)) * 45
                self.art.gate_effect(self.canvas, "rock", x, y, tick + index, 1.35)
            if motion == "rock":
                self.art.gate_item(self.canvas, "pickaxe", pokemon_x + 21,
                                   obstacle_y - 50, 3.1, int(math.sin(self.frame / 2) * 42))
        elif motion == "log":
            self.art.gate_item(self.canvas, "axe", pokemon_x + 28, obstacle_y - 48,
                               3.4, int(math.sin(self.frame / 2) * 46))
            for index in range(11):
                theta = self.frame / 4 + index * .57
                self.art.gate_effect(self.canvas, "wood", obstacle_x + math.cos(theta) * 44,
                                     obstacle_y - 20 + math.sin(theta) * 27, tick + index, 1.8)
        elif motion in ("surf", "mud", "lava", "steam"):
            for index in range(7):
                x = pokemon_x + (obstacle_x - pokemon_x) * (index / 7)
                y = obstacle_y - 30 + int(math.sin(self.frame / 3 + index) * 17)
                self.art.gate_effect(self.canvas, "water", x, y, tick + index, 1.8)
            if motion == "lava":
                for index in range(6):
                    self.art.gate_effect(self.canvas, "smoke", obstacle_x + index * 21 - 58,
                                         obstacle_y - 56 - index % 2 * 15, tick + index, 1.25)
        elif motion in ("vine", "ice", "snow"):
            effect = "fire" if motion in ("ice", "snow") else "plant"
            for index in range(6):
                self.art.gate_effect(self.canvas, effect, obstacle_x + (index - 3) * 23,
                                     obstacle_y - 55 + int(math.sin(self.frame / 4 + index) * 16),
                                     tick + index, 1.65)
        elif motion in ("wind", "fly"):
            for index in range(10):
                self.art.gate_effect(self.canvas, "wind", pokemon_x + index * 39,
                                     obstacle_y - 65 - int(math.sin(self.frame / 5 + index) * 25),
                                     tick + index, 1.65)
        else:
            self.art.gate_effect(self.canvas, "explode", obstacle_x, obstacle_y - 42, tick, 2.0)

    def draw_gate_trial(self):
        trial = self.gate_trial
        if not trial:
            self.mode = "game"
            return
        spec = trial["spec"]
        zone = RESERVE_ZONES[trial["target_index"]]
        biome_colors = {
            "coast": (19, 67, 104), "deepsea": (15, 47, 79), "cave": (48, 53, 72),
            "volcano": (78, 42, 47), "snow": (70, 102, 123), "forest": (27, 65, 48),
            "ancient_forest": (26, 61, 45), "desert": (111, 78, 49), "badlands": (91, 58, 50),
            "swamp": (39, 65, 58), "sky": (55, 89, 127), "crystal": (59, 52, 98),
            "dragon_valley": (79, 55, 71), "legendary_ruins": (57, 58, 87),
            "mountain": (65, 79, 86), "meadow": (45, 79, 56)}
        base = biome_colors.get(zone["biome"], (34, 53, 65))
        self.canvas.fill(base)
        pg.draw.rect(self.canvas, (16, 23, 41), (34, 31, 1212, 738), 3)
        for index in range(18):
            x = (index * 97 + 35) % W
            y = 215 + (index % 6) * 59
            pg.draw.circle(self.canvas, tuple(min(255, value + 18) for value in base), (x, y), 2)
        self.text(self.words("GERBANG PENJELAJAH", "SANCTUARY GATE TRIAL"), W / 2, 57,
                  retro.GOLD, self.medium, True)
        self.text(f"{zone['name']}  ·  {zone['biome'].replace('_', ' ').title()}", W / 2, 101,
                  CREAM, self.small, True)
        self.box((106, 139, 1068, 64), INK, 9)
        self.text(f"{spec['name'][self.life.language == 'en']}  ·  {spec['hint'][self.life.language == 'en']}",
                  W / 2, 171, CREAM, self.small, True)
        self.draw_gate_trial_barrier(spec["motion"],
                                     trial["timer"] / 2.8 if trial["phase"] == "action" else 0)
        if trial["phase"] == "choose":
            candidates = trial["candidates"]
            if candidates:
                ident = candidates[trial["selected"]]
                details = self.pokemon_data(ident) or {}
                pokemon_name = details.get("name", f"Pokémon #{ident}").title()
                types = pokemon_db.type_catalog().get(ident, ())
                type_text = " / ".join(kind.title() for kind in types)
                self.box((302, 533, 676, 100), INK, 12, retro.GOLD)
                sprite = self.pokemon_surface(ident, 74)
                if sprite:
                    self.canvas.blit(sprite, sprite.get_rect(midleft=(345, 582)))
                self.text(f"{pokemon_name}  ·  Lv.{self.pokemon_level(ident)}", 410, 552,
                          CREAM, self.small)
                self.text(type_text, 410, 588, GREEN, self.small)
                self.button("‹", (304, 558, 36, 48), lambda: self.select_gate_trial_pokemon(-1))
                self.button("›", (940, 558, 36, 48), lambda: self.select_gate_trial_pokemon(1))
                self.text(f"{trial['selected'] + 1} / {len(candidates)}", W / 2, 613,
                          MUTED, self.tiny, True)
                self.button(self.words("Coba Pokémon ini  ·  Enter", "Try this Pokémon  ·  Enter"),
                            (250, 667, 520, 55), self.begin_gate_trial_action, True)
            else:
                self.box((282, 546, 716, 76), INK, 10, (202, 104, 89))
                self.text(self.words("Tidak ada Pokémon sehat untuk mencoba rintangan.",
                                     "There is no healthy Pokémon to try this obstacle."), W / 2, 568,
                          retro.GOLD, self.small, True)
                self.text(self.words("Pulihkan Pokémon yang cocok atau tangkap di area sebelumnya.",
                                     "Heal a matching Pokémon or catch one in an earlier area."), W / 2, 598,
                          MUTED, self.tiny, True)
                self.button(self.words("Kembali ke suaka sebelumnya · Esc", "Return to previous sanctuary · Esc"),
                            (384, 667, 512, 55), self.cancel_gate_trial, True)
            if trial.get("feedback"):
                self.box((784, 667, 350, 55), (102, 52, 57), 8, (218, 110, 91))
                self.text(trial["feedback"], 959, 680, CREAM, self.tiny, True)
                self.text(self.words(f"HP trainer: {int(self.life.health)} · salah {trial['mistakes']}×",
                                     f"Trainer HP: {int(self.life.health)} · wrong {trial['mistakes']}×"),
                          959, 706, retro.GOLD, self.tiny, True)
            self.text(self.words("Pilih sendiri Pokémon yang ingin mencoba. Rintangan ini hanya perlu dilewati sekali.",
                                 "Choose which Pokémon will try. This obstacle only needs to be cleared once."),
                      W / 2, 734, MUTED, self.tiny, True)
        else:
            ident = trial.get("pokemon_id")
            progress = max(0.0, min(1.0, trial["timer"] / 2.8))
            px = int(200 + progress * 880)
            ground = 474 + int(math.sin(self.frame / 3) * 3)
            sprite = self.pokemon_surface(ident, 112) if ident else None
            if sprite:
                self.canvas.blit(sprite, sprite.get_rect(midbottom=(px, ground)))
            if spec["motion"] in ("surf", "fly"):
                char_y = ground - 59
            else:
                char_y = ground + 4
            self.art.character(self.canvas, px - 36, char_y, self.life.character, 1.2,
                               self.frame, True, "right")
            self.draw_gate_trial_action_fx(trial, px, 642, 444)
            for index in range(9):
                theta = self.frame / 4 + index * math.tau / 9
                radius = 39 + int(7 * math.sin(self.frame / 3 + index))
                color = TYPE_MOVES.get(spec["types"][0], TYPE_MOVES["normal"])[1]
                particle = (int(px + math.cos(theta) * radius),
                            int(411 + math.sin(theta) * 31))
                pg.draw.circle(self.canvas, color, particle, 3 + index % 2)
            self.text(self.words(f"Pokémon sedang {spec['action'][0]}…",
                                 f"Pokémon is {spec['action'][1]}…"), W / 2, 585,
                      retro.GOLD, self.small, True)
            pg.draw.rect(self.canvas, INK, (347, 650, 586, 18))
            pg.draw.rect(self.canvas, GREEN, (350, 653, int(580 * progress), 12))

    def overlay(self):
        self.buttons = []
        if self.mode == "gate_trial":
            self.draw_gate_trial()
            return
        if self.mode == "map":
            self.draw_global_map()
            return
        if self.mode == "tutorial_map":
            self.draw_tutorial_map()
            return
        veil = pg.Surface((W, H), pg.SRCALPHA)
        veil.fill((18, 29, 23, 205)); self.canvas.blit(veil, (0, 0))
        if self.mode == "pokemon_info":
            # The Pokédex detail panel includes long habitat text and visual
            # evolution paths; give those details a wider frame and margin.
            self.box((70, 130, 1140, 550), INK, 18)
        elif self.mode == "player_profile":
            self.box((205, 151, 870, 556), INK, 18)
        else:
            self.box((205, 151, 870, 507), INK, 18)
        if self.mode == "settings":
            self.draw_settings()
        elif self.mode == "phone":
            self.draw_phone()
        elif self.mode == "dex":
            self.draw_dex()
        elif self.mode == "center":
            self.draw_center()
        elif self.mode == "hospitality":
            self.draw_hospitality()
        elif self.mode == "daily_quests":
            self.draw_daily_quests()
        elif self.mode == "journal":
            self.draw_journal()
        elif self.mode == "player_profile":
            self.draw_player_profile()
        elif self.mode == "home_decor":
            self.draw_home_decor()
        elif self.mode == "secret_puzzle":
            self.draw_secret_puzzle()
        elif self.mode == "battle":
            self.draw_pokemon_battle()
        elif self.mode == "dead":
            self.draw_dead_screen()
        elif self.mode == "evolution":
            self.draw_evolution()
        elif self.mode == "encounter":
            self.draw_encounter()
        elif self.mode == "pokemon_info":
            self.draw_pokemon_info()
        elif self.mode == "interaction_picker":
            self.draw_interaction_picker()
        elif self.mode == "inventory":
            self.draw_bag_icon(250, 198, 26)
            self.text("TAS & INVENTARIS", 272, 183, CREAM, self.medium)
            self.text(f"Koin {self.life.money}  ·  HP {int(self.life.health)}/100  ·  Buruan {self.life.kills}", 245, 222, GREEN, self.small)
            for i, (name, count) in enumerate(self.life.bag.items()):
                x, y = 248 + (i // 6) * 220, 251 + (i % 6) * 44
                self.box((x - 8, y - 7, 204, 36), (48, 64, 52), 5)
                self.draw_item_icon(name, x + 11, y + 10)
                self.text(name, x + 29, y, CREAM if count else MUTED, self.small)
                self.text(f"×{count}", x + 163, y, GREEN if count else MUTED, self.small)
            self.text("Pasang senjata", 721, 245, CREAM)
            self.button("Tombak · 1", (716, 285, 317, 43), lambda: self.notify(self.life.equip("Tombak")), self.life.weapon == "Tombak")
            self.button("Busur · 2", (716, 337, 317, 43), lambda: self.notify(self.life.equip("Busur")), self.life.weapon == "Busur")
            self.button("Lepas senjata · 3", (716, 389, 317, 43), lambda: self.notify(self.life.equip("")))
            self.button("Pakai obat · H", (716, 441, 317, 43), self.use_healing_item)
            self.button("Makan bekal", (716, 493, 317, 43), self.eat_from_bag)
            self.text("Beli senjata di market. Busur memerlukan panah.", 248, 552, MUTED, self.small)
            self.button("Kembali · Esc / I", (245, 592, 788, 44), self.back, True)
        elif self.mode == "shop":
            self.draw_shop()
        elif self.mode == "weather":
            self.text("Cuaca & waktu", 242, 183, CREAM, self.medium)
            self.text("Otomatis berubah setiap tiga jam di dunia game.", 245, 235, MUTED)
            for i, weather in enumerate(("Cerah", "Berawan", "Hujan", "Salju", "Otomatis")):
                self.button(weather, (245, 286 + i * 53, 788, 44), lambda w=weather: self.set_weather(w), self.life.weather == weather)
            self.button("Kembali · Esc", (245, 592, 788, 44), self.back)
        elif self.mode == "help":
            self.text("Hidup, menjelajah, bekerja", 242, 183, CREAM, self.medium)
            lines = ["WASD / panah jalan · E interaksi · I tas · H obat.",
                     "Kiri hutan, kanan market; E di rumah, dapur, meja, kebun, dan kolam.",
                     "Kebun tanam/siram/panen; beri sayur ke ayam. Kolam: tunggu TARIK lalu E.",
                     "Beli senjata di market; I / 1 / 2 pasang. Space menyerang ke arah hadap.",
                     "Singa dan hyena berburu pada waktunya; satwa lain bisa melawan atau kabur.",
                     "R dekat kuda naik/turun · T +1 jam · C cuaca · mati bangun di tempat tidur.",
                     "Market buka 06–22. E bicara dengan NPC; jual hasil kebun, ternak, dan buruan.",
                     "PC: ketik opencode untuk AI. Terminal.app membuka sesi PC yang sama.",
                     "B: buka terminal bersama dari mana saja; layarnya sama dengan PC dan Terminal.app.",
                     "Esc meninggalkan PC · F10 Escape shell · Ctrl/Cmd+V paste.",
                     "P: Pokédex. M: peta global · roda / +/- zoom · klik bioma untuk fokus.",
                     "Dekati Pokémon di suaka, tekan E untuk memilih duel atau info Pokédex.",
                     "Duel: panah · A dekat · S bertahan · Q stun · W dekat · E jauh · R ultimate · Tab ganti.",
                     "Pokémon Center: pilih hingga 3 aktif, pulihkan HP, naik level, dan evolusi.",
                     "Pokémon KO diganti otomatis; pulihkan di Center. Pelatih Lv.>20 bawa 3 lawan.",
                     "Semakin jauh dari suaka, Pokémon yang ditemui semakin langka dan kuat."]
            for i, line in enumerate(lines):
                self.text(line, 245, 231 + i * 22, CREAM, self.small)
            self.button("Mengerti · Esc / F1", (245, 592, 788, 44), self.back, True)
        else:
            self.text("Istirahat sebentar", 242, 183, CREAM, self.medium)
            self.text("Dunia dijeda. Terminal dan AI tetap berjalan.", 245, 251, MUTED)
            self.button("Lanjut bermain", (245, 316, 788, 49), self.back, True)
            self.button("Profil / New Game / Load", (245, 377, 788, 49), self.to_title)
            self.button("Simpan & keluar", (245, 438, 788, 49), self.quit)
            self.button("Pengaturan / Settings", (245, 499, 788, 43), self.open_settings)
            self.text("Keluar aplikasi menutup terminal dan pekerjaan dalam sesi tersebut.", 245, 537, CREAM, self.small)
        if self.mode not in ("center", "battle", "daily_quests", "journal") and time.monotonic() < self.toast_until:
            width = min(1170, self.font.size(self.toast)[0] + 40)
            self.box(((W - width) / 2, 678, width, 39), CREAM, 10)
            self.text(self.toast, W / 2, 697, center=True)

    def draw_phone(self):
        self.text("PONSEL · PROMPT OPENCODE", 242, 183, CREAM, self.medium)
        self.text("Shell yang sama dapat dipakai dari PC, ponsel, dan Terminal.app.", 245, 231, MUTED, self.small)
        self.box((245, 273, 788, 66), (29, 39, 36), 8, (90, 118, 91))
        shown = self.phone_input[-92:]
        self.text("> " + shown + ("▏" if int(time.monotonic() * 2) % 2 else ""), 259, 293, GREEN, self.small)
        self.text(self.phone_status, 245, 355, GREEN if not self.phone_terminal.phone_marker else (232, 192, 112), self.small)
        if self.phone_terminal.running:
            lines = [line.rstrip() for line in self.phone_terminal.screen.display if line.strip()]
            self.text("TAMPILAN TERMINAL BERSAMA", 245, 396, CREAM, self.small)
            for row, line in enumerate(lines[-6:]):
                self.text(line[:99], 245, 423 + row * 24, (198, 208, 193), self.small)
        if self.phone_complete:
            self.text("✓ Respons selesai · notifikasi ponsel diterima", 245, 570, GREEN)
        self.text("Contoh: opencode run dijalankan otomatis · awali ! untuk perintah shell biasa.", 245, 592, MUTED, self.small)
        self.button("Kirim prompt", (245, 624, 255, 40), self.submit_phone_prompt, True)
        self.button("Buka Terminal.app", (511, 624, 270, 40), self.open_native_terminal)
        self.button("Tutup · B / Esc", (792, 624, 241, 40), self.back)

    def draw_daily_quests(self):
        self.life.ensure_daily_quests()
        self.text(f"MISI HARIAN · HARI {self.life.day:02}", 242, 183, CREAM, self.medium)
        self.text("Selesaikan kegiatan hari ini untuk mendapat koin bonus.", 245, 226, MUTED, self.small)
        for index, quest in enumerate(self.life.daily_quests):
            y = 276 + index * 91
            self.box((245, y, 788, 76), (29, 39, 36), 8, (69, 91, 74))
            self.text(quest["title"], 263, y + 11, CREAM, self.small)
            progress = int(quest.get("progress", 0))
            target = int(quest["target"])
            complete = quest.get("claimed", False)
            self.text("SELESAI" if complete else f"{progress}/{target}", 263, y + 43,
                      GREEN if complete else MUTED, self.tiny)
            retro.meter(self.canvas, (355, y + 46, 390, 10), progress, target,
                        GREEN if complete else retro.GOLD)
            self.text(f"+{quest['reward']} KOIN", 875, y + 28,
                      retro.GOLD if complete else CREAM, self.small, True)
        self.text(f"Tim: {len(self.life.pokemon_party)}/6 · Aktif: {len(self.life.pokemon_active)}/3",
                  245, 558, MUTED, self.small)
        self.button("Kembali · Esc / J", (245, 592, 788, 44), self.back, True)

    def draw_journal(self):
        biome = biome_at(self.life.scene, self.life.x, self.life.y)
        title = STORIES.get(biome, STORIES["meadow"])
        title_text = title[0 if self.life.language == "id" else 1]
        self.text(self.words("JURNAL PENJELAJAH", "EXPLORER JOURNAL"), 242, 183, CREAM, self.medium)
        self.text(self.words(f"Lokasi: {title_text} · {len(self.life.discovered_biomes)}/16 bioma ditemukan",
                             f"Current: {title_text} · {len(self.life.discovered_biomes)}/16 biomes found"),
                  245, 225, GREEN, self.small)
        entries = [name for name in BIOMES if name in self.life.discovered_biomes]
        pages = max(1, math.ceil(max(1, len(entries)) / 3))
        self.journal_page %= pages
        visible = entries[self.journal_page * 3:self.journal_page * 3 + 3]
        for index, name in enumerate(visible):
            data = STORIES[name]
            progress = self.life.biome_stories.get(name, {"progress": 0, "completed": False})
            y = 266 + index * 76
            self.box((245, y, 788, 64), retro.PANEL, 7)
            self.text(data[0 if self.life.language == "id" else 1], 260, y + 7, CREAM, self.small)
            self.text(data[2 if self.life.language == "id" else 3], 260, y + 34, MUTED, self.tiny)
            amount = int(progress.get("progress", 0))
            status = self.words("SELESAI", "COMPLETE") if progress.get("completed") else f"{amount}/{data[5]}"
            self.text(status, 980, y + 20, GREEN if progress.get("completed") else retro.GOLD, self.tiny, True)
        self.text(self.words(f"Rahasia ditemukan: {len(self.life.discovered_secrets)}/16",
                             f"Secrets found: {len(self.life.discovered_secrets)}/16"), 245, 510, CREAM, self.small)
        badges = self.life.badges[-4:]
        badge_text = "  ·  ".join(badges) if badges else self.words("Belum ada lencana", "No badges yet")
        self.text(self.words("Lencana:", "Badges:") + " " + badge_text, 245, 541, retro.GOLD, self.tiny)
        active_event = self.life.world_event
        event_label = active_event.get("title", self.words("Belum ada event aktif", "No active event"))
        self.text(self.words("Event:", "Event:") + " " + event_label, 245, 566, MUTED, self.tiny)
        cosmetic = next((row for row in COLLECTION_COSMETICS if row[1] == self.life.active_cosmetic), None)
        cosmetic_label = (cosmetic[2 if self.life.language == "en" else 3] if cosmetic else
                          self.words("Belum terbuka", "Locked"))
        self.text(self.words("Kosmetik aktif:", "Active cosmetic:") + " " + cosmetic_label,
                  245, 586, GREEN, self.tiny)
        self.button("<", (245, 602, 55, 38), lambda: setattr(self, "journal_page", (self.journal_page - 1) % pages))
        self.text(f"{self.journal_page + 1}/{pages}", 318, 610, MUTED, self.tiny)
        self.button(">", (360, 602, 55, 38), lambda: setattr(self, "journal_page", (self.journal_page + 1) % pages))
        unlocked_cosmetics = [row[1] for row in COLLECTION_COSMETICS if row[1] in self.life.cosmetics]
        self.button(self.words("Ganti kosmetik", "Cycle cosmetic"), (427, 600, 200, 42),
                    self.cycle_cosmetic, bool(unlocked_cosmetics))
        self.button(self.words("Kembali · Esc / L", "Back · Esc / L"), (642, 600, 391, 42), self.back, True)

    def cycle_cosmetic(self):
        unlocked = [row[1] for row in COLLECTION_COSMETICS if row[1] in self.life.cosmetics]
        if not unlocked:
            # Give every profile one starter cosmetic so this control has an
            # immediate, visible effect; later cosmetics still come from milestones.
            starter = COLLECTION_COSMETICS[0][1]
            self.life.cosmetics.append(starter)
            self.life.active_cosmetic = starter
            self.save_current()
            self.play_action_sound("ui-confirm", .2)
            self.notify(self.words("Kosmetik Mahkota Daun dibuka dan dipakai!",
                                   "Leaf Crown cosmetic unlocked and equipped!"))
            return
        try:
            index = unlocked.index(self.life.active_cosmetic)
        except ValueError:
            index = -1
        self.life.active_cosmetic = unlocked[(index + 1) % len(unlocked)]
        self.save_current()
        self.play_action_sound("ui-confirm", .2)

    def draw_secret_puzzle(self):
        biome = self.secret_puzzle or "meadow"
        question, choices, answer = PUZZLES[biome]
        prompt = question[0 if self.life.language == "id" else 1]
        self.text(self.words("TEKA-TEKI TEMPAT RAHASIA", "HIDDEN PLACE RIDDLE"), 242, 183, CREAM, self.medium)
        self.text(self.words("Pilih jawaban dengan angka 1–3 atau panah + Enter.",
                             "Choose with 1–3 or use arrows + Enter."), 245, 231, MUTED, self.small)
        self.box((245, 286, 788, 93), retro.PANEL, 8)
        self.text(prompt, 270, 319, retro.GOLD, self.font)
        for index, choice in enumerate(choices):
            label = f"{index+1} · {choice}"
            self.button(label, (245, 407 + index * 58, 788, 46),
                        lambda i=index: self.resolve_secret_puzzle(i))
        if self.secret_feedback:
            self.text(self.secret_feedback, 640, 594, retro.RED, self.small, True)
        self.button(self.words("Kembali · Esc", "Back · Esc"), (245, 636, 788, 38), self.back)

    def dex_entries(self):
        query = self.dex_query.lower().strip()
        types_by_id = pokemon_db.type_catalog()
        entries = []
        for entry in self.pokedex.catalog:
            try:
                ident = int(entry.get("id", 0))
            except (AttributeError, TypeError, ValueError):
                continue
            name = str(entry.get("name", ""))
            if query and query not in name.lower() and query != str(ident):
                continue
            if self.dex_type_filter != "all" and self.dex_type_filter not in types_by_id.get(ident, ()):
                continue
            if ident > 0:
                entries.append({**entry, "id": ident, "name": name or f"Pokémon #{ident}"})
        return entries

    def cycle_type_filter(self, attribute, step):
        filters = ("all", *TYPE_EMOJI.keys())
        current = getattr(self, attribute, "all")
        try:index = filters.index(current)
        except ValueError:index = 0
        setattr(self, attribute, filters[(index + step) % len(filters)])
        if attribute == "dex_type_filter":
            self.dex_page = 0
            entries = self.dex_entries()
            if entries:
                if not any(item["id"] == self.dex_selected for item in entries):
                    self.select_dex(entries[0]["id"])
            else:
                self.dex_detail = None
        elif attribute == "center_type_filter":
            visible = self.center_filtered_party()
            if visible and not any(index == self.center_selected for index, _ in visible):
                self.center_selected = visible[0][0]

    def type_filter_label(self, value):
        if value == "all":
            return self.words("SEMUA TIPE", "ALL TYPES")
        return f"{TYPE_EMOJI.get(value, '✨')} {value.upper()}"

    def select_dex(self, pokemon_id):
        try:
            pokemon_id = int(pokemon_id)
        except (TypeError, ValueError):
            return
        entries = self.dex_entries()
        if not any(item["id"] == pokemon_id for item in entries):
            return
        self.dex_selected = pokemon_id
        self.dex_detail = self.pokemon_data(self.dex_selected)
        self.pokedex.request(self.dex_selected)
        self.pokedex.request_species(self.dex_selected)
        selected_index = next((i for i, item in enumerate(entries)
                               if item["id"] == self.dex_selected), None)
        if selected_index is not None:
            self.dex_page = selected_index // 8

    def move_dex_selection(self, offset):
        entries = self.dex_entries()
        if not entries:
            return
        current = next((i for i, item in enumerate(entries)
                        if item["id"] == self.dex_selected), min(self.dex_page * 8, len(entries) - 1))
        target = max(0, min(len(entries) - 1, current + offset))
        self.select_dex(entries[target]["id"])

    def draw_dex(self):
        self.draw_pokedex_icon(252, 198, 26)
        self.text("POKÉDEX · SEMUA SPESIES", 274, 183, CREAM, self.medium)
        self.text(f"{len(self.life.pokemon_caught)} tertangkap · {len(self.life.pokemon_seen)} terlihat · {len(self.pokedex.catalog)} spesies", 651, 190, GREEN, self.small)
        self.box((245, 220, 294, 38), (29, 39, 36), 7)
        self.text("Cari / Search: " + self.dex_query + "▏", 257, 228, GREEN, self.small)
        self.button("◀", (547, 220, 38, 38), lambda: self.cycle_type_filter("dex_type_filter", -1))
        self.button(self.type_filter_label(self.dex_type_filter), (587, 220, 150, 38),
                    lambda: self.cycle_type_filter("dex_type_filter", 1), self.dex_type_filter != "all")
        self.button("▶", (739, 220, 38, 38), lambda: self.cycle_type_filter("dex_type_filter", 1))
        self.button(f"Poké Ball ×5 · {BUY['Pokeball'] * 5}", (779, 220, 254, 38),
                    lambda: self.trade("Pokeball", True, 5))
        entries = self.dex_entries()
        pages = max(1, (len(entries) + 7) // 8)
        self.dex_page = max(0, min(pages - 1, int(self.dex_page)))
        start = self.dex_page * 8
        visible = entries[start:start + 8]
        for row, item in enumerate(visible):
            y = 269 + row * 39
            selected = item["id"] == self.dex_selected
            self.box((245, y, 390, 35), (69, 91, 68) if selected else (43, 57, 49), 5)
            self.pokedex.request(item["id"])
            sprite = self.pokemon_surface(item["id"], 27)
            if sprite:
                self.canvas.blit(sprite, (252, y + 4))
            else:
                pg.draw.rect(self.canvas, (70, 92, 77), (253, y + 6, 24, 23))
                self.text("…", 265, y + 8, MUTED, self.tiny, True)
            status = "●" if item["id"] in self.life.pokemon_caught else "○" if item["id"] in self.life.pokemon_seen else "·"
            self.text(f"{status} #{item['id']:04} {item['name'].title()}", 286, y + 6, CREAM if selected else MUTED, self.small)
            self.buttons.append((pg.Rect(245, y, 390, 35), lambda ident=item["id"]: self.select_dex(ident)))
        if not self.pokedex.catalog:
            self.text("Mengunduh katalog resmi PokéAPI…", 264, 320, GREEN)
        self.button("←", (245, 594, 54, 39), lambda: self.change_dex_page(-1))
        self.text(f"{self.type_filter_label(self.dex_type_filter)} · {self.dex_page + 1}/{max(1, (len(entries) + 7) // 8)}", 313, 603, CREAM, self.small)
        self.button("→", (509, 594, 54, 39), lambda: self.change_dex_page(1))
        self.button("Kembali · P / Esc", (661, 594, 372, 39), self.back)
        detail = self.dex_detail
        if detail and detail.get("id") == self.dex_selected:
            ident = detail["id"]
            species = self.pokedex.species.get(ident)
            sprite = self.poke_surfaces.get(ident)
            if sprite:
                self.canvas.blit(sprite, sprite.get_rect(center=(814, 327)))
            name = detail.get("name", "Pokémon").title()
            self.text(f"#{ident:04} {name}", 851, 392, CREAM, self.medium, True)
            types = " · ".join(t["type"]["name"].title() for t in detail.get("types", []))
            self.text(types or "Memuat tipe…", 851, 429, GREEN, center=True)
            self.text("Tertangkap" if ident in self.life.pokemon_caught else "Belum tertangkap", 851, 465, MUTED, center=True)
        else:
            self.text("Pilih spesies untuk memuat data dan sprite.", 840, 387, MUTED, self.small, True)
        if detail and detail.get("id") == self.dex_selected:
            height = detail.get("height")
            weight = detail.get("weight")
            dimensions = (f"Tinggi {height / 10:.1f} m · Berat {weight / 10:.1f} kg"
                          if isinstance(height, (int, float)) and isinstance(weight, (int, float))
                          else "Memuat data ukuran…")
            self.text(dimensions, 840, 475, MUTED, self.tiny, True)
            self.text(self.words("RANTAI EVOLUSI", "EVOLUTION CHAIN"), 650, 496, GREEN, self.tiny)
            self.draw_evolution_chain(ident, 650, 509, 380, 65, max_rows=1, icon_size=26, font=self.tiny)
        self.text("↑↓ pilih · ←→ halaman · Enter detail · Tab tombol", 245, 568, MUTED, self.tiny)

    def draw_encounter(self):
        pokemon = self.encounter_target
        if not pokemon:
            self.text("Tidak ada Pokémon di sekitar.", W // 2, 310, CREAM, self.medium, True)
            self.button("Kembali · Esc", (445, 520, 390, 48), self.back)
            return
        ident = pokemon["id"]
        detail = self.pokemon_data(ident) or {}
        name = detail.get("name", f"Pokémon #{ident}").title()
        level = pokemon.get("level", 5)
        hp = self.base_stat(detail, "hp", 45) + int(level * 2.2)
        types = " · ".join(item["type"]["name"].title() for item in detail.get("types", [])) or "Memuat data tipe…"
        self.text("PERTEMUAN POKÉMON", 242, 183, CREAM, self.medium)
        self.text("Ia menyadari kehadiranmu…", 244, 218, MUTED, self.small)
        sprite = self.pokemon_surface(ident, 144)
        if sprite:
            self.canvas.blit(sprite, (275, 276))
        self.text(name, 505, 294, CREAM, self.big)
        self.text(f"Lv. {level}   ·   HP {hp}/{hp}", 510, 356, GREEN, self.medium)
        self.text(types, 510, 397, CREAM)
        self.text("Cry PokéAPI · suara akan diputar lagi saat duel dimulai", 510, 432, MUTED, self.small)
        self.button("ⓘ  Lihat info Pokédex", (510, 485, 250, 52), self.show_encounter_info,
                    self.encounter_choice == 0)
        self.button("⚔  Bertarung", (774, 485, 260, 52), self.choose_encounter_battle,
                    self.encounter_choice == 1)
        self.button("Dengarkan cry", (510, 551, 250, 42), lambda: self.play_pokemon_cry(ident))
        self.button("Tutup · Esc", (774, 551, 260, 42), self.back)
        self.text("← → pilih · Enter konfirmasi · I info · F bertarung · Esc tutup",
                  W // 2, 618, MUTED, self.tiny, True)

    def draw_pokemon_info(self):
        pokemon = self.encounter_target
        if not pokemon:
            self.back()
            return
        ident = pokemon["id"]
        detail = self.pokemon_data(ident) or {}
        species = self.pokedex.species.get(ident)
        name = detail.get("name", f"Pokémon #{ident}").title()
        self.text("POKÉDEX · DATA RESMI POKÉAPI", 242, 183, CREAM, self.medium)
        sprite = self.pokemon_surface(ident, 150)
        if sprite:
            self.canvas.blit(sprite, (274, 252))
        self.text(f"#{ident:04}  {name}", 488, 247, CREAM, self.medium)
        types = " · ".join(item["type"]["name"].title() for item in detail.get("types", [])) or "Memuat tipe…"
        abilities = ", ".join(item["ability"]["name"].replace("-", " ").title() for item in detail.get("abilities", []))
        self.text(f"Tipe: {types}", 490, 286, GREEN, self.small)
        self.text(f"Kemampuan: {abilities or 'Memuat…'}", 490, 312, CREAM, self.small)
        self.text(f"Tinggi {detail.get('height', 0) / 10:.1f} m  ·  Berat {detail.get('weight', 0) / 10:.1f} kg  ·  Lv.{pokemon.get('level', 5)}",
                  490, 338, MUTED, self.small)
        stats = detail.get("stats", [])
        for index, stat in enumerate(stats[:6]):
            stat_name = stat.get("stat", {}).get("name", "stat").replace("special-", "Sp. ").replace("-", " ").title()
            value = int(stat.get("base_stat", 0))
            y = 418 + index * 22
            self.text(f"{stat_name:12} {value:3}", 270, y, CREAM, self.tiny)
            self.box((403, y + 2, 180, 12), (61, 80, 65), 6)
            self.box((403, y + 2, max(2, min(180, value * 180 / 180)), 12), GREEN, 6)
        if species:
            habitat = (species.get("habitat") or {}).get("name", "unknown").replace("-", " ").title()
            color = (species.get("color") or {}).get("name", "unknown").title()
            self.text(f"Habitat: {habitat}  ·  Warna Pokédex: {color}  ·  Peluang tangkap: {species.get('capture_rate', '?')}",
                      625, 385, GREEN, self.small)
            self.text(self.words("RANTAI EVOLUSI", "EVOLUTION CHAIN"), 625, 417, retro.GOLD, self.small)
            self.draw_evolution_chain(ident, 625, 440, 540, 137,
                                      max_rows=2, icon_size=42, font=self.tiny)
        else:
            self.text("Memuat habitat dan entri Pokédex…", 625, 395, MUTED, self.small)
        self.button("Putar cry", (625, 584, 190, 44), lambda: self.play_pokemon_cry(ident), True)
        self.button("Kembali · I / Esc", (825, 584, 208, 44), lambda: setattr(self, "mode", "encounter"))

    def draw_player_profile(self):
        self.text(self.words("PROFIL PELATIH & TIM", "TRAINER & TEAM PROFILE"), 242, 183, CREAM, self.medium)
        self.text(self.words("Status, pengalaman, dan syarat evolusi", "Stats, experience, and evolution requirements"),
                  245, 220, GREEN, self.small)
        self.box((245, 254, 350, 310), (29, 43, 67), 8)
        self.text(self.life.player_name or "Adventurer", 265, 270, CREAM, self.medium)
        if self.life.godmode:
            self.text("GOD MODE · LGAB", 265, 294, retro.GOLD, self.tiny)
        identity_label=getattr(self.life,"trainer_versus_name","")
        if identity_label:
            self.text(identity_label.replace('_',' ').replace('-',' '),265,310,MUTED,self.small)
        else:
            self.text(self.words("Perempuan" if self.life.gender == "female" else "Laki-laki",
                                 "Female" if self.life.gender == "female" else "Male"), 265, 310, MUTED, self.small)
        level = int(self.life.trainer_level)
        xp = int(self.life.trainer_xp)
        threshold = max(100, level * 100)
        self.text(f"Trainer Lv. {level}", 265, 350, retro.GOLD, self.small)
        self.text(f"XP {xp} / {threshold}  ·  {self.life.trainer_xp_bank} {self.words('XP tersimpan','XP banked')}",
                  265, 380, CREAM, self.tiny)
        self.box((265, 405, 300, 14), (53, 68, 91), 5)
        self.box((265, 405, max(2, int(300 * min(1, xp / threshold))), 14), GREEN, 5)
        self.text(f"{self.words('Pelatih','Trainer')} HP {int(self.life.health)}/100  ·  ${self.life.money}",
                  265, 430, CREAM, self.tiny)
        stats = list(self.life.stats.items())
        self.text("  ·  ".join(f"{self.tr(name)} {int(value)}" for name, value in stats[:2]),
                  265, 458, MUTED, self.tiny)
        self.text("  ·  ".join(f"{self.tr(name)} {int(value)}" for name, value in stats[2:]),
                  265, 480, MUTED, self.tiny)
        self.text(self.words(f"Pokémon tersimpan: {len(self.life.pokemon_party)}  ·  Aktif: {len(self.life.pokemon_active)}/3",
                             f"Pokémon stored: {len(self.life.pokemon_party)}  ·  Active: {len(self.life.pokemon_active)}/3"),
                  265, 495, GREEN, self.tiny)
        self.text(self.words("XP tersimpan didapat dari duel dan misi.",
                             "Duels and quests grant banked XP."), 265, 524, MUTED, self.tiny)
        self.text(self.words("Evolusi memakai XP tersimpan + 10 koin.",
                             "Evolution spends banked XP + 10 coins."), 265, 544, MUTED, self.tiny)

        self.text(self.words("TIM AKTIF", "ACTIVE TEAM"), 635, 264, retro.GOLD, self.small)
        active = self.life.pokemon_active[:3]
        if not active:
            self.text(self.words("Belum ada Pokémon aktif.", "No active Pokémon yet."), 635, 306, MUTED, self.small)
        for index, ident in enumerate(active):
            y = 292 + index * 82
            detail = self.pokemon_data(ident) or pokemon_db.detail(ident) or {}
            self.box((630, y, 402, 72), (29, 43, 67), 7)
            sprite = self.pokemon_surface(ident, 48)
            if sprite:
                self.canvas.blit(sprite, sprite.get_rect(midleft=(645, y + 36)))
            name = detail.get("name", f"Pokémon #{ident}").title()
            level = self.pokemon_level(ident)
            pokemon_xp = int(self.life.pokemon_xp.get(str(ident), 0))
            needed = max(1, level * 18)
            self.text(f"{index + 1}. {name}  ·  Lv. {level}", 704, y + 8, CREAM, self.small)
            types = " / ".join(t["type"]["name"].title() for t in detail.get("types", []))
            self.text(f"{types or self.words('Tipe memuat…','Loading types…')}  ·  XP {pokemon_xp}/{needed}",
                      704, y + 38, MUTED, self.tiny)
            option = self.evolution_option(ident)
            if option:
                target_id, target_name, required_level = option
                xp_cost = self.evolution_xp_cost(ident)
                ready = level >= required_level and self.life.trainer_xp_bank >= xp_cost and self.life.money >= 10
                label = (self.words(f"Siap: {target_name.title()}", f"Ready: {target_name.title()}") if ready else
                         self.words(f"Butuh Lv.{required_level} + {xp_cost} XP pelatih",
                                    f"Needs Lv.{required_level} + {xp_cost} Trainer XP"))
                self.text(label, 704, y + 56, GREEN if ready else retro.GOLD, self.tiny)
            else:
                self.text(self.words("Evolusi berikutnya belum tersedia", "No evolution data available"),
                          704, y + 56, MUTED, self.tiny)
        self.button(self.words("Pokémon Center · kelola / evolusi", "Pokémon Center · manage / evolve"),
                    (630, 548, 402, 38), self.open_pokemon_center)
        self.life.ensure_companion_quest()
        companion = int(self.life.companion_id or next(iter(active), 1))
        companion_detail = self.pokemon_data(companion) or pokemon_db.detail(companion) or {}
        companion_name = companion_detail.get("name", f"Pokémon #{companion}").title()
        quest = self.life.companion_quest
        q_title = quest.get("title" if self.life.language == "id" else "title_en", "Companion quest")
        q_progress = min(int(quest.get("target", 1)), int(float(quest.get("progress", 0))))
        q_target = int(quest.get("target", 1))
        self.box((245, 592, 788, 49), (29, 43, 67), 7, (74, 100, 126))
        sprite = self.pokemon_surface(companion, 38)
        if sprite:
            self.canvas.blit(sprite, sprite.get_rect(midleft=(254, 616)))
        self.text(self.words(f"Pendamping: {companion_name} · Ikatan {self.life.companion_bond}/100",
                             f"Companion: {companion_name} · Bond {self.life.companion_bond}/100"),
                  299, 596, GREEN, self.tiny)
        self.box((299, 612, 310, 4), (53, 68, 91), 2)
        self.box((299, 612, max(1, int(310 * self.life.companion_bond / 100)), 4), GREEN, 2)
        self.text(f"{q_title} · {q_progress}/{q_target}", 299, 620, CREAM, self.tiny)
        self.button("‹", (750, 599, 35, 34), lambda: self.cycle_companion(-1))
        self.button("›", (790, 599, 35, 34), lambda: self.cycle_companion(1))
        ready = q_progress >= q_target and not quest.get("claimed")
        self.button(self.words("Klaim hadiah", "Claim reward") if ready else
                    (self.words("Selesai", "Claimed") if quest.get("claimed") else "+45 koin · +1 tiket"),
                    (835, 599, 188, 34), self.claim_companion_quest, ready)
        self.button(self.words("Tutup · U / Esc", "Close · U / Esc"), (245, 646, 788, 38), self.back)

    def draw_center(self):
        self.text("POKÉMON CENTER · PEMERIKSAAN TIM", 242, 183, CREAM, self.medium)
        self.text(self.center_message, 245, 222, GREEN, self.small)
        self.button("◀", (245, 250, 42, 35), lambda: self.cycle_type_filter("center_type_filter", -1))
        self.button(self.type_filter_label(self.center_type_filter), (289, 250, 224, 35),
                    lambda: self.cycle_type_filter("center_type_filter", 1), self.center_type_filter != "all")
        self.button("▶", (515, 250, 42, 35), lambda: self.cycle_type_filter("center_type_filter", 1))
        visible_party = self.center_filtered_party()
        for visible_index, (party_index, pokemon_id) in enumerate(visible_party):
            i = party_index
            row, col = divmod(visible_index, 2)
            rect = (245 + col * 182, 291 + row * 66, 170, 58)
            detail = self.pokemon_data(pokemon_id) or {}
            name = detail.get("name", f"Pokémon #{pokemon_id}").title()
            marker = "✓" if pokemon_id in self.life.pokemon_active else "·"
            self.button(f"{i + 1} {marker} {name}", rect,
                        lambda i=i: setattr(self, "center_selected", i), i == self.center_selected)
            type_names = [item["type"]["name"] for item in detail.get("types", [])]
            if not type_names:
                type_names = list(pokemon_db.type_catalog().get(pokemon_id, ()))
            badges = "  ".join(f"{TYPE_EMOJI.get(typ, '✨')} {typ.title()}" for typ in type_names)
            self.text(badges or "Memuat tipe…", rect[0] + 9, rect[1] + 37, MUTED, self.tiny)
        if not visible_party:
            self.text(self.words("Tidak ada Pokémon bertipe ini di tim.", "No party Pokémon match this type."),
                      421, 349, MUTED, self.small, True)
        pokemon_id = self.center_pokemon_id()
        detail = self.pokemon_data(pokemon_id) if pokemon_id else None
        if detail:
            self.canvas.blit(self.pokemon_surface(pokemon_id, 96), (651, 275))
            self.text(detail.get("name", "Pokémon").title(), 815, 274, CREAM, self.medium, True)
            types = " · ".join(item["type"]["name"].title() for item in detail.get("types", []))
            level = self.pokemon_level(pokemon_id)
            maximum = self.base_stat(detail, "hp", 45) + level * 2
            current = min(maximum, self.life.pokemon_health.get(str(pokemon_id), maximum))
            self.text(f"Tipe: {types}   ·   Level {level}", 815, 319, GREEN, self.small, True)
            self.text(f"HP: {current} / {maximum}   ·   XP: {self.life.pokemon_xp.get(str(pokemon_id), 0)} / {level * 18}",
                      815, 349, CREAM, self.small, True)
            option = self.evolution_option(pokemon_id)
            candidate = self.evolution_target(pokemon_id)
            if option:
                _, target_name, required_level = option
                xp_cost = self.evolution_xp_cost(pokemon_id)
                ready = bool(candidate and self.life.trainer_xp_bank >= xp_cost and self.life.money >= 10)
                label = (f"{self.words('Siap evolusi','Ready to evolve')} → {target_name.title()}" if ready else
                         self.words(f"{target_name.title()} · Lv.{required_level} · {xp_cost} XP pelatih + 10 koin",
                                    f"{target_name.title()} · Lv.{required_level} · {xp_cost} Trainer XP + 10 coins"))
                self.text(label, 815, 386, (255, 222, 121), self.small, True)
            else:
                self.text("Evolusi level-up terbuka setelah syarat spesies terpenuhi.", 815, 386, MUTED, self.small, True)
        else:
            self.text("Memuat data pemeriksaan dari PokéAPI…", 815, 320, MUTED, self.small, True)
        self.button("Pulihkan seluruh tim", (245, 496, 252, 43), self.heal_pokemon_party, True)
        target = self.evolution_target(pokemon_id) if pokemon_id else None
        self.button("Evolusi · V", (510, 496, 205, 43), self.evolve_selected, bool(target))
        self.button("Aktifkan / keluarkan", (728, 496, 305, 43), self.toggle_active_pokemon,
                    bool(pokemon_id in self.life.pokemon_active if pokemon_id else False))
        self.text(self.words(
            f"Trainer Lv.{self.life.trainer_level} · XP {self.life.trainer_xp}/{self.life.trainer_level * 100} · Tersimpan {self.life.trainer_xp_bank} XP",
            f"Trainer Lv.{self.life.trainer_level} · XP {self.life.trainer_xp}/{self.life.trainer_level * 100} · Banked {self.life.trainer_xp_bank} XP"),
            245, 532, MUTED, self.small)
        self.text(f"Tim aktif {len(self.life.pokemon_active)}/3 · ←/→ filter · ↑/↓ pilih · Enter aktifkan",
                  245, 555, MUTED, self.small)
        self.button("Keluar center · Esc", (245, 592, 788, 42), self.back)

    def draw_evolution(self):
        animation = self.evolution_anim
        if not animation:
            self.mode = "center"
            return
        t = animation["timer"]
        cx, cy = 640, 408
        old_id, new_id = animation["from"], animation["to"]
        self.draw_pokedex_icon(252, 198, 26)
        self.text("EVOLUSI POKÉMON", 276, 183, CREAM, self.medium)
        self.text(f"{animation['old_name'].title()}  →  {animation['name'].title()}",
                  640, 237, GREEN, self.small, True)
        intensity = max(0.0, min(1.0, t / 2.4))
        pulse = 1 + .08 * math.sin(t * 9)
        for ring in range(3):
            radius = 76 + ring * 25 + int(12 * math.sin(t * 5 - ring))
            color = ((151, 222, 132), (253, 220, 117), (117, 203, 208))[ring]
            pg.draw.ellipse(self.canvas, color, (cx - radius * pulse, cy - radius * .45 * pulse,
                                                 radius * 2 * pulse, radius * .9 * pulse), 2 if ring else 4)
        # A ring of pixel stars makes the transformation read as a special event.
        for index in range(18):
            angle = t * (2.8 - min(t, 2.4) * .7) + index * math.tau / 18
            radius = 105 + 18 * math.sin(t * 5 + index)
            sx, sy = int(cx + math.cos(angle) * radius), int(cy + math.sin(angle) * radius * .48)
            color = (255, 237, 157) if index % 2 else (181, 235, 167)
            pg.draw.rect(self.canvas, color, (sx - 3, sy - 3, 6, 6))
            pg.draw.rect(self.canvas, CREAM, (sx - 1, sy - 6, 2, 12))
            pg.draw.rect(self.canvas, CREAM, (sx - 6, sy - 1, 12, 2))

        old_surface = self.pokemon_surface(old_id, 112)
        new_surface = self.pokemon_surface(new_id, 112)
        if t < 2.45 and old_surface:
            # Fast orbit eases down to a gentle final turn before the flash.
            spin_time = min(t, 2.45)
            angle = (720 * spin_time - 147 * spin_time * spin_time) % 360
            scale = .84 + .22 * (.5 + .5 * math.sin(t * 10))
            turned = pg.transform.rotozoom(old_surface, angle, scale)
            self.canvas.blit(turned, turned.get_rect(center=(cx, cy)))
        if t >= 2.42:
            reveal = min(1.0, (t - 2.42) / .85)
            if new_surface:
                eased = 1 - (1 - reveal) ** 3
                turned = pg.transform.rotozoom(new_surface, (1 - eased) * 210,
                                               .48 + eased * .58)
                self.canvas.blit(turned, turned.get_rect(center=(cx, cy)))
            if 2.42 <= t <= 2.9:
                flash = pg.Surface((W, H), pg.SRCALPHA)
                flash.fill((255, 247, 210, int(120 * (1 - (t - 2.42) / .48))))
                self.canvas.blit(flash, (0, 0))
        caption = "Cahaya evolusi mengumpulkan energi…" if t < 2.42 else "Bintang-bintang menyatu menjadi bentuk baru!"
        self.text(caption, cx, 542, CREAM, self.small, True)
        self.button("Lewati animasi · Esc", (245, 592, 788, 42), self.finish_evolution)

    def change_dex_page(self, offset):
        entries = self.dex_entries()
        pages = max(1, (len(entries) + 7) // 8)
        self.dex_page = (max(0, min(pages - 1, int(self.dex_page))) + offset) % pages
        if entries:
            index = min(len(entries) - 1, self.dex_page * 8)
            self.select_dex(entries[index]["id"])

    def draw_pokemon_battle(self):
        battle = self.battle
        if not battle:
            return
        enemy = self.pokemon_data(battle["wild_id"])
        team = self.pokemon_data(battle["player_id"])
        b = battle
        arena = b.get("arena_style", "meadow")
        retro.arena(self.canvas, arena)
        weather = b.get("battle_weather", "Cerah")
        # Compact animated weather pass over the already cached stage art.
        if weather in ("Hujan", "Badai"):
            color = (170, 211, 235, 82) if weather == "Hujan" else (190, 211, 230, 105)
            overlay = pg.Surface((W, 800), pg.SRCALPHA)
            for i in range(34):
                x = (i * 173 + int(self.frame * (8 if weather == "Hujan" else 13))) % W
                y = (i * 97 + int(self.frame * (14 if weather == "Hujan" else 21))) % 590
                pg.draw.line(overlay, color, (x, y), (x - 5, y + 14), 2)
            self.canvas.blit(overlay, (0, 0))
        elif weather == "Salju":
            for i in range(22):
                x = (i * 211 + int(self.frame * 2)) % W
                y = (i * 127 + int(self.frame * 5)) % 590
                pg.draw.rect(self.canvas, (224, 239, 248), (x, y, 3, 3))
        elif weather == "Cerah":
            pg.draw.circle(self.canvas, (255, 219, 115), (1110, 265), 35, 4)
        # Fighter nameplates and HP bars.
        self.box((50, 24, 490, 105), (32, 51, 48), 14)
        self.box((740, 24, 490, 105), (32, 51, 48), 14)
        player_name = team.get("name", "Pokémon Anda").title() if team else "Pokémon Anda"
        enemy_name = enemy.get("name", "Pokémon liar").title() if enemy else "Pokémon liar"
        self.text(player_name, 76, 36, CREAM, self.medium)
        self.text(enemy_name, 764, 36, CREAM, self.medium)
        for detail, center_x in ((team, 443), (enemy, 1158)):
            if detail:
                height_m=float(detail.get("height", 0))/10
                weight_kg=float(detail.get("weight", 0))/10
                speed=self.base_stat(detail,"speed",70)
                self.text(f"{height_m:.1f}m · {weight_kg:g}kg · SPD {speed}",
                          center_x,52,MUTED,self.tiny,True)
        self._fight_bar(76, 77, 440, b.get("player_hp", 1), b.get("player_max", 1), left=True)
        self._fight_bar(764, 77, 440, b.get("wild_hp", 1), b.get("wild_max", 1), left=False)
        pg.draw.rect(self.canvas, (57, 71, 61), (76, 118, 440, 8), border_radius=0)
        if b.get("super_meter", 0):
            pg.draw.rect(self.canvas, (247, 194, 74), (76, 118, int(440 * b["super_meter"] / 100), 8), border_radius=0)
        self.text(f"ULTIMATE {int(b.get('super_meter', 0))}%", 76, 132, (255, 222, 121), self.small)
        self.text(f"TRAINER CONDITION ×{round(b.get('trainer_condition', 1.0) * 100)}%",
                  76, 150, GREEN, self.tiny)
        opponent_count = len(b.get("opponent_lineup", [b["wild_id"]]))
        battle_kind="TEAM BATTLE" if opponent_count > 1 else "WILD BATTLE"
        boss_scale = (f"  ·  ×{b.get('enemy_stat_multiplier',1):.2f} STAT"
                      if b.get("dungeon_is_boss") or (b.get("wild") or {}).get("is_boss") else "")
        self.text(f"{battle_kind}  ·  Lv.{b.get('wild_level',5)}  ·  {b.get('difficulty_label','BALANCED')}{boss_scale}",
                  W // 2, 47, CREAM, self.tiny, True)
        self.text(f"{BATTLE_WEATHER_EMOJI.get(weather, '☁')} {weather.upper()}  ·  {arena.upper()} ARENA", W // 2, 68, GREEN, self.tiny, True)
        active_buffs = []
        if b.get("fruit_speed_timer", 0) > 0:
            active_buffs.append(f"🍌 SPEED {b['fruit_speed_timer']:.0f}s")
        if b.get("fruit_double_timer", 0) > 0:
            active_buffs.append(f"🍒 SKILL ×2 {b['fruit_double_timer']:.0f}s")
        if active_buffs:
            self.text("  ·  ".join(active_buffs), W // 2, 105 if opponent_count > 1 else 89,
                      (255, 218, 100), self.tiny, True)
        arena_marks = [f"{effect['emoji']} {effect['label']} {effect['timer']:.0f}s"
                       for effect in b.get("arena_effects", []) if effect.get("timer", 0) > 0]
        if arena_marks:
            self.box((440, 134, 400, 27), (28, 46, 57), 7)
            self.text(" · ".join(arena_marks)[:56], W // 2, 148, (154, 229, 195), self.tiny, True)
        if b.get("arena_combo_timer", 0) > 0 and b.get("arena_combo"):
            self.box((394, 166, 492, 29), (76, 48, 42), 7, retro.GOLD)
            self.text(b["arena_combo"], W // 2, 180, (255, 224, 132), self.tiny, True)
        if b.get("dungeon_round_label"):
            self.text(b["dungeon_round_label"], W // 2, 87, CREAM, self.tiny, True)
        elif opponent_count > 1:
            self.text(f"RONDE {b.get('opponent_index', 0) + 1}/{opponent_count}", W // 2, 87, CREAM, self.tiny, True)
        if b.get("boss_phase", 1) >= 2:
            self.text(self.words("⚡ BOSS · FASE 2", "⚡ BOSS · PHASE 2"),
                      W // 2, 105, (255, 186, 93), self.tiny, True)
        # Sprites use the larger cached API art, with squash/stretch on impacts.
        ground = 606
        for platform in b.get("platforms", []):
            px, py = int(platform["x"]), ground + int(platform["height"])
            left = px - platform["width"] // 2
            wall_width = max(24, platform["width"] // 3)
            wall_x = left + platform["width"] // 2 - wall_width // 2
            pg.draw.rect(self.canvas, (100, 83, 65), (wall_x, py + 4, wall_width, ground - py + 2))
            pg.draw.polygon(self.canvas, (137, 118, 88),
                            [(wall_x - 6, py + 7), (wall_x + wall_width // 3, py - 5),
                             (wall_x + wall_width + 7, py + 5), (wall_x + wall_width, ground)])
            pg.draw.rect(self.canvas, (193, 157, 105), (left, py, platform["width"], 12), border_radius=0)
            pg.draw.rect(self.canvas, (231, 205, 145), (left, py, platform["width"], 4), border_radius=0)
            for rung_y in range(py + 22, ground - 5, 22):
                pg.draw.line(self.canvas, (197, 166, 119), (wall_x + 3, rung_y),
                             (wall_x + wall_width - 3, rung_y), 3)
        # Seven-second elemental marks live on the arena itself.  They render
        # before fighters, so water, flame, bushes and stone walls feel like
        # part of the stage rather than an icon glued over a Pokémon.
        self.draw_arena_effects(b, ground)
        for fruit in b.get("fruits", []):
            fx, fy = int(fruit["x"]), ground + int(fruit.get("y", 0)) - 20
            pg.draw.circle(self.canvas, (255, 238, 165), (fx, fy), 14, 2)
            glyph = self.fruit_font.render(fruit["emoji"], True, CREAM)
            glyph = pg.transform.scale(glyph, (21, 21))
            self.canvas.blit(glyph, glyph.get_rect(center=(fx, fy)))
        for puff in b.get("dust_particles",[]):
            progress=1-puff["ttl"]/max(.01,puff["duration"])
            radius=max(2,int(puff["size"]*(.7+progress*.7)))
            shade=int(139+75*progress)
            pg.draw.ellipse(self.canvas,(shade,min(232,shade-16),max(75,shade-49)),
                            (int(puff["x"]-radius),int(puff["y"]-radius*.45),radius*2,max(3,radius)))
        capture = b.get("capture")
        for key, ident, flip in (("player", b["player_id"], True), ("enemy", b["wild_id"], False)):
            if key == "enemy" and capture and capture["phase"] in ("shake", "success"):
                continue
            x = int(b.get(key + "_x", 350 if key == "player" else 760))
            y = int(b.get(key + "_y", 0))
            if key == "player" and b.get("attack_flash", 0) > 0:
                x += b["player_facing"] * (38 if b.get("attack_heavy") else 22)
            sprite = self.pokemon_surface(b.get(key + "_appearance", ident), self.fighter_size(ident))
            if sprite:
                faces_right = b.get("player_facing", 1) > 0 if key == "player" else b.get("enemy_x", 930) < b.get("player_x", 350)
                # PokeAPI front sprites face left by default; flip only when
                # the fighter needs to face right toward its opponent.
                if faces_right:
                    sprite = pg.transform.flip(sprite, True, False)
                immobilized=b.get(key+"_stun_timer",0)>0
                confused=self.status_active(key, "confuse")
                if confused and not self.life.reduced_motion:
                    sprite=pg.transform.rotate(sprite,(self.frame*7)%360)
                flash = b.get("hit_flash", 0) if key == "player" else b.get("enemy_flash", 0)
                if flash > 0 and not self.life.reduced_motion and int(flash * 50) % 2:
                    # Brighten RGB only; RGBA blending changes transparent GIF pixels too.
                    white = sprite.copy(); white.fill((150, 150, 150), special_flags=pg.BLEND_RGB_ADD); sprite = white
                shadow_x = x - 34
                fighter_y = b.get(key + "_y", 0)
                if key == "enemy" and b.get("enemy_attack_flash", 0) > 0:
                    toward_player = 1 if b["player_x"] > b["enemy_x"] else -1
                    lunge = 1 - min(1, b["enemy_attack_flash"] / .42)
                    x += int(toward_player * 34 * lunge)
                elif key == "player" and b.get("hit_flash", 0) > 0:
                    shake = b["hit_flash"] / .25
                    x += int(math.sin(self.frame * 3.4) * 10 * shake)
                pg.draw.ellipse(self.canvas, (105, 91, 69), (shadow_x, ground - 12, 68, 16))
                if key == "enemy" and capture and capture["phase"] == "absorb":
                    progress = min(1.0, capture["timer"] / capture["duration"])
                    size = max(4, int(104 * (1 - progress) ** 1.7))
                    ratio = min(size / max(1, sprite.get_width()), size / max(1, sprite.get_height()))
                    sprite = pg.transform.scale(sprite, (max(1, round(sprite.get_width() * ratio)),
                                                               max(1, round(sprite.get_height() * ratio))))
                    x = int(x + (capture["start_x"] - x) * progress)
                    self.canvas.blit(sprite, (x - size // 2, ground - size + fighter_y))
                else:
                    ko=b.get("ko_anim")
                    if ko and ko.get("owner")==key and ko.get("pokemon_id")==ident:
                        progress=1-ko["timer"]/ko["duration"]
                        eased=progress*progress*(3-2*progress)
                        turned=pg.transform.rotate(sprite,90*eased)
                        center=(x,ground-sprite.get_height() / 2 + fighter_y)
                        self.canvas.blit(turned,turned.get_rect(center=center))
                        skull_size=int(24+58*eased)
                        skull_y=int(ground-sprite.get_height()-20-76*eased+fighter_y)
                        skull=self.emoji_font.render("💀",True,CREAM)
                        skull=pg.transform.scale(skull,(skull_size,skull_size))
                        self.canvas.blit(skull,skull.get_rect(center=(x,skull_y)))
                    else:
                        self.canvas.blit(sprite, (x - sprite.get_width() // 2,
                                                  ground - sprite.get_height() + fighter_y))
                self.draw_fighter_status(key, x, ground - sprite.get_height() // 2 + fighter_y,
                                         sprite.get_height())
                if confused:
                    question=self.emoji_font.render("❔",True,CREAM)
                    question=pg.transform.scale(question,(38,38))
                    self.canvas.blit(question,question.get_rect(center=(x,ground-sprite.get_height()-25+fighter_y)))
                if key == "enemy" and b.get("enemy_guard_timer", 0) > 0 and not (b.get("ko_anim") or {}).get("owner") == key:
                    pg.draw.ellipse(self.canvas, (125, 207, 246),
                                    (x - 58, ground - 124 + fighter_y, 116, 121), 4)
                    shield = self.fruit_font.render("🛡️", True, CREAM)
                    self.canvas.blit(shield, shield.get_rect(center=(x, ground - 142 + fighter_y)))
                team_types = {t["type"]["name"] for t in (team or {}).get("types", [])}
                if key == "player" and fighter_y < -20 and "flying" in team_types:
                    self.text("🌪️", x, ground - 153 + fighter_y, CREAM, self.emoji_font, True)
                elif key == "player" and fighter_y > 12:
                    self.text("💦" if "water" in team_types and arena == "water" else "🪨", x, ground - 170 + fighter_y, CREAM, self.emoji_font, True)
        if capture:
            self.draw_capture(capture, b)
        self.draw_fight_vfx(b)
        if b.get("wild_max") and b.get("wild_hp", 1) / b["wild_max"] <= .28 and not b.get("trainer") and not b.get("result"):
            enemy_x = int(b.get("enemy_x", 760))
            pulse = 1 if int(self.frame / 18) % 2 else 0
            self.box((enemy_x - 105, 346, 210, 31), (161, 70, 63) if pulse else (94, 49, 45), 9)
            self.text("HP KRITIS · TANGKAP O", enemy_x, 361, CREAM, self.small, True)
        if b.get("attack_flash", 0) > 0:
            px, py = int(b["player_x"] + b["player_facing"] * 70), 500 + int(b.get("player_y", 0))
            color = (255, 239, 174) if b.get("attack_heavy") else (246, 249, 225)
            pg.draw.arc(self.canvas, color, (px - 42, py - 46, 84, 88), -1.1, 1.15, 6 if b.get("attack_heavy") else 4)
        if b.get("block_flash", 0) > 0:
            self.box((79, 100, 180, 34), (59, 117, 164), 10)
            self.text("BLOK!", 169, 117, CREAM, self.small, True)
        self.box((558, 204, 164, 42), (32, 51, 48), 12)
        seconds = max(0, int(math.ceil(b.get("time_left", 60))))
        self.text(f"{seconds // 60:02}:{seconds % 60:02}", W // 2, 225,
                  (238, 123, 94) if seconds <= 10 else CREAM, self.medium, True)
        if b.get("story_caption_timer", 0) > 0 and not b.get("boss_intro"):
            self.box((350, 440, 580, 42), (24, 34, 49), 9, retro.GOLD)
            caption = b.get("story_caption", "")
            if len(caption) > 66:
                caption = caption[:63].rstrip() + "…"
            self.text(caption, W // 2, 461, CREAM, self.tiny, True)
        phase = b.get("phase", "Memuat Pokémon dari PokéAPI…") if capture else (b.get("result") or b.get("phase", "Memuat Pokémon dari PokéAPI…"))
        enemy_ko = (b.get("ko_anim") or {}).get("owner") == "enemy"
        if capture or (b.get("result") and not enemy_ko):
            self.box((300, 536, 680, 40), (35, 54, 48), 12)
            self.text(phase, W // 2, 556, CREAM, self.small, True)
        self.box((910, 142, 340, 66), (32, 51, 48), 9)
        self.text("← → gerak · ↑ lompat/panjat · S tahan", 924, 151, CREAM, self.tiny)
        self.text("A dekat · S tahan · Q stun · W dekat · E jauh · R ult · 1–3 ganti", 924, 170, GREEN, self.tiny)
        self.text(f"O bola · ult tembus 40% guard · {int(b.get('time_left', 60))} dtk · Esc", 924, 185, MUTED, self.tiny)
        if b.get("matchup_tip_timer", 0) > 0 and b.get("matchup_tip"):
            self.box((910, 216, 340, 55), (26, 40, 52), 8)
            self.text(self.words("TIP JENIS · POKÉAPI", "TYPE TIP · POKÉAPI"), 923, 221, retro.GOLD, self.tiny)
            for index, (emoji, tip) in enumerate(b["matchup_tip"]):
                self.text(f"{emoji} {tip}"[:34], 923, 238 + index * 16, CREAM, self.tiny)
        if b.get("result") and b["player_hp"] <= 0:
            self.box((470, 586, 340, 44), (32, 51, 48), 12)
            self.text("Enter / Esc · kembali ke peta", W // 2, 608, CREAM, self.small, True)
        if b.get("intro"):
            self.draw_battle_intro(b)
        if b.get("ultimate_cutin"):
            self.draw_ultimate_cutin(b, b["ultimate_cutin"])
        if b.get("boss_intro"):
            self.draw_boss_intro(b, b["boss_intro"])
        if b.get("rocket_defeat_cutin") and not enemy_ko:
            self.draw_rocket_defeat_cutin(b,b["rocket_defeat_cutin"])
        if b.get("rocket_win_cutin"):
            self.draw_rocket_win_cutin(b,b["rocket_win_cutin"])
        if b.get("victory_cutin") and not enemy_ko:
            self.draw_victory_cutin(b, b["victory_cutin"])

    def draw_rocket_defeat_cutin(self,battle,cutin):
        """Team Rocket tumbles away, bursts into stars, then yields to the win cut-in."""
        elapsed=cutin["duration"]-cutin["timer"]
        self.battle_flash.fill((5,8,17,220));self.canvas.blit(self.battle_flash,(0,0))
        self.text(self.words("TEAM ROCKET KALAH!","TEAM ROCKET DEFEATED!"),640,102,retro.GOLD,self.big,True)
        image=cutin.get("image")
        if image is not None and elapsed<2.02:
            travel=min(1.0,elapsed/1.75)
            size=max(42,int(470*(1-travel*.86)))
            ratio=min(size/max(1,image.get_width()),size*.72/max(1,image.get_height()))
            scaled=pg.transform.smoothscale(image,(max(1,int(image.get_width()*ratio)),
                                                    max(1,int(image.get_height()*ratio))))
            angle=-900*travel
            rotated=pg.transform.rotate(scaled,angle)
            x=640+590*travel;y=388-330*travel
            for index in range(7,0,-1):
                trail_progress=max(0.0,travel-index*.075)
                if trail_progress<=0.025:continue
                trail_center=(int(640+590*trail_progress),int(388-330*trail_progress))
                self.emoji("⭐" if index%2 else "✨",trail_center,max(12,27-index))
            self.canvas.blit(rotated,rotated.get_rect(center=(int(x),int(y))))
        if elapsed>=1.78:
            fireworks=min(1.0,(elapsed-1.78)/.55)
            center=(1230,58)
            for index in range(20):
                angle=math.tau*index/20+((index%3)-1)*.12
                distance=14+94*fireworks+(index%4)*4
                point=(int(center[0]+math.cos(angle)*distance),
                       int(center[1]+math.sin(angle)*distance))
                self.emoji("⭐" if index%3 else "✨",point,16+(index%4)*4)
            self.text("TRING!",center[0]-76,center[1]+45,retro.CREAM,self.small,True)

    def draw_rocket_win_cutin(self,battle,cutin):
        """Use the supplied celebratory Team Rocket still with a bouncing shake."""
        elapsed=cutin["duration"]-cutin["timer"]
        self.battle_flash.fill((5,8,17,225));self.canvas.blit(self.battle_flash,(0,0))
        self.text(self.words("TEAM ROCKET MENANG!","TEAM ROCKET WINS!"),640,112,retro.GOLD,self.big,True)
        image=self.rocket_win_surface
        if image is not None:
            ratio=min(760/max(1,image.get_width()),440/max(1,image.get_height()))
            scaled=pg.transform.smoothscale(image,(max(1,int(image.get_width()*ratio)),
                                                    max(1,int(image.get_height()*ratio))))
            shake_x=math.sin(elapsed*23)*7
            bounce=math.sin(elapsed*13)*24
            rotated=pg.transform.rotate(scaled,math.sin(elapsed*27)*2.5)
            self.canvas.blit(rotated,rotated.get_rect(center=(640+shake_x,420+bounce)))
        self.text(self.words("Mereka kabur membawa kemenangan…","They escape with the victory…"),
                  640,710,retro.CREAM,self.small,True)

    def draw_victory_cutin(self, battle, cutin):
        """Celebrate the trainer and the exact Pokémon that won the battle."""
        progress = 1 - cutin["timer"] / max(.01, cutin["duration"])
        pulse = 1.0 + .035 * math.sin(progress * math.pi * 8)
        self.canvas.fill((13, 20, 42))
        for index in range(10):
            x = index * 150 - int(self.frame * 3) % 150
            pg.draw.polygon(self.canvas, (28, 47, 75),
                            [(x, 0), (x + 64, 0), (x + 176, H), (x + 110, H)])
        pg.draw.polygon(self.canvas, (242, 188, 79), [(0, 0), (510, 0), (420, H), (0, H)])
        pg.draw.polygon(self.canvas, (22, 34, 61), [(14, 14), (480, 14), (397, H - 14), (14, H - 14)])
        pg.draw.polygon(self.canvas, (242, 188, 79), [(770, 0), (1280, 0), (1280, H), (860, H)])
        trainer_name=cutin.get("trainer_name") or getattr(self.life,"trainer_versus_name","")
        portrait=self.trainer_versus_surface(trainer_name,(410,390))
        if portrait:
            bob=math.sin(self.frame*.12)*5
            self.canvas.blit(portrait,portrait.get_rect(center=(245,400+bob)))
        ident=int(cutin["pokemon_id"])
        detail=self.pokemon_data(ident) or pokemon_db.detail(ident) or {}
        pokemon=self.pokemon_surface(ident,int(255*pulse))
        if pokemon:
            self.canvas.blit(pokemon,pokemon.get_rect(center=(1002,410)))
        self.text(self.words("KEMENANGAN!","VICTORY!"),640,124,retro.GOLD,self.big,True)
        self.text(getattr(self.life,"player_name","Trainer"),245,652,CREAM,self.medium,True)
        self.text(self.words("PELATIH","TRAINER"),245,691,GREEN,self.tiny,True)
        self.text(detail.get("name",f"Pokémon #{ident}").title(),1002,652,CREAM,self.medium,True)
        self.text(self.words("POKÉMON PEMENANG","WINNING POKÉMON"),1002,691,GREEN,self.tiny,True)
        pg.draw.line(self.canvas,retro.GOLD,(476,410),(804,410),6)
        self.text("★",640,385,CREAM,self.big,True)
        self.text(self.words("Juara bersama!","Champions together!"),640,738,CREAM,self.small,True)

    def draw_boss_intro(self, battle, intro):
        """Short cinematic title card before a dungeon boss can fight."""
        progress = 1 - intro["timer"] / max(.01, intro["duration"])
        pulse = 1.0 + .045 * math.sin(self.frame * .55)
        self.canvas.fill((18, 14, 29))
        for index in range(8):
            x = index * 190 - int(self.frame * 2) % 190
            pg.draw.polygon(self.canvas, (35, 30, 48),
                            [(x, 0), (x + 88, 0), (x + 172, H), (x + 80, H)])
        accent = (255, 183, 70)
        # Reuse this full-screen overlay. Allocating a 1280×800 alpha surface
        # every frame during the boss cinematic caused a large allocation
        # churn on lower-memory laptops and could terminate the game on entry.
        glow = getattr(self, "_boss_intro_glow", None)
        if glow is None:
            glow = pg.Surface((W, H), pg.SRCALPHA)
            glow.fill((92, 39, 31, 75))
            self._boss_intro_glow = glow
        self.canvas.blit(glow, (0, 0))
        for index in range(10):
            y = int((index * 97 + self.frame * (5 + index % 3)) % H)
            pg.draw.line(self.canvas, (112, 77, 62), (0, y), (W, y - 48), 2)
        pg.draw.rect(self.canvas, accent, (105, 104, 1070, 6))
        pg.draw.rect(self.canvas, accent, (105, 690, 1070, 6))
        pokemon_id = battle["wild_id"]
        detail = self.pokemon_data(pokemon_id) or {}
        name = detail.get("name", "Dungeon Boss").title()
        sprite = self.pokemon_surface(pokemon_id, int(230 * pulse))
        if sprite:
            sprite = pg.transform.flip(sprite, True, False)
            self.canvas.blit(sprite, sprite.get_rect(center=(370, 420)))
        biome = battle.get("dungeon_biome", "cave").replace("_", " ").upper()
        if (battle.get("trainer") or {}).get("local_dungeon"):
            dungeon = self.local_dungeon_name(battle.get("dungeon_tier", 1)).upper()
        else:
            zone_index = battle.get("reserve_zone")
            if isinstance(zone_index, int) and 0 <= zone_index < len(RESERVE_ZONES):
                zone = RESERVE_ZONES[zone_index]
            else:
                zone = {"name": "POKÉMON SANCTUARY"}
            dungeon = self.words(f"PENJAGA · {zone['name']}", f"GUARDIAN · {zone['name']}").upper()
        self.text(self.words("BOSS DUNGEON", "DUNGEON BOSS"), 790, 210,
                  accent, self.big, True)
        self.text(name, 790, 300, CREAM, self.big, True)
        self.text(f"{dungeon}  ·  {biome}", 790, 355, (155, 219, 183), self.small, True)
        self.text(f"Lv. {battle.get('wild_level', 5)}  ·  {battle.get('difficulty_label', 'BOSS')}",
                  790, 394, CREAM, self.medium, True)
        self.text(self.words("Hadapi penjaga terakhir!", "Face the final guardian!"),
                  790, 493, (230, 202, 174), self.small, True)
        pg.draw.rect(self.canvas, accent, (410, 574, int(760 * min(1, progress)), 8))

    def draw_ultimate_cutin(self, battle, cutin):
        """Brief full-frame character splash before the ultimate impact lands."""
        progress = 1 - cutin["timer"] / max(.01, cutin["duration"])
        pulse = 1.0 + .035 * math.sin(progress * math.pi * 8)
        # Replacing the arena for a few frames creates a readable, anime-like cut-in.
        self.canvas.fill((18, 22, 50))
        for offset in range(-H, W + H, 88):
            pg.draw.polygon(self.canvas, (28, 34, 73),
                            [(offset, 0), (offset + 42, 0), (offset - 218, H), (offset - 260, H)])
        accent = TYPE_MOVES.get(cutin["move_type"], TYPE_MOVES["normal"])[1]
        ultimate_style = (cutin.get("move") or {}).get("ultimate_style", "beam")
        veil = pg.Surface((W, H), pg.SRCALPHA)
        veil.fill((*accent, 34))
        self.canvas.blit(veil, (0, 0))
        # Slanted frame and speed lines converge on the Pokémon portrait.
        pg.draw.polygon(self.canvas, accent, [(0, 0), (540, 0), (365, H), (0, H)])
        pg.draw.polygon(self.canvas, (21, 26, 55), [(10, 10), (518, 10), (354, H - 10), (10, H - 10)])
        for index in range(7):
            y = 105 + index * 84
            pg.draw.line(self.canvas, (239, 232, 218), (0, y), (210 + index * 17, y - 28), 3)
        pokemon_id = cutin["pokemon_id"]
        detail = self.pokemon_data(pokemon_id) or {}
        sprite = self.pokemon_surface(pokemon_id, int(220 * pulse))
        if sprite:
            if battle.get("player_facing", 1) > 0:
                sprite = pg.transform.flip(sprite, True, False)
            self.canvas.blit(sprite, sprite.get_rect(center=(280, 439)))
        self.text("ULTIMATE!", 610, 190, (255, 226, 124), self.big, True)
        self.text(detail.get("name", "Pokémon Anda").title(), 625, 280, CREAM, self.medium, True)
        self.text(cutin["move_name"], 625, 345, accent, self.medium, True)
        glyph = self.ultimate_font.render(cutin["emoji"], True, CREAM)
        glyph = pg.transform.scale(glyph, (116, 116))
        self.canvas.blit(glyph, glyph.get_rect(center=(625, 487)))
        # Each ultimate family receives a different motion language before
        # impact: beams converge, areas expand, rushes streak forward and
        # barrages shower repeated projectiles.
        if ultimate_style == "area":
            for radius in (72, 112, 154):
                pg.draw.circle(self.canvas, accent, (885, 486), radius, 4)
        elif ultimate_style == "rush":
            for index in range(7):
                y = 398 + index * 28
                pg.draw.line(self.canvas, accent, (742, y), (1090 + index * 15, y - 28), 7)
        elif ultimate_style == "barrage":
            for index in range(9):
                x = 744 + (index % 3) * 118
                y = 392 + (index // 3) * 80
                self.emoji(cutin["emoji"], (x, y), 34)
        elif ultimate_style == "wave":
            for index in range(4):
                pg.draw.arc(self.canvas, accent, (736, 386 + index * 24, 330, 95), .1, math.pi - .1, 6)
        else:
            for index in range(6):
                pg.draw.line(self.canvas, accent, (739, 485), (1090, 330 + index * 62), 4)
        pg.draw.rect(self.canvas, accent, (485, 584, 565, 8))

    def draw_battle_intro(self, battle):
        intro = battle["intro"]
        veil = pg.Surface((W, H), pg.SRCALPHA)
        veil.fill((13, 22, 28, 185))
        self.canvas.blit(veil, (0, 0))
        step = intro["step"]
        if step in ("player", "enemy"):
            player_side = step == "player"
            pokemon_id = battle["player_id"] if player_side else battle["wild_id"]
            detail = self.pokemon_data(pokemon_id) or {}
            name = detail.get("name", "Memuat Pokémon…").title()
            level = self.pokemon_level(pokemon_id) if player_side else battle.get("wild_level", 5)
            maximum = battle.get("player_max", 0) if player_side else battle.get("wild_max", 0)
            health = battle.get("player_hp", 0) if player_side else battle.get("wild_hp", 0)
            types = " · ".join(entry["type"]["name"].title() for entry in detail.get("types", []))
            self.box((330, 205, 620, 424), (30, 48, 45), 20, (239, 207, 116))
            weather = battle.get("battle_weather", "Cerah")
            arena = battle.get("arena_style", "meadow")
            self.text(f"{BATTLE_WEATHER_EMOJI.get(weather, '☁')} {weather.upper()}  ·  {arena.upper()} ARENA", W // 2, 230, GREEN, self.small, True)
            self.text("POKÉMON ANDA" if player_side else "LAWAN MENANTANG", W // 2, 263, GREEN if player_side else (242, 151, 123), self.medium, True)
            sprite = self.pokemon_surface(pokemon_id, 128)
            if sprite:
                if not player_side:
                    sprite = pg.transform.flip(sprite, True, False)
                self.canvas.blit(sprite, sprite.get_rect(center=(W // 2, 397)))
            self.text(name, W // 2, 478, CREAM, self.big, True)
            difficulty=(f"   ·   {battle.get('difficulty_label','BALANCED')}" if not player_side else '')
            self.text(f"Lv. {level}   ·   {types or 'Pokédex sedang memuat tipe…'}{difficulty}", W // 2, 518, GREEN, self.small, True)
            self.text(f"HP {int(health)}/{int(maximum)}   ·   Cry asli PokéAPI", W // 2, 548, CREAM, self.small, True)
            mods = battle.get('environment_mods', {}).get(str(pokemon_id), {})
            attack = int(mods.get('attack', 0)); defense = int(mods.get('defense', 0))
            buff_color = (120, 226, 151) if attack >= 0 else (247, 143, 126)
            def_color = (120, 226, 151) if defense >= 0 else (247, 143, 126)
            self.text(f"ATK {'+' if attack >= 0 else ''}{attack}%  ·  {'NAIK' if attack > 0 else 'TURUN' if attack < 0 else 'STABIL'}", W // 2, 580, buff_color, self.small, True)
            self.text(f"DEF {'+' if defense >= 0 else ''}{defense}%  ·  {'NAIK' if defense > 0 else 'TURUN' if defense < 0 else 'STABIL'}", W // 2, 607, def_color, self.small, True)
        else:
            self.text("PERTARUNGAN DIMULAI", W // 2, 300, CREAM, self.medium, True)
            self.text(step, W // 2, 435, (255, 220, 115), self.big, True)
            self.text("Bersiap!", W // 2, 503, GREEN, self.medium, True)

    def draw_capture(self, capture, battle):
        phase = capture["phase"]
        enemy_x = int(capture["target_x"])
        ball_x, ball_y = enemy_x, 610
        angle = 0
        scale = 1.0
        progress = min(1.0, capture["timer"] / max(.01, capture["duration"]))
        if phase == "throw":
            ball_x = int(capture["start_x"] + (enemy_x - capture["start_x"]) * progress)
            ball_y = int(520 - math.sin(progress * math.pi) * 170)
            angle = -progress * 600
        elif phase == "absorb":
            ball_y = int(610 - 14 * math.sin(progress * math.pi))
            for radius in (26, 39, 52):
                pg.draw.circle(self.canvas, (239, 250, 255), (ball_x, 500), max(2, int(radius * (1 - progress))), 2)
        elif phase == "shake":
            beat = math.sin(progress * math.pi * 2)
            ball_x += int(beat * 9)
            angle = beat * 20
            if capture.get("shakes", 0) == 2 and progress > .82:
                pg.draw.circle(self.canvas, (255, 247, 195), (ball_x, ball_y - 30), 13, 3)
        elif phase == "success":
            pulse = .5 + .5 * math.sin(progress * math.pi * 4)
            pg.draw.circle(self.canvas, (255, 231, 123), (ball_x, ball_y - 5), 34 + int(pulse * 22), 3)
            self.text("GOTCHA!", ball_x, 548, (255, 239, 162), self.medium, True)
        elif phase == "break":
            angle = math.sin(progress * math.pi * 5) * 12
            scale = 1 + .3 * math.sin(progress * math.pi)
            pg.draw.circle(self.canvas, (235, 251, 255), (ball_x, ball_y - 62), int(46 * (1 - progress * .5)), 4)
        if self.pokeball_surface:
            size = max(12, int(48 * scale))
            ball = pg.transform.scale(self.pokeball_surface, (size, size))
            ball = pg.transform.rotate(ball, angle)
            rect = ball.get_rect(center=(ball_x, ball_y))
            self.canvas.blit(ball, rect)
        else:
            radius = max(8, int(22 * scale))
            pg.draw.circle(self.canvas, (48, 42, 42), (ball_x, ball_y + 2), radius + 2)
            pg.draw.circle(self.canvas, (222, 67, 58), (ball_x, ball_y), radius)
            pg.draw.rect(self.canvas, (242, 242, 232), (ball_x - radius, ball_y, radius * 2, radius), border_bottom_left_radius=radius, border_bottom_right_radius=radius)
            pg.draw.arc(self.canvas, (255, 255, 255), (ball_x - radius + 3, ball_y - radius + 3, radius * 2 - 6, radius * 2 - 6), 0.15, 2.9, 3)
            pg.draw.line(self.canvas, (48, 42, 42), (ball_x - radius, ball_y), (ball_x + radius, ball_y), 4)
            pg.draw.circle(self.canvas, (246, 246, 236), (ball_x, ball_y), max(4, radius // 3))
            pg.draw.circle(self.canvas, (63, 72, 68), (ball_x, ball_y), max(2, radius // 6), 2)

    def draw_fight_vfx(self, battle):
        effect = battle.get("vfx")
        if not effect:
            return
        progress = 1 - effect["timer"] / max(.01, effect["duration"])
        start_x = effect.get("start_x", battle["player_x"] + battle["player_facing"] * 74)
        start_y = effect.get("start_y", 500 + battle.get("player_y", 0))
        end_x = effect.get("target_x", battle["enemy_x"])
        end_y = effect.get("target_y", 500 + battle.get("enemy_y", 0))
        travel = min(1, progress * (1.45 if effect["ultimate"] else 2.15))
        x = int(start_x + (end_x - start_x) * travel)
        y = int(start_y + (end_y - start_y) * travel - math.sin(travel * math.pi) * 36)
        color, style = effect["color"], effect["type"]
        radius = 18 + int(progress * (75 if effect["ultimate"] else 23))
        if effect["ultimate"]:
            if progress >= .38:
                impact = min(1.0, (progress - .38) / .62)
                self.battle_flash.fill((*color, int(82 * math.sin(impact * math.pi))))
                self.canvas.blit(self.battle_flash, (0, 0))
                x, y = int(end_x), int(end_y)
                shock = 24 + int(impact * 190)
                for ring in (shock, max(10, shock - 31), max(6, shock - 62)):
                    pg.draw.circle(self.canvas, color, (x, y), ring, 7)
                for index in range(12):
                    angle = index * math.tau / 12 + impact * 1.7
                    inner, outer = shock * .68, shock + 50
                    pg.draw.line(self.canvas, (255, 246, 203),
                                 (int(x + math.cos(angle) * inner), int(y + math.sin(angle) * inner)),
                                 (int(x + math.cos(angle) * outer), int(y + math.sin(angle) * outer)), 5)
        if style == "fire":
            pg.draw.polygon(self.canvas, color, [(x, y - radius), (x + radius // 2, y + 8), (x, y + radius // 2), (x - radius // 2, y + 8)])
            pg.draw.circle(self.canvas, (255, 225, 143), (x, y), max(6, radius // 3))
        elif style == "water":
            pg.draw.circle(self.canvas, color, (x, y), radius)
            pg.draw.circle(self.canvas, (219, 245, 255), (x - radius // 3, y - radius // 3), max(3, radius // 4))
            pg.draw.arc(self.canvas, (213, 244, 255), (x - radius, y - radius, radius * 2, radius * 2), .2, 2.7, 4)
        elif style == "leaf":
            pg.draw.ellipse(self.canvas, color, (x - radius, y - radius // 2, radius * 2, radius))
            pg.draw.line(self.canvas, (225, 251, 191), (x - radius + 5, y + radius // 3), (x + radius - 5, y - radius // 3), 3)
        elif style == "electric":
            points = [(x - radius // 2, y - radius), (x + 4, y - radius // 4), (x - 8, y - radius // 4),
                      (x + radius // 2, y + radius), (x + 10, y + radius // 5), (x + 16, y + radius // 5)]
            pg.draw.lines(self.canvas, color, False, points, 9)
        elif style in ("ice", "fairy"):
            for angle in (0, math.pi / 3, math.pi * 2 / 3):
                dx, dy = math.cos(angle) * radius, math.sin(angle) * radius
                pg.draw.line(self.canvas, color, (x - dx, y - dy), (x + dx, y + dy), 5)
            pg.draw.circle(self.canvas, (255, 255, 239), (x, y), max(4, radius // 4))
        elif style in ("rock", "earth"):
            for offset in (-radius // 2, 0, radius // 2):
                pg.draw.polygon(self.canvas, color, [(x + offset, y - radius), (x + offset + radius // 2, y), (x + offset - radius // 3, y + radius // 2)])
        elif style in ("psychic", "ghost", "poison", "dragon"):
            pg.draw.circle(self.canvas, color, (x, y), radius, 7)
            pg.draw.circle(self.canvas, (247, 235, 255), (x, y), max(5, radius // 3), 3)
            if style == "poison":
                for dx, dy in ((-radius, -radius), (radius, -radius // 2), (radius // 2, radius)):
                    pg.draw.circle(self.canvas, color, (x + dx, y + dy), max(5, radius // 5))
        else:
            pg.draw.line(self.canvas, color, (x - radius, y + radius // 2), (x + radius, y - radius // 2), 8)
            pg.draw.circle(self.canvas, color, (x, y), max(8, radius // 2), 4)
        if effect.get("owner") == "enemy":
            if progress < .48:
                for offset in (-13, 0, 13):
                    pg.draw.line(self.canvas, (255, 220, 165),
                                 (int(start_x + (x - start_x) * .2), int(start_y + offset),),
                                 (x, y + offset), 3)
            else:
                impact_radius = 25 + int(min(1, (progress - .48) / .52) * 54)
                points = []
                for index in range(12):
                    angle = index * math.tau / 12
                    extent = impact_radius if index % 2 == 0 else impact_radius * .48
                    points.append((int(x + math.cos(angle) * extent), int(y + math.sin(angle) * extent)))
                pg.draw.polygon(self.canvas, (255, 145, 89), points)
                pg.draw.circle(self.canvas, (255, 237, 183), (x, y), max(8, impact_radius // 3))
                impact_mark = self.emoji_font.render("💥", True, CREAM)
                self.canvas.blit(impact_mark, impact_mark.get_rect(center=(x, y)))
        if effect["ultimate"] and progress >= .38:
            pulse = 1.0 + .18 * math.sin(progress * math.pi * 8)
            badge_size = int(84 * pulse)
            badge = pg.transform.scale(self.ultimate_font.render(effect["emoji"], True, CREAM),
                                             (badge_size, badge_size))
            self.canvas.blit(badge, badge.get_rect(center=(x, y)))
            plate = pg.Rect(0, 0, 460, 44)
            plate.center = (W // 2, 278)
            retro.panel(self.canvas, plate, INK, retro.GOLD)
            self.text(effect["name"], *plate.center, CREAM, self.medium, True)
        label = self.small.render(effect["name"], True, CREAM)
        plate = label.get_rect(center=(x, y - radius - 14)).inflate(14, 8)
        pg.draw.rect(self.canvas, INK, plate, border_radius=0)
        self.canvas.blit(label, label.get_rect(center=plate.center))
        if effect["ultimate"] and progress < .38:
            badge = self.emoji_font.render(effect["emoji"], True, CREAM)
            self.canvas.blit(badge, badge.get_rect(center=(x, y)))
        elif travel < 1.0:
            mark = self.emoji_font.render(effect.get("emoji", "💥"), True, (255, 255, 255))
            self.canvas.blit(mark, mark.get_rect(center=(x, y)))

    def _fight_bar(self, x, y, width, hp, maximum, left=True):
        ratio = max(0, min(1, hp / max(1, maximum)))
        retro.meter(self.canvas, (x, y, width, 17), hp, maximum,
                    GREEN if ratio > .35 else retro.RED)
        self.text(f"HP {int(hp)}/{int(maximum)}", x, y + 23, CREAM, self.small)

    def draw_shop(self):
        self.text(self.shop_npc + " · Market", 242, 183, CREAM, self.medium)
        self.text(f"Koin {self.life.money}  /  Buka 06:00–22:00", 668, 190, GREEN)
        self.button("Beli", (245, 226, 170, 40), lambda: self.set_shop_tab("buy"), self.shop_tab == "buy")
        self.button("Jual hasil", (423, 226, 170, 40), lambda: self.set_shop_tab("sell"), self.shop_tab == "sell")
        if self.shop_npc == "Joy":
            self.button("Jual Pokémon", (601, 226, 190, 40), lambda: self.set_shop_tab("pokemon"), self.shop_tab == "pokemon")
        if self.shop_greeting:
            self.text(self.shop_greeting, 245, 263, MUTED, self.tiny)
        if self.shop_tab == "pokemon":
            self.draw_pokemon_market()
            return
        items = [k for k in BUY if (k in ("Tombak", "Busur", "Panah")) == (self.shop_npc == "Budi")] if self.shop_tab == "buy" else list(SELL)
        if self.shop_npc == "Joy" and self.shop_tab == "buy":
            self.text("Joy menerima hasil kebun, peternakan, dan buruan.", 245, 288, CREAM)
            items = []
        for i, item in enumerate(items):
            y = 284 + i * 41
            price = (BUY if self.shop_tab == "buy" else SELL)[item]
            self.text(item, 250, y + 8, CREAM, self.small)
            self.text(f"{price} koin  /  tas {self.life.bag[item]}", 424, y + 8, MUTED, self.small)
            if self.shop_tab == "buy":
                self.button("Beli 1", (694, y, 145, 35), lambda item=item: self.trade(item, True))
                if item == "Panah":
                    self.button("Beli 5", (849, y, 184, 35), lambda item=item: self.trade(item, True, 5))
            else:
                self.button("Jual 1", (694, y, 145, 35), lambda item=item: self.trade(item, False))
                self.button("Jual semua", (849, y, 184, 35), lambda item=item: self.trade(item, False, max(1, self.life.bag[item])))
        if not self.life.market_open:
            self.text("Market sudah tutup. Kembali pukul 06:00.", 245, 577, (232, 153, 102), self.small)
        self.button("Selesai · Esc", (245, 607, 788, 34), self.back, True)

    def draw_pokemon_market(self):
        if self.shop_npc != "Joy":
            self.text("Bicara dengan Joy untuk menjual Pokémon.", 245, 288, MUTED, self.small)
            return
        self.text("Pokémon aktif harus dikeluarkan di Pokémon Center sebelum dijual.",
                  245, 276, MUTED, self.tiny)
        if not self.life.pokemon_party:
            self.text("Party kosong.", 245, 328, MUTED)
        page=getattr(self,"market_page",0) % max(1,math.ceil(len(self.life.pokemon_party)/5))
        for index, pokemon_id in enumerate(self.life.pokemon_party[page*5:page*5+5]):
            y = 302 + index * 48
            detail = self.pokemon_data(pokemon_id) or {}
            name = detail.get("name", f"Pokémon #{pokemon_id}").title()
            value = self.pokemon_sale_value(pokemon_id)
            active = pokemon_id in self.life.pokemon_active
            self.box((245, y, 788, 41), (29, 39, 36), 6, (69, 91, 74))
            self.text(f"{index + 1}. {name} · Lv.{self.pokemon_level(pokemon_id)}",
                      258, y + 11, CREAM, self.small)
            self.text(f"{value} koin", 604, y + 11, retro.GOLD, self.small)
            if active:
                self.button("Aktif · Center", (735, y + 4, 137, 33),
                            lambda: self.notify("Keluarkan Pokémon ini dari tim aktif di Pokémon Center dulu."))
            elif len(self.life.pokemon_party) <= 1:
                self.button("Simpan satu", (735, y + 4, 137, 33),
                            lambda: self.notify("Simpan setidaknya satu Pokémon di party."))
            else:
                pending = self.sell_pokemon_pending == pokemon_id
                self.button("Konfirmasi jual" if pending else "Jual Pokémon",
                            (735, y + 4, 137, 33), lambda ident=pokemon_id: self.sell_party_pokemon(ident), pending)
                if pending:
                    self.button("Batal", (881, y + 4, 137, 33),
                                lambda: setattr(self, "sell_pokemon_pending", None))
        self.button("<",(245,554,60,35),lambda:setattr(self,"market_page",page-1))
        self.button(">",(973,554,60,35),lambda:setattr(self,"market_page",page+1))
        self.text(f"{page+1} / {max(1,math.ceil(len(self.life.pokemon_party)/5))}",640,568,MUTED,self.small,True)
        self.text("Pokédex tetap menyimpan catatan spesies yang pernah ditangkap.",
                  245, 596, MUTED, self.tiny)
        self.button("Selesai · Esc", (245, 625, 788, 34), self.back, True)

    def set_shop_tab(self, tab):
        self.shop_tab = tab

    def back(self):
        self.play_action_sound("ui-back", .2)
        self.mode = self.settings_return_mode if self.mode == "settings" else "game"
        pg.key.stop_text_input()
        pg.key.set_repeat()

    def to_title(self):
        self.selected = self.life.character
        self.mode = "title"

    def terminal_color(self, value, foreground=True):
        defaults = (220, 227, 211) if foreground else (17, 22, 25)
        palette = {"black": (24, 28, 30), "red": (229, 128, 118), "green": GREEN,
                   "brown": (225, 192, 120), "blue": (125, 167, 212), "magenta": (190, 146, 205),
                   "cyan": (123, 195, 192), "white": (231, 233, 220), "default": defaults}
        if value in palette:
            return palette[value]
        try:
            return tuple(bytes.fromhex(value)) if len(value) == 6 else defaults
        except (ValueError, TypeError):
            return defaults

    def draw_terminal(self):
        self.canvas.fill(INK)
        self.box((39, 28, 1202, 716), (18, 25, 26), 24, (88, 108, 91))
        self.text("NARA / PERSONAL COMPUTER".replace("NARA", self.life.player_name.upper()), 73, 53, CREAM, self.medium)
        self.text(self.terminal.shell_name.upper() + "  ·  TERMINAL LOKAL", 73, 96, GREEN, self.small)
        self.button("Terminal.app · buka", (728, 56, 214, 45), self.open_native_terminal)
        self.button("Tinggalkan PC · Esc", (956, 56, 246, 45), self.back, True)
        screen = self.terminal.screen
        for row in sorted(screen.dirty):
            if row >= screen.lines:
                continue
            yy = row * self.cell_h
            pg.draw.rect(self.terminal_cache, (17, 22, 25), (0, yy, self.terminal_area.width, self.cell_h))
            for col in range(screen.columns):
                cell = screen.buffer[row][col]
                foreground = self.terminal_color(cell.fg)
                background = self.terminal_color(cell.bg, False)
                if cell.reverse:
                    foreground, background = background, foreground
                if background != (17, 22, 25):
                    pg.draw.rect(self.terminal_cache, background, (col * self.cell_w, yy, self.cell_w, self.cell_h))
                if cell.data.strip():
                    glyph = self.mono.render(cell.data, True, foreground)
                    self.terminal_cache.blit(glyph, (col * self.cell_w, yy))
        screen.dirty.clear()
        self.canvas.blit(self.terminal_cache, self.terminal_area)
        if not screen.cursor.hidden and self.frame % 60 < 35:
            pg.draw.rect(self.canvas, GREEN, (self.terminal_area.x + screen.cursor.x * self.cell_w,
                                            self.terminal_area.y + screen.cursor.y * self.cell_h,
                                            self.cell_w, self.cell_h), 1)
        status = "LIVE · PC, ponsel, dan Terminal.app berbagi sesi" if self.terminal.running else "Sesi selesai · R untuk membuka lagi"
        if self.terminal.error:
            self.text(self.terminal.error, 88, 178, (232, 153, 102), self.small)
        elif self.terminal.bytes_received == 0:
            self.text("Membuka shell...", 88, 178, GREEN)
        self.text(status, 75, 716, GREEN, self.small)
        path = str(self.terminal.project)
        self.text("FOLDER AWAL  " + (path if len(path) < 107 else "..." + path[-104:]), 77, 749, CREAM, self.small)
        self.text("Ketik langsung · Ctrl/Cmd+V paste · F10 = Escape terminal · Esc = kembali ke dunia", 77, 771, MUTED, self.small)

    def open_native_terminal(self):
        self.notify(self.terminal.open_external())

    def terminal_key(self, event):
        if event.key == pg.K_ESCAPE:
            self.back()
            return
        if event.key == pg.K_r and not self.terminal.running:
            self.terminal.start()
            return
        mods = event.mod
        if event.key in (pg.K_PAGEUP, pg.K_PAGEDOWN) and mods & pg.KMOD_SHIFT:
            self.terminal.scroll(1 if event.key == pg.K_PAGEUP else -1)
            return
        self.terminal.return_to_bottom()
        if event.key == pg.K_v and mods & (pg.KMOD_CTRL | pg.KMOD_GUI):
            try:
                self.terminal.paste(pg.scrap.get_text())
            except pg.error:
                self.notify("Clipboard belum tersedia.")
            return
        if mods & pg.KMOD_CTRL and pg.K_a <= event.key <= pg.K_z:
            self.terminal.send(bytes([event.key - pg.K_a + 1]))
            return
        keys = {pg.K_RETURN: b"\r", pg.K_KP_ENTER: b"\r", pg.K_BACKSPACE: b"\x7f", pg.K_DELETE: b"\x1b[3~",
                pg.K_TAB: b"\x1b[Z" if mods & pg.KMOD_SHIFT else b"\t", pg.K_UP: b"\x1b[A",
                pg.K_DOWN: b"\x1b[B", pg.K_RIGHT: b"\x1b[C", pg.K_LEFT: b"\x1b[D",
                pg.K_HOME: b"\x1b[H", pg.K_END: b"\x1b[F", pg.K_PAGEUP: b"\x1b[5~", pg.K_PAGEDOWN: b"\x1b[6~",
                pg.K_F10: b"\x1b", pg.K_F1: b"\x1bOP", pg.K_F2: b"\x1bOQ", pg.K_F3: b"\x1bOR", pg.K_F4: b"\x1bOS"}
        if event.key in keys:
            self.terminal.send(keys[event.key])

    def handle(self, event):
        if event.type == pg.QUIT:
            if self.mode == "menu":
                self.quit()
            else:
                self.mode = "menu"
                pg.key.stop_text_input()
            return
        if event.type == pg.TEXTINPUT and self.mode == "terminal":
            # Keyboard shortcuts have already been forwarded by KEYDOWN.
            if not pg.key.get_mods() & (pg.KMOD_CTRL | pg.KMOD_GUI):
                self.terminal.return_to_bottom()
                self.terminal.send(event.text.encode("utf-8"))
        elif event.type == pg.TEXTINPUT and self.mode == "phone":
            self.phone_input = (self.phone_input + event.text.replace("\n", " "))[-220:]
        elif event.type == pg.TEXTINPUT and self.mode == "dex":
            self.dex_query = (self.dex_query + event.text.lower())[-32:]
            self.dex_page = 0
            self.dex_detail = None
            entries = self.dex_entries()
            if entries:
                self.select_dex(entries[0]["id"])
        if event.type == pg.MOUSEWHEEL and self.mode == "terminal":
            self.terminal.scroll(event.y)
        elif event.type == pg.MOUSEWHEEL and self.mode == "map":
            self.change_map_zoom(1.15 if event.y > 0 else 1 / 1.15)
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for rect, callback in self.buttons:
                if rect.collidepoint(self.mouse()):
                    self.play_action_sound("ui-confirm", .22)
                    callback()
                    return
            if self.mode == "map":
                point = self.mouse()
                for rect, zone in self.map_zone_rects:
                    if rect.collidepoint(point):
                        self.play_action_sound("ui-click", .16)
                        self.map_center[:] = [zone["x"] + RESERVE_ZONE_W / 2, zone["y"] + RESERVE_ZONE_H / 2]
                        self.map_zoom = max(self.map_zoom, 1.55)
                        return
        if event.type == pg.KEYDOWN:
            if self.mode in ("inventory", "shop", "weather", "dex", "center", "encounter",
                             "pokemon_info", "daily_quests", "journal", "secret_puzzle", "evolution", "settings", "hospitality", "home_decor", "map", "gate_trial"):
                if event.key in (pg.K_UP, pg.K_DOWN, pg.K_LEFT, pg.K_RIGHT, pg.K_1, pg.K_2, pg.K_3,
                                 pg.K_TAB, pg.K_PAGEUP, pg.K_PAGEDOWN):
                    self.play_action_sound("ui-click", .16)
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    self.play_action_sound("ui-confirm", .22)
            if self.mode == "terminal":
                self.terminal_key(event)
            elif self.mode == "phone":
                if event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    self.submit_phone_prompt()
                elif event.key == pg.K_BACKSPACE:
                    self.phone_input = self.phone_input[:-1]
                elif event.key == pg.K_v and event.mod & (pg.KMOD_CTRL | pg.KMOD_GUI):
                    try:
                        self.phone_input = (self.phone_input + pg.scrap.get_text().replace("\n", " "))[-220:]
                    except pg.error:
                        self.notify("Clipboard belum tersedia.")
                elif event.key in (pg.K_ESCAPE, pg.K_b):
                    self.back()
            elif self.mode == "encounter":
                if event.key in (pg.K_LEFT, pg.K_RIGHT, pg.K_UP, pg.K_DOWN):
                    self.encounter_choice = 1 - self.encounter_choice
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    (self.show_encounter_info if self.encounter_choice == 0
                     else self.choose_encounter_battle)()
                elif event.key in (pg.K_i, pg.K_1):
                    self.show_encounter_info()
                elif event.key in (pg.K_f, pg.K_2):
                    self.choose_encounter_battle()
                elif event.key == pg.K_ESCAPE:
                    self.back()
            elif self.mode == "pokemon_info":
                if event.key in (pg.K_i, pg.K_ESCAPE, pg.K_BACKSPACE):
                    self.mode = "encounter"
                elif event.key in (pg.K_RETURN, pg.K_SPACE):
                    self.choose_encounter_battle()
            elif self.mode == "map":
                if event.key in (pg.K_ESCAPE, pg.K_m):
                    self.mode = "game"
                elif event.key in (pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS):
                    self.change_map_zoom(1.25)
                elif event.key in (pg.K_MINUS, pg.K_KP_MINUS):
                    self.change_map_zoom(1 / 1.25)
                elif event.key in (pg.K_LEFT, pg.K_a):
                    self.map_center[0] = max(0, self.map_center[0] - 460 / self.map_zoom)
                elif event.key in (pg.K_RIGHT, pg.K_d):
                    self.map_center[0] = min(RESERVE_WIDTH, self.map_center[0] + 460 / self.map_zoom)
                elif event.key in (pg.K_UP, pg.K_w):
                    self.map_center[1] = max(0, self.map_center[1] - 420 / self.map_zoom)
                elif event.key in (pg.K_DOWN, pg.K_s):
                    self.map_center[1] = min(RESERVE_HEIGHT, self.map_center[1] + 420 / self.map_zoom)
            elif self.mode == "tutorial_map" and event.key in (pg.K_ESCAPE, pg.K_m):
                self.back()
            elif self.mode == "dex":
                if event.key == pg.K_TAB:
                    self.cycle_type_filter("dex_type_filter", 1)
                elif event.key == pg.K_BACKSPACE:
                    self.dex_query = self.dex_query[:-1]
                    self.dex_page = 0
                    entries = self.dex_entries()
                    if entries:
                        self.select_dex(entries[0]["id"])
                    else:
                        self.dex_detail = None
                elif event.key == pg.K_UP:
                    self.move_dex_selection(-1)
                elif event.key == pg.K_DOWN:
                    self.move_dex_selection(1)
                elif event.key == pg.K_RETURN:
                    entries = self.dex_entries()
                    if entries:
                        fallback = min(max(0, self.dex_page * 8), len(entries) - 1)
                        selected = next((item for item in entries if item["id"] == self.dex_selected),
                                        entries[fallback])
                        self.select_dex(selected["id"])
                elif event.key == pg.K_LEFT:
                    self.change_dex_page(-1)
                elif event.key == pg.K_RIGHT:
                    self.change_dex_page(1)
                elif event.key in (pg.K_ESCAPE, pg.K_p):
                    self.back()
            elif self.mode == "center":
                visible = self.center_filtered_party()
                if event.key in (pg.K_LEFT, pg.K_RIGHT):
                    self.cycle_type_filter("center_type_filter", -1 if event.key == pg.K_LEFT else 1)
                elif event.key == pg.K_UP:
                    self.move_center_selection(-1)
                elif event.key == pg.K_DOWN:
                    self.move_center_selection(1)
                elif pg.K_1 <= event.key <= pg.K_6 and event.key - pg.K_1 < len(visible):
                    self.center_selected = visible[event.key - pg.K_1][0]
                elif event.key == pg.K_v:
                    self.evolve_selected()
                elif event.key == pg.K_h:
                    self.heal_pokemon_party()
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    self.toggle_active_pokemon()
                elif event.key in (pg.K_ESCAPE, pg.K_n):
                    self.back()
            elif self.mode == "hospitality":
                if event.key == pg.K_1:
                    self.hospitality_order("meal" if self.hospitality_kind == "restaurant" else "hotel")
                elif event.key == pg.K_2 and self.hospitality_kind == "restaurant":
                    self.hospitality_order("drink")
                elif event.key in (pg.K_ESCAPE, pg.K_RETURN):
                    self.back()
            elif self.mode == "daily_quests":
                if event.key in (pg.K_ESCAPE, pg.K_j, pg.K_RETURN):
                    self.back()
            elif self.mode == "journal":
                if event.key in (pg.K_ESCAPE, pg.K_l):
                    self.back()
            elif self.mode == "secret_puzzle":
                if event.key == pg.K_ESCAPE:
                    self.back()
                elif pg.K_1 <= event.key <= pg.K_3:
                    self.resolve_secret_puzzle(event.key - pg.K_1)
            elif self.mode == "evolution":
                if event.key in (pg.K_ESCAPE, pg.K_RETURN):
                    self.finish_evolution()
            elif self.mode == "battle":
                if self.battle and self.battle.get("intro"):
                    if event.key == pg.K_ESCAPE:
                        self.finish_battle("Tantangan dibatalkan sebelum duel dimulai.")
                    return
                if event.key == pg.K_a:
                    self.pokemon_attack()
                elif event.key == pg.K_q:
                    self.pokemon_type_attack(0)
                elif event.key == pg.K_w:
                    self.pokemon_type_attack(1)
                elif event.key == pg.K_e:
                    self.pokemon_type_attack(2)
                elif event.key == pg.K_r:
                    self.pokemon_ultimate()
                elif event.key in (pg.K_1, pg.K_2, pg.K_3):
                    lineup = self.active_pokemon_team()
                    slot = event.key - pg.K_1
                    if slot < len(lineup) and not self.switch_battle_pokemon(lineup[slot]):
                        self.notify("Pokémon ini sedang KO atau sudah aktif.")
                elif event.key == pg.K_o:
                    self.pokemon_catch()
                elif event.key == pg.K_TAB:
                    self.change_battle_pokemon()
                elif event.key in (pg.K_RETURN, pg.K_ESCAPE):
                    self.finish_battle("Anda kembali menjelajah.")
            elif self.mode == "title":
                if event.key in (pg.K_1, pg.K_2, pg.K_3):
                    self.play_action_sound("ui-click", .16)
                    self.choose(event.key - pg.K_1)
                elif event.key in (pg.K_LEFT, pg.K_RIGHT):
                    self.play_action_sound("ui-click", .16)
                    self.selected = (self.selected + (1 if event.key == pg.K_RIGHT else -1)) % 3
                elif event.key == pg.K_RETURN:
                    self.play_action_sound("ui-confirm", .22)
                    self.begin()
                elif event.key == pg.K_ESCAPE:
                    self.play_action_sound("menu-open", .22)
                    self.mode = "menu"
            elif self.mode == "settings":
                if event.key in (pg.K_ESCAPE, pg.K_RETURN):
                    self.back()
            elif self.mode == "gate_trial":
                if event.key == pg.K_ESCAPE:
                    self.cancel_gate_trial()
                elif event.key in (pg.K_LEFT, pg.K_UP):
                    self.select_gate_trial_pokemon(-1)
                elif event.key in (pg.K_RIGHT, pg.K_DOWN):
                    self.select_gate_trial_pokemon(1)
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    self.begin_gate_trial_action()
            elif self.mode == "game":
                if event.key == pg.K_e:
                    self.interact()
                elif event.key == pg.K_i:
                    self.play_action_sound("inventory-open", .25)
                    self.mode = "inventory"
                elif event.key == pg.K_F1:
                    self.open_overlay("help")
                elif event.key == pg.K_ESCAPE:
                    self.play_action_sound("menu-open", .24)
                    self.mode = "menu"
                elif event.key == pg.K_SPACE:
                    if self.life.scene == "reserve" or self.closest_trainer(112):
                        self.attack_nearby_pokemon()
                    else:
                        self.attack()
                elif event.key == pg.K_r:
                    self.toggle_mount()
                elif event.key == pg.K_t:
                    self.skip_hour()
                elif event.key == pg.K_c:
                    self.open_overlay("weather")
                elif event.key == pg.K_u:
                    self.open_overlay("player_profile")
                elif event.key == pg.K_h:
                    self.use_healing_item()
                elif event.key == pg.K_b:
                    self.open_phone()
                elif event.key == pg.K_p:
                    self.open_dex()
                elif event.key == pg.K_j:
                    self.open_overlay("daily_quests")
                elif event.key == pg.K_l:
                    self.open_overlay("journal")
                elif event.key == pg.K_n:
                    self.open_pokemon_center()
                elif event.key == pg.K_m:
                    if self.life.tutorial_active:
                        self.play_action_sound("menu-open", .24)
                        self.mode = "tutorial_map"
                    else:
                        if not self.pokedex.catalog:
                            self.pokedex.request_catalog()
                        if self.life.scene == "reserve" and not self.wild_pokemon and self.pokedex.catalog:
                            self.spawn_map_pokemon()
                        self.open_global_map()
                elif event.key in (pg.K_1, pg.K_2, pg.K_3):
                    self.play_action_sound("ui-confirm", .18)
                    self.notify(self.life.equip({pg.K_1: "Tombak", pg.K_2: "Busur", pg.K_3: ""}[event.key]))
            elif self.mode == "inventory" and event.key in (pg.K_1, pg.K_2, pg.K_3, pg.K_h):
                if event.key == pg.K_h:
                    self.use_healing_item()
                else:
                    self.notify(self.life.equip({pg.K_1: "Tombak", pg.K_2: "Busur", pg.K_3: ""}[event.key]))
            elif self.mode == "player_profile" and event.key == pg.K_u:
                self.back()
            elif event.key in (pg.K_ESCAPE, pg.K_i, pg.K_F1, pg.K_RETURN):
                self.back()

    def update(self, dt):
        self.frame += dt * 60
        if self.mode == "gate_trial":
            self.update_gate_trial(dt)
        now = time.monotonic()
        queued, self.pending_action_sounds = self.pending_action_sounds, []
        for play_at, sound_name, volume in queued:
            if play_at <= now:
                self.play_action_sound(sound_name, volume)
            else:
                self.pending_action_sounds.append((play_at, sound_name, volume))
        self.footstep_timer = max(0.0, self.footstep_timer - dt)
        if self.door_close_timer > 0:
            self.door_close_timer = max(0.0, self.door_close_timer - dt)
            if self.door_close_timer == 0:
                self.play_action_sound("door-wood-close", .28)
        self.update_location_audio()
        self.terminal.poll()
        self.load_countdown_audio()
        self.load_pokemon_events()
        if self.phone_terminal.phone_marker and any(self.phone_terminal.phone_marker in row for row in self.phone_terminal.screen.display):
            self.phone_terminal.phone_marker = ""
            self.phone_complete = True
            self.phone_status = "Respons terminal selesai. Notifikasi ponsel baru tersedia."
            self.phone_unread = True
            self.notify("PONSEL: OpenCode selesai merespons · notifikasi baru diterima.")
        self.environment.update(dt)
        self.moving = False
        active = self.mode in ("game", "map", "tutorial_map", "terminal", "inventory", "shop", "weather", "phone", "dex", "center", "battle", "encounter", "pokemon_info", "interaction_picker", "daily_quests", "journal", "secret_puzzle", "evolution", "settings", "hospitality", "home_decor", "dead")
        if active:
            if self.mode == "game":self.ensure_walkable_position()
            if self.mode == "map" and not self.wild_pokemon and self.pokedex.catalog:
                self.spawn_map_pokemon()
            if self.mode == "battle":
                self.update_battle(dt)
            elif self.mode == "evolution":
                self.update_evolution(dt)
            self.attack_cooldown = max(0, self.attack_cooldown - dt)
            self.attack_flash = max(0, self.attack_flash - dt)
            if self.mode == "game" and not self.fishing and self.battle is None:
                keys = pg.key.get_pressed()
                reserve_zone = self.reserve_zone_at(self.life.x, self.life.y) if self.life.scene == "reserve" else None
                direction = pg.Vector2(int(keys[pg.K_d] or keys[pg.K_RIGHT]) - int(keys[pg.K_a] or keys[pg.K_LEFT]),
                                      int(keys[pg.K_s] or keys[pg.K_DOWN]) - int(keys[pg.K_w] or keys[pg.K_UP]))
                if direction.length_squared():
                    self.moving = True
                    self.facing = "left" if abs(direction.x) >= abs(direction.y) and direction.x < 0 else "right" if abs(direction.x) >= abs(direction.y) else "up" if direction.y < 0 else "down"
                    speed = 300 if self.life.mounted else 180 if self.life.stats["Energi"] > 10 else 105
                    if self.needs_depleted():
                        speed = 58 if self.life.mounted else 72
                    if self.life.scene in OUTSIDE and self.life.weather == "Salju":
                        speed *= .8
                    elif self.life.scene in OUTSIDE and self.life.weather == "Hujan":
                        # Wet paths are a little slower, while rain still helps
                        # Water/Grass battle types through the existing weather rules.
                        speed *= .92 if self.life.scene in ("coast", "mountain") else .86
                    elif self.life.scene in OUTSIDE and self.life.weather == "Badai":
                        speed *= .76
                    layout=reserve_layout(reserve_index_at(self.life.x,self.life.y)) if self.life.scene=="reserve" else scene_layout(self.life.scene) if self.life.scene in OUTSIDE else None
                    if layout:
                        lx=self.life.x%1280 if self.life.scene=="reserve" else self.life.x
                        ly=self.life.y%1600 if self.life.scene=="reserve" else self.life.y
                        if any(pg.Rect(r).collidepoint(lx,ly) for r in layout.get("ice",())):speed*=.82
                    step = direction.normalize() * dt * speed
                    for axis in ("x", "y"):
                        before = getattr(self.life, axis)
                        setattr(self.life, axis, before + getattr(step, axis))
                        feet = pg.Rect(self.life.x - 12, self.life.y - 12, 24, 14)
                        if any(feet.colliderect(rect) for rect in self.obstacles()):
                            setattr(self.life, axis, before)
                    if self.life.scene == "reserve":
                        zone = reserve_zone or self.reserve_zone_at(self.life.x, self.life.y)
                        self.life.x = max(zone["x"] + 28, min(zone["x"] + RESERVE_ZONE_W - 28, self.life.x))
                        self.life.y = max(zone["y"] + 155, min(zone["y"] + RESERVE_ZONE_H - 28, self.life.y))
                    elif self.life.scene in OUTSIDE:
                        self.check_edges()
                        self.life.x = max(30, min(1250, self.life.x))
                        self.life.y = max(156, min(664, self.life.y))
                    else:
                        self.life.x = max(211, min(1070, self.life.x))
                        self.life.y = max(281, min(655, self.life.y))
            if self.life.mounted:
                self.life.horse_x, self.life.horse_y, self.life.horse_scene = self.life.x, self.life.y, self.life.scene
            if self.mode == "game" and self.moving and self.footstep_timer <= 0:
                footstep = ("step-wood" if self.life.scene in ("house", "bedroom", "market")
                            else "step-dirt" if self.life.scene in ("forest", "reserve", "coast", "mountain")
                            else "step-grass")
                self.play_action_sound(footstep, .19 if not self.life.mounted else .13)
                self.footstep_timer = .43 if self.life.mounted else .31
            self.life.tick(dt, self.moving)
            self.ensure_farm_drops()
            self.check_daily_quest_rewards()
            self.update_world_events()
            if self.life.world_trainer_xp:
                self.award_trainer_xp(self.life.world_trainer_xp)
                self.life.world_trainer_xp = 0
            if self.life.story_notice:
                self.notify(self.life.story_notice)
                self.life.story_notice = ""
                self.save_current()
            health_before_animals = self.life.health
            self.wildlife.update(dt, self.obstacles("forest"), player_active=self.mode not in ("terminal", "phone", "dex", "battle", "encounter", "pokemon_info", "interaction_picker", "dead"))
            if self.life.health < health_before_animals and self.life.scene == "forest":
                attackers = [animal for animal in self.wildlife.living
                             if animal["species"] in ("Singa", "Hyena", "Babi hutan")
                             and math.hypot(animal["x"] - self.life.x, animal["y"] - self.life.y) < 100]
                if attackers:
                    self.play_action_sound("wildlife-hurt", .28)
                    self.play_wildlife_call(attackers[0]["species"])
            if self.mode == "game":
                if self.life.scene == "reserve":
                    if not self.wild_pokemon and self.pokedex.catalog:
                        self.spawn_map_pokemon()
                    self.update_reserve_pokemon(dt)
                self.update_trainers(dt)
            if self.life.scene == "forest":
                self.update_arrows(dt)
            if self.life.health <= 0 and not self.dead_active:
                self.start_dead_screen()
            if self.dead_active:
                self.dead_timer = max(0.0, self.dead_timer - dt)
                if self.dead_timer <= 0:
                    self.respawn()
            if self.fishing and time.monotonic() - self.fishing > 4.2:
                self.fishing = None
                self.notify("Ikannya lepas. Tekan E untuk mencoba lagi.")
            if self.life.elapsed - self.last_save > 15:
                self.save_current()
                self.last_save = self.life.elapsed

    def check_edges(self):
        if not 345 <= self.life.y <= 465:
            return
        if self.life.scene == "outdoors":
            if self.life.x < 35:
                self.transition("forest", 1204, 410)
                self.notify("Hutan liar. Singa berburu pagi & sore. Space: gunakan senjata.")
            elif self.life.x > 1245:
                self.transition("market", 75, 410)
                self.notify("Market: dekati NPC lalu E untuk membeli atau menjual.")
        elif self.life.scene == "forest" and self.life.x > 1245:
            self.transition("outdoors", 75, 410)
        elif self.life.scene == "market" and self.life.x < 35:
            self.transition("outdoors", 1204, 410)

    def update_arrows(self, dt):
        remaining = []
        for arrow in self.projectiles:
            distance = dt * 440
            arrow["x"] += arrow["dx"] * distance
            arrow["y"] += arrow["dy"] * distance
            arrow["travel"] += distance
            hit = False
            for animal in self.wildlife.living:
                size = SPECIES[animal["species"]]["size"]
                if math.hypot(arrow["x"] - animal["x"], arrow["y"] - (animal["y"] - size * .45)) < size * .34 + 6:
                    self.notify(self.wildlife.hit(animal, WEAPONS["Busur"]["damage"]))
                    self.play_action_sound("wildlife-hurt", .4)
                    self.play_wildlife_call(animal["species"])
                    if animal["hp"] <= 0: self.tutorial_advance("hunt")
                    hit = True
                    break
            if not hit and arrow["travel"] < WEAPONS["Busur"]["reach"] and not any(r.collidepoint(arrow["x"], arrow["y"]) for r in self.obstacles("forest")):
                remaining.append(arrow)
        self.projectiles = remaining

    def draw(self):
        self.buttons = []
        if self.mode == "title":
            self.title()
        elif self.mode == "terminal":
            self.draw_terminal()
        else:
            self.draw_world()
            if self.mode == "game":
                self.draw_world_event()
            if self.mode != "game":
                self.overlay()
        sw, sh = self.window.get_size()
        scale = min(sw / W, sh / H)
        scaled_size = (int(W * scale), int(H * scale))
        image = self.canvas if scaled_size == (W, H) else pg.transform.scale(self.canvas, scaled_size)
        self.window.fill((18, 27, 23))
        self.window.blit(image, ((sw - image.get_width()) // 2, (sh - image.get_height()) // 2))
        pg.display.flip()

    def quit(self):
        self.save_current()
        self.running = False

    def run(self):
        try:
            while self.running:
                dt = min(.05, self.clock.tick(60) / 1000)
                for event in pg.event.get():
                    self.handle(event)
                self.update(dt)
                self.draw()
        finally:
            self.save_current()
            self.terminal.close()
            pg.quit()


from adventure_flow import FlowMixin, TUTORIAL_STEPS
from fighter import FighterMixin

from online_ui import OnlineMixin

class Game(OnlineMixin, FlowMixin, FighterMixin, LegacyGame):
    pass

def main():
    parser = argparse.ArgumentParser(description="OpenRPG — RPG kehidupan dengan PC terminal shell asli")
    parser.add_argument("--project", type=Path, default=ROOT / "computer-workspace", help="Folder awal terminal PC")
    parser.add_argument("--shell", help="Shell terminal, default mengikuti SHELL")
    args = parser.parse_args()
    Game(args.project, shell=args.shell).run()


if __name__ == "__main__":
    main()
