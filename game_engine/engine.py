import webbrowser
import os
import sys
import csv
import json
import math
import re
import ctypes
import importlib
from typing import Any
import pygame

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(ENGINE_DIR)
ASSETS_DIR = os.path.join(ENGINE_DIR, "assets")

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from game_engine.terrain import TerrainRenderer
from game_engine.sim import facts as ast_facts
from game_engine import sandbox
from game_engine.hints_and_sfx import (
    RetroSoundFX, friendly_python_error, PROGRESSIVE_HINTS, SPELLBOOK_PILLS, QUEST_VIDEOS, TIP_VIDEOS
)

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

HERO_API_LINES = [
    "# Auto-generated helper module for Heroes of Python (Acts I - VII)",
    "_actions = []",
    "_scout_results = {}",
    "_sign_results = {}",
    "_read_signs = set()",
    "_today_result = 'clear'",
    "_look_results = {}",
    "_keys_held = set()",
    "_map_grid = []",
    "_dig_attempts = 0",
    "memory = {}",
    "_lit_torches = set()",
    "_hanoi_pegs = {'A': [3, 2, 1], 'B': [], 'C': []}",
    "_obelisk_bits = '00000000'",
    "AIR, EARTH, FIRE, WATER = 1, 2, 4, 8",
    "",
    "def _reset():",
    "    global _dig_attempts",
    "    _actions.clear()",
    "    _read_signs.clear()",
    "    _dig_attempts = 0",
    "",
    "def move_right(steps=1):",
    "    _actions.append(('rel', int(steps), 0))",
    "",
    "def move_left(steps=1):",
    "    _actions.append(('rel', -int(steps), 0))",
    "",
    "def move_down(steps=1):",
    "    _actions.append(('rel', 0, -int(steps)))",
    "",
    "def move_up(steps=1):",
    "    _actions.append(('rel', 0, int(steps)))",
    "",
    "def move_by(dx, dy):",
    "    _actions.append(('rel', int(dx), int(dy)))",
    "",
    "def move_to(x, y):",
    "    _actions.append(('abs', int(x), int(y)))",
    "",
    "def terraform(x, y, tile_type='B'):",
    "    _actions.append(('terraform', int(x), int(y), str(tile_type).upper()))",
    "",
    "def say(text):",
    "    _actions.append(('say', str(text)))",
    "",
    "def scout(name):",
    "    key = str(name).lower()",
    "    for k, v in _scout_results.items():",
    "        if key in k.lower():",
    "            return v",
    "    return (0, 0)",
    "",
    "def read_sign(x, y):",
    "    coord = (int(x), int(y))",
    "    _read_signs.add(coord)",
    "    return _sign_results.get(coord, '')",
    "",
    "def answer_sphinx(value):",
    "    _actions.append(('answer_sphinx', value))",
    "",
    "def recruit(unit_name, count=1):",
    "    _actions.append(('recruit', str(unit_name), int(count)))",
    "",
    "def open_gate(password):",
    "    _actions.append(('open_gate', str(password)))",
    "",
    "def today():",
    "    return _today_result",
    "",
    "def look(x, y):",
    "    return _look_results.get((int(x), int(y)), '?')",
    "",
    "def has_key(color):",
    "    return str(color).lower() in _keys_held",
    "",
    "def set_lever(name, value):",
    "    _actions.append(('set_lever', str(name).lower(), bool(value)))",
    "",
    "def get_map():",
    "    return [row[:] for row in _map_grid]",
    "",
    "def dig():",
    "    global _dig_attempts",
    "    _dig_attempts += 1",
    "    _actions.append(('dig', _dig_attempts))",
    "    return _dig_attempts >= 3",
    "",
    "def set_formation(order):",
    "    _actions.append(('set_formation', list(order)))",
    "",
    "def test_spell(fn):",
    "    _actions.append(('test_spell', fn))",
    "",
    "def is_open(x, y):",
    "    return _look_results.get((int(x), int(y)), 'M') not in ('M', 'W', 'L', 'F', '?')",
    "",
    "def is_lit(x, y):",
    "    return (int(x), int(y)) in _lit_torches",
    "",
    "def light_torch(x, y):",
    "    coord = (int(x), int(y))",
    "    if coord in _lit_torches:",
    "        return False",
    "    _lit_torches.add(coord)",
    "    _actions.append(('light_torch', int(x), int(y)))",
    "    return True",
    "",
    "def move_ring(src, dst):",
    "    _actions.append(('move_ring', str(src).upper(), str(dst).upper()))",
    "",
    "def answer_hydra(strikes):",
    "    _actions.append(('answer_hydra', int(strikes)))",
    "",
    "def obelisk_pattern():",
    "    return _obelisk_bits",
    "",
    "def set_obelisks(bits):",
    "    global _obelisk_bits",
    "    _obelisk_bits = str(bits)",
    "    _actions.append(('set_obelisks', str(bits)))",
    "",
    "def open_vault(code):",
    "    _actions.append(('open_vault', int(code)))",
    "",
    "def dye_banner(hex_color):",
    "    _actions.append(('dye_banner', str(hex_color).upper()))",
    "",
    "def attack(target=None):",
    "    _actions.append(('battle_attack', target))",
    "",
    "def shoot(target=None):",
    "    _actions.append(('battle_shoot', target))",
    "",
    "def move_toward(target=None):",
    "    _actions.append(('battle_move_toward', target))",
    "",
    "def defend():",
    "    _actions.append(('battle_defend',))",
]

hero_api_path = os.path.join(PROJECT_DIR, "hero_api.py")
with open(hero_api_path, "w", encoding="utf-8") as f:
    f.write("\n".join(HERO_API_LINES) + "\n")

import hero_api

TILE_SIZE = 84
MAP_COLS = 16
MAP_ROWS = 11
SIDEBAR_WIDTH = 576
BOTTOM_BAR_HEIGHT = 280

VIRTUAL_W = MAP_COLS * TILE_SIZE + SIDEBAR_WIDTH
VIRTUAL_H = MAP_ROWS * TILE_SIZE + BOTTOM_BAR_HEIGHT

TERRAIN_COSTS = {
    "R": 0.5,
    "G": 1.0,
    "B": 1.0,
    "S": 1.5,
    "M": None,
    "W": None,
    "L": None,
    "F": None,
}

TERRAIN_NAMES = {
    "R": "Cobble Road (0.5 MP)",
    "G": "Emerald Grass (1.0 MP)",
    "B": "Enchanted Bridge (1.0 MP)",
    "S": "Desert Sand (1.5 MP)",
    "M": "Jagged Peak (Blocked)",
    "W": "Deep River (Blocked)",
    "L": "Molten Lava (Blocked)",
    "F": "Ancient Forest (Blocked)",
}

ACT_SKILL_REWARDS = {
    "act1": "Logistics (+MP)",
    "act2": "Scholar (Types & Math)",
    "act3": "Tactics (Conditionals)",
    "act4": "Leadership (Lists & Loops)",
    "act5": "Wisdom (Functions & Scope)",
    "act6": "Pathfinding (Recursion)",
    "act7": "Sorcery (Binary & Hex)",
}

ACT_TEMPLATES = {
    "act1": """# ============================================================================
# ⚔ HEROES OF PYTHON — ACT I: THE STARTING VALLEY (my_hero.py) ⚔
# ============================================================================
# Spells: move_to(x, y), move_by(dx, dy), move_right(n), terraform(x, y, 'B')
# Tip: Save this file (Ctrl+S) to preview your path, or type in the Console!
# ============================================================================
from hero_api import (
    move_right, move_left, move_down, move_up,
    move_by, move_to, terraform
)

def plan_turn(gold, wood):
    # Quest 1: Collect 1,500 Gold at (4, 9) and (2, 5), then bribe Guard at (7, 7)
    pass
""",
    "act2": """# ============================================================================
# ⚔ HEROES OF PYTHON — ACT II: THE HERO'S JOURNAL (my_hero.py) ⚔
# ============================================================================
# Spells: # comments, say('text'), x, y = scout('Name'), answer_sphinx(val),
#         recruit(unit, count), int(read_sign(x, y)), open_gate(password)
# ============================================================================
from hero_api import (
    move_to, move_by, terraform,
    say, scout, read_sign, answer_sphinx, recruit, open_gate
)

COST = 60  # Constant price per Pikeman

def plan_turn(gold, wood):
    # silence cursed spells with # and use variables, math (//, %), and strings!
    pass
""",
    "act3": """# ============================================================================
# ⚔ HEROES OF PYTHON — ACT III: THE SHIFTING SANDS (my_hero.py) ⚔
# ============================================================================
# Spells: today(), look(x, y), has_key('blue'), set_lever(color, True/False),
#         attack(), defend(), move_toward()
# ============================================================================
from hero_api import (
    move_to, move_by,
    today, look, has_key, set_lever,
    attack, defend, move_toward
)

def plan_turn(gold, wood):
    # Use if / elif / else and boolean logic (and, or, not) to cross the desert!
    pass
""",
    "act4": """# ============================================================================
# ⚔ HEROES OF PYTHON — ACT IV: RAISING AN ARMY (my_hero.py) ⚔
# ============================================================================
# Spells: set_formation(['Archer', 'Pikeman']), get_map(), dig(),
#         shoot(), attack(), move_toward(), defend()
# ============================================================================
from hero_api import (
    move_to, move_by,
    set_formation, get_map, dig,
    shoot, attack, move_toward, defend
)

def plan_turn(gold, wood):
    # Order your army list, scan the 2D grid with get_map(), and loop waypoints!
    pass
""",
    "act5": """# ============================================================================
# ⚔ HEROES OF PYTHON — ACT V: THE SPELLBOOK (my_hero.py) ⚔
# ============================================================================
# Spells: def my_spell(x):, return, test_spell(fn), memory['code'] = 42
# Bonus: Check out the scrolls/ folder for Seer's Scroll text files!
# ============================================================================
from hero_api import (
    move_to, move_by, terraform,
    test_spell, memory
)

def bridge(x):
    terraform(x, 9, 'B')

def add_gold(a, b):
    return a + b

def plan_turn(gold, wood):
    # Call your custom functions and store secrets in memory['code'] = 42!
    pass
""",
    "act6": """# ============================================================================
# ⚔ HEROES OF PYTHON — ACT VI: THE UNDERGROUND (my_hero.py) ⚔
# ============================================================================
# Spells: light_torch(x, y), move_ring(src, dst), answer_hydra(strikes)
# Watch the live Ring Obelisk HUD at the top of the map as your recursion runs!
# ============================================================================
from hero_api import (
    move_to, move_by,
    light_torch, is_lit, is_open, move_ring, answer_hydra
)

def hanoi(n, src, dst, via):
    if n > 0:
        hanoi(n - 1, src, via, dst)
        move_ring(src, dst)
        hanoi(n - 1, via, dst, src)

def strikes(n):
    if n == 0:
        return 1
    return 1 + 2 * strikes(n - 1)

def plan_turn(gold, wood):
    # Use recursive functions with base cases to conquer the Underground!
    pass
""",
    "act7": """# ============================================================================
# ⚔ HEROES OF PYTHON — ACT VII: THE GRAIL (my_hero.py) ⚔
# ============================================================================
# Spells: set_obelisks('10101101'), open_vault(int(b, 2)), dye_banner('#FF8800'),
#         Bitwise operators: & (AND), | (OR), ^ (XOR), << (Left Shift)
# Watch the 8-Bit Obelisk Byte HUD at the top of the map!
# ============================================================================
from hero_api import (
    move_to, move_by,
    obelisk_pattern, set_obelisks, open_vault, dye_banner,
    AIR, EARTH, FIRE, WATER
)

def plan_turn(gold, wood):
    # Master Binary (base 2), Hexadecimal (#RRGGBB), and Bitwise XOR (^)!
    pass
""",
}



class HDArtRenderer:
    def __init__(self):
        self.tiles = {}
        self.sprites = {}
        self._load_external_sprites()
        self._build_hd_tiles()
        self.terrain = TerrainRenderer(TILE_SIZE, self.tiles, self.sprites.get("road"))

    def get_tile(self, grid, c, r, base_grid=None):
        return self.terrain.tile(grid, c, r, base_grid)

    def _load_external_sprites(self):
        if not os.path.exists(ASSETS_DIR):
            return
        for fname in os.listdir(ASSETS_DIR):
            if fname.endswith(".png"):
                path = os.path.join(ASSETS_DIR, fname)
                try:
                    img = pygame.image.load(path).convert_alpha()
                    key = fname[:-4]
                    self.sprites[key] = img
                except Exception:
                    pass

    def _get_scaled_sprite(self, key, size):
        if key not in self.sprites:
            return None
        cache_key = f"{key}_{size[0]}x{size[1]}"
        if cache_key not in self.sprites:
            self.sprites[cache_key] = pygame.transform.smoothscale(self.sprites[key], size)
        return self.sprites[cache_key]

    def _build_hd_tiles(self):
        s = TILE_SIZE

        grass = pygame.Surface((s, s))
        grass.fill((48, 118, 42))
        if "grass" in self.sprites:
            grass.blit(self._get_scaled_sprite("grass", (s, s)), (0, 0))
        else:
            for y in range(0, s, 4):
                for x in range(0, s, 4):
                    h = (x * 19 + y * 37) % 17
                    col = (54 + h, 128 + h, 46 + h // 2)
                    pygame.draw.rect(grass, col, (x, y, 4, 4))
        self.tiles["G"] = grass

        road = grass.copy()
        if "road" in self.sprites:
            road = pygame.Surface((s, s))
            road.blit(self._get_scaled_sprite("road", (s, s)), (0, 0))
        else:
            pygame.draw.rect(road, (125, 92, 58), (6, 6, s-12, s-12), border_radius=16)
            pygame.draw.rect(road, (172, 134, 88), (10, 10, s-20, s-20), border_radius=12)
        self.tiles["R"] = road

        mtn = grass.copy()
        if "mountain" in self.sprites:
            mtn = pygame.Surface((s, s))
            mtn.blit(self._get_scaled_sprite("mountain", (s, s)), (0, 0))
        else:
            pygame.draw.polygon(mtn, (82, 86, 98), [(6, s-14), (28, 12), (56, s-14)])
            pygame.draw.polygon(mtn, (112, 116, 130), [(22, s-10), (54, 8), (s-6, s-10)])
        self.tiles["M"] = mtn

        forest = grass.copy()
        if "forest" in self.sprites:
            forest = pygame.Surface((s, s))
            forest.blit(self._get_scaled_sprite("forest", (s, s)), (0, 0))
        else:
            for tx, ty, tr in [(26, 28, 20), (58, 32, 22), (40, 52, 24)]:
                pygame.draw.circle(forest, (24, 76, 30), (tx, ty), tr)
        self.tiles["F"] = forest

        water = pygame.Surface((s, s))
        water.fill((24, 82, 162))
        if "water" in self.sprites:
            water.blit(self._get_scaled_sprite("water", (s, s)), (0, 0))
        self.tiles["W"] = water

        lava = pygame.Surface((s, s))
        lava.fill((62, 20, 18))
        if "lava" in self.sprites:
            lava.blit(self._get_scaled_sprite("lava", (s, s)), (0, 0))
        self.tiles["L"] = lava

        bridge = water.copy()
        if "bridge" in self.sprites:
            bridge = pygame.Surface((s, s))
            bridge.blit(self._get_scaled_sprite("bridge", (s, s)), (0, 0))
        self.tiles["B"] = bridge

        sand = pygame.Surface((s, s))
        sand.fill((210, 185, 130))
        if "sand" in self.sprites:
            sand.blit(self._get_scaled_sprite("sand", (s, s)), (0, 0))
        else:
            for y in range(0, s, 4):
                for x in range(0, s, 4):
                    h = (x * 23 + y * 41) % 19
                    col = (200 + h, 178 + h, 120 + h // 2)
                    pygame.draw.rect(sand, col, (x, y, 4, 4))
            for wy in range(8, s - 4, 16):
                pygame.draw.arc(sand, (225, 205, 155), (2, wy, s - 4, 10), 0, math.pi, 2)
        self.tiles["S"] = sand

    def draw_object(self, screen, obj, px, py, tick):
        s = TILE_SIZE
        cx, cy = px + s // 2, py + s // 2
        otype = obj["Type"]
        bob = int(math.sin(tick * 0.08) * 4)

        shadow = pygame.Surface((s-20, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 95), (0, 0, s-20, 18))
        screen.blit(shadow, (px+10, py+s-22))

        if otype == "Gold":
            if "Chest" in obj["Name"]:
                sp = self._get_scaled_sprite("chest", (s-16, s-16))
                if sp:
                    screen.blit(sp, (px+8, py+8))
                else:
                    pygame.draw.rect(screen, (135, 76, 28), (px+16, py+24, s-32, s-36), border_radius=6)
            else:
                sp = self._get_scaled_sprite("gold_pile", (s-12, s-12))
                if sp:
                    screen.blit(sp, (px+6, py+6))
                else:
                    pygame.draw.circle(screen, (245, 195, 30), (cx, cy+6), 16)

        elif otype == "Mine":
            sp = self._get_scaled_sprite("mine", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4))

        elif otype == "Guard":
            sp = self._get_scaled_sprite("guard", (s-6, s-6))
            if sp:
                screen.blit(sp, (px+3, py+3))

        elif otype == "Mage":
            sp = self._get_scaled_sprite("mage", (s-6, s-6))
            if sp:
                screen.blit(sp, (px+3, py+3+bob))

        elif otype in ("Dwelling", "Boss"):
            key = "dragon_green" if otype == "Dwelling" else "dragon_black"
            sp = self._get_scaled_sprite(key, (s, s))
            if sp:
                screen.blit(sp, (px, py+bob))

        elif otype == "Monster":
            sp = self._get_scaled_sprite("monster", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4+bob))

        elif otype == "Sign":
            is_read = obj.get("Read", False)
            sp = self._get_scaled_sprite("sign", (s-12, s-12))
            if sp:
                screen.blit(sp, (px+6, py+6))
            if is_read:
                bx, by = px + s - 14, py + 12
                pygame.draw.circle(screen, (15, 35, 20), (bx, by), 9)
                pygame.draw.circle(screen, (45, 195, 85), (bx, by), 7)
                pygame.draw.lines(screen, (255, 255, 255), False, [
                    (bx - 4, by), (bx - 1, by + 3), (bx + 4, by - 3)
                ], 2)

        elif otype == "NPC":
            sp = self._get_scaled_sprite("npc", (s-10, s-10))
            if sp:
                screen.blit(sp, (px+5, py+5+bob))

        elif otype == "Sphinx":
            sp = self._get_scaled_sprite("sphinx", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4+bob))

        elif otype == "Shrine":
            sp = self._get_scaled_sprite("shrine", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4))

    def draw_hero(self, screen, px, py, tick):
        s = TILE_SIZE
        bob = int(math.sin(tick * 0.12) * 3)
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        sp = self._get_scaled_sprite("hero", (s, s))
        if sp:
            surf.blit(sp, (0, bob))
        else:
            pygame.draw.circle(surf, (75, 150, 240), (42, 30+bob), 16)
        screen.blit(surf, (px, py))


class StepLimitExceeded(Exception):
    pass


class HeroesGameEngine:
    @staticmethod
    def _exec_safe(code_obj_or_str, glb, loc=None, max_steps=25000):
        steps = [0]
        def _trace(frame, event, arg):
            if event == 'line':
                steps[0] += 1
                if steps[0] > max_steps:
                    raise StepLimitExceeded(
                        f'⚡ Endless Loop Guard! Your code ran over {max_steps:,} steps without stopping. Check your while-loop condition!'
                    )
            return _trace
        sys.settrace(_trace)
        try:
            if loc is None:
                exec(code_obj_or_str, glb)
            else:
                exec(code_obj_or_str, glb, loc)
        finally:
            sys.settrace(None)

    @staticmethod
    def _get_clipboard_text() -> str:
        try:
            import tkinter as tk
            r = tk.Tk()
            r.withdraw()
            txt = r.clipboard_get()
            r.destroy()
            return str(txt)
        except Exception:
            return ''

    @staticmethod
    def _wrap_text(text, font, max_width):
        if text is None or text == "":
            return [""]
        max_width = max(40, int(max_width))
        out_lines = []
        for raw_line in str(text).splitlines() or [""]:
            if not raw_line:
                out_lines.append("")
                continue
            # Preserve leading indentation
            leading_len = len(raw_line) - len(raw_line.lstrip(" "))
            leading = " " * min(leading_len, 8)
            words = raw_line.strip(" ").split(" ")
            current_line = leading
            for word in words:
                if not word:
                    continue
                # If a single word/URL is wider than max_width, break it by characters
                if font.size(word)[0] > max_width - font.size(leading)[0]:
                    if current_line.strip():
                        out_lines.append(current_line)
                        current_line = leading
                    chunk = current_line
                    for ch in word:
                        if font.size(chunk + ch)[0] <= max_width:
                            chunk += ch
                        else:
                            if chunk:
                                out_lines.append(chunk)
                            chunk = leading + ch
                    current_line = chunk
                    continue
                test_line = f"{current_line} {word}" if current_line.strip() else f"{leading}{word}"
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line.strip():
                        out_lines.append(current_line)
                    current_line = f"{leading}{word}"
            if current_line or not out_lines:
                out_lines.append(current_line)
        return out_lines if out_lines else [""]

    @staticmethod
    def _render_fitted(text: str, font, color, max_width: int) -> pygame.Surface:
        """Render a single-line surface, smoothly scaling its width down if it exceeds max_width."""
        surf = font.render(str(text), True, color)
        max_w = max(20, int(max_width))
        w, h = surf.get_size()
        if w > max_w and w > 0:
            new_h = max(10, int(h * (max_w / w)))
            surf = pygame.transform.smoothscale(surf, (max_w, new_h))
        return surf

    def _blit_button_label(self, rect: pygame.Rect, text: str, font, color, pad_x: int = 12):
        """Render and center a label inside a button rect, guaranteed never to overflow."""
        surf = self._render_fitted(text, font, color, rect.w - pad_x * 2)
        bx = rect.x + (rect.w - surf.get_width()) // 2
        by = rect.y + (rect.h - surf.get_height()) // 2
        self.canvas.blit(surf, (bx, by))

    def math_to_grid(self, x: int, y: int) -> tuple[int, int]:
        return (int(self.origin_col + x), int(self.origin_row - y))

    def grid_to_math(self, col: int, row: int) -> tuple[int, int]:
        return (int(col - self.origin_col), int(self.origin_row - row))

    @property
    def hero_x(self) -> int:
        return self.hero_col - self.origin_col

    @property
    def hero_y(self) -> int:
        return self.origin_row - self.hero_row

    @hero_x.setter
    def hero_x(self, val: int):
        self.hero_col = self.origin_col + int(val)

    @hero_y.setter
    def hero_y(self, val: int):
        self.hero_row = self.origin_row - int(val)

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Heroes of Python -- Self-Teaching Campaign & Duel Edition")

        info = pygame.display.Info()
        init_w = min(max(1600, int(info.current_w * 0.85)), info.current_w)
        init_h = min(max(900, int(info.current_h * 0.85)), info.current_h)

        self.window = pygame.display.set_mode((init_w, init_h), pygame.RESIZABLE)
        self.canvas = pygame.Surface((VIRTUAL_W, VIRTUAL_H))
        self.fullscreen = False
        self.last_window_size = (init_w, init_h)

        self.clock = pygame.time.Clock()
        self.art = HDArtRenderer()
        self.sfx = RetroSoundFX()

        mono_font = "dejavusansmono"
        ui_font = "dejavusans"
        self.font_coord = pygame.font.SysFont(mono_font, 16, bold=True)
        self.font_sm = pygame.font.SysFont(mono_font, 18, bold=True)
        self.font_md = pygame.font.SysFont(ui_font, 22, bold=True)
        self.font_lg = pygame.font.SysFont(ui_font, 25, bold=True)
        self.font_title = pygame.font.SysFont(ui_font, 32, bold=True)
        self.font_console = pygame.font.SysFont(mono_font, 20, bold=False)
        self.font_console_bold = pygame.font.SysFont(mono_font, 20, bold=True)

        self.show_grid = True
        self.last_mtime = 0
        self.tick = 0
        self.floating_texts = []
        self.current_act = "act1"
        self.scenario = None
        self.origin_col = 0
        self.origin_row = 10
        self.hero_col = 1
        self.hero_row = 0

        self.xp = 0
        self.hero_level = 1
        self.skills_unlocked: list[str] = []
        self.artifacts: list[str] = []
        self.act_stars: dict[str, int] = {}
        self.persistent_memory: dict[str, Any] = {}
        self.hint_tier = 0
        self.pill_rects: list[tuple[pygame.Rect, str]] = []

        self.load_scenario("act1")
        self.reset_game()

        self.console_add_output("✦ Welcome to Heroes of Python! (Click any Spell Pill above to insert it!)", (250, 215, 75))
        self.console_add_output("  Stuck? Click [? Archmage Hint] (or type 'hint') for 3 levels of help!", (165, 250, 175))
        self.console_add_output("  Ctrl+Enter = Commit Turn | Ctrl+D = Duel Mode | Ctrl+1..7 = Switch Act", (140, 180, 200))

        if self.load_game():
            self.status_msg = f"Game Loaded! Day {self.day}, Hero at ({self.hero_x}, {self.hero_y})."
            self.status_color = (120, 240, 150)
            self.console_add_output(f"═══ Day {self.day} ═══ Hero at ({self.hero_x}, {self.hero_y})", (250, 215, 75))

    def _current_quest_key(self) -> str:
        if self.current_act == "act1":
            return f"act1_q{min(3, self.quest_stage)}"
        act_Order = {
            "act2": ["comments", "output", "variables", "data_types", "constants", "operators", "type_cast", "strings"],
            "act3": ["act3_weather", "act3_look", "act3_shrine", "act3_compound", "act3_battle"],
            "act4": ["act4_lists", "act4_grid", "act4_for", "act4_while", "act4_battle"],
            "act5": ["act5_def", "act5_return", "act5_scope"],
            "act6": ["act6_torches", "act6_hanoi", "act6_hydra"],
            "act7": ["act7_binary", "act7_hex", "act7_bitwise"],
        }
        for q in act_Order.get(self.current_act, []):
            if q not in self.completed_quests:
                return q
        return "act1_q1"

    def request_archmage_hint(self):
        qkey = self._current_quest_key()
        tiers = PROGRESSIVE_HINTS.get(qkey)
        if not tiers:
            self.console_add_output("★ Archmage: All quests in this Act are complete! March to the Boss!", (255, 215, 0))
            return
        idx = min(self.hint_tier, 2)
        self.hint_tier = (self.hint_tier + 1) % 3
        self.sfx.play("magic")
        if idx == 0:
            self.console_add_output(tiers[0], (255, 225, 110))
            self.console_add_output("   (Click [? Archmage Hint] again for the exact code pattern!)", (160, 190, 220))
        elif idx == 1:
            self.console_add_output(tiers[1], (150, 245, 180))
            self.console_add_output("   (Click [? Archmage Hint] once more to auto-fill a starter spell!)", (160, 190, 220))
        else:
            starter = tiers[2]
            self.console_add_output(f"✍ HINT 3 (Example — Type this yourself below!):  {starter}", (255, 215, 0))
            vinfo = QUEST_VIDEOS.get(qkey)
            if vinfo:
                self.console_add_output(f"▶ Video Lesson: {vinfo[0]} -> {vinfo[1]} (Type 'video' or click [▶ Video] to open!)", (135, 220, 255))
            else:
                self.console_add_output("   Type the spell into the >>> box and press Enter!", (180, 255, 195))

    def watch_topic_video(self, custom_url=None, custom_title=None):
        qkey = self._current_quest_key()
        title, url = (custom_title, custom_url) if custom_url else QUEST_VIDEOS.get(qkey, ("Python For-Loops", "http://www.youtube.com/watch?v=KWgYha0clzw"))
        self.sfx.play("magic")
        self.console_add_output(f"▶ Opening Video Tutorial: {title}", (255, 215, 0))
        self.console_add_output(f"   URL: {url}", (135, 220, 255))
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _award_xp(self, amount: int, reason: str = ""):
        self.xp += amount
        new_lvl = 1 + self.xp // 250
        if new_lvl > self.hero_level:
            self.hero_level = new_lvl
            self.sfx.play("fanfare")
            self.console_add_output(f"★ LEVEL UP! Hero reached Level {self.hero_level}! (+{amount} XP)", (255, 215, 0))
            px = self.hero_col * TILE_SIZE + 8
            py = self.hero_row * TILE_SIZE - 30
            self.floating_texts.append([f"LEVEL UP! Lv.{self.hero_level}!", px, py, 95, (255, 215, 0)])
        elif reason:
            self.sfx.play("coin")
            self.console_add_output(f"★ {reason} (+{amount} XP)", (255, 215, 0))

    def _complete_quest(self, quest_id: str, label: str = ""):
        if quest_id not in self.completed_quests:
            self.completed_quests.add(quest_id)
            self.hint_tier = 0
            self._award_xp(150, label or f"Quest '{quest_id}' Complete!")

    def _cheat_step(self, dcol: int, drow: int):
        ncol = self.hero_col + dcol
        nrow = self.hero_row + drow
        if not (0 <= ncol < MAP_COLS and 0 <= nrow < MAP_ROWS):
            return
        obj = self.get_object_at(ncol, nrow)
        if obj:
            px, py = ncol * TILE_SIZE + 8, nrow * TILE_SIZE
            if obj["Type"] == "Sign":
                obj["Read"] = True
                obj["Collected"] = False
                self.console_add_output(f"§ Sign ({obj['X']}, {obj['Y']}): {obj['Description']}", (255, 225, 95))
            elif not obj["Collected"]:
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
                    obj["Collected"] = True
                if obj["Type"] == "Gold":
                    self.gold += obj["Value"]
                    self.sfx.play("coin")
                    self.floating_texts.append([f"+{obj['Value']} Gold!", px, py, 65, (255, 225, 55)])
                elif obj["Type"] == "Mine":
                    self.wood += obj["Value"]
                    self.sfx.play("coin")
                    self.floating_texts.append([f"+{obj['Value']} Wood/day!", px, py, 65, (120, 225, 255)])
                elif obj["Type"] == "Dwelling" and self.current_act == "act1":
                    self.dragons += obj["Value"]
                    self.sfx.play("fanfare")
                    self.floating_texts.append([f"+{obj['Value']} Green Dragons!", px, py, 80, (85, 255, 130)])
                    if self.quest_stage < 3:
                        self.quest_stage = 3
                elif obj["Type"] in ("Guard", "Mage"):
                    self.sfx.play("magic")
                    if self.current_act == "act1" and self.quest_stage < 2:
                        self.quest_stage = 2
                    self.floating_texts.append(["✦ Gate Bypassed!", px, py, 60, (140, 255, 150)])
                elif obj["Type"] == "NPC":
                    if "Key Merchant" in obj["Name"]:
                        self.keys_held.add("blue")
                        self.floating_texts.append(["♦ Got Blue Key!", px, py, 75, (110, 220, 255)])
                    elif "Arena" in obj["Name"] and self.current_act == "act3":
                        obj["Collected"] = False
                        self._start_battle(multi_stack=False)
                    elif "General Morgan" in obj["Name"] and self.current_act == "act4":
                        obj["Collected"] = False
                        self._start_battle(multi_stack=True)
                    elif obj["Value"] > 0:
                        self.gold += obj["Value"]
                        self.floating_texts.append([f"+{obj['Value']} Gold!", px, py, 65, (255, 225, 55)])
                elif obj["Type"] == "Boss":
                    self.sfx.play("fanfare")
                    self.victory = True
                    self.act_stars[self.current_act] = 3
        self.hero_col = ncol
        self.hero_row = nrow
        self.sfx.play("step")
        if self.current_act == "act2":
            self._trigger_zone_tips()
        elif self.current_act == "act3":
            self._trigger_act3_zone_tips()
        self.save_game()
        self.run_preview()

    def window_to_virtual(self, pos):
        ww, wh = self.window.get_size()
        scale = min(ww / VIRTUAL_W, wh / VIRTUAL_H)
        scaled_w = int(VIRTUAL_W * scale)
        scaled_h = int(VIRTUAL_H * scale)
        offset_x = (ww - scaled_w) // 2
        offset_y = (wh - scaled_h) // 2
        vx = int((pos[0] - offset_x) / scale)
        vy = int((pos[1] - offset_y) / scale)
        return vx, vy

    def _get_active_code(self) -> str:
        if self.console_commands:
            return "\n".join(self.console_commands)
        my_hero_file = os.path.join(PROJECT_DIR, "my_hero.py")
        if os.path.exists(my_hero_file):
            try:
                with open(my_hero_file, "r", encoding="utf-8") as f:
                    src = f.read()
                idx = src.find("def plan_turn")
                return src[idx:] if idx >= 0 else src
            except Exception:
                return ""
        return ""

    def save_game(self):
        try:
            data = {
                "current_act": self.current_act,
                "hero_x": self.hero_x,
                "hero_y": self.hero_y,
                "hero_col": self.hero_col,
                "hero_row": self.hero_row,
                "gold": self.gold,
                "wood": self.wood,
                "dragons": self.dragons,
                "day": self.day,
                "quest_stage": self.quest_stage,
                "victory": self.victory,
                "xp": self.xp,
                "hero_level": self.hero_level,
                "skills_unlocked": self.skills_unlocked,
                "artifacts": self.artifacts,
                "act_stars": self.act_stars,
                "persistent_memory": self.persistent_memory,
                "grid": self.grid,
                "collected_ids": [obj["ID"] for obj in self.objects if obj["Collected"] and obj["Type"] != "Sign"],
                "read_sign_ids": [obj["ID"] for obj in self.objects if obj.get("Read", False)],
                "shown_tips": list(self.shown_tips),
                "completed_quests": list(self.completed_quests),
                "hero_log": self.hero_log[-20:],
                "sphinx_answers_correct": self.sphinx_answers_correct,
                "battle_won": getattr(self, "battle_won", False),
                "shrine_solved": getattr(self, "shrine_solved", False),
                "keys_held": list(getattr(self, "keys_held", set())),
                "shrine_levers": getattr(self, "shrine_levers", {}),
                "lit_torches": [list(t) for t in getattr(self, "lit_torches", set())],
                "hanoi_pegs": getattr(self, "hanoi_pegs", {"A": [3, 2, 1], "B": [], "C": []}),
                "obelisk_bits": getattr(self, "obelisk_bits", "00000000"),
                "army_formation": getattr(self, "army_formation", ["Pikeman", "Archer"]),
            }
            with open(os.path.join(PROJECT_DIR, "savegame.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print("Failed to save game:", e)

    def load_game(self):
        save_path = os.path.join(PROJECT_DIR, "savegame.json")
        if not os.path.exists(save_path):
            return False
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_act = data.get("current_act", "act1")
            if saved_act != self.current_act:
                self.load_scenario(saved_act)
                self.reset_game()
                self.current_act = saved_act
            else:
                sc = self.scenario or {}
                origin = sc.get("origin", [0, 10])
                self.origin_col = origin[0]
                self.origin_row = origin[1]
            if "hero_col" in data and "hero_row" in data:
                self.hero_col = data["hero_col"]
                self.hero_row = data["hero_row"]
            else:
                self.hero_x = data.get("hero_x", 1)
                self.hero_y = data.get("hero_y", 10)
            self.gold = data.get("gold", 0)
            self.wood = data.get("wood", 0)
            self.dragons = data.get("dragons", 0)
            self.day = data.get("day", 1)
            self.quest_stage = data.get("quest_stage", 1)
            self.victory = data.get("victory", False)
            self.xp = data.get("xp", 0)
            self.hero_level = data.get("hero_level", 1)
            self.skills_unlocked = data.get("skills_unlocked", [])
            self.artifacts = data.get("artifacts", [])
            self.act_stars = data.get("act_stars", {})
            self.persistent_memory = data.get("persistent_memory", {})
            if "Boots of Speed" in self.artifacts:
                self.max_mp = (self.scenario.get("max_mp", 12.0) if self.scenario else 12.0) + 4.0
            if "grid" in data:
                self.grid = data["grid"]
            collected_ids = set(data.get("collected_ids", []))
            read_sign_ids = set(data.get("read_sign_ids", []))
            for obj in self.objects:
                if obj["Type"] == "Sign":
                    if obj["ID"] in read_sign_ids or obj["ID"] in collected_ids:
                        obj["Read"] = True
                    obj["Collected"] = False
                elif obj["ID"] in collected_ids:
                    obj["Collected"] = True
            self.shown_tips = set(data.get("shown_tips", []))
            self.completed_quests = set(data.get("completed_quests", []))
            self.hero_log = data.get("hero_log", [])
            self.sphinx_answers_correct = data.get("sphinx_answers_correct", 0)
            self.battle_won = data.get("battle_won", False)
            self.shrine_solved = data.get("shrine_solved", False)
            self.keys_held = set(data.get("keys_held", []))
            self.shrine_levers = data.get("shrine_levers", {"red": False, "blue": False, "green": False})
            self.lit_torches = {tuple(t) for t in data.get("lit_torches", [])}
            self.hanoi_pegs = data.get("hanoi_pegs", {"A": [3, 2, 1], "B": [], "C": []})
            self.obelisk_bits = data.get("obelisk_bits", "00000000")
            self.army_formation = data.get("army_formation", ["Pikeman", "Archer"])
            self._apply_act3_weather_grid()
            return True
        except Exception as e:
            print("Failed to load savegame:", e)
            return False

    def reset_game(self, clear_save=False):
        if clear_save:
            save_path = os.path.join(PROJECT_DIR, "savegame.json")
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
        sc = self.scenario or {}
        origin = sc.get("origin", [0, 10])
        self.origin_col = origin[0]
        self.origin_row = origin[1]
        map_file = os.path.join(PROJECT_DIR, sc.get("map_file", "game_engine/scenarios/act1_map.csv"))
        obj_file = os.path.join(PROJECT_DIR, sc.get("objects_file", "game_engine/scenarios/act1_objects.csv"))
        self.grid = self._load_map(map_file)
        self.base_grid = self._load_map(map_file)
        self.objects = self._load_objects(obj_file)
        start = sc.get("hero_start", [1, 10])
        self.hero_x = start[0]
        self.hero_y = start[1]
        self.gold = sc.get("starting_gold", 0)
        self.wood = sc.get("starting_wood", 0)
        self.dragons = sc.get("starting_dragons", 0)
        self.day = 1
        base_mp = sc.get("max_mp", 12.0)
        self.max_mp = base_mp + (4.0 if "Boots of Speed" in getattr(self, "artifacts", []) else 0.0)
        self.quest_stage = 1
        self.victory = False
        self.hint_tier = 0
        self.used_loop_in_act = False
        self.status_msg = "Check the Spellbook bar above, type a spell, or click [? Archmage Hint]!"
        self.status_color = (120, 240, 150)
        self.preview_data: dict[str, Any] = {
            "mp_used": 0.0, "path": [], "terraforms": [], "valid": False,
            "picked_ids": [], "expected_gold": 0, "expected_wood": 0, "expected_dragons": 0
        }
        self.last_mtime = 0

        self.console_input = ""
        self.console_cursor_pos = 0
        self.console_commands: list[str] = []
        self.console_history: list[str] = []
        self.console_history_idx = -1
        self.console_output: list[tuple[str, tuple[int,int,int]]] = []
        self.console_cursor_blink = 0
        self.console_multiline = ""
        self.console_in_block = False
        self.console_active = True

        self.shown_tips: set[str] = set()
        self.completed_quests: set[str] = set()
        self.active_tip: dict[str, Any] | None = None
        self.hero_log: list[str] = []
        self.sphinx_answers_correct = 0

        self.in_battle = False
        self.battle_won = False
        self.battle_lost = False
        self.battle_round = 0
        self.battle_player: dict = {}
        self.battle_archer: dict = {}
        self.battle_enemy: dict = {}
        self.shrine_levers = {"red": False, "blue": False, "green": False}
        self.shrine_solved = False
        self.keys_held: set[str] = set()

        self.army_formation = ["Pikeman", "Archer"]
        self.lit_torches: set[tuple[int, int]] = set()
        self.hanoi_pegs: dict[str, list[int]] = {"A": [3, 2, 1], "B": [], "C": []}
        self.obelisk_bits = "00000000"

        self.btn_hint = pygame.Rect(0, 0, 0, 0)
        self.btn_commit = pygame.Rect(0, 0, 0, 0)
        self.btn_grid = pygame.Rect(0, 0, 0, 0)
        self.btn_undo = pygame.Rect(0, 0, 0, 0)
        self.btn_reset = pygame.Rect(0, 0, 0, 0)
        self.btn_next_act = None
        self.clickable_links: list[tuple[pygame.Rect, str, str]] = []
        self.tip_video_rect: pygame.Rect | None = None
        self.act_tab_rects: list[tuple[pygame.Rect, str]] = []
        self.duel_replay: dict[str, Any] | None = None
        self._apply_act3_weather_grid()
        self._populate_scout_and_sign_data()
        self._populate_act3_data()

    def load_scenario(self, scenario_id: str):
        config_path = os.path.join(ENGINE_DIR, "scenarios", f"{scenario_id}.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.scenario = json.load(f)
            self.current_act = scenario_id
        else:
            self.scenario = None
            self.current_act = scenario_id
        sc = self.scenario or {}
        origin = sc.get("origin", [0, 10])
        self.origin_col = origin[0]
        self.origin_row = origin[1]

    def start_act(self, act_id: str):
        prev_act = getattr(self, "current_act", "act1")
        self._archive_and_write_act_template(prev_act, act_id)
        self.load_scenario(act_id)
        self.reset_game(clear_save=True)
        self.console_output.clear()
        title = self.scenario.get("title", act_id) if self.scenario else act_id
        self.console_add_output(f"═══ {title} ({act_id.upper()}) ═══", (250, 215, 75))
        if self.scenario:
            self.console_add_output(self.scenario.get("subtitle", ""), (180, 200, 220))
        qkey = self._current_quest_key()
        if qkey in QUEST_VIDEOS:
            vt, vu = QUEST_VIDEOS[qkey]
            self.console_add_output(f"▶ Video Guide for this Act: {vt} -> {vu} (Click [▶ Video] or type 'video')", (135, 220, 255))
        if act_id == "act2":
            self.console_commands = [
                "move_to(-8, 0)",
                "move_to(-5, 5)",
                "move_to(7, -5)",
            ]
            self.console_add_output("§ CURSED SCROLL LOADED! Lines 1 and 3 march you into danger!", (255, 160, 90))
            self.console_add_output("   Type 'silence 1' and 'silence 3' (or # comments) to comment them out!", (165, 250, 175))
            self.run_console_preview()
        else:
            self.console_add_output("Click [? Archmage Hint] anytime for step-by-step guidance!", (165, 250, 175))
        self.save_game()

    ARCHMAGE_TIPS: dict[str, dict[str, Any]] = {
        "comments": {
            "title": "✦ The Scroll of Silence",
            "lines": [
                "Lines starting with # are invisible to Python.",
                "# this line does nothing — but humans can read it!",
                "Use # to SILENCE the cursed spells, then move safely.",
            ]
        },
        "output": {
            "title": "✦ The Hero's Voice",
            "lines": [
                'say("For Erathia!") shouts a message on the map.',
                'print("info") writes to your spell log below.',
                'The gate wants you to SAY the password!',
            ]
        },
        "variables": {
            "title": "✦ Names for Things",
            "lines": [
                "x = 5 stores the number 5 in a box called x.",
                "x, y = scout('Merchant') finds where the Merchant is!",
                "Then use: move_to(x, y)",
            ]
        },
        "data_types": {
            "title": "✦ Not Everything is a Number",
            "lines": [
                '3.5 is a float.  "hello" is a str.  True is a bool.',
                "Call answer_sphinx(3.5), answer_sphinx('hi'), answer_sphinx(True)!",
                "Answer all 3 riddles to master Data Types!",
            ]
        },
        "constants": {
            "title": "✦ The Laws of the Realm",
            "lines": [
                "COST = 60 names a price you use many times.",
                "UPPERCASE names = constants that never change.",
                "Define COST = 60 and recruit('Pikeman', 2) at the Barracks!",
            ]
        },
        "operators": {
            "title": "✦ The Art of Calculation",
            "lines": [
                "gold // 60 = how many you can buy (drops remainder).",
                "gold % 60 = the leftover gold (the change).",
                "Try: print(gold // 60) and walk through the Operators Gate!",
            ]
        },
        "type_cast": {
            "title": "✦ Shape-Shifting Magic",
            "lines": [
                'Signs give you TEXT: "1500" — that is NOT a number!',
                'Use int(read_sign(0, -3)) to turn text into a number.',
                'Use float(read_sign(2, -3)) for decimals!',
            ]
        },
        "strings": {
            "title": "✦ Words Have Power",
            "lines": [
                '"DRAGON"[0] is "D".  "NOGARD"[::-1] is "DRAGON".',
                '.upper() makes UPPERCASE.  .lower() makes lowercase.',
                "Use open_gate('NOGARD'[::-1]) to unlock the String Gate!",
            ]
        },
        "if_else": {
            "title": "✦ The Fork in the Road",
            "lines": [
                'if today() == "sandstorm": take the northern detour!',
                'else: go straight across the desert.',
                "Sandstorms block tile (3, 0) on sandstorm days!",
            ]
        },
        "look_ahead": {
            "title": "✦ Scout the Path",
            "lines": [
                'look(x, y) tells you what is at a tile.',
                'if look(9, 2) == "NPC": go around!',
                "Check before you move — or walk into danger!",
            ]
        },
        "boolean": {
            "title": "✦ True and False",
            "lines": [
                "and = BOTH must be true.  or = ONE is enough.",
                "not = flip True to False (or False to True).",
                "Use set_lever('red', True) and set_lever('blue', True)!",
            ]
        },
        "compound_if": {
            "title": "✦ Complex Decisions",
            "lines": [
                "if gold >= 500 and has_key('blue'):",
                "  Combine conditions with and / or / not.",
                "Visit the Key Merchant at (12, 2) for the blue key!",
            ]
        },
        "battle_intro": {
            "title": "✦ The Arena Awaits!",
            "lines": [
                "Step onto the Arena Master at (15, 0) and Commit!",
                "In battle, type: attack()  or  move_toward()  or  defend()",
                "Defeat the Troglodytes to unlock the Arena Gate!",
            ]
        },
    }

    def show_tip(self, tip_id: str):
        if tip_id in self.shown_tips:
            return
        tip_data = self.ARCHMAGE_TIPS.get(tip_id)
        if not tip_data:
            return
        self.shown_tips.add(tip_id)
        self.active_tip = dict(tip_data)
        if tip_id in TIP_VIDEOS:
            self.active_tip["video"] = TIP_VIDEOS[tip_id]
            vt, vu = TIP_VIDEOS[tip_id]
            self.console_add_output(f"▶ Topic Video ({vt}): {vu}  [Type 'video' to watch]", (135, 220, 255))

    def _check_quest(self, quest_id: str) -> bool:
        checkers: dict[str, Any] = {
            "comments": self._check_comments,
            "output": self._check_output,
            "variables": self._check_variables,
            "data_types": self._check_data_types,
            "constants": self._check_constants,
            "operators": self._check_operators,
            "type_cast": self._check_type_cast,
            "strings": self._check_strings,
        }
        checker = checkers.get(quest_id)
        return checker() if checker else False

    def _code_facts(self) -> dict:
        return ast_facts.analyze(self._get_active_code())

    def _check_comments(self) -> bool:
        return self._code_facts()["comment_lines"] >= 2

    def _check_output(self) -> bool:
        return any(a[0] == "say" and "erathia" in str(a[1]).lower()
                   for a in hero_api._actions)

    def _check_variables(self) -> bool:
        f = self._code_facts()
        return "scout" in f["calls"] and "=" in self._get_active_code()

    def _check_data_types(self) -> bool:
        return self.sphinx_answers_correct >= 3

    def _check_constants(self) -> bool:
        f = self._code_facts()
        return bool(f["constants"]) or bool(re.search(r"\b[A-Z_]{2,}\s*=", self._get_active_code()))

    def _check_operators(self) -> bool:
        f = self._code_facts()
        return "//" in f["operators"] or "%" in f["operators"]

    def _check_type_cast(self) -> bool:
        f = self._code_facts()
        return "int" in f["casts"] or "float" in f["casts"]

    def _check_strings(self) -> bool:
        return any(a[0] == "open_gate" and a[1].upper() == "DRAGON"
                   for a in hero_api._actions)

    def _check_act2_guard(self, obj, sim):
        guard_quests = {
            4: ("comments", "Click [? Archmage Hint] or type 2+ # comment lines first!"),
            6: ("output", 'Use say("For Erathia!") to shout the password!'),
            10: ("variables", "Use x, y = scout('Merchant') and move_to(x, y)!"),
            17: ("operators", "Use // or % to calculate! e.g. print(gold // 60)"),
            22: ("type_cast", "Read the signs with read_sign(x,y) and convert with int()!"),
            24: ("strings", 'Reverse "NOGARD" and use open_gate("DRAGON")!'),
        }
        guard_id = obj["ID"]
        if guard_id in guard_quests:
            quest_id, hint = guard_quests[guard_id]
            if quest_id in self.completed_quests or self._check_quest(quest_id):
                self._complete_quest(quest_id)
                return True, ""
            return False, hint
        return True, ""

    def _check_act4_guard(self, obj, sim):
        code = self._get_active_code()
        gid = obj["ID"]
        if gid == 3:
            ok = "act4_lists" in self.completed_quests or any(
                a[0] == "set_formation" and a[1][:2] == ["Archer", "Pikeman"]
                for a in hero_api._actions
            )
            if ok:
                self._complete_quest("act4_lists", "Quest 1 (Lists & Formation) Complete!")
                return True, ""
            return False, "Call set_formation(['Archer', 'Pikeman']) first!"
        if gid == 6:
            ok = "act4_grid" in self.completed_quests or "get_map(" in code
            if ok:
                self._complete_quest("act4_grid", "Quest 2 (2D Map Scan) Complete!")
                return True, ""
            return False, "Call get_map() in your code to scan the 2D grid!"
        if gid == 11:
            dug = any(a[0] == "dig" and a[1] >= 3 for a in hero_api._actions)
            if "for " in code:
                self._complete_quest("act4_for", "Quest 3 (For-Loop Waypoints) Complete!")
            ok = "act4_while" in self.completed_quests or (dug and "while " in code)
            if ok:
                self._complete_quest("act4_while", "Quest 4 (While-Loop Digging) Complete!")
                return True, ""
            return False, "Use while not dig(): pass to unearth the treasure!"
        if gid == 13:
            if getattr(self, "battle_won", False) or "act4_battle" in self.completed_quests:
                self._complete_quest("act4_battle", "Quest 5 (Multi-Stack Battle) Complete!")
                return True, ""
            return False, "Step on General Morgan (12, 6) & win the Multi-Stack Battle!"
        return True, ""

    def _check_act5_guard(self, obj, sim):
        code = self._get_active_code()
        gid = obj["ID"]
        if gid == 2:
            ok = "act5_def" in self.completed_quests or "def " in code
            if ok:
                self._complete_quest("act5_def", "Quest 1 (Custom Function def) Complete!")
                return True, ""
            return False, "Define a reusable function with 'def ' to bridge the rivers!"
        if gid == 6:
            tested = any(a[0] == "test_spell" and callable(a[1]) for a in hero_api._actions)
            ok = "act5_return" in self.completed_quests or ("return " in code and tested)
            if ok:
                self._complete_quest("act5_return", "Quest 2 (Return Values) Complete!")
                return True, ""
            return False, "Write a function with 'return' and pass it to test_spell(fn)!"
        if gid == 9:
            ok = "act5_scope" in self.completed_quests or bool(self.persistent_memory) or bool(hero_api.memory)
            if ok:
                self._complete_quest("act5_scope", "Quest 3 (Persistent Memory & Scope) Complete!")
                return True, ""
            return False, "Store a value in memory['code'] = 42 to remember across turns!"
        return True, ""

    def _check_act6_guard(self, obj, sim):
        f = self._code_facts()
        has_rec = bool(f.get("recursive"))
        gid = obj["ID"]
        if gid == 2:
            torches = len(self.lit_torches) + sum(1 for a in hero_api._actions if a[0] == "light_torch")
            ok = "act6_torches" in self.completed_quests or (torches >= 3 and (has_rec or "def " in self._get_active_code()))
            if ok:
                self._complete_quest("act6_torches", "Quest 1 (Recursive Torches) Complete!")
                return True, ""
            return False, "Write a recursive function (def) to light 3+ cavern tiles with light_torch(x, y)!"
        if gid == 5:
            sim_pegs = {k: list(v) for k, v in self.hanoi_pegs.items()}
            for a in hero_api._actions:
                if a[0] == "move_ring":
                    _, src, dst = a
                    if src in sim_pegs and dst in sim_pegs and sim_pegs[src]:
                        r_top = sim_pegs[src][-1]
                        if not sim_pegs[dst] or sim_pegs[dst][-1] > r_top:
                            sim_pegs[dst].append(sim_pegs[src].pop())
            ok = "act6_hanoi" in self.completed_quests or (len(sim_pegs.get("C", [])) == 3 and (has_rec or "def " in self._get_active_code()))
            if ok:
                self._complete_quest("act6_hanoi", "Quest 2 (Towers of Hanoi) Complete!")
                return True, ""
            return False, "Write a recursive function def hanoi(n,a,c,b): to move all 3 rings from 'A' to 'C'!"
        if gid == 8:
            hydra_ok = any(a[0] == "answer_hydra" and a[1] == 15 for a in hero_api._actions)
            ok = "act6_hydra" in self.completed_quests or (hydra_ok and (has_rec or "def " in self._get_active_code()))
            if ok:
                self._complete_quest("act6_hydra", "Quest 3 (Hydra Recursion Math) Complete!")
                return True, ""
            return False, "Write a recursive function def strikes(n): and call answer_hydra(strikes(3))!"
        return True, ""

    def _check_act7_guard(self, obj, sim):
        code = self._get_active_code()
        gid = obj["ID"]
        if gid == 3:
            vault_ok = any(a[0] == "open_vault" and a[1] == 173 for a in hero_api._actions)
            ok = "act7_binary" in self.completed_quests or vault_ok
            if ok:
                self._complete_quest("act7_binary", "Quest 1 (Binary & Bytes) Complete!")
                return True, ""
            return False, "Call set_obelisks('10101101') and open_vault(173)!"
        if gid == 6:
            hex_ok = any(a[0] == "dye_banner" and a[1] == "#FF8800" for a in hero_api._actions)
            ok = "act7_hex" in self.completed_quests or hex_ok
            if ok:
                self._complete_quest("act7_hex", "Quest 2 (Hexadecimal Banner) Complete!")
                return True, ""
            return False, "Dye the Crystal Banner with dye_banner('#FF8800')!"
        if gid == 9:
            has_bit = any(op in code for op in ("&", "|", "^", "<<", ">>"))
            ok = "act7_bitwise" in self.completed_quests or has_bit
            if ok:
                self._complete_quest("act7_bitwise", "Quest 3 (Bitwise Magic & XOR) Complete!")
                return True, ""
            return False, "Use a bitwise operator (&, |, ^, <<, >>) in your spell code!"
        return True, ""

    def _api_read_sign(self, x: int, y: int) -> str:
        coord = (int(x), int(y))
        hero_api._read_signs.add(coord)
        for obj in self.objects:
            if obj["X"] == int(x) and obj["Y"] == int(y) and obj["Type"] == "Sign":
                obj["Read"] = True
                return obj["Description"]
        return ""

    def _build_hero_object(self):
        class Hero:
            pass
        h = Hero()
        h.x, h.y = self.hero_x, self.hero_y
        h.gold = self.gold
        h.wood = self.wood
        h.name = "Roland"
        h.mp = self.max_mp
        h.dragons = self.dragons
        h.day = self.day
        h.level = self.hero_level
        h.xp = self.xp
        h.army = list(self.army_formation)
        return h

    def _handle_say_actions(self):
        for act in hero_api._actions:
            if act[0] == "say":
                text = str(act[1])
                self.hero_log.append(text)
                px = self.hero_col * TILE_SIZE + 8
                py = self.hero_row * TILE_SIZE - 20
                self.floating_texts.append([f'» {text}', px, py, 90, (255, 255, 220)])
                if "erathia" in text.lower() and self.current_act == "act2":
                    self._complete_quest("output", "Quest 2 (Output) Complete!")

    def _handle_sphinx_answers(self):
        riddles = [
            ("float", "a number with a DECIMAL POINT (e.g. 3.5)"),
            ("str", "a piece of TEXT in quotes (e.g. 'hello')"),
            ("bool", "TRUE or FALSE (e.g. True)"),
        ]
        for act in hero_api._actions:
            if act[0] == "answer_sphinx":
                if self.sphinx_answers_correct >= len(riddles):
                    self.console_add_output("✦ All 3 Sphinx riddles already solved!", (110, 255, 130))
                    self._complete_quest("data_types", "Quest 4 (Data Types) Complete!")
                    break
                value = act[1]
                expected_type, desc = riddles[self.sphinx_answers_correct]
                actual_type = type(value).__name__
                if actual_type == expected_type:
                    self.sphinx_answers_correct += 1
                    self.sfx.play("magic")
                    self.console_add_output(
                        f"✓ Sphinx Riddle {self.sphinx_answers_correct}/3 Correct! {repr(value)} is a {actual_type}.",
                        (110, 255, 130)
                    )
                    if self.sphinx_answers_correct >= 3:
                        self._complete_quest("data_types", "Quest 4 (Data Types) Complete!")
                else:
                    self.sfx.play("fizzle")
                    self.console_add_output(
                        f"✗ Wrong type for Riddle {self.sphinx_answers_correct + 1}! {repr(value)} is a {actual_type}, not a {expected_type}.",
                        (255, 120, 120)
                    )
                    self.console_add_output(f"  The Sphinx wants: {desc}", (255, 200, 100))

    def _handle_recruit_and_constants(self):
        if self._check_constants() and self.current_act == "act2":
            self._complete_quest("constants", "Quest 5 (Constants) Complete!")
        for act in hero_api._actions:
            if act[0] == "recruit":
                _, unit_name, count = act
                cost_per = 60 if "pikeman" in unit_name.lower() else 100
                total_cost = cost_per * max(1, count)
                if self.gold >= total_cost:
                    self.gold -= total_cost
                    self.sfx.play("coin")
                    self.console_add_output(f"⚔ Recruited {count} {unit_name} for {total_cost} gold!", (110, 255, 130))
                else:
                    self.console_add_output(f"⚠ Need {total_cost}g for {count} {unit_name} (have {self.gold}g).", (255, 180, 100))

    def _handle_open_gate(self):
        for act in hero_api._actions:
            if act[0] == "open_gate":
                if str(act[1]).upper() == "DRAGON":
                    self._complete_quest("strings", "Quest 8 (Strings) Complete!")
                    self.console_add_output("✓ The gate swings open! DRAGON is correct!", (110, 255, 130))
                else:
                    self.sfx.play("fizzle")
                    self.console_add_output(f'✗ "{act[1]}" is not the password. Hint: reverse "NOGARD"!', (255, 120, 120))

    def _handle_advanced_act_actions(self):
        code = self._get_active_code()
        if "for " in code or "while " in code or "def " in code:
            self.used_loop_in_act = True
        if self.current_act == "act4" and "for " in code:
            self._complete_quest("act4_for", "Quest 3 (For-Loop Waypoints) Complete!")
        if self.current_act == "act5" and hero_api.memory:
            self.persistent_memory.update(hero_api.memory)
            self._complete_quest("act5_scope", "Quest 3 (Persistent Memory) Complete!")

        for act in hero_api._actions:
            kind = act[0]
            if kind == "set_formation":
                self.army_formation = act[1]
                self.console_add_output(f"❖ Army Formation set to: {self.army_formation}", (135, 220, 255))
                if self.army_formation[:2] == ["Archer", "Pikeman"]:
                    self._complete_quest("act4_lists", "Quest 1 (Lists & Formation) Complete!")
            elif kind == "dig":
                attempt = act[1]
                if attempt >= 3:
                    self.gold += 500
                    self.console_add_output("⚒ You unearthed the buried Grail Artifact! (+500 Gold)", (255, 215, 0))
                    self._complete_quest("act4_while", "Quest 4 (While-Loop Digging) Complete!")
            elif kind == "test_spell":
                fn = act[1]
                if callable(fn):
                    try:
                        r1 = fn(3, 4)
                        r2 = fn(10, 20)
                        if r1 is not None and r2 is not None:
                            self.console_add_output(f"✦ Spell Trial Passed! {fn.__name__}(3,4)->{r1}, (10,20)->{r2}", (110, 255, 130))
                            self._complete_quest("act5_return", "Quest 2 (Return Values) Complete!")
                        else:
                            self.console_add_output("✗ Your function returned None! Did you forget 'return'?", (255, 120, 120))
                    except Exception as e:
                        self.console_add_output(f"✗ Spell Trial error: {e}", (255, 120, 120))
            elif kind == "light_torch":
                _, tx, ty = act
                self.lit_torches.add((tx, ty))
                if len(self.lit_torches) >= 3:
                    self._complete_quest("act6_torches", "Quest 1 (Recursive Torches) Complete!")
            elif kind == "move_ring":
                _, src, dst = act
                pegs = self.hanoi_pegs
                if src in pegs and dst in pegs and pegs[src]:
                    ring = pegs[src][-1]
                    if not pegs[dst] or pegs[dst][-1] > ring:
                        pegs[dst].append(pegs[src].pop())
                        if len(pegs["C"]) == 3:
                            self.console_add_output("✦ All 3 Obelisk Rings moved to C!", (255, 215, 0))
                            self._complete_quest("act6_hanoi", "Quest 2 (Towers of Hanoi) Complete!")
            elif kind == "answer_hydra":
                if act[1] == 15:
                    self.console_add_output("✓ Correct! A size-3 Hydra takes 15 strikes (1 + 2*7)!", (110, 255, 130))
                    self._complete_quest("act6_hydra", "Quest 3 (Hydra Recursion Math) Complete!")
                else:
                    self.console_add_output(f"✗ {act[1]} is not right. Hint: size 0=1, 1=3, 2=7, 3=15!", (255, 120, 120))
            elif kind == "set_obelisks":
                self.obelisk_bits = act[1]
                self.console_add_output(f"⚡ Obelisks set to binary: {self.obelisk_bits}", (135, 220, 255))
            elif kind == "open_vault":
                if act[1] == 173:
                    self.gold += 700
                    self.console_add_output("✓ Dwarven Vault opened with 173 (0b10101101)! (+700 Gold)", (255, 215, 0))
                    self._complete_quest("act7_binary", "Quest 1 (Binary & Bytes) Complete!")
                else:
                    self.console_add_output(f"✗ Vault code {act[1]} failed! Convert '10101101' with int('10101101', 2).", (255, 120, 120))
            elif kind == "dye_banner":
                if act[1] == "#FF8800":
                    self.console_add_output("✦ Banner dyed blazing orange (#FF8800)!", (255, 165, 50))
                    self._complete_quest("act7_hex", "Quest 2 (Hexadecimal Banner) Complete!")
                else:
                    self.console_add_output(f"✗ {act[1]} is not #FF8800!", (255, 120, 120))

    def _populate_scout_and_sign_data(self):
        hero_api._scout_results = {}
        hero_api._sign_results = {}
        for obj in self.objects:
            if not obj["Collected"] or obj["Type"] == "Sign":
                hero_api._scout_results[obj["Name"]] = (obj["X"], obj["Y"])
                if obj["Type"] == "Sign":
                    hero_api._sign_results[(obj["X"], obj["Y"])] = obj["Description"]

    def _get_today(self) -> str:
        events = ["clear", "sandstorm", "oasis", "clear", "sandstorm",
                  "clear", "oasis", "clear", "sandstorm", "clear"]
        return events[self.day % len(events)]

    def _wander_npcs(self):
        import random
        rng = random.Random(self.day * 97 + 13)
        if self.current_act == "act2":
            spots = [(1, 3), (2, 3), (3, 2), (1, 2)]
            wx, wy = rng.choice(spots)
            for obj in self.objects:
                if "Wandering Merchant" in obj["Name"] and not obj["Collected"]:
                    obj["X"], obj["Y"] = wx, wy
                    obj["col"], obj["row"] = self.math_to_grid(wx, wy)
        elif self.current_act == "act3":
            spots = [(9, 2), (8, 2), (10, 2), (9, 3)]
            wx, wy = rng.choice(spots)
            for obj in self.objects:
                if "Wandering Monster" in obj["Name"] and not obj["Collected"]:
                    obj["X"], obj["Y"] = wx, wy
                    obj["col"], obj["row"] = self.math_to_grid(wx, wy)

    def _archive_and_write_act_template(self, old_act: str, new_act: str):
        """Archive non-default my_hero.py to spellbook_archive/ and write the new Act starter template."""
        my_hero_path = os.path.join(PROJECT_DIR, "my_hero.py")
        try:
            if os.path.exists(my_hero_path):
                with open(my_hero_path, "r", encoding="utf-8") as f:
                    cur_src = f.read()
                # Archive if the child wrote custom code (not just a default template)
                is_default = any(cur_src.strip() == tmpl.strip() for tmpl in ACT_TEMPLATES.values())
                if cur_src.strip() and not is_default and "pass" not in cur_src.splitlines()[-1]:
                    arch_dir = os.path.join(PROJECT_DIR, "spellbook_archive")
                    os.makedirs(arch_dir, exist_ok=True)
                    arch_path = os.path.join(arch_dir, f"{old_act}_my_hero.py")
                    idx_a = 2
                    while os.path.exists(arch_path):
                        arch_path = os.path.join(arch_dir, f"{old_act}_my_hero_{idx_a}.py")
                        idx_a += 1
                    with open(arch_path, "w", encoding="utf-8") as af:
                        af.write(cur_src)
                    self.console_add_output(f"✦ Archived your previous spellbook to spellbook_archive/{os.path.basename(arch_path)}", (180, 225, 255))
            tmpl = ACT_TEMPLATES.get(new_act)
            if tmpl:
                with open(my_hero_path, "w", encoding="utf-8") as f:
                    f.write(tmpl.lstrip("\n"))
                self.last_mtime = os.path.getmtime(my_hero_path)
        except Exception:
            pass

    def _draw_act_puzzle_hud(self):
        """Draw live visual puzzle HUD at the top of the map for Act VI (Hanoi Rings) and Act VII (8-Bit Obelisks)."""
        map_w = MAP_COLS * TILE_SIZE
        if self.current_act == "act6":
            hud_w, hud_h = 560, 108
            hx = (map_w - hud_w) // 2
            hy = 10
            panel = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
            pygame.draw.rect(panel, (18, 20, 32, 220), (0, 0, hud_w, hud_h), border_radius=12)
            pygame.draw.rect(panel, (215, 175, 65, 240), (0, 0, hud_w, hud_h), 2, border_radius=12)
            self.canvas.blit(panel, (hx, hy))

            pegs = getattr(self, "hanoi_pegs", {"A": [3, 2, 1], "B": [], "C": []})
            done_c = len(pegs.get("C", [])) == 3
            hdr_col = (110, 255, 140) if done_c else (255, 220, 90)
            hdr_txt = "✦ OBELISK RINGS (Towers of Hanoi) — SOLVED! ✦" if done_c else "✦ OBELISK RINGS: Move all 3 rings from Peg A to Peg C! ✦"
            hdr_s = self._render_fitted(hdr_txt, self.font_sm, hdr_col, hud_w - 24)
            self.canvas.blit(hdr_s, (hx + (hud_w - hdr_s.get_width()) // 2, hy + 6))

            ring_colors = {
                1: ((95, 220, 255), "1 (Small)"),
                2: ((255, 195, 65), "2 (Med)"),
                3: ((235, 85, 95), "3 (Large)"),
            }
            for idx_p, peg_name in enumerate(("A", "B", "C")):
                px = hx + 95 + idx_p * 185
                base_y = hy + hud_h - 24
                # Draw peg base & vertical post
                pygame.draw.rect(self.canvas, (130, 140, 165), (px - 56, base_y, 112, 6), border_radius=3)
                pygame.draw.rect(self.canvas, (160, 170, 195), (px - 4, base_y - 48, 8, 48), border_radius=3)
                lbl_s = self.font_coord.render(f"Peg {peg_name}", True, (220, 230, 245))
                self.canvas.blit(lbl_s, (px - lbl_s.get_width() // 2, base_y + 7))

                stack = pegs.get(peg_name, [])
                for level_i, r_size in enumerate(stack):
                    rw = 26 + r_size * 24
                    rh = 13
                    rx = px - rw // 2
                    ry = base_y - (level_i + 1) * (rh + 2)
                    rcol, _ = ring_colors.get(r_size, ((200, 200, 200), str(r_size)))
                    pygame.draw.rect(self.canvas, rcol, (rx, ry, rw, rh), border_radius=5)
                    pygame.draw.rect(self.canvas, (255, 255, 255), (rx, ry, rw, rh), 1, border_radius=5)

        elif self.current_act == "act7":
            hud_w, hud_h = 740, 96
            hx = (map_w - hud_w) // 2
            hy = 10
            panel = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
            pygame.draw.rect(panel, (18, 22, 34, 225), (0, 0, hud_w, hud_h), border_radius=12)
            pygame.draw.rect(panel, (110, 200, 255, 240), (0, 0, hud_w, hud_h), 2, border_radius=12)
            self.canvas.blit(panel, (hx, hy))

            bits_str = str(getattr(self, "obelisk_bits", "00000000")).ljust(8, "0")[:8]
            try:
                dec_val = int(bits_str, 2)
            except ValueError:
                dec_val = 0
            hex_val = f"0x{dec_val:02X}"
            matched = (dec_val == 173)
            hdr_col = (110, 255, 140) if matched else (250, 215, 75)
            hdr_txt = f"✦ 8-BIT OBELISK BYTE: {bits_str}  =  Decimal {dec_val} ({hex_val})  [Target: 10101101 = 173]"
            hdr_s = self._render_fitted(hdr_txt, self.font_sm, hdr_col, hud_w - 24)
            self.canvas.blit(hdr_s, (hx + (hud_w - hdr_s.get_width()) // 2, hy + 6))

            place_vals = [128, 64, 32, 16, 8, 4, 2, 1]
            for i, pval in enumerate(place_vals):
                is_on = (bits_str[i] == "1")
                bx = hx + 22 + i * 88
                by = hy + 32
                bw, bh = 78, 54
                bg_c = (45, 135, 195) if is_on else (32, 38, 52)
                bdr_c = (255, 230, 95) if is_on else (85, 95, 120)
                pygame.draw.rect(self.canvas, bg_c, (bx, by, bw, bh), border_radius=8)
                pygame.draw.rect(self.canvas, bdr_c, (bx, by, bw, bh), 2 if is_on else 1, border_radius=8)
                bit_s = self.font_md.render("1" if is_on else "0", True, (255, 245, 140) if is_on else (130, 140, 165))
                pv_s = self.font_coord.render(str(pval), True, (220, 240, 255) if is_on else (120, 130, 150))
                self.canvas.blit(bit_s, (bx + (bw - bit_s.get_width()) // 2, by + 4))
                self.canvas.blit(pv_s, (bx + (bw - pv_s.get_width()) // 2, by + 31))

    def _step_duel_replay(self):
        """Advance one event in the animated Programmable Duel Replay."""
        rep = self.duel_replay
        if not rep or rep.get("done"):
            return
        events = rep["events"]
        while rep["idx"] < len(events):
            ev = events[rep["idx"]]
            rep["idx"] += 1
            kind = ev.get("t")
            for sid_str, snap in ev.get("after", {}).items():
                st = rep["stacks"].get(int(sid_str))
                if st:
                    st.update(snap)
            if kind == "round":
                rep["round"] = ev.get("n", rep["round"])
                rep["banner"] = f"── Round {rep['round']} ──"
                return
            if kind == "move":
                st = rep["stacks"].get(ev.get("id"))
                path = ev.get("path", [])
                if st and path:
                    rep["active_id"] = st["id"]
                    rep["target_id"] = None
                    rep["banner"] = f"{st['count']}x {st['name']} moves to ({st['x']}, {st['y']})"
                    self.sfx.play("step")
                    return
            if kind in ("attack", "retaliate"):
                att = rep["stacks"].get(ev.get("id"))
                dfn = rep["stacks"].get(ev.get("target"))
                if att and dfn:
                    rep["active_id"] = att["id"]
                    rep["target_id"] = dfn["id"]
                    verb = "shoots" if ev.get("ranged") else ("retaliates on" if kind == "retaliate" else "strikes")
                    rep["banner"] = f"{att['name']} {verb} {dfn['name']} for {ev.get('damage', 0)} dmg! ({ev.get('kills', 0)} slain)"
                    self.sfx.play("arrow" if ev.get("ranged") else "sword")
                    return
            if kind == "spell":
                dfn = rep["stacks"].get(ev.get("target"))
                sp_name = ev.get("spell", "spell").upper()
                rep["active_id"] = None
                rep["target_id"] = dfn["id"] if dfn else None
                if ev.get("immune"):
                    rep["banner"] = f"✦ {sp_name} cast on {dfn['name'] if dfn else 'target'} — IMMUNE!"
                else:
                    rep["banner"] = f"✦ {sp_name} hits {dfn['name'] if dfn else 'target'} for {ev.get('damage', 0)} dmg! ({ev.get('kills', 0)} slain)"
                self.sfx.play("magic")
                return
            if kind == "defend":
                st = rep["stacks"].get(ev.get("id"))
                if st and not ev.get("auto"):
                    rep["active_id"] = st["id"]
                    rep["target_id"] = None
                    rep["banner"] = f"❖ {st['name']} defends (+30% defense)"
                    return
            if kind == "end":
                rep["done"] = True
                w = ev.get("winner")
                rep["banner"] = f"★ VICTORY! ({ev.get('reason', '')})" if w == "red" else f"✖ DEFEAT! ({ev.get('reason', '')})"
                self.sfx.play("fanfare" if w == "red" else "fizzle")
                return
        rep["done"] = True

    def _update_and_draw_duel_replay(self, mouse_x: int, mouse_y: int):
        """Render the 15x11 animated tactical battlefield for Programmable AI Duels."""
        rep = self.duel_replay
        if not rep:
            return
        if not rep.get("paused") and not rep.get("done"):
            if self.tick - rep.get("last_step_tick", 0) >= 12:
                rep["last_step_tick"] = self.tick
                self._step_duel_replay()

        map_w = MAP_COLS * TILE_SIZE
        map_h = MAP_ROWS * TILE_SIZE
        overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        overlay.fill((12, 15, 26, 238))
        self.canvas.blit(overlay, (0, 0))

        names = rep.get("names", {"red": "Red", "blue": "Blue"})
        title_txt = f"⚔ CODE DUEL REPLAY: {names.get('red')} vs {names.get('blue')} (Round {rep.get('round', 1)}) ⚔"
        title_s = self._render_fitted(title_txt, self.font_title, (255, 215, 75), map_w - 60)
        self.canvas.blit(title_s, (map_w // 2 - title_s.get_width() // 2, 14))

        banner_s = self._render_fitted(rep.get("banner", ""), self.font_md, (150, 235, 255), map_w - 80)
        self.canvas.blit(banner_s, (map_w // 2 - banner_s.get_width() // 2, 52))

        cols, rows = 15, 11
        cell = 72
        gx0 = (map_w - cols * cell) // 2
        gy0 = 86

        obstacles = {tuple(o) for o in rep.get("obstacles", [])}
        for r in range(rows):
            for c in range(cols):
                rx = gx0 + c * cell
                ry = gy0 + r * cell
                if (c, r) in obstacles:
                    pygame.draw.rect(self.canvas, (68, 62, 58), (rx, ry, cell - 2, cell - 2), border_radius=6)
                    pygame.draw.rect(self.canvas, (110, 100, 92), (rx, ry, cell - 2, cell - 2), 2, border_radius=6)
                else:
                    bg = (42, 48, 64) if (c + r) % 2 == 0 else (34, 40, 54)
                    pygame.draw.rect(self.canvas, bg, (rx, ry, cell - 2, cell - 2), border_radius=5)
                    pygame.draw.rect(self.canvas, (64, 76, 102), (rx, ry, cell - 2, cell - 2), 1, border_radius=5)

        sprite_for_unit = {
            "Pikeman": "guard", "Swordsman": "guard", "Cavalier": "hero",
            "Archer": "hero", "Monk": "mage", "Griffin": "dragon_green",
            "Angel": "mage", "Green Dragon": "dragon_green", "Black Dragon": "dragon_black",
        }
        for sid, st in rep.get("stacks", {}).items():
            if st.get("count", 0) <= 0:
                continue
            sx_cell = gx0 + st["x"] * cell
            sy_cell = gy0 + st["y"] * cell
            is_red = (st["side"] == "red")
            base_col = (35, 115, 210) if is_red else (195, 48, 52)
            pygame.draw.rect(self.canvas, base_col, (sx_cell + 4, sy_cell + 4, cell - 10, cell - 10), border_radius=8)
            if sid == rep.get("active_id"):
                pygame.draw.rect(self.canvas, (255, 235, 85), (sx_cell + 2, sy_cell + 2, cell - 6, cell - 6), 3, border_radius=9)
            elif sid == rep.get("target_id"):
                pygame.draw.rect(self.canvas, (255, 90, 90), (sx_cell + 2, sy_cell + 2, cell - 6, cell - 6), 3, border_radius=9)

            sp_key = sprite_for_unit.get(st["name"], "monster" if not is_red else "hero")
            sp = self.art._get_scaled_sprite(sp_key, (cell - 22, cell - 22))
            if sp:
                self.canvas.blit(sp, (sx_cell + 10, sy_cell + 6))

            lbl = self._render_fitted(f"{st['count']} {st['name'][:6]}", self.font_coord, (255, 255, 255), cell - 6)
            pygame.draw.rect(self.canvas, (15, 18, 26), (sx_cell + 3, sy_cell + cell - 21, cell - 8, 17), border_radius=4)
            self.canvas.blit(lbl, (sx_cell + (cell - lbl.get_width()) // 2, sy_cell + cell - 20))

        # Replay control bar at bottom of overlay
        ctrl_y = gy0 + rows * cell + 6
        pause_lbl = "▶ Resume (Space)" if rep.get("paused") else "❚❚ Pause (Space)"
        step_lbl = "Step +1 (→)"
        close_lbl = "✖ Close Replay (Esc)"
        b1 = pygame.Rect(map_w // 2 - 310, ctrl_y, 190, 32)
        b2 = pygame.Rect(map_w // 2 - 105, ctrl_y, 160, 32)
        b3 = pygame.Rect(map_w // 2 + 70, ctrl_y, 220, 32)
        rep["btn_pause"] = b1
        rep["btn_step"] = b2
        rep["btn_close"] = b3
        for rect_b, txt_b, col_b in [(b1, pause_lbl, (55, 95, 160)), (b2, step_lbl, (65, 120, 95)), (b3, close_lbl, (155, 55, 55))]:
            hov = rect_b.collidepoint((mouse_x, mouse_y))
            c_draw = tuple(min(255, ch + 30) for ch in col_b) if hov else col_b
            pygame.draw.rect(self.canvas, c_draw, rect_b, border_radius=7)
            pygame.draw.rect(self.canvas, (210, 225, 245), rect_b, 1, border_radius=7)
            self._blit_button_label(rect_b, txt_b, self.font_sm, (255, 255, 255), pad_x=8)

    def _run_code_duel(self, opponent="squire"):
        blue_file = os.path.join(ENGINE_DIR, ".duels", "parent_blue.py")
        cfg = {
            "budget": 5000,
            "handicap_gold": 0,
            "fallback_ai": opponent if opponent in ("squire", "knight", "warlord") else "squire",
            "red_name": "Hero's Army (duel_red.py)",
            "blue_name": f"Parent / {opponent.capitalize()} AI",
        }
        job = {
            "mode": "duel",
            "red_file": "duel_red.py",
            "blue_file": blue_file if (opponent == "parent" and os.path.exists(blue_file)) else None,
            "config": cfg,
            "seed": self.day * 37 + self.tick,
        }
        self.console_add_output(f"⚔ Running Programmable Duel vs {cfg['blue_name']}...", (255, 215, 0))
        res = sandbox.run_job(job, timeout=5.0)
        if not res.get("ok"):
            self.sfx.play("fizzle")
            self.console_add_output(f"✗ Duel Code Error: {res.get('error', 'Unknown error')}", (255, 110, 110))
            return
        b = res["battle"]
        winner = b["winner"]
        rounds = b["rounds"]
        red_surv = ", ".join(f"{s['count']}x {s['unit']}" for s in b["red_survivors"]) or "None"
        blue_surv = ", ".join(f"{s['count']}x {s['unit']}" for s in b["blue_survivors"]) or "None"
        evs = b.get("events", [])
        if evs and evs[0].get("t") == "start":
            start_ev = evs[0]
            stacks_dict = {int(s["id"]): dict(s) for s in start_ev.get("stacks", [])}
            self.duel_replay = {
                "names": start_ev.get("names", {"red": cfg["red_name"], "blue": cfg["blue_name"]}),
                "obstacles": start_ev.get("obstacles", []),
                "stacks": stacks_dict,
                "events": evs[1:],
                "idx": 0,
                "round": 1,
                "banner": "Battle Starting! Watch your duel_red.py code in action!",
                "active_id": None,
                "target_id": None,
                "paused": False,
                "done": False,
                "last_step_tick": self.tick,
            }
        if winner == "red":
            self.sfx.play("fanfare")
            self.console_add_output(f"★ DUEL VICTORY in {rounds} rounds! Survivors: {red_surv}", (110, 255, 130))
            self._award_xp(200, f"Defeated {cfg['blue_name']} in Code Duel!")
        else:
            self.sfx.play("fizzle")
            self.console_add_output(f"✖ DUEL DEFEAT in {rounds} rounds! Enemy left: {blue_surv}", (255, 120, 120))
            self.console_add_output("   Edit duel_red.py to upgrade your draft() or battle_turn() strategy!", (180, 220, 255))

    def _apply_act3_weather_grid(self):
        if self.current_act != "act3" or not hasattr(self, "base_grid") or not self.base_grid:
            return
        self.grid = [r[:] for r in self.base_grid]
        if self._get_today() == "sandstorm":
            c, r = self.math_to_grid(3, 0)
            if 0 <= c < MAP_COLS and 0 <= r < MAP_ROWS and (c, r) != (self.hero_col, self.hero_row):
                self.grid[r][c] = "M"

    def _populate_act3_data(self):
        hero_api._today_result = self._get_today()
        hero_api._keys_held = getattr(self, "keys_held", set())
        hero_api._map_grid = [r[:] for r in self.grid] if hasattr(self, "grid") and self.grid else []
        hero_api.memory.clear()
        hero_api.memory.update(getattr(self, "persistent_memory", {}))
        hero_api._lit_torches = set(getattr(self, "lit_torches", set()))
        hero_api._obelisk_bits = getattr(self, "obelisk_bits", "00000000")
        hero_api._look_results = {}
        if hasattr(self, "grid") and self.grid:
            for r in range(len(self.grid)):
                for c in range(len(self.grid[0])):
                    mx, my = self.grid_to_math(c, r)
                    hero_api._look_results[(mx, my)] = self.grid[r][c]
        for obj in self.objects:
            if not obj["Collected"]:
                hero_api._look_results[(obj["X"], obj["Y"])] = obj["Type"]

    def _handle_set_lever(self):
        levers = getattr(self, "shrine_levers", {"red": False, "blue": False, "green": False})
        for act in hero_api._actions:
            if act[0] == "set_lever":
                levers[act[1]] = act[2]
                self.console_add_output(f"⚙ Lever '{act[1]}' set to {act[2]}", (200, 180, 255))
        self.shrine_levers = levers
        for obj in self.objects:
            if obj["Type"] == "Shrine" and not obj["Collected"] and self.current_act == "act3":
                expr = obj["Description"]
                if self._eval_shrine(expr, levers):
                    obj["Collected"] = True
                    self.shrine_solved = True
                    self._complete_quest("act3_shrine", "Quest 3 (Boolean Shrines) Complete!")
                    self.console_add_output(f"✓ Shrine solved! Rule: {expr} = True!", (110, 255, 130))
                    px, py = obj.get("col", obj["X"]) * TILE_SIZE + 8, obj.get("row", obj["Y"]) * TILE_SIZE
                    self.floating_texts.append(["✦ Shrine Solved!", px, py, 80, (200, 180, 255)])

    def _eval_shrine(self, expression: str, levers: dict) -> bool:
        expr = expression.replace("AND", "and").replace("OR", "or").replace("NOT", "not")
        ns = {k: v for k, v in levers.items()}
        try:
            return bool(eval(expr, {"__builtins__": {}}, ns))
        except Exception:
            return False

    def _start_battle(self, multi_stack=False, duel_mode=False):
        self.in_battle = True
        self.battle_round = 0
        self.battle_won = False
        self.battle_lost = False
        bonus_atk = 3 if "Tome of Fire" in self.artifacts else 0
        self.battle_player = {
            "name": "Cavaliers" if duel_mode else "Pikemen",
            "count": 15 if duel_mode else (12 if multi_stack else 10),
            "hp": 12 if duel_mode else 10, "top_hp": 12 if duel_mode else 10,
            "atk": 6 + bonus_atk, "dfn": 5, "dmg_min": 2, "dmg_max": 4,
            "x": 1, "y": 1 if (multi_stack or duel_mode) else 2, "speed": 3,
        }
        self.battle_archer = {
            "name": "Archers", "count": 12 if duel_mode else (8 if multi_stack else 0),
            "hp": 10, "top_hp": 10,
            "atk": 7 + bonus_atk, "dfn": 3, "dmg_min": 2, "dmg_max": 4,
            "x": 0, "y": 3, "speed": 3,
        }
        self.battle_enemy = {
            "name": "Warlord Guard" if duel_mode else "Troglodytes",
            "count": 14 if duel_mode else (10 if multi_stack else 8),
            "hp": 7 if duel_mode else 5, "top_hp": 7 if duel_mode else 5,
            "atk": 5 if duel_mode else 4, "dfn": 4 if duel_mode else 3, "dmg_min": 1, "dmg_max": 3,
            "x": 7, "y": 2, "speed": 2,
        }
        self.sfx.play("sword")
        if duel_mode:
            self.console_add_output("═══ ⚔ HOTSEAT / AI DUEL ARENA STARTED! ⚔ ═══", (255, 215, 0))
        else:
            self.console_add_output("═══ TACTICAL ARENA BATTLE STARTED! ═══", (255, 80, 80))
        self.console_add_output("Click Spellbook pills or type: shoot() | attack() | move_toward() | defend()", (180, 220, 255))

    def _run_battle_round(self):
        if not getattr(self, "in_battle", False):
            return
        self.battle_round += 1
        p = self.battle_player
        ar = getattr(self, "battle_archer", {"count": 0})
        e = self.battle_enemy
        dist = abs(p["x"] - e["x"]) + abs(p["y"] - e["y"])

        action = None
        for act in hero_api._actions:
            if act[0] in ("battle_attack", "battle_shoot", "battle_move_toward", "battle_defend"):
                action = act[0]
                break

        if action == "battle_shoot" and ar.get("count", 0) > 0:
            self.sfx.play("arrow")
            dmg = self._battle_calc_damage(ar, e)
            self._battle_apply_damage(e, dmg)
            self.console_add_output(f"➤ Archers loose a volley for {dmg} ranged damage!", (140, 255, 160))
        elif action in ("battle_attack", "battle_shoot"):
            self.sfx.play("sword")
            if dist <= 1:
                dmg = self._battle_calc_damage(p, e)
                self._battle_apply_damage(e, dmg)
                self.console_add_output(f"⚔ {p['name']} strike for {dmg} damage!", (120, 255, 120))
            else:
                self._battle_move_unit(p, e)
                new_dist = abs(p["x"] - e["x"]) + abs(p["y"] - e["y"])
                if new_dist <= 1:
                    dmg = self._battle_calc_damage(p, e)
                    self._battle_apply_damage(e, dmg)
                    self.console_add_output(f"⚔ {p['name']} charge and strike for {dmg} damage!", (120, 255, 120))
                else:
                    self.console_add_output(f"→ {p['name']} advance to ({p['x']}, {p['y']}).", (200, 220, 255))
            if ar.get("count", 0) > 0 and e["count"] > 0:
                admg = self._battle_calc_damage(ar, e)
                self._battle_apply_damage(e, admg)
                self.console_add_output(f"➤ Archers support with {admg} arrow damage!", (140, 255, 160))
        elif action == "battle_move_toward":
            self.sfx.play("step")
            self._battle_move_unit(p, e)
            self.console_add_output(f"→ {p['name']} advance to ({p['x']}, {p['y']}).", (200, 220, 255))
        elif action == "battle_defend":
            p["defending"] = True
            self.console_add_output(f"❖ {p['name']} brace for impact! (+30% defense)", (100, 200, 255))
        else:
            self.console_add_output("? Type shoot(), attack(), move_toward(), or defend()!", (255, 200, 100))

        if e["count"] <= 0:
            self.battle_won = True
            self.in_battle = False
            self.sfx.play("fanfare")
            q_id = "act4_battle" if self.current_act == "act4" else "act3_battle"
            self._complete_quest(q_id, "Arena Battle Won!")
            self.console_add_output("═══ VICTORY! Enemy army defeated! ═══", (255, 215, 0))
            self.save_game()
            return

        dist = abs(p["x"] - e["x"]) + abs(p["y"] - e["y"])
        if dist <= 1:
            defense_bonus = 1.3 if p.get("defending") else 1.0
            dmg = self._battle_calc_damage(e, p, defense_mult=defense_bonus)
            self._battle_apply_damage(p, dmg)
            self.console_add_output(f"✖ {e['name']} counter-attack for {dmg} damage!", (255, 120, 120))
        else:
            self._battle_move_unit(e, p)
            self.console_add_output(f"→ {e['name']} advance to ({e['x']}, {e['y']}).", (255, 180, 180))

        p["defending"] = False

        if p["count"] <= 0:
            self.battle_lost = True
            self.in_battle = False
            self.sfx.play("fizzle")
            self.console_add_output("═══ DEFEAT! Press Ctrl+D or step on the Commander to retry! ═══", (255, 80, 80))
            return

        self.console_add_output(
            f"── Round {self.battle_round}: {p['name']} {p['count']} (HP {p['top_hp']}) | {e['name']} {e['count']} (HP {e['top_hp']}) ──",
            (180, 180, 200)
        )

    def _battle_calc_damage(self, attacker, defender, defense_mult=1.0):
        import random
        base = attacker["count"] * random.randint(attacker["dmg_min"], attacker["dmg_max"])
        atk, dfn = attacker["atk"], int(defender["dfn"] * defense_mult)
        if atk > dfn:
            base = int(base * (1 + 0.05 * min(atk - dfn, 60)))
        else:
            base = int(base * max(0.3, 1 - 0.025 * min(dfn - atk, 28)))
        return max(1, base)

    def _battle_apply_damage(self, stack, damage):
        remaining_dmg = damage
        while remaining_dmg > 0 and stack["count"] > 0:
            if remaining_dmg >= stack["top_hp"]:
                remaining_dmg -= stack["top_hp"]
                stack["count"] -= 1
                stack["top_hp"] = stack["hp"]
            else:
                stack["top_hp"] -= remaining_dmg
                remaining_dmg = 0

    def _battle_move_unit(self, mover, target):
        dx = target["x"] - mover["x"]
        dy = target["y"] - mover["y"]
        steps = min(mover["speed"], max(0, abs(dx) + abs(dy) - 1))
        for _ in range(steps):
            if abs(dx) >= abs(dy) and dx != 0:
                mover["x"] += 1 if dx > 0 else -1
            elif dy != 0:
                mover["y"] += 1 if dy > 0 else -1
            dx = target["x"] - mover["x"]
            dy = target["y"] - mover["y"]
            if abs(dx) + abs(dy) <= 1:
                break

    def _check_act3_weather(self) -> bool:
        code = self._get_active_code()
        return "if " in code and "today()" in code

    def _check_act3_look(self) -> bool:
        code = self._get_active_code()
        return "look(" in code and "if " in code

    def _check_act3_shrine(self) -> bool:
        return getattr(self, "shrine_solved", False)

    def _check_act3_compound(self) -> bool:
        code = self._get_active_code()
        has_bool = " and " in code or " or " in code or "not " in code
        return has_bool and "if " in code

    def _check_act3_battle(self) -> bool:
        return getattr(self, "battle_won", False)

    def _check_act3_guard(self, obj, sim):
        guard_quests = {
            5: ("act3_weather", "Use if/else with today() to handle weather!"),
            9: ("act3_look", "Use look(x, y) with if to check the path!"),
            14: ("act3_shrine", "Solve a Logic Shrine with set_lever()!"),
            18: ("act3_compound", "Use and/or/not in an if statement!"),
            22: ("act3_battle", "Win the Arena battle with attack()!"),
        }
        guard_id = obj["ID"]
        if guard_id in guard_quests:
            quest_id, hint = guard_quests[guard_id]
            checker = {
                "act3_weather": self._check_act3_weather,
                "act3_look": self._check_act3_look,
                "act3_shrine": self._check_act3_shrine,
                "act3_compound": self._check_act3_compound,
                "act3_battle": self._check_act3_battle,
            }
            check_fn = checker.get(quest_id)
            if quest_id in self.completed_quests or (check_fn and check_fn()):
                self._complete_quest(quest_id)
                return True, ""
            return False, hint
        return True, ""

    def _build_act_sidebar_scroll(self) -> list:
        act_quests = {
            "act2": (
                "ACT II: THE HERO'S JOURNAL",
                [
                    ("comments", "1. Comments", "Silence curses with #"),
                    ("output", "2. Output", "Use say('For Erathia!')"),
                    ("variables", "3. Variables", "Store scout() results"),
                    ("data_types", "4. Data Types", f"Sphinx ({self.sphinx_answers_correct}/3)"),
                    ("constants", "5. Constants", "Define UPPERCASE = 60"),
                    ("operators", "6. Operators", "Use // and % math"),
                    ("type_cast", "7. Type Casting", "Convert text with int()"),
                    ("strings", "8. Strings", "open_gate('DRAGON')"),
                ],
                "Defeat the Tax Collector at (-1, -5)!"
            ),
            "act3": (
                f"ACT III: SHIFTING SANDS ({self._get_today().upper()})",
                [
                    ("act3_weather", "1. If/Else", "Handle daily weather"),
                    ("act3_look", "2. Scout", "Check tiles with look()"),
                    ("act3_shrine", "3. Boolean", "Solve logic shrines"),
                    ("act3_compound", "4. Compound", "Use and/or/not in if"),
                    ("act3_battle", "5. Battle", "Win the Arena fight"),
                ],
                "Slay the Sand Wyrm at (15, -3)!"
            ),
            "act4": (
                "ACT IV: RAISING AN ARMY",
                [
                    ("act4_lists", "1. Lists", "set_formation(['Archer','Pikeman'])"),
                    ("act4_grid", "2. 2D Lists", "Scan map with get_map()"),
                    ("act4_for", "3. For-Loops", "Loop over waypoint tuples"),
                    ("act4_while", "4. While-Loops", "while not dig(): pass"),
                    ("act4_battle", "5. Multi-Battle", "Win at General Morgan (12,6)"),
                ],
                "Defeat the Troglodyte King at (14, 1)!"
            ),
            "act5": (
                "ACT V: THE SPELLBOOK",
                [
                    ("act5_def", "1. Functions", "Define def bridge(x):"),
                    ("act5_return", "2. Return", "return + test_spell(fn)"),
                    ("act5_scope", "3. Scope/Mem", "Save memory['code'] = 42"),
                ],
                "Defeat the Necromancer Lord at (13, 1)!"
            ),
            "act6": (
                f"ACT VI: THE UNDERGROUND (Rings C:{len(self.hanoi_pegs.get('C',[]))}/3)",
                [
                    ("act6_torches", "1. Torches", f"light_torch(x,y) ({len(self.lit_torches)}/3)"),
                    ("act6_hanoi", "2. Hanoi", "Move 3 rings A->C (move_ring)"),
                    ("act6_hydra", "3. Hydra Math", "answer_hydra(15) for size-3"),
                ],
                "Defeat the Dungeon Overlord at (2, 1)!"
            ),
            "act7": (
                f"ACT VII: THE GRAIL (Bits: {self.obelisk_bits})",
                [
                    ("act7_binary", "1. Binary", "set_obelisks & open_vault(173)"),
                    ("act7_hex", "2. Hex Dye", "dye_banner('#FF8800')"),
                    ("act7_bitwise", "3. Bitwise", "Use & | ^ << in code"),
                ],
                "Conquer the Titan of the Grail at (13, 1)!"
            ),
        }
        title, quests, boss_msg = act_quests[self.current_act]
        done_cnt = sum(1 for q, _, _ in quests if q in self.completed_quests)
        stars_earned = self.act_stars.get(self.current_act, 0)
        star_str = "★" * stars_earned + "☆" * (3 - stars_earned)
        scroll: list[tuple[str, tuple[int, int, int]]] = [
            (f"{title}  [{star_str}]", (255, 220, 85)),
            (f"Quests: {done_cnt}/{len(quests)}  |  Click [? Archmage Hint] if stuck!", (180, 200, 220)),
            ("", (0, 0, 0)),
        ]
        for quest_id, name, desc in quests:
            done = quest_id in self.completed_quests
            marker = "✓" if done else "○"
            col = (110, 235, 130) if done else (200, 200, 215)
            scroll.append((f"  {marker} {name}: {desc}", col))

        scroll.append(("", (0, 0, 0)))
        for quest_id, name, desc in quests:
            if quest_id not in self.completed_quests:
                tiers = PROGRESSIVE_HINTS.get(quest_id)
                scroll.append(("NEXT MICRO-LESSON:", (135, 220, 255)))
                scroll.append((f"  {desc}", (255, 230, 95)))
                if tiers:
                    scroll.append((f"  Try typing: {tiers[2]}", (165, 250, 175)))
                vinfo = QUEST_VIDEOS.get(quest_id)
                if vinfo:
                    scroll.append((f"  ▶ [Click to Watch: {vinfo[0]}]", (135, 220, 255)))
                break
        else:
            scroll.append(("ALL QUESTS DONE!", (255, 215, 0)))
            scroll.append((f"  {boss_msg}", (255, 230, 95)))
        return scroll

    def _load_map(self, filename):
        grid = []
        with open(filename, "r", encoding="utf-8") as f:
            for row in csv.reader(f):
                if row:
                    grid.append([c.strip().upper() for c in row])
        return grid

    def _load_objects(self, filename):
        objs = []
        with open(filename, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                math_x = int(row["X"])
                math_y = int(row["Y"])
                col, row_idx = self.math_to_grid(math_x, math_y)
                objs.append({
                    "ID": int(row["ID"]),
                    "Type": row["Type"].strip(),
                    "Name": row["Name"].strip(),
                    "X": math_x,
                    "Y": math_y,
                    "col": col,
                    "row": row_idx,
                    "Value": int(row.get("Value", 0)),
                    "Guard_Power": int(row.get("Guard_Power", 0)),
                    "Description": row.get("Description", "").strip(),
                    "Collected": False if row["Type"].strip() == "Sign" else bool(int(row.get("Collected", 0))),
                    "Read": False
                })
        return objs

    def get_object_at(self, col: int, row: int):
        for obj in self.objects:
            if obj.get("col") == col and obj.get("row") == row and (not obj["Collected"] or obj["Type"] == "Sign"):
                return obj
        return None

    def _interact_object(self, obj, sim, x, y, mp, cost=0.0):
        if obj["ID"] in sim["picked_ids"]:
            return True
        if obj["Type"] == "Gold":
            sim["expected_gold"] += obj["Value"]
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Mine":
            sim["expected_wood"] += obj["Value"]
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Guard":
            if obj["Value"] == 0 and self.current_act != "act1":
                guard_dispatch = {
                    "act2": self._check_act2_guard,
                    "act3": self._check_act3_guard,
                    "act4": self._check_act4_guard,
                    "act5": self._check_act5_guard,
                    "act6": self._check_act6_guard,
                    "act7": self._check_act7_guard,
                }
                check_fn = guard_dispatch.get(self.current_act, self._check_act2_guard)
                passed, hint = check_fn(obj, sim)
                if not passed:
                    sim["valid"] = False
                    sim["error"] = f"✖ {obj['Name']}: {hint}"
                    sim["path"].append((self.math_to_grid(x, y)[0], self.math_to_grid(x, y)[1], mp + cost, False))
                    return False
                sim["picked_ids"].append(obj["ID"])
            elif sim["expected_gold"] < obj["Value"]:
                sim["valid"] = False
                sim["error"] = f"Guard at ({x},{y}) demands {obj['Value']} Gold! (You have {sim['expected_gold']})"
                sim["path"].append((self.math_to_grid(x, y)[0], self.math_to_grid(x, y)[1], mp + cost, False))
                return False
            else:
                sim["expected_gold"] -= obj["Value"]
                sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Mage":
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Dwelling":
            sim["expected_dragons"] += obj["Value"]
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Monster":
            if sim["expected_dragons"] < 1:
                sim["valid"] = False
                sim["error"] = f"{obj['Name']} at ({x},{y})! Need at least 1 Dragon to fight!"
                sim["path"].append((self.math_to_grid(x, y)[0], self.math_to_grid(x, y)[1], mp + cost, False))
                return False
            else:
                sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Boss":
            if self.current_act == "act1":
                needed = obj["Value"]
                if sim["expected_dragons"] < needed:
                    sim["valid"] = False
                    sim["error"] = f"The {obj['Name']} is too powerful! Need {needed} Dragons! (You have {sim['expected_dragons']})"
                    sim["path"].append((self.math_to_grid(x, y)[0], self.math_to_grid(x, y)[1], mp + cost, False))
                    return False
                sim["picked_ids"].append(obj["ID"])
            else:
                req_map = {"act2": 7, "act3": 5, "act4": 4, "act5": 3, "act6": 3, "act7": 3}
                req = req_map.get(self.current_act, 3)
                done = len(self.completed_quests)
                if done < req:
                    sim["valid"] = False
                    sim["error"] = f"The {obj['Name']} laughs! Complete at least {req} quests first! ({done}/{req})"
                    sim["path"].append((self.math_to_grid(x, y)[0], self.math_to_grid(x, y)[1], mp + cost, False))
                    return False
                sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] in ("Sign", "Sphinx", "Shrine", "Marketplace"):
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "NPC":
            sim["expected_gold"] += obj["Value"]
            sim["picked_ids"].append(obj["ID"])
        return True

    def _build_console_namespace(self):
        self._populate_scout_and_sign_data()
        self._populate_act3_data()
        ns: dict[str, Any] = {
            "move_right": hero_api.move_right,
            "move_left": hero_api.move_left,
            "move_down": hero_api.move_down,
            "move_up": hero_api.move_up,
            "move_by": hero_api.move_by,
            "move_to": hero_api.move_to,
            "terraform": hero_api.terraform,
            "say": hero_api.say,
            "scout": hero_api.scout,
            "read_sign": self._api_read_sign,
            "answer_sphinx": hero_api.answer_sphinx,
            "recruit": hero_api.recruit,
            "open_gate": hero_api.open_gate,
            "today": hero_api.today,
            "look": hero_api.look,
            "has_key": hero_api.has_key,
            "set_lever": hero_api.set_lever,
            "get_map": hero_api.get_map,
            "dig": hero_api.dig,
            "set_formation": hero_api.set_formation,
            "memory": hero_api.memory,
            "test_spell": hero_api.test_spell,
            "is_open": hero_api.is_open,
            "light_torch": hero_api.light_torch,
            "is_lit": hero_api.is_lit,
            "move_ring": hero_api.move_ring,
            "answer_hydra": hero_api.answer_hydra,
            "obelisk_pattern": hero_api.obelisk_pattern,
            "set_obelisks": hero_api.set_obelisks,
            "open_vault": hero_api.open_vault,
            "dye_banner": hero_api.dye_banner,
            "AIR": hero_api.AIR,
            "EARTH": hero_api.EARTH,
            "FIRE": hero_api.FIRE,
            "WATER": hero_api.WATER,
            "attack": hero_api.attack,
            "shoot": hero_api.shoot,
            "move_toward": hero_api.move_toward,
            "defend": hero_api.defend,
            "hero": self._build_hero_object(),
            "gold": self.gold,
            "wood": self.wood,
            "dragons": self.dragons,
            "day": self.day,
            "hero_x": self.hero_x,
            "hero_y": self.hero_y,
            "print": self._console_print,
            "range": range,
            "abs": abs,
            "int": int,
            "float": float,
            "str": str,
            "len": len,
            "min": min,
            "max": max,
            "sum": sum,
            "sorted": sorted,
            "enumerate": enumerate,
            "bin": bin,
            "hex": hex,
            "type": type,
            "round": round,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "True": True,
            "False": False,
            "None": None,
        }
        return ns

    def _console_print(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        text = sep.join(str(a) for a in args)
        self.console_add_output(text, (200, 220, 255))

    def console_add_output(self, text: str, color: tuple = (200, 200, 200)):
        self.console_output.append((text, color))
        if len(self.console_output) > 50:
            self.console_output = self.console_output[-50:]

    def _export_console_to_my_hero(self):
        if not self.console_commands:
            self.console_add_output("No queued spells to save!", (255, 180, 100))
            return
        body = "\n".join(f"    {line}" for line in self.console_commands)
        content = (
            "from hero_api import (\n"
            "    move_right, move_left, move_down, move_up,\n"
            "    move_by, move_to, terraform,\n"
            "    say, scout, read_sign, answer_sphinx, recruit, open_gate,\n"
            "    today, look, has_key, set_lever,\n"
            "    get_map, dig, set_formation,\n"
            "    memory, test_spell,\n"
            "    is_open, light_torch, is_lit, move_ring, answer_hydra,\n"
            "    obelisk_pattern, set_obelisks, open_vault, dye_banner,\n"
            "    AIR, EARTH, FIRE, WATER,\n"
            "    attack, shoot, move_toward, defend\n"
            ")\n\n"
            "def plan_turn(gold, wood):\n"
            f"{body}\n"
        )
        with open(os.path.join(PROJECT_DIR, "my_hero.py"), "w", encoding="utf-8") as f:
            f.write(content)
        self.console_add_output("✓ Exported queued spells to my_hero.py!", (110, 255, 130))

    def execute_console_command(self, line: str):
        stripped = line.strip()
        if not stripped:
            return

        if stripped.lower() in ("hint", "?"):
            self.request_archmage_hint()
            return
        if stripped.lower() in ("video", "watch"):
            self.watch_topic_video()
            return
        if stripped.lower().startswith("silence"):
            parts = stripped.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(self.console_commands):
                    ln = self.console_commands[idx]
                    if not ln.lstrip().startswith("#"):
                        self.console_commands[idx] = "# " + ln
                    self.console_add_output(f"♪ Silenced line {idx+1}: {self.console_commands[idx]}", (165, 250, 175))
                    self.run_console_preview()
                    return
            self.console_add_output("Usage: silence 1  (comments out line 1 with #)", (255, 200, 100))
            return
        if stripped.lower().startswith("duel"):
            parts = stripped.lower().split()
            if len(parts) >= 2 and parts[1] in ("squire", "knight", "warlord", "parent"):
                self._run_code_duel(parts[1])
            else:
                self._start_battle(multi_stack=True, duel_mode=True)
                self.console_add_output("★ Tip: Type 'duel squire', 'duel knight', 'duel warlord', or 'duel parent' to test duel_red.py!", (255, 215, 0))
            return

        if getattr(self, "in_battle", False):
            hero_api._reset()
            ns = self._build_console_namespace()
            try:
                self._exec_safe(stripped, {"__builtins__": {}}, ns)
            except Exception as e:
                self.sfx.play("fizzle")
                self.console_add_output(friendly_python_error(e), (255, 120, 80))
            self._run_battle_round()
            self.console_input = ""
            if not self.console_history or self.console_history[-1] != stripped:
                self.console_history.append(stripped)
            self.console_history_idx = len(self.console_history)
            return

        if stripped.lower() in ("clear", "cls"):
            self.console_commands.clear()
            self.console_output.clear()
            self.console_add_output("✦ Spells cleared! Ready for new commands.", (120, 240, 150))
            self.run_console_preview()
            return
        if stripped.lower() == "save":
            self._export_console_to_my_hero()
            return
        if stripped.lower() == "undo":
            self.undo_pending_actions()
            return
        if stripped.lower() == "help":
            for helpline in [
                "╔══ SELF-TEACHING & FUN SHORTCUTS ════════╗",
                "║ hint / ?   = 3-Tier Archmage Hint       ║",
                "║ duel       = Launch Tactical Duel Arena ║",
                "║ save       = Export spells to my_hero.py║",
                "║ Ctrl+1..7  = Jump to Act I through VII  ║",
                "║ Ctrl+M     = Toggle Sound Effects       ║",
                "╚═════════════════════════════════════════╝",
            ]:
                self.console_add_output(helpline, (180, 220, 255))
            return
        if stripped.lower() == "list":
            if not self.console_commands:
                self.console_add_output("(no spells queued yet)", (180, 180, 180))
            else:
                for i, cmd in enumerate(self.console_commands, 1):
                    self.console_add_output(f"  {i}. {cmd}", (165, 250, 175))
            return

        self.console_commands.append(stripped)
        self.console_add_output(f">>> {stripped}", (130, 200, 130))
        self.run_console_preview()

    def run_console_preview(self):
        hero_api._reset()
        sim: dict[str, Any] = {
            "valid": True,
            "path": [(self.hero_col, self.hero_row, 0.0, True)],
            "terraforms": [],
            "expected_gold": self.gold,
            "expected_wood": self.wood,
            "expected_dragons": self.dragons,
            "mp_used": 0.0,
            "error": None,
            "picked_ids": []
        }

        if not self.console_commands:
            self.preview_data = sim
            self.status_msg = "Click a Spell Pill, type a spell, or click [? Archmage Hint]!"
            self.status_color = (120, 240, 150)
            return

        ns = self._build_console_namespace()
        code = "\n".join(self.console_commands)
        try:
            self._exec_safe(code, {"__builtins__": {}}, ns)
        except Exception as e:
            self.sfx.play("fizzle")
            friendly_msg = friendly_python_error(e)
            sim["valid"] = False
            sim["error"] = friendly_msg
            self.preview_data = sim
            self.status_msg = friendly_msg
            self.status_color = (255, 105, 105)
            if self.console_commands:
                bad = self.console_commands.pop()
                self.console_add_output(friendly_msg, (255, 110, 110))
                self.console_add_output(f"   (Removed line: {bad})", (255, 160, 100))
            return

        self._simulate_path(sim)

    def run_preview(self):
        if self.console_commands:
            self.run_console_preview()
            return

        hero_api._reset()
        self._populate_scout_and_sign_data()
        self._populate_act3_data()
        sim: dict[str, Any] = {
            "valid": True,
            "path": [(self.hero_col, self.hero_row, 0.0, True)],
            "terraforms": [],
            "expected_gold": self.gold,
            "expected_wood": self.wood,
            "expected_dragons": self.dragons,
            "mp_used": 0.0,
            "error": None,
            "picked_ids": []
        }

        try:
            if "my_hero" in sys.modules:
                importlib.reload(sys.modules["my_hero"])
            else:
                import my_hero
            sys.modules["my_hero"].plan_turn(self.gold, self.wood)
        except Exception as e:
            friendly_msg = friendly_python_error(e)
            sim["valid"] = False
            sim["error"] = friendly_msg
            self.preview_data = sim
            self.status_msg = friendly_msg
            self.status_color = (255, 105, 105)
            return

        self._simulate_path(sim)

    def _simulate_path(self, sim: dict[str, Any]):
        temp_grid = [r[:] for r in self.grid]
        cur_col, cur_row = self.hero_col, self.hero_row
        mp = 0.0

        step_queue = []
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
                        step_queue.append((cur_col, cur_row))

        cur_col, cur_row = self.hero_col, self.hero_row

        init_obj = self.get_object_at(cur_col, cur_row)
        if init_obj and init_obj["ID"] not in sim["picked_ids"]:
            init_mx, init_my = self.grid_to_math(cur_col, cur_row)
            if not self._interact_object(init_obj, sim, init_mx, init_my, 0.0):
                self.preview_data = sim
                self.status_msg = sim["error"]
                self.status_color = (255, 110, 110)
                return

        for ncol, nrow in step_queue:
            mx, my = self.grid_to_math(ncol, nrow)
            if not (0 <= ncol < MAP_COLS and 0 <= nrow < MAP_ROWS):
                sim["valid"] = False
                sim["error"] = f"Moved off the map edge at ({mx}, {my})!"
                sim["path"].append((ncol, nrow, mp, False))
                break

            tile = temp_grid[nrow][ncol]
            cost = TERRAIN_COSTS.get(tile, None)
            if cost is None:
                sim["valid"] = False
                sim["error"] = f"Blocked by {TERRAIN_NAMES.get(tile, tile)} at ({mx}, {my})!"
                sim["path"].append((ncol, nrow, mp, False))
                break

            if mp + cost > self.max_mp:
                sim["valid"] = False
                sim["error"] = f"Out of Movement Points! ({mp + cost:.1f} / {self.max_mp} MP)"
                sim["path"].append((ncol, nrow, mp + cost, False))
                break

            obj = self.get_object_at(ncol, nrow)
            if obj and obj["ID"] not in sim["picked_ids"]:
                if not self._interact_object(obj, sim, mx, my, mp, cost):
                    break

            mp += cost
            cur_col, cur_row = ncol, nrow
            sim["path"].append((cur_col, cur_row, mp, True))

        sim["mp_used"] = mp

        if sim["valid"]:
            pickup_msgs = []
            for pid in sim["picked_ids"]:
                for obj in self.objects:
                    if obj["ID"] == pid:
                        if obj["Type"] == "Sign":
                            msg = "Re-read Sign" if obj.get("Read", False) else "Read Sign"
                            if msg not in pickup_msgs:
                                pickup_msgs.append(msg)
                        elif not obj["Collected"]:
                            if obj["Type"] == "Gold":
                                pickup_msgs.append(f"+{obj['Value']}g")
                            elif obj["Type"] == "Mine":
                                pickup_msgs.append(f"+{obj['Value']}w")
                            elif obj["Type"] == "Dwelling":
                                if self.current_act == "act1":
                                    pickup_msgs.append(f"+{obj['Value']} Dragons!")
                            elif obj["Type"] == "Monster":
                                pickup_msgs.append(f"Defeat {obj['Name']}!")
                            elif obj["Type"] == "Boss":
                                pickup_msgs.append(f"SLAY {obj['Name']}!!")
            pickups_str = f" Pickups: {', '.join(pickup_msgs)}" if pickup_msgs else ""
            self.status_msg = f"Preview OK! ({mp:.1f}/{self.max_mp} MP){pickups_str} -- Click [COMMIT TURN]!"
            self.status_color = (110, 245, 145)
        else:
            self.status_msg = sim["error"]
            self.status_color = (255, 110, 110)

        self.preview_data = sim

    def undo_pending_actions(self):
        """Clear ALL pending commands/paths for the current turn as a penalty when a path goes wrong."""
        had_console = bool(self.console_commands)
        self.console_commands.clear()

        my_hero_path = os.path.join(PROJECT_DIR, "my_hero.py")
        cleared_file = False
        if not had_console and os.path.exists(my_hero_path):
            try:
                tmpl = ACT_TEMPLATES.get(self.current_act, ACT_TEMPLATES["act1"])
                with open(my_hero_path, "w", encoding="utf-8") as f:
                    f.write(tmpl.lstrip("\n"))
                self.last_mtime = os.path.getmtime(my_hero_path)
                cleared_file = True
            except Exception:
                pass

        hero_api._reset()
        self.sfx.play("fizzle")
        if had_console or cleared_file or (self.preview_data and len(self.preview_data.get("path", [])) > 1):
            self.console_add_output(
                "↩ Undid ALL pending actions for this turn! Plan your path fresh from your Hero's position.",
                (255, 195, 90)
            )
        else:
            self.console_add_output("Nothing pending to undo.", (180, 180, 180))
        self.run_console_preview()
        self.status_msg = "↩ All pending moves cleared! Type your spells fresh for this turn."
        self.status_color = (255, 205, 95)

    def commit_turn(self):
        self.run_preview()
        if not self.preview_data or not self.preview_data["valid"]:
            self.sfx.play("fizzle")
            return

        code_now = self._get_active_code()
        if "for " in code_now or "while " in code_now or "def " in code_now:
            self.used_loop_in_act = True

        if self.current_act != "act1":
            self._handle_say_actions()
            self._handle_sphinx_answers()
            self._handle_recruit_and_constants()
            self._handle_open_gate()
            self._handle_advanced_act_actions()
        if self.current_act == "act3":
            self._handle_set_lever()

        for sx, sy in getattr(hero_api, "_read_signs", set()):
            for obj in self.objects:
                if obj["X"] == sx and obj["Y"] == sy and obj["Type"] == "Sign":
                    obj["Read"] = True

        if self.preview_data["terraforms"]:
            self.sfx.play("magic")
        elif len(self.preview_data["path"]) > 1:
            self.sfx.play("step")

        for tx, ty, ttype in self.preview_data["terraforms"]:
            self.grid[ty][tx] = ttype

        if self.preview_data["path"]:
            fx, fy, _, _ = self.preview_data["path"][-1]
            self.hero_col, self.hero_row = fx, fy

        boss_slain = False
        for oid in self.preview_data["picked_ids"]:
            for obj in self.objects:
                if obj["ID"] == oid:
                    px, py = obj.get("col", obj["X"]) * TILE_SIZE + 8, obj.get("row", obj["Y"]) * TILE_SIZE
                    if obj["Type"] == "Sign":
                        already_read = obj.get("Read", False)
                        obj["Read"] = True
                        obj["Collected"] = False
                        self.console_add_output(f"§ Sign ({obj['X']}, {obj['Y']}): {obj['Description']}", (255, 225, 95))
                        msg = "§ Read Again" if already_read else "§ Read Sign!"
                        self.floating_texts.append([msg, px, py, 60, (255, 240, 140)])
                    elif not obj["Collected"]:
                        if obj["Type"] not in ("Sphinx", "Dwelling", "Shrine") or self.current_act == "act1":
                            obj["Collected"] = True
                        if obj["Type"] == "Gold":
                            self.sfx.play("coin")
                            self.floating_texts.append([f"+{obj['Value']} Gold!", px, py, 65, (255, 225, 55)])
                            # Award Relic Artifacts on special chests!
                            if self.current_act == "act1" and obj["ID"] == 2 and "Boots of Speed" not in self.artifacts:
                                self.artifacts.append("Boots of Speed")
                                self.max_mp += 4.0
                                self.console_add_output("★ Relic Found: Boots of Speed! (+4.0 Max MP per day!)", (255, 215, 0))
                            elif self.current_act == "act1" and obj["ID"] == 6 and "Tome of Fire" not in self.artifacts:
                                self.artifacts.append("Tome of Fire")
                                self.console_add_output("✦ Relic Found: Tome of Fire! (+3 Attack in Arena Battles!)", (255, 160, 60))
                        elif obj["Type"] == "Mine":
                            self.sfx.play("coin")
                            self.floating_texts.append([f"+{obj['Value']} Wood/day!", px, py, 65, (120, 225, 255)])
                        elif obj["Type"] in ("Guard", "Mage"):
                            self.sfx.play("magic")
                            if self.current_act == "act1":
                                self.floating_texts.append(["Region 2 Unlocked!", px, py, 80, (140, 255, 150)])
                                self.quest_stage = 2
                                self.hint_tier = 0
                            else:
                                self.floating_texts.append(["✦ Gate Opened!", px, py, 60, (140, 255, 150)])
                        elif obj["Type"] == "Dwelling":
                            self.sfx.play("fanfare")
                            if self.current_act == "act1":
                                self.floating_texts.append([f"+{obj['Value']} Green Dragons!", px, py, 80, (85, 255, 130)])
                                if self.quest_stage < 3:
                                    self.quest_stage = 3
                                    self.hint_tier = 0
                            else:
                                self.floating_texts.append(["Barracks Visited!", px, py, 60, (85, 255, 130)])
                        elif obj["Type"] == "Monster":
                            self.sfx.play("sword")
                            self.floating_texts.append([f"{obj['Name']} Defeated!", px, py, 65, (255, 180, 80)])
                        elif obj["Type"] == "Boss":
                            self.sfx.play("fanfare")
                            self.floating_texts.append(["BOSS DEFEATED!!! VICTORY!!!", px, py, 120, (255, 215, 0)])
                            boss_slain = True
                        elif obj["Type"] == "NPC":
                            if "Key Merchant" in obj["Name"]:
                                self.keys_held.add("blue")
                                self.sfx.play("coin")
                                self.console_add_output("♦ Obtained the BLUE KEY from Key Merchant!", (110, 220, 255))
                                self.floating_texts.append(["♦ Got Blue Key!", px, py, 75, (110, 220, 255)])
                            elif "Arena" in obj["Name"] and self.current_act == "act3":
                                obj["Collected"] = False
                                if not getattr(self, "in_battle", False) and not getattr(self, "battle_won", False):
                                    self._start_battle(multi_stack=False)
                            elif "General Morgan" in obj["Name"] and self.current_act == "act4":
                                obj["Collected"] = False
                                if not getattr(self, "in_battle", False) and not getattr(self, "battle_won", False):
                                    self._start_battle(multi_stack=True)
                            elif obj["Value"] > 0:
                                self.sfx.play("coin")
                                self.floating_texts.append([f"+{obj['Value']} Gold from {obj['Name']}!", px, py, 65, (255, 225, 55)])
                        elif obj["Type"] == "Sphinx":
                            self.floating_texts.append(["The Oracle speaks...", px, py, 60, (200, 180, 255)])

        self.gold = self.preview_data["expected_gold"]
        self.wood = self.preview_data["expected_wood"]
        self.dragons = self.preview_data.get("expected_dragons", self.dragons)

        for obj in self.objects:
            if obj["Type"] == "Mine" and obj["Collected"] and obj["ID"] not in self.preview_data["picked_ids"]:
                self.wood += obj["Value"]

        self.day += 1
        self._wander_npcs()
        self._apply_act3_weather_grid()

        if self.current_act == "act2":
            self._trigger_zone_tips()
        elif self.current_act == "act3":
            self._trigger_act3_zone_tips()
            self.console_add_output(f"  Weather today: {self._get_today()}", (255, 200, 100))

        if boss_slain:
            self.victory = True
            # Calculate 1-to-3 Star Rating
            stars = 1
            if self.day <= 6:
                stars += 1
            if self.used_loop_in_act or len(self.completed_quests) >= 3:
                stars += 1
            self.act_stars[self.current_act] = max(stars, self.act_stars.get(self.current_act, 0))
            skill_reward = ACT_SKILL_REWARDS.get(self.current_act)
            if skill_reward and skill_reward not in self.skills_unlocked:
                self.skills_unlocked.append(skill_reward)
                self.console_add_output(f"★ Unlocked Secondary Skill: {skill_reward}!", (255, 215, 0))
            self._award_xp(300 * stars, f"{self.current_act.upper()} Conquered ({'★'*stars})!")
            self.status_msg = f"VICTORY on Day {self.day}! Rating: {'★'*stars}!"
            self.status_color = (255, 215, 0)
        else:
            self.status_msg = f"Day {self.day}! Hero at ({self.hero_x}, {self.hero_y}). Click a Spell Pill or [? Hint]!"
            self.status_color = (125, 215, 255)

        self.console_commands.clear()
        self.console_add_output(f"═══ Day {self.day} ═══ Hero at ({self.hero_x}, {self.hero_y})", (250, 215, 75))
        self.save_game()
        self.run_console_preview()

    def _trigger_zone_tips(self):
        hx, hy = self.hero_x, self.hero_y
        zones = [
            ((-8, -3), (1, 6), "comments"),
            ((-1, 4), (3, 6), "output"),
            ((-1, 7), (1, 4), "variables"),
            ((4, 8), (-1, 2), "data_types"),
            ((4, 8), (-2, 0), "constants"),
            ((-6, -2), (-3, 0), "operators"),
            ((-1, 5), (-4, -2), "type_cast"),
            ((3, 7), (-3, 0), "strings"),
        ]
        for (x0, x1), (y0, y1), tip_id in zones:
            if x0 <= hx <= x1 and y0 <= hy <= y1:
                self.show_tip(tip_id)
                break

    def _trigger_act3_zone_tips(self):
        hx, hy = self.hero_x, self.hero_y
        zones = [
            ((0, 5), (-1, 4), "if_else"),
            ((5, 11), (0, 4), "look_ahead"),
            ((6, 11), (-4, 0), "boolean"),
            ((11, 15), (0, 4), "compound_if"),
            ((13, 16), (-3, 1), "battle_intro"),
        ]
        for (x0, x1), (y0, y1), tip_id in zones:
            if x0 <= hx <= x1 and y0 <= hy <= y1:
                self.show_tip(tip_id)
                break

    def _draw_battle_overlay(self):
        map_w = MAP_COLS * TILE_SIZE
        map_h = MAP_ROWS * TILE_SIZE
        overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        overlay.fill((12, 14, 24, 220))
        self.canvas.blit(overlay, (0, 0))

        p = self.battle_player
        ar = getattr(self, "battle_archer", {"count": 0})
        e = self.battle_enemy
        dist = abs(p["x"] - e["x"]) + abs(p["y"] - e["y"])

        title_s = self._render_fitted(f"⚔ ARENA TACTICAL COMBAT — ROUND {self.battle_round + 1} ⚔", self.font_title, (255, 215, 75), map_w - 40)
        self.canvas.blit(title_s, (map_w // 2 - title_s.get_width() // 2, 28))

        sub_s = self._render_fitted(
            f"Distance: {dist} tile(s)  |  Commands:  shoot()   attack()   move_toward()   defend()",
            self.font_md, (180, 225, 255), map_w - 40
        )
        self.canvas.blit(sub_s, (map_w // 2 - sub_s.get_width() // 2, 72))

        cols, rows = 9, 5
        cell = 110
        gx0 = (map_w - cols * cell) // 2
        gy0 = 130

        for r in range(rows):
            for c in range(cols):
                rx = gx0 + c * cell
                ry = gy0 + r * cell
                bg = (46, 52, 68) if (c + r) % 2 == 0 else (38, 44, 58)
                pygame.draw.rect(self.canvas, bg, (rx, ry, cell - 2, cell - 2), border_radius=8)
                pygame.draw.rect(self.canvas, (75, 88, 115), (rx, ry, cell - 2, cell - 2), 2, border_radius=8)
                coord_lbl = self.font_coord.render(f"{c},{r}", True, (110, 125, 150))
                self.canvas.blit(coord_lbl, (rx + 6, ry + 4))

        px = gx0 + p["x"] * cell
        py = gy0 + p["y"] * cell
        pygame.draw.rect(self.canvas, (35, 120, 215), (px + 8, py + 8, cell - 18, cell - 18), border_radius=12)
        hero_sp = self.art._get_scaled_sprite("guard", (cell - 26, cell - 26))
        if hero_sp:
            self.canvas.blit(hero_sp, (px + 12, py + 10))
        p_badge = self._render_fitted(f"{p['count']}x {p['name']}", self.font_md, (140, 255, 160), cell + 36)
        p_hp = self._render_fitted(f"Top HP: {p['top_hp']}/{p['hp']}", self.font_sm, (255, 255, 255), cell + 36)
        self.canvas.blit(p_badge, (px + (cell - p_badge.get_width()) // 2, py + cell + 4))
        self.canvas.blit(p_hp, (px + (cell - p_hp.get_width()) // 2, py + cell + 28))

        if ar.get("count", 0) > 0:
            ax = gx0 + ar["x"] * cell
            ay = gy0 + ar["y"] * cell
            pygame.draw.rect(self.canvas, (45, 160, 115), (ax + 8, ay + 8, cell - 18, cell - 18), border_radius=12)
            ar_sp = self.art._get_scaled_sprite("hero", (cell - 26, cell - 26))
            if ar_sp:
                self.canvas.blit(ar_sp, (ax + 12, ay + 10))
            ar_badge = self._render_fitted(f"{ar['count']}x Archers", self.font_md, (180, 255, 190), cell + 36)
            self.canvas.blit(ar_badge, (ax + (cell - ar_badge.get_width()) // 2, ay + cell + 4))

        ex = gx0 + e["x"] * cell
        ey = gy0 + e["y"] * cell
        pygame.draw.rect(self.canvas, (195, 50, 50), (ex + 8, ey + 8, cell - 18, cell - 18), border_radius=12)
        mon_sp = self.art._get_scaled_sprite("monster", (cell - 26, cell - 26))
        if mon_sp:
            self.canvas.blit(mon_sp, (ex + 12, ey + 10))
        e_badge = self._render_fitted(f"{e['count']}x {e['name']}", self.font_md, (255, 150, 150), cell + 36)
        e_hp = self._render_fitted(f"Top HP: {e['top_hp']}/{e['hp']}", self.font_sm, (255, 255, 255), cell + 36)
        self.canvas.blit(e_badge, (ex + (cell - e_badge.get_width()) // 2, ey + cell + 4))
        self.canvas.blit(e_hp, (ex + (cell - e_hp.get_width()) // 2, ey + cell + 28))

    def draw(self):
        self.canvas.fill((22, 24, 32))
        mouse_x, mouse_y = self.window_to_virtual(pygame.mouse.get_pos())
        sx = MAP_COLS * TILE_SIZE
        map_h = MAP_ROWS * TILE_SIZE

        display_grid = self.grid
        if self.preview_data and self.preview_data["terraforms"]:
            display_grid = [row[:] for row in self.grid]
            for tx, ty, ttype in self.preview_data["terraforms"]:
                display_grid[ty][tx] = ttype

        for r in range(MAP_ROWS):
            for c in range(MAP_COLS):
                px, py = c * TILE_SIZE, r * TILE_SIZE
                self.canvas.blit(self.art.get_tile(display_grid, c, r, self.base_grid), (px, py))

                mx, my = self.grid_to_math(c, r)
                if (mx, my) in getattr(self, "lit_torches", set()):
                    torch_glow = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    pygame.draw.circle(torch_glow, (255, 200, 60, 95), (TILE_SIZE // 2, TILE_SIZE // 2), 28)
                    pygame.draw.circle(torch_glow, (255, 240, 150, 180), (TILE_SIZE // 2, TILE_SIZE // 2), 10)
                    self.canvas.blit(torch_glow, (px, py))

                if self.show_grid:
                    grid_overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    pygame.draw.rect(grid_overlay, (255, 255, 255, 30), (0, 0, TILE_SIZE, TILE_SIZE), 1)
                    if my == 0:
                        pygame.draw.line(grid_overlay, (255, 220, 90, 140), (0, TILE_SIZE - 2), (TILE_SIZE, TILE_SIZE - 2), 2)
                    if mx == 0:
                        pygame.draw.line(grid_overlay, (255, 220, 90, 140), (1, 0), (1, TILE_SIZE), 2)
                    self.canvas.blit(grid_overlay, (px, py))

                    if (mx, my) == (0, 0):
                        pygame.draw.rect(self.canvas, (255, 215, 0), (px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2), 2, border_radius=4)
                        lbl_shadow = self.font_coord.render("0,0 ★", True, (0, 0, 0))
                        lbl = self.font_coord.render("0,0 ★", True, (255, 235, 110))
                    else:
                        lbl_shadow = self.font_coord.render(f"{mx},{my}", True, (0, 0, 0))
                        lbl = self.font_coord.render(f"{mx},{my}", True, (240, 245, 235))
                    self.canvas.blit(lbl_shadow, (px + 6, py + 4))
                    self.canvas.blit(lbl, (px + 5, py + 3))

        if self.preview_data:
            for tx, ty, ttype in self.preview_data["terraforms"]:
                px, py = tx * TILE_SIZE, ty * TILE_SIZE
                self.canvas.blit(self.art.tiles.get(ttype, self.art.tiles["B"]), (px, py))
                pygame.draw.rect(self.canvas, (190, 120, 255), (px+3, py+3, TILE_SIZE-6, TILE_SIZE-6), 4, border_radius=8)

        for obj in self.objects:
            if not obj["Collected"]:
                self.art.draw_object(self.canvas, obj, obj.get("col", obj["X"]) * TILE_SIZE, obj.get("row", obj["Y"]) * TILE_SIZE, self.tick)

        if self.preview_data and len(self.preview_data["path"]) > 1:
            pts = self.preview_data["path"]
            for i in range(1, len(pts)):
                x1, y1, _, _ = pts[i-1]
                x2, y2, _, ok = pts[i]
                p1 = (x1 * TILE_SIZE + TILE_SIZE // 2, y1 * TILE_SIZE + TILE_SIZE // 2)
                p2 = (x2 * TILE_SIZE + TILE_SIZE // 2, y2 * TILE_SIZE + TILE_SIZE // 2)
                col = (85, 255, 130) if ok else (255, 80, 80)
                pygame.draw.line(self.canvas, (15, 45, 20), p1, p2, 10)
                pygame.draw.line(self.canvas, col, p1, p2, 6)
                pygame.draw.circle(self.canvas, col, p2, 8)
                pygame.draw.circle(self.canvas, (255, 255, 255), p2, 4)

            fx, fy, _, f_ok = pts[-1]
            dest_px = fx * TILE_SIZE + TILE_SIZE // 2
            dest_py = fy * TILE_SIZE + TILE_SIZE // 2
            dest_col = (85, 255, 130) if f_ok else (255, 80, 80)
            pulse = int(abs(math.sin(self.tick * 0.1)) * 6)
            pygame.draw.circle(self.canvas, dest_col, (dest_px, dest_py), 14 + pulse, 3)
            pygame.draw.circle(self.canvas, (255, 255, 255), (dest_px, dest_py), 5)

        self.art.draw_hero(self.canvas, self.hero_col * TILE_SIZE, self.hero_row * TILE_SIZE, self.tick)

        if 0 <= mouse_x < sx and 0 <= mouse_y < map_h:
            hover_hc = mouse_x // TILE_SIZE
            hover_hr = mouse_y // TILE_SIZE
            if 0 <= hover_hc < MAP_COLS and 0 <= hover_hr < MAP_ROWS:
                hpx, hpy = hover_hc * TILE_SIZE, hover_hr * TILE_SIZE
                hover_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                hover_pulse = int(abs(math.sin(self.tick * 0.12)) * 30)
                pygame.draw.rect(hover_surf, (255, 235, 120, 32 + hover_pulse // 3), (0, 0, TILE_SIZE, TILE_SIZE), border_radius=6)
                pygame.draw.rect(hover_surf, (255, 225 + hover_pulse, 85, 220), (1, 1, TILE_SIZE - 2, TILE_SIZE - 2), 3, border_radius=6)
                self.canvas.blit(hover_surf, (hpx, hpy))

        # Clamp floating texts inside the map viewport so they never bleed off-screen or into the sidebar
        for ft in self.floating_texts[:]:
            surf = self._render_fitted(ft[0], self.font_lg, ft[4], sx - 24)
            fx_clamped = max(8, min(int(ft[1]), sx - surf.get_width() - 8))
            fy_clamped = max(8, min(int(ft[2]), map_h - surf.get_height() - 8))
            self.canvas.blit(surf, (fx_clamped, fy_clamped))
            ft[2] -= 1.0
            ft[3] -= 1
            if ft[3] <= 0:
                self.floating_texts.remove(ft)

        if not getattr(self, "in_battle", False) and not self.victory and not self.active_tip and not getattr(self, "duel_replay", None):
            self._draw_act_puzzle_hud()

        if getattr(self, "in_battle", False):
            self._draw_battle_overlay()
        elif getattr(self, "duel_replay", None):
            self._update_and_draw_duel_replay(mouse_x, mouse_y)

        self.btn_next_act = None
        if self.victory:
            map_w = sx
            overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 145))
            self.canvas.blit(overlay, (0, 0))

            pulse = int(abs(math.sin(self.tick * 0.05)) * 40)
            victory_font = pygame.font.SysFont("dejavusans", 68, bold=True)
            sub_font = pygame.font.SysFont("dejavusans", 34, bold=True)
            btn_font = pygame.font.SysFont("dejavusans", 28, bold=True)
            gold_col = (215 + pulse, 185 + pulse // 2, 0)

            stars = self.act_stars.get(self.current_act, 1)
            star_txt = "★ " * stars + "☆ " * (3 - stars)
            txt1 = self._render_fitted(f"VICTORY!  {star_txt}", victory_font, gold_col, map_w - 60)
            txt2 = self._render_fitted(f"You conquered {self.current_act.upper()} in {self.day} Days!", sub_font, (240, 235, 220), map_w - 60)
            txt3 = self._render_fitted(f"Hero Level {self.hero_level}  |  Total XP: {self.xp}", sub_font, (135, 220, 255), map_w - 60)

            self.canvas.blit(txt1, (map_w // 2 - txt1.get_width() // 2, map_h // 2 - 110))
            self.canvas.blit(txt2, (map_w // 2 - txt2.get_width() // 2, map_h // 2 - 25))
            self.canvas.blit(txt3, (map_w // 2 - txt3.get_width() // 2, map_h // 2 + 25))

            next_act = self.scenario.get("next_scenario") if self.scenario else None
            if next_act:
                self.btn_next_act = pygame.Rect(map_w // 2 - 180, map_h // 2 + 85, 360, 56)
                glow_btn = int(abs(math.sin(self.tick * 0.08)) * 25)
                btn_col = (35 + glow_btn, 140 + glow_btn, 65 + glow_btn)
                pygame.draw.rect(self.canvas, btn_col, self.btn_next_act, border_radius=14)
                pygame.draw.rect(self.canvas, (200, 235, 200), self.btn_next_act, 2, border_radius=14)
                next_label = f"Continue to {next_act.upper()} →"
                self._blit_button_label(self.btn_next_act, next_label, btn_font, (255, 255, 255), pad_x=16)

        if self.active_tip:
            map_w = sx
            overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.canvas.blit(overlay, (0, 0))

            tip_font_title = pygame.font.SysFont("dejavusans", 28, bold=True)
            tip_font_body = pygame.font.SysFont("dejavusansmono", 19, bold=False)
            tip_font_hint = pygame.font.SysFont("dejavusans", 18, bold=True)

            box_w = 760
            inner_max_w = box_w - 52
            wrapped_tip_lines: list[tuple[str, tuple[int, int, int]]] = []
            for i, line in enumerate(self.active_tip.get("lines", [])):
                col = (200, 230, 255) if i % 2 == 0 else (180, 255, 190)
                for wl in self._wrap_text(line, tip_font_body, inner_max_w):
                    wrapped_tip_lines.append((wl, col))

            box_h = max(230, 120 + len(wrapped_tip_lines) * 28)
            box_x = map_w // 2 - box_w // 2
            box_y = map_h // 2 - box_h // 2
            pygame.draw.rect(self.canvas, (28, 25, 40), (box_x, box_y, box_w, box_h), border_radius=16)
            pygame.draw.rect(self.canvas, (210, 175, 65), (box_x, box_y, box_w, box_h), 3, border_radius=16)

            title_surf = self._render_fitted(self.active_tip["title"], tip_font_title, (250, 215, 75), inner_max_w)
            self.canvas.blit(title_surf, (box_x + box_w // 2 - title_surf.get_width() // 2, box_y + 16))
            for idx_l, (wl, col) in enumerate(wrapped_tip_lines):
                self.canvas.blit(tip_font_body.render(wl, True, col), (box_x + 26, box_y + 60 + idx_l * 28))

            self.tip_video_rect = None
            v_info = self.active_tip.get("video")
            if v_info:
                btn_txt = f"▶ Click Here (or Press V): Watch {v_info[0]}"
                vrect = pygame.Rect(box_x + 40, box_y + box_h - 48, box_w - 80, 36)
                is_vhov = vrect.collidepoint((mouse_x, mouse_y))
                pygame.draw.rect(self.canvas, (55, 115, 185) if is_vhov else (35, 75, 130), vrect, border_radius=8)
                pygame.draw.rect(self.canvas, (255, 215, 85), vrect, 2, border_radius=8)
                self._blit_button_label(vrect, btn_txt, tip_font_hint, (255, 245, 150) if is_vhov else (255, 255, 255), pad_x=14)
                self.tip_video_rect = vrect
            else:
                dismiss = self._render_fitted("Press any key or click to continue...", tip_font_hint, (150, 150, 170), inner_max_w)
                self.canvas.blit(dismiss, (box_x + box_w // 2 - dismiss.get_width() // 2, box_y + box_h - 36))

        # --------------------------------------------------------------------
        # SIDEBAR PANEL (Right side: sx to VIRTUAL_W)
        # --------------------------------------------------------------------
        pygame.draw.rect(self.canvas, (30, 34, 46), (sx, 0, SIDEBAR_WIDTH, VIRTUAL_H))
        pygame.draw.line(self.canvas, (95, 105, 135), (sx, 0), (sx, VIRTUAL_H), 3)
        sidebar_inner_w = SIDEBAR_WIDTH - 68
        title_s = self._render_fitted("HEROES OF PYTHON", self.font_title, (250, 215, 75), SIDEBAR_WIDTH - 48)
        self.canvas.blit(title_s, (sx + 24, 12))

        # Clickable Act Switcher Bar (Acts I - VII with star ratings)
        self.act_tab_rects = []
        romans = ["I", "II", "III", "IV", "V", "VI", "VII"]
        tab_w = (SIDEBAR_WIDTH - 40 - 6 * 6) // 7
        for idx_t, r_num in enumerate(romans):
            aid = f"act{idx_t + 1}"
            tx_tab = sx + 20 + idx_t * (tab_w + 6)
            trect = pygame.Rect(tx_tab, 50, tab_w, 32)
            is_cur = (self.current_act == aid)
            is_thov = trect.collidepoint((mouse_x, mouse_y))
            stars_n = self.act_stars.get(aid, 0)
            star_badge = f" ★{stars_n}" if stars_n > 0 else ""
            bg_tab = (75, 130, 205) if is_cur else ((55, 85, 135) if is_thov else (38, 44, 62))
            bdr_tab = (255, 220, 85) if is_cur else ((140, 185, 240) if is_thov else (80, 92, 122))
            pygame.draw.rect(self.canvas, bg_tab, trect, border_radius=7)
            pygame.draw.rect(self.canvas, bdr_tab, trect, 2 if is_cur else 1, border_radius=7)
            lbl_col = (255, 245, 150) if is_cur else ((230, 240, 255) if stars_n == 0 else (140, 245, 165))
            self._blit_button_label(trect, f"{r_num}{star_badge}", self.font_coord, lbl_col, pad_x=3)
            self.act_tab_rects.append((trect, aid))

        # 1. Stats Box (auto-wrapped & clipped to box)
        stats_rect = pygame.Rect(sx + 20, 90, SIDEBAR_WIDTH - 40, 178)
        pygame.draw.rect(self.canvas, (42, 47, 64), stats_rect, border_radius=12)
        mp_used = self.preview_data["mp_used"] if self.preview_data else 0.0
        preview_gold = self.preview_data.get('expected_gold', self.gold) if self.preview_data else self.gold
        relic_str = ", ".join(self.artifacts) if self.artifacts else "None yet"
        stats = [
            (f"Day {self.day}   Hero: ({self.hero_x}, {self.hero_y})   [{self.current_act.upper()}]", (235, 240, 250)),
            (f"Level {self.hero_level} ({self.xp} XP)   Skills: {len(self.skills_unlocked)}/7", (180, 225, 255)),
            (f"Move Points: {mp_used:.1f} / {self.max_mp:.1f} MP", (120, 245, 155) if mp_used <= self.max_mp else (255, 105, 105)),
            (f"Gold: {self.gold} (After: {preview_gold})   Wood: {self.wood}", (255, 220, 65)),
            (f"Dragons: {self.dragons}  |  Relics: {relic_str}", (85, 255, 130) if self.dragons > 0 else (200, 185, 130)),
        ]
        self.canvas.set_clip(stats_rect.inflate(-12, -10))
        stat_y = stats_rect.y + 10
        for txt, col in stats:
            for wl in self._wrap_text(txt, self.font_md, sidebar_inner_w):
                if stat_y + 24 <= stats_rect.bottom - 6:
                    self.canvas.blit(self.font_md.render(wl, True, col), (sx + 34, stat_y))
                    stat_y += 30
        self.canvas.set_clip(None)

        # 2. Quest Scroll Box (every line word-wrapped & clipped to scroll_rect)
        scroll_y = 280
        scroll_h = 486
        scroll_rect = pygame.Rect(sx + 20, scroll_y, SIDEBAR_WIDTH - 40, scroll_h)
        pygame.draw.rect(self.canvas, (48, 42, 34), scroll_rect, border_radius=12)
        pygame.draw.rect(self.canvas, (205, 170, 90), scroll_rect, 3, border_radius=12)

        if self.current_act in ("act2", "act3", "act4", "act5", "act6", "act7"):
            scroll = self._build_act_sidebar_scroll()
        elif self.victory:
            scroll = [
                ("*** VICTORY! ***", (255, 215, 0)),
                ("", (0,0,0)),
                ("You have defeated the Black Dragon", (240, 235, 220)),
                ("and conquered the Lava Sanctuary!", (240, 235, 220)),
                ("", (0,0,0)),
                ("Click [Continue to ACT2] on the map", (255, 190, 125)),
                ("or press Ctrl+2..7 for Acts II–VII!", (255, 190, 125)),
            ]
        elif self.quest_stage == 1:
            scroll = [
                ("ACT I — QUEST 1: THREE WAYS TO MOVE", (255, 220, 85)),
                ("Goal: Collect 1,500 Gold & bribe the Border Guard at coordinate (7, 7)!", (240, 235, 220)),
                ("", (0,0,0)),
                ("STEP 1 (Copy): Type move_to(4, 9)", (165, 250, 175)),
                ("STEP 2 (Tweak): Then move_to(2, 5)", (135, 220, 255)),
                ("STEP 3 (Master): Then move_to(7, 7)", (255, 225, 110)),
                ("", (0,0,0)),
                ("Stuck? Click [? Archmage Hint] below and type the spells yourself!", (255, 190, 125)),
            ]
        elif self.quest_stage == 2:
            scroll = [
                ("ACT I — QUEST 2: LOOP BRIDGE SPELL", (255, 220, 85)),
                ("Goal: Bridge the River (X=10) & reach the Green Dragon Cliff at (14, 9)!", (240, 235, 220)),
                ("", (0,0,0)),
                ("STEP 1: terraform(10, 7, 'B')", (165, 250, 175)),
                ("STEP 2: terraform(14, 9, 'G')", (135, 220, 255)),
                ("STEP 3: move_to(14, 9)", (255, 225, 110)),
                ("", (0,0,0)),
                ("Click [? Archmage Hint] if stuck!", (255, 190, 125)),
            ]
        else:
            scroll = [
                ("ACT I — QUEST 3: SLAY THE DRAGON", (255, 220, 85)),
                ("Goal: March south to (14, 1) and defeat the Boss with your dragons!", (240, 235, 220)),
                ("", (0,0,0)),
                (f"  Dragons in Army: {self.dragons} / 5", (85, 255, 130) if self.dragons >= 5 else (255, 160, 80)),
                ("1. Bridge Lava row Y=4:", (215, 215, 215)),
                ("   for x in range(12, 16):", (165, 250, 175)),
                ("       terraform(x, 4, 'B')", (165, 250, 175)),
                ("2. move_to(14, 1)", (165, 250, 175)),
            ]

        if self.current_act == "act1" and not self.victory:
            qkey = self._current_quest_key()
            vinfo = QUEST_VIDEOS.get(qkey)
            if vinfo:
                scroll.append(("", (0, 0, 0)))
                scroll.append((f"  ▶ [Click to Watch: {vinfo[0]}]", (135, 220, 255)))

        self.clickable_links = []
        self.canvas.set_clip(scroll_rect.inflate(-12, -12))
        ry = scroll_y + 14
        scroll_line_h = 23
        for txt, col in scroll:
            if ry + scroll_line_h > scroll_rect.bottom - 8:
                break
            if not txt:
                ry += 10
                continue
            if "▶" in txt:
                qkey = self._current_quest_key()
                vinfo = QUEST_VIDEOS.get(qkey)
                url = vinfo[1] if vinfo else "http://www.youtube.com/watch?v=KWgYha0clzw"
                title = vinfo[0] if vinfo else "Video Tutorial"
                btn_lines = self._wrap_text(txt.strip(), self.font_sm, sidebar_inner_w - 16)
                btn_h_vid = 10 + len(btn_lines) * 21
                if ry + btn_h_vid > scroll_rect.bottom - 6:
                    break
                lrect = pygame.Rect(sx + 32, ry, sidebar_inner_w + 4, btn_h_vid)
                is_hov = lrect.collidepoint((mouse_x, mouse_y))
                bg_c = (55, 95, 155) if is_hov else (32, 48, 78)
                pygame.draw.rect(self.canvas, bg_c, lrect, border_radius=6)
                pygame.draw.rect(self.canvas, (135, 220, 255), lrect, 1, border_radius=6)
                txt_c = (255, 240, 130) if is_hov else col
                for bi, bline in enumerate(btn_lines):
                    bsurf = self.font_sm.render(bline, True, txt_c)
                    bx = lrect.x + (lrect.w - bsurf.get_width()) // 2
                    self.canvas.blit(bsurf, (bx, lrect.y + 5 + bi * 21))
                self.clickable_links.append((lrect, url, title))
                ry += btn_h_vid + 6
            else:
                for wl in self._wrap_text(txt, self.font_sm, sidebar_inner_w):
                    if ry + scroll_line_h > scroll_rect.bottom - 8:
                        break
                    self.canvas.blit(self.font_sm.render(wl, True, col), (sx + 34, ry))
                    ry += scroll_line_h
        self.canvas.set_clip(None)

        # 3. Tile Inspector Box (all lines word-wrapped & clipped to inspector_rect)
        inspector_y = 776
        inspector_h = 280
        inspector_rect = pygame.Rect(sx + 20, inspector_y, SIDEBAR_WIDTH - 40, inspector_h)
        pygame.draw.rect(self.canvas, (42, 47, 64), inspector_rect, border_radius=12)
        pygame.draw.rect(self.canvas, (75, 88, 120), inspector_rect, 2, border_radius=12)
        inspector_max_w = SIDEBAR_WIDTH - 68
        self.canvas.set_clip(inspector_rect.inflate(-12, -12))
        if 0 <= mouse_x < sx and 0 <= mouse_y < map_h:
            hc, hr = mouse_x // TILE_SIZE, mouse_y // TILE_SIZE
            if 0 <= hc < MAP_COLS and 0 <= hr < MAP_ROWS:
                tx, ty = self.grid_to_math(hc, hr)
                dx, dy = tx - self.hero_x, ty - self.hero_y
                tcode = self.grid[hr][hc]
                obj = self.get_object_at(hc, hr)
                origin_suffix = " ★ [ORIGIN]" if (tx, ty) == (0, 0) else ""
                hero_suffix = " ⚔ [HERO]" if (hc, hr) == (self.hero_col, self.hero_row) else ""
                tile_text = f"Tile ({tx}, {ty}){origin_suffix}{hero_suffix} -- {TERRAIN_NAMES.get(tcode, tcode)}"
                cur_y = inspector_y + 12
                for tl in self._wrap_text(tile_text, self.font_md, inspector_max_w):
                    self.canvas.blit(self.font_md.render(tl, True, (225, 240, 255)), (sx + 32, cur_y))
                    cur_y += 26
                for coord_line in (f"Absolute: move_to({tx}, {ty})", f"Relative: move_by({dx}, {dy})"):
                    for cl in self._wrap_text(coord_line, self.font_sm, inspector_max_w):
                        self.canvas.blit(self.font_sm.render(cl, True, (150, 250, 175)), (sx + 32, cur_y))
                        cur_y += 24
                cur_y += 2
                if obj:
                    is_read = obj["Type"] == "Sign" and obj.get("Read", False)
                    prefix = "✓ [READ] " if is_read else "* "
                    color = (130, 245, 150) if is_read else (255, 225, 95)
                    obj_text = f"{prefix}{obj['Name']}: {obj['Description']}"
                    for ol in self._wrap_text(obj_text, self.font_sm, inspector_max_w):
                        if cur_y + 20 <= inspector_rect.bottom - 8:
                            self.canvas.blit(self.font_sm.render(ol, True, color), (sx + 32, cur_y))
                            cur_y += 22
        else:
            cur_y = inspector_y + 40
            for hl in self._wrap_text("Hover mouse over any tile on the map!", self.font_md, inspector_max_w):
                self.canvas.blit(self.font_md.render(hl, True, (180, 195, 215)), (sx + 32, cur_y))
                cur_y += 28
        self.canvas.set_clip(None)

        # --------------------------------------------------------------------
        # BOTTOM SPELL CONSOLE BAR + CLICKABLE SPELLBOOK PILLS
        # --------------------------------------------------------------------
        by = map_h
        console_w = sx - 300
        btn_col_x = sx - 280

        pygame.draw.rect(self.canvas, (18, 20, 28), (0, by, sx, BOTTOM_BAR_HEIGHT))
        pygame.draw.line(self.canvas, (70, 85, 120), (0, by), (sx, by), 3)

        # Clickable Spellbook Pill Bar (top strip of bottom bar)
        self.pill_rects = []
        pills = SPELLBOOK_PILLS.get(self.current_act, SPELLBOOK_PILLS["act1"])
        px_cursor = 8
        pill_y = by + 6
        hdr_s = self.font_sm.render("✦ Spellbook:", True, (250, 215, 75))
        self.canvas.blit(hdr_s, (px_cursor, pill_y + 4))
        px_cursor += hdr_s.get_width() + 12
        for label, code_str in pills:
            pw = self.font_sm.size(label)[0] + 18
            if px_cursor + pw <= console_w - 6:
                prect = pygame.Rect(px_cursor, pill_y, pw, 28)
                is_hover = prect.collidepoint((mouse_x, mouse_y))
                pcol = (65, 110, 175) if is_hover else (38, 52, 82)
                pygame.draw.rect(self.canvas, pcol, prect, border_radius=6)
                pygame.draw.rect(self.canvas, (110, 160, 230), prect, 1, border_radius=6)
                self._blit_button_label(prect, label, self.font_sm, (220, 240, 255), pad_x=6)
                self.pill_rects.append((prect, code_str))
                px_cursor += pw + 6

        log_y = by + 38
        log_h = 154
        log_rect = pygame.Rect(4, log_y, console_w - 8, log_h)
        pygame.draw.rect(self.canvas, (12, 14, 22), log_rect, border_radius=6)

        line_h = 22
        max_visible = log_h // line_h
        url_re = re.compile(r"(https?://\S+)")

        # Wrap all recent console entries first, then slice the last `max_visible` wrapped lines
        # so multi-line wrapped messages never push newer lines off the bottom of the log!
        wrapped_console_rows: list[tuple[str, tuple[int, int, int], str | None]] = []
        for text, color in self.console_output[-25:]:
            url_match = url_re.search(text)
            extracted_url = url_match.group(1).rstrip(").,") if url_match else None
            for wl in self._wrap_text(text, self.font_console, console_w - 28):
                m_line = url_re.search(wl)
                row_url = m_line.group(1).rstrip(").,") if m_line else (extracted_url if "▶" in text or "URL:" in text else None)
                wrapped_console_rows.append((wl, color, row_url))

        visible_rows = wrapped_console_rows[-max_visible:]
        self.canvas.set_clip(log_rect.inflate(-4, -4))
        for line_idx, (wl, color, row_url) in enumerate(visible_rows):
            ly = log_y + 4 + line_idx * line_h
            if row_url:
                tw, th = self.font_console.size(wl)
                crect = pygame.Rect(12, ly, min(tw + 6, console_w - 24), th)
                is_chov = crect.collidepoint((mouse_x, mouse_y))
                draw_col = (255, 235, 110) if is_chov else (115, 215, 255)
                self.canvas.blit(self.font_console.render(wl, True, draw_col), (14, ly))
                pygame.draw.line(self.canvas, draw_col, (14, ly + th - 2), (14 + min(tw, console_w - 28), ly + th - 2), 2 if is_chov else 1)
                self.clickable_links.append((crect, row_url, "Video Tutorial"))
            else:
                self.canvas.blit(self.font_console.render(wl, True, color), (14, ly))
        self.canvas.set_clip(None)

        input_y = log_y + log_h + 6
        input_h = 32
        input_rect = pygame.Rect(4, input_y, console_w - 8, input_h)
        self.console_cursor_blink += 1
        glow = int(abs(math.sin(self.console_cursor_blink * 0.06)) * 30)
        border_col = (55 + glow, 100 + glow, 180 + min(glow, 40))
        pygame.draw.rect(self.canvas, (22, 26, 36), input_rect, border_radius=6)
        pygame.draw.rect(self.canvas, border_col, input_rect, 2, border_radius=6)

        prompt = "... " if self.console_in_block else ">>> "
        prompt_color = (100, 180, 255) if not self.console_in_block else (180, 140, 255)
        self.canvas.blit(self.font_console_bold.render(prompt, True, prompt_color), (12, input_y + 5))
        prompt_w = self.font_console_bold.size(prompt)[0]

        display_input = self.console_input
        cpos = min(len(display_input), getattr(self, "console_cursor_pos", len(display_input)))
        max_input_w = console_w - 36 - prompt_w
        # Scroll input horizontally around the cursor if the typed line is wider than the input box
        left_trim = 0
        while self.font_console.size(display_input[left_trim:cpos])[0] > max_input_w and left_trim < cpos:
            left_trim += 1
        visible_input = display_input[left_trim:]
        while self.font_console.size(visible_input)[0] > max_input_w and len(visible_input) > 1:
            visible_input = visible_input[:-1]

        self.canvas.blit(self.font_console.render(visible_input, True, (230, 240, 255)), (12 + prompt_w, input_y + 5))

        if (self.console_cursor_blink // 20) % 2 == 0:
            vis_cpos = max(0, min(len(visible_input), cpos - left_trim))
            cursor_x = 12 + prompt_w + self.font_console.size(visible_input[:vis_cpos])[0] + 1
            pygame.draw.rect(self.canvas, (120, 200, 255), (cursor_x, input_y + 5, 2, 20))

        # Status message under input box (wraps up to 2 lines so long errors never get cut off)
        status_lines = self._wrap_text(self.status_msg, self.font_sm, console_w - 20)
        for s_idx, s_line in enumerate(status_lines[:2]):
            self.canvas.blit(self.font_sm.render(s_line, True, self.status_color), (12, input_y + 35 + s_idx * 20))

        # 5 Action Buttons (all labels auto-fitted & centered inside their button rect)
        btn_w = 260
        btn_h = 44
        can_commit = bool(self.preview_data and self.preview_data["valid"] and (
            len(self.preview_data.get("path", [])) > 1
            or self.preview_data.get("terraforms")
            or self.console_commands
        ))
        has_pending = bool(
            self.console_commands
            or (self.preview_data and (
                len(self.preview_data.get("path", [])) > 1
                or self.preview_data.get("terraforms")
                or not self.preview_data.get("valid", True)
            ))
        )
        path_invalid = bool(self.preview_data and not self.preview_data.get("valid", True) and has_pending)

        self.btn_commit = pygame.Rect(btn_col_x, by + 8, btn_w, btn_h)
        self.btn_undo = pygame.Rect(btn_col_x, by + 60, btn_w, btn_h)
        self.btn_hint = pygame.Rect(btn_col_x, by + 112, btn_w, btn_h)
        self.btn_grid = pygame.Rect(btn_col_x, by + 164, btn_w, btn_h)
        self.btn_reset = pygame.Rect(btn_col_x, by + 216, btn_w, btn_h)

        commit_col = (45, 175, 90) if can_commit else (55, 60, 70)
        pygame.draw.rect(self.canvas, commit_col, self.btn_commit, border_radius=9)
        self._blit_button_label(self.btn_commit, "⚔ COMMIT TURN", self.font_md, (255, 255, 255))

        pulse_u = int(abs(math.sin(self.tick * 0.12)) * 35) if path_invalid else 0
        undo_col = (210 + pulse_u, 75, 45) if path_invalid else ((165, 95, 45) if has_pending else (55, 58, 68))
        pygame.draw.rect(self.canvas, undo_col, self.btn_undo, border_radius=9)
        if path_invalid:
            pygame.draw.rect(self.canvas, (255, 220, 110), self.btn_undo, 2, border_radius=9)
        undo_txt_col = (255, 250, 230) if has_pending else (155, 160, 175)
        self._blit_button_label(self.btn_undo, "↩ Undo Pending Moves", self.font_md, undo_txt_col)

        pygame.draw.rect(self.canvas, (195, 135, 30), self.btn_hint, border_radius=9)
        self._blit_button_label(self.btn_hint, f"? Archmage Hint ({self.hint_tier+1}/3)", self.font_md, (255, 250, 220))

        grid_col = (80, 70, 140) if self.show_grid else (55, 50, 85)
        pygame.draw.rect(self.canvas, grid_col, self.btn_grid, border_radius=9)
        grid_label = "▦ Grid: ON" if self.show_grid else "▦ Grid: OFF"
        self._blit_button_label(self.btn_grid, grid_label, self.font_md, (220, 220, 240))

        pygame.draw.rect(self.canvas, (140, 50, 50), self.btn_reset, border_radius=9)
        self._blit_button_label(self.btn_reset, "↺ Reset Map", self.font_md, (255, 200, 200))

        ww, wh = self.window.get_size()
        scale = min(ww / VIRTUAL_W, wh / VIRTUAL_H)
        scaled_w = int(VIRTUAL_W * scale)
        scaled_h = int(VIRTUAL_H * scale)
        offset_x = (ww - scaled_w) // 2
        offset_y = (wh - scaled_h) // 2

        self.window.fill((0, 0, 0))
        if scaled_w == VIRTUAL_W and scaled_h == VIRTUAL_H:
            self.window.blit(self.canvas, (offset_x, offset_y))
        else:
            scaled = pygame.transform.smoothscale(self.canvas, (scaled_w, scaled_h))
            self.window.blit(scaled, (offset_x, offset_y))

        any_hover = any(r.collidepoint((mouse_x, mouse_y)) for r, _, _ in getattr(self, "clickable_links", []))
        if not any_hover:
            any_hover = any(r.collidepoint((mouse_x, mouse_y)) for r, _ in getattr(self, "pill_rects", []))
        if not any_hover:
            any_hover = any(r.collidepoint((mouse_x, mouse_y)) for r, _ in getattr(self, "act_tab_rects", []))
        if not any_hover and getattr(self, "active_tip", None) and getattr(self, "tip_video_rect", None):
            any_hover = self.tip_video_rect.collidepoint((mouse_x, mouse_y))
        try:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if any_hover else pygame.SYSTEM_CURSOR_ARROW)
        except Exception:
            pass

        pygame.display.flip()

    def run(self):
        running = True
        pygame.key.set_repeat(400, 35)
        while running:
            self.tick += 1
            if not self.console_commands:
                my_hero_file = os.path.join(PROJECT_DIR, "my_hero.py")
                if os.path.exists(my_hero_file):
                    mtime = os.path.getmtime(my_hero_file)
                    if mtime != self.last_mtime:
                        self.last_mtime = mtime
                        self.run_preview()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif getattr(self, "duel_replay", None) and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    rep = self.duel_replay
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.duel_replay = None
                        elif event.key == pygame.K_SPACE:
                            rep["paused"] = not rep.get("paused", False)
                        elif event.key == pygame.K_RIGHT:
                            rep["paused"] = True
                            self._step_duel_replay()
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        vpos = self.window_to_virtual(event.pos)
                        if rep.get("btn_close") and rep["btn_close"].collidepoint(vpos):
                            self.duel_replay = None
                        elif rep.get("btn_pause") and rep["btn_pause"].collidepoint(vpos):
                            rep["paused"] = not rep.get("paused", False)
                        elif rep.get("btn_step") and rep["btn_step"].collidepoint(vpos):
                            rep["paused"] = True
                            self._step_duel_replay()
                    continue

                elif self.active_tip and (event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN):
                    v_info = self.active_tip.get("video")
                    clicked_tip_vid = (
                        event.type == pygame.MOUSEBUTTONDOWN
                        and event.button == 1
                        and getattr(self, "tip_video_rect", None)
                        and self.tip_video_rect.collidepoint(self.window_to_virtual(event.pos))
                    )
                    pressed_v = (event.type == pygame.KEYDOWN and event.key == pygame.K_v)
                    self.active_tip = None
                    self.tip_video_rect = None
                    if v_info and (clicked_tip_vid or pressed_v):
                        self.watch_topic_video(v_info[1], v_info[0])
                    continue

                elif event.type == pygame.KEYDOWN:
                    mods = pygame.key.get_mods()

                    if event.key == pygame.K_F11:
                        self.fullscreen = not self.fullscreen
                        if self.fullscreen:
                            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else:
                            info = pygame.display.Info()
                            self.window = pygame.display.set_mode(
                                (int(info.current_w * 0.85), int(info.current_h * 0.85)),
                                pygame.RESIZABLE
                            )
                    elif event.key == pygame.K_F5:
                        self.console_commands.clear()
                        self.last_mtime = 0
                        self.run_preview()

                    elif mods & pygame.KMOD_CTRL:
                        if event.key == pygame.K_LEFT:
                            self._cheat_step(-1, 0)
                        elif event.key == pygame.K_RIGHT:
                            self._cheat_step(1, 0)
                        elif event.key == pygame.K_UP:
                            self._cheat_step(0, -1)
                        elif event.key == pygame.K_DOWN:
                            self._cheat_step(0, 1)
                        elif event.key == pygame.K_RETURN:
                            self.commit_turn()
                        elif event.key == pygame.K_r:
                            self.reset_game(clear_save=True)
                        elif event.key == pygame.K_g:
                            self.show_grid = not self.show_grid
                        elif event.key == pygame.K_l:
                            self.console_output.clear()
                        elif event.key == pygame.K_z:
                            self.execute_console_command("undo")
                        elif event.key == pygame.K_w:
                            self.watch_topic_video()
                        elif event.key == pygame.K_v:
                            clip = self._get_clipboard_text().replace("\r", "")
                            if clip:
                                first_line = clip.splitlines()[0]
                                pos = getattr(self, "console_cursor_pos", len(self.console_input))
                                self.console_input = self.console_input[:pos] + first_line + self.console_input[pos:]
                                self.console_cursor_pos = pos + len(first_line)
                        elif event.key == pygame.K_h:
                            self.request_archmage_hint()
                        elif event.key == pygame.K_d:
                            self._start_battle(multi_stack=True, duel_mode=True)
                        elif event.key == pygame.K_m:
                            self.sfx.enabled = not self.sfx.enabled
                            state_str = "ON" if self.sfx.enabled else "OFF"
                            self.console_add_output(f"♫ Sound Effects: {state_str}", (180, 220, 255))
                        elif event.key == pygame.K_1:
                            self.start_act("act1")
                        elif event.key == pygame.K_2:
                            self.start_act("act2")
                        elif event.key == pygame.K_3:
                            self.start_act("act3")
                        elif event.key == pygame.K_4:
                            self.start_act("act4")
                        elif event.key == pygame.K_5:
                            self.start_act("act5")
                        elif event.key == pygame.K_6:
                            self.start_act("act6")
                        elif event.key == pygame.K_7:
                            self.start_act("act7")

                    elif event.key == pygame.K_RETURN:
                        line = self.console_input.strip()
                        if self.console_in_block:
                            if line == "":
                                full_block = self.console_multiline
                                self.console_in_block = False
                                self.console_multiline = ""
                                self.console_input = ""
                                self.console_cursor_pos = 0
                                self.execute_console_command(full_block)
                            else:
                                self.console_multiline += "\n" + self.console_input
                                self.console_add_output(f"... {self.console_input}", (150, 140, 200))
                                indent = len(self.console_input) - len(self.console_input.lstrip())
                                self.console_input = " " * max(indent, 4)
                                self.console_cursor_pos = len(self.console_input)
                        else:
                            if line.endswith(":"):
                                self.console_in_block = True
                                self.console_multiline = self.console_input
                                self.console_add_output(f">>> {self.console_input}", (130, 200, 130))
                                self.console_add_output("    (type indented lines, blank Enter to finish)", (120, 120, 160))
                                self.console_input = "    "
                                self.console_cursor_pos = 4
                            else:
                                cmd = self.console_input
                                self.console_input = ""
                                self.console_cursor_pos = 0
                                if cmd.strip():
                                    self.console_history.append(cmd.strip())
                                    self.console_history_idx = -1
                                    self.execute_console_command(cmd)

                    elif event.key == pygame.K_LEFT:
                        self.console_cursor_pos = max(0, getattr(self, "console_cursor_pos", len(self.console_input)) - 1)

                    elif event.key == pygame.K_RIGHT:
                        self.console_cursor_pos = min(len(self.console_input), getattr(self, "console_cursor_pos", len(self.console_input)) + 1)

                    elif event.key == pygame.K_HOME:
                        self.console_cursor_pos = 0

                    elif event.key == pygame.K_END:
                        self.console_cursor_pos = len(self.console_input)

                    elif event.key == pygame.K_BACKSPACE:
                        pos = getattr(self, "console_cursor_pos", len(self.console_input))
                        if pos > 0 and self.console_input:
                            self.console_input = self.console_input[:pos - 1] + self.console_input[pos:]
                            self.console_cursor_pos = pos - 1

                    elif event.key == pygame.K_DELETE:
                        pos = getattr(self, "console_cursor_pos", len(self.console_input))
                        if pos < len(self.console_input):
                            self.console_input = self.console_input[:pos] + self.console_input[pos + 1:]

                    elif event.key == pygame.K_ESCAPE:
                        if self.console_in_block:
                            self.console_in_block = False
                            self.console_multiline = ""
                            self.console_input = ""
                            self.console_cursor_pos = 0
                            self.console_add_output("(block cancelled)", (180, 180, 180))
                        else:
                            self.console_input = ""
                            self.console_cursor_pos = 0

                    elif event.key == pygame.K_UP:
                        if self.console_history:
                            if self.console_history_idx == -1:
                                self.console_history_idx = len(self.console_history) - 1
                            elif self.console_history_idx > 0:
                                self.console_history_idx -= 1
                            self.console_input = self.console_history[self.console_history_idx]
                            self.console_cursor_pos = len(self.console_input)

                    elif event.key == pygame.K_DOWN:
                        if self.console_history_idx >= 0:
                            self.console_history_idx += 1
                            if self.console_history_idx >= len(self.console_history):
                                self.console_history_idx = -1
                                self.console_input = ""
                            else:
                                self.console_input = self.console_history[self.console_history_idx]
                            self.console_cursor_pos = len(self.console_input)

                    elif event.key == pygame.K_TAB:
                        partial = self.console_input.lstrip()
                        completions = [
                            "move_right(", "move_left(", "move_up(", "move_down(",
                            "move_to(", "move_by(", "terraform(",
                            "say(", "scout(", "read_sign(", "answer_sphinx(",
                            "recruit(", "open_gate(", "type(",
                            "today(", "look(", "has_key(", "set_lever(",
                            "get_map()", "dig()", "set_formation(",
                            "memory[", "test_spell(",
                            "light_torch(", "move_ring(", "answer_hydra(",
                            "set_obelisks(", "open_vault(", "dye_banner(",
                            "attack()", "shoot()", "move_toward()", "defend()",
                            "for ", "while ", "def ", "return ", "if ", "elif ", "else:", "range(",
                            "print(", "int(", "float(", "str(", "bin(", "hex(",
                            "True", "False", "and ", "or ", "not ",
                            "clear", "undo", "help", "list", "save", "hint", "duel",
                        ]
                        matches = [c for c in completions if c.startswith(partial)]
                        if len(matches) == 1:
                            leading = len(self.console_input) - len(self.console_input.lstrip())
                            self.console_input = " " * leading + matches[0]
                            self.console_cursor_pos = len(self.console_input)
                        elif len(matches) > 1:
                            self.console_add_output("  ".join(matches), (180, 220, 255))

                    elif event.unicode and event.unicode.isprintable():
                        pos = getattr(self, "console_cursor_pos", len(self.console_input))
                        self.console_input = self.console_input[:pos] + event.unicode + self.console_input[pos:]
                        self.console_cursor_pos = pos + len(event.unicode)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    vpos = self.window_to_virtual(event.pos)
                    # Check clickable Act Switcher tabs at top of Sidebar
                    clicked_act_tab = False
                    for trect, tab_act_id in getattr(self, "act_tab_rects", []):
                        if trect.collidepoint(vpos):
                            self.start_act(tab_act_id)
                            clicked_act_tab = True
                            break
                    if clicked_act_tab:
                        continue
                    # Check clickable video links in Console Log & Sidebar
                    clicked_link = False
                    for lrect, lurl, ltitle in getattr(self, "clickable_links", []):
                        if lrect.collidepoint(vpos):
                            self.watch_topic_video(lurl, ltitle)
                            clicked_link = True
                            break
                    if clicked_link:
                        continue
                    # Check clickable Spellbook pills
                    clicked_pill = False
                    for prect, tip_str in self.pill_rects:
                        if prect.collidepoint(vpos):
                            if tip_str == "__WATCH_VIDEO__":
                                self.watch_topic_video()
                            else:
                                self.console_add_output(f"✦ Spellbook Info: {tip_str} (Type it in the >>> box below!)", (180, 225, 255))
                                self.sfx.play("step")
                            clicked_pill = True
                            break
                    if clicked_pill:
                        continue
                    if self.btn_next_act and self.btn_next_act.collidepoint(vpos):
                        next_act = self.scenario.get("next_scenario") if self.scenario else None
                        if next_act:
                            self.start_act(next_act)
                    elif self.btn_hint.collidepoint(vpos):
                        self.request_archmage_hint()
                    elif self.btn_commit.collidepoint(vpos):
                        self.commit_turn()
                    elif self.btn_undo.collidepoint(vpos):
                        self.undo_pending_actions()
                    elif self.btn_grid.collidepoint(vpos):
                        self.show_grid = not self.show_grid
                    elif self.btn_reset.collidepoint(vpos):
                        self.reset_game(clear_save=True)

            current_size = self.window.get_size()
            if current_size != self.last_window_size and not self.fullscreen:
                self.last_window_size = current_size

            self.draw()
            self.clock.tick(30)

        pygame.quit()


def main():
    HeroesGameEngine().run()

if __name__ == "__main__":
    main()
