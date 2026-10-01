"""Rubriques des posts réseaux sociaux : registre et faits réels de chacune.

Chaque rubrique décrit son libellé, son titre géant, sa couverture de carrousel et une fonction qui renvoie ses faits
(ou None s'il n'y a pas assez de données réelles : la rubrique est alors sautée). Les faits ont tous la même forme
(« ranking ») : une liste d'entrées titre / artiste / détail / chiffre exact, sans rien d'inventé.

Rotation (3 posts par semaine) : la rubrique publiée depuis le plus longtemps passe en premier, dans l'ordre du registre.
"""
from datetime import date

from core import db, storage
from core.helpers import country_name
from core.services.live_chart import SOURCES

RECENT = "o.observed_on >= CURRENT_DATE - 7"
COUNTRIES = {"TG": "Togo", "BJ": "Bénin", "GH": "Ghana", "CI": "Côte d’Ivoire", "SN": "Sénégal"}


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def _date(d) -> str:
    months = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    try:
        d = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    except ValueError:
        return str(d)
    return f"{d.day} {months[d.month - 1]}"


def _seen(track_id: int, extra: str = "") -> list:
    """Positions du titre sur 7 jours, meilleures d'abord (4 au plus). extra : filtre SQL sur des constantes du code."""
    rows = db.all(f"""SELECT DISTINCT o.source, c.code, o.position FROM chart_observations o JOIN countries c ON c.id = o.country_id
                      WHERE o.track_id = ? AND {RECENT} {extra} ORDER BY o.position, o.source, c.code""", [track_id])
    return [{"platform": SOURCES.get(r["source"], r["source"]), "country": r["code"], "position": int(r["position"])} for r in rows[:4]]


def _pos(seen: list, with_country: bool = True) -> str:
    return " · ".join(f"{s['platform']}" + (f" {s['country']}" if with_country else "") + f" n°{s['position']}" for s in seen[:2])


def _tracks(where: str = "", params: list | None = None, having: str = "", order: str = "charts DESC, best, t.id", limit: int = 5) -> list:
    """Titres vus dans les classements des plateformes sur 7 jours (artistes hors zone exclus)."""
    return db.all(f"""SELECT t.id AS track_id, t.title, t.featuring, t.release_date, a.name AS artist, a.fans,
                             COALESCE(a.image_url, t.cover_url) AS image_url,
                             COUNT(DISTINCT o.source || o.country_id) AS charts, COUNT(DISTINCT o.country_id) AS countries,
                             MIN(o.position) AS best, STRING_AGG(DISTINCT c.code, ',') AS codes
                      FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                      JOIN countries c ON c.id = o.country_id
                      WHERE {RECENT} AND a.status <> 'out_of_scope' {where}
                      GROUP BY t.id, a.id {having} ORDER BY {order} LIMIT {int(limit)}""", params or [])


def _track_entry(r, detail: str, seen: list | None = None, **extra) -> dict:
    return {"track_id": int(r["track_id"]), "title": r["title"], "artist": r["artist"], "image_url": r["image_url"],
            "detail": detail, "seen": seen or [], **extra}


def _clips(where: str = "", order: str = "plays DESC", limit: int = 5) -> list:
    """Clips YouTube des artistes vérifiés de la zone, avec leur dernier relevé (vues, « j'aime ») et celui d'il y a 6 jours ou plus."""
    return db.all(f"""WITH last AS (SELECT DISTINCT ON (s.track_platform_id) s.track_platform_id, s.plays, s.likes, s.captured_on
                                     FROM snapshots s ORDER BY s.track_platform_id, s.captured_on DESC)
                      SELECT * FROM (
                          SELECT t.id AS track_id, t.title, a.name AS artist, COALESCE(a.image_url, t.cover_url) AS image_url,
                                 p.published_at, l.plays, l.likes,
                                 (SELECT s0.plays FROM snapshots s0 WHERE s0.track_platform_id = l.track_platform_id
                                    AND s0.captured_on <= l.captured_on - 6 ORDER BY s0.captured_on DESC LIMIT 1) AS before
                          FROM last l JOIN track_platform_ids p ON p.id = l.track_platform_id JOIN tracks t ON t.id = p.track_id
                          JOIN artists a ON a.id = t.artist_id
                          WHERE p.platform = 'youtube' AND a.status = 'active' AND l.captured_on >= CURRENT_DATE - 7) x
                      WHERE TRUE {where} ORDER BY {order} LIMIT {int(limit)}""")


def _artists(column: str, label: str, limit: int = 5) -> list:
    rows = db.all(f"""SELECT a.name, a.image_url, a.{column} AS n, COALESCE(a.base_country, gc.code) AS country
                      FROM artists a LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                      WHERE a.status = 'active' AND a.{column} > 0 ORDER BY a.{column} DESC, a.id LIMIT {int(limit)}""")
    out = []
    for r in rows:
        where = country_name(r["country"]) if r["country"] else "Afrique de l’Ouest"
        out.append({"title": where, "artist": r["name"], "image_url": r["image_url"], "detail": f"{_fmt(r['n'])} {label}",
                    "row_title": r["name"], "figure_value": _fmt(r["n"]), "figure_label": label,
                    "line": f"{r['name']} ({where}) : {_fmt(r['n'])} {label}"})
    return out


# ---------------------------------------------------------------- faits de chaque rubrique

def top_country(code: str):
    def build():
        rows = _tracks("AND c.code = ?", [code])
        return [_track_entry(r, _pos(s, False), s) for r in rows for s in [_seen(int(r["track_id"]), f"AND c.code = '{code}'")]]
    return build


def by_source(source: str):
    def build():
        rows = _tracks("AND o.source = ?", [source], order="best, countries DESC, t.id")
        return [_track_entry(r, _pos(s), s) for r in rows for s in [_seen(int(r["track_id"]), f"AND o.source = '{source}'")]]
    return build


def numbers_one():
    rows = db.all(f"""SELECT DISTINCT ON (o.source, c.code) o.source, c.code, t.id AS track_id, t.title, a.name AS artist,
                             COALESCE(a.image_url, t.cover_url) AS image_url
                      FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                      JOIN countries c ON c.id = o.country_id
                      WHERE {RECENT} AND o.position = 1 AND a.status <> 'out_of_scope'
                        AND o.source IN ('apple_music', 'deezer', 'shazam', 'youtube_trending')
                      ORDER BY o.source, c.code, o.observed_on DESC""")
    out, seen = [], set()
    for r in sorted(rows, key=lambda r: (r["code"], r["source"])):
        if r["track_id"] in seen:
            continue
        seen.add(r["track_id"])
        out.append(_track_entry(r, f"n°1 {SOURCES.get(r['source'], r['source'])} {country_name(r['code'])}",
                                figure_value="N°1", figure_label=f"{SOURCES.get(r['source'], r['source'])} {country_name(r['code'])}"))
    return out[:7]


def cross_border():
    rows = _tracks(having="HAVING COUNT(DISTINCT o.country_id) >= 2", order="countries DESC, charts DESC, best, t.id")
    return [_track_entry(r, "Classé dans " + ", ".join(country_name(c) for c in (r["codes"] or "").split(",") if c),
                         _seen(int(r["track_id"])), figure_value=str(r["countries"]), figure_label="pays") for r in rows]


def releases():
    rows = _tracks("AND t.release_date >= CURRENT_DATE - 21", order="best, charts DESC, t.id")
    return [_track_entry(r, f"Sorti le {_date(r['release_date'])} · " + _pos(s), s) for r in rows for s in [_seen(int(r["track_id"]))]]


def featurings():
    rows = _tracks("AND COALESCE(t.featuring, '') <> ''")
    return [_track_entry(r, f"feat. {r['featuring']} · " + _pos(s), s) for r in rows for s in [_seen(int(r["track_id"]))]]


def revelations():
    rows = _tracks("AND a.status = 'active' AND (a.is_emerging = 1 OR COALESCE(a.fans, 0) < 100000)", order="best, charts DESC, t.id")
    return [_track_entry(r, _pos(s) + (f" · {_fmt(r['fans'])} fans Deezer" if r["fans"] else ""), s) for r in rows for s in [_seen(int(r["track_id"]))]]


def clips_views():
    return [_track_entry(r, f"{_fmt(r['plays'])} vues · {_fmt(r['likes'] or 0)} j’aime", figure_value=_fmt(r["plays"]), figure_label="vues YouTube")
            for r in _clips("AND plays > 0")]


def clips_likes():
    return [_track_entry(r, f"{_fmt(r['likes'])} j’aime · {_fmt(r['plays'])} vues", figure_value=_fmt(r["likes"]), figure_label="j’aime YouTube")
            for r in _clips("AND likes > 0", "likes DESC")]


def clips_growth():
    return [_track_entry(r, f"+{_fmt(r['plays'] - r['before'])} vues en une semaine", figure_value="+" + _fmt(r["plays"] - r["before"]),
                         figure_label="vues en 7 jours")
            for r in _clips("AND before IS NOT NULL AND plays > before", "plays - before DESC")]


def clips_new():
    return [_track_entry(r, f"Clip publié le {_date(r['published_at'])} · {_fmt(r['plays'])} vues", figure_value=_fmt(r["plays"]),
                         figure_label="vues YouTube")
            for r in _clips("AND published_at >= CURRENT_DATE - 14", "published_at DESC, plays DESC")]


def news():
    base = storage.blob_public_url()
    rows = db.all("""SELECT title, source_name, image_path FROM news WHERE status = 'published'
                     AND published_at >= LOCALTIMESTAMP - INTERVAL '7 days' ORDER BY country_id IS NULL, published_at DESC LIMIT 5""")
    return [{"title": r["title"], "artist": r["source_name"], "detail": r["source_name"], "row_title": r["title"],
             "image_url": f"{base}/media/news/{r['image_path']}" if base and r["image_path"] else None,
             "figure_value": "", "figure_label": "", "line": f"{r['title']} ({r['source_name']})"} for r in rows]


def key_figures():
    rows = db.all(f"""SELECT c.code,
                             (SELECT COUNT(*) FROM artists a WHERE a.status = 'active' AND a.base_country = c.code) AS artists,
                             (SELECT COUNT(DISTINCT o.track_id) FROM chart_observations o WHERE o.country_id = c.id AND {RECENT}) AS tracks
                      FROM countries c WHERE c.is_active = 1 ORDER BY c.sort_order""")
    return [{"title": f"{_fmt(r['artists'])} artistes suivis", "artist": country_name(r["code"]), "row_title": country_name(r["code"]),
             "detail": f"{_fmt(r['artists'])} artistes suivis · {_fmt(r['tracks'])} titres dans les classements cette semaine",
             "figure_value": _fmt(r["tracks"]), "figure_label": "titres classés cette semaine",
             "line": f"{country_name(r['code'])} : {_fmt(r['artists'])} artistes suivis, {_fmt(r['tracks'])} titres dans les classements"}
            for r in rows if r["artists"] or r["tracks"]]


# ---------------------------------------------------------------- registre

def _t(label, big, cover, intro, question, source, build):
    return {"label": label, "big": big, "cover": dict(zip(("kicker", "headline", "subtitle"), cover)) if cover else None, "intro": intro,
            "question": question, "source": source, "build": build}


CHARTS = "Classements Apple Music, Deezer, Shazam et YouTube (7 derniers jours)"
YT = "YouTube (relevés quotidiens Cauri Charts)"

# Rubriques historiques (faits dans facts.py) puis nouvelles, ordre de la rotation pour celles jamais publiées
THEMES = {
    "classement": _t("Tendances", None, None, None, None, None, None),
    "top_tg": _t("Top Togo", "Top Togo", ("Les titres qui font bouger", "le Togo", "cette semaine"),
                 "🇹🇬 Ce qui tourne au Togo cette semaine :", "Votre son du moment au Togo ?", CHARTS, top_country("TG")),
    "numeros_un": _t("Les n°1 des plateformes", "Les n°1", ("Qui est", "n°1 ?", "sur chaque plateforme, dans chaque pays"),
                     "🥇 Les n°1 des plateformes en Afrique de l’Ouest :", "Lequel mérite sa place ?", CHARTS, numbers_one),
    "artiste": _t("Artiste de la semaine", None, None, None, None, None, None),
    "clips_vues": _t("Clips les plus vus", "Les plus vus", ("YouTube", "les clips les plus vus", "en Afrique de l’Ouest"),
                     "▶️ Les clips les plus vus de nos artistes :", "Vous les avez tous vus ?", YT, clips_views),
    "top_bj": _t("Top Bénin", "Top Bénin", ("Les titres qui font bouger", "le Bénin", "cette semaine"),
                 "🇧🇯 Ce qui tourne au Bénin cette semaine :", "Votre son du moment au Bénin ?", CHARTS, top_country("BJ")),
    "shazam": _t("Les plus shazamés", "Shazam", ("Ce que vous cherchez", "sur Shazam", "le son que tout le monde veut connaître"),
                 "🔎 Les titres que l’Afrique de l’Ouest shazame le plus :", "Vous aussi, vous l’avez shazamé ?", "Classements Shazam (7 derniers jours)",
                 by_source("shazam")),
    "frontieres": _t("Sans frontières", "Sans frontières", ("Ils traversent", "les frontières", "classés dans plusieurs pays"),
                     "🌍 Ces titres sont classés dans plusieurs pays d’Afrique de l’Ouest :", "Quel titre unit toute la région ?", CHARTS, cross_border),
    "weekend": _t("Spécial week-end", None, None, None, None, None, None),
    "top_gh": _t("Top Ghana", "Top Ghana", ("Les titres qui font bouger", "le Ghana", "cette semaine"),
                 "🇬🇭 Ce qui tourne au Ghana cette semaine :", "Votre son du moment au Ghana ?", CHARTS, top_country("GH")),
    "nouveaux_clips": _t("Nouveaux clips", "Nouveaux clips", ("Tout juste sortis", "les nouveaux clips", "des deux dernières semaines"),
                         "🎬 Les nouveaux clips de nos artistes :", "Lequel avez-vous déjà regardé ?", YT, clips_new),
    "fans_deezer": _t("Les plus suivis sur Deezer", "Les plus suivis", ("Deezer", "les plus suivis", "artistes d’Afrique de l’Ouest"),
                      "💜 Les artistes d’Afrique de l’Ouest les plus suivis sur Deezer :", "Vous suivez qui ?", "Deezer (nombre de fans)",
                      lambda: _artists("fans", "fans Deezer")),
    "top_ci": _t("Top Côte d’Ivoire", "Top Côte d’Ivoire", ("Les titres qui font bouger", "la Côte d’Ivoire", "cette semaine"),
                 "🇨🇮 Ce qui tourne en Côte d’Ivoire cette semaine :", "Votre son du moment en Côte d’Ivoire ?", CHARTS, top_country("CI")),
    "deezer": _t("Top Deezer", "Top Deezer", ("Deezer", "le top", "en Afrique de l’Ouest"),
                 "🎧 Le meilleur de nos artistes dans les classements Deezer :", "Votre titre préféré de la liste ?",
                 "Classements Deezer (7 derniers jours)", by_source("deezer")),
    "sorties": _t("Sorties récentes", "Nouveautés", ("Tout juste sortis", "déjà classés", "les sorties des trois dernières semaines"),
                  "🆕 Sortis il y a moins de trois semaines, déjà dans les classements :", "Vous avez écouté lequel ?", CHARTS, releases),
    "revelations": _t("Révélations", "Révélations", ("À suivre de près", "les révélations", "jeunes talents déjà classés"),
                      "✨ Des artistes émergents déjà dans les classements :", "Qui sera la prochaine star ?",
                      CHARTS + " ; fans : Deezer", revelations),
    "top_sn": _t("Top Sénégal", "Top Sénégal", ("Les titres qui font bouger", "le Sénégal", "cette semaine"),
                 "🇸🇳 Ce qui tourne au Sénégal cette semaine :", "Votre son du moment au Sénégal ?", CHARTS, top_country("SN")),
    "youtube_tendances": _t("Tendances YouTube", "Tendances YouTube", ("YouTube", "en tendance", "musique en Afrique de l’Ouest"),
                            "🔥 Nos artistes dans les tendances YouTube :", "Vous l’avez vu passer ?",
                            "Tendances YouTube (7 derniers jours)", by_source("youtube_trending")),
    "clips_likes": _t("Clips les plus aimés", "Les plus aimés", ("YouTube", "les clips les plus aimés", "en nombre de « j’aime »"),
                      "❤️ Les clips qui récoltent le plus de « j’aime » :", "Votre coup de cœur ?", YT, clips_likes),
    "abonnes_youtube": _t("Les chaînes les plus suivies", "Abonnés YouTube", ("YouTube", "les chaînes les plus suivies", "artistes d’Afrique de l’Ouest"),
                          "📺 Les chaînes YouTube les plus suivies de nos artistes :", "Vous êtes abonné à laquelle ?",
                          "YouTube (nombre d’abonnés)", lambda: _artists("youtube_subscribers", "abonnés YouTube")),
    "featurings": _t("Featurings du moment", "Featurings", ("Ensemble c’est mieux", "les featurings", "classés cette semaine"),
                     "🤝 Les collaborations qui marchent cette semaine :", "Quel featuring rêvez-vous d’entendre ?", CHARTS, featurings),
    "actualites": _t("L’actu de la semaine", "L’actu", ("Ce qu’il fallait retenir", "l’actu musique", "de la semaine"),
                     "📰 L’actualité musicale de la semaine :", "Quelle info vous a marqué ?", "Médias cités", news),
    "clips_progression": _t("Plus fortes progressions", "En progression", ("YouTube", "ça décolle", "plus fortes hausses de vues en 7 jours"),
                            "📈 Les clips qui ont gagné le plus de vues cette semaine :", "Lequel va encore monter ?", YT, clips_growth),
    "apple_music": _t("Top Apple Music", "Apple Music", ("Apple Music", "le top", "en Afrique de l’Ouest"),
                      "🍎 Nos artistes dans les classements Apple Music :", "Votre préféré ?", "Classements Apple Music (7 derniers jours)",
                      by_source("apple_music")),
    "chiffres": _t("Cauri Charts en chiffres", "En chiffres", ("Cauri Charts", "en chiffres", "la musique d’Afrique de l’Ouest suivie au jour le jour"),
                   "📊 Cauri Charts en chiffres cette semaine :", "Quel pays domine selon vous ?", "Données Cauri Charts", key_figures),
}


def labels() -> dict:
    return {k: v["label"] for k, v in THEMES.items()}


def facts(key: str):
    """Faits d'une nouvelle rubrique, ou None (rubrique inconnue, historique, ou sans données)."""
    th = THEMES.get(key)
    if not th or not th["build"]:
        return None
    entries = [e for e in (th["build"]() or []) if e]
    if not entries:
        return None
    return {"kind": "ranking", "theme": key, "label": th["label"], "headline": th["label"], "big": th["big"], "cover": th["cover"],
            "intro": th["intro"], "question": th["question"], "top": entries, "source": th["source"],
            # Sans photo dans la liste (chiffres, actualités) : photo d'un artiste suivi, tirée au hasard
            "image": next((e["image_url"] for e in entries if e.get("image_url")), None) or db.value(
                "SELECT image_url FROM artists WHERE status = 'active' AND image_url LIKE 'https://%' ORDER BY random() LIMIT 1")}


def rotation() -> list:
    """Rubriques par ancienneté de dernière publication (jamais publiées d'abord, dans l'ordre du registre)."""
    last = {r["theme"]: r["d"] for r in db.all("SELECT theme, MAX(slot_date) AS d FROM social_posts GROUP BY theme")}
    keys = list(THEMES)
    return sorted(keys, key=lambda k: (last.get(k) is not None, last.get(k) or date.min, keys.index(k)))
