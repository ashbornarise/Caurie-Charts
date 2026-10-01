"""Actualités importées des médias musicaux (traduction de News\\FeedParser et News\\FeedImporter).

On ne garde que le titre, un court résumé, une vignette et le lien vers l'article (le média est toujours cité).
Les vignettes sont téléchargées et recadrées : aucune requête vers un site tiers depuis le navigateur du visiteur.
"""
import email.utils
import hashlib
import html
import io
import ipaddress
import re
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from defusedxml import ElementTree as ET

from core import conf, db, storage
from core.helpers import slugify
from core.repos import now_utc

MEDIA_NS = "{http://search.yahoo.com/mrss/}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

COUNTRY_WORDS = {
    "TG": ["togo", "togolais", "togolaise", "lomé", "lome"],
    "BJ": ["bénin", "benin", "béninois", "béninoise", "cotonou"],
    "GH": ["ghana", "ghanaian", "ghanéen", "ghanéenne", "accra", "kumasi"],
    "CI": ["côte d'ivoire", "côte d’ivoire", "ivory coast", "ivoirien", "ivoirienne", "abidjan"],
    "SN": ["sénégal", "senegal", "sénégalais", "sénégalaise", "senegalese", "dakar"],
    "NG": ["nigeria", "nigérian", "nigériane", "nigerian", "lagos", "abuja", "naija"],
}
CATEGORY_WORDS = {
    "evenement": r"festivals?|concerts?|tournée|tour|olympia|scènes?|awards?|cérémonie|vmas?|grammys?|headline|performs?|stage",
    "sortie": r"albums?|singles?|clips?|ep|nouveau titre|sortie|dévoile|release[sd]?|drops?|vidéo|video|mixtape|feat|tracklist",
}
MUSIC_WORDS = (r"music|musique|musical|songs?|chansons?|albums?|ep|singles?|singer|chanteur|chanteuse|rapper|rappeur|rap|artistes?|artists?|"
               r"concerts?|festival|tour|clip|afrobeats?|amapiano|highlife|hiplife|afropop|gospel|coupé-décalé|mbalax|dj|producer|beatmaker|lyrics|grammys?|vmas?|"
               r"headies|awards?|stream(s|ing)?|spotify|audiomack|boomplay|billboard|charts?|playlist|mixtape|remix|collab")


# ---------------------------------------------------------------- lecture des flux

def is_http(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s/$.?#][^\s]*$", url or "", re.I))


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]*>", "", s or "")


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_strip_tags(value))).strip()


def _summary(h: str) -> str:
    # Les flux WordPress terminent souvent par « L'article X est apparu en premier sur Y »
    h = re.sub(r"<p>\s*(L[’']article|The post)\b.*?</p>", "", h or "", flags=re.I | re.S)
    t = _text(h)
    t = re.sub(r"\s*(\[(…|\.\.\.|&#8230;)\]|Lire la suite.*|Read more.*)$", "…", t, flags=re.I)
    if len(t) > 260:
        t = t[:257].rstrip(" ,.;:-") + "…"
    return t


def _date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        d = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _child_text(el, tag: str) -> str:
    c = el.find(tag)
    return "".join(c.itertext()) if c is not None else ""


def _image(item, h: str):
    """media:content, media:thumbnail, enclosure image, puis première <img> du contenu."""
    for c in item.findall(MEDIA_NS + "content"):
        typ, medium = c.get("type") or "", c.get("medium") or ""
        if medium == "image" or typ.startswith("image/") or (typ == "" and medium == ""):
            if is_http(c.get("url") or ""):
                return c.get("url")
    for t in item.findall(MEDIA_NS + "thumbnail"):
        if is_http(t.get("url") or ""):
            return t.get("url")
    for e in item.findall("enclosure"):
        if (e.get("type") or "").startswith("image/") and is_http(e.get("url") or ""):
            return e.get("url")
    m = re.search(r"""<img[^>]+src=["']([^"']+)["']""", h or "", re.I)
    if m and is_http(html.unescape(m.group(1))):
        return html.unescape(m.group(1))
    return None


def parse_feed(xml: str) -> list:
    """Flux RSS 2.0 ou Atom → articles normalisés."""
    try:
        doc = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except Exception:  # noqa: BLE001
        return []
    items = []
    channel = doc.find("channel")
    if channel is not None and channel.find("item") is not None:
        for it in channel.findall("item"):
            url = _child_text(it, "link").strip()
            content = _child_text(it, CONTENT_NS + "encoded")
            desc = _child_text(it, "description")
            items.append({"guid": _child_text(it, "guid").strip() or url, "title": _text(_child_text(it, "title")), "url": url,
                          "summary": _summary(desc if desc != "" else content), "published_at": _date(_child_text(it, "pubDate")),
                          "image": _image(it, desc + content)})
    elif doc.tag in ("feed", ATOM_NS + "feed"):
        ns = ATOM_NS if doc.tag.startswith("{") else ""
        for en in doc.findall(ns + "entry"):
            url = ""
            for link in en.findall(ns + "link"):
                if (link.get("rel") or "") in ("", "alternate"):
                    url = link.get("href") or ""
                    break
            h = _child_text(en, ns + "summary") + _child_text(en, ns + "content")
            items.append({"guid": _child_text(en, ns + "id").strip() or url, "title": _text(_child_text(en, ns + "title")), "url": url,
                          "summary": _summary(h), "published_at": _date(_child_text(en, ns + "published") or _child_text(en, ns + "updated")),
                          "image": _image(en, h)})
    return [i for i in items if i["title"] != "" and is_http(i["url"])]


def og_image(page: str):
    for prop in ("og:image", "twitter:image"):
        p = re.escape(prop)
        m = (re.search(rf"""<meta[^>]+(?:property|name)=["']{p}["'][^>]*content=["']([^"']+)["']""", page, re.I)
             or re.search(rf"""<meta[^>]+content=["']([^"']+)["'][^>]*(?:property|name)=["']{p}["']""", page, re.I))
        if m and is_http(html.unescape(m.group(1))):
            return html.unescape(m.group(1))
    return None


# ---------------------------------------------------------------- téléchargement sûr

def is_public_host(host: str) -> bool:
    """L'hôte ne résout que vers des adresses publiques (protection SSRF)."""
    if not host or host.lower() == "localhost":
        return False
    try:
        ips = [host] if _is_ip(host) else list({a[4][0] for a in socket.getaddrinfo(host, None)})
    except OSError:
        return False
    if not ips:
        return False
    for ip in ips:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified:
            return False
    return True


def _is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def http_get(url: str, binary: bool = False):
    """Suit les redirections soi-même en vérifiant chaque étape (jamais d'adresse locale ou privée)."""
    for _ in range(5):
        if not is_http(url) or not is_public_host(urlparse(url).hostname or ""):
            return None
        try:
            r = requests.get(url, allow_redirects=False, timeout=20, stream=True,
                             headers={"User-Agent": f"Mozilla/5.0 (compatible; CauriChartsBot/1.0; +{conf.get('app.url')})"})
            if 300 <= r.status_code < 400 and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            body = r.raw.read(8_000_001, decode_content=True)
        except requests.RequestException:
            return None
        if len(body) > 8_000_000 or not (200 <= r.status_code < 300):
            return None
        return body if binary else body.decode(r.encoding or "utf-8", errors="replace")
    return None


# ---------------------------------------------------------------- import

def detect_country(text: str):
    for code, words in COUNTRY_WORDS.items():
        if any(w in text for w in words):
            return code
    return None


def _has_word(text: str, alternatives: str) -> bool:
    return bool(re.search(rf"(?<![^\W_])(?:{alternatives})(?![^\W_])", text, re.I))


def detect_category(text: str) -> str:
    for category, words in CATEGORY_WORDS.items():
        if _has_word(text, words):
            return category
    return "industrie"


def is_about_music(text: str) -> bool:
    return _has_word(text, MUSIC_WORDS)


class FeedImporter:
    def __init__(self, fetch=None):
        self.fetch = fetch or http_get

    def run(self) -> list:
        cfg = conf.get("news")
        report = []
        for feed in cfg["feeds"]:
            xml = self.fetch(feed["url"])
            if xml is None:
                report.append(f"{feed['name']} : flux injoignable")
                continue
            items = parse_feed(xml)[: int(cfg["per_feed"])]
            added = images = 0
            for item in items:
                result = self._store(feed, item, int(cfg["max_age_days"]))
                added += 1 if result else 0
                images += 1 if result == "image" else 0
            report.append(f"{feed['name']} : {len(items)} articles lus, {added} ajoutés ({images} avec vignette)")
        removed = self._prune(int(cfg["keep"]))
        if removed:
            report.append(f"{removed} anciennes actualités importées retirées")
        return report

    def _store(self, feed: dict, item: dict, max_age_days: int):
        guid = hashlib.sha256((feed["url"] + "|" + item["guid"]).encode()).hexdigest()[:64]
        if db.value("SELECT 1 FROM news WHERE external_guid = ?", [guid]):
            return None
        now = now_utc()
        published = item.get("published_at") or now
        if datetime.strptime(published, "%Y-%m-%d %H:%M:%S") < datetime.strptime(now, "%Y-%m-%d %H:%M:%S") - timedelta(days=max_age_days):
            return None
        published = min(published, now)
        text = (item["title"] + " " + item["summary"]).lower()
        if feed.get("music_only") and not is_about_music(text):
            return None
        image_url = item.get("image")
        if not image_url:
            page = self.fetch(item["url"])
            image_url = og_image(page) if page else None
        image = self._thumbnail(image_url, guid) if image_url else None
        country = detect_country(text)
        db.insert("news", {
            "title": item["title"][:200], "slug": slugify(item["title"])[:200] + "-" + guid[:6],
            "summary": (item["summary"] if item["summary"] != "" else item["title"])[:400], "category": detect_category(text),
            "country_id": db.value("SELECT id FROM countries WHERE code = ?", [country]) if country else None,
            "source_name": feed["name"], "source_url": item["url"][:500], "image_path": image, "origin": "feed",
            "external_guid": guid, "status": "published", "published_at": published,
        })
        return "image" if image else "text"

    def _thumbnail(self, url: str, guid: str):
        """Télécharge, vérifie et recadre l'image en 16:9 (JPEG) ; retourne le nom du fichier."""
        from PIL import Image
        cfg = conf.get("news.image")
        data = self.fetch(url, binary=True) if self.fetch is http_get else self.fetch(url)
        if data is None or isinstance(data, str) or len(data) > cfg["max_bytes"]:
            return None
        try:
            src = Image.open(io.BytesIO(data))
            src.load()
        except Exception:  # noqa: BLE001
            return None
        w, h = src.size
        if w < 400 or h < 220:
            return None  # logo ou icône : la carte affiche sa teinte à la place
        tw, th = int(cfg["width"]), int(cfg["height"])
        scale = max(tw / w, th / h)
        cw, ch = round(tw / scale), round(th / scale)
        left, top = int((w - cw) / 2), int((h - ch) / 3)
        dst = src.convert("RGB").resize((tw, th), Image.LANCZOS, box=(left, top, left + cw, top + ch))
        buf = io.BytesIO()
        dst.save(buf, "JPEG", quality=80)
        name = guid[:24] + ".jpg"
        try:
            storage.store_media("news", name, buf.getvalue(), "image/jpeg")
        except Exception:  # noqa: BLE001
            return None
        return name

    @staticmethod
    def _prune(keep: int) -> int:
        """Ne garde que les $keep actualités importées les plus récentes (et retire leurs vignettes)."""
        old = db.all(f"SELECT id, image_path FROM news WHERE origin = 'feed' ORDER BY published_at DESC LIMIT 100000 OFFSET {max(0, keep)}")
        for row in old:
            if row["image_path"]:
                f = storage.MEDIA / "news" / row["image_path"].split("/")[-1]
                if f.is_file():
                    f.unlink()
            db.run("DELETE FROM news WHERE id = ?", [row["id"]])
        return len(old)
