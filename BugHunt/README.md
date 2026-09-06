# Bug Hunt

Webcam swat game for the booth. Glitch bugs appear one at a time; the player
swats the green ones with their hand and leaves the amber and red ones alone.
Three consecutive rounds, one minute of play, **150 points clears the
challenge**.

It runs today on placeholder art drawn in code. Generated PNGs drop into
`assets/` later and take over on the next launch — no game code changes.

## Run it

```
cd BugHunt
python bughunt.py
```

Uses the existing `HandTracker/.venv` (mediapipe, opencv, numpy, sounddevice
are already installed there):

```
..\HandTracker\.venv\Scripts\python.exe bughunt.py
```

| Flag | |
|---|---|
| `--camera 1` | pick a different webcam |
| `--windowed` | do not start fullscreen |
| `--no-audio` | silent |
| `--width / --height` | capture resolution, default 1280x720 |

Keys: **Q** quit · **R** restart · **F** fullscreen · **M** mute · **D** debug overlay

## How a round plays

A hold-to-start ring on the attract screen — dwell, not a tap, so nobody starts
by waving past the camera. Then three rounds of `ROUND_SECONDS`, each opened by
a 3-second countdown. One bug is on screen at a time, and it never spawns within
`MIN_SPAWN_DISTANCE` of a hand, so parking on the spawn point does not work.

| Event | Points |
|---|---|
| Green bug swatted | **+10** |
| 3rd consecutive green and beyond | **+5** each |
| Amber bug swatted | **−20** |
| Red bug swatted | **−35** |
| Green bug escaped | **−5** |

Score floors at 0. Simulated over a full session (`--no-audio`, scripted
players), that spread puts a careful player around 450, a sloppy one around 365,
and a player who swats everything at **120 — under the 150 bar**. Accuracy has
to matter or the keychain means nothing.

Every number above lives in the `BOOTH SETTINGS` block at the top of
`bughunt.py`. `ROUND_SECONDS` defaults to 20, so three rounds is the one-minute
limit; if the brief actually means a full minute *per* round, that is the one
value to change.

## Dropping in the real art

1. Generate the sprites on a flat `#FF00FF` background (see the asset prompt pack).
2. Put them in `BugHunt/raw/`.
3. `python batch_key.py` — keys out the magenta, de-spills the edges, trims the
   canvas, writes PNG-32 into `assets/`.
4. Relaunch. The startup log says which files it picked up.

Filenames it looks for, all square canvases:

```
bug_green.png        bug_amber.png        bug_red.png
bug_green_spawn.png  bug_amber_spawn.png  bug_red_spawn.png
splat_green_1..3.png                     (or splat_1..3.png for a shared set)
swatter.png          swatter_impact.png
bezel.png            badge_cleared.png
```

Two geometry rules the artwork has to respect, because they are what the game
anchors to:

- **Bugs, splats, badge** — artwork centred, filling about 80% of the canvas.
- **Swatter** — the canvas must be centred **on the paddle**, not on the whole
  object, with the handle running off toward the lower-right corner. The paddle
  is what tracks the hand, so that point is the sprite's anchor.

Audio works the same way: drop a WAV into `assets/audio/` and it replaces the
synthesised placeholder.

```
swat_hit  wrong_hit  spawn  countdown_beep  tick_warning
round_clear  cleared  failed
music_game  music_attract          (looped beds)
```

## Files

| | |
|---|---|
| `bughunt.py` | game loop, state machine, scoring, HUD |
| `hands.py` | MediaPipe wrapper — palm position, on-screen span, velocity |
| `art.py` | the swap layer: real PNG if present, placeholder if not |
| `procedural.py` | the placeholder art, drawn in code |
| `blit.py` | alpha compositing |
| `audio.py` | mixer, WAV loading, synthesised fallbacks |
| `batch_key.py` | magenta → transparency for generated sprites |

Detection runs on a 480px copy of the frame. MediaPipe's palm accuracy at that
size is indistinguishable and it roughly halves the per-frame cost, which is the
difference between a smooth booth laptop and a laggy one.

## Before the event

- Test the sound through the **laptop speakers in a noisy room**, not
  headphones. Booth games usually fail because nobody could hear the hit.
- Run `--windowed` with **D** on once to check the frame rate on the actual
  booth laptop. Under ~20 fps, drop `--width 960 --height 540`.
- Light the player's hands from the front. Backlighting (a window behind the
  player) is the one condition MediaPipe reliably struggles with.
