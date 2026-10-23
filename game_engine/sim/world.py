"""
The live adventure-map world used inside the sandbox.

Every hero_api call acts on a World *immediately* (moves happen in code order),
so player code can react: `if hero.mp >= 2: dig()`.

A World wraps a JSON-able `state` dict (see campaign.new_state) and records
what happened during the day: path, events, log, battles, errors.
"""
import copy
import random

from .rules import (TERRAIN, MAP_COLS, MAP_ROWS, RESOURCES, UNITS, MAX_ARMY_SLOTS,
                    terrain_cost, terrain_name)
from .battle import Battle
from .generals import GENERALS

DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


class HeroError(Exception):
    """A game-rule problem caused by player code (friendly message, stops the turn)."""


class HeroStopped(Exception):
    """The hero could not continue moving (blocked, out of MP, lost a battle...)."""


# Objects that stay on the map after you visit them
PERSISTENT = {"Sign", "Town", "Market", "Tavern", "Sphinx", "Seer", "Merchant", "Altar",
              "Vault", "Shrine", "Banner", "Obelisk", "Gate", "DigSite", "RingShrine",
              "Herald", "Well"}


def _type_name(v):
    return type(v).__name__


class World:
    def __init__(self, state, dry=False):
        self.s = copy.deepcopy(state)
        self.rules = self.s.setdefault("rules", {})
        self.dry = dry
        self.reset_day()

    # ------------------------------------------------------------------
    # Day bookkeeping
    # ------------------------------------------------------------------
    def reset_day(self):
        h = self.s["hero"]
        self.mp = 0.0
        self.path = [(h["x"], h["y"], 0.0, True)]
        self.events = []
        self.terraforms = []
        self.battles = []
        self.says = []
        self.error = None
        self.picked = []
        self.rng = random.Random(self.s.get("seed", 1) * 1000 + self.s.get("day", 1))

    @property
    def hero(self):
        return self.s["hero"]

    @property
    def max_mp(self):
        return float(self.hero.get("max_mp", 12.0)) + self.skill_rank("Logistics")

    def skill_rank(self, name):
        return int(self.s.get("skills", {}).get(name, 0))

    def counter(self, name, inc=1):
        c = self.s.setdefault("counters", {})
        c[name] = c.get(name, 0) + inc

    def flag(self, name, value=True):
        self.s.setdefault("flags", {})[name] = value

    def has_flag(self, name):
        return bool(self.s.get("flags", {}).get(name))

    def event(self, text, kind="info", x=None, y=None):
        self.events.append({"text": str(text), "kind": kind,
                            "x": self.hero["x"] if x is None else x,
                            "y": self.hero["y"] if y is None else y})

    def res(self, name):
        return self.s.setdefault("resources", {}).get(name, 0)

    def add_res(self, name, amount):
        r = self.s.setdefault("resources", {})
        r[name] = r.get(name, 0) + amount

    # ------------------------------------------------------------------
    # Map queries
    # ------------------------------------------------------------------
    @property
    def grid(self):
        return self.s["grid"]

    def in_map(self, x, y):
        return 0 <= x < MAP_COLS and 0 <= y < MAP_ROWS

    def objects_at(self, x, y, include_hidden=False):
        return [o for o in self.s["objects"]
                if o["x"] == x and o["y"] == y and not o.get("collected")
                and (include_hidden or not o.get("hidden"))]

    def object_at(self, x, y):
        objs = self.objects_at(x, y)
        return objs[0] if objs else None

    def find_object(self, kind):
        """Find an object by type or name (case-insensitive)."""
        k = str(kind).lower()
        for o in self.s["objects"]:
            if o.get("collected") or o.get("hidden"):
                continue
            if o["type"].lower() == k or o["name"].lower() == k:
                return o
        return None

    def object_by_id(self, oid):
        for o in self.s["objects"]:
            if o["id"] == oid:
                return o
        return None

    def adjacent_object(self, otype):
        hx, hy = self.hero["x"], self.hero["y"]
        for dx, dy in ((0, 0),) + DIRS4:
            for o in self.objects_at(hx + dx, hy + dy):
                if o["type"] == otype:
                    return o
        return None

    def here(self, otype):
        for o in self.objects_at(self.hero["x"], self.hero["y"]):
            if o["type"] == otype:
                return o
        return None

    def walkable(self, x, y):
        if not self.in_map(x, y) or terrain_cost(self.grid[y][x]) is None:
            return False
        return not any(self.blocks(o) for o in self.objects_at(x, y))

    def blocks(self, obj):
        if obj["type"] == "Gate" and not obj.get("open"):
            if obj.get("kind") == "key" and self.key_gate_ok(obj):
                return False
            return True
        return False

    def key_gate_ok(self, obj):
        if obj.get("key") and obj["key"] not in self.s.get("keys", []):
            return False
        if obj.get("day_only") and self.is_night():
            return False
        if obj.get("night_only") and not self.is_night():
            return False
        return True

    def is_night(self):
        return bool(self.rules.get("night_cycle")) and self.s.get("day", 1) % 2 == 0

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------
    def stop(self, msg, nx=None, ny=None, cost=0.0):
        if nx is not None:
            self.path.append((nx, ny, self.mp + cost, False))
        self.error = msg
        raise HeroStopped(msg)

    def step_to(self, nx, ny):
        if self.dry:
            return
        if not self.in_map(nx, ny):
            self.stop(f"Moved off the map edge at ({nx}, {ny})!", nx, ny)
        tile = self.grid[ny][nx]
        for o in self.objects_at(nx, ny):
            if self.blocks(o):
                self.stop(self.block_message(o), nx, ny)
        cost = terrain_cost(tile)
        if cost is None:
            self.stop(f"Blocked by {terrain_name(tile)} at ({nx}, {ny})!", nx, ny)
        if self.mp + cost > self.max_mp + 1e-9:
            self.stop(f"Out of Movement Points! ({self.mp + cost:.1f} / {self.max_mp:.1f} MP)", nx, ny, cost)
        for o in list(self.objects_at(nx, ny)):
            if not self.interact(o, nx, ny, cost):
                return
        self.mp += cost
        self.hero["x"], self.hero["y"] = nx, ny
        self.path.append((nx, ny, self.mp, True))
        self.counter(f"stood:{nx},{ny}")

    def block_message(self, o):
        if o.get("kind") == "key":
            need = []
            if o.get("key") and o["key"] not in self.s.get("keys", []):
                need.append(f"the {o['key']} key")
            if o.get("day_only") and self.is_night():
                need.append("daylight (it's night!)")
            if o.get("night_only") and not self.is_night():
                need.append("darkness (it only opens at night)")
            return f"The {o['name']} is locked. You need {' and '.join(need)}."
        return (f"The {o['name']} at ({o['x']}, {o['y']}) is closed! "
                f"Stand next to it and use open_gate(...).")

    def walk_rel(self, dx, dy):
        if self.dry:
            return
        sx = 1 if dx > 0 else -1
        for _ in range(abs(dx)):
            self.step_to(self.hero["x"] + sx, self.hero["y"])
        sy = 1 if dy > 0 else -1
        for _ in range(abs(dy)):
            self.step_to(self.hero["x"], self.hero["y"] + sy)

    def walk_abs(self, tx, ty):
        if self.dry:
            return
        while self.hero["x"] != tx:
            self.step_to(self.hero["x"] + (1 if self.hero["x"] < tx else -1), self.hero["y"])
        while self.hero["y"] != ty:
            self.step_to(self.hero["x"], self.hero["y"] + (1 if self.hero["y"] < ty else -1))

    def find_path(self, tx, ty):
        """BFS over walkable tiles (used by travel_to)."""
        from collections import deque
        start = (self.hero["x"], self.hero["y"])
        if start == (tx, ty):
            return [start]
        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            for dx, dy in DIRS4:
                n = (cur[0] + dx, cur[1] + dy)
                if n in prev or not self.walkable(*n):
                    continue
                if self.rules.get("fog") and not self.is_lit(*n):
                    continue
                prev[n] = cur
                if n == (tx, ty):
                    path = [n]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return list(reversed(path))
                q.append(n)
        return None

    # ------------------------------------------------------------------
    # Terraform
    # ------------------------------------------------------------------
    def terraform(self, x, y, ttype):
        if not self.in_map(x, y):
            return
        if ttype not in TERRAIN:
            raise HeroError(f"'{ttype}' is not a terrain type. Try 'B' (bridge) or 'G' (grass).")
        allowed = self.rules.get("terraform")
        if allowed is not None:
            ok = allowed.get(ttype)
            if ok is None or self.grid[y][x] not in ok:
                raise HeroError(
                    f"The terraform spell can't turn {terrain_name(self.grid[y][x])} at ({x}, {y}) "
                    f"into '{ttype}' here.")
        self.grid[y][x] = ttype
        self.terraforms.append((x, y, ttype))
        self.s.setdefault("terraformed", []).append([x, y, ttype])

    # ------------------------------------------------------------------
    # Object interaction when stepping onto a tile
    # ------------------------------------------------------------------
    def collect(self, o):
        o["collected"] = True
        self.picked.append(o["id"])

    def give_reward(self, reward, o=None):
        if not reward:
            return
        for r in RESOURCES:
            if reward.get(r):
                self.add_res(r, reward[r])
                self.event(f"+{reward[r]} {r.capitalize()}!", "gain")
        if reward.get("key"):
            keys = self.s.setdefault("keys", [])
            if reward["key"] not in keys:
                keys.append(reward["key"])
            self.event(f"Got the {reward['key']} key!", "gain")
        for unit, count in reward.get("units", {}).items():
            self.add_units(unit, count)
            self.event(f"+{count} {unit}!", "gain")
        if reward.get("flag"):
            self.flag(reward["flag"])
        if reward.get("reveal"):
            for oid in reward["reveal"]:
                ob = self.object_by_id(oid)
                if ob:
                    ob["hidden"] = False
        if reward.get("mana"):
            self.hero["mana"] = self.hero.get("mana", 0) + reward["mana"]
        if reward.get("message"):
            self.event(reward["message"], "story")

    def add_units(self, unit, count):
        army = self.s.setdefault("army", [])
        for slot in army:
            if slot["unit"] == unit:
                slot["count"] += count
                return
        if len(army) >= MAX_ARMY_SLOTS:
            raise HeroError(f"All {MAX_ARMY_SLOTS} army slots are full! No room for {unit}.")
        army.append({"unit": unit, "count": count})

    def interact(self, o, x, y, cost):
        t = o["type"]
        self.counter(f"visit:{o['id']}")
        legacy = self.rules.get("legacy_act1")
        if t == "Gold":
            self.add_res("gold", o["value"])
            self.event(f"+{o['value']} Gold!", "gain", x, y)
            self.collect(o)
        elif t == "Resource":
            self.add_res(o["resource"], o["value"])
            self.event(f"+{o['value']} {o['resource'].capitalize()}!", "gain", x, y)
            self.collect(o)
        elif t == "Mine":
            self.add_res(o.get("resource", "wood"), o["value"])
            self.event(f"+{o['value']} {o.get('resource', 'wood').capitalize()}/day!", "gain", x, y)
            self.collect(o)
        elif t == "Guard":
            if self.res("gold") < o["value"]:
                self.stop(f"Guard at ({x},{y}) demands {o['value']} Gold! (You have {self.res('gold')})",
                          x, y, cost)
            self.add_res("gold", -o["value"])
            self.event("Region unlocked!", "gain", x, y)
            self.collect(o)
        elif t == "Mage":
            self.event(o.get("message", "The Archmage nods wisely."), "story", x, y)
            self.collect(o)
        elif t == "Keymaster":
            self.give_reward({"key": o["key"]})
            self.collect(o)
        elif t == "Dwelling":
            if legacy:
                self.s["dragons"] = self.s.get("dragons", 0) + o["value"]
                self.event(f"+{o['value']} Dragons!", "gain", x, y)
            else:
                self.add_units(o["unit"], o["value"])
                self.event(f"+{o['value']} {o['unit']}!", "gain", x, y)
            self.collect(o)
        elif t in ("Monster", "Boss"):
            if legacy:
                need = 1 if t == "Monster" else o["value"]
                have = self.s.get("dragons", 0)
                if have < need:
                    msg = (f"{o['name']} at ({x},{y})! You need at least 1 Dragon to fight! (You have {have})"
                           if t == "Monster" else
                           f"The {o['name']} is too powerful! Need {need} Dragons! (You have {have})")
                    self.stop(msg, x, y, cost)
                self.event(f"{o['name']} defeated!" if t == "Monster" else "BOSS SLAIN!!!", "gain", x, y)
                if t == "Boss":
                    self.flag("boss_slain")
                self.collect(o)
            else:
                self.fight(o, x, y, cost)
        elif t == "Treasure":
            self.give_reward(o.get("reward"), o)
            self.collect(o)
        elif t == "Merchant":
            if not o.get("visited_today"):
                o["visited_today"] = True
                self.counter("merchant_visits")
                self.give_reward(o.get("reward"))
                self.event(o.get("message", "The merchant pays you for your company!"), "story", x, y)
        elif t == "Seer":
            self.event(o.get("message", "The Seer smiles mysteriously."), "story", x, y)
            if o.get("reward") and not o.get("rewarded"):
                o["rewarded"] = True
                self.give_reward(o["reward"])
        elif t == "Obelisk":
            o["lit"] = not o.get("lit", False)
            self.event(f"Obelisk {o.get('bit', '')} {'glows!' if o['lit'] else 'goes dark.'}", "info", x, y)
        elif t == "Herald" and o.get("message"):
            self.event(o["message"], "story", x, y)
        return True

    # ------------------------------------------------------------------
    # Battles
    # ------------------------------------------------------------------
    def fight(self, o, x, y, cost):
        from . import api  # late import: api depends on world
        army = [dict(a) for a in self.s.get("army", []) if a["count"] > 0]
        if not army:
            self.stop(f"{o['name']} blocks the way at ({x},{y}) and you have no army! Recruit troops first.",
                      x, y, cost)
        red_ctrl, red_spell, note = api.player_battle_controllers(self)
        blue = GENERALS.get(o.get("ai", "squire"), GENERALS["squire"])
        seed = self.s.get("seed", 1) * 7919 + self.s.get("day", 1) * 31 + o["id"]
        b = Battle(army, o["army"], red_ctrl, blue, seed=seed,
                   obstacles=o.get("obstacles"),
                   red_spell=red_spell if self.rules.get("spells") else None,
                   red_mana=self.hero.get("mana", 0),
                   spell_power=1 + 0.25 * self.skill_rank("Sorcery"),
                   names={"red": self.hero.get("name", "Hero"), "blue": o["name"]})
        offense = self.skill_rank("Offense")
        if offense:
            for st in b.stacks.values():
                if st.side == "red":
                    st.attack += offense
        if note:
            b.note(note)
        result = b.run()
        self.battles.append({"name": o["name"], "x": x, "y": y, "obj_id": o["id"], "result": result})
        self.hero["mana"] = b.mana["red"] if self.rules.get("spells") else self.hero.get("mana", 0)
        lost = ", ".join(f"{n} {u}" for u, n in result["red_losses"].items()) or "nobody"
        if result["winner"] != "red":
            self.stop(f"Your army lost the battle vs {o['name']}! ({result['reason']}) "
                      f"Improve battle_turn() in my_army.py or bring more troops.", x, y, cost)
        self.s["army"] = result["red_survivors"]
        self.counter("battles_won")
        self.counter(f"won:{o['id']}")
        self.event(f"Victory vs {o['name']}! Lost: {lost}", "gain", x, y)
        if o.get("boss"):
            self.flag("boss_slain")
        self.give_reward(o.get("reward"))
        self.collect(o)

    # ------------------------------------------------------------------
    # Fog / torches (Act VI)
    # ------------------------------------------------------------------
    def is_lit(self, x, y):
        return [x, y] in self.s.get("lit", []) or (x, y) == (self.hero["x"], self.hero["y"])

    # ------------------------------------------------------------------
    # End of day
    # ------------------------------------------------------------------
    def end_day(self):
        s = self.s
        for o in s["objects"]:
            if o["type"] == "Mine" and o.get("collected") and o["id"] not in self.picked:
                self.add_res(o.get("resource", "wood"), o["value"])
        if self.rules.get("daily_gold"):
            self.add_res("gold", self.rules["daily_gold"])
        s["day"] = s.get("day", 1) + 1
        rng = random.Random(s.get("seed", 1) * 1000 + s["day"])
        hx, hy = self.hero["x"], self.hero["y"]
        for o in s["objects"]:
            o.pop("visited_today", None)
            if o.get("wander") and not o.get("collected"):
                x0, y0, x1, y1 = o["wander"]
                spots = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
                         if (x, y) != (hx, hy) and (x, y) != (o["x"], o["y"])
                         and terrain_cost(self.grid[y][x]) is not None
                         and not self.objects_at(x, y)]
                if spots:
                    o["x"], o["y"] = rng.choice(spots)
        events = self.rules.get("daily_events")
        if events:
            s["today"] = rng.choice(events)
        changes = self.rules.get("price_changes", {}).get(str(s["day"]))
        if changes:
            s.setdefault("prices", {}).update(changes)
            s.setdefault("news", []).append(self.rules.get("price_news", {}).get(str(s["day"]), ""))
        self.apply_day_layout()

    def apply_day_layout(self):
        """Some acts change the map each day (sandstorms, shifting signs...)."""
        layouts = self.rules.get("day_layouts")
        if not layouts:
            return
        today = self.s.get("today")
        base = self.s.get("base_grid")
        if base:
            self.s["grid"] = [row[:] for row in base]
            for x, y, t in self.s.get("terraformed", []):
                self.s["grid"][y][x] = t
        for x, y, t in layouts.get(today, []):
            if (x, y) != (self.hero["x"], self.hero["y"]):
                self.s["grid"][y][x] = t
        for o in self.s["objects"]:
            if o.get("show_on"):
                o["hidden"] = today not in o["show_on"]

    # ------------------------------------------------------------------
    def day_result(self):
        return {"path": [list(p) for p in self.path], "events": self.events,
                "terraforms": [list(t) for t in self.terraforms], "battles": self.battles,
                "says": self.says, "mp_used": self.mp, "error": self.error,
                "picked": self.picked}


def army_power(army):
    return sum(UNITS[a["unit"]]["cost"] * a["count"] for a in army if a["unit"] in UNITS)
