"""Enregistre un classement de plateforme (traduction d'Import\\ChartImporter).

Chaque ligne est rapprochée d'un titre existant (identifiant de plateforme, sinon artiste + titre
normalisés) ; sinon le titre et l'artiste sont créés, puis la position est notée (chart_observations).
Un artiste découvert ainsi arrive « en attente » avec un pays suggéré : il n'entre dans les classements
qu'après confirmation de son pays de soumission (règle des pays).
"""
import re

from core import audit, db
from core.helpers import slugify
from core.services.imports import normalizer as N

PLATFORMS = ["youtube", "audiomack", "boomplay", "spotify", "apple_music", "deezer"]


def _stats():
    return {"rows": 0, "matched": 0, "new_tracks": 0, "new_artists": 0}


def import_chart(country_code: str, source: str, snapshot: dict, user_id: int | None = None) -> dict:
    country = db.one("SELECT id, code FROM countries WHERE code = ?", [country_code.upper()])
    if not country:
        raise ValueError(f"Pays inconnu : {country_code}")
    cid, day, stats = int(country["id"]), snapshot["observed_on"], _stats()
    with db.atomic():
        # Un nouvel import du même classement le même jour remplace le précédent
        db.run("DELETE FROM chart_observations WHERE source = ? AND country_id = ? AND observed_on = ?", [source, cid, day])
        for row in snapshot["rows"]:
            t, a = str(row.get("title") or "").strip(), str(row.get("artist") or "").strip()
            if t == "" or a == "" or int(row["position"]) < 1:
                continue
            track_id = _find_or_create_track(row, source, cid, stats)
            db.run("""INSERT INTO chart_observations (source, country_id, observed_on, position, track_id, raw_title, raw_artist) VALUES (?, ?, ?, ?, ?, ?, ?)
                      ON CONFLICT (source, country_id, observed_on, position) DO UPDATE SET track_id = EXCLUDED.track_id,
                        raw_title = EXCLUDED.raw_title, raw_artist = EXCLUDED.raw_artist""",
                   [source, cid, day, int(row["position"]), track_id, t[:255], a[:255]])
            stats["rows"] += 1
        refresh_guessed_countries()
    audit.log(user_id, "import.chart", "country_source", f"{country['code']}:{source}:{day}", None, stats)
    return stats


def upsert_track(row: dict, source: str, country_id: int) -> tuple[int, dict]:
    """Crée ou retrouve un titre (et son artiste) sans noter de position : artistes suivis, chaînes de labels."""
    stats = {**_stats(), "rows": 1}
    return _find_or_create_track(row, source, country_id, stats), stats


def _find_or_create_track(row: dict, source: str, cid: int, stats: dict) -> int:
    # Une source peut indiquer la plateforme de ses identifiants (tendances YouTube : identifiant de vidéo)
    platform = row.get("platform") or (source if source in PLATFORMS else None)
    platform = platform if platform in PLATFORMS else None
    external_id = str(row["external_id"]) if row.get("external_id") not in (None, "") else None

    if platform and external_id:
        tid = db.value("SELECT track_id FROM track_platform_ids WHERE platform = ? AND external_id = ?", [platform, external_id])
        if tid:
            stats["matched"] += 1
            return int(tid)

    key = N.track_key(row["title"], row["artist"])
    track_id = db.value("SELECT id FROM tracks WHERE match_key = ? LIMIT 1", [key])
    if not track_id:
        # Titres saisis avant l'import (sans clé) : comparaison sur le nom
        for cand in db.all("""SELECT t.id, t.title, a.name FROM tracks t JOIN artists a ON a.id = t.artist_id
                              WHERE t.match_key IS NULL AND a.match_key IS NULL AND a.name ILIKE ?""",
                           [_like(N.primary_artist(row["artist"])) + "%"]):
            if N.track_key(cand["title"], cand["name"]) == key:
                track_id = int(cand["id"])
                db.update("tracks", {"match_key": key}, "id = :id", {"id": track_id})
                break

    if track_id:
        stats["matched"] += 1
    else:
        artist_id = _find_or_create_artist(row["artist"], cid, stats)
        feat = N.featuring(row["artist"])
        image = row.get("image") or ""
        track_id = db.insert("tracks", {
            "title": str(row["title"]).strip()[:200],
            "slug": unique_slug("tracks", slugify(N.primary_artist(row["artist"]) + " " + str(row["title"]))),
            "artist_id": artist_id,
            "featuring": feat[:255] if feat else None,
            "release_date": str(row["release_date"])[:10] if row.get("release_date") else None,
            "cover_url": image if image.startswith("https://") else None,
            "match_key": key,
        })
        stats["new_tracks"] += 1

    if platform and external_id:
        db.run("""INSERT INTO track_platform_ids (track_id, platform, external_id, kind, url, published_at, match_status)
                  VALUES (?, ?, ?, ?, ?, ?, 'auto') ON CONFLICT DO NOTHING""",
               [track_id, platform, external_id[:191], row.get("kind") or "main", row.get("url"),
                str(row["release_date"])[:10] if row.get("release_date") else None])
    return int(track_id)


def _like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _find_or_create_artist(artist_field: str, cid: int, stats: dict) -> int:
    name, key = N.primary_artist(artist_field), N.artist_key(artist_field)
    aid = db.value("SELECT id FROM artists WHERE match_key = ? LIMIT 1", [key])
    if not aid:
        for a in db.all("SELECT id, name FROM artists WHERE match_key IS NULL AND name ILIKE ?", [_like(name[:3]) + "%"]):
            if N.artist_key(a["name"]) == key:
                aid = int(a["id"])
                db.update("artists", {"match_key": key}, "id = :id", {"id": aid})
                break
    if aid:
        return int(aid)
    stats["new_artists"] += 1
    return db.insert("artists", {
        "name": name[:150], "slug": unique_slug("artists", slugify(name)),
        "submission_country_id": cid,  # provisoire : l'artiste reste en attente tant que le pays n'est pas confirmé
        "status": "pending", "guessed_country_id": cid, "match_key": key,
    })


def refresh_guessed_countries() -> None:
    """Pays suggéré d'un artiste en attente : celui dont les classements le citent le plus souvent."""
    db.run("""UPDATE artists a SET guessed_country_id = best.country_id FROM (
                SELECT t.artist_id, o.country_id, COUNT(*) AS n,
                       ROW_NUMBER() OVER (PARTITION BY t.artist_id ORDER BY COUNT(*) DESC, o.country_id) AS rk
                FROM chart_observations o JOIN tracks t ON t.id = o.track_id GROUP BY t.artist_id, o.country_id
              ) best WHERE best.artist_id = a.id AND best.rk = 1 AND a.status = 'pending'""")


def parse_csv(text: str) -> list[dict]:
    """Lignes collées dans l'admin : « position;titre;artiste » (ou tabulation) ; sans position, l'ordre fait foi."""
    rows, n = [], 0
    for line in re.split(r"\r\n|\n|\r", text.strip()):
        if line.strip() == "":
            continue
        cols = [c.strip() for c in re.split(r"\t|;", line)]
        n += 1
        if len(cols) >= 3 and cols[0].isdigit():
            pos, t, a = cols[0], cols[1], cols[2]
            external = cols[3] if len(cols) > 3 else None
        elif len(cols) >= 2:
            t, a, pos = cols[0], cols[1], n
            external = cols[2] if len(cols) > 2 else None
        else:
            raise ValueError(f"Ligne {n} illisible : « {line} »")
        rows.append({"position": int(pos), "title": t, "artist": a, "external_id": external or None})
    return rows


def unique_slug(table: str, base: str) -> str:
    slug, i = base, 2
    while db.value(f"SELECT id FROM {table} WHERE slug = ?", [slug]):
        slug, i = f"{base}-{i}", i + 1
    return slug
