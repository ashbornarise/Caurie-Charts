"""Découverte des artistes de chaque pays (traduction d'Import\\ArtistDiscovery).

1. Wikidata : musiciens ayant la nationalité du pays → confirmés directement (nationalité unique) ;
2. réseau Deezer : artistes proches des artistes confirmés → vérifiés ensuite par ArtistClassifier.
Seuls les candidats avec une vraie fanbase (config/discovery.php) entrent au catalogue.
"""
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from core import clock
from core import audit, conf, db, env
from core.helpers import country_name
from core.repos import now_utc
from core.services.imports import chart_importer
from core.services.imports import normalizer as N
from core.services.imports.matching import ArtistEnricher
from core.services.platforms import YouTubeQuota

REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
SEEDS_CACHE = REPO / "storage" / "cache" / "discovery-seeds.json"
REJECTED_CACHE = REPO / "storage" / "cache" / "discovery-rejected.json"


def _enc(s) -> str:
    return quote(str(s), safe="-_.~")


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except ValueError:
        return {}


def _write(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


class ArtistDiscovery:
    def __init__(self, http):
        self.http = http
        self.cfg = conf.get("discovery")
        self.budget = int(self.cfg["max_new_per_run"])
        self.rejected: dict = {}

    def run(self) -> list:
        limit = (clock.today() - timedelta(days=30)).isoformat()
        self.rejected = {k: d for k, d in _read(REJECTED_CACHE).items() if d >= limit}
        report = []
        countries = {r["code"]: r["id"] for r in db.all("SELECT id, code FROM countries WHERE is_active = 1")}
        order = list(dict.fromkeys(list(self.cfg["priority"]) + list(countries)))
        # Chaque pays a sa part du budget, pour Wikidata puis pour le réseau Deezer ; le reste passe au suivant
        order = [c for c in order if c in countries]
        share = int(self.cfg["max_new_per_run"]) // (2 * max(1, len(order)))
        left = 0
        for phase in ("wikidata", "network"):
            for code in order:
                self.budget = share + left
                if phase == "wikidata" and code in (self.cfg.get("wikidata_countries") or {}):
                    report.append(f"{code} Wikidata : " + self._wikidata(code, int(countries[code])))
                elif phase == "network":
                    report.append(f"{code} réseau Deezer : " + self._network(code, int(countries[code])))
                left = max(0, self.budget)
        report.append(f"Abonnés YouTube mis à jour : {self._refresh_subscribers()}")
        report.append(f"Profils Spotify trouvés (Wikidata) : {self._spotify_ids()}")
        _write(REJECTED_CACHE, self.rejected)
        return report

    def _sparql(self, query: str):
        r = self.http.request("GET", "https://query.wikidata.org/sparql?format=json&query=" + _enc(query),
                              {"User-Agent": f"CauriCharts/1.0 ( {conf.get('app.url')} )", "Accept": "application/sparql-results+json"})
        try:
            return (json.loads(r["body"]).get("results") or {}).get("bindings") or []
        except ValueError:
            return []

    def _wikidata(self, code: str, country_id: int) -> str:
        qid = self.cfg["wikidata_countries"][code]
        sparql = ("SELECT ?p ?pLabel (SAMPLE(?yt) AS ?yt) (SAMPLE(?dz) AS ?dz) (COUNT(DISTINCT ?nat) AS ?nats) WHERE {\n"
                  f"            ?p wdt:P27 wd:{qid} ; wdt:P27 ?nat .\n"
                  "            ?p wdt:P106 ?occ . VALUES ?occ { wd:Q177220 wd:Q2252262 wd:Q639669 wd:Q753110 wd:Q130857 wd:Q183945 wd:Q488205 wd:Q36834 wd:Q855091 }\n"
                  "            OPTIONAL { ?p wdt:P2397 ?yt } OPTIONAL { ?p wdt:P2722 ?dz }\n"
                  "            FILTER NOT EXISTS { ?p wdt:P570 ?death }\n"
                  '            SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }\n'
                  "        } GROUP BY ?p ?pLabel LIMIT 500")
        try:
            rows = self._sparql(sparql)
        except Exception:  # noqa: BLE001
            return "Wikidata injoignable"
        added = skipped = 0
        for row in rows:
            if self.budget <= 0:
                break
            label = (row.get("pLabel") or {}).get("value") or ""
            if label == "" or re.fullmatch(r"Q\d+", label) or label in self.rejected or self._exists(label):
                continue
            dz = (row.get("dz") or {}).get("value")
            profile = self._deezer("/artist/" + _enc(dz)) if dz else \
                ArtistEnricher.best_match(self._deezer("/search/artist?limit=10&q=" + _enc(label)).get("data") or [], label)
            if profile and profile.get("nb_fan") is not None and profile.get("image") is None:
                profile = {"id": int(profile["id"]), "nb_fan": int(profile["nb_fan"]), "image": profile.get("picture_xl"), "name": profile.get("name") or label}
            channel = (row.get("yt") or {}).get("value")
            subs = self._subscribers([channel]).get(channel) if channel else None
            if not self._has_fanbase(int((profile or {}).get("nb_fan") or 0), subs):
                self.rejected[label] = clock.today().isoformat()
                skipped += 1
                continue
            artist_id = self._create((profile or {}).get("name") or label, profile, country_id)
            if not artist_id:
                self.rejected[label] = clock.today().isoformat()
                skipped += 1
                continue
            single = int((row.get("nats") or {}).get("value") or 1) == 1
            data = {"youtube_channel_id": channel, "youtube_subscribers": subs, "discovered_via": "Wikidata : nationalité " + country_name(code),
                    "origin_country": code, "origin_source": "wikidata",
                    "origin_note": "Nationalité Wikidata : https://www.wikidata.org/wiki/" + row["p"]["value"].rsplit("/", 1)[-1],
                    "origin_checked_at": now_utc()}
            if single:
                # Nationalité unique : confirmé (règle : nationalité = pays de carrière)
                data.update({"status": "active", "submission_country_id": country_id, "base_country": code, "origin_confidence": 0.9})
            else:
                data.update({"origin_confidence": 0.5, "origin_note": "Plusieurs nationalités (diaspora ?) : à vérifier. " + data["origin_note"]})
            db.update("artists", data, "id = :id", {"id": artist_id})
            audit.log(None, "artist.discovered", "artist", artist_id, data["discovered_via"], data)
            added += 1
        return f"{len(rows)} fiches, {added} ajoutés, {skipped} sans fanbase suffisante"

    def _network(self, code: str, country_id: int) -> str:
        explored = _read(SEEDS_CACHE)
        seeds = db.all("""SELECT id, name, deezer_id FROM artists WHERE status = 'active' AND submission_country_id = ? AND deezer_id IS NOT NULL
                          ORDER BY fans DESC NULLS LAST""", [country_id])
        # Les moins récemment explorés d'abord ; chacun est réexploré au plus une fois par semaine
        week_ago = (clock.today() - timedelta(days=7)).isoformat()
        seeds = [s for s in seeds if explored.get(str(s["id"]), "") < week_ago][: int(self.cfg["seeds_per_run"])]
        added = 0
        stop = False
        for seed in seeds:
            explored[str(seed["id"])] = clock.today().isoformat()
            for r in self._deezer(f"/artist/{int(seed['deezer_id'])}/related?limit=25").get("data") or []:
                if self.budget <= 0:
                    stop = True
                    break
                name = str(r["name"])
                if self._exists(name) or not self._has_fanbase(int(r.get("nb_fan") or 0), None):
                    continue
                profile = {"id": int(r["id"]), "nb_fan": int(r["nb_fan"]), "image": r.get("picture_xl")}
                artist_id = self._create(name, profile, country_id)
                if artist_id:
                    # Pays pressenti seulement : vérifié par ArtistClassifier, puis choisi par l'équipe
                    db.update("artists", {"discovered_via": f"Réseau Deezer : proche de {seed['name']} ({code})",
                                          "guessed_country_id": country_id, "origin_checked_at": None}, "id = :id", {"id": artist_id})
                    added += 1
            if stop:
                break
        _write(SEEDS_CACHE, explored)
        return f"{len(seeds)} artistes explorés, {added} nouveaux candidats"

    def _create(self, name: str, profile, country_id: int):
        """Ajoute l'artiste et ses 10 titres les plus écoutés sur Deezer."""
        if not profile or not profile.get("id"):
            return None
        top = self._deezer(f"/artist/{int(profile['id'])}/top?limit=10").get("data") or []
        artist_id = None
        for t in top:
            # Titre dont l'artiste principal est bien celui-ci (pas une apparition en invité)
            if N.artist_key(str((t.get("artist") or {}).get("name") or "")) != N.artist_key(name):
                continue
            track_id, _ = chart_importer.upsert_track({"title": str(t["title"]), "artist": name, "external_id": str(t["id"]),
                                                       "url": t.get("link"), "image": (t.get("album") or {}).get("cover_xl")}, "deezer", country_id)
            artist_id = artist_id or int(db.value("SELECT artist_id FROM tracks WHERE id = ?", [track_id]))
        if not artist_id:
            return None
        db.update("artists", {"deezer_id": int(profile["id"]), "fans": int(profile["nb_fan"]), "image_url": profile.get("image"),
                              "profile_checked_at": now_utc()}, "id = :id", {"id": artist_id})
        self.budget -= 1
        return artist_id

    def _spotify_ids(self) -> int:
        """Identifiant Spotify public (P1902 de Wikidata), pour le badge « Écouter sur Spotify »."""
        values = " ".join(f"wd:{q}" for q in self.cfg["wikidata_countries"].values())
        sparql = ("SELECT ?pLabel ?alias ?sp WHERE { VALUES ?c { " + values + " } ?p wdt:P27 ?c ; wdt:P1902 ?sp .\n"
                  '            OPTIONAL { ?p skos:altLabel ?alias FILTER(LANG(?alias) IN ("fr","en")) }\n'
                  '            SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". } }')
        try:
            rows = self._sparql(sparql)
        except Exception:  # noqa: BLE001
            return 0
        n = 0
        for row in rows:
            sp = (row.get("sp") or {}).get("value") or ""
            if not re.fullmatch(r"[A-Za-z0-9]{22}", sp):
                continue
            for name in [x for x in [(row.get("pLabel") or {}).get("value") or "", (row.get("alias") or {}).get("value") or ""] if x]:
                n += db.update("artists", {"spotify_id": sp}, "match_key = :k AND spotify_id IS NULL", {"k": N.artist_key(name)})
        return n

    def _refresh_subscribers(self) -> int:
        rows = db.all("SELECT id, youtube_channel_id FROM artists WHERE youtube_channel_id IS NOT NULL AND status <> 'out_of_scope' ORDER BY id LIMIT 500")
        n = 0
        for i in range(0, len(rows), 50):
            chunk = rows[i:i + 50]
            subs = self._subscribers([r["youtube_channel_id"] for r in chunk])
            for r in chunk:
                if r["youtube_channel_id"] in subs:
                    db.update("artists", {"youtube_subscribers": subs[r["youtube_channel_id"]]}, "id = :id", {"id": r["id"]})
                    n += 1
        return n

    def _subscribers(self, channel_ids: list) -> dict:
        """Abonnés YouTube par chaîne (1 unité de quota pour 50 chaînes)."""
        key = env.get("YOUTUBE_API_KEY", "")
        if not key or not channel_ids or not YouTubeQuota.spend(1):
            return {}
        try:
            r = json.loads(self.http.request("GET", "https://www.googleapis.com/youtube/v3/channels?part=statistics&id="
                                             + _enc(",".join(channel_ids)) + "&key=" + _enc(key))["body"])
        except Exception:  # noqa: BLE001
            return {}
        return {item["id"]: int((item.get("statistics") or {}).get("subscriberCount") or 0)
                for item in r.get("items") or [] if not (item.get("statistics") or {}).get("hiddenSubscriberCount")}

    def _has_fanbase(self, fans: int, subs) -> bool:
        return fans >= int(self.cfg["min_deezer_fans"]) or (subs or 0) >= int(self.cfg["min_youtube_subs"])

    @staticmethod
    def _exists(name: str) -> bool:
        return bool(db.value("SELECT 1 FROM artists WHERE match_key = ?", [N.artist_key(name)]))

    def _deezer(self, p: str) -> dict:
        time.sleep(0.12)  # limite Deezer : 50 requêtes par 5 secondes
        try:
            r = self.http.request("GET", "https://api.deezer.com" + p)
            data = json.loads(r["body"])
        except Exception:  # noqa: BLE001
            return {}
        return data if isinstance(data, dict) and "error" not in data else {}
