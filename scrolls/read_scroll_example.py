# ============================================================================
# 📜 SEER'S SCROLL READER (scrolls/read_scroll_example.py) 📜
# ============================================================================
# Run this in Thonny to see how Python opens and reads a text file line-by-line!
# ============================================================================
import os

SCROLL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seer_3.txt")

with open(SCROLL_FILE, "r", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split(",")
        if len(parts) == 3:
            x = int(parts[0])
            y = int(parts[1])
            name = parts[2]
            print(f"Seer Scroll Waypoint: {name} is at ({x}, {y})")
