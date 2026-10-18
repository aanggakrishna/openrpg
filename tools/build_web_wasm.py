#!/usr/bin/env python3
"""Package the current OpenRPG game for Pygame WebAssembly.

The desktop game remains the source of truth.  This tool copies its current
game modules unchanged into a browser filesystem, then replaces only the
platform boundaries (local terminal, network transport, and remote media).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "web_runtime"
STAGE = ROOT / ".web_wasm_build"
APP = STAGE / "assets"
OUTPUT = ROOT / "public" / "desktop" / "pygbag-source.tar.gz"
MANIFEST = ROOT / "public" / "desktop" / "build-manifest.json"

RUNTIME_MODULES = (
    "adventure_flow.py", "art.py", "combat_rules.py", "environment.py",
    "fighter.py", "gba_world.py", "i18n.py", "online_ui.py", "pokedex.py",
    "pokemon_db.py", "retro.py", "scenery.py", "state.py", "wildlife.py",
    "world_features.py", "world_regions.py",
)


def copytree(source: Path, destination: Path, *, ignore=None) -> None:
    shutil.copytree(source, destination, ignore=ignore, dirs_exist_ok=True)


def main() -> None:
    if not RUNTIME.is_dir():
        raise SystemExit("web_runtime is missing; browser adapters cannot be built.")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    APP.mkdir(parents=True)

    # Keep the desktop gameplay implementation intact. The browser copy only
    # removes the native TTS WAV dependency: Pygbag's package scanner treats
    # it as a third-party package, while the service itself cannot exist in a
    # browser. All maps, UI, player flow, combat, and state logic are copied.
    engine_source = (ROOT / "main.py").read_text(encoding="utf-8")
    engine_source = engine_source.replace("import wave\n", "")
    engine_source = engine_source.replace(
        "    def prepare_countdown_audio(self):\n",
        "    def prepare_countdown_audio(self):\n"
        "        if sys.platform == 'emscripten':\n"
        "            self.countdown_tts_loading = False\n"
        "            return\n",
    )
    engine_source = engine_source.replace(
        "    def speak_free_tts(self, phrase, rate=235):\n",
        "    def speak_free_tts(self, phrase, rate=235):\n"
        "        if sys.platform == 'emscripten':\n"
        "            return\n",
    )
    engine_source = engine_source.replace(
        "        pg.key.set_repeat()\n        pg.scrap.init()\n",
        "        pg.key.set_repeat()\n"
        "        try:\n"
        "            pg.scrap.init()\n"
        "        except (AttributeError, NotImplementedError, pg.error):\n"
        "            pass\n",
    )
    engine_source = engine_source.replace(
        "        if self.life.companion_id:\n"
        "            self.pokedex.request_animation(self.life.companion_id)\n",
        "        if self.life.companion_id:\n"
        "            self.pokedex.request(self.life.companion_id)\n"
        "            self.pokedex.request_animation(self.life.companion_id)\n",
    )
    engine_source = engine_source.replace(
        "            ident = value[\"id\"]\n"
        "            if value[\"image\"]:\n",
        "            ident = value[\"id\"]\n"
        "            browser_surface = value.get(\"surface\")\n"
        "            if browser_surface is not None:\n"
        "                self.poke_surfaces[ident] = self.fit_pokemon_sprite(browser_surface, 96)\n"
        "                self.poke_battle_surfaces[ident] = self.fit_pokemon_sprite(browser_surface, 136)\n"
        "                for key in [key for key in self.pokemon_render_cache if key[0] == ident]:\n"
        "                    del self.pokemon_render_cache[key]\n"
        "            elif value[\"image\"]:\n",
    )
    engine_source = engine_source.replace(
        "        if source is None:\n            return None\n        key = (ident, int(target_size), frame_index)\n",
        "        if source is None:\n"
        "            # Browser Pygame cannot decode network PNG bytes. Use the\n"
        "            # same bundled FireRed front sprites used by gate quizzes.\n"
        "            source = self.gate_quiz_sprite(ident, target_size)\n"
        "        if source is None:\n            return None\n        key = (ident, int(target_size), frame_index)\n",
    )
    # Publish a tiny read-only snapshot for the browser touch layer. This is
    # injected only into the WebAssembly copy: it lets the HTML controls show
    # the real battle cooldown and Ultimate meter rather than inventing them.
    browser_audio_bridge = '''    def request_browser_audio(self, path):
        """Queue an optional audio file from the static site after boot."""
        if sys.platform != "emscripten":
            return
        try:
            from browser_media import request
            audio_root = ROOT / "assets" / "audio"
            relative = Path(path).relative_to(audio_root).as_posix()
            request(relative, "/openrpg/assets/audio/" + relative, channel="audio")
        except Exception:
            pass

    def pump_browser_audio(self):
        """Place completed background downloads in Pygame's virtual FS."""
        if sys.platform != "emscripten":
            return
        try:
            from browser_media import poll
            while True:
                result = poll("audio")
                if not result:
                    break
                relative, data, _error = result
                if not data:
                    continue
                target = ROOT / "assets" / "audio" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        except Exception:
            pass

'''
    browser_mobile_bridge = '''    def publish_browser_mobile_state(self):
        try:
            import json
            import platform
            name_entry = bool(self.mode == "setup" and self.wizard.get("step") == 0)
            if name_entry:
                supplied_name = getattr(platform.window, "openrpgMobileNameInput", None)
                if supplied_name is not None:
                    clean_name = ''.join(char for char in str(supplied_name) if char.isprintable())[:18]
                    if clean_name != self.wizard.get("name", ""):
                        self.wizard["name"] = clean_name
            battle = self.battle if self.mode == "battle" else None
            if battle:
                blocked = bool(battle.get("result") or battle.get("intro") or
                               battle.get("boss_intro") or battle.get("capture") or
                               battle.get("ultimate_cutin"))
                snapshot = {
                    "mode": self.mode,
                    "battle": {
                        "locked": blocked,
                        "basicCooldown": round(max(0.0, float(battle.get("player_cooldown", 0.0))), 2),
                        "skillCooldown": round(max(0.0, float(battle.get("type_cooldown", 0.0))), 2),
                        "ultimateMeter": round(max(0.0, min(100.0, float(battle.get("super_meter", 0.0)))), 1),
                        "ultimateReady": bool(not blocked and battle.get("super_meter", 0.0) >= 100),
                    },
                }
            else:
                snapshot = {"mode": self.mode, "battle": None}
            snapshot["nameInput"] = name_entry
            snapshot["name"] = self.wizard.get("name", "") if name_entry else ""
            platform.window.openrpgMobileState = json.dumps(snapshot)
        except Exception:
            pass

'''
    engine_source = engine_source.replace(
        "    def update(self, dt):\n        self.frame += dt * 60\n",
        browser_audio_bridge + browser_mobile_bridge + "    def update(self, dt):\n        self.pump_browser_audio()\n        self.publish_browser_mobile_state()\n        self.frame += dt * 60\n",
        1,
    )
    if "def publish_browser_mobile_state" not in engine_source:
        raise SystemExit("Could not inject the browser mobile control state bridge.")
    engine_source = engine_source.replace(
        "        if path.is_file() and music_key != self._music_key:\n",
        "        if not path.is_file():\n"
        "            self.request_browser_audio(path)\n"
        "        if path.is_file() and music_key != self._music_key:\n",
    )
    engine_source = engine_source.replace(
        "        if not path.is_file():\n            return\n        try:\n            sound = self.action_sounds.get(filename)\n",
        "        if not path.is_file():\n"
        "            self.request_browser_audio(path)\n"
        "            return\n"
        "        try:\n            sound = self.action_sounds.get(filename)\n",
        1,
    )
    engine_source = engine_source.replace(
        "    def play_battle_sound(self, sound_name, volume=0.52):\n"
        "        sound = self.battle_sounds.get(sound_name)\n"
        "        if sound:\n"
        "            sound.set_volume(volume)\n"
        "            sound.play()\n",
        "    def play_battle_sound(self, sound_name, volume=0.52):\n"
        "        sound = self.battle_sounds.get(sound_name)\n"
        "        if sound:\n"
        "            sound.set_volume(volume)\n"
        "            sound.play()\n"
        "        elif sys.platform == 'emscripten':\n"
        "            self.request_browser_audio(ROOT / 'assets' / 'audio' / 'sfx' / f'{sound_name}.ogg')\n",
    )
    (APP / "game_engine.py").write_text(engine_source, encoding="utf-8")
    for name in RUNTIME_MODULES:
        shutil.copy2(ROOT / name, APP / name)

    # Pygame WebAssembly has no OS emoji font.  Keep the desktop font path
    # untouched, but replace it in the staged browser build with compact,
    # coloured pixel icons so existing emoji-driven gameplay remains visible.
    browser_retro = (APP / "retro.py").read_text(encoding="utf-8")
    icon_font_start = browser_retro.index("class IconFont:")
    browser_retro = browser_retro[:icon_font_start] + '''class IconFont:
    """Browser-safe pixel pictograms for the game's existing emoji prompts."""
    def __init__(self, size):
        self.pixels = max(12, int(size))
        self.cache = {}

    @staticmethod
    def _box(surface, color, x, y, w, h, width=0):
        pg.draw.rect(surface, color, (x, y, w, h), width)

    def _icon(self, text):
        size = self.pixels
        icon = pg.Surface((size, size), pg.SRCALPHA)
        q = max(1, size // 20)
        def p(value): return int(value * q)
        def rect(color, x, y, w, h, width=0):
            pg.draw.rect(icon, color, (p(x), p(y), p(w), p(h)), p(width) if width else 0)
        def line(color, points, width=1):
            pg.draw.lines(icon, color, False, [(p(x), p(y)) for x, y in points], p(width))
        def poly(color, points):
            pg.draw.polygon(icon, color, [(p(x), p(y)) for x, y in points])
        def ellipse(color, x, y, w, h, width=0):
            pg.draw.ellipse(icon, color, (p(x), p(y), p(w), p(h)), p(width) if width else 0)

        # Preserve the meaning and colour of the real emoji, rather than
        # silently substituting missing-font tofu boxes.
        if text in ("🔥", "🌋"):
            poly((176, 45, 32), [(10,19),(3,14),(8,3),(12,10),(15,1),(18,12),(16,18)])
            poly((255, 178, 43), [(10,17),(7,13),(11,7),(13,13),(15,15)])
        elif text in ("💧", "💦", "🌊", "🌧"):
            poly((59, 154, 224), [(10,2),(4,12),(4,16),(7,19),(13,19),(16,16),(16,12)])
            ellipse((173, 234, 255), 7, 11, 4, 5)
        elif text in ("🍃", "🌿", "🍀"):
            line((47, 106, 45), [(10,18),(10,7)], 2)
            ellipse((68, 180, 79), 2, 5, 9, 7)
            ellipse((94, 205, 86), 9, 2, 8, 9)
        elif text == "⚡":
            poly((255, 215, 49), [(12,1),(4,11),(9,11),(7,19),(17,7),(12,7)])
            line((183, 113, 27), [(12,1),(4,11),(9,11)], 1)
        elif text in ("❄", "❄️", "☃"):
            for a, b in (((10,1),(10,19)),((2,5),(18,15)),((18,5),(2,15))): line((125,221,255), [a,b], 2)
        elif text in ("🪨",):
            poly((112, 91, 78), [(3,16),(5,8),(11,4),(17,8),(18,15),(14,19),(6,19)])
            poly((163, 139, 116), [(6,10),(11,6),(15,10),(12,13),(7,13)])
        elif text in ("💥", "💢", "💫"):
            poly((255, 202, 41), [(10,1),(12,7),(18,4),(14,10),(19,12),(13,13),(14,19),(10,15),(5,19),(6,13),(1,11),(6,9),(3,4),(8,7)])
            ellipse((243, 88, 55), 8, 8, 4, 4)
        elif text in ("☠", "☠️"):
            ellipse((205, 184, 192), 3, 3, 14, 12)
            ellipse((36, 42, 59), 6, 7, 3, 3); ellipse((36, 42, 59), 12, 7, 3, 3)
            rect((36,42,59), 7, 13, 6, 2)
            line((205,184,192), [(4,18),(16,20)], 2); line((205,184,192), [(16,18),(4,20)], 2)
        elif text in ("🌪", "💨"):
            for y, width in ((5,10),(9,15),(13,12),(17,7)):
                line((187, 231, 236), [(10-width//2,y),(10+width//2,y)], 2)
        elif text == "🔮":
            ellipse((74, 42, 130), 3, 3, 14, 14); ellipse((180, 117, 231), 5, 5, 7, 6)
            rect((232, 206, 111), 6, 17, 8, 2)
        elif text == "🐞":
            ellipse((26, 27, 38), 8, 3, 4, 4); ellipse((221, 59, 49), 4, 6, 12, 12)
            line((36,38,46), [(10,6),(10,18)], 1)
            ellipse((36,38,46), 6, 10, 2, 2); ellipse((36,38,46), 12, 10, 2, 2)
        elif text == "👻":
            ellipse((230, 220, 244), 3, 3, 14, 14)
            poly((230,220,244), [(3,11),(3,18),(6,16),(9,19),(12,16),(16,18),(17,11)])
            ellipse((60,44,87), 6, 8, 2, 3); ellipse((60,44,87), 12, 8, 2, 3)
        elif text in ("🐉",):
            ellipse((71, 168, 98), 4, 5, 12, 12); poly((232, 141, 49), [(5,7),(1,2),(8,5)])
            ellipse((255,238,144), 13, 8, 2, 2)
        elif text == "🌑":
            ellipse((48, 54, 75), 2, 2, 16, 16); ellipse((93, 102, 125), 5, 5, 3, 3)
        elif text == "⚙":
            for angle in range(0, 360, 45):
                # A small square gear is more legible than a missing glyph.
                pass
            rect((153, 169, 181), 4, 4, 12, 12); ellipse((66,77,91), 7, 7, 6, 6)
            rect((153,169,181), 8, 1, 4, 18); rect((153,169,181), 1, 8, 18, 4)
        elif text in ("✨", "⭐", "🏁", "🧬"):
            poly((255, 221, 79), [(10,1),(12,7),(19,10),(12,12),(10,19),(8,12),(1,10),(8,8)])
            if text == "🏁":
                rect((235,235,224), 3, 4, 13, 11); rect((37,49,57), 3, 4, 6, 5); rect((37,49,57), 10, 10, 6, 5)
        elif text == "🎲":
            rect((242, 239, 215), 3, 3, 14, 14); rect((91, 46, 53), 3, 3, 14, 14, 1)
            for x, y in ((6,6),(14,6),(10,10),(6,14),(14,14)): ellipse((190,55,55),x,y,2,2)
        elif text in ("✊", "✋", "✌", "✌️", "🦵", "🥊"):
            ellipse((246, 184, 125), 4, 7, 12, 10)
            if text in ("✋",):
                for x in (5,8,11,14): rect((246,184,125), x, 3, 2, 8)
            elif text in ("✌", "✌️"):
                rect((246,184,125), 6, 2, 3, 8); rect((246,184,125), 11, 2, 3, 8)
        elif text in ("🥤", "🧋", "☕", "🍵", "🧃", "🍹", "🥛"):
            rect((80, 177, 221), 5, 6, 10, 12); rect((225, 242, 247), 5, 5, 10, 2)
            line((239, 99, 102), [(12,1),(10,6)], 2)
        elif text in ("🍜", "🍛", "🍱", "🍕", "🍔", "🍙", "🍲", "🥪"):
            ellipse((234, 177, 76), 3, 9, 14, 8); ellipse((255, 235, 178), 5, 8, 10, 5)
            line((183,72,52), [(7,10),(14,12)], 2)
        else:
            # Unknown emoji: display a clear Poké Ball-like game icon, never a
            # blank/missing-font square.
            ellipse((234, 70, 67), 2, 2, 16, 16)
            rect((241, 240, 224), 2, 10, 16, 2)
            ellipse((246, 245, 230), 7, 7, 6, 6); ellipse((50, 61, 68), 9, 9, 2, 2)
        return icon

    def render(self, text, antialias, color):
        key = (text, tuple(color))
        if key not in self.cache:
            self.cache[key] = self._icon(text)
        return self.cache[key]
'''
    (APP / "retro.py").write_text(browser_retro, encoding="utf-8")

    # Pygbag is single-threaded.  Desktop uses a worker only to pre-render
    # sanctuary chunks; in the browser render the identical chunk on demand.
    browser_art = (APP / "art.py").read_text(encoding="utf-8")
    browser_art = browser_art.replace("import threading\n", "import threading\nimport sys\n")
    browser_art = browser_art.replace(
        "        self.reserve_chunk_worker = threading.Thread(\n"
        "            target=self._reserve_chunk_worker, name=\"openrpg-biome-render\", daemon=True)\n"
        "        self.reserve_chunk_worker.start()\n"
        "        self.request_reserve_chunk(0)\n",
        "        self.reserve_chunk_worker = None\n"
        "        if sys.platform != 'emscripten':\n"
        "            self.reserve_chunk_worker = threading.Thread(\n"
        "                target=self._reserve_chunk_worker, name=\"openrpg-biome-render\", daemon=True)\n"
        "            self.reserve_chunk_worker.start()\n"
        "        self.request_reserve_chunk(0)\n",
    )
    browser_art = browser_art.replace(
        "            self.reserve_chunk_pending.add(index)\n"
        "            self.reserve_chunk_jobs.put(index)\n",
        "            self.reserve_chunk_pending.add(index)\n"
        "            if self.reserve_chunk_worker is None:\n"
        "                try:\n"
        "                    self.reserve_chunk_results.put((index, self.build_reserve_chunk(index), None))\n"
        "                except Exception as error:\n"
        "                    self.reserve_chunk_results.put((index, None, error))\n"
        "            else:\n"
        "                self.reserve_chunk_jobs.put(index)\n",
    )
    (APP / "art.py").write_text(browser_art, encoding="utf-8")

    # FireRed sprites only exist through Gen III. Keep the browser's first
    # random partner within that local, offline-ready set.
    browser_flow = (APP / "adventure_flow.py").read_text(encoding="utf-8")
    browser_flow = browser_flow.replace(
        "STARTERS = (1,4,7,25,37,43,54,58,60,66,74,92,133,152,155,158,179,187,252,255,258,280,387,390,393,403)",
        "STARTERS = (1,4,7,25,37,43,54,58,60,66,74,92,133,152,155,158,179,187,252,255,258,280)",
    )
    # Pygbag does not consistently emit TEXTINPUT from touch-driven virtual
    # keys. Let the browser build accept ordinary A-Z keydown events only in
    # the existing character-name step; desktop text input remains unchanged.
    browser_flow = browser_flow.replace(
        "            if event.type==pg.KEYDOWN:\n                if event.key==pg.K_BACKSPACE:\n"
        "                    self.wizard['name']=self.wizard['name'][:-1]\n",
        "            if event.type==pg.KEYDOWN:\n"
        "                if pg.K_a <= event.key <= pg.K_z:\n"
        "                    self.wizard['name']=(self.wizard['name']+chr(event.key))[:18];return\n"
        "                if event.key==pg.K_SPACE:\n"
        "                    self.wizard['name']=(self.wizard['name']+' ')[:18];return\n"
        "                if event.key==pg.K_BACKSPACE:\n"
        "                    self.wizard['name']=self.wizard['name'][:-1]\n",
        1,
    )
    (APP / "adventure_flow.py").write_text(browser_flow, encoding="utf-8")

    # Browser-only seams.  They expose the same interfaces as desktop modules.
    for name in ("main.py", "terminal.py", "pokedex.py", "online_client.py", "browser_media.py"):
        shutil.copy2(RUNTIME / name, APP / name)
    copytree(RUNTIME / "PIL", APP / "PIL")

    # The full map, GBA assets, UI, sound, and all non-Pokémon artwork live in
    # the archive.  Sprite files are served separately from public/assets so
    # they are fetched only when a species is actually needed.
    def ignored(directory: str, names: list[str]):
        # Audio is hosted as separate static files and downloaded only when a
        # scene or action requests it. Keeping it out of the boot archive cuts
        # the phone's mandatory first download by roughly 58 MiB.
        ignored_names = {".DS_Store", "pokemon-sprites", "audio", "__pycache__"}
        return [name for name in names if name in ignored_names]

    copytree(ROOT / "assets", APP / "assets", ignore=ignored)
    public_sprites = ROOT / "public" / "assets" / "pokemon-sprites"
    copytree(ROOT / "assets" / "pokemon-sprites", public_sprites)

    # The loader unpacks this archive under /data/data/pygbag-source and adds
    # its assets/ directory to sys.path.
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    with tarfile.open(temporary, "w:gz", compresslevel=6) as archive:
        archive.add(APP, arcname="assets")
    temporary.replace(OUTPUT)

    desktop_main = ROOT / "main.py"
    manifest = {
        "engine": "Pygame WebAssembly / Pygbag",
        "desktop_main_sha256": hashlib.sha256(desktop_main.read_bytes()).hexdigest(),
        "browser_game_engine_sha256": hashlib.sha256((APP / "game_engine.py").read_bytes()).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "game_engine.py preserves desktop gameplay; only native terminal/TTS and browser transport adapters differ.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Built {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MiB)")
    print(f"Desktop game checksum: {manifest['desktop_main_sha256']}")


if __name__ == "__main__":
    main()
