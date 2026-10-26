# ============================================================================
# 🤫 SECRET PARENT DUEL STRATEGY (game_engine/.duels/parent_blue.py)
# ============================================================================
# Your child runs `duel parent` in the game console to fight this script!
# ============================================================================
from battle_api import attack, shoot, defend, wait, cast

def draft(budget, shop):
    return [
        ('Angel', 1),
        ('Swordsman', 3),
        ('Monk', 2),
        ('Pikeman', 5),
    ]

def battle_turn(me, battle):
    shooters = [e for e in battle.enemies if e.is_shooter]
    if battle.can_shoot(me):
        target = battle.weakest(shooters) if shooters else battle.weakest()
        return shoot(target)
    if shooters and (me.is_flying or me.speed >= 6):
        return attack(battle.nearest(me, shooters))
    return attack(battle.nearest(me))

def hero_spell(battle):
    if battle.mana >= 10 and battle.enemies:
        return cast('lightning', battle.weakest())
    return None
