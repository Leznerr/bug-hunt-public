"""Turn generated sprites into game-ready PNG-32.

Image models will not give you real transparency, so the prompts ask for a flat
magenta background instead. This removes it, kills the magenta bleeding into the
edge pixels, and trims the canvas to the artwork.

    python batch_key.py            reads raw/, writes assets/

Check the result over a GREEN background, not a white one - white hides exactly
the magenta fringe this script exists to remove, and the game draws these over a
live camera feed.
"""

import pathlib
import sys

import cv2
import numpy as np

HERE = pathlib.Path(__file__).parent


def key_image(img):
    hsv = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2HSV)

    # magenta sits around hue 150 on OpenCV's 0-179 scale
    mask = cv2.inRange(hsv, (140, 90, 90), (170, 255, 255))

    # grow the key by a pixel so no fringe survives, then soften the cut
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    alpha = cv2.GaussianBlur(255 - mask, (3, 3), 0)

    # de-spill: pull green up on edge pixels so leftover magenta goes neutral
    b, g, r = cv2.split(img[:, :, :3].astype(np.float32))
    keep = 255 - mask
    edge = (keep > 0) & (cv2.erode(keep, np.ones((5, 5), np.uint8)) == 0)
    g[edge] = np.maximum(g[edge], np.minimum(b[edge], r[edge]))

    out = cv2.merge([b, g, r, alpha.astype(np.float32)]).astype(np.uint8)

    rows = np.where(alpha.any(axis=1))[0]
    cols = np.where(alpha.any(axis=0))[0]
    if rows.size and cols.size:
        out = out[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    return out


def main():
    src = HERE / (sys.argv[1] if len(sys.argv) > 1 else "raw")
    dst = HERE / (sys.argv[2] if len(sys.argv) > 2 else "assets")
    if not src.exists():
        raise SystemExit(f"Nothing to key: {src} does not exist. "
                         f"Put the generated PNGs in there first.")
    dst.mkdir(parents=True, exist_ok=True)

    files = sorted(src.glob("*.png")) + sorted(src.glob("*.jpg"))
    if not files:
        raise SystemExit(f"No images found in {src}")

    for path in files:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            print(f"  skipped {path.name} (could not decode)")
            continue
        out = key_image(img)
        target = dst / (path.stem + ".png")
        cv2.imwrite(str(target), out)
        coverage = (out[:, :, 3] > 0).mean()
        warn = "  <- almost nothing survived, check the background colour" if coverage < 0.05 else ""
        print(f"  {path.name:28} -> {target.name:28} {out.shape[1]}x{out.shape[0]}"
              f"  {coverage:5.1%} opaque{warn}")


if __name__ == "__main__":
    main()
