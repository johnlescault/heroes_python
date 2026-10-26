# ============================================================================
# ⚔️ HEROES OF PYTHON: HOTSEAT DUEL ARENA (duel_red.py) ⚔️
# ============================================================================
# Type 'duel squire', 'duel knight', 'duel warlord', or 'duel parent'
# in the game console to pit your code against AI Generals or your Parent!
# ============================================================================
from battle_api import attack, shoot, move_toward, defend, wait, cast, AIR, FIRE

def draft(budget, shop):
    # Spend up to 5,000 gold (max 7 slots): Pikeman=60, Archer=100, Griffin=200,
    # Swordsman=300, Monk=400, Cavalier=1000, Angel=3000
    return [
        ('Cavalier', 2),
        ('Monk', 4),
        ('Archer', 10),
        ('Griffin', 2),
    ]

def battle_turn(me, battle):
    target = battle.weakest()
    if battle.can_shoot(me):
        return shoot(target)
    if me.is_shooter and battle.adjacent_enemies(me):
        return defend()
    return attack(target)

def hero_spell(battle):
    if battle.mana >= 15 and battle.enemies:
        return cast('fireball', battle.weakest())
    return None
