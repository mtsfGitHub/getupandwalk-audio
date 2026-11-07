"""Crea l'audio di Get up and Walk per un giorno.

Uso:  python build.py                 → oggi (ora italiana)
      python build.py --data 2026-11-07
      python build.py --voce prova    → toni al posto delle voci, per provare il montaggio
"""
import argparse
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="")
    ap.add_argument("--voce", default="kokoro", choices=["kokoro", "prova"])
    ap.add_argument("--html", help="file HTML del post già scaricato (per le prove)")
    ap.add_argument("--no-sito", action="store_true", help="non aggiornare la pagina e il feed")
    args = ap.parse_args()

    day = date.fromisoformat(args.data) if args.data.strip() else datetime.now(ZoneInfo("Europe/Rome")).date()
    model = yaml.safe_load(Path("modello.yaml").read_text("utf-8"))

    print(f"Giorno: {day:%d/%m/%Y}")
    if args.html:
        post = parse_post(Path(args.html).read_text("utf-8"), day, "https://getupandwalk.gesuiti.it/")
    else:
        post = fetch_post(day)
    print(f"Post: {post.title} — {post.ref} — {post.author}\n  {post.url}")
    print("Sezioni trovate: " + ", ".join(f"{s.label} ({len(s.paras)})" for s in post.sections))
    if post.quote_lines:
        print(f"Citazione: {post.quote_source}")

    liturgia, origine = liturgical_day(day)
    print(f"Liturgia ({origine}): {liturgia}")

    values = fill_values(post, liturgia)
    events = build_events(model, values)
    current = None
    for ev in events:
        if ev.section != current:
            current = ev.section
            print(f"\n== {current}")
        if ev.kind == "speak":
            who = "M" if ev.voice == model["voci"]["struttura"] else "F"
            print(f"  [{who} x{ev.speed:.2f}] {ev.text[:90]}{'…' if len(ev.text) > 90 else ''}")
        elif ev.kind != "gap":
            print(f"  <{ev.kind} {ev.secs:g} s>")

    print("\nGenero le voci…")
    voice = make_voice(args.voce, model["voci"].get("riserva", "im_nicola"))
    audio, secs = render(events, voice, model)
    tag = f"{day:%Y-%m-%d}"
    filename = f"getupandwalk-{tag}.mp3"
    out = Path("out")
    mp3 = to_mp3(audio, out / filename, title=f"{post.title} · {day:%d/%m/%Y}", artist="Get up and Walk",
                 album="Get up and Walk · in ascolto", comment=post.url)
    print(f"MP3: {mp3} ({secs / 60:.1f} minuti, {mp3.stat().st_size / 1e6:.1f} MB)")

    (out / "data.txt").write_text(tag)
    if voice.broken:
        (out / "avviso.md").write_text(
            f"L'audio del {day:%d/%m/%Y} è uscito con la voce di riserva ({voice.fallback}), "
            f"perché le voci scelte non hanno funzionato:\n\n"
            + "\n".join(f"- {k}: {v}" for k, v in voice.broken.items())
            + "\n\nSe succede più giorni di fila, il servizio potrebbe essere cambiato: scrivilo a Claude.\n")
    (out / "titolo.txt").write_text(f"{post.title} · {day:%d/%m/%Y}")
    (out / "note.md").write_text(f"{liturgia}\n\nCommento di {post.ref}, a cura di {post.author}\n\n{post.url}\n")

    if not args.no_sito:
        sito.save_episode({
            "date": tag, "title": post.title, "ref": post.ref, "author": post.author,
            "image": post.image, "caption": post.caption, "liturgia": liturgia[:1].upper() + liturgia[1:],
            "post": post.url, "audio": sito.asset_url(tag, filename),
            "seconds": round(secs), "bytes": mp3.stat().st_size,
        })
        print(f"Pagina aggiornata: {sito.SITE_URL}")


if __name__ == "__main__":
    sys.exit(main())
