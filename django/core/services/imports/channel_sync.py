"""Données YouTube de tous les titres, artiste par artiste, au moindre coût de quota (traduction de YouTubeChannelSync).

La chaîne est trouvée une fois (100 unités), ses vidéos sont lues depuis la liste de la chaîne (1 unité / 50)
et rattachées aux titres ; les chaînes connues sont relues chaque jour. Priorité : Togo et Bénin.
"""
import html
import json
import re
from urllib.parse import quote

from core import db, env
from core.repos import now_utc
from core.services.imports import chart_importer
from core.services.imports import normalizer as N
from core.services.imports.sources import YouTubeDiscoverySource
from core.services.platforms import YouTubeQuota

API = "https://www.googleapis.com/youtube/v3/"


def _enc(s) -> str:
    return quote(str(s), safe="-_.~")


class YouTubeChannelSync:
    def __init__(self, http):
        self.http = http

    def run(self, new_channels: int = 40, refresh: int = 300) -> list:
        key = env.get("YOUTUBE_API_KEY", "")
        if not key:
            return ["clé YouTube absente"]
        found = clips = created = 0
        # 1. Chaînes à trouver : artistes confirmés d'abord (Togo, Bénin en tête), puis présents dans les classements
        todo = db.all(f"""SELECT a.id, a.name, a.status, a.submission_country_id FROM artists a JOIN countries c ON c.id = a.submission_country_id
                          WHERE a.status <> 'out_of_scope' AND a.youtube_channel_id IS NULL
                            AND (a.channel_checked_at IS NULL OR a.channel_checked_at < LOCALTIMESTAMP - INTERVAL '30 days')
                          ORDER BY a.status = 'active' DESC, c.code IN ('TG', 'BJ') DESC,
                                   EXISTS (SELECT 1 FROM tracks t JOIN chart_observations o ON o.track_id = t.id
                                           WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 7) DESC,
                                   COALESCE(a.fans, 0) DESC
                          LIMIT {max(0, int(new_channels))}""")
        for a in todo:
            if not YouTubeQuota.spend(102):  # recherche (100) + deux pages de vidéos
                break
            channel = self._find_channel(a["name"], key)
            db.update("artists", {"channel_checked_at": now_utc(), **({"youtube_channel_id": channel} if channel else {})}, "id = :id", {"id": a["id"]})
            if channel:
                found += 1
                c, n = self._sync_channel(int(a["id"]), a["name"], channel, int(a["submission_country_id"]), key, 2)
                clips, created = clips + c, created + n

        # 2. Chaînes connues : nouvelles vidéos, les moins récemment relues d'abord
        known = db.all(f"""SELECT id, name, youtube_channel_id, submission_country_id FROM artists
                           WHERE status <> 'out_of_scope' AND youtube_channel_id IS NOT NULL
                             AND (channel_checked_at IS NULL OR channel_checked_at < LOCALTIMESTAMP - INTERVAL '20 hours')
                           ORDER BY status = 'active' DESC, channel_checked_at IS NOT NULL, channel_checked_at NULLS FIRST
                           LIMIT {max(0, int(refresh))}""")
        refreshed = 0
        for a in known:
            if not YouTubeQuota.spend(2):
                break
            c, n = self._sync_channel(int(a["id"]), a["name"], a["youtube_channel_id"], int(a["submission_country_id"]), key, 1)
            db.update("artists", {"channel_checked_at": now_utc()}, "id = :id", {"id": a["id"]})
            clips, created, refreshed = clips + c, created + n, refreshed + 1
        return [f"{found} nouvelles chaînes trouvées sur {len(todo)} recherchées", f"{refreshed} chaînes relues",
                f"{clips} vidéos rattachées à des titres, {created} titres ajoutés au catalogue",
                f"Quota YouTube restant : {YouTubeQuota.remaining()}"]

    def _find_channel(self, name: str, key: str):
        """Chaîne officielle : nom identique (ou « Nom - Topic », « NomVEVO », « Nom Officiel »)."""
        key0 = N.text(name).replace(" ", "")
        for item in self._get("search?part=snippet&type=channel&maxResults=5&q=" + _enc(name), key).get("items") or []:
            title = re.sub(r"\s*(-\s*topic|vevo|officiel|official|music|tv)\s*$", "", item["snippet"]["title"], flags=re.I)
            if N.text(title).replace(" ", "") == key0:
                return item["snippet"].get("channelId") or (item.get("id") or {}).get("channelId")
        return None

    def _sync_channel(self, artist_id: int, artist_name: str, channel_id: str, country_id: int, key: str, pages: int):
        uploads = "UU" + channel_id[2:]  # liste « vidéos mises en ligne » de la chaîne
        videos, token = [], ""
        for _ in range(pages):
            r = self._get("playlistItems?part=snippet&maxResults=50&playlistId=" + _enc(uploads) + ("&pageToken=" + _enc(token) if token else ""), key)
            videos += [it["snippet"] for it in r.get("items") or []]
            token = r.get("nextPageToken") or ""
            if not token:
                break
        tracks = db.all("SELECT id, title FROM tracks WHERE artist_id = ? ORDER BY id", [artist_id])
        linked = created = 0
        for v in videos:
            video_id = (v.get("resourceId") or {}).get("videoId")
            title = html.unescape(str(v.get("title") or ""))
            if not video_id or db.value("SELECT 1 FROM track_platform_ids WHERE platform = 'youtube' AND external_id = ?", [video_id]):
                continue
            track_id = self.match_track(title, tracks)
            if track_id is None:
                # « Artiste - Titre » inconnu : nouveau titre de l'artiste (hors teasers, mix, interviews)
                rows = YouTubeDiscoverySource.parse([{"id": {"videoId": video_id}, "snippet": v}])["rows"]
                row = rows[0] if rows else None
                if not row or N.artist_key(row["artist"]) != N.artist_key(artist_name):
                    continue
                _, stats = chart_importer.upsert_track(row, "youtube_channel", country_id)
                created += stats["new_tracks"]
                linked += 1
                continue
            db.run("""INSERT INTO track_platform_ids (track_id, platform, external_id, kind, url, published_at, match_status)
                      VALUES (?, 'youtube', ?, ?, ?, ?, 'auto') ON CONFLICT DO NOTHING""",
                   [track_id, video_id, self.kind(title), "https://www.youtube.com/watch?v=" + _enc(video_id),
                    v["publishedAt"][:10] if v.get("publishedAt") else None])
            linked += 1
        return linked, created

    @staticmethod
    def match_track(video_title: str, tracks: list):
        """Titre de l'artiste contenu dans le titre de la vidéo (le plus long gagne)."""
        if re.search(r"\b(teaser|extrait|snippet|making of|behind the scenes|interview|reaction|réaction)\b", video_title, re.I):
            return None
        haystack = " " + N.text(video_title) + " "
        best, best_len = None, 0
        for t in tracks:
            needle = N.title(t["title"])
            if len(needle) < 2:
                continue
            if f" {needle} " in haystack and len(needle) > best_len:
                best, best_len = int(t["id"]), len(needle)
        return best

    @staticmethod
    def kind(title: str) -> str:
        if re.search(r"lyric|paroles", title, re.I):
            return "lyrics"
        if re.search(r"visuali[sz]er|audio", title, re.I):
            return "audio"
        if re.search(r"\blive\b|en concert", title, re.I | re.A):
            return "live"
        if re.search(r"remix", title, re.I):
            return "remix"
        return "clip"

    def _get(self, p: str, key: str) -> dict:
        try:
            r = self.http.request("GET", API + p + "&key=" + _enc(key))
            return (json.loads(r["body"]) or {}) if r["status"] == 200 else {}
        except Exception:  # noqa: BLE001
            return {}
