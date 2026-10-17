"""Offline-first browser Pokédex adapter with the desktop PokedexClient API."""
from __future__ import annotations

import queue
import sys
from pathlib import Path

import pygame as pg
import pokemon_db


class PokedexClient:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = pokemon_db.catalog()
        self.details = {}
        self.sprites = {}
        self.animated = {}
        self.species = {}
        self.evolution = {}
        self.items = {}
        self.moves = {}
        self.cries = {}
        self.results = queue.Queue()
        self.requested = set()
        self.requested_animation = set()
        self.requested_species = set()
        self.requested_evolution = set()
        self.requested_items = set()
        self.requested_moves = set()
        self.requested_cries = set()
        self.media_status = {}
        self.media_errors = {}

    def request_catalog(self):
        return None

    def request(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        if not 1 <= pokemon_id <= 20000 or pokemon_id in self.requested:
            return
        detail = pokemon_db.detail(pokemon_id)
        if not detail:
            self.media_status[pokemon_id] = "failed"
            self.media_errors[pokemon_id] = "Pokémon data is unavailable."
            return
        self.requested.add(pokemon_id)
        self.media_status[pokemon_id] = "ready"
        self.details[pokemon_id] = detail
        # WebAssembly cannot decode the desktop client's PNG bytes through
        # BytesIO. Load the bundled FireRed file directly instead, so a
        # partner, starter, and wild Pokémon never depend on a remote API.
        sprite = None
        name = str(detail.get("name", "")).lower().replace(" ", "-")
        path = Path(__file__).parent / "assets" / "gba" / "pokemon" / name / "front.png"
        if path.is_file():
            try:
                sprite = pg.image.load(str(path)).convert_alpha()
            except (pg.error, OSError):
                pass
        self.results.put(("pokemon", {"id": pokemon_id, "detail": detail,
                                      "image": None, "surface": sprite}))

    def request_animation(self, pokemon_id):
        self.requested_animation.add(int(pokemon_id))

    def request_species(self, pokemon_id):
        pokemon_id = int(pokemon_id)
        data = pokemon_db.species(pokemon_id)
        if data:
            self.species[pokemon_id] = data
            self.results.put(("species", {"id": pokemon_id, "data": data}))

    def request_evolution(self, chain_id):
        chain_id = int(chain_id)
        data = pokemon_db.evolution(chain_id)
        if data:
            self.evolution[chain_id] = data
            self.results.put(("evolution", {"id": chain_id, "data": data}))

    def request_item(self, name):
        self.requested_items.add(name)

    def request_move(self, name):
        data = pokemon_db.move(name)
        if data:
            self.moves[name] = data
            self.results.put(("move", {"name": name, "data": data}))

    def request_cry(self, pokemon_id):
        self.requested_cries.add(int(pokemon_id))

    def poll(self, limit=None):
        items = []
        while limit is None or len(items) < max(0, int(limit)):
            try:
                kind, value = self.results.get_nowait()
                if kind == "pokemon":
                    self.requested.discard(value["id"])
                items.append((kind, value))
            except queue.Empty:
                break
        return items
