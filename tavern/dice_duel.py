#!/usr/bin/env python3
# ============================================================================
# 🎲 THE ERATHIA TAVERN: DICE OF FORTUNE (tavern/dice_duel.py) 🎲
# ============================================================================
# Run this script in Thonny (Press F5) to practice Python's `input()`,
# `int()` type-casting, `random.randint()`, and `while` loops!
# ============================================================================
import random

def play_tavern_dice():
    print("=" * 60)
    print("★ WELCOME TO THE ERATHIA TAVERN DICE DUEL! ★")
    print("=" * 60)
    hero_name = input("Tavern Keeper: What is your name, young Hero? ").strip() or "Roland"
    gold = 100
    print(f"\nGreetings, Sir {hero_name}! You start with {gold} Gold coins.")
    print("Rules: We each roll two 6-sided dice (2d6). Highest sum wins the wager!")
    print("       Type 0 as your wager anytime to leave the table.\n")

    while gold > 0:
        raw_bet = input(f"[Gold: {gold}] How much gold do you wager? ")
        # input() always returns a string (str), so we convert it with int()!
        if not raw_bet.strip().isdigit():
            print("⚠ Please type a whole number (like 20)!")
            continue

        bet = int(raw_bet)
        if bet == 0:
            break
        if bet > gold:
            print(f"⚠ You only have {gold} gold!")
            continue

        guess_raw = input("Bonus Math Bet! Guess the exact sum of your 2 dice (2-12) for 3x gold, or press Enter to skip: ").strip()

        h1, h2 = random.randint(1, 6), random.randint(1, 6)
        k1, k2 = random.randint(1, 6), random.randint(1, 6)
        hero_sum = h1 + h2
        keeper_sum = k1 + k2

        print(f"  -> {hero_name} rolled [{h1}] + [{h2}] = {hero_sum}")
        print(f"  -> Tavern Keeper rolled [{k1}] + [{k2}] = {keeper_sum}")

        if guess_raw.isdigit() and int(guess_raw) == hero_sum:
            bonus = bet * 2
            gold += bonus
            print(f"  ★ EXACT SUM PREDICTION! +{bonus} Bonus Gold!")

        if hero_sum > keeper_sum:
            gold += bet
            print(f"  ✓ You won the round! (+{bet} Gold)\n")
        elif hero_sum < keeper_sum:
            gold -= bet
            print(f"  ✗ The Tavern Keeper wins this round! (-{bet} Gold)\n")
        else:
            print("  ═ It's a tie! Your wager is returned.\n")

    print("=" * 60)
    print(f"Farewell, {hero_name}! You leave the Tavern with {gold} Gold!")
    print("=" * 60)

if __name__ == "__main__":
    play_tavern_dice()
