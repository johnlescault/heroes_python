"""
Square-grid battle engine (Heroes 3 inspired) -- pure Python, deterministic.

The engine asks a *controller* function for every stack's turn:

    def battle_turn(me, battle):        # me = StackView, battle = BattleView
        return attack(battle.enemies[0])

Controllers return an action dict built by the helpers at the bottom of this
file (attack, shoot, move, move_toward, defend, wait).  The full fight is
recorded as a list of events so the pygame view can replay it.
"""
import random
from collections import deque
from dataclasses import dataclass

from .rules import UNITS, SPELLS, BF_COLS, BF_ROWS

ROUND_LIMIT = 30
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class BattleCodeError(Exception):
    """Raised when a controller crashes; carries the side that crashed."""

    def __init__(self, side, original):
        super().__init__(str(original))
        self.side = side
        self.original = original


# ----------------------------------------------------------------------------
# Read-only views handed to player code
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class StackView:
    id: int
    name: str
    side: str            # "red" or "blue"
    count: int
    hp: int              # total hit points of the whole stack
    top_hp: int          # hit points of the top creature
    unit_hp: int         # max hit points of one creature
    attack: int
    defense: int
    dmg_min: int
    dmg_max: int
    speed: int
    x: int
    y: int
    is_shooter: bool
    shots: int
    is_flying: bool
    immune: int
    is_defending: bool
    retaliations: int

    def __repr__(self):
        return f"<{self.count} {self.name} at ({self.x},{self.y}) hp={self.hp}>"


class BattleView:
    """What a controller is allowed to see. Everything returned is a copy."""

    def __init__(self, battle, side):
        self._b = battle
        self.side = side
        self.round = battle.round
        self.allies = [s.view() for s in battle.alive(side)]
        self.enemies = [s.view() for s in battle.alive(battle.other(side))]
        self.mana = battle.mana[side]
        self.cols = BF_COLS
        self.rows = BF_ROWS

    def __repr__(self):
        return f"<Battle round {self.round}: {len(self.allies)} allies vs {len(self.enemies)} enemies>"

    @staticmethod
    def distance(a, b):
        """Manhattan distance between two stacks (or (x, y) tuples)."""
        ax, ay = (a.x, a.y) if hasattr(a, "x") else a
        bx, by = (b.x, b.y) if hasattr(b, "x") else b
        return abs(ax - bx) + abs(ay - by)

    def adjacent_enemies(self, me):
        return [e for e in self.enemies if self.distance(me, e) == 1]

    def can_shoot(self, me):
        return bool(me.is_shooter and me.shots > 0 and not self.adjacent_enemies(me))

    def tile(self, x, y):
        """'.' open, '#' obstacle, 'S' a stack stands there, None off the field."""
        if not (0 <= x < BF_COLS and 0 <= y < BF_ROWS):
            return None
        if (x, y) in self._b.obstacles:
            return "#"
        if self._b.stack_at(x, y):
            return "S"
        return "."

    def reachable(self, me):
        """List of (x, y) tiles the stack could move to this turn."""
        st = self._b.stacks[me.id]
        return sorted(self._b.reachable_tiles(st).keys())

    def weakest(self, stacks=None):
        stacks = self.enemies if stacks is None else stacks
        return min(stacks, key=lambda s: s.hp) if stacks else None

    def nearest(self, me, stacks=None):
        stacks = self.enemies if stacks is None else stacks
        return min(stacks, key=lambda s: self.distance(me, s)) if stacks else None


# ----------------------------------------------------------------------------
# Internal mutable stack
# ----------------------------------------------------------------------------
class Stack:
    def __init__(self, sid, side, unit, count, x, y):
        info = UNITS[unit]
        self.id = sid
        self.side = side
        self.name = unit
        self.count = int(count)
        self.unit_hp = info["hp"]
        self.top_hp = info["hp"]
        self.attack = info["attack"]
        self.defense = info["defense"]
        self.dmg = info["dmg"]
        self.speed = info["speed"]
        self.shots = info["shots"]
        self.is_shooter = info["shots"] > 0
        self.flying = info["flying"]
        self.max_ret = info.get("retaliations", 1)
        self.ret_left = self.max_ret
        self.immune = info.get("immune", 0)
        self.hits_all_adjacent = info.get("hits_all_adjacent", False)
        self.no_retaliation_against = info.get("no_retaliation_against", False)
        self.x, self.y = x, y
        self.defending = False
        self.start_count = self.count

    @property
    def alive(self):
        return self.count > 0

    @property
    def total_hp(self):
        return 0 if self.count <= 0 else (self.count - 1) * self.unit_hp + self.top_hp

    def view(self):
        return StackView(
            id=self.id, name=self.name, side=self.side, count=self.count, hp=self.total_hp,
            top_hp=self.top_hp, unit_hp=self.unit_hp, attack=self.attack,
            defense=self.defense, dmg_min=self.dmg[0], dmg_max=self.dmg[1],
            speed=self.speed, x=self.x, y=self.y, is_shooter=self.is_shooter,
            shots=self.shots, is_flying=self.flying, immune=self.immune,
            is_defending=self.defending, retaliations=self.ret_left)

    def snap(self):
        return {"count": self.count, "top_hp": self.top_hp, "x": self.x, "y": self.y,
                "hp": self.total_hp, "shots": self.shots, "defending": self.defending}

    def take_damage(self, dmg):
        """Apply damage; returns number of creatures killed."""
        before = self.count
        total = self.total_hp - dmg
        if total <= 0:
            self.count = 0
            self.top_hp = 0
        else:
            self.count = (total + self.unit_hp - 1) // self.unit_hp
            self.top_hp = total - (self.count - 1) * self.unit_hp
        return before - self.count


def formation_rows(n):
    if n <= 0:
        return []
    if n <= 6:
        start = 5 - (n - 1)
        return [start + 2 * i for i in range(n)]
    return [0, 2, 4, 5, 6, 8, 10][:n]


# ----------------------------------------------------------------------------
# Battle
# ----------------------------------------------------------------------------
class Battle:
    def __init__(self, red_army, blue_army, red_ctrl, blue_ctrl, seed=0,
                 obstacles=None, red_spell=None, blue_spell=None,
                 red_mana=0, blue_mana=0, spell_power=1, names=None,
                 round_limit=ROUND_LIMIT, max_notes=400):
        self.rng = random.Random(seed)
        self.ctrl = {"red": red_ctrl, "blue": blue_ctrl}
        self.spell_ctrl = {"red": red_spell, "blue": blue_spell}
        self.mana = {"red": red_mana, "blue": blue_mana}
        self.spell_power = spell_power
        self.names = names or {"red": "Your army", "blue": "Enemy"}
        self.round_limit = round_limit
        self.round = 0
        self.events = []
        self.notes = 0
        self.max_notes = max_notes
        self.stacks = {}
        sid = 0
        for side, army, col in (("red", red_army, 0), ("blue", blue_army, BF_COLS - 1)):
            army = [a for a in army if a and a.get("count", 0) > 0][:7]
            for row, entry in zip(formation_rows(len(army)), army):
                self.stacks[sid] = Stack(sid, side, entry["unit"], entry["count"], col, row)
                sid += 1
        if obstacles is None:
            obstacles = self._random_obstacles()
        occupied = {(s.x, s.y) for s in self.stacks.values()}
        self.obstacles = {tuple(o) for o in obstacles if tuple(o) not in occupied}

    # -- helpers ---------------------------------------------------------
    def _random_obstacles(self):
        obs = set()
        for _ in range(self.rng.randint(2, 5)):
            obs.add((self.rng.randint(4, 10), self.rng.randint(1, 9)))
        return obs

    @staticmethod
    def other(side):
        return "blue" if side == "red" else "red"

    def alive(self, side=None):
        return [s for s in self.stacks.values() if s.alive and (side is None or s.side == side)]

    def stack_at(self, x, y):
        for s in self.stacks.values():
            if s.alive and s.x == x and s.y == y:
                return s
        return None

    def note(self, text, sid=None):
        if self.notes < self.max_notes:
            self.events.append({"t": "note", "id": sid, "text": str(text)[:200]})
            self.notes += 1

    def free(self, x, y, ignore=None):
        if not (0 <= x < BF_COLS and 0 <= y < BF_ROWS):
            return False
        if (x, y) in self.obstacles:
            return False
        s = self.stack_at(x, y)
        return s is None or s is ignore

    def reachable_tiles(self, st):
        """BFS: {(x, y): path_list} for tiles reachable this turn (excluding start)."""
        start = (st.x, st.y)
        prev = {start: None}
        dist = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            if dist[cur] >= st.speed:
                continue
            for dx, dy in DIRS:
                nx, ny = cur[0] + dx, cur[1] + dy
                if not (0 <= nx < BF_COLS and 0 <= ny < BF_ROWS) or (nx, ny) in dist:
                    continue
                passable = self.free(nx, ny, ignore=st)
                if not passable and not st.flying:
                    continue
                dist[(nx, ny)] = dist[cur] + 1
                prev[(nx, ny)] = cur
                q.append((nx, ny))
        out = {}
        for tile in dist:
            if tile == start or not self.free(tile[0], tile[1], ignore=st):
                continue
            path, t = [], tile
            while t is not None:
                path.append(t)
                t = prev[t]
            out[tile] = list(reversed(path))
        return out

    def full_path_len(self, st, goal_tiles):
        """Unlimited-range BFS distance from stack to any goal tile (walkers respect blockers)."""
        start = (st.x, st.y)
        goals = set(goal_tiles)
        if start in goals:
            return 0, start
        seen = {start}
        q = deque([(start, 0)])
        while q:
            cur, d = q.popleft()
            for dx, dy in DIRS:
                nx, ny = cur[0] + dx, cur[1] + dy
                if (nx, ny) in seen or not (0 <= nx < BF_COLS and 0 <= ny < BF_ROWS):
                    continue
                if not st.flying and not self.free(nx, ny, ignore=st):
                    continue
                seen.add((nx, ny))
                if (nx, ny) in goals and self.free(nx, ny, ignore=st):
                    return d + 1, (nx, ny)
                q.append(((nx, ny), d + 1))
        return None, None

    # -- damage -------------------------------------------------------------
    def roll_damage(self, att, dfn, ranged=False, melee_penalty=False):
        lo, hi = att.dmg
        base = att.count * self.rng.randint(lo, hi)
        a, d = att.attack, dfn.defense
        if dfn.defending:
            d = int(d * 1.3)
        if a > d:
            base *= 1 + 0.05 * min(a - d, 60)
        else:
            base *= 1 - 0.025 * min(d - a, 28)
        if melee_penalty:
            base *= 0.5
        return max(1, int(base))

    def strike(self, att, dfn, kind):
        melee_penalty = kind != "shoot" and att.is_shooter
        dmg = self.roll_damage(att, dfn, ranged=(kind == "shoot"), melee_penalty=melee_penalty)
        kills = dfn.take_damage(dmg)
        self.events.append({"t": "retaliate" if kind == "retaliate" else "attack",
                            "id": att.id, "target": dfn.id, "ranged": kind == "shoot",
                            "damage": dmg, "kills": kills,
                            "after": {dfn.id: dfn.snap(), att.id: att.snap()}})
        if not dfn.alive:
            self.events.append({"t": "death", "id": dfn.id})

    def melee(self, att, dfn):
        targets = [dfn]
        if att.hits_all_adjacent:
            for s in self.alive(self.other(att.side)):
                if s is not dfn and abs(s.x - att.x) + abs(s.y - att.y) == 1:
                    targets.append(s)
        for t in targets:
            if t.alive:
                self.strike(att, t, "attack")
        if (dfn.alive and dfn.ret_left > 0 and att.alive
                and not att.no_retaliation_against):
            dfn.ret_left -= 1
            self.strike(dfn, att, "retaliate")

    # -- actions -------------------------------------------------------------
    def do_move(self, st, path):
        if len(path) < 2:
            return
        st.x, st.y = path[-1]
        self.events.append({"t": "move", "id": st.id, "path": [list(p) for p in path],
                            "after": {st.id: st.snap()}})

    def find_target(self, st, target, verb):
        tid = getattr(target, "id", target)
        tgt = self.stacks.get(tid) if isinstance(tid, int) else None
        if tgt is None or not tgt.alive:
            self.note(f"{st.name}: {verb} target is not a living stack.", st.id)
            return None
        if tgt.side == st.side:
            self.note(f"{st.name} refuses to {verb} its own allies!", st.id)
            return None
        return tgt

    def act_attack(self, st, target):
        tgt = self.find_target(st, target, "attack")
        if tgt is None:
            return self.act_defend(st, auto=True)
        if abs(st.x - tgt.x) + abs(st.y - tgt.y) == 1:
            return self.melee(st, tgt)
        adj = [(tgt.x + dx, tgt.y + dy) for dx, dy in DIRS]
        reach = self.reachable_tiles(st)
        options = [(len(reach[t]), t) for t in adj if t in reach]
        if options:
            options.sort()
            self.do_move(st, reach[options[0][1]])
            return self.melee(st, tgt)
        # Can't reach this turn -> march toward it
        self.act_move_toward(st, tgt, quiet=True)

    def act_move_toward(self, st, target, quiet=False):
        tgt = self.find_target(st, target, "move toward") if not quiet else target
        if tgt is None:
            return self.act_defend(st, auto=True)
        adj = [(tgt.x + dx, tgt.y + dy) for dx, dy in DIRS]
        reach = self.reachable_tiles(st)
        if not reach:
            return self.act_defend(st, auto=True)
        best, best_score = None, None
        for tile, path in reach.items():
            d = min(abs(tile[0] - a[0]) + abs(tile[1] - a[1]) for a in adj)
            score = (d, len(path))
            if best_score is None or score < best_score:
                best, best_score = tile, score
        here = min(abs(st.x - a[0]) + abs(st.y - a[1]) for a in adj)
        if best is None or best_score[0] >= here:
            return self.act_defend(st, auto=True)
        self.do_move(st, reach[best])

    def act_shoot(self, st, target):
        tgt = self.find_target(st, target, "shoot")
        if tgt is None:
            return self.act_defend(st, auto=True)
        if not st.is_shooter:
            self.note(f"{st.name} has no bow! Attacking instead.", st.id)
            return self.act_attack(st, tgt)
        if st.shots <= 0:
            self.note(f"{st.name} is out of arrows! Attacking instead.", st.id)
            return self.act_attack(st, tgt)
        if any(abs(e.x - st.x) + abs(e.y - st.y) == 1 for e in self.alive(self.other(st.side))):
            self.note(f"{st.name} can't shoot with an enemy next to it! Fighting in melee.", st.id)
            return self.act_attack(st, tgt)
        st.shots -= 1
        self.strike(st, tgt, "shoot")

    def act_move(self, st, x, y):
        reach = self.reachable_tiles(st)
        if (x, y) == (st.x, st.y):
            return self.act_defend(st, auto=True)
        if (x, y) not in reach:
            self.note(f"{st.name} can't reach ({x}, {y}) this turn (speed {st.speed}).", st.id)
            return self.act_defend(st, auto=True)
        self.do_move(st, reach[(x, y)])

    def act_defend(self, st, auto=False):
        st.defending = True
        self.events.append({"t": "defend", "id": st.id, "auto": auto, "after": {st.id: st.snap()}})

    def execute(self, st, action):
        if action is None:
            self.note(f"{st.name}: battle_turn returned nothing (did you forget 'return'?). Defending.", st.id)
            return self.act_defend(st, auto=True)
        if not isinstance(action, dict) or "type" not in action:
            self.note(f"{st.name}: '{action!r}' is not a battle action. Use attack(), shoot(), move()...", st.id)
            return self.act_defend(st, auto=True)
        kind = action["type"]
        if kind == "attack":
            return self.act_attack(st, action.get("target"))
        if kind == "shoot":
            return self.act_shoot(st, action.get("target"))
        if kind == "move":
            return self.act_move(st, int(action.get("x", st.x)), int(action.get("y", st.y)))
        if kind == "move_toward":
            return self.act_move_toward(st, action.get("target"))
        if kind == "defend":
            return self.act_defend(st)
        self.note(f"{st.name}: unknown action '{kind}'. Defending.", st.id)
        return self.act_defend(st, auto=True)

    # -- spells --------------------------------------------------------------
    def cast(self, side, action):
        if not action:
            return
        if not isinstance(action, dict) or action.get("type") != "cast":
            self.note("hero_spell must return cast(spell, target) or None.")
            return
        name = action.get("spell")
        spell = SPELLS.get(name)
        if spell is None:
            self.note(f"Unknown spell '{name}'. Known: {', '.join(SPELLS)}")
            return
        if self.mana[side] < spell["mana"]:
            self.note(f"Not enough mana for {name} ({self.mana[side]}/{spell['mana']}).")
            return
        tid = getattr(action.get("target"), "id", action.get("target"))
        tgt = self.stacks.get(tid) if isinstance(tid, int) else None
        if tgt is None or not tgt.alive:
            self.note(f"{name}: target is not a living stack.")
            return
        self.mana[side] -= spell["mana"]
        if spell.get("buff_defense"):
            tgt.defense += spell["buff_defense"]
            self.events.append({"t": "spell", "side": side, "spell": name, "target": tgt.id,
                                "damage": 0, "kills": 0, "immune": False,
                                "after": {tgt.id: tgt.snap()}})
            return
        targets = [tgt]
        if spell["area"]:
            targets += [s for s in self.alive() if s is not tgt
                        and abs(s.x - tgt.x) <= 1 and abs(s.y - tgt.y) <= 1]
        for t in targets:
            if t.immune & spell["school"]:
                self.events.append({"t": "spell", "side": side, "spell": name, "target": t.id,
                                    "damage": 0, "kills": 0, "immune": True,
                                    "after": {t.id: t.snap()}})
                continue
            dmg = int(spell["damage"] * self.spell_power)
            kills = t.take_damage(dmg)
            self.events.append({"t": "spell", "side": side, "spell": name, "target": t.id,
                                "damage": dmg, "kills": kills, "immune": False,
                                "after": {t.id: t.snap()}})
            if not t.alive:
                self.events.append({"t": "death", "id": t.id})

    # -- main loop -----------------------------------------------------------
    def call(self, side, fn, *args):
        try:
            return fn(*args)
        except BattleCodeError:
            raise
        except Exception as e:  # noqa: BLE001 - player code may raise anything
            raise BattleCodeError(side, e) from e

    def run(self):
        self.events.append({
            "t": "start", "names": self.names,
            "obstacles": sorted([list(o) for o in self.obstacles]),
            "stacks": [{"id": s.id, "side": s.side, "name": s.name, "count": s.count,
                        "x": s.x, "y": s.y, "hp": s.total_hp, "top_hp": s.top_hp,
                        "unit_hp": s.unit_hp, "shooter": s.is_shooter, "flying": s.flying}
                       for s in self.stacks.values()]})
        winner, reason = None, ""
        while winner is None:
            self.round += 1
            if self.round > self.round_limit:
                winner, reason = self._decide_by_strength()
                break
            self.events.append({"t": "round", "n": self.round})
            for s in self.alive():
                s.ret_left = s.max_ret
            for side in ("red", "blue"):
                fn = self.spell_ctrl.get(side)
                if fn and self.alive(side) and self.alive(self.other(side)):
                    self.cast(side, self.call(side, fn, BattleView(self, side)))
            order = sorted(self.alive(), key=lambda s: (-s.speed, (s.side == "blue") ^ (self.round % 2 == 0), s.id))
            queue = deque(order)
            waited = set()
            while queue:
                st = queue.popleft()
                if not st.alive:
                    continue
                if not self.alive("red") or not self.alive("blue"):
                    break
                st.defending = False
                action = self.call(st.side, self.ctrl[st.side], st.view(), BattleView(self, st.side))
                if isinstance(action, dict) and action.get("type") == "wait":
                    if st.id in waited:
                        self.act_defend(st, auto=True)
                    else:
                        waited.add(st.id)
                        self.events.append({"t": "wait", "id": st.id})
                        queue.append(st)
                    continue
                self.execute(st, action)
            if not self.alive("blue"):
                winner, reason = "red", "All enemy stacks defeated"
            elif not self.alive("red"):
                winner, reason = "blue", "All your stacks were defeated"
        self.events.append({"t": "end", "winner": winner, "reason": reason, "rounds": self.round})
        return self.result(winner, reason)

    def _decide_by_strength(self):
        def value(side):
            return sum(s.count * UNITS[s.name]["cost"] for s in self.alive(side))
        r, b = value("red"), value("blue")
        if r > b:
            return "red", f"Time ran out ({self.round_limit} rounds) - red army is stronger"
        return "blue", f"Time ran out ({self.round_limit} rounds) - the defenders hold"

    def result(self, winner, reason):
        def survivors(side):
            return [{"unit": s.name, "count": s.count} for s in self.stacks.values()
                    if s.side == side and s.alive]

        def losses(side):
            out = {}
            for s in self.stacks.values():
                if s.side == side and s.start_count - s.count > 0:
                    out[s.name] = out.get(s.name, 0) + s.start_count - s.count
            return out
        return {"winner": winner, "reason": reason, "rounds": min(self.round, self.round_limit),
                "red_survivors": survivors("red"), "blue_survivors": survivors("blue"),
                "red_losses": losses("red"), "blue_losses": losses("blue"),
                "events": self.events}


# ----------------------------------------------------------------------------
# Action helpers (exposed to player code)
# ----------------------------------------------------------------------------
def attack(target):
    """Walk next to the target (if needed) and strike it."""
    return {"type": "attack", "target": getattr(target, "id", target)}


def shoot(target):
    """Shoot an arrow at the target (shooters only)."""
    return {"type": "shoot", "target": getattr(target, "id", target)}


def move(x, y):
    """Move to the battlefield square (x, y)."""
    return {"type": "move", "x": x, "y": y}


def move_toward(target):
    """Walk as far as possible toward the target without attacking."""
    return {"type": "move_toward", "target": getattr(target, "id", target)}


def defend():
    """Skip the turn and get +30% defense until your next turn."""
    return {"type": "defend"}


def wait():
    """Act later in this round (after the other stacks)."""
    return {"type": "wait"}


def cast(spell, target):
    """Hero spell (use inside hero_spell(battle))."""
    return {"type": "cast", "spell": spell, "target": getattr(target, "id", target)}
