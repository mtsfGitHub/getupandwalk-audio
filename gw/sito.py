"""La pagina di ascolto (docs/index.html) e il feed podcast (docs/feed.xml), pubblicati con GitHub Pages."""
import html
import json
import os
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from .liturgia import MONTHS, DAYS

DOCS = Path("docs")
REPO = os.environ.get("GITHUB_REPOSITORY", "mtsfGitHub/getupandwalk-audio")
OWNER, NAME = REPO.split("/")
SITE_URL = f"https://{OWNER.lower()}.github.io/{NAME}/"
KEEP = 60  # quante puntate mostrare nella pagina e nel feed


def asset_url(tag, filename):
    return f"https://github.com/{REPO}/releases/download/{tag}/{filename}"


def load_episodes():
    p = DOCS / "episodes.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else []


def save_episode(ep):
    eps = [e for e in load_episodes() if e["date"] != ep["date"]]
    eps.append(ep)
    eps.sort(key=lambda e: e["date"], reverse=True)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "episodes.json").write_text(json.dumps(eps, ensure_ascii=False, indent=1), "utf-8")
    (DOCS / ".nojekyll").write_text("")
    write_page(eps[:KEEP])
    write_feed(eps[:KEEP])


def _date_label(iso):
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def _mmss(secs):
    secs = int(round(secs))
    return f"{secs // 60}:{secs % 60:02d}"


def write_page(eps):
    e = html.escape
    if not eps:
        return
    top, rest = eps[0], eps[1:]
    def data(x):
        fields = {"src": x["audio"], "title": x["title"], "date": _date_label(x["date"]), "lit": x.get("liturgia", ""),
                  "by": f'Commento di {x.get("ref", "")}, a cura di {x.get("author", "")}', "img": x.get("image", ""),
                  "cap": x.get("caption", ""), "post": x["post"], "voci": x.get("voci", "")}
        return " ".join(f'data-{k}="{e(v)}"' for k, v in fields.items())
    items = "\n".join(
        f'<li><button type="button" class="ep" {data(x)}>'
        f'<span class="d">{e(_date_label(x["date"]))}</span><span class="t">{e(x["title"])}</span>'
        f'<span class="m">{_mmss(x["seconds"])}</span></button></li>' for x in eps)
    img = f'<img id="img" src="{e(top.get("image", ""))}" alt="{e(top.get("caption") or top["title"])}"{"" if top.get("image") else " hidden"}>'
    page = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Get up and Walk · in ascolto</title>
<link rel="alternate" type="application/rss+xml" title="Get up and Walk · in ascolto" href="feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Display&family=Literata:ital,opsz@0,7..72;1,7..72&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
:root{{--bg:#EFF0F4;--surface:#FBFBFD;--ink:#1A2240;--muted:#5A6079;--line:#D5D8E3;--gold:#9A6F17;--lapis:#2B3A78;--on:#F6F2E6;
--fd:"Libre Caslon Display",Georgia,serif;--fr:"Literata",Georgia,serif;--fu:"IBM Plex Sans",system-ui,sans-serif}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0D1224;--surface:#151B33;--ink:#E9E5D8;--muted:#9EA3BC;--line:#2A3254;--gold:#D6B160;--lapis:#C9A957;--on:#141A31;color-scheme:dark}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--fu);line-height:1.5;
padding:24px max(16px,env(safe-area-inset-right)) 64px max(16px,env(safe-area-inset-left))}}
.wrap{{max-width:860px;margin:0 auto;display:flex;flex-direction:column;gap:28px}}
.eyebrow{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);font-weight:600}}
.today{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:28px;align-items:start}}
@media (max-width:680px){{.today{{grid-template-columns:1fr}}}}
.today img{{width:100%;border-radius:12px;display:block}}
.cap{{font-size:13px;color:var(--muted);font-style:italic;margin-top:8px}}
.info{{display:flex;flex-direction:column;gap:10px;min-width:0}}
.date{{font-family:var(--fr);font-style:italic;color:var(--muted)}}
.lit{{font-size:14px;color:var(--muted)}}
h1{{font-family:var(--fd);font-weight:400;font-size:clamp(32px,6vw,46px);line-height:1.05;margin:0;text-wrap:balance}}
.by{{color:var(--muted)}}
audio{{width:100%;margin-top:6px}}
.actions{{display:flex;gap:14px;flex-wrap:wrap;font-size:14px}}
a{{color:var(--lapis)}}
h2{{font-family:var(--fd);font-weight:400;font-size:26px;margin:0 0 8px}}
ul{{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}}
.ep{{width:100%;display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:baseline;text-align:left;border:0;border-bottom:1px solid var(--line);
background:none;color:inherit;font:inherit;padding:12px 4px;cursor:pointer}}
.ep:hover{{background:var(--surface)}}
.ep.on .t{{color:var(--gold)}}
.ep .d{{color:var(--muted);font-size:13px;min-width:13ch}}
.ep .t{{font-family:var(--fr)}}
.ep .m{{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}}
@media (max-width:520px){{.ep{{grid-template-columns:1fr auto}}.ep .d{{grid-column:1/-1}}}}
footer{{font-size:12px;color:var(--muted)}}
</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">Get up and Walk · in ascolto</div>
  <section class="today">
    <div>{img}<div class="cap" id="cap">{e(top.get("caption", ""))}</div></div>
    <div class="info">
      <div class="date" id="date">{e(_date_label(top["date"]))}</div>
      <div class="lit" id="lit">{e(top.get("liturgia", ""))}</div>
      <h1 id="title">{e(top["title"])}</h1>
      <div class="by" id="by">Commento di {e(top.get("ref", ""))}, a cura di {e(top.get("author", ""))}</div>
      <audio id="player" controls preload="none" src="{e(top["audio"])}"></audio>
      <div class="actions">
        <a id="dl" href="{e(top["audio"])}">Scarica l'MP3</a>
        <a id="post" href="{e(top["post"])}" target="_blank" rel="noopener">Leggi il post</a>
        <a href="feed.xml">Feed podcast</a>
      </div>
    </div>
  </section>
  {"<section><h2>Tutti i giorni</h2><ul>" + items + "</ul></section>" if rest else ""}
  <footer>Testi: <a href="https://getupandwalk.gesuiti.it/">getupandwalk.gesuiti.it</a> · Lettura con voci digitali<span id="voci" hidden></span>.</footer>
</div>
<script>
const $=id=>document.getElementById(id);
function show(b,play){{
  const d=b.dataset;
  ['title','date','lit','by','cap'].forEach(k=>$(k).textContent=d[k]);
  $('voci').textContent=d.voci?' ('+d.voci+')':'';
  const img=$('img');if(img){{img.hidden=!d.img;if(d.img){{img.src=d.img;img.alt=d.cap||d.title}}}}
  $('dl').href=d.src;$('post').href=d.post;
  document.querySelectorAll('.ep').forEach(x=>x.classList.toggle('on',x===b));
  const p=$('player');if(p.getAttribute('src')!==d.src){{p.src=d.src}}
  if(play){{p.play().catch(()=>{{}});window.scrollTo({{top:0,behavior:'smooth'}})}}
}}
document.querySelectorAll('.ep').forEach(b=>b.addEventListener('click',()=>show(b,true)));
const first=document.querySelector('.ep');if(first)first.classList.add('on');
</script>
</body>
</html>
"""
    (DOCS / "index.html").write_text(page, "utf-8")


def write_feed(eps):
    e = html.escape
    now = format_datetime(datetime.now(timezone.utc))
    cover = eps[0].get("image", "") if eps else ""
    items = []
    for x in eps:
        d = datetime.strptime(x["date"], "%Y-%m-%d").replace(hour=5, tzinfo=timezone.utc)
        items.append(f"""  <item>
    <title>{e(_date_label(x["date"]))} · {e(x["title"])}</title>
    <description>{e(x.get("liturgia", ""))}. Commento di {e(x.get("ref", ""))}, a cura di {e(x.get("author", ""))}.</description>
    <link>{e(x["post"])}</link>
    <guid isPermaLink="false">getupandwalk-{x["date"]}</guid>
    <pubDate>{format_datetime(d)}</pubDate>
    <enclosure url="{e(x["audio"])}" length="{x.get("bytes", 0)}" type="audio/mpeg"/>
    <itunes:duration>{int(x["seconds"])}</itunes:duration>
    {f'<itunes:image href="{e(x["image"])}"/>' if x.get("image") else ""}
  </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
  <title>Get up and Walk · in ascolto</title>
  <link>{SITE_URL}</link>
  <description>Il Vangelo del giorno commentato secondo la spiritualità ignaziana, da ascoltare.</description>
  <language>it</language>
  <lastBuildDate>{now}</lastBuildDate>
  <itunes:author>Get up and Walk</itunes:author>
  <itunes:explicit>false</itunes:explicit>
  <itunes:category text="Religion &amp; Spirituality"><itunes:category text="Christianity"/></itunes:category>
  {f'<itunes:image href="{e(cover)}"/>' if cover else ""}
{chr(10).join(items)}
</channel>
</rss>
"""
    (DOCS / "feed.xml").write_text(feed, "utf-8")
