"""Export compact species data for the static browser game build."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pokemon_db

DEST = ROOT / "public" / "data" / "pokedex.json"


def main():
    rows = []
    for entry in pokemon_db.catalog():
        ident = entry["id"]
        detail = pokemon_db.detail(ident)
        if not detail:
            continue
        stats = {item["stat"]["name"]: item["base_stat"] for item in detail["stats"]}
        moves = []
        for move in pokemon_db.loadout(ident):
            if move:
                moves.append({
                    "name": move["name"].replace("-", " ").title(),
                    "type": move["type"]["name"],
                    "power": move["power"],
                    "accuracy": move["accuracy"],
                })
        rows.append({
            "id": ident,
            "name": detail["name"].replace("-", " ").title(),
            "types": [item["type"]["name"] for item in detail["types"]],
            "stats": stats,
            "moves": moves,
        })
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    print(f"Exported {len(rows)} species to {DEST} ({DEST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
