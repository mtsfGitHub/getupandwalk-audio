"""Prova di lettura: modi diversi di tenere insieme due parole ("Padre mio") come un'unica unità di senso."""
from pathlib import Path

import numpy as np

from gw.montaggio import to_mp3
from gw.voce import RATE, Voices

FRASE = "Portate via di qui queste cose e non fate della casa del {} un mercato!"
VARIANTI = [("Uno, normale.", "Padre mio"),
            ("Due, spazio unito.", "Padre mio"),
            ("Tre, con il trattino.", "Padre-mio"),
            ("Quattro, senza confine.", "Padre ⟦unito⟧mio"),
            ("Cinque, attaccato.", "Padremio")]
VOCI = ["azure:it-IT-GiuseppeMultilingualNeural", "azure:it-IT-Isabella:DragonLatestNeural"]


def gap(s):
    return np.zeros(int(s * RATE), dtype=np.float32)


def main():
    v = Voices(fallback="prova:im_nicola")
    parts = []
    for title, words in VARIANTI:
        parts += [v.say(title, VOCI[0], 1.0), gap(0.8)]
        for voice in VOCI:
            try:
                parts += [v.say(FRASE.format(words), voice, 0.92), gap(1.2)]
            except Exception as e:
                print("salto", title, voice, e)
        parts.append(gap(1.0))
    if v.broken:
        print("ATTENZIONE: voci di riserva usate", v.broken)
    Path("out").mkdir(exist_ok=True)
    to_mp3(np.concatenate(parts), "out/prova-padre-mio.mp3", title="Prova: Padre mio", artist="Get up and Walk",
           album="Prove")


if __name__ == "__main__":
    main()
