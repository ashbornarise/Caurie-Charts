"""Faits RÉELS d'un post (traduction de Social\\PostFacts) : classements publiés par Cauri Charts s'il y en a,
sinon positions relevées dans les classements des plateformes. Rien n'est inventé : l'IA ne reçoit que ces faits.
"""
import json

from core import db
from core.services.live_chart import SOURCES


def _seen(track_id: int, extra: str = "") -> list:
    """Positions distinctes du titre sur 7 jours, meilleures d'abord (4 au plus) — équivalent du GROUP_CONCAT PHP."""
    rows = db.all(f"""SELECT DISTINCT o.source, c.code, o.position FROM chart_observations o JOIN countries c ON c.id = o.country_id
                      WHERE o.track_id = ? AND o.observed_on >= CURRENT_DATE - 7 {extra} ORDER BY o.position, o.source, c.code""", [track_id])
    return [{"platform": SOURCES.get(r["source"], r["source"]), "country": r["code"], "position": int(r["position"])} for r in rows[:4]]


def for_theme(theme: str):
    if theme == "classement":
        return _chart() or _platform_trends()
    if theme == "artiste":
        return _artist_of_the_week()
    if theme == "weekend":
        return _weekend()
    return None


def _chart():
    """Dernier classement Afrique de l'Ouest publié (Top 5, n° 1, plus forte montée)."""
    run = db.one("""SELECT r.id, r.period_start, r.period_end FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
                    WHERE ct.code = 'prime-wa' AND r.period_type = 'week' AND r.status = 'published'
                      AND r.period_end >= CURRENT_DATE - 10 ORDER BY r.period_end DESC LIMIT 1""")
    if not run:
        return None
    top = db.all("""SELECT t.id AS track_id, e.position, e.previous_position, e.weeks_on_chart, t.title, a.name AS artist, c.code AS country, a.image_url
                    FROM chart_entries e JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
                    JOIN countries c ON c.id = a.submission_country_id WHERE e.chart_run_id = ? ORDER BY e.position LIMIT 10""", [run["id"]])
    climber = None
    for e in top:
        if e["previous_position"] and e["previous_position"] - e["position"] > ((climber or {}).get("gain") or 0):
            climber = {**e, "gain": e["previous_position"] - e["position"]}
    return {"kind": "cauri_chart", "label": "Prime Chart · Afrique de l’Ouest", "headline": "Prime Chart Afrique de l’Ouest",
            "period": {"start": run["period_start"], "end": run["period_end"]}, "top": top[:5], "climber": climber,
            "image": top[0]["image_url"] if top else None, "source": "Classement Cauri Charts (méthodologie publique)"}


def _platform_trends():
    rows = db.all("""SELECT t.id AS track_id, t.title, a.name AS artist, a.image_url, COALESCE(a.base_country, gc.code) AS country,
                        COUNT(DISTINCT o.source || o.country_id) AS charts, MIN(o.position) AS best
                     FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                     LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                     WHERE o.observed_on >= CURRENT_DATE - 7 AND a.status <> 'out_of_scope'
                     GROUP BY t.id, a.id, gc.code ORDER BY charts DESC, best, t.id LIMIT 5""")
    if not rows:
        return None
    return {"kind": "platform_trends", "label": "Tendances de la semaine", "headline": "Les titres qui dominent les plateformes",
            "top": [{**r, "seen": _seen(int(r["track_id"]))} for r in rows], "image": rows[0]["image_url"],
            "source": "Classements Apple Music, Deezer, Shazam et YouTube (7 derniers jours)"}


def _recent_artist_ids() -> list:
    ids = []
    for r in db.all("SELECT facts FROM social_posts WHERE theme = 'artiste' AND slot_date >= CURRENT_DATE - 42 AND slot_date < CURRENT_DATE"):
        try:
            v = json.loads(r["facts"] or "")
            if isinstance(v, dict) and v.get("artist_id") is not None:
                ids.append(int(v["artist_id"]))
        except (ValueError, TypeError):
            pass
    return ids


def _artist_of_the_week():
    a = db.one("""SELECT a.id, a.name, a.slug, a.image_url, a.fans, COALESCE(a.base_country, gc.code) AS country,
                     COUNT(DISTINCT o.source || o.country_id) AS charts, MIN(o.position) AS best
                  FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                  LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                  WHERE o.observed_on >= CURRENT_DATE - 7 AND a.status = 'active' AND NOT (a.id = ANY(?::int[]))
                  GROUP BY a.id, gc.code ORDER BY charts DESC, best, a.fans DESC NULLS LAST, a.id LIMIT 1""", [_recent_artist_ids()])
    if not a:
        return None
    tracks = db.all("""SELECT t.id AS track_id, t.cover_url, t.title FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                       WHERE t.artist_id = ? AND o.observed_on >= CURRENT_DATE - 7
                       GROUP BY t.id ORDER BY MIN(o.position), t.id LIMIT 3""", [a["id"]])
    return {"kind": "artist", "label": "Artiste de la semaine", "headline": "Artiste de la semaine", "artist_id": int(a["id"]),
            "artist": {"name": a["name"], "country": a["country"], "deezer_fans": int(a["fans"]) if a["fans"] else None,
                       "profile": "/artiste/" + a["slug"]},
            "tracks": [{"track_id": int(t["track_id"]), "title": t["title"], "image_url": t["cover_url"], "seen": _seen(int(t["track_id"]))} for t in tracks],
            "image": a["image_url"], "source": "Classements Apple Music, Deezer, Shazam et YouTube ; fans : Deezer"}


def _weekend():
    new = db.all("""SELECT t.id AS track_id, t.title, a.name AS artist, a.image_url, MIN(o.position) AS best
                    FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                    WHERE o.observed_on >= CURRENT_DATE - 7 AND o.position <= 30 AND a.status <> 'out_of_scope'
                      AND NOT EXISTS (SELECT 1 FROM chart_observations o2 WHERE o2.track_id = t.id AND o2.observed_on < CURRENT_DATE - 7)
                    GROUP BY t.id, a.id ORDER BY best, t.id LIMIT 5""")
    news = db.all("""SELECT title, source_name FROM news WHERE status = 'published' AND published_at >= LOCALTIMESTAMP - INTERVAL '7 days'
                     ORDER BY country_id IS NULL, published_at DESC LIMIT 3""")
    if not new and not news:
        return None
    return {"kind": "weekend", "label": "Spécial week-end", "headline": "Ce que l’Afrique de l’Ouest écoute ce week-end",
            "top": [{**r, "seen": _seen(int(r["track_id"]), "AND o.position <= 30")} for r in new], "news": news,
            "image": new[0]["image_url"] if new else None,
            "source": "Nouvelles entrées dans les classements des plateformes ; actualités : médias cités"}
