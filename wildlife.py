"""Persistent wildlife: schedules, fleeing, predator hunts and player combat."""
import math
import random

SPECIES = {
    "Singa": {"hp": 100, "speed": 120, "damage": 15, "size": 44, "meat": 4, "hide": 2},
    "Gajah": {"hp": 200, "speed": 40, "damage": 25, "size": 96, "meat": 7, "hide": 3},
    "Kelinci": {"hp": 28, "speed": 86, "damage": 0, "size": 35, "meat": 1, "hide": 1},
    "Babi hutan": {"hp": 75, "speed": 60, "damage": 9, "size": 52, "meat": 3, "hide": 1},
    "Hyena": {"hp": 70, "speed": 135, "damage": 10, "size": 36, "meat": 2, "hide": 1},
    "Monyet": {"hp": 38, "speed": 76, "damage": 0, "size": 40, "meat": 1, "hide": 1},
}
PREY = {"Singa": ("Kelinci", "Babi hutan", "Monyet", "Hyena"), "Hyena": ("Kelinci", "Monyet")}


def hunting_time(species, hour):
    if species == "Singa":
        return 6 <= hour < 10 or 16 <= hour < 20
    if species == "Hyena":
        return hour >= 18 or hour < 6
    return False


class Wildlife:
    def __init__(self, life):
        self.life = life
        self.rng = random.Random(571 + life.day)
        self.events = []
        required = {"species", "id", "x", "y", "hp", "state", "facing", "goal_x", "goal_y", "until", "cooldown", "provoked", "respawn", "moving"}
        life.animals[:] = [a for a in life.animals if isinstance(a, dict) and a.get("species") in SPECIES and required.issubset(a)]
        if not life.animals:
            for species, count in (("Singa", 1), ("Gajah", 1), ("Kelinci", 4), ("Babi hutan", 2), ("Hyena", 1), ("Monyet", 2)):
                for _ in range(count):
                    life.animals.append(self.spawn(species, len(life.animals)))

    def spawn(self, species, number):
        x, y = self.rng.uniform(170, 1100), self.rng.uniform(190, 610)
        return {"id": number, "species": species, "x": x, "y": y, "hp": SPECIES[species]["hp"],
                "state": "Jalan", "facing": "down", "goal_x": x, "goal_y": y, "until": 0,
                "cooldown": 0, "provoked": 0, "respawn": 0, "moving": False}

    @property
    def population(self):
        # Keep legacy animals in the save, but only simulate a sparse population.
        caps = {"Singa":1,"Hyena":1,"Gajah":1,"Kelinci":4,"Babi hutan":2,"Monyet":2}
        counts, result = {}, []
        for animal in self.life.animals:
            species = animal["species"]
            if counts.get(species, 0) < caps[species]:
                result.append(animal)
                counts[species] = counts.get(species, 0) + 1
        return result

    @property
    def living(self):
        return [a for a in self.population if a["hp"] > 0]

    def log(self, text):
        self.events.append(text)
        self.events = self.events[-4:]

    def kill(self, animal, player=False):
        animal["hp"] = 0
        animal["state"] = "Mati"
        animal["moving"] = False
        animal["respawn"] = self.life.elapsed + 100
        if player:
            spec = SPECIES[animal["species"]]
            self.life.bag["Daging"] += spec["meat"]
            self.life.bag["Kulit"] += spec["hide"]
            self.life.kills += 1
            self.life.complete("Berburu")
            self.log(f"{animal['species']}: +{spec['meat']} daging, +{spec['hide']} kulit")

    def hit(self, animal, damage):
        if animal["hp"] <= 0:
            return ""
        animal["hp"] = max(0, animal["hp"] - damage)
        animal["provoked"] = self.life.elapsed + 12
        if not animal["hp"]:
            self.kill(animal, player=True)
            return self.events[-1]
        return f"{animal['species']} terkena serangan. HP {int(animal['hp'])}."

    def move(self, animal, tx, ty, speed, dt, obstacles):
        dx, dy = tx - animal["x"], ty - animal["y"]
        distance = math.hypot(dx, dy)
        animal["moving"] = distance > 4
        if distance < 4:
            return
        animal["facing"] = "left" if abs(dx) > abs(dy) and dx < 0 else "right" if abs(dx) > abs(dy) else "up" if dy < 0 else "down"
        step = min(speed * dt, distance)
        xx = max(62, min(1204, animal["x"] + dx / distance * step))
        yy = max(167, min(654, animal["y"] + dy / distance * step))
        def blocked(x, y):
            return any(r.collidepoint(x, y - 4) for r in obstacles)
        if not blocked(xx, yy):
            animal["x"], animal["y"] = xx, yy
        elif not blocked(xx, animal["y"]):
            animal["x"] = xx
        elif not blocked(animal["x"], yy):
            animal["y"] = yy
        else:
            # Choose a fresh reachable waypoint rather than staying against a tree.
            animal["until"] = 0
            animal["goal_x"], animal["goal_y"] = self.rng.uniform(100, 1180), self.rng.uniform(190, 630)

    def update(self, dt, obstacles=(), player_active=True):
        life = self.life
        now = life.elapsed
        for animal in self.population:
            if animal["hp"] <= 0:
                if now >= animal["respawn"]:
                    animal.update(self.spawn(animal["species"], animal["id"]))
                    for _ in range(30):
                        if not any(r.collidepoint(animal["x"], animal["y"]) for r in obstacles):
                            break
                        animal.update(self.spawn(animal["species"], animal["id"]))
                continue
            animal["cooldown"] = max(0, animal["cooldown"] - dt)
            animal["moving"] = False
            species = animal["species"]
            spec = SPECIES[species]
            hunting = hunting_time(species, life.hour)
            player_distance = math.hypot(life.x - animal["x"], life.y - animal["y"])
            player_here = life.scene == "forest" and player_active
            provoked = animal["provoked"] > now
            dangerous = (species in PREY and hunting) or provoked
            if player_here and spec["damage"] and dangerous and player_distance < (200 if species in PREY else 140):
                animal["state"] = "Menyerang"
                self.move(animal, life.x, life.y, spec["speed"] * 1.3, dt, obstacles)
                if player_distance < spec["size"] * .35 + 23 and animal["cooldown"] == 0:
                    life.health = max(0, life.health - spec["damage"])
                    animal["cooldown"] = 1.2
                    self.log(f"{species} menyerang: -{spec['damage']} HP")
                continue
            threats = [a for a in self.living if a is not animal and a["species"] in PREY
                       and hunting_time(a["species"], life.hour) and species in PREY[a["species"]]
                       and math.hypot(a["x"] - animal["x"], a["y"] - animal["y"]) < 185]
            if player_here and (provoked or species in ("Kelinci", "Monyet")) and player_distance < 110:
                threats.append({"x": life.x, "y": life.y})
            if threats:
                nearest = min(threats, key=lambda a: math.hypot(a["x"] - animal["x"], a["y"] - animal["y"]))
                animal["state"] = "Kabur"
                self.move(animal, animal["x"] + (animal["x"] - nearest["x"]) * 2,
                          animal["y"] + (animal["y"] - nearest["y"]) * 2, spec["speed"] * 1.65, dt, obstacles)
                continue
            # Hour skips must respect the new sleep schedule before feeding.
            sleeping = (species in ("Kelinci", "Monyet", "Gajah", "Babi hutan") and not life.daylight) or (species == "Singa" and 11 <= life.hour < 15) or (species == "Hyena" and 7 <= life.hour < 16)
            if sleeping:
                animal["state"] = "Tidur"
                continue
            if animal.get("fed_until", 0) > now:
                animal["state"] = "Makan"
                continue
            if hunting and species in PREY:
                prey = [a for a in self.living if a["species"] in PREY[species]]
                if prey:
                    target = min(prey, key=lambda a: math.hypot(a["x"] - animal["x"], a["y"] - animal["y"]))
                    distance = math.hypot(target["x"] - animal["x"], target["y"] - animal["y"])
                    if distance < 300:
                        animal["state"] = "Berburu"
                        self.move(animal, target["x"], target["y"], spec["speed"] * 1.45, dt, obstacles)
                        if distance < 34 and animal["cooldown"] == 0:
                            target["hp"] -= spec["damage"] * 2
                            animal["cooldown"] = 1
                            if target["hp"] <= 0:
                                self.kill(target)
                                animal["until"] = now + 12
                                animal["fed_until"] = now + 12
                                self.log(f"{species} menangkap {target['species']}")
                        continue
            if now > animal["until"]:
                animal["goal_x"] = self.rng.uniform(90, 1185)
                animal["goal_y"] = self.rng.uniform(185, 635)
                animal["until"] = now + self.rng.uniform(3, 9)
            animal["state"] = "Jalan" if math.hypot(animal["goal_x"] - animal["x"], animal["goal_y"] - animal["y"]) > 8 else "Makan rumput"
            self.move(animal, animal["goal_x"], animal["goal_y"], spec["speed"] * .5, dt, obstacles)
