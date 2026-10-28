"""Données Spotify par Apify (validé par le fondateur le 28/10/2026), dans l'offre gratuite d'Apify (5 $ par mois).

- auditeurs() : auditeurs mensuels, abonnés, rang mondial et villes d'écoute des artistes qui BUZZENT cette semaine
  (Top 20 publiés, plus fortes hausses, liste « buzz » des clips) : pas de relevé de masse, seulement ceux qui peuvent
  nous rapporter des vues. Outil omkar-cloud : 2 500 artistes offerts par mois.
- playlists() : écoutes cumulées de chaque titre des playlists suivies (0,01 $ la playlist) ; d'une semaine à l'autre,
  la différence donne les écoutes mondiales de la semaine. Données gardées pour l'affichage et le contrôle anti-fraude :
  elles n'entrent pas dans le score officiel sans nouvelle version publique de la formule.
Plafond dur : PLAFOND_MOIS dollars par mois (compteur api_quota « cout-apify », par mois).
"""
import json
from datetime import date, datetime, timezone

import requests

from core import db, env
from core.services.platforms import PlatformException, log_write

API = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items"
ACTEUR_AUDITEURS = "omkar-cloud~spotify-monthly-listeners-scraper"
ACTEUR_PLAYLISTS = "s-r~free-spotify-playlist-intelligence"
PLAFOND_MOIS = 4.50
PRIX_PLAYLIST = 0.01
PRIX_ARTISTE = 0.002          # au-delà des 2 500 offerts ; compté par prudence
MAX_ARTISTES = 150            # par semaine : ~600 par mois, loin des 2 500 offerts
# Playlists éditoriales suivies (Spotify ne publie de Top 50 par pays que pour le Nigeria dans notre zone)
PLAYLISTS = {"37i9dQZEVXbKY7jLzlJ11V": "Top 50 - Nigeria"}


def tables() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS spotify_artistes (id SERIAL PRIMARY KEY, artist_id INTEGER NOT NULL, releve_le DATE NOT NULL,
              spotify_id VARCHAR(30) NULL, auditeurs BIGINT NULL, abonnes BIGINT NULL, rang INTEGER NULL, villes TEXT NULL,
              UNIQUE (artist_id, releve_le))""")
    db.run("""CREATE TABLE IF NOT EXISTS spotify_titres (id SERIAL PRIMARY KEY, spotify_id VARCHAR(30) NOT NULL, releve_le DATE NOT NULL,
              titre VARCHAR(300) NOT NULL, artistes VARCHAR(300) NOT NULL, ecoutes BIGINT NULL, playlist VARCHAR(30) NOT NULL,
              position INTEGER NULL, UNIQUE (spotify_id, releve_le, playlist))""")


def _mois() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-01")   # api_quota.day est une date : le 1er du mois


def depense() -> float:
    return int(db.value("SELECT units_used FROM api_quota WHERE api = 'cout-apify' AND day = ?", [_mois()]) or 0) / 1e6


def _compte(dollars: float) -> None:
    db.run("""INSERT INTO api_quota (api, day, units_used) VALUES ('cout-apify', ?, ?)
              ON CONFLICT (api, day) DO UPDATE SET units_used = api_quota.units_used + EXCLUDED.units_used""",
           [_mois(), int(dollars * 1e6)])


def _lance(acteur: str, entree: dict, cout: float) -> list:
    jeton = env.get("APIFY_TOKEN", "")
    if not jeton:
        raise PlatformException("APIFY_TOKEN absent")
    if depense() + cout > PLAFOND_MOIS:
        raise PlatformException(f"Apify : plafond du mois atteint ({depense():.2f} $ / {PLAFOND_MOIS} $)")
    r = requests.post(API.format(acteur), params={"token": jeton, "timeout": 290}, json=entree, timeout=320)
    if r.status_code >= 300:
        raise PlatformException(f"Apify {acteur} : HTTP {r.status_code} {r.text[:200]}")
    _compte(cout)
    return r.json()


def selection(limite: int = MAX_ARTISTES) -> list:
    """Les artistes qui buzzent : Top 20 des derniers classements publiés, plus fortes hausses de la semaine, liste buzz."""
    from core.services.social.clips import BUZZ
    ids = [r["artist_id"] for r in db.all(
        """SELECT DISTINCT ON (a.id) a.id AS artist_id, e.position FROM chart_entries e
           JOIN chart_runs r ON r.id = e.chart_run_id AND r.status = 'published' AND r.period_type = 'week'
           JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = COALESCE(e.artist_id, t.artist_id)
           WHERE r.period_start >= CURRENT_DATE - 14 AND e.position <= 20 ORDER BY a.id, e.position""")]
    ids += [r["artist_id"] for r in db.all(
        """SELECT t.artist_id, MAX(w.score) AS s FROM weekly_scores w JOIN tracks t ON t.id = w.track_id
           JOIN artists a ON a.id = t.artist_id AND a.status = 'active'
           WHERE w.week_start >= CURRENT_DATE - 14 GROUP BY t.artist_id ORDER BY s DESC LIMIT 60""")]
    ids += [r["id"] for r in db.all("SELECT id FROM artists WHERE lower(name) = ANY(?)", [[b.lower() for b in BUZZ]])]
    return list(dict.fromkeys(int(i) for i in ids))[:limite]


def auditeurs(limite: int = MAX_ARTISTES) -> list:
    tables()
    ids = selection(limite)
    deja = {int(r["artist_id"]) for r in db.all("SELECT artist_id FROM spotify_artistes WHERE releve_le > CURRENT_DATE - 6")}
    arts = [a for a in db.all("SELECT id, name, spotify_id FROM artists WHERE id = ANY(?)", [[i for i in ids if i not in deja]])]
    if not arts:
        return ["Spotify : rien à relever (déjà fait cette semaine)"]
    entree = [f"https://open.spotify.com/artist/{a['spotify_id']}" if a.get("spotify_id") else a["name"] for a in arts]
    lignes, trouves = [], 0
    for i in range(0, len(arts), 50):
        lot = arts[i:i + 50]
        try:
            res = _lance(ACTEUR_AUDITEURS, {"artists": entree[i:i + 50], "scrapeDetails": False}, PRIX_ARTISTE * len(lot))
        except PlatformException as exc:
            lignes.append(str(exc))
            break
        par_id = {x.get("id"): x for x in res if x.get("id")}
        par_nom = {str(x.get("name") or "").lower(): x for x in res}
        for a in lot:
            x = par_id.get(a.get("spotify_id")) if a.get("spotify_id") else par_nom.get(a["name"].lower())
            if not x or x.get("monthly_listeners") is None:
                continue   # nom trouvé chez un autre artiste ou absent de Spotify : rien plutôt qu'un faux chiffre
            villes = [{"ville": c.get("city"), "pays": c.get("country"), "auditeurs": c.get("listeners")} for c in x.get("top_cities") or []]
            db.run("""INSERT INTO spotify_artistes (artist_id, releve_le, spotify_id, auditeurs, abonnes, rang, villes)
                      VALUES (?, CURRENT_DATE, ?, ?, ?, ?, ?) ON CONFLICT (artist_id, releve_le) DO NOTHING""",
                   [a["id"], x.get("id"), x.get("monthly_listeners"), x.get("followers"), x.get("world_rank"),
                    json.dumps(villes, ensure_ascii=False)])
            if not a.get("spotify_id") and x.get("id"):
                db.run("UPDATE artists SET spotify_id = ? WHERE id = ? AND spotify_id IS NULL", [x["id"], a["id"]])
            trouves += 1
    lignes.insert(0, f"Spotify : {trouves} artiste(s) relevé(s) sur {len(arts)} qui buzzent · Apify {depense():.2f} $ ce mois")
    return lignes


def playlists() -> list:
    tables()
    try:
        res = _lance(ACTEUR_PLAYLISTS, {"playlists": list(PLAYLISTS), "trackDiffs": False}, PRIX_PLAYLIST * len(PLAYLISTS))
    except PlatformException as exc:
        return [str(exc)]
    n = 0
    for p in res:
        for t in p.get("tracks") or []:
            if not t.get("id"):
                continue
            db.run("""INSERT INTO spotify_titres (spotify_id, releve_le, titre, artistes, ecoutes, playlist, position)
                      VALUES (?, CURRENT_DATE, ?, ?, ?, ?, ?) ON CONFLICT (spotify_id, releve_le, playlist) DO NOTHING""",
                   [t["id"], str(t.get("name") or "")[:300], ", ".join(a.get("name", "") for a in t.get("artists") or [])[:300],
                    t.get("playcount"), p.get("id"), (t.get("position") or 0) + 1])
            n += 1
    return [f"Spotify playlists : {n} titre(s) relevé(s) dans {len(res)} playlist(s)"]


# ---------------------------------------------------------------- lecture (pages artistes, posts)

def fiche(artist_id: int) -> dict | None:
    """Dernier relevé de l'artiste et évolution depuis le relevé précédent ; None si jamais relevé."""
    try:
        rows = db.all("SELECT * FROM spotify_artistes WHERE artist_id = ? ORDER BY releve_le DESC LIMIT 2", [artist_id])
    except Exception:  # noqa: BLE001 — table pas encore créée
        return None
    if not rows:
        return None
    a = rows[0]
    prec = rows[1] if len(rows) > 1 else None
    return {"auditeurs": a["auditeurs"], "abonnes": a["abonnes"], "rang": a["rang"], "releve_le": str(a["releve_le"])[:10],
            "villes": json.loads(a["villes"] or "[]")[:5], "spotify_id": a["spotify_id"],
            "evolution": (int(a["auditeurs"]) - int(prec["auditeurs"])) if prec and a["auditeurs"] and prec["auditeurs"] else None}


def ecoutes_semaine(spotify_id: str) -> int | None:
    """Écoutes mondiales de la semaine d'un titre (différence entre deux relevés à 6-8 jours d'écart)."""
    rows = db.all("SELECT releve_le, ecoutes FROM spotify_titres WHERE spotify_id = ? AND ecoutes IS NOT NULL "
                  "ORDER BY releve_le DESC LIMIT 10", [spotify_id])
    if len(rows) < 2:
        return None
    dernier = rows[0]
    for r in rows[1:]:
        ecart = (date.fromisoformat(str(dernier["releve_le"])[:10]) - date.fromisoformat(str(r["releve_le"])[:10])).days
        if 6 <= ecart <= 8:
            return int(dernier["ecoutes"]) - int(r["ecoutes"])
    return None
