"""
Sandbox runner: executes the player's code in a separate Python process.

    python runner.py  < job.json  > result (last line starts with @@RESULT@@)

The engine (game_engine/sandbox.py) starts this process for every preview /
commit, so an infinite loop or a crash can never freeze the game window.
"""
import builtins
import copy
import inspect
import io
import json
import os
import random
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

from game_engine.sim import api, facts as facts_mod  # noqa: E402
from game_engine.sim.world import World, HeroError, HeroStopped  # noqa: E402
from game_engine.sim.battle import Battle, BattleCodeError  # noqa: E402
from game_engine.sim.generals import GENERALS  # noqa: E402
from game_engine.sim.rules import UNITS  # noqa: E402

RESULT_MARK = "@@RESULT@@"
MAX_LOG_LINES = 400


class EndlessDream(BaseException):
    """Raised when player code runs too many lines (probably an infinite loop)."""


# ----------------------------------------------------------------------------
# Line budget + recursion depth tracking (only for the player's own files)
# ----------------------------------------------------------------------------
class Tracer:
    def __init__(self, files, limit):
        self.files = {os.path.abspath(f) for f in files}
        self.limit = limit
        self.lines = 0
        self.depth = {}
        self.max_depth = {}

    def global_trace(self, frame, event, arg):
        if os.path.abspath(frame.f_code.co_filename) in self.files:
            if event == "call":
                n = frame.f_code.co_name
                d = self.depth.get(n, 0) + 1
                self.depth[n] = d
                if d > self.max_depth.get(n, 0):
                    self.max_depth[n] = d
            return self.local_trace
        return None

    def local_trace(self, frame, event, arg):
        if event == "line":
            self.lines += 1
            if self.lines > self.limit:
                raise EndlessDream()
        elif event == "return":
            n = frame.f_code.co_name
            if self.depth.get(n, 0) > 0:
                self.depth[n] -= 1
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
    raise HeroError("input() needs a keyboard, but your hero is out adventuring! "
                    "Use read_sign() to read text in the game. (Try input() in the tavern/ scripts!)")


# ----------------------------------------------------------------------------
# Friendly error messages
# ----------------------------------------------------------------------------
def locate(exc, files):
    files = {os.path.abspath(f) for f in files}
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
        return (f"Your hero fell into an endless dream... your code ran over {limit:,} lines "
                f"without finishing. Is a while-loop never becoming False?")
    if isinstance(exc, RecursionError):
        return ("Lost forever in the Labyrinth! A function kept calling itself and never stopped. "
                "Every recursive function needs a BASE CASE that returns without calling itself.")
    if isinstance(exc, IndentationError):
        return (f"The spaces at the start of a line are wrong ({exc.msg}). Lines inside "
                f"def/if/for/while must be pushed right by 4 spaces.")
    if isinstance(exc, SyntaxError):
        tip = ""
        m = exc.msg or ""
        if "expected ':'" in m:
            tip = " Lines starting with if / for / while / def need a ':' at the end."
        elif "never closed" in m or "unmatched" in m:
            tip = " Count your brackets ( ) [ ] - every opening one needs a closing one."
        elif "unterminated string" in m:
            tip = " A text string is missing its closing quote mark."
        elif "invalid syntax" in m:
            tip = " Check for a missing comma, bracket or quote."
        elif "'=' " in m or "Maybe you meant '=='" in m:
            tip = " Use == to compare and = to store a value."
        return f"Your spell is written wrong: {m}.{tip}"
    if isinstance(exc, NameError):
        name = getattr(exc, "name", None) or msg.split("'")[1] if "'" in msg else msg
        if name in api.API_UNLOCK:
            return (f"'{name}' is a game spell, but you didn't import it. Add {name} to the "
                    f"'from hero_api import ...' line at the top.")
        return (f"Python doesn't know the word '{name}'. Check the spelling - or did you "
                f"create it inside another function? (Variables inside a function vanish when it ends!)")
    if isinstance(exc, TypeError):
        if "concatenate str" in msg or ("'str'" in msg and "'int'" in msg) or ("'str'" in msg and "'float'" in msg):
            return f"You mixed text (str) and numbers (int/float): {msg}. Use str(number) or int(text)!"
        if "NoneType" in msg:
            return f"{msg}. Something is None - did a function forget to 'return' its answer?"
        if "positional argument" in msg:
            return f"Wrong number of values given to a function: {msg}."
        if "not callable" in msg:
            return f"{msg}. Did you put () after something that isn't a function?"
        return f"Type mix-up: {msg}"
    if isinstance(exc, ValueError):
        if "invalid literal for int()" in msg:
            return f"int() can only turn digit-text like '42' into a number: {msg}"
        if "could not convert string to float" in msg:
            return f"float() can only turn number-text like '2.5' into a number: {msg}"
        return f"Bad value: {msg}"
    if isinstance(exc, IndexError):
        return (f"{msg}. That position doesn't exist! Lists start counting at 0, so a list "
                f"with 3 things has positions 0, 1 and 2.")
    if isinstance(exc, KeyError):
        return f"There's no key {msg} in that dictionary."
    if kind == "FrozenInstanceError":
        return "Nice try! The Black Dragon laughs at your hacking. Battle info is read-only."
    if isinstance(exc, AttributeError):
        return f"{msg}. Check the spelling after the dot."
    if isinstance(exc, ZeroDivisionError):
        return "You can't divide by zero - not even wizards can!"
    if isinstance(exc, SystemExit):
        return "exit() stops Python completely. Heroes never quit!"
    if isinstance(exc, ImportError):
        return f"{msg}. Check the names in your import line."
    return f"{kind}: {msg}"


def describe(exc, files, limit, kind_override=None):
    target = exc.original if isinstance(exc, BattleCodeError) else exc
    fname, line, text = locate(target, files)
    return {"error": friendly(target, limit), "error_kind": kind_override or type(target).__name__,
            "error_file": fname, "error_line": line, "error_text": text}


# ----------------------------------------------------------------------------
# Loading player files
# ----------------------------------------------------------------------------
def load_module(name, path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    code = compile(src, path, "exec")
    mod = types.ModuleType(name)
    mod.__file__ = path
    sys.modules[name] = mod
    exec(code, mod.__dict__)  # noqa: S102 - running the child's own code is the point
    return mod


def install_api_modules():
    hero = types.ModuleType("hero_api")
    for n in api.API_UNLOCK:
        setattr(hero, n, getattr(api, n))
    hero.TERRAIN = api.TERRAIN
    sys.modules["hero_api"] = hero
    bat = types.ModuleType("battle_api")
    for n, v in api.BATTLE_EXPORTS.items():
        setattr(bat, n, v)
    sys.modules["battle_api"] = bat


def call_flex(fn, args):
    try:
        params = [p for p in inspect.signature(fn).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        n = len(params)
    except (TypeError, ValueError):
        n = len(args)
    return fn(*args[:n])


def json_safe(obj):
    return json.loads(json.dumps(obj, default=str))


# ----------------------------------------------------------------------------
# Adventure day(s)
# ----------------------------------------------------------------------------
def run_days(job):
    state = job["state"]
    hero_path = os.path.join(PROJECT_DIR, job.get("hero_file", "my_hero.py"))
    army_path = os.path.join(PROJECT_DIR, job.get("army_file", "my_army.py"))
    files = [hero_path, army_path]
    limit = int(job.get("step_budget", 300_000))
    days_wanted = max(1, int(job.get("days", 1)))
    out = {"ok": True, "days": [], "log": [], "final_state": None, "trials": [], "depths": {}}

    log = out["log"]
    real_stdout = sys.stdout
    sys.stdout = LogWriter(log)
    builtins.input = no_input
    old_limit = sys.getrecursionlimit()
    hero_mod = None
    for d in range(days_wanted):
        world = World(state)
        api.W = world
        api.memory.clear()
        api.memory.update(world.s.get("memory", {}))
        army_cache = {}

        def army_loader(_cache=army_cache):
            if "mod" not in _cache:
                _cache["mod"] = load_module("my_army", army_path) if os.path.exists(army_path) else None
            return _cache["mod"]
        api.PLAYER_ARMY["loader"] = army_loader
        random.seed(world.s.get("seed", 1) * 1000 + world.s.get("day", 1))
        day = {"day": world.s.get("day", 1), "log_start": len(log)}
        tracer = Tracer(files, limit)
        try:
            sys.setrecursionlimit(600)
            with tracer:
                hero_mod = load_module("my_hero", hero_path)
                fn = getattr(hero_mod, "plan_turn", None)
                if not callable(fn):
                    raise HeroError("my_hero.py needs a function called plan_turn(). "
                                    "Did you rename or delete it?")
                call_flex(fn, [world.res("gold"), world.res("wood")])
        except HeroStopped:
            day.update({"error": world.error, "error_kind": "blocked", "error_file": None,
                        "error_line": None, "error_text": ""})
        except BattleCodeError as e:
            day.update(describe(e, files, limit))
        except (Exception, EndlessDream, SystemExit) as e:  # noqa: BLE001
            day.update(describe(e, files, limit, "rule" if isinstance(e, HeroError) else None))
        finally:
            sys.setrecursionlimit(old_limit)
            sys.stdout.flush()
        world.s["memory"] = json_safe(dict(api.memory))
        for k, v in tracer.max_depth.items():
            out["depths"][k] = max(out["depths"].get(k, 0), v)
        day.update(world.day_result())
        if day.get("error") is None and world.error:
            day["error"] = world.error
        day["log"] = log[day.pop("log_start"):]
        out["days"].append(json_safe(day))
        if day.get("error"):
            out["ok"] = False
            break
        world.end_day()
        state = world.s
    if out["ok"]:
        out["final_state"] = json_safe(state)

    # Spell trials (unit tests of the player's functions)
    for trial in job.get("trials", []):
        out["trials"].append(run_trial(trial, hero_path, army_path, files, limit, out["ok"] and hero_mod))
    sys.stdout.flush()
    sys.stdout = real_stdout
    return out


def run_trial(trial, hero_path, army_path, files, limit, hero_mod):
    res = {"func": trial["func"], "args": trial.get("args", []), "expect": trial.get("expect"),
           "ok": False, "got": None, "error": None}
    try:
        mod = sys.modules.get("my_hero") if trial.get("file", "my_hero") == "my_hero" else None
        if mod is None:
            path = hero_path if trial.get("file", "my_hero") == "my_hero" else army_path
            mod = load_module("trial_mod", path)
        fn = getattr(mod, trial["func"], None)
        if not callable(fn):
            res["error"] = f"No function named {trial['func']}() in your code yet."
            return res
        with Tracer(files, limit):
            sys.setrecursionlimit(600)
            got = fn(*copy.deepcopy(trial.get("args", [])))
        res["got"] = repr(got)
        want = trial.get("expect")
        if isinstance(want, float) or isinstance(got, float):
            res["ok"] = isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - want) < 1e-6
        else:
            res["ok"] = got == want and type(got) is type(want)
            if got == want and type(got) is not type(want):
                res["error"] = f"Right value but wrong type: got {type(got).__name__}, wanted {type(want).__name__}."
    except (Exception, EndlessDream) as e:  # noqa: BLE001
        res["error"] = friendly(e, limit)
    finally:
        sys.setrecursionlimit(1000)
    return res


# ----------------------------------------------------------------------------
# Hotseat duel: duel_red.py (child) vs .duels/parent_blue.py (parent)
# ----------------------------------------------------------------------------
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
                blue_army = cfg.get("blue_army") or [{"unit": "Pikeman", "count": 20},
                                                    {"unit": "Archer", "count": 15},
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
    install_api_modules()
    try:
        if job.get("mode") == "duel":
            result = run_duel(job)
        else:
            result = run_days(job)
            result["facts"] = gather_facts(job)
    except BaseException as e:  # noqa: BLE001 - never die silently
        result = {"ok": False, "fatal": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()}
    sys.__stdout__.write("\n" + RESULT_MARK + json.dumps(result, default=str) + "\n")
    sys.__stdout__.flush()


def gather_facts(job):
    out = []
    for key, default in (("hero_file", "my_hero.py"), ("army_file", "my_army.py")):
        p = os.path.join(PROJECT_DIR, job.get(key, default))
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                out.append(facts_mod.analyze(f.read()))
    return facts_mod.merge(*out) if out else facts_mod.analyze("")


if __name__ == "__main__":
    main()
