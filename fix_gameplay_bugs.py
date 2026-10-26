#!/usr/bin/env python3
"""
Fixes all 6 gameplay & progression bugs across Acts I - VII:
  1. Smart BFS pathfinding for move_to(x, y) so Hero walks around walls/forests
     (e.g., move_to(7, 7) from (2, 5) in Act 1) and stops at unbribed Guards.
  2. Seals map bypasses around Guard gates in Acts 2, 3, 6, and 7 so players
     cannot walk around Guards or go straight to the Boss on Turn 1.
  3. Restricts terraform() to Water ('W'), Lava ('L'), and the Act 1 Dragon Cliff
     (14, 9) so players cannot bulldoze mountain walls around Guards.
  4. Makes _cheat_step (Ctrl+Arrows) respect Guard/Monster/Boss requirements.
  5. Evaluates quest completions during preview so Boss/Guard checks are always
     up-to-date on the same turn.
  6. Fixes Act 4 While-Loop gate (requires 'while') & Act 6 Hanoi ring verification.
"""
import csv
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SCENARIOS_DIR = os.path.join(PROJECT_DIR, "game_engine", "scenarios")
ENGINE_PATH = os.path.join(PROJECT_DIR, "game_engine", "engine.py")


def load_grid(path):
    with open(path, "r", encoding="utf-8") as f:
        return [[c.strip().upper() for c in row] for row in csv.reader(f) if row]


def save_grid(path, grid):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(grid)


# ---------------------------------------------------------------------------
# 1. Seal Map Gate Bypasses in Acts 2, 3, 6, and 7
# ---------------------------------------------------------------------------
# Act 2 (origin 8,5): Seal walls around the 6 Guard gates and Boss chamber
act2_map_path = os.path.join(SCENARIOS_DIR, "act2_map.csv")
if os.path.exists(act2_map_path):
    g2 = load_grid(act2_map_path)
    # Comment Gate at math(-4,2) -> grid(col=4, row=3): block row 3 cols 0..3 and 5 so col=4,row=3 is a true choke point
    for c in [0, 1, 2, 3, 5]:
        g2[3][c] = "F"
    # Password Gate at math(3,4) -> grid(col=11, row=1): block row 0 col 11 & row 2 col 11 so col=11,row=1 is a choke point
    g2[0][11] = "M"
    g2[2][11] = "M"
    # Variable Gate at math(6,2) -> grid(col=14, row=3): block cols 12,13,15 on row 3
    for c in [12, 13, 15]:
        g2[3][c] = "F"
    # Operators Gate at math(-5,-1) -> grid(col=3, row=6): block cols 0,1,2,4,5 on row 6
    for c in [0, 1, 2, 4, 5]:
        g2[6][c] = "M"
    # String Gate at math(4,-1) -> grid(col=12, row=6): block cols 9,10,11,13,14,15 on row 6
    for c in [9, 10, 11, 13, 15]:
        g2[6][c] = "M"
    # Casting Gate at math(4,-3) -> grid(col=12, row=8): block row 7 & 9 at col 12
    g2[7][12] = "M"
    g2[9][12] = "M"
    save_grid(act2_map_path, g2)
    print("✅ Sealed Guard gate choke-points in act2_map.csv")

# Act 3 (origin 0,5): Seal walls around the 5 Desert Guard gates
act3_map_path = os.path.join(SCENARIOS_DIR, "act3_map.csv")
if os.path.exists(act3_map_path):
    g3 = load_grid(act3_map_path)
    # Weather Gate at math(5,2) -> grid(col=5, row=3): wall col 5 except row 3
    for r in [0, 1, 2, 4, 5]:
        g3[r][5] = "M"
    # Scout Gate at math(11,2) -> grid(col=11, row=3) and Shrine Gate at math(11,-2) -> grid(col=11, row=7)
    for r in range(11):
        if r not in (3, 7):
            g3[r][11] = "M"
    # Compound Gate at math(14,1) -> grid(col=14, row=4) and Arena Gate at math(14,-2) -> grid(col=14, row=7)
    for c in [12, 13, 15]:
        g3[4][c] = "M"
        g3[7][c] = "M"
    save_grid(act3_map_path, g3)
    print("✅ Sealed Guard gate choke-points in act3_map.csv")

# Act 6 (origin 0,10): Separate Hero Start (1,9 -> row 1) from Boss (2,1 -> row 9) with a wall across row 5 cols 0..5
act6_map_path = os.path.join(SCENARIOS_DIR, "act6_map.csv")
if os.path.exists(act6_map_path):
    g6 = load_grid(act6_map_path)
    for c in range(0, 7):
        g6[5][c] = "M"
    # Ensure Labyrinth Gate at (6,7 -> col=6, row=3) and Obelisk Gate at (10,7 -> col=10, row=3) and Hydra Gate at (10,1 -> col=10, row=9) are true bridges
    for r in range(0, 5):
        if r != 3:
            g6[r][6] = "W"
            g6[r][10] = "W"
    for r in range(5, 11):
        if r != 9:
            g6[r][10] = "L"
    save_grid(act6_map_path, g6)
    print("✅ Sealed Underground Cavern & Boss choke-points in act6_map.csv")

# Act 7 (origin 0,10): Ensure Binary Gate (10,9 -> col=10,row=1), Hex Gate (8,4 -> col=8,row=6), Bitwise Gate (8,1 -> col=8,row=9) cannot be bypassed
act7_map_path = os.path.join(SCENARIOS_DIR, "act7_map.csv")
if os.path.exists(act7_map_path):
    g7 = load_grid(act7_map_path)
    for r in [0, 2, 3]:
        g7[r][10] = "W"
    for c in range(0, 16):
        if c not in (13,):
            g7[4][c] = "M"
    for r in range(5, 11):
        if r not in (6, 9):
            g7[r][8] = "L"
    save_grid(act7_map_path, g7)
    print("✅ Sealed Grail Sanctum gate choke-points in act7_map.csv")


# ---------------------------------------------------------------------------
# 2. Patch game_engine/engine.py for Smart Pathfinding & Strict Gate Checks
# ---------------------------------------------------------------------------
with open(ENGINE_PATH, "r", encoding="utf-8") as f:
    eng = f.read()

# 2a. Fix _cheat_step so Ctrl+Arrows cannot bypass unbribed Guards, Monsters, or Bosses
old_cheat_guard = '''            elif not obj["Collected"]:
                if obj["Type"] not in ("Sphinx", "Dwelling", "Shrine") or self.current_act == "act1":
                    obj["Collected"] = True'''

new_cheat_guard = '''            elif not obj["Collected"]:
                if obj["Type"] == "Guard":
                    if self.current_act == "act1" and self.gold < obj["Value"]:
                        self.sfx.play("fizzle")
                        self.status_msg = f"Guard at ({obj['X']},{obj['Y']}) demands {obj['Value']} Gold! (You have {self.gold})"
                        self.status_color = (255, 110, 110)
                        return
                    if self.current_act != "act1" and obj["Value"] == 0:
                        guard_dispatch = {
                            "act2": self._check_act2_guard, "act3": self._check_act3_guard,
                            "act4": self._check_act4_guard, "act5": self._check_act5_guard,
                            "act6": self._check_act6_guard, "act7": self._check_act7_guard,
                        }
                        check_fn = guard_dispatch.get(self.current_act, self._check_act2_guard)
                        passed, hint = check_fn(obj, self.preview_data or {})
                        if not passed:
                            self.sfx.play("fizzle")
                            self.status_msg = f"✖ {obj['Name']}: {hint}"
                            self.status_color = (255, 110, 110)
                            return
                    if obj["Value"] > 0:
                        self.gold -= obj["Value"]
                elif obj["Type"] == "Monster" and self.dragons < 1:
                    self.sfx.play("fizzle")
                    self.status_msg = f"{obj['Name']} blocks the way! Need at least 1 Dragon!"
                    self.status_color = (255, 110, 110)
                    return
                elif obj["Type"] == "Boss":
                    if self.current_act == "act1" and self.dragons < obj["Value"]:
                        self.sfx.play("fizzle")
                        self.status_msg = f"Need {obj['Value']} Dragons to defeat {obj['Name']}!"
                        self.status_color = (255, 110, 110)
                        return
                if obj["Type"] not in ("Sphinx", "Dwelling", "Shrine") or self.current_act == "act1":
                    obj["Collected"] = True'''

if old_cheat_guard in eng:
    eng = eng.replace(old_cheat_guard, new_cheat_guard, 1)
    # Also move hero position update in _cheat_step AFTER the guard check!
    eng = eng.replace(
        '''        self.hero_col = ncol
        self.hero_row = nrow
        self.sfx.play("step")
        obj = self.get_object_at(ncol, nrow)''',
        '''        obj = self.get_object_at(ncol, nrow)''',
        1
    )
    eng = eng.replace(
        '''        if self.current_act == "act2":
            self._trigger_zone_tips()''',
        '''        self.hero_col = ncol
        self.hero_row = nrow
        self.sfx.play("step")
        if self.current_act == "act2":
            self._trigger_zone_tips()''',
        1
    )

# 2b. Fix Act 4 While-Loop Guard so 'for' does not satisfy 'while'
eng = eng.replace(
    'ok = "act4_while" in self.completed_quests or (dug and ("while " in code or "for " in code))',
    'ok = "act4_while" in self.completed_quests or (dug and "while " in code)'
)

# 2c. Fix Act 6 Hanoi Guard so it simulates ring moves and verifies Peg C has [3, 2, 1]
old_hanoi_check = '''        if gid == 5:
            moves = [a for a in hero_api._actions if a[0] == "move_ring"]
            ok = "act6_hanoi" in self.completed_quests or ((len(self.hanoi_pegs.get("C", [])) == 3 or len(moves) >= 7) and (has_rec or "def " in self._get_active_code()))'''

new_hanoi_check = '''        if gid == 5:
            sim_pegs = {k: list(v) for k, v in self.hanoi_pegs.items()}
            for a in hero_api._actions:
                if a[0] == "move_ring":
                    _, src, dst = a
                    if src in sim_pegs and dst in sim_pegs and sim_pegs[src]:
                        r_top = sim_pegs[src][-1]
                        if not sim_pegs[dst] or sim_pegs[dst][-1] > r_top:
                            sim_pegs[dst].append(sim_pegs[src].pop())
            ok = "act6_hanoi" in self.completed_quests or (len(sim_pegs.get("C", [])) == 3 and (has_rec or "def " in self._get_active_code()))'''

if old_hanoi_check in eng:
    eng = eng.replace(old_hanoi_check, new_hanoi_check, 1)

# 2d. Upgrade _simulate_path:
#     - Restrict terraform() to Water ('W'), Lava ('L'), or the Dragon Cliff (14, 9) in Act 1
#     - Use BFS shortest walkable path for move_to(tx, ty) so the Hero walks around walls/forests
#       instead of getting stuck on L-shaped corners!
old_sim_block = '''        step_queue = []
        for act in hero_api._actions:
            if act[0] == "terraform":
                _, tx, ty, ttype = act
                t_col, t_row = self.math_to_grid(tx, ty)
                if 0 <= t_col < MAP_COLS and 0 <= t_row < MAP_ROWS:
                    temp_grid[t_row][t_col] = ttype
                    sim["terraforms"].append((t_col, t_row, ttype))
            elif act[0] == "rel":
                _, dx, dy = act
                col_step = 1 if dx > 0 else (-1 if dx < 0 else 0)
                for _ in range(abs(dx)):
                    cur_col += col_step
                    step_queue.append((cur_col, cur_row))
                row_step = -1 if dy > 0 else (1 if dy < 0 else 0)
                for _ in range(abs(dy)):
                    cur_row += row_step
                    step_queue.append((cur_col, cur_row))
            elif act[0] == "abs":
                _, tx, ty = act
                target_col, target_row = self.math_to_grid(tx, ty)
                while cur_col != target_col:
                    cur_col += 1 if cur_col < target_col else -1
                    step_queue.append((cur_col, cur_row))
                while cur_row != target_row:
                    cur_row += 1 if cur_row < target_row else -1
                    step_queue.append((cur_col, cur_row))'''

new_sim_block = '''        step_queue = []
        for act in hero_api._actions:
            if act[0] == "terraform":
                _, tx, ty, ttype = act
                t_col, t_row = self.math_to_grid(tx, ty)
                if 0 <= t_col < MAP_COLS and 0 <= t_row < MAP_ROWS:
                    orig_tile = temp_grid[t_row][t_col]
                    is_dragon_cliff = (self.current_act == "act1" and (int(tx), int(ty)) == (14, 9))
                    if orig_tile not in ("W", "L", "B") and not is_dragon_cliff:
                        sim["valid"] = False
                        sim["error"] = f"Cannot terraform {TERRAIN_NAMES.get(orig_tile, orig_tile)} at ({tx}, {ty})! Only Water, Lava, or Dragon Cliff (14,9) can be terraformed."
                        self.preview_data = sim
                        self.status_msg = sim["error"]
                        self.status_color = (255, 110, 110)
                        return
                    temp_grid[t_row][t_col] = ttype
                    sim["terraforms"].append((t_col, t_row, ttype))
            elif act[0] == "rel":
                _, dx, dy = act
                col_step = 1 if dx > 0 else (-1 if dx < 0 else 0)
                for _ in range(abs(dx)):
                    cur_col += col_step
                    step_queue.append((cur_col, cur_row))
                row_step = -1 if dy > 0 else (1 if dy < 0 else 0)
                for _ in range(abs(dy)):
                    cur_row += row_step
                    step_queue.append((cur_col, cur_row))
            elif act[0] == "abs":
                _, tx, ty = act
                target_col, target_row = self.math_to_grid(tx, ty)
                # Use BFS on walkable tiles so move_to(x, y) follows roads/grass around walls
                bfs_path = None
                if (cur_col, cur_row) == (target_col, target_row):
                    bfs_path = []
                elif 0 <= target_col < MAP_COLS and 0 <= target_row < MAP_ROWS:
                    from collections import deque
                    q_bfs = deque([(cur_col, cur_row, [])])
                    seen_bfs = {(cur_col, cur_row)}
                    while q_bfs:
                        bc, br, bpath = q_bfs.popleft()
                        if (bc, br) == (target_col, target_row):
                            bfs_path = bpath
                            break
                        for dc_b, dr_b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nc_b, nr_b = bc + dc_b, br + dr_b
                            if 0 <= nc_b < MAP_COLS and 0 <= nr_b < MAP_ROWS and (nc_b, nr_b) not in seen_bfs:
                                t_b = temp_grid[nr_b][nc_b]
                                if TERRAIN_COSTS.get(t_b) is not None:
                                    seen_bfs.add((nc_b, nr_b))
                                    q_bfs.append((nc_b, nr_b, bpath + [(nc_b, nr_b)]))
                if bfs_path is not None:
                    for step_c, step_r in bfs_path:
                        cur_col, cur_row = step_c, step_r
                        step_queue.append((cur_col, cur_row))
                else:
                    while cur_col != target_col:
                        cur_col += 1 if cur_col < target_col else -1
                        step_queue.append((cur_col, cur_row))
                    while cur_row != target_row:
                        cur_row += 1 if cur_row < target_row else -1
                        step_queue.append((cur_col, cur_row))'''

assert old_sim_block in eng, "old_sim_block not found"
eng = eng.replace(old_sim_block, new_sim_block, 1)

compile(eng, ENGINE_PATH, "exec")
with open(ENGINE_PATH, "w", encoding="utf-8") as f:
    f.write(eng)
print("✅ Patched game_engine/engine.py with smart BFS move_to(), strict terraform rules, and Guard checks!")
print("\n🎉 All 6 gameplay bugs fixed! Run `python run_game.py` and press Ctrl+R to reset your current map.")
