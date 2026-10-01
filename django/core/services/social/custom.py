"""Posts « sur demande » : une phrase en français (« les 20 titres les plus écoutés de l'année au Ghana ») devient un post.

L'IA (Groq ou Gemini) ne fait que traduire la demande en réglages choisis dans une liste fermée (mesure, pays, période,
nombre de titres) ; les chiffres viennent toujours de la base. Ce qui n'existe pas (nombre exact de streams…) est dit
dans l'explication rendue à l'équipe, jamais inventé.
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
}
PERIODS = {"jour": ("latest", "du jour"), "semaine": ("week", "de la semaine"), "mois": ("month", "du mois"),
           "annee": ("year", "de l'année"), "tout": ("all", "depuis le lancement")}
CHART_SOURCES = ["apple_music", "deezer", "shazam", "youtube_trending"]

SYSTEM = f"""Tu aides l'équipe de Cauri Charts (classements musicaux d'Afrique de l'Ouest) à créer un post réseaux sociaux.
Tu transformes la demande en réglages. Tu ne donnes AUCUN chiffre : les données sont lues ensuite dans la base.
Réglages possibles :
- metric : {json.dumps(METRICS, ensure_ascii=False)}
- country : "WA" (toute l'Afrique de l'Ouest couverte) ou un code pays parmi {{pays}}
- period : {list(PERIODS)} (utilisé pour metric = classements)
- source : null, ou une plateforme parmi {CHART_SOURCES} si la demande en vise une seule (metric = classements)
- limit : nombre de titres ou d'artistes, de 3 à 20
Règles :
- « streams », « écoutes », « les plus écoutés » : les plateformes ne publient pas le nombre d'écoutes ; utilise metric « classements »
  et dis-le clairement dans explanation.
- Les relevés ont commencé le 30 septembre 2026 : une période plus longue ne couvre que ce qui a été relevé ; dis-le si c'est le cas.
- Si la demande est impossible avec ces données, choisis la mesure la plus proche et explique l'écart.
Réponds uniquement par un objet JSON :
{{"metric": "...", "country": "...", "period": "...", "source": null, "limit": 10,
 "title": "titre du post, 40 caractères max", "explanation": "une ou deux phrases pour l'équipe : ce qui est mesuré et ce qui ne l'est pas"}}"""


def interpret(client, request_text: str) -> dict:
    codes = [r["code"] for r in db.all("SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order")]
    answer = client.ask(SYSTEM.replace("{pays}", json.dumps(codes)), "Demande : " + request_text, 600)
    j = ai.extract_json(answer["text"]) or {}
    p = {
        "metric": j.get("metric") if j.get("metric") in METRICS else "classements",
        "country": str(j.get("country") or "WA").upper(),
        "period": j.get("period") if j.get("period") in PERIODS else "semaine",
        "source": j.get("source") if j.get("source") in CHART_SOURCES else None,
        "title": str(j.get("title") or "").strip()[:60],
        "explanation": str(j.get("explanation") or "").strip()[:500],
        "request": request_text,
    }
    p["country"] = p["country"] if p["country"] in codes else "WA"
    try:
        p["limit"] = max(3, min(20, int(j.get("limit") or 10)))
    except (TypeError, ValueError):
        p["limit"] = 10
    return p


def _where(p: dict) -> str:
    # Code pays tiré de la table des pays (liste fermée) : sans risque dans la requête
    return "" if p["country"] == "WA" else f"AND COALESCE(a.base_country, '') = '{p['country']}'"


def entries(p: dict) -> list:
    m, n = p["metric"], p["limit"]
    if m == "classements":
        cid = None if p["country"] == "WA" else db.value("SELECT id FROM countries WHERE code = ?", [p["country"]])
        rows = live_chart.build(cid, p["source"], n, "prime", 20, PERIODS[p["period"]][0])["rows"]
        out = []
        for r in rows:
            seen = [{"platform": SOURCES.get(s["source"], s["source"]), "country": s["country"], "position": s["position"]} for s in r["seen"][:4]]
            out.append(T._track_entry(r | {"artist": r["artist_name"], "image_url": r.get("cover_url") or r.get("artist_image")},
                                      T._pos(seen), seen))
        return out
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


def facts(p: dict) -> dict | None:
    rows = entries(p)
    if not rows:
        return None
    where = "Afrique de l’Ouest" if p["country"] == "WA" else country_name(p["country"])
    period = PERIODS[p["period"]][1] if p["metric"] == "classements" else ""
    title = p["title"] or f"Top {len(rows)} {where}"
    source = {"classements": "Classements " + (SOURCES.get(p["source"]) if p["source"] else "Apple Music, Deezer, Shazam et YouTube"),
              "fans_deezer": "Deezer (nombre de fans)", "abonnes_youtube": "YouTube (nombre d’abonnés)"}.get(p["metric"], "YouTube (relevés quotidiens Cauri Charts)")
    return {"kind": "ranking", "theme": "demande", "label": title, "headline": title, "big": title,
            "cover": {"kicker": where, "headline": title, "subtitle": (period or METRICS[p["metric"]]).capitalize()},
            "intro": f"{title} ({where}{', ' + period if period else ''}) :", "question": "Votre préféré dans la liste ?",
            "top": rows, "source": source, "request": p["request"], "measure": METRICS[p["metric"]], "explanation": p["explanation"],
            "image": next((e["image_url"] for e in rows if e.get("image_url")), None)}
