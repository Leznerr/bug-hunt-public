"""The art swap layer.

The game calls draw_bug / draw_swatter / draw_splat and never learns whether it
got a generated PNG or the placeholder drawn in procedural.py. Drop a file with
the right name into assets/ and it takes over on the next launch.

Expected files (all PNG-32 with real alpha, square canvas):

  bug_green.png  bug_amber.png  bug_red.png        bug centred, ~80% of canvas
  bug_green_spawn.png  bug_amber_spawn.png  bug_red_spawn.png
  splat_green_1..3.png  (or splat_1..3.png for a shared set)
  swatter.png  swatter_impact.png                  centred ON THE PADDLE
  bezel.png                                        16:9, centre fully transparent
  badge_cleared.png

The swatter canvas must be centred on the paddle, not on the whole object - the
paddle is what tracks the hand, so that point is the sprite's anchor.
"""

import pathlib

import cv2
import numpy as np

import procedural
from blit import blit_rgba

CONTENT_RATIO = 0.80        # how much of a sprite canvas the artwork fills


class Art:
    def __init__(self, asset_dir="assets"):
        self.dir = pathlib.Path(__file__).parent / asset_dir
        self.png = {}
        self.cache = procedural.build_cache()
        self.loaded = []
        self._load()

    # -- loading -------------------------------------------------------------
    def _read(self, name):
        path = self.dir / f"{name}.png"
        if not path.exists():
            return None
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"[art] could not decode {path.name}, using placeholder")
            return None
        if img.shape[2] == 3:
            print(f"[art] {path.name} has no alpha channel - key it first, skipping")
            return None
        self.loaded.append(path.name)
        return img

    def _load(self):
        for tier in ("green", "amber", "red"):
            self.png[("bug", tier)] = self._read(f"bug_{tier}")
            self.png[("spawn", tier)] = self._read(f"bug_{tier}_spawn")
            variants = []
            for n in (1, 2, 3):
                v = self._read(f"splat_{tier}_{n}")
                if v is None:
                    v = self._read(f"splat_{n}")
                variants.append(v)
            self.png[("splat", tier)] = [v for v in variants if v is not None] or None
        self.png["swatter"] = self._read("swatter")
        self.png["swatter_impact"] = self._read("swatter_impact")
        self.png["bezel"] = self._read("bezel")
        self.png["badge_cleared"] = self._read("badge_cleared")

    @property
    def using_placeholders(self):
        return not self.loaded

    def report(self):
        if self.loaded:
            return f"{len(self.loaded)} generated asset(s) loaded: " + ", ".join(sorted(self.loaded))
        return "no assets found in assets/ - running on placeholder art"

    # -- drawing -------------------------------------------------------------
    @staticmethod
    def _scale_for(sprite, radius):
        """Scale factor that renders `sprite` at the requested on-screen radius."""
        return (2.0 * radius) / (CONTENT_RATIO * sprite.shape[1])

    def draw_bug(self, frame, x, y, radius, tier, phase, spawning=0.0, alpha=1.0, angle=0.0):
        """spawning: 1.0 at the instant it appears, falling to 0.0 once settled."""
        if spawning > 0.0:
            sprite = self.png[("spawn", tier)]
            if sprite is None:
                sprite = self.cache[("spawn", tier)]
        else:
            sheet = self.png[("bug", tier)]
            if sheet is not None:
                sprite = sheet                      # a real PNG is one frame
            else:
                frames = self.cache[("bug", tier)]
                sprite = frames[int(phase) % len(frames)]
        blit_rgba(frame, sprite, x, y, self._scale_for(sprite, radius), angle, alpha)

    def draw_swatter(self, frame, x, y, radius, angle=0.0, impact=False):
        key = "swatter_impact" if impact else "swatter"
        sprite = self.png[key]
        if sprite is None:
            sprite = self.cache[key]
        blit_rgba(frame, sprite, x, y, self._scale_for(sprite, radius), angle)

    def draw_splat(self, frame, x, y, radius, tier, variant, alpha=1.0):
        pool = self.png[("splat", tier)]
        if pool is None:
            pool = self.cache[("splat", tier)]
        sprite = pool[variant % len(pool)]
        blit_rgba(frame, sprite, x, y, self._scale_for(sprite, radius), 0.0, alpha)

    def draw_bezel(self, frame, accent):
        """Full-frame CRT surround. Procedural fallback is corner brackets."""
        sprite = self.png["bezel"]
        h, w = frame.shape[:2]
        if sprite is not None:
            resized = cv2.resize(sprite, (w, h), interpolation=cv2.INTER_LINEAR)
            blit_rgba(frame, resized, w // 2, h // 2, 1.0, 0.0, 1.0)
            return
        m, L = 14, 46
        for (px, py, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1),
                                 (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            cv2.line(frame, (px, py), (px + sx * L, py), accent, 3, cv2.LINE_AA)
            cv2.line(frame, (px, py), (px, py + sy * L), accent, 3, cv2.LINE_AA)

    def draw_badge(self, frame, x, y, radius, accent):
        sprite = self.png["badge_cleared"]
        if sprite is not None:
            blit_rgba(frame, sprite, x, y, (2.0 * radius) / (CONTENT_RATIO * sprite.shape[1]))
            return
        cv2.circle(frame, (x, y), radius, (30, 34, 30), -1, cv2.LINE_AA)
        cv2.circle(frame, (x, y), radius, accent, 6, cv2.LINE_AA)
        for a in range(0, 360, 45):
            r = np.deg2rad(a)
            cv2.line(frame,
                     (int(x + np.cos(r) * (radius + 8)), int(y + np.sin(r) * (radius + 8))),
                     (int(x + np.cos(r) * (radius + 24)), int(y + np.sin(r) * (radius + 24))),
                     accent, 4, cv2.LINE_AA)
