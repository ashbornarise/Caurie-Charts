"""Revue des titres signalés par Gemini avec la recherche Google, avant la publication du mardi (27/10/2026).

Demande du fondateur : pour chaque pays, Google cherche d'abord les titres qui buzzent cette semaine-là, puis Gemini
juge chaque titre signalé (pic soudain, rapport YouTube anormal) au vu de ce buzz et de ses propres recherches :
- « valider » : preuve d'un vrai buzz (sortie récente, tendance, presse, réseaux, autres classements) ;
- « exclure » : seulement devant une preuve claire de gonflement (achat de vues, re-upload, compilation, faux titre) ;
- sinon le titre reste en attente et le fondateur tranche.
Seules les décisions de certitude « haute » sont appliquées, avec leur raison (publique pour une exclusion).
"""
import json
from datetime import date, timedelta

from core import db
from core.services.platforms import HttpClient, log_write
from core.services.social.comptes import _gemini

DRAPEAUX = {"spike": "hausse soudaine des vues d'une semaine à l'autre",
            "youtube_ratio": "vues YouTube très au-dessus des écoutes audio (Spotify, Deezer, Audiomack…)"}


def en_attente(code: str, week_start: str) -> list:
    return db.all("""SELECT w.track_id, a.name AS artiste, t.title AS titre, w.score, w.flags, w.breakdown
                     FROM weekly_scores w JOIN countries c ON c.id = w.country_id JOIN tracks t ON t.id = w.track_id
                     JOIN artists a ON a.id = t.artist_id
                     WHERE c.code = ? AND w.week_start = ? AND w.review_status = 'pending' AND w.score > 0
                     ORDER BY w.score DESC""", [code, week_start])


def buzz(pays: str, debut: date, http: HttpClient) -> str:
    """Étape 1 : les titres qui buzzent dans le pays cette semaine (recherche Google)."""
    fin = debut + timedelta(days=6)
    texte, meta = _gemini(
        f"Quels sont les titres de musique qui buzzent au {pays} pendant la semaine du {debut:%d/%m/%Y} au {fin:%d/%m/%Y} ? "
        "Cherche sur Google : nouvelles sorties, tendances TikTok et YouTube, classements locaux (Apple Music, Boomplay, "
        "Audiomack, Shazam), presse musicale du pays. Donne une liste courte : artiste – titre – pourquoi ça buzze.", http)
    return texte.strip()[:4000] if meta.get("webSearchQueries") else ""


def juger(pays: str, debut: date, titres: list, contexte: str, http: HttpClient) -> list:
    """Étape 2 : une décision par titre signalé, au vu du buzz et de recherches propres à chaque titre."""
    lignes = []
    for t in titres:
        drapeaux = ", ".join(DRAPEAUX.get(f, f) for f in json.loads(t["flags"] or "[]"))
        lignes.append(f'- id {t["track_id"]} : {t["artiste"]} – « {t["titre"]} » (signalé : {drapeaux} ; détail {t["breakdown"]})')
    texte, meta = _gemini(
        f"Tu es le contrôleur anti-fraude d'un classement musical du {pays}, semaine du {debut:%d/%m/%Y}.\n"
        f"Ce que la recherche Google a trouvé comme titres qui buzzent cette semaine :\n{contexte or '(rien trouvé)'}\n\n"
        "Titres signalés par notre système :\n" + "\n".join(lignes) + "\n\n"
        "Pour chaque titre, cherche sur Google s'il y a un vrai buzz (sortie récente, clip, tendance, presse, polémique, "
        "autres classements). Règles : « valider » si le buzz est réel et prouvé ; « exclure » seulement s'il y a une preuve "
        "claire de gonflement (achat de vues, re-upload, compilation, live ou vidéo qui n'est pas le titre) ; sinon "
        "« attente ». Termine par une ligne JSON : "
        '{"decisions": [{"id": 0, "decision": "valider|exclure|attente", "certitude": "haute|moyenne|faible", '
        '"raison": "une phrase en français, factuelle"}]}', http)
    if not meta.get("webSearchQueries"):
        return []
    from core.services import ai
    d = ai.extract_json(texte[texte.rfind('{"decisions"'):] if '{"decisions"' in texte else texte) or {}
    return d.get("decisions") or []


def revoir(code: str, week_start: str, user_id: int = 1, appliquer: bool = True, http: HttpClient | None = None) -> dict:
    """Revue d'un pays : {"valides": [...], "exclus": [...], "attente": [...]} (titres « artiste – titre : raison »)."""
    from core.services.chart_service import ChartService
    http = http or HttpClient(120)
    titres = en_attente(code, week_start)
    bilan = {"valides": [], "exclus": [], "attente": []}
    if not titres:
        return bilan
    pays = db.value("SELECT name_fr FROM countries WHERE code = ?", [code]) or code
    debut = date.fromisoformat(week_start)
    contexte = buzz(pays, debut, http)
    par_id = {int(t["track_id"]): t for t in titres}
    decisions = {}
    for i in range(0, len(titres), 10):   # lots de 10 : des recherches précises pour chaque titre
        for x in juger(pays, debut, titres[i:i + 10], contexte, http):
            try:
                decisions[int(x.get("id"))] = x
            except (TypeError, ValueError):
                continue
    service = ChartService()
    for tid, t in par_id.items():
        x = decisions.get(tid) or {}
        nom = f"{t['artiste']} – {t['titre']}"
        raison = str(x.get("raison") or "").strip()[:400]
        choix = {"valider": "validated", "exclure": "excluded"}.get(x.get("decision"))
        if not choix or x.get("certitude") != "haute" or not raison:
            bilan["attente"].append(f"{nom} : {raison or 'pas de preuve trouvée'}")
            continue
        if appliquer:
            service.decide(tid, week_start, choix, f"Revue IA (Gemini + Google) : {raison}", user_id)
        bilan["valides" if choix == "validated" else "exclus"].append(f"{nom} : {raison}")
    log_write("revue_ia", "info", f"{code} {week_start} : {len(bilan['valides'])} validé(s), {len(bilan['exclus'])} exclu(s), "
                                  f"{len(bilan['attente'])} en attente")
    return bilan
