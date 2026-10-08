"""Shared pixel UI. Rendering only: no simulation or input state lives here."""
from pathlib import Path
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
    # VT323 has Latin accents but no arrows/filled-circle navigation glyphs.
    symbols = str.maketrans({'←':'<', '→':'>', '↑':'^', '↓':'v', '↔':'<>',
                            '⚔':'', 'ⓘ':'i', '▶':'>', '●':'*', '○':'o', '−':'-', '–':'-', '…':'...'})

    def __init__(self, size):
        self.source = pg.font.Font(str(Path(__file__).parent / 'assets/fonts/VT323-Regular.ttf'), size)

    def render(self, text, antialias, color, background=None):
        return self.source.render(str(text).translate(self.symbols), False, color, background)

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


def arena(surface, style):
    palettes = {
        'meadow': ((48, 88, 111), (61, 116, 122), (47, 87, 95), (100, 159, 104), (78, 65, 67)),
        'water': ((43, 75, 113), (55, 108, 147), (37, 76, 121), (84, 175, 182), (45, 74, 110)),
        'cave': ((28, 30, 52), (53, 49, 80), (40, 40, 63), (141, 115, 151), (63, 52, 80)),
        'sky': ((69, 117, 157), (105, 160, 179), (66, 120, 156), (182, 203, 195), (66, 85, 117)),
    }
    sky, far, near, grass, dirt = palettes.get(style, palettes['meadow'])
    surface.fill(sky)
    pg.draw.rect(surface, GOLD, (1016, 180, 64, 64))
    pg.draw.rect(surface, sky, (1016, 180, 8, 8))
    pg.draw.rect(surface, sky, (1072, 236, 8, 8))
    for offset, color, baseline in ((0, far, 460), (90, near, 555)):
        for i in range(9):
            x = i * 176 - offset
            height = 64 + (i * 47 % 5) * 22
            for step in range(4):
                pg.draw.rect(surface, color, (x + step * 16, baseline-height-step*20, 176-step*32, height+step*20))
    pg.draw.rect(surface, dirt, (0, 606, 1280, 194))
    pg.draw.rect(surface, grass, (0, 606, 1280, 12))
    for x in range(0, 1280, 24):
        pg.draw.rect(surface, grass, (x, 618, 12, 6))
    for y in range(644, 800, 32):
        for x in range((y//32 % 2)*32, 1280, 64):
            pg.draw.rect(surface, (max(0,dirt[0]-12), max(0,dirt[1]-12), max(0,dirt[2]-12)), (x,y,48,4))


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
