"""Bug Hunt - webcam swat game for the booth.

Swat the green bugs with your hand. Leave the amber and red ones alone.
Three consecutive rounds, one minute of play, 150 points clears the challenge.

    python bughunt.py                 default camera, 1280x720
    python bughunt.py --camera 1      pick a different webcam
    python bughunt.py --no-audio      silent
    python bughunt.py --windowed      do not start fullscreen

Keys:  Q quit   R restart   F fullscreen   M mute   D debug overlay

The art is placeholder until real PNGs land in assets/ - see art.py for the
filenames. Nothing in this file needs to change when they do.
"""

import argparse
import random
import time

import cv2
import numpy as np

from art import Art
from audio import Audio
from blit import overlay_panel
from hands import HandTracker

# ==========================================================================
#  BOOTH SETTINGS - the only numbers an operator should need to touch
# ==========================================================================
ROUNDS = 3
ROUND_SECONDS = 20            # 3 x 20s = the one-minute limit
COUNTDOWN_SECONDS = 3         # shown before every round
TARGET_SCORE = 150            # reaching this clears the challenge

POINTS = {
    "green": +10,             # the ones you want
    "amber": -20,             # cost of a careless swat
    "red": -35,               # cost of a reckless one
}
ESCAPE_PENALTY = -5           # a green bug that got away
COMBO_AT = 3                  # consecutive greens before the bonus starts
COMBO_BONUS = 5               # extra points per green while the combo holds

# Per round: how long a bug stays, the gap after it goes, and the tier mix.
ROUND_TUNING = [
    dict(life=1.10, gap=0.55, mix=(0.70, 0.20, 0.10)),
    dict(life=0.95, gap=0.45, mix=(0.60, 0.25, 0.15)),
    dict(life=0.80, gap=0.38, mix=(0.55, 0.25, 0.20)),
]

MAX_ACTIVE = 1                # the brief says bugs appear one at a time
BUG_RADIUS = 46
MIN_SPAWN_DISTANCE = 260      # px from a hand, so nobody can camp the spawn
HIT_COOLDOWN = 0.22           # after a swat, before another can register
FEED_DIM = 0.28               # how much to darken the camera feed

# ==========================================================================
COLOURS = dict(               # BGR
    accent=(150, 220, 120),
    ink=(245, 248, 244),
    muted=(170, 185, 175),
    good=(80, 210, 90),
    warn=(40, 175, 235),
    bad=(70, 80, 235),
    panel=(24, 30, 26),
)
FONT = cv2.FONT_HERSHEY_DUPLEX
TIERS = ("green", "amber", "red")


def text(img, s, pos, scale, colour, weight=2, centre=False, shadow=True):
    """Text with a drop shadow, because it sits on top of a live camera feed."""
    (tw, th), _ = cv2.getTextSize(s, FONT, scale, weight)
    x, y = pos
    if centre:
        x -= tw // 2
    if shadow:
        cv2.putText(img, s, (x + 2, y + 2), FONT, scale, (0, 0, 0), weight + 1, cv2.LINE_AA)
    cv2.putText(img, s, (x, y), FONT, scale, colour, weight, cv2.LINE_AA)
    return tw, th


class Bug:
    __slots__ = ("x", "y", "tier", "born", "dies", "swatted_at", "wobble")

    def __init__(self, x, y, tier, now, life):
        self.x, self.y, self.tier = x, y, tier
        self.born, self.dies = now, now + life
        self.swatted_at = None
        self.wobble = random.uniform(0, 6.28)


class Splat:
    __slots__ = ("x", "y", "tier", "variant", "born")

    def __init__(self, x, y, tier, now):
        self.x, self.y, self.tier = x, y, tier
        self.variant = random.randrange(3)
        self.born = now


class Game:
    def __init__(self, args):
        self.art = Art()
        self.audio = Audio(enabled=not args.no_audio)
        self.tracker = HandTracker(max_hands=2)
        self.debug = False
        self.muted = args.no_audio

        self.cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        if not self.cap.isOpened():
            raise SystemExit(f"Could not open camera {args.camera}. "
                             f"Try --camera 1, or close whatever else is using it.")

        ok, frame = self.cap.read()
        if not ok:
            raise SystemExit("Camera opened but returned no frame.")
        self.h, self.w = frame.shape[:2]
        self.play_box = (90, 150, self.w - 90, self.h - 120)

        self.window = "Bug Hunt"
        cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)
        self.fullscreen = not args.windowed
        self._apply_fullscreen()

        print(f"[art]   {self.art.report()}")
        print(f"[audio] {self.audio.report()}")
        print(f"[video] {self.w}x{self.h}")

        self.state = None
        self.to_attract()

    # -- state transitions ---------------------------------------------------
    def to_attract(self):
        self.state = "attract"
        self.score = 0
        self.round = 0
        self.bugs, self.splats = [], []
        self.dwell = 0.0
        self.combo = 0
        self.best_combo = 0
        self.stats = dict(hit=0, wrong=0, escaped=0)
        self.last_hit_at = 0.0
        self.cleared = False
        self.audio.music("music_attract")

    def to_countdown(self):
        self.state = "countdown"
        self.phase_start = time.time()
        self.last_beep = -1

    def to_play(self):
        self.state = "play"
        self.phase_start = time.time()
        self.next_spawn = self.phase_start + 0.3
        self.last_hit_at = 0.0
        self.last_tick = -1
        self.bugs = []
        self.audio.music("music_game")

    def to_result(self):
        self.state = "result"
        self.phase_start = time.time()
        self.dwell = 0.0
        self.cleared = self.score >= TARGET_SCORE
        self.audio.stop_music()
        self.audio.play("cleared" if self.cleared else "failed")

    def _apply_fullscreen(self):
        cv2.setWindowProperty(
            self.window, cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN if self.fullscreen else cv2.WINDOW_NORMAL)

    # -- gameplay ------------------------------------------------------------
    def tuning(self):
        return ROUND_TUNING[min(self.round, len(ROUND_TUNING) - 1)]

    def spawn(self, now, hands):
        x0, y0, x1, y1 = self.play_box
        for _ in range(24):
            x = random.randint(x0, x1)
            y = random.randint(y0, y1)
            if all(np.hypot(x - h.x, y - h.y) > MIN_SPAWN_DISTANCE for h in hands):
                break
        tier = random.choices(TIERS, weights=self.tuning()["mix"])[0]
        self.bugs.append(Bug(x, y, tier, now, self.tuning()["life"]))
        self.audio.play("spawn")

    def resolve_hits(self, now, hands, swat_radius):
        if now - self.last_hit_at < HIT_COOLDOWN:
            return
        for bug in self.bugs:
            if bug.swatted_at is not None:
                continue
            reach = BUG_RADIUS + swat_radius * 0.55
            if not any(np.hypot(hand.x - bug.x, hand.y - bug.y) < reach for hand in hands):
                continue

            bug.swatted_at = now
            self.last_hit_at = now
            self.splats.append(Splat(bug.x, bug.y, bug.tier, now))
            self.score += POINTS[bug.tier]

            if bug.tier == "green":
                self.combo += 1
                self.best_combo = max(self.best_combo, self.combo)
                if self.combo >= COMBO_AT:
                    self.score += COMBO_BONUS
                self.stats["hit"] += 1
                self.audio.play("swat_hit")
            else:
                self.combo = 0
                self.stats["wrong"] += 1
                self.audio.play("wrong_hit")

            self.score = max(0, self.score)
            break

    def update_play(self, now, hands, swat_radius):
        elapsed = now - self.phase_start
        remaining = ROUND_SECONDS - elapsed

        if now >= self.next_spawn and len([b for b in self.bugs if b.swatted_at is None]) < MAX_ACTIVE:
            if remaining > 0.6:
                self.spawn(now, hands)
            self.next_spawn = now + self.tuning()["life"] + self.tuning()["gap"]

        self.resolve_hits(now, hands, swat_radius)

        alive = []
        for bug in self.bugs:
            if bug.swatted_at is not None:
                if now - bug.swatted_at < 0.18:
                    alive.append(bug)
                continue
            if now >= bug.dies:
                if bug.tier == "green":
                    self.score = max(0, self.score + ESCAPE_PENALTY)
                    self.stats["escaped"] += 1
                    self.combo = 0
                continue
            alive.append(bug)
        self.bugs = alive
        self.splats = [s for s in self.splats if now - s.born < 0.7]

        tick = int(remaining)
        if 0 <= tick <= 4 and tick != self.last_tick:
            self.last_tick = tick
            self.audio.play("tick_warning")

        if remaining <= 0:
            self.round += 1
            if self.round >= ROUNDS:
                self.to_result()
            else:
                self.audio.play("round_clear")
                self.to_countdown()

    # -- drawing -------------------------------------------------------------
    def draw_world(self, frame, now):
        for s in self.splats:
            age = (now - s.born) / 0.7
            self.art.draw_splat(frame, int(s.x), int(s.y), 58, s.tier, s.variant,
                                alpha=max(0.0, 1.0 - age ** 2))
        for bug in self.bugs:
            if bug.swatted_at is not None:
                continue
            age = now - bug.born
            spawning = 1.0 if age < 0.14 else 0.0
            phase = (now * 11 + bug.wobble) % 8
            # squash slightly as the bug's time runs out, so urgency is visible
            left = max(0.0, (bug.dies - now) / max(0.001, bug.dies - bug.born))
            pulse = 1.0 + 0.05 * np.sin(now * 14 + bug.wobble) * (1.0 - left)
            angle = np.sin(now * 3 + bug.wobble) * 6
            self.art.draw_bug(frame, int(bug.x), int(bug.y), int(BUG_RADIUS * pulse),
                              bug.tier, phase, spawning, angle=angle)
            if left < 0.35:                       # about-to-escape ring
                cv2.circle(frame, (int(bug.x), int(bug.y)), int(BUG_RADIUS + 14),
                           COLOURS["warn"], 2, cv2.LINE_AA)

    def draw_hands(self, frame, hands, swat_radius, now):
        impact = (now - self.last_hit_at) < 0.10 if self.state == "play" else False
        for hand in hands:
            angle = float(np.clip(-hand.vx * 0.03, -28, 28))
            self.art.draw_swatter(frame, int(hand.x), int(hand.y), swat_radius,
                                  angle=angle, impact=impact)

    def draw_hud(self, frame, now):
        w = self.w
        overlay_panel(frame, 0, 0, w, 96, COLOURS["panel"], 0.55)

        tw, _ = text(frame, f"{self.score}", (28, 66), 1.7, COLOURS["ink"], 3)
        text(frame, f"/ {TARGET_SCORE}", (40 + tw, 66), 0.7, COLOURS["muted"], 1)

        # progress toward clearing
        bx0, bx1, by = 30, 230, 80          # fixed width, so it does not jump as the score grows
        frac = min(1.0, self.score / TARGET_SCORE)
        cv2.rectangle(frame, (bx0, by), (bx1, by + 7), (60, 70, 62), -1)
        cv2.rectangle(frame, (bx0, by), (int(bx0 + (bx1 - bx0) * frac), by + 7),
                      COLOURS["good"] if frac >= 1 else COLOURS["accent"], -1)

        # round pips
        cx = w // 2 - (ROUNDS * 34) // 2
        for i in range(ROUNDS):
            done = i < self.round
            live = i == self.round and self.state == "play"
            colour = COLOURS["accent"] if done else (COLOURS["ink"] if live else (90, 100, 92))
            cv2.circle(frame, (cx + i * 34, 40), 9, colour, -1 if (done or live) else 2, cv2.LINE_AA)
        text(frame, f"ROUND {min(self.round + 1, ROUNDS)} OF {ROUNDS}", (w // 2, 76),
             0.55, COLOURS["muted"], 1, centre=True)

        # round timer
        if self.state == "play":
            remaining = max(0.0, ROUND_SECONDS - (now - self.phase_start))
            colour = COLOURS["bad"] if remaining <= 5 else COLOURS["ink"]
            text(frame, f"{remaining:04.1f}", (w - 150, 62), 1.4, colour, 3)
            cv2.rectangle(frame, (w - 300, 80), (w - 30, 87), (60, 70, 62), -1)
            cv2.rectangle(frame, (w - 300, 80),
                          (int(w - 300 + 270 * (remaining / ROUND_SECONDS)), 87), colour, -1)

        if self.combo >= COMBO_AT:
            text(frame, f"COMBO x{self.combo}", (w // 2, 130), 0.8,
                 COLOURS["accent"], 2, centre=True)

    def draw_attract(self, frame, hands, dt):
        overlay_panel(frame, 0, 0, self.w, self.h, (0, 0, 0), 0.45)
        cx, cy = self.w // 2, self.h // 2
        text(frame, "BUG HUNT", (cx, cy - 120), 2.4, COLOURS["ink"], 4, centre=True)
        text(frame, "Swat the GREEN bugs with your hand", (cx, cy - 66), 0.85,
             COLOURS["accent"], 2, centre=True)
        text(frame, "Leave AMBER and RED alone", (cx, cy - 32), 0.75,
             COLOURS["warn"], 2, centre=True)
        text(frame, f"{ROUNDS} rounds  -  {ROUNDS * ROUND_SECONDS}s  -  {TARGET_SCORE} points to clear",
             (cx, cy + 4), 0.65, COLOURS["muted"], 1, centre=True)

        # tier legend, drawn with the same art the game uses
        for i, tier in enumerate(TIERS):
            x = cx + (i - 1) * 190
            self.art.draw_bug(frame, x, cy + 92, 40, tier, (time.time() * 8 + i * 3) % 8)
            label = {"green": "+10  SWAT", "amber": "-20  AVOID", "red": "-35  AVOID"}[tier]
            text(frame, label, (x, cy + 156), 0.6,
                 COLOURS["good"] if tier == "green" else COLOURS["bad"], 2, centre=True)

        target = (cx, self.h - 130)
        held = self._dwell_target(frame, hands, target, dt, "HOLD TO START")
        if held:
            self.round = 0
            self.score = 0
            self.stats = dict(hit=0, wrong=0, escaped=0)
            self.combo = self.best_combo = 0
            self.to_countdown()

    def draw_countdown(self, frame, now):
        overlay_panel(frame, 0, 0, self.w, self.h, (0, 0, 0), 0.4)
        left = COUNTDOWN_SECONDS - (now - self.phase_start)
        n = int(np.ceil(left))
        if n != self.last_beep and n > 0:
            self.last_beep = n
            self.audio.play("countdown_beep")
        cx, cy = self.w // 2, self.h // 2
        text(frame, f"ROUND {self.round + 1}", (cx, cy - 70), 1.3, COLOURS["accent"], 3, centre=True)
        if left > 0:
            grow = 1.0 + (1.0 - (left % 1.0)) * 0.5
            text(frame, str(max(1, n)), (cx, cy + 60), 3.5 * grow, COLOURS["ink"], 6, centre=True)
        else:
            self.to_play()

    def draw_result(self, frame, hands, dt):
        overlay_panel(frame, 0, 0, self.w, self.h, (0, 0, 0), 0.6)
        cx, cy = self.w // 2, self.h // 2
        if self.cleared:
            self.art.draw_badge(frame, cx, cy - 120, 62, COLOURS["accent"])
            text(frame, "CHALLENGE CLEARED", (cx, cy - 20), 1.6, COLOURS["good"], 3, centre=True)
            text(frame, "Collect your keychain and get the officer's signature",
                 (cx, cy + 20), 0.7, COLOURS["ink"], 2, centre=True)
        else:
            text(frame, "NOT CLEARED", (cx, cy - 60), 1.8, COLOURS["bad"], 3, centre=True)
            text(frame, f"You needed {TARGET_SCORE - self.score} more points",
                 (cx, cy - 12), 0.75, COLOURS["ink"], 2, centre=True)

        text(frame, f"{self.score} POINTS", (cx, cy + 78), 1.3, COLOURS["ink"], 3, centre=True)
        line = (f"{self.stats['hit']} swatted    "
                f"{self.stats['wrong']} wrong hits    "
                f"{self.stats['escaped']} got away    "
                f"best combo x{self.best_combo}")
        text(frame, line, (cx, cy + 116), 0.6, COLOURS["muted"], 1, centre=True)

        target = (cx, self.h - 120)
        if self._dwell_target(frame, hands, target, dt, "HOLD FOR NEXT PLAYER"):
            self.to_attract()

    def _dwell_target(self, frame, hands, target, dt, label):
        """A hold-to-confirm ring. Dwell beats a tap - nobody starts by accident."""
        tx, ty = target
        r = 52
        over = any(np.hypot(h.x - tx, h.y - ty) < r + 40 for h in hands)
        self.dwell = min(1.0, self.dwell + dt / 1.1) if over else max(0.0, self.dwell - dt / 0.5)

        cv2.circle(frame, (tx, ty), r, (70, 80, 72), 5, cv2.LINE_AA)
        if self.dwell > 0:
            cv2.ellipse(frame, (tx, ty), (r, r), -90, 0, 360 * self.dwell,
                        COLOURS["accent"], 5, cv2.LINE_AA)
        text(frame, label, (tx, ty + r + 34), 0.6, COLOURS["ink"], 2, centre=True)
        if not hands:
            text(frame, "show your hand to the camera", (tx, ty - r - 24), 0.55,
                 COLOURS["muted"], 1, centre=True)
        if self.dwell >= 1.0:
            self.dwell = 0.0
            return True
        return False

    # -- loop ----------------------------------------------------------------
    def run(self):
        prev = time.time()
        fps = 0.0
        no_hand_since = None

        while True:
            ok, frame = self.cap.read()
            if not ok:
                print("Camera dropped a frame.")
                break
            frame = cv2.flip(frame, 1)

            now = time.time()
            dt = min(0.1, now - prev)
            prev = now
            fps = fps * 0.9 + (1.0 / dt) * 0.1 if dt > 0 else fps

            hands = self.tracker.find(frame, dt)
            swat_radius = int(np.clip(hands[0].span * 0.85, 70, 150)) if hands else 95

            overlay_panel(frame, 0, 0, self.w, self.h, (0, 0, 0), FEED_DIM)

            if self.state == "play":
                self.update_play(now, hands, swat_radius)
                self.draw_world(frame, now)
                self.draw_hud(frame, now)
                if hands:
                    no_hand_since = None
                else:
                    no_hand_since = no_hand_since or now
                    if now - no_hand_since > 1.2:
                        text(frame, "SHOW YOUR HAND", (self.w // 2, self.h - 70),
                             0.9, COLOURS["warn"], 2, centre=True)
            elif self.state == "attract":
                self.draw_attract(frame, hands, dt)
            elif self.state == "countdown":
                self.draw_hud(frame, now)
                self.draw_countdown(frame, now)
            elif self.state == "result":
                self.draw_result(frame, hands, dt)

            self.draw_hands(frame, hands, swat_radius, now)
            self.art.draw_bezel(frame, COLOURS["accent"])

            if self.debug:
                text(frame, f"{fps:4.1f} fps   hands {len(hands)}   state {self.state}"
                            f"   {'PLACEHOLDER ART' if self.art.using_placeholders else 'PNG ART'}",
                     (20, self.h - 20), 0.5, COLOURS["muted"], 1)

            cv2.imshow(self.window, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or cv2.getWindowProperty(self.window, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord('r'):
                self.to_attract()
            if key == ord('d'):
                self.debug = not self.debug
            if key == ord('f'):
                self.fullscreen = not self.fullscreen
                self._apply_fullscreen()
            if key == ord('m'):
                self.muted = not self.muted
                self.audio.set_muted(self.muted)

        self.close()

    def close(self):
        self.audio.close()
        self.tracker.close()
        self.cap.release()
        cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description="Bug Hunt booth game")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--windowed", action="store_true")
    args = ap.parse_args()
    Game(args).run()


if __name__ == "__main__":
    main()
