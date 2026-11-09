"""Legge il post del giorno da Get up and Walk e ne ricava le parti."""
import re
from dataclasses import dataclass, field
from datetime import date

import requests
from bs4 import BeautifulSoup

SITE = "https://getupandwalk.gesuiti.it"
HEADERS = {"User-Agent": "getupandwalk-audio (+https://github.com/mtsfGitHub/getupandwalk-audio)"}

KNOWN = [
    ("prep", re.compile(r"^mi\s+preparo\b", re.I)),
    ("testo", re.compile(r"^entro\s+nel\s+testo\b", re.I)),
    ("ispira", re.compile(r"^mi\s+lascio\s+ispirare\b", re.I)),
    ("immagino", re.compile(r"^immagino\b", re.I)),
    ("domande", re.compile(r"^rifletto\b", re.I)),
    ("ringrazio", re.compile(r"^ringrazio\b", re.I)),
]
STOP = re.compile(r"^(TAG\b|TAG[A-Za-z]|Condividi|Iscriviti|Seguici|Da leggere|Vuoi ricevere)", re.I)
ART = re.compile(r"\bsec\.|secolo|\b1[0-9]{3}\b|affresco|olio su|tela|tavola|chiesa|basilica|museo|volta|"
                 r"cappella|mosaico|particolare|scultura|dipinto|icona", re.I)
CREDIT = re.compile(r"^\s*(©|\(c\)|foto\b|immagine\b|credit)|diritti riservati|realizzata con|riproduzione", re.I)
SEPARATOR = re.compile(r"^[\*\-–—_\s]+$")
BLOCKS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "figcaption", "blockquote", "pre"]
BOOKS = {"Mt": "Matteo", "Mc": "Marco", "Lc": "Luca", "Gv": "Giovanni"}


@dataclass
class Section:
    key: str
    label: str
    ref: str = ""
    paras: list = field(default_factory=list)


@dataclass
class Post:
    day: date
    url: str
    title: str = ""
    ref: str = ""
    author: str = ""
    author_url: str = ""
    image: str = ""
    caption: str = ""
    quote_lines: list = field(default_factory=list)
    quote_source: str = ""
    sections: list = field(default_factory=list)

    def section(self, key):
        return next((s for s in self.sections if s.key == key), None)

    @property
    def evangelist(self):
        sec = self.section("testo")
        m = re.match(r"^(Mt|Mc|Lc|Gv)\b", (sec.ref if sec and sec.ref else self.ref) or "")
        return BOOKS[m.group(1)] if m else ""


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def find_post_url(day):
    """L'indirizzo del post di quel giorno (archivio del giorno, poi API di WordPress)."""
    prefix = f"{SITE}/{day:%Y/%m/%d}/"
    try:
        html = _get(prefix)
        m = re.search(r'href="(' + re.escape(prefix) + r'[^"/#?]+/)"', html)
        if m:
            return m.group(1)
    except requests.RequestException:
        pass
    api = (f"{SITE}/wp-json/wp/v2/posts?per_page=5&_fields=link,date"
           f"&after={day:%Y-%m-%d}T00:00:00&before={day:%Y-%m-%d}T23:59:59")
    for item in requests.get(api, headers=HEADERS, timeout=30).json():
        if item.get("link", "").startswith(prefix):
            return item["link"]
    raise RuntimeError(f"Nessun post trovato per il {day:%d/%m/%Y}")


def _block_text(el):
    for br in el.find_all("br"):
        br.replace_with("\n")
    text = el.get_text("")
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in text.split("\n")]
    return "\n".join(l for l in lines if l)


def _key_for(heading):
    for key, rx in KNOWN:
        if rx.search(heading):
            return key
    return "altro"


def parse_post(html, day, url):
    soup = BeautifulSoup(html, "html.parser")
    post = Post(day=day, url=url)
    og = soup.find("meta", property="og:image")
    post.image = og["content"] if og and og.get("content") else ""
    h1 = soup.find("h1")
    post.title = _block_text(h1) if h1 else ""
    if not post.title:
        ogt = soup.find("meta", property="og:title")
        post.title = (ogt["content"].split(" - ")[0] if ogt else "").strip()

    # "commento di Lc 16,9-15, a cura di Giuseppe Amalfa SJ"
    node = soup.find(string=re.compile(r"commento di", re.I))
    el = node.parent if node is not None else None
    for _ in range(3):
        if el is None or "a cura di" in el.get_text(" "):
            break
        el = el.parent
    if el is not None and "a cura di" in el.get_text(" "):
        text = re.sub(r"\s+", " ", el.get_text(" ")).strip()
        m = re.search(r"commento di\s+(.+?)\s*,?\s+a cura di\s+(.+)$", text, re.I)
        if m:
            post.ref = m.group(1).strip().rstrip(",")
            post.author = re.split(r"\s{2,}| \| ", m.group(2).strip())[0]
    link = (el.find("a", href=re.compile(r"/author/")) if el is not None else None) \
        or soup.find("a", href=re.compile(r"getupandwalk\.gesuiti\.it/author/"))
    if link is not None:
        post.author_url = link["href"]
    meta = soup.find("meta", attrs={"name": "author"})
    if meta and meta.get("content"):
        post.author = meta["content"].strip()

    # the container that holds the title and the Ignatian headings
    container = h1
    while container is not None and container.parent is not None:
        container = container.parent
        heads = container.find_all(["h2", "h3", "h4", "h5", "h6"])
        if any(_key_for(_block_text(h)) != "altro" for h in heads):
            break
    if container is None:
        container = soup

    blocks = []
    for el in container.find_all(BLOCKS):
        if el.find_parent(BLOCKS):
            continue
        text = _block_text(el)
        if not text or SEPARATOR.match(text):
            continue
        blocks.append((el.name, text))

    start = 0
    for i, (tag, text) in enumerate(blocks):
        if tag == "h1":
            start = i + 1
            break

    cur, preamble = None, []
    for tag, text in blocks[start:]:
        if STOP.match(text):
            if post.sections:
                break
            continue
        is_head = tag in ("h2", "h3", "h4", "h5", "h6") and len(text) <= 60
        if is_head:
            key = _key_for(text)
            if key == "altro" and not post.sections and not re.match(r"^(mi|entro|chiedo|contemplo|ascolto|prego|domando|sosto|torno|resto|guardo|leggo)\b", text, re.I):
                continue  # heading of a side box, not of the prayer
            refm = re.search(r"\(([^)]+)\)", text)
            cur = Section(key=key, label=re.sub(r"\s*\(.*\)\s*$", "", text).strip(), ref=refm.group(1) if refm else "")
            post.sections.append(cur)
            if key == "testo" and cur.ref and not post.ref:
                post.ref = cur.ref
            continue
        if re.match(r"^commento di\b", text, re.I):
            continue
        if cur is None:
            preamble.append((tag, text))
        elif text != post.author:
            cur.paras.append(text)

    post.sections = [s for s in post.sections if s.paras]
    # didascalie dell'immagine e note di copyright: non vanno lette come citazione
    captions = [t for tag, t in preamble if tag == "figcaption" or CREDIT.search(t)]
    preamble = [t for tag, t in preamble if not (tag == "figcaption" or CREDIT.search(t))]
    if len(preamble) >= 3 and ART.search(preamble[0]):
        captions.append(preamble.pop(0))
    post.caption = " ".join(c.replace("\n", " ") for c in captions)
    if len(preamble) >= 2:
        post.quote_source = preamble[-1].replace("\n", " ")
        post.quote_lines = [l for p in preamble[:-1] for l in p.split("\n")]
    if not post.sections:
        raise RuntimeError("Non ho trovato le sezioni del post (Mi preparo, Entro nel testo…)")
    return post


def fetch_post(day):
    url = find_post_url(day)
    return parse_post(_get(url), day, url)
