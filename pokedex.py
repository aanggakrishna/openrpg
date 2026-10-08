"""Asynchronous PokéAPI catalogue, detail and sprite cache."""
from __future__ import annotations

import json
import pokemon_db
from pathlib import Path
import queue
import ssl
import threading
from urllib.request import Request, urlopen
try:
    import certifi
except ImportError:  # Keep offline/cached play working before dependencies are refreshed.
    certifi = None

API = "https://pokeapi.co/api/v2"
TLS_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()


class PokedexClient:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_path = self.cache_dir / "species.json"
        self.catalog = []
        self.details = {}
        self.sprites = {}
        self.animated = {}
        self.species = {}
        self.evolution = {}
        self.jobs = queue.Queue()
        self.results = queue.Queue()
        self.requested = set()
        self.media_status = {}
        self.media_errors = {}
        self.requested_animation = set()
        self.requested_species = set()
        self.requested_evolution = set()
        self.items = {}
        self.requested_items = set()
        self.moves = {}
        self.requested_moves = set()
        self.cries = {}
        self.requested_cries = set()
        if self.catalog_path.exists():
            try:
                self.catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.catalog = []
        if not self.catalog:
            self.catalog = pokemon_db.catalog()
        self.worker = threading.Thread(target=self._work, daemon=True, name="pokeapi-cache")
        self.worker.start()
        self.request_catalog()
        self.request_item("poke-ball")

    def _get(self, url):
        request = Request(url, headers={"User-Agent": "OpenRPG/0.3 (Pokédex cache)"})
        with urlopen(request, timeout=14, context=TLS_CONTEXT) as response:
            return response.read()

    def request_catalog(self):
        if not self.catalog:
            self.jobs.put(("catalog", 0))

    def request(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        if not 1 <= pokemon_id <= 2000 or pokemon_id in self.requested or (pokemon_id in self.details and pokemon_id in self.sprites):
            return
        self.requested.add(pokemon_id)
        self.media_status[pokemon_id] = "loading"
        self.media_errors.pop(pokemon_id, None)
        self.jobs.put(("pokemon", pokemon_id))

    def request_animation(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        if pokemon_id in self.requested_animation or pokemon_id in self.animated:
            return
        self.requested_animation.add(pokemon_id)
        self.jobs.put(("animation", pokemon_id))

    def request_species(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        if pokemon_id in self.requested_species or pokemon_id in self.species:
            return
        self.requested_species.add(pokemon_id)
        self.jobs.put(("species", pokemon_id))

    def request_evolution(self, chain_id):
        chain_id = int(chain_id)
        if chain_id in self.requested_evolution or chain_id in self.evolution:
            return
        self.requested_evolution.add(chain_id)
        self.jobs.put(("evolution", chain_id))

    def request_item(self, name):
        if name in self.requested_items or name in self.items:
            return
        self.requested_items.add(name)
        self.jobs.put(("item", name))

    def request_move(self, name):
        if not name or name in self.requested_moves or name in self.moves:
            return
        self.requested_moves.add(name)
        self.jobs.put(("move", name))

    def request_cry(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        if pokemon_id in self.requested_cries or pokemon_id in self.cries:
            return
        self.requested_cries.add(pokemon_id)
        self.jobs.put(("cry", pokemon_id))

    def _work(self):
        while True:
            kind, pokemon_id = self.jobs.get()
            try:
                if kind == "catalog":
                    raw = json.loads(self._get(f"{API}/pokemon-species/?limit=2000"))
                    entries = []
                    for item in raw.get("results", []):
                        try:
                            ident = int(item["url"].rstrip("/").split("/")[-1])
                        except (KeyError, TypeError, ValueError):
                            continue
                        entries.append({"id": ident, "name": item["name"]})
                    entries.sort(key=lambda item: item["id"])
                    tmp = self.catalog_path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(entries), encoding="utf-8")
                    tmp.replace(self.catalog_path)
                    self.results.put(("catalog", entries))
                elif kind == "evolution":
                    path = self.cache_dir / f"evolution-{pokemon_id}.json"
                    if path.exists():
                        data = json.loads(path.read_text(encoding="utf-8"))
                    else:
                        data = pokemon_db.evolution(pokemon_id) or json.loads(self._get(f"{API}/evolution-chain/{pokemon_id}/"))
                        tmp = path.with_suffix(".tmp")
                        tmp.write_text(json.dumps(data), encoding="utf-8")
                        tmp.replace(path)
                    self.results.put(("evolution", {"id": pokemon_id, "data": data}))
                elif kind == "species":
                    path = self.cache_dir / f"species-{pokemon_id}.json"
                    if path.exists():
                        data = json.loads(path.read_text(encoding="utf-8"))
                    else:
                        data = pokemon_db.species(pokemon_id) or json.loads(self._get(f"{API}/pokemon-species/{pokemon_id}/"))
                        tmp = path.with_suffix(".tmp")
                        tmp.write_text(json.dumps(data), encoding="utf-8")
                        tmp.replace(path)
                    local = pokemon_db.species(pokemon_id)
                    if local and not data.get("flavor_text_entries"):
                        data = dict(data, flavor_text_entries=local.get("flavor_text_entries", []))
                    self.results.put(("species", {"id": pokemon_id, "data": data}))
                elif kind == "animation":
                    detail_path = self.cache_dir / f"{pokemon_id}.json"
                    detail = json.loads(detail_path.read_text(encoding="utf-8")) if detail_path.exists() else json.loads(self._get(f"{API}/pokemon/{pokemon_id}/"))
                    sprites = detail.get("sprites", {})
                    image_url = (sprites.get("other", {}).get("showdown", {}).get("front_default")
                                 or sprites.get("versions", {}).get("generation-v", {}).get("black-white", {}).get("animated", {}).get("front_default"))
                    image = None
                    if image_url:
                        path = self.cache_dir / f"{pokemon_id}-battle.gif"
                        if path.exists():
                            image = path.read_bytes()
                        else:
                            image = self._get(image_url)
                            tmp = path.with_suffix(".tmp")
                            tmp.write_bytes(image)
                            tmp.replace(path)
                    self.results.put(("animation", {"id": pokemon_id, "image": image}))
                elif kind == "item":
                    path = self.cache_dir / f"item-{pokemon_id}.png"
                    if path.exists():
                        image = path.read_bytes()
                    else:
                        detail = json.loads(self._get(f"{API}/item/{pokemon_id}/"))
                        image_url = detail.get("sprites", {}).get("default")
                        image = self._get(image_url) if image_url else None
                        if image:
                            tmp = path.with_suffix(".tmp")
                            tmp.write_bytes(image)
                            tmp.replace(path)
                    self.results.put(("item", {"name": pokemon_id, "image": image}))
                elif kind == "move":
                    path = self.cache_dir / f"move-{pokemon_id}.json"
                    if path.exists():
                        data = json.loads(path.read_text(encoding="utf-8"))
                    else:
                        data = pokemon_db.move(pokemon_id) or json.loads(self._get(f"{API}/move/{pokemon_id}/"))
                        tmp = path.with_suffix(".tmp")
                        tmp.write_text(json.dumps(data), encoding="utf-8")
                        tmp.replace(path)
                    self.results.put(("move", {"name": pokemon_id, "data": data}))
                elif kind == "cry":
                    path = self.cache_dir / f"{pokemon_id}-cry.ogg"
                    if path.exists():
                        audio = path.read_bytes()
                    else:
                        detail_path = self.cache_dir / f"{pokemon_id}.json"
                        detail = json.loads(detail_path.read_text(encoding="utf-8")) if detail_path.exists() else json.loads(self._get(f"{API}/pokemon/{pokemon_id}/"))
                        audio_url = detail.get("cries", {}).get("latest") or detail.get("cries", {}).get("legacy")
                        audio = self._get(audio_url) if audio_url else None
                        if audio:
                            tmp = path.with_suffix(".tmp")
                            tmp.write_bytes(audio)
                            tmp.replace(path)
                    self.results.put(("cry", {"id": pokemon_id, "audio": audio}))
                else:
                    detail_path = self.cache_dir / f"{pokemon_id}.json"
                    sprite_path = self.cache_dir / f"{pokemon_id}.png"
                    if detail_path.exists():
                        detail = json.loads(detail_path.read_text(encoding="utf-8"))
                    else:
                        detail = pokemon_db.detail(pokemon_id) or json.loads(self._get(f"{API}/pokemon/{pokemon_id}/"))
                        tmp = detail_path.with_suffix(".tmp")
                        tmp.write_text(json.dumps(detail), encoding="utf-8")
                        tmp.replace(detail_path)
                    image = sprite_path.read_bytes() if sprite_path.exists() else None
                    if image is not None and not image.startswith(b"\x89PNG\r\n\x1a\n"):
                        image = None
                    if image is None:
                        sprites = detail.get("sprites", {})
                        image_urls = (
                            sprites.get("other", {}).get("official-artwork", {}).get("front_default"),
                            sprites.get("front_default"),
                            f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{pokemon_id}.png",
                            f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pokemon_id}.png",
                        )
                        errors = []
                        for image_url in dict.fromkeys(url for url in image_urls if url):
                            try:
                                image = self._get(image_url)
                                if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                                    raise ValueError("server returned data that is not a PNG image")
                                tmp = sprite_path.with_suffix(".tmp")
                                tmp.write_bytes(image)
                                tmp.replace(sprite_path)
                                break
                            except Exception as exc:
                                errors.append(f"{type(exc).__name__}: {exc}")
                                image = None
                        self.results.put(("pokemon", {"id": pokemon_id, "detail": detail,
                                                        "image": image, "image_error": "; ".join(errors[-2:])}))
                    else:
                        self.results.put(("pokemon", {"id": pokemon_id, "detail": detail, "image": image,
                                                        "image_error": ""}))
            except Exception as exc:  # Network errors are reported to the game thread.
                self.results.put(("error", {"id": pokemon_id, "message": str(exc)}))

    def poll(self):
        items = []
        while True:
            try:
                kind, value = self.results.get_nowait()
            except queue.Empty:
                return items
            if kind == "catalog":
                self.catalog = value
            elif kind == "pokemon":
                self.details[value["id"]] = value["detail"]
                if value["image"]:
                    self.sprites[value["id"]] = value["image"]
                    self.media_status[value["id"]] = "ready"
                    self.media_errors.pop(value["id"], None)
                else:
                    self.media_status[value["id"]] = "failed"
                    self.media_errors[value["id"]] = value.get("image_error") or "Sprite image was unavailable."
                self.requested.discard(value["id"])
            elif kind == "animation":
                if value["image"]:
                    self.animated[value["id"]] = value["image"]
                self.requested_animation.discard(value["id"])
            elif kind == "species":
                self.species[value["id"]] = value["data"]
                self.requested_species.discard(value["id"])
            elif kind == "evolution":
                self.evolution[value["id"]] = value["data"]
                self.requested_evolution.discard(value["id"])
            elif kind == "item":
                if value.get("image"):
                    self.items[value["name"]] = value["image"]
                self.requested_items.discard(value["name"])
            elif kind == "move":
                self.moves[value["name"]] = value["data"]
                self.requested_moves.discard(value["name"])
            elif kind == "cry":
                if value.get("audio"):
                    self.cries[value["id"]] = value["audio"]
                self.requested_cries.discard(value["id"])
            else:
                self.requested.discard(value["id"])
                if kind == "error":
                    self.media_status[value["id"]] = "failed"
                    self.media_errors[value["id"]] = value.get("message", "Download failed.")
                    self.requested_animation.discard(value["id"])
                    self.requested_species.discard(value["id"])
                    self.requested_evolution.discard(value["id"])
                    self.requested_moves.clear()
                    self.requested_cries.discard(value["id"])
            items.append((kind, value))
