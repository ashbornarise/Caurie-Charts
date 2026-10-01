"""Chaîne Telegram : classement de la semaine et posts publiés par un bot (API Bot de Telegram, gratuite).

Rythme : posts en rotation lundi, mercredi et vendredi (album de visuels et légende), Top 10 le dimanche ;
classement officiel dès sa publication dans l'admin.

TELEGRAM_BOT_TOKEN : jeton donné par @BotFather ; TELEGRAM_CHAT_ID : identifiant de la chaîne (-100…), trouvé avec
« manage.py telegram --chats » une fois le bot ajouté comme administrateur de la chaîne.
Chaque envoi est noté dans le journal d'audit : un même classement n'est jamais envoyé deux fois.
"""
import json
from html import escape as _escape

from core import audit, db, env
from core.helpers import fmt_date, share_url, url
from core.services import chart_top
from core.services.platforms import HttpClient, PlatformException

API = "https://api.telegram.org/bot{}/{}"


def escape(s) -> str:
    """Échappement HTML de Telegram : &lt; &gt; &amp; seulement (les apostrophes restent lisibles)."""
    return _escape(str(s), quote=False)


def configured() -> bool:
    return bool(env.get("TELEGRAM_BOT_TOKEN", "") and env.get("TELEGRAM_CHAT_ID", ""))


def call(method: str, payload: dict | None = None, http: HttpClient | None = None) -> dict:
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise PlatformException("TELEGRAM_BOT_TOKEN absent")
    resp = (http or HttpClient(30)).request("POST", API.format(token, method), {"Content-Type": "application/json"},
                                            json.dumps(payload or {}, ensure_ascii=False).encode())
    try:
        data = json.loads(resp["body"])
    except ValueError:
        data = {}
    if not data.get("ok"):
        raise PlatformException("Telegram : " + str(data.get("description") or f"HTTP {resp['status']}"))
    return data["result"]


def chart_message(data: dict) -> str:
    """Texte HTML du Top (Telegram accepte <b>, <a>, <i>)."""
    head = ("🏆 <b>Classement officiel " if data["official"] else "🔥 <b>Tendances de la semaine · ") + escape(data["name"]) + "</b>"
    if data.get("until"):
        same = not data.get("since") or str(data["since"])[:10] == str(data["until"])[:10]
        head += (f"\n<i>Relevé du {fmt_date(data['until'])}</i>" if same
                 else f"\n<i>Du {fmt_date(data['since'])} au {fmt_date(data['until'])}</i>")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"{medals.get(r['rank'], str(r['rank']) + '.')} <a href=\"{url('titre/' + r['track_slug'])}\">{escape(r['title'])}</a> — {escape(r['artist'])}"
             for r in data["rows"]]
    source = ("Classement Cauri Charts (méthodologie publique)" if data["official"]
              else "D’après les classements Apple Music, Deezer, Shazam et YouTube")
    link = url(chart_top.page_path(data["code"]))
    return "\n".join([head, ""] + lines + ["", f"<i>{source}</i>", f"👉 <a href=\"{link}\">Classement complet</a>"])


def send_chart(code: str = chart_top.REGION, force: bool = False, http: HttpClient | None = None) -> str:
    """Envoie le Top 10 (officiel s'il est publié, sinon tendances). Retourne un compte rendu."""
    if not configured():
        return "Telegram non configuré (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)"
    data = chart_top.top(code, 10)
    if not data or not data["rows"]:
        return "rien à envoyer : pas de classement"
    key = f"run-{data['run']['id']}" if data["official"] else f"tendances-{code}-{data.get('until')}"
    if not force and db.value("SELECT 1 FROM audit_log WHERE action = 'telegram.chart' AND reason = ? LIMIT 1", [key]):
        return f"déjà envoyé ({key})"
    text = chart_message(data)
    chat = env.get("TELEGRAM_CHAT_ID")
    if data["official"]:
        # Visuel du classement (image de partage) avec le texte en légende ; Telegram limite la légende à 1024 caractères
        if len(text) <= 1024:
            call("sendPhoto", {"chat_id": chat, "photo": share_url(int(data["run"]["id"]), "square"), "caption": text, "parse_mode": "HTML"}, http)
        else:
            call("sendPhoto", {"chat_id": chat, "photo": share_url(int(data["run"]["id"]), "square")}, http)
            call("sendMessage", {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, http)
    else:
        call("sendMessage", {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, http)
    audit.log(None, "telegram.chart", "chart_run" if data["official"] else None, data["run"]["id"] if data["official"] else None, key, {}, None)
    return f"envoyé ({key})"


def post_caption(post: dict, limit: int = 1024) -> str:
    """Légende HTML d'un post (titre, texte, hashtags, lien), tronquée à la limite des légendes Telegram."""
    tail = f"\n\n{escape(post.get('hashtags') or '')}\n👉 <a href=\"{url('/')}\">cauricharts.com</a>"
    head = f"<b>{escape(post['title'])}</b>\n\n"
    body = escape(post.get("caption") or "")
    room = limit - len(head) - len(tail)
    if len(body) > room:
        body = body[: max(0, room - 1)].rsplit("\n", 1)[0].rstrip() + "…"
    return head + body + tail


def send_post(post: dict, force: bool = False, http: HttpClient | None = None) -> str:
    """Post réseaux sociaux dans la chaîne : album des visuels 4:5 (couverture puis titres), légende sur la première image."""
    from core import storage
    if not configured():
        return "Telegram non configuré"
    key = f"post-{post['id']}"
    if not force and db.value("SELECT 1 FROM audit_log WHERE action = 'telegram.post' AND reason = ? LIMIT 1", [key]):
        return f"déjà envoyé ({key})"
    base = storage.blob_public_url()
    if not base:
        return "pas d’adresse publique pour les images (Blob)"
    try:
        slides = json.loads(post.get("carousel") or "[]") or []
    except ValueError:
        slides = []
    files = [s["file"] if isinstance(s, dict) else s for s in slides] or [post.get("image_square")]
    photos = [f"{base}/media/social/{f}" for f in files if f][:10]  # un album Telegram compte 10 images au plus
    if not photos:
        return "pas d’image pour ce post"
    chat, caption = env.get("TELEGRAM_CHAT_ID"), post_caption(post)
    if len(photos) == 1:
        call("sendPhoto", {"chat_id": chat, "photo": photos[0], "caption": caption, "parse_mode": "HTML"}, http)
    else:
        media = [{"type": "photo", "media": p} for p in photos]
        media[0].update({"caption": caption, "parse_mode": "HTML"})
        call("sendMediaGroup", {"chat_id": chat, "media": media}, http)
    audit.log(None, "telegram.post", "social_post", post["id"], key, {"images": len(photos)}, None)
    return f"envoyé ({key}, {len(photos)} images)"


def chats(http: HttpClient | None = None) -> list:
    """Chaînes et groupes où le bot a reçu un message (pour trouver TELEGRAM_CHAT_ID)."""
    found = {}
    for u in call("getUpdates", {"allowed_updates": ["channel_post", "message", "my_chat_member"]}, http):
        for k in ("channel_post", "message", "my_chat_member"):
            chat = (u.get(k) or {}).get("chat")
            if chat:
                found[chat["id"]] = {"id": chat["id"], "type": chat.get("type"), "title": chat.get("title") or chat.get("username")}
    return list(found.values())
