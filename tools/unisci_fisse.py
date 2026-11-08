"""Unisce le parti fisse appena create (cartella A) a quelle già nel progetto (voci-fisse/),
così due audio fatti quasi insieme non si cancellano a vicenda l'elenco."""
import json
import pathlib
import shutil
import sys

new = pathlib.Path(sys.argv[1])
dst = pathlib.Path("voci-fisse")
if not new.exists():
    sys.exit(0)
dst.mkdir(exist_ok=True)
for f in new.glob("*.flac"):
    shutil.copyfile(f, dst / f.name)
load = lambda p: json.loads(p.read_text("utf-8")) if p.exists() else {}
index = load(dst / "indice.json")
for k, v in load(new / "indice.json").items():
    if k not in index or v.get("usato", "") > index[k].get("usato", ""):
        index[k] = v
index = {k: v for k, v in index.items() if (dst / f"{k}.flac").exists()}
(dst / "indice.json").write_text(json.dumps(dict(sorted(index.items(), key=lambda kv: kv[1]["creato"])),
                                            ensure_ascii=False, indent=1) + "\n", "utf-8")
print(len(index), "parti fisse nel progetto")
