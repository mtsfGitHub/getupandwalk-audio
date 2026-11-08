"""Mette in fila voce, pause e musica e produce l'MP3."""
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

from .fondi import track
from .voce import level as voice_level
from .musica import RATE

# livello di ogni musica: da sola (musica), nelle pause, sotto la voce; e quanto lentamente sfuma (secondi)
LEVELS = {"campane": {"music": 1.0, "pause": 0.55, "under": 0.38, "fade": 1.6},
          "accordo": {"music": 1.0, "pause": 0.8, "under": 0.32, "fade": 1.4},
          "liuto": {"music": 1.0, "pause": 0.75, "under": 0.28, "fade": 1.4},
          "giorno": {"music": 1.0, "pause": 0.75, "under": 0.28, "fade": 1.4}}


VOICE_DB = -20.0      # volume di ogni frase (dBFS, misurato dove c'è voce)
MUSIC_DB = -8.0       # musica da sola, a volume 0.45: tanti dB sotto la voce


def render(events, voice, model, log=print, marks=None, store=None):
    pieces, beds = [], []            # audio della voce; per ogni pezzo: (musica di fondo, livello)
    under = model["musica"].get("sotto_la_voce", True)
    cache = {}
    glue = False                     # "comprà|tevene": i pezzi si toccano, senza il margine di silenzio
    cut = int(0.018 * RATE)
    for i, ev in enumerate(events):
        if ev.kind == "gap" and ev.secs == 0:
            glue = True
            if pieces and len(pieces[-1]) > 4 * cut:
                pieces[-1] = pieces[-1][:-cut]
                b = beds[-1]
                beds[-1] = (b[0], len(pieces[-1]), b[2], b[3])
            continue
        if ev.kind == "speak":
            key = (ev.text, ev.voice, round(ev.speed, 3))
            if key not in cache and ev.fixed and store is not None:
                kept = store.get(ev.text, ev.voice, ev.speed)
                if kept is not None:
                    cache[key] = kept
            if key not in cache:
                broken_before = len(getattr(voice, "broken", {}))
                skipped_before = getattr(voice, "skipped", 0)
                if ev.voice.startswith("coro:"):
                    cache[key] = voice.say_choir(ev.text, ev.voice[5:].split("|"), ev.speed)
                elif "|" in ev.voice:
                    cache[key] = voice.say_both(ev.text, *ev.voice.split("|"), ev.speed)
                else:
                    cache[key] = voice.say(ev.text, ev.voice, ev.speed)
                cache[key] = voice_level(cache[key], VOICE_DB)
                # si salva solo se è venuta con le voci scelte (non con quelle di riserva)
                if ev.fixed and store is not None and not getattr(voice, "test", False) \
                        and not getattr(voice, "broken", {}) and getattr(voice, "skipped", 0) == skipped_before:
                    store.put(ev.text, ev.voice, ev.speed, cache[key])
            a = cache[key]
            if glue and len(a) > 4 * cut:
                a = a[cut:]
            glue = False
            pieces.append(a)
            kind = "under"
            if marks is not None:
                pos = sum(len(p) for p in pieces[:-1]) / RATE
                marks.append((round(pos, 2), round(pos + len(a) / RATE, 2), ev.section, ev.voice.split(":", 1)[-1][:30], ev.text[:50]))
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
                    hold = int(1.5 * RATE) if nxt == 0 and ro > 2 * RATE else 0   # finire prima: il silenzio è silenzio
                    seg[n - ro:n - hold] = np.linspace(lvl, nxt, ro - hold)
                    seg[n - hold:] = nxt
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
        # ogni musica portata allo stesso volume, in proporzione fissa alla voce
        rms = float(np.sqrt(np.mean(t.astype(np.float64) ** 2))) + 1e-9
        k = 10 ** ((VOICE_DB + MUSIC_DB) / 20) / rms / 0.45
        mix += music * level * vol * k
    # "aria di stanza": un fruscio scurissimo e quasi impercettibile, come in una registrazione vera,
    # perché tra una frase e l'altra non ci sia il vuoto digitale assoluto
    air_db = float(model["musica"].get("aria", -62))
    if air_db > -90:
        from scipy.signal import butter, sosfilt
        rng = np.random.default_rng(11)
        air = sosfilt(butter(2, [80, 1400], "band", fs=RATE, output="sos"), rng.standard_normal(len(mix)))
        air *= 10 ** (air_db / 20) / max(1e-9, float(np.sqrt(np.mean(air ** 2))))
        edge = min(len(air) // 2, int(3 * RATE))
        air[:edge] *= np.linspace(0, 1, edge); air[-edge:] *= np.linspace(1, 0, edge)
        mix += air.astype(np.float32)
    peak = max(1e-9, float(np.max(np.abs(mix))))
    if peak > 0.98:
        mix *= 0.98 / peak
    return mix.astype(np.float32), secs


def to_mp3(audio, path, title, artist, album, comment=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # si misura il volume complessivo e si alza o abbassa TUTTO dello stesso guadagno
    # (loudnorm "dinamico" gonfierebbe la musica da sola fino al volume della voce);
    # un limitatore tiene a bada solo i picchi
    norm = "loudnorm=I=-16:TP=-1.5:LRA=11"
    try:
        import json
        r = subprocess.run(["ffmpeg", "-v", "info", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "-",
                            "-af", norm + ":print_format=json", "-f", "null", "-"],
                           input=audio.tobytes(), capture_output=True, check=True)
        txt = r.stderr.decode(errors="ignore")
        m = json.loads(txt[txt.rindex("{"):txt.rindex("}") + 1])
        gain = max(-20.0, min(20.0, -16.0 - float(m["input_i"])))
        norm = f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=5:release=80:level=false"
    except Exception:
        pass
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "-",
           "-af", norm, "-ar", "44100", "-ac", "1",
           "-codec:a", "libmp3lame", "-b:a", "96k",
           "-metadata", f"title={title}", "-metadata", f"artist={artist}", "-metadata", f"album={album}",
           "-metadata", f"comment={comment}", str(path)]
    subprocess.run(cmd, input=audio.tobytes(), check=True)
    return path
