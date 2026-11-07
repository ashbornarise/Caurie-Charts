"""Nouvelles sorties des artistes suivis, relevées sur Deezer (06/11/2026).

Constat : l'album « SHOGUN IN LAGOS » de Didi B, sorti le 6 novembre, n'existait pas chez nous ; les titres
n'arrivaient qu'avec un clip YouTube officiel ou une entrée dans un classement de plateforme, soit des jours plus tard.
Ici, chaque titre d'un album, EP ou single paru ces JOURS derniers est créé tout de suite (avec sa date de sortie et
son identifiant Deezer), pour que les relevés suivants (popularité Deezer, Apple, Boomplay, Shazam, clips) le trouvent
déjà en base. API publique de Deezer : gratuite, sans clé ni quota (50 requêtes par 5 secondes au plus)."""
import time
from datetime import date, timedelta

import requests

from core import db
from core.services.imports import chart_importer

JOURS = 14
API = "https://api.deezer.com"


def _get(chemin: str, params: dict | None = None) -> dict:
    for essai in range(3):
        try:
            r = requests.get(API + chemin, params=params or {}, timeout=20)
            d = r.json()
            if isinstance(d, dict) and (d.get("error") or {}).get("code") == 4:   # trop de requêtes : on patiente
                time.sleep(5)
                continue
            return d if isinstance(d, dict) else {}
        except (requests.RequestException, ValueError):
            time.sleep(2 * (essai + 1))
    return {}


def artistes(limite: int | None = None) -> list:
    """Artistes actifs avec un identifiant Deezer : ceux vus récemment dans un classement d'abord."""
    lim = f"LIMIT {int(limite)}" if limite else ""
    return db.all(f"""SELECT a.id, a.name, a.deezer_id, a.submission_country_id,
                             (SELECT MAX(o.observed_on) FROM tracks t JOIN chart_observations o ON o.track_id = t.id
                               WHERE t.artist_id = a.id) AS vu
                      FROM artists a WHERE a.status = 'active' AND a.deezer_id IS NOT NULL AND a.submission_country_id IS NOT NULL
                      ORDER BY vu DESC NULLS LAST, a.id {lim}""")


def releve(jours: int = JOURS, limite: int | None = None) -> list:
    depuis = (date.today() - timedelta(days=jours)).isoformat()
    vus, crees, sorties = 0, 0, []
    for a in artistes(limite):
        vus += 1
        albums = _get(f"/artist/{a['deezer_id']}/albums", {"limit": 6}).get("data") or []
        for al in albums:
            if str(al.get("release_date") or "") < depuis:
                continue
            titres = _get(f"/album/{al['id']}/tracks", {"limit": 50}).get("data") or []
            nouveaux = 0
            for t in titres:
                artiste = (t.get("artist") or {}).get("name") or a["name"]
                row = {"title": str(t.get("title") or "").strip(), "artist": artiste, "external_id": str(t.get("id") or ""),
                       "url": t.get("link"), "image": al.get("cover_xl") or al.get("cover_big"), "release_date": al.get("release_date")}
                if not row["title"]:
                    continue
                avant = db.value("SELECT 1 FROM track_platform_ids WHERE platform = 'deezer' AND external_id = ?", [row["external_id"]])
                chart_importer.upsert_track(row, "deezer", int(a["submission_country_id"]))
                if not avant:
                    nouveaux += 1
            if nouveaux:
                crees += nouveaux
                sorties.append(f"{a['name']} — « {al.get('title')} » ({al.get('record_type')}, {al.get('release_date')}) : {nouveaux} titre(s)")
        time.sleep(0.12)   # sous la limite de Deezer
    return [f"Sorties Deezer : {vus} artistes vérifiés, {crees} nouveaux titres"] + sorties[:40]


def catalogue(limite: int = 120) -> list:
    """Catalogue complet (07/11/2026, demande du fondateur : « suivre tous les sons de nos artistes ») : tous les albums,
    EP et singles de chaque artiste actif sur Deezer, pas seulement les sorties récentes. Chaque artiste est repassé au
    plus tous les 30 jours (colonne catalogue_le) ; les artistes jamais passés d'abord, les plus présents en tête."""
    db.run("ALTER TABLE artists ADD COLUMN IF NOT EXISTS catalogue_le TIMESTAMPTZ NULL")
    lot = db.all(f"""SELECT a.id, a.name, a.deezer_id, a.submission_country_id FROM artists a
                     WHERE a.status = 'active' AND a.deezer_id IS NOT NULL AND a.submission_country_id IS NOT NULL
                       AND (a.catalogue_le IS NULL OR a.catalogue_le < NOW() - INTERVAL '30 days')
                     ORDER BY a.catalogue_le NULLS FIRST, COALESCE(a.youtube_subscribers, 0) + COALESCE(a.fans, 0) DESC
                     LIMIT {int(limite)}""")
    artistes, crees = 0, 0
    for a in lot:
        albums, url = [], f"/artist/{a['deezer_id']}/albums"
        params = {"limit": 100}
        for _ in range(5):   # 500 sorties au plus par artiste
            d = _get(url, params)
            albums += d.get("data") or []
            if not d.get("next"):
                break
            params = {"limit": 100, "index": len(albums)}
        for al in albums:
            for t in _get(f"/album/{al['id']}/tracks", {"limit": 100}).get("data") or []:
                titre = str(t.get("title") or "").strip()
                if not titre:
                    continue
                ext = str(t.get("id") or "")
                if db.value("SELECT 1 FROM track_platform_ids WHERE platform = 'deezer' AND external_id = ?", [ext]):
                    continue
                chart_importer.upsert_track({"title": titre, "artist": (t.get("artist") or {}).get("name") or a["name"],
                                             "external_id": ext, "url": t.get("link"),
                                             "image": al.get("cover_xl") or al.get("cover_big"),
                                             "release_date": al.get("release_date")}, "deezer", int(a["submission_country_id"]))
                crees += 1
            time.sleep(0.1)
        db.run("UPDATE artists SET catalogue_le = NOW() WHERE id = ?", [a["id"]])
        artistes += 1
    return [f"Catalogue Deezer : {artistes} artiste(s) passés en entier, {crees} titre(s) ajouté(s)"]
