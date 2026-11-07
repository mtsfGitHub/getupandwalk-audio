"""Mette in fila voce, pause e musica e produce l'MP3."""
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

from .musica import RATE, load_track, pavane


def render(events, voice, model, log=print):
    pieces, levels = [], []          # audio della voce e livello della musica per ogni pezzo
    bed = 0.28 if model["musica"].get("sotto_la_voce", True) else 0.0
    cache = {}
    for i, ev in enumerate(events):
        if ev.kind == "speak":
            key = (ev.text, ev.voice, round(ev.speed, 3))
            if key not in cache:
                cache[key] = (voice.say_both(ev.text, *ev.voice.split("|"), ev.speed) if "|" in ev.voice
                              else voice.say(ev.text, ev.voice, ev.speed))
            a = cache[key]
            pieces.append(a); levels.append(np.full(len(a), bed, dtype=np.float32))
        else:
            n = int(ev.secs * RATE)
            pieces.append(np.zeros(n, dtype=np.float32))
            lvl = {"music": 1.0, "pause": 0.75, "gap": bed}[ev.kind]
            levels.append(np.full(n, lvl, dtype=np.float32))
        if ev.kind == "speak" and i % 20 == 0:
            log(f"  voce: {i + 1}/{len(events)}")
    tail = int(3.5 * RATE)
    pieces.append(np.zeros(tail, dtype=np.float32)); levels.append(np.zeros(tail, dtype=np.float32))
    speech = np.concatenate(pieces)
    level = np.concatenate(levels)
    # transizioni morbide della musica (circa un secondo)
    a = 1 - np.exp(-1 / (0.45 * RATE))
    level = lfilter([a], [1, -(1 - a)], level, zi=[level[0]])[0].astype(np.float32)
    secs = len(speech) / RATE
    track = Path("musica/brano.mp3")
    music = load_track(track, secs) if track.exists() else pavane(secs)
    music = music[:len(speech)]
    vol = float(model["musica"].get("volume", 0.6))
    mix = speech + music * level * vol * 0.45
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
