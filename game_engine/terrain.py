import numpy as np
import pygame

LIQUID = ("W", "L")


def _hash(*vals):
    h = 2166136261
    for v in vals:
        h = ((h ^ (int(v) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h


def _to_arr(surf):
    return pygame.surfarray.array3d(surf).astype(np.float32)


def _to_surf(arr):
    return pygame.surfarray.make_surface(np.clip(arr, 0, 255).astype(np.uint8)).convert()


def make_seamless(a):
    w, h = a.shape[:2]
    wx = np.sin(np.pi * (np.arange(w) + 0.5) / w) ** 2
    wy = np.sin(np.pi * (np.arange(h) + 0.5) / h) ** 2
    weight = (wx[:, None] * wy[None, :])[..., None]
    rolled = np.roll(a, (w // 2, h // 2), axis=(0, 1))
    mean = a.mean(axis=(0, 1))
    blended = a * weight + rolled * (1 - weight)
    return mean + (blended - mean) / np.sqrt(weight ** 2 + (1 - weight) ** 2)


def _variants(a):
    out = []
    for t in (a, a.transpose(1, 0, 2)):
        out += [t, t[::-1], t[:, ::-1], t[::-1, ::-1]]
    return out


def _wobble(wx, wy):
    return (np.sin(wx * 0.21 + wy * 0.13) * 1.8
            + np.sin(wx * 0.083 - wy * 0.19 + 1.7) * 2.6
            + np.sin(wx * 0.47 + wy * 0.51) * 0.8)


class TerrainRenderer:
    def __init__(self, tile_size, textures, road_sprite=None):
        self.s = tile_size
        s = tile_size
        self.cache = {}
        self.xs = np.arange(s, dtype=np.float32)[:, None] * np.ones((1, s), dtype=np.float32)
        self.ys = np.arange(s, dtype=np.float32)[None, :] * np.ones((s, 1), dtype=np.float32)

        self.tex = {}
        for code in "GMFWLS":
            seamless = make_seamless(_to_arr(textures[code]))
            if code in "MF":
                shifted = np.roll(seamless, self.s // 2, axis=0)
                self.tex[code] = [seamless, seamless[::-1], shifted, shifted[::-1]]
            else:
                self.tex[code] = _variants(seamless)

        if road_sprite is not None:
            crop = road_sprite.subsurface((50, 50, 128, 128)).copy()
            crop = pygame.transform.smoothscale(crop, (s, s)).convert()
            road_arr = _to_arr(crop)
        else:
            road_arr = _to_arr(textures["R"])
        self.tex["R"] = _variants(make_seamless(road_arr))

    def tile(self, grid, c, r, base_grid=None):
        rows, cols = len(grid), len(grid[0])
        code = grid[r][c]

        def nb(dc, dr):
            cc, rr = c + dc, r + dr
            if 0 <= cc < cols and 0 <= rr < rows:
                return grid[rr][cc]
            return code

        nbs = {"n": nb(0, -1), "e": nb(1, 0), "s": nb(0, 1), "w": nb(-1, 0)}
        under = None
        if code == "B":
            original = base_grid[r][c] if base_grid else None
            under = original if original in LIQUID else self._under(grid, c, r)
        key = (code, c, r, nbs["n"], nbs["e"], nbs["s"], nbs["w"], under)
        surf = self.cache.get(key)
        if surf is None:
            surf = self._build(code, c, r, nbs, under)
            self.cache[key] = surf
        return surf

    @staticmethod
    def _under(grid, c, r):
        rows, cols = len(grid), len(grid[0])
        seen = {(c, r)}
        queue = [(c, r)]
        while queue:
            nxt = []
            for x, y in queue:
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < cols and 0 <= ny < rows) or (nx, ny) in seen:
                        continue
                    t = grid[ny][nx]
                    if t in LIQUID:
                        return t
                    if t == "B":
                        seen.add((nx, ny))
                        nxt.append((nx, ny))
            queue = nxt
        return "W"

    def _build(self, code, c, r, nbs, under=None):
        v = _hash(c, r, 7) % 8
        if code == "R":
            return _to_surf(self._road(c, r, nbs, v))
        if code == "B":
            return self._bridge(c, r, nbs, v, under or "W")
        if code == "W" or code == "L":
            return _to_surf(self._liquid(code, c, r, nbs, v))
        if code in ("M", "F"):
            return _to_surf(self._outcrop(code, c, r, nbs, v))
        if code == "S":
            arr = self.tex["S"][v].copy()
            arr = self._banks(arr, c, r, nbs)
            return _to_surf(arr)
        arr = self.tex["G"][v].copy()
        arr = self._banks(arr, c, r, nbs)
        return _to_surf(arr)

    def _dist(self, side):
        s = self.s
        return {"n": self.ys, "s": (s - 1) - self.ys, "w": self.xs, "e": (s - 1) - self.xs}[side]

    def _gradient(self, arr, side, c, r, width, color, amax, power=1.5):
        s = self.s
        wob = _wobble(c * s + self.xs, r * s + self.ys)
        a = np.clip(1 - (self._dist(side) + wob * 0.8) / width, 0, 1) ** power * amax
        a = a[..., None]
        return arr * (1 - a) + np.array(color, dtype=np.float32) * a

    def _banks(self, arr, c, r, nbs):
        for side, n in nbs.items():
            if n == "W":
                arr = self._gradient(arr, side, c, r, 13, (30, 46, 28), 0.55)
                arr = self._gradient(arr, side, c, r, 5, (118, 98, 64), 0.75, 1.0)
            elif n == "L":
                arr = self._gradient(arr, side, c, r, 14, (40, 22, 16), 0.65)
                arr = self._gradient(arr, side, c, r, 5, (255, 120, 40), 0.55, 1.0)
        return arr

    def _liquid(self, code, c, r, nbs, v, skip_sides=()):
        arr = self.tex[code][v].copy()
        for side, n in nbs.items():
            if n in LIQUID or n == "B" or side in skip_sides:
                continue
            if code == "W":
                arr = self._gradient(arr, side, c, r, 16, (205, 235, 250), 0.40)
                arr = self._gradient(arr, side, c, r, 6, (245, 252, 255), 0.65, 1.0)
            else:
                arr = self._gradient(arr, side, c, r, 15, (30, 12, 10), 0.70)
                arr = self._gradient(arr, side, c, r, 4, (20, 8, 8), 0.55, 1.0)
        return arr

    def _shape_sd(self, open_sides, c, r, inset, rc, wob_amp):
        s = self.s
        sd = np.full((s, s), 1e3, dtype=np.float32)
        for side in open_sides:
            sd = np.minimum(sd, self._dist(side) - inset)

        for a, b, cx, cy in (("w", "n", 0, 0), ("e", "n", s - 1, 0),
                             ("w", "s", 0, s - 1), ("e", "s", s - 1, s - 1)):
            if a in open_sides and b in open_sides:
                px = inset + rc if cx == 0 else (s - 1) - inset - rc
                py = inset + rc if cy == 0 else (s - 1) - inset - rc
                in_corner = ((self.xs < inset + rc) if cx == 0 else (self.xs > (s - 1) - inset - rc)) & \
                            ((self.ys < inset + rc) if cy == 0 else (self.ys > (s - 1) - inset - rc))
                arc = rc - np.hypot(self.xs - px, self.ys - py)
                sd = np.where(in_corner, np.minimum(sd, arc), sd)

        wob = _wobble(c * s + self.xs, r * s + self.ys)
        return sd + wob * wob_amp

    def _road(self, c, r, nbs, v):
        road = self.tex["R"][v]
        grass = self.tex["G"][_hash(c, r, 7) % 8]
        open_sides = {k for k, n in nbs.items() if n not in ("R", "B")}

        if not open_sides:
            return road.copy()

        sd = self._shape_sd(open_sides, c, r, inset=9.0, rc=16.0, wob_amp=0.7)
        feather = 4.0

        rim = np.clip(1 - sd / 9.0, 0, 1)[..., None] ** 1.5
        dirt = np.array((104, 80, 52), dtype=np.float32)
        road_rgb = road * (1 - 0.45 * rim) + dirt * (0.45 * rim)

        alpha = np.clip(sd / feather + 0.5, 0, 1)[..., None]
        shade = np.clip(1 + sd / 10.0, 0, 1)[..., None] * (sd < 0)[..., None]
        grass_rgb = grass * (1 - 0.22 * shade)

        out = grass_rgb * (1 - alpha) + road_rgb * alpha
        return self._banks(out, c, r, nbs)

    def _outcrop(self, code, c, r, nbs, v):
        tex = self.tex[code]
        art = tex[v % len(tex)]
        grass = self.tex["G"][_hash(c, r, 7) % 8]
        open_sides = {k for k, n in nbs.items() if n != code}

        if not open_sides:
            return art.copy()

        sd = self._shape_sd(open_sides, c, r, inset=3.0, rc=24.0, wob_amp=1.3)
        rim_col = np.array((26, 20, 18) if code == "M" else (8, 30, 12), dtype=np.float32)
        rim = np.clip(1 - sd / 8.0, 0, 1)[..., None] ** 1.3
        body = art * (1 - 0.6 * rim) + rim_col * (0.6 * rim)

        alpha = np.clip(sd / 3.0 + 0.5, 0, 1)[..., None]
        shade = np.clip(1 + sd / 14.0, 0, 1)[..., None] * (sd < 0)[..., None]
        grass_rgb = grass * (1 - 0.38 * shade)

        out = grass_rgb * (1 - alpha) + body * alpha
        return self._banks(out, c, r, nbs)

    def _bridge(self, c, r, nbs, v, under="W"):
        def score(a, b):
            total = 0.0
            for n in (nbs[a], nbs[b]):
                if n == "B":
                    total += 2.0
                elif n == "R":
                    total += 2.0
                elif n not in LIQUID and n not in ("M", "F"):
                    total += 1.0
            return total

        horizontal = score("w", "e") >= score("n", "s")
        start_n, end_n = ("w", "e") if horizontal else ("n", "s")
        cap_start = nbs[start_n] != "B"
        cap_end = nbs[end_n] != "B"

        base = self._liquid(under, c, r, nbs, v, skip_sides=(start_n, end_n))
        base_surf = _to_surf(base)

        deck = self._deck(c, r, cap_start, cap_end)
        if horizontal:
            deck = pygame.transform.rotate(deck, 90)
        base_surf.blit(deck, (0, 0))
        return base_surf

    def _deck(self, c, r, cap_start, cap_end):
        s = self.s
        deck = pygame.Surface((s, s), pygame.SRCALPHA)
        x0 = int(s * 0.17)
        x1 = s - x0
        bw = x1 - x0

        for i in range(6):
            pygame.draw.rect(deck, (0, 0, 0, 20),
                             (x0 - 2 - i + 5, 0, bw + 4 + 2 * i, s), border_radius=3)

        palette = [(139, 92, 48), (152, 102, 54), (128, 84, 44), (160, 110, 60), (120, 78, 40)]
        pl = s // 6
        for i in range(6):
            h = _hash(c, r, i, 3)
            base = palette[h % len(palette)]
            j = (h >> 8) % 17 - 8
            col = tuple(max(0, min(255, ch + j)) for ch in base)
            y = i * pl
            pygame.draw.rect(deck, col, (x0, y, bw, pl))
            pygame.draw.line(deck, tuple(min(255, ch + 38) for ch in col), (x0, y), (x1 - 1, y), 1)
            pygame.draw.line(deck, (54, 33, 16), (x0, y + pl - 1), (x1 - 1, y + pl - 1), 1)
            dark = tuple(max(0, ch - 30) for ch in col)
            for g in range(2):
                gh = _hash(c, r, i, g, 11)
                gy = y + 3 + (gh % max(1, pl - 6))
                gx = x0 + 4 + ((gh >> 5) % max(1, bw // 3))
                pygame.draw.line(deck, dark, (gx, gy), (gx + 10 + (gh >> 12) % 18, gy), 1)
            for nx in (x0 + 5, x1 - 6):
                pygame.draw.circle(deck, (46, 36, 32), (nx, y + pl // 2), 2)
                pygame.draw.circle(deck, (190, 178, 150), (nx - 1, y + pl // 2 - 1), 1)

        for rx in (x0 - 3, x1 - 4):
            pygame.draw.rect(deck, (84, 52, 26), (rx, 0, 7, s), border_radius=2)
            pygame.draw.rect(deck, (168, 118, 62), (rx + 1, 0, 2, s))
            pygame.draw.line(deck, (44, 26, 12), (rx + 6, 0), (rx + 6, s), 1)
        for rx in (x0 - 5, x1 - 6):
            pygame.draw.rect(deck, (70, 42, 20), (rx, s // 2 - 6, 11, 12), border_radius=3)
            pygame.draw.rect(deck, (178, 130, 70), (rx + 1, s // 2 - 6, 9, 3), border_radius=2)
            pygame.draw.circle(deck, (214, 168, 84), (rx + 5, s // 2 - 4), 2)

        def cap(y):
            pygame.draw.rect(deck, (62, 38, 18), (x0 - 6, y, bw + 12, 9), border_radius=3)
            pygame.draw.rect(deck, (150, 104, 54), (x0 - 6, y + 1, bw + 12, 3), border_radius=2)
            for nx in (x0 - 2, x1 + 1):
                pygame.draw.circle(deck, (205, 170, 100), (nx, y + 5), 2)

        if cap_start:
            cap(0)
        if cap_end:
            cap(s - 9)
        return deck
