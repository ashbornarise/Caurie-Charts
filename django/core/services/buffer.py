"""Programmation des posts sur Instagram, Facebook et TikTok par Buffer (API GraphQL, offre gratuite : 3 comptes).

BUFFER_API_KEY : clé créée sur https://publish.buffer.com/settings/api.
Les visuels sont donnés par leur adresse publique (Vercel Blob) : Buffer les télécharge lui-même.
Chaque post n'est programmé qu'une fois par compte (journal d'audit) ; il reste annulable dans Buffer jusqu'à l'heure prévue.
"""
import json
from datetime import date, datetime, time, timezone

from core import audit, db, env
from core.helpers import url
from core.services.platforms import HttpClient, PlatformException

API = "https://api.buffer.com"
# Limites des plateformes pour un carrousel de photos
MAX_IMAGES = {"instagram": 20, "facebook": 10, "tiktok": 35}
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
    else:
        files = [s["file"] if isinstance(s, dict) else s for s in slides] or [post.get("image_square")]
    return [f"{base}/media/social/{f}" for f in files if f][:MAX_IMAGES.get(service, 10)]


def payload(post: dict, channel: dict, due_at: datetime | None) -> dict:
    service = channel["service"]
    pics = images(post, service)
    if not pics:
        raise PlatformException("pas d'image pour ce post")
    data = {"channelId": channel["id"], "text": text(post, service), "assets": [{"image": {"url": p}} for p in pics],
            "schedulingType": "automatic", "needsApproval": False,
            "mode": "customScheduled" if due_at else "addToQueue"}
    if due_at:
        data["dueAt"] = due_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if service == "instagram":
        # Plusieurs images dans un post « post » : Instagram en fait un carrousel
        data["metadata"] = {"instagram": {"type": "post", "shouldShareToFeed": True}}
    elif service == "facebook":
        data["metadata"] = {"facebook": {"type": "post"}}
    elif service == "tiktok":
        data["metadata"] = {"tiktok": {"title": post["title"][:90]}}
    return data


CREATE = """mutation($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id dueAt } }
  ... on InvalidInputError { message } ... on LimitReachedError { message } ... on UnauthorizedError { message }
  ... on NotFoundError { message } ... on UnexpectedError { message } ... on RestProxyError { message } } }"""


def schedule(post: dict, due_at: datetime | None = None, force: bool = False, http: HttpClient | None = None) -> str:
    """Programme le post sur chaque compte relié ; sans date, il prend la prochaine place de la file Buffer."""
    if not configured():
        return "Buffer non configuré (BUFFER_API_KEY)"
    done = []
    for ch in channels(http):
        if ch["service"] not in MAX_IMAGES:
            continue
        key = f"post-{post['id']}-{ch['service']}"
        if not force and db.value("SELECT 1 FROM audit_log WHERE action = 'buffer.post' AND reason = ? LIMIT 1", [key]):
            done.append(f"{ch['service']} déjà programmé")
            continue
        try:
            r = call(CREATE, {"input": payload(post, ch, due_at)}, http)["createPost"]
        except PlatformException as exc:
            done.append(f"{ch['service']} : {exc}")
            continue
        if "post" not in r:
            done.append(f"{ch['service']} : {r.get('message', 'refusé')}")
            continue
        audit.log(None, "buffer.post", "social_post", post["id"], key, {"buffer_id": r["post"]["id"], "due": r["post"].get("dueAt")}, None)
        done.append(f"{ch['service']} programmé")
    return ", ".join(done) or "aucun compte relié à Buffer"
