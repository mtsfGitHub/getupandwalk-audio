"""Confronto delle voci italiane di Azure: tutte leggono lo stesso brano (dal Vangelo dell'8 novembre).

Uso: python campioni_azure.py   → out/campioni-azure/*.mp3   (servono AZURE_SPEECH_KEY e AZURE_SPEECH_REGION)
"""
import re
from pathlib import Path

import numpy as np

from gw.montaggio import to_mp3
from gw.voce import RATE, AzureEngine, _trim

TEXT = [
    "Mi preparo.",
    "Chiudo gli occhi, libero la mente da preoccupazioni e pensieri, mi concentro sul momento presente.",
    "In quel tempo, Gesù disse ai suoi discepoli questa parabola: «Il regno dei cieli sarà simile a dieci "
    "vergini che presero le loro lampade e uscirono incontro allo sposo.",
    "A mezzanotte si alzò un grido: «Ecco lo sposo! Andategli incontro!».",
    "Andate piuttosto dai venditori e ⟦ipa:komˈpratevene|compratevene⟧.",
    "Quale parola o frase, cattura la mia attenzione in modo particolare?",
]


def silence(s):
    return np.zeros(int(s * RATE), dtype=np.float32)


def main():
    az = AzureEngine()
    voices = [v for v in az.voices() if v.get("Locale") == "it-IT"]
    voices.sort(key=lambda v: (v.get("Gender", ""), "DragonHD" not in v["ShortName"], v["ShortName"]))
    print(len(voices), "voci italiane:", ", ".join(v["ShortName"] for v in voices))
    out = Path("out/campioni-azure")
    out.mkdir(parents=True, exist_ok=True)
    every = {"Female": [], "Male": []}
    for v in voices:
        short = v["ShortName"]
        name = re.sub(r"(Multilingual)?Neural$", "", short.split("-", 2)[-1]).replace(":DragonHDLatest", " HD")
        name = name.replace(":", " ")
        try:
            parts = [_trim(az.say(f"Sono {name}.", short, 1.0)), silence(0.8)]
            for line in TEXT:
                parts += [_trim(az.say(line, short, 0.92)), silence(0.9)]
        except Exception as e:
            print("salto", short, e)
            continue
        a = np.concatenate(parts)
        g = "donne" if v.get("Gender") == "Female" else "uomini"
        to_mp3(a, out / f"{g}-{re.sub(r'[^A-Za-z0-9]+', '-', name)}.mp3", title=short,
               artist="Get up and Walk", album="Campioni Azure")
        every.setdefault(v.get("Gender"), []).extend([a, silence(1.5)])
        print("fatto:", short)
    for gender, label in (("Male", "uomini"), ("Female", "donne")):
        if every.get(gender):
            to_mp3(np.concatenate(every[gender]), out / f"0-tutti-{label}.mp3", title=f"Voci Azure: {label}",
                   artist="Get up and Walk", album="Campioni Azure")
    print("Caratteri usati:", az.chars)


if __name__ == "__main__":
    main()
