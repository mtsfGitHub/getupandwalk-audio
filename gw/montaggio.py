"""Mette in fila voce, pause e musica e produce l'MP3."""
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

from .fondi import track
from .musica import RATE

# livello di ogni musica: da sola (musica), nelle pause, sotto la voce; e quanto lentamente sfuma (secondi)
LEVELS = {"campane": {"music": 1.0, "pause": 0.55, "under": 0.38, "fade": 1.6},
          "accordo": {"music": 1.0, "pause": 0.8, "under": 0.32, "fade": 1.4},
          "liuto": {"music": 1.0, "pause": 0.75, "under": 0.28, "fade": 1.4},
          "giorno": {"music": 1.0, "pause": 0.75, "under": 0.28, "fade": 1.4}}


def render(events, voice, model, log=print):
    pieces, beds = [], []            # audio della voce; per ogni pezzo: (musica di fondo, livello)
    under = model["musica"].get("sotto_la_voce", True)
    cache = {}
    for i, ev in enumerate(events):
        if ev.kind == "speak":
            key = (ev.text, ev.voice, round(ev.speed, 3))
            if key not in cache:
                if ev.voice.startswith("coro:"):
                    cache[key] = voice.say_choir(ev.text, ev.voice[5:].split("|"), ev.speed)
                elif "|" in ev.voice:
                    cache[key] = voice.say_both(ev.text, *ev.voice.split("|"), ev.speed)
                else:
                    cache[key] = voice.say(ev.text, ev.voice, ev.speed)
            a = cache[key]
            pieces.append(a)
            kind = "under"
        else:
            a = np.zeros(int(ev.secs * RATE), dtype=np.float32)
            pieces.append(a)
            kind = {"music": "music", "pause": "pause", "gap": "under"}[ev.kind]
        lv = LEVELS.get(ev.bed)
        beds.append((ev.bed, len(a), 0.0 if not lv or (kind == "under" and not under) else lv[kind] * ev.vol,
                     (ev.ramp, ev.ramp_out)))
        if ev.kind == "speak" and i % 20 == 0:
            log(f"  voce: {i + 1}/{len(events)}")
    tail = int(3.5 * RATE)
    pieces.append(np.zeros(tail, dtype=np.float32)); beds.append(("nessuna", tail, 0.0, (0.0, 0.0)))
    speech = np.concatenate(pieces)
    secs = len(speech) / RATE
    vol = float(model["musica"].get("volume", 0.6))
    mix = speech.copy()
    for name in sorted({b[0] for b in beds if b[0] in LEVELS}):
        segs = []
        for k, (b, n, lvl, ramp) in enumerate(beds):
            seg = np.full(n, lvl if b == name else 0.0, dtype=np.float32)
            r_in, r_out = ramp
            if b == name and (r_in > 0 or r_out > 0) and n > 2:
                # entra e/o esce sfumando lentamente, dal livello di prima e verso quello di dopo
                prev = beds[k - 1][2] if k and beds[k - 1][0] == name else 0.0
                nxt = beds[k + 1][2] if k + 1 < len(beds) and beds[k + 1][0] == name else 0.0
                ri = min(int(r_in * RATE), n)
                ro = min(int(r_out * RATE), n - ri)
                if ri:
                    seg[:ri] = np.linspace(prev, lvl, ri)
                if ro:
                    seg[n - ro:] = np.linspace(lvl, nxt, ro)
            segs.append(seg)
        level = np.concatenate(segs)
        tau = LEVELS[name]["fade"]
        a = 1 - np.exp(-1 / (tau * RATE))       # entrate e uscite sfumate
        level = lfilter([a], [1, -(1 - a)], level, zi=[level[0]])[0].astype(np.float32)
        used = np.nonzero(level > 1e-4)[0]
        if not len(used):
            continue
        music = np.zeros(len(speech), dtype=np.float32)
        t = track(name, (used[-1] + 1) / RATE + 2, model.get("_giorno"))
        music[:min(len(t), len(music))] = t[:len(music)]
        mix += music * level * vol * 0.45
    peak = max(1e-9, float(np.max(np.abs(mix))))
    if peak > 0.98:
        mix *= 0.98 / peak
    return mix.astype(np.float32), secs


def to_mp3(audio, path, title, artist, album, comment=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "-",
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "1",
           "-codec:a", "libmp3lame", "-b:a", "96k",
           "-metadata", f"title={title}", "-metadata", f"artist={artist}", "-metadata", f"album={album}",
           "-metadata", f"comment={comment}", str(path)]
    subprocess.run(cmd, input=audio.tobytes(), check=True)
    return path
