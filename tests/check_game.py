"""Integration check: actual art, combat, riding, and shell survival after death.

Run from the repository: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
    .venv/bin/python tests/check_game.py
Never touches .openrpg/save.json or submits a request to an AI provider.
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pygame as pg
from main import Game, ROOT
from state import Life
from wildlife import Wildlife


g = Game(ROOT / "artifacts/expanded-shell", ROOT / "artifacts/expanded-save.json")
try:
    g.life = Life()
    g.wildlife = Wildlife(g.life)
    g.begin(); g.update(0)
    for scene in ("outdoors", "forest", "market", "house", "bedroom"):
        g.life.scene = scene; g.life.x = 650; g.life.y = 460 if scene == "forest" else 610
        g.draw(); pg.image.save(g.canvas, ROOT / f"artifacts/v2-{scene}.png")
    g.life.scene = "forest"; g.life.minutes = 20 * 60
    g.life.weather_override = "Salju"; g.life.advance_time(0)
    g.wildlife.update(.1, g.obstacles("forest"), player_active=False)
    g.draw(); pg.image.save(g.canvas, ROOT / "artifacts/v2-night-snow.png")
    g.life.scene = "outdoors"; g.life.minutes = 8 * 60
    g.life.weather_override = "Cerah"; g.life.advance_time(0)
    g.life.x, g.life.y = g.life.horse_x, g.life.horse_y
    g.toggle_mount(); assert g.life.mounted
    g.draw(); pg.image.save(g.canvas, ROOT / "artifacts/v2-horse.png")
    g.life.x = 1248; g.life.y = 410; g.check_edges(); assert g.life.scene == "market"
    g.life.x = 31; g.check_edges(); assert g.life.scene == "outdoors"
    g.toggle_mount(); assert not g.life.mounted
    for index in range(3):
        for direction in ("down", "up", "left", "right"):
            frames = []
            for frame in (0, 7, 14, 21):
                s = pg.Surface((160, 160), pg.SRCALPHA)
                g.art.character(s, 80, 130, index, 2, frame, True, direction)
                frames.append(pg.image.tobytes(s, "RGBA"))
            assert len(set(frames)) >= 3, (index, direction)
    print("Four-direction animation verified for all three characters")
    g.mode = "inventory"; g.draw(); pg.image.save(g.canvas, ROOT / "artifacts/v2-inventory.png")
    g.life.scene = "market"; g.mode = "shop"; g.shop_npc = "Budi"
    g.draw(); pg.image.save(g.canvas, ROOT / "artifacts/v2-shop.png")
    g.life.money = 300; g.trade("Busur", True); g.trade("Panah", True, 5); g.life.equip("Busur")
    g.life.scene = "forest"; g.life.x = 650; g.life.y = 410; g.mode = "game"; g.facing = "right"
    g.attack(); assert g.life.bag["Panah"] == 4 and len(g.projectiles) == 1
    g.update_arrows(.1)
    g.life.scene = "bedroom"; g.life.x = 899; g.life.y = 369; g.mode = "game"; g.interact()
    g.terminal.send(b"printf '\\nSESSION_OK\\n'\r")
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        g.update(.016); time.sleep(.03)
        if "SESSION_OK" in [x.strip() for x in g.terminal.screen.display]:
            break
    else:
        raise AssertionError("Shell failed to start")
    pid = g.terminal.process.pid
    proof = ROOT / "artifacts/expanded-shell/alive-after-death.txt"
    proof.unlink(missing_ok=True)
    g.terminal.send(b"(sleep 1; printf 'still-running' > alive-after-death.txt) &\r")
    g.life.health = 0; g.update(.016)
    assert g.life.scene == "bedroom" and g.life.health == 100
    assert g.terminal.running and g.terminal.process.pid == pid
    deadline = time.monotonic() + 5
    while not proof.exists() and time.monotonic() < deadline:
        g.update(.016); time.sleep(.05)
    assert proof.read_text() == "still-running"
    print("Death + bed respawn preserved actual shell PID and background job")
    g.life.scene = "forest"; g.life.health = 100; g.life.bag["Tombak"] = 1; g.life.equip("Tombak")
    g.life.x = 400; g.life.y = 410; g.facing = "right"; g.attack_cooldown = 0
    a = g.wildlife.spawn("Kelinci", 500); a.update(x=440, y=410); g.life.animals = [a]
    previous = g.life.bag["Daging"]; g.attack()
    assert a["hp"] == 0 and g.life.bag["Daging"] == previous + 1
    print("Ammo, hunting loot, trade, mounting and area transitions verified")
finally:
    g.terminal.close()
    pg.quit()
