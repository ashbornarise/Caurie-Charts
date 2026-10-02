"""Fonctions d'affichage, traduction fidèle de src/helpers.php (mêmes sorties HTML)."""
import hashlib
import math
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from markupsafe import Markup, escape

from core import conf
from core.i18n import locale, t

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "public" / "assets"

PERIOD_SLUGS = {"semaine": "week", "mois": "month", "annee": "year", "tout": "all"}
PERIOD_BY_TYPE = {v: k for k, v in PERIOD_SLUGS.items()}


def e(value) -> str:
    return str(escape("" if value is None else value))


def _qs(query: dict | None) -> str:
    if not query:
        return ""
    return "?" + urlencode({k: ("" if v is None else v) for k, v in query.items()}, doseq=True)


def url(p: str = "/", query: dict | None = None) -> str:
    return conf.get("app.url") + "/" + p.lstrip("/") + _qs(query)


def path(p: str = "/", query: dict | None = None) -> str:
    return "/" + p.lstrip("/") + _qs(query)


_ASSET_VERSIONS: dict = {}


def asset(file: str) -> str:
    """Adresse versionnée par le contenu du fichier : sur Vercel, la date des fichiers est figée et ne change pas
    d'un déploiement à l'autre, alors que les fichiers sont servis « immuables » pendant un an."""
    if file not in _ASSET_VERSIONS:
        full = ASSETS_DIR / file
        _ASSET_VERSIONS[file] = hashlib.md5(full.read_bytes()).hexdigest()[:8] if full.is_file() else "0"
    return f"/assets/{file}?v={_ASSET_VERSIONS[file]}"


def brand() -> str:
    return str(conf.get("app.name"))


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def fmt_number(n) -> str:
    n = 0 if n is None else float(n)
    # Arrondi comme number_format de PHP (moitié vers l'extérieur)
    rounded = int(math.floor(abs(n) + 0.5)) * (1 if n >= 0 else -1)
    s = f"{abs(rounded):,}"
    sep = " " if locale() == "fr" else ","
    return ("-" if rounded < 0 else "") + s.replace(",", sep)


_FR_MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_date(value, with_year: bool = True) -> str:
    d = _to_date(value)
    if locale() == "fr":
        return f"{d.day} {_FR_MONTHS[d.month - 1]}" + (f" {d.year}" if with_year else "")
    return f"{_EN_MONTHS[d.month - 1]} {d.day}" + (f", {d.year}" if with_year else "")


def month_name(month: int) -> str:
    fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    return (fr if locale() == "fr" else en)[month - 1]


def slugify(text: str) -> str:
    # Comme transliterator_transliterate('Any-Latin; Latin-ASCII') en PHP (ɔ → o, œ → oe, ß → ss)
    from unidecode import unidecode
    text = unidecode(str(text))
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).lower().strip("-")
    return text or "n-a"


def initials(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]+", "", str(text or ""), flags=re.UNICODE).replace("_", "")
    words = cleaned.strip().split()
    return "".join(w[0].upper() for w in words[:2])


def country_name(code: str) -> str:
    return t("country." + str(code).upper())


def chart_name(code: str) -> str:
    return str(conf.get(f"charts.{code}.name", code))


def ucfirst(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def period_label(run: dict) -> str:
    pt = run["period_type"]
    if pt == "week":
        return t("period.week_of", start=fmt_date(run["period_start"], False), end=fmt_date(run["period_end"]))
    if pt == "month":
        key = str(run["period_key"])
        return ucfirst(month_name(int(key[5:7]))) + " " + key[:4]
    return t("period.year_n", year=run["period_key"]) + (" · " + t("period.provisional") if run.get("is_provisional") else "")


def movement(entry: dict) -> dict:
    prev = entry.get("previous_position")
    if prev is None:
        return {"type": "re" if int(entry["weeks_on_chart"]) > 1 else "new", "value": None}
    diff = int(prev) - int(entry["position"])
    return {"type": "up" if diff > 0 else ("down" if diff < 0 else "same"), "value": abs(diff)}


def is_group_label(label_owner) -> bool:
    return label_owner is not None and label_owner == conf.get("app.group_label.code")


def chart_path(country_code: str, chart_code: str, period_type: str = "week", key: str | None = None) -> str:
    slug = PERIOD_BY_TYPE[period_type]
    if str(country_code).upper() == "WA" or chart_code == "prime-wa":
        query = {} if chart_code in ("prime", "prime-wa") else {"classement": chart_code}
        return path("classements/afrique-de-l-ouest/" + slug + ("/" + key if key else ""), query)
    return path("classements/" + str(country_code).lower() + "/" + chart_code + "/" + slug + ("/" + key if key else ""))


def _php_round(x: float, n: int = 1):
    r = math.floor(abs(x) * 10 ** n + 0.5) / 10 ** n
    r = r if x >= 0 else -r
    return int(r) if r == int(r) else r


def rank_chart_svg(points: list, max_rank: int, aria_label: str) -> Markup:
    w, h, pad_l, pad_r, pad_t, pad_b = 640, 240, 36, 16, 16, 28
    n = len(points)
    max_rank = max([max_rank] + [int(p["position"]) for p in points])

    def x(i):
        return pad_l + i * (w - pad_l - pad_r) / (n - 1) if n > 1 else (w + pad_l - pad_r) / 2

    def y(rank):
        return pad_t + (rank - 1) * (h - pad_t - pad_b) / max(1, max_rank - 1)

    svg = f'<svg class="rank-chart" viewBox="0 0 {w} {h}" role="img" aria-label="{e(aria_label)}">'
    for rank in dict.fromkeys([1, math.ceil(max_rank / 2), max_rank]):
        yy = _php_round(y(rank))
        svg += f'<line class="rank-chart__grid" x1="{pad_l}" x2="{w - pad_r}" y1="{yy}" y2="{yy}"/>'
        svg += f'<text class="rank-chart__axis" x="{pad_l - 8}" y="{_php_round(yy + 4)}" text-anchor="end">{rank}</text>'
    if n > 1:
        d = [("L" if i else "M") + f"{_php_round(x(i))} {_php_round(y(int(p['position'])))}" for i, p in enumerate(points)]
        svg += '<path class="rank-chart__line" d="' + " ".join(d) + '"/>'
    for i, p in enumerate(points):
        cx, cy = _php_round(x(i)), _php_round(y(int(p["position"])))
        tip = e(p["label"] + " : " + t("chart.position_n", n=p["position"]))
        svg += (f'<g class="rank-chart__pt"><title>{tip}</title><circle class="rank-chart__hit" cx="{cx}" cy="{cy}" r="14"/>'
                f'<circle class="rank-chart__dot" cx="{cx}" cy="{cy}" r="5"/></g>')
    if n > 0:
        svg += f'<text class="rank-chart__axis" x="{pad_l}" y="{h - 8}">{e(points[0]["label"])}</text>'
        if n > 1:
            svg += f'<text class="rank-chart__axis" x="{w - pad_r}" y="{h - 8}" text-anchor="end">{e(points[-1]["label"])}</text>'
    return Markup(svg + "</svg>")


def flag(code: str, height: int = 20, cls: str = "flag") -> Markup:
    file = f"img/flags/{str(code).lower()}.svg"
    if not (ASSETS_DIR / file).is_file():
        return Markup("")
    width = round(height * 1.5)
    return Markup(f'<img class="{e(cls)}" src="{asset(file)}" alt="" width="{width}" height="{height}" loading="lazy">')


def legal(key: str) -> Markup:
    value = str(conf.get(f"app.legal.{key}", "") or "").strip()
    return Markup(e(value)) if value else Markup(f'<mark class="todo">{e(t("legal.todo"))}</mark>')


def platform_name(platform: str) -> str:
    return {"youtube": "YouTube", "audiomack": "Audiomack", "boomplay": "Boomplay", "spotify": "Spotify",
            "apple_music": "Apple Music", "deezer": "Deezer"}.get(platform, ucfirst(platform))


def url_with(u: str, query: dict) -> str:
    return u + ("&" if "?" in u else "?") + urlencode(query) if query else u


def spotify_url(artist_spotify_id, artist: str, title: str | None = None) -> str:
    if artist_spotify_id and re.fullmatch(r"[A-Za-z0-9]{22}", str(artist_spotify_id)):
        return "https://open.spotify.com/artist/" + artist_spotify_id
    return "https://open.spotify.com/search/" + quote((artist + " " + (title or "")).strip(), safe="")


def period_slug(period_type: str) -> str:
    return PERIOD_BY_TYPE[period_type]


def rawurlencode(s) -> str:
    return quote(str(s), safe="-_.~")


def share_url(run_id: int, fmt: str) -> str:
    return url(f"partage/{int(run_id)}-{fmt}")


def nl2br(s) -> Markup:
    """Comme nl2br(e($s)) en PHP : texte échappé, « <br /> » devant chaque saut de ligne."""
    return Markup(re.sub(r"(\r\n|\n\r|\n|\r)", r"<br />\1", e(s)))


def paragraphs(s) -> list[str]:
    return re.split(r"\n\s*\n", str(s or "").strip())


def url_host(u) -> str:
    from urllib.parse import urlparse
    return urlparse(str(u)).hostname or ""


def number_format(n, decimals: int = 0, dec_point: str = ".", thousands: str = ",") -> str:
    """number_format de PHP (arrondi moitié vers l'extérieur)."""
    n = float(n or 0)
    q = math.floor(abs(n) * 10 ** decimals + 0.5)
    whole, frac = divmod(q, 10 ** decimals)
    s = f"{int(whole):,}".replace(",", thousands)
    if decimals:
        s += dec_point + str(int(frac)).zfill(decimals)
    return ("-" if n < 0 and q else "") + s


def from_json(s):
    import json
    try:
        return json.loads(s) if s else None
    except (TypeError, ValueError):
        return None


def to_json(v) -> str:
    """json_encode de PHP (séparateurs compacts, « / » échappé, Unicode échappé)."""
    import json
    return json.dumps(v, separators=(",", ":")).replace("/", r"\/")


def php_str(v) -> str:
    """(string) d'une valeur PHP : 1.0 → « 1 », 0.35 → « 0.35 », null → «  »."""
    if v is None or v is False:
        return ""
    if v is True:
        return "1"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


def add_days(day, n: int) -> str:
    from datetime import timedelta
    return (_to_date(day) + timedelta(days=n)).isoformat()
