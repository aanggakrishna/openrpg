"""Shared pixel UI. Rendering only: no simulation or input state lives here."""
import pygame as pg

INK = (19, 25, 46)
PANEL = (31, 43, 69)
EDGE = (88, 111, 146)
CREAM = (255, 241, 204)
MUTED = (164, 184, 207)
GREEN = (117, 224, 166)
GOLD = (255, 204, 103)
RED = (245, 116, 109)


class PixelFont:
    # Keep the pixel-art panels and game world, while using a familiar UI face
    # so long instructions, names and status values stay easy to read.
    symbols = str.maketrans({'←':'<', '→':'>', '↑':'^', '↓':'v', '↔':'<>',
                            '⚔':'', 'ⓘ':'i', '▶':'>', '●':'*', '○':'o', '−':'-', '–':'-', '…':'...'})

    def __init__(self, size):
        self.source = pg.font.SysFont('Arial', size)

    def render(self, text, antialias, color, background=None):
        return self.source.render(str(text).translate(self.symbols), True, color, background)

    def size(self, text):
        return self.source.size(str(text).translate(self.symbols))

    def get_linesize(self):
        return self.source.get_linesize()


def font(size):
    return PixelFont(size)


def panel(surface, rect, color, border=None):
    r = pg.Rect(rect)
    if r.width <= 0 or r.height <= 0:
        return
    if r.height < 20:
        pg.draw.rect(surface, color, r)
        return
    # Map legacy dark panels into one coherent palette; keep semantic accents.
    if max(color[:3]) < 120:
        color = INK if sum(color[:3]) < 130 else PANEL
    light = sum(color[:3]) > 570
    outline = border or (EDGE if not light else GOLD)
    pg.draw.rect(surface, (9, 14, 28), r.move(4, 4))
    pg.draw.rect(surface, outline, r)
    pg.draw.rect(surface, color, r.inflate(-4, -4))
    pg.draw.line(surface, (255, 229, 170) if light else (65, 85, 118),
                 (r.left + 4, r.top + 4), (r.right - 5, r.top + 4), 2)
    for x, y in ((r.left, r.top), (r.right-3, r.top), (r.left, r.bottom-3), (r.right-3, r.bottom-3)):
        pg.draw.rect(surface, INK, (x, y, 3, 3))


def pixelate(surface, factor=2):
    size = surface.get_size()
    tiny = pg.transform.scale(surface, (max(1, size[0]//factor), max(1, size[1]//factor)))
    pg.transform.scale(tiny, size, surface)


def meter(surface, rect, value, maximum, color=GREEN):
    r = pg.Rect(rect)
    pg.draw.rect(surface, (10, 17, 32), r)
    inner = r.inflate(-4, -4)
    fill = inner.copy()
    fill.width = round(inner.width * max(0, min(1, value / max(1, maximum))))
    if fill.width:
        pg.draw.rect(surface, color, fill)
        pg.draw.line(surface, CREAM, fill.topleft, (fill.right-1, fill.top), 1)
    for x in range(inner.left + 12, inner.right, 14):
        pg.draw.line(surface, INK, (x, inner.top), (x, inner.bottom-1), 2)


_ARENAS = {}

def arena(surface, style):
    """Four cached pixel stages; artwork is built once, not each combat frame."""
    if style not in _ARENAS:
        stage = pg.Surface((1280,800))
        palette = {
            'meadow':((30,55,74),(57,97,107),(38,70,73),(87,145,100),(41,54,65)),
            'water':((27,48,81),(56,100,134),(33,74,103),(91,177,194),(35,58,84)),
            'cave':((19,20,39),(44,39,66),(30,30,50),(165,130,193),(37,31,55)),
            'sky':((45,76,111),(103,151,176),(61,106,140),(196,213,207),(52,68,94)),
        }
        sky,far,near,edge,floor=palette.get(style,palette['meadow'])
        stage.fill(sky)
        for row in range(12):
            color=tuple(min(255,v+row*2) for v in sky)
            pg.draw.rect(stage,color,(0,row*51,1280,51))
        for i in range(28):
            x=(i*197+53)%1280;y=230+(i*83)%200
            pg.draw.rect(stage,tuple(min(255,c+38) for c in sky),(x,y,2,2))
        for offset,color,base in ((0,far,515),(110,near,580)):
            for i in range(10):
                x=i*165-offset;peak=base-80-(i*71%115)
                pg.draw.polygon(stage,color,[(x-50,base),(x+10,peak+48),(x+40,peak+48),(x+65,peak),(x+93,peak),(x+120,peak+40),(x+205,base)])
        if style=='cave':
            for i in range(9):
                x=i*167+19;height=65+(i*37)%105
                pg.draw.polygon(stage,(71,68,113),[(x,606),(x+18,606-height),(x+34,590-height),(x+48,606)])
                pg.draw.line(stage,(133,169,199),(x+18,606-height),(x+28,594),3)
        elif style=='water':
            pg.draw.rect(stage,(43,98,127),(0,520,1280,86))
            for i in range(40):
                x=(i*113)%1280;y=532+(i*37)%60
                pg.draw.rect(stage,(72,137,158),(x,y,24+(i%3)*10,3))
            for x in (80,1140):
                pg.draw.rect(stage,(90,106,119),(x,387,34,218))
                pg.draw.rect(stage,(151,156,161),(x-12,378,58,14))
                pg.draw.rect(stage,(91,177,194),(x+7,410,20,46))
        else:
            # Ruined columns and tournament pennants give the stage depth.
            for x in (92,1110):
                pg.draw.rect(stage,(64,81,94),(x,384,50,222))
                pg.draw.rect(stage,(121,137,140),(x-9,374,68,15))
                pg.draw.rect(stage,(91,108,116),(x+5,396,8,185))
                pg.draw.line(stage,(184,167,118),(x+26,304),(x+26,389),3)
                pg.draw.polygon(stage,(171,79,94),[(x+29,309),(x+90,321),(x+29,342)])
            for i in range(13):
                x=i*111-22
                pg.draw.rect(stage,(37,72,65),(x,579,74,27))
                pg.draw.rect(stage,(54,94,77),(x+9,568,48,14))
        pg.draw.rect(stage,floor,(0,606,1280,194))
        pg.draw.rect(stage,edge,(0,606,1280,7))
        pg.draw.rect(stage,tuple(max(0,c-25) for c in edge),(0,613,1280,8))
        for y in range(632,800,36):
            for x in range(-60+(y//36%2)*58,1280,116):
                pg.draw.rect(stage,tuple(min(255,c+8) for c in floor),(x,y,110,29),1)
        _ARENAS[style]=stage
    surface.blit(_ARENAS[style],(0,0))


class IconFont:
    """Color emoji fonts can ignore requested size; enforce a pixel icon budget."""
    def __init__(self, size):
        self.pixels = size
        self.source = pg.font.SysFont('Apple Color Emoji,Segoe UI Emoji,Noto Color Emoji', size)
        self.cache = {}

    def render(self, text, antialias, color):
        key = (text, tuple(color))
        if key not in self.cache:
            glyph = self.source.render(text, True, color)
            bounds = glyph.get_bounding_rect()
            if bounds.width and bounds.height:
                glyph = glyph.subsurface(bounds)
            ratio = self.pixels / max(1, glyph.get_width(), glyph.get_height())
            size = (max(1, round(glyph.get_width()*ratio)), max(1, round(glyph.get_height()*ratio)))
            glyph = pg.transform.scale(glyph, (max(1,size[0]//2), max(1,size[1]//2)))
            self.cache[key] = pg.transform.scale(glyph, size)
        return self.cache[key]
