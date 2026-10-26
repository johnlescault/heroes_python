"""
Sandbox runner for Programmable AI Duels and AST Code Analysis.
Executes duel_red.py vs parent_blue.py / AI Generals in an isolated subprocess
with line-budget tracing so infinite loops can never freeze the game window.
"""
import builtins
import io
import json
import os
import sys
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.dirname(HERE)
PROJECT_DIR = os.path.dirname(ENGINE_DIR)
if sys.path and os.path.abspath(sys.path[0]) == HERE:
    sys.path.pop(0)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from game_engine.sim import facts as facts_mod  # noqa: E402
from game_engine.sim import battle as _battle  # noqa: E402
from game_engine.sim.battle import Battle, BattleCodeError  # noqa: E402
from game_engine.sim.generals import GENERALS  # noqa: E402
from game_engine.sim.rules import UNITS, AIR, EARTH, FIRE, WATER  # noqa: E402

RESULT_MARK = "@@RESULT@@"
MAX_LOG_LINES = 400

BATTLE_EXPORTS = {
    "attack": _battle.attack, "shoot": _battle.shoot, "move": _battle.move,
    "move_toward": _battle.move_toward, "defend": _battle.defend, "wait": _battle.wait,
    "cast": _battle.cast, "AIR": AIR, "EARTH": EARTH, "FIRE": FIRE, "WATER": WATER,
}


class HeroError(Exception):
    """A game-rule problem caused by player code."""


class EndlessDream(BaseException):
    """Raised when player code runs too many lines (infinite loop)."""


class Tracer:
    def __init__(self, files, limit):
        self.files = {os.path.abspath(f) for f in files if f}
        self.limit = limit
        self.lines = 0

    def global_trace(self, frame, event, arg):
        if os.path.abspath(frame.f_code.co_filename) in self.files:
            return self.local_trace
        return None

    def local_trace(self, frame, event, arg):
        if event == "line":
            self.lines += 1
            if self.lines > self.limit:
                raise EndlessDream()
        return self.local_trace

    def __enter__(self):
        sys.settrace(self.global_trace)
        return self

    def __exit__(self, *exc):
        sys.settrace(None)
        return False


class LogWriter(io.TextIOBase):
    def __init__(self, sink):
        self.sink = sink
        self.buf = ""

    def write(self, s):
        self.buf += str(s)
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if len(self.sink) < MAX_LOG_LINES:
                self.sink.append(line)
        return len(s)

    def flush(self):
        if self.buf:
            if len(self.sink) < MAX_LOG_LINES:
                self.sink.append(self.buf)
            self.buf = ""


def no_input(prompt=""):
    raise HeroError("input() needs a keyboard! Try running the scripts inside the tavern/ folder in Thonny!")


def locate(exc, files):
    files = {os.path.abspath(f) for f in files if f}
    if isinstance(exc, SyntaxError) and exc.filename:
        return os.path.basename(exc.filename), exc.lineno, (exc.text or "").strip()
    found = None
    for fr in traceback.extract_tb(exc.__traceback__):
        if os.path.abspath(fr.filename) in files:
            found = (os.path.basename(fr.filename), fr.lineno, (fr.line or "").strip())
    return found or (None, None, "")


def friendly(exc, limit=0):
    kind = type(exc).__name__
    msg = str(exc)
    if isinstance(exc, HeroError):
        return msg
    if isinstance(exc, EndlessDream):
        return f"Your code ran over {limit:,} lines without finishing. Check your while-loop condition!"
    if isinstance(exc, RecursionError):
        return "Infinite Recursion! Every recursive function needs a BASE CASE that returns without calling itself."
    if isinstance(exc, IndentationError):
        return f"Indentation Error ({exc.msg}): Lines inside def/if/for/while must be indented by 4 spaces."
    if isinstance(exc, SyntaxError):
        return f"Syntax Error: {exc.msg}"
    return f"{kind}: {msg}"


def describe(exc, files, limit, kind_override=None):
    target = exc.original if isinstance(exc, BattleCodeError) else exc
    fname, line, text = locate(target, files)
    return {"error": friendly(target, limit), "error_kind": kind_override or type(target).__name__,
            "error_file": fname, "error_line": line, "error_text": text}


def load_module(name, path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    code = compile(src, path, "exec")
    mod = types.ModuleType(name)
    mod.__file__ = path
    sys.modules[name] = mod
    exec(code, mod.__dict__)  # noqa: S102
    return mod


def install_battle_api():
    bat = types.ModuleType("battle_api")
    for n, v in BATTLE_EXPORTS.items():
        setattr(bat, n, v)
    sys.modules["battle_api"] = bat


def json_safe(obj):
    return json.loads(json.dumps(obj, default=str))


def validate_draft(picks, budget, side):
    if picks is None:
        raise HeroError(f"{side}: draft() returned nothing. Return a list like [('Archer', 10)].")
    if not isinstance(picks, (list, tuple)):
        raise HeroError(f"{side}: draft() must return a list of (unit, count) pairs.")
    army, total = [], 0
    for p in picks:
        if isinstance(p, dict):
            unit, count = p.get("unit"), p.get("count")
        else:
            try:
                unit, count = p
            except (TypeError, ValueError):
                raise HeroError(f"{side}: each draft pick must be a pair like ('Archer', 10), not {p!r}.") from None
        if unit not in UNITS:
            raise HeroError(f"{side}: unknown unit '{unit}'.")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise HeroError(f"{side}: count for {unit} must be a positive whole number.")
        total += UNITS[unit]["cost"] * count
        army.append({"unit": unit, "count": count})
    if len(army) > 7:
        raise HeroError(f"{side}: max 7 army slots (you drafted {len(army)}).")
    if total > budget:
        raise HeroError(f"{side}: that army costs {total} gold but the budget is {budget}.")
    return army, total


def run_duel(job):
    red_path = os.path.join(PROJECT_DIR, job.get("red_file", "duel_red.py"))
    blue_path = job.get("blue_file")
    files = [red_path] + ([blue_path] if blue_path else [])
    limit = int(job.get("step_budget", 2_000_000))
    cfg = job.get("config", {})
    budget = int(cfg.get("budget", 5000))
    shop = {u: UNITS[u]["cost"] for u in UNITS if u not in cfg.get("banned_units", [])}
    out = {"ok": False, "log": [], "error": None, "battle": None, "red_army": None, "blue_army": None}
    real_stdout = sys.stdout
    sys.stdout = LogWriter(out["log"])
    builtins.input = no_input
    side = "red"
    try:
        with Tracer(files, limit):
            red = load_module("duel_red", red_path)
            side = "blue"
            if blue_path and os.path.exists(blue_path):
                blue = load_module("duel_blue", blue_path)
                blue_turn = getattr(blue, "battle_turn", None) or GENERALS["squire"]
                blue_draft = getattr(blue, "draft", None)
            else:
                g = GENERALS.get(cfg.get("fallback_ai", "squire"), GENERALS["squire"])
                blue, blue_turn, blue_draft = None, g, None
            side = "red"
            red_budget = budget + int(cfg.get("handicap_gold", 0))
            if not callable(getattr(red, "draft", None)):
                raise HeroError("duel_red.py needs a draft(budget, shop) function.")
            if not callable(getattr(red, "battle_turn", None)):
                raise HeroError("duel_red.py needs a battle_turn(me, battle) function.")
            red_army, red_cost = validate_draft(red.draft(red_budget, dict(shop)), red_budget, "Red")
            side = "blue"
            blue_shop = {u: c for u, c in shop.items() if u not in cfg.get("blue_banned_units", [])}
            if blue_draft:
                blue_army, blue_cost = validate_draft(blue_draft(budget, dict(blue_shop)), budget, "Blue")
            else:
                ai_name = cfg.get("fallback_ai", "squire")
                if ai_name == "warlord":
                    blue_army = [{"unit": "Angel", "count": 1}, {"unit": "Cavalier", "count": 1},
                                 {"unit": "Monk", "count": 2}, {"unit": "Swordsman", "count": 1}]
                elif ai_name == "knight":
                    blue_army = [{"unit": "Cavalier", "count": 2}, {"unit": "Swordsman", "count": 5},
                                 {"unit": "Archer", "count": 10}, {"unit": "Griffin", "count": 2}]
                else:
                    blue_army = [{"unit": "Pikeman", "count": 20}, {"unit": "Archer", "count": 15},
                                 {"unit": "Griffin", "count": 6}]
                blue_cost = sum(UNITS[a["unit"]]["cost"] * a["count"] for a in blue_army)
            side = "battle"
            b = Battle(red_army, blue_army, red.battle_turn, blue_turn, seed=int(job.get("seed", 1)),
                       red_spell=getattr(red, "hero_spell", None),
                       blue_spell=getattr(blue, "hero_spell", None) if blue else None,
                       red_mana=int(cfg.get("mana", 20)), blue_mana=int(cfg.get("mana", 20)),
                       names={"red": cfg.get("red_name", "Red (you)"), "blue": cfg.get("blue_name", "Blue")})
            out["battle"] = b.run()
            out.update({"ok": True, "red_army": red_army, "blue_army": blue_army,
                        "red_cost": red_cost, "blue_cost": blue_cost})
    except BattleCodeError as e:
        out.update(describe(e, files, limit))
        out["error_side"] = e.side
    except (Exception, EndlessDream, SystemExit) as e:  # noqa: BLE001
        out.update(describe(e, files, limit))
        out["error_side"] = side
    finally:
        sys.stdout.flush()
        sys.stdout = real_stdout
    return json_safe(out)


def main():
    job = json.loads(sys.stdin.read())
    install_battle_api()
    try:
        result = run_duel(job)
    except BaseException as e:  # noqa: BLE001
        result = {"ok": False, "fatal": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()}
    sys.__stdout__.write("\n" + RESULT_MARK + json.dumps(result, default=str) + "\n")
    sys.__stdout__.flush()


if __name__ == "__main__":
    main()
