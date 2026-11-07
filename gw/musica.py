"""Un liuto sintetico (corde pizzicate, metodo Karplus-Strong) che suona una pavana lenta in re minore.

È la stessa musica dell'app di prova. Si sostituisce con un brano vero mettendo un file in musica/brano.mp3.
"""
import numpy as np
from scipy.signal import fftconvolve

RATE = 24000
BEAT = 0.85
# basso, due voci interne, melodia (prima e seconda metà della battuta)
BARS = [[50, 57, 62, 69, 65], [48, 55, 60, 67, 64], [46, 53, 58, 65, 62], [41, 57, 60, 65, 69],
        [43, 55, 58, 70, 67], [50, 57, 62, 69, 65], [45, 52, 57, 64, 61], [50, 53, 57, 62, 0],
        [41, 57, 60, 72, 69], [48, 55, 60, 67, 72], [50, 57, 62, 74, 69], [45, 57, 60, 72, 76],
        [46, 53, 62, 74, 70], [43, 55, 62, 70, 67], [45, 52, 61, 69, 73], [50, 57, 66, 74, 0]]


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _string(m, rng):
    """Una corda pizzicata, già intonata e normalizzata."""
    f = _hz(m)
    big = RATE * 2  # sintetizza al doppio e ricampiona: intonazione più precisa
    n_per = max(2, int(big / f - 0.5))
    dur = 4.5 if m < 52 else 3.2
    length = int(big * dur)
    y = np.zeros(length + n_per + 1)
    noise = rng.uniform(-1, 1, n_per)
    lp = np.zeros(n_per)
    acc = 0.0
    for i in range(n_per):
        acc = acc * 0.55 + noise[i] * 0.45
        lp[i] = acc
    pp = max(1, int(n_per * 0.18))
    lp[pp:] -= lp[:-pp].copy()
    y[:n_per] = lp
    rho = 0.99925 if m < 52 else 0.9984
    i = n_per
    while i < length:
        j = min(i + n_per, length)
        prev = y[i - n_per:j - n_per]
        prev2 = y[i - n_per - 1:j - n_per - 1] if i - n_per - 1 >= 0 else np.concatenate(([0.0], y[:j - n_per - 1]))
        y[i:j] = rho * 0.5 * (prev + prev2)
        i = j
    y = y[:length]
    actual = big / (n_per + 0.5)
    # ricampiona alla frequenza giusta e a RATE
    out_len = int(length / big * RATE * actual / f)
    src = np.linspace(0, length - 1, out_len)
    out = np.interp(src, np.arange(length), y)
    out /= max(1e-9, np.max(np.abs(out)))
    fade = int(0.3 * RATE)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out.astype(np.float32)


def pavane(seconds, seed=7):
    rng = np.random.default_rng(seed)
    cache = {}
    total = int((seconds + 6) * RATE)
    buf = np.zeros(total, dtype=np.float32)

    def pluck(m, t, vel):
        if not m:
            return
        if m not in cache:
            cache[m] = _string(m, rng)
        s = cache[m]
        start = int((t + rng.uniform(-0.012, 0.012)) * RATE)
        if start < 0 or start >= total:
            return
        end = min(total, start + len(s))
        buf[start:end] += s[:end - start] * vel * 0.35

    t, k = 0.1, 0
    while t < seconds + 2:
        bs, i1, i2, m1, m2 = BARS[k % len(BARS)]
        v = 0.85 + rng.uniform(0, 0.3)
        pluck(bs, t, 0.55 * v); pluck(i1, t + 0.03, 0.3 * v); pluck(i2, t + 0.06, 0.3 * v); pluck(m1, t + 0.09, 0.5 * v)
        pluck(i1, t + BEAT, 0.24); pluck(i2, t + BEAT * 1.5, 0.22)
        if m2:
            pluck(m2, t + BEAT * 2, 0.46 * v)
        else:
            pluck(i2, t + BEAT * 2, 0.25)
        pluck(bs + 12, t + BEAT * 2, 0.2)
        pluck(i1, t + BEAT * 3, 0.22); pluck(i2, t + BEAT * 3.5, 0.2)
        t += BEAT * 4
        k += 1

    # riverbero: una stanza ampia, come una chiesa piccola
    n = int(3.2 * RATE)
    imp = rng.uniform(-1, 1, n) * np.power(1 - np.arange(n) / n, 2.8)
    wet = fftconvolve(buf, imp)[:total]
    wet /= max(1e-9, np.max(np.abs(wet)))
    dry = buf / max(1e-9, np.max(np.abs(buf)))
    mix = 0.75 * dry + 0.38 * wet
    mix /= max(1e-9, np.max(np.abs(mix)))
    return (mix * 0.8).astype(np.float32)


def load_track(path, seconds):
    """Un brano vero (per esempio da Pray as you go), ripetuto fino alla durata richiesta."""
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    need = int((seconds + 6) * RATE)
    reps = int(np.ceil(need / max(1, len(a))))
    a = np.tile(a, reps)[:need]
    return (a / max(1e-9, np.max(np.abs(a))) * 0.8).astype(np.float32)
