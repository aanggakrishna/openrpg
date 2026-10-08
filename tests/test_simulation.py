import json
import tempfile
import unittest
from pathlib import Path

from state import Life
from wildlife import Wildlife, hunting_time


class SimulationTests(unittest.TestCase):
    def test_old_save_migrates_inventory_and_health(self):
        life = Life()
        raw = {key: getattr(life, key) for key in ("character", "scene", "x", "y", "day", "minutes", "elapsed", "stats", "crops", "fed_at", "accomplishments")}
        raw["bag"] = {"Sayur": 7, "Ikan": 3, "Telur": 5, "Makanan": 2}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "save.json"
            path.write_text(json.dumps(raw))
            loaded = Life.load(path)
            self.assertEqual(loaded.bag["Telur"], 5)
            self.assertEqual(loaded.bag["Busur"], 0)
            self.assertEqual(loaded.health, 100)
            self.assertEqual(loaded.money, 150)

    def test_trade_preserves_money_and_prevents_invalid_sales(self):
        life = Life()
        life.trade("Tombak", True)
        self.assertEqual((life.money, life.bag["Tombak"]), (70, 1))
        life.trade("Tombak", True)
        self.assertEqual(life.money, 70)
        life.trade("Busur", True)
        self.assertEqual(life.bag["Busur"], 0)
        life.trade("Telur", False)
        self.assertEqual((life.money, life.bag["Telur"]), (82, 0))
        life.trade("Telur", False)
        self.assertEqual(life.money, 82)
        life.minutes = 23 * 60
        life.trade("Panah", True)
        self.assertEqual(life.money, 82)

    def test_hour_skip_wraps_day_and_grows_plants(self):
        life = Life(minutes=23 * 60 + 30)
        life.garden(0); life.garden(0)
        life.skip_hour()
        self.assertEqual((life.day, life.hour), (2, 0))
        self.assertEqual(int(life.minutes % 60), 30)
        self.assertEqual(life.crops[0]["stage"], "ripe")

    def test_respawn_preserves_inventory_money_and_clock(self):
        life = Life(health=0, scene="forest", mounted=True)
        life.bag["Tombak"] = 1
        life.money = 77
        life.respawn()
        self.assertEqual((life.scene, life.health, life.mounted), ("bedroom", 100, False))
        self.assertEqual((life.bag["Tombak"], life.money, life.hour), (1, 77, 8))

    def test_hunting_schedule_and_predator_prey_combat(self):
        self.assertTrue(hunting_time("Singa", 7))
        self.assertFalse(hunting_time("Singa", 12))
        self.assertTrue(hunting_time("Hyena", 23))
        life = Life(minutes=7 * 60, scene="bedroom")
        world = Wildlife(life)
        lion, rabbit = world.spawn("Singa", 0), world.spawn("Kelinci", 1)
        lion.update(x=600, y=400); rabbit.update(x=625, y=400)
        life.animals = [lion, rabbit]
        world.update(.01)
        self.assertEqual(rabbit["hp"], 0)
        self.assertEqual(life.bag["Daging"], 0)
        self.assertTrue(world.events)
        lion["cooldown"] = 0; rabbit.update(world.spawn("Kelinci", 1)); rabbit.update(x=625, y=400)
        life.minutes = 12 * 60
        world.update(.01)
        self.assertEqual(lion["state"], "Tidur")
        self.assertEqual(rabbit["hp"], 28)

    def test_player_hunt_yields_loot_and_elephant_retaliates(self):
        life = Life(minutes=12 * 60, scene="forest", x=600, y=400)
        world = Wildlife(life)
        rabbit = world.spawn("Kelinci", 0)
        world.hit(rabbit, 28)
        self.assertEqual((life.bag["Daging"], life.bag["Kulit"], life.kills), (1, 1, 1))
        elephant = world.spawn("Gajah", 1)
        elephant.update(x=615, y=400)
        life.animals = [elephant]
        world.hit(elephant, 28)
        world.update(.01)
        self.assertEqual(life.health, 75)

    def test_extended_save_roundtrip(self):
        life = Life(scene="market", money=90, weather_override="Salju", mounted=True, horse_scene="market")
        Wildlife(life)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "save.json"; life.save(path)
            loaded = Life.load(path)
            self.assertEqual((loaded.money, loaded.scene, loaded.weather_override), (90, "market", "Salju"))
            self.assertEqual(len(loaded.animals), 11)


if __name__ == "__main__":
    unittest.main()
