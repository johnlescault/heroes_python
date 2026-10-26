#!/usr/bin/env python3
# ============================================================================
# 🏛️ THE SPHINX'S MATH & BINARY GAUNTLET (tavern/riddle_master.py) 🏛️
# ============================================================================
# Run this script in Thonny (Press F5) to practice `input()`, `int()`,
# integer division `//`, remainder `%`, and binary numbers!
# ============================================================================

RIDDLES = [
    (
        "Riddle 1 (Division //): Pikemen cost 60 gold each. If you have 500 gold, "
        "how many whole Pikemen can you recruit? (500 // 60)",
        500 // 60,
    ),
    (
        "Riddle 2 (Remainder %): After buying those Pikemen for 60 gold each with 500 gold, "
        "how much leftover change do you have? (500 % 60)",
        500 % 60,
    ),
    (
        "Riddle 3 (Recursion Math): A size-0 Hydra takes 1 strike. Each larger Hydra takes "
        "1 + 2 * previous_strikes (size 1 = 3, size 2 = 7, size 3 = 15). How many strikes for size 4?",
        31,
    ),
    (
        "Riddle 4 (Binary): What is the 4-bit binary number 1101 in normal base-10 decimal? "
        "(Hint: 8 + 4 + 0 + 1)",
        13,
    ),
]

def main():
    print("=" * 60)
    print("★ THE SPHINX'S INTERACTIVE RIDDLE GAUNTLET ★")
    print("=" * 60)
    score = 0
    for idx, (question, answer) in enumerate(RIDDLES, 1):
        print(f"\n{question}")
        user_text = input("Your answer: ").strip()
        try:
            user_val = int(user_text)
        except ValueError:
            print(f"  ✗ '{user_text}' is not an integer! The answer was {answer}.")
            continue

        if user_val == answer:
            score += 1
            print("  ✓ Correct! The Sphinx nods in approval.")
        else:
            print(f"  ✗ Not quite! You answered {user_val}, but the answer is {answer}.")

    print("\n" + "=" * 60)
    print(f"You solved {score} / {len(RIDDLES)} Sphinx Riddles!")
    print("=" * 60)

if __name__ == "__main__":
    main()
