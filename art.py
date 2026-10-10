"""Kenney CC0 pixel assets: tile maps, furniture and character sprites."""
from pathlib import Path
import math
import queue
import random
import threading
from collections import OrderedDict
import pygame as pg
from scenery import Scenery
from world_regions import reserve_layout, reserve_solids, scene_layout

ROOT = Path(__file__).resolve().parent / "assets"
NINJA = ROOT / "ninja-adventure/Ninja Adventure - Asset Pack"
# Playable trainers use the human adventurer sprites from the bundled CC0 pack.
# Keep the legacy slot order so old saves keep a stable character index, while
# replacing the two ninja slots with ordinary villagers.
PLAYER_STYLES = ("Boy", "Hunter", "Woman", "Villager4", "OldMan", "Samurai", "Princess", "Cavegirl", "EggGirl")
FACING = {"down": 0, "up": 1, "left": 2, "right": 3}
RESERVE_WIDTH, RESERVE_HEIGHT = 5120, 6400
RESERVE_ZONE_W, RESERVE_ZONE_H = 1280, 1600
RESERVE_COLUMNS, RESERVE_ROWS = 4, 4
RESERVE_LEVEL_REQUIREMENTS = [0, 4, 8, 12, 6, 10, 14, 18, 16, 20, 24, 28, 32, 36, 40, 45]
RESERVE_CENTERS = [(160, 690)] + [(c * 1280 + 640, r * 1600 + 955) for r in range(4) for c in range(4)]
RESERVE_ZONES = [
    {"name": "Suaka Hijau", "biome": "meadow", "x": 0, "y": 0, "color": (114, 171, 103)},
    {"name": "Hutan Rimba", "biome": "forest", "x": 1280, "y": 0, "color": (64, 130, 76)},
    {"name": "Gurun Pasir", "biome": "desert", "x": 2560, "y": 0, "color": (213, 177, 105)},
    {"name": "Pantai Pesisir", "biome": "coast", "x": 3840, "y": 0, "color": (73, 157, 190)},
    {"name": "Rawa Air", "biome": "swamp", "x": 0, "y": 1600, "color": (75, 119, 85)},
    {"name": "Gua Batu", "biome": "cave", "x": 1280, "y": 1600, "color": (83, 87, 91)},
    {"name": "Dataran Tanah", "biome": "badlands", "x": 2560, "y": 1600, "color": (159, 121, 83)},
    {"name": "Pegunungan", "biome": "mountain", "x": 3840, "y": 1600, "color": (120, 137, 151)},
    {"name": "Gunung Berapi", "biome": "volcano", "x": 0, "y": 3200, "color": (127, 77, 69)},
    {"name": "Tundra Salju", "biome": "snow", "x": 1280, "y": 3200, "color": (176, 207, 222)},
    {"name": "Kepulauan Angin", "biome": "sky", "x": 2560, "y": 3200, "color": (108, 174, 210)},
    {"name": "Reruntuhan Kristal", "biome": "crystal", "x": 3840, "y": 3200, "color": (127, 104, 167)},
    {"name": "Hutan Purba", "biome": "ancient_forest", "x": 0, "y": 4800, "color": (71, 109, 68)},
    {"name": "Palung Samudra", "biome": "deepsea", "x": 1280, "y": 4800, "color": (37, 94, 139)},
    {"name": "Lembah Naga", "biome": "dragon_valley", "x": 2560, "y": 4800, "color": (128, 82, 92)},
    {"name": "Kuil Legenda", "biome": "legendary_ruins", "x": 3840, "y": 4800, "color": (117, 92, 150)},
]


class RPGArt:
    def __init__(self):
        self.tiles = {}
        self.scaled = {}
        for pack in ("tiny-town", "tiny-farm", "tiny-dungeon"):
            for path in (ROOT / pack / "Tiles").glob("*.png"):
                self.tiles[pack, int(path.stem.split("_")[1])] = pg.image.load(path).convert_alpha()
        self.sheet = pg.image.load(ROOT / "roguelike-rpg-pack/Spritesheet/roguelikeSheet_transparent.png").convert_alpha()
        self.characters = {}
        for name in dict.fromkeys(PLAYER_STYLES + ("OldMan", "Villager4")):
            for anim in ("Idle", "Walk", "Attack"):
                self.characters[name, anim] = pg.image.load(NINJA / f"Actor/Character/{name}/SeparateAnim/{anim}.png").convert_alpha()
        self.nature = pg.image.load(NINJA / "Backgrounds/Tilesets/TilesetNature.png").convert_alpha()
        # The nature atlas also has multi-tile tree parts. Cropping every 32px
        # cell made some of those parts appear as half-trees in the world.
        # Use only the intact, rounded tree cells from its first row.
        safe_tree_cells = (0, 32, 96, 256, 288)
        self.tree_sprites = [pg.transform.scale(self.nature.subsurface((x, 0, 32, 32)), (112, 112))
                             for x in safe_tree_cells]
        self.rock_sprites = [pg.transform.scale(self.nature.subsurface((x, 96, 32, 32)), (52, 52))
                             for x in range(0, 384, 32)]
        self.ground_sprites = [pg.transform.scale(self.nature.subsurface((x, y, 16, 16)), (24, 24))
                               for y in range(160, 320, 16) for x in range(0, 384, 16)]
        self.animal_sheets = {}
        for name, folder, file in [("Singa", "Lion", "SpriteSheetYellow"), ("Kuda", "Horse", "SpriteSheetBrown"),
                                    ("Babi hutan", "WildBoar", "SpriteSheet"), ("Hyena", "Hyena", "SpriteSheet"),
                                    ("Monyet", "Monkey", "SpriteSheetBrown"), ("Ayam", "Chicken", "SpriteSheetWhite")]:
            path = NINJA / f"Actor/Animal/{folder}/{file}.png"
            self.animal_sheets[name] = pg.image.load(path).convert_alpha()
            side = path.with_name(file + "Side.png")
            if side.exists():
                self.animal_sheets[name + "Side"] = pg.image.load(side).convert_alpha()
        for name, file in (("Gajah", "elephant.png"), ("Kelinci", "rabbit.png")):
            path = ROOT / "generated" / file
            if path.exists():
                self.animal_sheets[name] = pg.image.load(path).convert_alpha()
        # Keep the north road to the online gym clear. The two former trees at
        # (616,252) and (735,221) visually narrowed the entrance and blocked
        # the player's collision box.
        self.trees = {"outdoors": [(76, 250), (105, 514), (1200, 271), (1138, 434), (460, 661)],
                      "forest": [(65 + i * 108, 238 + (i % 3) * 15) for i in range(11)] +
                                [(78 + i * 105, 660 - (i % 3) * 16) for i in range(11)] +
                                [(202, 337), (410, 310), (730, 302), (930, 335), (1123, 320),
                                 (133, 560), (328, 579), (520, 620), (827, 590), (1100, 570)],
                      "market": [(90, 271), (1185, 277), (160, 628), (1095, 640), (730, 199)],
                      "reserve": [(190 + i * 137, 145 + (i % 4) * 33) for i in range(17)] +
                                 [(135 + i * 145, 1510 - (i % 4) * 31) for i in range(17)] +
                                 [(360, 490), (630, 695), (920, 375), (1150, 930), (1470, 550),
                                  (1740, 900), (2050, 445), (2220, 1120), (470, 1210), (1580, 1300),
                                  (430, 550), (900, 550), (1100, 1010), (390, 1040), (960, 1130),
                                  (155, 970), (540, 1185), (1115, 545), (1380, 365), (1860, 680),
                                  (2350, 565), (2310, 945), (1940, 1330), (1280, 260), (1290, 1380)],
                      "coast": [(75, 255), (1190, 263), (1080, 658)],
                      "mountain": [(132, 600), (1180, 548), (960, 222)]}
        # Scene backgrounds are generated only when the player visits them.
        self.background = None
        self.forest_background = None
        self.market_background = None
        # Extra trees in the woodland and wetland regions; paths remain clear.
        rng = random.Random(751)
        for zone_index, zone in enumerate(RESERVE_ZONES):
            # Small groves in leafy biomes; sparse silhouettes elsewhere keep
            # the long routes readable and leave room for Pokémon encounters.
            biome = zone["biome"]
            count = 13 if biome in ("forest", "swamp", "snow", "ancient_forest") else 4
            if biome in ("deepsea", "sky", "desert", "badlands", "cave", "volcano"):
                count = 0
            for _ in range(count):
                self.trees["reserve"].append((zone["x"] + rng.randrange(90, 1190), zone["y"] + rng.randrange(190, 1480)))
        # One road network, shared by art and tree placement. Junctions are unions.
        self.reserve_paths = [pg.Rect(0, y - 48, RESERVE_WIDTH, 96)
                              for y in range(800, RESERVE_HEIGHT, RESERVE_ZONE_H // 2)]
        self.reserve_paths += [pg.Rect(x - 40, 0, 80, RESERVE_HEIGHT)
                               for x in (1280, 2560, 3840)]
        self.reserve_paths += [pg.Rect(x - 28, 0, 56, RESERVE_HEIGHT)
                               for x in (640, 1920, 3200, 4480)]
        self.reserve_paths += [pg.Rect(132, 670, 48, 130), pg.Rect(640, 448, 640, 56)]
        self.trees["reserve"] = [(x, y) for x, y in self.trees["reserve"]
                                 if not any(r.colliderect(pg.Rect(x-48, y-90, 96, 96))
                                            for r in self.reserve_paths)]
        # Sanctuary terrain is split into independently cached 1280×1600 zones.
        # A small LRU cache caps map-background memory regardless of world size.
        self.scenery = Scenery(self)
        self._region_obstacles = {}
        self.trees["reserve"] = []  # Regional props now come from shared geometry.
        self.reserve_chunks = OrderedDict()
        # A camera view at a zone corner can show 2 columns × 2 rows. Keep all
        # visible chunks resident; a two-entry cache rebuilt half the map on
        # every frame at intersections, causing severe stutter and allocations.
        self.reserve_chunk_limit = 4
        # Biome chunks are expensive to rasterize. Build them away from the
        # render loop so entering an unexplored region cannot stall movement.
        self.reserve_chunk_jobs = queue.Queue()
        self.reserve_chunk_results = queue.Queue()
        self.reserve_chunk_pending = set()
        self.reserve_chunk_errors = set()
        self.reserve_chunk_worker = threading.Thread(
            target=self._reserve_chunk_worker, name="openrpg-biome-render", daemon=True)
        self.reserve_chunk_worker.start()
        self.request_reserve_chunk(0)
        self.coast_background = None
        self.mountain_background = None

    def image(self, pack, index, size=48):
        key = (pack, index, size)
        if key not in self.scaled:
            if pack == "rpg":
                x, y = index
                source = self.sheet.subsurface((x * 17, y * 17, 16, 16))
            else:
                source = self.tiles[pack, index]
            self.scaled[key] = pg.transform.scale(source, (size, size))
        return self.scaled[key]

    def tile(self, target, pack, index, x, y, size=48):
        target.blit(self.image(pack, index, size), (x, y))

    def fill(self, target, pack, index, rect, size=48):
        rect = pg.Rect(rect)
        previous = target.get_clip()
        target.set_clip(rect)
        tile = self.image(pack, index, size)
        for y in range(rect.y, rect.bottom, size):
            for x in range(rect.x, rect.right, size):
                target.blit(tile, (x, y))
        target.set_clip(previous)

    def grid(self, target, pack, rows, x, y, size=48):
        for row, tiles in enumerate(rows):
            for col, index in enumerate(tiles):
                if index is not None:
                    self.tile(target, pack, index, x + col * size, y + row * size, size)

    def tree(self, target, x, y, autumn=False, variant=0):
        pg.draw.ellipse(target, (106, 153, 77), (x - 40, y - 15, 80, 20))
        target.blit(self.tree_sprites[variant % len(self.tree_sprites)], (x - 56, y - 112))

    def tree_obstacles(self, scene):
        return [pg.Rect(x - 13, y - 17, 26, 22) for x, y in self.trees.get(scene, [])]

    def fence(self, target, x, y, width):
        count = max(2, round(width / 32))
        for i in range(count):
            self.tile(target, "tiny-town", 44 if i == 0 else 46 if i == count - 1 else 45, x + i * 32, y, 32)

    def build_outdoors(self, target):
        self.fill(target, "tiny-town", 0, (0, 0, 1280, 800))
        for i in range(150):
            x, y = (i * 137 + 51) % 1240, 125 + (i * 83) % 571
            self.tile(target, "tiny-town", 2 if i % 11 == 0 else 1, x, y, 32)
        self.grid(target, "tiny-town", [
            [52, 53, 53, 55, 53, 53, 54],
            [64, 65, 65, 65, 65, 65, 66],
            [72, 73, 73, 73, 73, 73, 75],
            [84, 73, 84, 85, 73, 84, 73],
        ], 182, 158)
        self.grid(target, "tiny-town", [[48, 49, 51, 49, 50], [60, 61, 61, 61, 62]], 812, 158)
        self.grid(target, "tiny-farm", [[102, 103, 103, 103, 104], [114, 115, 115, 115, 116]], 812, 254)
        self.tile(target, "tiny-town", 78, 908, 302)
        self.fence(target, 798, 326, 110)
        self.fence(target, 973, 326, 110)
        self.fence(target, 797, 399, 300)
        self.tile(target, "tiny-farm", 73, 1029, 362, 32)
        self.tile(target, "tiny-farm", 122, 841, 363, 32)
        # Water edges and terrain are actual shoreline tiles.
        self.grid(target, "rpg", [
            [(2, 0), (3, 0), (3, 0), (3, 0), (3, 0), (4, 0)],
            [(2, 1), (0, 0), (1, 0), (0, 0), (1, 0), (4, 1)],
            [(2, 1), (1, 0), (0, 0), (1, 0), (0, 0), (4, 1)],
            [(2, 2), (3, 2), (3, 2), (3, 2), (3, 2), (4, 2)],
        ], 930, 477)
        self.fill(target, "rpg", (8, 2), (930, 573, 96, 48))
        self.tile(target, "tiny-farm", 84, 1015, 547, 32)
        self.grid(target, "tiny-farm", [[98, 99]], 251, 563)
        for x, y, tile in [(172, 462, 29), (428, 365, 28), (742, 543, 78), (1131, 665, 77)]:
            self.tile(target, "tiny-farm", tile, x, y, 32)
        self.scenery.local_overlay(target, "outdoors")

    def outdoors(self, target, life, frame):
        if self.background is None:
            self.background = pg.Surface((1280, 800)).convert()
            self.build_outdoors(self.background)
        target.blit(self.background, (0, 0))
        for i, crop in enumerate(life.crops):
            x, y = 556 + i % 3 * 62, 418 + i // 3 * 69
            self.tile(target, "tiny-farm", 1, x, y)
            stage = crop["stage"]
            if stage != "empty":
                index = 4 if stage == "planted" else (29, 41, 53)[i % 3] if stage == "growing" else (32, 44, 56)[i % 3]
                self.tile(target, "tiny-farm", index, x, y)
            if stage == "growing":
                pg.draw.rect(target, (83, 150, 185), (x + 6, y + 43, 36, 3))
        for i, (x, y) in enumerate([(851, 307), (990, 318), (1054, 387)]):
            x += int(math.sin(frame / 70 + i) * 7)
            self.animal(target, "Ayam", x, y, 32, "down", frame, True)

    def build_forest(self, target):
        self.fill(target, "tiny-town", 0, (0, 0, 1280, 800))
        rng = random.Random(208)
        paths = [pg.Rect(0, 375, 1280, 76), pg.Rect(605, 285, 80, 298)]
        for i in range(120):
            x, y = rng.randrange(35, 1220), rng.randrange(168, 660)
            if any(rect.collidepoint(x, y) for rect in paths):
                continue
            self.tile(target, "tiny-town", 2 if i % 9 == 0 else 1, x, y, 32)
        tint = pg.Surface(target.get_size(), pg.SRCALPHA)
        tint.fill((22, 66, 34, 28)); target.blit(tint, (0, 0))
        self.tile(target, "tiny-town", 83, 1182, 439, 48)
        self.scenery.local_overlay(target, "forest")

    def forest(self, target):
        if self.forest_background is None:
            self.forest_background = pg.Surface((1280, 800)).convert()
            self.build_forest(self.forest_background)
        target.blit(self.forest_background, (0, 0))

    def build_reserve(self, target):
        self.fill(target, "tiny-town", 0, target.get_rect())
        paths = self.reserve_paths
        # A colorful Pokémon Center beside the entrance and a marked battle ring
        # make the reserve's services and challenge area easy to spot at a glance.
        pg.draw.ellipse(target, (114, 151, 89), (1040, 735, 480, 150))
        pg.draw.ellipse(target, (234, 217, 172), (1062, 747, 436, 122), 7)
        pg.draw.ellipse(target, (111, 148, 91), (1102, 765, 356, 87), 4)
        pg.draw.rect(target, (231, 225, 204), (78, 566, 158, 105))
        pg.draw.rect(target, (183, 70, 72), (68, 548, 178, 40))
        pg.draw.polygon(target, (202, 83, 83), [(68, 549), (157, 506), (246, 549)])
        pg.draw.rect(target, (134, 67, 62), (137, 615, 42, 56))
        pg.draw.rect(target, (114, 187, 208), (91, 589, 33, 35))
        pg.draw.rect(target, (114, 187, 208), (190, 589, 33, 35))
        pg.draw.circle(target, (255, 255, 244), (157, 558), 20)
        pg.draw.circle(target, (206, 76, 82), (157, 558), 20, 6)
        pg.draw.line(target, (206, 76, 82), (138, 558), (176, 558), 5)
        pg.draw.circle(target, (206, 76, 82), (157, 558), 5)
        water = [[(2, 0), (3, 0), (3, 0), (4, 0)],
                 [(2, 1), (0, 0), (1, 0), (4, 1)],
                 [(2, 2), (3, 2), (3, 2), (4, 2)]]
        self.grid(target, "rpg", water, 1792, 1120, 48)
        self.grid(target, "rpg", water, 288, 288, 48)
        rng = random.Random(191)
        # Scattered grasses, flowers, and stones give the wide reserve texture
        # while leaving its paths and lakes readable.
        lakes = [pg.Rect(270, 270, 220, 200), pg.Rect(1770, 1100, 230, 220)]
        for _ in range(240):
            x, y = rng.randrange(32, 2528), rng.randrange(80, 1520)
            if any(r.collidepoint(x, y) for r in paths + lakes):
                continue
            self.tile(target, "tiny-town", 2 if rng.randrange(5) == 0 else 1, x, y, rng.choice((24, 28, 32)))
        for i, (x, y) in enumerate(self.trees["reserve"]):
            pg.draw.ellipse(target, (106, 153, 77), (x - 40, y - 15, 80, 20))
            target.blit(self.tree_sprites[(int(x) // 112) % len(self.tree_sprites)], (x - 56, y - 112))
        for x in range(80, 2480, 160):
            self.tile(target, "tiny-town", 2, x, 160 + (x % 4) * 25, 32)
            self.tile(target, "tiny-farm", 77, x + 60, 1380 - (x % 3) * 42, 32)

    def draw_regional_centers(self, target):
        """Draw small healing stations after biome terrain and paths are painted."""
        for cx, cy in RESERVE_CENTERS[1:]:
            pg.draw.rect(target, (45, 45, 56), (cx - 90, cy - 206, 180, 164))
            pg.draw.rect(target, (235, 229, 207), (cx - 82, cy - 198, 164, 154))
            pg.draw.polygon(target, (177, 55, 65), [(cx - 94, cy - 194),
                           (cx, cy - 244), (cx + 94, cy - 194)])
            pg.draw.rect(target, (126, 57, 57), (cx - 20, cy - 100, 40, 56))
            pg.draw.rect(target, (104, 178, 205), (cx - 68, cy - 174, 34, 34))
            pg.draw.rect(target, (104, 178, 205), (cx + 34, cy - 174, 34, 34))
            pg.draw.circle(target, (255, 255, 244), (cx, cy - 205), 22)
            pg.draw.circle(target, (206, 76, 82), (cx, cy - 205), 21, 6)
            pg.draw.line(target, (206, 76, 82), (cx - 20, cy - 205), (cx + 20, cy - 205), 5)
            pg.draw.circle(target, (206, 76, 82), (cx, cy - 205), 5)

    def extend_reserve(self, target):
        """Paint the ten new biomes and connect them to the original sanctuary."""
        rng = random.Random(8241)
        for zone in RESERVE_ZONES[1:]:
            x, y, w, h = zone["x"], zone["y"], RESERVE_ZONE_W, RESERVE_ZONE_H
            pg.draw.rect(target, zone["color"], (x, y, w, h))
            # Low contrast ground texture keeps the landscape readable at game scale.
            for _ in range(310):
                px, py = x + rng.randrange(0, w), y + rng.randrange(0, h)
                tint = tuple(max(0, min(255, c + rng.randrange(-15, 16))) for c in zone["color"])
                pg.draw.rect(target, tint, (px, py, rng.randrange(8, 25), rng.randrange(5, 14)))
            biome = zone["biome"]
            if biome in ("coast", "swamp", "deepsea"):
                for i in range(4):
                    cx, cy = x + 210 + i * 260, y + 330 + (i % 2) * 690
                    outer = (22, 72, 119) if biome == "deepsea" else (47, 125, 151) if biome == "coast" else (46, 95, 91)
                    inner = (48, 133, 170) if biome == "deepsea" else (119, 190, 199) if biome == "coast" else (95, 145, 120)
                    pg.draw.ellipse(target, outer, (cx - 135, cy - 78, 270, 156))
                    pg.draw.ellipse(target, inner, (cx - 116, cy - 58, 232, 116), 5)
                for i in range(14):
                    rx, ry = x + rng.randrange(40, 1240), y + rng.randrange(120, 1480)
                    pg.draw.ellipse(target, (213, 195, 140), (rx, ry, 92, 19))
            elif biome in ("desert", "badlands"):
                for i in range(10):
                    dx, dy = x + rng.randrange(-60, 1100), y + rng.randrange(120, 1500)
                    color = (224, 194, 123) if biome == "desert" else (181, 138, 99)
                    pg.draw.ellipse(target, color, (dx, dy, 310, 90))
                    pg.draw.arc(target, (238, 214, 154), (dx + 20, dy + 8, 260, 64), 0, math.pi, 3)
            elif biome in ("cave", "mountain", "volcano", "dragon_valley"):
                for i in range(13):
                    rx, ry = x + rng.randrange(30, 1200), y + rng.randrange(120, 1460)
                    points = [(rx - 65, ry + 48), (rx - 42, ry - 35), (rx, ry - rng.randrange(65, 130)), (rx + 55, ry - 20), (rx + 76, ry + 48)]
                    col = (66, 69, 78) if biome == "cave" else (128, 79, 91) if biome == "dragon_valley" else (98, 110, 122) if biome == "mountain" else (83, 66, 66)
                    pg.draw.polygon(target, col, points)
                    pg.draw.line(target, (153, 158, 164), points[1], points[2], 4)
                if biome == "volcano":
                    pg.draw.ellipse(target, (243, 111, 43), (x + 395, y + 535, 470, 270))
                    pg.draw.ellipse(target, (255, 194, 59), (x + 465, y + 590, 325, 155))
            elif biome in ("snow", "sky"):
                for i in range(17):
                    cx, cy = x + rng.randrange(40, 1240), y + rng.randrange(140, 1480)
                    color = (229, 242, 244) if biome == "snow" else (178, 218, 232)
                    pg.draw.ellipse(target, color, (cx - 100, cy - 32, 200, 65))
                    if biome == "snow":
                        pg.draw.circle(target, (246, 251, 252), (cx, cy - 8), 7)
            elif biome in ("crystal", "legendary_ruins"):
                for i in range(28):
                    cx, cy = x + rng.randrange(40, 1240), y + rng.randrange(120, 1480)
                    crystal = biome == "crystal"
                    tint = (91, 221, 218) if crystal else (220, 190, 106)
                    light = (204, 255, 248) if crystal else (255, 232, 158)
                    pg.draw.polygon(target, tint, [(cx, cy - 45), (cx + 22, cy), (cx, cy + 44), (cx - 18, cy)])
                    pg.draw.line(target, light, (cx, cy - 40), (cx, cy + 28), 3)
            elif biome == "ancient_forest":
                for i in range(30):
                    tx = x + rng.randrange(80, 1200)
                    ty = y + rng.randrange(140, 1480)
                    pg.draw.rect(target, (75, 58, 43), (tx - 8, ty - 52, 16, 60))
                    pg.draw.circle(target, (41, 83, 52), (tx, ty - 58), 43)
                    pg.draw.circle(target, (92, 129, 62), (tx, ty - 69), 28)

        self.paint_paths(target, self.reserve_paths)

    def paint_paths(self, target, paths):
        """Bake stable pixel dirt trails, with outside edges only at intersections."""
        step = 4
        w, h = target.get_width() // step, target.get_height() // step
        mask = pg.mask.Mask((w, h))
        for r in paths:
            r = r.clip(target.get_rect())
            if r.width and r.height:
                stamp = pg.mask.Mask(((r.width + step - 1)//step,
                                      (r.height + step - 1)//step), fill=True)
                mask.draw(stamp, (r.x//step, r.y//step))
        layer = pg.Surface((w, h), pg.SRCALPHA)
        base = (191, 143, 91)
        for y in range(h):
            for x in range(w):
                if not mask.get_at((x, y)):
                    continue
                value = (x * 374761393 + y * 668265263) & 0xffffffff
                value = ((value ^ (value >> 13)) * 1274126177) & 0xffffffff
                noise = (value >> 16) % 31
                color = (base[0]+noise//4, base[1]+noise//5, base[2]+noise//6)
                left = x > 0 and not mask.get_at((x-1,y))
                right = x+1 < w and not mask.get_at((x+1,y))
                top = y > 0 and not mask.get_at((x,y-1))
                bottom = y+1 < h and not mask.get_at((x,y+1))
                if top or left:
                    color = (222, 182, 121)
                elif bottom or right:
                    color = (142, 105, 67)
                elif noise == 0:
                    color = (168, 123, 78)
                elif noise == 1:
                    color = (218, 171, 112)
                layer.set_at((x,y), color)
                # A few broken tufts along the verge, never across a junction.
                if value % 7 == 0:
                    for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
                        nx,ny=x+dx,y+dy
                        if 0 <= nx < w and 0 <= ny < h and not mask.get_at((nx,ny)):
                            layer.set_at((nx,ny), (110, 144, 75))
        target.blit(pg.transform.scale(layer, target.get_size()), (0,0))

    def build_biome(self, target, biome):
        self.scenery.ground(target, biome)
        self.scenery.local_overlay(target, biome)

    def reserve(self, target, camera):
        cam_x, cam_y = int(camera[0]), int(camera[1])
        left = max(0, cam_x // RESERVE_ZONE_W)
        top = max(0, cam_y // RESERVE_ZONE_H)
        right = min(RESERVE_COLUMNS - 1, (cam_x + target.get_width() - 1) // RESERVE_ZONE_W)
        bottom = min(RESERVE_ROWS - 1, (cam_y + target.get_height() - 1) // RESERVE_ZONE_H)
        # Install completed chunks on the main thread and keep the normal LRU
        # cap. Pygame drawing and display updates stay on the game thread.
        while True:
            try:
                index, chunk, error = self.reserve_chunk_results.get_nowait()
            except queue.Empty:
                break
            self.reserve_chunk_pending.discard(index)
            if chunk is not None:
                self.reserve_chunks[index] = chunk
                self.reserve_chunks.move_to_end(index)
                while len(self.reserve_chunks) > self.reserve_chunk_limit:
                    self.reserve_chunks.pop(next(iter(self.reserve_chunks)))
            elif error:
                self.reserve_chunk_errors.add(index)

        visible = []
        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                index = row * RESERVE_COLUMNS + col
                visible.append(index)
                if index not in self.reserve_chunks:
                    self.request_reserve_chunk(index)

        for index in visible:
            zone = RESERVE_ZONES[index]
            chunk = self.reserve_chunks.get(index)
            if chunk is None:
                # A flat biome-color placeholder is cheap and avoids freezing
                # for a frame while the worker draws a never-visited region.
                rect = pg.Rect(zone["x"] - cam_x, zone["y"] - cam_y,
                               RESERVE_ZONE_W, RESERVE_ZONE_H).clip(target.get_rect())
                if rect.width and rect.height:
                    target.fill(zone["color"], rect)
            else:
                self.reserve_chunks.move_to_end(index)
                target.blit(chunk, (zone["x"] - cam_x, zone["y"] - cam_y))

    def request_reserve_chunk(self, index):
        if (0 <= index < len(RESERVE_ZONES) and index not in self.reserve_chunks
                and index not in self.reserve_chunk_pending and index not in self.reserve_chunk_errors):
            self.reserve_chunk_pending.add(index)
            self.reserve_chunk_jobs.put(index)

    def _reserve_chunk_worker(self):
        while True:
            index = self.reserve_chunk_jobs.get()
            try:
                chunk = self.build_reserve_chunk(index)
                self.reserve_chunk_results.put((index, chunk, None))
            except Exception as error:
                self.reserve_chunk_results.put((index, None, error))

    def build_reserve_chunk(self, index):
        return self.scenery.reserve(index)

    def region_obstacles(self, index):
        if index not in self._region_obstacles:
            self._region_obstacles[index] = tuple(pg.Rect(r) for r in reserve_solids(index))
        return self._region_obstacles[index]

    def biome(self, target, name):
        attr = "coast_background" if name == "coast" else "mountain_background"
        background = getattr(self, attr)
        if background is None:
            background = pg.Surface((1280, 800)).convert()
            self.build_biome(background, name)
            setattr(self, attr, background)
        target.blit(background, (0, 0))

    def build_market(self, target):
        self.fill(target, "tiny-town", 0, (0, 0, 1280, 800))
        self.fill(target, "rpg", (6, 2), (211, 185, 870, 442))
        self.scenery.local_overlay(target, "market")
        for x, y, color in [(327, 271, (193, 115, 92)), (816, 271, (90, 137, 162)), (586, 543, (183, 149, 79))]:
            # Pixel stall frame around genuine asset counters and produce.
            pg.draw.rect(target, (78, 59, 43), (x - 10, y - 50, 194, 66))
            for i in range(6):
                pg.draw.rect(target, color if i % 2 else (239, 219, 174), (x + i * 29, y - 45, 29, 50))
            for px in (x + 6, x + 165):
                pg.draw.rect(target, (104, 74, 50), (px, y - 44, 7, 128))
            self.grid(target, "rpg", [[(26, 3), (27, 3), (27, 5)]], x, y + 46, 58)
            for i, tile in enumerate((23, 35, 47)):
                self.tile(target, "tiny-farm", tile, x + i * 52 + 8, y + 31, 32)
        self.fence(target, 218, 665, 820)
        self.tile(target, "tiny-town", 104, 700, 340, 48)

    def market(self, target):
        if self.market_background is None:
            self.market_background = pg.Surface((1280, 800)).convert()
            self.build_market(self.market_background)
        target.blit(self.market_background, (0, 0))

    def room(self, target):
        target.fill((71, 85, 69))
        pg.draw.rect(target, (47, 57, 47), (170, 137, 940, 574))
        self.fill(target, "rpg", (8, 4), (188, 153, 904, 100))
        self.fill(target, "rpg", (8, 2), (188, 253, 904, 437))
        self.fill(target, "rpg", (17, 0), (188, 246, 904, 8))
        self.tile(target, "rpg", (33, 0), 611, 647, 58)

    def house(self, target):
        self.room(target)
        self.tile(target, "rpg", (28, 0), 211, 215, 80)
        self.tile(target, "rpg", (33, 2), 315, 214, 80)
        self.tile(target, "rpg", (31, 0), 402, 215, 80)
        self.grid(target, "rpg", [[(28, 1), (29, 2)], [(28, 2), (28, 3)]], 464, 171, 40)
        # Carpet: green nine-slice tiles.
        self.grid(target, "rpg", [[(10, 16), (11, 16), (11, 16), (11, 16), (12, 16)],
                                  [(10, 17), (11, 17), (11, 17), (11, 17), (12, 17)],
                                  [(10, 18), (11, 18), (11, 18), (11, 18), (12, 18)]], 500, 361)
        self.grid(target, "rpg", [[(26, 3), (27, 3), (27, 5)]], 532, 389, 64)
        for x in (548, 648):
            self.tile(target, "rpg", (19, 4), x, 500, 48)
        self.tile(target, "tiny-farm", 124, 561, 389, 32)
        self.tile(target, "tiny-farm", 125, 658, 389, 32)
        self.grid(target, "rpg", [[(23, 3), (24, 3)]], 823, 380, 96)
        self.tile(target, "rpg", (32, 0), 983, 181, 72)
        self.plant(target, 762, 279)
        self.tile(target, "rpg", (26, 8), 715, 187, 48)
        self.scenery.interior(target, "house")

    def bedroom(self, target):
        self.room(target)
        self.tile(target, "rpg", (17, 2), 284, 213, 176)
        self.grid(target, "rpg", [[(28, 1)], [(28, 2)], [(28, 3)]], 504, 200, 48)
        self.grid(target, "rpg", [[(23, 4), (24, 4)]], 788, 244, 144)
        self.tile(target, "rpg", (19, 4), 897, 363, 64)
        self.plant(target, 740, 304)
        for x in (564, 660):
            self.grid(target, "rpg", [[(44, 2)], [(44, 3)]], x, 154, 48)
        self.scenery.interior(target, "bedroom")

    def plant(self, target, x, y):
        self.tile(target, "tiny-farm", 76, x - 16, y - 32, 32)
        self.tile(target, "rpg", (28, 9), x - 24, y - 59, 48)

    def character(self, target, x, y, index, scale, frame, walking, facing="down", attacking=False, npc=None):
        name = npc or PLAYER_STYLES[index % len(PLAYER_STYLES)]
        anim = "Attack" if attacking else "Walk" if walking else "Idle"
        source = self.characters[name, anim]
        row = int(frame / 7) % 4 if anim == "Walk" else 0
        sprite = source.subsurface((FACING[facing] * 16, row * 16, 16, 16))
        size = max(16, round(16 * scale * 1.8))
        pg.draw.ellipse(target, (55, 70, 46), (x - size * .28, y - 7, size * .56, 11))
        target.blit(pg.transform.scale(sprite, (size, size)), (x - size / 2, y - size))

    def animal(self, target, species, x, y, size, facing, frame, moving):
        source = self.animal_sheets.get(species)
        if source is None:
            return
        if species in ("Gajah", "Kelinci"):
            cell_w, cell_h = source.get_width() // 4, source.get_height() // 4
            row = {"down": 0, "up": 1, "left": 2, "right": 3}[facing]
            col = int(frame / 8) % 4 if moving else 0
            sprite = source.subsurface((col * cell_w, row * cell_h, cell_w, cell_h))
        else:
            sideways = facing in ("left", "right") and species + "Side" in self.animal_sheets
            source = self.animal_sheets.get(species + "Side", source) if sideways else source
            col = 1 if facing in ("right", "down") else 0
            cell_w, cell_h = source.get_width() // 2, source.get_height()
            sprite = source.subsurface((col * cell_w, 0, cell_w, cell_h))
            if facing == "left" and not sideways:
                sprite = pg.transform.flip(sprite, True, False)
        height = size if species in ("Gajah", "Kelinci") else round(size * cell_h / cell_w)
        bob = int(moving and math.sin(frame / 5) > 0) * 2
        pg.draw.ellipse(target, (53, 76, 46), (x - size * .32, y - 7, size * .64, 11))
        target.blit(pg.transform.scale(sprite, (size, height)), (x - size / 2, y - height - bob))
