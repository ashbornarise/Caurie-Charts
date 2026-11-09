"""Genre de chaque titre, pour les classements par genre (09/11/2026, avant l'envoi à Nec+Ultra).

Données réelles seulement :
1. le genre officiel d'Apple Music (API iTunes, gratuite) : par l'identifiant Apple du titre, sinon par recherche
   « artiste + titre » avec vérification du nom de l'artiste ;
2. quand Apple ne tranche pas (« African », « Worldwide », « Pop »…) ou pour les genres qu'Apple ne connaît pas
   (coupé-décalé, zouglou, mbalax), l'IA cherche sur Google le genre de l'artiste ; seule une réponse de certitude
   haute est retenue, sinon le titre reste sans genre (il n'entre dans aucun classement de genre).
Le genre d'un titre déjà étiqueté à la main (genre_source = 'manuel') n'est jamais remplacé.
"""
import json
import re
import time
import unicodedata
from urllib.parse import urlencode

from core import db
from core.repos import now_utc
from core.services.platforms import HttpClient, PlatformException

GENRES = {"afrobeats": "Afrobeats", "rap": "Rap", "gospel": "Gospel", "coupe-decale": "Coupé-décalé & Zouglou",
          "highlife": "Highlife", "mbalax": "Mbalax", "rnb": "R&B"}
# Un classement de genre n'est publié que s'il a assez de matière (même esprit que la règle des 8 artistes par pays)
MIN_TITRES, MIN_ARTISTES = 10, 5

# genre Apple (primaryGenreName, en minuscules) -> notre genre ; None = Apple ne tranche pas, on demande à l'IA
APPLE = {
    "afrobeats": "afrobeats", "afro-beat": "afrobeats", "afrobeat": "afrobeats", "afro-pop": "afrobeats", "afropop": "afrobeats",
    "afro house": "afrobeats", "afro-fusion": "afrobeats", "amapiano": "afrobeats", "alté": "afrobeats",
    "hip-hop/rap": "rap", "hip-hop": "rap", "rap": "rap", "drill": "rap", "uk drill": "rap", "trap": "rap",
    "french rap": "rap", "rap francophone": "rap", "afro-trap": "rap", "underground rap": "rap",
    "gospel": "gospel", "christian": "gospel", "christian & gospel": "gospel", "christian music": "gospel",
    "inspirational": "gospel", "praise & worship": "gospel", "contemporary gospel": "gospel", "traditional gospel": "gospel",
    "highlife": "highlife", "hiplife": "highlife", "mbalax": "mbalax",
    "r&b/soul": "rnb", "r&b": "rnb", "soul": "rnb", "contemporary r&b": "rnb", "neo-soul": "rnb",
    "coupé-décalé": "coupe-decale", "coupe-decale": "coupe-decale", "zouglou": "coupe-decale",
}
# Pays où un artiste « afro » peut en réalité faire un genre local qu'Apple ne connaît pas : l'IA vérifie
GENRES_LOCAUX = {"CI": "coupe-decale", "SN": "mbalax", "GH": "highlife"}


def _norme(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def depuis_apple(nom: str | None) -> str | None:
    return APPLE.get((nom or "").strip().lower())


def assure_schema() -> None:
    """Colonnes de genre sur les titres et types de classement déclarés dans la configuration (idempotent)."""
    from core import conf
    db.run("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS genre VARCHAR(20) NULL")
    db.run("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS genre_source VARCHAR(12) NULL")
    db.run("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS genre_apple VARCHAR(60) NULL")
    db.run("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS genre_checked_at TIMESTAMP(0) NULL")
    db.run("CREATE INDEX IF NOT EXISTS idx_track_genre ON tracks (genre)")
    existants = {r["code"] for r in db.all("SELECT code FROM chart_types")}
    for i, (code, c) in enumerate((conf.get("charts") or {}).items()):
        if code not in existants:
            db.run("""INSERT INTO chart_types (code, name, kind, is_public, is_computed, is_regional, sort_order)
                      VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (code) DO NOTHING""",
                   [code, c["name"][:100], c["kind"], int(bool(c.get("public"))), int(bool(c.get("computed"))),
                    int(bool(c.get("regional"))), 20 + i])


def genres_des_titres() -> dict:
    """{track_id: genre} des titres étiquetés."""
    try:
        return {int(r["id"]): r["genre"] for r in db.all("SELECT id, genre FROM tracks WHERE genre IS NOT NULL")}
    except Exception:  # noqa: BLE001 — colonne absente tant que l'étiquetage n'a jamais tourné
        return {}


# ---------------------------------------------------------------- Apple Music (API iTunes)

def _itunes(http: HttpClient, chemin: str, params: dict) -> list:
    r = http.request("GET", f"https://itunes.apple.com/{chemin}?{urlencode(params)}")
    if r["status"] != 200:
        raise PlatformException(f"iTunes {r['status']}")
    return json.loads(r["body"] or "{}").get("results") or []


def apple_par_ids(ids: list[str], http: HttpClient) -> dict:
    """{identifiant Apple du titre: genre Apple}, 150 identifiants par appel."""
    out = {}
    for i in range(0, len(ids), 150):
        for x in _itunes(http, "lookup", {"id": ",".join(ids[i:i + 150]), "entity": "song"}):
            if x.get("wrapperType") == "track" and x.get("primaryGenreName"):
                out[str(x["trackId"])] = x["primaryGenreName"]
    return out


def apple_par_artiste(artiste: str, http: HttpClient) -> dict:
    """{titre normalisé: genre Apple} des chansons de l'artiste (une recherche par artiste : l'API iTunes n'accepte
    qu'une vingtaine de recherches par minute), plus « * » = son genre le plus fréquent. Nom de l'artiste vérifié."""
    na = _norme(artiste)
    out, compte = {}, {}
    for x in _itunes(http, "search", {"term": artiste, "entity": "song", "attribute": "artistTerm", "limit": 50}):
        g = x.get("primaryGenreName")
        if not g or _norme(x.get("artistName", "")).find(na) < 0:
            continue
        out.setdefault(_norme(x.get("trackName", "")), g)
        compte[g] = compte.get(g, 0) + 1
    if compte:
        out["*"] = max(compte, key=compte.get)
    return out


def _du_titre(chansons: dict, titre: str) -> str | None:
    nt = _norme(re.split(r"\(|\[| feat| ft\.", titre or "", flags=re.I)[0])
    for nom, g in chansons.items():
        if nom != "*" and nt and (nom == nt or nom.startswith(nt + " ")):
            return g
    return chansons.get("*")


# ---------------------------------------------------------------- vérification par l'IA (Google)

def ia_par_artiste(artistes: list[dict], client=None) -> dict:
    """{artist_id: genre} pour des artistes qu'Apple ne classe pas clairement ; certitude haute seulement.
    artistes : [{id, nom, pays, apple, titres}]."""
    from core.services import ai
    client = client or ai.make()
    if not client or not artistes:
        return {}
    lignes = "\n".join(f'- id {a["id"]} : {a["nom"]} ({a["pays"] or "?"}) ; genre Apple : {a["apple"] or "aucun"} ; '
                       f'titres : {", ".join(a["titres"][:3])}' for a in artistes)
    choix = " | ".join(GENRES)
    rep = client.ask(
        "Tu es documentaliste musical, spécialiste de l'Afrique de l'Ouest. Tu ne réponds qu'avec des faits vérifiés.",
        "Pour chaque artiste, cherche sur Google le genre musical principal de sa musique actuelle. "
        f"Genres possibles : {choix} | autre. Coupé-décalé et zouglou comptent ensemble (« coupe-decale »). "
        "Le gospel désigne la musique chrétienne. « autre » si aucun ne convient (reggae, variété, mandingue…).\n"
        f"{lignes}\n\nRéponds par une ligne JSON : "
        '{"artistes": [{"id": 0, "genre": "...", "certitude": "haute|moyenne|faible", "preuve": "source courte"}]}',
        max_tokens=1500, web_searches=1)
    if not rep.get("sources"):
        return {}   # réponse sans recherche Google (fournisseur de secours) : rien de vérifié, on ne retient rien
    d = ai.extract_json(rep.get("text") or "") or {}
    out = {}
    for x in d.get("artistes") or []:
        if x.get("certitude") == "haute" and x.get("genre") in GENRES:
            out[int(x["id"])] = x["genre"]
    return out


# ---------------------------------------------------------------- étiquetage

def etiqueter(limite: int = 400, http: HttpClient | None = None, client_ia=None, avec_ia: bool = True,
             pause: float = 3.2) -> dict:
    """Étiquette les titres classés récemment (les plus utiles d'abord). Revient sur un titre tous les 60 jours."""
    assure_schema()
    http = http or HttpClient(30)
    titres = db.all(
        """SELECT t.id, t.title, t.artist_id, a.name AS artiste, COALESCE(a.base_country, a.origin_country) AS pays,
                  (SELECT p.external_id FROM track_platform_ids p WHERE p.track_id = t.id AND p.platform = 'apple_music' LIMIT 1) AS apple_id,
                  (SELECT MAX(w.score) FROM weekly_scores w WHERE w.track_id = t.id AND w.week_start >= CURRENT_DATE - 56) AS recent
           FROM tracks t JOIN artists a ON a.id = t.artist_id
           WHERE t.is_active = 1 AND a.status = 'active' AND COALESCE(t.genre_source, '') <> 'manuel'
             AND (t.genre_checked_at IS NULL OR t.genre_checked_at < CURRENT_TIMESTAMP - INTERVAL '60 days')
           ORDER BY recent DESC NULLS LAST, t.id DESC LIMIT ?""", [limite])
    par_id = apple_par_ids([str(t["apple_id"]) for t in titres if t["apple_id"]], http) if titres else {}
    bilan = {"titres": len(titres), "apple": 0, "ia": 0, "sans": 0}
    resultats, a_verifier = {}, {}
    par_artiste: dict = {}
    for t in titres:
        apple = par_id.get(str(t["apple_id"])) if t["apple_id"] else None
        if not apple:
            aid = int(t["artist_id"])
            if aid not in par_artiste:
                try:
                    par_artiste[aid] = apple_par_artiste(t["artiste"], http)
                except PlatformException:
                    par_artiste[aid] = {}
                time.sleep(pause)
            apple = _du_titre(par_artiste[aid], t["title"])
        genre = depuis_apple(apple)
        local = GENRES_LOCAUX.get((t["pays"] or "").upper())
        resultats[int(t["id"])] = {"apple": apple, "genre": genre, "source": "apple" if genre else None}
        # l'IA vérifie : genre Apple inconnu ou vague, ou artiste d'un pays à genre local qu'Apple range en « afro »
        if avec_ia and (genre is None or (local and genre == "afrobeats")):
            a = a_verifier.setdefault(int(t["artist_id"]), {"id": int(t["artist_id"]), "nom": t["artiste"], "pays": t["pays"],
                                                             "apple": apple, "titres": []})
            a["titres"].append(t["title"])
    if a_verifier:
        artistes = list(a_verifier.values())
        verdicts = {}
        for i in range(0, len(artistes), 15):
            try:
                verdicts.update(ia_par_artiste(artistes[i:i + 15], client_ia))
            except PlatformException:
                break   # crédit d'IA épuisé : on garde le genre Apple, l'IA repassera dans 60 jours
        for t in titres:
            g = verdicts.get(int(t["artist_id"]))
            if g:
                resultats[int(t["id"])].update(genre=g, source="ia")
    maintenant = now_utc()
    for tid, r in resultats.items():
        db.run("UPDATE tracks SET genre = ?, genre_source = ?, genre_apple = ?, genre_checked_at = ? WHERE id = ?",
               [r["genre"], r["source"], (r["apple"] or "")[:60] or None, maintenant, tid])
        bilan["apple" if r["source"] == "apple" else "ia" if r["source"] == "ia" else "sans"] += 1
    return bilan
