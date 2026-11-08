"""Le parti fisse della preghiera (Padre nostro, "Mi preparo", introduzioni…) si generano una volta sola
e si salvano in voci-fisse/: ogni giorno si riusano identiche, senza consumare caratteri.
Se nel modello cambia il testo, la voce o la velocità di una frase, quella frase si rigenera da sola.
Per rifarne una che non piace: togliere la sua riga da voci-fisse/indice.json (o chiederlo a Claude)."""
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from .musica import RATE

DIR = Path(__file__).resolve().parent.parent / "voci-fisse"
VERSION = 2           # cambiarlo rigenera tutto (per esempio se cambia il modo di trattare le voci)
KEEP_DAYS = 60        # una frase non più usata da tanto si cancella


def _key(text, voice, speed):
    raw = json.dumps([text, voice, round(float(speed), 3), VERSION], ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class Store:
    def __init__(self, folder=DIR):
        self.dir = Path(folder)
        self.index_file = self.dir / "indice.json"
        try:
            self.index = json.loads(self.index_file.read_text("utf-8"))
        except Exception:
            self.index = {}
        self.today = dt.date.today().isoformat()
        self.hits = self.new = 0

    def get(self, text, voice, speed):
        k = _key(text, voice, speed)
        f = self.dir / f"{k}.flac"
        if k in self.index and f.exists():
            import soundfile as sf
            a, rate = sf.read(str(f), dtype="float32")
            if rate == RATE:
                self.index[k]["usato"] = self.today
                self.hits += 1
                return a
        return None

    def put(self, text, voice, speed, audio):
        import soundfile as sf
        self.dir.mkdir(parents=True, exist_ok=True)
        k = _key(text, voice, speed)
        sf.write(str(self.dir / f"{k}.flac"), np.asarray(audio, dtype=np.float32), RATE, subtype="PCM_16")
        self.index[k] = {"testo": text, "voce": voice if not voice.startswith("coro:") else
                         f"coro di {voice.count('|') + 1} voci", "velocita": round(float(speed), 3),
                         "creato": self.today, "usato": self.today}
        self.new += 1

    def save(self):
        limit = (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat()
        for k in [k for k, v in self.index.items() if v.get("usato", "") < limit]:
            (self.dir / f"{k}.flac").unlink(missing_ok=True)
            del self.index[k]
        if self.index:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.index_file.write_text(json.dumps(dict(sorted(self.index.items(), key=lambda kv: kv[1]["creato"])),
                                                  ensure_ascii=False, indent=1) + "\n", "utf-8")
