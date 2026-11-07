"""Riporta la puntata appena creata nella pagina e nel feed partendo dalla versione più recente del sito
(serve quando nel frattempo un'altra esecuzione ha già aggiornato la pagina)."""
import json
import shutil
import sys
from pathlib import Path

from gw import sito

day, saved = sys.argv[1], Path(sys.argv[2])
ep = next(e for e in json.loads((saved / "episodes.json").read_text("utf-8")) if e["date"] == day)
sito.save_episode(ep)
post = saved / "post.json"
if post.exists():
    (sito.DOCS / "posts").mkdir(parents=True, exist_ok=True)
    shutil.copy(post, sito.DOCS / "posts" / f"{day}.json")
