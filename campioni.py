"""Confronto di voci: tutte le voci italiane di Microsoft Edge leggono la stessa preghiera.

Uso: python campioni.py   → out/campioni/*.mp3
"""
import asyncio
import re
from pathlib import Path

import numpy as np

from gw.montaggio import to_mp3
from gw.scaletta import speakable
from gw.voce import RATE, Voices

TEXT = [
    "Mi preparo.",
    "Chiudo gli occhi, mi concentro sul momento presente, libero la mente da preoccupazioni e pensieri.",
    "Gesù diceva ai discepoli: chi è fedele in cose di poco conto, è fedele anche in cose importanti.",
    "Parlo con il Signore come un amico parla con un amico.",
]


def silence(s):
    return np.zeros(int(s * RATE), dtype=np.float32)


def italian_edge_voices():
    import edge_tts
    voices = asyncio.run(edge_tts.list_voices())
    return sorted(v["ShortName"] for v in voices if v["Locale"] == "it-IT")


def main():
    v = Voices(fallback="prova:im_nicola")
    out = Path("out/campioni")
    out.mkdir(parents=True, exist_ok=True)
    every = []
    for short in italian_edge_voices():
        name = re.sub(r"(Multilingual)?Neural$", "", short.split("-")[-1])
        multi = " multilingue" if "Multilingual" in short else ""
        parts = [v.say(f"Sono {name}{multi}.", f"edge:{short}", 1.0), silence(0.8)]
        for line in TEXT:
            parts += [v.say(speakable(line), f"edge:{short}", 0.95), silence(0.9)]
        if v.broken:
            raise SystemExit(f"Voce {short} non disponibile: {v.broken}")
        a = np.concatenate(parts)
        to_mp3(a, out / f"{name}{'-multilingue' if multi else ''}.mp3", title=short, artist="Get up and Walk",
               album="Campioni voci")
        every += [a, silence(1.5)]
        print("fatto:", short)
    to_mp3(np.concatenate(every), out / "0-tutte-le-voci.mp3", title="Tutte le voci",
           artist="Get up and Walk", album="Campioni voci")


if __name__ == "__main__":
    main()
