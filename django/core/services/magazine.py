"""Cauri Hebdo : l'article de la semaine, écrit chaque dimanche à partir des chiffres réels du classement.

Aucune IA ici : chaque phrase est assemblée à partir des relevés (n°1, Top 10, progressions, n°1 par pays,
répartition des pays), pour qu'aucun chiffre ni fait ne puisse être inventé. Publié dans Actualités.
"""
from collections import Counter

from core import clock, db
from core.helpers import country_name, slugify
from core.repos import now_utc
from core.services import live_chart, reliability

MAIN = ["NG", "GH", "CI", "SN", "TG", "BJ", "ML", "BF"]


def _who(r: dict) -> str:
    country = f" ({country_name(r['artist_country'])})" if r.get("artist_country") else ""
    return f"{r['artist_name']}{country}"


def de(name: str) -> str:
    """« de Rema », « d'Ayra Starr » (élision devant une voyelle)."""
    return ("d'" if name[:1].lower() in "aeiouyéèêàâîôûh" else "de ") + name


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def facts() -> dict:
    top = [r for r in live_chart.build(None, None, 20, "prime", 20, "week")["rows"] if not r.get("is_artist")]
    buzz = live_chart.build(None, None, 5, "buzz", 20, "week")["rows"]
    fresh = live_chart.build(None, None, 5, "fresh", 20, "week")["rows"]
    leaders = []
    for c in db.all(f"SELECT id, code FROM countries WHERE is_active = 1 AND code IN ({','.join(['?'] * len(MAIN))}) ORDER BY sort_order", MAIN):
        rows = live_chart.build(c["id"], None, 20, "prime", 20, "week")["rows"]
        if rows and reliability.measure(c["id"], rows)["score"] >= 45:
            leaders.append({"country": c["code"], **rows[0]})
    return {"top": top, "buzz": buzz, "fresh": fresh, "leaders": leaders,
            "countries": Counter(r["artist_country"] for r in top if r.get("artist_country"))}


def write(f: dict, week: str) -> dict | None:
    top = f["top"]
    if len(top) < 10:
        return None
    one = top[0]
    title = f"Cauri Hebdo, semaine {week} : « {one['title']} » {de(one['artist_name'])} en tête de l'Afrique de l'Ouest"
    paras = []
    platforms = sorted({s["source"] for s in one.get("seen") or []} - set(reliability.COMPUTED))
    names = [live_chart.SOURCES.get(p, p) for p in platforms]
    paras.append(f"« {one['title']} » {de(_who(one))} prend la première place du Top 20 Afrique de l'Ouest cette semaine"
                 + (f", porté par {', '.join(names[:-1]) + ' et ' + names[-1] if len(names) > 1 else names[0]}." if names else "."))
    podium = top[1:3]
    paras.append("Sur le podium, " + " puis ".join(f"« {r['title']} » {de(_who(r))}" for r in podium) + ".")
    rest = top[3:10]
    paras.append("Le reste du Top 10 : " + " ; ".join(f"n°{i + 4} « {r['title']} » ({r['artist_name']})" for i, r in enumerate(rest)) + ".")
    if f["countries"]:
        parts = [f"{country_name(c)} {n} {_plural(n, 'titre', 'titres')}" for c, n in f["countries"].most_common(5)]
        paras.append(f"{len(f['countries'])} pays sont représentés dans le Top 20 : " + ", ".join(parts)
                     + ". Rappel de la règle : au plus 5 titres d'un même pays, pour laisser de la place à toute la région.")
    if f["buzz"]:
        paras.append("Ceux qui montent, hors du Top 20 : " + ", ".join(f"« {r['title']} » {de(_who(r))}" for r in f["buzz"][:3]) + ".")
    in_top10 = {r.get("track_id") for r in top[:10]}
    fresh = [r for r in f["fresh"] if r.get("track_id") not in in_top10]
    if fresh:
        paras.append("Côté nouveautés, hors du Top 10 : " + ", ".join(f"« {r['title']} » ({r['artist_name']})" for r in fresh[:3]) + ".")
    if f["leaders"]:
        paras.append("Les n°1 par pays : " + " ; ".join(f"{country_name(r['country'])} : « {r['title']} » {de(r['artist_name'])}" for r in f["leaders"]) + ".")
    paras.append("Comment c'est calculé : chaque place dans les classements de Deezer, Apple Music, Shazam et YouTube rapporte des points, "
                 "chaque pays pèse autant, et chaque classement affiche sa note de fiabilité. Classement complet et méthode sur cauricharts.com.")
    summary = f"« {one['title']} » {de(one['artist_name'])} est n°1 du Top 20 Afrique de l'Ouest. Le podium, le Top 10, ceux qui montent et les n°1 de chaque pays."
    return {"title": title[:200], "summary": summary[:400], "body": "\n\n".join(paras), "image": one.get("cover_url") or one.get("artist_image")}


def publish(today=None) -> str:
    """Article de la semaine (une seule fois par semaine ISO), avec la pochette du n°1 en vignette."""
    from core.services.news import FeedImporter
    day = today or clock.today()
    year, week, _ = day.isocalendar()
    guid = f"cauri-hebdo-{year}-W{week:02d}"
    if db.value("SELECT 1 FROM news WHERE external_guid = ?", [guid]):
        return f"Cauri Hebdo {year}-S{week} déjà publié"
    art = write(facts(), str(week))
    if not art:
        return "Cauri Hebdo : pas assez de titres cette semaine"
    image = FeedImporter()._thumbnail(art["image"], guid) if art.get("image") else None
    db.insert("news", {"title": art["title"], "slug": slugify(art["title"])[:180] + f"-{year}-s{week:02d}", "summary": art["summary"],
                       "body": art["body"], "category": "classement", "country_id": None, "source_name": "Cauri Charts",
                       "source_url": None, "image_path": image, "origin": "manual", "external_guid": guid,
                       "status": "published", "published_at": now_utc()})
    return f"Cauri Hebdo {year}-S{week} publié : {art['title']}"
