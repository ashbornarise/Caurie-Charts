"""Portrait d'artiste : un carrousel par grand artiste, uniquement avec des faits sourcés.

  bio       : résumé de l'article Wikipédia (français, sinon anglais), licence CC BY-SA, source citée ;
  palmarès  : récompenses de Wikidata (propriété P166) avec leur année, sinon ses meilleures places chez Cauri Charts ;
  chiffres  : chaîne YouTube officielle (abonnés, vues totales), fans Deezer, meilleure place, classements de la semaine ;
  titres    : ses titres présents dans les classements des 7 derniers jours.
L'artiste est choisi parmi les confirmés les plus présents dans les classements, jamais deux fois en 8 semaines.
"""
import json
import re
from datetime import date
from urllib.parse import quote

from core import conf, db
from core.helpers import country_name
from core.services.imports import normalizer as N
from core.services.platforms import HttpClient

UA = {"User-Agent": "CauriCharts/1.0 (https://cauricharts.com ; contact@cauricharts.com)"}


def _json(url: str):
    r = HttpClient(20).request("GET", url, UA)
    try:
        return json.loads(r["body"]) if r["status"] == 200 else None
    except ValueError:
        return None


def pick(day: date) -> dict | None:
    """L'artiste confirmé le plus présent dans les classements de la semaine, pas encore portraituré depuis 8 semaines."""
    done = []
    for r in db.all("SELECT facts FROM social_posts WHERE theme = 'portrait' AND slot_date >= CURRENT_DATE - 56"):
        try:
            done.append(int(json.loads(r["facts"]).get("artist_id")))
        except (ValueError, TypeError):
            pass
    return db.one(f"""SELECT a.*, c.code AS country FROM artists a JOIN countries c ON c.id = a.submission_country_id
                      WHERE a.status = 'active' AND a.image_url IS NOT NULL {"AND a.id NOT IN (" + ",".join(map(str, done)) + ")" if done else ""}
                      ORDER BY (SELECT COUNT(DISTINCT o.source || o.country_id) FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                                WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 7) DESC,
                               COALESCE(a.youtube_subscribers, 0) + COALESCE(a.fans, 0) DESC LIMIT 1""")


def wikidata_id(name: str, country: str) -> str | None:
    """Identifiant Wikidata de l'artiste : même nom ET nationalité du pays attendu (pas d'homonyme)."""
    qid = (conf.get("discovery") or {}).get("wikidata_countries", {}).get(country)
    for lang in ("fr", "en"):
        found = _json(f"https://www.wikidata.org/w/api.php?action=wbsearchentities&language={lang}&type=item&limit=5&format=json&search={quote(name)}") or {}
        for item in found.get("search") or []:
            if N.artist_key(item.get("label", "")) != N.artist_key(name):
                continue
            claims = ((_json(f"https://www.wikidata.org/wiki/Special:EntityData/{item['id']}.json") or {}).get("entities", {})
                      .get(item["id"], {}).get("claims", {}))
            nat = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P27", [])}
            if qid in nat:
                return item["id"]
    return None


def awards(qid: str) -> list:
    """Récompenses (P166) avec l'année quand elle est connue, les plus récentes d'abord."""
    q = ("SELECT ?awardLabel ?year WHERE { wd:" + qid + " p:P166 ?st . ?st ps:P166 ?award . "
         "OPTIONAL { ?st pq:P585 ?d . BIND(YEAR(?d) AS ?year) } "
         'SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". } }')
    data = _json("https://query.wikidata.org/sparql?format=json&query=" + quote(q)) or {}
    out = []
    for b in (data.get("results") or {}).get("bindings") or []:
        label = (b.get("awardLabel") or {}).get("value", "")
        if label and not re.fullmatch(r"Q\d+", label):
            out.append({"award": label, "year": int(b["year"]["value"]) if b.get("year") else None})
    out = list({(a["award"], a["year"]): a for a in out}.values())
    return sorted(out, key=lambda a: -(a["year"] or 0))


def bio(name: str, qid: str | None) -> dict | None:
    """Résumé Wikipédia (titre exact donné par Wikidata), coupé à la fin d'une phrase."""
    titles = {}
    if qid:
        ent = (_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json") or {}).get("entities", {}).get(qid, {})
        titles = {k[:2]: v["title"] for k, v in (ent.get("sitelinks") or {}).items() if k in ("frwiki", "enwiki")}
    for lang in ("fr", "en"):
        title = titles.get(lang)
        if not title:
            continue
        s = _json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}") or {}
        text = str(s.get("extract") or "").strip()
        # Graphies spéciales (« stylisé REMΛ ») : absentes des polices des visuels, et sans intérêt pour le lecteur
        text = re.sub(r",?\s*(stylisé|stylised|stylized)[^,.;]*", "", text)
        text = re.sub("[^\u0000-\u024F\u2018-\u201F\u2026\u00ab\u00bb\u2013\u2014]", "", text).strip()
        if len(text) < 60:
            continue
        cut, out = 420, ""
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if len(out) + len(sentence) > cut and out:
                break
            out = (out + " " + sentence).strip()
        return {"text": out, "lang": lang, "url": f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"}
    return None


def facts(a: dict) -> dict:
    qid = wikidata_id(a["name"], a["country"])
    tracks = db.all("""SELECT t.title, MIN(o.position) AS best, COUNT(DISTINCT o.source || o.country_id) AS charts
                       FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                       WHERE t.artist_id = ? AND o.observed_on >= CURRENT_DATE - 7 GROUP BY t.id, t.title ORDER BY charts DESC, best LIMIT 5""", [a["id"]])
    best = db.one("""SELECT o.position, o.source, c.code FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                     JOIN countries c ON c.id = o.country_id WHERE t.artist_id = ? ORDER BY o.position, o.observed_on DESC LIMIT 1""", [a["id"]])
    return {"artist_id": a["id"], "name": a["name"], "slug": a["slug"], "country": a["country"], "qid": qid,
            "awards": awards(qid)[:6] if qid else [], "bio": bio(a["name"], qid), "tracks": tracks, "best": best,
            "youtube_subscribers": a.get("youtube_subscribers"), "youtube_views_total": a.get("youtube_views_total"),
            "fans": a.get("fans"), "photo": a.get("image_hd_url") or a.get("image_url"), "credit": a.get("image_credit"),
            "spotify": _spotify(a.get("spotify_id"))}


def _spotify(spotify_id) -> dict | None:
    """Compteurs publics de Spotify (Kworb) ; None si l'artiste n'est pas suivi ou si Kworb ne répond pas."""
    try:
        from core.services import kworb
        return kworb.chiffres(spotify_id)
    except Exception:  # noqa: BLE001 — le portrait se fait sans ce bloc
        return None


def _n(v) -> str:
    return f"{int(v):,}".replace(",", " ")


def post(day: date) -> dict | None:
    from core.services import live_chart
    from core.services.social import editorial as E
    a = pick(day)
    if not a:
        return None
    f = facts(a)
    country = country_name(f["country"])
    stats = []
    if f["youtube_views_total"]:
        stats.append((1, _n(f["youtube_views_total"]) + " vues", "chaîne YouTube officielle, au total"))
    if f["youtube_subscribers"]:
        stats.append((2, _n(f["youtube_subscribers"]) + " abonnés", "sur YouTube"))
    if f["fans"]:
        stats.append((3, _n(f["fans"]) + " fans", "sur Deezer"))
    if f["best"]:
        b = f["best"]
        stats.append((4, f"N°{b['position']}", f"{live_chart.SOURCES.get(b['source'], b['source'])} {country_name(b['code'])}, sa meilleure place relevée"))
    slides = [{"bg": E.INK, "fg": E.WHITE, "acc": E.GOLD, "tag": "EN CHIFFRES", "big": f["name"].upper(),
               "rows": [(i + 1, v, d) for i, (_, v, d) in enumerate(stats)]}] if stats else []
    # Palmarès : récompenses (Wikidata), complétées par ses n°1 et meilleures places chez Cauri Charts
    records = db.all("""SELECT o.source, c.code, MIN(o.position) AS best FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                        JOIN countries c ON c.id = o.country_id WHERE t.artist_id = ? AND o.source NOT IN ('deezer_popularity', 'youtube_views')
                        GROUP BY o.source, c.code ORDER BY best, o.source LIMIT 5""", [f["artist_id"]])
    rows = [(a_["year"] or "—", a_["award"], "") for a_ in f["awards"][:5]]
    rows += [(f"N°{r['best']}", f"{live_chart.SOURCES.get(r['source'], r['source'])} {country_name(r['code'])}", "meilleure place relevée")
             for r in records][: max(0, 5 - len(rows))]
    if rows:
        slides.append({"bg": E.GOLD, "fg": E.INK, "acc": E.INK, "tag": "PALMARÈS", "big": "SES RÉCOMPENSES" if f["awards"] else "SES RECORDS",
                       "rows": rows})
    # Spotify en chiffres (compteurs publics relevés par Kworb), seulement pour les artistes qu'il suit
    sp = f.get("spotify")
    if sp:
        from core.services.kworb import volume
        rows = [(1, volume(sp["total"]) + " de streams", "sur Spotify, au total")]
        if sp["jour"] >= 1e5:
            rows.append((2, volume(sp["jour"]) + " par jour", "le rythme d'écoute en ce moment"))
        if sp["auditeurs"]:
            rows.append((3, volume(sp["auditeurs"]) + " d'auditeurs", "chaque mois" + (f" (record : {volume(sp['record_auditeurs'])})" if sp["record_auditeurs"] and sp["record_auditeurs"] > sp["auditeurs"] * 1.05 else "")))
        if sp["titres"]:
            t = sp["titres"][0]
            rows.append((4, volume(t["streams"]), f"« {t['titre']} »{' (en featuring)' if t['feat'] else ''}, son titre le plus écouté"))
        if sp["jours_cap"] is not None and sp["jours_cap"] <= 60:
            rows.append((5, volume(sp["cap"]), f"le prochain cap, d'ici {sp['jours_cap']} jour{'s' if sp['jours_cap'] > 1 else ''} à ce rythme"))
        slides.append({"bg": E.VIOLET, "fg": E.WHITE, "acc": E.GOLD, "tag": "SPOTIFY EN CHIFFRES", "big": "SES STREAMS", "rows": rows})
    if f["bio"]:
        src = "Wikipédia" + ("" if f["bio"]["lang"] == "fr" else " (anglais)")
        slides.append({"bg": E.CREAM, "fg": E.INK, "acc": E.VIOLET, "tag": "BIOGRAPHIE", "big": "SON HISTOIRE",
                       "body": f["bio"]["text"] + f" (Source : {src}, CC BY-SA)"})
    if f["tracks"]:
        slides.append({"bg": E.VIOLET, "fg": E.WHITE, "acc": E.GOLD, "tag": "EN CE MOMENT", "big": "SES TITRES CLASSÉS",
                       "rows": [(f"N°{t['best']}", t["title"], f"dans {t['charts']} classement{'s' if t['charts'] > 1 else ''} cette semaine") for t in f["tracks"]]})
    if len(slides) < 2:
        return None  # trop peu de faits pour un vrai portrait
    slides.append({"bg": E.INK, "fg": E.WHITE, "acc": E.GOLD, "tag": "SA FICHE", "big": "TOUT SUR " + f["name"].upper(),
                   "body": f"Classements, titres, chiffres et clips : cauricharts.com/artiste/{f['slug']}", "cta": "SUIVRE CAURI"})
    year, week, _ = day.isocalendar()
    name = f"{day.isoformat()}-portrait-{f['slug']}"[:80]
    cover = {"kicker": "Portrait", "headline": f["name"], "subtitle": f"Artiste · {country}", "photo": f["photo"]}
    files = E.render(name, slides, cover)
    bits = [f"Portrait : {f['name']} ({country})."]
    if f["bio"]:
        bits.append(f["bio"]["text"].split(". ")[0].rstrip(".") + ".")
    if stats:
        bits.append("En chiffres : " + " ; ".join(f"{v} {d}" for _, v, d in stats[:3]) + ".")
    if sp:
        bits.append(f"Sur Spotify : {volume(sp['total'])} de streams au total"
                    + (f", {volume(sp['auditeurs'])} d'auditeurs chaque mois" if sp["auditeurs"] else "")
                    + (f" ; son titre le plus écouté, « {sp['titres'][0]['titre']} », dépasse les {volume(sp['titres'][0]['streams'])}" if sp["titres"] else "") + ".")
    if f["awards"]:
        bits.append("Palmarès : " + " ; ".join(f"{a_['award']}" + (f" ({a_['year']})" if a_["year"] else "") for a_ in f["awards"][:3]) + ".")
    bits.append("Sa fiche complète : lien en bio.")
    if f["bio"]:
        bits.append(f"Bio : Wikipédia (CC BY-SA). Données : Cauri Charts, YouTube, Deezer, Wikidata" + (", Spotify (compteurs publics, via Kworb)." if sp else "."))
    if f["credit"]:
        bits.append(f["credit"])
    tag = "#" + re.sub(r"[^A-Za-z0-9]", "", f["name"])
    return E.save_post("portrait", day.isoformat(), f"Portrait : {f['name']}", "\n\n".join(bits),
                       f"#CauriCharts #Portrait {tag} #{re.sub(r'[^A-Za-z]', '', country)} #AfriqueDeLOuest",
                       files, {"kind": "portrait", "artist_id": f["artist_id"], "qid": f["qid"], "week": week})
