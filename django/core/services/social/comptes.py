"""Comptes Instagram et TikTok officiels des artistes, trouvés par Gemini avec la recherche Google (27/10/2026).

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
                "ALTER TABLE artists ADD COLUMN IF NOT EXISTS comptes_le TIMESTAMP NULL"):
        db.run(sql)


def _gemini(prompt: str, http: HttpClient, reflexion: str = "minimal") -> tuple[str, dict]:
    cle = env.get("GEMINI_API_KEY", "")
    if not cle:
        raise PlatformException("GEMINI_API_KEY absente")
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
        '"certitude_tiktok": "haute|moyenne|faible", "preuve": "courte"}', http)
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
    """Cherche et enregistre les comptes d'un artiste (fiche « artists ») ; renvoie ce qui a changé."""
    if artiste.get("comptes_source") == "manuel":
        return {}
    pays = artiste.get("origin_country") or artiste.get("base_country") or ""
    trouve = chercher(artiste["name"], pays, http)
    champs = {}
    for site in ("instagram", "tiktok"):
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
        maj["comptes_source"] = "ia-google"
        log_write("comptes", "info", f"{artiste['name']} : {champs} ({trouve.get('preuve', '')[:120]})")
    db.update("artists", maj, "id = :id", {"id": artiste["id"]})
    return champs


def a_chercher(limite: int) -> list:
    """Artistes actifs les plus suivis d'abord, jamais cherchés ou cherchés il y a plus de 60 jours."""
    return db.all("""SELECT id, name, instagram, tiktok, origin_country, base_country, comptes_source FROM artists
                     WHERE status = 'active' AND coalesce(comptes_source, '') <> 'manuel'
                       AND (comptes_le IS NULL OR comptes_le < CURRENT_TIMESTAMP - INTERVAL '60 days')
                     ORDER BY youtube_subscribers DESC NULLS LAST, fans DESC NULLS LAST LIMIT ?""", [limite])
