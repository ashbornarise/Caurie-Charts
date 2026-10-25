"""Publication sur TikTok par la Content Posting API (25/10/2026), sans Buffer.

Publication directe (video.publish) ou brouillon dans la boîte TikTok (video.upload) pour ajouter un son dans l'appli.
Envoi du fichier (FILE_UPLOAD, par morceaux) : pas de vérification de domaine nécessaire, nos vidéos étant sur le Blob.
Les réglages viennent de l'écran de publication du Studio, conforme aux exigences de TikTok : compte affiché,
visibilité choisie (jamais par défaut), commentaires/duos/collages, contenu commercial, confirmation musicale.
Le jeton du compte est en base (tiktok_auth) ; il est renouvelé par la tâche GitHub « Connexion TikTok »."""
from datetime import datetime, timezone

import requests

from core import env
from core.services import tiktok
from core.services.platforms import PlatformException

API = "https://open.tiktokapis.com/v2"
MORCEAU = 10 * 1024 * 1024
PETIT = 5 * 1024 * 1024


def jeton() -> str:
    """Jeton d'accès valide du compte connecté (renouvelé si la clé secrète est disponible ici)."""
    ligne = tiktok._ligne_active()
    if not ligne:
        raise PlatformException("compte TikTok non connecté : connectez-le sur cauricharts.com/tiktok/connecter")
    if env.get("TIKTOK_CLIENT_SECRET"):
        t = tiktok.rafraichit(ligne)
        if t:
            return t
    expire = ligne.get("access_expire")
    if isinstance(expire, str):
        expire = datetime.fromisoformat(expire.replace("Z", "+00:00"))
    if expire and expire.tzinfo is None:
        expire = expire.replace(tzinfo=timezone.utc)
    if expire and expire <= datetime.now(timezone.utc):
        raise PlatformException("jeton TikTok expiré : relancez la tâche « Connexion TikTok » sur GitHub")
    return ligne["access_token"]


def _post(chemin: str, corps: dict, jet: str) -> dict:
    try:
        r = requests.post(f"{API}{chemin}", json=corps, timeout=60,
                          headers={"Authorization": f"Bearer {jet}", "Content-Type": "application/json; charset=UTF-8"})
        d = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise PlatformException(f"TikTok : {exc}") from exc
    err = d.get("error") or {}
    if err.get("code") not in (None, "ok"):
        lisible = {
            "unaudited_client_can_only_post_to_private_accounts":
                "application pas encore auditée par TikTok : publication directe possible seulement si le compte TikTok est "
                "privé (Réglages > Confidentialité > Compte privé) et la vidéo en « Moi uniquement ». Le brouillon, lui, marche.",
            "spam_risk_too_many_posts": "trop de publications aujourd'hui : TikTok limite le nombre de posts par jour.",
            "privacy_level_option_mismatch": "cette visibilité n'est pas permise pour ce compte.",
            "access_token_invalid": "jeton TikTok invalide : reconnectez le compte sur cauricharts.com/tiktok/connecter.",
        }.get(err.get("code"))
        raise PlatformException(f"TikTok : {lisible or err.get('message') or err.get('code')} ({err.get('code')})")
    return d.get("data") or {}


def createur() -> dict:
    """Informations exigées avant toute publication : compte, visibilités permises, interactions, durée maximale."""
    return _post("/post/publish/creator_info/query/", {}, jeton())


def _source(taille: int) -> dict:
    if taille < PETIT:
        return {"source": "FILE_UPLOAD", "video_size": taille, "chunk_size": taille, "total_chunk_count": 1}
    morceau = min(MORCEAU, taille)
    return {"source": "FILE_UPLOAD", "video_size": taille, "chunk_size": morceau, "total_chunk_count": max(1, taille // morceau)}


def _envoie(upload_url: str, video: bytes, src: dict) -> None:
    """Envoie les morceaux dans l'ordre ; le dernier absorbe les octets restants (règle de TikTok)."""
    taille, morceau, n = src["video_size"], src["chunk_size"], src["total_chunk_count"]
    for i in range(n):
        debut = i * morceau
        fin = taille - 1 if i == n - 1 else debut + morceau - 1
        r = requests.put(upload_url, data=video[debut:fin + 1], timeout=300, headers={
            "Content-Type": "video/mp4", "Content-Length": str(fin - debut + 1), "Content-Range": f"bytes {debut}-{fin}/{taille}"})
        if r.status_code not in (200, 201, 206):
            raise PlatformException(f"TikTok : envoi du morceau {i + 1}/{n} refusé ({r.status_code})")


def publier(video_url: str, titre: str, reglages: dict, brouillon: bool = False) -> str:
    """Publie (ou dépose en brouillon) la vidéo ; renvoie le publish_id. reglages : privacy_level, disable_comment,
    disable_duet, disable_stitch, brand_organic_toggle, brand_content_toggle (écran du Studio)."""
    jet = jeton()
    try:
        video = requests.get(video_url, timeout=120).content
    except requests.RequestException as exc:
        raise PlatformException(f"vidéo illisible : {exc}") from exc
    src = _source(len(video))
    if brouillon:
        d = _post("/post/publish/inbox/video/init/", {"source_info": src}, jet)
    else:
        if not reglages.get("privacy_level"):
            raise PlatformException("TikTok : choisissez qui peut voir la vidéo")
        info = {"title": titre[:2200], "privacy_level": reglages["privacy_level"]}
        for k in ("disable_comment", "disable_duet", "disable_stitch", "brand_organic_toggle", "brand_content_toggle"):
            info[k] = bool(reglages.get(k))
        d = _post("/post/publish/video/init/", {"post_info": info, "source_info": src}, jet)
    _envoie(d["upload_url"], video, src)
    return d["publish_id"]


def statut(publish_id: str) -> dict:
    return _post("/post/publish/status/fetch/", {"publish_id": publish_id}, jeton())
