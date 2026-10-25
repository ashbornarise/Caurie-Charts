"""Publication directe sur Instagram et Facebook (API Graph de Meta), sans passer par Buffer (25/10/2026).

Jeton d'utilisateur système « cauri-stats » (application « Cauri Charts Stats ») : n'expire pas, droits de publication
Instagram et Page. Ce que Buffer ne fait pas : l'artiste du post est invité en collaboration (le reel apparaît aussi sur
son profil, devant ses abonnés), et pas de file d'attente limitée.
Variables : META_ACCESS_TOKEN, META_IG_ID, META_PAGE_ID ; META_DIRECT=1 pour l'activer dans buffer.schedule."""
import json
import time

import requests

from core import db, env
from core.services.platforms import PlatformException

G = "https://graph.facebook.com/v21.0"
ATTENTE_MAX = 300   # secondes : traitement d'une vidéo par Instagram


def _env(k: str) -> str:
    return (env.get(k, "") or "").strip().strip('"')


def configured() -> bool:
    return all(_env(k) for k in ("META_ACCESS_TOKEN", "META_IG_ID", "META_PAGE_ID"))


def actif() -> bool:
    return configured() and _env("META_DIRECT") in ("1", "oui", "true")


def _appel(methode: str, chemin: str, jeton: str | None = None, **params) -> dict:
    params["access_token"] = jeton or _env("META_ACCESS_TOKEN")
    try:
        r = requests.request(methode, f"{G}/{chemin}", data=params if methode == "POST" else None,
                             params=params if methode != "POST" else None, timeout=120)
        d = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise PlatformException(f"Meta : {exc}") from exc
    if "error" in d:
        raise PlatformException(f"Meta : {d['error'].get('message', d['error'])}")
    return d


_jeton_page: str | None = None


def jeton_page() -> str:
    global _jeton_page
    if not _jeton_page:
        _jeton_page = _appel("GET", _env("META_PAGE_ID"), fields="access_token")["access_token"]
    return _jeton_page


def collaborateurs(post: dict) -> list[str]:
    """Comptes Instagram des artistes du post (au plus 3), à inviter en collaboration."""
    try:
        f = json.loads(post.get("facts") or "{}")
    except ValueError:
        f = {}
    noms = list(f.get("collab") or [])
    artistes = [f.get("artiste")] + [x.get("artiste") for x in (f.get("fiches") or [])[:1]]
    if f.get("track_id"):
        artistes.append(db.value("SELECT a.name FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE t.id = ?", [f["track_id"]]))
    for nom in [a for a in artistes if a]:
        ig = db.value("SELECT instagram FROM artists WHERE lower(name) = lower(?) AND instagram IS NOT NULL AND instagram <> '' "
                      "ORDER BY youtube_subscribers DESC NULLS LAST LIMIT 1", [nom])
        if ig:
            noms.append(ig.lstrip("@"))
    return [n for n in dict.fromkeys(noms) if n and n.lower() != "cauricharts"][:3]


def _attend(conteneur: str) -> None:
    debut = time.time()
    while time.time() - debut < ATTENTE_MAX:
        s = _appel("GET", conteneur, fields="status_code,status").get("status_code")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise PlatformException(f"Instagram : traitement refusé ({s})")
        time.sleep(5)
    raise PlatformException("Instagram : traitement trop long")


def _conteneur(params: dict, collab: list) -> str:
    """Crée le conteneur ; si un compte invité est refusé, recommence sans les invitations."""
    if collab:
        try:
            return _appel("POST", f"{_env('META_IG_ID')}/media", **params, collaborators=json.dumps(collab))["id"]
        except PlatformException:
            pass
    return _appel("POST", f"{_env('META_IG_ID')}/media", **params)["id"]


def instagram(post: dict, reel: bool, publier: bool = True) -> str:
    """Reel (vidéo 9:16) ou post photo / carrousel. Renvoie l'identifiant du média (ou du conteneur si publier=False)."""
    from core.services import buffer
    legende, collab, ig = buffer.text(post, "instagram"), collaborateurs(post), _env("META_IG_ID")
    if reel:
        video = buffer.video_url(post)
        if not video:
            raise PlatformException("pas de vidéo pour ce post")
        cid = _conteneur({"media_type": "REELS", "video_url": video, "caption": legende, "share_to_feed": "true"}, collab)
    else:
        photos = buffer.images(post, "instagram")
        if not photos:
            raise PlatformException("pas d'image pour ce post")
        if len(photos) == 1:
            cid = _conteneur({"image_url": photos[0], "caption": legende}, collab)
        else:
            enfants = [_appel("POST", f"{ig}/media", image_url=u, is_carousel_item="true")["id"] for u in photos[:10]]
            cid = _conteneur({"media_type": "CAROUSEL", "children": ",".join(enfants), "caption": legende}, collab)
    _attend(cid)
    if not publier:
        return cid
    return _appel("POST", f"{ig}/media_publish", creation_id=cid)["id"]


def facebook(post: dict, reel: bool, publier: bool = True) -> str:
    """Vidéo ou photo(s) sur la page Facebook. publier=False : envoyé non publié (essai)."""
    from core.services import buffer
    page, jeton, legende = _env("META_PAGE_ID"), jeton_page(), buffer.text(post, "facebook")
    pub = "true" if publier else "false"
    if reel:
        video = buffer.video_url(post)
        if not video:
            raise PlatformException("pas de vidéo pour ce post")
        return _appel("POST", f"{page}/videos", jeton, file_url=video, description=legende, published=pub)["id"]
    photos = buffer.images(post, "facebook")
    if not photos:
        raise PlatformException("pas d'image pour ce post")
    if len(photos) == 1:
        return _appel("POST", f"{page}/photos", jeton, url=photos[0], caption=legende, published=pub)["id"]
    ids = [_appel("POST", f"{page}/photos", jeton, url=u, published="false")["id"] for u in photos[:10]]
    if not publier:
        return ",".join(ids)
    return _appel("POST", f"{page}/feed", jeton, message=legende,
                  attached_media=json.dumps([{"media_fbid": i} for i in ids]))["id"]
