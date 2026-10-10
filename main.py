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
        self.dex_sprite = None
        self.pokemon_rng = random.Random()
        self.pokemon_encounter_clock = 0.0
        self.battle = None
        self.encounter_target = None
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
        ]
        self.center_selected = 0
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
        return [("Sari", 415 + math.sin(self.life.elapsed / 6) * 13, 350, "Woman", "Makanan & obat"),
                ("Budi", 902 + math.sin(self.life.elapsed / 7) * 12, 350, "Hunter", "Senjata & panah"),
                ("Danu", 673 + math.sin(self.life.elapsed / 8) * 13, 594, "OldMan", "Pembeli hasil panen")]

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
            result += [("restaurant", 780, 590, "Restoran · makan & minum"),
                       ("hotel", 880, 620, "Hotel · tidur & pulihkan kebutuhan")]
            for i in range(6):
                result.append((f"crop{i}", 580 + i % 3 * 62, 440 + i // 3 * 69, "Kebun: tanam / siram / panen"))
            if self.life.horse_scene == "outdoors" and not self.life.mounted:
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            return result
        if self.life.scene == "forest":
            result = [("farm", 1237, 405, "Kembali ke rumah"), ("wood", 645, 555, "Kumpulkan kayu"),
                      ("reserve", 650, 177, "Jelajahi suaka Pokémon ke utara"),
                      ("restaurant", 300, 475, "Restoran hutan · makan & minum"),
                      ("hotel", 980, 475, "Penginapan hutan · pulihkan kebutuhan")]
            if self.life.horse_scene == "forest" and not self.life.mounted:
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            return result
        if self.life.scene == "reserve":
            result = [("forest", 92, 800, "Kembali ke hutan")]
            zone = self.reserve_zone_at(self.life.x, self.life.y)
            result += [("restaurant", zone["x"] + 250, zone["y"] + 1070, "Restoran · makan & minum"),
                       ("hotel", zone["x"] + 1030, zone["y"] + 1070, "Hotel · tidur & pulihkan kebutuhan")]
            zone_centers = [(x, y) for x, y in RESERVE_CENTERS
                            if zone["x"] <= x < zone["x"] + RESERVE_ZONE_W
                            and zone["y"] <= y < zone["y"] + RESERVE_ZONE_H]
            if not zone_centers:
                zone_centers = [(zone["x"] + RESERVE_ZONE_W // 2,
                                 zone["y"] + RESERVE_ZONE_H // 2 + 155)]
            result.extend(("center", x, y, "Pokémon Center · periksa, pulihkan, evolusi")
                          for x, y in zone_centers)
            result.extend(("gate:" + gate["direction"], gate["x"], gate["y"],
                           ("Gerbang terkunci · Lv." + str(gate["required_level"])
                            if self.player_progress_level() < gate["required_level"]
                            else "Gerbang · " + gate["target"]["name"]))
                          for gate in self.reserve_gates())
            if not self.life.mounted and self.life.horse_scene == "reserve":
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            return result
        if self.life.scene == "coast":
            return [("reserve", 50, 410, "Kembali ke suaka"), ("restaurant", 280, 500, "Restoran pantai · makan & minum"),
                    ("hotel", 1050, 500, "Hotel pantai · pulihkan kebutuhan")]
        if self.life.scene == "mountain":
            return [("reserve", 640, 640, "Kembali ke suaka"), ("restaurant", 290, 560, "Restoran gunung · makan & minum"),
                    ("hotel", 1000, 560, "Hotel gunung · pulihkan kebutuhan")]
        if self.life.scene == "market":
            result = [("farm", 43, 405, "Kembali ke rumah")]
            result += [("restaurant", 700, 610, "Restoran · makan & minum"),
                       ("hotel", 960, 610, "Hotel · tidur & pulihkan kebutuhan")]
            result += [("npc_" + name, x, y + 25, f"Bicara dengan {name}") for name, x, y, _, _ in self.npcs()]
            if self.life.horse_scene == "market" and not self.life.mounted:
                result.append(("horse", self.life.horse_x, self.life.horse_y, "Naik kuda · R"))
            return result
        if self.life.scene == "house":
            return [("outside", 640, 662, "Keluar rumah"), ("kitchen", 356, 306, "Masak makanan"),
                    ("water", 247, 308, "Minum air"), ("table", 596, 453, "Makan di meja"),
                    ("sofa", 888, 475, "Bersantai"), ("room", 1015, 235, "Masuk kamar")]
        return [("living", 640, 662, "Ke ruang keluarga"), ("bed", 370, 414, "Tidur & pulihkan energi"),
                ("pc", 899, 369, "Gunakan PC · terminal asli")]

    def reserve_gates(self):
        """Return neighboring biome gates around the player's current region."""
        col = max(0, min(RESERVE_COLUMNS - 1, int(self.life.x // RESERVE_ZONE_W)))
        row = max(0, min(RESERVE_ROWS - 1, int(self.life.y // RESERVE_ZONE_H)))
        zone = RESERVE_ZONES[row * RESERVE_COLUMNS + col]
        gates = []
        for direction, dc, dr in (("utara", 0, -1), ("selatan", 0, 1),
                                  ("barat", -1, 0), ("timur", 1, 0)):
            nc, nr = col + dc, row + dr
            if not (0 <= nc < RESERVE_COLUMNS and 0 <= nr < RESERVE_ROWS):
                continue
            target_index = nr * RESERVE_COLUMNS + nc
            target = RESERVE_ZONES[target_index]
            if direction == "utara":
                x, y = zone["x"] + RESERVE_ZONE_W // 2, zone["y"] + 155
            elif direction == "selatan":
                x, y = zone["x"] + RESERVE_ZONE_W // 2, zone["y"] + RESERVE_ZONE_H - 28
            elif direction == "barat":
                x, y = zone["x"] + 28, zone["y"] + RESERVE_ZONE_H // 2
            else:
                x, y = zone["x"] + RESERVE_ZONE_W - 28, zone["y"] + RESERVE_ZONE_H // 2
            gates.append({"direction": direction, "x": x, "y": y, "target": target,
                          "col": nc, "row": nr,
                          "required_level": RESERVE_LEVEL_REQUIREMENTS[target_index]})
        return gates

    def player_progress_level(self):
        levels = [self.pokemon_level(ident) for ident in self.life.pokemon_party]
        return max(levels, default=1)

    def travel_reserve_gate(self, direction):
        gate = next((item for item in self.reserve_gates() if item["direction"] == direction), None)
        if not gate:
            return
        if self.player_progress_level() < gate["required_level"]:
            self.notify(f"Gerbang terkunci. Butuh Pokémon Lv.{gate['required_level']} · tim tertinggi Lv.{self.player_progress_level()}.")
            return
        target = gate["target"]
        if direction == "timur":
            x, y = target["x"] + 115, target["y"] + RESERVE_ZONE_H // 2
        elif direction == "barat":
            x, y = target["x"] + RESERVE_ZONE_W - 115, target["y"] + RESERVE_ZONE_H // 2
        elif direction == "selatan":
            x, y = target["x"] + RESERVE_ZONE_W // 2, target["y"] + 135
        else:
            x, y = target["x"] + RESERVE_ZONE_W // 2, target["y"] + RESERVE_ZONE_H - 135
        self.life.x, self.life.y = x, y
        if self.life.mounted:
            self.life.horse_x, self.life.horse_y = x, y
        self.projectiles.clear()
        self.spawn_map_pokemon()
        self.notify(f"Memasuki {target['name']} · {target['biome']} · Pokémon lebih langka dan kuat")

    def obstacles(self, scene=None):
        scene = scene or self.life.scene
        trees = self.art.tree_obstacles(scene)
        if scene == "outdoors":
            return trees + [pg.Rect(181, 170, 340, 132), pg.Rect(824, 176, 217, 118), pg.Rect(930, 477, 288, 91), pg.Rect(1026, 568, 192, 100)]
        if scene == "forest":
            return trees
        if scene == "reserve":
            return trees + [pg.Rect(288, 288, 192, 144), pg.Rect(1792, 1120, 192, 144), pg.Rect(78, 566, 158, 105)]
        if scene == "coast":
            return trees + [pg.Rect(600, 240, 256, 192)]
        if scene == "mountain":
            return trees + [pg.Rect(535, 135, 50, 590), pg.Rect(704, 135, 50, 590)]
        if scene == "market":
            return trees + [pg.Rect(320, 220, 194, 112), pg.Rect(809, 220, 194, 112), pg.Rect(576, 493, 194, 83)]
        if scene == "house":
            return [pg.Rect(204, 194, 301, 71), pg.Rect(539, 335, 150, 75), pg.Rect(832, 388, 207, 49)]
        return [pg.Rect(284, 216, 176, 150), pg.Rect(804, 227, 253, 98)]

    def nearest(self):
        found = min(self.stations(), key=lambda s: math.hypot(s[1] - self.life.x, s[2] - self.life.y))
        return found if math.hypot(found[1] - self.life.x, found[2] - self.life.y) < 81 else None

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
        if self.life.mounted:
            self.life.horse_scene, self.life.horse_x, self.life.horse_y = scene, x, y
        self.fishing = None
        self.projectiles.clear()
        self.save_current()

    def interact(self):
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
            else:
                self.play_action_sound("ui-error", .35)
                self.notify("Terlalu cepat! Tunggu tulisan TARIK muncul.")
            self.fishing = None
            return
        if self.life.scene == "reserve":
            pokemon = self.closest_pokemon(155)
            if pokemon:
                self.open_pokemon_encounter(pokemon)
                return
        station = self.nearest()
        if not station:
            if self.life.scene == "reserve":
                pokemon = self.closest_pokemon(150)
                trainer = self.closest_trainer(112)
                if pokemon or trainer:
                    self.attack_nearby_pokemon()
                    return
            self.play_action_sound("ui-error", .32)
            self.notify("Dekati Pokémon / pelatih lalu tekan Space, atau dekati benda dan tekan E.")
            return
        action = station[0]
        if action in ("restaurant", "hotel"):
            self.play_action_sound("menu-open", .32)
            self.hospitality_kind = action
            self.mode = "hospitality"
            return
        if action.startswith("gate:"):
            self.travel_reserve_gate(action.split(":", 1)[1])
            return
        if action in ("reserve", "coast", "mountain"):
            x, y = {"reserve": (100, 800), "coast": (70, 410), "mountain": (640, 680)}[action]
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
            self.shop_tab = "sell" if self.shop_npc == "Danu" else "buy"
            self.sell_pokemon_pending = None
            self.play_action_sound("shop-bell", .32)
            self.mode = "shop"
            return
        if action == "home":
            self.transition("house", 640, 608)
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
            elif stage == "ready":
                self.play_action_sound("harvest-pop", .5)
                self.play_action_sound("pickup-item", .25)
            else:
                self.play_action_sound("ui-error", .25)
            self.notify(result)
        elif action == "ranch":
            fed_at = self.life.fed_at
            result = self.life.feed()
            if self.life.fed_at != fed_at:
                self.play_action_sound("chicken", .28)
                self.queue_action_sound("egg-collect", .24, .4)
            else:
                self.play_action_sound("ui-error", .25)
            self.notify(result)
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
            else:
                self.play_action_sound("ui-error", .25)
        elif action == "water":
            self.life.boost("Minum", 45)
            self.play_action_sound("drink", .38)
            self.notify("Segelas air segar. Minum +45.")
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
        elif action == "pc":
            self.terminal.start()
            self.mode = "terminal"
            self.life.complete("Menggunakan PC")
            pg.key.start_text_input()
            pg.key.set_repeat(350, 35)

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
        if self.life.bag.get(item, 0) != quantity_before:
            self.play_action_sound("buy" if buying else "sell-coins", .34)
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
        if self.shop_npc != "Danu" or not self.life.market_open:
            self.notify("Pokémon hanya bisa dijual kepada Danu saat market buka.")
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
        self.notify(f"{name} dijual kepada Danu seharga {value} koin.")
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
        for entry in entries:
            ident = int(entry.get("id", 0))
            if ident > 0:
                roaming_pools[(12 + ident % 4) if ident in RARE_POKEMON_IDS else (ident * 7 + 3) % len(RESERVE_ZONES)].append(entry)
        # Put familiar, already-cached sprites in the entrance clearing first.
        for pokemon_id, (x, y) in zip((1, 15, 16), ((265, 665), (700, 880), (1060, 665))):
            item = by_id.get(pokemon_id)
            if item and self.loaded_reserve_zone == 0:
                self.wild_pokemon.append({"id": pokemon_id, "x": float(x), "y": float(y), "home_x": float(x), "home_y": float(y),
                                          "moving": False, "state": "idle", "timer": self.pokemon_rng.uniform(1, 4), "vx": 0, "vy": 0, "level": 5, "requested": False})
                self.pokedex.request(pokemon_id)
        self.reserve_trainers = []
        trainer_names = ["Mira", "Raka", "Sari", "Danu", "Laras", "Banyu", "Genta", "Salju", "Awan", "Kirana", "Batu", "Reruntuhan", "Penjaga Purba", "Penjaga Palung", "Penjaga Naga", "Juara Legenda"]
        for index, zone in enumerate(RESERVE_ZONES):
            if index != self.loaded_reserve_zone:
                continue
            cx, cy = zone["x"] + RESERVE_ZONE_W // 2, zone["y"] + RESERVE_ZONE_H // 2
            level = 5 + index * 4
            trainer = {"id": f"ranger-{index}", "name": trainer_names[index], "x": float(cx), "y": float(cy), "zone": index,
                       "team": [biome_ids[index][0], biome_ids[index][min(1, len(biome_ids[index])-1)], biome_ids[index][-1]], "level": level,
                       "target": (cx + 90, cy), "defeated": False, "paid": False, "cooldown": 0}
            if index == len(RESERVE_ZONES) - 1:
                trainer["id"] = "arena-champion"
            self.reserve_trainers.append(trainer)
            pool = [by_id[i] for i in biome_ids[index] if i in by_id]
            if not pool:
                pool = [entry for entry in entries if entry.get("id", 0) > 0]
            # Eight encounters per biome, with two additional rare slots in
            # distant regions. Sprite data is fetched only near the player.
            for slot in range(8 + (2 if index >= 8 else 0)):
                for attempt in range(50):
                    x = self.pokemon_rng.randint(zone["x"] + 110, zone["x"] + RESERVE_ZONE_W - 110)
                    y = self.pokemon_rng.randint(zone["y"] + 180, zone["y"] + RESERVE_ZONE_H - 150)
                    if math.hypot(x - 100, y - 800) < 180 and index == 0:
                        continue
                    if any(math.hypot(p["x"] - x, p["y"] - y) < 105 for p in self.wild_pokemon):
                        continue
                    if any(rect.collidepoint(x, y) for rect in self.obstacles("reserve")):
                        continue
                    break
                else:
                    continue
                choices = pool
                if roaming_pools[index] and self.pokemon_rng.random() < .24:
                    choices = roaming_pools[index]
                rare_chance = min(.72, max(0.0, (index - 5) * .075))
                if index >= 5 and self.pokemon_rng.random() < rare_chance:
                    rare = [entry for entry in entries if entry.get("id", 0) in RARE_POKEMON_IDS]
                    if rare:
                        choices = rare
                item = self.pokemon_rng.choice(choices)
                is_rare = int(item["id"]) in RARE_POKEMON_IDS
                lv = level + self.pokemon_rng.randint(0, 5) + (5 if is_rare else 0)
                self.wild_pokemon.append({"id": item["id"], "x": float(x), "y": float(y), "home_x": float(x), "home_y": float(y),
                                          "moving": False, "state": "idle", "timer": self.pokemon_rng.uniform(1, 4), "vx": 0, "vy": 0,
                                          "level": lv, "requested": False, "zone": index, "rare": is_rare})

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
        if trainer and int(trainer.get("level", 0)) > 20:
            opponent_lineup = list(dict.fromkeys(int(ident) for ident in trainer.get("team", [])[:3]))
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
        self.life.pokemon_seen = list(dict.fromkeys(self.life.pokemon_seen + [pokemon_id]))
        self.save_current()
        arena_style = self.pokemon_rng.choice(("meadow", "water", "cave", "sky"))
        battle_weather = self.pokemon_rng.choice(("Cerah", "Berawan", "Hujan", "Salju", "Badai"))
        self.battle = {"wild_id": pokemon_id, "opponent_lineup": opponent_lineup, "opponent_index": 0,
                       "music_track": self.choose_battle_music(),
                       "player_id": living[0], "player_lineup": team, "phase": "Memuat Pokémon…",
                       "player_x": 350.0, "enemy_x": 760.0, "player_y": 0.0, "enemy_y": 0.0,
                       "player_vy": 0.0, "player_facing": 1, "player_cooldown": 0.0,
                       "enemy_cooldown": 1.4, "enemy_ai_timer": .6, "enemy_action": "approach",
                       "enemy_target_x": 760.0, "enemy_target_y": 0.0, "enemy_guard_timer": 0.0,
                       "special_cooldown": 0.0, "hit_flash": 0.0,
                       "enemy_flash": 0.0, "block_flash": 0.0, "attack_flash": 0.0,
                       "attack_heavy": False, "type_cooldown": 0.0, "super_meter": 0.0,
                       "result": "", "trainer": trainer, "wild": wild,
                       "wild_level": wild.get("level", 5) if wild else (trainer.get("level", 5) if trainer else 5), "vfx": None,
                       "time_left": 60.0, "timeout": False, "fruit_timer": self.pokemon_rng.uniform(3.0, 6.0),
                       "fruits": [],
                       "platforms": self.random_battle_platforms(),
                       "arena_style": arena_style, "battle_weather": battle_weather, "api_moves": [],
                       "intro": {"step": "player", "timer": 1.35, "index": 0, "cry_requested": False, "cry_played": False},
                       "rewarded": False}
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
        return self.pokedex.details.get(int(pokemon_id))

    @staticmethod
    def base_stat(detail, name, default):
        if not detail:
            return default
        for item in detail.get("stats", []):
            if item.get("stat", {}).get("name") == name:
                return int(item.get("base_stat", default))
        return default

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
        if trainer and complete and battle.get("wild_hp", 1) <= 0 and battle.get("player_hp", 0) > 0:
            if not trainer.get("paid"):
                reward = 35 + trainer.get("level", 5) * 3
                self.life.money += reward
                trainer["paid"] = True
                message = f"{trainer['name']} kalah! +{reward} koin dan Pokémon mendapat pengalaman. " + message
            trainer["defeated"] = True
            trainer["cooldown"] = 35
            self.save_current()
        self.battle = None
        self.mode = "game"
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
        xp = int(getattr(self.life, "trainer_xp", 0)) + max(0, int(amount))
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
        nearby = [t for t in trainers if t.get("cooldown", 0) <= 0 and math.hypot(t["x"] - self.life.x, t["y"] - self.life.y) <= max_distance]
        return min(nearby, key=lambda t: math.hypot(t["x"] - self.life.x, t["y"] - self.life.y), default=None)

    def attack_nearby_pokemon(self):
        if self.life.scene == "reserve":
            pokemon = self.closest_pokemon(155)
            if pokemon:
                self.open_pokemon_encounter(pokemon)
                return
        trainer = self.closest_trainer()
        if trainer:
            if trainer.get("team"):
                self.begin_pokemon_battle(trainer["team"][0], trainer=trainer)
                return
        if self.life.scene == "reserve" and self.closest_pokemon(150, include_hidden=True):
            self.notify("Ada gerakan di semak! Dekati pelan-pelan atau coba serang saat Pokémon terlihat.")
            return
        self.attack()

    def open_pokemon_encounter(self, pokemon):
        self.encounter_target = pokemon
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
                "grunt_02": "grunt_02.ogg",
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
        opposing = {entry["type"]["name"] for entry in enemy.get("types", [])}
        super_effective = {"fire": {"grass", "ice", "bug", "steel"}, "water": {"fire", "ground", "rock"},
                           "grass": {"water", "ground", "rock"}, "electric": {"water", "flying"},
                           "ice": {"grass", "ground", "flying", "dragon"}, "fighting": {"normal", "ice", "rock", "dark", "steel"},
                           "ground": {"fire", "electric", "poison", "rock", "steel"}, "psychic": {"fighting", "poison"},
                           "fairy": {"fighting", "dragon", "dark"}}
        if opposing & super_effective.get(move_type, set()):
            damage = int(damage * 1.45)
            b["phase"] = f"Sangat efektif! {move_name} −{damage} HP!"
        if guarded:
            damage = max(1, int(damage * .45))
            b["phase"] = f"Lawan menangkis {move_name}! −{damage} HP."
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
        types = team.get("types", [])
        move_type = types[b.get("move_slot", 0) % len(types)]["type"]["name"] if types else "normal"
        ultimate_emoji = ULTIMATE_EMOJI.get(move_type, "✨")
        move_name = ultimate_emoji + " Ultimate " + TYPE_MOVES.get(move_type, TYPE_MOVES["normal"])[0]
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
        if b.get("enemy_guard_timer", 0) > 0:
            damage = int(damage * .72)
        b["wild_hp"] = max(0, b["wild_hp"] - damage)
        b["enemy_flash"] = .55
        if b["wild_hp"] <= 0:
            self._win_battle()

    def _win_battle(self):
        b = self.battle
        self.queue_pokemon_cry(b["player_id"])
        trainer = b.get("trainer")
        lineup = b.get("opponent_lineup", [b["wild_id"]])
        has_next = bool(trainer and b.get("opponent_index", 0) + 1 < len(lineup))
        if not has_next and not b.get("victory_announced"):
            b["victory_announced"] = True
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
        b["wild_level"] = min(100, int(b.get("trainer", {}).get("level", 20)) + index * 2)
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
        # A fainted Pokémon is much easier to catch, but a standard Poké Ball
        # should never guarantee the capture. Low HP improves the odds.
        hp_ratio = self.battle["wild_hp"] / max(1, self.battle["wild_max"])
        chance = min(90, 25 + int(65 * (1 - hp_ratio)))
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
        self.battle["phase"] = f"Poké Ball dilempar! Peluang tertangkap {chance}%"

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
            self.life.pokemon_caught = list(dict.fromkeys(self.life.pokemon_caught + [pokemon_id]))
            self.life.record_daily_quest("catch", 1)
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
            self.finish_battle(f"Berhasil menangkap {name}! {placement}")
            return True
        elif phase == "break":
            b["capture"] = None
            b["phase"] = "Pokémon lepas dari bola! Tetap bergerak dan coba lagi."
        return True

    def update_battle(self, dt):
        b = self.battle
        if not b or "wild_hp" not in b:
            return
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
        if not b.get("result") and not b.get("capture"):
            b["time_left"] = max(0.0, b.get("time_left", 60.0) - dt)
            if b["time_left"] <= 0:
                b["timeout"] = True
                b["result"] = ("Waktu habis! O untuk mencoba menangkap · Esc untuk melewati duel"
                                if not b.get("trainer") else "Waktu habis! Lawan tidak dapat ditangkap · Esc untuk melewati")
                b["phase"] = "Batas duel 60 detik tercapai."
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
        # Random fruits appear on the arena floor and can be collected by
        # walking into them. They restore health or shorten move cooldowns.
        b["fruit_timer"] -= dt
        if b["fruit_timer"] <= 0 and len(b.get("fruits", [])) < 2:
            b.setdefault("fruits", []).append({
                "x": self.pokemon_rng.randint(180, 1140), "y": 0,
                "kind": self.pokemon_rng.choice(("health", "energy", "skill")),
                "emoji": self.pokemon_rng.choice(("🍎", "🍓", "🍊", "🍇"))})
            b["fruit_timer"] = self.pokemon_rng.uniform(6, 10)
        remaining_fruits = []
        for fruit in b.get("fruits", []):
            if abs(fruit["x"] - b["player_x"]) < 48 and abs(fruit["y"] - b.get("player_y", 0)) < 50:
                if fruit["kind"] == "health":
                    b["player_hp"] = min(b["player_max"], b["player_hp"] + 16)
                    self.life.pokemon_health[str(b["player_id"])] = b["player_hp"]
                    b["phase"] = f"{fruit['emoji']} Buah pemulih! +16 HP."
                elif fruit["kind"] == "energy":
                    b["super_meter"] = min(100, b.get("super_meter", 0) + 24)
                    b["phase"] = f"{fruit['emoji']} Buah energi! Ultimate +24%."
                else:
                    b["type_cooldown"] = 0
                    b["special_cooldown"] = 0
                    for key in b.get("cooldowns", {}):
                        b["cooldowns"][key] = max(0, b["cooldowns"][key] - 2.0)
                    b["phase"] = f"{fruit['emoji']} Buah cepat! Jurus siap dipakai."
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

    def prepare_battle(self):
        if not self.battle:
            return
        enemy = self.pokemon_data(self.battle["wild_id"])
        team = self.pokemon_data(self.battle["player_id"])
        if not enemy or not team:
            return
        b = self.battle
        b["wild_max"] = max(10, self.base_stat(enemy, "hp", 45) + int(b.get("wild_level", 5) * 2.2))
        b.setdefault("wild_hp", b["wild_max"])
        b["wild_hp"] = min(b["wild_hp"], b["wild_max"])
        player_id = str(b["player_id"])
        b["player_max"] = max(10, self.base_stat(team, "hp", 45) + self.pokemon_level(int(player_id)) * 2)
        b.setdefault("player_hp", self.life.pokemon_health.get(player_id, b["player_max"]))
        b["player_hp"] = min(b["player_hp"], b["player_max"])
        self.life.pokemon_health[player_id] = b["player_hp"]
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
        return int(self.life.pokemon_party[self.center_selected])

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

    def evolution_target(self, pokemon_id):
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
                        if trigger == "level-up" and current_level >= required:
                            child_url = child.get("species", {}).get("url", "")
                            try:
                                return int(child_url.rstrip("/").split("/")[-1]), child["species"]["name"]
                            except (ValueError, KeyError, AttributeError):
                                pass
                return None
            for child in link.get("evolves_to", []):
                result = walk(child)
                if result:
                    return result
            return None
        return walk(chain.get("chain", {}))

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
        self.life.pokemon_party = list(dict.fromkeys(new_id if value == pokemon_id else value for value in self.life.pokemon_party))
        self.life.pokemon_active = list(dict.fromkeys(new_id if value == pokemon_id else value for value in self.life.pokemon_active))[:3]
        self.life.pokemon_caught = list(dict.fromkeys(self.life.pokemon_caught + [new_id]))
        self.life.pokemon_seen = list(dict.fromkeys(self.life.pokemon_seen + [new_id]))
        self.life.pokemon_levels[str(new_id)] = self.pokemon_level(pokemon_id)
        self.life.pokemon_xp[str(new_id)] = self.life.pokemon_xp.pop(str(pokemon_id), 0)
        self.life.pokemon_health[str(new_id)] = self.life.pokemon_health.pop(str(pokemon_id), 1)
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
        for title, x, y in [("RUMAH / RUANG KELUARGA", 640, 167), ("AIR", 248, 294),
                            ("DAPUR", 361, 294), ("MEJA MAKAN", 625, 577), ("SOFA", 919, 503),
                            ("KAMAR", 1015, 273), ("E · KELUAR", 640, 679)]:
            self.label(title, x, y)

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
        if self.life.scene in ("coast", "mountain"):
            self.art.biome(self.canvas, self.life.scene)
            title = "PANTAI PASANG SURUT" if self.life.scene == "coast" else "PEGUNUNGAN KABUT"
            self.label(title, 640, 159)
            self.label("SUAKA  <", 100, 456)
            self.world_characters()
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
        drawables += [(t["y"], "trainer", t) for t in self.route_trainers if t["scene"] == self.life.scene]
        if not self.life.mounted and self.life.scene == self.life.horse_scene:
            drawables.append((self.life.horse_y, "horse", (self.life.horse_x, self.life.horse_y)))
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
                self.art.character(self.canvas, obj["x"], obj["y"], 1, 1.8, self.frame, True, "down", npc="Hunter")
                self.label(obj["name"] + (" · MENANG" if obj.get("defeated") else " · SPACE"), obj["x"], obj["y"] - 42)
            elif kind == "animal":
                self.art.animal(self.canvas, obj["species"], obj["x"], obj["y"], SPECIES[obj["species"]]["size"], obj["facing"], self.frame, obj["moving"])
                if obj["hp"] < SPECIES[obj["species"]]["hp"]:
                    self.box((obj["x"] - 23, obj["y"] + 3, 46, 5), INK, 2)
                    self.box((obj["x"] - 23, obj["y"] + 3, max(1, 46 * obj["hp"] / SPECIES[obj["species"]]["hp"]), 5), (215, 112, 91), 2)
                if math.hypot(obj["x"] - self.life.x, obj["y"] - self.life.y) < 155:
                    self.text(obj["species"] + " · " + obj["state"], obj["x"], obj["y"] + 24, INK, self.small, True)
            else:
                if self.life.mounted:
                    self.art.animal(self.canvas, "Kuda", self.life.x, self.life.y, 66, self.facing, self.frame, self.moving)
                self.sprite(self.life.x, self.life.y - (29 if self.life.mounted else 0), scale=1.7, walking=self.moving and not self.life.mounted)
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
        drawables += [(p["y"], "pokemon", p) for p in self.wild_pokemon]
        drawables += [(t["y"], "trainer", t) for t in self.reserve_trainers]
        if not self.life.mounted and self.life.horse_scene == "reserve":
            drawables.append((self.life.horse_y, "horse", (self.life.horse_x, self.life.horse_y)))
        drawables.append((self.life.y, "player", None))
        for _, kind, obj in sorted(drawables, key=lambda item: item[0]):
            wx, wy = (obj[0], obj[1]) if kind == "tree" or kind == "horse" else (obj["x"], obj["y"]) if kind in ("pokemon", "trainer") else (self.life.x, self.life.y)
            if not (left <= wx <= right and top <= wy <= bottom):
                continue
            px, py = wx - camera_x, wy - camera_y
            if kind == "tree":
                self.art.tree(self.world_canvas, px, py, variant=(int(obj[0]) // 112) % 2)
            elif kind == "pokemon":
                sprite = self.pokemon_surface(obj["id"], 52)
                if sprite:
                    bob = int(math.sin(self.frame / 5 + obj["id"]) * 4) if obj.get("moving") else int(math.sin(self.frame / 13 + obj["id"]) * 2)
                    image = pg.transform.flip(sprite, True, False) if obj.get("vx", 0) >= 0 else sprite
                    if obj.get("state") != "hide":
                        self.world_canvas.blit(image, image.get_rect(midbottom=(int(px), int(py - 3 + bob))))
                        if obj.get("state") == "flee" and int(self.frame / 12) % 2 == 0:
                            pg.draw.circle(self.world_canvas, (244, 231, 153), (int(px), int(py - 66 + bob)), 5)
                    elif int(self.frame / 15) % 2 == 0:
                        pg.draw.circle(self.world_canvas, (179, 213, 120), (int(px), int(py - 12)), 4)
                    if math.hypot(obj["x"] - self.life.x, obj["y"] - self.life.y) < 155 and obj.get("state") != "hide":
                        detail = self.pokemon_data(obj["id"]) or {}
                        name = detail.get("name", "Pokémon liar").title()
                        rarity = " · ★ RARE" if obj.get("rare") else ""
                        tag = self.small.render(self.tr(f"{name} · Lv.{obj.get('level', 5)}{rarity}"), True, CREAM)
                        self.world_canvas.blit(tag, tag.get_rect(center=(int(px), int(py + 11))))
            elif kind == "trainer":
                self.art.character(self.world_canvas, px, py, 1, 1.8, self.frame, True, "down", npc="Hunter")
                caption = obj["name"] + (" · REMATCH" if obj.get("defeated") else " · SPACE TANTANG")
                label = self.small.render(caption, True, INK)
                back = pg.Rect(0, 0, label.get_width() + 12, label.get_height() + 7)
                back.midbottom = (int(px), int(py - 40))
                pg.draw.rect(self.world_canvas, GREEN if obj.get("defeated") else CREAM, back, border_radius=0)
                self.world_canvas.blit(label, label.get_rect(center=back.center))
            elif kind == "horse":
                self.art.animal(self.world_canvas, "Kuda", px, py, 65, "right", self.frame, False)
            else:
                if self.life.mounted:
                    self.art.animal(self.world_canvas, "Kuda", px, py, 66, self.facing, self.frame, self.moving)
                self.art.character(self.world_canvas, px, py - (29 if self.life.mounted else 0), self.life.character,
                                   1.7, self.frame, self.moving, self.facing)
        self.canvas.blit(self.world_canvas, (0, 135))
        sx = lambda x: x - self.reserve_camera[0]
        sy = lambda y: y - self.reserve_camera[1] + 135
        zone = self.reserve_zone_at(self.life.x, self.life.y)
        self.label(zone["name"].upper(), 640, 154)
        for gate in self.reserve_gates():
            gx, gy = sx(gate["x"]), sy(gate["y"])
            if -80 < gx < W + 80 and 190 < gy < 592 + 135:
                required = gate["required_level"]
                if self.player_progress_level() < required:
                    gate_label = f"TERKUNCI · Lv.{required} · {gate['target']['name']}"
                else:
                    gate_label = "GERBANG · " + gate["target"]["name"]
                self.label(gate_label, gx, gy - 30)
        for index, (cx, cy) in enumerate(RESERVE_CENTERS):
            if -130 < sx(cx) < W + 130 and 180 < sy(cy) < H + 100:
                self.label("POKÉMON CENTER · E", sx(cx), sy(cy) - 114)
        zone = self.reserve_zone_at(self.life.x, self.life.y)
        self.label("RESTORAN · E", sx(zone["x"] + 250), sy(zone["y"] + 1070) - 59)
        self.label("HOTEL · E", sx(zone["x"] + 1030), sy(zone["y"] + 1070) - 59)
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
        col = max(0, min(RESERVE_COLUMNS - 1, int(x // RESERVE_ZONE_W)))
        row = max(0, min(RESERVE_ROWS - 1, int(y // RESERVE_ZONE_H)))
        return RESERVE_ZONES[row * RESERVE_COLUMNS + col]

    def update_location_audio(self):
        """Switch to locally bundled music when the player changes location."""
        if not pg.mixer.get_init():
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
            "mountain": "adventure.ogg",
        }.get(scene, "adventure.ogg")
        zone_name = ""
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

    def change_map_zoom(self, factor):
        self.map_zoom = max(0.55, min(3.2, self.map_zoom * factor))

    def enter_reserve_from_map(self):
        self.mode = "game"
        if self.life.scene != "reserve":
            self.transition("reserve", 100, 800)
        if not self.wild_pokemon:
            self.spawn_map_pokemon()
        self.notify(f"Suaka terbuka · {len(RESERVE_ZONES)} bioma dan habitat Pokémon tersebar di seluruh peta.")

    def hud(self, station):
        self.box((24, 18, 1232, 113), INK, 15)
        self.text("OPENRPG", 44, 30, CREAM, self.medium)
        location = {"outdoors": "Rumah & peternakan", "house": "Ruang keluarga", "bedroom": "Kamar", "forest": "Hutan liar", "market": "Market", "reserve": f"Suaka Pokémon · {len(RESERVE_ZONES)} bioma", "coast": "Pantai pasang surut", "mountain": "Pegunungan kabut"}[self.life.scene]
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
        self.text(f"{weapon} / SPACE serang / I tas / H obat / R kuda / B terminal", 456, 94, CREAM, self.tiny)
        status = "PC AKTIF" if self.terminal.running else "PROMPT JALAN" if self.phone_terminal.phone_marker else "PC SIAP"
        self.text(status, 1100, 36, GREEN if self.terminal.running or self.phone_terminal.phone_marker else MUTED, self.small)
        if self.phone_unread:
            self.text("HP · PESAN BARU", 985, 61, GREEN, self.small)
        if self.mode == "game":
            self.button("Misi · J", (956, 81, 112, 35), lambda: self.open_overlay("daily_quests"))
            self.button("Cuaca · C", (1090, 81, 145, 35), lambda: self.open_overlay("weather"))
        self.box((24, 727, 1232, 54), INK, 12)
        self.text("WASD JALAN / T +1 JAM / M PETA", 44, 743, MUTED, self.tiny)
        prompt = "E · " + station[3] if station else "< Hutan     Rumah & peternakan     Market >"
        if self.life.scene == "forest" and not station:
            prompt = "Singa: 06–10 & 16–20  /  Utara: masuk suaka Pokémon"
        if self.life.scene == "reserve":
            wild = self.closest_pokemon(155)
            trainer = self.closest_trainer(112)
            if wild:
                detail = self.pokemon_data(wild["id"]) or {}
                prompt = f"E · opsi Pokémon {detail.get('name', 'Pokémon liar').title()} · Lv.{wild.get('level', 5)}"
            elif trainer:
                prompt = f"Space · tantang pelatih {trainer['name']}"
            else:
                prompt = "Pokémon berkeliaran · dekati, lalu E untuk opsi"
        if self.fishing:
            age = time.monotonic() - self.fishing
            prompt = "E · TARIK SEKARANG!" if age >= 2.5 else "Tunggu ikan menggigit..."
        prompt = prompt if len(prompt) < 62 else prompt[:59] + "…"
        self.text(prompt, 648, 756, GREEN, self.small, True)
        self.draw_bag_icon(1007, 754, 18)
        self.text("I TAS", 1022, 743, MUTED, self.tiny)
        self.draw_pokedex_icon(1085, 754, 18)
        self.text("P DEX", 1100, 743, MUTED, self.tiny)
        self.text("F1 / ESC", 1185, 743, MUTED, self.tiny, True)
        if self.life.scene == "forest" and self.wildlife.events and time.monotonic() >= self.toast_until:
            self.text(self.wildlife.events[-1], 40, 681, CREAM, self.small)
        if self.mode not in ("center", "battle", "daily_quests") and time.monotonic() < self.toast_until:
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

    def overlay(self):
        self.buttons = []
        if self.mode == "map":
            self.draw_global_map()
            return
        veil = pg.Surface((W, H), pg.SRCALPHA)
        veil.fill((18, 29, 23, 205)); self.canvas.blit(veil, (0, 0))
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
        if self.mode not in ("center", "battle", "daily_quests") and time.monotonic() < self.toast_until:
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

    def dex_entries(self):
        query = self.dex_query.lower().strip()
        return [entry for entry in self.pokedex.catalog if not query or query in entry["name"].lower() or query == str(entry["id"])]

    def select_dex(self, pokemon_id):
        self.dex_selected = int(pokemon_id)
        self.dex_detail = self.pokemon_data(self.dex_selected)
        self.pokedex.request(self.dex_selected)
        self.pokedex.request_species(self.dex_selected)
        entries = self.dex_entries()
        selected_index = next((i for i, item in enumerate(entries)
                               if item["id"] == self.dex_selected), None)
        if selected_index is not None:
            self.dex_page = selected_index // 8

    def move_dex_selection(self, offset):
        entries = self.dex_entries()
        if not entries:
            return
        current = next((i for i, item in enumerate(entries)
                        if item["id"] == self.dex_selected), self.dex_page * 8)
        target = max(0, min(len(entries) - 1, current + offset))
        self.select_dex(entries[target]["id"])

    def draw_dex(self):
        self.draw_pokedex_icon(252, 198, 26)
        self.text("POKÉDEX · SEMUA SPESIES", 274, 183, CREAM, self.medium)
        self.text(f"{len(self.life.pokemon_caught)} tertangkap · {len(self.life.pokemon_seen)} terlihat · {len(self.pokedex.catalog)} spesies", 651, 190, GREEN, self.small)
        self.box((245, 220, 470, 38), (29, 39, 36), 7)
        self.text("Cari nama / nomor: " + self.dex_query + "▏", 257, 228, GREEN, self.small)
        self.button(f"Beli 5 Poké Ball · {BUY['Pokeball'] * 5} koin", (729, 220, 304, 38),
                    lambda: self.trade("Pokeball", True, 5))
        entries = self.dex_entries()
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
        self.text(f"Halaman {self.dex_page + 1} / {max(1, (len(entries) + 7) // 8)}", 313, 603, CREAM, self.small)
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
            abilities = ", ".join(a.get("ability", {}).get("name", "").replace("-", " ").title()
                                   for a in detail.get("abilities", []))
            height = detail.get("height")
            weight = detail.get("weight")
            dimensions = (f"Tinggi {height / 10:.1f} m · Berat {weight / 10:.1f} kg"
                          if isinstance(height, (int, float)) and isinstance(weight, (int, float))
                          else "Memuat data ukuran…")
            ability_label = f"Kemampuan: {abilities}" if abilities else "Kemampuan: memuat…"
            self.text(dimensions, 840, 475, MUTED, self.tiny, True)
            self.text(ability_label[:50], 650, 492, CREAM, self.tiny)
            stat_labels = {"hp": "HP", "attack": "ATK", "defense": "DEF",
                           "special-attack": "SP.A", "special-defense": "SP.D", "speed": "SPD"}
            for index, stat in enumerate(detail.get("stats", [])[:6]):
                stat_name = stat.get("stat", {}).get("name", "")
                short = stat_labels.get(stat_name, stat_name[:4].upper())
                value = int(stat.get("base_stat", 0))
                col, row = index % 3, index // 3
                x, y = 660 + col * 126, 512 + row * 20
                self.text(f"{short} {value}", x, y, GREEN, self.tiny)
            if species:
                flavor = next((entry.get("flavor_text", "").replace("\n", " ").replace("\f", " ")
                               for entry in species.get("flavor_text_entries", [])
                               if entry.get("language", {}).get("name") == "en"), "")
                words = flavor.split()
                for row in range(2):
                    line = ""
                    while words and len(line) + len(words[0]) < 64:
                        line = (line + " " + words.pop(0)).strip()
                    if line:
                        self.text(line, 650, 552 + row * 16, MUTED, self.tiny)
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
        self.button("⚔  Lawan · Enter", (510, 485, 250, 52), self.choose_encounter_battle, True)
        self.button("ⓘ  Informasi · I", (774, 485, 260, 52), self.show_encounter_info)
        self.button("Dengarkan cry", (510, 551, 250, 42), lambda: self.play_pokemon_cry(ident))
        self.button("Tutup · Esc", (774, 551, 260, 42), self.back)

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
            flavor = next((entry["flavor_text"].replace("\n", " ").replace("\f", " ")
                           for entry in species.get("flavor_text_entries", [])
                           if entry.get("language", {}).get("name") == "en"), "")
            words = flavor.split()
            for row in range(3):
                line = ""
                while words and len(line) + len(words[0]) < 68:
                    line = (line + " " + words.pop(0)).strip()
                if line:
                    self.text(line, 625, 420 + row * 22, CREAM, self.tiny)
        else:
            self.text("Memuat habitat dan entri Pokédex…", 625, 395, MUTED, self.small)
        self.button("Putar cry", (625, 584, 190, 44), lambda: self.play_pokemon_cry(ident), True)
        self.button("Kembali · I / Esc", (825, 584, 208, 44), lambda: setattr(self, "mode", "encounter"))

    def draw_center(self):
        self.text("POKÉMON CENTER · PEMERIKSAAN TIM", 242, 183, CREAM, self.medium)
        self.text(self.center_message, 245, 222, GREEN, self.small)
        team_ids = self.life.pokemon_party[:6]
        for i, pokemon_id in enumerate(team_ids):
            row, col = divmod(i, 2)
            rect = (245 + col * 182, 260 + row * 70, 170, 58)
            detail = self.pokemon_data(pokemon_id) or {}
            name = detail.get("name", f"Pokémon #{pokemon_id}").title()
            marker = "✓" if pokemon_id in self.life.pokemon_active else "·"
            self.button(f"{i + 1} {marker} {name}", rect,
                        lambda i=i: setattr(self, "center_selected", i), i == self.center_selected)
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
            candidate = self.evolution_target(pokemon_id)
            if candidate:
                self.text("Siap evolusi → " + candidate[1].title(), 815, 386, (255, 222, 121), self.small, True)
            else:
                self.text("Evolusi level-up terbuka setelah syarat spesies terpenuhi.", 815, 386, MUTED, self.small, True)
        else:
            self.text("Memuat data pemeriksaan dari PokéAPI…", 815, 320, MUTED, self.small, True)
        self.button("Pulihkan seluruh tim", (245, 496, 252, 43), self.heal_pokemon_party, True)
        target = self.evolution_target(pokemon_id) if pokemon_id else None
        self.button("Evolusi · V", (510, 496, 205, 43), self.evolve_selected, bool(target))
        self.button("Aktifkan / keluarkan", (728, 496, 305, 43), self.toggle_active_pokemon,
                    bool(pokemon_id in self.life.pokemon_active if pokemon_id else False))
        self.text(f"Trainer Lv.{self.life.trainer_level} · XP {self.life.trainer_xp}/{self.life.trainer_level * 100} · Evolusi: 100 XP + level + 10 koin",
                  245, 532, MUTED, self.small)
        self.text(f"Tim aktif {len(self.life.pokemon_active)}/3 · Tab mengganti saat duel · anggota mati otomatis diganti",
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
        self.dex_page = (self.dex_page + offset) % pages
        if entries:
            self.select_dex(entries[self.dex_page * 8]["id"])

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
        self._fight_bar(76, 77, 440, b.get("player_hp", 1), b.get("player_max", 1), left=True)
        self._fight_bar(764, 77, 440, b.get("wild_hp", 1), b.get("wild_max", 1), left=False)
        pg.draw.rect(self.canvas, (57, 71, 61), (76, 118, 440, 8), border_radius=0)
        if b.get("super_meter", 0):
            pg.draw.rect(self.canvas, (247, 194, 74), (76, 118, int(440 * b["super_meter"] / 100), 8), border_radius=0)
        self.text(f"ULTIMATE {int(b.get('super_meter', 0))}%", 76, 132, (255, 222, 121), self.small)
        opponent_count = len(b.get("opponent_lineup", [b["wild_id"]]))
        battle_kind="TEAM BATTLE" if opponent_count > 1 else "WILD BATTLE"
        self.text(f"{battle_kind}  ·  Lv.{b.get('wild_level',5)}  ·  {b.get('difficulty_label','BALANCED')}", W // 2, 47, CREAM, self.tiny, True)
        self.text(f"{BATTLE_WEATHER_EMOJI.get(weather, '☁')} {weather.upper()}  ·  {arena.upper()} ARENA", W // 2, 68, GREEN, self.tiny, True)
        if opponent_count > 1:
            self.text(f"RONDE {b.get('opponent_index', 0) + 1}/{opponent_count}", W // 2, 87, CREAM, self.tiny, True)
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
        for fruit in b.get("fruits", []):
            fx, fy = int(fruit["x"]), ground - 20
            pg.draw.circle(self.canvas, (255, 238, 165), (fx, fy), 10, 2)
            glyph = self.fruit_font.render(fruit["emoji"], True, CREAM)
            glyph = pg.transform.scale(glyph, (15, 15))
            self.canvas.blit(glyph, glyph.get_rect(center=(fx, fy)))
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
                stunned=b.get(key+"_stun_timer",0)>0
                if stunned and not self.life.reduced_motion:
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
                if stunned:
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
        phase = b.get("phase", "Memuat Pokémon dari PokéAPI…") if capture else (b.get("result") or b.get("phase", "Memuat Pokémon dari PokéAPI…"))
        if capture or b.get("result"):
            self.box((300, 536, 680, 40), (35, 54, 48), 12)
            self.text(phase, W // 2, 556, CREAM, self.small, True)
        self.box((910, 142, 340, 66), (32, 51, 48), 9)
        self.text("← → gerak · ↑ lompat/panjat · S tahan", 924, 151, CREAM, self.tiny)
        self.text("A dekat · S tahan · Q stun · W dekat · E jauh · R ult · 1–3 ganti", 924, 170, GREEN, self.tiny)
        self.text(f"O bola · ult tembus 40% guard · {int(b.get('time_left', 60))} dtk · Esc", 924, 185, MUTED, self.tiny)
        if b.get("result") and b["player_hp"] <= 0:
            self.box((470, 586, 340, 44), (32, 51, 48), 12)
            self.text("Enter / Esc · kembali ke peta", W // 2, 608, CREAM, self.small, True)
        if b.get("intro"):
            self.draw_battle_intro(b)
        if b.get("ultimate_cutin"):
            self.draw_ultimate_cutin(b, b["ultimate_cutin"])

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
        if self.shop_npc == "Danu":
            self.button("Jual Pokémon", (601, 226, 190, 40), lambda: self.set_shop_tab("pokemon"), self.shop_tab == "pokemon")
        if self.shop_tab == "pokemon":
            self.draw_pokemon_market()
            return
        items = [k for k in BUY if (k in ("Tombak", "Busur", "Panah")) == (self.shop_npc == "Budi")] if self.shop_tab == "buy" else list(SELL)
        if self.shop_npc == "Danu" and self.shop_tab == "buy":
            self.text("Danu menerima hasil kebun, peternakan, dan buruan.", 245, 288, CREAM)
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
        if self.shop_npc != "Danu":
            self.text("Bicara dengan Danu untuk menjual Pokémon.", 245, 288, MUTED, self.small)
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
                             "pokemon_info", "daily_quests", "evolution", "settings", "hospitality", "map"):
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
                if event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_1):
                    self.choose_encounter_battle()
                elif event.key in (pg.K_i, pg.K_2):
                    self.show_encounter_info()
                elif event.key == pg.K_SPACE and self.encounter_target:
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
            elif self.mode == "dex":
                if event.key == pg.K_BACKSPACE:
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
                        selected = next((item for item in entries if item["id"] == self.dex_selected),
                                        entries[self.dex_page * 8])
                        self.select_dex(selected["id"])
                elif event.key == pg.K_LEFT:
                    self.change_dex_page(-1)
                elif event.key == pg.K_RIGHT:
                    self.change_dex_page(1)
                elif event.key in (pg.K_ESCAPE, pg.K_p):
                    self.back()
            elif self.mode == "center":
                if pg.K_1 <= event.key <= pg.K_6 and event.key - pg.K_1 < len(self.life.pokemon_party):
                    self.center_selected = event.key - pg.K_1
                elif event.key == pg.K_v:
                    self.evolve_selected()
                elif event.key == pg.K_h:
                    self.heal_pokemon_party()
                elif event.key in (pg.K_ESCAPE, pg.K_n, pg.K_RETURN):
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
                elif event.key == pg.K_h:
                    self.use_healing_item()
                elif event.key == pg.K_b:
                    self.open_phone()
                elif event.key == pg.K_p:
                    self.open_dex()
                elif event.key == pg.K_j:
                    self.open_overlay("daily_quests")
                elif event.key == pg.K_n:
                    self.open_pokemon_center()
                elif event.key == pg.K_m:
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
            elif event.key in (pg.K_ESCAPE, pg.K_i, pg.K_F1, pg.K_RETURN):
                self.back()

    def update(self, dt):
        self.frame += dt * 60
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
        active = self.mode in ("game", "map", "terminal", "inventory", "shop", "weather", "phone", "dex", "center", "battle", "encounter", "pokemon_info", "daily_quests", "evolution", "settings", "hospitality", "dead")
        if active:
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
            self.check_daily_quest_rewards()
            health_before_animals = self.life.health
            self.wildlife.update(dt, self.obstacles("forest"), player_active=self.mode not in ("terminal", "phone", "dex", "battle", "encounter", "pokemon_info", "dead"))
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


from adventure_flow import FlowMixin
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
