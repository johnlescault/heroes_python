"""
Extract individual tiles and sprites from generated sprite sheets.
Run this once to populate the assets/ folder with clean square tiles and character sprites.
Strips borders from tiles and text labels from sprites.
"""
import os
from PIL import Image, ImageFilter
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

BRAIN_DIR = os.path.expanduser(
    "~/.gemini/antigravity-ide/brain/8d828419-8a49-4f2b-af7d-45ab90a5ac4e"
)

def find_file(prefix):
    """Find the latest file in the brain directory by prefix."""
    matches = []
    for f in sorted(os.listdir(BRAIN_DIR)):
        if f.startswith(prefix) and (f.endswith(".jpg") or f.endswith(".png")):
            matches.append(os.path.join(BRAIN_DIR, f))
    return matches[-1] if matches else None


def remove_dark_bg(img, threshold=35):
    """Make near-black pixels transparent."""
    arr = np.array(img.convert("RGBA"))
    total = arr[:, :, 0].astype(int) + arr[:, :, 1].astype(int) + arr[:, :, 2].astype(int)
    is_dark = total < (threshold * 3)
    arr[is_dark, 3] = 0
    return Image.fromarray(arr)


def trim_to_content(img):
    """Trim transparent/empty space around the image content."""
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img


# ============================================================================
# 1. TERRAIN TILES — heavy crop to eliminate ALL border artifacts
# ============================================================================
terrain_file = find_file("terrain_tiles")

if terrain_file:
    print(f"Loading terrain tiles from: {terrain_file}")
    img = Image.open(terrain_file).convert("RGB")
    w, h = img.size
    tw = w // 4
    th = h // 3

    tiles_map = {
        (0, 0): "grass.png",
        (1, 0): "road.png",
        (2, 0): "mountain.png",
        (3, 0): "forest.png",
        (0, 1): "water.png",
        (1, 1): "lava.png",
        (2, 1): "bridge.png",
    }

    for (col, row), fname in tiles_map.items():
        x1 = col * tw
        y1 = row * th
        x2 = x1 + tw
        y2 = y1 + th
        tile = img.crop((x1, y1, x2, y2))

        # Crop 12% off each edge — aggressive enough to kill all border frames
        bx = int(tile.width * 0.12)
        by = int(tile.height * 0.12)
        tile = tile.crop((bx, by, tile.width - bx, tile.height - by))

        # Make it perfectly square
        side = min(tile.width, tile.height)
        cx = (tile.width - side) // 2
        cy = (tile.height - side) // 2
        tile = tile.crop((cx, cy, cx + side, cy + side))

        # Save as RGB (no alpha needed for terrain tiles - they fill the whole cell)
        out_path = os.path.join(ASSETS_DIR, fname)
        tile.save(out_path)
        print(f"  [OK] {fname} ({tile.size[0]}x{tile.size[1]})")
else:
    print("[WARN] Could not find terrain_tiles image")


# ============================================================================
# 2. CHARACTER/OBJECT SPRITES — clean black background removal
# ============================================================================
sprites_file = find_file("sprites_clean")

if sprites_file:
    print(f"\nLoading character sprites from: {sprites_file}")
    img = Image.open(sprites_file).convert("RGBA")
    w, h = img.size
    sw = w // 4
    sh = h // 3

    sprites_map = {
        (0, 0): "hero.png",
        (1, 0): "gold_pile.png",
        (2, 0): "chest.png",
        (3, 0): "guard.png",
        (0, 1): "mage.png",
        (1, 1): "dragon_green.png",
        (2, 1): "monster.png",
        (3, 1): "dragon_black.png",
    }

    for (col, row), fname in sprites_map.items():
        x1 = col * sw
        y1 = row * sh
        x2 = x1 + sw
        y2 = y1 + sh
        sprite = img.crop((x1, y1, x2, y2))

        # Remove dark/black background
        sprite = remove_dark_bg(sprite, threshold=30)
        sprite = trim_to_content(sprite)

        out_path = os.path.join(ASSETS_DIR, fname)
        sprite.save(out_path)
        print(f"  [OK] {fname} ({sprite.size[0]}x{sprite.size[1]})")
else:
    print("[WARN] Could not find sprites_clean image")


# ============================================================================
# 3. MINE/SAWMILL SPRITE
# ============================================================================
mine_file = find_file("mine_sprite")

if mine_file:
    print(f"\nLoading mine sprite from: {mine_file}")
    img = Image.open(mine_file).convert("RGBA")
    img = remove_dark_bg(img, threshold=30)
    img = trim_to_content(img)

    out_path = os.path.join(ASSETS_DIR, "mine.png")
    img.save(out_path)
    print(f"  [OK] mine.png ({img.size[0]}x{img.size[1]})")
else:
    print("[WARN] Could not find mine_sprite image")

print("\n✅ Asset extraction complete!")
