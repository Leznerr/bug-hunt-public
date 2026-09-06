"""Sound, with synthesised placeholders.

Same swap contract as the art: drop a WAV into assets/audio/ with the matching
name and it replaces the synthesised version. Mono or stereo, 44.1 kHz.

  swat_hit  wrong_hit  spawn  countdown_beep  round_clear  tick_warning  cleared
  music_game  music_attract      (looped beds)

A booth laptop with no working audio device must not take the game down with it,
so every failure here degrades to silence rather than raising.
"""

import pathlib
import threading
import wave

import numpy as np

SR = 44100

try:
    import sounddevice as sd
except Exception:                                    # noqa: BLE001 - optional dep
    sd = None


# --------------------------------------------------------------------------
# synthesis
# --------------------------------------------------------------------------
def _env(n, attack=0.005, release=0.25):
    """Attack/release envelope. `release` is a fraction of the total length."""
    a = min(max(1, int(attack * SR)), n)
    r = min(max(1, int(release * n)), n - a if n > a else 1)
    e = np.ones(n, dtype=np.float32)
    e[:a] = np.linspace(0, 1, a)
    e[n - r:] *= np.linspace(1, 0, r)
    return e


def _square(freq, dur, duty=0.5):
    """Square wave. `freq` may be a scalar or a list of points to sweep through."""
    n = max(1, int(dur * SR))
    f = np.atleast_1d(np.asarray(freq, dtype=np.float32))
    if f.size == 1:
        f = np.full(n, f[0], dtype=np.float32)
    else:
        f = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, f.size), f).astype(np.float32)
    phase = np.cumsum(f) / SR
    return np.where((phase % 1.0) < duty, 1.0, -1.0).astype(np.float32)


def _noise(dur):
    rng = np.random.default_rng(1)
    return rng.uniform(-1, 1, int(dur * SR)).astype(np.float32)


def _synth(name):
    if name == "swat_hit":
        body = _square(np.array([880, 220]), 0.09, duty=0.25) * 0.5
        thump = _square(np.array([150, 60]), 0.11) * 0.5
        n = max(body.size, thump.size)
        s = np.zeros(n, dtype=np.float32)
        s[:body.size] += body
        s[:thump.size] += thump
        return s * _env(n, release=0.6) * 0.8
    if name == "wrong_hit":
        s = _square(np.array([300, 90]), 0.34, duty=0.5) * 0.6
        s += _noise(0.34) * 0.15
        return s * _env(s.size, release=0.5) * 0.9
    if name == "spawn":
        s = _square(np.array([420, 900]), 0.07, duty=0.35)
        return s * _env(s.size, release=0.5) * 0.35
    if name == "countdown_beep":
        s = _square(660, 0.12, duty=0.5)
        return s * _env(s.size, release=0.4) * 0.5
    if name == "tick_warning":
        s = _square(1200, 0.03, duty=0.2)
        return s * _env(s.size, release=0.8) * 0.3
    if name == "round_clear":
        s = np.concatenate([_square(523, 0.10), _square(784, 0.18)])
        return s * _env(s.size, release=0.4) * 0.5
    if name == "cleared":
        notes = (523, 659, 784, 1047)
        s = np.concatenate([_square(f, 0.12) for f in notes])
        s = np.concatenate([s, _square(1047, 0.55) * 0.9])
        return s * _env(s.size, release=0.35) * 0.55
    if name == "failed":
        s = _square(np.array([440, 330, 220, 165]), 0.7)
        return s * _env(s.size, release=0.4) * 0.5
    return None


# --------------------------------------------------------------------------
class Audio:
    def __init__(self, asset_dir="assets/audio", enabled=True):
        self.dir = pathlib.Path(__file__).parent / asset_dir
        self.bank = {}
        self.loaded = []
        self._voices = []
        self._lock = threading.Lock()
        self._stream = None
        self.ok = False
        self._muted = False
        if not enabled:
            return
        self._fill_bank()
        self._open()

    def _fill_bank(self):
        names = ("swat_hit", "wrong_hit", "spawn", "countdown_beep", "tick_warning",
                 "round_clear", "cleared", "failed", "music_game", "music_attract")
        for name in names:
            path = self.dir / f"{name}.wav"
            data = self._read_wav(path) if path.exists() else None
            if data is not None:
                self.loaded.append(path.name)
            else:
                data = _synth(name)
            if data is not None:
                self.bank[name] = data

    @staticmethod
    def _read_wav(path):
        try:
            with wave.open(str(path), "rb") as w:
                frames = w.readframes(w.getnframes())
                width, channels, rate = w.getsampwidth(), w.getnchannels(), w.getframerate()
            dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(width)
            if dtype is None:
                print(f"[audio] {path.name}: unsupported bit depth, skipping")
                return None
            data = np.frombuffer(frames, dtype=dtype).astype(np.float32)
            data /= float(np.iinfo(dtype).max)
            if channels > 1:
                data = data.reshape(-1, channels).mean(axis=1)
            if rate != SR:                            # cheap linear resample
                n = int(data.size * SR / rate)
                data = np.interp(np.linspace(0, data.size, n), np.arange(data.size), data)
            return data.astype(np.float32)
        except Exception as exc:                      # noqa: BLE001
            print(f"[audio] {path.name}: {exc}")
            return None

    def _open(self):
        if sd is None:
            print("[audio] sounddevice not available - running silent")
            return
        try:
            self._stream = sd.OutputStream(samplerate=SR, channels=1, dtype="float32",
                                           blocksize=512, callback=self._callback)
            self._stream.start()
            self.ok = True
        except Exception as exc:                      # noqa: BLE001
            print(f"[audio] no output device ({exc}) - running silent")

    def _callback(self, outdata, frames, time_info, status):  # noqa: ARG002
        out = np.zeros(frames, dtype=np.float32)
        with self._lock:
            keep = []
            for v in self._voices:
                data, pos, gain, loop = v
                n = frames
                while n > 0:
                    chunk = data[pos:pos + n]
                    out[frames - n:frames - n + chunk.size] += chunk * gain
                    pos += chunk.size
                    n -= chunk.size
                    if pos >= data.size:
                        if not loop:
                            break
                        pos = 0
                if loop or pos < data.size:
                    keep.append([data, pos, gain, loop])
            self._voices = keep
        outdata[:, 0] = np.clip(out, -1.0, 1.0)

    def play(self, name, gain=1.0):
        data = self.bank.get(name)
        if not self.ok or self._muted or data is None:
            return
        with self._lock:
            if len(self._voices) > 12:               # keep the mix from mudding up
                self._voices.pop(0)
            self._voices.append([data, 0, gain, False])

    def music(self, name, gain=0.35):
        self.stop_music()
        data = self.bank.get(name)
        if not self.ok or self._muted or data is None:
            return
        with self._lock:
            self._voices.append([data, 0, gain, True])

    def stop_music(self):
        with self._lock:
            self._voices = [v for v in self._voices if not v[3]]

    def set_muted(self, muted):
        """Mute without tearing the stream down, so unmuting is instant."""
        self._muted = bool(muted)
        if muted:
            self.stop_music()

    def report(self):
        if not self.ok:
            return "audio off"
        if self.loaded:
            return f"{len(self.loaded)} audio file(s) loaded, rest synthesised"
        return "all sound synthesised - drop WAVs in assets/audio/ to replace"

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:                         # noqa: BLE001
                pass
