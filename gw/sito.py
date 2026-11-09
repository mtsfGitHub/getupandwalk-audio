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


def _author(x):
    name = html.escape(x.get("author", ""))
    url = x.get("author_url", "")
    if not url:
        return f'<em>{name}</em>'
    return f'<a class="aut" href="{html.escape(url)}" target="_blank" rel="noopener">{name}</a>'


def write_page(eps):
    e = html.escape
    if not eps:
        return
    top = eps[0]

    def parts(iso):
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        return str(d.day), MONTHS[d.month - 1].capitalize(), str(d.year)

    def data(x):
        g, m, a = parts(x["date"])
        fields = {"src": x["audio"], "title": x["title"], "date": _date_label(x["date"]), "lit": x.get("liturgia", ""),
                  "ref": x.get("ref", ""), "author": x.get("author", ""), "aurl": x.get("author_url", ""), "img": x.get("image", ""),
                  "cap": x.get("caption", ""), "post": x["post"], "voci": x.get("voci", ""),
                  "g": g, "m": m, "a": a, "dur": _mmss(x["seconds"])}
        return " ".join(f'data-{k}="{e(v)}"' for k, v in fields.items())

    cards = "\n".join(
        f'<li{" hidden" if x is top else ""}><div role="button" tabindex="0" class="ep" {data(x)}>'
        f'<span class="cal"><b>{e(parts(x["date"])[0])}</b><span>{e(parts(x["date"])[1])}</span><small>{e(parts(x["date"])[2])}</small></span>'
        f'<span class="t">{e(x["title"])}</span>'
        f'<span class="m">Commento di <span class="nw">{e(x.get("ref", ""))}</span><br>a cura di {_author(x)}</span>'
        f'<span class="dur">▶ {_mmss(x["seconds"])}</span></div></li>' for x in eps)
    g, m, a = parts(top["date"])
    img = f'<img id="img" src="{e(top.get("image", ""))}" alt="{e(top.get("caption") or top["title"])}"{"" if top.get("image") else " hidden"}>'
    page = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Get up and Walk · in ascolto</title>
<meta name="description" content="Il Vangelo del giorno e il commento di Get up and Walk, da ascoltare come una preghiera guidata.">
<link rel="alternate" type="application/rss+xml" title="Get up and Walk · in ascolto" href="feed.xml">
<link rel="icon" href="logo-ihs.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500&family=Source+Sans+3:wght@300;400;600;700&display=swap">
<style>
:root{{--blu:#00476B;--grigio:#DCDCDC;--grigio2:#EDEDED;--giallo:#F6B91C;--link:#1B7CBE;--ink:#111;--muted:#4A4A4A;--nero:#202020;
--ft:"Cinzel","Trajan Pro",Georgia,serif;--fs:"Source Sans 3","Segoe UI",system-ui,sans-serif;color-scheme:light}}
*{{box-sizing:border-box}}
body{{margin:0;background:#fff;color:var(--ink);font-family:var(--fs);line-height:1.45}}
.in{{max-width:1180px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left));padding-right:max(16px,env(safe-area-inset-right))}}
header.top{{background:var(--blu);color:#fff;padding-top:env(safe-area-inset-top)}}
header.top .in{{display:flex;align-items:center;gap:22px;padding-block:30px}}
header.top img{{width:96px;height:96px;flex:none}}
header.top .nome{{font-family:var(--ft);font-size:clamp(28px,5vw,46px);letter-spacing:.02em;line-height:1;margin:0;font-weight:400}}
header.top .sotto{{font-weight:300;font-size:clamp(14px,2vw,17px);margin-top:8px;opacity:.95}}
header.top a{{color:inherit;text-decoration:none;display:flex;align-items:center;gap:22px}}
@media (max-width:560px){{header.top img{{width:64px;height:64px}}header.top .in,header.top a{{gap:14px}}}}
.banda{{background:var(--grigio)}}
.banda .in{{padding-block:16px;font-family:var(--ft);font-size:clamp(24px,3.6vw,32px);letter-spacing:.16em;text-transform:uppercase;color:var(--nero)}}
main .in{{padding-block:32px 48px;display:flex;flex-direction:column;gap:28px}}
.oggi{{background:var(--grigio);padding:24px;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:40px;align-items:start}}
@media (max-width:820px){{.oggi{{grid-template-columns:1fr;gap:24px;padding:16px}}}}
.oggi img{{width:100%;height:auto;display:block;max-width:100%}}
.cap{{font-size:13px;color:var(--muted);margin-top:6px}}
.info{{display:flex;flex-direction:column;align-items:flex-start;gap:14px;min-width:0}}
.cal{{background:var(--giallo);color:var(--nero);display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:300;line-height:1.1}}
.info .cal{{width:168px;height:148px}}
.info .cal b{{font-size:58px;font-weight:300}}
.info .cal span{{font-size:23.5px}}
.info .cal small{{font-size:16.5px;margin-top:4px}}
.lit{{font-size:15px;color:var(--muted)}}
h1{{font-size:clamp(28px,4vw,36px);font-weight:700;margin:0;line-height:1.1;text-wrap:balance}}
.by{{font-size:16px}}
.by em{{font-style:normal;color:var(--link)}}
.aut{{color:var(--link);text-decoration:none}}
.aut:hover{{text-decoration:underline}}
audio{{width:100%;max-width:520px}}
.azioni{{display:flex;gap:12px;flex-wrap:wrap}}
.btn{{display:inline-flex;align-items:center;gap:6px;padding:9px 14px;font-size:15px;text-decoration:none;color:#fff;border:0}}
.btn.blu{{background:var(--link)}}
.btn.nero{{background:var(--nero)}}
.btn:hover{{filter:brightness(1.1)}}
h2{{font-family:var(--ft);font-weight:400;font-size:22px;letter-spacing:.12em;text-transform:uppercase;margin:0 0 14px}}
.giorni{{list-style:none;margin:0;padding:0 0 10px;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(220px,250px);gap:20px;
overflow-x:auto;scroll-snap-type:x mandatory}}
.giorni li{{scroll-snap-align:start;display:flex}}
.giorni li[hidden]{{display:none!important}}
.ep{{width:100%;background:var(--grigio);border:0;box-sizing:border-box;padding:12px 12px 16px;text-align:left;font:inherit;color:inherit;cursor:pointer;
display:flex;flex-direction:column;gap:12px;outline-offset:3px}}
.ep .cal{{height:112px}}
.ep .cal b{{font-size:42px;font-weight:300}}
.ep .cal span{{font-size:18.5px}}
.ep .cal small{{font-size:15.5px}}
.ep .t{{font-weight:700;font-size:20px;line-height:1.15}}
.ep .m{{font-size:14px;color:var(--muted)}}
.ep .m em{{font-style:normal;color:var(--link)}}
.ep .dur{{margin-top:auto;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}}
.ep:hover{{background:var(--grigio2)}}
.ep.on{{box-shadow:inset 0 -4px 0 var(--blu)}}
.ep.on .dur{{color:var(--blu);font-weight:600}}
.nw{{white-space:nowrap}}
.testo{{display:flex;flex-direction:column;gap:10px;min-width:0}}
/* telefono e tablet (anche il telefono in orizzontale): banda stretta come la versione mobile di Get up and Walk */
@media (max-width:1024px),(max-height:520px){{
  header.top .in{{padding-block:6px}}
  header.top a{{gap:16px}}
  header.top img{{width:36px;height:36px}}
  header.top .nome{{font-size:clamp(20px,5.6vw,27px)}}
  header.top .sotto{{display:none}}
  .banda .in{{padding-block:6px;font-size:clamp(16px,4.6vw,22px);letter-spacing:.14em;
    padding-left:calc(max(16px,env(safe-area-inset-left,0px)) + 52px)}}
  main .in{{padding-block:20px 36px;gap:20px}}
  .oggi{{grid-template-columns:1fr;gap:18px;padding:12px}}
  .info{{display:grid;grid-template-columns:auto minmax(0,1fr);gap:16px 18px;align-items:start;width:100%}}
  .info .cal{{width:clamp(104px,24vw,168px);height:clamp(100px,22vw,148px)}}
  .info .cal b{{font-size:clamp(42px,9.4vw,58px)}}
  .info .cal span{{font-size:clamp(18.5px,3.9vw,23.5px)}}
  .info audio,.info .azioni{{grid-column:1/-1}}
  .info audio{{max-width:none}}
  h1{{font-size:clamp(24px,5.4vw,34px)}}
  .by{{font-size:15px}}
  .by .sep{{display:block;height:0;overflow:hidden}}
  /* giorni precedenti in griglia di tre, come sul sito */
  .giorni{{grid-auto-flow:row;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-columns:auto;overflow:visible;gap:16px}}
  .giorni li:nth-child(n+8){{display:none}}
  .giorni.tutti li{{display:flex}}
  .altri{{display:inline-flex}}
}}
/* telefono in verticale */
@media (max-width:560px) and (min-height:521px){{
  .giorni{{grid-auto-flow:column;grid-template-columns:none;grid-auto-columns:minmax(180px,200px);overflow-x:auto;gap:14px}}
  .giorni li:nth-child(n+8){{display:flex}}
  .altri{{display:none!important}}
  .ep .cal{{height:96px}}
  .ep .t{{font-size:18px}}
}}
.altri{{display:none;margin-top:14px;background:var(--nero);color:#fff;border:0;padding:9px 14px;font:inherit;font-size:15px;cursor:pointer}}
footer{{background:var(--blu);color:#fff;font-size:13px}}
footer .in{{padding-block:18px calc(18px + env(safe-area-inset-bottom))}}
footer a{{color:#fff}}
</style>
</head>
<body>
<header class="top"><div class="in"><a href="https://getupandwalk.gesuiti.it/" target="_blank" rel="noopener">
  <img src="logo-ihs.png" alt="">
  <div><p class="nome">GET UP AND WALK</p><div class="sotto">il vangelo quotidiano commentato secondo il metodo della spiritualità ignaziana</div></div>
</a></div></header>
<div class="banda"><div class="in">in ascolto</div></div>
<main><div class="in">
  <section class="oggi">
    <div>{img}<div class="cap" id="cap">{e(top.get("caption", ""))}</div></div>
    <div class="info">
      <div class="cal" id="cal"><b id="cg">{e(g)}</b><span id="cm">{e(m)}</span><small id="ca">{e(a)}</small></div>
      <div class="testo">
        <div class="lit" id="lit">{e(top.get("liturgia", ""))}</div>
        <h1 id="title">{e(top["title"])}</h1>
        <div class="by">commento di <span id="ref" class="nw">{e(top.get("ref", ""))}</span><span class="sep">, </span>a cura di <a id="author" class="aut" href="{e(top.get("author_url") or "#")}" target="_blank" rel="noopener">{e(top.get("author", ""))}</a></div>
      </div>
      <audio id="player" controls preload="none" src="{e(top["audio"])}"></audio>
      <div class="azioni">
        <a class="btn blu" id="post" href="{e(top["post"])}" target="_blank" rel="noopener">Vai alla preghiera&nbsp;›</a>
        <a class="btn nero" id="dl" href="{e(top["audio"])}" download>Scarica l'audio</a>
      </div>
    </div>
  </section>
  {"<section aria-label='Gli ultimi giorni'><ul class='giorni' id='giorni'>" + cards + "</ul>" + ("<button type='button' class='altri' id='altri'>Mostra tutti i giorni</button>" if len(eps) > 7 else "") + "</section>" if len(eps) > 1 else ""}
</div></main>
<footer><div class="in">Testi: <a href="https://getupandwalk.gesuiti.it/">getupandwalk.gesuiti.it</a> · Voci generate al computer<span id="voci" hidden></span></div></footer>
<script>
const $=id=>document.getElementById(id);
function show(b,play){{
  const d=b.dataset;
  $('title').textContent=d.title;$('lit').textContent=d.lit;$('ref').textContent=d.ref;$('author').textContent=d.author;$('author').href=d.aurl||'#';
  $('cap').textContent=d.cap;$('cg').textContent=d.g;$('cm').textContent=d.m;$('ca').textContent=d.a;
  const img=$('img');if(img){{img.hidden=!d.img;if(d.img){{img.src=d.img;img.alt=d.cap||d.title}}}}
  $('dl').href=d.src;$('post').href=d.post;
  document.querySelectorAll('.ep').forEach(x=>{{x.classList.toggle('on',x===b);x.parentElement.hidden=x===b}});
  const p=$('player');if(p.getAttribute('src')!==d.src){{p.src=d.src;p.load()}}
  if(play){{p.play().catch(()=>{{}});window.scrollTo({{top:0,behavior:'smooth'}})}}
}}
document.querySelectorAll('.ep').forEach(b=>{{
  b.addEventListener('click',ev=>{{if(ev.target.closest('a'))return;show(b,true)}});
  b.addEventListener('keydown',ev=>{{if(ev.key==='Enter'||ev.key===' '){{ev.preventDefault();show(b,true)}}}});
}});
const first=document.querySelector('.ep');if(first){{first.classList.add('on');first.parentElement.hidden=true}}
const altri=$('altri');if(altri)altri.addEventListener('click',()=>{{$('giorni').classList.add('tutti');altri.remove()}});
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
