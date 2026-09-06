"""Hand tracking, reduced to what the game actually needs.

The game only ever asks "where is the palm, and how big is it on screen" - the
palm because you swat with a hand rather than a fingertip, and the size because
it scales the swatter so the sprite matches how close the player is standing.

Detection runs on a downscaled copy of the frame. MediaPipe's accuracy at 480px
is indistinguishable here and it roughly halves the per-frame cost, which is the
difference between a smooth booth laptop and a laggy one.
"""

import cv2
import mediapipe as mp
import numpy as np

PALM_IDS = (0, 5, 9, 13, 17)        # wrist plus the four knuckles


class Hand:
    __slots__ = ("x", "y", "span", "vx", "vy")

    def __init__(self, x, y, span):
        self.x, self.y, self.span = x, y, span
        self.vx = self.vy = 0.0

    @property
    def speed(self):
        return float(np.hypot(self.vx, self.vy))


class HandTracker:
    def __init__(self, max_hands=2, detect_width=480,
                 detection_confidence=0.6, tracking_confidence=0.5):
        self.detect_width = detect_width
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            model_complexity=0,             # the fast model; plenty for palm tracking
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self._prev = {}

    def find(self, frame, dt):
        """Return a list of Hand in full-frame pixel coordinates."""
        h, w = frame.shape[:2]
        scale = self.detect_width / float(w)
        small = cv2.resize(frame, (self.detect_width, int(h * scale)),
                           interpolation=cv2.INTER_AREA)
        small.flags.writeable = False
        result = self.hands.process(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))

        found = []
        if result.multi_hand_landmarks:
            for i, lms in enumerate(result.multi_hand_landmarks):
                pts = np.array([[lms.landmark[j].x * w, lms.landmark[j].y * h]
                                for j in PALM_IDS])
                cx, cy = pts.mean(axis=0)
                span = float(np.linalg.norm(pts[0] - pts[2])) * 2.0
                hand = Hand(float(cx), float(cy), span)

                # velocity, so the game can tell a swat from a hand resting on a bug
                prev = self._prev.get(i)
                if prev is not None and dt > 0:
                    hand.vx = (hand.x - prev[0]) / dt
                    hand.vy = (hand.y - prev[1]) / dt
                self._prev[i] = (hand.x, hand.y)
                found.append(hand)

        for stale in [k for k in self._prev if k >= len(found)]:
            del self._prev[stale]
        return found

    def close(self):
        self.hands.close()
