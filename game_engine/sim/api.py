"""
The player-facing API. Inside the sandbox, `import hero_api` gives you THIS
module's public functions, bound to the live World for the current day.

Each function lists the Act that unlocks it in API_UNLOCK.  Calling a locked
function raises a friendly HeroError.
"""
from collections.abc import Mapping

from .world import HeroError
from .rules import MAP_COLS, MAP_ROWS, MAX_ARMY_SLOTS, TERRAIN, UNITS, AIR, EARTH, FIRE, WATER
from . import battle as _battle

W = None  # the live World, set by the runner

API_UNLOCK = {
    # Act I
    "move_right": 1, "move_left": 1, "move_up": 1, "move_down": 1,
    "move_by": 1, "move_to": 1, "terraform": 1,
    # Act II
    "say": 2, "scout": 2, "hero": 2, "resources": 2, "answer_sphinx": 2,
    "recruit": 2, "trade": 2, "read_sign": 2, "open_gate": 2, "realm": 2, "price": 2,
    # Act III
    "today": 3, "look": 3, "has_key": 3, "is_night": 3, "set_levers": 3,
    # Act IV
    "get_map": 4, "dig": 4, "set_formation": 4,
    # Act V
    "memory": 5,
    # Act VI
    "is_open": 6, "light_torch": 6, "is_lit": 6, "travel_to": 6, "move_ring": 6, "rings": 6,
    # Act VII
    "obelisk_pattern": 7, "set_obelisks": 7, "open_vault": 7, "dye_banner": 7,
}

ACT_NAMES = {1: "Act I", 2: "Act II", 3: "Act III", 4: "Act IV", 5: "Act V",
             6: "Act VI", 7: "Act VII", 8: "Act VIII"}


def _need(name):
    if W is None:
        raise HeroError("The game engine isn't running. Start the game with run_game.py, "
                        "then save this file to see your hero move!")
    act = W.s.get("act_num", 1)
    need = API_UNLOCK.get(name, 1)
    if act < need:
        raise HeroError(f"{name}() is a spell from {ACT_NAMES.get(need, 'a later act')}. "
                        f"You'll learn it soon!")


def _int(value, what):
    if isinstance(value, bool):
        raise HeroError(f"{what} must be a whole number, not True/False.")
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise HeroError(f"{what} must be a whole number (you gave {value}). Try int() or //.")
    if isinstance(value, str):
        raise HeroError(f"{what} must be a number, but you gave text '{value}'. Did you forget int()?")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HeroError(f"{what} must be a number (you gave {type(value).__name__}).") from None


# ============================================================================
# ACT I -- movement
# ============================================================================
def move_right(steps=1):
    """Move right by 'steps' tiles."""
    _need("move_right")
    W.walk_rel(_int(steps, "steps"), 0)


def move_left(steps=1):
    """Move left by 'steps' tiles."""
    _need("move_left")
    W.walk_rel(-_int(steps, "steps"), 0)


def move_down(steps=1):
    """Move down by 'steps' tiles (negative Y)."""
    _need("move_down")
    W.walk_rel(0, -_int(steps, "steps"))


def move_up(steps=1):
    """Move up by 'steps' tiles (positive Y)."""
    _need("move_up")
    W.walk_rel(0, _int(steps, "steps"))


def move_by(dx, dy):
    """Move from where you stand by (dx, dy): positive dx is right, positive dy is up."""
    _need("move_by")
    W.walk_rel(_int(dx, "dx"), _int(dy, "dy"))


def move_to(x, y):
    """Walk to the map square (x, y): first along x, then along y."""
    _need("move_to")
    W.walk_abs(_int(x, "x"), _int(y, "y"))


def terraform(x, y, tile_type="B"):
    """Change the terrain at (x, y). 'B' = bridge, 'G' = grass."""
    _need("terraform")
    W.terraform(_int(x, "x"), _int(y, "y"), str(tile_type).upper())


# ============================================================================
# ACT II -- output, variables, types, constants, operators, casting, strings
# ============================================================================
def say(*words):
    """Shout something! It appears above your hero (people nearby may answer)."""
    _need("say")
    text = " ".join(str(w) for w in words)
    W.says.append(text)
    W.event(f'"{text}"', "say")
    for o in W.objects_at(W.hero["x"], W.hero["y"]):
        listen = o.get("listen")
        if not listen or o.get("heard"):
            continue
        want = listen["equals"]
        if text == want:
            o["heard"] = True
            W.counter(f"heard:{o['id']}")
            W.event(listen.get("reply", "They heard you!"), "story")
            W.give_reward(listen.get("reward"))
            if listen.get("open"):
                g = W.object_by_id(listen["open"])
                if g:
                    g["open"] = True
        elif text.lower() == str(want).lower():
            W.event(f"{o['name']}: \"Almost! Check your CAPITAL letters.\"", "story")
        else:
            W.event(f"{o['name']}: \"Hmm? That's not what I want to hear.\"", "story")


def scout(name):
    """Find something on the map. Returns its (x, y) position."""
    _need("scout")
    o = W.find_object(name)
    if o is None:
        raise HeroError(f"Your scouts can't find any '{name}' on the map.")
    return (o["x"], o["y"])


class _Army(list):
    pass


class ArmySlot:
    """One army slot: slot.unit (name) and slot.count."""
    __slots__ = ("unit", "count")

    def __init__(self, unit, count):
        self.unit = unit
        self.count = count

    @property
    def name(self):
        return self.unit

    def __repr__(self):
        return f"{self.count} {self.unit}"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.unit == other
        return isinstance(other, ArmySlot) and (self.unit, self.count) == (other.unit, other.count)

    __hash__ = None


class _Hero:
    """Read-only facts about your hero (hero.x, hero.gold, hero.mp ...)."""

    def __setattr__(self, key, value):
        raise HeroError(f"hero.{key} is read-only. The Archmage sees what you tried there!")

    def __repr__(self):
        if W is None:
            return "<hero>"
        return (f"<{self.name} at ({self.x}, {self.y}), {self.mp:.1f} MP left, "
                f"{self.gold} gold, day {self.day}>")

    def _w(self):
        _need("hero")
        return W

    x = property(lambda self: self._w().hero["x"], doc="Column you stand on")
    y = property(lambda self: self._w().hero["y"], doc="Row you stand on")
    name = property(lambda self: self._w().hero.get("name", "Orrin"))
    mp = property(lambda self: round(self._w().max_mp - W.mp, 2), doc="Movement points left today")
    max_mp = property(lambda self: self._w().max_mp)
    mp_used = property(lambda self: round(self._w().mp, 2))
    gold = property(lambda self: self._w().res("gold"))
    wood = property(lambda self: self._w().res("wood"))
    ore = property(lambda self: self._w().res("ore"))
    gems = property(lambda self: self._w().res("gems"))
    crystal = property(lambda self: self._w().res("crystal"))
    mana = property(lambda self: self._w().hero.get("mana", 0))
    day = property(lambda self: self._w().s.get("day", 1))
    week = property(lambda self: (self._w().s.get("day", 1) - 1) // 7 + 1)
    level = property(lambda self: self._w().s.get("level", 1))
    keys = property(lambda self: list(self._w().s.get("keys", [])))
    has_boat = property(lambda self: False)

    @property
    def army(self):
        """A list of your army slots (max 7). Each has .unit and .count."""
        return _Army(ArmySlot(a["unit"], a["count"]) for a in self._w().s.get("army", []))


hero = _Hero()


class _Resources(Mapping):
    """resources["gold"], resources["wood"] ... (read-only)."""

    def _r(self):
        _need("resources")
        return W.s.get("resources", {})

    def __getitem__(self, key):
        r = self._r()
        if key not in r:
            raise KeyError(f"No resource called '{key}'. Try: {', '.join(r)}")
        return r[key]

    def __iter__(self):
        return iter(dict(self._r()))

    def __len__(self):
        return len(self._r())

    def __repr__(self):
        return repr(dict(self._r())) if W else "<resources>"

    def __setitem__(self, key, value):
        raise HeroError("You can't just write gold into existence! Resources are read-only.")


resources = _Resources()


class _Realm:
    """The Laws of the Realm (real constants of the game world)."""
    MAP_COLS = MAP_COLS
    MAP_ROWS = MAP_ROWS
    MAX_ARMY_SLOTS = MAX_ARMY_SLOTS
    WEEK_LENGTH = 7

    @property
    def MAX_MP(self):
        _need("realm")
        return W.max_mp

    def __setattr__(self, key, value):
        raise HeroError("The Laws of the Realm can't be changed by mortals!")

    def __repr__(self):
        return "<The Laws of the Realm>"


realm = _Realm()


def price(unit):
    """How much gold one creature costs in town today."""
    _need("price")
    p = W.s.get("prices", {})
    if unit not in p:
        raise HeroError(f"The town doesn't sell '{unit}'. For sale: {', '.join(p) or 'nothing'}")
    return p[unit]


def _sphinx_check(spec, value):
    """Returns (ok, explanation)."""
    t = spec.get("type")
    actual = type(value).__name__
    if t:
        if t == "int" and (isinstance(value, bool) or not isinstance(value, int)):
            return False, f"I asked for a whole number (int). You gave me a {actual}: {value!r}"
        if t == "float" and not isinstance(value, float):
            return False, f"I asked for a number with a decimal point (float). You gave me a {actual}: {value!r}"
        if t == "str" and not isinstance(value, str):
            return False, f"I asked for text (str). You gave me a {actual}: {value!r}"
        if t == "bool" and not isinstance(value, bool):
            return False, f"I asked for True or False (bool). You gave me a {actual}: {value!r}"
        if t == "list" and not isinstance(value, list):
            return False, f"I asked for a list. You gave me a {actual}: {value!r}"
    if "greater_than" in spec and not value > spec["greater_than"]:
        return False, f"{value!r} is too small. It must be bigger than {spec['greater_than']}!"
    if spec.get("equals_hero_name") and value != W.hero.get("name"):
        return False, f"That's not your hero's name. (Hint: hero.name)"
    if "equals" in spec:
        want = spec["equals"]
        if isinstance(want, bool) or isinstance(value, bool):
            ok = value is want
        elif isinstance(want, (int, float)) and isinstance(value, (int, float)):
            ok = abs(value - want) < 1e-9
        else:
            ok = value == want
        if not ok:
            return False, f"{value!r} is not the answer. Try again!"
    if "truth_table" in spec:
        op = spec["truth_table"]
        fn = {"and": lambda a, b: a and b, "or": lambda a, b: a or b,
              "xor": lambda a, b: a != b, "nand": lambda a, b: not (a and b)}[op]
        want = [[a, b, fn(a, b)] for a in (False, True) for b in (False, True)]
        if value != want:
            return False, (f"That truth table for '{op}' is not right. I want 4 rows "
                           f"[A, B, result] in the order FF, FT, TF, TT.")
    return True, "Correct!"


def answer_sphinx(value):
    """Answer the riddle of the Sphinx you are standing on."""
    _need("answer_sphinx")
    o = W.here("Sphinx")
    if o is None:
        raise HeroError("There's no Sphinx here. Walk onto the Sphinx first!")
    riddles = o["riddles"]
    i = o.get("progress", 0)
    if i >= len(riddles):
        W.event("Sphinx: \"You have answered all my riddles already!\"", "story")
        return True
    ok, why = _sphinx_check(riddles[i], value)
    if not ok:
        raise HeroError(f"Sphinx riddle {i + 1}: {why}")
    o["progress"] = i + 1
    W.counter(f"sphinx:{o['id']}")
    W.event(f"Sphinx: \"Riddle {i + 1} correct!\"", "gain")
    if o["progress"] >= len(riddles):
        W.counter(f"sphinx_done:{o['id']}")
        W.give_reward(o.get("reward"))
        W.event("Sphinx: \"You are wise, young hero.\"", "story")
    return True


def recruit(unit, count):
    """Hire creatures while standing in a Town. Example: recruit("Pikeman", 10)"""
    _need("recruit")
    town = W.here("Town")
    if town is None:
        raise HeroError("You can only recruit while standing in a Town.")
    count = _int(count, "count")
    if count <= 0:
        raise HeroError("You must recruit at least 1 creature.")
    prices = W.s.get("prices", {})
    if unit not in prices:
        raise HeroError(f"This town doesn't train '{unit}'. For sale: {', '.join(prices)}")
    cost = prices[unit] * count
    extra = {k: v * count for k, v in UNITS.get(unit, {}).get("cost_extra", {}).items()}
    if W.res("gold") < cost:
        raise HeroError(f"{count} {unit} cost {cost} gold, but you only have {W.res('gold')}. "
                        f"(Max you can afford: {W.res('gold') // prices[unit]})")
    for r, need in extra.items():
        if W.res(r) < need:
            raise HeroError(f"{count} {unit} also need {need} {r}, but you have {W.res(r)}.")
    max_afford = W.res("gold") // prices[unit]
    for r, per in UNITS.get(unit, {}).get("cost_extra", {}).items():
        max_afford = min(max_afford, W.res(r) // per)
    W.add_units(unit, count)
    W.add_res("gold", -cost)
    for r, need in extra.items():
        W.add_res(r, -need)
    W.counter(f"recruited:{unit}", count)
    if count == max_afford:
        key = f"max_recruit_day:{W.s.get('day', 1)}"
        if not W.s.get("counters", {}).get(key):
            W.counter(key)
            W.counter("max_recruit_days")
    W.event(f"Recruited {count} {unit} for {cost} gold!", "gain")


def trade(give, get, amount):
    """Trade at a Market. Example: trade("wood", "ore", 10)"""
    _need("trade")
    m = W.here("Market")
    if m is None:
        raise HeroError("You can only trade while standing on a Market.")
    amount = _int(amount, "amount")
    rate = m.get("rates", {}).get(f"{give}:{get}")
    if rate is None:
        raise HeroError(f"This market doesn't trade {give} for {get}. "
                        f"Offers: {', '.join(k.replace(':', ' -> ') for k in m.get('rates', {}))}")
    if amount <= 0 or amount % rate != 0:
        raise HeroError(f"The merchant trades in bundles of {rate} {give}. {amount} isn't a multiple of {rate}! "
                        f"(Hint: the % operator tells you the leftover.)")
    if W.res(give) < amount:
        raise HeroError(f"You only have {W.res(give)} {give}.")
    W.add_res(give, -amount)
    W.add_res(get, amount // rate)
    W.counter(f"traded:{give}:{get}", amount // rate)
    W.event(f"Traded {amount} {give} for {amount // rate} {get}.", "gain")


def read_sign():
    """Read the sign you are standing on. Always returns TEXT (a str)."""
    _need("read_sign")
    for o in W.objects_at(W.hero["x"], W.hero["y"]):
        if "text" in o:
            W.counter(f"read:{o['id']}")
            return str(o["text"])
    raise HeroError("There's no sign here to read. Walk onto a sign first!")


def open_gate(answer):
    """Open the gate next to you. Each gate wants a different answer!"""
    _need("open_gate")
    g = W.adjacent_object("Gate")
    if g is None:
        raise HeroError("There's no gate next to you. Stand right beside a gate.")
    if g.get("open"):
        W.event(f"The {g['name']} is already open.", "info")
        return True
    kind = g.get("kind", "password")
    want = g.get("answer")
    if kind == "password":
        if not isinstance(answer, str):
            raise HeroError(f"The {g['name']} wants a password (text), not a {type(answer).__name__}. "
                            f"Did you forget str()?")
        if answer != want:
            if answer.lower() == str(want).lower():
                raise HeroError(f"The {g['name']} rumbles: \"Close! Check the CAPITAL letters.\"")
            raise HeroError(f"The {g['name']} stays shut. '{answer}' is not the password.")
    elif kind in ("toll", "number"):
        if isinstance(answer, str):
            raise HeroError(f"The {g['name']} wants a NUMBER, but you gave text '{answer}'. "
                            f"Did you forget int() or float()?")
        if isinstance(answer, bool) or not isinstance(answer, (int, float)):
            raise HeroError(f"The {g['name']} wants a number, not a {type(answer).__name__}.")
        if abs(answer - want) > 1e-9:
            raise HeroError(f"The {g['name']} stays shut. {answer} is not right.")
        if kind == "toll":
            if W.res("gold") < want:
                raise HeroError(f"The toll is {want} gold but you only have {W.res('gold')}.")
            W.add_res("gold", -int(want))
    else:
        raise HeroError(f"The {g['name']} doesn't open with words. It needs a key.")
    g["open"] = True
    W.counter(f"opened:{g['id']}")
    W.event(f"The {g['name']} swings open!", "gain", g["x"], g["y"])
    W.give_reward(g.get("reward"))
    return True


# ============================================================================
# ACT III -- decisions
# ============================================================================
def today():
    """What's happening today? e.g. 'clear', 'sandstorm', 'festival'"""
    _need("today")
    return W.s.get("today", "clear")


def look(x, y):
    """What's at (x, y)? Returns an object type like 'Monster'/'Gold', else the terrain letter."""
    _need("look")
    x, y = _int(x, "x"), _int(y, "y")
    if not W.in_map(x, y):
        return None
    if W.rules.get("fog") and not W.is_lit(x, y):
        return "?"
    o = W.object_at(x, y)
    if o is not None:
        return o["type"]
    return W.grid[y][x]


def has_key(color):
    """True if you carry the key of that color."""
    _need("has_key")
    return str(color) in W.s.get("keys", [])


def is_night():
    """True when it's night (every even day in lands with a night cycle)."""
    _need("is_night")
    return W.is_night()


def set_levers(a, b, c):
    """Pull the three levers of a Shrine (True = up, False = down)."""
    _need("set_levers")
    o = W.here("Shrine")
    if o is None:
        raise HeroError("There are no levers here. Stand on a Shrine.")
    for name, v in (("a", a), ("b", b), ("c", c)):
        if not isinstance(v, bool):
            raise HeroError(f"Lever {name} only understands True or False (you gave {v!r}).")
    result = bool(eval(o["rule"], {"__builtins__": {}}, {"A": a, "B": b, "C": c}))  # noqa: S307
    W.counter(f"levers:{o['id']}")
    if result != o.get("want", True):
        raise HeroError(f"The shrine stays dark. With A={a}, B={b}, C={c} the rule "
                        f"'{o['rule']}' is {result}, but it must be {o.get('want', True)}.")
    if not o.get("solved"):
        o["solved"] = True
        W.counter(f"solved:{o['id']}")
        W.event(f"The {o['name']} lights up!", "gain")
        W.give_reward(o.get("reward"))
    return True


# ============================================================================
# ACT IV -- lists & loops
# ============================================================================
def get_map():
    """The whole map as a list of rows: world[y][x] is a terrain letter."""
    _need("get_map")
    return [row[:] for row in W.grid]


def dig():
    """Dig for treasure where you stand (costs 2 MP). Returns True if you found something."""
    _need("dig")
    hx, hy = W.hero["x"], W.hero["y"]
    if W.mp + 2 > W.max_mp + 1e-9:
        W.stop(f"Not enough MP to dig! ({W.max_mp - W.mp:.1f} left, digging costs 2)")
    W.mp += 2
    W.path.append((hx, hy, W.mp, True))
    dug = W.s.setdefault("dug", [])
    if [hx, hy] not in dug:
        dug.append([hx, hy])
    W.counter("digs")
    for o in W.objects_at(hx, hy, include_hidden=True):
        if o["type"] == "DigSite":
            o["collected"] = True
            W.counter(f"found:{o['id']}")
            W.event(o.get("message", "You found buried treasure!"), "gain")
            W.give_reward(o.get("reward"))
            return True
    W.event("Just sand...", "info")
    return False


def set_formation(order):
    """Reorder your army. order = list of unit names, e.g. ["Archer", "Pikeman"]"""
    _need("set_formation")
    if not isinstance(order, (list, tuple)):
        raise HeroError("set_formation needs a list of unit names, like ['Archer', 'Pikeman'].")
    army = W.s.get("army", [])
    names = [getattr(n, "unit", n) for n in order]
    if sorted(names) != sorted(a["unit"] for a in army):
        raise HeroError(f"Your formation must list each of your units exactly once: "
                        f"{[a['unit'] for a in army]}")
    by_name = {a["unit"]: a for a in army}
    W.s["army"] = [by_name[n] for n in names]
    W.counter("formations")
    W.event("Formation set: " + ", ".join(names), "info")


# ============================================================================
# ACT V -- memory (persists between turns, unlike normal variables)
# ============================================================================
class _Memory(dict):
    """A notebook that survives between days: memory["visits"] = 3"""


memory = _Memory()


# ============================================================================
# ACT VI -- the underground (recursion)
# ============================================================================
def is_open(x, y):
    """True if (x, y) is open cave floor (not rock, not off the map)."""
    _need("is_open")
    x, y = _int(x, "x"), _int(y, "y")
    return W.in_map(x, y) and W.walkable(x, y)


def is_lit(x, y):
    """True if a torch already burns at (x, y)."""
    _need("is_lit")
    return [_int(x, "x"), _int(y, "y")] in W.s.get("lit", [])


def light_torch(x, y):
    """Light a torch at (x, y). It must be open floor next to a lit tile (or your hero)."""
    _need("light_torch")
    x, y = _int(x, "x"), _int(y, "y")
    lit = W.s.setdefault("lit", [])
    if [x, y] in lit:
        return False
    if not (W.in_map(x, y) and W.walkable(x, y)):
        raise HeroError(f"You can't light a torch inside solid rock at ({x}, {y}). Check is_open() first!")
    near = any([x + dx, y + dy] in lit or (x + dx, y + dy) == (W.hero["x"], W.hero["y"])
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) or (x, y) == (W.hero["x"], W.hero["y"])
    if not near:
        raise HeroError(f"Torch at ({x}, {y}) is too far from the light. Light tiles next to lit ones!")
    if len(lit) > 400:
        raise HeroError("You've run out of torches!")
    lit.append([x, y])
    W.counter("torches")
    W.events.append({"text": "", "kind": "torch", "x": x, "y": y})
    for o in W.objects_at(x, y, include_hidden=True):
        if o.get("hidden") and o.get("reveal_on_light"):
            o["hidden"] = False
            W.event(f"The light reveals: {o['name']}!", "gain", x, y)
    return True


def travel_to(x, y):
    """(Expert Pathfinding) Walk the shortest route to (x, y) through lit tunnels."""
    _need("travel_to")
    if not W.has_flag("travel_unlocked"):
        raise HeroError("You need Expert Pathfinding to use travel_to(). Light up the whole labyrinth first!")
    x, y = _int(x, "x"), _int(y, "y")
    path = W.find_path(x, y)
    if path is None:
        raise HeroError(f"No lit path leads to ({x}, {y}).")
    for px, py in path[1:]:
        W.step_to(px, py)


def _hanoi():
    o = W.here("RingShrine")
    if o is None:
        raise HeroError("Stand on the Ring Shrine to move magic rings.")
    return o


def move_ring(source, target):
    """Move the top ring from obelisk source to target ('A', 'B' or 'C')."""
    _need("move_ring")
    o = _hanoi()
    pegs = o["pegs"]
    s, t = str(source).upper(), str(target).upper()
    if s not in pegs or t not in pegs:
        raise HeroError("Obelisks are called 'A', 'B' and 'C'.")
    if not pegs[s]:
        raise HeroError(f"Obelisk {s} has no rings to move!")
    ring = pegs[s][-1]
    if pegs[t] and pegs[t][-1] < ring:
        raise HeroError(f"Ring {ring} is bigger than ring {pegs[t][-1]} on obelisk {t}. "
                        f"A bigger ring can't sit on a smaller one!")
    pegs[t].append(pegs[s].pop())
    o["moves"] = o.get("moves", 0) + 1
    if o["moves"] > 5000:
        raise HeroError("Too many ring moves! The obelisks are exhausted.")
    W.events.append({"text": f"{s}->{t}", "kind": "ring", "x": o["x"], "y": o["y"]})
    goal = o.get("goal", "C")
    if len(pegs[goal]) == o["n"] and not o.get("solved"):
        o["solved"] = True
        W.counter(f"hanoi:{o['n']}")
        W.counter(f"solved:{o['id']}")
        W.event(f"All {o['n']} rings on obelisk {goal} in {o['moves']} moves!", "gain")
        W.give_reward(o.get("reward"))


def rings():
    """The rings on each obelisk, e.g. {'A': [3, 2, 1], 'B': [], 'C': []}"""
    _need("rings")
    o = _hanoi()
    return {k: list(v) for k, v in o["pegs"].items()}


# ============================================================================
# ACT VII -- bits, bytes, binary, hex
# ============================================================================
def _obelisks():
    obs = [o for o in W.s["objects"] if o["type"] == "Obelisk" and not o.get("hidden")]
    return sorted(obs, key=lambda o: -o.get("bit", 0))


def obelisk_pattern():
    """The 8 obelisks as text, highest bit first: e.g. '10110000'"""
    _need("obelisk_pattern")
    return "".join("1" if o.get("lit") else "0" for o in _obelisks())


def set_obelisks(bits):
    """At the Altar: light the obelisks with a pattern like '11001000'."""
    _need("set_obelisks")
    if W.here("Altar") is None:
        raise HeroError("Only the Obelisk Altar can control all obelisks. Stand on it!")
    if not isinstance(bits, str):
        raise HeroError(f"set_obelisks wants text like '10101101', not a {type(bits).__name__}. "
                        f"(Hint: bin() gives '0b...' text.)")
    obs = _obelisks()
    if len(bits) != len(obs) or any(ch not in "01" for ch in bits):
        raise HeroError(f"The pattern must be exactly {len(obs)} characters of 0 and 1 (you gave '{bits}').")
    for o, ch in zip(obs, bits):
        o["lit"] = ch == "1"
    W.counter("obelisks_set")
    W.event(f"The obelisks shine: {bits}", "gain")


def open_vault(code):
    """Enter a code into the Dwarven Vault you are standing on."""
    _need("open_vault")
    v = W.here("Vault")
    if v is None:
        raise HeroError("There's no vault here.")
    if v.get("open"):
        return True
    if isinstance(code, str):
        raise HeroError(f"The vault's dial only takes numbers. You gave text '{code}'. Try int(text, 2)!")
    code = _int(code, "code")
    if v.get("needs_pattern"):
        pattern = obelisk_pattern()
        if int(pattern, 2) != v["answer"]:
            raise HeroError(f"The vault wants the obelisks to show {v['answer']} in binary. "
                            f"They show {pattern} = {int(pattern, 2)}.")
    if code != v["answer"]:
        raise HeroError(f"The dial clicks... wrong code ({code}).")
    v["open"] = True
    W.counter(f"opened:{v['id']}")
    W.event(f"The {v['name']} opens!", "gain")
    W.give_reward(v.get("reward"))
    return True


def dye_banner(color):
    """Dye the banner you stand on. color is hex text like '#FF8800'."""
    _need("dye_banner")
    b = W.here("Banner")
    if b is None:
        raise HeroError("There's no banner pole here.")
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        raise HeroError(f"Banner colors look like '#RRGGBB' (7 characters). You gave {color!r}.")
    try:
        int(color[1:], 16)
    except ValueError:
        raise HeroError(f"'{color}' has letters that aren't hex digits (0-9, A-F).") from None
    if color.upper() != b["answer"].upper():
        r, g, bl = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        raise HeroError(f"The dye makes red={r}, green={g}, blue={bl}. That's not the color the crystals want.")
    b["dyed"] = True
    W.counter(f"dyed:{b['id']}")
    W.event(f"The banner glows {color.upper()}!", "gain")
    W.give_reward(b.get("reward"))
    return True


# ============================================================================
# Battle helpers for my_army.py  (import from battle_api)
# ============================================================================
BATTLE_EXPORTS = {
    "attack": _battle.attack, "shoot": _battle.shoot, "move": _battle.move,
    "move_toward": _battle.move_toward, "defend": _battle.defend, "wait": _battle.wait,
    "cast": _battle.cast, "AIR": AIR, "EARTH": EARTH, "FIRE": FIRE, "WATER": WATER,
}

PLAYER_ARMY = {"module": None, "error": None, "loader": None}


def player_battle_controllers(world):
    """Return (battle_turn, hero_spell, note) for the red side."""
    from .generals import squire
    loader = PLAYER_ARMY.get("loader")
    mod = loader() if loader else None
    if mod is None:
        return squire, None, "No my_army.py found - your troops fight on instinct (they charge!)."
    turn = getattr(mod, "battle_turn", None)
    if not callable(turn):
        return squire, None, "my_army.py has no battle_turn(me, battle) - your troops charge on instinct."
    return turn, getattr(mod, "hero_spell", None), None


HERO_EXPORTS = [n for n in API_UNLOCK]

__all__ = HERO_EXPORTS + ["TERRAIN"]
