# ============================================================================
# ⚔️ HEROES OF PYTHON: MY SPELLBOOK (my_hero.py) ⚔️
# ============================================================================
# HOW TO PLAY:
# 1. Edit the code inside plan_turn() and press Ctrl+S to SAVE.
# 2. Watch the Game Window! Your Hero's green preview path updates live!
# 3. Click [COMMIT TURN] in the Game Window (or press Enter) to execute!
#
# 💰 Gold, Wood, and Dragons are AUTO-COLLECTED when your hero steps on them!
# ============================================================================

from hero_api import (
    move_right, move_left, move_down, move_up,
    move_by, move_to, terraform
)

def plan_turn(gold, wood):
    # ------------------------------------------------------------------------
    # 📜 QUEST 1: THE STARTING VALLEY (3 Ways to Move!)
    # Goal: Collect 1500 Gold and unlock the Border Guard at (7, 3)!
    #
    # 1. DIRECTIONAL STEPS (Relative):
    #    move_right(3), move_down(1), move_left(2), move_up(1)
    #
    # 2. RELATIVE VECTORS (From where your Hero stands right now):
    #    move_by(dx, dy)  --> Example: move_by(3, 1) moves 3 Right, 1 Down
    #
    # 3. ABSOLUTE MAP COORDINATES (Target exact X, Y grid number):
    #    move_to(x, y)    --> Example: move_to(4, 1) walks to tile (4, 1)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # 📜 QUEST 2: THE ARCHMAGE'S LOOP SPELL (Region 2 & 3)
    # Build a Magic Bridge ('B') across Water (X=10) or Lava (Y=6):
    #
    # for x in range(10, 16):
    #     terraform(x, 6, 'B')
    #
    # terraform(14, 1, 'G')   # Turn the mountain at (14, 1) into grass!
    # move_to(14, 1)          # Visit the Green Dragon Cliff to recruit dragons!
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # 📜 QUEST 3: THE FINAL BOSS BATTLE (Lava Sanctuary)
    # Goal: Slay the Black Dragon at (14, 9) with your army of 5 Dragons!
    #
    # Step 1: Step onto the Green Dragon Cliff at (14, 1) to recruit dragons!
    #         (If you are already standing on (14, 1), click [COMMIT TURN]!)
    #
    # Step 2: Bridge the Lava Row (Y=6) with a for-loop:
    #         for x in range(10, 16):
    #             terraform(x, 6, 'B')
    #
    # Step 3: March straight down Column 14 to the Black Dragon Boss!
    #         move_to(14, 9)
    # ------------------------------------------------------------------------

    # Keep your magic bridge across the Lava:


    # Terraformed the mountain to grass:


    # 🐉 READY FOR THE BOSS?

    pass  # Placeholder: replace with your spells (move_right(3), etc.)
