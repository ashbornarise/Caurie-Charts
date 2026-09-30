"""Wikidata et liste de suivi (traduction de WikidataLookup et ArtistWatch)."""
import json
import re
from pathlib import Path
from urllib.parse import quote

from core import conf, db, env
from core.repos import now_utc
from core.services.imports import chart_importer
from core.services.imports import normalizer as N
from core.services.imports.matching import ArtistEnricher
from core.services.imports.sources import YouTubeDiscoverySource
from core.services.platforms import YouTubeQuota

REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
_LETTER = r"[^\W\d_]"


def _json(resp):
    try:
        return json.loads(resp["body"])
    except (ValueError, TypeError):
        return None


def _enc(s) -> str:
    return quote(str(s), safe="-_.~")


class WikidataLookup:
    """Nationalité d'après Wikidata (gratuit, sans clé), fiches d'artistes musicaux uniquement."""
    API = "https://www.wikidata.org/w/api.php?format=json&"
    MUSIC_QIDS = ["Q639669", "Q177220", "Q2252262", "Q753110", "Q130857", "Q183945", "Q488205", "Q36834", "Q215380",
                  "Q2088357", "Q5741069", "Q855091", "Q1259917"]
    MUSIC_WORDS = re.compile(r"\b(rapp?eu?r|rappeuse|singer|chanteu[rs]e?|chanteuse|musici[ae]n|musicienne|songwriter|auteur-compositeur"
                             r"|artiste|artist|dj|producer|producteur|groupe|band|duo|beatmaker)\b", re.I)
    DEMONYMS = {
        "GH": "ghanaian|ghanéen|ghanéenne", "CI": "ivoirien|ivoirienne|ivorian", "SN": "sénégalais|sénégalaise|senegalese",
        "TG": "togolais|togolaise|togolese", "BJ": "béninois|béninoise|beninese", "NG": "nigerian|nigérian|nigériane",
        "FR": "french|français|française", "US": "american|américain|américaine", "GB": "british|britannique|english|anglais",
        "ZA": "south african|sud-africain|sud-africaine", "CM": "cameroonian|camerounais|camerounaise",
        "CD": "congolese|congolais|congolaise", "ML": "malian|malien|malienne", "BF": "burkinabé|burkinabè|burkinabe",
        "GN": "guinean|guinéen|guinéenne", "KE": "kenyan|kényan", "TZ": "tanzanian|tanzanien", "CA": "canadian|canadien|canadienne",
        "JM": "jamaican|jamaïcain", "BE": "belgian|belge", "MA": "moroccan|marocain|marocaine", "GA": "gabonese|gabonais",
    }

    def __init__(self, http):
        self.http, self.iso = http, {}

    def find(self, name: str):
        search = self._get("action=wbsearchentities&type=item&limit=7&language=fr&uselang=fr&search=" + _enc(name))
        ids = {}
        for s in search.get("search") or []:
            labels = [s.get("label") or ""] + list(s.get("aliases") or []) + [(s.get("match") or {}).get("text") or ""]
            if any(N.text(lbl) == N.text(name) for lbl in labels):
                ids[s["id"]] = s.get("description") or ""
        if not ids:
            return None
        entities = self._get("action=wbgetentities&props=claims|descriptions&languages=fr|en&ids=" + "|".join(ids)).get("entities") or {}
        found = {}
        for qid, e in entities.items():
            descs = e.get("descriptions") or {}
            desc = (((descs.get("fr") or {}).get("value") or "") + " " + ((descs.get("en") or {}).get("value") or "")).strip()
            claims = e.get("claims") or {}
            is_music = bool(set(self.MUSIC_QIDS) & set(self._values(claims, "P106") + self._values(claims, "P31"))) or bool(self.MUSIC_WORDS.search(desc))
            if not is_music:
                continue  # homonyme : village, film, prénom...
            country_qids = self._values(claims, "P27") or (self._values(claims, "P495") + self._values(claims, "P740"))
            codes = list(dict.fromkeys(c for c in (self._iso_code(q) for q in country_qids) if c))
            how = "nationalité Wikidata"
            if not codes:
                d = self.demonym(desc)
                if d:
                    codes, how = [d], f"description Wikidata « {desc[:60]} »"
            if codes:
                found[qid] = {"codes": codes, "how": how}
        if len(found) != 1:
            return None  # introuvable, ou plusieurs artistes homonymes
        qid = next(iter(found))
        codes = found[qid]["codes"]
        how = found[qid]["how"]
        note = how[:1].upper() + how[1:] + " : https://www.wikidata.org/wiki/" + qid
        if len(codes) > 1:
            # Plusieurs nationalités : l'équipe tranche (diaspora, double nationalité)
            return {"nationality": ",".join(codes), "base_country": None, "confidence": 0.5, "source": "wikidata", "note": note}
        return {"nationality": codes[0], "base_country": codes[0], "confidence": 0.9, "source": "wikidata", "note": note}

    @classmethod
    def demonym(cls, text: str):
        for code, words in cls.DEMONYMS.items():
            if re.search(rf"(?<!{_LETTER})({words})(?!{_LETTER})", text, re.I):
                return code
        return None

    @staticmethod
    def _values(claims: dict, prop: str) -> list:
        out = []
        for c in claims.get(prop) or []:
            v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            if c.get("rank") != "deprecated" and isinstance(v, dict) and "id" in v:
                out.append(v["id"])
        return out

    def _iso_code(self, qid: str):
        if qid not in self.iso:
            e = (self._get("action=wbgetentities&props=claims&ids=" + qid).get("entities") or {}).get(qid) or {}
            p297 = (e.get("claims") or {}).get("P297") or [{}]
            value = ((p297[0].get("mainsnak") or {}).get("datavalue") or {}).get("value")
            self.iso[qid] = value.upper() if isinstance(value, str) else None
        return self.iso[qid]

    def _get(self, query: str) -> dict:
        try:
            r = self.http.request("GET", self.API + query, {"User-Agent": f"CauriCharts/1.0 ( {conf.get('app.url')} )"})
        except Exception:  # noqa: BLE001
            return {}
        return (_json(r) or {}) if r["status"] == 200 else {}


class ArtistWatch:
    """Liste de suivi (config/watchlist.php) : artistes absents des classements et chaînes YouTube de labels."""
    CACHE = REPO / "storage" / "cache" / "watch-channels.json"

    def __init__(self, http):
        self.http = http

    def run(self) -> list:
        cfg = conf.get("watchlist") or {}
        report = [self._artist(str(name), hint) for name, hint in (cfg.get("artists") or {}).items()]
        for channel_id, (label, country) in self._channels(cfg).items():
            report.append(self._channel(channel_id, label, country))
        return report

    def _artist(self, name: str, hint) -> str:
        found = _json(self.http.request("GET", "https://api.deezer.com/search/artist?limit=10&q=" + _enc(name))) or {}
        profile = ArtistEnricher.best_match(found.get("data") or [], name)
        if not profile:
            return f"{name} : introuvable sur Deezer"
        top = _json(self.http.request("GET", f"https://api.deezer.com/artist/{profile['id']}/top?limit=10")) or {}
        country_id = self._country_id(hint)
        new, artist_id = 0, None
        for t in top.get("data") or []:
            track_id, stats = chart_importer.upsert_track({"title": str(t["title"]), "artist": name, "external_id": str(t["id"]),
                                                           "url": t.get("link"), "image": (t.get("album") or {}).get("cover_xl")},
                                                          "deezer", country_id)
            new += stats["new_tracks"]
            artist_id = artist_id or int(db.value("SELECT artist_id FROM tracks WHERE id = ?", [track_id]))
        if not artist_id:
            return f"{name} : aucun titre sur Deezer"
        artist = db.one("SELECT status, origin_note FROM artists WHERE id = ?", [artist_id])
        data = {"deezer_id": profile["id"], "fans": profile["nb_fan"], "image_url": profile["image"], "profile_checked_at": now_utc()}
        if artist["status"] == "pending" and "suivi" not in str(artist["origin_note"] or ""):
            # Réexamen avec les indices de scène ; le pays pressenti reste une indication, pas une confirmation
            data["origin_checked_at"] = None
            data["guessed_country_id"] = country_id if hint else None
        db.update("artists", data, "id = :id", {"id": artist_id})
        return f"{name} : suivi ({'confirmé' if artist['status'] == 'active' else artist['status']}), {new} nouveaux titres"

    def _channels(self, cfg: dict) -> dict:
        key = env.get("YOUTUBE_API_KEY", "")
        try:
            cache = json.loads(self.CACHE.read_text(encoding="utf-8")) if self.CACHE.is_file() else {}
        except ValueError:
            cache = {}
        out = {cid: (cid, country) for cid, country in (cfg.get("channels") or {}).items()}
        for label, country in (cfg.get("channel_names") or {}).items():
            if label not in cache and key and YouTubeQuota.spend(100):
                r = _json(self.http.request("GET", "https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&maxResults=3&q="
                                            + _enc(label) + "&key=" + _enc(key))) or {}
                for item in r.get("items") or []:
                    if N.text(item["snippet"]["title"]) == N.text(label):
                        cache[label] = item["snippet"]["channelId"]
                        break
                cache.setdefault(label, False)
                try:
                    self.CACHE.parent.mkdir(parents=True, exist_ok=True)
                    self.CACHE.write_text(json.dumps(cache, indent=4, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
            if cache.get(label):
                out[cache[label]] = (label, country)
        return out

    def _channel(self, channel_id: str, label: str, country) -> str:
        key = env.get("YOUTUBE_API_KEY", "")
        if not key:
            return f"{label} : clé YouTube absente"
        if not YouTubeQuota.spend(2):
            return f"{label} : quota YouTube du jour atteint, reporté"
        api = "https://www.googleapis.com/youtube/v3/"
        c = _json(self.http.request("GET", api + "channels?part=contentDetails&id=" + _enc(channel_id) + "&key=" + _enc(key))) or {}
        items = c.get("items") or [{}]
        playlist = ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
        if not playlist:
            return f"{label} : chaîne introuvable"
        pl = _json(self.http.request("GET", api + "playlistItems?part=snippet&maxResults=25&playlistId=" + _enc(playlist) + "&key=" + _enc(key))) or {}
        # Même format que la recherche YouTube, pour réutiliser le filtre « Artiste - Titre »
        videos = [{"id": {"videoId": ((it.get("snippet") or {}).get("resourceId") or {}).get("videoId", "")}, "snippet": it.get("snippet") or {}}
                  for it in pl.get("items") or []]
        rows = YouTubeDiscoverySource.parse(videos)["rows"]
        new = sum(chart_importer.upsert_track(row, "youtube_discovery", self._country_id(country))[1]["new_tracks"] for row in rows)
        return f"{label} : {len(rows)} clips lus, {new} nouveaux titres"

    @staticmethod
    def _country_id(code) -> int:
        return int(db.value("SELECT id FROM countries WHERE code = ?", [code or ""])
                   or db.value("SELECT id FROM countries WHERE is_pilot = 1 LIMIT 1"))
