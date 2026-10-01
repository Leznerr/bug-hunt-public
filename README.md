# Bug Hunt

A webcam-based bug-swatting booth game. Bugs appear on a live camera feed — swat the **green** ones with your hand, avoid the **amber** and **red** ones. Three rounds, 60 seconds total, **150 points to clear the challenge**.

---

## Prerequisites

- **Python 3.10+**
- **Webcam** (built-in or USB)
- **Windows** (uses DirectShow for camera capture)

## Setup

1. **Create a virtual environment** (from the project root):
   ```
   py -m venv .venv
   ```

2. **Activate it**:
   ```
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```
   pip install -r BugHunt\requirements.txt
   ```
   > If `pip` isn't recognized, use: `.venv\Scripts\pip.exe install -r BugHunt\requirements.txt`
   This installs: `mediapipe`, `opencv-python`, `numpy`, and `sounddevice`.

## Run the Game

```
cd BugHunt
py bughunt.py
```

Or without activating the venv:
```
cd BugHunt
..\.venv\Scripts\python.exe bughunt.py
```

> **Tip:** On Windows, use `py` if `python` is not recognized.

The game launches in **fullscreen** by default. To run in a window:
```
py bughunt.py --windowed
```

### Command-Line Options

| Flag                  | Description                          |
|-----------------------|--------------------------------------|
| `--camera N`          | Select webcam index (default: `0`)   |
| `--windowed`          | Start in windowed mode               |
| `--no-audio`          | Disable all sound                    |
| `--width W --height H`| Capture resolution (default: 1280×720)|

## Controls

| Key | Action             |
|-----|--------------------|
| `Q` | Quit               |
| `R` | Restart / reset    |
| `F` | Toggle fullscreen  |
| `M` | Toggle mute        |
| `D` | Toggle debug overlay |

## How to Play

1. **Show your hand** to the camera on the attract screen and **hold it over the circle** to start.
2. **Swat green bugs** — they give **+10 points** each.
3. **Avoid amber** (−20) **and red** (−35) bugs.
4. **Don't let green bugs escape** — each one that times out costs −5.
5. **Build combos** — 3+ consecutive green swats earn +5 bonus per hit.
6. Score **150+ points** across 3 rounds (20 seconds each) to clear the challenge.

## Troubleshooting

- **"Could not open camera"** → Try `--camera 1` or close other apps using the webcam.
- **No sound** → The game runs silently if no audio device is found; this is intentional so the game never crashes from missing audio.
- **Low FPS** → Press `D` to check frame rate, then try `--width 960 --height 540` to reduce resolution.
- **Backlit hands not detected** → Light the player from the front; MediaPipe struggles with backlighting.