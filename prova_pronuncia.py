"""Prova di pronuncia: la parola detta a pezzi e incollata senza pausa, per spostare l'accento."""
from pathlib import Path

import numpy as np

from gw.montaggio import to_mp3
from gw.voce import RATE, Voices, _trim

PRIMA = "Andate piuttosto dai venditori e"
VARIANTI = [("Uno.", ["comprà", "tevene."]), ("Due.", ["compra", "tevene."]), ("Tre.", ["e compràte", "vene."])]


def glued(v, voice, pieces, speed):
    out = []
    for k, p in enumerate(pieces):
        a = _trim(v.say(p, voice, speed), thr=0.01)
        pad = int(0.012 * RATE)
        out.append(a[pad:-pad] if len(a) > 4 * pad else a)
    return np.concatenate(out)


def main():
    v = Voices(fallback="prova:im_nicola")
    parts = []
    for n, pieces in VARIANTI:
        parts += [v.say(n, "edge:it-IT-DiegoNeural", 1.0), np.zeros(int(0.7 * RATE), dtype=np.float32)]
        for voice in ("edge:it-IT-IsabellaNeural", "edge:it-IT-GiuseppeNeural"):
            first = PRIMA if not pieces[0].startswith("e ") else PRIMA[:-2]
            parts.append(v.say(first, voice, 0.92))
            parts.append(np.zeros(int(0.06 * RATE), dtype=np.float32))
            parts.append(glued(v, voice, pieces, 0.92))
            parts.append(np.zeros(int(1.0 * RATE), dtype=np.float32))
        parts.append(np.zeros(int(1.0 * RATE), dtype=np.float32))
    Path("out").mkdir(exist_ok=True)
    to_mp3(np.concatenate(parts), "out/prova-pronuncia.mp3", title="Prova pronuncia", artist="Get up and Walk",
           album="Prove")


if __name__ == "__main__":
    main()
