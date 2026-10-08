"""Read-only, on-demand access to the official local PokéAPI dataset."""
import sqlite3
from contextlib import closing
from pathlib import Path
from functools import lru_cache
PATH = Path(__file__).resolve().parent / '.openrpg/database/pokedex.sqlite3'

@lru_cache(maxsize=256)
def detail(ident):
    if not PATH.exists():
        return None
    with closing(sqlite3.connect(f"file:{PATH}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        p = db.execute('SELECT * FROM pokemon WHERE id=?', (str(ident),)).fetchone()
        if p is None:
            return None
        types = [{'slot':int(r['slot']), 'type':{'name':r['identifier']}} for r in db.execute(
            'SELECT pt.slot,t.identifier FROM pokemon_types pt JOIN types t ON t.id=pt.type_id WHERE pt.pokemon_id=? ORDER BY pt.slot', (str(ident),))]
        stats = [{'base_stat':int(r['base_stat']), 'stat':{'name':r['identifier']}} for r in db.execute(
            'SELECT ps.base_stat,s.identifier FROM pokemon_stats ps JOIN stats s ON s.id=ps.stat_id WHERE ps.pokemon_id=?', (str(ident),))]
        moves = [{'move': {'name':r[0]}} for r in db.execute(
            'SELECT DISTINCT m.identifier FROM pokemon_moves pm JOIN moves m ON m.id=pm.move_id WHERE pm.pokemon_id=?', (str(ident),))]
        return {'id':int(p['id']), 'name':p['identifier'], 'height':int(p['height']), 'weight':int(p['weight']),
                'types':types, 'stats':stats, 'moves':moves,
                'abilities':[{'ability':{'name':r[0]},'is_hidden':r[1]=='1'} for r in db.execute('SELECT a.identifier,pa.is_hidden FROM pokemon_abilities pa JOIN abilities a ON a.id=pa.ability_id WHERE pa.pokemon_id=?',(str(ident),))],
                'sprites':{'front_default':f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{ident}.png', 'other':{'showdown':{'front_default':f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/{ident}.gif'}}},
                'cries':{'latest':f'https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/{ident}.ogg'},
                'species':{'name':p['identifier'], 'url':f'https://pokeapi.co/api/v2/pokemon-species/{p["species_id"]}/'}}

@lru_cache(maxsize=512)
def move(name):
    if not PATH.exists():
        return None
    with closing(sqlite3.connect(f"file:{PATH}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        r = db.execute('SELECT m.*,t.identifier type_name FROM moves m JOIN types t ON t.id=m.type_id WHERE m.identifier=?', (name,)).fetchone()
        if not r:
            return None
        return {'name':name, 'power':int(r['power'] or 0), 'accuracy':int(r['accuracy'] or 100),
                'type':{'name':r['type_name']}, 'damage_class':{'name':{1:'status',2:'physical',3:'special'}[int(r['damage_class_id'])]}}

@lru_cache(maxsize=256)
def loadout(ident):
    """Select damaging moves from the actual learnset, favoring native types."""
    p = detail(ident)
    if not p:
        return []
    own = {t['type']['name'] for t in p['types']}
    moves = [move(e['move']['name']) for e in p['moves']]
    all_moves = [m for m in moves if m]
    moves = [m for m in all_moves if m['power'] > 0]
    if not moves:
        moves = sorted(all_moves,key=lambda m:(m['damage_class']['name']!='status',m['name'] in ('transform','sketch','counter','mirror-coat','cosmic-power')),reverse=True)
    moves.sort(key=lambda m: (m['type']['name'] in own, -abs(m['power']-60)), reverse=True)
    if not moves:
        return []
    first = moves[0]
    second = next((m for m in moves[1:] if m['type'] != first['type']), moves[min(1,len(moves)-1)])
    ultimate = max(moves, key=lambda m: (m['type']['name'] in own, min(150,m['power'])))
    return [first, second, ultimate]

@lru_cache(maxsize=256)
def species(ident):
    if not PATH.exists():return None
    with closing(sqlite3.connect(f"file:{PATH}?mode=ro", uri=True)) as db:
        db.row_factory=sqlite3.Row
        r=db.execute('SELECT * FROM pokemon_species WHERE id=?',(str(ident),)).fetchone()
        if not r:return None
        flavor=[]
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='pokemon_species_flavor_text'").fetchone():
            flavor=[{'flavor_text':row[0],'language':{'name':'en'}} for row in db.execute("SELECT flavor_text FROM pokemon_species_flavor_text WHERE species_id=? AND language_id='9' ORDER BY CAST(version_id AS INTEGER) DESC LIMIT 2",(str(ident),))]
        return {'id':int(r['id']),'name':r['identifier'],'capture_rate':int(r['capture_rate']), 'flavor_text_entries':flavor,
                'habitat':{'name':{'1':'cave','2':'forest','3':'grassland','4':'mountain','5':'rare','6':'rough-terrain','7':'sea','8':'urban','9':'waters-edge'}.get(r['habitat_id'],'unknown')},
                'color':{'name':{'1':'black','2':'blue','3':'brown','4':'gray','5':'green','6':'pink','7':'purple','8':'red','9':'white','10':'yellow'}.get(r['color_id'],'unknown')},
                'is_legendary':r['is_legendary']=='1','is_mythical':r['is_mythical']=='1',
                'evolution_chain':{'url':f"https://pokeapi.co/api/v2/evolution-chain/{r['evolution_chain_id']}/"}}

@lru_cache(maxsize=256)
def evolution(chain_id):
    if not PATH.exists():return None
    with closing(sqlite3.connect(f"file:{PATH}?mode=ro", uri=True)) as db:
        db.row_factory=sqlite3.Row
        rows=list(db.execute('SELECT * FROM pokemon_species WHERE evolution_chain_id=?',(str(chain_id),)))
        if not rows:return None
        def branch(row):
            conditions=[]
            for c in db.execute('SELECT * FROM pokemon_evolution WHERE evolved_species_id=?',(row['id'],)):
                # Only expose automatic level evolutions when no special condition is required.
                special=any(c[key] not in ('','0') for key in ('trigger_item_id','held_item_id','minimum_happiness','minimum_beauty','minimum_affection','location_id','time_of_day','known_move_id','known_move_type_id','party_species_id','party_type_id','trade_species_id','condition_expression','minimum_steps','minimum_damage_taken','minimum_move_count','gender_id','relative_physical_stats','needs_overworld_rain','turn_upside_down','needs_multiplayer','near_special_rock','region_id','nature_bitmask','required_pokemon_form_id'))
                if c['evolution_trigger_id']=='1' and c['minimum_level'] and not special:
                    conditions.append({'trigger':{'name':'level-up'},'min_level':int(c['minimum_level'])})
            return {'species':{'name':row['identifier'],'url':f"https://pokeapi.co/api/v2/pokemon-species/{row['id']}/"},
                    'evolution_details':conditions,'evolves_to':[branch(child) for child in rows if child['evolves_from_species_id']==row['id']]}
        return {'id':chain_id,'chain':branch(next((r for r in rows if not r['evolves_from_species_id']),rows[0]))}

@lru_cache(maxsize=512)
def effectiveness(attack_type,defense_types):
    if not PATH.exists():return 1.0
    with closing(sqlite3.connect(f"file:{PATH}?mode=ro", uri=True)) as db:
        multiplier=1.0
        for typ in defense_types:
            r=db.execute('SELECT te.damage_factor FROM type_efficacy te JOIN types a ON a.id=te.damage_type_id JOIN types d ON d.id=te.target_type_id WHERE a.identifier=? AND d.identifier=?',(attack_type,typ)).fetchone()
            if r:multiplier*=int(r[0])/100
        return multiplier

def catalog():
    if not PATH.exists():return []
    with closing(sqlite3.connect(f'file:{PATH}?mode=ro',uri=True)) as db:
        return [{'id':int(row[0]),'name':row[1]} for row in db.execute('SELECT id,identifier FROM pokemon_species ORDER BY CAST(id AS INTEGER)')]
