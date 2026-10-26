# ============================================================================
# battle_api.py — Helper stubs for duel_red.py (Hotseat & AI Duel Arena)
# ============================================================================
AIR, EARTH, FIRE, WATER = 1, 2, 4, 8

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
    """Act later in this round (after slower stacks move)."""
    return {"type": "wait"}

def cast(spell, target):
    """Cast a hero spell ('magic_arrow', 'lightning', 'fireball', 'ice_bolt', 'stone_skin')."""
    return {"type": "cast", "spell": spell, "target": getattr(target, "id", target)}
