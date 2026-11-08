"""Dal modello (modello.yaml) e dal post del giorno alla sequenza di cose da dire e da suonare."""
import re
from dataclasses import dataclass

from .liturgia import day_name

BOOKS = {"Mt": "Matteo", "Mc": "Marco", "Lc": "Luca", "Gv": "Giovanni"}
PAUSE_RE = re.compile(r"\[\s*pausa(?:\s+(\d+(?:[.,]\d+)?|breve|media|lunga))?\s*(?:s|sec|secondi)?\s*\]", re.I)
PAUSE_WORDS = {"breve": 1.0, "media": 2.0, "lunga": 3.5}


def _pause_secs(m):
    v = (m.group(1) or "").lower()
    if not v:
        return 2.0
    return PAUSE_WORDS.get(v) or float(v.replace(",", "."))
QUOTE_RE = re.compile(r"(«[^»]{1,80}»|“[^”]{1,80}”|\"[^\"]{1,80}\"|‘[^’]{1,80}’)([.,;:!?]*)")


@dataclass
class Event:
    kind: str            # "speak", "pause" (con musica), "music", "gap" (breve silenzio)
    secs: float = 0.0
    text: str = ""
    voice: str = ""
    speed: float = 1.0
    section: str = ""
    bed: str = "accordo"     # quale musica di fondo: campane, accordo, liuto, giorno, nessuna
    vol: float = 1.0         # volume della musica in questo momento (0.5 = metà)
    ramp: float = 0.0        # secondi per arrivarci, sfumando
    ramp_out: float = 0.0    # secondi per uscirne, sfumando
    fixed: bool = False      # frase uguale tutti i giorni: si genera una volta e si riusa
    pitch: float = 0.0       # tono in percentuale (negativo = più grave)
    soft: bool = False       # voce ammorbidita
    gain: float = 1.0        # volume della voce (1 = come tutte le altre)


MESI = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
ROMANI = {"I": 1, "V": 5, "X": 10, "L": 50}


def _arabic(r):
    total, prev = 0, 0
    for ch in reversed(r):
        v = ROMANI[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def speakable(t):
    t = t.replace("*", "")
    # "X agosto" → "10 agosto" (si legge "dieci agosto", non "ics agosto")
    t = re.sub(r"\b([IVXL]{1,6})\s+(" + MESI + r")\b", lambda m: f"{_arabic(m.group(1).upper())} {m.group(2)}", t,
               flags=re.I)
    t = re.sub(r"\bSJ\b", "gesuita", t)
    t = re.sub(r"\b(Mt|Mc|Lc|Gv)\s*(\d+),\s*(\d+)(?:\s*[-–]\s*(\d+))?",
               lambda m: f"{BOOKS[m.group(1)]}, capitolo {m.group(2)}, versetti da {m.group(3)}"
                         + (f" a {m.group(4)}" if m.group(4) else ""), t)
    t = re.sub(r"[«»“”\"]", "", t).replace("‘", "")
    t = re.sub(r"\b(po|mo|di|de|be|to|va|fa|da|sta)’", r"\1'", t, flags=re.I)   # un po’, va’, di’: apostrofo vero
    t = re.sub(r"’(?=\w)", "'", t).replace("’", "")
    t = re.sub(r"([!?…])\s*\.", r"\1", t)          # «aprici!». → aprici!  (non due segni di fine frase)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(text, cfg, nl_pause=None, dot_pause=None):
    """Testo → pezzi da leggere e pause (a capo, [pausa], due punti, brevi citazioni con altro passo)."""
    p = cfg["pause"]
    nl = p["a_capo"]
    colon = (p["due_punti"], p.get("punto_e_virgola", 0.0), p.get("punto_esclamativo"), p.get("punto_interrogativo"))
    if nl_pause is not None:
        nl = float(nl_pause)
    out = []
    lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    for n, line in enumerate(lines):
        if n:
            out.append(("pause", nl))
        last = 0
        for m in PAUSE_RE.finditer(line):
            out += _refine(line[last:m.start()], colon, dot_pause)
            out.append(("pause", _pause_secs(m)))
            last = m.end()
        out += _refine(line[last:], colon, dot_pause)
    return out


def _refine(part, colon, dot_pause=None):
    out = []
    if dot_pause:                       # un respiro dopo ogni punto, anche senza andare a capo
        sentences = [s for s in re.split(r"(?<=[.!?…])[»”\"’)]*\s+", part.strip()) if s.strip()]
        if len(sentences) > 1:
            excl, quest = (colon[2], colon[3]) if isinstance(colon, tuple) and len(colon) > 3 else (None, None)
            for k, s in enumerate(sentences):
                out += _refine(s, colon)
                if k < len(sentences) - 1:
                    end = re.sub(r"[»”\"’)\s]+$", "", s)[-1:]
                    pause = excl if end == "!" else quest if end == "?" else None
                    out.append(("pause", float(dot_pause if pause is None else min(pause, dot_pause))))
            return out
    colon, semi = (colon[0], colon[1]) if isinstance(colon, tuple) else (colon, 0.0)
    pieces = re.split(r"(?<=[:;])\s+", part.strip())
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
            out.append(("pause", semi if piece.rstrip().endswith(";") else colon))
    return out


def apply_pronunciation(text, words):
    """Parole che la voce sbaglia: si scrivono come vanno lette (es. compratevene → compràtevene)."""
    for w, say in (words or {}).items():
        def keep_case(m, say=say):
            return say[:1].upper() + say[1:] if m.group(0)[:1].isupper() else say
        text = re.sub(r"\b" + re.escape(w) + r"\b", keep_case, text, flags=re.I)
    return text


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
        # "Giovanni Pascoli, San Lorenzo." → "Giovanni Pascoli, da San Lorenzo."
        "citazione_fonte_letta": re.sub(r",\s*(?!da\b)", ", da ", src, count=1) if "," in src else src,
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
    default_bed = model["musica"].get("fondo", "accordo")

    def fill(text, extra=None):
        vals = dict(values, **(extra or {}))
        return re.sub(r"\{(\w+)\}", lambda m: str(vals.get(m.group(1), m.group(0))), str(text))

    def add_items(items, section, sec_bed, extra=None):
        for it in items:
            if "per_ogni_domanda" in it:
                for qi, q in enumerate(values["domande"]):
                    add_items(it["per_ogni_domanda"], section, sec_bed, {"domanda": q, "_n": qi})
                continue
            bed = it.get("fondo", sec_bed)
            vol = float(it.get("volume_musica", 1.0))
            r_in = float(it.get("sfumatura_entrata", it.get("sfumatura", 0.0)))
            r_out = float(it.get("sfumatura_uscita", it.get("sfumatura", 0.0)))
            if "pausa" in it or "musica" in it:
                kind, secs = ("pause", it["pausa"]) if "pausa" in it else ("music", it["musica"])
                events.append(Event(kind, secs=float(secs), section=section, bed=bed, vol=vol, ramp=r_in, ramp_out=r_out))
                continue
            who = next((k for k in ("coro_grande", "coro_piccolo", "M|F", "F|M", "MF", "M", "F") if k in it), None)
            if not who:
                continue
            # fissa = senza parti che cambiano ogni giorno (l'evangelista sono solo quattro)
            fixed = "|" not in who and set(re.findall(r"\{(\w+)\}", str(it[who]))) <= {"evangelista"}
            text = fill(it[who], extra).strip()
            if "|" in who:                      # voci alternate: una domanda ciascuno
                who = who.split("|")[(extra or {}).get("_n", 0) % 2]
            if not text or re.search(r"\{\w+\}", text):
                continue
            if who.startswith("coro"):
                voice = "coro:" + "|".join(voices.get(who) or [voices["struttura"], voices["contenuti"]])
            else:
                voice = {"M": voices["struttura"], "F": voices["contenuti"],
                         "MF": voices["struttura"] + "|" + voices["contenuti"]}[who]
            speed = base * float(it.get("velocita", 1.0))
            text = apply_pronunciation(text, model.get("pronuncia"))
            if it.get("di_seguito"):
                # tutto in una sola lettura, con un breve respiro a fine riga: l'intonazione resta continua
                t = " ⟦pausa⟧ ".join(speakable(r) for r in text.split("\n") if r.strip())
                events.append(Event("speak", text=t, voice=voice, speed=speed, section=section, bed=bed, vol=vol,
                                    fixed=fixed, pitch=float(it.get("tono", 0)), soft=bool(it.get("morbido")),
                                    gain=float(it.get("volume_voce", 1.0))))
                events.append(Event("gap", secs=float(model.get("pause", {}).get("a_capo", 1.2)), section=section,
                                    bed=bed, vol=vol))
                continue
            # "crescendo: [2, 4, 8, 12, 16]": il coro si allarga riga dopo riga (l'ultimo numero vale per il resto)
            grow = it.get("crescendo") if who.startswith("coro") else None
            line = 0
            for tok in _tokens(text, model, it.get("pausa_a_capo"), it.get("pausa_punto")):
                if tok[0] == "pause":
                    events.append(Event("gap", secs=tok[1], section=section, bed=bed, vol=vol))
                else:
                    t = speakable(tok[1])
                    if t and re.search(r"\w", t):
                        if grow:
                            names = voices.get(who) or [voices["struttura"], voices["contenuti"]]
                            voice = "coro:" + "|".join(names[:max(1, int(grow[min(line, len(grow) - 1)]))])
                            line += 1
                        # le brevi citazioni rallentano un poco, ma mai troppo
                        sp = max(speed * tok[2], min(speed, 0.85))
                        for j, piece in enumerate(re.split(r"\|(?![^⟦]*⟧)", t)):      # "comprà|tevene": pezzi incollati
                            if j:
                                events.append(Event("gap", secs=0.0, section=section, bed=bed, vol=vol))
                            if piece.strip():
                                events.append(Event("speak", text=piece.strip(), voice=voice, speed=sp,
                                                    section=section, bed=bed, vol=vol, fixed=fixed,
                                                    pitch=float(it.get("tono", 0)), soft=bool(it.get("morbido")),
                                                    gain=float(it.get("volume_voce", 1.0))))
            events.append(Event("gap", secs=max(0.45, nl), section=section, bed=bed, vol=vol))

    for sec in model["scaletta"]:
        cond = sec.get("se")
        if cond and not values.get(CONDITIONS.get(cond, cond)):
            continue
        add_items(sec.get("elementi", []), sec["sezione"], sec.get("fondo", default_bed))

    # niente silenzio doppio prima di una pausa o di un momento di musica
    cleaned = []
    for ev in events:
        if ev.kind in ("pause", "music") and cleaned and cleaned[-1].kind == "gap":
            cleaned.pop()
        cleaned.append(ev)
    return cleaned
