"""Rapprochements et profils (traduction de YouTubeMatcher, DeezerTrackMatcher, ArtistEnricher et SceneSignals)."""
import json
import re
import time
from urllib.parse import quote

from core import db
from core.repos import now_utc
from core.services.imports import normalizer as N
from core.services.platforms import PlatformException, QuotaExceededException


def _json(resp):
    try:
        return json.loads(resp["body"])
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- clip YouTube officiel

class YouTubeMatcher:
    """Trouve le clip officiel des titres qui n'en ont pas (100 unités par recherche, marqué « auto »)."""
    MIN_SCORE = 4

    def __init__(self, youtube):
        self.youtube = youtube

    @staticmethod
    def score(result: dict, title: str, artist: str) -> int:
        haystack, channel = N.text(result.get("title") or ""), N.text(result.get("artist") or "")
        artist_key, title_key = N.artist_key(artist), N.title(title)
        score = 0
        if artist_key and (artist_key in haystack or artist_key in channel or artist_key.replace(" ", "") in channel):
            score += 2
        if title_key and title_key in haystack:
            score += 2
        if re.search(r"\b(official|officiel|clip|video)\b", haystack):
            score += 1
        for word in ["lyrics", "lyric", "cover", "remix", "live", "reaction", "instrumental", "karaoke", "slowed", "sped up"]:
            if word in haystack and word not in N.text(title):
                score -= 3
                break
        return score

    @classmethod
    def best(cls, results: list, title: str, artist: str):
        best, best_score = None, cls.MIN_SCORE - 1
        for r in results:
            s = cls.score(r, title, artist)
            if s > best_score and r.get("external_id"):
                best, best_score = {**r, "score": s}, s
        return best

    def run(self, limit: int) -> dict:
        candidates = db.all(
            f"""SELECT t.id, t.title, a.name AS artist,
                   (SELECT COUNT(*) FROM chart_observations o WHERE o.track_id = t.id AND o.observed_on >= CURRENT_DATE - 14) AS recent
                FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id
                WHERE t.is_active = 1 AND a.status = 'active'
                  AND NOT EXISTS (SELECT 1 FROM track_platform_ids p WHERE p.track_id = t.id AND p.platform = 'youtube')
                  AND (t.youtube_checked_at IS NULL OR t.youtube_checked_at < LOCALTIMESTAMP - INTERVAL '14 days')
                -- Pays sans classement de plateforme d'abord, puis un titre par artiste, puis les plus présents
                -- Artistes sans chaîne connue d'abord : la lecture de leur chaîne (1 unité) trouve déjà les clips des autres
                ORDER BY a.youtube_channel_id IS NULL DESC, c.code IN ('TG', 'BJ') DESC,
                         (SELECT COUNT(*) FROM track_platform_ids p2 JOIN tracks t2 ON t2.id = p2.track_id
                           WHERE t2.artist_id = a.id AND p2.platform = 'youtube') ASC,
                         recent DESC, t.id DESC LIMIT {max(0, int(limit))}""")
        stats = {"searched": 0, "matched": 0, "status": "ok"}
        for c in candidates:
            try:
                results = self.youtube.search_track(c["artist"] + " " + c["title"])
            except QuotaExceededException:
                stats["status"] = "quota épuisé"
                break
            except PlatformException as exc:
                stats["status"] = f"arrêt : {exc}"
                break
            stats["searched"] += 1
            db.update("tracks", {"youtube_checked_at": now_utc()}, "id = :id", {"id": c["id"]})
            best = self.best(results, c["title"], c["artist"])
            if best:
                db.run("""INSERT INTO track_platform_ids (track_id, platform, external_id, kind, url, published_at, match_status)
                          VALUES (?, 'youtube', ?, 'clip', ?, ?, 'auto') ON CONFLICT DO NOTHING""",
                       [c["id"], best["external_id"], best["url"], best["published_at"]])
                stats["matched"] += 1
        return stats


# ---------------------------------------------------------------- identifiants Deezer

class DeezerTrackMatcher:
    """Retrouve sur Deezer (recherche gratuite) les titres des classements sans identifiant Deezer."""

    def __init__(self, http):
        self.http = http

    def run(self, limit: int = 400) -> dict:
        tracks = db.all(
            f"""SELECT t.id, t.title, a.name AS artist, t.cover_url FROM tracks t JOIN artists a ON a.id = t.artist_id
                WHERE a.status <> 'out_of_scope'
                  AND NOT EXISTS (SELECT 1 FROM track_platform_ids p WHERE p.track_id = t.id AND p.platform = 'deezer')
                  AND EXISTS (SELECT 1 FROM chart_observations o WHERE o.track_id = t.id AND o.observed_on >= CURRENT_DATE - 30)
                ORDER BY a.status = 'active' DESC, t.id DESC LIMIT {max(0, int(limit))}""")
        matched = 0
        for t in tracks:
            time.sleep(0.13)  # limite Deezer : 50 requêtes par 5 secondes
            try:
                # Recherche simple « artiste titre » (la syntaxe avancée ne renvoie plus rien)
                q = N.primary_artist(t["artist"]) + " " + re.sub(r"\s*[\(\[].*$", "", t["title"])
                r = _json(self.http.request("GET", "https://api.deezer.com/search?limit=5&q=" + quote(q, safe="-_.~"))) or {}
            except Exception:  # noqa: BLE001
                continue
            for d in r.get("data") or []:
                if N.track_key(str(d["title"]), str((d.get("artist") or {}).get("name") or "")) == N.track_key(t["title"], t["artist"]):
                    db.run("""INSERT INTO track_platform_ids (track_id, platform, external_id, kind, url, match_status)
                              VALUES (?, 'deezer', ?, 'main', ?, 'auto') ON CONFLICT DO NOTHING""", [t["id"], str(d["id"]), d.get("link")])
                    cover = (d.get("album") or {}).get("cover_xl")
                    if not t["cover_url"] and cover:
                        db.update("tracks", {"cover_url": cover}, "id = :id", {"id": t["id"]})
                    matched += 1
                    break
        return {"checked": len(tracks), "matched": matched}


# ---------------------------------------------------------------- profils Deezer

class ArtistEnricher:
    """Photo et nombre de fans (API publique Deezer), revérifiés au plus tous les 7 jours."""
    API = "https://api.deezer.com"

    def __init__(self, http, pause_ms: int = 120):
        self.http, self.pause_ms = http, pause_ms

    def run(self, limit: int = 80) -> dict:
        artists = db.all(f"""SELECT id, name, deezer_id FROM artists
                             WHERE status <> 'out_of_scope' AND (profile_checked_at IS NULL OR profile_checked_at < LOCALTIMESTAMP - INTERVAL '7 days')
                             ORDER BY profile_checked_at IS NOT NULL, id LIMIT {max(0, int(limit))}""")
        stats = {"checked": 0, "found": 0}
        for a in artists:
            profile = self._profile(int(a["id"]), a["name"], int(a["deezer_id"]) if a["deezer_id"] else None)
            data = {"profile_checked_at": now_utc()}
            if profile:
                data.update({"deezer_id": profile["id"], "fans": profile["nb_fan"], "image_url": profile["image"]})
                stats["found"] += 1
            db.update("artists", data, "id = :id", {"id": a["id"]})
            stats["checked"] += 1
        return stats

    def _profile(self, artist_id: int, name: str, deezer_id):
        deezer_id = deezer_id or self._id_from_tracks(artist_id, name)
        if deezer_id:
            artist = self._get(f"/artist/{deezer_id}")
            if artist and "id" in artist:
                return self.normalize(artist)
        found = self._get("/search/artist?limit=10&q=" + quote(name, safe="-_.~")) or {}
        return self.best_match(found.get("data") or [], name)

    def _id_from_tracks(self, artist_id: int, name: str):
        track_id = db.value("""SELECT p.external_id FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id
                               WHERE t.artist_id = ? AND p.platform = 'deezer' LIMIT 1""", [artist_id])
        if not track_id:
            return None
        track = self._get("/track/" + quote(str(track_id), safe="")) or {}
        for c in [track.get("artist") or {}] + list(track.get("contributors") or []):
            if "id" in c and "name" in c and N.text(c["name"]) == N.text(name):
                return int(c["id"])
        return None

    @classmethod
    def best_match(cls, results: list, name: str):
        key = N.text(name)
        matches = [r for r in results if "name" in r and N.text(r["name"]) == key]
        if not matches:
            return None
        matches.sort(key=lambda r: -(r.get("nb_fan") or 0))
        return cls.normalize(matches[0])

    @staticmethod
    def normalize(artist: dict) -> dict:
        image = artist.get("picture_xl") or artist.get("picture_big")
        # Deezer renvoie une silhouette grise quand l'artiste n'a pas de photo : on garde les initiales
        if image and re.search(r"/images/artist//", image):
            image = None
        return {"id": int(artist["id"]), "nb_fan": int(artist.get("nb_fan") or 0), "image": image}

    def _get(self, p: str):
        time.sleep(self.pause_ms / 1000)  # limite Deezer : 50 requêtes par 5 secondes
        try:
            resp = self.http.request("GET", self.API + p)
        except Exception:  # noqa: BLE001
            return None
        data = _json(resp)
        return data if resp["status"] == 200 and isinstance(data, dict) and "error" not in data else None


# ---------------------------------------------------------------- indices de scène

class SceneSignals:
    """Marqueurs locaux (villes, gentilés, indicatifs, langues) comptés dans des textes publics."""
    MARKERS = {
        "TG": ["togo", "togolais", "togolaise", "lomé", "lome", "kara", "sokodé", "kpalimé", "aného", "228", "éwé", "ewe", "mina", "kabyè", "kabye", "tg228"],
        "BJ": ["bénin", "benin", "béninois", "béninoise", "cotonou", "porto-novo", "parakou", "abomey", "229", "fon", "goun", "yoruba du bénin"],
        "CI": ["côte d'ivoire", "côte d’ivoire", "ivoirien", "ivoirienne", "abidjan", "yopougon", "yop", "abobo", "cocody", "bouaké", "225",
               "nouchi", "babi", "rap ivoire", "coupé-décalé", "coupe decale"],
        "SN": ["sénégal", "senegal", "sénégalais", "sénégalaise", "dakar", "pikine", "thiès", "saint-louis", "221", "wolof", "galsen", "mbalax", "kebetu"],
        "GH": ["ghana", "ghanaian", "accra", "kumasi", "tema", "233", "twi", "hiplife", "highlife", "asakaa", "drill gh"],
        "NG": ["nigeria", "nigerian", "naija", "lagos", "abuja", "ibadan", "port harcourt", "234", "yoruba", "igbo", "hausa",
               "street pop", "afrobeats naija"],
        "BF": ["burkina", "burkinabè", "burkinabé", "burkinabe", "ouagadougou", "ouaga", "bobo-dioulasso", "226", "mooré", "moore", "faso"],
        "CV": ["cap-vert", "cabo verde", "cape verde", "capverdien", "capverdienne", "praia", "mindelo", "238", "morna", "funaná", "kizomba cv"],
        "GM": ["gambie", "gambia", "gambian", "gambien", "banjul", "serrekunda", "220", "mandinka"],
        "GW": ["guinée-bissau", "guinea-bissau", "bissau", "bissau-guinéen", "245", "gumbé", "kriol"],
        "LR": ["liberia", "libéria", "liberian", "libérien", "monrovia", "231", "hipco"],
        "NE": ["niger", "nigérien", "nigérienne", "niamey", "zinder", "maradi", "227", "zarma", "haoussa du niger"],
        "SL": ["sierra leone", "sierra-léonais", "sierra leonean", "freetown", "232", "krio", "salone"],
        "GN": ["guinée", "guinea conakry", "guinéen", "guinéenne", "conakry", "kankan", "224", "soussou", "peul", "malinké"],
        "ML": ["mali", "malien", "malienne", "bamako", "ségou", "sikasso", "223", "bambara", "wassoulou"],
        "MR": ["mauritanie", "mauritania", "mauritanien", "mauritanienne", "nouakchott", "nouadhibou", "222", "hassaniya"],
    }
    PAYOUT_COUNTRIES = ["FR", "US", "GB", "BE", "CA", "DE", "NL", "CH", "IT", "ES", "AE"]
    _LETTER = r"[^\W\d_]"

    @classmethod
    def score(cls, text: str) -> dict:
        text = text.lower()
        scores: dict = {}
        for code, words in cls.MARKERS.items():
            for w in words:
                pattern = (rf"(?<!\d){w}(?!\d)" if w.isdigit()          # indicatif : nombre isolé
                           else rf"(?<!{cls._LETTER}){re.escape(w)}(?!{cls._LETTER})")
                n = len(re.findall(pattern, text))
                if n:
                    scores[code] = scores.get(code, 0) + min(n, 3)
        return dict(sorted(scores.items(), key=lambda kv: -kv[1]))

    @staticmethod
    def dominant(scores: dict):
        """Pays dominant si les indices sont nets (3 points au moins et deux fois plus que le suivant)."""
        if not scores:
            return None
        values = list(scores.values())
        top, second = values[0], values[1] if len(values) > 1 else 0
        return next(iter(scores)) if top >= 3 and top >= 2 * second else None
