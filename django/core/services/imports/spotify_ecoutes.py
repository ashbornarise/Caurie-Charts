"""Écoutes Spotify de chaque titre de nos artistes (07/11/2026, demande du fondateur : « obtenir les données stream pour
chaque titre que nous suivons, les albums etc. des artistes », et « ces nombres d'écoute doivent être pris dans nos
données de classement »).

Spotify ne publie pas d'écoutes par pays en Afrique de l'Ouest : on relève le compteur MONDIAL de chaque titre (comme
les vues YouTube), et la différence d'une semaine à l'autre donne les écoutes de la semaine.

Deux sources :
  1. kworb()  : kworb.net, gratuit, mis à jour chaque jour. Tous les titres de l'artiste (albums, singles, featurings)
                avec le total d'écoutes. Couvre surtout les artistes déjà bien écoutés (22 sur 40 à l'essai).
  2. apify()  : pour les artistes absents de Kworb (les trois quarts), l'outil topapi/spotify-scraper en « une ligne
                par titre » sur la discographie complète (0,074 $ les 1 000 titres, essai du 07/11 : 207 titres pour
                2 artistes, ~0,015 $), dans le plafond Apify partagé (spotify_apify.PLAFOND_MOIS).
Chaque compteur est gardé dans snapshots (plateforme « spotify », un relevé par jour) : historique complet.
"""
import html
import re
import time
from datetime import date

import requests

from core import db
from core.services.imports import normalizer as N
from core.services.imports import chart_importer

KWORB = "https://kworb.net/spotify/artist/{}_songs.html"
LIGNE = re.compile(r'<tr><td class="text"><div>(\*\s*)?<a href="https://open\.spotify\.com/track/([A-Za-z0-9]{22})"[^>]*>(.*?)</a></div></td>'
                   r'<td>([\d,]+)</td><td>([\d,\-]*)</td></tr>')
MAJ = re.compile(r"Last updated:\s*(\d{4})/(\d{2})/(\d{2})")
ACTEUR = "topapi~spotify-scraper"
PRIX_TITRE = 0.000074
PRIX_LANCEMENT = 0.003
PAR_LOT = 8                   # artistes par passage (réponse en moins de 5 minutes)
MAX_SORTIES = 200             # sorties par artiste (les plus récentes d'abord)


def colonnes() -> None:
    db.run("ALTER TABLE artists ADD COLUMN IF NOT EXISTS ecoutes_spotify_le DATE NULL")
    db.run("ALTER TABLE artists ADD COLUMN IF NOT EXISTS kworb VARCHAR(10) NULL")   # 'oui' / 'non' (page absente)


def _entier(s) -> int:
    return int(re.sub(r"[^\d]", "", str(s or "")) or 0)


def lire_kworb(spotify_id: str, session=None) -> tuple[list, str | None]:
    """[(id du titre, titre, écoutes totales, écoutes du jour, featuring ?)], date de mise à jour ; ([], None) si absent."""
    r = (session or requests).get(KWORB.format(spotify_id), headers={"User-Agent": "Mozilla/5.0 (CauriCharts)"}, timeout=25)
    if r.status_code == 404:
        return [], None
    r.raise_for_status()
    texte = r.content.decode("utf-8", "replace")   # Kworb ne déclare pas son encodage : « LÃ©gendes » sinon
    m = MAJ.search(texte)
    jour = f"{m[1]}-{m[2]}-{m[3]}" if m else date.today().isoformat()
    lignes = [(tid, html.unescape(re.sub(r"<[^>]+>", "", titre)).strip(), _entier(total), _entier(journ), bool(etoile))
              for etoile, tid, titre, total, journ in LIGNE.findall(texte)]
    return lignes, jour


def _titre_existant(titre: str) -> int | None:
    """Featuring : le titre appartient à un autre artiste ; on ne le relie que s'il existe déjà chez nous, sans ambiguïté."""
    lignes = db.all("SELECT id FROM tracks WHERE match_key LIKE ? LIMIT 2", ["%|" + N.title(titre)])
    return int(lignes[0]["id"]) if len(lignes) == 1 else None


def enregistrer(artiste: dict, lignes: list, jour: str) -> tuple[int, int]:
    """Relie chaque titre Spotify à un titre de la base (créé s'il manque) et note son compteur du jour."""
    lignes = [l for l in lignes if l[1] and l[2] > 0]
    if not lignes:
        return 0, 0
    cid = int(artiste["submission_country_id"])

    def connus() -> dict:
        return {r["external_id"]: int(r["id"]) for r in db.all(
            "SELECT id, external_id FROM track_platform_ids WHERE platform = 'spotify' AND external_id = ANY(?)", [[l[0] for l in lignes]])}

    ids = connus()
    # Titres pas encore reliés : créés ou retrouvés une seule fois ; les featurings (titre d'un autre artiste) seulement
    # s'ils existent déjà chez nous, recherchés le lundi pour ne pas refaire chaque jour la même recherche
    avant = int(db.value("SELECT COUNT(*) FROM tracks WHERE artist_id = ?", [artiste["id"]]) or 0)
    nouveaux = 0
    for tid, titre, _total, _jour, featuring in lignes:
        if tid in ids:
            continue
        if featuring:
            if date.today().isoweekday() != 1 and artiste.get("deja"):
                continue
            track_id = _titre_existant(titre)
            if track_id:
                db.run("""INSERT INTO track_platform_ids (track_id, platform, external_id, kind, url, match_status)
                          VALUES (?, 'spotify', ?, 'main', ?, 'auto') ON CONFLICT DO NOTHING""",
                       [track_id, tid, f"https://open.spotify.com/track/{tid}"])
                nouveaux += 1
        else:
            chart_importer.upsert_track({"title": titre, "artist": artiste["name"], "external_id": tid,
                                         "url": f"https://open.spotify.com/track/{tid}"}, "spotify", cid)
            nouveaux += 1
    if nouveaux:
        ids = connus()
    crees = int(db.value("SELECT COUNT(*) FROM tracks WHERE artist_id = ?", [artiste["id"]]) or 0) - avant
    # Compteurs du jour : une seule écriture pour tout l'artiste
    paires = [(ids[l[0]], l[2]) for l in lignes if l[0] in ids]
    if paires:
        db.run("""INSERT INTO snapshots (track_platform_id, captured_on, plays, source)
                  SELECT u.tpi, CAST(? AS DATE), u.plays, 'api' FROM unnest(CAST(? AS INTEGER[]), CAST(? AS BIGINT[])) AS u(tpi, plays)
                  ON CONFLICT (track_platform_id, captured_on) DO UPDATE SET plays = EXCLUDED.plays""",
               [jour, [p[0] for p in paires], [p[1] for p in paires]])
    return len(paires), crees


def a_relever(limite: int, source: str) -> list:
    """Artistes actifs avec un identifiant Spotify, les moins récemment relevés d'abord (ceux des classements en tête)."""
    filtre = "AND (a.kworb IS NULL OR a.kworb = 'oui')" if source == "kworb" else "AND a.kworb = 'non'"
    return db.all(f"""SELECT a.id, a.name, a.spotify_id, a.submission_country_id, a.ecoutes_spotify_le IS NOT NULL AS deja FROM artists a
                      WHERE a.status = 'active' AND a.spotify_id IS NOT NULL AND a.submission_country_id IS NOT NULL {filtre}
                        AND (a.ecoutes_spotify_le IS NULL OR a.ecoutes_spotify_le < CURRENT_DATE)
                      ORDER BY a.ecoutes_spotify_le NULLS FIRST,
                               EXISTS (SELECT 1 FROM tracks t JOIN weekly_scores w ON w.track_id = t.id
                                       WHERE t.artist_id = a.id AND w.week_start >= CURRENT_DATE - 14) DESC, a.id
                      LIMIT {int(limite)}""")


def kworb(limite: int = 800, pause: float = 0.8) -> list:
    """Chaque jour : tous les artistes présents sur Kworb (gratuit). Un artiste absent est noté pour Apify."""
    colonnes()
    lus = absents = titres = nouveaux = 0
    s = requests.Session()
    for a in a_relever(limite, "kworb"):
        try:
            lignes, jour = lire_kworb(a["spotify_id"], s)
        except requests.RequestException:
            continue
        if jour is None:
            db.run("UPDATE artists SET kworb = 'non' WHERE id = ?", [a["id"]])
            absents += 1
        else:
            r, c = enregistrer(a, lignes, jour)
            titres, nouveaux = titres + r, nouveaux + c
            db.run("UPDATE artists SET kworb = 'oui', ecoutes_spotify_le = CURRENT_DATE WHERE id = ?", [a["id"]])
            lus += 1
        time.sleep(pause)
    return [f"Écoutes Spotify (Kworb) : {lus} artistes, {titres} titres relevés, {nouveaux} titres ajoutés ; "
            f"{absents} artiste(s) absents de Kworb (relevés par Apify)"]


def apify(limite: int = 600, jours: int = 6) -> list:
    """Artistes absents de Kworb : discographie complète par Apify, au plus une fois tous les JOURS jours, sous le plafond."""
    from core.services import spotify_apify as SA
    from core.services.platforms import PlatformException
    colonnes()
    lot = db.all(f"""SELECT a.id, a.name, a.spotify_id, a.submission_country_id, a.ecoutes_spotify_le IS NOT NULL AS deja FROM artists a
                     WHERE a.status = 'active' AND a.spotify_id IS NOT NULL AND a.submission_country_id IS NOT NULL AND a.kworb = 'non'
                       -- plafond Apify (07/11/2026) : chaque semaine les artistes en course dans nos classements (un score
                       -- ces 14 derniers jours), chaque mois les autres
                       AND (a.ecoutes_spotify_le IS NULL OR a.ecoutes_spotify_le <= CURRENT_DATE - CASE WHEN EXISTS (
                              SELECT 1 FROM tracks t JOIN weekly_scores w ON w.track_id = t.id
                              WHERE t.artist_id = a.id AND w.week_start >= CURRENT_DATE - 14 AND w.score > 0) THEN {int(jours)} ELSE 28 END)
                     ORDER BY a.ecoutes_spotify_le NULLS FIRST,
                              EXISTS (SELECT 1 FROM tracks t JOIN weekly_scores w ON w.track_id = t.id
                                      WHERE t.artist_id = a.id AND w.week_start >= CURRENT_DATE - 14 AND w.score > 0) DESC, a.id
                     LIMIT {int(limite)}""")
    lus = titres = nouveaux = 0
    for i in range(0, len(lot), PAR_LOT):
        paquet = lot[i:i + PAR_LOT]
        estime = PRIX_LANCEMENT + PRIX_TITRE * 60 * len(paquet)   # réservé avant le passage ; la facture suit le nombre de titres
        try:
            res = SA._lance(ACTEUR, {"urls": [f"https://open.spotify.com/artist/{a['spotify_id']}" for a in paquet],
                                     "trackRows": True, "maxAlbumsPerArtist": MAX_SORTIES, "includeSingles": True,
                                     "maxResults": 0, "compact": True, "scrapePreviewUrls": False}, estime)
        except PlatformException as exc:
            return [f"Écoutes Spotify (Apify) : {lus} artistes, {titres} titres · arrêt : {exc}"]
        SA._compte(max(0.0, PRIX_LANCEMENT + PRIX_TITRE * len(res or []) - estime))
        par_artiste: dict = {}
        for x in res or []:
            source = str(x.get("sourceUri") or x.get("input") or "").split(":")[-1].split("/")[-1][:22]
            par_artiste.setdefault(source, []).append(x)
        for a in paquet:
            lignes = []
            for x in par_artiste.get(a["spotify_id"], []):
                tid = str(x.get("id") or "")[:22]
                featuring = N.artist_key(str(x.get("artistName") or "")) != N.artist_key(a["name"])
                if len(tid) == 22:
                    lignes.append((tid, str(x.get("name") or "").strip(), _entier(x.get("playCount")), 0, featuring))
            r, c = enregistrer(a, lignes, date.today().isoformat())
            db.run("UPDATE artists SET ecoutes_spotify_le = CURRENT_DATE WHERE id = ?", [a["id"]])
            lus, titres, nouveaux = lus + 1, titres + r, nouveaux + c
    return [f"Écoutes Spotify (Apify) : {lus} artistes, {titres} titres relevés, {nouveaux} titres ajoutés · {SA.depense():.2f} $ ce mois"]
