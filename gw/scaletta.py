"""Dal modello (modello.yaml) e dal post del giorno alla sequenza di cose da dire e da suonare."""
import re
from dataclasses import dataclass

from .liturgia import day_name

BOOKS = {"Mt": "Matteo", "Mc": "Marco", "Lc": "Luca", "Gv": "Giovanni"}
PAUSE_RE = re.compile(r"\[\s*pausa(?:\s+(\d+(?:[.,]\d+)?))?\s*(?:s|sec|secondi)?\s*\]", re.I)
QUOTE_RE = re.compile(r"(«[^»]{1,80}»|“[^”]{1,80}”|\"[^\"]{1,80}\"|‘[^’]{1,80}’)([.,;:!?]*)")


@dataclass
class Event:
    kind: str            # "speak", "pause" (con musica), "music", "gap" (breve silenzio)
    secs: float = 0.0
    text: str = ""
    voice: str = ""
    speed: float = 1.0
    section: str = ""


def speakable(t):
    t = t.replace("*", "")
    t = re.sub(r"\bSJ\b", "gesuita", t)
    t = re.sub(r"\b(Mt|Mc|Lc|Gv)\s*(\d+),\s*(\d+)(?:\s*[-–]\s*(\d+))?",
               lambda m: f"{BOOKS[m.group(1)]}, capitolo {m.group(2)}, versetti da {m.group(3)}"
                         + (f" a {m.group(4)}" if m.group(4) else ""), t)
    t = re.sub(r"[«»“”\"]", "", t).replace("‘", "")
    t = re.sub(r"’(?=\w)", "'", t).replace("’", "")
    return re.sub(r"\s+", " ", t).strip()


def _tokens(text, cfg):
    """Testo → pezzi da leggere e pause (a capo, [pausa], due punti, brevi citazioni con altro passo)."""
    nl, colon = cfg["pause"]["a_capo"], cfg["pause"]["due_punti"]
    out = []
    lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    for n, line in enumerate(lines):
        if n:
            out.append(("pause", nl))
        last = 0
        for m in PAUSE_RE.finditer(line):
            out += _refine(line[last:m.start()], colon)
            out.append(("pause", float(m.group(1).replace(",", ".")) if m.group(1) else 2.0))
            last = m.end()
        out += _refine(line[last:], colon)
    return out


def _refine(part, colon):
    out = []
    pieces = re.split(r"(?<=:)\s+", part.strip())
    for i, piece in enumerate(pieces):
        last = 0
        for m in QUOTE_RE.finditer(piece):
            words = len(re.sub(r"[«»“”\"‘’]", "", m.group(1)).split())
            if words > 6:
                continue
            if piece[last:m.start()].strip():
                out.append(("say", piece[last:m.start()].strip(), 1.0))
            out.append(("say", m.group(0), 0.9))
            last = m.end()
        if piece[last:].strip():
            out.append(("say", piece[last:].strip(), 1.0))
        if i < len(pieces) - 1 and piece.strip():
            out.append(("pause", colon))
    return out


def fill_values(post, liturgia):
    gospel, comm, dom = post.section("testo"), post.section("ispira"), post.section("domande")
    sec_text = lambda k: "\n".join(post.section(k).paras) if post.section(k) else ""
    src = post.quote_source.strip()
    if src and not src.endswith((".", "!", "?")):
        src += "."
    return {
        "giorno": day_name(post.day),
        "liturgia": liturgia,
        "titolo": post.title,
        "autore": post.author,
        "evangelista": post.evangelist,
        "vangelo": "\n".join(p.replace("\n", " ") for p in gospel.paras) if gospel else "",
        "commento": "\n".join(p.replace("\n", " ") for p in comm.paras) if comm else "",
        "domande": [p.replace("\n", " ") for p in dom.paras] if dom else [],
        "citazione": "\n".join(post.quote_lines),
        "citazione_fonte": src,
        "mi_preparo_post": sec_text("prep"),
        "immagino_post": sec_text("immagino"),
        "ringrazio_post": sec_text("ringrazio"),
    }


CONDITIONS = {"citazione": "citazione", "vangelo": "vangelo", "commento": "commento", "domande": "domande"}


def build_events(model, values):
    voices = model["voci"]
    base = float(voices.get("velocita", 1.0))
    nl = float(model["pause"]["a_capo"])
    events = []

    def fill(text, extra=None):
        vals = dict(values, **(extra or {}))
        return re.sub(r"\{(\w+)\}", lambda m: str(vals.get(m.group(1), m.group(0))), str(text))

    def add_items(items, section, extra=None):
        for it in items:
            if "per_ogni_domanda" in it:
                for q in values["domande"]:
                    add_items(it["per_ogni_domanda"], section, {"domanda": q})
                continue
            if "pausa" in it:
                events.append(Event("pause", secs=float(it["pausa"]), section=section))
                continue
            if "musica" in it:
                events.append(Event("music", secs=float(it["musica"]), section=section))
                continue
            who = "M" if "M" in it else "F" if "F" in it else None
            if not who:
                continue
            text = fill(it[who], extra).strip()
            if not text or re.search(r"\{\w+\}", text):
                continue
            voice = voices["struttura"] if who == "M" else voices["contenuti"]
            speed = base * float(it.get("velocita", 1.0))
            for tok in _tokens(text, model):
                if tok[0] == "pause":
                    events.append(Event("gap", secs=tok[1], section=section))
                else:
                    t = speakable(tok[1])
                    if t:
                        events.append(Event("speak", text=t, voice=voice, speed=speed * tok[2], section=section))
            events.append(Event("gap", secs=max(0.45, nl), section=section))

    for sec in model["scaletta"]:
        cond = sec.get("se")
        if cond and not values.get(CONDITIONS.get(cond, cond)):
            continue
        add_items(sec.get("elementi", []), sec["sezione"])

    # niente silenzio doppio prima di una pausa o di un momento di musica
    cleaned = []
    for ev in events:
        if ev.kind in ("pause", "music") and cleaned and cleaned[-1].kind == "gap":
            cleaned.pop()
        cleaned.append(ev)
    return cleaned
