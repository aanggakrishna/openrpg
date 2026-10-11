#!/usr/bin/env python3
"""Create the browser-only Pygbag source tree from the desktop engine.

The desktop files stay untouched.  Browser replacements remove the local shell,
native worker threads, and direct PokéAPI access while retaining the same game
engine, state format, combat, map, and assets.
"""

# Build with:
#   python3 tools/build_wasm_bundle.py
#   /tmp/openrpg-pygbag-venv/bin/pygbag --build --disable-sound-format-error .web_wasm_build
# Then copy ``.web_wasm_build/build/web/.web_wasm_build.tar.gz`` to
# ``public/desktop/openrpg-game.tar.gz`` and update the generated loader URL.
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".web_wasm_build"

MODULES = [
    "adventure_flow.py", "art.py", "combat_rules.py", "environment.py", "fighter.py",
    "i18n.py", "online_combat.py", "online_ui.py", "pokedex.py", "pokemon_db.py",
    "retro.py", "scenery.py", "state.py", "wildlife.py", "world_features.py", "world_regions.py",
]

BROWSER_MAIN = r'''"""Browser entry point for the shared desktop game engine."""
import asyncio
import json
import sys
from pathlib import Path
import pygame as pg
import browser_media


async def main():
    # Import after browser startup so failures are shown in the outer shell.
    from game_engine import Game, ROOT
    save_path = ROOT / ".openrpg" / "save.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "emscripten":
        try:
            from platform import window
            cloud_save = window.parent.OPENRPG_WASM_SAVE
            if cloud_save:
                bundle = json.loads(str(cloud_save))
                files = bundle.get("files", {}) if bundle.get("format") == "openrpg-web-save-v1" else {}
                allowed = {"save.json", *(f"profiles/slot-{slot}.json" for slot in range(1, 5))}
                for relative, contents in files.items():
                    if relative in allowed:
                        target = save_path.parent / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(str(contents), encoding="utf-8")
        except Exception:
            pass
    game = Game(ROOT / "computer-workspace", save_path=save_path)
    if sys.platform == "emscripten":
        try:
            from platform import window
            game.online_url = str(window.parent.OPENRPG_CONFIG.onlineServerUrl or "")
        except Exception:
            pass
    clock, last_save = pg.time.Clock(), 0.0

    def cloud_bundle():
        files = {}
        paths = [("save.json", save_path)]
        paths.extend((f"profiles/slot-{slot}.json", save_path.parent / "profiles" / f"slot-{slot}.json") for slot in range(1, 5))
        for relative, path in paths:
            try: files[relative] = path.read_text(encoding="utf-8")
            except OSError: pass
        return json.dumps({"format": "openrpg-web-save-v1", "files": files})

    try:
        while game.running:
            dt = min(.05, clock.tick(60) / 1000)
            for event in pg.event.get(): game.handle(event)
            game.update(dt); game.draw()
            if sys.platform == "emscripten" and game.playing:
                last_save += dt
                if last_save >= 15:
                    last_save = 0; game.save_current()
                    try:
                        from platform import window
                        window.parent.postMessage(json.dumps({"type":"openrpg-wasm-save", "save":cloud_bundle()}), "*")
                    except Exception: pass
            await asyncio.sleep(0)
            await browser_media.pump()
    finally:
        game.save_current()
        if sys.platform == "emscripten":
            try:
                from platform import window
                window.parent.postMessage(json.dumps({"type":"openrpg-wasm-save", "save":cloud_bundle()}), "*")
            except Exception: pass
        game.terminal.close(); pg.quit()

try:
    asyncio.run(main())
except Exception:
    # Keep startup failures visible in the web shell instead of leaving a blank
    # canvas. This also lets the authenticated parent page report the error.
    import traceback
    error = traceback.format_exc()
    print(error)
    if sys.platform == "emscripten":
        try:
            from platform import window
            window.document.getElementById("infobox").innerText = error
            window.document.getElementById("infobox").style.display = "block"
            window.parent.postMessage(json.dumps({"type": "openrpg-wasm-error", "error": error}), "*")
        except Exception:
            pass
'''

BROWSER_TERMINAL = '''from pathlib import Path
class _Screen:
    def __init__(self, lines): self.display=[\"\"]*lines; self.dirty=set(range(lines))
class BrowserTerminal:
    def __init__(self, project, columns=132, lines=36, shell=None):
        self.project=Path(project); self.columns=columns; self.lines=lines; self.screen=_Screen(lines); self.error=\"\"; self.bytes_received=0; self.phone_marker=\"\"; self.phone_command=\"\"
    @property
    def shell_name(self): return \"BROWSER\"
    @property
    def running(self): return False
    def start(self): self.error=\"Terminal is available in the desktop edition.\"
    def close(self): pass
    def poll(self): pass
    def send(self, data): pass
    def paste(self, data): pass
    def scroll(self, amount): pass
    def return_to_bottom(self): pass
    def run_from_phone(self, command): return \"Terminal is available in the desktop edition.\"
    def open_external(self): return \"Terminal is available in the desktop edition.\"
'''

BROWSER_MEDIA = '''import asyncio, queue, sys
_pending=queue.Queue(); _finished={\"pokemon\":queue.Queue(),\"audio\":queue.Queue()}; _active=set(); _requested=set()
def request(key,url,channel=\"pokemon\"):
    if (channel,key) not in _requested: _requested.add((channel,key)); _pending.put((channel,key,url))
def poll(channel=\"pokemon\"):
    try: result=_finished[channel].get_nowait()
    except queue.Empty: return None
    _requested.discard((channel,result[0])); return result
async def _fetch(channel,key,url):
    try:
        from aio.filelike import fopen
        async with fopen(url,\"rb\") as source: data=source.read()
        _finished[channel].put((key,data,\"\"))
    except Exception as exc: _finished[channel].put((key,None,f\"{type(exc).__name__}: {exc}\"))
async def pump():
    if sys.platform != \"emscripten\": return
    for task in tuple(_active):
        if task.done(): _active.discard(task)
    while len(_active)<3:
        try: channel,key,url=_pending.get_nowait()
        except queue.Empty: break
        _active.add(asyncio.create_task(_fetch(channel,key,url)))
'''

BROWSER_ONLINE = r'''import asyncio, json, queue, time
class OnlineClient:
    def __init__(self,url,profile):
        self.url=url.rstrip("/"); self.profile=dict(profile); self.token=self.profile.get("token",""); self.commands=queue.Queue(maxsize=32); self.events=queue.SimpleQueue(); self.keys={}; self.connected=False; self.stopped=False; self.last_input=0.; self.pending=0; self.send("connect",profile=self.profile)
    def send(self,action,**kwargs):
        body=kwargs.get("profile",self.profile) if action=="connect" else dict(action=action,**kwargs)
        try:self.commands.put_nowait((action,body))
        except queue.Full:self.events.put(("error","Please wait for the previous actions"))
    def pump(self,dt=0):
        if self.stopped:return
        if self.connected and time.monotonic()-self.last_input>=.085:self.last_input=time.monotonic();self.send("input",keys=dict(self.keys))
        if self.pending>=2:return
        try:action,body=self.commands.get_nowait()
        except queue.Empty:return
        self.pending+=1;asyncio.create_task(self._request(action,body))
    async def _request(self,action,body):
        try:
            from platform import window,ffi,jsiter
            path="/connect" if action=="connect" else "/action"; headers={"Content-Type":"application/json"}
            if action!="connect" and self.token:headers["Authorization"]="Bearer "+self.token
            response=await jsiter(window.fetch(self.url+path,ffi({"method":"POST","headers":ffi(headers),"body":json.dumps(body)})));data=await jsiter(response.json())
            if not response.ok:raise ValueError(data.get("error","Online server refused the request"))
            if action=="connect":self.token=data.get("token","");self.connected=True;self.events.put(("connected",data))
            else:data["_action"]=action;self.events.put(("state",data))
        except Exception as exc:self.events.put(("disconnected" if action=="connect" else "error",str(exc)[:180]));self.connected=False if action=="connect" else self.connected
        finally:self.pending=max(0,self.pending-1)
    def close(self):self.connected=False;self.stopped=True
'''

def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")

def main() -> None:
    if STAGE.exists(): shutil.rmtree(STAGE)
    STAGE.mkdir()
    for module in MODULES: shutil.copy2(ROOT / module, STAGE / module)
    shutil.copytree(ROOT / "assets", STAGE / "assets", ignore=shutil.ignore_patterns("pokedex.sqlite3"))
    engine = (ROOT / "main.py").read_text(encoding="utf-8")
    # The browser Python runtime does not bundle the stdlib wave module. The
    # desktop-only countdown WAV verifier is deliberately disabled there.
    engine = engine.replace("import wave", "if sys.platform != 'emscripten':\n    import wave\nelse:\n    wave = None")
    engine = engine.replace("from PIL import Image", "try:\n    from PIL import Image\nexcept ImportError:\n    Image = None")
    engine = engine.replace("from terminal import ShellTerminal", "if sys.platform == 'emscripten':\n    from browser_terminal import BrowserTerminal as ShellTerminal\nelse:\n    from terminal import ShellTerminal")
    engine = engine.replace("        pg.scrap.init()", "        if sys.platform != 'emscripten':\n            try: pg.scrap.init()\n            except pg.error: pass")
    engine = engine.replace("    def prepare_countdown_audio(self):\n", "    def prepare_countdown_audio(self):\n        if sys.platform == 'emscripten':\n            self.countdown_tts_loading = False\n            return\n")
    engine = engine.replace("        # A interrupted OS speech renderer can leave a valid header with no PCM.\n        # SDL_mixer may accept that file but crash when its empty Sound is played.\n        try:", "        # A interrupted OS speech renderer can leave a valid header with no PCM.\n        # SDL_mixer may accept that file but crash when its empty Sound is played.\n        if wave is None:\n            return False\n        try:")
    engine = engine.replace("    def speak_free_tts(self, phrase, rate=235):\n", "    def speak_free_tts(self, phrase, rate=235):\n        if sys.platform == 'emscripten':\n            return\n")
    write(STAGE / "game_engine.py", engine)
    art = (ROOT / "art.py").read_text(encoding="utf-8")
    art = art.replace("import threading", "import threading\nimport sys")
    art = art.replace("        self.reserve_chunk_worker = threading.Thread(\n            target=self._reserve_chunk_worker, name=\"openrpg-biome-render\", daemon=True)\n        self.reserve_chunk_worker.start()", "        self.reserve_chunk_worker = None\n        if sys.platform != 'emscripten':\n            self.reserve_chunk_worker = threading.Thread(target=self._reserve_chunk_worker, name='openrpg-biome-render', daemon=True)\n            self.reserve_chunk_worker.start()")
    art = art.replace("            self.reserve_chunk_pending.add(index)\n            self.reserve_chunk_jobs.put(index)", "            self.reserve_chunk_pending.add(index)\n            if self.reserve_chunk_worker is None:\n                try:\n                    self.reserve_chunks[index] = self.build_reserve_chunk(index)\n                    self.reserve_chunk_pending.discard(index)\n                except Exception:\n                    self.reserve_chunk_errors.add(index)\n            else:\n                self.reserve_chunk_jobs.put(index)")
    write(STAGE / "art.py", art)
    dex = (ROOT / "pokedex.py").read_text(encoding="utf-8")
    dex = dex.replace("import json", "import json\nimport sys")
    dex = dex.replace("import pokemon_db", "import pokemon_db")
    dex = dex.replace("import ssl\nimport threading\nfrom urllib.request import Request, urlopen\ntry:\n    import certifi\nexcept ImportError:  # Keep offline/cached play working before dependencies are refreshed.\n    certifi = None\n\nAPI = \"https://pokeapi.co/api/v2\"\nTLS_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()", "import threading\nif sys.platform != 'emscripten':\n    import ssl\n    from urllib.request import Request, urlopen\n    try:\n        import certifi\n    except ImportError:\n        certifi = None\n    TLS_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()\nelse:\n    TLS_CONTEXT = None\n\nAPI = 'https://pokeapi.co/api/v2'")
    dex = dex.replace("        self.worker = threading.Thread(target=self._work, daemon=True, name=\"pokeapi-cache\")\n        self.worker.start()", "        self.worker = None\n        if sys.platform != 'emscripten':\n            self.worker = threading.Thread(target=self._work, daemon=True, name='pokeapi-cache')\n            self.worker.start()")
    dex = dex.replace("        self.requested.add(pokemon_id)\n        self.media_status[pokemon_id] = \"loading\"\n        self.media_errors.pop(pokemon_id, None)\n        self.jobs.put((\"pokemon\", pokemon_id))", "        self.requested.add(pokemon_id)\n        self.media_status[pokemon_id] = 'loading'\n        self.media_errors.pop(pokemon_id, None)\n        if sys.platform == 'emscripten':\n            detail = pokemon_db.detail(pokemon_id)\n            sprite = None\n            try:\n                sprite = (Path(__file__).resolve().parent / 'assets' / 'pokemon-sprites' / f'{pokemon_id}.png').read_bytes()\n            except OSError:\n                pass\n            self.results.put(('pokemon', {'id': pokemon_id, 'detail': detail or {}, 'image': sprite, 'image_error': '' if sprite else 'Sprite unavailable'}))\n            return\n        self.jobs.put(('pokemon', pokemon_id))")
    dex = dex.replace("        self.jobs.put((\"species\", pokemon_id))", "        if sys.platform == 'emscripten':\n            self.species[pokemon_id] = pokemon_db.detail(pokemon_id) or {}\n            return\n        self.jobs.put(('species', pokemon_id))")
    dex = dex.replace("        self.jobs.put((\"evolution\", chain_id))", "        if sys.platform == 'emscripten':\n            self.evolution[chain_id] = {}\n            return\n        self.jobs.put(('evolution', chain_id))")
    dex = dex.replace("        self.jobs.put((\"item\", name))", "        if sys.platform == 'emscripten':\n            self.items[name] = {}\n            return\n        self.jobs.put(('item', name))")
    dex = dex.replace("        self.jobs.put((\"move\", name))", "        if sys.platform == 'emscripten':\n            self.moves[name] = {}\n            return\n        self.jobs.put(('move', name))")
    dex = dex.replace("        self.jobs.put((\"cry\", pokemon_id))", "        if sys.platform == 'emscripten': return\n        self.jobs.put(('cry', pokemon_id))")
    write(STAGE / "pokedex.py", dex)
    online = (ROOT / "online_ui.py").read_text(encoding="utf-8")
    online = online.replace("from online_client import OnlineClient", "import sys\nif sys.platform == 'emscripten':\n    from browser_online import OnlineClient\nelse:\n    from online_client import OnlineClient")
    write(STAGE / "online_ui.py", online)
    write(STAGE / "main.py", BROWSER_MAIN)
    write(STAGE / "browser_terminal.py", BROWSER_TERMINAL)
    write(STAGE / "browser_media.py", BROWSER_MEDIA)
    write(STAGE / "browser_online.py", BROWSER_ONLINE)

if __name__ == "__main__": main()
