"""Confronto di voci femminili: la stessa preghiera letta da voci diverse, per scegliere a orecchio.

Uso: python campioni.py   → out/campioni/*.mp3
"""
from pathlib import Path

import numpy as np

from gw.montaggio import to_mp3
from gw.scaletta import speakable
from gw.voce import RATE, Voices

MALE = "im_nicola"
CANDIDATES = [
    ("1-paola-piper", "piper:it_IT-paola-medium", "Voce uno: Paola."),
    ("2-dora-spagnola", "ef_dora", "Voce due: Dora."),
    ("3-siwis-francese", "ff_siwis", "Voce tre: Siwis."),
    ("4-dora-portoghese", "pf_dora", "Voce quattro: Dora, seconda versione."),
    ("5-sara-attuale", "if_sara", "Voce cinque: Sara, quella di oggi."),
]
TEXT = [
    "Chiudo gli occhi, mi concentro sul momento presente, libero la mente da preoccupazioni e pensieri.",
    "Esprimo interiormente il mio desiderio di stare alla presenza del Signore.",
    "Gesù diceva ai discepoli: chi è fedele in cose di poco conto, è fedele anche in cose importanti.",
    "Parlo con il Signore come un amico parla con un amico.",
]


def silence(s):
    return np.zeros(int(s * RATE), dtype=np.float32)


def main():
    v = Voices()
    out = Path("out/campioni")
    out.mkdir(parents=True, exist_ok=True)
    every = []
    for slug, voice, intro in CANDIDATES:
        parts = [v.say(intro, MALE, 1.0), silence(0.8)]
        for line in TEXT:
            parts += [v.say(speakable(line), voice, 0.95), silence(0.9)]
        a = np.concatenate(parts)
        to_mp3(a, out / f"{slug}.mp3", title=slug, artist="Get up and Walk", album="Campioni voci")
        every += [a, silence(1.5)]
        print("fatto:", slug)
    to_mp3(np.concatenate(every), out / "0-tutte-le-voci.mp3", title="Tutte le voci",
           artist="Get up and Walk", album="Campioni voci")


if __name__ == "__main__":
    main()
