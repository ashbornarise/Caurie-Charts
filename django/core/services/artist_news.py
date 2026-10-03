"""Actualité des artistes : sorties détectées chaque nuit sur Deezer, et faits ajoutés par la rédaction avec leur source.

  automatique : nouveaux clips des chaînes YouTube officielles (avec leurs vues), puis albums, EP et singles parus ces
                21 derniers jours sur Deezer ;
  rédaction   : sortie annoncée, concert, clip, distinction… saisi dans Admin > Actu des artistes, lien de la source
                obligatoire (compte officiel de l'artiste, média).
Affichée sur l'accueil (« L'actu des artistes ») et sur la fiche de chaque artiste.
"""
import json
import re
from datetime import date, timedelta

from core import budget, clock, db
from core.services.platforms import HttpClient

KINDS = {"album": "Album", "ep": "EP", "single": "Single", "concert": "Concert", "clip": "Nouveau clip", "distinction": "Distinction",
         "autre": "Actualité"}


def collect_releases(limit: int = 150) -> str:
    """Nouvelles sorties Deezer des artistes confirmés, ceux du Top en premier."""
    artists = db.all(f"""SELECT a.id, a.deezer_id FROM artists a WHERE a.status = 'active' AND a.deezer_id IS NOT NULL
                         ORDER BY EXISTS (SELECT 1 FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                                          WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 14) DESC,
                                  COALESCE(a.fans, 0) DESC LIMIT {int(limit)}""")
    since = (clock.today() - timedelta(days=21)).isoformat()
    http, added = HttpClient(15), 0
    for a in artists:
        if budget.over():
            break
        r = http.request("GET", f"https://api.deezer.com/artist/{int(a['deezer_id'])}/albums?limit=10")
        try:
            items = json.loads(r["body"]).get("data") or [] if r["status"] == 200 else []
        except ValueError:
            items = []
        for al in items:
            if str(al.get("release_date") or "") < since:
                continue
            kind = {"album": "album", "ep": "ep", "single": "single"}.get(al.get("record_type"), "single")
            n = db.run("""INSERT INTO artist_events (artist_id, kind, title, event_date, image_url, source_name, source_url, origin, external_id)
                          VALUES (?, ?, ?, ?, ?, 'Deezer', ?, 'deezer', ?) ON CONFLICT (external_id) DO NOTHING""",
                       [a["id"], kind, str(al["title"])[:200], al["release_date"], al.get("cover_xl") or al.get("cover_big"),
                        al.get("link"), f"dz{al['id']}"])
            added += 1 if n else 0
    return f"{added} nouvelles sorties détectées sur Deezer"


GENERIC = re.compile(r"\b(official|officiel(le)?|clip|video|vidéo|title|titre|lyrics?|paroles|audio|visuali[sz]er|vostfr|hd|4k)\b", re.I)


def clean_title(title: str, artist: str = "") -> str:
    """« En Tas - Official title » → « En Tas » ; vide si le titre ne contient que des mots génériques."""
    t = str(title)
    if artist and t.lower().startswith(artist.lower()):
        t = t[len(artist):].lstrip(" -–:|") or t  # « Blaqbonez- Ikebe 3000 » → « Ikebe 3000 »
    t = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", t)
    t = re.sub(r"\s*[-–|]\s*(official|officiel|clip|video|vidéo|lyrics?|audio).*$", "", t, flags=re.I).strip(" -–|")
    return "" if not GENERIC.sub("", t).strip(" -–|.") else t


def _views(e: dict) -> int:
    m = re.match(r"([\d ]+) vues", str(e.get("summary") or ""))
    return int(m.group(1).replace(" ", "")) if m else 0


def collect_youtube() -> str:
    """Nouveaux clips officiels (chaînes YouTube des artistes, déjà relues chaque nuit) des 21 derniers jours, avec leurs vues."""
    since = (clock.today() - timedelta(days=21)).isoformat()
    rows = db.all("""SELECT p.external_id, p.url, p.published_at, p.kind, t.title, t.artist_id, a.name AS artist_name,
                            (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id ORDER BY s.captured_on DESC LIMIT 1) AS views
                     FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id JOIN artists a ON a.id = t.artist_id
                     WHERE p.platform = 'youtube' AND p.kind IN ('clip', 'live') AND a.status = 'active'
                       AND a.youtube_channel_id IS NOT NULL AND p.published_at >= ?""", [since])
    added = 0
    for r in rows:
        title = clean_title(r["title"], r["artist_name"])
        if not title:
            continue  # titre générique (« Clip officiel ») : pas assez d'information pour une actualité
        r["title"] = title
        views = f"{int(r['views']):,} vues sur YouTube".replace(",", " ") if r["views"] else None
        n = db.run("""INSERT INTO artist_events (artist_id, kind, title, event_date, summary, image_url, source_name, source_url, origin, external_id)
                      VALUES (?, 'clip', ?, ?, ?, ?, 'YouTube', ?, 'youtube', ?)
                      ON CONFLICT (external_id) DO UPDATE SET summary = EXCLUDED.summary""",
                   [r["artist_id"], r["title"][:200], str(r["published_at"])[:10], views,
                    f"https://i.ytimg.com/vi/{r['external_id']}/hqdefault.jpg", r["url"], f"yt{r['external_id']}"])
        added += 1 if n else 0
    return f"{len(rows)} clips YouTube récents à l'affiche"


def latest(limit: int = 6, artist_id: int | None = None, days: int = 21, kind: str | None = None) -> list:
    """À venir (30 jours) puis récentes (21 jours) ; les albums et EP avant les singles."""
    today = clock.today()
    flt, params = ("AND e.artist_id = ?", [artist_id]) if artist_id else ("", [])
    if kind in KINDS:
        flt, params = flt + " AND e.kind = ?", [*params, kind]
    rows = db.all(f"""SELECT e.*, a.name AS artist_name, a.slug AS artist_slug, COALESCE(e.image_url, a.image_url) AS picture
                      FROM artist_events e JOIN artists a ON a.id = e.artist_id
                      WHERE e.status = 'published' AND a.status = 'active'
                        AND e.event_date BETWEEN ? AND ? {flt}
                      -- À venir d'abord, puis les clips YouTube (la plateforme la plus regardée), puis albums et EP, plus récents en tête
                      ORDER BY e.event_date > ? DESC, e.origin = 'youtube' DESC, e.kind IN ('album', 'ep', 'concert', 'distinction') DESC,
                               e.event_date DESC
                      LIMIT {int(limit) * 8}""",
                   [(today - timedelta(days=days if not artist_id else 365)).isoformat(), (today + timedelta(days=60)).isoformat(), *params,
                    today.isoformat()])
    for r in rows:
        d = r["event_date"] if isinstance(r["event_date"], date) else date.fromisoformat(str(r["event_date"])[:10])
        r["upcoming"] = d > today
    # À venir d'abord, puis les clips YouTube les plus vus (la plateforme la plus regardée), puis albums, EP et le reste
    rows.sort(key=lambda e: (not e["upcoming"], e["origin"] != "youtube", -_views(e), e["kind"] not in ("album", "ep", "concert", "distinction")))
    rows = [e for e in rows if not (e["origin"] == "youtube" and _views(e) < 1000)][:limit]
    for r in rows:
        r["kind_label"] = KINDS.get(r["kind"], "Actualité")
    return rows
