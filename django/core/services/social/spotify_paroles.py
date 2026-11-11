"""Paroles synchronisées de Spotify (11/11/2026, idée du fondateur : spotify-lyrics-scraper, Paxsenix0/Spotify-Lyrics-API).

Les paroles affichées dans Spotify (texte exact + début de chaque ligne) passent par l'API interne du lecteur web :
1. cookie « sp_dc » d'un compte Spotify (SPOTIFY_SP_DC, fichier de secrets — jamais dans le code) ;
2. jeton d'accès sur open.spotify.com/api/token, qui exige depuis 2025 un code TOTP calculé avec un secret que
   Spotify fait tourner : la version à jour est publiée dans un dépôt public (xyloflake/spot-secrets-go), comme le
   fait Paxsenix ;
3. paroles sur spclient.wg.spotify.com/color-lyrics/v2/track/<id>.
API non publique : elle peut casser du jour au lendemain ; studio_paroles retombe alors sur Whisper.
"""
import base64
import hashlib
import hmac
import struct
import time

import requests

from core import env

SECRETS_URL = "https://raw.githubusercontent.com/xyloflake/spot-secrets-go/refs/heads/main/secrets/secretDict.json"
NAVIGATEUR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
_cache: dict = {}


class SpotifyParolesErreur(RuntimeError):
    pass


def _secret() -> tuple[bytes, str]:
    """(clé TOTP, version) d'après le dernier secret publié."""
    if _cache.get("secret") and time.time() - _cache["secret"][2] < 3600:
        return _cache["secret"][:2]
    d = requests.get(SECRETS_URL, timeout=15, headers={"User-Agent": NAVIGATEUR}).json()
    version = max(d, key=lambda v: int(v))
    cle = "".join(str(v ^ ((i % 33) + 9)) for i, v in enumerate(d[version])).encode()
    _cache["secret"] = (cle, version, time.time())
    return cle, version


def _totp(cle: bytes, instant_s: float) -> str:
    compteur = struct.pack(">Q", int(instant_s // 30))
    h = hmac.new(cle, compteur, hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def jeton() -> str:
    if _cache.get("jeton") and _cache["jeton"][1] > time.time() + 60:
        return _cache["jeton"][0]
    sp_dc = env.get("SPOTIFY_SP_DC", "")
    if not sp_dc:
        raise SpotifyParolesErreur("SPOTIFY_SP_DC absent")
    entetes = {"User-Agent": NAVIGATEUR, "Origin": "https://open.spotify.com/", "Referer": "https://open.spotify.com/",
               "Cookie": f"sp_dc={sp_dc}"}
    try:
        serveur = float(requests.get("https://open.spotify.com/api/server-time", headers=entetes, timeout=15).json()["serverTime"])
    except Exception:  # noqa: BLE001
        serveur = time.time()
    cle, version = _secret()
    code = _totp(cle, serveur)
    r = requests.get("https://open.spotify.com/api/token", headers=entetes, timeout=20,
                     params={"reason": "init", "productType": "mobile-web-player", "totp": code, "totpVer": version,
                             "totpServer": code})
    d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not d.get("accessToken") or d.get("isAnonymous"):
        raise SpotifyParolesErreur(f"jeton refusé (HTTP {r.status_code}) : {r.text[:200]}")
    _cache["jeton"] = (d["accessToken"], d.get("accessTokenExpirationTimestampMs", 0) / 1000)
    return d["accessToken"]


RECHERCHE_HASH = "130115162add6f3499d2f88ead8a37a7cad1d4d2314f3a206377035e7d26b74c"   # requête « searchDesktop » du lecteur web


def cherche(titre: str, artiste: str = "") -> dict | None:
    """Le titre sur Spotify : {id, titre, artistes, duree_ms}. Recherche du lecteur web (l'API publique répond
    « QUOTA_EXCEEDED » avec ce jeton, 11/11/2026) ; on garde le premier résultat dont un artiste correspond."""
    import json
    variables = {"searchTerm": f"{titre} {artiste}".strip(), "offset": 0, "limit": 10, "numberOfTopResults": 5,
                 "includeAudiobooks": False}
    r = requests.get("https://api-partner.spotify.com/pathfinder/v1/query", timeout=20,
                     headers={"Authorization": f"Bearer {jeton()}", "App-Platform": "WebPlayer", "User-Agent": NAVIGATEUR},
                     params={"operationName": "searchDesktop", "variables": json.dumps(variables),
                             "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": RECHERCHE_HASH}})})
    if r.status_code != 200:
        raise SpotifyParolesErreur(f"recherche refusée (HTTP {r.status_code})")
    items = (((r.json().get("data") or {}).get("searchV2") or {}).get("tracksV2") or {}).get("items") or []
    cible = (artiste or "").lower()
    for it in items:
        d = (it.get("item") or {}).get("data") or {}
        noms = [a["profile"]["name"] for a in (d.get("artists") or {}).get("items", [])]
        if d.get("id") and (not cible or any(cible in n.lower() or n.lower() in cible for n in noms)):
            return {"id": d["id"], "titre": d.get("name"), "artistes": ", ".join(noms),
                    "duree_ms": ((d.get("duration") or {}).get("totalMilliseconds"))}
    return None


def paroles(track_id: str) -> dict:
    """{sync: LINE_SYNCED|UNSYNCED, lignes: [(debut_s, texte)], fournisseur}."""
    r = requests.get(f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}", timeout=20,
                     params={"format": "json", "market": "from_token"},
                     headers={"Authorization": f"Bearer {jeton()}", "App-Platform": "WebPlayer", "Accept": "application/json",
                              "User-Agent": NAVIGATEUR})
    if r.status_code == 404:
        raise SpotifyParolesErreur("pas de paroles sur Spotify pour ce titre")
    if r.status_code != 200:
        raise SpotifyParolesErreur(f"paroles refusées (HTTP {r.status_code})")
    ly = r.json()["lyrics"]
    lignes = [(int(l["startTimeMs"]) / 1000, l["words"].strip()) for l in ly["lines"] if l.get("words", "").strip() not in ("", "♪")]
    return {"sync": ly.get("syncType"), "lignes": lignes, "fournisseur": ly.get("provider")}
