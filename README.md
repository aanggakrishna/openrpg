# OpenRPG

**A 2D life RPG built with Python and Pygame.** Explore a home, garden, farm, forest, market, and Pokémon sanctuary in an 8-bit pixel-art world. Take care of your character, collect Pokémon, fight real-time battles, and open a real shell terminal inside the game.

[Getting started](#getting-started) · [Controls](#controls) · [Activities](#activities) · [Real terminal](#real-terminal) · [Asset credits](assets/CREDITS.md) · [License](#license)

## Getting started

**Requirements:** Python 3.10+ and macOS or Linux. Pokémon catalog entries and images are fetched from PokéAPI when first needed and stored in a local cache.

On macOS, double-click `run.command`. Or launch from a terminal:

```sh
git clone https://github.com/aanggakrishna/openrpg.git
cd openrpg
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Choose Nara, Bima, or Ayu, then press Enter. Progress is saved automatically to `.openrpg/save.json`; existing saves remain supported.

## Features at a glance

- **Life simulation:** eat, drink, rest, cook, garden, raise farm animals, fish, and look after your health.
- **An explorable world:** home, farm, forest, market, coast, mountains, and a **5,120 × 4,800 pixel** sanctuary with 12 habitats.
- **Wildlife and horseback riding:** animals move and interact with their surroundings; buy equipment, hunt, and ride a horse.
- **Pokémon:** Pokédex powered by PokéAPI, roaming wild Pokémon, up to three active party members, a Pokémon Center, evolution, and battles against AI and trainers.
- **Real-time arcade battles:** multi-platform arenas, jumping, guarding, attacks, type moves, ultimates, healing items, and Poké Balls with a chance to catch.
- **Real terminal:** run a shell and OpenCode from the bedroom PC. The same terminal session can also be opened in Terminal.app and keeps running while you explore the game.
- **8-bit retro style:** pixel-art world, pixel font, arcade HUD, animations, and move effects.

## Assets

The game uses original PNG tilesets and sprites from Kenney:

- [Tiny Town](https://kenney.nl/assets/tiny-town): grass, paths, houses, trees, and fences.
- [Tiny Farm](https://kenney.nl/assets/tiny-farm): crops, farm animals, farming, and farmer characters.
- [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon): Ayu character sprite.
- [Roguelike/RPG Pack](https://kenney.nl/assets/roguelike-rpg-pack): shoreline, floors, kitchen, beds, tables, chairs, and decor.

The Kenney packs are licensed **CC0**. Four-direction walking animations come from [Ninja Adventure](https://pixel-boy.itch.io/ninja-adventure-asset-pack) by Pixel-Boy and AAA, also CC0. It also provides NPCs, detailed trees, lions, horses, chickens, boars, hyenas, and monkeys. The elephant and rabbit spritesheets were generated for this project; each has four directions and four walking poses. See [`assets/CREDITS.md`](assets/CREDITS.md) for credits and included asset licenses.

## Controls

| Key | Action |
| --- | --- |
| WASD / arrow keys | Move |
| E | Interact; choose battle or Pokédex information when meeting a Pokémon |
| I | Inventory |
| H | Use medicine |
| R | Mount or dismount the horse |
| T | Advance time by one hour |
| C | Open weather options |
| B | Open the shared terminal view |
| P | Open the Pokédex |
| M | Open the sanctuary map; use the mouse wheel or +/- to zoom |
| N | Open the Pokémon Center |
| Space | Attack with a weapon or start a battle near a Pokémon |
| F1 / Esc | Help / menu |

## Activities

- **Home and bedroom:** cook and eat in the kitchen; restore your needs in the living room; sleep to restore health and energy; use the PC to open the terminal.
- **Garden and farm:** plant, water, and harvest vegetables; feed chickens to collect eggs. Sell your harvest at the market.
- **Fishing:** cast a line in the pond, wait for a bite, then press E to reel it in.
- **Forest:** explore wildlife habitats. Predators hunt at certain times; animals can flee, fight back, and respawn.
- **Pokémon sanctuary:** press M or use the portal in the yard. The 5,120 × 4,800 map contains 12 connected habitats. Wild Pokémon roam and hide; rarer species appear farther from the entrance.
- **Pokémon encounters:** approach a Pokémon and press E to choose a battle or view Pokédex information. Downloaded catalog data and sprites are cached in `.openrpg/pokedex`.
- **Pokémon Center:** inspect and heal Pokémon, choose up to three active party members, and evolve Pokémon that meet the requirements.
- **Battles:** move with the arrow keys; press Up to jump or climb, Shift to guard, A for a close-range punch, S/D for moves, F for an ultimate, 1–3 to switch Pokémon, and O to throw a Poké Ball. Battles have a 60-second limit. Trainers also challenge you on the road and in the arena.
- **Market:** Sari sells food and medicine, Budi sells weapons, and Danu buys crops, farm goods, fish, and hunting loot. The market is open from 06:00 to 22:00.

### Hunting and health

You start with 150 coins and five Poké Balls. Sari sells extra Poké Balls for 12 coins each. A spear costs 80 coins; a bow costs 160, and arrows cost 3 coins each. Buy weapons from Budi, then equip the spear with 1 or the bow with 2. The spear is a close-range weapon; the bow uses one arrow per shot. Hunting animals adds meat and hides to your inventory. Predators do not yield hunting loot.

Lions hunt at **06:00–10:00 and 16:00–20:00**; hyenas hunt from **18:00–06:00**. Elephants and wild boars can fight back. Animals respawn after 100 seconds of play time.

Your needs decrease while playing, using the PC, opening the inventory, or shopping. Low energy slows movement. Hunger or thirst reaching zero reduces health; wildlife attacks also cause damage. Medicine restores 45 HP, and sleep restores health. When HP runs out, you wake up in bed at full health; your inventory and money are preserved. **Character death does not restart the terminal session or AI process.**

### Time and weather

The in-game clock and day are shown at the top of the screen. One real-time second equals 1.3 in-game minutes. Press T to advance exactly 60 minutes, including day changes and crop growth. Lighting changes through morning, afternoon, and night. Weather can change automatically every three in-game hours. Press C to choose clear, cloudy, rain, snow, or automatic weather. Snow slows movement outdoors.

Skipping an hour immediately updates wildlife schedules; animal movement during the skipped hour is not simulated step by step. The pause, help, and character selection screens pause the world; the terminal keeps running.

## Real terminal

Press B anywhere to open the terminal, or use the PC in the bedroom. The terminal runs your local shell. Type `opencode` to start OpenCode, or use `opencode run` as you normally would. OpenCode must be installed and authenticated on your computer.

The PC opens a **local interactive login shell** using `$SHELL`—usually zsh on macOS or bash on Linux. It runs in a controlling pseudo-terminal, supporting job control and Ctrl+C. Keyboard input, paste, commands, files, and processes are real.

Example commands:

```sh
pwd
ls
python3 --version
git status
opencode
```

OpenCode does not start automatically. Type `opencode` in the terminal to use it with your existing configuration and login. If it is not found on PATH, try `~/.opencode/bin/opencode`.

The default working directory is `computer-workspace/` inside the game folder. It is created the first time you use the PC. Choose another project directory or shell:

```sh
.venv/bin/python main.py --project /path/to/project
.venv/bin/python main.py --shell /bin/bash
```

The shell runs as your user and can perform the same operations as a regular terminal. Its starting directory is not a sandbox; `cd` can move to other directories.

| PC control | Action |
| --- | --- |
| Type + Enter | Run a command |
| Tab / arrow keys | Shell and CLI completion / navigation |
| Ctrl+C | Stop the foreground process |
| Ctrl/Cmd+V | Paste from the clipboard |
| Mouse wheel / Shift+PageUp / Shift+PageDown | Scroll terminal history |
| F10 | Send Escape to the shell or CLI |
| Esc / Leave PC button | Return to the game without closing the shell |
| R after the shell exits | Start a new shell |

You can leave the PC to garden or fish while a command runs, then return to the same session. This works while the game remains open. Quitting the game saves progress and closes the shell and its child processes. Commands detached with `nohup` or `disown` follow normal shell behavior.

Terminal history holds up to 2,000 lines. New output or input returns the view to the bottom. CLI applications using the alternate screen can return to the shell view when they exit.

## Platform and notes

Locations include the yard, forest, Pokémon sanctuary, coast, mountains, market, home, and bedroom. Pokédex data is fetched from PokéAPI and requires an internet connection for items not yet cached. The embedded terminal supports macOS and Linux and is keyboard-controlled.

## Retro 8-bit theme

The game uses the VT323 pixel font, angular panels, a navy/mint/gold palette, segmented HP bars, consistently sized item icons, and pixel-art battle backgrounds. Shared UI components are in `retro.py`. Terminal output uses a Unicode monospace font for readability. Controls and save format remain unchanged.

VT323 by Peter Hull is bundled from the Google Fonts repository (`ofl/vt323`) under the SIL Open Font License; see `assets/fonts/OFL.txt`.

## Regression checks

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m unittest discover -s tests
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python tests/check_game.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python tests/check_retro.py
```

The retro UI check uses mock Pokémon data and requires no network. Tests use isolated save files and shell sessions.

## License

Original OpenRPG code is released under the [MIT License](LICENSE). Third-party assets retain their respective licenses; see the [asset credits and license list](assets/CREDITS.md) and the license files included with each pack. The MIT License for OpenRPG code does not cover trademarks or Pokémon data and artwork.

## Adventure flow update

The main menu provides **New Game**, **Load Game**, **Save Game**, and **Settings**. Create an adventurer with a name, gender and animated appearance, then receive a random basic Pokémon at level 3–5. Four additional profile slots are available alongside the original save. Existing downloads and the original save are retained.

Menus support mouse input or **arrow keys + Enter**; **Esc** goes back. In the Pokédex and global map, **Tab** switches between browsing/panning and button navigation. **B** opens the live terminal; keys are passed to the shell while it is focused.

- **J:** daily quests, manual reward claims, daily completion bonus and ticket gacha. Completed unclaimed rewards remain available after a day change. Gacha pools are shown in the UI; duplicates award coins.
- **Pokémon Center:** browse a paginated collection, select a Pokémon and choose one of three active slots. Healing the active team costs 5–20 coins depending on missing HP (free when already healthy). Sleeping at home can restore the active team for free.
- Carry up to **10 empty Poké Balls**, with **3 active Pokémon** and a collection that is no longer limited to six species. Duplicate species share their collection entry.
- **Combat:** arrows move/jump/drop, **A** strikes at close range, **S/D** use learnset-based skills, **F** uses an ultimate, **Shift** guards and **1/2/3** switches the active fighter. Skill cards show names and individual cooldowns. Attacks travel toward the target's position and can miss. Guarding uses a separate guard meter.
- Wild Pokémon and trainers have a **30% chance per encounter** to approach and offer a battle, with a cooldown and accept/decline choice. Menus and the terminal are safe from interruptions.
- Settings include language, music/effect/cry volumes and reduced flashes.

### Local Pokémon database

Build the local database from official PokéAPI CSV data before playing the updated fighter mode:

```sh
.venv/bin/python tools/build_pokedex.py
```

Optionally download all standard species sprites and unmodified cries for offline use:

```sh
.venv/bin/python tools/cache_pokemon_media.py
```

Both commands resume existing downloads. Database files live in `.openrpg/database/`; media remain in `.openrpg/pokedex/`; new profiles are in `.openrpg/profiles/`. The original save remains `.openrpg/save.json`. CSV metadata are queried on demand and map artwork is cached by area, so downloading the collection does not load all media into memory.

Validation:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test*.py'
```

Evolution at a Pokémon Center costs 10 coins and currently supports ordinary level evolutions. Item, trade, friendship and other special evolution conditions are retained in the source database but are not automatically treated as level evolutions.
