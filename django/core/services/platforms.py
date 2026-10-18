"""Clients des plateformes et relevé quotidien des compteurs (traduction de Services\\Platforms).

- YouTube Data API v3 : videos.list (1 unité / 50 clips) ; search.list (100 unités, admin seulement).
- Spotify Web API : métadonnées uniquement (aucun nombre de streams par titre).
- Audiomack, Boomplay : pas d'accès API ouvert, relevé manuel dans l'admin.
Pas de scraping des pages publiques : les conditions d'utilisation l'interdisent.
"""
import base64
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import requests

from core import db, env

log = logging.getLogger("cauri")
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "logs"


def log_write(channel: str, level: str, message: str, context: dict | None = None) -> None:
    """Journal fichier dans storage/logs (comme Services\\Logger) ; sur Vercel, sortie standard seulement."""
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {channel}.{level.upper()} {message}" + (
        " " + json.dumps(context, ensure_ascii=False) if context else "")
    log.info(line)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / f"{channel}-{datetime.now():%Y-%m}.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


class PlatformException(RuntimeError):
    pass


class QuotaExceededException(PlatformException):
    def __init__(self, message: str, partial: dict | None = None):
        super().__init__(message)
        self.partial = partial or {}


class HttpClient:
    """Client HTTP minimal, remplaçable par un faux client dans les tests."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def request(self, method: str, url: str, headers: dict | None = None, body: str | bytes | None = None) -> dict:
        try:
            r = requests.request(method, url, headers={"User-Agent": "CauriCharts/1.0", **(headers or {})},
                                 data=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise PlatformException(f"Requête HTTP échouée : {exc}")
        return {"status": r.status_code, "body": r.text}


class QuotaStore:
    """Compteur de quota journalier par API (table api_quota)."""

    def used(self, api: str, day: str) -> int:
        return int(db.value("SELECT units_used FROM api_quota WHERE api = ? AND day = ?", [api, day]) or 0)

    def add(self, api: str, day: str, units: int) -> None:
        db.run("""INSERT INTO api_quota (api, day, units_used) VALUES (?, ?, ?)
                  ON CONFLICT (api, day) DO UPDATE SET units_used = api_quota.units_used + EXCLUDED.units_used""", [api, day, units])


class MemoryQuotaStore(QuotaStore):
    """Quota en mémoire (tests)."""

    def __init__(self):
        self._used: dict = {}

    def used(self, api, day):
        return self._used.get(f"{api}|{day}", 0)

    def add(self, api, day, units):
        self._used[f"{api}|{day}"] = self.used(api, day) + units


def pacific_day() -> str:
    # Le quota YouTube se réinitialise à minuit, heure du Pacifique
    return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")


class YouTubeQuota:
    """Quota YouTube partagé par tous les modules ; une réserve est gardée pour le relevé des vues."""
    RESERVE = 300

    @staticmethod
    def daily() -> int:
        return int(env.get("YOUTUBE_DAILY_QUOTA", "10000") or 10000)

    @classmethod
    def spend(cls, units: int, essential: bool = False) -> bool:
        store, day = QuotaStore(), pacific_day()
        left = cls.daily() - store.used(YouTubeClient.API, day)
        if left - units < (0 if essential else cls.RESERVE):
            return False
        store.add(YouTubeClient.API, day, units)
        return True

    @classmethod
    def remaining(cls) -> int:
        return max(0, cls.daily() - QuotaStore().used(YouTubeClient.API, pacific_day()))


class ManualPlatformClient:
    """Plateformes sans accès API ouvert au projet : compteurs saisis dans l'admin ou déclarés."""

    def __init__(self, platform: str, reason: str):
        self._platform, self._reason = platform, reason

    def platform(self):
        return self._platform

    def is_available(self):
        return False

    def reason(self):
        return self._reason

    def fetch_track_stats(self, track_id):
        raise PlatformException(f"{self._platform} : {self._reason}")

    def search_track(self, query):
        return []


class YouTubeClient:
    API = "youtube"
    BATCH = 50
    BASE = "https://www.googleapis.com/youtube/v3/"

    def __init__(self, api_key: str, http: HttpClient, quota: QuotaStore, daily_quota: int = 10000, today=None):
        self.api_key, self.http, self.quota, self.daily_quota, self.today = api_key or "", http, quota, daily_quota, today

    def platform(self):
        return "youtube"

    def is_available(self):
        return self.api_key != ""

    def remaining_quota(self) -> int:
        return max(0, self.daily_quota - self.quota.used(self.API, self._day()))

    def fetch_track_stats(self, track_id):
        return self.fetch_many([track_id]).get(track_id)

    def fetch_many(self, video_ids: list) -> dict:
        """Statistiques par paquets de 50 (1 unité chacun) ; s'arrête proprement au quota épuisé."""
        self._assert_available()
        out: dict = {}
        ids = list(dict.fromkeys(video_ids))
        for i in range(0, len(ids), self.BATCH):
            chunk = ids[i:i + self.BATCH]
            if self.remaining_quota() < 1:
                raise QuotaExceededException("Quota YouTube du jour épuisé", out)
            data = self._get("videos", {"part": "statistics", "id": ",".join(chunk), "maxResults": self.BATCH}, 1)
            for item in data.get("items", []):
                s = item.get("statistics", {})
                out[item["id"]] = {
                    "plays": int(s.get("viewCount", 0)),
                    "likes": int(s["likeCount"]) if "likeCount" in s else None,  # masqué par certaines chaînes
                    "comments": int(s["commentCount"]) if "commentCount" in s else None,
                    "popularity": None,
                }
        return out

    def search_track(self, query: str) -> list:
        self._assert_available()
        if self.remaining_quota() < 100:
            raise QuotaExceededException("Quota YouTube insuffisant pour une recherche (100 unités)")
        data = self._get("search", {"part": "snippet", "type": "video", "maxResults": 10, "q": query}, 100)
        out = []
        for item in data.get("items", []):
            vid = item.get("id", {}).get("videoId", "")
            sn = item.get("snippet", {})
            out.append({"external_id": vid, "title": sn.get("title", ""), "artist": sn.get("channelTitle", ""),
                        "url": "https://www.youtube.com/watch?v=" + vid,
                        "image": sn.get("thumbnails", {}).get("medium", {}).get("url"),
                        "published_at": sn["publishedAt"][:10] if sn.get("publishedAt") else None})
        return out

    def _get(self, endpoint: str, params: dict, cost: int) -> dict:
        params = {**params, "key": self.api_key}
        # Le quota est compté avant l'appel : une requête en échec consomme aussi des unités chez Google
        self.quota.add(self.API, self._day(), cost)
        resp = self.http.request("GET", self.BASE + endpoint + "?" + urlencode(params))
        try:
            data = json.loads(resp["body"])
        except ValueError:
            data = None
        if resp["status"] != 200 or not isinstance(data, dict):
            reason = ((data or {}).get("error", {}).get("errors") or [{}])[0].get("reason") if isinstance(data, dict) else None
            reason = reason or f"HTTP {resp['status']}"
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                raise QuotaExceededException("Quota YouTube refusé par Google")
            raise PlatformException(f"YouTube {endpoint} : {reason}")
        return data

    def _assert_available(self):
        if not self.is_available():
            raise PlatformException("YOUTUBE_API_KEY absente du fichier .env")

    def _day(self) -> str:
        return self.today() if self.today else pacific_day()


class SpotifyClient:
    """Spotify Web API : métadonnées uniquement ; rien de ce client n'entre dans le score."""
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    BASE = "https://api.spotify.com/v1/"

    def __init__(self, client_id: str, client_secret: str, http: HttpClient):
        self.client_id, self.client_secret, self.http = client_id or "", client_secret or "", http
        self._token, self._expires = None, 0

    def platform(self):
        return "spotify"

    def is_available(self):
        return self.client_id != "" and self.client_secret != ""

    def fetch_track_stats(self, track_id: str):
        data = self.get("tracks/" + quote(track_id, safe=""))
        if data is None:
            return None
        images = (data.get("album") or {}).get("images") or []
        return {"plays": 0, "likes": None, "comments": None,
                "popularity": int(data["popularity"]) if "popularity" in data else None,
                "image": images[0]["url"] if images else None, "title": data.get("name")}

    def search_track(self, query: str) -> list:
        data = self.get("search?" + urlencode({"q": query, "type": "track", "limit": 10})) or {}
        out = []
        for tr in (data.get("tracks") or {}).get("items", []):
            images = (tr.get("album") or {}).get("images") or []
            out.append({"external_id": tr["id"], "title": tr["name"],
                        "artist": ", ".join(a["name"] for a in tr.get("artists", [])),
                        "url": (tr.get("external_urls") or {}).get("spotify"),
                        "image": (images[1]["url"] if len(images) > 1 else images[0]["url"]) if images else None,
                        "published_at": (tr.get("album") or {}).get("release_date")})
        return out

    def get(self, p: str):
        if not self.is_available():
            raise PlatformException("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET absents du fichier .env")
        resp = self.http.request("GET", self.BASE + p, {"Authorization": "Bearer " + self.token()})
        if resp["status"] == 404:
            return None
        if resp["status"] != 200:
            raise PlatformException(f"Spotify : HTTP {resp['status']}")
        return json.loads(resp["body"])

    def token(self) -> str:
        if self._token and time.time() < self._expires - 60:
            return self._token
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        resp = self.http.request("POST", self.TOKEN_URL, {"Authorization": "Basic " + basic,
                                 "Content-Type": "application/x-www-form-urlencoded"}, "grant_type=client_credentials")
        try:
            data = json.loads(resp["body"])
        except ValueError:
            data = {}
        if resp["status"] != 200 or not data.get("access_token"):
            raise PlatformException("Spotify : jeton refusé")
        self._token = data["access_token"]
        self._expires = time.time() + int(data.get("expires_in", 3600))
        return self._token


def _youtube(http: HttpClient) -> "YouTubeClient":
    """Clé YouTube principale ; quand son quota du jour est presque épuisé, la seconde clé (YOUTUBE_API_KEY_2, autre
    projet Google Cloud, son propre quota de 10 000 unités) prend le relais, avec son propre compteur."""
    quota = int(env.get("YOUTUBE_DAILY_QUOTA", "10000") or 10000)
    principale = YouTubeClient(env.get("YOUTUBE_API_KEY", ""), http, QuotaStore(), quota)
    seconde = env.get("YOUTUBE_API_KEY_2", "")
    if seconde and (not principale.is_available() or principale.remaining_quota() < 1000):
        relais = YouTubeClient(seconde, http, QuotaStore(), quota)
        relais.API = "youtube2"
        return relais
    return principale


def clients(http: HttpClient | None = None) -> dict:
    http = http or HttpClient()
    return {
        "youtube": _youtube(http),
        "spotify": SpotifyClient(env.get("SPOTIFY_CLIENT_ID", ""), env.get("SPOTIFY_CLIENT_SECRET", ""), http),
        "audiomack": ManualPlatformClient("audiomack", "accès API sur demande, relevé manuel en attendant"),
        "boomplay": ManualPlatformClient("boomplay", "pas d'API publique connue, relevé manuel"),
    }


class CollectService:
    """Relevé quotidien : les contenus relevés le moins récemment passent en premier."""

    def __init__(self, platform_clients: dict):
        self.clients = platform_clients

    def run(self, day: str) -> dict:
        report = {}
        for platform, client in self.clients.items():
            if not client.is_available():
                report[platform] = {"status": "ignorée", "raison": client.reason() if isinstance(client, ManualPlatformClient) else "identifiants absents du .env"}
                continue
            if platform == "youtube":
                report[platform] = self._collect_youtube(client, day)
            elif platform == "spotify":
                report[platform] = self._collect_spotify(client, day)
            else:
                report[platform] = {"status": "non géré"}
        return report

    def _queue(self, platform: str, day: str) -> list:
        return db.all(
            """SELECT tpi.id, tpi.external_id, MAX(s.captured_on) AS last_day
               FROM track_platform_ids tpi
               JOIN tracks t ON t.id = tpi.track_id AND t.is_active = 1
               JOIN artists a ON a.id = t.artist_id AND a.status <> 'out_of_scope'
               LEFT JOIN snapshots s ON s.track_platform_id = tpi.id
               WHERE tpi.platform = ?
               GROUP BY tpi.id, tpi.external_id
               HAVING MAX(s.captured_on) IS NULL OR MAX(s.captured_on) < ?
               ORDER BY MAX(s.captured_on) IS NOT NULL, MAX(s.captured_on) ASC NULLS FIRST""", [platform, day])

    def _collect_youtube(self, client: YouTubeClient, day: str) -> dict:
        queue = self._queue("youtube", day)
        by_external = {r["external_id"]: r["id"] for r in queue}
        status = "ok"
        try:
            stats = client.fetch_many(list(by_external))
        except QuotaExceededException as exc:
            stats, status = exc.partial, "quota épuisé, reste en file pour demain"
        for vid, s in stats.items():
            self.save_snapshot(int(by_external[vid]), day, s)
        return {"status": status, "en_file": len(queue), "releves": len(stats), "introuvables": len(queue) - len(stats),
                "quota_restant": client.remaining_quota()}

    def _collect_spotify(self, client: SpotifyClient, day: str) -> dict:
        done = 0
        for row in self._queue("spotify", day):
            s = client.fetch_track_stats(row["external_id"])
            if s is None:
                continue
            self.save_snapshot(int(row["id"]), day, s)
            if s.get("image"):
                # Pochette officielle si le titre n'en a pas encore
                db.run("""UPDATE tracks t SET cover_url = ? FROM track_platform_ids tpi
                          WHERE tpi.track_id = t.id AND tpi.id = ? AND t.cover_url IS NULL""", [s["image"], row["id"]])
            done += 1
        return {"status": "ok", "releves": done}

    @staticmethod
    def save_snapshot(track_platform_id: int, day: str, s: dict) -> None:
        db.run("""INSERT INTO snapshots (track_platform_id, captured_on, plays, likes, comments, popularity, source)
                  VALUES (?, ?, ?, ?, ?, ?, 'api')
                  ON CONFLICT (track_platform_id, captured_on) DO UPDATE SET plays = EXCLUDED.plays, likes = EXCLUDED.likes,
                     comments = EXCLUDED.comments, popularity = EXCLUDED.popularity""",
               [track_platform_id, day, s["plays"], s.get("likes"), s.get("comments"), s.get("popularity")])
