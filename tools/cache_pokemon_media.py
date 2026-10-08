"""Resumable downloads of official Pokémon front sprites and unmodified cries."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.request import urlopen
import sqlite3
from contextlib import closing
import time
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.openrpg/pokedex'

def download(job):
    ident,kind=job
    path=CACHE/f'{ident}{"-cry.ogg" if kind=="cry" else ".png"}'
    if path.exists():return 'cached'
    url=(f'https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/{ident}.ogg' if kind=='cry' else f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{ident}.png')
    for attempt in range(3):
        try:
            with urlopen(url,timeout=20) as response:data=response.read()
            # Do not overwrite a file produced by the game while downloading.
            try:
                with path.open('xb') as output:output.write(data)
            except FileExistsError:pass
            return 'downloaded'
        except Exception:
            time.sleep(.3*(attempt+1))
    return f'missing:{ident}:{kind}'

def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(ROOT/'.openrpg/database/pokedex.sqlite3')) as db:
        ids=[int(r[0]) for r in db.execute('SELECT id FROM pokemon_species')]
    jobs=[(i,k) for i in ids for k in ('sprite','cry')]
    counts={};missing=[]
    with ThreadPoolExecutor(max_workers=8) as workers:
        for n,result in enumerate(workers.map(download,jobs),1):
            counts[result]=counts.get(result,0)+1
            if result.startswith('missing:'):missing.append(result)
            if n%100==0:print(n,'/',len(jobs),flush=True)
    (CACHE/'media-download-report.txt').write_text(str(counts))
    print('COMPLETE',len(ids),'species;',len(missing),'unavailable files',flush=True)
if __name__=='__main__':main()
