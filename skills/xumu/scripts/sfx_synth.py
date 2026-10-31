#!/usr/bin/env python3
"""Sound effects synthesised from scratch: no download, no licence question, same output for the same arguments.

  python sfx_synth.py list
  python sfx_synth.py make pop --out pop.wav [--pitch 1.2] [--length 1.0] [--seed 3] [--gain -6]
  python sfx_synth.py track events.json --len 29.6 --out sfx.wav

Presets: pop (hanazi / sticker pop-in), click (UI tap), ding (highlight), sparkle (shine), whoosh (transition),
thud (landing). --pitch scales frequency, --length scales duration, --seed varies the random parts.

events.json: [{"t": 2.13, "preset": "pop", "gain": -8, "pitch": 1.1, "seed": 4}, ...] in programme seconds; `track`
lays them on one silent track of --len seconds (48 kHz mono, 16-bit) that the composition mixes as its SFX layer.
A file event {"t": 5.0, "file": "audio/sfx/fs-648387.mp3", "gain": -10, "peak": 0.335} lays a downloaded sound
(Freesound via Shotcraft's sfx-source.py, or any WAV/MP3) so that its energy peak ("peak", seconds from the file
start, e.g. the manifest's energy_peak_seconds) lands on t; optional "start"/"length" trim the file in seconds.
16-bit 48 kHz WAV is read directly, anything else is decoded through ffmpeg.
Keep effects about 10-15 dB under the voice; vary pitch or seed between neighbours so repeats do not sound stamped.
"""
import argparse
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import wave

SR = 48000


def _np():
    import numpy as np
    return np


def env_exp(n, tau, np):
    return np.exp(-np.arange(n) / (tau * SR))


def attack(sig, ms, np):
    k = max(1, int(SR * ms / 1000))
    sig[:k] *= np.linspace(0, 1, k)
    return sig


def lowpass(x, cutoff, np):
    """One-pole low-pass; cutoff may be a per-sample array (moving filter for whooshes)."""
    c = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = 1 - np.exp(-2 * math.pi * c / SR)
    y = np.empty_like(x)
    prev = 0.0
    for i in range(len(x)):
        prev += a[i] * (x[i] - prev)
        y[i] = prev
    return y


def pop(pitch, length, rng, np):
    n = int(SR * 0.09 * length)
    f = 900 * pitch * np.exp(-np.arange(n) / (0.025 * SR)) + 260 * pitch   # quick downward chirp
    ph = 2 * math.pi * np.cumsum(f) / SR
    s = np.sin(ph) * env_exp(n, 0.03 * length, np)
    return attack(s, 1.5, np)


def click(pitch, length, rng, np):
    n = int(SR * 0.03 * length)
    noise = np.array([rng.uniform(-1, 1) for _ in range(n)])
    hp = np.diff(noise, prepend=0.0)                                         # crude high-pass: bright tick
    tone = np.sin(2 * math.pi * 2200 * pitch * np.arange(n) / SR) * 0.4
    return (hp * 0.6 + tone) * env_exp(n, 0.006 * length, np)


def ding(pitch, length, rng, np):
    n = int(SR * 0.7 * length)
    t = np.arange(n) / SR
    f = 1320 * pitch
    s = np.sin(2 * math.pi * f * t) + 0.35 * np.sin(2 * math.pi * 2 * f * t) + 0.12 * np.sin(2 * math.pi * 3.01 * f * t)
    return attack(s * env_exp(n, 0.18 * length, np) / 1.5, 3, np)


def sparkle(pitch, length, rng, np):
    n = int(SR * 0.45 * length)
    out = np.zeros(n)
    for _ in range(5):
        start = int(rng.uniform(0, 0.25 * length) * SR)
        f = rng.uniform(2200, 4200) * pitch
        m = min(n - start, int(SR * 0.16 * length))
        t = np.arange(m) / SR
        out[start:start + m] += np.sin(2 * math.pi * f * t) * env_exp(m, 0.04 * length, np) * rng.uniform(0.4, 0.9)
    return attack(out / 2.5, 2, np)


def whoosh(pitch, length, rng, np):
    n = int(SR * 0.45 * length)
    noise = np.array([rng.uniform(-1, 1) for _ in range(n)])
    shape = np.sin(np.linspace(0, math.pi, n)) ** 2                          # swell and fade
    cutoff = 300 * pitch + 3200 * pitch * shape                              # filter opens with the swell
    return lowpass(noise, cutoff, np) * shape * 2.2


def thud(pitch, length, rng, np):
    n = int(SR * 0.22 * length)
    f = 140 * pitch * np.exp(-np.arange(n) / (0.06 * SR)) + 55 * pitch
    s = np.sin(2 * math.pi * np.cumsum(f) / SR) * env_exp(n, 0.07 * length, np)
    return attack(s, 2, np)


PRESETS = {'pop': pop, 'click': click, 'ding': ding, 'sparkle': sparkle, 'whoosh': whoosh, 'thud': thud}


def make(preset, pitch=1.0, length=1.0, seed=0, gain=-6.0):
    np = _np()
    if preset not in PRESETS:
        raise SystemExit(f'unknown preset {preset}; choose from {", ".join(PRESETS)}')
    s = PRESETS[preset](pitch, length, random.Random(f'{preset}:{seed}'), np)
    peak = float(np.abs(s).max()) or 1.0
    return s / peak * 10 ** (gain / 20)


def write_wav(path, samples):
    np = _np()
    pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def load_audio(path, start=0.0, length=None):
    """Mono float samples at SR from an audio file: 16-bit 48 kHz WAV directly, anything else through ffmpeg."""
    np = _np()
    path = Path(path)
    data = None
    if path.suffix.lower() == '.wav':
        try:
            with wave.open(str(path)) as w:
                if w.getsampwidth() == 2 and w.getframerate() == SR:
                    raw = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float) / 32768
                    data = raw.reshape(-1, w.getnchannels()).mean(axis=1)
        except (wave.Error, EOFError):
            data = None
    if data is None:
        cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-']
        try:
            pcm = subprocess.run(cmd, capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SystemExit(f'cannot decode {path}: {exc} (ffmpeg is needed for non-WAV files)')
        data = np.frombuffer(pcm, dtype='<f4').astype(float)
    a = int(round(start * SR))
    b = len(data) if length is None else a + int(round(length * SR))
    return data[a:b]


def event_samples(e):
    """One event -> (samples, start sample on the track). Preset events start at t; file events put their peak on t."""
    np = _np()
    if 'file' in e:
        start = float(e.get('start', 0.0))
        s = load_audio(e['file'], start, e.get('length'))
        if not len(s):
            raise SystemExit(f"{e['file']}: no audio in the selected range")
        peak = float(np.abs(s).max()) or 1.0
        s = s / peak * 10 ** (e.get('gain', -10.0) / 20)
        lead = max(0.0, float(e.get('peak', start)) - start)   # seconds from the cut start to the energy peak
        return s, int(round((e['t'] - lead) * SR))
    s = make(e['preset'], e.get('pitch', 1.0), e.get('length', 1.0), e.get('seed', 0), e.get('gain', -8.0))
    return s, int(round(e['t'] * SR))


def track(events, length):
    np = _np()
    out = np.zeros(int(SR * length))
    for e in events:
        s, at = event_samples(e)
        if at < 0:   # peak alignment pulled the start before 0: drop the head
            s, at = s[-at:], 0
        if at >= len(out) or not len(s):
            continue
        m = min(len(s), len(out) - at)
        out[at:at + m] += s[:m]
    peak = float(np.abs(out).max())
    if peak > 0.98:
        out *= 0.98 / peak   # overlapping hits: scale down instead of clipping
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    p = sub.add_parser('make')
    p.add_argument('preset')
    p.add_argument('--out', required=True)
    p.add_argument('--pitch', type=float, default=1.0)
    p.add_argument('--length', type=float, default=1.0)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--gain', type=float, default=-6.0, help='peak level in dBFS')
    p = sub.add_parser('track')
    p.add_argument('events')
    p.add_argument('--len', type=float, required=True)
    p.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'list':
        print('\n'.join(PRESETS))
    elif a.cmd == 'make':
        write_wav(a.out, make(a.preset, a.pitch, a.length, a.seed, a.gain))
        print(f'saved: {a.out}')
    else:
        events = json.loads(Path(a.events).read_text(encoding='utf-8'))
        write_wav(a.out, track(events, a.len))
        print(f'saved: {a.out} ({len(events)} events, {a.len:.2f} s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
