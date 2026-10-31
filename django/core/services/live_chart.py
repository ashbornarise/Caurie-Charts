"""Classements en direct (traduction fidèle de Services\\Charts\\LiveChart).

Chaque position rapporte des points sur 100 selon la taille du classement de la plateforme
(n° 1 d'un Top 200 = 100 points, dernier = 0,5). Artistes hors des pays couverts masqués.
Modes : prime, buzz, fresh, icon, legend (voir METHODOLOGIE.md, section 5 bis).
"""
import hashlib
import json
from datetime import date, timedelta

from django.core.cache import cache

from core import clock
from core import conf, db

SOURCES = {
    "apple_music": "Apple Music",
    "deezer": "Deezer",
    "shazam": "Shazam",
    "youtube_trending": "YouTube tendances",
    "youtube_discovery": "YouTube nouveaux clips",
    "deezer_popularity": "Popularité Deezer",
    "youtube_views": "Vues YouTube",
}
WINDOWS = {"latest": "latest", "week": 7, "month": 30, "year": 365, "all": "all"}
DISCOVERY = ["shazam", "youtube_trending", "youtube_discovery"]
CACHE_TTL = 1800  # 30 minutes


def sources(country_id=None) -> list[str]:
    params, where = [], "observed_on >= CURRENT_DATE - 3"
    if country_id is not None:
        where += " AND country_id = ?"
        params.append(country_id)
    found = {r["source"] for r in db.all(f"SELECT DISTINCT source FROM chart_observations WHERE {where}", params)}
    return [s for s in SOURCES if s in found]


def build(country_id=None, source=None, limit: int = 100, mode: str = "prime", top_size: int = 20, period: str = "latest") -> dict:
    """Classement demandé, mis en cache 30 minutes. La clé inclut le dernier relevé : un nouvel import l'invalide.
    Deux niveaux : la mémoire de l'instance, puis la table live_cache (partagée par toutes les instances Vercel, qui
    repartent à vide à chaque démarrage). Sans elle, chaque page vue par un robot recalculait tout (Neon jamais en
    veille, 207 heures de calcul en octobre 2026)."""
    stamp = cache.get("live:stamp")
    if stamp is None:
        stamp = str(db.value("SELECT MAX(id) FROM chart_observations") or "")   # index de la clé : immédiat
        cache.set("live:stamp", stamp, 120)
    key = "live:" + hashlib.md5(json.dumps([country_id, source, limit, mode, top_size, period, stamp]).encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    cached = _partage_lit(key)
    if cached is None:
        cached = _compute(country_id, source, limit, mode, top_size, period)
        cached["rows"] = _with_spotify(cached["rows"])
        _partage_ecrit(key, cached)
    cache.set(key, cached, CACHE_TTL)
    return cached


def _table() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS live_cache (cle VARCHAR(40) PRIMARY KEY, valeur TEXT NOT NULL,
              expire TIMESTAMPTZ NOT NULL)""")


def _partage_lit(key: str):
    try:
        v = db.value("SELECT valeur FROM live_cache WHERE cle = ? AND expire > NOW()", [key])
        if not v:
            return None
        result = json.loads(v)
        # JSON a rendu les dates en texte : on les retrouve telles que la base les donne
        for obj, champs in [(result, ("day", "since"))] + [(r, ("release_date", "observed_on")) for r in result["rows"]]:
            for c in champs:
                if isinstance(obj.get(c), str) and len(obj[c]) == 10:
                    obj[c] = date.fromisoformat(obj[c])
        return result
    except Exception:  # noqa: BLE001 — table absente : elle est créée à la première écriture
        return None


def _partage_ecrit(key: str, value: dict) -> None:
    texte = json.dumps(value, default=str, ensure_ascii=False)
    for essai in range(2):
        try:
            db.run(f"""INSERT INTO live_cache (cle, valeur, expire) VALUES (?, ?, NOW() + INTERVAL '{CACHE_TTL} seconds')
                       ON CONFLICT (cle) DO UPDATE SET valeur = EXCLUDED.valeur, expire = EXCLUDED.expire""", [key, texte])
            if int(key[-4:], 16) % 50 == 0:   # ménage de temps en temps
                db.run("DELETE FROM live_cache WHERE expire < NOW() - INTERVAL '1 day'")
            return
        except Exception:  # noqa: BLE001
            if essai:
                return
            _table()


def clear_cache() -> None:
    cache.clear()
    try:
        db.run("DELETE FROM live_cache")
    except Exception:  # noqa: BLE001
        pass


def _with_spotify(rows: list[dict]) -> list[dict]:
    ids = [int(r["track_id"]) for r in rows if not r.get("is_artist") and r.get("track_id")]
    if not ids:
        return rows
    declared = {int(d["track_id"]): d for d in db.all(
        f"""SELECT track_id, SUM(streams) AS streams, MIN(period_start) AS start, MAX(period_end) AS "end" FROM submissions
            WHERE platform = 'spotify' AND status = 'validated' AND period_end >= CURRENT_DATE - 35
              AND track_id IN ({','.join(['?'] * len(ids))}) GROUP BY track_id""", ids)}
    for r in rows:
        r["spotify_declared"] = declared.get(int(r["track_id"])) if r.get("track_id") is not None else None
    return rows


def _compute(country_id, source, limit, mode, top_size, period) -> dict:
    window = "all" if mode == "legend" else WINDOWS.get(period, "latest")
    rows = _observations(country_id, source, window)
    # Classement des cinq pays : chaque pays pèse autant (points divisés par le nombre de sources du pays)
    per_country: dict = {}
    if country_id is None and source is None:
        for r in rows:
            per_country.setdefault(r["chart_country"], set()).add(r["source"])
    tracks: dict = {}
    day = since = None
    for r in rows:
        day = max(day or r["observed_on"], r["observed_on"])
        since = min(since or r["observed_on"], r["observed_on"])
        size = max(1, int(r["size"]))
        points = 100 * (size + 1 - int(r["position"])) / size
        if per_country:
            points /= len(per_country[r["chart_country"]])
        tid = int(r["track_id"])
        if tid not in tracks:
            tracks[tid] = {**r, "points": 0.0, "discovery": 0.0, "seen": {}, "best": 10 ** 12}
        t = tracks[tid]
        t["points"] += points
        if r["source"] in DISCOVERY:
            t["discovery"] += points
        t["best"] = min(t["best"], int(r["position"]))
        k = r["source"] + r["chart_country"]
        if k not in t["seen"] or t["seen"][k]["position"] > int(r["position"]):
            t["seen"][k] = {"source": r["source"], "country": r["chart_country"], "position": int(r["position"])}
    items = list(tracks.values())
    if country_id is None:
        items = [t for t in items if t.get("status") == "active"]
    if country_id is not None:
        # Même règle que le classement officiel : un pays ne classe que ses propres artistes. Les tops des plateformes
        # d'un pays contiennent des artistes d'ailleurs (Nigeria au Liberia…) : ils ne remplissent pas son classement.
        items = [t for t in items if t.get("artist_country") == t.get("chart_country")]
        # Pas de classement « coûte que coûte » : trop peu d'artistes du pays suivis = un seul artiste répété partout.
        # On affiche alors « pas encore assez de données » plutôt qu'un Top rempli artificiellement.
        artists = {t["artist_id"] for t in items if t.get("status") == "active"}
        minimum = int(conf.get("live_chart.min_artists", 8) or 0)
        if source is None and len(artists) < minimum:
            return {"rows": [], "day": day, "since": since, "insufficient": {"artists": len(artists), "min": minimum}}
    for t in items:
        t["seen"] = sorted(t["seen"].values(), key=lambda s: s["position"])

    if source is not None and country_id is not None and mode == "prime":
        items.sort(key=lambda t: t["best"])
        for t in items:
            t["rank"] = t["best"]  # vue d'une plateforme : positions d'origine
        return {"rows": items[:limit], "day": day, "since": since}

    by_points = lambda t: (-t["points"], -len(t["seen"]), t["best"])  # noqa: E731
    items.sort(key=by_points)
    if mode == "prime" and country_id is None and source is None and conf.get("charts.prime-wa.country_cap"):
        # Classement régional : au plus N titres d'artistes d'un même pays dans le Top (même règle que le classement officiel)
        from core.services.charts import ChartRanker
        items = ChartRanker.cap_per_country([{**t, "country": t.get("artist_country")} for t in items], top_size,
                                            int(conf.get("charts.prime-wa.country_cap")))

    if mode == "buzz":
        top_size = min(top_size, len(items) // 2)
        top = {int(t["track_id"]) for t in items[:top_size]}
        rises = _rises(country_id, day)
        items = [t for t in items if int(t["track_id"]) not in top]
        for t in items:
            t["rise"] = rises.get(int(t["track_id"]), 0)
            t["points"] = t["discovery"] + t["rise"]
        items = [t for t in items if t["points"] > 0]
        items.sort(key=by_points)
    elif mode == "fresh":
        limit_date = (clock.today() - timedelta(days=56)).isoformat()
        items = [t for t in items if (t["release_date"] and t["release_date"] >= limit_date) or t["is_emerging"]]
    elif mode == "icon":
        items = _by_artist(items)

    for i, t in enumerate(items):
        t["rank"] = i + 1
    return {"rows": items[:limit], "day": day, "since": since}


def _observations(country_id, source, window) -> list[dict]:
    params, flt = [], ""
    if country_id is not None:
        flt += " AND o.country_id = ?"
        params.append(country_id)
    if source is not None:
        flt += " AND o.source = ?"
        params.append(source)
    if isinstance(window, int):
        flt += f" AND o.observed_on >= CURRENT_DATE - {int(window)}"
    # taille de chaque classement : calculée sur la même fenêtre, pas sur tout l'historique
    sizes = flt.replace("o.", "")
    if window == "latest":
        sizes += " AND observed_on >= CURRENT_DATE - 3"
    latest = "" if window != "latest" else """JOIN (SELECT source, country_id, MAX(observed_on) AS day FROM chart_observations
                  WHERE observed_on >= CURRENT_DATE - 3 GROUP BY source, country_id) d
             ON d.source = o.source AND d.country_id = o.country_id AND d.day = o.observed_on"""
    return db.all(
        f"""SELECT o.source, o.position, o.observed_on, oc.code AS chart_country, l.size,
                   t.id AS track_id, t.title, t.slug AS track_slug, t.cover_url, t.featuring, t.release_date,
                   a.id AS artist_id, a.name AS artist_name, a.slug AS artist_slug, a.image_url AS artist_image, a.status,
                   a.is_emerging, a.spotify_id AS artist_spotify,
                   COALESCE(CASE WHEN a.status = 'active' THEN ac.code END, a.base_country, gc.code) AS artist_country
            FROM chart_observations o
            {latest}
            JOIN (SELECT source, country_id, observed_on, MAX(position) AS size FROM chart_observations
                   WHERE TRUE{sizes} GROUP BY source, country_id, observed_on) l
              ON l.source = o.source AND l.country_id = o.country_id AND l.observed_on = o.observed_on
            JOIN countries oc ON oc.id = o.country_id
            JOIN tracks t ON t.id = o.track_id
            JOIN artists a ON a.id = t.artist_id
            LEFT JOIN countries ac ON ac.id = a.submission_country_id
            LEFT JOIN countries gc ON gc.id = a.guessed_country_id
            WHERE a.status <> 'out_of_scope'{flt}
            ORDER BY o.id""", params + params)


def _rises(country_id, day) -> dict:
    if not day:
        return {}
    params, flt = [day, day, day], ""
    if country_id is not None:
        flt, params = " AND now.country_id = ?", params + [country_id]
    rows = db.all(
        f"""SELECT now.track_id, now.position AS pos, MIN(prev.position) AS prev_pos,
                   (SELECT MAX(position) FROM chart_observations s WHERE s.source = now.source AND s.country_id = now.country_id
                     AND s.observed_on = now.observed_on) AS size
            FROM chart_observations now
            JOIN chart_observations prev ON prev.track_id = now.track_id AND prev.source = now.source AND prev.country_id = now.country_id
                 AND prev.observed_on BETWEEN ?::date - 8 AND ?::date - 5
            WHERE now.observed_on = ?::date{flt}
            GROUP BY now.track_id, now.source, now.country_id, now.position, now.observed_on""", params)
    rises: dict = {}
    for r in rows:
        gain = int(r["prev_pos"]) - int(r["pos"])
        if gain > 0:
            rises[int(r["track_id"])] = rises.get(int(r["track_id"]), 0) + 100 * gain / max(1, int(r["size"]))
    return rises


def _by_artist(items: list[dict]) -> list[dict]:
    artists: dict = {}
    for t in items:
        aid = int(t["artist_id"])
        if aid not in artists:
            artists[aid] = {**t, "titles": 0, "top_title": t["title"], "top_slug": t["track_slug"], "points": 0.0, "seen": {}}
        a = artists[aid]
        a["points"] += t["points"]
        a["titles"] += 1
        for s in t["seen"]:
            k = s["source"] + s["country"]
            if k not in a["seen"] or a["seen"][k]["position"] > s["position"]:
                a["seen"][k] = s
    out = list(artists.values())
    for a in out:
        a["seen"] = sorted(a["seen"].values(), key=lambda s: s["position"])
        a["is_artist"] = True
    out.sort(key=lambda a: (-a["points"], -a["titles"]))
    return out
