"""Placeholder art, drawn in code.

Every function here returns an RGBA sprite with the same geometry contract the
real PNGs will have, so swapping in generated art is a file drop and nothing
else:

  bug     - square canvas, bug centred, roughly 80% of the frame
  swatter - square canvas, centred on the PADDLE (the handle runs off toward
            the lower-right corner), because the paddle is what tracks the hand
  splat   - square canvas, blob centred

Sprites are built once at startup and cached, including the leg-animation
phases, so the game loop only ever composites.
"""

import cv2
import numpy as np

from blit import new_layer

# BGRA palettes per bug tier: shell, rim light, shadow, circuit trace.
TIERS = {
    "green": dict(shell=(66, 145, 63), rim=(120, 215, 140), shade=(38, 88, 36),
                  trace=(210, 220, 90), outline=(24, 42, 22)),
    "amber": dict(shell=(18, 122, 179), rim=(70, 195, 235), shade=(10, 70, 105),
                  trace=(130, 235, 250), outline=(12, 45, 66)),
    "red":   dict(shell=(43, 59, 190), rim=(70, 120, 240), shade=(28, 34, 110),
                  trace=(200, 70, 230), outline=(22, 26, 70)),
}

LEG_PHASES = 8          # how many cached leg positions make the crawl cycle
SPRITE = 200            # canvas size for a bug sprite


def _ellipse(img, centre, axes, colour, thickness=-1, angle=0):
    cv2.ellipse(img, centre, axes, angle, 0, 360, colour, thickness, cv2.LINE_AA)


def bug(tier, phase):
    """One bug frame. `phase` is 0..LEG_PHASES-1 and drives the leg wiggle."""
    p = TIERS[tier]
    img = new_layer((SPRITE, SPRITE))
    cx, cy = SPRITE // 2, SPRITE // 2 + 6
    t = phase / LEG_PHASES * 2 * np.pi

    body_w, body_h = 52, 64

    # --- legs: three a side, alternating tripod gait -------------------------
    for i, ly in enumerate((-30, -2, 26)):
        swing = np.sin(t + i * 2.1) * 9
        for side in (-1, 1):
            hip = (cx + side * (body_w - 12), cy + ly)
            knee = (int(hip[0] + side * 26), int(hip[1] + ly * 0.35 + swing))
            foot = (int(knee[0] + side * 20), int(knee[1] + 16 + swing * 0.5))
            cv2.line(img, hip, knee, p["outline"] + (255,), 9, cv2.LINE_AA)
            cv2.line(img, knee, foot, p["outline"] + (255,), 7, cv2.LINE_AA)
            cv2.line(img, hip, knee, p["shade"] + (255,), 5, cv2.LINE_AA)
            cv2.line(img, knee, foot, p["shade"] + (255,), 4, cv2.LINE_AA)

    # --- antennae ------------------------------------------------------------
    for side in (-1, 1):
        base = (cx + side * 16, cy - body_h + 8)
        tip = (int(base[0] + side * (26 + np.sin(t * 1.5) * 4)), base[1] - 34)
        cv2.line(img, base, tip, p["outline"] + (255,), 7, cv2.LINE_AA)
        cv2.line(img, base, tip, p["shade"] + (255,), 3, cv2.LINE_AA)
        cv2.circle(img, tip, 5, p["rim"] + (255,), -1, cv2.LINE_AA)

    # --- shell ---------------------------------------------------------------
    _ellipse(img, (cx, cy), (body_w + 4, body_h + 4), p["outline"] + (255,))
    _ellipse(img, (cx, cy), (body_w, body_h), p["shell"] + (255,))
    # shadow along the lower edge
    cv2.ellipse(img, (cx, cy), (body_w, body_h), 0, 25, 155,
                p["shade"] + (255,), 14, cv2.LINE_AA)
    # rim light along the upper edge
    cv2.ellipse(img, (cx, cy), (body_w - 5, body_h - 5), 0, 200, 340,
                p["rim"] + (255,), 6, cv2.LINE_AA)
    # wing split
    cv2.line(img, (cx, cy - 22), (cx, cy + body_h - 8),
             p["outline"] + (255,), 4, cv2.LINE_AA)

    # --- circuit traces on the carapace --------------------------------------
    for side in (-1, 1):
        pts = np.array([[cx + side * 10, cy + 4], [cx + side * 10, cy + 24],
                        [cx + side * 30, cy + 24], [cx + side * 30, cy + 44]], np.int32)
        cv2.polylines(img, [pts], False, p["trace"] + (255,), 3, cv2.LINE_AA)
        cv2.circle(img, (cx + side * 30, cy + 44), 4, p["trace"] + (255,), -1, cv2.LINE_AA)

    # --- head ----------------------------------------------------------------
    hy = cy - body_h - 4
    cv2.circle(img, (cx, hy), 30, p["outline"] + (255,), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, hy), 26, p["shell"] + (255,), -1, cv2.LINE_AA)
    cv2.ellipse(img, (cx, hy), (22, 22), 0, 200, 340, p["rim"] + (255,), 5, cv2.LINE_AA)

    # --- eyes: the tier's expression -----------------------------------------
    white = (255, 255, 255, 255)
    black = (20, 20, 20, 255)
    for side in (-1, 1):
        ex, ey = cx + side * 12, hy - 2
        cv2.circle(img, (ex, ey), 9, white, -1, cv2.LINE_AA)
        cv2.circle(img, (ex, ey), 9, black, 2, cv2.LINE_AA)
        if tier == "green":
            cv2.circle(img, (ex, ey), 4, black, -1, cv2.LINE_AA)
        elif tier == "amber":
            # wary: half-lidded
            cv2.circle(img, (ex, ey + 2), 4, black, -1, cv2.LINE_AA)
            cv2.rectangle(img, (ex - 10, ey - 10), (ex + 10, ey - 3), p["shell"] + (255,), -1)
            cv2.line(img, (ex - 10, ey - 3), (ex + 10, ey - 3), black, 2, cv2.LINE_AA)
        else:
            # angry: narrowed pupil under a slanted brow
            cv2.ellipse(img, (ex, ey + 1), (3, 6), 0, 0, 360, black, -1, cv2.LINE_AA)
            cv2.line(img, (ex - side * 11, ey - 11), (ex + side * 9, ey - 4),
                     black, 4, cv2.LINE_AA)

    if tier == "red":
        # hazard spikes so it reads as dangerous even in peripheral vision
        for a in (150, 120, 60, 30):        # lower half, clear of the head
            r = np.deg2rad(a)
            base = (int(cx + np.cos(r) * body_w), int(cy + np.sin(r) * body_h))
            tip = (int(cx + np.cos(r) * (body_w + 20)), int(cy + np.sin(r) * (body_h + 20)))
            cv2.line(img, base, tip, p["outline"] + (255,), 9, cv2.LINE_AA)
            cv2.line(img, base, tip, p["rim"] + (255,), 4, cv2.LINE_AA)

    return img


def bug_spawn(tier):
    """Glitch-in frame: the idle sprite sliced and channel-split."""
    src = bug(tier, 0)
    img = np.zeros_like(src)
    bands = 5
    h = src.shape[0] // bands
    rng = np.random.default_rng(7)
    for i in range(bands):
        y0, y1 = i * h, (i + 1) * h if i < bands - 1 else src.shape[0]
        shift = int(rng.integers(-26, 27))
        band = np.roll(src[y0:y1], shift, axis=1)
        if i % 2:                       # cut gaps through alternating bands
            band[: max(1, (y1 - y0) // 4)] = 0
        img[y0:y1] = band
    # cheap chromatic fringe
    img[:, :, 0] = np.roll(img[:, :, 0], 4, axis=1)
    img[:, :, 2] = np.roll(img[:, :, 2], -4, axis=1)
    return img


def splat(tier, variant):
    """Goo decal left behind by a swatted bug."""
    p = TIERS[tier]
    size = 170
    img = new_layer((size, size))
    c = size // 2
    rng = np.random.default_rng(variant * 31 + 5)

    pts = []
    for i in range(22):
        a = i / 22 * 2 * np.pi
        r = 34 + rng.uniform(-8, 26) * (1.0 if i % 3 else 1.6)
        pts.append([c + np.cos(a) * r, c + np.sin(a) * r])
    poly = np.array(pts, np.int32)

    cv2.fillPoly(img, [poly], p["outline"] + (255,), cv2.LINE_AA)
    inner = ((poly - c) * 0.86 + c).astype(np.int32)
    cv2.fillPoly(img, [inner], p["shell"] + (255,), cv2.LINE_AA)
    cv2.ellipse(img, (c - 10, c - 12), (14, 9), -25, 0, 360, p["rim"] + (255,), -1, cv2.LINE_AA)

    for _ in range(8):                  # satellite droplets
        a, d = rng.uniform(0, 2 * np.pi), rng.uniform(46, 78)
        dp = (int(c + np.cos(a) * d), int(c + np.sin(a) * d))
        r = int(rng.integers(3, 8))
        cv2.circle(img, dp, r + 2, p["outline"] + (255,), -1, cv2.LINE_AA)
        cv2.circle(img, dp, r, p["shell"] + (255,), -1, cv2.LINE_AA)
    return img


def swatter(impact=False):
    """Flyswatter, canvas centred on the paddle, handle toward lower-right."""
    size = 300
    img = new_layer((size, size))
    c = size // 2
    red = (48, 48, 205, 255)
    red_dark = (28, 28, 130, 255)
    outline = (25, 25, 35, 255)
    mesh = (215, 220, 220, 190)

    # handle: paddle centre out to the lower-right corner
    cv2.line(img, (c + 30, c + 30), (size - 18, size - 18), outline, 20, cv2.LINE_AA)
    cv2.line(img, (c + 30, c + 30), (size - 18, size - 18), red, 13, cv2.LINE_AA)
    cv2.circle(img, (size - 18, size - 18), 13, outline, -1, cv2.LINE_AA)
    cv2.circle(img, (size - 18, size - 18), 9, red_dark, -1, cv2.LINE_AA)
    cv2.circle(img, (size - 18, size - 18), 4, (0, 0, 0, 0), -1)

    half = 62 if not impact else 70
    r = 22

    def rounded(colour, pad, thick):
        h = half + pad
        cv2.rectangle(img, (c - h + r, c - h), (c + h - r, c + h), colour, thick, cv2.LINE_AA)
        cv2.rectangle(img, (c - h, c - h + r), (c + h, c + h - r), colour, thick, cv2.LINE_AA)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cv2.circle(img, (c + sx * (h - r), c + sy * (h - r)), r, colour, thick, cv2.LINE_AA)

    rounded(outline, 6, -1)
    rounded(mesh, 0, -1)
    rounded(red, 6, 9)

    # perforations
    step = 15
    for gy in range(c - half + 8, c + half - 6, step):
        for gx in range(c - half + 8, c + half - 6, step):
            if abs(gx - c) < half - 12 and abs(gy - c) < half - 12:
                cv2.circle(img, (gx, gy), 4, (0, 0, 0, 0), -1, cv2.LINE_AA)

    if impact:
        for a in (200, 235, 270, 305, 340):
            rad = np.deg2rad(a)
            p0 = (int(c + np.cos(rad) * (half + 14)), int(c + np.sin(rad) * (half + 14)))
            p1 = (int(c + np.cos(rad) * (half + 40)), int(c + np.sin(rad) * (half + 40)))
            cv2.line(img, p0, p1, (255, 255, 255, 230), 6, cv2.LINE_AA)
    return img


def build_cache():
    """Every placeholder sprite the game can ask for, drawn once."""
    cache = {}
    for tier in TIERS:
        cache[("bug", tier)] = [bug(tier, i) for i in range(LEG_PHASES)]
        cache[("spawn", tier)] = bug_spawn(tier)
        cache[("splat", tier)] = [splat(tier, v) for v in range(3)]
    cache["swatter"] = swatter(False)
    cache["swatter_impact"] = swatter(True)
    return cache
