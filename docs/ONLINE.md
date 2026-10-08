# Online gym and co-op dungeons

## Start a server

The server uses Python's standard library and the bundled Pokédex database. It does not need Pygame, a display, downloaded sprites, or an API key.

```sh
python3 online_server.py --host 0.0.0.0 --port 8765 --join-code YOUR_ROOM_CODE
```

On the same computer, connect to `http://127.0.0.1:8765`. Friends use `http://YOUR_SERVER_IP:8765` and the same room code. Allow inbound TCP 8765 on the host/router. `GET /health` returns the server name and protocol version.

Alternatively:

```sh
export OPENRPG_JOIN_CODE=YOUR_ROOM_CODE
docker compose -f compose.online.yml up --build -d
```

The Docker volume `openrpg-online` stores accounts, collections, coins, team health, and dungeon unlocks. Back it up before moving servers. Native installations save this data in `.openrpg/server.sqlite3`; use `--database PATH` to change it.

Use an HTTPS reverse proxy for an internet-facing server: plain HTTP sends session credentials and chat unencrypted. This release is intended for a trusted friend group: the first connection imports a local save, so initial inventory/levels are trusted. It is not a cheat-resistant public economy. The server validates subsequent combat, ownership, payments, and unlocks.

## Join from the game

1. Load your profile and walk north from the home/farm clearing to **ONLINE GYM**.
2. Press **E**, enter the server URL, enter its optional room code, then **Connect**.
3. **Arrow keys** move. **E** interacts with the nearby center/exit. **Tab + Enter** or the mouse operates buttons.
4. **T** opens chat; Enter sends; Escape cancels typing. **B** opens the existing real terminal from the lobby. Escape returns to the online room. The terminal continues running while you explore.
5. Choose a player, then **PvP** or **Trade**. Invitations expire after 45 seconds; the recipient can accept or decline.
6. Walk east to the dungeon road. The road spans 3,200 world pixels and the camera follows you. Stand near a gate and press **E**.

### Profiles and trading

On the first connection, your owned Pokémon, levels, active team, and coins are copied to a new server profile. After that, online progress is authoritative on that server and **separate from offline progress**. Later offline captures or purchases do not automatically import. Connecting to another server creates a separate online profile.

Credentials are stored per local save-path and server URL in `.openrpg/online/`. Keep these files when moving your installation; never share them or commit them. Reconnecting restores the server collection. Switching a URL between an IP and hostname creates a separate local credential entry, so use a consistent address.

Trades can exchange two species, give a Pokémon for free, or sell one for coins. The recipient sees the species and price before accepting. A trade checks both collections and the buyer's balance again before committing. Duplicate species and giving away your final Pokémon without a replacement are rejected. Replaying an accepted offer cannot charge twice. Team membership adjusts if a traded Pokémon was active.

A Pokémon Center is available in the gym and every dungeon lobby. Select 1–3 active Pokémon, and heal the collection for **5 coins**. Health carries between online battles. The roster UI is paginated rather than loading every sprite.

## PvP

The server simulates movement, gravity, platforms, aimed projectiles, guard, cooldowns, health, and team switches. Clients send controls, not damage or victory claims.

| Control | Action |
|---|---|
| Left / Right | Move |
| Up | Jump onto platforms |
| A | Short-range punch |
| S / D | Species-specific moves from the bundled Pokédex |
| F | Ultimate at 100% energy |
| Left Shift | Guard |
| 1 / 2 / 3 | Switch active Pokémon |

A three-count introduction precedes a **60-second** round. Fainted Pokémon automatically switch to the next healthy team member. At time-out, the remaining normalized team health decides the winner; equal totals draw. PvP awards 30 coins and one level to the winning active team. Forfeit removes that player's team from combat. A disconnected player times out after 15 seconds.

Weather and arena are chosen for each match. Moves matching weather or terrain gain 15% power. Online combat shares the offline move definitions, but has its own authoritative network simulation and interface; it is not an exact port of every offline animation or capture mechanic. Opponent-owned Pokémon cannot be captured.

## Co-op dungeon progression

| Tier | Enemy levels | Boss |
|---|---|---|
| 1 | 1–3 → 4–6 → 7–9 | 10 |
| 2 | 11–13 → 14–16 → 17–19 | 20 |
| … | Same pattern in increments of 10 | … |
| 10 | 91–93 → 94–96 → 97–99 | 100 |

Each run contains **5 low-level enemies, 3 middle-level enemies, 2 high-level enemies, then 1 boss**. Bosses come from strong species, receive 2.5× health and boosted damage, and are always at the tier's maximum level.

Players explicitly select **Ready** in the lobby. **Start raid** includes up to four ready players in that room; players who are not ready stay outside. Each stage has a 180-second limit, a fresh three-count introduction, and shared enemies. Health carries between stages. Clear the boss to unlock the next tier, earn `50 × tier` coins, and gain two levels for the participating active team. Leaving before victory grants no reward or unlock. Tier 10 is the final tier.

## Loading and resource use

- All **1,025** bundled species are assigned to the 16 offline habitat pools. Encounters rotate; all species are not instantiated simultaneously.
- Only the current habitat's encounters and trainer are spawned (8–13 encounters). Entering another habitat replaces them; revisiting rerolls its encounters.
- Terrain chunks are generated on demand. Decoded Pokémon media caches are trimmed during exploration; downloaded media on disk is never deleted.
- Online clients receive only their current room and current match. Online sprite surfaces are capped at 40 entries.
- HTTP I/O runs on a background worker. Server loss leaves an error message and the **Leave** button available.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_online*.py' -v
```

These checks cover local HTTP clients, trade replay protection, chat, PvP damage, melee range, gravity, dungeon waves, strongest-boss health, unlocks, and UI/area loading. Internet latency, long-duration load, reverse-proxy configuration, and your actual host still need a two-machine play session after deployment.
