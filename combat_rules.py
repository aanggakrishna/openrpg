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
    emoji=next((v for k,v in VARIANTS.items() if k in name),EMOJI.get(typ,'💥'))
    return {'name':name.replace('-',' ').title(),'type':typ,'power':min(140,power),'accuracy':move.get('accuracy') or 100,
            'emoji':emoji,'style':'status' if status else 'area' if area else 'beam' if beam else 'melee' if melee else 'projectile',
            'range':150 if melee else 410 if area else 610 if beam else 750,
            'cooldown':12 if ultimate else round(1.4+power/65+(0.7 if area else 0),1),'ultimate':ultimate}

