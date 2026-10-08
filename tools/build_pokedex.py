"""Download official PokéAPI CSV tables once and build a local SQLite database.
Existing assets and API caches are never removed. Re-running resumes downloads.
"""
import csv
import sqlite3
from contextlib import closing
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '.openrpg' / 'database'
TABLES = ('pokemon', 'pokemon_species', 'pokemon_types', 'types', 'pokemon_stats', 'stats',
          'pokemon_species_flavor_text', 'moves', 'pokemon_moves', 'pokemon_evolution', 'type_efficacy', 'abilities', 'pokemon_abilities')

def fetch(table):
    path = DEST / (table + '.csv')
    if not path.exists():
        url = f'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/{table}.csv'
        with urllib.request.urlopen(url, timeout=90) as response:
            payload = response.read()
        tmp = path.with_suffix('.download')
        tmp.write_bytes(payload)
        tmp.replace(path)
    return table

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as workers:
        for table in workers.map(fetch, TABLES):
            print('Downloaded:', table, flush=True)
    path = DEST / 'pokedex.build.sqlite3'
    with closing(sqlite3.connect(path)) as db:
        for table in TABLES:
            db.execute(f'DROP TABLE IF EXISTS {table}')
            with (DEST / (table + '.csv')).open() as source:
                rows = csv.reader(source)
                columns = next(rows)
                db.execute(f'CREATE TABLE {table} (' + ','.join('"'+c+'" TEXT' for c in columns) + ')')
                db.executemany(f'INSERT INTO {table} VALUES (' + ','.join('?' for _ in columns) + ')', rows)
            if 'pokemon_id' in columns:
                db.execute(f'CREATE INDEX idx_{table}_pokemon ON {table}(pokemon_id)')
            if 'species_id' in columns:
                db.execute(f'CREATE INDEX idx_{table}_species ON {table}(species_id)')
            if 'id' in columns:
                db.execute(f'CREATE INDEX idx_{table}_id ON {table}(id)')
        db.commit()
        print('Species:', db.execute('SELECT count(*) FROM pokemon_species').fetchone()[0], flush=True)
        print('Moves:', db.execute('SELECT count(*) FROM moves').fetchone()[0], flush=True)
    path.replace(DEST / 'pokedex.sqlite3')
if __name__ == '__main__':
    main()
