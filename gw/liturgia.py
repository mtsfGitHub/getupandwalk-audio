"""Il giorno liturgico, in forma da leggere ad alta voce.

Prima lo cerca sulla pagina della CEI; se non riesce, lo calcola con le regole del calendario romano.
"""
import re
from datetime import date, timedelta

import requests

CEI = "https://www.chiesacattolica.it/liturgia-del-giorno/?data-liturgia={:%Y%m%d}"
HEADERS = {"User-Agent": "getupandwalk-audio (+https://github.com/mtsfGitHub/getupandwalk-audio)"}

DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]  # date.weekday()
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
          "settembre", "ottobre", "novembre", "dicembre"]
ORD = ["", "prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima",
       "undicesima", "dodicesima", "tredicesima", "quattordicesima", "quindicesima", "sedicesima",
       "diciassettesima", "diciottesima", "diciannovesima", "ventesima", "ventunesima", "ventiduesima",
       "ventitreesima", "ventiquattresima", "venticinquesima", "ventiseiesima", "ventisettesima",
       "ventottesima", "ventinovesima", "trentesima", "trentunesima", "trentaduesima", "trentatreesima",
       "trentaquattresima"]
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def day_name(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def _roman(s):
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _spoken(title):
    t = re.sub(r"\s*\((anno|ciclo)[^)]*\)", "", title, flags=re.I).strip()
    t = re.sub(r"\b([IVXL]+)\s+(SETTIMANA|DOMENICA)\b",
               lambda m: f"{ORD[_roman(m.group(1))]} {m.group(2)}" if _roman(m.group(1)) < len(ORD) else m.group(0),
               t, flags=re.I)
    t = t.lower()
    return t[0].lower() + t[1:] if t else t


def from_cei(d):
    html = requests.get(CEI.format(d), headers=HEADERS, timeout=30).text
    m = re.search(r"<title>\s*([^<]+?)\s*</title>", html, re.I | re.S)
    if not m:
        return None
    title = re.split(r"\s+[|–-]\s+", m.group(1).strip())[0]
    if not re.search(r"settimana|domenica|solennit|festa|ceneri|santo|pasqua|natale|ottava|commemorazione", title, re.I):
        return None
    return _spoken(title)


# ---- calcolo di riserva -------------------------------------------------------------
def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(y, month, day)


def _sun_idx(d):  # domenica = 0
    return (d.weekday() + 1) % 7


def advent1(y):
    xmas = date(y, 12, 25)
    return xmas - timedelta(days=(_sun_idx(xmas) or 7) + 21)


def baptism(y):
    ep = date(y, 1, 6)
    return ep + timedelta(days=7 - _sun_idx(ep))


FIXED = {(1, 1): "solennità di Maria Santissima Madre di Dio", (1, 6): "solennità dell'Epifania del Signore",
         (2, 2): "festa della Presentazione del Signore", (3, 19): "solennità di San Giuseppe",
         (3, 25): "solennità dell'Annunciazione del Signore",
         (6, 24): "solennità della Natività di San Giovanni Battista", (6, 29): "solennità dei Santi Pietro e Paolo",
         (8, 6): "festa della Trasfigurazione del Signore",
         (8, 15): "solennità dell'Assunzione della Beata Vergine Maria",
         (9, 14): "festa dell'Esaltazione della Santa Croce", (11, 1): "solennità di Tutti i Santi",
         (11, 2): "commemorazione di tutti i fedeli defunti",
         (11, 9): "festa della Dedicazione della Basilica Lateranense",
         (12, 8): "solennità dell'Immacolata Concezione", (12, 25): "solennità del Natale del Signore",
         (12, 26): "festa di Santo Stefano, primo martire",
         (12, 27): "festa di San Giovanni, apostolo ed evangelista", (12, 28): "festa dei Santi Innocenti, martiri"}


def computed(d):
    y, dow, dn = d.year, _sun_idx(d), DAYS[d.weekday()]
    E, A1, B = easter(y), advent1(y), baptism(y)
    ash, pent = E - timedelta(days=46), E + timedelta(days=49)
    e = (d - E).days
    mov = {-7: "domenica delle Palme", -3: "giovedì santo", -2: "venerdì santo", -1: "sabato santo",
           0: "domenica di Pasqua", 42: "solennità dell'Ascensione del Signore", 49: "domenica di Pentecoste",
           56: "solennità della Santissima Trinità", 63: "solennità del Santissimo Corpo e Sangue di Cristo",
           68: "solennità del Sacratissimo Cuore di Gesù"}
    if e in mov:
        return mov[e]
    if d == ash:
        return "mercoledì delle Ceneri"
    if d == A1 - timedelta(days=7):
        return "solennità di Nostro Signore Gesù Cristo Re dell'universo"
    if d == B:
        return "festa del Battesimo del Signore"
    xmas = date(y, 12, 25)
    hf = date(y, 12, 30) if _sun_idx(xmas) == 0 else xmas + timedelta(days=7 - _sun_idx(xmas))
    if d == hf:
        return "festa della Santa Famiglia di Gesù, Maria e Giuseppe"
    fx = FIXED.get((d.month, d.day))
    in_adv, in_lent, in_east = A1 <= d < xmas, ash <= d < E, E <= d <= pent
    strong = bool(fx) and fx.startswith(("solennità", "commemorazione"))
    if fx and (dow != 0 or (not (in_adv or in_lent or in_east) and (strong or re.search(r"del Signore|Santa Croce|Lateranense", fx)))):
        return fx
    if in_lent:
        if -6 <= e < 0:
            return f"{dn} santo"
        if (d - ash).days < 4:
            return f"{dn} dopo le Ceneri"
        w = (d - (ash + timedelta(days=4))).days // 7 + 1
        return f"{ORD[w]} domenica di Quaresima" if dow == 0 else f"{dn} della {ORD[w]} settimana di Quaresima"
    if in_east:
        if e < 7:
            return f"{dn} fra l'ottava di Pasqua"
        w = e // 7 + 1
        return f"{ORD[w]} domenica di Pasqua" if dow == 0 else f"{dn} della {ORD[w]} settimana di Pasqua"
    if in_adv:
        w = (d - A1).days // 7 + 1
        return f"{ORD[w]} domenica di Avvento" if dow == 0 else f"{dn} della {ORD[w]} settimana di Avvento"
    if d >= xmas or d < B:
        return f"{dn} fra l'ottava di Natale" if d.month == 12 else f"{dn} del tempo di Natale"
    sun = d - timedelta(days=dow)
    w = (sun - B).days // 7 + 1 if d < ash else 35 - (A1 - sun).days // 7
    return f"{ORD[w]} domenica del tempo ordinario" if dow == 0 else f"{dn} della {ORD[w]} settimana del tempo ordinario"


CAPS = [("tempo ordinario", "Tempo Ordinario"), ("tempo di natale", "Tempo di Natale"), ("avvento", "Avvento"),
        ("quaresima", "Quaresima"), ("pasqua", "Pasqua"), ("natale", "Natale"), ("pentecoste", "Pentecoste"),
        ("ceneri", "Ceneri"), ("palme", "Palme"), ("signore", "Signore"), ("santissima trinità", "Santissima Trinità"),
        ("santissimo corpo e sangue di cristo", "Santissimo Corpo e Sangue di Cristo"), ("cristo", "Cristo"),
        ("re dell'universo", "Re dell'Universo"), ("tutti i santi", "Tutti i Santi"), ("epifania", "Epifania"),
        ("ascensione", "Ascensione"), ("battesimo", "Battesimo"), ("santa famiglia", "Santa Famiglia"),
        ("sacratissimo cuore di gesù", "Sacratissimo Cuore di Gesù"), ("gesù", "Gesù"), ("maria", "Maria"),
        ("giuseppe", "Giuseppe"), ("beata vergine", "Beata Vergine"), ("immacolata concezione", "Immacolata Concezione")]


def capitalized(t):
    """Le maiuscole liturgiche: «settimana del Tempo Ordinario», «domenica di Avvento»…"""
    for low, cap in CAPS:
        t = re.sub(r"\b" + re.escape(low) + r"\b", cap, t, flags=re.I)
    return t


def liturgical_day(d):
    try:
        found = from_cei(d)
        if found:
            return capitalized(found), "CEI"
    except requests.RequestException:
        pass
    return capitalized(computed(d)), "calcolato"
