"""Le musiche di fondo, sintetizzate (senza diritti d'autore).

  campane  → campane a distesa che chiamano alla preghiera
  accordo  → un accordo tenuto, morbido e lontano, con qualche nota in eco
  liuto    → la pavana per liuto della prima versione

Ognuna si può sostituire con un file vero: musica/campane.mp3, musica/accordo.mp3, musica/liuto.mp3.
"""
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

from .musica import RATE, load_track, pavane


def _reverb(x, seconds, rng, wet=0.5):
    n = int(seconds * RATE)
    imp = rng.uniform(-1, 1, n)
    imp = sosfilt(butter(2, 2200, "low", fs=RATE, output="sos"), imp)    # coda scura, non fruscia
    imp *= np.power(1 - np.arange(n) / n, 3.0)
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


# quanto addolcire ogni musica: frequenza sopra la quale si tagliano gli acuti (Hz)
WARM = {"campane": 2000, "accordo": 2800, "liuto": 2400, "giorno": 2400}


def warm(x, name):
    """Toglie gli acuti graffianti e lascia il suono più rotondo."""
    cut = WARM.get(name)
    if not cut or not len(x):
        return x
    peak = float(np.max(np.abs(x)))
    y = sosfilt(butter(4, cut, "low", fs=RATE, output="sos"), x.astype(np.float64))
    y = sosfilt(butter(2, 90, "high", fs=RATE, output="sos"), y)          # niente rimbombo in basso
    return (y / max(1e-9, float(np.max(np.abs(y)))) * peak).astype(np.float32)


def track(name, seconds, day=None):
    return warm(_track(name, seconds, day), name)


def _track(name, seconds, day=None):
    if name == "giorno":
        # fino al 7 novembre 2026 c'era la pavana: quegli audio restano come erano
        if day is None or str(day) <= "2026-11-07":
            return pavane(seconds)
        return daily(seconds, day)
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


# ---- una musica nuova ogni giorno ------------------------------------------------------------
# Tonalità, giro di accordi, strumento, andamento e melodia cambiano con la data:
# ogni giorno un brano diverso, ma sempre dello stesso carattere raccolto.
KEYS = {"re minore": (62, "min"), "la minore": (57, "min"), "mi minore": (64, "min"), "sol minore": (55, "min"),
        "sol maggiore": (55, "maj"), "fa maggiore": (53, "maj"), "do maggiore": (60, "maj"), "si♭ maggiore": (58, "maj")}
SCALES = {"min": [0, 2, 3, 5, 7, 8, 10], "maj": [0, 2, 4, 5, 7, 9, 11]}
PROGRESSIONS = {   # gradi della scala (0 = primo grado)
    "min": [[0, 6, 5, 4], [0, 3, 6, 2], [0, 4, 0, 6, 2, 6, 0, 4], [2, 6, 0, 4], [0, 5, 3, 4], [0, 3, 0, 4]],
    "maj": [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 0], [0, 2, 3, 4], [5, 3, 0, 4], [0, 3, 1, 4]],
}
INSTRUMENTS = {     # (smorzamento corda bassa, corda alta, chiarezza del pizzico, ottava della melodia)
    "liuto": (0.99925, 0.9984, 0.55, 0),
    "arpa": (0.9996, 0.9992, 0.75, 12),
    "chitarra": (0.9994, 0.9986, 0.45, 0),
}


def _chord(root_midi, mode, degree):
    sc = SCALES[mode]
    notes = [root_midi + sc[(degree + k) % 7] + 12 * ((degree + k) // 7) for k in (0, 2, 4)]
    return notes


def daily_info(day):
    import datetime as dt
    d = dt.date.fromisoformat(day) if isinstance(day, str) else day
    rng = np.random.default_rng(d.toordinal() * 7919)
    key = list(KEYS)[rng.integers(len(KEYS))]
    root, mode = KEYS[key]
    prog = PROGRESSIONS[mode][rng.integers(len(PROGRESSIONS[mode]))]
    inst = list(INSTRUMENTS)[rng.integers(len(INSTRUMENTS))]
    beat = float(rng.uniform(0.78, 0.95))
    pattern = int(rng.integers(3))
    return {"key": key, "root": root, "mode": mode, "prog": prog, "inst": inst, "beat": beat,
            "pattern": pattern, "seed": d.toordinal()}


def daily(seconds, day):
    from .musica import _hz
    info = daily_info(day)
    rng = np.random.default_rng(info["seed"])
    low_rho, high_rho, bright, mel_oct = INSTRUMENTS[info["inst"]]
    total = int((seconds + 6) * RATE)
    buf = np.zeros(total, dtype=np.float32)
    cache = {}

    def string(m):
        if m not in cache:
            f = _hz(m)
            big = RATE * 2
            n_per = max(2, int(big / f - 0.5))
            dur = 4.5 if m < 52 else 3.4
            length = int(big * dur)
            y = np.zeros(length + n_per + 1)
            noise = rng.uniform(-1, 1, n_per)
            acc, lp = 0.0, np.zeros(n_per)
            for i in range(n_per):
                acc = acc * (1 - bright) + noise[i] * bright
                lp[i] = acc
            pp = max(1, int(n_per * 0.2))
            lp[pp:] -= lp[:-pp].copy()
            y[:n_per] = lp
            rho = low_rho if m < 52 else high_rho
            i = n_per
            while i < length:
                j = min(i + n_per, length)
                prev2 = y[i - n_per - 1:j - n_per - 1] if i - n_per - 1 >= 0 else np.concatenate(([0.0], y[:j - n_per - 1]))
                y[i:j] = rho * 0.5 * (y[i - n_per:j - n_per] + prev2)
                i = j
            y = y[:length]
            actual = big / (n_per + 0.5)
            out_len = int(length / big * RATE * actual / f)
            out = np.interp(np.linspace(0, length - 1, out_len), np.arange(length), y)
            out /= max(1e-9, np.max(np.abs(out)))
            fade = int(0.3 * RATE)
            out[-fade:] *= np.linspace(1, 0, fade)
            cache[m] = out.astype(np.float32)
        return cache[m]

    def pluck(m, t, vel):
        s = string(m)
        start = int((t + rng.uniform(-0.012, 0.012)) * RATE)
        if 0 <= start < total:
            end = min(total, start + len(s))
            buf[start:end] += s[:end - start] * vel * 0.35

    B = info["beat"]
    t, bar = 0.1, 0
    prev_mel = None
    while t < seconds + 2:
        degree = info["prog"][bar % len(info["prog"])]
        chord = _chord(info["root"], info["mode"], degree)
        bass = chord[0] - 12 if chord[0] - 12 >= 40 else chord[0]
        inner = [n for n in chord]
        v = 0.85 + rng.uniform(0, 0.3)
        pluck(bass, t, 0.55 * v)
        pat = info["pattern"]
        if pat == 0:      # arpeggio lento, sale e scende
            seq = [inner[0], inner[1], inner[2], inner[1]] * 2
            for k, n in enumerate(seq):
                pluck(n, t + B * 0.5 * k, 0.26 if k else 0.32)
        elif pat == 1:    # accordo e due rintocchi
            for k, n in enumerate(inner):
                pluck(n, t + 0.03 * (k + 1), 0.3 * v)
            pluck(inner[1], t + B * 2, 0.24); pluck(inner[2], t + B * 3, 0.22)
        else:             # basso, poi accordi spezzati in terzine larghe
            for k, n in enumerate([inner[0], inner[2], inner[1], inner[2], inner[0], inner[1]]):
                pluck(n, t + B * (2 / 3) * k, 0.24)
        # melodia: note dell'accordo, di grado vicino alla nota precedente
        cands = sorted({n + 12 + mel_oct for n in chord} | {n + 24 + mel_oct for n in chord})
        cands = [c for c in cands if 64 <= c <= 84] or cands
        if prev_mel is None:
            m1 = cands[len(cands) // 2]
        else:
            m1 = min(cands, key=lambda c: abs(c - prev_mel) + rng.uniform(0, 3))
        pluck(m1, t + 0.09, 0.48 * v)
        if rng.uniform() < 0.7:
            m2 = min(cands, key=lambda c: abs(c - m1 - rng.choice([-3, -2, 2, 3])) + rng.uniform(0, 1))
            pluck(m2, t + B * 2, 0.42 * v)
            prev_mel = m2
        else:
            prev_mel = m1
        t += B * 4
        bar += 1
    return (_reverb(buf.astype(np.float64), 3.2, rng, wet=0.4) * 0.8).astype(np.float32)
