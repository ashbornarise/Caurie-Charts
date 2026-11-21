"""Date de sortie des titres qui n'en ont pas (formule v7, 21/11/2026).

Audit des tops S47 par les IA : la règle « un titre de plus d'un an quitte le Top » ne s'appliquait pas aux titres SANS
date (Calm Down de Rema, 2022 ; Magic in the Air, 2014 ; Forever (Remix) de Gyakie, 2021 étaient classés). Avant le calcul,
on cherche la date des titres candidats dans la recherche publique d'iTunes (gratuite, sans clé) : on ne retient que les
résultats du MÊME artiste principal et du MÊME titre (mêmes clés que l'importeur), et on garde la plus ancienne date
(la sortie d'origine, pas une réédition). Rien trouvé : le titre garde « sans date » (jamais de date devinée).
"""
import json
import time
from urllib.parse import urlencode

from core import db
from core.services.imports import normalizer as N
from core.services.platforms import HttpClient, PlatformException

URL = "https://itunes.apple.com/search?"


def _cle_artiste(nom: str) -> str:
    return N.track_key("x", nom).split("|")[0]


def date_itunes(titre: str, artiste: str, http: HttpClient | None = None) -> str | None:
    http = http or HttpClient(20)
    try:
        resp = http.request("GET", URL + urlencode({"term": f"{N.primary_artist(artiste)} {titre}", "entity": "song", "limit": 25}))
    except PlatformException:
        return None
    if resp["status"] != 200:
        return None
    try:
        resultats = json.loads(resp["body"]).get("results") or []
    except ValueError:
        return None
    cle, cle_art = N.track_key(titre, artiste), _cle_artiste(artiste)
    dates = []
    for r in resultats:
        nom = str(r.get("artistName") or "").replace(" & ", ", ")
        if _cle_artiste(nom) != cle_art:
            continue
        if N.track_key(str(r.get("trackName") or ""), nom) != cle:
            continue
        d = str(r.get("releaseDate") or "")[:10]
        if len(d) == 10:
            dates.append(d)
    return min(dates) if dates else None


def completer(track_ids: list, limite: int = 30, pause: float = 3.1) -> dict:
    """Cherche et enregistre la date des titres sans date (au plus `limite` recherches). Renvoie {track_id: date}."""
    if not track_ids:
        return {}
    rows = db.all(f"""SELECT t.id, t.title, a.name FROM tracks t JOIN artists a ON a.id = t.artist_id
                      WHERE t.release_date IS NULL AND t.id IN ({', '.join(['?'] * len(track_ids))})""", list(track_ids))
    http, trouvees = HttpClient(20), {}
    for r in rows[:limite]:
        d = date_itunes(r["title"], r["name"], http)
        if d:
            db.run("UPDATE tracks SET release_date = ? WHERE id = ? AND release_date IS NULL", [d, r["id"]])
            trouvees[int(r["id"])] = d
        time.sleep(pause)   # iTunes limite à ~20 requêtes par minute et par adresse : 30 titres = 1 min 30
    return trouvees
