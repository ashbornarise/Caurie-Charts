"""Données YouTube de tous les titres, artiste par artiste, au moindre coût de quota (traduction de YouTubeChannelSync).

La chaîne est trouvée une fois (1 à 3 unités par une vidéo connue ou le pseudo @nom ; 100 en dernier recours), ses vidéos sont lues depuis la liste de la chaîne (1 unité / 50)
et rattachées aux titres ; les chaînes connues sont relues chaque jour. Priorité : Togo et Bénin.
"""
import html
import json
import re
from urllib.parse import quote

from core import budget, db, env
from core.repos import now_utc
from core.services.imports import chart_importer
from core.services.imports import normalizer as N
from core.services.imports.sources import YouTubeDiscoverySource
from core.services.platforms import YouTubeQuota

API = "https://www.googleapis.com/youtube/v3/"


def _enc(s) -> str:
    return quote(str(s), safe="-_.~")


class YouTubeChannelSync:
    SEARCHES = 8  # recherches par nom (100 unités) par passage, en dernier recours

    def __init__(self, http):
        self.http = http
        self.searches_left = self.SEARCHES

    def run(self, new_channels: int = 40, refresh: int = 300) -> list:
        key = env.get("YOUTUBE_API_KEY", "")
        if not key:
            return ["clé YouTube absente"]
        found = clips = created = 0
        # 1. Chaînes à trouver : artistes confirmés d'abord (Togo, Bénin en tête), puis présents dans les classements
        todo = db.all(f"""SELECT a.id, a.name, a.status, a.submission_country_id FROM artists a JOIN countries c ON c.id = a.submission_country_id
                          WHERE a.status <> 'out_of_scope' AND a.youtube_channel_id IS NULL
                            AND (a.channel_checked_at IS NULL OR a.channel_checked_at < LOCALTIMESTAMP - INTERVAL '30 days')
                          -- Les artistes présents dans un classement cette semaine d'abord (ce sont eux que le public consulte)
                          ORDER BY EXISTS (SELECT 1 FROM tracks t JOIN chart_observations o ON o.track_id = t.id
                                           WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 7) DESC,
                                   a.status = 'active' DESC, c.code IN ('TG', 'BJ') DESC,
                                   COALESCE(a.fans, 0) DESC
                          LIMIT {max(0, int(new_channels))}""")
        self.searches_left = self.SEARCHES
        for a in todo:
            if budget.over():
                break  # temps de l'étape écoulé : la suite la nuit prochaine
            if YouTubeQuota.remaining() < YouTubeQuota.RESERVE + 10:
                break
            channel = self._find_channel(a["name"], key, int(a["id"]))
            if channel and not self.confirms(channel, int(a["id"]), key):
                channel = None  # chaîne d'un homonyme : aucune de ses vidéos ne porte un titre de l'artiste
            db.update("artists", {"channel_checked_at": now_utc(), **({"youtube_channel_id": channel} if channel else {})}, "id = :id", {"id": a["id"]})
            if channel and YouTubeQuota.spend(2):  # deux pages de vidéos
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
            if budget.over():
                break  # temps de l'étape écoulé : la suite la nuit prochaine
            if not YouTubeQuota.spend(2):
                break
            c, n = self._sync_channel(int(a["id"]), a["name"], a["youtube_channel_id"], int(a["submission_country_id"]), key, 1)
            db.update("artists", {"channel_checked_at": now_utc()}, "id = :id", {"id": a["id"]})
            clips, created, refreshed = clips + c, created + n, refreshed + 1
        stats = refresh_channel_stats()
        return [f"{found} nouvelles chaînes trouvées sur {len(todo)} recherchées", f"{refreshed} chaînes relues",
                f"abonnés et vues totales relevés pour {stats} chaînes",
                f"{clips} vidéos rattachées à des titres, {created} titres ajoutés au catalogue",
                f"Quota YouTube restant : {YouTubeQuota.remaining()}"]

    @staticmethod
    def same_name(channel_title: str, name: str) -> bool:
        """Chaîne officielle : nom identique (ou « Nom - Topic », « NomVEVO », « Nom Officiel »)."""
        title = re.sub(r"\s*(-\s*topic|vevo|officiel|official|music|tv)\s*$", "", channel_title or "", flags=re.I)
        return N.text(title).replace(" ", "") == N.text(name).replace(" ", "") != ""

    @staticmethod
    def handles(name: str) -> list:
        """Pseudos YouTube probables : @nom, @nomofficiel, @nommusic (sans espaces ni accents)."""
        base = re.sub(r"[^a-z0-9._-]", "", N.text(name).replace(" ", ""))
        return [h for h in dict.fromkeys([base, base + "officiel", base + "official", base + "music"]) if len(h) >= 3][:3]

    def _find_channel(self, name: str, key: str, artist_id: int | None = None):
        """Chaînes portant le nom de l'artiste, du moins cher au plus cher : vidéos déjà connues (1 unité), pseudos @nom
        (1 unité chacun), recherche (100, plafonnée). Entre plusieurs chaînes officielles (principale, VEVO, Topic),
        celle qui a le plus d'abonnés."""
        found, titles = [], {}
        if artist_id:
            videos = [r["external_id"] for r in db.all("""SELECT p.external_id FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id
                                                         WHERE t.artist_id = ? AND p.platform = 'youtube' LIMIT 10""", [artist_id])]
            if videos and YouTubeQuota.spend(1):
                for it in self._get("videos?part=snippet&id=" + _enc(",".join(videos)), key).get("items") or []:
                    sn = it.get("snippet") or {}
                    if sn.get("channelId") and self.same_name(sn.get("channelTitle", ""), name):
                        found.append(sn["channelId"])
                        titles[sn["channelId"]] = sn.get("channelTitle", "")
        for handle in self.handles(name):
            if not YouTubeQuota.spend(1):
                break
            for item in self._get("channels?part=snippet&forHandle=" + _enc("@" + handle), key).get("items") or []:
                if self.same_name((item.get("snippet") or {}).get("title", ""), name):
                    found.append(item["id"])
                    titles[item["id"]] = (item.get("snippet") or {}).get("title", "")
        secondary = re.compile(r"(-\s*topic|vevo)\s*$", re.I)
        # Seulement une chaîne VEVO ou « Topic » (générée par YouTube) : la chaîne principale se trouve par la recherche
        only_secondary = bool(found) and all(secondary.search(titles.get(f, "")) for f in found)
        if (not found or only_secondary) and self.searches_left > 0 and YouTubeQuota.spend(100):
            self.searches_left -= 1
            results = self._get("search?part=snippet&type=channel&maxResults=8&q=" + _enc(name + " music"), key).get("items") or []
            for item in results:
                if self.same_name(item["snippet"]["title"], name):
                    cid = item["snippet"].get("channelId") or (item.get("id") or {}).get("channelId")
                    found.append(cid)
                    titles[cid] = item["snippet"]["title"]
            if not found and results and artist_id:
                # Aucun nom identique : l'IA choisit parmi les vraies chaînes trouvées ; la vérification par titre reste obligatoire
                pick = self._ai_pick(name, artist_id, results, key)
                if pick:
                    found.append(pick)
        found = list(dict.fromkeys(f for f in found if f))
        if artist_id:
            # Seules les chaînes dont une vidéo porte un titre de l'artiste comptent (écarte les homonymes : joueurs, fans…)
            found = [f for f in found if self.confirms(f, artist_id, key)]
            only_secondary = bool(found) and all(secondary.search(titles.get(f, "") or "") for f in found)
            if (not found or only_secondary) and self.searches_left > 0 and YouTubeQuota.spend(100):
                # Homonymes seulement, ou seulement VEVO / Topic : recherche « nom + titre phare », puis l'IA choisit parmi les vraies chaînes trouvées
                self.searches_left -= 1
                hit = db.value("SELECT t.title FROM tracks t WHERE t.artist_id = ? ORDER BY (SELECT COUNT(*) FROM chart_observations o WHERE o.track_id = t.id) DESC LIMIT 1", [artist_id]) or ""
                results = self._get("search?part=snippet&type=channel&maxResults=8&q=" + _enc(f"{name} {hit}"), key).get("items") or []
                cands = [it["snippet"].get("channelId") or (it.get("id") or {}).get("channelId") for it in results
                         if self.same_name(it["snippet"]["title"], name)]
                pick = self._ai_pick(name, artist_id, results, key) if results else None
                for it in results:
                    titles.setdefault(it["snippet"].get("channelId") or (it.get("id") or {}).get("channelId"), it["snippet"]["title"])
                for c in dict.fromkeys([*cands, *([pick] if pick else [])]):
                    if c and c not in found and self.confirms(c, artist_id, key):
                        found.append(c)
        if len(found) <= 1:
            return found[0] if found else None
        if not YouTubeQuota.spend(1):
            return found[0]
        subs = {it["id"]: int((it.get("statistics") or {}).get("subscriberCount") or 0)
                for it in self._get("channels?part=statistics&id=" + _enc(",".join(found)), key).get("items") or []}
        # Chaîne principale avant VEVO et Topic, puis la plus suivie
        return max(found, key=lambda c: (not secondary.search(titles.get(c, "")), subs.get(c, 0)))

    def _ai_pick(self, name: str, artist_id: int, results: list, key: str):
        """Chaîne officielle choisie par l'IA parmi les résultats réels de la recherche (jamais une adresse inventée)."""
        from core.services import ai
        client = ai.make()
        if not client or not client.is_available():
            return None
        ids = [(it["snippet"].get("channelId") or (it.get("id") or {}).get("channelId")) for it in results]
        ids = [i for i in ids if i]
        stats = {}
        if ids and YouTubeQuota.spend(1):
            stats = {it["id"]: it.get("statistics") or {} for it in self._get("channels?part=statistics&id=" + _enc(",".join(ids)), key).get("items") or []}
        titles = [r["title"] for r in db.all("SELECT title FROM tracks WHERE artist_id = ? ORDER BY id LIMIT 12", [artist_id])]
        options = [{"id": i, "nom": it["snippet"]["title"], "description": str(it["snippet"].get("description") or "")[:160],
                    "abonnes": int((stats.get(i) or {}).get("subscriberCount") or 0)} for i, it in zip(ids, results)]
        system = ("Tu identifies la chaîne YouTube OFFICIELLE d'un artiste musical parmi une liste de chaînes réelles. "
                  "Réponds uniquement en JSON : {\"id\": \"<id de la liste>\" ou null}. Choisis null en cas de doute : "
                  "jamais une chaîne de fans, de compilation, de paroles ou d'un homonyme. N'invente aucun identifiant.")
        prompt = json.dumps({"artiste": name, "ses_titres": titles, "chaines": options}, ensure_ascii=False)
        try:
            pick = (ai.extract_json(client.ask(system, prompt, 300)["text"]) or {}).get("id")
        except Exception:  # noqa: BLE001
            return None
        return pick if pick in ids else None  # un identifiant hors de la liste est ignoré

    def confirms(self, channel_id: str, artist_id: int, key: str) -> bool:
        """La chaîne est celle de l'artiste si l'une de ses 50 dernières vidéos porte un titre de notre catalogue (1 unité)."""
        if not YouTubeQuota.spend(1):
            return False
        r = self._get("playlistItems?part=snippet&maxResults=50&playlistId=" + _enc("UU" + channel_id[2:]), key)
        tracks = db.all("SELECT id, title FROM tracks WHERE artist_id = ? ORDER BY id", [artist_id])
        return any(self.match_track(html.unescape(str((it.get("snippet") or {}).get("title") or "")), tracks) for it in r.get("items") or [])

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


def refresh_channel_stats(limit: int = 1000) -> int:
    """Abonnés et vues totales des chaînes officielles (1 unité de quota pour 50 chaînes), les moins récentes d'abord."""
    from core.services.platforms import YouTubeQuota
    key = env.get("YOUTUBE_API_KEY", "")
    rows = db.all(f"""SELECT id, youtube_channel_id FROM artists WHERE youtube_channel_id IS NOT NULL AND status <> 'out_of_scope'
                      ORDER BY youtube_views_total IS NOT NULL, id LIMIT {int(limit)}""")
    n = 0
    for i in range(0, len(rows), 50):
        chunk = rows[i:i + 50]
        if not key or not YouTubeQuota.spend(1):
            break
        try:
            from core.services.platforms import HttpClient
            r = json.loads(HttpClient(20).request("GET", API + "channels?part=statistics&id=" + _enc(",".join(c["youtube_channel_id"] for c in chunk))
                                                  + "&key=" + _enc(key))["body"])
        except Exception:  # noqa: BLE001
            continue
        stats = {it["id"]: it.get("statistics") or {} for it in r.get("items") or []}
        for c in chunk:
            st = stats.get(c["youtube_channel_id"])
            if st:
                db.update("artists", {"youtube_views_total": int(st.get("viewCount") or 0),
                                      "youtube_subscribers": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount") or 0)},
                          "id = :id", {"id": c["id"]})
                n += 1
    return n
