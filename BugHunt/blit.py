"""Alpha compositing helpers.

Everything the game draws goes through here, so a procedurally drawn shape and a
real PNG land on the frame the same way.
"""

import cv2
import numpy as np


def blit_rgba(dst, rgba, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    """Draw an RGBA image centred on (cx, cy), rotated and scaled.

    dst    - BGR frame, modified in place
    rgba   - HxWx4 uint8 sprite
    angle  - degrees, counter-clockwise
    alpha  - extra opacity multiplier, 0..1 (used for fades)
    """
    if rgba is None or scale <= 0 or alpha <= 0:
        return

    h, w = rgba.shape[:2]

    # Rotate and scale about the sprite centre, into a canvas big enough that
    # the corners cannot be clipped off during rotation.
    diag = int(np.ceil(np.hypot(w, h) * scale)) + 2
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, scale)
    M[0, 2] += diag / 2.0 - w / 2.0
    M[1, 2] += diag / 2.0 - h / 2.0
    warped = cv2.warpAffine(
        rgba, M, (diag, diag),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    # Where does it land on the frame, and how much of it is actually on screen?
    x0, y0 = int(round(cx - diag / 2.0)), int(round(cy - diag / 2.0))
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(dst.shape[1], x0 + diag), min(dst.shape[0], y0 + diag)
    if dx0 >= dx1 or dy0 >= dy1:
        return

    src = warped[dy0 - y0:dy1 - y0, dx0 - x0:dx1 - x0]
    a = (src[:, :, 3:4].astype(np.float32) / 255.0) * float(alpha)
    roi = dst[dy0:dy1, dx0:dx1]
    np.copyto(roi, (src[:, :, :3].astype(np.float32) * a
                    + roi.astype(np.float32) * (1.0 - a)).astype(np.uint8))


def overlay_panel(dst, x0, y0, x1, y1, colour, alpha):
    """Translucent filled rectangle - used for HUD backing and screen dimming."""
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(dst.shape[1], x1), min(dst.shape[0], y1)
    if x0 >= x1 or y0 >= y1:
        return
    roi = dst[y0:y1, x0:x1]
    layer = np.full_like(roi, colour, dtype=np.uint8)
    cv2.addWeighted(layer, alpha, roi, 1.0 - alpha, 0, roi)


def new_layer(size):
    """A blank transparent RGBA canvas of (w, h), for building a sprite."""
    w, h = size
    return np.zeros((h, w, 4), dtype=np.uint8)
