"""Crea l'audio di Get up and Walk per un giorno.

Uso:  python build.py                 → oggi (ora italiana)
      python build.py --data 2026-11-07
      python build.py --voce prova    → toni al posto delle voci, per provare il montaggio
"""
import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from gw import sito
from gw.liturgia import liturgical_day
from gw.montaggio import render, to_mp3
from gw.post import fetch_post, parse_post
from gw.scaletta import build_events, fill_values
from gw.voce import make_voice


NAMES = {"it-IT-DiegoNeural": "Diego", "it-IT-ElsaNeural": "Elsa", "it-IT-IsabellaNeural": "Isabella",
         "it-IT-GiuseppeNeural": "Giuseppe", "im_nicola": "Nicola", "if_sara": "Sara"}


def _person(spec):
    """edge:it-IT-GiuseppeNeural → Giuseppe; azure:it-IT-Alessio:DragonLatestNeural → Alessio"""
    n = spec.split(":", 1)[-1]
    m = re.match(r"[a-z]{2}-[A-Z]{2}-([A-Za-z]+?)(Multilingual)?(Neural)?(:|$)", n)
    return NAMES.get(n, m.group(1) if m else n)


def voices_label(model, voice):
    specs = [model["voci"]["struttura"], model["voci"]["contenuti"]]
    if any(s.split(":")[0] in voice.broken for s in specs if ":" in s):
        specs = [voice._reserve(s.split(":")[0], s.split(":", 1)[-1]) for s in specs]
    names = []
    for s in specs:
        n = _person(s)
        if n not in names:
            names.append(n)
    kind = specs[0].split(":")[0] if ":" in specs[0] else "kokoro"
    engine = {"edge": "Microsoft Edge", "azure": "Microsoft Azure", "kokoro": "Kokoro"}.get(kind, kind.capitalize())
    return " e ".join(names) + f", {engine}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="")
    ap.add_argument("--voce", default="kokoro", choices=["kokoro", "prova"])
    ap.add_argument("--html", help="file HTML del post già scaricato (per le prove)")
    ap.add_argument("--no-sito", action="store_true", help="non aggiornare la pagina e il feed")
    ap.add_argument("--contenuti", default="", help="prova con un'altra voce femminile (es. azure:it-IT-FabiolaNeural)")
    ap.add_argument("--struttura", default="", help="prova con un'altra voce maschile")
    ap.add_argument("--modello", default="modello.yaml", help="un altro modello, per una prova")
    args = ap.parse_args()

    day = date.fromisoformat(args.data) if args.data.strip() else datetime.now(ZoneInfo("Europe/Rome")).date()
    model = yaml.safe_load(Path(args.modello or "modello.yaml").read_text("utf-8"))
    for role in ("contenuti", "struttura"):          # prova con un'altra voce: niente parti fisse
        if getattr(args, role):
            model["voci"][role] = getattr(args, role)
            model["parti_fisse"] = False

    print(f"Giorno: {day:%d/%m/%Y}")
    if args.html:
        post = parse_post(Path(args.html).read_text("utf-8"), day, "https://getupandwalk.gesuiti.it/")
    else:
        try:
            post = fetch_post(day)
        except RuntimeError as e:
            if "Nessun post" in str(e):
                print(f"{e}: forse non è ancora uscito.")
                return 3
            raise
    print(f"Post: {post.title} — {post.ref} — {post.author}\n  {post.url}")
    print("Sezioni trovate: " + ", ".join(f"{s.label} ({len(s.paras)})" for s in post.sections))
    if post.quote_lines:
        print(f"Citazione: {post.quote_source}")

    liturgia, origine = liturgical_day(day)
    print(f"Liturgia ({origine}): {liturgia}")

    values = fill_values(post, liturgia)
    fix = Path(f"correzioni/{day:%Y-%m-%d}.yaml")
    if fix.exists():                       # correzioni a mano per quel giorno (dal pannello)
        corr = yaml.safe_load(fix.read_text("utf-8")) or {}
        values.update(corr)
        print("Correzioni del giorno: " + ", ".join(corr))
    from gw.autore import apply as voices_for_author
    g = voices_for_author(model, post.author, values.get("voce_autore"))
    print(f"Autore: {post.author} ({'donna' if g == 'F' else 'uomo'}) → commento letto da "
          f"{model['voci']['contenuti']}, struttura {model['voci']['struttura']}")
    events = build_events(model, values)
    current = None
    for ev in events:
        if ev.section != current:
            current = ev.section
            print(f"\n== {current}")
        if ev.kind == "speak":
            who = (f"CORO{len(ev.voice.split('|'))}" if ev.voice.startswith("coro:") else "MF" if "|" in ev.voice
                   else "M" if ev.voice == model["voci"]["struttura"] else "F")
            print(f"  [{who} x{ev.speed:.2f}] {ev.text[:90]}{'…' if len(ev.text) > 90 else ''}")
        elif ev.kind != "gap":
            print(f"  <{ev.kind} {ev.secs:g} s>")

    print("\nGenero le voci…")
    voice = make_voice(args.voce, model["voci"].get("riserva", "im_nicola"))
    model["_giorno"] = f"{day:%Y-%m-%d}"
    if any(s.get("fondo") == "giorno" for s in model["scaletta"]) or model["musica"].get("fondo") == "giorno":
        from gw.fondi import daily_info
        if f"{day:%Y-%m-%d}" > "2026-11-07":
            i = daily_info(day)
            print(f"Musica del giorno: {i['inst']} in {i['key']}, giro {i['prog']}")
    marks = []
    store = None
    if model.get("parti_fisse"):          # solo quando la preghiera è definitiva
        from gw.fisse import Store
        store = Store()
    audio, secs = render(events, voice, model, marks=marks, store=store)
    if store:
        store.save()
        print(f"Parti fisse: {store.hits} riusate, {store.new} nuove")
    import json as _json
    Path("out").mkdir(exist_ok=True); (Path("out") / "tempi.json").write_text(_json.dumps(marks, ensure_ascii=False), "utf-8")   # per controllare l'audio
    print("TEMPI " + _json.dumps(marks, ensure_ascii=False))
    tag = f"{day:%Y-%m-%d}"
    filename = f"getupandwalk-{tag}.mp3"
    out = Path("out")
    mp3 = to_mp3(audio, out / filename, title=f"{post.title} · {day:%d/%m/%Y}", artist="Get up and Walk",
                 album="Get up and Walk · in ascolto", comment=post.url)
    print(f"MP3: {mp3} ({secs / 60:.1f} minuti, {mp3.stat().st_size / 1e6:.1f} MB)")
    az = voice.engines.get("azure")
    if az is not None:
        print(f"Caratteri Azure usati oggi: {az.chars}")

    (out / "data.txt").write_text(tag)
    if voice.broken:
        (out / "avviso.md").write_text(
            f"L'audio del {day:%d/%m/%Y} è uscito con le voci di riserva ({voices_label(model, voice)}), "
            f"perché le voci scelte non hanno funzionato:\n\n"
            + "\n".join(f"- {k}: {v}" for k, v in voice.broken.items())
            + "\n\nSe succede più giorni di fila, il servizio potrebbe essere cambiato: scrivilo a Claude.\n")
    (out / "titolo.txt").write_text(f"{post.title} · {day:%d/%m/%Y}")
    (out / "note.md").write_text(f"{liturgia}\n\nCommento di {post.ref}, a cura di {post.author}\n\n{post.url}\n")

    if not args.no_sito:
        # il post letto, per il pannello di controllo
        import dataclasses
        import json
        posts = Path("docs/posts")
        posts.mkdir(parents=True, exist_ok=True)
        data = dataclasses.asdict(post)
        data["day"] = tag
        (posts / f"{tag}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        sito.save_episode({
            "date": tag, "title": post.title, "ref": post.ref, "author": post.author,
            "author_url": getattr(post, "author_url", ""), "image": post.image, "caption": post.caption, "liturgia": liturgia[:1].upper() + liturgia[1:],
            "post": post.url, "audio": sito.asset_url(tag, filename),
            "seconds": round(secs), "bytes": mp3.stat().st_size, "voci": voices_label(model, voice),
        })
        print(f"Pagina aggiornata: {sito.SITE_URL}")


if __name__ == "__main__":
    sys.exit(main())
