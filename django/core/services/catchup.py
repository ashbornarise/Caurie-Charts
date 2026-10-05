"""Rattrapage du matin (5 h UTC, après la chaîne de nuit) : ce que la nuit a généré mais pas publié.

Pour chaque post du jour fait par la chaîne (rubriques automatiques, Cauri Matin, portrait, Cauri Hebdo) :
  - visuels absents du Blob : renvoyés depuis le disque s'ils y sont, sinon le visuel 9:16 est recomposé
    depuis le visuel carré (fond flouté) ;
  - pas encore programmé dans Buffer : programmé (Cauri Matin à 7 h, ou au plus tôt ; les autres à 18 h) ;
  - Cauri Matin sans son article dans Actualités : article écrit.
Jamais les posts faits à la main (présentation, annonces, demandes de l'admin) ni ceux refusés.
Ne relance pas la chaîne : rien n'est recalculé, aucun post n'est régénéré.
"""
import io
import json
from datetime import datetime, timedelta, timezone

from core import clock, db, storage
from core.services import buffer
from core.services.platforms import HttpClient

EDITORIAL = ("matin", "portrait", "hebdo")


def _automatic(theme: str) -> bool:
    from core.services.social.themes import THEMES
    return theme in EDITORIAL or theme in THEMES


def _online(name: str, http) -> bool:
    return http.request("HEAD", f"{storage.blob_public_url()}/media/social/{name}")["status"] == 200


def story_from_square(square: bytes, size: tuple[int, int]) -> bytes:
    """Visuel 9:16 recomposé depuis le visuel carré ou 4:5 : l'image entière au centre, sur elle-même floutée."""
    from PIL import Image, ImageFilter
    sq = Image.open(io.BytesIO(square)).convert("RGB")
    W, H = size
    bg = sq.resize((round(sq.width * H / sq.height), H), Image.LANCZOS)
    x = (bg.width - W) // 2
    bg = bg.crop((x, 0, x + W, H)).filter(ImageFilter.GaussianBlur(max(8, W // 54)))
    fg = sq.resize((W, round(sq.height * W / sq.width)), Image.LANCZOS)
    bg.paste(fg, (0, (H - fg.height) // 2))
    out = io.BytesIO()
    bg.save(out, "JPEG", quality=92)
    return out.getvalue()


def repair_media(post: dict, http) -> list:
    """Remet en ligne les visuels manquants d'un post ; retourne ce qui a été fait ou reste impossible."""
    if not storage.blob_token():
        return []
    from core.services.news import http_get
    base = storage.blob_public_url()
    slides = json.loads(post.get("carousel") or "[]") or []
    lines = []
    for s in [x for x in slides if isinstance(x, dict)]:
        for key in ("file", "tiktok"):
            name = s.get(key)
            if not name or _online(name, http):
                continue
            local = storage.MEDIA / "social" / name
            if local.is_file():
                storage.blob_put(f"media/social/{name}", local.read_bytes(), "image/jpeg")
                lines.append(f"{name} renvoyé")
            elif key == "tiktok" and s.get("file") and _online(s["file"], http):
                ref = next((x["tiktok"] for x in slides if isinstance(x, dict) and x.get("tiktok") and x["tiktok"] != name
                            and _online(x["tiktok"], http)), None)
                from PIL import Image
                size = Image.open(io.BytesIO(http_get(f"{base}/media/social/{ref}", binary=True))).size if ref else (2160, 3840)
                data = story_from_square(http_get(f"{base}/media/social/{s['file']}", binary=True), size)
                storage.blob_put(f"media/social/{name}", data, "image/jpeg")
                lines.append(f"{name} recomposé depuis le visuel carré")
            else:
                lines.append(f"{name} introuvable : à refaire depuis l'admin")
    return lines


def due_for(post: dict, now: datetime) -> datetime | None:
    """Heure de publication : Cauri Matin à 7 h (ou dès que possible jusqu'à midi), les autres à 18 h (heure de Lomé)."""
    day = clock.today()
    soon = now + timedelta(minutes=20)
    if post["theme"] == "matin":
        seven = datetime.combine(day, datetime.min.time(), timezone.utc) + timedelta(hours=7)
        return max(seven, soon) if soon.hour < 12 else None  # passé midi, un « journal du matin » n'a plus de sens
    evening = buffer.evening(day)
    return evening if soon < evening else None


def scheduled(post_id: int) -> bool:
    return bool(db.value("SELECT 1 FROM audit_log WHERE action = 'buffer.post' AND reason LIKE ? LIMIT 1", [f"post-{post_id}-%"]))


def run(http=None, now: datetime | None = None) -> tuple[list, list]:
    """(compte rendu, problèmes restants)."""
    http = http or HttpClient(15)
    now = now or datetime.now(timezone.utc)
    lines, problems = [], []
    posts = [p for p in db.all("SELECT * FROM social_posts WHERE slot_date = ? AND status IN ('draft', 'approved') ORDER BY id",
                               [clock.today().isoformat()]) if _automatic(p["theme"])]
    for post in posts:
        tag = f"{post['title']} ({post['theme']})"
        try:
            lines += [f"{tag} : {x}" for x in repair_media(post, http)]
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{tag} : visuels non vérifiés ({exc})")
        if post["theme"] == "matin":
            try:
                from core.services.social import matin
                result = matin.article(post)
                if result != "article déjà publié":
                    lines.append(f"{tag} : {result}")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{tag} : article non écrit ({exc})")
        if not buffer.configured() or scheduled(post["id"]):
            continue
        due = due_for(post, now)
        if not due:
            problems.append(f"{tag} : pas programmé et trop tard aujourd'hui, à publier à la main")
            continue
        result = buffer.schedule(post, due)
        lines.append(f"{tag} : Buffer ({due:%H:%M} UTC) : {result}")
        if buffer.failed(result):
            problems.append(f"{tag} : {result}")
        else:
            db.update("social_posts", {"status": "approved"}, "id = :id AND status = 'draft'", {"id": post["id"]})
    return lines or ["rien à rattraper"], problems
