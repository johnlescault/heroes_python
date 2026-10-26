import math
import numpy as np
import pygame


class RetroSoundFX:
    # Procedural sound synthesizer using numpy + pygame.sndarray (no .wav files needed)
    def __init__(self):
        self.enabled = True
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._build_sounds()
        except Exception:
            self.enabled = False

    def _tone(self, freqs, durations, wave="sine", volume=0.22):
        sr = 22050
        chunks = []
        for freq, dur in zip(freqs, durations):
            n = int(sr * dur)
            if n <= 0:
                continue
            t = np.linspace(0, dur, n, endpoint=False)
            if freq <= 0:
                sig = np.zeros(n)
            elif wave == "square":
                sig = np.sign(np.sin(2 * np.pi * freq * t))
            elif wave == "saw":
                sig = 2.0 * (t * freq - np.floor(0.5 + t * freq))
            else:
                sig = np.sin(2 * np.pi * freq * t)
            # Smooth attack/decay envelope
            env = np.ones(n)
            fade = min(n // 4, 400)
            if fade > 0:
                env[:fade] = np.linspace(0.0, 1.0, fade)
                env[-fade:] = np.linspace(1.0, 0.0, fade)
            chunks.append(sig * env * volume)
        if not chunks:
            return None
        mono = (np.concatenate(chunks) * 32767).astype(np.int16)
        stereo = np.column_stack([mono, mono])
        return pygame.sndarray.make_sound(stereo)

    def _build_sounds(self):
        self.sounds["coin"] = self._tone([987.7, 1318.5], [0.07, 0.14], "sine", 0.22)
        self.sounds["step"] = self._tone([220.0, 277.2], [0.04, 0.05], "sine", 0.15)
        self.sounds["magic"] = self._tone([523.3, 659.3, 784.0, 1046.5], [0.06, 0.06, 0.06, 0.14], "sine", 0.20)
        self.sounds["sword"] = self._tone([180.0, 110.0], [0.06, 0.09], "saw", 0.22)
        self.sounds["arrow"] = self._tone([880.0, 660.0], [0.04, 0.06], "sine", 0.18)
        self.sounds["fizzle"] = self._tone([311.1, 233.1, 164.8], [0.08, 0.08, 0.14], "square", 0.16)
        self.sounds["fanfare"] = self._tone([523.3, 659.3, 784.0, 1046.5, 1318.5], [0.09, 0.09, 0.09, 0.12, 0.25], "square", 0.18)

    def play(self, name: str):
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass


def friendly_python_error(exc: Exception) -> str:
    # Kid-friendly translation of Python errors into wizard advice
    kind = type(exc).__name__
    msg = str(exc)
    if isinstance(exc, IndentationError):
        return "⚡ Indentation Error: Lines inside for / if / while / def must start with 4 spaces!"
    if isinstance(exc, SyntaxError):
        if "expected ':'" in msg:
            return "⚡ Missing Colon (:): Lines starting with for, if, else, while, or def must end with ':'!"
        if "unterminated string" in msg:
            return "⚡ Missing Quote: A text string is missing its closing quote mark!"
        if "never closed" in msg or "unmatched" in msg:
            return "⚡ Unclosed Bracket: Every opening ( or [ needs a matching closing ) or ]!"
        return f"⚡ Syntax Error: Check for a missing comma, colon (:), or quote! ({msg})"
    if isinstance(exc, NameError):
        word = msg.split("'")[1] if "'" in msg else msg
        return f"⚡ Unknown Word '{word}': Check your spelling! (Text words need quotes like '{word}')"
    if isinstance(exc, TypeError):
        if "str" in msg and ("int" in msg or "float" in msg):
            return "⚡ Type Mix-Up: You mixed text and numbers! Use int('1500') or str(42) to convert."
        return f"⚡ Type Mix-Up: Check the arguments you passed into the spell! ({msg})"
    if isinstance(exc, ValueError):
        return "⚡ Value Error: int() only works on digit text like int('1500'), not words!"
    if isinstance(exc, ZeroDivisionError):
        return "⚡ Division by Zero: Even Archmages cannot divide by 0!"
    return f"⚡ Spell Fizzled ({kind}): {msg}"


# 3-Tier Progressive Self-Teaching Hints for Every Quest in Acts I-VII
# Format: quest_key -> [(tier1_concept, tier2_pattern, tier3_starter_code)]
PROGRESSIVE_HINTS = {
    "act1_q1": (
        "★ HINT 1 (Idea): Walk to the Gold Pile at (4, 9) and Chest at (2, 5) to get 1,500 Gold, then step on the Border Guard at (7, 7)!",
        "➤ HINT 2 (Pattern): Use move_to(x, y) to walk to a tile! Example: move_to(4, 9)",
        "move_to(4, 9)",
    ),
    "act1_q2": (
        "★ HINT 1 (Idea): Water at X=10 blocks you! Use terraform(10, 7, 'B') to build a bridge, and terraform(14, 9, 'G') to turn the Dragon Peak into Grass!",
        "➤ HINT 2 (Pattern): for y in range(6, 10): terraform(10, y, 'B')",
        "terraform(10, 7, 'B')",
    ),
    "act1_q3": (
        "★ HINT 1 (Idea): Bridge the Molten Lava row at Y=4 using a for-loop, then march down to the Black Dragon at (14, 1)!",
        "➤ HINT 2 (Pattern): for x in range(12, 16): terraform(x, 4, 'B')  then  move_to(14, 1)",
        "terraform(14, 4, 'B')",
    ),
    "comments": (
        "★ HINT 1 (Idea): In Python, any line starting with # is a COMMENT. Python ignores it! Type 2 comment lines starting with #.",
        "➤ HINT 2 (Pattern): # silence the curse",
        "# silencing the cursed spell",
    ),
    "output": (
        "★ HINT 1 (Idea): Strings are text inside quotes. Call say() with the tavern password to shout it on the map!",
        "➤ HINT 2 (Pattern): say('For Erathia!')",
        "say('For Erathia!')",
    ),
    "variables": (
        "★ HINT 1 (Idea): Variables store values using =. Call scout('Merchant') to get his (x, y) coordinates and store them!",
        "➤ HINT 2 (Pattern): x, y = scout('Merchant')   then   move_to(x, y)",
        "x, y = scout('Merchant')",
    ),
    "data_types": (
        "★ HINT 1 (Idea): Python has 3 main types here: float (decimal like 3.5), str (text like 'hi'), and bool (True or False).",
        "➤ HINT 2 (Pattern): Call answer_sphinx(3.5), then answer_sphinx('hi'), then answer_sphinx(True)",
        "answer_sphinx(3.5)",
    ),
    "constants": (
        "★ HINT 1 (Idea): Constants are variables written in ALL_CAPS that never change, like COST = 60.",
        "➤ HINT 2 (Pattern): Type COST = 60 and then recruit('Pikeman', 2)",
        "COST = 60",
    ),
    "operators": (
        "★ HINT 1 (Idea): // is integer division (how many you can buy) and % is remainder (leftover gold).",
        "➤ HINT 2 (Pattern): print(gold // 60)",
        "print(gold // 60)",
    ),
    "type_cast": (
        "★ HINT 1 (Idea): read_sign(0, -3) returns text '1500'. Wrap it in int(...) to turn text into a real number!",
        "➤ HINT 2 (Pattern): print(int(read_sign(0, -3)))",
        "print(int(read_sign(0, -3)))",
    ),
    "strings": (
        "★ HINT 1 (Idea): [::-1] reverses any string in Python! 'NOGARD'[::-1] becomes 'DRAGON'.",
        "➤ HINT 2 (Pattern): open_gate('NOGARD'[::-1])",
        "open_gate('NOGARD'[::-1])",
    ),
    "act3_weather": (
        "★ HINT 1 (Idea): Use an if/else statement with today() so your hero checks the weather before moving!",
        "➤ HINT 2 (Pattern): if today() == 'sandstorm': move_to(2, 3) else: move_to(4, 2)",
        "if today() == 'sandstorm': move_to(2, 3)",
    ),
    "act3_look": (
        "★ HINT 1 (Idea): look(x, y) tells you what is on a tile before you step on it! Combine look() with if.",
        "➤ HINT 2 (Pattern): if look(8, 3) == 'Gold': move_to(8, 3)",
        "if look(8, 3) == 'Gold': move_to(8, 3)",
    ),
    "act3_shrine": (
        "★ HINT 1 (Idea): 'and' needs BOTH levers to be True! Set both the red and blue levers to True.",
        "➤ HINT 2 (Pattern): set_lever('red', True)  and  set_lever('blue', True)",
        "set_lever('red', True)",
    ),
    "act3_compound": (
        "★ HINT 1 (Idea): Combine two conditions using 'and' or 'or' inside an if statement!",
        "➤ HINT 2 (Pattern): if gold > 100 and not False: move_to(14, 1)",
        "if gold > 100 and True: print('Ready!')",
    ),
    "act3_battle": (
        "★ HINT 1 (Idea): Walk onto the Arena Master at (15, 0) and Commit Turn to start the Arena fight! Then type attack()!",
        "➤ HINT 2 (Pattern): move_to(15, 0)  (or in battle: attack())",
        "move_to(15, 0)",
    ),
    "act4_lists": (
        "★ HINT 1 (Idea): A Python list uses square brackets [ ]. Put 'Archer' first and 'Pikeman' second!",
        "➤ HINT 2 (Pattern): set_formation(['Archer', 'Pikeman'])",
        "set_formation(['Archer', 'Pikeman'])",
    ),
    "act4_grid": (
        "★ HINT 1 (Idea): get_map() returns a 2D list (a list of rows). Store it in a variable!",
        "➤ HINT 2 (Pattern): world = get_map()",
        "world = get_map()",
    ),
    "act4_for": (
        "★ HINT 1 (Idea): Loop over a list of coordinate pairs using a for-loop!",
        "➤ HINT 2 (Pattern): for x, y in [(4, 2), (6, 2)]: move_to(x, y)",
        "for x, y in [(4, 2), (6, 2)]: move_to(x, y)",
    ),
    "act4_while": (
        "★ HINT 1 (Idea): A while-loop repeats as long as its condition is True! Keep calling dig() until it returns True.",
        "➤ HINT 2 (Pattern): while not dig(): pass",
        "while not dig(): pass",
    ),
    "act4_battle": (
        "★ HINT 1 (Idea): Step onto General Morgan at (12, 6) and Commit Turn! In battle, use shoot() and attack()!",
        "➤ HINT 2 (Pattern): move_to(12, 6)",
        "move_to(12, 6)",
    ),
    "act5_def": (
        "★ HINT 1 (Idea): 'def' creates your own custom spell! Define a function that calls terraform(x, 9, 'B').",
        "➤ HINT 2 (Pattern): def bridge(x): terraform(x, 9, 'B')",
        "def bridge(x): terraform(x, 9, 'B')",
    ),
    "act5_return": (
        "★ HINT 1 (Idea): 'return' sends an answer back from a function! Define a function with return and pass it to test_spell().",
        "➤ HINT 2 (Pattern): def add(a, b): return a + b   then   test_spell(add)",
        "def add(a, b): return a + b",
    ),
    "act5_scope": (
        "★ HINT 1 (Idea): Normal variables vanish at the end of a turn. Store a key in the persistent memory dictionary!",
        "➤ HINT 2 (Pattern): memory['code'] = 42",
        "memory['code'] = 42",
    ),
    "act6_torches": (
        "★ HINT 1 (Idea): Write a recursive function def spread(x): that lights torch (x, 9) and calls spread(x + 1) until x > 4!",
        "➤ HINT 2 (Pattern): def spread(x): if x <= 4: light_torch(x, 9); spread(x + 1)",
        "def spread(x):\n    if x <= 4:\n        light_torch(x, 9)\n        spread(x + 1)\nspread(1)",
    ),
    "act6_hanoi": (
        "★ HINT 1 (Idea): Recursion makes 3 rings easy! Move n-1 rings to helper peg, move ring n to target, then n-1 rings from helper to target!",
        "➤ HINT 2 (Pattern): def hanoi(n, a, c, b): if n > 0: hanoi(n-1, a, b, c); move_ring(a, c); hanoi(n-1, b, c, a)",
        "def hanoi(n, a, c, b):\n    if n > 0:\n        hanoi(n-1, a, b, c)\n        move_ring(a, c)\n        hanoi(n-1, b, c, a)\nhanoi(3, 'A', 'C', 'B')",
    ),
    "act6_hydra": (
        "★ HINT 1 (Idea): Write a recursive function def strikes(n): where n==0 returns 1, else 1 + 2 * strikes(n - 1)!",
        "➤ HINT 2 (Pattern): def strikes(n): return 1 if n == 0 else 1 + 2 * strikes(n - 1)",
        "def strikes(n):\n    if n == 0: return 1\n    return 1 + 2 * strikes(n - 1)\nanswer_hydra(strikes(3))",
    ),
    "act7_binary": (
        "★ HINT 1 (Idea): Light the 8-bit obelisks with '10101101' and convert that binary string to an int for open_vault()!",
        "➤ HINT 2 (Pattern): set_obelisks('10101101')  and  open_vault(int('10101101', 2))",
        "set_obelisks('10101101')",
    ),
    "act7_hex": (
        "★ HINT 1 (Idea): Hex colors start with # followed by 2 hex digits each for Red (FF), Green (88), Blue (00)!",
        "➤ HINT 2 (Pattern): dye_banner('#FF8800')",
        "dye_banner('#FF8800')",
    ),
    "act7_bitwise": (
        "★ HINT 1 (Idea): Bitwise operators (&, |, ^, <<, >>) combine binary bits directly! Use ^ (XOR) or | (OR).",
        "➤ HINT 2 (Pattern): print(173 ^ 163)",
        "print(173 ^ 163)",
    ),
}

SPELLBOOK_PILLS = {
    "act1": [
        ("▶ Video", "__WATCH_VIDEO__"),
        ("move_right(n)", "Walk right n tiles — you type the number!"),
        ("move_down(n)", "Walk down n tiles — you type the number!"),
        ("move_by(dx, dy)", "Move relative by (dx, dy) from your Hero"),
        ("move_to(x, y)", "Walk to exact map coordinate (x, y)"),
        ("terraform(x, y, 'B')", "Turn Water/Lava at (x, y) into Bridge ('B') or Grass ('G')"),
        ("for x in range(a, b):", "Repeat indented spells for each number from a to b-1"),
    ],
    "act2": [
        ("▶ Video", "__WATCH_VIDEO__"),
        ("# comment", "Start a line with # so Python ignores it"),
        ("say('text')", "Shout a text string on the map"),
        ("x, y = scout('Name')", "Store an NPC's (x, y) coordinates in variables"),
        ("answer_sphinx(val)", "Pass a float (3.5), str ('hi'), or bool (True)"),
        ("int(read_sign(x, y))", "Read text from a sign and convert to a whole number"),
        ("open_gate(pw)", "Pass the decoded password string to unlock a gate"),
    ],
    "act3": [
        ("▶ Video", "__WATCH_VIDEO__"),
        ("today()", "Returns today's weather ('clear', 'sandstorm', 'oasis')"),
        ("look(x, y)", "Returns what is on tile (x, y) before you step there"),
        ("if / else:", "Make a decision based on a condition"),
        ("set_lever(color, bool)", "Set 'red', 'blue', or 'green' lever to True/False"),
        ("attack() / defend()", "Arena combat commands — type one per round"),
    ],
    "act4": [
        ("▶ Video", "__WATCH_VIDEO__"),
        ("set_formation([..])", "Pass a list of unit names in order"),
        ("get_map()", "Returns the 2D map grid as a list of rows"),
        ("for x, y in list:", "Loop over a list of (x, y) waypoint tuples"),
        ("while not dig():", "Keep calling dig() in a loop until treasure is found"),
        ("shoot() / attack()", "Multi-stack Arena commands"),
    ],
    "act5": [
        ("▶ Video", "__WATCH_VIDEO__"),
        ("def name(x):", "Define your own custom reusable spell function"),
        ("return value", "Send an answer back from inside your function"),
        ("test_spell(fn)", "Test your custom function at the Trial Tower"),
        ("memory['key'] = val", "Save a value in the persistent memory dictionary"),
    ],
    "act6": [
        ("▶ Video", "__WATCH_VIDEO__"),
        ("light_torch(x, y)", "Light a cavern torch at (x, y)"),
        ("move_ring(src, dst)", "Move top ring between 'A', 'B', and 'C'"),
        ("answer_hydra(n)", "Give total strikes needed to defeat the Hydra"),
    ],
    "act7": [
        ("▶ Video", "__WATCH_VIDEO__"),
        ("set_obelisks('bits')", "Set the 8 obelisks using an 8-bit binary string"),
        ("open_vault(int(b, 2))", "Convert binary string to int and open the vault"),
        ("dye_banner('#HEX')", "Dye banner with a 6-digit hex color string"),
        ("a ^ b  |  a & b", "Bitwise XOR (^), OR (|), AND (&), and shifts (<<)"),
    ],
}

QUEST_VIDEOS = {
    "act1_q1": ("Python For-Loops & Movement (5 min)", "http://www.youtube.com/watch?v=KWgYha0clzw"),
    "act1_q2": ("Learn Python For-Loops in 5 Minutes", "http://www.youtube.com/watch?v=KWgYha0clzw"),
    "act1_q3": ("Learn Python For-Loops in 5 Minutes", "http://www.youtube.com/watch?v=KWgYha0clzw"),
    "comments": ("Variables & Data Types Intro (4 min)", "http://www.youtube.com/watch?v=mQamOwiW3iM"),
    "output": ("Variables & Data Types Intro (4 min)", "http://www.youtube.com/watch?v=mQamOwiW3iM"),
    "variables": ("Variables & Data Types Intro (4 min)", "http://www.youtube.com/watch?v=mQamOwiW3iM"),
    "data_types": ("Python Variables & Types (Bro Code)", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "constants": ("Python Variables & Types (Bro Code)", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "operators": ("Python Variables & Types (Bro Code)", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "type_cast": ("Python Variables & Type Casting", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "strings": ("Python Variables & Strings", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "act3_weather": ("If/Elif/Else Statements in Python (8 min)", "http://www.youtube.com/watch?v=FvMPfrgGeKs"),
    "act3_look": ("If/Elif/Else Statements in Python (8 min)", "http://www.youtube.com/watch?v=FvMPfrgGeKs"),
    "act3_shrine": ("Booleans & Conditionals Visually Explained", "http://www.youtube.com/watch?v=3wkrYGmUqMk"),
    "act3_compound": ("Booleans & Conditionals Visually Explained", "http://www.youtube.com/watch?v=3wkrYGmUqMk"),
    "act3_battle": ("If/Elif/Else Statements in Python (8 min)", "http://www.youtube.com/watch?v=FvMPfrgGeKs"),
    "act4_lists": ("Learn Python For-Loops in 5 Minutes", "http://www.youtube.com/watch?v=KWgYha0clzw"),
    "act4_grid": ("Learn Python For-Loops in 5 Minutes", "http://www.youtube.com/watch?v=KWgYha0clzw"),
    "act4_for": ("Learn Python For-Loops in 5 Minutes", "http://www.youtube.com/watch?v=KWgYha0clzw"),
    "act4_while": ("While Loops in Python Are Easy (7 min)", "http://www.youtube.com/watch?v=rRTjPnVooxE"),
    "act4_battle": ("While Loops in Python Are Easy (7 min)", "http://www.youtube.com/watch?v=rRTjPnVooxE"),
    "act5_def": ("Functions in Python Are Easy (10 min)", "http://www.youtube.com/watch?v=89cGQjB5R4M"),
    "act5_return": ("Functions in Python Are Easy (10 min)", "http://www.youtube.com/watch?v=89cGQjB5R4M"),
    "act5_scope": ("Python Functions & Scope Visually Explained", "http://www.youtube.com/watch?v=KW6qncswzHw"),
    "act6_torches": ("Better Way to Understand Recursion (4 min)", "http://www.youtube.com/watch?v=Q83nN97LVOU"),
    "act6_hanoi": ("Learn Recursion in 5 Minutes!", "http://www.youtube.com/watch?v=ivl5-snqul8"),
    "act6_hydra": ("Learn Recursion in 5 Minutes!", "http://www.youtube.com/watch?v=ivl5-snqul8"),
    "act7_binary": ("Basics of Binary for Kids (Under 3 min)", "http://www.youtube.com/watch?v=2Z03p3yhGmk"),
    "act7_hex": ("Read & Write in Hexadecimal Easy Way (6 min)", "http://www.youtube.com/watch?v=bt4zavZCrLg"),
    "act7_bitwise": ("Binary Numbers for Kids (Socratica)", "http://www.youtube.com/watch?v=hvteVokz7jE"),
}

TIP_VIDEOS = {
    "comments": ("Variables & Data Types Intro (4 min)", "http://www.youtube.com/watch?v=mQamOwiW3iM"),
    "output": ("Variables & Data Types Intro (4 min)", "http://www.youtube.com/watch?v=mQamOwiW3iM"),
    "variables": ("Variables & Data Types Intro (4 min)", "http://www.youtube.com/watch?v=mQamOwiW3iM"),
    "data_types": ("Python Variables & Types (Bro Code)", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "constants": ("Python Variables & Types (Bro Code)", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "operators": ("Python Variables & Types (Bro Code)", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "type_cast": ("Python Variables & Type Casting", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "strings": ("Python Variables & Strings", "http://www.youtube.com/watch?v=LKFrQXaoSMQ"),
    "if_else": ("If/Elif/Else Statements in Python (8 min)", "http://www.youtube.com/watch?v=FvMPfrgGeKs"),
    "look_ahead": ("If/Elif/Else Statements in Python (8 min)", "http://www.youtube.com/watch?v=FvMPfrgGeKs"),
    "boolean": ("Booleans & Conditionals Visually Explained", "http://www.youtube.com/watch?v=3wkrYGmUqMk"),
    "compound_if": ("Booleans & Conditionals Visually Explained", "http://www.youtube.com/watch?v=3wkrYGmUqMk"),
    "battle_intro": ("If/Elif/Else Statements in Python (8 min)", "http://www.youtube.com/watch?v=FvMPfrgGeKs"),
}
