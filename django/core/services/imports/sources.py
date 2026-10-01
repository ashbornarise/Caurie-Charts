"""Sources de classement par pays (traduction des *ChartSource PHP).

fetch() retourne None si le pays n'est pas couvert, sinon
{'observed_on': 'AAAA-MM-JJ', 'rows': [{'position', 'title', 'artist', 'external_id', 'url', 'image', 'release_date'}, ...]}
"""
import csv
import html
import io
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from core import clock
from core import db
from core.services.imports import normalizer as N
from core.services.platforms import PlatformException


def _json(resp):
    try:
        return json.loads(resp["body"])
    except (ValueError, TypeError):
        return None


def _today() -> str:
    return clock.today().isoformat()


def months_ago(n: int, today: date | None = None) -> str:
    """strtotime('-n months') de PHP : un jour inexistant déborde sur le mois suivant (31 mars - 1 mois = 3 mars)."""
    import calendar
    d = today or clock.today()
    total = d.year * 12 + d.month - 1 - n
    y, m = divmod(total, 12)
    m += 1
    extra = d.day - calendar.monthrange(y, m)[1]
    return (date(y, m, min(d.day, calendar.monthrange(y, m)[1])) + timedelta(days=max(0, extra))).isoformat()


class AppleMusicChartSource:
    """« Les plus écoutés » par pays, flux public d'Apple (sans clé, 100 titres). Pas de classement pour le Togo."""
    URL = "https://rss.marketingtools.apple.com/api/v2/{}/music/most-played/{}/songs.json"

    def __init__(self, http, limit: int = 100):
        self.http, self.limit = http, limit

    def key(self):
        return "apple_music"

    def is_available(self):
        return True

    def fetch(self, code: str):
        resp = self.http.request("GET", self.URL.format(code.lower(), self.limit))
        if resp["status"] in (400, 404, 500):
            return None  # pays non couvert par Apple Music
        data = _json(resp)
        if resp["status"] != 200 or not isinstance(data, dict) or "results" not in (data.get("feed") or {}):
            raise PlatformException(f"Apple Music : réponse inattendue (HTTP {resp['status']})")
        return self.parse(data)

    @staticmethod
    def parse(data: dict) -> dict:
        updated = data.get("feed", {}).get("updated")
        try:
            day = datetime.fromisoformat(updated.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat() if updated else _today()
        except ValueError:
            day = _today()
        rows = []
        for i, r in enumerate(data["feed"]["results"]):
            art = r.get("artworkUrl100")
            rows.append({"position": i + 1, "title": str(r["name"]), "artist": str(r["artistName"]), "external_id": str(r["id"]),
                         "url": r.get("url"), "image": art.replace("100x100bb", "600x600bb") if art else None,  # 600 px
                         "release_date": r.get("releaseDate")})
        return {"observed_on": day, "rows": rows}


class DeezerChartSource:
    """« Top <pays> » du compte Deezer Charts : Côte d'Ivoire et Sénégal seulement."""
    PLAYLISTS = {"CI": 1362497945, "SN": 1362523075, "NG": 1362516565}
    URL = "https://api.deezer.com/playlist/{}/tracks?limit=100"

    def __init__(self, http):
        self.http = http

    def key(self):
        return "deezer"

    def is_available(self):
        return True

    def fetch(self, code: str):
        playlist = self.PLAYLISTS.get(code.upper())
        if playlist is None:
            return None
        resp = self.http.request("GET", self.URL.format(playlist))
        data = _json(resp)
        if resp["status"] != 200 or not isinstance(data, dict) or "data" not in data or "error" in data:
            raise PlatformException(f"Deezer : réponse inattendue (HTTP {resp['status']})")
        return self.parse(data)

    @staticmethod
    def parse(data: dict) -> dict:
        rows = []
        for i, t in enumerate(data["data"]):
            album = t.get("album") or {}
            rows.append({"position": i + 1, "title": str(t.get("title") or ""), "artist": str((t.get("artist") or {}).get("name") or ""),
                         "external_id": str(t.get("id") or ""), "url": t.get("link"), "image": album.get("cover_xl") or album.get("cover_big")})
        return {"observed_on": _today(), "rows": [r for r in rows if r["title"] and r["artist"]]}


class ShazamChartSource:
    """Top 200 Shazam (7 derniers jours), CSV public : Ghana, Côte d'Ivoire, Sénégal, Nigeria."""
    SLUGS = {"GH": "ghana", "CI": "ivory-coast", "SN": "senegal", "NG": "nigeria"}
    URL = "https://www.shazam.com/services/charts/csv/top-200/{}"

    def __init__(self, http):
        self.http = http

    def key(self):
        return "shazam"

    def is_available(self):
        return True

    def fetch(self, code: str):
        slug = self.SLUGS.get(code.upper())
        if slug is None:
            return None
        resp = self.http.request("GET", self.URL.format(slug), {"User-Agent": "Mozilla/5.0 (compatible; CauriCharts/1.0)"})
        if resp["status"] != 200:
            raise PlatformException(f"Shazam : réponse inattendue (HTTP {resp['status']})")
        return self.parse(resp["body"])

    @staticmethod
    def parse(text: str) -> dict:
        text = text.lstrip("﻿")
        rows = []
        for line in re.split(r"\r\n|\n|\r", text):
            cols = next(csv.reader(io.StringIO(line)), [])
            if len(cols) < 3 or not cols[0].strip().isdigit():
                continue  # date, en-tête, lignes vides
            rows.append({"position": int(cols[0]), "artist": cols[1].strip(), "title": cols[2].strip()})
        return {"observed_on": _today(), "rows": [r for r in rows if r["artist"] and r["title"]]}


class AudiomackChartSource:
    """« Weekly 100 » par pays : clé API accordée sur demande ; en attendant, import CSV dans l'admin."""
    PLAYLISTS = {"TG": "togo", "BJ": "benin", "CI": "cote-divoire", "SN": "senegal", "GH": "ghana"}

    def __init__(self, consumer_key: str, consumer_secret: str):
        self.consumer_key, self.consumer_secret = consumer_key, consumer_secret

    def key(self):
        return "audiomack"

    def is_available(self):
        return False  # à activer quand fetch() sera branché sur l'API

    def fetch(self, code: str):
        raise PlatformException("Audiomack : accès API à obtenir, utiliser l'import CSV en attendant.")


_SPLIT_CLEAN = re.compile(r"\s*[\(\[][^\)\]]*(official|officiel|clip|video|vidéo|audio|lyric|visuali[sz]er|live|prod\.?|dir\.?|by )[^\)\]]*[\)\]]", re.I)
_QUOTES = " \t\"'“”«»"


class YouTubeTrendingSource:
    """Vidéos musicales populaires par pays (videos.list chart=mostPopular, 1 unité) : Ghana, Sénégal, Nigeria."""
    COUNTRIES = ["GH", "SN", "NG"]
    URL = "https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&videoCategoryId=10&maxResults=50&regionCode={}&key={}"

    def __init__(self, http, api_key: str):
        self.http, self.api_key = http, api_key or ""

    def key(self):
        return "youtube_trending"

    def is_available(self):
        return self.api_key != ""

    def fetch(self, code: str):
        code = code.upper()
        if code not in self.COUNTRIES:
            return None
        resp = self.http.request("GET", self.URL.format(code, quote(self.api_key, safe="")))
        data = _json(resp)
        if resp["status"] != 200 or not isinstance(data, dict) or "items" not in data:
            raise PlatformException(f"YouTube tendances : réponse inattendue (HTTP {resp['status']})")
        return self.parse(data)

    @classmethod
    def parse(cls, data: dict) -> dict:
        rows = []
        for i, v in enumerate(data["items"]):
            sn = v.get("snippet") or {}
            artist, title = cls.split(str(sn.get("title") or ""), str(sn.get("channelTitle") or ""))
            if artist == "" or title == "":
                continue
            rows.append({"position": i + 1, "title": title, "artist": artist, "external_id": str(v["id"]), "platform": "youtube",
                         "kind": cls.kind(str(sn.get("title") or "")), "url": "https://www.youtube.com/watch?v=" + quote(str(v["id"]), safe="-_.~"),
                         "image": ((sn.get("thumbnails") or {}).get("high") or {}).get("url"),
                         "release_date": sn["publishedAt"][:10] if sn.get("publishedAt") else None})
        return {"observed_on": _today(), "rows": rows}

    @staticmethod
    def split(video_title: str, channel: str) -> tuple[str, str]:
        """« Artiste - Titre (Clip Officiel) » → (Artiste, Titre) ; sans tiret, l'artiste est la chaîne."""
        clean = _SPLIT_CLEAN.sub("", video_title)
        clean = re.sub(r"\s*\|.*$", "", clean).strip()
        channel = re.sub(r"\s*(-\s*Topic|VEVO|Official|Officiel|TV|Music)\s*$", "", channel, flags=re.I).strip()
        m = re.match(r"^(.+?)\s+[-–—~]\s+(.+)$", clean)
        if m:
            return m.group(1).strip(), m.group(2).strip(_QUOTES)
        return channel, clean.strip(_QUOTES)

    @staticmethod
    def kind(title: str) -> str:
        if re.search(r"lyric", title, re.I):
            return "lyrics"
        if re.search(r"visuali[sz]er|audio", title, re.I):
            return "audio"
        if re.search(r"\blive\b", title, re.I | re.A):
            return "live"
        return "clip"


class YouTubeDiscoverySource:
    """Nouveaux clips les plus vus (21 jours) pour les pays sans classement de plateforme : Togo, Bénin (100 unités/recherche)."""
    QUERIES = {"TG": ["togo clip officiel", "musique togolaise 2026"], "BJ": ["bénin clip officiel", "musique béninoise 2026"]}
    URL = ("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&videoCategoryId=10&order=viewCount&maxResults=50"
           "&publishedAfter={}&q={}&key={}")
    EXCLUDE = re.compile(r"\b(teaser|extrait|mix|mixtape vol|interview|s['’]exprime|live session|challenge|karaok[eé]|reaction|réaction"
                         r"|making of|behind|playlist|compilation|non[- ]stop)\b", re.I)

    def __init__(self, http, api_key: str):
        self.http, self.api_key = http, api_key or ""

    def key(self):
        return "youtube_discovery"

    def is_available(self):
        return self.api_key != ""

    def fetch(self, code: str):
        queries = self.QUERIES.get(code.upper())
        if queries is None:
            return None
        after = (datetime.now(timezone.utc) - timedelta(days=21)).strftime("%Y-%m-%dT%H:%M:%SZ")
        items: dict = {}
        for q in queries:
            resp = self.http.request("GET", self.URL.format(quote(after, safe=""), quote(q, safe=""), quote(self.api_key, safe="")))
            data = _json(resp)
            if resp["status"] != 200 or not isinstance(data, dict) or "items" not in data:
                msg = ((data or {}).get("error") or {}).get("message") if isinstance(data, dict) else None
                raise PlatformException("YouTube découverte : " + (msg or f"HTTP {resp['status']}"))
            for i, item in enumerate(data["items"]):
                vid = (item.get("id") or {}).get("videoId")
                # Rang combiné : meilleure place obtenue dans l'une des recherches
                if vid and (vid not in items or items[vid]["rank"] > i):
                    items[vid] = {"rank": i, "item": item}
        ordered = sorted(items.values(), key=lambda x: x["rank"])
        return self.parse([x["item"] for x in ordered])

    @classmethod
    def parse(cls, items: list) -> dict:
        rows = []
        for v in items:
            sn = v.get("snippet") or {}
            video_title = html.unescape(str(sn.get("title") or ""))
            if cls.EXCLUDE.search(video_title) or not re.search(r"\s[-–—]\s", video_title):
                continue
            artist, title = YouTubeTrendingSource.split(video_title, html.unescape(str(sn.get("channelTitle") or "")))
            if artist == "" or title == "" or len(artist) > 60:
                continue
            vid = str((v.get("id") or {}).get("videoId") or "")
            rows.append({"position": len(rows) + 1, "title": title, "artist": artist, "external_id": vid, "platform": "youtube",
                         "kind": "clip", "url": "https://www.youtube.com/watch?v=" + quote(vid, safe="-_.~"),
                         "image": ((sn.get("thumbnails") or {}).get("high") or {}).get("url"),
                         "release_date": sn["publishedAt"][:10] if sn.get("publishedAt") else None})
        return {"observed_on": _today(), "rows": rows}


class DeezerPopularitySource:
    """Titres des artistes confirmés d'un pays classés par popularité Deezer (« rank ») : rend visibles le Togo et le Bénin."""

    def __init__(self, http, size: int = 200):
        self.http, self.size = http, size

    def key(self):
        return "deezer_popularity"

    def is_available(self):
        return True

    def fetch(self, code: str):
        artists = db.all("""SELECT a.name, a.deezer_id FROM artists a JOIN countries c ON c.id = a.submission_country_id
                            WHERE a.status = 'active' AND a.deezer_id IS NOT NULL AND c.code = ?""", [code.upper()])
        if not artists:
            return None
        tracks: dict = {}
        for a in artists:
            time.sleep(0.12)  # limite Deezer : 50 requêtes par 5 secondes
            try:
                top = _json(self.http.request("GET", f"https://api.deezer.com/artist/{int(a['deezer_id'])}/top?limit=50")) or {}
            except Exception:  # noqa: BLE001
                continue
            for t in top.get("data") or []:
                # Titres dont il est l'artiste principal (ses featurings comptent chez l'autre artiste)
                if N.artist_key(str((t.get("artist") or {}).get("name") or "")) != N.artist_key(a["name"]) or not t.get("rank"):
                    continue
                tracks[str(t["id"])] = {"rank_score": int(t["rank"]), "title": str(t["title"]), "artist": a["name"],
                                        "external_id": str(t["id"]), "platform": "deezer", "url": t.get("link"),
                                        "image": (t.get("album") or {}).get("cover_xl")}
        return self.rank(list(tracks.values()), self.size)

    @staticmethod
    def rank(tracks: list, size: int) -> dict:
        tracks = sorted(tracks, key=lambda t: -t["rank_score"])
        rows = []
        for i, t in enumerate(tracks[:size]):
            rows.append({"position": i + 1, **{k: v for k, v in t.items() if k != "rank_score"}})
        return {"observed_on": _today(), "rows": rows}


class YouTubeViewsSource:
    """Vues YouTube des clips suivis (relevés quotidiens) : vues gagnées sur 6 jours, sinon vues des clips de moins de 18 mois."""

    def __init__(self, size: int = 100):
        self.size = size

    def key(self):
        return "youtube_views"

    def is_available(self):
        return True

    def fetch(self, code: str):
        clips = db.all(
            """SELECT t.title, a.name AS artist, p.external_id, p.url, p.published_at,
                   (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id ORDER BY s.captured_on DESC LIMIT 1) AS views,
                   (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id AND s.captured_on <= CURRENT_DATE - 6
                     ORDER BY s.captured_on DESC LIMIT 1) AS views_before
               FROM track_platform_ids p
               JOIN tracks t ON t.id = p.track_id
               JOIN artists a ON a.id = t.artist_id AND a.status = 'active'
               JOIN countries c ON c.id = a.submission_country_id AND c.code = ?
               WHERE p.platform = 'youtube'
               ORDER BY p.id""", [code.upper()])
        if not clips:
            return None
        with_history = any(c["views_before"] is not None for c in clips)
        recent = months_ago(18)
        scored = []
        for c in clips:
            if c["views"] is None:
                continue
            if with_history:
                score = int(c["views"]) - int(c["views_before"]) if c["views_before"] is not None else None
            else:
                score = int(c["views"]) if not c["published_at"] or str(c["published_at"])[:10] >= recent else None
            if score is not None and score > 0:
                scored.append({**c, "score": score})
        scored.sort(key=lambda c: -c["score"])
        rows = [{"position": i + 1, "title": c["title"], "artist": c["artist"], "external_id": c["external_id"],
                 "platform": "youtube", "kind": "clip", "url": c["url"]} for i, c in enumerate(scored[: self.size])]
        return {"observed_on": _today(), "rows": rows} if rows else None
