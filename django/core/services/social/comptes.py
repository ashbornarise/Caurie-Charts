"""Comptes Instagram et TikTok officiels des artistes.

Ordre des sources (11/11/2026) : 1) les liens que l'artiste a renseignés dans Spotify for Artists (spotify_paroles.
liens_artiste : officiels, gratuits) ; 2) Gemini avec la recherche Google (27/10/2026), seulement pour ce qui manque.
Quand Spotify donne un autre compte que celui de la fiche, rien n'est remplacé : une proposition attend le fondateur
(table comptes_propositions, admin « Comptes à vérifier »).

Sert aux mentions et aux invitations en collaboration (core.services.meta.collaborateurs). Garde-fous :
- une vraie recherche Google doit avoir eu lieu (requêtes et sources renvoyées), sinon on n'enregistre rien ;
- certitude « haute » seulement, jamais un fan club, un média ou une page de label ;
- TikTok : le profil doit exister (page publique tiktok.com/@nom) ; Instagram refuse cette vérification ;
- un compte déjà attribué à un autre artiste est écarté ; ce que le fondateur a saisi (« manuel ») n'est jamais remplacé.
"""
import json
import re
from datetime import datetime, timezone

from core import db, env
from core.services.platforms import HttpClient, PlatformException, log_write

URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
MODELES = ("gemini-3.5-flash", "gemini-flash-lite-latest")
NOM = re.compile(r"[A-Za-z0-9._]{2,30}")
PAS_ARTISTE = re.compile(r"fan|\bfc\b|_fc|news|update|daily|media|\btv\b|_tv|hype|records|music_?page|officielfan|actu",
                         re.I)


def colonnes() -> None:
    for sql in ("ALTER TABLE artists ADD COLUMN IF NOT EXISTS tiktok VARCHAR(60) NULL",
                "ALTER TABLE artists ADD COLUMN IF NOT EXISTS comptes_source VARCHAR(20) NULL",
                "ALTER TABLE artists ADD COLUMN IF NOT EXISTS comptes_le TIMESTAMP NULL",
                """CREATE TABLE IF NOT EXISTS comptes_propositions (
                    id BIGSERIAL PRIMARY KEY, artist_id INTEGER NOT NULL, site VARCHAR(12) NOT NULL, actuel VARCHAR(60),
                    propose VARCHAR(60) NOT NULL, source VARCHAR(20) NOT NULL, cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    statut VARCHAR(10) NOT NULL DEFAULT 'a_voir', CONSTRAINT uq_comptes_prop UNIQUE (artist_id, site, propose))"""):
        db.run(sql)


def _pseudo(url: str | None, site: str) -> str | None:
    """« https://instagram.com/didibofficial/ » -> « didibofficial »."""
    m = re.search(r"(?:instagram\.com|tiktok\.com)/@?([A-Za-z0-9._]{2,30})", url or "")
    v = m.group(1).rstrip(".") if m else None
    return v if v and v.lower() not in ("p", "reel", "explore", "accounts", "stories") else None


def proposer(artiste: dict, site: str, propose: str, source: str) -> None:
    propose = propose.lower()   # Instagram et TikTok ignorent la casse (« Asakemusic » = « asakemusic »)
    db.run("""INSERT INTO comptes_propositions (artist_id, site, actuel, propose, source) VALUES (?, ?, ?, ?, ?)
              ON CONFLICT (artist_id, site, propose) DO NOTHING""",
           [artiste["id"], site, artiste.get(site) or None, propose, source])


def depuis_spotify(artiste: dict) -> dict:
    """Comptes officiels d'après Spotify. Fiche vide : on remplit (sauf fiche saisie à la main) ; fiche différente :
    proposition à valider. Renvoie ce qui a été enregistré."""
    if not artiste.get("spotify_id"):
        return {}
    from core.services.social import spotify_paroles as SP
    liens = SP.liens_artiste(artiste["spotify_id"])
    champs = {}
    for site in ("instagram", "tiktok"):
        v = _pseudo(liens.get(site), site)
        actuel = str(artiste.get(site) or "").lstrip("@")
        if not v or v.lower() == actuel.lower():
            continue
        autre = db.value(f"SELECT name FROM artists WHERE lower({site}) = lower(?) AND id <> ? LIMIT 1", [v, artiste["id"]])
        if autre:
            log_write("comptes", "warning", f"{artiste['name']} : @{v} (Spotify) déjà attribué à {autre}, écarté")
            continue
        if actuel or artiste.get("comptes_source") == "manuel":
            proposer(artiste, site, v, "spotify")
        else:
            champs[site] = v
    maj = {**champs, "comptes_le": datetime.now(timezone.utc).replace(tzinfo=None)}
    if champs:
        maj["comptes_source"] = "spotify"
        log_write("comptes", "info", f"{artiste['name']} : {champs} (liens officiels Spotify)")
    db.update("artists", maj, "id = :id", {"id": artiste["id"]})
    return champs


def _gemini(prompt: str, http: HttpClient, reflexion: str = "minimal", part: float = 1.0) -> tuple[str, dict]:
    """Gemini avec recherche Google ; part < 1 pour une tâche secondaire (s'arrête avant le plafond du jour)."""
    from core.services import ia_budget
    cle = env.get("GEMINI_API_KEY", "")
    if not cle:
        raise PlatformException("GEMINI_API_KEY absente")
    if not ia_budget.peut("gemini", part):
        raise PlatformException("Gemini : budget du jour atteint")
    corps = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "tools": [{"google_search": {}}],
                        "generationConfig": {"temperature": 0.1, "thinkingConfig": {"thinkingLevel": reflexion}}},
                       ensure_ascii=False).encode()
    dernier = "aucun modèle"
    for m in MODELES:
        r = http.request("POST", URL.format(m), {"x-goog-api-key": cle, "Content-Type": "application/json"}, corps)
        try:
            d = json.loads(r["body"])
        except ValueError:
            d = {}
        c = (d.get("candidates") or [None])[0]
        if r["status"] == 200 and c:
            ia_budget.gemini_usage(d)
            texte = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts") or [])
            return texte, c.get("groundingMetadata") or {}
        dernier = (d.get("error") or {}).get("message") or f"HTTP {r['status']}"
        if r["status"] not in (404, 429, 500, 503):
            break
    raise PlatformException("Gemini : " + dernier)


def tiktok_existe(nom: str, http: HttpClient) -> bool | None:
    """True / False selon la page publique du profil ; None si TikTok ne répond pas (on ne conclut pas)."""
    try:
        r = http.request("GET", f"https://www.tiktok.com/@{nom}",
                         {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36"}, None)
    except Exception:  # noqa: BLE001
        return None
    corps = r.get("body") or ""
    corps = corps.decode("utf-8", "ignore") if isinstance(corps, bytes) else corps
    if f'"uniqueId":"{nom}"'.lower() in corps.lower():
        return True
    return False if '"statusCode":10221' in corps or '"statusCode":10202' in corps else None


def chercher(nom: str, pays: str = "", http: HttpClient | None = None) -> dict:
    """{"instagram": str|None, "tiktok": str|None, "preuve": str} ; uniquement des comptes sûrs."""
    from core.services import ai
    http = http or HttpClient(90)
    # Question en langage naturel : avec une consigne « JSON seulement », Gemini répond de mémoire sans chercher
    texte, meta = _gemini(
        f"Quels sont les comptes Instagram et TikTok officiels du musicien {nom}" + (f" ({pays})" if pays else "") + " ? "
        "Cherche sur Google ses liens officiels (bio YouTube, Spotify, Audiomack, Wikidata, Chartmetric, presse) pour ne pas "
        "confondre avec un fan club, un média ou son label. Termine ta réponse par une ligne JSON : "
        '{"instagram": "nom sans @ ou null", "tiktok": "nom sans @ ou null", "certitude_instagram": "haute|moyenne|faible", '
        '"certitude_tiktok": "haute|moyenne|faible", "preuve": "courte"}', http, part=0.5)   # tâche secondaire
    if not meta.get("webSearchQueries") or not meta.get("groundingChunks"):
        return {"instagram": None, "tiktok": None, "preuve": "pas de recherche Google : rien enregistré"}
    d = ai.extract_json(texte[texte.rfind('{"instagram"'):] if '{"instagram"' in texte else texte) or {}
    out = {"preuve": str(d.get("preuve") or "")[:300]}
    for site in ("instagram", "tiktok"):
        v = str(d.get(site) or "").strip().lstrip("@")
        v = v if v.lower() not in ("null", "none") else ""
        ok = NOM.fullmatch(v or "") and d.get(f"certitude_{site}") == "haute" and not PAS_ARTISTE.search(v)
        if ok and site == "tiktok" and tiktok_existe(v, http) is False:
            ok = False
        out[site] = v if ok else None
    return out


def completer(artiste: dict, http: HttpClient | None = None) -> dict:
    """Cherche et enregistre les comptes d'un artiste (fiche « artists ») ; renvoie ce qui a changé.
    Spotify d'abord (officiel) ; Gemini + Google ensuite, seulement pour ce qui manque encore."""
    champs_sp = {}
    try:
        champs_sp = depuis_spotify(artiste)
    except Exception as exc:  # noqa: BLE001 — API non publique : on continue avec Gemini
        log_write("comptes", "warning", f"{artiste['name']} : liens Spotify indisponibles ({str(exc)[:120]})")
    if artiste.get("comptes_source") == "manuel":
        return champs_sp
    artiste = {**artiste, **champs_sp}
    manque = [site for site in ("instagram", "tiktok") if not artiste.get(site)]
    if not manque:
        return champs_sp
    pays = artiste.get("origin_country") or artiste.get("base_country") or ""
    trouve = chercher(artiste["name"], pays, http)
    champs = {}
    for site in manque:
        v = trouve.get(site)
        if not v or v.lower() == str(artiste.get(site) or "").lower():
            continue
        autre = db.value(f"SELECT name FROM artists WHERE lower({site}) = lower(?) AND id <> ? LIMIT 1", [v, artiste["id"]])
        if autre:
            log_write("comptes", "warning", f"{artiste['name']} : @{v} déjà attribué à {autre}, écarté")
            continue
        champs[site] = v
    maj = {**champs, "comptes_le": datetime.now(timezone.utc).replace(tzinfo=None)}
    if champs:
        maj["comptes_source"] = "spotify+ia" if champs_sp else "ia-google"
        log_write("comptes", "info", f"{artiste['name']} : {champs} ({trouve.get('preuve', '')[:120]})")
    db.update("artists", maj, "id = :id", {"id": artiste["id"]})
    return {**champs_sp, **champs}


def a_chercher(limite: int) -> list:
    """Artistes actifs les plus suivis d'abord, jamais cherchés ou cherchés il y a plus de 60 jours."""
    return db.all("""SELECT id, name, spotify_id, instagram, tiktok, origin_country, base_country, comptes_source FROM artists
                     WHERE status = 'active' AND coalesce(comptes_source, '') <> 'manuel'
                       AND (comptes_le IS NULL OR comptes_le < CURRENT_TIMESTAMP - INTERVAL '60 days')
                     ORDER BY youtube_subscribers DESC NULLS LAST, fans DESC NULLS LAST LIMIT ?""", [limite])


def tous_spotify() -> list:
    """Passage hebdomadaire Spotify : tous les artistes actifs qui ont une page Spotify, fiches manuelles comprises
    (pour les propositions)."""
    return db.all("""SELECT id, name, spotify_id, instagram, tiktok, comptes_source FROM artists
                     WHERE status = 'active' AND spotify_id IS NOT NULL ORDER BY fans DESC NULLS LAST""")
