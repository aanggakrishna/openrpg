"""Shared move definitions, usable by the headless online server."""
EMOJI={'normal':'⭐','fire':'🔥','water':'💧','grass':'🍃','electric':'⚡','ice':'❄️','ground':'🪨',
       'rock':'🪨','ghost':'👻','psychic':'🔮','poison':'☠️','flying':'🌪️','dark':'🌙','fairy':'✨','steel':'⚙️','bug':'🐛','dragon':'🐉','fighting':'🥊'}
VARIANTS={'wood':'🪵','branch':'🪵','leaf':'🍃','seed':'🌱','vine':'🌿','solar':'☀️','rain':'🌧️',
          'storm':'⛈️','thunder':'⚡','blizzard':'🌨️','snow':'❄️','bubble':'🫧','surf':'🌊','wave':'🌊',
          'swift':'⭐','meteor':'☄️','moon':'🌙','web':'🕸️','wind':'🌪️','sand':'🏜️','mud':'🟤','petal':'🌸'}

def skill(move,ultimate=False):
    typ=move['type']['name']; name=move['name'];power=move.get('power') or 50
    status=move.get('damage_class',{}).get('name')=='status'
    melee=move.get('damage_class',{}).get('name')=='physical' and any(w in name for w in ('punch','kick','tackle','scratch','bite','slash','headbutt','claw','chop'))
    area=any(w in name for w in ('quake','surf','storm','blizzard','discharge','explosion'))
    beam=any(w in name for w in ('beam','flame','breath','pump'))
    # Skill icon follows the move's actual type. This also keeps coverage moves
    # on dual-type Pokémon honest: a secondary-type move carries its own icon.
    emoji=EMOJI.get(typ,'💥')
    return {'name':name.replace('-',' ').title(),'type':typ,'power':min(140,power),'accuracy':move.get('accuracy') or 100,
            'emoji':emoji,'damage_class':move.get('damage_class',{}).get('name','special'),
            'style':'status' if status else 'area' if area else 'beam' if beam else 'melee' if melee else 'projectile',
            'range':150 if melee else 410 if area else 610 if beam else 750,
            'cooldown':12 if ultimate else round(1.4+power/65+(0.7 if area else 0),1),'ultimate':ultimate}

def fighter_loadout(moves):
    """Build the same Q/W/E/R controls for offline, online, and bot fighters."""
    if not moves:
        return [], None
    moves=list(moves[:3])
    while len(moves)<3:moves.append(moves[-1])
    q,w,e=(skill(move) for move in moves)
    # Preserve each Pokémon's real move name/type/emoji, while making the
    # combat roles readable and predictable across every battle mode.
    q.update(style='projectile',range=max(420,q['range']),cooldown=max(6.0,q['cooldown']),
             stun_chance=.42)
    w.update(style='melee',range=116,cooldown=max(1.7,min(3.2,w['cooldown'])))
    if e['style'] in ('melee','status'):e['style']='projectile'
    e.update(range=max(650,e['range']),cooldown=max(3.5,min(5.5,e['cooldown'])))
    ultimate=dict(e)
    ultimate.update(style='beam',range=1100,cooldown=12.0,ultimate=True,
                    power=min(150,max(100,int(ultimate['power']*1.25))),stun_chance=0)
    return [q,w,e],ultimate
