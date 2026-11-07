"""Le musiche di fondo, sintetizzate (senza diritti d'autore).

  campane  → campane a distesa che chiamano alla preghiera
  accordo  → un accordo tenuto, morbido e lontano, con qualche nota in eco
  liuto    → la pavana per liuto della prima versione

Ognuna si può sostituire con un file vero: musica/campane.mp3, musica/accordo.mp3, musica/liuto.mp3.
"""
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

from .musica import RATE, load_track, pavane


def _reverb(x, seconds, rng, wet=0.5):
    n = int(seconds * RATE)
    imp = rng.uniform(-1, 1, n) * np.power(1 - np.arange(n) / n, 3.0)
    w = fftconvolve(x, imp)[:len(x)]
    w /= max(1e-9, np.max(np.abs(w)))
    d = x / max(1e-9, np.max(np.abs(x)))
    y = (1 - wet) * d + wet * w
    return y / max(1e-9, np.max(np.abs(y)))


def bells(seconds, seed=3):
    """Tre campane a distesa: parziali inarmoniche tipiche delle campane di bronzo."""
    rng = np.random.default_rng(seed)
    total = int((seconds + 4) * RATE)
    out = np.zeros(total, dtype=np.float64)
    # (rapporto, ampiezza, durata del suono in secondi): bordone, fondamentale, terza minore, quinta, nominale…
    partials = [(0.5, 0.9, 9.0), (1.0, 0.6, 6.5), (1.19, 0.5, 5.0), (1.5, 0.3, 4.0), (2.0, 0.7, 4.5),
                (2.51, 0.25, 2.5), (2.66, 0.2, 2.2), (3.01, 0.18, 1.8), (4.07, 0.1, 1.2)]
    nominals = [392.0, 329.6, 293.7]          # sol, mi, re: tre campane di una piccola chiesa
    t_bell = np.arange(int(10 * RATE)) / RATE
    strikes = {}
    for i, f in enumerate(nominals):
        s = np.zeros_like(t_bell)
        for ratio, amp, dur in partials:
            fr = f / 2 * ratio * (1 + rng.uniform(-0.002, 0.002))
            s += amp * np.exp(-t_bell / (dur / 4.6)) * np.sin(2 * np.pi * fr * t_bell + rng.uniform(0, 6.28))
        click = np.exp(-t_bell / 0.004) * rng.uniform(-1, 1, len(t_bell)) * 0.4
        strikes[i] = (s + click) / np.max(np.abs(s + click))
    t, k = 0.2, 0
    while t < seconds:
        i = k % 3
        vel = 0.75 + rng.uniform(0, 0.25)
        start = int((t + rng.uniform(-0.06, 0.06)) * RATE)
        if start >= 0:
            end = min(total, start + len(strikes[i]))
            out[start:end] += strikes[i][:end - start] * vel
        t += 0.95 + rng.uniform(-0.08, 0.12)
        k += 1
    return (_reverb(out, 3.5, rng, wet=0.45) * 0.8).astype(np.float32)


def held_chord(seconds, seed=5):
    """Un accordo tenuto che cambia lentamente, con qualche nota sospesa in eco."""
    rng = np.random.default_rng(seed)
    total = int((seconds + 6) * RATE)
    t = np.arange(total) / RATE
    out = np.zeros(total, dtype=np.float64)
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    chords = [[50, 57, 64, 66], [47, 54, 62, 69], [43, 50, 66, 71], [45, 52, 62, 69]]   # Re9, Si-7, Sol7+, La4
    dur, fade = 14.0, 5.0
    n_chords = int(np.ceil(seconds / (dur - fade))) + 2
    for c in range(n_chords):
        start = c * (dur - fade)
        mask = (t >= start) & (t < start + dur)
        if not mask.any():
            continue
        tt = t[mask] - start
        env = np.minimum(1, tt / fade) * np.minimum(1, (dur - tt) / fade)
        for m in chords[c % len(chords)]:
            f = hz(m)
            voice = np.zeros_like(tt)
            for det in (-0.12, 0.0, 0.12):           # leggero coro: tre corde quasi uguali
                ff = f * 2 ** (det / 12)
                for h, a in ((1, 1.0), (2, 0.28), (3, 0.1)):
                    voice += a * np.sin(2 * np.pi * ff * h * tt + rng.uniform(0, 6.28))
            lfo = 0.85 + 0.15 * np.sin(2 * np.pi * rng.uniform(0.04, 0.09) * tt + rng.uniform(0, 6.28))
            out[mask] += voice * env * lfo * (0.55 if m < 52 else 0.35)
    # note sospese in eco, ogni tanto
    notes = [74, 76, 78, 81, 69]
    tn = 3.0
    while tn < seconds:
        f = hz(notes[rng.integers(len(notes))])
        n = int(4 * RATE)
        s = int(tn * RATE)
        tt = np.arange(min(n, total - s)) / RATE
        tone = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 1.2) * np.minimum(1, tt / 0.02) * 0.25
        for echo in range(4):                         # eco lenta
            o = s + int(echo * 0.55 * RATE)
            if o >= total:
                break
            e = min(len(tone), total - o)
            out[o:o + e] += tone[:e] * (0.45 ** echo)
        tn += rng.uniform(5.5, 9.5)
    return (_reverb(out, 4.5, rng, wet=0.55) * 0.75).astype(np.float32)


def track(name, seconds):
    f = Path(f"musica/{name}.mp3")
    if f.exists():
        return load_track(f, seconds)
    if name == "liuto" and Path("musica/brano.mp3").exists():
        return load_track(Path("musica/brano.mp3"), seconds)
    if name == "campane":
        return bells(min(seconds, 90))
    if name == "accordo":
        return held_chord(seconds)
    return pavane(seconds)
