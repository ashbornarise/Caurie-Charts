"""Classement automatique du pays des artistes découverts (traduction d'Import\\ArtistClassifier).

MusicBrainz et Wikidata recoupés, puis l'IA qui juge des indices collectés gratuitement (chaîne YouTube,
Wikipédia, artistes proches, marqueurs de scène). Règle : c'est le pays où l'artiste mène sa carrière qui fait foi.
Décision automatique seulement au-dessus du seuil (config/ai.php), journalisée et modifiable dans l'admin.
"""
import html
import json
import re
import time
from urllib.parse import quote

from core import audit, conf, db, env
from core.helpers import country_name
from core.repos import now_utc, php_round
from core.services import ai
from core.services.imports import normalizer as N
from core.services.imports.matching import SceneSignals
from core.services.imports.watch import WikidataLookup
from core.services.platforms import YouTubeQuota

MB = "https://musicbrainz.org/ws/2/artist?fmt=json&limit=5&query="


def _enc(s) -> str:
    return quote(str(s), safe="-_.~")


def _json(resp):
    try:
        return json.loads(resp["body"])
    except (ValueError, TypeError):
        return None


class ArtistClassifier:
    def __init__(self, http, ai_client=None):
        self.http, self.ai = http, ai_client
        self.evidence_cache: dict = {}
        self.searches_left = 15  # recherches YouTube par nom (100 unités chacune) par passage

    def run(self, limit: int = 60) -> dict:
        cfg = conf.get("ai.classify")
        covered = {r["code"]: r["id"] for r in db.all("SELECT id, code FROM countries WHERE is_active = 1")}
        artists = db.all(f"""SELECT a.id, a.name, c.code AS guessed FROM artists a LEFT JOIN countries c ON c.id = a.guessed_country_id
                             WHERE a.status = 'pending' AND (a.origin_checked_at IS NULL OR a.origin_checked_at < LOCALTIMESTAMP - INTERVAL '30 days')
                             ORDER BY a.origin_checked_at IS NOT NULL, a.fans DESC NULLS LAST, a.id LIMIT {max(0, int(limit))}""")
        stats = {"checked": 0, "active": 0, "out_of_scope": 0, "pending": 0, "ai_calls": 0}
        ai_left = int(cfg["max_ai_calls"])
        threshold = float(cfg["threshold"])
        wikidata = WikidataLookup(self.http)
        ai_ok = bool(self.ai and self.ai.is_available())
        for a in artists:
            verdict = self.combine(self._music_brainz(a["name"]), wikidata.find(a["name"]))
            needs_ai = verdict is None or verdict["confidence"] < threshold
            if needs_ai and ai_ok and ai_left <= 0:
                continue  # quota IA du passage épuisé : examiné au prochain passage
            if needs_ai and ai_ok and ai_left > 0:
                verdict = self._ask_ai(int(a["id"]), a["name"])
                ai_left -= 1
                stats["ai_calls"] += 1
            decision = self.decide(verdict, list(covered), threshold)
            # Garde-fou diaspora : un pays de distribution ou de revenus n'écarte pas un artiste dont la scène
            # pointe vers un des cinq pays
            if decision == "out_of_scope" and (verdict or {}).get("base_country") in SceneSignals.PAYOUT_COUNTRIES:
                ev = self._evidence(int(a["id"]), a["name"])
                scene = ev["scene_country"] or ev["related_country"]
                if scene and scene in covered:
                    decision = "pending"
                    verdict = {**verdict, "base_country": scene, "confidence": 0.6,
                               "note": f"Possible artiste de la diaspora : pays déclaré {verdict.get('nationality')}, mais sa scène pointe vers "
                                       f"{country_name(scene)} ({ev['summary']}). {verdict.get('note')}"}
            verdict = verdict or {}
            data = {"origin_checked_at": now_utc(), "origin_country": verdict.get("nationality"), "base_country": verdict.get("base_country"),
                    "origin_source": verdict.get("source"),
                    "origin_confidence": php_round(float(verdict["confidence"]), 2) if verdict.get("confidence") is not None else None,
                    "origin_note": verdict["note"][:1000] if verdict.get("note") is not None else None}
            if decision == "active":
                data["status"], data["submission_country_id"] = "active", covered[verdict["base_country"]]
            elif decision == "out_of_scope":
                data["status"] = "out_of_scope"
            db.update("artists", data, "id = :id", {"id": a["id"]})
            if decision != "pending":
                audit.log(None, "artist.auto_classify", "artist", int(a["id"]), data["origin_note"], data)
            stats["checked"] += 1
            stats[decision] += 1
        return stats

    @staticmethod
    def decide(verdict, covered_codes: list, threshold: float) -> str:
        """active : carrière dans un pays couvert ; out_of_scope : ailleurs ; pending : incertain (diaspora comprise)."""
        if not verdict or (verdict.get("confidence") or 0) < threshold or not verdict.get("base_country"):
            return "pending"
        if verdict["base_country"].upper() in covered_codes:
            return "active"
        return "pending" if str(verdict.get("nationality") or "").upper() in covered_codes else "out_of_scope"

    @staticmethod
    def combine(mb, wd):
        """MusicBrainz et Wikidata d'accord → confiance renforcée ; en désaccord → pas de décision."""
        if mb and wd:
            if mb["base_country"] != wd["base_country"]:
                return {"nationality": None, "base_country": None, "confidence": 0.0, "source": "musicbrainz+wikidata",
                        "note": f"Sources en désaccord. {mb['note']} ; {wd['note']}"}
            return {**wd, "confidence": 0.95, "source": "musicbrainz+wikidata", "note": f"{mb['note']} ; {wd['note']}"}
        return mb or wd

    def _music_brainz(self, name: str):
        time.sleep(1.1)  # MusicBrainz : une requête par seconde au plus
        try:
            resp = self.http.request("GET", MB + _enc(f'artist:"{name}"'), {"User-Agent": f"CauriCharts/1.0 ( {conf.get('app.url')} )",
                                                                            "Accept": "application/json"})
        except Exception:  # noqa: BLE001
            return None
        data = _json(resp) or {}
        key, countries = N.text(name), {}
        for r in data.get("artists") or []:
            if (r.get("score") or 0) >= 95 and N.text(r.get("name") or "") == key and r.get("country"):
                # Fiche incohérente (pays d'origine différent du pays actuel) : on ne tranche pas
                begin = r.get("begin-area")
                if begin and begin.get("type") == "Country" and begin.get("name") != (r.get("area") or {}).get("name"):
                    return None
                countries[r["country"]] = r["id"]
        if len(countries) != 1:
            return None
        code = next(iter(countries))
        return {"nationality": code, "base_country": code, "confidence": 0.9, "source": "musicbrainz",
                "note": "MusicBrainz : https://musicbrainz.org/artist/" + countries[code]}

    def _ask_ai(self, artist_id: int, name: str):
        seen = db.all("""SELECT t.title, o.source, c.code FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                         JOIN countries c ON c.id = o.country_id WHERE t.artist_id = ?
                         GROUP BY t.title, o.source, c.code ORDER BY MIN(o.position) LIMIT 8""", [artist_id])
        context = "\n".join(f"- « {s['title']} » ({s['source']}, classement {s['code']})" for s in seen)
        ev = self._evidence(artist_id, name)
        channel, wiki, evidence = ev["channel"], ev["wiki"], ev["lines"]
        system = ("Tu es documentaliste musical pour un classement de l'Afrique de l'Ouest. Tu identifies le pays d'un artiste musical "
                  "à partir des indices fournis et de tes connaissances. Tu ne devines jamais : si tu ne connais pas cet artiste avec certitude "
                  "et que les indices ne suffisent pas, mets confidence à 0.5 ou moins. Attention aux homonymes. "
                  "Important : beaucoup d'artistes africains déclarent sur les plateformes un pays de distribution ou de perception des revenus "
                  "(France, États-Unis, Royaume-Uni…). Ce pays déclaré n'est PAS leur pays : retiens le pays de la scène à laquelle ils appartiennent "
                  "(origine, public, langue, collaborations, label local, marqueurs comme 228, Lomé, Abidjan, 225, Dakar…). Réponds uniquement par un objet JSON.")
        prompt = (f"Artiste : « {name} »\nTitres repérés dans les classements des plateformes :\n{context}\n\n"
                  "Indices :\n" + ("- " + "\n- ".join(evidence) if evidence else "(aucun indice trouvé)") + "\n\n"
                  "Réponds en JSON : {\"nationality\": code ISO pays ou null, \"base_country\": code ISO du pays où se "
                  "déroule principalement sa carrière musicale (label, scène, résidence) ou null, \"confidence\": nombre de 0 à 1, "
                  "\"reason\": une phrase en français qui cite l'indice utilisé}")
        try:
            answer = self.ai.ask(system, prompt, 1200, 3)
        except Exception:  # noqa: BLE001
            return None
        j = ai.extract_json(answer["text"])
        if not j:
            return None

        def iso(v):
            return v.upper() if isinstance(v, str) and re.fullmatch(r"[A-Za-z]{2}", v) else None
        try:
            confidence = float(j.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        sources = ([f"https://www.youtube.com/channel/{channel['id']}"] if channel else []) + [w["url"] for w in wiki] + answer["sources"][:3]
        verdict = {"nationality": iso(j.get("nationality")), "base_country": iso(j.get("base_country")),
                   "confidence": max(0.0, min(1.0, confidence)), "source": "ia",
                   "note": (str(j.get("reason") or "") + " Sources : " + " ".join(s for s in sources if s)).strip()}
        return self.corroborate(verdict, (channel or {}).get("country"), " ".join(w["snippet"] for w in wiki),
                                ev["scene_country"], ev["related_country"])

    @staticmethod
    def corroborate(verdict: dict, channel_country, wiki_text: str, scene_country=None, related_country=None) -> dict:
        """Garde-fou anti-invention : l'IA ne décide seule que si un indice collecté confirme sa réponse."""
        base = verdict["base_country"]
        confirmed = bool(base) and (
            (bool(channel_country) and channel_country.upper() == base)
            or (wiki_text != "" and WikidataLookup.demonym(wiki_text) == base)
            or scene_country == base
            or related_country == base)
        if not confirmed:
            verdict = {**verdict, "confidence": min(verdict["confidence"], 0.8), "note": "Suggestion IA non recoupée. " + verdict["note"]}
        return verdict

    def _evidence(self, artist_id: int, name: str) -> dict:
        if artist_id in self.evidence_cache:
            return self.evidence_cache[artist_id]
        channel = self._youtube_channel(artist_id, name)
        wiki = self._wikipedia(name)
        related_country, related_names = self._related(artist_id)
        titles = " ".join(r["title"] for r in db.all("SELECT title FROM tracks WHERE artist_id = ? ORDER BY id LIMIT 20", [artist_id]))
        scores = SceneSignals.score(" ".join([(channel or {}).get("description") or "", (channel or {}).get("uploads") or "",
                                              " ".join(w["snippet"] for w in wiki), titles]))
        scene_country = SceneSignals.dominant(scores)
        lines = []
        if channel:
            declared = channel["country"] or "non renseigné"
            lines.append(f"Chaîne YouTube « {channel['title']} » : pays déclaré = {declared}"
                         + (" (souvent un pays de distribution, pas l’origine)" if channel["country"] in SceneSignals.PAYOUT_COUNTRIES else "")
                         + (" ; description : " + channel["description"][:300] if channel["description"] else ""))
            if channel.get("uploads"):
                lines.append("Dernières vidéos de la chaîne : " + channel["uploads"][:500])
        for w in wiki:
            lines.append(f"Wikipédia ({w['lang']}) « {w['title']} » : {w['snippet']}")
        if related_names:
            lines.append("Artistes proches sur Deezer (pays confirmé) : " + ", ".join(related_names))
        if scores:
            lines.append("Marqueurs de scène relevés (villes, indicatifs, langues) : " + ", ".join(f"{c} {n}" for c, n in scores.items()))
        summary = " ; ".join(x for x in [f"marqueurs locaux {scene_country}" if scene_country else None,
                                         f"artistes proches {related_country}" if related_country else None] if x)
        self.evidence_cache[artist_id] = {"channel": channel, "wiki": wiki, "lines": lines, "scene_country": scene_country,
                                          "related_country": related_country, "summary": summary or "indices faibles"}
        return self.evidence_cache[artist_id]

    def _related(self, artist_id: int):
        deezer_id = db.value("SELECT deezer_id FROM artists WHERE id = ?", [artist_id])
        if not deezer_id:
            return None, []
        try:
            data = _json(self.http.request("GET", f"https://api.deezer.com/artist/{int(deezer_id)}/related?limit=25")) or {}
        except Exception:  # noqa: BLE001
            return None, []
        counts, names = {}, []
        for r in data.get("data") or []:
            known = db.one("""SELECT c.code FROM artists a JOIN countries c ON c.id = a.submission_country_id
                              WHERE a.match_key = ? AND a.status = 'active' LIMIT 1""", [N.artist_key(str(r["name"]))])
            if known:
                counts[known["code"]] = counts.get(known["code"], 0) + 1
                names.append(f"{r['name']} ({known['code']})")
        counts = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
        top = next(iter(counts), None)
        total = sum(counts.values())
        return (top if top and counts[top] >= 2 and counts[top] >= 0.6 * total else None), names[:8]

    def _youtube_channel(self, artist_id: int, name: str):
        key = env.get("YOUTUBE_API_KEY", "")
        if not key:
            return None
        api = "https://www.googleapis.com/youtube/v3/"

        def get(p: str, cost: int = 1) -> dict:
            # Chaque appel est décompté du quota YouTube partagé (réserve gardée pour le relevé des vues)
            if not YouTubeQuota.spend(cost):
                return {}
            return _json(self.http.request("GET", api + p + "&key=" + _enc(key))) or {}
        try:
            video = db.value("""SELECT p.external_id FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id
                                WHERE t.artist_id = ? AND p.platform = 'youtube' LIMIT 1""", [artist_id])
            channel_id = None
            if video:
                items = get("videos?part=snippet&id=" + _enc(video)).get("items") or [{}]
                channel_id = (items[0].get("snippet") or {}).get("channelId")
            if not channel_id and self.searches_left > 0:
                self.searches_left -= 1
                for item in get("search?part=snippet&type=video&maxResults=5&q=" + _enc(name), 100).get("items") or []:
                    if N.text(name) in N.text(item["snippet"]["title"] + " " + item["snippet"]["channelTitle"]):
                        channel_id = item["snippet"]["channelId"]
                        break
            if not channel_id:
                return None
            c = (get("channels?part=snippet,contentDetails&id=" + _enc(channel_id)).get("items") or [None])[0]
            if not c:
                return None
            uploads = ""
            playlist = ((c.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
            if playlist:
                for it in get("playlistItems?part=snippet&maxResults=15&playlistId=" + _enc(playlist)).get("items") or []:
                    uploads += " | " + it["snippet"]["title"] + " — " + str(it["snippet"].get("description") or "")[:160]
        except Exception:  # noqa: BLE001
            return None
        s = c.get("snippet") or {}
        return {"id": channel_id, "title": str(s.get("title") or ""), "country": s.get("country"),
                "description": str(s.get("description") or "").strip(), "uploads": uploads.strip(" |")}

    def _wikipedia(self, name: str) -> list:
        out = []
        for lang, word in (("fr", "musique"), ("en", "music")):
            try:
                r = self.http.request("GET", f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch="
                                      + _enc(f'"{name}" {word}'), {"User-Agent": f"CauriCharts/1.0 ( {conf.get('app.url')} )"})
            except Exception:  # noqa: BLE001
                continue
            for s in ((_json(r) or {}).get("query") or {}).get("search") or []:
                plain = re.sub(r"<[^>]+>", "", s["snippet"])
                if N.text(name) not in N.text(s["title"] + " " + plain):
                    continue
                out.append({"lang": lang, "title": s["title"], "snippet": html.unescape(plain).strip(),
                            "url": f"https://{lang}.wikipedia.org/wiki/" + _enc(s["title"].replace(" ", "_"))})
        return out[:4]
