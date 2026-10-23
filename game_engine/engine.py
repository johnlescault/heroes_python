import os
import sys
import csv
import json
import math
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

def _reset():
    _actions.clear()

def move_right(steps=1):
    """Move relative to the right by 'steps' tiles."""
    _actions.append(("rel", int(steps), 0))

def move_left(steps=1):
    """Move relative to the left by 'steps' tiles."""
    _actions.append(("rel", -int(steps), 0))

def move_down(steps=1):
    """Move relative down by 'steps' tiles."""
    _actions.append(("rel", 0, int(steps)))

def move_up(steps=1):
    """Move relative up by 'steps' tiles."""
    _actions.append(("rel", 0, -int(steps)))

def move_by(dx, dy):
    """Move relative to current position by (dx, dy) tiles."""
    _actions.append(("rel", int(dx), int(dy)))

def move_to(x, y):
    """Move to the exact absolute map coordinate (x, y)."""
    _actions.append(("abs", int(x), int(y)))

def terraform(x, y, tile_type="B"):
    """Alter the map grid at absolute coordinate (x, y)."""
    _actions.append(("terraform", int(x), int(y), str(tile_type).upper()))
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
BOTTOM_BAR_HEIGHT = 156

VIRTUAL_W = MAP_COLS * TILE_SIZE + SIDEBAR_WIDTH   # 1920 px
VIRTUAL_H = MAP_ROWS * TILE_SIZE + BOTTOM_BAR_HEIGHT  # 1080 px

TERRAIN_COSTS = {
    "R": 0.5,  # Dirt Road
    "G": 1.0,  # Grass
    "B": 1.0,  # Bridge
    "M": None, # Mountain (Blocked)
    "W": None, # Water (Blocked)
    "L": None, # Lava (Blocked)
    "F": None, # Dense Forest (Blocked)
}

TERRAIN_NAMES = {
    "R": "Cobble Road (0.5 MP)",
    "G": "Emerald Grass (1.0 MP)",
    "B": "Enchanted Bridge (1.0 MP)",
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

        self.show_grid = True
        self.last_mtime = 0
        self.tick = 0
        self.floating_texts = []
        self.reset_game()
        # Restore saved game if available
        if self.load_game():
            self.status_msg = f"Game Loaded! Day {self.day}, Hero at ({self.hero_x}, {self.hero_y})."
            self.status_color = (120, 240, 150)
            self.run_preview()

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
                "hero_x": self.hero_x,
                "hero_y": self.hero_y,
                "gold": self.gold,
                "wood": self.wood,
                "dragons": self.dragons,
                "day": self.day,
                "quest_stage": self.quest_stage,
                "victory": self.victory,
                "grid": self.grid,
                "collected_ids": [obj["ID"] for obj in self.objects if obj["Collected"]],
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
            self.hero_x = data.get("hero_x", 1)
            self.hero_y = data.get("hero_y", 0)
            self.gold = data.get("gold", 0)
            self.wood = data.get("wood", 0)
            self.dragons = data.get("dragons", 0)
            self.day = data.get("day", 1)
            self.quest_stage = data.get("quest_stage", 1)
            self.victory = data.get("victory", False)
            if "grid" in data:
                self.grid = data["grid"]
            collected_ids = set(data.get("collected_ids", []))
            for obj in self.objects:
                if obj["ID"] in collected_ids:
                    obj["Collected"] = True
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
        self.grid = self._load_map(os.path.join(PROJECT_DIR, "world_map.csv"))
        # Pristine copy of the original terrain (bridges use it to know what they span)
        self.base_grid = self._load_map(os.path.join(PROJECT_DIR, "world_map.csv"))
        self.objects = self._load_objects(os.path.join(PROJECT_DIR, "map_objects.csv"))
        self.hero_x = 1
        self.hero_y = 0
        self.gold = 0
        self.wood = 0
        self.dragons = 0
        self.day = 1
        self.max_mp = 12.0
        self.quest_stage = 1
        self.victory = False
        self.status_msg = "Map Reset! Edit my_hero.py and press Ctrl+S to plan your first turn!"
        self.status_color = (120, 240, 150)
        # Clear preview -- don't auto-run so MP shows 0/12 cleanly
        self.preview_data: dict[str, Any] = {"mp_used": 0.0, "path": [], "terraforms": [], "valid": False, "picked_ids": [], "expected_gold": 0, "expected_wood": 0, "expected_dragons": 0}
        self.last_mtime = 0  # Force re-preview on next save

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
                objs.append({
                    "ID": int(row["ID"]),
                    "Type": row["Type"].strip(),
                    "Name": row["Name"].strip(),
                    "X": int(row["X"]),
                    "Y": int(row["Y"]),
                    "Value": int(row["Value"]),
                    "Guard_Power": int(row["Guard_Power"]),
                    "Description": row["Description"].strip(),
                    "Collected": False
                })
        return objs

    def get_object_at(self, x, y):
        for obj in self.objects:
            if obj["X"] == x and obj["Y"] == y and not obj["Collected"]:
                return obj
        return None

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
            if sim["expected_gold"] < obj["Value"]:
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
            needed = obj["Value"]
            if sim["expected_dragons"] < needed:
                sim["valid"] = False
                sim["error"] = f"The {obj['Name']} is too powerful! Need {needed} Dragons! (You have {sim['expected_dragons']})"
                sim["path"].append((x, y, mp + cost, False))
                return False
            else:
                sim["picked_ids"].append(obj["ID"])
        return True

    def run_preview(self):
        hero_api._reset()
        sim: dict[str, Any] = {
            "valid": True,
            "path": [(self.hero_x, self.hero_y, 0.0, True)],
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

        temp_grid = [r[:] for r in self.grid]
        cx, cy = self.hero_x, self.hero_y
        mp = 0.0

        # Expand BOTH relative ('rel') and absolute ('abs') commands into steps
        step_queue = []
        for act in hero_api._actions:
            if act[0] == "terraform":
                _, tx, ty, ttype = act
                if 0 <= tx < MAP_COLS and 0 <= ty < MAP_ROWS:
                    temp_grid[ty][tx] = ttype
                    sim["terraforms"].append((tx, ty, ttype))
            elif act[0] == "rel":
                _, dx, dy = act
                sx = 1 if dx > 0 else (-1 if dx < 0 else 0)
                for _ in range(abs(dx)):
                    cx += sx
                    step_queue.append((cx, cy))
                sy = 1 if dy > 0 else (-1 if dy < 0 else 0)
                for _ in range(abs(dy)):
                    cy += sy
                    step_queue.append((cx, cy))
            elif act[0] == "abs":
                _, tx, ty = act
                while cx != tx:
                    cx += 1 if cx < tx else -1
                    step_queue.append((cx, cy))
                while cy != ty:
                    cy += 1 if cy < ty else -1
                    step_queue.append((cx, cy))

        cx, cy = self.hero_x, self.hero_y

        # Check if the hero begins the turn standing on an uncollected object (e.g. Dwelling)
        init_obj = self.get_object_at(cx, cy)
        if init_obj and init_obj["ID"] not in sim["picked_ids"]:
            if not self._interact_object(init_obj, sim, cx, cy, 0.0):
                self.preview_data = sim
                self.status_msg = sim["error"]
                self.status_color = (255, 110, 110)
                return

        for nx, ny in step_queue:
            if not (0 <= nx < MAP_COLS and 0 <= ny < MAP_ROWS):
                sim["valid"] = False
                sim["error"] = f"Moved off the map edge at ({nx}, {ny})!"
                sim["path"].append((nx, ny, mp, False))
                break

            tile = temp_grid[ny][nx]
            cost = TERRAIN_COSTS.get(tile, None)
            if cost is None:
                sim["valid"] = False
                sim["error"] = f"Blocked by {TERRAIN_NAMES.get(tile, tile)} at ({nx}, {ny})!"
                sim["path"].append((nx, ny, mp, False))
                break

            if mp + cost > self.max_mp:
                sim["valid"] = False
                sim["error"] = f"Out of Movement Points! ({mp + cost:.1f} / {self.max_mp} MP)"
                sim["path"].append((nx, ny, mp + cost, False))
                break

            # Auto-interact: gold, wood, guards, mages, dwellings, monsters, boss
            obj = self.get_object_at(nx, ny)
            if obj and obj["ID"] not in sim["picked_ids"]:
                if not self._interact_object(obj, sim, nx, ny, mp, cost):
                    break

            mp += cost
            cx, cy = nx, ny
            sim["path"].append((cx, cy, mp, True))

        sim["mp_used"] = mp

        # Build status message with pickup summary
        if sim["valid"]:
            pickup_msgs = []
            for pid in sim["picked_ids"]:
                for obj in self.objects:
                    if obj["ID"] == pid and not obj["Collected"]:
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

        for tx, ty, ttype in self.preview_data["terraforms"]:
            self.grid[ty][tx] = ttype

        if self.preview_data["path"]:
            fx, fy, _, _ = self.preview_data["path"][-1]
            self.hero_x, self.hero_y = fx, fy

        boss_slain = False
        for oid in self.preview_data["picked_ids"]:
            for obj in self.objects:
                if obj["ID"] == oid and not obj["Collected"]:
                    obj["Collected"] = True
                    px, py = obj["X"] * TILE_SIZE + 8, obj["Y"] * TILE_SIZE
                    if obj["Type"] == "Gold":
                        self.floating_texts.append([f"+{obj['Value']} Gold!", px, py, 65, (255, 225, 55)])
                    elif obj["Type"] == "Mine":
                        self.floating_texts.append([f"+{obj['Value']} Wood/day!", px, py, 65, (120, 225, 255)])
                    elif obj["Type"] in ("Guard", "Mage"):
                        self.floating_texts.append(["Region 2 Unlocked!", px, py, 80, (140, 255, 150)])
                        self.quest_stage = 2
                    elif obj["Type"] == "Dwelling":
                        self.floating_texts.append([f"+{obj['Value']} Green Dragons!", px, py, 80, (85, 255, 130)])
                        if self.quest_stage < 3:
                            self.quest_stage = 3
                    elif obj["Type"] == "Monster":
                        self.floating_texts.append([f"{obj['Name']} Defeated!", px, py, 65, (255, 180, 80)])
                    elif obj["Type"] == "Boss":
                        self.floating_texts.append(["BOSS SLAIN!!! VICTORY!!!", px, py, 120, (255, 215, 0)])
                        boss_slain = True

        self.gold = self.preview_data["expected_gold"]
        self.wood = self.preview_data["expected_wood"]
        self.dragons = self.preview_data.get("expected_dragons", self.dragons)

        # Collect daily income from mines that were previously flagged
        for obj in self.objects:
            if obj["Type"] == "Mine" and obj["Collected"] and obj["ID"] not in self.preview_data["picked_ids"]:
                self.wood += obj["Value"]

        self.day += 1

        if boss_slain:
            self.victory = True
            self.status_msg = f"VICTORY on Day {self.day}! The Black Dragon is defeated! You are a Python Master!"
            self.status_color = (255, 215, 0)
        else:
            self.status_msg = f"Day {self.day}! Hero at ({self.hero_x}, {self.hero_y}). Update my_hero.py!"
            self.status_color = (125, 215, 255)
        self.save_game()
        self.run_preview()

    # ------------------------------------------------------------------------
    # RENDERING ON 1920x1080 CANVAS -> SCALED TO ANY WINDOW SIZE
    # ------------------------------------------------------------------------
    def draw(self):
        self.canvas.fill((22, 24, 32))
        mx, my = self.window_to_virtual(pygame.mouse.get_pos())

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
                    # Subtle semi-transparent grid line instead of solid black
                    grid_overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    pygame.draw.rect(grid_overlay, (255, 255, 255, 30), (0, 0, TILE_SIZE, TILE_SIZE), 1)
                    self.canvas.blit(grid_overlay, (px, py))
                    # Coordinate label with dark shadow for readability
                    lbl_shadow = self.font_coord.render(f"{c},{r}", True, (0, 0, 0))
                    lbl = self.font_coord.render(f"{c},{r}", True, (240, 245, 235))
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
                self.art.draw_object(self.canvas, obj, obj["X"] * TILE_SIZE, obj["Y"] * TILE_SIZE, self.tick)

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
        self.art.draw_hero(self.canvas, self.hero_x * TILE_SIZE, self.hero_y * TILE_SIZE, self.tick)

        # 6. Floating Text Animations
        for ft in self.floating_texts[:]:
            surf = self.font_lg.render(ft[0], True, ft[4])
            self.canvas.blit(surf, (ft[1], ft[2]))
            ft[2] -= 1.0
            ft[3] -= 1
            if ft[3] <= 0:
                self.floating_texts.remove(ft)

        # 6b. Victory Overlay
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
            gold_col = (215 + pulse, 185 + pulse // 2, 0)

            txt1 = victory_font.render("VICTORY!", True, gold_col)
            txt2 = sub_font.render("The Black Dragon has been slain!", True, (240, 235, 220))
            txt3 = sub_font.render(f"Conquered in {self.day} Days", True, (135, 220, 255))

            self.canvas.blit(txt1, (map_w // 2 - txt1.get_width() // 2, map_h // 2 - 80))
            self.canvas.blit(txt2, (map_w // 2 - txt2.get_width() // 2, map_h // 2))
            self.canvas.blit(txt3, (map_w // 2 - txt3.get_width() // 2, map_h // 2 + 50))

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

        if self.victory:
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
                ("Click [Reset Map] to play again,", (255, 190, 125)),
                ("or edit the CSV files to make", (255, 190, 125)),
                ("your OWN adventure map!", (255, 190, 125)),
            ]
        elif self.quest_stage == 1:
            scroll = [
                ("QUEST 1: THREE WAYS TO MOVE", (255, 220, 85)),
                ("Goal: Collect 1,500 Gold & bribe the", (240, 235, 220)),
                ("Border Guard at coordinate (7, 3)!", (240, 235, 220)),
                ("", (0,0,0)),
                ("1. DIRECTIONAL STEPS (Relative):", (135, 220, 255)),
                ("   move_right(3)  or  move_down(1)", (165, 250, 175)),
                ("", (0,0,0)),
                ("2. RELATIVE VECTOR (From Hero):", (135, 220, 255)),
                ("   move_by(dx, dy) e.g. move_by(3, 1)", (165, 250, 175)),
                ("", (0,0,0)),
                ("3. ABSOLUTE COORDINATE (Exact Tile):", (135, 220, 255)),
                ("   move_to(x, y)  e.g. move_to(4, 1)", (165, 250, 175)),
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
                ("the Green Dragon Cliff at (14, 1)!", (240, 235, 220)),
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
                ("Then move_to(14, 1) for dragons!", (255, 190, 125)),
                ("You may need to terraform mountains.", (255, 190, 125)),
            ]
        else:  # quest_stage >= 3
            scroll = [
                ("QUEST 3: SLAY THE BLACK DRAGON", (255, 220, 85)),
                ("Goal: March south to (14, 9) and", (240, 235, 220)),
                ("defeat the Boss with your dragons!", (240, 235, 220)),
                ("", (0,0,0)),
                ("ARMY STATUS:", (135, 220, 255)),
                (f"  Dragons in Army: {self.dragons} / 5", (85, 255, 130) if self.dragons >= 5 else (255, 160, 80)),
                ("  Boss Requirement: 5 Dragons", (215, 215, 215)),
                ("", (0,0,0)),
                ("HOW TO REACH THE BOSS:", (135, 220, 255)),
                ("1. If needed, bridge Lava row Y=6:", (215, 215, 215)),
                ("   for x in range(10, 16):", (165, 250, 175)),
                ("       terraform(x, 6, 'B')", (165, 250, 175)),
                ("2. Move straight down column 14:", (215, 215, 215)),
                ("   move_to(14, 9)", (165, 250, 175)),
            ]

        for i, (txt, col) in enumerate(scroll):
            self.canvas.blit(self.font_sm.render(txt, True, col), (sx + 36, scroll_y + 18 + i * 26))

        # Tile Inspector — expanded to 4 lines for readability
        pygame.draw.rect(self.canvas, (42, 47, 64), (sx + 20, 784, SIDEBAR_WIDTH - 40, 140), border_radius=12)
        if 0 <= mx < sx and 0 <= my < MAP_ROWS * TILE_SIZE:
            hc, hr = mx // TILE_SIZE, my // TILE_SIZE
            if 0 <= hc < MAP_COLS and 0 <= hr < MAP_ROWS:
                dx, dy = hc - self.hero_x, hr - self.hero_y
                tcode = self.grid[hr][hc]
                obj = self.get_object_at(hc, hr)
                self.canvas.blit(self.font_md.render(f"Tile ({hc}, {hr}) -- {TERRAIN_NAMES.get(tcode, tcode)}", True, (225, 240, 255)), (sx + 32, 792))
                self.canvas.blit(self.font_sm.render(f"Absolute: move_to({hc}, {hr})", True, (150, 250, 175)), (sx + 32, 822))
                self.canvas.blit(self.font_sm.render(f"Relative: move_by({dx}, {dy})", True, (150, 250, 175)), (sx + 32, 846))
                if obj:
                    self.canvas.blit(self.font_sm.render(f"* {obj['Name']}: {obj['Description']}", True, (255, 225, 95)), (sx + 32, 870))
            else:
                self.canvas.blit(self.font_md.render("Hover mouse over any tile on the map!", True, (180, 195, 215)), (sx + 32, 825))
        else:
            self.canvas.blit(self.font_md.render("Hover mouse over any tile on the map!", True, (180, 195, 215)), (sx + 32, 825))

        # 8. Bottom Control Bar
        by = MAP_ROWS * TILE_SIZE
        pygame.draw.rect(self.canvas, (26, 29, 38), (0, by, sx, BOTTOM_BAR_HEIGHT))
        pygame.draw.line(self.canvas, (95, 105, 135), (0, by), (sx, by), 3)

        self.canvas.blit(self.font_lg.render(self.status_msg, True, self.status_color), (26, by + 18))

        self.btn_preview = pygame.Rect(26, by + 72, 270, 64)
        self.btn_commit = pygame.Rect(316, by + 72, 290, 64)
        self.btn_grid = pygame.Rect(626, by + 72, 250, 64)
        self.btn_reset = pygame.Rect(896, by + 72, 220, 64)

        pygame.draw.rect(self.canvas, (55, 130, 205), self.btn_preview, border_radius=10)
        can_commit = self.preview_data and self.preview_data["valid"]
        pygame.draw.rect(self.canvas, (45, 175, 90) if can_commit else (75, 80, 92), self.btn_commit, border_radius=10)
        pygame.draw.rect(self.canvas, (100, 88, 155), self.btn_grid, border_radius=10)
        pygame.draw.rect(self.canvas, (175, 68, 68), self.btn_reset, border_radius=10)

        self.canvas.blit(self.font_md.render("Preview (Ctrl+S)", True, (255, 255, 255)), (self.btn_preview.x + 28, self.btn_preview.y + 16))
        self.canvas.blit(self.font_md.render("COMMIT TURN", True, (255, 255, 255)), (self.btn_commit.x + 48, self.btn_commit.y + 16))
        self.canvas.blit(self.font_md.render("Toggle Grid", True, (255, 255, 255)), (self.btn_grid.x + 42, self.btn_grid.y + 16))
        self.canvas.blit(self.font_md.render("Reset Map", True, (255, 255, 255)), (self.btn_reset.x + 36, self.btn_reset.y + 16))

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
        while running:
            self.tick += 1
            # Auto-reload when my_hero.py is saved in Thonny!
            my_hero_file = os.path.join(PROJECT_DIR, "my_hero.py")
            if os.path.exists(my_hero_file):
                mtime = os.path.getmtime(my_hero_file)
                if mtime != self.last_mtime:
                    self.last_mtime = mtime
                    self.run_preview()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
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
                    elif event.key == pygame.K_r:
                        self.reset_game(clear_save=True)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.commit_turn()
                    elif event.key == pygame.K_g:
                        self.show_grid = not self.show_grid
                    elif event.key == pygame.K_p:
                        self.run_preview()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    vpos = self.window_to_virtual(event.pos)
                    if self.btn_preview.collidepoint(vpos):
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
