"""Asynchronous browser entry point for the unmodified OpenRPG game engine."""
from __future__ import annotations

import asyncio
import json
import sys

import pygame as pg

from game_engine import Game, ROOT
import browser_media


def update_browser_controls(game: Game) -> None:
    """Bridge virtual keyboard input through the DOM in Pygbag's event loop."""
    try:
        from platform import window

        document = window.document
        body = document.body
        name_entry = bool(game.mode == "setup" and game.wizard.get("step") == 0)
        if name_entry:
            field = document.getElementById("mobile-name-input")
            value = field.value if field is not None else ""
            game.wizard["name"] = "".join(
                char for char in str(value or "") if char.isprintable()
            )[:18]

        battle = game.battle if game.mode == "battle" else None
        if battle:
            blocked = bool(
                battle.get("result")
                or battle.get("intro")
                or battle.get("boss_intro")
                or battle.get("capture")
                or battle.get("ultimate_cutin")
            )
            battle_state = {
                "locked": blocked,
                "basicCooldown": round(max(0.0, float(battle.get("player_cooldown", 0.0))), 2),
                "skillCooldown": round(max(0.0, float(battle.get("type_cooldown", 0.0))), 2),
                "ultimateMeter": round(max(0.0, min(100.0, float(battle.get("super_meter", 0.0)))), 1),
                "ultimateReady": bool(not blocked and battle.get("super_meter", 0.0) >= 100),
            }
        else:
            battle_state = None
        body.setAttribute(
            "data-openrpg-mobile-state",
            json.dumps({
                "mode": game.mode,
                "battle": battle_state,
                "nameInput": name_entry,
                "name": game.wizard.get("name", "") if name_entry else "",
            }),
        )

        if name_entry and body.getAttribute("data-openrpg-mobile-name-done") == "true":
            body.setAttribute("data-openrpg-mobile-name-done", "false")
            game.next_setup()
    except Exception as error:
        print("OpenRPG browser input bridge:", str(error))


async def main() -> None:
    game = Game(ROOT / "computer-workspace")
    game.begin()
    clock = pg.time.Clock()
    try:
        while game.running:
            dt = min(0.05, clock.tick(60) / 1000)
            for event in pg.event.get():
                game.handle(event)
            update_browser_controls(game)
            game.update(dt)
            game.draw()
            await browser_media.pump()
            await asyncio.sleep(0)
    finally:
        game.save_current()
        game.terminal.close()
        pg.quit()


asyncio.run(main())
