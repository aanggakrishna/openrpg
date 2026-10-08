"""Daylight, warm indoor light, rain, clouds and snow over the game world."""
import math
import random
import pygame as pg

OUTSIDE = ("outdoors", "forest", "market", "reserve", "coast", "mountain")


class Environment:
    def __init__(self):
        self.time = 0
        self.overlay = pg.Surface((1280, 800), pg.SRCALPHA)
        self.halo = pg.Surface((300, 300), pg.SRCALPHA)
        for radius in range(148, 0, -1):
            alpha = max(0, int(27 * (1 - radius / 148) ** 1.7))
            pg.draw.circle(self.halo, (248, 210, 143, alpha), (150, 150), radius)
        rng = random.Random(23)
        self.particles = [(rng.uniform(0, 1400), rng.uniform(0, 800), rng.uniform(.7, 1.4)) for _ in range(180)]

    def update(self, dt):
        self.time += dt

    def draw(self, target, life):
        hour = life.minutes / 60
        if 7 <= hour < 17:
            dark = 0
        elif 5 <= hour < 7:
            dark = int(90 * (7 - hour) / 2)
        elif 17 <= hour < 19:
            dark = int(90 * (hour - 17) / 2)
        else:
            dark = 90
        self.overlay.fill((0, 0, 0, 0))
        world_rect = pg.Rect(0, 135, 1280, 588)
        if life.scene in OUTSIDE:
            if dark:
                pg.draw.rect(self.overlay, (17, 28, 60, dark), world_rect)
            target.blit(self.overlay, (0, 0))
            if dark:
                old = target.get_clip()
                target.set_clip(world_rect)
                target.blit(self.halo, (int(life.x - 150), int(life.y - 170)))
                target.set_clip(old)
            self.overlay.fill((0, 0, 0, 0))
            if 16 <= hour < 18:
                pg.draw.rect(self.overlay, (223, 139, 77, 22), world_rect)
                target.blit(self.overlay, (0, 0))
                self.overlay.fill((0, 0, 0, 0))
            if life.weather == "Berawan":
                pg.draw.rect(self.overlay, (62, 75, 94, 25), world_rect)
            elif life.weather == "Hujan":
                pg.draw.rect(self.overlay, (38, 65, 97, 43), world_rect)
                old = self.overlay.get_clip(); self.overlay.set_clip(world_rect)
                for x, y, speed in self.particles:
                    xx = (x - self.time * 85 * speed) % 1280
                    yy = 135 + (y + self.time * 410 * speed) % 588
                    pg.draw.line(self.overlay, (185, 217, 240, 155), (xx, yy), (xx - 6, yy + 15), 1)
                self.overlay.set_clip(old)
            elif life.weather == "Salju":
                pg.draw.rect(self.overlay, (197, 220, 225, 28), world_rect)
                old = self.overlay.get_clip(); self.overlay.set_clip(world_rect)
                for x, y, speed in self.particles:
                    xx = (x + math.sin(self.time * .8 + y) * 16) % 1280
                    yy = 135 + (y + self.time * 52 * speed) % 588
                    pg.draw.circle(self.overlay, (248, 249, 242, 230), (int(xx), int(yy)), 2 if speed > 1 else 1)
                self.overlay.set_clip(old)
        elif dark:
            pg.draw.rect(self.overlay, (92, 60, 32, 30), world_rect)
        target.blit(self.overlay, (0, 0))
