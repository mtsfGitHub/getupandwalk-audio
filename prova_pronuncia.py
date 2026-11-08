"""Prova di pronuncia: la stessa frase scritta in modi diversi, numerati, per scegliere quello giusto."""
from pathlib import Path

import numpy as np

from gw.montaggio import to_mp3
from gw.voce import RATE, Voices

FRASE = "Andate piuttosto dai venditori e {}."
VARIANTI = [
    "⟦ipa:komˈpratevene|compratevene⟧",
    "compra tevene",
    "compràte vene",
    "comprà-tevene",
]
NUMERI = ["Uno.", "Due.", "Tre.", "Quattro."]


def main():
    v = Voices(fallback="prova:im_nicola")
    parts = []
    for n, var in zip(NUMERI, VARIANTI):
        parts.append(v.say(n, "edge:it-IT-DiegoNeural", 1.0))
        parts.append(np.zeros(int(0.7 * RATE), dtype=np.float32))
        for voce in ("edge:it-IT-IsabellaNeural", "edge:it-IT-GiuseppeNeural"):
            try:
                parts.append(v.engines.setdefault("edge", __import__("gw.voce", fromlist=["EdgeEngine"]).EdgeEngine())
                             .say(FRASE.format(var), voce.split(":")[1], 0.92))
            except Exception as e:
                print("variante", n, voce, "non accettata:", e)
                parts.append(v.say("Questa versione non funziona.", "edge:it-IT-DiegoNeural", 1.0))
            parts.append(np.zeros(int(0.9 * RATE), dtype=np.float32))
        parts.append(np.zeros(int(1.2 * RATE), dtype=np.float32))
    Path("out").mkdir(exist_ok=True)
    to_mp3(np.concatenate(parts), "out/prova-pronuncia.mp3", title="Prova pronuncia", artist="Get up and Walk",
           album="Prove")


if __name__ == "__main__":
    main()
