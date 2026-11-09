"""Chi legge il commento segue chi l'ha scritto: autore uomo → il commento lo legge la voce maschile;
autrice donna → la voce femminile, e tutto lo schema si rovescia (anche la struttura e il Padre nostro)."""
import re

FEMMINILI = {
    "mounira", "donatella", "verena", "gloria", "giovanna", "maria", "anna", "chiara", "francesca", "paola",
    "elena", "silvia", "laura", "marta", "lucia", "teresa", "rosa", "cristina", "monica", "barbara", "sara",
    "giulia", "federica", "valentina", "alessandra", "beatrice", "caterina", "agnese", "irene", "miriam", "ruth",
    "ester", "rachele", "agata", "cecilia", "clara", "carmen", "nadia", "noemi", "simona", "stefania", "tiziana",
    "manuela", "daniela", "roberta", "patrizia", "michela", "emanuela", "letizia", "suor", "sr", "madre",
}
MASCHILI_IN_A = {"andrea", "luca", "nicola", "mattia", "elia", "enea", "battista", "tobia", "gianluca", "zaccaria",
                 "geremia", "isaia", "giona", "evangelista", "costa", "sava"}


def gender(author, overrides=None):
    """'M' o 'F' dal nome dell'autore. 'autori' nel modello corregge i casi sbagliati."""
    author = (author or "").strip()
    for name, g in (overrides or {}).items():
        if name.lower() == author.lower():
            return str(g).upper()[:1]
    low = author.lower()
    if re.search(r"\b(s\.?\s?j\.?|p\.|padre|don|fr\.|fra|frate|mons\.?)(\s|$)", low):
        return "M"
    words = [w for w in re.split(r"[\s,.]+", low) if w]
    if not words:
        return "M"
    first = words[0]
    if first in FEMMINILI:
        return "F"
    if first in MASCHILI_IN_A:
        return "M"
    return "F" if first.endswith("a") else "M"


def apply(model, author, override=None):
    """Scambia le due voci del modello se l'autore è una donna. Restituisce 'M' o 'F'."""
    v = model["voci"]
    g = (override or "").upper()[:1] or gender(author, model.get("autori"))
    if g == "F" and v.get("secondo_autore", True):
        v["struttura"], v["contenuti"] = v["contenuti"], v["struttura"]
    return g
