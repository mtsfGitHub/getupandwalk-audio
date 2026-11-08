"""Prepara il sito con gli MP3 serviti direttamente.

Ogni versione di un audio ha un nome suo (getupandwalk-DATA-xxxxxxxx.mp3): se un audio viene rifatto mentre
qualcuno lo sta ascoltando, la sua versione resta sul sito ancora 24 ore e l'ascolto non si interrompe.
Uso: python tools/prepara_sito.py _site  (con gli MP3 appena scaricati in _site/audio/getupandwalk-DATA.mp3)
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.request

site = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
audio = site / "audio"
repo = os.environ.get("GITHUB_REPOSITORY", "mtsfGitHub/getupandwalk-audio")
owner, name = repo.split("/")
live = f"https://{owner.lower()}.github.io/{name}/audio/"
now = dt.datetime.now(dt.timezone.utc)
KEEP = dt.timedelta(hours=24)

try:
    urllib.request.urlopen(live + "versioni.json", timeout=20).read()
    first_time = False
except Exception:
    first_time = True

# 1. nome con la "firma" del contenuto
current = {}
for f in sorted(audio.glob("getupandwalk-????-??-??.mp3")):
    sig = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
    new = f.with_name(f"{f.stem}-{sig}.mp3")
    if first_time:          # chi sta ascoltando con il vecchio nome (senza firma) non viene interrotto
        import shutil
        shutil.copyfile(f, new)
    else:
        f.rename(new)
    current[f.name] = new.name

# 2. le versioni precedenti, ancora per 24 ore
try:
    old = json.loads(urllib.request.urlopen(live + "versioni.json", timeout=20).read())
except Exception:
    old = {}
index = {v: now.isoformat() for v in current.values()}
for fname, seen in old.items():
    if fname in index:
        index[fname] = seen
        continue
    try:
        age = now - dt.datetime.fromisoformat(seen)
    except Exception:
        continue
    if age < KEEP and re.fullmatch(r"getupandwalk-\d{4}-\d{2}-\d{2}-[0-9a-f]{8}\.mp3", fname):
        try:
            (audio / fname).write_bytes(urllib.request.urlopen(live + fname, timeout=60).read())
            index[fname] = seen
            print("tengo ancora la versione precedente", fname)
        except Exception as e:
            print("non riesco a tenere", fname, e)
for fname in index:
    if fname in current.values():
        index[fname] = old.get(fname, now.isoformat())
(audio / "versioni.json").write_text(json.dumps(index, indent=1))

# 3. la pagina punta alle versioni nuove
page = site / "index.html"
html = page.read_text("utf-8")
pat = re.compile(r"https://github\.com/" + re.escape(repo) + r"/releases/download/[^/\"']+/(getupandwalk-[0-9-]+\.mp3)")
html = pat.sub(lambda m: "audio/" + current[m.group(1)] if m.group(1) in current else m.group(0), html)
page.write_text(html, "utf-8")
print(len(current), "MP3 serviti dal sito")
