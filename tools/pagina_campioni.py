"""Pagina di ascolto dei campioni di voci: _site/campioni/index.html con un lettore per ogni file."""
import html
import pathlib
import re
import sys

d = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "_site/campioni")
files = sorted(p.name for p in d.glob("*.mp3"))


def label(name):
    if name.startswith("0-"):
        return "Tutti gli uomini" if "uomini" in name else "Tutte le donne"
    n = re.sub(r"^(donne|uomini)-|\.mp3$", "", name)
    n = n.replace("-MAI-Voice-", " · nuova MAI ").replace("-DragonLatest", " · Dragon").replace("-HD", " · HD")
    n = re.sub(r"(\d)-(\d)", r"\1.\2", n).replace("-Flash", " Flash")
    return n


def block(title, items, note=""):
    rows = "".join(f'<div class="v"><b>{html.escape(label(f))}</b><audio controls preload="none" src="{f}"></audio></div>'
                   for f in items)
    return f"<h2>{title}</h2>{note}{rows}"


uomini = [f for f in files if f.startswith("uomini-")]
donne = [f for f in files if f.startswith("donne-")]
tutti = sorted((f for f in files if f.startswith("0-")), key=lambda f: "uomini" not in f)
NOTE_TUTTI = '<p class="n">Tutti gli uomini, poi tutte le donne, una voce dopo l&#39;altra.</p>'
page = f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Voci Azure a confronto</title>
<style>
body{{font-family:Georgia,serif;max-width:640px;margin:0 auto;padding:16px;background:#faf7f2;color:#2b2622}}
h1{{font-size:1.5rem}} h2{{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #d8cfc2;padding-bottom:4px}}
p{{line-height:1.5}} .v{{margin:12px 0}} .v b{{display:block;font-family:system-ui,sans-serif;font-size:.95rem;margin-bottom:4px}}
audio{{width:100%}} .n{{font-size:.9rem;color:#6b6158}}
</style></head><body>
<h1>Voci di Azure a confronto</h1>
<p>Ogni voce dice il suo nome e poi legge lo stesso brano: la preparazione, un pezzo del Vangelo dell'8 novembre,
«compratevene» con l'accento scritto in modo esatto, e la domanda «Quale parola o frase…».</p>
<p class="n">«HD» e «Dragon» sono le voci più recenti e naturali; «MAI» sono voci nuovissime di Microsoft, «Flash» la loro versione veloce.
Quando hai scelto, scrivi a Claude il nome dell'uomo e quello della donna.</p>
{block("Tutti insieme", tutti, NOTE_TUTTI)}
{block("Uomini", uomini)}
{block("Donne", donne)}
</body></html>"""
(d / "index.html").write_text(page, "utf-8")
print(len(files), "campioni nella pagina")
