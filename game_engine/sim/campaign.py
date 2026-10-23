"""
Campaign logic: acts, quests, objectives, rewards, skills, XP, stars, templates.

Pure Python (no pygame) so it can be unit-tested and used by tools.
Acts live in game_engine/campaign/actN.py as an ACT dict (see act2.py for the
documented format).
"""
import csv
import importlib
import inspect
import os
import shutil
from collections import deque

from .rules import MAP_COLS, MAP_ROWS, RESOURCES, terrain_cost

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(ENGINE_DIR)

ACT_ORDER = ["act1", "act2", "act3", "act4", "act5", "act6", "act7", "act8"]
SAVE_VERSION = 2
LEVELS = [0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200, 4000, 5000, 6200, 7500, 9000]
RANK_NAMES = {0: "-", 1: "Basic", 2: "Advanced", 3: "Expert"}

# Concept skills (Heroes 3 secondary skills)
SKILLS = {
    "Scholar": "Comments", "Diplomacy": "Input & Output", "Scouting": "Variables",
    "Wisdom": "Data Types", "Estates": "Constants", "Offense": "Operators",
    "Mysticism": "Type Casting", "Intelligence": "Strings", "Tactics": "If Statements",
    "Navigation": "Boolean Algebra", "Leadership": "Lists", "Logistics": "Loops",
    "Sorcery": "Functions", "Resistance": "Scope", "Pathfinding": "Recursion",
    "Eagle Eye": "Bits & Bytes", "Earth Magic": "Binary", "Fire Magic": "Hexadecimal",
    "Air Magic": "Bitwise Logic",
}
SKILL_EFFECTS = {
    "Logistics": "+1 Movement Point per rank",
    "Offense": "+1 attack for all your troops per rank",
    "Wisdom": "+5 mana per rank",
    "Sorcery": "+25% spell damage per rank",
    "Pathfinding": "Expert: unlocks travel_to()",
}


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------
def load_act(act_id):
    mod = importlib.import_module(f"game_engine.campaign.{act_id}")
    return mod.ACT


def act_num(act_id):
    return ACT_ORDER.index(act_id) + 1


def next_act(act_id):
    i = ACT_ORDER.index(act_id)
    return ACT_ORDER[i + 1] if i + 1 < len(ACT_ORDER) else None


def parse_map(text):
    rows = [ln.strip().replace(" ", "") for ln in text.strip().splitlines() if ln.strip()]
    grid = [list(r.upper()) for r in rows]
    assert len(grid) == MAP_ROWS, f"map must have {MAP_ROWS} rows (got {len(grid)})"
    for i, r in enumerate(grid):
        assert len(r) == MAP_COLS, f"map row {i} must have {MAP_COLS} tiles (got {len(r)})"
    return grid


def load_csv_map(path):
    with open(path, encoding="utf-8") as f:
        return [[c.strip().upper() for c in row] for row in csv.reader(f) if row]


def load_csv_objects(path):
    objs = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            o = {"id": int(row["ID"]), "type": row["Type"].strip(), "name": row["Name"].strip(),
                 "x": int(row["X"]), "y": int(row["Y"]), "value": int(row["Value"]),
                 "power": int(row["Guard_Power"]), "desc": row["Description"].strip()}
            if o["type"] == "Mine":
                o["resource"] = "wood"
            objs.append(o)
    return objs


def new_state(act_id, carry=None, seed=None):
    act = load_act(act_id)
    if act.get("map_csv"):
        grid = load_csv_map(os.path.join(PROJECT_DIR, act["map_csv"]))
    else:
        grid = parse_map(act["map"])
    if act.get("objects_csv"):
        objects = load_csv_objects(os.path.join(PROJECT_DIR, act["objects_csv"]))
    else:
        objects = [dict(o) for o in act.get("objects", [])]
    first_q = act["quests"][0]["id"] if act.get("quests") else None
    for o in objects:
        o.setdefault("value", 0)
        o.setdefault("desc", "")
        o.setdefault("collected", False)
        if o.get("appear_at") and o["appear_at"] != first_q:
            o["hidden"] = True
        if o["type"] == "DigSite":
            o["hidden"] = True
    carry = carry or {}
    res = {r: 0 for r in RESOURCES}
    res.update(act.get("resources", {}))
    hero = {"x": act["hero"]["x"], "y": act["hero"]["y"],
            "max_mp": act["hero"].get("max_mp", 12.0),
            "name": carry.get("hero_name", act["hero"].get("name", "Orrin")),
            "mana": act["hero"].get("mana", 0)}
    state = {
        "save_version": SAVE_VERSION, "act": act_id, "act_num": act_num(act_id),
        "quest_index": 0, "quest_progress": {}, "completed": [], "quest_start_day": 1,
        "day": 1, "hero": hero, "resources": res, "army": [dict(a) for a in act.get("army", [])],
        "dragons": 0, "grid": grid, "base_grid": [r[:] for r in grid], "objects": objects,
        "keys": [], "flags": {}, "counters": {}, "memory": {},
        "xp": carry.get("xp", 0), "level": carry.get("level", 1),
        "skills": dict(carry.get("skills", {})), "stars": dict(carry.get("stars", {})),
        "prices": dict(act.get("prices", {})), "rules": dict(act.get("rules", {})),
        "seed": seed if seed is not None else act.get("seed", 7),
        "today": act.get("rules", {}).get("first_event", "clear"), "lit": [], "dug": [],
        "act_complete": False, "terraformed": [], "news": [],
    }
    hero["mana"] += 5 * state["skills"].get("Wisdom", 0)
    if state["rules"].get("day_layouts"):
        from .world import World
        w = World(state)
        w.apply_day_layout()
        state = w.s
    return state


def migrate_v1(data):
    """Convert an old (pre-campaign) Act I savegame into a v2 state."""
    st = new_state("act1")
    st["hero"]["x"] = data.get("hero_x", 1)
    st["hero"]["y"] = data.get("hero_y", 0)
    st["resources"]["gold"] = data.get("gold", 0)
    st["resources"]["wood"] = data.get("wood", 0)
    st["dragons"] = data.get("dragons", 0)
    st["day"] = data.get("day", 1)
    if "grid" in data:
        st["grid"] = data["grid"]
    collected = set(data.get("collected_ids", []))
    for o in st["objects"]:
        if o["id"] in collected:
            o["collected"] = True
    if 9 in collected:
        st["flags"]["boss_slain"] = True
    # Fast-forward quests that are already done
    act = load_act("act1")
    for q in act["quests"]:
        if check_all(st, q["objectives"], {}, {}):
            st["completed"].append(q["id"])
            st["quest_index"] += 1
        else:
            break
    if st["quest_index"] >= len(act["quests"]):
        st["act_complete"] = True
    return st


# ----------------------------------------------------------------------------
# Objectives
# ----------------------------------------------------------------------------
def counters(state):
    return state.get("counters", {})


def all_lit(state):
    lit = {tuple(p) for p in state.get("lit", [])}
    start = (state["hero"]["x"], state["hero"]["y"])
    grid = state["grid"]
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in seen or not (0 <= n[0] < MAP_COLS and 0 <= n[1] < MAP_ROWS):
                continue
            if terrain_cost(grid[n[1]][n[0]]) is None:
                continue
            seen.add(n)
            q.append(n)
    seen.discard(start)
    return seen <= lit


def check(state, obj, ctx):
    t = obj["type"]
    c = counters(state)
    facts = ctx.get("facts", {})
    if t == "collected":
        ids = obj.get("ids") or [obj["id"]]
        return all(any(o["id"] == i and o.get("collected") for o in state["objects"]) for i in ids)
    if t == "visited":
        return c.get(f"visit:{obj['id']}", 0) > 0
    if t == "counter":
        return c.get(obj["name"], 0) >= obj.get("at_least", 1)
    if t == "flag":
        return bool(state.get("flags", {}).get(obj["name"]))
    if t == "fact":
        return bool(facts.get(obj["name"]))
    if t == "fact_min":
        v = facts.get(obj["name"], 0)
        return (len(v) if isinstance(v, (list, dict)) else v) >= obj["min"]
    if t == "fact_has":
        return obj["value"] in facts.get(obj["name"], [])
    if t == "const_used":
        return any(n >= obj.get("min_uses", 2) for n in facts.get("constants", {}).values())
    if t == "resource":
        return state["resources"].get(obj["name"], 0) >= obj.get("at_least", 0)
    if t == "army_has":
        return sum(a["count"] for a in state.get("army", []) if a["unit"] == obj["unit"]) >= obj.get("at_least", 1)
    if t == "army_order":
        units = [a["unit"] for a in state.get("army", [])]
        want = obj["order"]
        return units[:len(want)] == want if obj.get("prefix") else units == want
    if t == "at":
        return (state["hero"]["x"], state["hero"]["y"]) == (obj["x"], obj["y"])
    if t == "printed":
        return any(ln.strip() for ln in ctx.get("log", []))
    if t == "printed_value":
        val = str(ctx.get("start", {}).get(obj["name"]))
        return any(val in ln for ln in ctx.get("log", []))
    if t == "said":
        return obj["text"] in ctx.get("says", [])
    if t == "trials":
        trials = ctx.get("trials", [])
        return bool(trials) and all(tr.get("ok") for tr in trials)
    if t == "depth":
        depths = ctx.get("depths", {})
        if obj.get("func"):
            return depths.get(obj["func"], 0) >= obj["min"]
        return any(d >= obj["min"] for d in depths.values())
    if t == "opened":
        return c.get(f"opened:{obj['id']}", 0) > 0
    if t == "won":
        return c.get(f"won:{obj['id']}", 0) > 0
    if t == "all_lit":
        return all_lit(state)
    if t == "days_max":
        return state.get("day", 1) - state.get("quest_start_day", 1) <= obj["n"]
    if t == "solved":
        return c.get(f"solved:{obj['id']}", 0) > 0
    if t == "lines_max":
        return 0 < facts.get("lines", 999) <= obj["n"]
    if t == "any":
        return any(check(state, o, ctx) for o in obj["of"])
    raise ValueError(f"unknown objective type {t}")


def check_all(state, objectives, ctx, progress=None):
    ok = True
    for i, ob in enumerate(objectives):
        if progress is not None and i in progress:
            continue
        if check(state, ob, ctx):
            if progress is not None:
                progress.append(i)
        else:
            ok = False
    return ok


def describe_objective(ob):
    return ob.get("text", "")


# ----------------------------------------------------------------------------
# Rewards & progression
# ----------------------------------------------------------------------------
def level_for(xp):
    lvl = 1
    for i, need in enumerate(LEVELS):
        if xp >= need:
            lvl = i + 1
    return lvl


def apply_reward(state, reward, messages):
    if not reward:
        return
    for r in RESOURCES:
        if reward.get(r):
            state["resources"][r] = state["resources"].get(r, 0) + reward[r]
            messages.append(f"+{reward[r]} {r}")
    if reward.get("xp"):
        before = state.get("level", 1)
        state["xp"] = state.get("xp", 0) + reward["xp"]
        state["level"] = level_for(state["xp"])
        messages.append(f"+{reward['xp']} XP")
        if state["level"] > before:
            messages.append(f"LEVEL UP! Your hero is now level {state['level']}!")
            state["hero"]["mana"] = state["hero"].get("mana", 0) + 5
    skill = reward.get("skill")
    if skill:
        sk = state.setdefault("skills", {})
        new = min(3, sk.get(skill, 0) + 1)
        if new != sk.get(skill, 0):
            sk[skill] = new
            eff = SKILL_EFFECTS.get(skill, "")
            messages.append(f"{RANK_NAMES[new]} {skill} ({SKILLS.get(skill, '')})" + (f" - {eff}" if eff else ""))
            if skill == "Wisdom":
                state["hero"]["mana"] = state["hero"].get("mana", 0) + 5
            if skill == "Pathfinding" and new >= 3:
                state["flags"]["travel_unlocked"] = True
    for unit, n in reward.get("units", {}).items():
        for slot in state["army"]:
            if slot["unit"] == unit:
                slot["count"] += n
                break
        else:
            if len(state["army"]) < 7:
                state["army"].append({"unit": unit, "count": n})
        messages.append(f"+{n} {unit}")
    if reward.get("flag"):
        state["flags"][reward["flag"]] = True
    for oid in reward.get("reveal", []):
        for o in state["objects"]:
            if o["id"] == oid:
                o["hidden"] = False
    if reward.get("mana"):
        state["hero"]["mana"] = state["hero"].get("mana", 0) + reward["mana"]
    if reward.get("max_mp"):
        state["hero"]["max_mp"] = state["hero"].get("max_mp", 12) + reward["max_mp"]


def current_quest(state, act=None):
    act = act or load_act(state["act"])
    qi = state.get("quest_index", 0)
    return act["quests"][qi] if qi < len(act["quests"]) else None


def start_quest(state, quest):
    state["quest_start_day"] = state.get("day", 1)
    for o in state["objects"]:
        if o.get("appear_at") == quest["id"]:
            o["hidden"] = False
    for k, v in quest.get("on_start", {}).get("resources", {}).items():
        state["resources"][k] = state["resources"].get(k, 0) + v


def evaluate(state, ctx):
    """
    After a committed turn: check the current quest (and chain through any
    quests that are already satisfied). Returns a list of popup dicts.
    """
    act = load_act(state["act"])
    popups = []
    guard = 0
    while not state.get("act_complete") and guard < 20:
        guard += 1
        q = current_quest(state, act)
        if q is None:
            break
        prog = state.setdefault("quest_progress", {}).setdefault(q["id"], [])
        if not check_all(state, q["objectives"], ctx, prog):
            break
        stars = 1
        for level in ("2", "3"):
            crit = q.get("stars", {}).get(level)
            if crit is not None and check_all(state, crit, ctx):
                stars = int(level)
            else:
                break
        best = max(stars, state.setdefault("stars", {}).get(q["id"], 0))
        state["stars"][q["id"]] = best
        msgs = []
        apply_reward(state, q.get("reward"), msgs)
        state["completed"].append(q["id"])
        state["quest_index"] += 1
        popups.append({"kind": "quest", "title": f"Quest complete: {q['title']}",
                       "stars": stars, "lines": msgs, "learned": q.get("learned", "")})
        nq = current_quest(state, act)
        if nq is None:
            state["act_complete"] = True
            v = act.get("victory", {})
            popups.append({"kind": "victory", "title": v.get("title", "VICTORY!"),
                           "lines": v.get("lines", [])})
        else:
            start_quest(state, nq)
            popups.append({"kind": "tip", "quest": nq["id"]})
    return popups


def star_hints(quest):
    out = []
    for level in ("2", "3"):
        for ob in quest.get("stars", {}).get(level, []):
            if ob.get("text"):
                out.append((int(level), ob["text"]))
    return out


# ----------------------------------------------------------------------------
# Templates, archives and API stubs
# ----------------------------------------------------------------------------
def archive_player_files(act_id, project_dir=PROJECT_DIR):
    arch = os.path.join(project_dir, "spellbook_archive")
    os.makedirs(arch, exist_ok=True)
    saved = []
    for name in ("my_hero.py", "my_army.py"):
        src = os.path.join(project_dir, name)
        if os.path.exists(src):
            dst = os.path.join(arch, f"{act_id}_{name}")
            n = 2
            while os.path.exists(dst):
                dst = os.path.join(arch, f"{act_id}_{name[:-3]}_{n}.py")
                n += 1
            shutil.copy2(src, dst)
            saved.append(dst)
    return saved


def write_templates(act_id, project_dir=PROJECT_DIR, overwrite=True):
    act = load_act(act_id)
    written = []
    for key, name in (("template", "my_hero.py"), ("army_template", "my_army.py")):
        text = act.get(key)
        if not text:
            continue
        path = os.path.join(project_dir, name)
        if os.path.exists(path) and not overwrite:
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.lstrip("\n"))
        written.append(path)
    for extra_name, text in act.get("extra_files", {}).items():
        path = os.path.join(project_dir, extra_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.lstrip("\n"))
            written.append(path)
    return written


def _sig(fn):
    try:
        return str(inspect.signature(fn))
    except (TypeError, ValueError):
        return "(*args)"


def generate_stubs(act_number, project_dir=PROJECT_DIR):
    """Write hero_api.py / battle_api.py stubs (for Thonny autocomplete & docs)."""
    from . import api
    lines = [
        "# ============================================================================",
        "# hero_api.py -- AUTO-GENERATED by the game. Don't edit (it gets rewritten)!",
        "# These are the spells your hero knows so far. The real magic happens inside",
        "# the game: run run_game.py, then save my_hero.py to see your hero move.",
        "# ============================================================================",
        "",
    ]
    objects = {"hero", "resources", "realm", "memory"}
    for name, need in api.API_UNLOCK.items():
        if need > act_number:
            continue
        obj = getattr(api, name)
        if name in objects:
            doc = (type(obj).__doc__ or "").strip().splitlines()[0] if type(obj).__doc__ else ""
            if name == "hero":
                lines += ["class _Hero:", f'    """{doc}"""',
                          "    x = 0; y = 0; mp = 12.0; max_mp = 12.0; name = 'Orrin'",
                          "    gold = 0; wood = 0; ore = 0; gems = 0; crystal = 0; mana = 0",
                          "    day = 1; week = 1; level = 1; keys = []; army = []", "",
                          "hero = _Hero()", ""]
            elif name == "resources":
                lines += [f"resources = {{}}  # {doc}", ""]
            elif name == "realm":
                lines += ["class _Realm:", f'    """{doc}"""',
                          "    MAX_MP = 12.0; MAP_COLS = 16; MAP_ROWS = 11; MAX_ARMY_SLOTS = 7; WEEK_LENGTH = 7",
                          "", "realm = _Realm()", ""]
            else:
                lines += [f"memory = {{}}  # {doc}", ""]
            continue
        doc = (obj.__doc__ or "").strip()
        lines += [f"def {name}{_sig(obj)}:", f'    """{doc}"""', "    pass", ""]
    with open(os.path.join(project_dir, "hero_api.py"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if act_number >= 3:
        bl = ["# battle_api.py -- AUTO-GENERATED by the game. Use it in my_army.py.", ""]
        for name, obj in api.BATTLE_EXPORTS.items():
            if callable(obj):
                bl += [f"def {name}{_sig(obj)}:", f'    """{(obj.__doc__ or "").strip()}"""', "    pass", ""]
            else:
                bl.append(f"{name} = {obj}")
        with open(os.path.join(project_dir, "battle_api.py"), "w", encoding="utf-8") as f:
            f.write("\n".join(bl) + "\n")
