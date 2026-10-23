"""
Static game rules shared by the simulator, the battle engine and the renderer.

Pure Python (no pygame) so it can be imported inside the sandbox subprocess.
"""

# ----------------------------------------------------------------------------
# ADVENTURE MAP TERRAIN
# code -> (display name, MP cost or None if blocked)
# ----------------------------------------------------------------------------
TERRAIN = {
    "R": ("Cobble Road", 0.5),
    "G": ("Emerald Grass", 1.0),
    "B": ("Enchanted Bridge", 1.0),
    "S": ("Desert Sand", 1.5),
    "D": ("Cave Floor", 1.0),
    "M": ("Jagged Peak", None),
    "W": ("Deep River", None),
    "L": ("Molten Lava", None),
    "F": ("Ancient Forest", None),
    "X": ("Cave Rock", None),
}


def terrain_cost(code):
    return TERRAIN.get(code, (code, None))[1]


def terrain_name(code):
    name, cost = TERRAIN.get(code, (code, None))
    return f"{name} ({cost} MP)" if cost is not None else f"{name} (Blocked)"


MAP_COLS = 16
MAP_ROWS = 11

RESOURCES = ("gold", "wood", "ore", "mercury", "sulfur", "crystal", "gems")

# ----------------------------------------------------------------------------
# BATTLE UNITS (simplified, Heroes 3 inspired)
# ----------------------------------------------------------------------------
UNITS = {
    #  name            atk def  dmg      hp  spd  shots fly   cost  extra
    "Pikeman":      dict(attack=4,  defense=5,  dmg=(1, 3),   hp=10,  speed=4,  shots=0,  flying=False, cost=60),
    "Archer":       dict(attack=6,  defense=3,  dmg=(2, 3),   hp=10,  speed=4,  shots=12, flying=False, cost=100),
    "Griffin":      dict(attack=8,  defense=8,  dmg=(3, 6),   hp=25,  speed=6,  shots=0,  flying=True,  cost=200,
                         retaliations=2, cost_extra={"ore": 2}),
    "Swordsman":    dict(attack=10, defense=12, dmg=(6, 9),   hp=35,  speed=5,  shots=0,  flying=False, cost=300),
    "Monk":         dict(attack=12, defense=7,  dmg=(10, 12), hp=30,  speed=5,  shots=12, flying=False, cost=400),
    "Cavalier":     dict(attack=15, defense=15, dmg=(15, 25), hp=100, speed=7,  shots=0,  flying=False, cost=1000),
    "Angel":        dict(attack=20, defense=20, dmg=(50, 50), hp=200, speed=12, shots=0,  flying=True,  cost=3000,
                         cost_extra={"gems": 1}),
    "Green Dragon": dict(attack=18, defense=18, dmg=(40, 50), hp=180, speed=10, shots=0,  flying=True,  cost=4000,
                         cost_extra={"crystal": 1}),
    # --- monsters (not recruitable in towns) ---
    "Troglodyte":   dict(attack=4,  defense=3,  dmg=(1, 3),   hp=5,   speed=4,  shots=0,  flying=False, cost=50),
    "Harpy":        dict(attack=6,  defense=5,  dmg=(1, 4),   hp=14,  speed=6,  shots=0,  flying=True,  cost=130),
    "Gnoll":        dict(attack=3,  defense=5,  dmg=(2, 3),   hp=6,   speed=4,  shots=0,  flying=False, cost=50),
    "Lizardman":    dict(attack=5,  defense=6,  dmg=(2, 3),   hp=14,  speed=4,  shots=12, flying=False, cost=110),
    "Sand Wyrm":    dict(attack=12, defense=10, dmg=(8, 14),  hp=90,  speed=5,  shots=0,  flying=False, cost=900),
    "Minotaur":     dict(attack=14, defense=12, dmg=(12, 20), hp=50,  speed=6,  shots=0,  flying=False, cost=500),
    "Hydra":        dict(attack=16, defense=18, dmg=(25, 45), hp=175, speed=5,  shots=0,  flying=False, cost=2200,
                         hits_all_adjacent=True, no_retaliation_against=True),
    "Skeleton":     dict(attack=5,  defense=4,  dmg=(1, 3),   hp=6,   speed=4,  shots=0,  flying=False, cost=60),
    "Lich":         dict(attack=13, defense=10, dmg=(11, 13), hp=30,  speed=6,  shots=12, flying=False, cost=550),
    "Black Dragon": dict(attack=25, defense=25, dmg=(40, 50), hp=300, speed=15, shots=0,  flying=True,  cost=8000,
                         immune=0b1111),
}

TOWN_UNITS = ("Pikeman", "Archer", "Griffin", "Swordsman", "Monk", "Cavalier", "Angel")

MAX_ARMY_SLOTS = 7

# ----------------------------------------------------------------------------
# MAGIC (Act VII bitmasks)
# ----------------------------------------------------------------------------
AIR, EARTH, FIRE, WATER = 1, 2, 4, 8

SPELLS = {
    # name: school bit, mana cost, effect
    "magic_arrow": dict(school=AIR,   mana=5,  damage=30,  area=False),
    "lightning":   dict(school=AIR,   mana=10, damage=75,  area=False),
    "fireball":    dict(school=FIRE,  mana=15, damage=60,  area=True),
    "ice_bolt":    dict(school=WATER, mana=8,  damage=50,  area=False),
    "stone_skin":  dict(school=EARTH, mana=5,  damage=0,   area=False, buff_defense=6),
}

# Battlefield
BF_COLS = 15
BF_ROWS = 11
