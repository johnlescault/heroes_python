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

# ============================================================================
# PATH CONFIGURATION
# The engine lives in game_engine/ but player files live in the parent dir.
# ============================================================================
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(ENGINE_DIR)
ASSETS_DIR = os.path.join(ENGINE_DIR, "assets")

# Ensure the project dir is on sys.path so we can import my_hero / hero_api
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from game_engine.terrain import TerrainRenderer

# Lock Windows High-DPI Awareness so 4K monitors render crisp pixels
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Auto-generate hero_api.py in the PROJECT directory (next to my_hero.py)
HERO_API_CODE = '''# Auto-generated helper module for Heroes of Python
_actions = []
_scout_results = {}   # Filled by engine before exec
_sign_results = {}    # Filled by engine before exec

def _reset():
    _actions.clear()

def move_right(steps=1):
    """Move relative to the right by 'steps' tiles."""
    _actions.append(("rel", int(steps), 0))

def move_left(steps=1):
    """Move relative to the left by 'steps' tiles."""
    _actions.append(("rel", -int(steps), 0))

def move_down(steps=1):
    """Move relative down by 'steps' tiles (negative Y)."""
    _actions.append(("rel", 0, -int(steps)))

def move_up(steps=1):
    """Move relative up by 'steps' tiles (positive Y)."""
    _actions.append(("rel", 0, int(steps)))

def move_by(dx, dy):
    """Move relative to current position by (dx, dy) tiles.
    Positive dx is right, negative dx is left.
    Positive dy is up, negative dy is down."""
    _actions.append(("rel", int(dx), int(dy)))

def move_to(x, y):
    """Move to the exact absolute map coordinate (x, y)."""
    _actions.append(("abs", int(x), int(y)))

def terraform(x, y, tile_type="B"):
    """Alter the map grid at absolute coordinate (x, y)."""
    _actions.append(("terraform", int(x), int(y), str(tile_type).upper()))

def say(text):
    """Shout a message! Shows as a speech bubble over the hero."""
    _actions.append(("say", str(text)))

def scout(name):
    """Find where an NPC is on the map. Returns (x, y) coordinates."""
    key = str(name).lower()
    for k, v in _scout_results.items():
        if key in k.lower():
            return v
    return None

def read_sign(x, y):
    """Read the text on a sign at position (x, y). Returns a string."""
    return _sign_results.get((int(x), int(y)), "")

def answer_sphinx(value):
    """Answer the Sphinx\'s riddle with a value of the correct type."""
    _actions.append(("answer_sphinx", value))

def recruit(unit_name, count):
    """Recruit soldiers from a Barracks or Dwelling."""
    _actions.append(("recruit", str(unit_name), int(count)))

def open_gate(password):
    """Try to open a locked gate with a password."""
    _actions.append(("open_gate", str(password)))

# ── Act III: The Shifting Sands ──
_today_result = "clear"       # Set by engine before exec
_look_results = {}            # Set by engine before exec
_keys_held = set()            # Set by engine before exec

def today():
    """What's the weather today? Returns 'sandstorm', 'clear', or 'oasis'."""
    return _today_result

def look(x, y):
    """Look at a tile. Returns tile type or object type if one is there."""
    return _look_results.get((int(x), int(y)), "?")

def has_key(color):
    """Do you have a key of this color?"""
    return str(color).lower() in _keys_held

def set_lever(name, value):
    """Set a lever to True or False for the Logic Shrine."""
    _actions.append(("set_lever", str(name).lower(), bool(value)))

# Battle tutorial functions (only work during battle)
def attack(target=None):
    """Attack an adjacent enemy."""
    _actions.append(("battle_attack",))

def move_toward(target=None):
    """Move toward the closest enemy."""
    _actions.append(("battle_move_toward",))

def defend():
    """Defend this round (+30%% defense)."""
    _actions.append(("battle_defend",))
'''

hero_api_path = os.path.join(PROJECT_DIR, "hero_api.py")
with open(hero_api_path, "w", encoding="utf-8") as f:
    f.write(HERO_API_CODE)

import hero_api

# ============================================================================
# VIRTUAL CANVAS CONFIGURATION
# The game renders to a fixed-size virtual canvas, then scales to ANY window.
# ============================================================================
TILE_SIZE = 84
MAP_COLS = 16
MAP_ROWS = 11
SIDEBAR_WIDTH = 576
BOTTOM_BAR_HEIGHT = 280

VIRTUAL_W = MAP_COLS * TILE_SIZE + SIDEBAR_WIDTH   # 1920 px
VIRTUAL_H = MAP_ROWS * TILE_SIZE + BOTTOM_BAR_HEIGHT  # 1204 px

TERRAIN_COSTS = {
    "R": 0.5,  # Dirt Road
    "G": 1.0,  # Grass
    "B": 1.0,  # Bridge
    "S": 1.5,  # Sand (slow)
    "M": None, # Mountain (Blocked)
    "W": None, # Water (Blocked)
    "L": None, # Lava (Blocked)
    "F": None, # Dense Forest (Blocked)
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

# ============================================================================
# HIGH-RESOLUTION FANTASY ART & SPRITE ENGINE
# Loads square PNG tiles from game_engine/assets/. Falls back to procedural art.
# ============================================================================
class HDArtRenderer:
    def __init__(self):
        self.tiles = {}
        self.sprites = {}
        self._load_external_sprites()
        self._build_hd_tiles()
        # Context-aware terrain: seamless textures, auto-tiled roads, rotating bridges, shorelines
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
                    key = fname[:-4]  # strip .png
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

        # 1. EMERALD GRASS
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
            for bx, by in [(16, 20), (54, 18), (28, 62), (66, 52), (14, 68), (44, 38)]:
                pygame.draw.line(grass, (85, 175, 65), (bx, by), (bx-4, by-9), 2)
                pygame.draw.line(grass, (95, 190, 75), (bx, by), (bx+3, by-10), 2)
                if (bx + by) % 3 == 0:
                    pygame.draw.circle(grass, (245, 220, 85), (bx+2, by-10), 3)
        self.tiles["G"] = grass

        # 2. COBBLE / DIRT ROAD
        road = grass.copy()
        if "road" in self.sprites:
            road = pygame.Surface((s, s))
            road.blit(self._get_scaled_sprite("road", (s, s)), (0, 0))
        else:
            pygame.draw.rect(road, (125, 92, 58), (6, 6, s-12, s-12), border_radius=16)
            pygame.draw.rect(road, (172, 134, 88), (10, 10, s-20, s-20), border_radius=12)
            stones = [(22, 22, 10), (44, 20, 9), (60, 28, 8), (26, 44, 11), (50, 46, 10), (32, 62, 9), (56, 62, 8)]
            for sx, sy, sr in stones:
                pygame.draw.circle(road, (150, 115, 74), (sx, sy), sr)
                pygame.draw.circle(road, (195, 160, 112), (sx-2, sy-2), sr-3)
        self.tiles["R"] = road

        # 3. JAGGED MOUNTAIN PEAK
        mtn = grass.copy()
        if "mountain" in self.sprites:
            mtn = pygame.Surface((s, s))
            mtn.blit(self._get_scaled_sprite("mountain", (s, s)), (0, 0))
        else:
            pygame.draw.ellipse(mtn, (28, 68, 25), (6, s-24, s-12, 18))
            pygame.draw.polygon(mtn, (82, 86, 98), [(6, s-14), (28, 12), (56, s-14)])
            pygame.draw.polygon(mtn, (62, 65, 76), [(28, 12), (42, s-14), (56, s-14)])
            pygame.draw.polygon(mtn, (112, 116, 130), [(22, s-10), (54, 8), (s-6, s-10)])
            pygame.draw.polygon(mtn, (78, 82, 95), [(54, 8), (66, s-10), (s-6, s-10)])
            pygame.draw.polygon(mtn, (240, 246, 255), [(28, 12), (19, 32), (28, 28), (36, 33)])
            pygame.draw.polygon(mtn, (245, 250, 255), [(54, 8), (42, 34), (54, 28), (65, 36)])
            pygame.draw.polygon(mtn, (195, 210, 235), [(54, 8), (54, 28), (65, 36)])
        self.tiles["M"] = mtn

        # 4. ANCIENT FOREST
        forest = grass.copy()
        if "forest" in self.sprites:
            forest = pygame.Surface((s, s))
            forest.blit(self._get_scaled_sprite("forest", (s, s)), (0, 0))
        else:
            trees = [(26, 28, 20), (58, 32, 22), (40, 52, 24)]
            for tx, ty, tr in trees:
                pygame.draw.ellipse(forest, (25, 62, 22), (tx-14, ty+12, 28, 12))
                pygame.draw.rect(forest, (102, 64, 32), (tx-5, ty+4, 10, 18))
                pygame.draw.circle(forest, (24, 76, 30), (tx, ty), tr)
                pygame.draw.circle(forest, (42, 112, 44), (tx-3, ty-4), tr-4)
                pygame.draw.circle(forest, (72, 152, 62), (tx-6, ty-7), tr-10)
        self.tiles["F"] = forest

        # 5. DEEP RIVER
        water = pygame.Surface((s, s))
        water.fill((24, 82, 162))
        if "water" in self.sprites:
            water.blit(self._get_scaled_sprite("water", (s, s)), (0, 0))
        else:
            for y in range(0, s, 6):
                c = 155 + int(math.sin(y * 0.2) * 20)
                pygame.draw.rect(water, (28, 92, c), (0, y, s, 6))
            for wy in range(14, s-10, 20):
                pygame.draw.arc(water, (115, 185, 245), (10, wy, 28, 12), 0, math.pi, 3)
                pygame.draw.arc(water, (115, 185, 245), (44, wy+6, 28, 12), 0, math.pi, 3)
        self.tiles["W"] = water

        # 6. MOLTEN LAVA
        lava = pygame.Surface((s, s))
        lava.fill((62, 20, 18))
        if "lava" in self.sprites:
            lava.blit(self._get_scaled_sprite("lava", (s, s)), (0, 0))
        else:
            pygame.draw.circle(lava, (185, 42, 18), (s//2, s//2), s//2 - 4)
            pygame.draw.circle(lava, (238, 105, 20), (s//2 - 4, s//2 + 2), s//3)
            pygame.draw.circle(lava, (255, 205, 55), (s//2 - 8, s//2 + 4), s//5)
        self.tiles["L"] = lava

        # 7. ENCHANTED BRIDGE
        bridge = water.copy()
        if "bridge" in self.sprites:
            bridge = pygame.Surface((s, s))
            bridge.blit(self._get_scaled_sprite("bridge", (s, s)), (0, 0))
        else:
            pygame.draw.rect(bridge, (125, 78, 38), (4, 10, s-8, s-20), border_radius=6)
            for x in range(10, s-10, 14):
                pygame.draw.rect(bridge, (158, 104, 54), (x, 12, 10, s-24), border_radius=3)
                pygame.draw.line(bridge, (85, 50, 22), (x, 12), (x, s-12), 2)
            pygame.draw.rect(bridge, (215, 168, 72), (4, 8, s-8, 6), border_radius=3)
            pygame.draw.rect(bridge, (215, 168, 72), (4, s-14, s-8, 6), border_radius=3)
        self.tiles["B"] = bridge

        # 8. DESERT SAND
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
            # Dune ripples
            for wy in range(8, s - 4, 16):
                pygame.draw.arc(sand, (225, 205, 155), (2, wy, s - 4, 10), 0, math.pi, 2)
        self.tiles["S"] = sand

    def draw_object(self, screen, obj, px, py, tick):
        s = TILE_SIZE
        cx, cy = px + s // 2, py + s // 2
        otype = obj["Type"]
        bob = int(math.sin(tick * 0.08) * 4)

        # Ground shadow under every interactive object
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
                    pygame.draw.rect(screen, (175, 102, 42), (px+16, py+24, s-32, 16), border_radius=6)
                    pygame.draw.rect(screen, (245, 200, 50), (px+16, py+24, s-32, s-36), 3, border_radius=6)
                    pygame.draw.rect(screen, (255, 225, 80), (cx-6, cy-2, 12, 14), border_radius=3)
            else:
                sp = self._get_scaled_sprite("gold_pile", (s-12, s-12))
                if sp:
                    screen.blit(sp, (px+6, py+6))
                else:
                    for dx, dy, r in [(-14, 10, 11), (14, 10, 11), (0, 4, 13), (-7, 14, 10), (8, 14, 10)]:
                        pygame.draw.circle(screen, (245, 195, 30), (cx+dx, cy+dy), r)
                        pygame.draw.circle(screen, (255, 235, 110), (cx+dx-3, cy+dy-3), r//2)
                        pygame.draw.circle(screen, (175, 125, 10), (cx+dx, cy+dy), r, 2)

        elif otype == "Mine":
            sp = self._get_scaled_sprite("mine", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4))
            else:
                pygame.draw.rect(screen, (145, 98, 52), (px+16, py+32, s-32, s-42))
                pygame.draw.polygon(screen, (185, 65, 45), [(px+10, py+34), (cx, py+12), (px+s-10, py+34)])
                pygame.draw.rect(screen, (55, 35, 18), (cx-9, cy+6, 18, 22), border_radius=4)

        elif otype == "Guard":
            sp = self._get_scaled_sprite("guard", (s-6, s-6))
            if sp:
                screen.blit(sp, (px+3, py+3))
            else:
                pygame.draw.rect(screen, (130, 138, 150), (px+12, py+14, 16, s-24), border_radius=4)
                pygame.draw.rect(screen, (130, 138, 150), (px+s-28, py+14, 16, s-24), border_radius=4)
                pygame.draw.rect(screen, (200, 45, 45), (px+20, cy-6, s-40, 12))
                pygame.draw.circle(screen, (250, 215, 65), (cx, cy), 9)

        elif otype == "Mage":
            sp = self._get_scaled_sprite("mage", (s-6, s-6))
            if sp:
                screen.blit(sp, (px+3, py+3+bob))
            else:
                pygame.draw.polygon(screen, (105, 52, 175), [(px+18, py+s-14), (cx, py+12+bob), (px+s-18, py+s-14)])
                pygame.draw.circle(screen, (145, 230, 255), (cx, py+16+bob), 9)

        elif otype in ("Dwelling", "Boss"):
            key = "dragon_green" if otype == "Dwelling" else "dragon_black"
            sp = self._get_scaled_sprite(key, (s, s))
            if sp:
                screen.blit(sp, (px, py+bob))
            else:
                body_c = (42, 175, 72) if otype == "Dwelling" else (52, 52, 64)
                wing_c = (95, 225, 115) if otype == "Dwelling" else (210, 45, 45)
                pygame.draw.polygon(screen, wing_c, [(cx, cy+bob), (px+6, py+12+bob), (px+18, cy+12+bob)])
                pygame.draw.polygon(screen, wing_c, [(cx, cy+bob), (px+s-6, py+12+bob), (px+s-18, cy+12+bob)])
                pygame.draw.circle(screen, body_c, (cx, cy+6+bob), 16)
                pygame.draw.circle(screen, body_c, (cx, py+20+bob), 11)
                pygame.draw.circle(screen, (255, 230, 50), (cx-4, py+18+bob), 3)
                pygame.draw.circle(screen, (255, 230, 50), (cx+4, py+18+bob), 3)

        elif otype == "Monster":
            sp = self._get_scaled_sprite("monster", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4+bob))
            else:
                pygame.draw.circle(screen, (195, 58, 58), (cx, cy+bob), 20)
                pygame.draw.circle(screen, (255, 240, 90), (cx-6, cy-4+bob), 4)
                pygame.draw.circle(screen, (255, 240, 90), (cx+6, cy-4+bob), 4)

        elif otype == "Sign":
            is_read = obj.get("Read", False)
            sp = self._get_scaled_sprite("sign", (s-12, s-12))
            if sp:
                screen.blit(sp, (px+6, py+6))
            else:
                # Wooden signpost
                post_c = (105, 68, 32)
                plank_c = (160, 115, 58)
                # Post
                pygame.draw.rect(screen, post_c, (cx-3, cy-4, 6, s//2+4), border_radius=2)
                # Plank
                pygame.draw.rect(screen, plank_c, (px+12, py+12, s-24, 24), border_radius=5)
                pygame.draw.rect(screen, (130, 90, 42), (px+12, py+12, s-24, 24), 2, border_radius=5)
                # Wood grain lines
                pygame.draw.line(screen, (140, 100, 48), (px+16, py+18), (px+s-16, py+18), 1)
                pygame.draw.line(screen, (140, 100, 48), (px+16, py+28), (px+s-16, py+28), 1)
                if not is_read:
                    # "?" text when unread
                    pygame.draw.circle(screen, (245, 225, 95), (cx, py+22), 7)
                    pygame.draw.circle(screen, plank_c, (cx, py+22), 5)
                    pygame.draw.rect(screen, (245, 225, 95), (cx-1, py+19, 3, 6))

            # If the sign has been read, draw a clean checkmark badge in the top-right corner
            if is_read:
                bx, by = px + s - 14, py + 12
                # Outer dark ring
                pygame.draw.circle(screen, (15, 35, 20), (bx, by), 9)
                # Green badge body
                pygame.draw.circle(screen, (45, 195, 85), (bx, by), 7)
                # White checkmark ✓
                pygame.draw.lines(screen, (255, 255, 255), False, [
                    (bx - 4, by), (bx - 1, by + 3), (bx + 4, by - 3)
                ], 2)

        elif otype == "NPC":
            sp = self._get_scaled_sprite("npc", (s-10, s-10))
            if sp:
                screen.blit(sp, (px+5, py+5+bob))
            else:
                # Hooded figure
                robe_c = (65, 85, 145)
                # Body robe
                pygame.draw.polygon(screen, robe_c, [
                    (cx-14, py+s-16), (cx-10, py+22+bob),
                    (cx+10, py+22+bob), (cx+14, py+s-16)
                ])
                # Hood
                pygame.draw.circle(screen, robe_c, (cx, py+20+bob), 13)
                # Face
                pygame.draw.circle(screen, (215, 185, 155), (cx, py+20+bob), 9)
                # Eyes
                pygame.draw.circle(screen, (40, 40, 50), (cx-3, py+19+bob), 2)
                pygame.draw.circle(screen, (40, 40, 50), (cx+3, py+19+bob), 2)
                # Belt
                pygame.draw.rect(screen, (180, 145, 60), (cx-10, py+36+bob, 20, 3), border_radius=1)

        elif otype == "Sphinx":
            sp = self._get_scaled_sprite("sphinx", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4+bob))
            else:
                # Golden sphinx - cat body with human-ish face
                gold = (225, 185, 65)
                dark_gold = (175, 135, 35)
                # Body
                pygame.draw.ellipse(screen, gold, (px+10, cy+2+bob, s-20, 24))
                # Front paws
                pygame.draw.ellipse(screen, dark_gold, (px+14, cy+16+bob, 12, 10))
                pygame.draw.ellipse(screen, dark_gold, (px+s-26, cy+16+bob, 12, 10))
                # Head
                pygame.draw.circle(screen, gold, (cx, py+22+bob), 14)
                # Headdress (Egyptian striped)
                pygame.draw.polygon(screen, (45, 85, 165), [(cx-16, py+20+bob), (cx, py+6+bob), (cx+16, py+20+bob)])
                pygame.draw.line(screen, (225, 195, 75), (cx-10, py+14+bob), (cx+10, py+14+bob), 2)
                pygame.draw.line(screen, (225, 195, 75), (cx-13, py+18+bob), (cx+13, py+18+bob), 2)
                # Eyes
                pygame.draw.circle(screen, (180, 40, 40), (cx-5, py+22+bob), 3)
                pygame.draw.circle(screen, (180, 40, 40), (cx+5, py+22+bob), 3)

        elif otype == "Shrine":
            sp = self._get_scaled_sprite("shrine", (s-8, s-8))
            if sp:
                screen.blit(sp, (px+4, py+4))
            else:
                # Glowing stone pillar with colored orbs (levers)
                pillar_c = (95, 100, 115)
                # Base
                pygame.draw.rect(screen, (75, 78, 88), (px+14, cy+10, s-28, 18), border_radius=4)
                # Pillar
                pygame.draw.rect(screen, pillar_c, (px+18, py+12, s-36, s//2+6), border_radius=6)
                pygame.draw.rect(screen, (120, 125, 140), (px+20, py+14, s-40, s//2+2), border_radius=4)
                # Top stone cap
                pygame.draw.rect(screen, (80, 85, 95), (px+14, py+10, s-28, 8), border_radius=3)
                # Glowing orbs (red, blue, green = lever colors)
                glow = int(math.sin(tick * 0.06) * 30)
                orb_colors = [
                    (min(255, 200 + glow), 60, 60),    # Red
                    (60, 60, min(255, 200 + glow)),     # Blue
                    (60, min(255, 200 + glow), 60),     # Green
                ]
                for i, col in enumerate(orb_colors):
                    orb_x = px + 24 + i * 12
                    orb_y = py + 26
                    pygame.draw.circle(screen, col, (orb_x, orb_y), 5)
                    pygame.draw.circle(screen, (255, 255, 255), (orb_x-1, orb_y-1), 2)

    def draw_hero(self, screen, px, py, tick):
        s = TILE_SIZE
        bob = int(math.sin(tick * 0.12) * 3)
        surf = pygame.Surface((s, s), pygame.SRCALPHA)

        sp = self._get_scaled_sprite("hero", (s, s))
        if sp:
            surf.blit(sp, (0, bob))
        else:
            # High-detail mounted knight fallback
            pygame.draw.ellipse(surf, (0, 0, 0, 90), (14, s-18, s-28, 14))
            pygame.draw.ellipse(surf, (220, 208, 190), (16, 40+bob, 48, 26))
            pygame.draw.polygon(surf, (220, 40, 40), [(32, 26+bob), (12, 54+bob), (38, 50+bob)])
            pygame.draw.circle(surf, (75, 150, 240), (42, 30+bob), 12)
            pygame.draw.circle(surf, (245, 215, 75), (42, 16+bob), 9)
            pygame.draw.polygon(surf, (250, 60, 60), [(42, 7+bob), (28, 2+bob), (36, 14+bob)])
            pygame.draw.line(surf, (240, 248, 255), (50, 34+bob), (70, 10+bob), 5)

        screen.blit(surf, (px, py))

# ============================================================================
# MAIN GAME ENGINE — Fully resizable, maximizable, 4K-ready
# ============================================================================
class HeroesGameEngine:
    @staticmethod
    def _wrap_text(text, font, max_width):
        """Word-wrap text to fit within max_width pixels. Returns list of lines."""
        if not text:
            return [""]
        words = text.split(" ")
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                # If single word is wider than max, force it on its own line
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines if lines else [""]

    def math_to_grid(self, x: int, y: int) -> tuple[int, int]:
        """Convert math coordinates (x, y) to grid coordinates (col, row)."""
        return (int(self.origin_col + x), int(self.origin_row - y))

    def grid_to_math(self, col: int, row: int) -> tuple[int, int]:
        """Convert grid coordinates (col, row) to math coordinates (x, y)."""
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
        pygame.display.set_caption("Heroes of Python -- Adventure Map")

        # Start at 85% of screen, fully resizable & maximizable
        info = pygame.display.Info()
        init_w = min(max(1600, int(info.current_w * 0.85)), info.current_w)
        init_h = min(max(900, int(info.current_h * 0.85)), info.current_h)

        self.window = pygame.display.set_mode((init_w, init_h), pygame.RESIZABLE)
        self.canvas = pygame.Surface((VIRTUAL_W, VIRTUAL_H))
        self.fullscreen = False
        self.last_window_size = (init_w, init_h)

        self.clock = pygame.time.Clock()
        self.art = HDArtRenderer()

        # Fonts — use Linux-available fonts with Windows fallbacks
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
        self.load_scenario("act1")
        self.reset_game()
        # Welcome message for the Spell Console
        self.console_add_output("✦ Welcome to the Spell Console!", (250, 215, 75))
        self.console_add_output("  Type a spell and press Enter:", (180, 200, 220))
        self.console_add_output("  move_right(3)   move_to(4, 9)", (165, 250, 175))
        self.console_add_output("  Type 'help' for all commands", (140, 180, 200))
        self.console_add_output("  Ctrl+Enter = commit your turn", (140, 180, 200))
        # Restore saved game if available
        if self.load_game():
            self.status_msg = f"Game Loaded! Day {self.day}, Hero at ({self.hero_x}, {self.hero_y})."
            self.status_color = (120, 240, 150)
            self.console_add_output(f"═══ Day {self.day} ═══ Hero at ({self.hero_x}, {self.hero_y})", (250, 215, 75))

    def window_to_virtual(self, pos):
        """Convert a window-space mouse position to virtual canvas coordinates."""
        ww, wh = self.window.get_size()
        scale = min(ww / VIRTUAL_W, wh / VIRTUAL_H)
        scaled_w = int(VIRTUAL_W * scale)
        scaled_h = int(VIRTUAL_H * scale)
        offset_x = (ww - scaled_w) // 2
        offset_y = (wh - scaled_h) // 2
        vx = int((pos[0] - offset_x) / scale)
        vy = int((pos[1] - offset_y) / scale)
        return vx, vy

    def save_game(self):
        """Save current progress to savegame.json."""
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
                "grid": self.grid,
                "collected_ids": [obj["ID"] for obj in self.objects if obj["Collected"] and obj["Type"] != "Sign"],
                "read_sign_ids": [obj["ID"] for obj in self.objects if obj.get("Read", False)],
                "shown_tips": list(self.shown_tips),
                "completed_quests": list(self.completed_quests),
                "hero_log": self.hero_log[-20:],
                "battle_won": getattr(self, "battle_won", False),
                "shrine_solved": getattr(self, "shrine_solved", False),
                "keys_held": list(getattr(self, "keys_held", set())),
                "shrine_levers": getattr(self, "shrine_levers", {}),
            }
            with open(os.path.join(PROJECT_DIR, "savegame.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print("Failed to save game:", e)

    def load_game(self):
        """Load progress from savegame.json if it exists."""
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
            if "grid" in data:
                self.grid = data["grid"]
            collected_ids = set(data.get("collected_ids", []))
            read_sign_ids = set(data.get("read_sign_ids", []))
            for obj in self.objects:
                if obj["Type"] == "Sign":
                    if obj["ID"] in read_sign_ids or obj["ID"] in collected_ids:
                        obj["Read"] = True
                    obj["Collected"] = False  # Signs never disappear
                elif obj["ID"] in collected_ids:
                    obj["Collected"] = True
            self.shown_tips = set(data.get("shown_tips", []))
            self.completed_quests = set(data.get("completed_quests", []))
            self.hero_log = data.get("hero_log", [])
            self.battle_won = data.get("battle_won", False)
            self.shrine_solved = data.get("shrine_solved", False)
            self.keys_held = set(data.get("keys_held", []))
            self.shrine_levers = data.get("shrine_levers", {"red": False, "blue": False, "green": False})
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
        # Load map and objects from scenario config
        sc = self.scenario or {}
        origin = sc.get("origin", [0, 10])
        self.origin_col = origin[0]
        self.origin_row = origin[1]
        map_file = os.path.join(PROJECT_DIR, sc.get("map_file", "world_map.csv"))
        obj_file = os.path.join(PROJECT_DIR, sc.get("objects_file", "map_objects.csv"))
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
        self.max_mp = sc.get("max_mp", 12.0)
        self.quest_stage = 1
        self.victory = False
        self.status_msg = "Type spells below! Example: move_right(3)"
        self.status_color = (120, 240, 150)
        # Clear preview -- don't auto-run so MP shows 0/12 cleanly
        self.preview_data: dict[str, Any] = {"mp_used": 0.0, "path": [], "terraforms": [], "valid": False, "picked_ids": [], "expected_gold": 0, "expected_wood": 0, "expected_dragons": 0}
        self.last_mtime = 0  # Force re-preview on next save

        # ── Spell Command Console state ──
        self.console_input = ""              # Current line being typed
        self.console_commands: list[str] = []  # Accumulated commands this turn
        self.console_history: list[str] = []   # Full history for ↑/↓ recall
        self.console_history_idx = -1          # -1 = not browsing history
        self.console_output: list[tuple[str, tuple[int,int,int]]] = []  # (text, color) log lines
        self.console_cursor_blink = 0          # For blinking cursor animation
        self.console_multiline = ""            # Buffer for multi-line blocks (for/if)
        self.console_in_block = False          # True when collecting indented continuation
        self.console_active = True             # Console always active in this version

        # ── Act II+ systems ──
        self.shown_tips: set[str] = set()      # Archmage Tips already shown (persisted)
        self.completed_quests: set[str] = set()  # Quest IDs completed (persisted)
        self.active_tip: dict[str, Any] | None = None  # Currently displayed tip overlay
        self.hero_log: list[str] = []          # Output from say() and print()
        self.sphinx_answers_correct = 0        # Track Sphinx progress

        # ── Act III systems ──
        self.in_battle = False                 # True during battle tutorial
        self.battle_won = False                # True after winning battle
        self.battle_lost = False               # True after losing battle
        self.battle_round = 0
        self.battle_player: dict = {}
        self.battle_enemy: dict = {}
        self.shrine_levers = {"red": False, "blue": False, "green": False}
        self.shrine_solved = False
        self.keys_held: set[str] = set()       # Keys collected (e.g. "blue")

        # ── Button rects (overwritten by draw() every frame) ──
        self.btn_preview = pygame.Rect(0, 0, 0, 0)
        self.btn_commit = pygame.Rect(0, 0, 0, 0)
        self.btn_grid = pygame.Rect(0, 0, 0, 0)
        self.btn_reset = pygame.Rect(0, 0, 0, 0)
        self.btn_next_act = None
        self._populate_scout_and_sign_data()
        self._populate_act3_data()

    # ── Campaign / Scenario system ──
    def load_scenario(self, scenario_id: str):
        """Load a scenario config JSON file."""
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
        """Transition to a new act (called when beating the current act's boss)."""
        self.load_scenario(act_id)
        self.reset_game(clear_save=True)
        self.console_output.clear()
        title = self.scenario.get("title", act_id) if self.scenario else act_id
        self.console_add_output(f"═══ {title} ═══", (250, 215, 75))
        self.console_add_output(self.scenario.get("subtitle", ""), (180, 200, 220)) if self.scenario else None
        self.console_add_output("Type 'help' for commands.", (140, 180, 200))
        self.save_game()

    # ── Archmage Tip popup system ──
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
                'say("hello") shouts a message on the map.',
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
                '3 is an int.  3.5 is a float.  "hello" is a str.',
                "True and False are bools. Use type(x) to check!",
                "The Sphinx wants answers of the RIGHT TYPE.",
            ]
        },
        "constants": {
            "title": "✦ The Laws of the Realm",
            "lines": [
                "COST = 60 names a price you use many times.",
                "UPPERCASE names = constants that never change.",
                "Change it ONCE at the top, it updates everywhere!",
            ]
        },
        "operators": {
            "title": "✦ The Art of Calculation",
            "lines": [
                "gold // 60 = how many you can buy (drops remainder).",
                "gold % 60 = the leftover gold (the change).",
                "Try: print(1500 // 60, 'pikemen', 1500 % 60, 'change')",
            ]
        },
        "type_cast": {
            "title": "✦ Shape-Shifting Magic",
            "lines": [
                'Signs give you TEXT: "1500" — that\'s NOT a number!',
                'Use int("1500") to turn text into the number 1500.',
                'Use float("2.5") for decimals, str(42) for text.',
            ]
        },
        "strings": {
            "title": "✦ Words Have Power",
            "lines": [
                '"DRAGON"[0] is "D".  "DRAGON"[::-1] is "NOGARD".',
                '.upper() makes UPPERCASE.  .lower() makes lowercase.',
                "Reverse the Keymaster's scroll to open the gate!",
            ]
        },
        # ── Act III Tips ──
        "if_else": {
            "title": "✦ The Fork in the Road",
            "lines": [
                'if today() == "sandstorm": take the detour!',
                'else: go straight across the desert.',
                "The weather changes every day. You must DECIDE!",
            ]
        },
        "look_ahead": {
            "title": "✦ Scout the Path",
            "lines": [
                'look(x, y) tells you what is at a tile.',
                'if look(6, 3) == "Monster": go around!',
                "Check before you move — or walk into danger!",
            ]
        },
        "boolean": {
            "title": "✦ True and False",
            "lines": [
                "and = BOTH must be true.  or = ONE is enough.",
                "not = flip True to False (or False to True).",
                "Set levers to make the shrine's rule TRUE!",
            ]
        },
        "compound_if": {
            "title": "✦ Complex Decisions",
            "lines": [
                "if gold >= 500 and not is_sandstorm:",
                "  Combine conditions with and / or / not.",
                "Parentheses ( ) group conditions like math!",
            ]
        },
        "battle_intro": {
            "title": "✦ The Arena Awaits!",
            "lines": [
                "Your Pikemen face the Troglodytes!",
                "if adjacent: attack()  else: move_toward()",
                "Type ONE command per round. Win to proceed!",
            ]
        },
    }

    def show_tip(self, tip_id: str):
        """Show an Archmage Tip popup (only once per save)."""
        if tip_id in self.shown_tips:
            return
        tip_data = self.ARCHMAGE_TIPS.get(tip_id)
        if not tip_data:
            return
        self.shown_tips.add(tip_id)
        self.active_tip = dict(tip_data)

    # ── Quest check functions for Act II ──
    def _check_quest(self, quest_id: str) -> bool:
        """Run the check function for a quest. Returns True if passed."""
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
        if checker:
            return checker()
        return False

    def _check_comments(self) -> bool:
        """Did they type at least 2 lines starting with #?"""
        return sum(1 for cmd in self.console_commands if cmd.strip().startswith("#")) >= 2

    def _check_output(self) -> bool:
        """Did they use say() with the correct password?"""
        return any(a[0] == "say" and "erathia" in str(a[1]).lower()
                   for a in hero_api._actions)

    def _check_variables(self) -> bool:
        """Did they use scout() and store the result?"""
        code = "\n".join(self.console_commands)
        return "scout(" in code and "=" in code

    def _check_data_types(self) -> bool:
        """Did they answer the Sphinx correctly?"""
        return self.sphinx_answers_correct >= 3

    def _check_constants(self) -> bool:
        """Did they define an UPPERCASE constant?"""
        code = "\n".join(self.console_commands)
        return bool(re.search(r'\b[A-Z_]{2,}\s*=', code))

    def _check_operators(self) -> bool:
        """Did they use // or % in their commands?"""
        code = "\n".join(self.console_commands)
        return "//" in code or "%" in code

    def _check_type_cast(self) -> bool:
        """Did they use int() or float() conversion?"""
        code = "\n".join(self.console_commands)
        return ("int(" in code or "float(" in code)

    def _check_strings(self) -> bool:
        """Did they open the gate with the reversed password?"""
        return any(a[0] == "open_gate" and a[1] == "DRAGON"
                   for a in hero_api._actions)

    # ── Act II Guard interaction logic ──
    def _check_act2_guard(self, obj, sim):
        """Check if an Act II guard's quest requirement is met. Returns (passed, hint)."""
        guard_quests = {
            4: ("comments", "Silence curses with # comments first!"),
            6: ("output", 'Use say("For Erathia!") to shout the password!'),
            10: ("variables", "Use x, y = scout('Merchant') and move_to(x, y)!"),
            17: ("operators", "Use // to calculate! e.g. print(gold // 60)"),
            22: ("type_cast", "Read the signs with read_sign(x,y) and convert with int()!"),
            24: ("strings", 'Reverse "NOGARD" and use open_gate()!'),
        }
        guard_id = obj["ID"]
        if guard_id in guard_quests:
            quest_id, hint = guard_quests[guard_id]
            if quest_id in self.completed_quests or self._check_quest(quest_id):
                self.completed_quests.add(quest_id)
                return True, ""
            return False, hint
        return True, ""  # Unknown guard, let through

    # ── New API helper methods ──
    def _api_scout(self, name: str):
        """Find an object by name, return its (x, y)."""
        name_lower = str(name).lower()
        for obj in self.objects:
            if not obj["Collected"] and name_lower in obj["Name"].lower():
                return (obj["X"], obj["Y"])
        return None

    def _api_read_sign(self, x: int, y: int) -> str:
        """Read a sign's text at (x, y). Marks the sign as read."""
        for obj in self.objects:
            if obj["X"] == int(x) and obj["Y"] == int(y) and obj["Type"] == "Sign":
                obj["Read"] = True
                return obj["Description"]
        return ""

    def _build_hero_object(self):
        """Build a read-only hero stats object."""
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
        return h

    def _handle_say_actions(self):
        """Process any say() actions from the current command set."""
        for act in hero_api._actions:
            if act[0] == "say":
                text = str(act[1])
                self.hero_log.append(text)
                # Add floating speech bubble
                px = self.hero_col * TILE_SIZE + 8
                py = self.hero_row * TILE_SIZE - 20
                self.floating_texts.append([f'💬 {text}', px, py, 90, (255, 255, 220)])

    def _handle_sphinx_answers(self):
        """Process answer_sphinx() actions and check types."""
        riddles = [
            ("float", "a number with a DECIMAL POINT"),
            ("str", "a piece of TEXT in quotes"),
            ("bool", "TRUE or FALSE"),
        ]
        answer_idx = 0
        for act in hero_api._actions:
            if act[0] == "answer_sphinx" and answer_idx < len(riddles):
                value = act[1]
                expected_type, desc = riddles[answer_idx]
                actual_type = type(value).__name__
                if actual_type == expected_type:
                    self.sphinx_answers_correct += 1
                    self.console_add_output(f"✓ Correct! {repr(value)} is a {actual_type}.", (110, 255, 130))
                else:
                    self.console_add_output(f"✗ Wrong type! {repr(value)} is a {actual_type}, not a {expected_type}.", (255, 120, 120))
                    self.console_add_output(f"  The Sphinx wanted: {desc}", (255, 200, 100))
                answer_idx += 1

    def _handle_open_gate(self):
        """Process open_gate() actions."""
        for act in hero_api._actions:
            if act[0] == "open_gate":
                if act[1] == "DRAGON":
                    self.console_add_output("✓ The gate swings open! DRAGON is correct!", (110, 255, 130))
                else:
                    self.console_add_output(f'✗ "{act[1]}" is not the password. Hint: reverse "NOGARD"!', (255, 120, 120))

    def _populate_scout_and_sign_data(self):
        """Fill hero_api scout/sign lookup tables before exec."""
        hero_api._scout_results = {}
        hero_api._sign_results = {}
        for obj in self.objects:
            if not obj["Collected"] or obj["Type"] == "Sign":
                hero_api._scout_results[obj["Name"]] = (obj["X"], obj["Y"])
                if obj["Type"] == "Sign":
                    hero_api._sign_results[(obj["X"], obj["Y"])] = obj["Description"]

    # ── Act III: Daily Events, Look, Shrines, Battle Tutorial ──
    def _get_today(self) -> str:
        """Deterministic daily event based on day number."""
        events = ["clear", "sandstorm", "oasis", "clear", "sandstorm",
                  "clear", "oasis", "clear", "sandstorm", "clear"]
        return events[self.day % len(events)]

    def _populate_act3_data(self):
        """Fill hero_api with Act III data: weather, look results, keys."""
        hero_api._today_result = self._get_today()
        hero_api._keys_held = getattr(self, "keys_held", set())
        # Build look results: terrain + objects
        hero_api._look_results = {}
        if hasattr(self, "grid") and self.grid:
            for r in range(len(self.grid)):
                for c in range(len(self.grid[0])):
                    mx, my = self.grid_to_math(c, r)
                    hero_api._look_results[(mx, my)] = self.grid[r][c]
        # Objects override terrain
        for obj in self.objects:
            if not obj["Collected"]:
                hero_api._look_results[(obj["X"], obj["Y"])] = obj["Type"]

    def _handle_set_lever(self):
        """Process set_lever() actions and check shrine solutions."""
        levers = getattr(self, "shrine_levers", {"red": False, "blue": False, "green": False})
        for act in hero_api._actions:
            if act[0] == "set_lever":
                levers[act[1]] = act[2]
                self.console_add_output(f"⚙ Lever '{act[1]}' set to {act[2]}", (200, 180, 255))
        self.shrine_levers = levers
        # Check all shrine objects to see if any are solved
        for obj in self.objects:
            if obj["Type"] == "Shrine" and not obj["Collected"]:
                expr = obj["Description"]
                if self._eval_shrine(expr, levers):
                    obj["Collected"] = True
                    self.shrine_solved = True
                    self.console_add_output(f"✓ Shrine solved! Rule: {expr} = True!", (110, 255, 130))
                    px, py = obj.get("col", obj["X"]) * TILE_SIZE + 8, obj.get("row", obj["Y"]) * TILE_SIZE
                    self.floating_texts.append(["✦ Shrine Solved!", px, py, 80, (200, 180, 255)])

    def _eval_shrine(self, expression: str, levers: dict) -> bool:
        """Evaluate a boolean expression with lever values."""
        expr = expression.replace("AND", "and").replace("OR", "or").replace("NOT", "not")
        ns = {k: v for k, v in levers.items()}
        try:
            return bool(eval(expr, {"__builtins__": {}}, ns))
        except Exception:
            return False

    # ── Battle Tutorial (Act III simplified 1v1) ──
    def _start_battle(self):
        """Start a battle tutorial: Pikemen vs Troglodytes."""
        self.in_battle = True
        self.battle_round = 0
        self.battle_won = False
        self.battle_lost = False
        # Player: 10 Pikemen, Atk 4, Def 5, Dmg 1-3, HP 10, Speed 4
        self.battle_player = {
            "name": "Pikemen", "count": 10, "hp": 10, "top_hp": 10,
            "atk": 4, "dfn": 5, "dmg_min": 1, "dmg_max": 3,
            "x": 1, "y": 3, "speed": 4,
        }
        # Enemy: 8 Troglodytes, Atk 4, Def 3, Dmg 1-3, HP 5, Speed 4
        self.battle_enemy = {
            "name": "Troglodytes", "count": 8, "hp": 5, "top_hp": 5,
            "atk": 4, "dfn": 3, "dmg_min": 1, "dmg_max": 3,
            "x": 7, "y": 3, "speed": 4,
        }
        self.console_add_output("═══ BATTLE! ═══", (255, 80, 80))
        self.console_add_output(f"Your {self.battle_player['count']} Pikemen vs {self.battle_enemy['count']} Troglodytes!", (255, 200, 100))
        self.console_add_output("Commands: attack()  move_toward()  defend()", (180, 220, 255))
        self.console_add_output("Type a command and press Enter for each round.", (140, 180, 200))

    def _run_battle_round(self):
        """Execute one round of the battle tutorial."""
        import random
        if not getattr(self, "in_battle", False):
            return
        self.battle_round += 1
        p = self.battle_player
        e = self.battle_enemy
        dist = abs(p["x"] - e["x"]) + abs(p["y"] - e["y"])

        # Process player action
        action = None
        for act in hero_api._actions:
            if act[0] in ("battle_attack", "battle_move_toward", "battle_defend"):
                action = act[0]
                break

        if action == "battle_attack":
            if dist <= 1:
                dmg = self._battle_calc_damage(p, e)
                self._battle_apply_damage(e, dmg)
                self.console_add_output(f"⚔ Pikemen attack! {dmg} damage to Troglodytes!", (120, 255, 120))
            else:
                # Move adjacent first, then attack if possible
                self._battle_move_unit(p, e)
                new_dist = abs(p["x"] - e["x"]) + abs(p["y"] - e["y"])
                if new_dist <= 1:
                    dmg = self._battle_calc_damage(p, e)
                    self._battle_apply_damage(e, dmg)
                    self.console_add_output(f"⚔ Pikemen charge and attack! {dmg} damage!", (120, 255, 120))
                else:
                    self.console_add_output(f"→ Pikemen advance toward Troglodytes.", (200, 220, 255))
        elif action == "battle_move_toward":
            self._battle_move_unit(p, e)
            self.console_add_output(f"→ Pikemen move to ({p['x']}, {p['y']}).", (200, 220, 255))
        elif action == "battle_defend":
            p["defending"] = True
            self.console_add_output("🛡 Pikemen brace for impact! (+30% defense)", (100, 200, 255))
        else:
            self.console_add_output("? No valid battle command. Use attack(), move_toward(), or defend().", (255, 200, 100))

        # Check if enemy is dead
        if e["count"] <= 0:
            self.battle_won = True
            self.in_battle = False
            self.console_add_output("═══ VICTORY! Troglodytes defeated! ═══", (255, 215, 0))
            self.console_add_output(f"Your Pikemen survived: {p['count']} remaining.", (120, 255, 120))
            return

        # Enemy turn: simple AI — move toward, attack if adjacent
        dist = abs(p["x"] - e["x"]) + abs(p["y"] - e["y"])
        if dist <= 1:
            defense_bonus = 1.3 if p.get("defending") else 1.0
            dmg = self._battle_calc_damage(e, p, defense_mult=defense_bonus)
            self._battle_apply_damage(p, dmg)
            self.console_add_output(f"💀 Troglodytes attack! {dmg} damage to Pikemen!", (255, 120, 120))
        else:
            self._battle_move_unit(e, p)
            self.console_add_output(f"→ Troglodytes advance to ({e['x']}, {e['y']}).", (255, 180, 180))

        p["defending"] = False  # Reset defend

        # Check if player is dead
        if p["count"] <= 0:
            self.battle_lost = True
            self.in_battle = False
            self.console_add_output("═══ DEFEAT! Your Pikemen have fallen! ═══", (255, 80, 80))
            self.console_add_output("Try again! Use if/else to decide when to attack vs defend.", (255, 200, 100))
            return

        # Status
        self.console_add_output(f"── Round {self.battle_round} end: Pikemen {p['count']}×{p['top_hp']}hp | Trogs {e['count']}×{e['top_hp']}hp ──", (180, 180, 200))

    def _battle_calc_damage(self, attacker, defender, defense_mult=1.0):
        """Calculate battle damage (simplified H3 formula)."""
        import random
        base = attacker["count"] * random.randint(attacker["dmg_min"], attacker["dmg_max"])
        atk, dfn = attacker["atk"], int(defender["dfn"] * defense_mult)
        if atk > dfn:
            base = int(base * (1 + 0.05 * min(atk - dfn, 60)))
        else:
            base = int(base * max(0.3, 1 - 0.025 * min(dfn - atk, 28)))
        return max(1, base)

    def _battle_apply_damage(self, stack, damage):
        """Apply damage to a unit stack, killing units as needed."""
        remaining_dmg = damage
        while remaining_dmg > 0 and stack["count"] > 0:
            if remaining_dmg >= stack["top_hp"]:
                remaining_dmg -= stack["top_hp"]
                stack["count"] -= 1
                stack["top_hp"] = stack["hp"]  # Next unit at full HP
            else:
                stack["top_hp"] -= remaining_dmg
                remaining_dmg = 0

    def _battle_move_unit(self, mover, target):
        """Move a unit toward a target (simple step, not pathfinding)."""
        dx = target["x"] - mover["x"]
        dy = target["y"] - mover["y"]
        steps = min(mover["speed"], abs(dx) + abs(dy) - 1)  # Stop adjacent
        for _ in range(max(1, steps)):
            if abs(dx) >= abs(dy):
                mover["x"] += 1 if dx > 0 else -1
            else:
                mover["y"] += 1 if dy > 0 else -1
            dx = target["x"] - mover["x"]
            dy = target["y"] - mover["y"]
            if abs(dx) + abs(dy) <= 1:
                break

    # ── Act III quest checks ──
    def _check_act3_weather(self) -> bool:
        """Used if/today() in commands."""
        code = "\n".join(self.console_commands)
        return "if " in code and "today()" in code

    def _check_act3_look(self) -> bool:
        """Used look() with if."""
        code = "\n".join(self.console_commands)
        return "look(" in code and "if " in code

    def _check_act3_shrine(self) -> bool:
        """Solved a logic shrine."""
        return getattr(self, "shrine_solved", False)

    def _check_act3_compound(self) -> bool:
        """Used and/or/not in an if statement."""
        code = "\n".join(self.console_commands)
        has_bool = " and " in code or " or " in code or "not " in code
        return has_bool and "if " in code

    def _check_act3_battle(self) -> bool:
        """Won the battle tutorial."""
        return getattr(self, "battle_won", False)

    def _check_act3_guard(self, obj, sim):
        """Check if an Act III guard's quest requirement is met."""
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
                self.completed_quests.add(quest_id)
                return True, ""
            return False, hint
        return True, ""

    def _build_act3_sidebar_scroll(self) -> list:
        """Build the sidebar quest list for Act III."""
        quests = [
            ("act3_weather", "1. If/Else", "Handle daily weather"),
            ("act3_look", "2. Scout", "Check tiles with look()"),
            ("act3_shrine", "3. Boolean", "Solve logic shrines"),
            ("act3_compound", "4. Compound", "Use and/or/not in if"),
            ("act3_battle", "5. Battle", "Win the Arena fight"),
        ]
        scroll: list[tuple[str, tuple[int, int, int]]] = [
            ("ACT III: THE SHIFTING SANDS", (255, 220, 85)),
            (f"Quests: {sum(1 for q, _, _ in quests if q in self.completed_quests)} / 5", (180, 200, 220)),
            (f"Weather: {self._get_today().upper()}", (255, 200, 100)),
            ("", (0, 0, 0)),
        ]
        for quest_id, name, desc in quests:
            done = quest_id in self.completed_quests
            marker = "+" if done else "-"
            col = (110, 235, 130) if done else (200, 200, 215)
            scroll.append((f"  {marker} {name}: {desc}", col))

        scroll.append(("", (0, 0, 0)))
        # Battle status
        if getattr(self, "in_battle", False):
            p = self.battle_player
            e = self.battle_enemy
            scroll.append(("BATTLE IN PROGRESS!", (255, 80, 80)))
            scroll.append((f"  Pikemen: {p['count']}x{p['top_hp']}hp", (120, 255, 120)))
            scroll.append((f"  Troglodytes: {e['count']}x{e['top_hp']}hp", (255, 120, 120)))
            scroll.append((f"  Round: {self.battle_round}", (200, 200, 220)))
        else:
            for quest_id, name, desc in quests:
                if quest_id not in self.completed_quests:
                    scroll.append(("CURRENT OBJECTIVE:", (135, 220, 255)))
                    scroll.append((f"  {desc}", (255, 230, 95)))
                    break
            else:
                scroll.append(("ALL QUESTS DONE! Defeat the Boss!", (255, 215, 0)))
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
        """Find an active object at grid tile (col, row)."""
        for obj in self.objects:
            if obj.get("col") == col and obj.get("row") == row and (not obj["Collected"] or obj["Type"] == "Sign"):
                return obj
        return None

    def get_object_at_math(self, x: int, y: int):
        """Find an active object at math coordinates (x, y)."""
        col, row = self.math_to_grid(x, y)
        return self.get_object_at(col, row)

    # ------------------------------------------------------------------------
    # HYBRID (RELATIVE + ABSOLUTE) SIMULATION & PREVIEW ENGINE
    # ------------------------------------------------------------------------
    def _interact_object(self, obj, sim, x, y, mp, cost=0.0):
        """Unified object interaction logic. Returns True if valid, False if blocked."""
        if obj["ID"] in sim["picked_ids"]:
            return True
        if obj["Type"] == "Gold":
            sim["expected_gold"] += obj["Value"]
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Mine":
            sim["expected_wood"] += obj["Value"]
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Guard":
            # Quest-based guards (Value == 0, checked by act-specific quest system)
            if obj["Value"] == 0 and self.current_act != "act1":
                if self.current_act == "act3":
                    passed, hint = self._check_act3_guard(obj, sim)
                else:
                    passed, hint = self._check_act2_guard(obj, sim)
                if not passed:
                    sim["valid"] = False
                    sim["error"] = f"🔒 {obj['Name']}: {hint}"
                    sim["path"].append((x, y, mp + cost, False))
                    return False
                sim["picked_ids"].append(obj["ID"])
            # Act I gold-based guards
            elif sim["expected_gold"] < obj["Value"]:
                sim["valid"] = False
                sim["error"] = f"Guard at ({x},{y}) demands {obj['Value']} Gold! (You have {sim['expected_gold']})"
                sim["path"].append((x, y, mp + cost, False))
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
                sim["error"] = f"{obj['Name']} at ({x},{y})! You need at least 1 Dragon to fight! (You have {sim['expected_dragons']})"
                sim["path"].append((x, y, mp + cost, False))
                return False
            else:
                sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Boss":
            if self.current_act == "act1":
                needed = obj["Value"]
                if sim["expected_dragons"] < needed:
                    sim["valid"] = False
                    sim["error"] = f"The {obj['Name']} is too powerful! Need {needed} Dragons! (You have {sim['expected_dragons']})"
                    sim["path"].append((x, y, mp + cost, False))
                    return False
                else:
                    sim["picked_ids"].append(obj["ID"])
            else:
                # Act II+ boss: check all quests completed
                all_done = len(self.completed_quests) >= 7  # 7 concept quests before boss
                if not all_done:
                    sim["valid"] = False
                    done = len(self.completed_quests)
                    sim["error"] = f"The {obj['Name']} laughs! Complete all quests first! ({done}/7)"
                    sim["path"].append((x, y, mp + cost, False))
                    return False
                sim["picked_ids"].append(obj["ID"])
        # Act II types: Sign, NPC, Sphinx — auto-collect on visit
        elif obj["Type"] == "Sign":
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "NPC":
            # Arena Master triggers battle
            if "Arena" in obj["Name"] and self.current_act == "act3":
                if not getattr(self, "in_battle", False) and not getattr(self, "battle_won", False):
                    self._start_battle()
            sim["expected_gold"] += obj["Value"]
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Sphinx":
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Shrine":
            sim["picked_ids"].append(obj["ID"])
        elif obj["Type"] == "Marketplace":
            sim["picked_ids"].append(obj["ID"])
        return True

    # ------------------------------------------------------------------
    # SPELL COMMAND CONSOLE — execute typed commands
    # ------------------------------------------------------------------
    def _build_console_namespace(self):
        """Build the exec() namespace with all hero_api functions available."""
        self._populate_scout_and_sign_data()
        self._populate_act3_data()
        ns: dict[str, Any] = {
            # Movement
            "move_right": hero_api.move_right,
            "move_left": hero_api.move_left,
            "move_down": hero_api.move_down,
            "move_up": hero_api.move_up,
            "move_by": hero_api.move_by,
            "move_to": hero_api.move_to,
            "terraform": hero_api.terraform,
            # Act II functions
            "say": hero_api.say,
            "scout": hero_api.scout,
            "read_sign": self._api_read_sign,
            "answer_sphinx": hero_api.answer_sphinx,
            "recruit": hero_api.recruit,
            "open_gate": hero_api.open_gate,
            # Act III functions
            "today": hero_api.today,
            "look": hero_api.look,
            "has_key": hero_api.has_key,
            "set_lever": hero_api.set_lever,
            "attack": hero_api.attack,
            "move_toward": hero_api.move_toward,
            "defend": hero_api.defend,
            # Hero stats
            "hero": self._build_hero_object(),
            "gold": self.gold,
            "wood": self.wood,
            "dragons": self.dragons,
            "day": self.day,
            "hero_x": self.hero_x,
            "hero_y": self.hero_y,
            # Builtins
            "print": self._console_print,
            "range": range,
            "abs": abs,
            "int": int,
            "float": float,
            "str": str,
            "len": len,
            "min": min,
            "max": max,
            "type": type,
            "round": round,
            "bool": bool,
            "True": True,
            "False": False,
            "None": None,
        }
        return ns

    def _console_print(self, *args, **kwargs):
        """Redirect print() calls from console into the output log."""
        sep = kwargs.get("sep", " ")
        text = sep.join(str(a) for a in args)
        self.console_add_output(text, (200, 220, 255))

    def console_add_output(self, text: str, color: tuple = (200, 200, 200)):
        """Add a line to the console output log, keeping at most 50 lines."""
        self.console_output.append((text, color))
        if len(self.console_output) > 50:
            self.console_output = self.console_output[-50:]

    def execute_console_command(self, line: str):
        """Execute a single console command string."""
        stripped = line.strip()
        if not stripped:
            return

        # ── Battle mode: each command = one round ──
        if getattr(self, "in_battle", False):
            hero_api._reset()
            ns = self._build_console_namespace()
            try:
                exec(stripped, ns)
            except Exception as e:
                self.console_add_output(f"⚠ {e}", (255, 120, 80))
            self._run_battle_round()
            self.console_input = ""
            # Add to history
            if not self.console_history or self.console_history[-1] != stripped:
                self.console_history.append(stripped)
            self.console_history_idx = len(self.console_history)
            return

        # Special commands
        if stripped.lower() in ("clear", "cls"):
            self.console_commands.clear()
            self.console_output.clear()
            self.console_add_output("✦ Spells cleared! Ready for new commands.", (120, 240, 150))
            self.run_console_preview()
            return
        if stripped.lower() == "undo":
            if self.console_commands:
                removed = self.console_commands.pop()
                self.console_add_output(f"↩ Undid: {removed}", (255, 200, 100))
                self.run_console_preview()
            else:
                self.console_add_output("Nothing to undo.", (180, 180, 180))
            return
        if stripped.lower() == "help":
            for helpline in [
                "╔══ MOVEMENT ═════════════════════╗",
                "║ move_right(n)  move_left(n)      ║",
                "║ move_up(n)     move_down(n)       ║",
                "║ move_to(x, y)  move_by(dx, dy)   ║",
                "║ terraform(x, y, 'B')             ║",
                "╠══ ACT II SPELLS ════════════════╣",
                '║ say("text")     - shout on map    ║',
                "║ scout('name')   - find NPC (x,y)  ║",
                "║ read_sign(x,y)  - read sign text   ║",
                "║ answer_sphinx(v) - answer riddle   ║",
                "║ recruit('unit',n) - hire troops    ║",
                '║ open_gate("pw")  - unlock gate     ║',
                "╠══ ACT III DECISIONS ════════════╣",
                "║ today()    - check the weather     ║",
                "║ look(x, y) - inspect a tile        ║",
                "║ has_key(c) - check for a key        ║",
                '║ set_lever("red", True)  - shrine   ║',
                "║ attack()       - battle: hit!       ║",
                "║ move_toward()  - battle: advance    ║",
                "║ defend()       - battle: brace      ║",
                "╠══ SPECIAL ═══════════════════════╣",
                "║ clear  - erase all spells         ║",
                "║ undo   - remove last spell        ║",
                "║ list   - show queued spells        ║",
                "║ Ctrl+Enter - commit turn           ║",
                "╚═════════════════════════════════╝",
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

        # Store command and try to execute
        self.console_commands.append(stripped)
        self.console_add_output(f">>> {stripped}", (130, 200, 130))

        # Run preview with all accumulated commands
        self.run_console_preview()

    def run_console_preview(self):
        """Replay all console commands to build the preview."""
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
            # No console commands — show clean state
            self.preview_data = sim
            self.status_msg = "Type spells below! Example: move_right(3)"
            self.status_color = (120, 240, 150)
            return

        # Replay all commands in sequence
        ns = self._build_console_namespace()
        code = "\n".join(self.console_commands)
        try:
            exec(code, {"__builtins__": {}}, ns)
        except Exception as e:
            etype = type(e).__name__
            sim["valid"] = False
            sim["error"] = f"⚡ Spell fizzled! {etype}: {e}"
            self.preview_data = sim
            self.status_msg = sim["error"]
            self.status_color = (255, 105, 105)
            # Remove the bad command
            if self.console_commands:
                bad = self.console_commands.pop()
                self.console_add_output(f"⚡ Spell fizzled: {etype}: {e}", (255, 110, 110))
                self.console_add_output(f"   (removed: {bad})", (255, 160, 100))
            return

        # Now simulate the path from hero_api._actions (same as run_preview)
        self._simulate_path(sim)

    def run_preview(self):
        """Run preview from my_hero.py file (fallback / legacy mode)."""
        # If console has commands, use console preview instead
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
            # Call plan_turn -- return value is optional now
            sys.modules["my_hero"].plan_turn(self.gold, self.wood)
        except Exception as e:
            sim["valid"] = False
            sim["error"] = f"Code Error: {str(e)}"
            self.preview_data = sim
            self.status_msg = sim["error"]
            self.status_color = (255, 105, 105)
            return

        self._simulate_path(sim)

    def _simulate_path(self, sim: dict[str, Any]):
        """Shared simulation logic: process hero_api._actions into a path preview."""
        temp_grid = [r[:] for r in self.grid]
        cur_col, cur_row = self.hero_col, self.hero_row
        mp = 0.0

        # Expand BOTH relative ('rel') and absolute ('abs') commands into steps
        step_queue = []
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
                    step_queue.append((cur_col, cur_row))

        cur_col, cur_row = self.hero_col, self.hero_row

        # Check if the hero begins the turn standing on an uncollected object (e.g. Dwelling)
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

            # Auto-interact: gold, wood, guards, mages, dwellings, monsters, boss
            obj = self.get_object_at(ncol, nrow)
            if obj and obj["ID"] not in sim["picked_ids"]:
                if not self._interact_object(obj, sim, mx, my, mp, cost):
                    break

            mp += cost
            cur_col, cur_row = ncol, nrow
            sim["path"].append((cur_col, cur_row, mp, True))

        sim["mp_used"] = mp

        # Build status message with pickup summary
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

    def commit_turn(self):
        self.run_preview()
        if not self.preview_data or not self.preview_data["valid"]:
            return

        # Process special actions before committing
        if self.current_act != "act1":
            self._handle_say_actions()
            self._handle_sphinx_answers()
            self._handle_open_gate()
        if self.current_act == "act3":
            self._handle_set_lever()

        # Mark any signs read via code read_sign()
        for sx, sy in getattr(hero_api, "_read_signs", set()):
            for obj in self.objects:
                if obj["X"] == sx and obj["Y"] == sy and obj["Type"] == "Sign":
                    obj["Read"] = True

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
                        obj["Collected"] = False  # Signs NEVER disappear!
                        self.console_add_output(f"📜 Sign: {obj['Description']}", (255, 225, 95))
                        msg = "📜 Read Again" if already_read else "📜 Read Sign!"
                        self.floating_texts.append([msg, px, py, 60, (255, 240, 140)])
                    elif not obj["Collected"]:
                        obj["Collected"] = True
                        if obj["Type"] == "Gold":
                            self.floating_texts.append([f"+{obj['Value']} Gold!", px, py, 65, (255, 225, 55)])
                        elif obj["Type"] == "Mine":
                            self.floating_texts.append([f"+{obj['Value']} Wood/day!", px, py, 65, (120, 225, 255)])
                        elif obj["Type"] in ("Guard", "Mage"):
                            if self.current_act == "act1":
                                self.floating_texts.append(["Region 2 Unlocked!", px, py, 80, (140, 255, 150)])
                                self.quest_stage = 2
                            else:
                                self.floating_texts.append(["✦ Gate Opened!", px, py, 60, (140, 255, 150)])
                        elif obj["Type"] == "Dwelling":
                            if self.current_act == "act1":
                                self.floating_texts.append([f"+{obj['Value']} Green Dragons!", px, py, 80, (85, 255, 130)])
                                if self.quest_stage < 3:
                                    self.quest_stage = 3
                            else:
                                self.floating_texts.append(["Barracks Visited!", px, py, 60, (85, 255, 130)])
                        elif obj["Type"] == "Monster":
                            self.floating_texts.append([f"{obj['Name']} Defeated!", px, py, 65, (255, 180, 80)])
                        elif obj["Type"] == "Boss":
                            self.floating_texts.append(["BOSS DEFEATED!!! VICTORY!!!", px, py, 120, (255, 215, 0)])
                            boss_slain = True
                        elif obj["Type"] == "NPC":
                            self.floating_texts.append([f"+{obj['Value']} Gold from {obj['Name']}!", px, py, 65, (255, 225, 55)])
                        elif obj["Type"] == "Sphinx":
                            self.floating_texts.append(["The Sphinx speaks...", px, py, 60, (200, 180, 255)])

        self.gold = self.preview_data["expected_gold"]
        self.wood = self.preview_data["expected_wood"]
        self.dragons = self.preview_data.get("expected_dragons", self.dragons)

        # Collect daily income from mines that were previously flagged
        for obj in self.objects:
            if obj["Type"] == "Mine" and obj["Collected"] and obj["ID"] not in self.preview_data["picked_ids"]:
                self.wood += obj["Value"]

        self.day += 1

        # Show Archmage Tips based on hero position
        if self.current_act == "act2":
            self._trigger_zone_tips()
        elif self.current_act == "act3":
            self._trigger_act3_zone_tips()
            # Show weather in console
            self.console_add_output(f"  Weather: {self._get_today()}", (255, 200, 100))

        if boss_slain:
            self.victory = True
            if self.current_act == "act1":
                self.status_msg = f"VICTORY on Day {self.day}! The Black Dragon is defeated! You are a Python Master!"
            elif self.current_act == "act2":
                self.status_msg = f"ACT II COMPLETE on Day {self.day}! You've mastered the Hero's Journal!"
            elif self.current_act == "act3":
                self.status_msg = f"ACT III COMPLETE on Day {self.day}! The Sand Wyrm is defeated!"
            else:
                self.status_msg = f"VICTORY on Day {self.day}!"
            self.status_color = (255, 215, 0)
        else:
            self.status_msg = f"Day {self.day}! Hero at ({self.hero_x}, {self.hero_y}). Cast new spells!"
            self.status_color = (125, 215, 255)
        # Clear console commands for the new turn
        self.console_commands.clear()
        self.console_add_output(f"═══ Day {self.day} ═══ Hero at ({self.hero_x}, {self.hero_y})", (250, 215, 75))
        self.save_game()
        self.run_console_preview()

    def _trigger_zone_tips(self):
        """Show Archmage Tips when the hero enters a quest zone in Act II."""
        hx, hy = self.hero_x, self.hero_y
        zones = [
            # (x_range, y_range, tip_id)
            ((1, 5), (1, 3), "comments"),
            ((7, 12), (0, 3), "output"),
            ((8, 12), (1, 4), "variables"),
            ((13, 16), (3, 6), "data_types"),
            ((12, 16), (5, 7), "constants"),
            ((3, 7), (6, 9), "operators"),
            ((7, 13), (7, 9), "type_cast"),
            ((12, 15), (6, 8), "strings"),
        ]
        for (x0, x1), (y0, y1), tip_id in zones:
            if x0 <= hx < x1 and y0 <= hy < y1:
                self.show_tip(tip_id)
                break

    def _trigger_act3_zone_tips(self):
        """Show Archmage Tips when the hero enters a quest zone in Act III."""
        hx, hy = self.hero_x, self.hero_y
        zones = [
            ((0, 5), (3, 7), "if_else"),
            ((5, 9), (1, 5), "look_ahead"),
            ((7, 11), (5, 9), "boolean"),
            ((10, 14), (2, 6), "compound_if"),
            ((13, 16), (4, 9), "battle_intro"),
        ]
        for (x0, x1), (y0, y1), tip_id in zones:
            if x0 <= hx < x1 and y0 <= hy < y1:
                self.show_tip(tip_id)
                break

    def _build_act2_sidebar_scroll(self) -> list:
        """Build the sidebar quest list for Act II."""
        quests = [
            ("comments", "1. Comments", "Silence curses with #"),
            ("output", "2. Output", "Use say() and print()"),
            ("variables", "3. Variables", "Store scout() results"),
            ("data_types", "4. Data Types", "Answer the Sphinx"),
            ("constants", "5. Constants", "Use UPPERCASE names"),
            ("operators", "6. Operators", "Use // and % math"),
            ("type_cast", "7. Type Casting", "Convert text to numbers"),
            ("strings", "8. Strings", "Reverse the password"),
        ]
        title = self.scenario.get("title", "Act II") if self.scenario else "Act II"
        scroll: list[tuple[str, tuple[int, int, int]]] = [
            (f"ACT II: {title.upper()}", (255, 220, 85)),
            (f"Quests: {len(self.completed_quests)} / 8 complete", (180, 200, 220)),
            ("", (0, 0, 0)),
        ]
        for quest_id, name, desc in quests:
            done = quest_id in self.completed_quests
            marker = "+" if done else "-"
            col = (110, 235, 130) if done else (200, 200, 215)
            scroll.append((f"  {marker} {name}: {desc}", col))

        # Current objective hint
        scroll.append(("", (0, 0, 0)))
        # Find first incomplete quest
        for quest_id, name, desc in quests:
            if quest_id not in self.completed_quests:
                scroll.append(("CURRENT OBJECTIVE:", (135, 220, 255)))
                scroll.append((f"  {desc}", (255, 230, 95)))
                break
        else:
            scroll.append(("ALL QUESTS DONE! Defeat the Boss!", (255, 215, 0)))
            scroll.append(("  Move to the Tax Collector.", (255, 230, 95)))

        return scroll

    # ------------------------------------------------------------------------
    # RENDERING ON 1920x1080 CANVAS -> SCALED TO ANY WINDOW SIZE
    # ------------------------------------------------------------------------
    def draw(self):
        self.canvas.fill((22, 24, 32))
        mouse_x, mouse_y = self.window_to_virtual(pygame.mouse.get_pos())
        sx = MAP_COLS * TILE_SIZE

        # Display grid = real map + previewed terraforms, so auto-tiling (roads, bridges,
        # shorelines) already looks right while the player is still planning.
        display_grid = self.grid
        if self.preview_data and self.preview_data["terraforms"]:
            display_grid = [row[:] for row in self.grid]
            for tx, ty, ttype in self.preview_data["terraforms"]:
                display_grid[ty][tx] = ttype

        # 1. Draw Map Tiles — NO border lines between tiles for seamless look
        for r in range(MAP_ROWS):
            for c in range(MAP_COLS):
                px, py = c * TILE_SIZE, r * TILE_SIZE
                self.canvas.blit(self.art.get_tile(display_grid, c, r, self.base_grid), (px, py))

                # Coordinate labels (when grid is toggled on)
                if self.show_grid:
                    math_x, math_y = self.grid_to_math(c, r)
                    # Subtle semi-transparent grid line instead of solid black
                    grid_overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    pygame.draw.rect(grid_overlay, (255, 255, 255, 30), (0, 0, TILE_SIZE, TILE_SIZE), 1)

                    # Axis markings (X-Axis: y=0, Y-Axis: x=0)
                    if math_y == 0:  # X-Axis
                        pygame.draw.line(grid_overlay, (255, 220, 90, 140), (0, TILE_SIZE - 2), (TILE_SIZE, TILE_SIZE - 2), 2)
                    if math_x == 0:  # Y-Axis
                        pygame.draw.line(grid_overlay, (255, 220, 90, 140), (1, 0), (1, TILE_SIZE), 2)

                    self.canvas.blit(grid_overlay, (px, py))

                    # Origin marker (0, 0)
                    if (math_x, math_y) == (0, 0):
                        pygame.draw.rect(self.canvas, (255, 215, 0), (px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2), 2, border_radius=4)
                        lbl_shadow = self.font_coord.render("0,0 ★", True, (0, 0, 0))
                        lbl = self.font_coord.render("0,0 ★", True, (255, 235, 110))
                    else:
                        lbl_shadow = self.font_coord.render(f"{math_x},{math_y}", True, (0, 0, 0))
                        lbl = self.font_coord.render(f"{math_x},{math_y}", True, (240, 245, 235))
                    self.canvas.blit(lbl_shadow, (px + 6, py + 4))
                    self.canvas.blit(lbl, (px + 5, py + 3))

        # 2. Draw Preview Terraforms (magic spell previews)
        if self.preview_data:
            for tx, ty, ttype in self.preview_data["terraforms"]:
                px, py = tx * TILE_SIZE, ty * TILE_SIZE
                self.canvas.blit(self.art.tiles.get(ttype, self.art.tiles["B"]), (px, py))
                pygame.draw.rect(self.canvas, (190, 120, 255), (px+3, py+3, TILE_SIZE-6, TILE_SIZE-6), 4, border_radius=8)

        # 3. Draw Map Objects
        for obj in self.objects:
            if not obj["Collected"]:
                self.art.draw_object(self.canvas, obj, obj.get("col", obj["X"]) * TILE_SIZE, obj.get("row", obj["Y"]) * TILE_SIZE, self.tick)

        # 4. Draw Preview Path — GREEN line & dots only, NO ghost hero
        if self.preview_data and len(self.preview_data["path"]) > 1:
            pts = self.preview_data["path"]
            for i in range(1, len(pts)):
                x1, y1, _, _ = pts[i-1]
                x2, y2, _, ok = pts[i]
                p1 = (x1 * TILE_SIZE + TILE_SIZE // 2, y1 * TILE_SIZE + TILE_SIZE // 2)
                p2 = (x2 * TILE_SIZE + TILE_SIZE // 2, y2 * TILE_SIZE + TILE_SIZE // 2)
                col = (85, 255, 130) if ok else (255, 80, 80)
                # Dark outline for visibility on any terrain
                pygame.draw.line(self.canvas, (15, 45, 20), p1, p2, 10)
                # Bright colored path line
                pygame.draw.line(self.canvas, col, p1, p2, 6)
                # Step dot
                pygame.draw.circle(self.canvas, col, p2, 8)
                pygame.draw.circle(self.canvas, (255, 255, 255), p2, 4)

            # Pulsing destination marker
            fx, fy, _, f_ok = pts[-1]
            dest_px = fx * TILE_SIZE + TILE_SIZE // 2
            dest_py = fy * TILE_SIZE + TILE_SIZE // 2
            dest_col = (85, 255, 130) if f_ok else (255, 80, 80)
            pulse = int(abs(math.sin(self.tick * 0.1)) * 6)
            pygame.draw.circle(self.canvas, dest_col, (dest_px, dest_py), 14 + pulse, 3)
            pygame.draw.circle(self.canvas, (255, 255, 255), (dest_px, dest_py), 5)

        # 5. Draw Active Hero (solid, not ghost)
        self.art.draw_hero(self.canvas, self.hero_col * TILE_SIZE, self.hero_row * TILE_SIZE, self.tick)

        # 5b. Map Tile Hover Cursor (glowing frame on hovered tile)
        if 0 <= mouse_x < sx and 0 <= mouse_y < MAP_ROWS * TILE_SIZE:
            hover_hc = mouse_x // TILE_SIZE
            hover_hr = mouse_y // TILE_SIZE
            if 0 <= hover_hc < MAP_COLS and 0 <= hover_hr < MAP_ROWS:
                hpx, hpy = hover_hc * TILE_SIZE, hover_hr * TILE_SIZE
                hover_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                hover_pulse = int(abs(math.sin(self.tick * 0.12)) * 30)
                # Soft translucent background
                pygame.draw.rect(hover_surf, (255, 235, 120, 32 + hover_pulse // 3), (0, 0, TILE_SIZE, TILE_SIZE), border_radius=6)
                # Luminous golden border
                pygame.draw.rect(hover_surf, (255, 225 + hover_pulse, 85, 220), (1, 1, TILE_SIZE - 2, TILE_SIZE - 2), 3, border_radius=6)
                self.canvas.blit(hover_surf, (hpx, hpy))

        # 6. Floating Text Animations
        for ft in self.floating_texts[:]:
            surf = self.font_lg.render(ft[0], True, ft[4])
            self.canvas.blit(surf, (ft[1], ft[2]))
            ft[2] -= 1.0
            ft[3] -= 1
            if ft[3] <= 0:
                self.floating_texts.remove(ft)

        # 6b. Victory Overlay
        self.btn_next_act = None  # Reset each frame
        if self.victory:
            map_w = MAP_COLS * TILE_SIZE
            map_h = MAP_ROWS * TILE_SIZE
            overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            self.canvas.blit(overlay, (0, 0))

            # Pulsing golden text
            pulse = int(abs(math.sin(self.tick * 0.05)) * 40)
            victory_font = pygame.font.SysFont("dejavusans", 72, bold=True)
            sub_font = pygame.font.SysFont("dejavusans", 36, bold=True)
            btn_font = pygame.font.SysFont("dejavusans", 28, bold=True)
            gold_col = (215 + pulse, 185 + pulse // 2, 0)

            txt1 = victory_font.render("VICTORY!", True, gold_col)
            if self.current_act == "act1":
                txt2 = sub_font.render("The Black Dragon has been slain!", True, (240, 235, 220))
            else:
                txt2 = sub_font.render("The Hero's Journal is complete!", True, (240, 235, 220))
            txt3 = sub_font.render(f"Conquered in {self.day} Days", True, (135, 220, 255))

            self.canvas.blit(txt1, (map_w // 2 - txt1.get_width() // 2, map_h // 2 - 100))
            self.canvas.blit(txt2, (map_w // 2 - txt2.get_width() // 2, map_h // 2 - 20))
            self.canvas.blit(txt3, (map_w // 2 - txt3.get_width() // 2, map_h // 2 + 30))

            # "Continue to Act II" button (only if there's a next act)
            next_act = self.scenario.get("next_scenario") if self.scenario else None
            if next_act:
                self.btn_next_act = pygame.Rect(map_w // 2 - 180, map_h // 2 + 85, 360, 56)
                glow_btn = int(abs(math.sin(self.tick * 0.08)) * 25)
                btn_col = (35 + glow_btn, 140 + glow_btn, 65 + glow_btn)
                pygame.draw.rect(self.canvas, btn_col, self.btn_next_act, border_radius=14)
                pygame.draw.rect(self.canvas, (200, 235, 200), self.btn_next_act, 2, border_radius=14)
                next_label = f"Continue to Act II →" if next_act == "act2" else f"Continue →"
                txt_btn = btn_font.render(next_label, True, (255, 255, 255))
                self.canvas.blit(txt_btn, (self.btn_next_act.x + self.btn_next_act.w // 2 - txt_btn.get_width() // 2,
                                           self.btn_next_act.y + 12))

        # 6c. Archmage Tip Overlay
        if self.active_tip:
            map_w = MAP_COLS * TILE_SIZE
            map_h = MAP_ROWS * TILE_SIZE
            # Semi-transparent backdrop
            overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.canvas.blit(overlay, (0, 0))
            # Tip box
            box_w, box_h = 700, 220
            box_x = map_w // 2 - box_w // 2
            box_y = map_h // 2 - box_h // 2
            tip_font_title = pygame.font.SysFont("dejavusans", 30, bold=True)
            tip_font_body = pygame.font.SysFont("dejavusansmono", 21, bold=False)
            tip_font_hint = pygame.font.SysFont("dejavusans", 18, bold=False)
            # Box background with gold border
            pygame.draw.rect(self.canvas, (28, 25, 40), (box_x, box_y, box_w, box_h), border_radius=16)
            pygame.draw.rect(self.canvas, (210, 175, 65), (box_x, box_y, box_w, box_h), 3, border_radius=16)
            # Title
            title_surf = tip_font_title.render(self.active_tip["title"], True, (250, 215, 75))
            self.canvas.blit(title_surf, (box_x + box_w // 2 - title_surf.get_width() // 2, box_y + 16))
            # Body lines
            for i, line in enumerate(self.active_tip.get("lines", [])):
                col = (200, 230, 255) if i % 2 == 0 else (180, 255, 190)
                self.canvas.blit(tip_font_body.render(line, True, col), (box_x + 30, box_y + 60 + i * 32))
            # Dismiss hint
            dismiss = tip_font_hint.render("Press any key to continue...", True, (150, 150, 170))
            self.canvas.blit(dismiss, (box_x + box_w // 2 - dismiss.get_width() // 2, box_y + box_h - 34))

        # 7. Right Sidebar
        sx = MAP_COLS * TILE_SIZE
        pygame.draw.rect(self.canvas, (30, 34, 46), (sx, 0, SIDEBAR_WIDTH, VIRTUAL_H))
        pygame.draw.line(self.canvas, (95, 105, 135), (sx, 0), (sx, VIRTUAL_H), 3)

        self.canvas.blit(self.font_title.render("HEROES OF PYTHON", True, (250, 215, 75)), (sx + 24, 18))

        # Stats Card
        pygame.draw.rect(self.canvas, (42, 47, 64), (sx + 20, 68, SIDEBAR_WIDTH - 40, 195), border_radius=12)
        mp_used = self.preview_data["mp_used"] if self.preview_data else 0.0
        preview_gold = self.preview_data.get('expected_gold', self.gold) if self.preview_data else self.gold
        preview_dragons = self.preview_data.get('expected_dragons', self.dragons) if self.preview_data else self.dragons
        stats = [
            (f"Day {self.day}    Hero At: ({self.hero_x}, {self.hero_y})", (235, 240, 250)),
            (f"Move Points: {mp_used:.1f} / {self.max_mp:.1f} MP", (120, 245, 155) if mp_used <= self.max_mp else (255, 105, 105)),
            (f"Gold: {self.gold}  (After Turn: {preview_gold})", (255, 220, 65)),
            (f"Wood: {self.wood}  (Sawmills Flagged)", (205, 165, 115)),
            (f"Dragons: {self.dragons}  (After Turn: {preview_dragons})", (85, 255, 130) if self.dragons > 0 else (140, 140, 140)),
        ]
        for i, (txt, col) in enumerate(stats):
            self.canvas.blit(self.font_md.render(txt, True, col), (sx + 34, 80 + i * 34))

        # Tutorial Scroll Card
        scroll_y = 280
        scroll_h = 486
        pygame.draw.rect(self.canvas, (48, 42, 34), (sx + 20, scroll_y, SIDEBAR_WIDTH - 40, scroll_h), border_radius=12)
        pygame.draw.rect(self.canvas, (205, 170, 90), (sx + 20, scroll_y, SIDEBAR_WIDTH - 40, scroll_h), 3, border_radius=12)

        if self.current_act == "act3":
            scroll = self._build_act3_sidebar_scroll()
        elif self.current_act == "act2":
            scroll = self._build_act2_sidebar_scroll()
        elif self.victory:
            scroll = [
                ("*** VICTORY! ***", (255, 215, 0)),
                ("", (0,0,0)),
                ("You have defeated the Black Dragon", (240, 235, 220)),
                ("and conquered the Lava Sanctuary!", (240, 235, 220)),
                ("", (0,0,0)),
                ("PYTHON SKILLS LEARNED:", (135, 220, 255)),
                ("  * Variables (gold, wood, dragons)", (165, 250, 175)),
                ("  * Functions (move_to, terraform)", (165, 250, 175)),
                ("  * For-Loops (bridging terrain)", (165, 250, 175)),
                ("  * Coordinates (x, y grid system)", (165, 250, 175)),
                ("  * CSV Databases (map_objects.csv)", (165, 250, 175)),
                ("", (0,0,0)),
                ("Click [Continue to Act II] above!", (255, 190, 125)),
            ]
        elif self.quest_stage == 1:
            scroll = [
                ("QUEST 1: THREE WAYS TO MOVE", (255, 220, 85)),
                ("Goal: Collect 1,500 Gold & bribe the", (240, 235, 220)),
                ("Border Guard at coordinate (7, 7)!", (240, 235, 220)),
                ("", (0,0,0)),
                ("1. DIRECTIONAL STEPS (Relative):", (135, 220, 255)),
                ("   move_right(3)  or  move_up(1)", (165, 250, 175)),
                ("", (0,0,0)),
                ("2. RELATIVE VECTOR (From Hero):", (135, 220, 255)),
                ("   move_by(dx, dy) e.g. move_by(3, -1)", (165, 250, 175)),
                ("", (0,0,0)),
                ("3. ABSOLUTE COORDINATE (Exact Tile):", (135, 220, 255)),
                ("   move_to(x, y)  e.g. move_to(4, 9)", (165, 250, 175)),
                ("", (0,0,0)),
                ("Gold is AUTO-COLLECTED on step!", (255, 230, 95)),
                ("Just walk to it -- no extra code needed.", (255, 230, 95)),
                ("", (0,0,0)),
                ("TIP: Hover mouse on any tile to compare", (255, 190, 125)),
                ("move_to(x, y) vs move_by(dx, dy)!", (255, 190, 125)),
            ]
        elif self.quest_stage == 2:
            scroll = [
                ("QUEST 2: THE LOOP BRIDGE SPELL", (255, 220, 85)),
                ("Goal: Bridge the River (X=10) & reach", (240, 235, 220)),
                ("the Green Dragon Cliff at (14, 9)!", (240, 235, 220)),
                ("", (0,0,0)),
                ("SPELL: terraform(x, y, 'B')", (205, 165, 255)),
                ("Turns Water (W) or Lava (L) into a", (215, 215, 215)),
                ("walkable Enchanted Bridge ('B')!", (215, 215, 215)),
                ("", (0,0,0)),
                ("PYTHON FOR-LOOPS:", (135, 220, 255)),
                ("To bridge the river at column X=10:", (215, 215, 215)),
                ("  for y in range(0, 11):", (165, 250, 175)),
                ("      terraform(10, y, 'B')", (165, 250, 175)),
                ("", (0,0,0)),
                ("Then move_to(14, 9) for dragons!", (255, 190, 125)),
                ("You may need to terraform mountains.", (255, 190, 125)),
            ]
        else:  # quest_stage >= 3
            scroll = [
                ("QUEST 3: SLAY THE BLACK DRAGON", (255, 220, 85)),
                ("Goal: March south to (14, 1) and", (240, 235, 220)),
                ("defeat the Boss with your dragons!", (240, 235, 220)),
                ("", (0,0,0)),
                ("ARMY STATUS:", (135, 220, 255)),
                (f"  Dragons in Army: {self.dragons} / 5", (85, 255, 130) if self.dragons >= 5 else (255, 160, 80)),
                ("  Boss Requirement: 5 Dragons", (215, 215, 215)),
                ("", (0,0,0)),
                ("HOW TO REACH THE BOSS:", (135, 220, 255)),
                ("1. If needed, bridge Lava row Y=4:", (215, 215, 215)),
                ("   for x in range(10, 16):", (165, 250, 175)),
                ("       terraform(x, 4, 'B')", (165, 250, 175)),
                ("2. Move straight down column 14:", (215, 215, 215)),
                ("   move_to(14, 1)", (165, 250, 175)),
            ]

        for i, (txt, col) in enumerate(scroll):
            self.canvas.blit(self.font_sm.render(txt, True, col), (sx + 36, scroll_y + 18 + i * 26))

        # Tile Inspector — expanded with word-wrap for long descriptions
        inspector_y = 776
        inspector_h = 280
        pygame.draw.rect(self.canvas, (42, 47, 64), (sx + 20, inspector_y, SIDEBAR_WIDTH - 40, inspector_h), border_radius=12)
        pygame.draw.rect(self.canvas, (75, 88, 120), (sx + 20, inspector_y, SIDEBAR_WIDTH - 40, inspector_h), 2, border_radius=12)
        inspector_max_w = SIDEBAR_WIDTH - 80  # Max text width inside the card
        if 0 <= mouse_x < sx and 0 <= mouse_y < MAP_ROWS * TILE_SIZE:
            hc, hr = mouse_x // TILE_SIZE, mouse_y // TILE_SIZE
            if 0 <= hc < MAP_COLS and 0 <= hr < MAP_ROWS:
                tx, ty = self.grid_to_math(hc, hr)
                dx, dy = tx - self.hero_x, ty - self.hero_y
                tcode = self.grid[hr][hc]
                obj = self.get_object_at(hc, hr)
                # Tile name (with wrapping)
                origin_suffix = " ★ [ORIGIN]" if (tx, ty) == (0, 0) else ""
                hero_suffix = " ⚔ [HERO]" if (hc, hr) == (self.hero_col, self.hero_row) else ""
                tile_text = f"Tile ({tx}, {ty}){origin_suffix}{hero_suffix} -- {TERRAIN_NAMES.get(tcode, tcode)}"
                tile_lines = self._wrap_text(tile_text, self.font_md, inspector_max_w)
                cur_y = inspector_y + 12
                for tl in tile_lines:
                    self.canvas.blit(self.font_md.render(tl, True, (225, 240, 255)), (sx + 32, cur_y))
                    cur_y += 26
                self.canvas.blit(self.font_sm.render(f"Absolute: move_to({tx}, {ty})", True, (150, 250, 175)), (sx + 32, cur_y))
                cur_y += 24
                self.canvas.blit(self.font_sm.render(f"Relative: move_by({dx}, {dy})", True, (150, 250, 175)), (sx + 32, cur_y))
                cur_y += 26
                if obj:
                    is_read = obj["Type"] == "Sign" and obj.get("Read", False)
                    prefix = "✓ [READ] " if is_read else "* "
                    color = (130, 245, 150) if is_read else (255, 225, 95)
                    obj_text = f"{prefix}{obj['Name']}: {obj['Description']}"
                    obj_lines = self._wrap_text(obj_text, self.font_sm, inspector_max_w)
                    for ol in obj_lines:
                        if cur_y < inspector_y + inspector_h - 10:  # Don't overflow the box
                            self.canvas.blit(self.font_sm.render(ol, True, color), (sx + 32, cur_y))
                            cur_y += 22
            else:
                self.canvas.blit(self.font_md.render("Hover mouse over any tile on the map!", True, (180, 195, 215)), (sx + 32, inspector_y + 45))
        else:
            self.canvas.blit(self.font_md.render("Hover mouse over any tile on the map!", True, (180, 195, 215)), (sx + 32, inspector_y + 45))

        # 8. Bottom Spell Console Bar
        by = MAP_ROWS * TILE_SIZE
        console_w = sx - 300  # Reserve 300px on the right for buttons
        btn_col_x = sx - 280  # Button column start

        # Background
        pygame.draw.rect(self.canvas, (18, 20, 28), (0, by, sx, BOTTOM_BAR_HEIGHT))
        pygame.draw.line(self.canvas, (70, 85, 120), (0, by), (sx, by), 3)

        # ── Status message bar (top strip) ──
        pygame.draw.rect(self.canvas, (30, 34, 46), (0, by + 2, console_w, 30))
        # Word-wrap status message if it's too long
        status_max_w = console_w - 24
        if self.font_sm.size(self.status_msg)[0] > status_max_w:
            status_lines = self._wrap_text(self.status_msg, self.font_sm, status_max_w)
            # Show just the first line that fits in the status bar
            self.canvas.blit(self.font_sm.render(status_lines[0], True, self.status_color), (12, by + 7))
        else:
            self.canvas.blit(self.font_sm.render(self.status_msg, True, self.status_color), (12, by + 7))

        # ── Console output log (scrollable area) ──
        log_y = by + 34
        log_h = 170  # Height for output lines
        pygame.draw.rect(self.canvas, (12, 14, 22), (4, log_y, console_w - 8, log_h), border_radius=6)

        # Show last N lines that fit
        line_h = 22
        max_visible = log_h // line_h
        visible_lines = self.console_output[-max_visible:] if self.console_output else []
        line_idx = 0
        for text, color in visible_lines:
            if line_idx >= max_visible:
                break
            # Word-wrap long console lines instead of truncating
            console_max_w = console_w - 28
            wrapped = self._wrap_text(text, self.font_console, console_max_w)
            for wl in wrapped:
                if line_idx >= max_visible:
                    break
                self.canvas.blit(self.font_console.render(wl, True, color), (14, log_y + 4 + line_idx * line_h))
                line_idx += 1

        # ── Console input line (bottom) ──
        input_y = by + 34 + log_h + 6
        input_h = 32
        # Subtle glow effect on the input box
        self.console_cursor_blink += 1
        glow = int(abs(math.sin(self.console_cursor_blink * 0.06)) * 30)
        border_col = (55 + glow, 100 + glow, 180 + min(glow, 40))
        pygame.draw.rect(self.canvas, (22, 26, 36), (4, input_y, console_w - 8, input_h), border_radius=6)
        pygame.draw.rect(self.canvas, border_col, (4, input_y, console_w - 8, input_h), 2, border_radius=6)

        # Prompt and text
        prompt = "... " if self.console_in_block else ">>> "
        prompt_color = (100, 180, 255) if not self.console_in_block else (180, 140, 255)
        self.canvas.blit(self.font_console_bold.render(prompt, True, prompt_color), (12, input_y + 5))
        prompt_w = self.font_console_bold.size(prompt)[0]

        # Input text (scroll if too long)
        display_input = self.console_input
        max_input_w = console_w - 40 - prompt_w
        while self.font_console.size(display_input)[0] > max_input_w and len(display_input) > 1:
            display_input = display_input[1:]
        self.canvas.blit(self.font_console.render(display_input, True, (230, 240, 255)), (12 + prompt_w, input_y + 5))

        # Blinking cursor
        if (self.console_cursor_blink // 20) % 2 == 0:
            cursor_x = 12 + prompt_w + self.font_console.size(display_input)[0] + 2
            pygame.draw.rect(self.canvas, (120, 200, 255), (cursor_x, input_y + 5, 2, 20))

        # ── Spell count badge ──
        n_spells = len(self.console_commands)
        badge_text = f"{n_spells} spell{'s' if n_spells != 1 else ''} queued"
        badge_color = (110, 245, 145) if n_spells > 0 else (120, 120, 140)
        self.canvas.blit(self.font_sm.render(badge_text, True, badge_color), (console_w - 180, input_y + 8))

        # ── Right-side button column ──
        btn_w = 260
        btn_h = 50

        can_commit = self.preview_data and self.preview_data["valid"]
        self.btn_commit = pygame.Rect(btn_col_x, by + 10, btn_w, btn_h)
        self.btn_grid = pygame.Rect(btn_col_x, by + 68, btn_w, btn_h)
        self.btn_reset = pygame.Rect(btn_col_x, by + 126, btn_w, btn_h)
        self.btn_preview = pygame.Rect(btn_col_x, by + 184, btn_w, btn_h)

        # Commit button (most prominent)
        commit_col = (45, 175, 90) if can_commit else (55, 60, 70)
        pygame.draw.rect(self.canvas, commit_col, self.btn_commit, border_radius=10)
        self.canvas.blit(self.font_md.render("⚔ COMMIT TURN", True, (255, 255, 255)), (self.btn_commit.x + 36, self.btn_commit.y + 12))

        # Grid toggle
        grid_col = (80, 70, 140) if self.show_grid else (55, 50, 85)
        pygame.draw.rect(self.canvas, grid_col, self.btn_grid, border_radius=10)
        grid_label = "▦ Grid: ON" if self.show_grid else "▦ Grid: OFF"
        self.canvas.blit(self.font_md.render(grid_label, True, (220, 220, 240)), (self.btn_grid.x + 60, self.btn_grid.y + 12))

        # Reset button
        pygame.draw.rect(self.canvas, (140, 50, 50), self.btn_reset, border_radius=10)
        self.canvas.blit(self.font_md.render("↺ Reset Map", True, (255, 200, 200)), (self.btn_reset.x + 52, self.btn_reset.y + 12))

        # Preview button (least prominent, since console auto-previews)
        pygame.draw.rect(self.canvas, (45, 85, 130), self.btn_preview, border_radius=10)
        self.canvas.blit(self.font_md.render("⟐ Reload my_hero.py", True, (180, 210, 255)), (self.btn_preview.x + 16, self.btn_preview.y + 12))

        # Scale canvas to window with aspect-ratio-preserving fit
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

        pygame.display.flip()

    def run(self):
        running = True
        # Enable key repeat for smooth typing (delay 400ms, repeat every 35ms)
        pygame.key.set_repeat(400, 35)
        while running:
            self.tick += 1
            # Auto-reload when my_hero.py is saved (only if console is empty)
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

                # ── Archmage Tip dismissal (intercepts all input while showing) ──
                elif self.active_tip and (event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN):
                    self.active_tip = None
                    continue  # Don't process this event further

                elif event.type == pygame.KEYDOWN:
                    mods = pygame.key.get_mods()

                    # ── Global shortcuts (always available) ──
                    if event.key == pygame.K_F11:
                        self.fullscreen = not self.fullscreen
                        if self.fullscreen:
                            self.window = pygame.display.set_mode(
                                (0, 0), pygame.FULLSCREEN
                            )
                        else:
                            info = pygame.display.Info()
                            self.window = pygame.display.set_mode(
                                (int(info.current_w * 0.85), int(info.current_h * 0.85)),
                                pygame.RESIZABLE
                            )
                    elif event.key == pygame.K_F5:
                        # F5 = force reload my_hero.py
                        self.console_commands.clear()
                        self.last_mtime = 0
                        self.run_preview()

                    # ── Ctrl shortcuts ──
                    elif mods & pygame.KMOD_CTRL:
                        if event.key == pygame.K_RETURN:
                            # Ctrl+Enter = commit turn
                            self.commit_turn()
                        elif event.key == pygame.K_r:
                            self.reset_game(clear_save=True)
                        elif event.key == pygame.K_g:
                            self.show_grid = not self.show_grid
                        elif event.key == pygame.K_l:
                            # Ctrl+L = clear console output
                            self.console_output.clear()
                        elif event.key == pygame.K_z:
                            # Ctrl+Z = undo last command
                            self.execute_console_command("undo")

                    # ── Console typing ──
                    elif event.key == pygame.K_RETURN:
                        line = self.console_input.strip()
                        if self.console_in_block:
                            if line == "":
                                # Empty line ends the block
                                full_block = self.console_multiline
                                self.console_in_block = False
                                self.console_multiline = ""
                                self.console_input = ""
                                self.execute_console_command(full_block)
                            else:
                                # Append to block
                                self.console_multiline += "\n" + self.console_input
                                self.console_add_output(f"... {self.console_input}", (150, 140, 200))
                                # Auto-indent next line (keep same indent level)
                                indent = len(self.console_input) - len(self.console_input.lstrip())
                                self.console_input = " " * max(indent, 4)
                        else:
                            if line.endswith(":"):
                                # Start a multi-line block (for, if, while, def)
                                self.console_in_block = True
                                self.console_multiline = self.console_input
                                self.console_add_output(f">>> {self.console_input}", (130, 200, 130))
                                self.console_add_output("    (type indented lines, blank Enter to finish)", (120, 120, 160))
                                self.console_input = "    "  # Auto-indent!
                            else:
                                # Single-line command
                                cmd = self.console_input
                                self.console_input = ""
                                if cmd.strip():
                                    self.console_history.append(cmd.strip())
                                    self.console_history_idx = -1
                                    self.execute_console_command(cmd)

                    elif event.key == pygame.K_BACKSPACE:
                        if self.console_input:
                            self.console_input = self.console_input[:-1]

                    elif event.key == pygame.K_ESCAPE:
                        if self.console_in_block:
                            # Cancel multi-line block
                            self.console_in_block = False
                            self.console_multiline = ""
                            self.console_input = ""
                            self.console_add_output("(block cancelled)", (180, 180, 180))
                        else:
                            self.console_input = ""

                    elif event.key == pygame.K_UP:
                        # Navigate command history
                        if self.console_history:
                            if self.console_history_idx == -1:
                                self.console_history_idx = len(self.console_history) - 1
                            elif self.console_history_idx > 0:
                                self.console_history_idx -= 1
                            self.console_input = self.console_history[self.console_history_idx]

                    elif event.key == pygame.K_DOWN:
                        if self.console_history_idx >= 0:
                            self.console_history_idx += 1
                            if self.console_history_idx >= len(self.console_history):
                                self.console_history_idx = -1
                                self.console_input = ""
                            else:
                                self.console_input = self.console_history[self.console_history_idx]

                    elif event.key == pygame.K_TAB:
                        # Simple tab-completion for commands
                        partial = self.console_input.lstrip()
                        completions = [
                            "move_right(", "move_left(", "move_up(", "move_down(",
                            "move_to(", "move_by(", "terraform(",
                            "say(", "scout(", "read_sign(", "answer_sphinx(",
                            "recruit(", "open_gate(", "type(",
                            "today(", "look(", "has_key(", "set_lever(",
                            "attack(", "move_toward(", "defend(",
                            "for ", "if ", "elif ", "else:", "range(",
                            "print(", "int(", "float(", "str(",
                            "True", "False", "and ", "or ", "not ",
                            "clear", "undo", "help", "list",
                        ]
                        matches = [c for c in completions if c.startswith(partial)]
                        if len(matches) == 1:
                            # Preserve leading whitespace
                            leading = len(self.console_input) - len(self.console_input.lstrip())
                            self.console_input = " " * leading + matches[0]
                        elif len(matches) > 1:
                            self.console_add_output("  ".join(matches), (180, 220, 255))

                    elif event.unicode and event.unicode.isprintable():
                        self.console_input += event.unicode

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    vpos = self.window_to_virtual(event.pos)
                    # "Continue to Act II" button on victory overlay
                    if self.btn_next_act and self.btn_next_act.collidepoint(vpos):
                        next_act = self.scenario.get("next_scenario") if self.scenario else None
                        if next_act:
                            self.start_act(next_act)
                    elif self.btn_preview.collidepoint(vpos):
                        self.console_commands.clear()
                        self.last_mtime = 0
                        self.run_preview()
                    elif self.btn_commit.collidepoint(vpos):
                        self.commit_turn()
                    elif self.btn_grid.collidepoint(vpos):
                        self.show_grid = not self.show_grid
                    elif self.btn_reset.collidepoint(vpos):
                        self.reset_game(clear_save=True)

            # Handle window resize: detect size change each frame (works on all platforms)
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
