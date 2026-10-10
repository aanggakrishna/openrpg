# Asset credits

Downloaded from the creator's official website on 2026-10-07.

| Pack | Creator | License | Source | Used for |
| --- | --- | --- | --- | --- |
| Tiny Town 1.1 | Kenney | CC0 1.0 | https://kenney.nl/assets/tiny-town | Grass, paths, houses, trees, fences |
| Tiny Farm 1.0 | Kenney | CC0 1.0 | https://kenney.nl/assets/tiny-farm | Crops, farm, animals, farmer characters, tools |
| Tiny Dungeon 1.0 | Kenney | CC0 1.0 | https://kenney.nl/assets/tiny-dungeon | Ayu character sprite |
| Roguelike/RPG Pack | Kenney, with help from Lynn Evers | CC0 1.0 | https://kenney.nl/assets/roguelike-rpg-pack | Shoreline, floors, kitchen, beds, tables, chairs, decor |

Original license files are included in each pack's directory. CC0 permits personal and commercial use without requiring attribution. Character names and gameplay are specific to OpenRPG. Game UI and the PC monitor are drawn by the game. Current animated characters use Ninja Adventure, below; Kenney character sprites were used in the first version.

## Animated expansion (2026-10-07)

- **Ninja Adventure**, by Pixel-Boy and AAA: https://pixel-boy.itch.io/ninja-adventure-asset-pack — CC0 1.0. Original license is included at `ninja-adventure/Ninja Adventure - Asset Pack/LICENSE.txt`. The new trainer selector uses the pack's human adventurer/villager sprites (Boy, Hunter, Woman, Villager, Old Man, Samurai, Princess and Cavegirl); ninja sprites are not offered as playable choices. The pack also supplies detailed trees and forest props, lions, horses, chickens, boars, hyenas, and monkeys. Animal sheets have directional poses; player walking uses separate animated frames.
- **Gajah and kelinci**: original project sprite sheets generated with ImageGen, saved as `generated/elephant.png` and `generated/rabbit.png`. Each sheet has four directions and four walking poses. These are generated assets, separate from the CC0 third-party packs above.

- **Pokémon names, data, and artwork**: supplied through the community PokéAPI, https://pokeapi.co/. Pokémon is a trademark of Nintendo, Creatures Inc., and GAME FREAK inc. Data and artwork are cached locally after they are accessed; downloaded artwork is not redistributed as original project art.

## Adventure flow and local Pokédex (2026-10-08)

- Additional selectable animated characters (NinjaBlue, NinjaGreen, Samurai, Princess, Cavegirl and EggGirl) reuse the bundled **Ninja Adventure** pack by Pixel-Boy and AAA, CC0: https://pixel-boy.itch.io/ninja-adventure-asset-pack.
- The local SQLite database is built from official **PokéAPI** CSV tables: https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv. Species, stats, types, abilities, evolution conditions, descriptions, learnsets, move power and accuracy come from these tables. Fighter cooldowns, ranges and ultimate variants are OpenRPG game rules, not official Pokémon move properties.
- The 1,025 standard Pokémon PNG sprites in `pokemon-sprites/` were sourced from the PokeAPI sprites repository (https://github.com/PokeAPI/sprites); its `LICENCE.txt` is included alongside them. That notice states the repository is distributed under CC0 while also identifying Pokémon image contents as © The Pokémon Company and disclaiming clearance of third-party rights. Pokémon trademarks and underlying rights are not covered by OpenRPG's MIT license.
- Additional Pokémon sprite and cry downloads use https://github.com/PokeAPI/sprites and https://github.com/PokeAPI/cries. Cry files are stored and played without filtering, pitch changes or retro conversion. Volume can be adjusted in Settings.
