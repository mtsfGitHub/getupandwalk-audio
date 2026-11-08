"""Controlla se Azure ha nuove voci italiane rispetto all'elenco salvato (voci-azure.txt).

Scrive l'elenco aggiornato e, se ci sono novità, out/nuove-voci.md (testo dell'avviso).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from gw.voce import AzureEngine  # noqa: E402

known_file = pathlib.Path("voci-azure.txt")
known = set(known_file.read_text().split()) if known_file.exists() else set()
now = sorted(v["ShortName"] for v in AzureEngine().voices() if v.get("Locale") == "it-IT")
new = [v for v in now if v not in known]
gone = sorted(known - set(now))
known_file.write_text("\n".join(now) + "\n")
print(len(now), "voci italiane;", "nuove:", new or "nessuna", "; sparite:", gone or "nessuna")
if new or gone:
    out = pathlib.Path("out"); out.mkdir(exist_ok=True)
    lines = []
    if new:
        lines += ["Su Azure ci sono **nuove voci italiane**:", ""] + [f"- {v}" for v in new] + [""]
    if gone:
        lines += ["Queste voci **non ci sono più**:", ""] + [f"- {v}" for v in gone] + [""]
    lines += ["I campioni si stanno rifacendo con tutte le voci: tra qualche minuto si ascoltano su "
              "https://mtsfgithub.github.io/getupandwalk-audio/campioni/", "",
              "Per provarne una nella preghiera, scrivilo a Claude."]
    (out / "nuove-voci.md").write_text("\n".join(lines) + "\n")
