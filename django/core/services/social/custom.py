"""Posts « sur demande » : une phrase en français (« les 20 titres les plus écoutés de l'année au Ghana ») devient un post.

L'IA (Groq, Gemini ou OpenRouter) ne fait que traduire la demande en réglages choisis dans une liste fermée (mesure,
pays, période, plateforme, artiste, nombre) ; le titre est construit par le site et les chiffres viennent toujours de
la base. Ce que les données ne permettent pas (genre musical, ambiance, nombre exact de streams…) est signalé à
l'équipe, jamais inventé.
"""
import json

from core import db
from core.helpers import country_name
from core.services import ai, live_chart
from core.services.live_chart import SOURCES
from core.services.social import themes as T

METRICS = {
    "classements": "positions dans les classements des plateformes (points selon la place)",
    "vues_youtube": "vues YouTube des clips",
    "likes_youtube": "« j'aime » YouTube des clips",
    "progression_vues": "vues YouTube gagnées en 7 jours",
    "nouveaux_clips": "clips publiés ces 14 derniers jours",
    "fans_deezer": "nombre de fans Deezer des artistes",
    "abonnes_youtube": "nombre d'abonnés YouTube des artistes",
    "artiste": "les titres d'un artiste précis dans les classements",
}
PERIODS = {"jour": ("latest", "du jour"), "semaine": ("week", "de la semaine"), "mois": ("month", "du mois"),
           "annee": ("year", "de l’année"), "tout": ("all", "depuis le lancement")}
CHART_SOURCES = ["apple_music", "deezer", "shazam", "youtube_trending"]

SYSTEM = f"""Tu traduis une demande de post de l'équipe de Cauri Charts (classements musicaux d'Afrique de l'Ouest) en réglages.
Tu ne donnes AUCUN chiffre et tu n'écris AUCUN titre : les données et le titre viennent ensuite du site.
Réglages possibles (liste fermée) :
- metric : {json.dumps(METRICS, ensure_ascii=False)}
- country : "WA" (toute l'Afrique de l'Ouest couverte) ou un code pays parmi {{pays}}
- period : {list(PERIODS)} (pour metric = classements ou artiste)
- source : null, ou une plateforme parmi {CHART_SOURCES} si la demande en vise une seule
- artist : nom de l'artiste si la demande porte sur un artiste précis (metric = artiste), sinon null
- limit : nombre de titres ou d'artistes, de 3 à 20
Ce que les données NE contiennent PAS : genre musical ou style (gothique, rap, gospel…), ambiance, langue, âge ou sexe des
artistes, nombre exact d'écoutes ou de streams, ventes, données avant le 30 septembre 2026.
Si la demande s'appuie sur l'un de ces critères, ignore-le pour les réglages et nomme-le dans "unsupported".
« Streams », « écoutes », « les plus écoutés » : metric « classements » (les plateformes ne publient pas les écoutes) ;
ajoute « nombre exact de streams » dans "unsupported".
Réponds uniquement par un objet JSON :
{{"metric": "...", "country": "WA", "period": "semaine", "source": null, "artist": null, "limit": 10,
 "unsupported": ["critère impossible", "..."], "explanation": "une phrase pour l'équipe : ce qui sera mesuré"}}"""


def interpret(client, request_text: str) -> dict:
    codes = [r["code"] for r in db.all("SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order")]
    answer = client.ask(SYSTEM.replace("{pays}", json.dumps(codes)), "Demande : " + request_text, 600)
    j = ai.extract_json(answer["text"]) or {}
    p = {
        "metric": j.get("metric") if j.get("metric") in METRICS else "classements",
        "country": str(j.get("country") or "WA").upper(),
        "period": j.get("period") if j.get("period") in PERIODS else "semaine",
        "source": j.get("source") if j.get("source") in CHART_SOURCES else None,
        "artist": str(j.get("artist") or "").strip()[:80] or None,
        "unsupported": [str(u)[:60] for u in (j.get("unsupported") or []) if str(u).strip()][:5],
        "explanation": str(j.get("explanation") or "").strip()[:400],
        "request": request_text,
    }
    p["country"] = p["country"] if p["country"] in codes else "WA"
    if p["metric"] == "artiste" and not p["artist"]:
        p["metric"] = "classements"
    try:
        p["limit"] = max(3, min(20, int(j.get("limit") or 10)))
    except (TypeError, ValueError):
        p["limit"] = 10
    return p


def find_artist(name: str):
    """Artiste suivi le plus proche du nom demandé (le plus de fans en cas d'homonymes)."""
    return db.one("""SELECT id, name, image_url, fans FROM artists WHERE status = 'active'
                     AND (name ILIKE ? OR name ILIKE ?) ORDER BY (name ILIKE ?) DESC, fans DESC NULLS LAST LIMIT 1""",
                  [name, f"%{name}%", name])


def entries(p: dict) -> list:
    m, n = p["metric"], p["limit"]
    if m == "artiste":
        a = find_artist(p["artist"])
        if not a:
            return []
        p["artist"] = a["name"]
        rows = db.all(f"""SELECT t.id AS track_id, t.title, a.name AS artist, COALESCE(t.cover_url, a.image_url) AS image_url, MIN(o.position) AS best
                          FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                          WHERE a.id = ? {'' if PERIODS[p['period']][0] in ('latest', 'all') else f"AND o.observed_on >= CURRENT_DATE - {live_chart.WINDOWS[PERIODS[p['period']][0]]}"}
                          GROUP BY t.id, a.id ORDER BY best, t.id LIMIT {int(n)}""", [a["id"]])
        return [T._track_entry(r, T._pos(s), s) for r in rows for s in [T._seen(int(r["track_id"]))]]
    if m == "classements":
        cid = None if p["country"] == "WA" else db.value("SELECT id FROM countries WHERE code = ?", [p["country"]])
        # Classement demandé : seulement les artistes au pays confirmé (les « à vérifier » restent sur le site)
        rows = [r for r in live_chart.build(cid, p["source"], n + 15, "prime", 20, PERIODS[p["period"]][0])["rows"]
                if r.get("status") == "active"][:n]
        out = []
        for r in rows:
            seen = [{"platform": SOURCES.get(s["source"], s["source"]), "country": s["country"], "position": s["position"]} for s in r["seen"][:4]]
            out.append(T._track_entry(r | {"artist": r["artist_name"], "image_url": r.get("cover_url") or r.get("artist_image")},
                                      T._pos(seen), seen))
        return out
    # Code pays tiré de la table des pays (liste fermée) : sans risque dans la requête
    country = "" if p["country"] == "WA" else f"AND track_id IN (SELECT t.id FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE a.base_country = '{p['country']}')"
    if m == "vues_youtube":
        return [T._track_entry(r, f"{T._fmt(r['plays'])} vues · {T._fmt(r['likes'] or 0)} j’aime", figure_value=T._fmt(r["plays"]), figure_label="vues YouTube")
                for r in T._clips(f"AND plays > 0 {country}", limit=n)]
    if m == "likes_youtube":
        return [T._track_entry(r, f"{T._fmt(r['likes'])} j’aime · {T._fmt(r['plays'])} vues", figure_value=T._fmt(r["likes"]), figure_label="j’aime YouTube")
                for r in T._clips(f"AND likes > 0 {country}", "likes DESC", n)]
    if m == "progression_vues":
        return [T._track_entry(r, f"+{T._fmt(r['plays'] - r['before'])} vues en une semaine", figure_value="+" + T._fmt(r["plays"] - r["before"]),
                               figure_label="vues en 7 jours")
                for r in T._clips(f"AND before IS NOT NULL AND plays > before {country}", "plays - before DESC", n)]
    if m == "nouveaux_clips":
        return [T._track_entry(r, f"Clip publié le {T._date(r['published_at'])} · {T._fmt(r['plays'])} vues", figure_value=T._fmt(r["plays"]),
                               figure_label="vues YouTube")
                for r in T._clips(f"AND published_at >= CURRENT_DATE - 14 {country}", "published_at DESC, plays DESC", n)]
    column, label = ("fans", "fans Deezer") if m == "fans_deezer" else ("youtube_subscribers", "abonnés YouTube")
    return [e for e in T._artists(column, label, 200) if p["country"] == "WA" or e["title"] == country_name(p["country"])][:n]


def title(p: dict, n: int, where: str) -> str:
    """Titre du post, construit à partir des réglages (jamais écrit par l'IA)."""
    period = PERIODS[p["period"]][1]
    on = f" sur {SOURCES.get(p['source'], p['source'])}" if p.get("source") else ""
    return {
        "classements": f"Top {n} {where}{on}, {period}",
        "vues_youtube": f"Les {n} clips les plus vus · {where}",
        "likes_youtube": f"Les {n} clips les plus aimés · {where}",
        "progression_vues": f"Les clips qui décollent · {where}",
        "nouveaux_clips": f"Nouveaux clips · {where}",
        "fans_deezer": f"Les artistes les plus suivis sur Deezer · {where}",
        "abonnes_youtube": f"Les chaînes YouTube les plus suivies · {where}",
        "artiste": f"{p.get('artist')} dans les classements",
    }[p["metric"]]


def facts(p: dict) -> dict | None:
    rows = entries(p)
    if not rows:
        return None
    where = "Afrique de l’Ouest" if p["country"] == "WA" else country_name(p["country"])
    head = title(p, len(rows), where)
    source = {"classements": "Classements " + (SOURCES.get(p["source"]) if p["source"] else "Apple Music, Deezer, Shazam et YouTube"),
              "artiste": "Classements Apple Music, Deezer, Shazam et YouTube",
              "fans_deezer": "Deezer (nombre de fans)", "abonnes_youtube": "YouTube (nombre d’abonnés)"}.get(p["metric"], "YouTube (relevés quotidiens Cauri Charts)")
    cover = {"kicker": where if p["metric"] != "artiste" else "Cauri Charts", "headline": head.split(" · ")[0].split(",")[0],
             "subtitle": (PERIODS[p["period"]][1] if p["metric"] in ("classements", "artiste") else METRICS[p["metric"]]).capitalize()}
    return {"kind": "ranking", "theme": "demande", "label": head, "headline": head, "big": cover["headline"], "cover": cover,
            "intro": head + " :", "question": "Votre préféré dans la liste ?",
            "top": rows, "source": source, "request": p["request"], "measure": METRICS[p["metric"]],
            "unsupported": p["unsupported"], "explanation": p["explanation"],
            "image": next((e["image_url"] for e in rows if e.get("image_url")), None)}
