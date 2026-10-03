"""Lectures publiques (traduction de ChartRepository, NewsRepository et PartnerRepository).

MySQL → PostgreSQL : « <=> » devient IS NOT DISTINCT FROM, CURDATE() - INTERVAL n DAY devient CURRENT_DATE - n,
FIELD() devient array_position(). MySQL range les NULL en tête en tri croissant (et en fin en décroissant),
PostgreSQL l'inverse : NULLS FIRST/LAST est précisé pour garder exactement le même ordre.
"""
import json
import math
import secrets
from datetime import datetime, timezone

from core import conf, db


def php_round(x: float, precision: int = 0):
    """round() de PHP : moitié vers l'extérieur (Python arrondit au pair)."""
    m = 10 ** precision
    r = math.floor(abs(x) * m + 0.5) / m
    r = r if x >= 0 else -r
    return int(r) if precision == 0 else r


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- classements

def countries(active_only: bool = True) -> list[dict]:
    return db.all("SELECT * FROM countries" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY sort_order, code")


def country(code: str) -> dict | None:
    return db.one("SELECT * FROM countries WHERE code = ? AND is_active = 1", [str(code).upper()])


def number_ones() -> dict:
    rows = db.all(
        """SELECT COALESCE(c.code, 'WA') AS code, t.title, t.slug AS track_slug, a.name AS artist_name
           FROM chart_runs r
           JOIN chart_types ct ON ct.id = r.chart_type_id AND ct.code IN ('prime', 'prime-wa')
           LEFT JOIN countries c ON c.id = r.country_id
           JOIN chart_entries e ON e.chart_run_id = r.id AND e.position = 1
           JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
           WHERE r.period_type = 'week' AND r.status = 'published'
             AND r.period_end = (SELECT MAX(r2.period_end) FROM chart_runs r2
                                 WHERE r2.country_id IS NOT DISTINCT FROM r.country_id AND r2.chart_type_id = r.chart_type_id
                                   AND r2.period_type = 'week' AND r2.status = 'published')""")
    return {r["code"]: r for r in rows}


def latest_run(country_id, chart_code: str, period_type: str) -> dict | None:
    return db.one(
        """SELECT r.*, ct.code AS chart_code, ct.kind FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
           WHERE r.country_id IS NOT DISTINCT FROM ?::smallint AND ct.code = ? AND r.period_type = ? AND r.status = 'published' AND ct.is_public = 1
           ORDER BY r.period_end DESC LIMIT 1""", [country_id, chart_code, period_type])


def run(country_id, chart_code: str, period_type: str, period_key: str) -> dict | None:
    return db.one(
        """SELECT r.*, ct.code AS chart_code, ct.kind FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
           WHERE r.country_id IS NOT DISTINCT FROM ?::smallint AND ct.code = ? AND r.period_type = ? AND r.period_key = ?
             AND r.status = 'published' AND ct.is_public = 1""", [country_id, chart_code, period_type, period_key])


def run_by_id(run_id: int, published_only: bool = True) -> dict | None:
    return db.one(
        """SELECT r.*, ct.code AS chart_code, ct.kind, COALESCE(c.code, 'WA') AS country_code, COALESCE(c.chart_size, 20) AS chart_size
           FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id LEFT JOIN countries c ON c.id = r.country_id
           WHERE r.id = ?""" + (" AND r.status = 'published'" if published_only else ""), [run_id])


def published_runs(country_id, chart_code: str, period_type: str, limit: int = 60) -> list[dict]:
    return db.all(
        f"""SELECT r.id, r.period_key, r.period_start, r.period_end, r.is_provisional FROM chart_runs r
            JOIN chart_types ct ON ct.id = r.chart_type_id
            WHERE r.country_id IS NOT DISTINCT FROM ?::smallint AND ct.code = ? AND r.period_type = ? AND r.status = 'published'
            ORDER BY r.period_end DESC LIMIT {int(limit)}""", [country_id, chart_code, period_type])


def entries(run_id: int, limit: int | None = None) -> list[dict]:
    rows = db.all(
        """SELECT e.*, t.title, t.slug AS track_slug, t.featuring, t.cover_url, t.release_date,
                  a.name AS artist_name, a.slug AS artist_slug, a.label_owner, ac.code AS artist_country
           FROM chart_entries e
           LEFT JOIN tracks t ON t.id = e.track_id
           LEFT JOIN artists a ON a.id = COALESCE(e.artist_id, t.artist_id)
           LEFT JOIN countries ac ON ac.id = a.submission_country_id
           WHERE e.chart_run_id = ? ORDER BY e.position""" + (f" LIMIT {int(limit)}" if limit else ""), [run_id])
    return _with_sources(run_id, rows) if rows else []


def _with_sources(run_id: int, rows: list[dict]) -> list[dict]:
    r = db.one("""SELECT r.country_id, r.period_type, r.period_start, r.period_end, ct.code
                  FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id WHERE r.id = ?""", [run_id])
    if not r:
        return rows
    is_artist = rows[0]["track_id"] is None
    ids = [int(e["artist_id"] if is_artist else e["track_id"]) for e in rows if (e["artist_id"] if is_artist else e["track_id"])]
    if not ids:
        return rows
    if r["code"] == "legend":
        frm, to = "1970-01-01", r["period_end"]
    elif r["period_type"] == "week":
        frm, to = r["period_start"], r["period_start"]
    else:
        frm, to = r["period_start"], r["period_end"]
    key = "t.artist_id" if is_artist else "w.track_id"
    params = [frm, to]
    country_sql = ""
    if r["country_id"] is not None:
        country_sql = " AND w.country_id = ?"
        params.append(int(r["country_id"]))
    data = db.all(
        f"""SELECT {key} AS id, w.breakdown FROM weekly_scores w JOIN tracks t ON t.id = w.track_id
            WHERE w.week_start BETWEEN ? AND ?{country_sql} AND w.review_status <> 'excluded'
              AND {key} IN ({','.join(['?'] * len(ids))})""", params + ids)
    depth = int(conf.get("formula.chart_depth", 100))
    totals: dict = {}
    chart_weeks: dict = {}
    for row in data:
        for source, b in (json.loads(row["breakdown"] or "{}") or {}).items():
            delta = float(b.get("delta", 0) or 0)
            if delta <= 0:
                continue
            t = totals.setdefault(row["id"], {})
            if source.startswith("chart:"):
                platform = source[6:]
                t.setdefault(platform, {})["chart_sum"] = t.get(platform, {}).get("chart_sum", 0) + delta
                chart_weeks.setdefault(row["id"], {})[platform] = chart_weeks.get(row["id"], {}).get(platform, 0) + 1
                continue
            if source.startswith("declaration:"):
                if float(b.get("weight", 0) or 0) <= 0:
                    continue
                platform = source[12:]
                t.setdefault(platform, {})["declared"] = t.get(platform, {}).get("declared", 0) + delta
                continue
            kind = "views" if source == "youtube" else "plays"
            t.setdefault(source, {})[kind] = t.get(source, {}).get(kind, 0) + delta
    for e in rows:
        rid = int(e["artist_id"] if is_artist else e["track_id"])
        sources, streams, views = {}, 0, 0
        for platform, t in totals.get(rid, {}).items():
            if "views" in t:
                views += int(t["views"])
                sources[platform] = {"kind": "views", "value": int(t["views"])}
            elif "plays" in t or "declared" in t:
                value = int(t.get("plays", 0) + t.get("declared", 0))
                streams += value
                sources[platform] = {"kind": "plays" if "plays" in t else "declared", "value": value}
            elif "chart_sum" in t:
                avg = t["chart_sum"] / max(1, chart_weeks[rid][platform])
                sources[platform] = {"kind": "chart", "value": max(1, php_round(depth + 1 - avg))}
        e["sources"] = dict(sorted(sources.items(), key=lambda kv: (kv[1]["kind"] == "chart", -kv[1]["value"])))
        e["streams"] = streams
        e["views"] = views
    return rows


def artist(slug: str) -> dict | None:
    return db.one(
        """SELECT a.*, c.code AS country_code, tc.code AS top_country_code
           FROM artists a JOIN countries c ON c.id = a.submission_country_id LEFT JOIN countries tc ON tc.id = a.top_country_id
           WHERE a.slug = ? AND a.status <> 'out_of_scope'""", [slug])


def artist_tracks(artist_id: int) -> list[dict]:
    return db.all(
        """SELECT t.id, t.title, t.slug, t.featuring, t.cover_url, t.release_date,
                  MIN(e.position) AS peak, COUNT(e.id) AS weeks,
                  (SELECT e2.position FROM chart_entries e2 JOIN chart_runs r2 ON r2.id = e2.chart_run_id
                    WHERE e2.track_id = t.id AND r2.chart_type_id = ct.id AND r2.period_type = 'week' AND r2.status = 'published'
                    ORDER BY r2.period_end DESC LIMIT 1) AS last_position
           FROM tracks t
           JOIN chart_types ct ON ct.code = 'prime'
           LEFT JOIN chart_runs r ON r.chart_type_id = ct.id AND r.period_type = 'week' AND r.status = 'published'
           LEFT JOIN chart_entries e ON e.chart_run_id = r.id AND e.track_id = t.id
           WHERE t.artist_id = ?
           GROUP BY t.id, t.title, t.slug, t.featuring, t.cover_url, t.release_date, ct.id
           ORDER BY MIN(e.position) IS NULL, MIN(e.position), t.release_date DESC NULLS LAST""", [artist_id])


def artist_live(artist_id: int) -> dict:
    positions = db.all(
        """SELECT o.source, c.code AS country, t.title, t.slug AS track_slug, MIN(o.position) AS best
           FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN countries c ON c.id = o.country_id
           WHERE t.artist_id = ? AND o.observed_on >= CURRENT_DATE - 7
           GROUP BY o.source, c.code, t.id, t.title, t.slug
           ORDER BY MIN(o.position), o.source""", [artist_id])
    videos = db.all(
        """SELECT t.id AS track_id, p.url, p.kind,
                  (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id ORDER BY s.captured_on DESC LIMIT 1) AS views,
                  (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id AND s.captured_on <= CURRENT_DATE - 7
                    ORDER BY s.captured_on DESC LIMIT 1) AS views_week_ago,
                  (SELECT MAX(s.captured_on) FROM snapshots s WHERE s.track_platform_id = p.id) AS measured_on
           FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id
           WHERE t.artist_id = ? AND p.platform = 'youtube'""", [artist_id])
    by_track, total, week, measured = {}, 0, 0, None
    for v in videos:
        if v["views"] is None:
            continue
        by_track[int(v["track_id"])] = by_track.get(int(v["track_id"]), 0) + int(v["views"])
        total += int(v["views"])
        if v["views_week_ago"] is not None:
            week += max(0, int(v["views"]) - int(v["views_week_ago"]))
        measured = max(measured or v["measured_on"], v["measured_on"])
    tracks = db.all(
        """SELECT t.id, t.title, t.slug, t.featuring, t.cover_url, t.release_date,
                  (SELECT MIN(o.position) FROM chart_observations o WHERE o.track_id = t.id) AS best_ever,
                  (SELECT o.source FROM chart_observations o WHERE o.track_id = t.id ORDER BY o.position, o.observed_on DESC LIMIT 1) AS best_source,
                  (SELECT c.code FROM chart_observations o JOIN countries c ON c.id = o.country_id WHERE o.track_id = t.id
                    ORDER BY o.position, o.observed_on DESC LIMIT 1) AS best_country
           FROM tracks t WHERE t.artist_id = ? AND t.is_active = 1
           ORDER BY (SELECT MIN(o.position) FROM chart_observations o WHERE o.track_id = t.id) IS NULL,
                    (SELECT MIN(o.position) FROM chart_observations o WHERE o.track_id = t.id), t.release_date DESC NULLS LAST""", [artist_id])
    for t in tracks:
        t["views"] = by_track.get(int(t["id"]))
    return {
        "positions": positions,
        "tracks": tracks,
        "views_total": total if videos else None,
        "views_week": week or None,
        "measured_on": measured,
        "charts_count": len({p["source"] + p["country"] for p in positions}),
    }


def hot_artists(country_id=None, limit: int = 12) -> list[dict]:
    params, flt = [], ""
    if country_id is not None:
        flt, params = " AND a.submission_country_id = ?", [country_id]
    return db.all(
        f"""SELECT a.id, a.name, a.slug, a.image_url, a.fans, c.code AS country_code,
                   COUNT(DISTINCT o.source || '-' || o.country_id) AS charts, MIN(o.position) AS best,
                   (SELECT o2.source FROM chart_observations o2 JOIN tracks t2 ON t2.id = o2.track_id
                     WHERE t2.artist_id = a.id AND o2.observed_on >= CURRENT_DATE - 7 ORDER BY o2.position, o2.id LIMIT 1) AS best_source
            FROM artists a
            JOIN countries c ON c.id = a.submission_country_id
            LEFT JOIN tracks t ON t.artist_id = a.id
            LEFT JOIN chart_observations o ON o.track_id = t.id AND o.observed_on >= CURRENT_DATE - 7
            WHERE a.status = 'active'{flt}
            GROUP BY a.id, a.name, a.slug, a.image_url, a.fans, c.code
            ORDER BY COUNT(DISTINCT o.source || '-' || o.country_id) DESC, MIN(o.position) IS NULL, MIN(o.position),
                     a.fans DESC NULLS LAST
            LIMIT {int(limit)}""", params)


def artist_icon_history(artist_id: int) -> list[dict]:
    return db.all(
        """SELECT r.period_key, r.period_end, e.position FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
           JOIN chart_types ct ON ct.id = r.chart_type_id
           WHERE e.artist_id = ? AND ct.code = 'icon' AND r.status = 'published' ORDER BY r.period_end""", [artist_id])


def track(slug: str) -> dict | None:
    return db.one(
        """SELECT t.*, a.name AS artist_name, a.slug AS artist_slug, a.label_owner, a.spotify_id AS artist_spotify, c.code AS country_code
           FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id
           WHERE t.slug = ? AND a.status <> 'out_of_scope'""", [slug])


def track_positions(track_id: int) -> list[dict]:
    return db.all(
        """SELECT r.period_key, r.period_start, r.period_end, e.position, e.score, c.chart_size
           FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id JOIN chart_types ct ON ct.id = r.chart_type_id
           JOIN countries c ON c.id = r.country_id
           WHERE e.track_id = ? AND ct.code = 'prime' AND r.period_type = 'week' AND r.status = 'published'
           ORDER BY r.period_end""", [track_id])


def track_links(track_id: int) -> list[dict]:
    return db.all(
        """SELECT platform, url, kind, external_id FROM track_platform_ids WHERE track_id = ? AND url IS NOT NULL
           ORDER BY array_position(ARRAY['youtube','audiomack','boomplay','spotify','apple_music','deezer']::varchar[], platform)""", [track_id])


def exclusions(limit: int = 50) -> list[dict]:
    return db.all(
        f"""SELECT tr.week_start, tr.reason, tr.created_at, t.title, t.slug, a.name AS artist_name, c.code AS country_code
            FROM track_reviews tr JOIN tracks t ON t.id = tr.track_id JOIN artists a ON a.id = t.artist_id
            JOIN countries c ON c.id = a.submission_country_id
            WHERE tr.decision = 'excluded' ORDER BY tr.week_start DESC LIMIT {int(limit)}""")


def sitemap_entries() -> dict:
    return {
        "artists": db.all("SELECT slug, name, updated_at, COALESCE(image_hd_url, image_url) AS image FROM artists WHERE status = 'active'"),
        # Titres classés par Cauri Charts, ou vus dans les classements des plateformes sur 90 jours (artistes de la zone)
        "tracks": db.all("""SELECT DISTINCT t.slug, t.title, a.name AS artist, t.cover_url FROM tracks t JOIN artists a ON a.id = t.artist_id
                            WHERE a.status <> 'out_of_scope' AND (
                                EXISTS (SELECT 1 FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id AND r.status = 'published'
                                        WHERE e.track_id = t.id)
                                OR EXISTS (SELECT 1 FROM chart_observations o WHERE o.track_id = t.id AND o.observed_on >= CURRENT_DATE - 30
                                           AND o.source NOT IN ('deezer_popularity', 'youtube_views')))"""),
        "news": db.all("SELECT slug, title, published_at, image_path, external_guid FROM news WHERE status = 'published' AND published_at <= ?", [now_utc()]),
    }


# ---------------------------------------------------------------- actualités

NEWS_CATEGORIES = ["annonce", "classement", "sortie", "evenement", "industrie"]


def news_latest(limit: int = 5, country_id=None, offset: int = 0) -> list[dict]:
    params = [now_utc()]
    where = "n.status = 'published' AND n.published_at <= ?"
    if country_id:
        where += " AND (n.country_id IS NULL OR n.country_id = ?)"
        params.append(country_id)
    return db.all(
        f"""SELECT n.*, c.code AS country_code FROM news n LEFT JOIN countries c ON c.id = n.country_id
            WHERE {where} ORDER BY n.published_at DESC NULLS LAST LIMIT {int(limit)} OFFSET {int(offset)}""", params)


def news_count_published() -> int:
    return int(db.value("SELECT COUNT(*) FROM news WHERE status = 'published' AND published_at <= ?", [now_utc()]))


def news_by_slug(slug: str) -> dict | None:
    return db.one(
        """SELECT n.*, c.code AS country_code FROM news n LEFT JOIN countries c ON c.id = n.country_id
           WHERE n.slug = ? AND n.status = 'published' AND n.published_at <= ?""", [slug, now_utc()])


# ---------------------------------------------------------------- partenaires

PARTNER_TIERS = ["officiel", "media", "plateforme", "institution"]


def partners_active() -> list[dict]:
    return db.all(
        """SELECT * FROM partners WHERE is_active = 1
           ORDER BY array_position(ARRAY['officiel','plateforme','media','institution']::varchar[], tier), sort_order, name""")


def partners_all() -> list[dict]:
    return db.all("SELECT * FROM partners ORDER BY is_active DESC, sort_order, name")


def partner(pid: int) -> dict | None:
    return db.one("SELECT * FROM partners WHERE id = ?", [pid])


def random_hex(n: int) -> str:
    return secrets.token_hex(n)


def footer_links() -> dict:
    """Liens du bas de page (artistes et titres du moment, dernières éditions), mis en cache une heure."""
    from django.core.cache import cache
    data = cache.get("footer-links")
    if data is not None:
        return data
    data = {
        "artists": db.all("""SELECT a.name, a.slug FROM artists a WHERE a.status = 'active'
                             AND EXISTS (SELECT 1 FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                                         WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 7)
                             ORDER BY COALESCE(a.youtube_subscribers, 0) + COALESCE(a.fans, 0) DESC LIMIT 8"""),
        "tracks": db.all("""SELECT t.title, t.slug FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                            JOIN artists a ON a.id = t.artist_id WHERE a.status = 'active' AND o.observed_on >= CURRENT_DATE - 3
                            GROUP BY t.id, t.title, t.slug ORDER BY COUNT(DISTINCT o.source || o.country_id) DESC, MIN(o.position) LIMIT 8"""),
        "editions": db.all("""SELECT title, slug FROM news WHERE status = 'published' AND origin = 'manual'
                              AND (external_guid LIKE 'cauri-hebdo-%' OR external_guid LIKE 'cauri-matin-%')
                              ORDER BY published_at DESC LIMIT 3"""),
    }
    cache.set("footer-links", data, 3600)
    return data
