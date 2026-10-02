"""Programmation des posts sur Instagram, Facebook et TikTok par Buffer (API GraphQL, offre gratuite : 3 comptes).

BUFFER_API_KEY : clé créée sur https://publish.buffer.com/settings/api.
Les visuels sont donnés par leur adresse publique (Vercel Blob) : Buffer les télécharge lui-même.
Chaque post n'est programmé qu'une fois par compte (journal d'audit) ; il reste annulable dans Buffer jusqu'à l'heure prévue.
"""
import json
from datetime import date, datetime, time, timedelta, timezone

from core import audit, db, env
from core.helpers import url
from core.services.platforms import HttpClient, PlatformException

API = "https://api.buffer.com"
# Limites des plateformes pour un carrousel de photos
MAX_IMAGES = {"instagram": 20, "facebook": 10, "tiktok": 35}
NOTIFY_REELS = ("instagram", "tiktok")
PUBLISH_HOUR = 18  # heure de Lomé (UTC) : la fin de journée, quand l'audience est sur son téléphone


def evening(day: date) -> datetime:
    return datetime.combine(day, time(PUBLISH_HOUR), timezone.utc)


def configured() -> bool:
    return bool(env.get("BUFFER_API_KEY", ""))


def call(query: str, variables: dict | None = None, http: HttpClient | None = None) -> dict:
    key = env.get("BUFFER_API_KEY", "")
    if not key:
        raise PlatformException("BUFFER_API_KEY absente")
    resp = (http or HttpClient(30)).request("POST", API, {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                                            json.dumps({"query": query, "variables": variables or {}}).encode())
    try:
        data = json.loads(resp["body"])
    except ValueError:
        data = {}
    if data.get("errors"):
        raise PlatformException("Buffer : " + "; ".join(e.get("message", "?") for e in data["errors"]))
    if resp["status"] != 200 or "data" not in data:
        raise PlatformException(f"Buffer : HTTP {resp['status']}")
    return data["data"]


def channels(http: HttpClient | None = None) -> list:
    """Comptes reliés à Buffer (actifs seulement) : [{id, service, name}]."""
    out = []
    for org in call("query { account { organizations { id } } }", None, http)["account"]["organizations"]:
        found = call("query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id name service isDisconnected isLocked } }",
                     {"o": org["id"]}, http)["channels"]
        out += [c for c in found if not c["isDisconnected"] and not c["isLocked"]]
    return out


def text(post: dict, service: str) -> str:
    """Légende : titre, texte, hashtags ; le lien n'est cliquable que sur Facebook (« lien en bio » ailleurs)."""
    link = url("/") if service == "facebook" else "Lien en bio : cauricharts.com"
    body = f"{post['title']}\n\n{post.get('caption') or ''}\n\n{link}\n\n{post.get('hashtags') or ''}".strip()
    return body[:2200]  # limite des légendes Instagram et TikTok


TIKTOK_SIZE = (1080, 1920)  # TikTok refuse les photos de plus de 2 073 600 pixels : nos visuels 4K sont réduits


def tiktok_copies(files: list, base: str) -> list:
    """Copie 1080 × 1920 de chaque visuel 9:16, créée une fois et déposée à côté de l'original (« …-tt.jpg »)."""
    import io
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    from core import storage
    from core.services.news import http_get

    def one(f: str) -> str:
        small = f.rsplit(".", 1)[0] + "-tt.jpg"
        try:
            if HttpClient(15).request("HEAD", f"{base}/media/social/{small}")["status"] == 200:
                return small
            data = http_get(f"{base}/media/social/{f}", binary=True)
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img = img.resize(TIKTOK_SIZE, Image.LANCZOS) if img.size[0] > TIKTOK_SIZE[0] else img
            out = io.BytesIO()
            img.save(out, "JPEG", quality=90, optimize=True)
            storage.blob_put(f"media/social/{small}", out.getvalue(), "image/jpeg")
            return small
        except Exception:  # noqa: BLE001 — sans copie, on garde l'original (TikTok le refusera, l'erreur sera visible)
            return f

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, files))


def images(post: dict, service: str) -> list:
    """Adresses publiques des visuels : 9:16 pour TikTok, 4:5 ailleurs (couverture puis titres)."""
    from core import storage
    base = storage.blob_public_url()
    if not base:
        raise PlatformException("pas d'adresse publique pour les images (Blob)")
    try:
        slides = json.loads(post.get("carousel") or "[]") or []
    except ValueError:
        slides = []
    if service == "tiktok":
        files = [s.get("tiktok") for s in slides if isinstance(s, dict)] or [post.get("image_story")]
        files = tiktok_copies([f for f in files if f][:MAX_IMAGES["tiktok"]], base)
    else:
        files = [s["file"] if isinstance(s, dict) else s for s in slides] or [post.get("image_square")]
    return [f"{base}/media/social/{f}" for f in files if f][:MAX_IMAGES.get(service, 10)]


def video_url(post: dict) -> str | None:
    from core import storage
    base = storage.blob_public_url()
    return f"{base}/media/social/{post['video']}" if base and post.get("video") else None


def payload(post: dict, channel: dict, due_at: datetime | None, reel: bool = False) -> dict:
    """Carrousel de photos, ou vidéo 9:16 (reel Instagram et Facebook, vidéo TikTok) si reel=True."""
    service = channel["service"]
    if reel:
        video = video_url(post)
        if not video:
            raise PlatformException("pas de vidéo pour ce post")
        assets = [{"video": {"url": video}}]
    else:
        pics = images(post, service)
        if not pics:
            raise PlatformException("pas d'image pour ce post")
        assets = [{"image": {"url": p}} for p in pics]
    # Vidéo sur Instagram et TikTok : Buffer prévient le téléphone à l'heure dite et ouvre l'application, où l'on ajoute
    # un son de leur bibliothèque (impossible par API). Facebook n'a pas ce mode : sa vidéo part seule, musique incrustée.
    notify = reel and service in NOTIFY_REELS
    data = {"channelId": channel["id"], "text": text(post, service), "assets": assets,
            "schedulingType": "notification" if notify else "automatic", "needsApproval": False,
            "mode": "customScheduled" if due_at else "addToQueue"}
    if due_at:
        data["dueAt"] = due_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if service == "instagram":
        # Plusieurs images dans un post « post » : Instagram en fait un carrousel
        data["metadata"] = {"instagram": {"type": "reel" if reel else "post", "shouldShareToFeed": True}}
    elif service == "facebook":
        data["metadata"] = {"facebook": {"type": "reel" if reel else "post"}}
    elif service == "tiktok":
        data["metadata"] = {"tiktok": {"title": post["title"][:90]}}
    return data


CREATE = """mutation($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id dueAt } }
  ... on InvalidInputError { message } ... on LimitReachedError { message } ... on UnauthorizedError { message }
  ... on NotFoundError { message } ... on UnexpectedError { message } ... on RestProxyError { message } } }"""


def schedule(post: dict, due_at: datetime | None = None, force: bool = False, http: HttpClient | None = None) -> str:
    """Programme le post sur chaque compte relié : le carrousel à l'heure prévue, puis la vidéo du Top le lendemain
    à midi (deux publications pour un post). Sans date, chaque envoi prend la prochaine place de la file Buffer."""
    if not configured():
        return "Buffer non configuré (BUFFER_API_KEY)"
    done = []
    jobs = [("", False, due_at)]
    if post.get("video"):
        # La vidéo le lendemain à midi : le soir reste au carrousel du jour et au magazine du dimanche
        jobs.append(("-reel", True, due_at + timedelta(hours=18) if due_at else None))
    for ch in channels(http):
        if ch["service"] not in MAX_IMAGES:
            continue
        for suffix, reel, when in jobs:
            label = ch["service"] + (" (vidéo)" if reel else "")
            key = f"post-{post['id']}-{ch['service']}{suffix}"
            if not force and db.value("SELECT 1 FROM audit_log WHERE action = 'buffer.post' AND reason = ? LIMIT 1", [key]):
                done.append(f"{label} déjà programmé")
                continue
            try:
                r = call(CREATE, {"input": payload(post, ch, when, reel)}, http)["createPost"]
            except PlatformException as exc:
                done.append(f"{label} : {exc}")
                continue
            if "post" not in r:
                done.append(f"{label} : {r.get('message', 'refusé')}")
                continue
            audit.log(None, "buffer.post", "social_post", post["id"], key, {"buffer_id": r["post"]["id"], "due": r["post"].get("dueAt")}, None)
            done.append(f"{label} programmé")
    return ", ".join(done) or "aucun compte relié à Buffer"
