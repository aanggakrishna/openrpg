"""Assemble FireRed metatiles with their real palettes, layers and flip bits.

Input is the local pret/pokefirered study export. No ROM or network required.
Generated PNGs are runtime assets; the game never needs this source export.
"""
from pathlib import Path
import json
import struct
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/firered-rev1-assets'
DEST = ROOT / 'assets/gba/environment'

def palette(path):
    return [tuple(map(int, line.split())) for line in path.read_text().splitlines()[3:] if line.strip()]

class Tileset:
    def __init__(self, primary, secondary):
        self.primary = SOURCE / 'data/tilesets/primary' / primary
        self.secondary = SOURCE / 'data/tilesets/secondary' / secondary
        self.sheets = [Image.open(p / 'tiles.png') for p in (self.primary, self.secondary)]
        self.pals = [palette((self.primary if i < 7 else self.secondary) / 'palettes' / f'{i:02}.pal') for i in range(13)]
        self.blocks = [p.joinpath('metatiles.bin').read_bytes() for p in (self.primary, self.secondary)]
        self.cache = {}

    def tile(self, descriptor, transparent):
        ident, pal = descriptor & 1023, descriptor >> 12
        sheet = self.sheets[ident >= 640]
        index = ident if ident < 640 else ident - 640
        x, y = (index % (sheet.width // 8)) * 8, (index // (sheet.width // 8)) * 8
        source = sheet.crop((x, y, x + 8, y + 8))
        colors = self.pals[pal] if pal < len(self.pals) else self.pals[0]
        tile = Image.new('RGBA', (8, 8))
        tile.putdata([(*colors[int(v) % 16], 0 if transparent and int(v) % 16 == 0 else 255) for v in source.getdata()])
        if descriptor & 1024: tile = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if descriptor & 2048: tile = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return tile

    def block(self, ident):
        if ident not in self.cache:
            data = self.blocks[ident >= 640]
            offset = (ident if ident < 640 else ident - 640) * 16
            result = Image.new('RGBA', (16, 16))
            if offset + 16 <= len(data):
                for i, entry in enumerate(struct.unpack_from('<8H', data, offset)):
                    tile = self.tile(entry, i >= 4)
                    result.alpha_composite(tile, ((i % 2) * 8, ((i % 4) // 2) * 8))
            self.cache[ident] = result
        return self.cache[ident]

    def atlas(self):
        result = Image.new('RGBA', (16 * 16, 64 * 16))
        for i in range(1024): result.paste(self.block(i), ((i % 16) * 16, (i // 16) * 16))
        return result

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for primary, secondary in [('general', 'pallet_town'), ('general', 'viridian_city'),
                               ('general', 'cave'), ('building', 'generic_building_1')]:
        tiles = Tileset(primary, secondary)
        atlas = tiles.atlas()
        atlas.save(DEST / f'{secondary}.png')
        preview = Image.new('RGB', (16 * 56, 64 * 62), '#243c40')
        draw = ImageDraw.Draw(preview)
        for i in range(1024):
            x, y = i % 16 * 56, i // 16 * 62
            preview.paste(tiles.block(i).resize((48,48), Image.Resampling.NEAREST), (x,y))
            draw.text((x,y+48), str(i), fill='white')
        preview.save(ROOT / 'artifacts' / f'gba-atlas-{secondary}.png')
        for page in range(4):
            preview.crop((0,page*992,896,(page+1)*992)).save(
                ROOT/'artifacts'/f'gba-atlas-{secondary}-{page}.png')
        layout_name = {'pallet_town':'PalletTown', 'viridian_city':'ViridianCity'}.get(secondary)
        if layout_name:
            layouts = json.loads((SOURCE/'data/layouts/layouts.json').read_text())['layouts']
            layout = next(e for e in layouts if e.get('name') == layout_name + '_Layout')
            raw = (SOURCE/layout['blockdata_filepath']).read_bytes()
            rendered = Image.new('RGBA',(layout['width']*16,layout['height']*16))
            for j,(entry,) in enumerate(struct.iter_unpack('<H',raw)):
                rendered.paste(tiles.block(entry & 1023),(j%layout['width']*16,j//layout['width']*16))
            rendered.save(ROOT/'artifacts'/f'gba-map-{secondary}.png')
            crops = ({'home':(80,48,160,128), 'lab':(208,144,320,224)} if secondary=='pallet_town' else
                     {'center':(384,352,464,432), 'mart':(544,256,608,320),
                      'hotel':(528,96,624,176), 'restaurant':(384,240,464,320)})
            grass = {tuple(c) for i in (1,16,17,640) for c in tiles.block(i).getdata()}
            for name,box in crops.items():
                cut = rendered.crop(box)
                cut.putdata([(r,g,b,0 if (r,g,b,a) in grass else a) for r,g,b,a in cut.getdata()])
                cut.save(DEST/f'{name}.png')
        if secondary == 'pallet_town':
            tree=Image.new('RGBA',(32,32))
            for j,ident in enumerate((28,29,36,37)):
                tree.paste(tiles.block(ident),(j%2*16,j//2*16))
            grass={tuple(c) for c in tiles.block(1).getdata()}
            tree.putdata([(r,g,b,0 if (r,g,b,a) in grass else a) for r,g,b,a in tree.getdata()])
            tree.save(DEST/'tree.png')
            rock=Image.new('RGBA',(32,32))
            for j,ident in enumerate((104,105,120,121)):
                rock.paste(tiles.block(ident),(j%2*16,j//2*16))
            rock.putdata([(r,g,b,0 if (r,g,b,a) in grass else a) for r,g,b,a in rock.getdata()])
            rock.save(DEST/'rock.png')
    # Native tilemap terrain backdrops, decoded as 32×32 screen blocks.
    for kind in ('grass', 'water', 'cave', 'mountain'):
        base = SOURCE / 'graphics/battle_terrain' / kind
        sheet = Image.open(base / 'terrain.png')
        colors = palette(base / 'terrain.pal')
        descriptors = (base / 'terrain.bin').read_bytes()
        # Battle backgrounds occupy palette banks 2 onward; bank 0 is blank.
        result = Image.new('RGBA', (256,160))
        for i in range(min(640,len(descriptors)//2)):
            desc = struct.unpack_from('<H', descriptors, i*2)[0]
            idx = desc & 1023
            x, y = idx % (sheet.width//8)*8, idx//(sheet.width//8)*8
            piece = sheet.crop((x,y,x+8,y+8))
            rgba=Image.new('RGBA',(8,8))
            bank = max(0, (desc >> 12) - 2)
            rgba.putdata([(*colors[bank*16+int(v)%16],255) for v in piece.getdata()])
            if desc & 1024: rgba=rgba.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if desc & 2048: rgba=rgba.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            result.paste(rgba,(i%32*8,i//32*8))
        result.save(DEST / f'arena_{kind}.png')

if __name__ == '__main__': main()
