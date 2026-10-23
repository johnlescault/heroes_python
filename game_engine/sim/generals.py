"""
Built-in AI generals. They use EXACTLY the same battle API as your code
(battle_turn(me, battle) -> action), so you can read them and learn!

    Squire  - charges the nearest enemy.
    Knight  - shooters shoot the weakest enemy, fighters hunt enemy shooters.
    Warlord - focuses fire on whatever it can finish off, protects its archers.
"""
from .battle import attack, shoot, defend, wait


def squire(me, battle):
    target = battle.nearest(me)
    if battle.can_shoot(me):
        return shoot(target)
    return attack(target)


def knight(me, battle):
    if battle.can_shoot(me):
        return shoot(battle.weakest())
    shooters = [e for e in battle.enemies if e.is_shooter]
    if shooters:
        return attack(battle.nearest(me, shooters))
    return attack(battle.nearest(me))


def expected_damage(attacker, target):
    avg = (attacker.dmg_min + attacker.dmg_max) / 2 * attacker.count
    diff = attacker.attack - target.defense
    if diff > 0:
        avg *= 1 + 0.05 * diff
    else:
        avg *= 1 - 0.025 * min(-diff, 28)
    return avg


def warlord(me, battle):
    enemies = battle.enemies
    # 1. Can we finish someone off? Pick the most valuable stack we can kill.
    killable = [e for e in enemies if expected_damage(me, e) >= e.hp]
    if battle.can_shoot(me):
        if killable:
            return shoot(max(killable, key=lambda e: e.attack * e.count))
        return shoot(max(enemies, key=lambda e: expected_damage(me, e) / max(1, e.hp)))
    if me.is_shooter and battle.adjacent_enemies(me):
        return attack(battle.weakest(battle.adjacent_enemies(me)))
    # 2. Slow fighters wait on round 1 so the enemy walks into them.
    if battle.round == 1 and me.speed <= 4 and not me.is_flying:
        return wait()
    if killable:
        return attack(min(killable, key=lambda e: battle.distance(me, e)))
    shooters = [e for e in enemies if e.is_shooter]
    if shooters and (me.is_flying or me.speed >= 6):
        return attack(battle.nearest(me, shooters))
    target = battle.nearest(me)
    if battle.round <= 2 and battle.distance(me, target) > me.speed + 1 and me.speed <= 4:
        return defend()
    return attack(target)


GENERALS = {"squire": squire, "knight": knight, "warlord": warlord}
