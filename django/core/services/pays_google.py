"""Pays des artistes vérifié par Google (Gemini avec recherche Google) : décision du fondateur du 02/11/2026,
« même nos anciens relevés partent chez Google, qui décidera ».

Par lots de 40 artistes vus dans les classements (les plus récents d'abord). Google n'est suivi que s'il est sûr
(certitude « haute ») :
  - pays d'Afrique de l'Ouest  → pays corrigé, artiste en attente validé ;
  - pays hors de la zone       → artiste « hors zone » (ne compte plus dans nos classements) ;
  - doute                      → réponse notée, rien ne change.
Chaque changement est inscrit dans pays_verifs avec l'ancienne valeur (retour arrière possible).
Coût : ~0,045 $ par lot (une recherche Google + jetons), dans le budget Gemini du jour (ia_budget).
"""
import json
import re

from core import db
from core.services.platforms import HttpClient, PlatformException
from core.services.social.comptes import _gemini

TAILLE = 40


def colonnes() -> None:
    db.run("ALTER TABLE artists ADD COLUMN IF NOT EXISTS pays_google VARCHAR(2) NULL")
    db.run("ALTER TABLE artists ADD COLUMN IF NOT EXISTS pays_google_le TIMESTAMPTZ NULL")
    db.run("""CREATE TABLE IF NOT EXISTS pays_verifs (id SERIAL PRIMARY KEY, artist_id INTEGER NOT NULL, nom VARCHAR(200),
              pays_google VARCHAR(2), certitude VARCHAR(10), ancien_pays VARCHAR(2), ancien_statut VARCHAR(20),
              nouveau_pays VARCHAR(2), nouveau_statut VARCHAR(20), cree_le TIMESTAMPTZ DEFAULT NOW())""")


def a_verifier(limite: int) -> list:
    """Artistes vus dans un classement ces 30 derniers jours et jamais vérifiés : actifs d'abord, les plus vus d'abord."""
    return db.all(f"""SELECT a.id, a.name, a.status, c.code AS pays,
                         (SELECT t.title FROM tracks t WHERE t.artist_id = a.id ORDER BY t.id LIMIT 1) AS titre,
                         (SELECT COUNT(*) FROM tracks t JOIN chart_observations o ON o.track_id = t.id
                           WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 7) AS vus
                      FROM artists a LEFT JOIN countries c ON c.id = a.submission_country_id
                      WHERE a.status IN ('active', 'pending') AND a.pays_google_le IS NULL
                        AND EXISTS (SELECT 1 FROM tracks t JOIN chart_observations o ON o.track_id = t.id
                                    WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 30)
                      ORDER BY a.status = 'active' DESC, vus DESC, a.id LIMIT {int(limite)}""")


def _demande(lot: list, http: HttpClient) -> dict:
    lignes = "\n".join(f"{i + 1}. {a['name']}" + (f" (titre : « {a['titre']} »)" if a.get("titre") else "") for i, a in enumerate(lot))
    # Question en langage naturel : avec « réponds seulement en JSON », Gemini saute la recherche Google
    prompt = ("Recherche sur Google la nationalité de chacun de ces artistes musicaux (chanteurs, rappeurs, DJ, groupes). "
              "Un titre connu est indiqué pour éviter les homonymes.\n" + lignes +
              "\n\nPour chacun, donne le pays d'origine de l'artiste (code ISO à 2 lettres) et ta certitude : « haute » seulement si "
              "des sources fiables le confirment, sinon « moyenne » ou « basse ». N'invente rien : en cas de doute, mets null. "
              "Termine ta réponse par un bloc JSON : [{\"n\": numéro, \"pays\": \"XX\" ou null, \"certitude\": \"haute|moyenne|basse\"}]")
    texte, _ = _gemini(prompt, http, "low", 1.0)
    blocs = re.findall(r"\[\s*\{.*?\}\s*\]", texte, re.S)
    try:
        liste = json.loads(blocs[-1]) if blocs else []
    except ValueError:
        liste = []
    return {int(x["n"]): x for x in liste if isinstance(x, dict) and str(x.get("n", "")).isdigit()}


def verifier(lots: int = 4, taille: int = TAILLE, appliquer: bool = True, http: HttpClient | None = None) -> list:
    from core.services import ia_budget
    colonnes()
    http = http or HttpClient(90)
    ouest = {c["code"]: c["id"] for c in db.all("SELECT id, code FROM countries")}   # les 16 pays de la zone
    lignes, changes = [], 0
    for _ in range(lots):
        if not ia_budget.peut("gemini", 0.5):   # tâche secondaire : la moitié du budget du jour au plus
            lignes.append("budget Gemini du jour atteint : la suite demain")
            break
        lot = a_verifier(taille)
        if not lot:
            lignes.append("tous les artistes vus dans les classements sont vérifiés")
            break
        try:
            reponses = _demande(lot, http)
        except PlatformException as exc:
            lignes.append(str(exc))
            break
        for i, a in enumerate(lot):
            r = reponses.get(i + 1) or {}
            pays = str(r.get("pays") or "").upper()[:2] or None
            certitude = str(r.get("certitude") or "").lower()
            nouveau_pays, nouveau_statut = a["pays"], a["status"]
            if pays and re.fullmatch(r"[A-Z]{2}", pays) and certitude == "haute":
                if pays in ouest:
                    nouveau_pays = pays
                    nouveau_statut = "active" if a["status"] == "pending" else a["status"]
                else:
                    nouveau_statut = "out_of_scope"
            change = (nouveau_pays, nouveau_statut) != (a["pays"], a["status"])
            if appliquer:
                db.run("UPDATE artists SET pays_google = ?, pays_google_le = NOW() WHERE id = ?", [pays, a["id"]])
                if change:
                    db.run("UPDATE artists SET status = ?, submission_country_id = COALESCE(?, submission_country_id), "
                           "base_country = COALESCE(?, base_country) WHERE id = ?",
                           [nouveau_statut, ouest.get(nouveau_pays) if nouveau_pays in ouest else None,
                            pays if nouveau_statut == "out_of_scope" else None, a["id"]])
                if pays in ouest and certitude == "haute":
                    # 06/11/2026 : Himra et Didi B restaient sans pays (base_country vide) alors que Google les sait Ivoiriens
                    db.run("UPDATE artists SET base_country = ? WHERE id = ? AND base_country IS NULL", [pays, a["id"]])
                    db.run("""INSERT INTO pays_verifs (artist_id, nom, pays_google, certitude, ancien_pays, ancien_statut, nouveau_pays, nouveau_statut)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                           [a["id"], a["name"], pays, certitude, a["pays"], a["status"], nouveau_pays, nouveau_statut])
            if change:
                changes += 1
                lignes.append(f"{a['name']} : {a['pays'] or '?'}/{a['status']} → {nouveau_pays or '?'}/{nouveau_statut} (Google : {pays}, {certitude})")
    lignes.insert(0, f"Pays vérifiés par Google : {changes} correction(s) · {ia_budget.bilan()}")
    return lignes
