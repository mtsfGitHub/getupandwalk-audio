"""Collegamento con il pannello di controllo (l'app in Claude).

  python pannello.py esporta 2026-11-07 > pannello.json
      La scaletta del giorno, costruita dal modello, nel formato del pannello.
  python pannello.py applica pannello.json
      Riporta nel modello (modello.yaml) le modifiche fatte nel pannello.
"""
import json
import re
import sys
import uuid
from pathlib import Path

import yaml

from gw.liturgia import MONTHS, computed
from gw.post import Post, Section
from gw.scaletta import fill_values

VOICE = {"M": "struct", "F": "content", "MF": "both"}
WHO = {v: k for k, v in VOICE.items()}


def uid():
    return uuid.uuid4().hex[:7]


def load_post(day):
    d = json.loads(Path(f"docs/posts/{day}.json").read_text("utf-8"))
    from datetime import date
    post = Post(day=date.fromisoformat(d["day"]), url=d["url"])
    for k in ("title", "ref", "author", "author_url", "image", "caption", "quote_lines", "quote_source"):
        setattr(post, k, d.get(k, ""))
    post.sections = [Section(**s) for s in d["sections"]]
    return post


def raw_text(post):
    lines = [f"{post.day.day} {MONTHS[post.day.month - 1]} {post.day.year}", post.title,
             f"commento di {post.ref}, a cura di {post.author}"]
    if post.caption:
        lines.append(post.caption)
    if post.quote_lines:
        lines += post.quote_lines + [post.quote_source]
    for s in post.sections:
        lines.append(f"{s.label} ({s.ref})" if s.ref else s.label)
        lines += [p for p in s.paras]
    return "\n".join(lines)


def export(day):
    model = yaml.safe_load(Path("modello.yaml").read_text("utf-8"))
    post = load_post(day)
    values = fill_values(post, computed(post.day))
    fix = Path(f"correzioni/{day}.yaml")
    if fix.exists():
        values.update(yaml.safe_load(fix.read_text("utf-8")) or {})
    fill = lambda t, extra=None: re.sub(r"\{(\w+)\}", lambda m: str(dict(values, **(extra or {})).get(m.group(1), m.group(0))), str(t))
    sections = []
    for sec in model["scaletta"]:
        cond = sec.get("se")
        if cond and not values.get(cond):
            continue
        out = {"id": uid(), "label": sec["sezione"], "ref": "", "se": cond or "", "fondo": sec.get("fondo", ""),
               "items": []}
        if sec["sezione"] == "Entro nel testo":
            out["ref"] = post.ref

        def add(el, extra=None, grp=None, qi=None):
            item = None
            if "pausa" in el:
                item = {"id": uid(), "kind": "pause", "secs": el["pausa"]}
            elif "musica" in el:
                item = {"id": uid(), "kind": "music", "secs": el["musica"]}
            else:
                who = next((k for k in ("coro_grande", "coro_piccolo", "M|F", "F|M", "MF", "M", "F") if k in el), None)
                if not who:
                    return
                tpl = str(el[who])
                alt = who if "|" in who else ""
                if alt:
                    who = alt.split("|")[(extra or {}).get("_n", 0) % 2]
                text = fill(tpl, extra).strip()
                if not text or re.search(r"\{\w+\}", text):
                    return
                cls = "gospel" if "{vangelo}" in tpl else "quote" if "{citazione}" in tpl else ""
                item = {"id": uid(), "kind": "say", "voice": VOICE.get(who, "both"), "text": text, "tpl": tpl, "orig": text,
                        "cls": cls, "show": text.rstrip(".") != sec["sezione"], "rateMul": float(el.get("velocita", 1))}
            if "fondo" in el:
                item["fondo"] = el["fondo"]
            if "pausa_a_capo" in el:
                item["nlp"] = el["pausa_a_capo"]
            for k, f in (("pausa_punto", "dotp"), ("volume_musica", "mvol"), ("sfumatura", "ramp"),
                         ("sfumatura_entrata", "rin"), ("sfumatura_uscita", "rout")):
                if k in el:
                    item[f] = el[k]
            if item.get("kind") == "say" and who.startswith("coro"):
                item["coro"] = who
                if "crescendo" in el:
                    item["grow"] = el["crescendo"]
            extra = {k: el[k] for k in ("tono", "morbido", "volume_voce", "di_seguito") if k in el}
            if extra and item.get("kind") == "say":
                item["extra"] = extra
            if item.get("kind") == "say" and alt:
                item["alt"] = alt
            if grp:
                item["grp"], item["qi"] = grp, qi
            out["items"].append(item)

        for el in sec.get("elementi", []):
            if "per_ogni_domanda" in el:
                for qi, q in enumerate(values["domande"]):
                    for sub in el["per_ogni_domanda"]:
                        add(sub, {"domanda": q, "_n": qi}, "domande", qi)
            else:
                add(el)
        sections.append(out)
    key = f"{post.title}|{post.ref}".lower()
    prog = {"key": key, "edited": True, "sections": sections}
    return {"raw": raw_text(post), "prog": prog, "base": prog, "day": day}


class Block(str):
    pass


def _block(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


def apply(path):
    doc = json.loads(Path(path).read_text("utf-8"))
    doc = doc.get("data", doc)
    prog = doc["prog"]
    notes, scaletta = [], []
    for sec in prog["sections"]:
        out = {"sezione": sec.get("label") or "Senza titolo"}
        se = sec.get("se") or ""
        items = sec.get("items", [])
        if not se:
            tpls = " ".join(i.get("tpl", "") for i in items)
            se = ("vangelo" if "{vangelo}" in tpls else "commento" if "{commento}" in tpls else
                  "citazione" if "{citazione" in tpls else "domande" if any(i.get("grp") for i in items) else "")
        if se:
            out["se"] = se
        if sec.get("fondo"):
            out["fondo"] = sec["fondo"]
        els, done_group = [], False
        for it in items:
            if it.get("grp") == "domande":
                if done_group:
                    continue
                done_group = True
                qs = sorted((x for x in items if x.get("grp") == "domande" and x.get("kind") == "say"
                             and "{domanda}" in (x.get("tpl") or "")), key=lambda x: x.get("qi", 0))
                if any((x.get("text") or "").strip() != x.get("orig") for x in qs):
                    CORRECTIONS["domande"] = [(x.get("text") or "").strip() for x in qs]
                first = [x for x in items if x.get("grp") == "domande" and x.get("qi") == 0]
                second = [x for x in items if x.get("grp") == "domande" and x.get("qi") == 1]
                sub = []
                for j, x in enumerate(first):
                    el = convert(x, notes)
                    if not el:
                        continue
                    y = second[j] if j < len(second) else None
                    k = next((k for k in ("M", "F") if k in el), None)
                    if k and y is not None and y.get("kind") == "say" and y.get("voice") != x.get("voice") \
                            and y.get("voice") in ("struct", "content"):
                        el = {(k + "|" + ("F" if k == "M" else "M")): el.pop(k), **el}
                    sub.append(el)
                els.append({"per_ogni_domanda": sub})
                continue
            el = convert(it, notes)
            if el:
                els.append(el)
        out["elementi"] = els
        scaletta.append(out)

    # Vangelo e commento: gli a capo che erano paragrafi del post tornano paragrafi (riga vuota),
    # quelli aggiunti a mano restano a capo semplici
    day = doc.get("day")
    if day and Path(f"docs/posts/{day}.json").exists():
        orig = fill_values(load_post(day), "")
        for k in ("vangelo", "commento"):
            if k in CORRECTIONS and "\n\n" not in CORRECTIONS[k] and "\n\n" in orig.get(k, ""):
                CORRECTIONS[k] = _paragraphs(orig[k], CORRECTIONS[k])

    text = Path("modello.yaml").read_text("utf-8")
    head = text[:text.index("\nscaletta:") + 1]
    Path("modello.yaml").write_text(head + write_scaletta(scaletta), "utf-8")
    if CORRECTIONS:
        day = doc.get("day") or "oggi"
        Path("correzioni").mkdir(exist_ok=True)
        Path(f"correzioni/{day}.yaml").write_text(
            "# Correzioni fatte a mano nel pannello, valgono solo per questo giorno\n"
            + yaml.dump(CORRECTIONS, allow_unicode=True, sort_keys=False, width=10000), "utf-8")
        print(f"Correzioni del giorno salvate in correzioni/{day}.yaml: " + ", ".join(CORRECTIONS))
    for n in notes:
        print("Nota:", n)


def _q(v):
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _num(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


def _element(el, ind):
    """Un elemento nello stesso stile del modello scritto a mano."""
    lines, first = [], True
    for k, v in el.items():
        lead = ind + ("- " if first else "  ")
        first = False
        if k == "per_ogni_domanda":
            lines.append(f"{lead}per_ogni_domanda:")
            for sub in v:
                lines += _element(sub, ind + "    ")
        elif isinstance(v, bool):
            lines.append(f"{lead}{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{lead}{k}: {_num(v)}")
        elif isinstance(v, list):
            lines.append(f"{lead}{k}: [" + ", ".join(_num(x) for x in v) + "]")
        elif "\n" in str(v):
            lines.append(f"{lead}{k}: |-")
            lines += [ind + "    " + l for l in str(v).split("\n")]
        else:
            lines.append(f"{lead}{k}: {v if k == 'fondo' else _q(v)}")
    return lines


def write_scaletta(scaletta):
    out = ["scaletta:"]
    for i, sec in enumerate(scaletta):
        if i:
            out.append("")
        out.append(f"  - sezione: {sec['sezione']}")
        for k in ("se", "fondo"):
            if sec.get(k):
                out.append(f"    {k}: {sec[k]}")
        out.append("    elementi:")
        for el in sec["elementi"]:
            out += _element(el, "      ")
    return "\n".join(out) + "\n"


CORRECTIONS = {}


def _paragraphs(orig, new):
    import difflib
    o = orig.replace("\n\n", "\n")
    sm = difflib.SequenceMatcher(None, o, new, autojunk=False)
    para = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            para.update(j1 + k for k in range(i2 - i1) if o[i1 + k] == "\n")
    return "".join("\n\n" if c == "\n" and j in para else c for j, c in enumerate(new))


def _extract(tpl, text):
    """Dal testo corretto nel pannello ricava i valori dei segnaposto (es. {citazione})."""
    names = re.findall(r"\{(\w+)\}", tpl)
    if not names or "domanda" in names:
        return None
    pattern = "^" + re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.+?)", re.escape(tpl)) + "$"
    m = re.match(pattern, text.strip(), re.S)
    return {k: re.sub(r"[ \t]{2,}", " ", v).strip() for k, v in m.groupdict().items()} if m else None


def convert(it, notes):
    kind = it.get("kind")
    if kind in ("pause", "music"):
        el = {"pausa" if kind == "pause" else "musica": round(float(it.get("secs", 0)), 1)}
        if it.get("mvol") is not None:
            el["volume_musica"] = it["mvol"]
        if it.get("ramp") is not None:
            el["sfumatura"] = it["ramp"]
        if it.get("rin") is not None:
            el["sfumatura_entrata"] = it["rin"]
        if it.get("rout") is not None:
            el["sfumatura_uscita"] = it["rout"]
        if it.get("fondo"):
            el["fondo"] = it["fondo"]
        return el
    if kind != "say":
        return None
    who = it["coro"] if it.get("coro") and it.get("voice") == "both" else WHO.get(it.get("voice"), "F")
    tpl, text = it.get("tpl"), (it.get("text") or "").strip()
    if not text:
        return None
    if tpl and re.search(r"\{\w+\}", tpl):
        if text != it.get("orig") and "{domanda}" not in tpl:
            found = _extract(tpl, text)
            if found:
                CORRECTIONS.update(found)
            else:
                notes.append(f"testo del giorno modificato ma non riconosciuto: {text[:60]}…")
        value = tpl
    else:
        value = text
    el = {who: value}
    if abs(float(it.get("rateMul", 1)) - 1) > 0.001:
        el["velocita"] = round(float(it["rateMul"]), 2)
    if it.get("nlp") is not None:
        el["pausa_a_capo"] = it["nlp"]
    if it.get("dotp") is not None:
        el["pausa_punto"] = it["dotp"]
    if it.get("grow") and str(who).startswith("coro"):
        el["crescendo"] = it["grow"]
    for k, v in (it.get("extra") or {}).items():
        el[k] = v
    if it.get("fondo"):
        el["fondo"] = it["fondo"]
    return el


if __name__ == "__main__":
    if sys.argv[1] == "esporta":
        print(json.dumps(export(sys.argv[2]), ensure_ascii=False))
    elif sys.argv[1] == "applica":
        apply(sys.argv[2])
