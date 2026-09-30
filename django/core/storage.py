"""Fichiers envoyés (captures des déclarations, logos, images d'actualités).

En local : dossiers du dépôt (storage/uploads hors du dossier public, public/media pour les médias).
Sur Vercel (disque en lecture seule) : Vercel Blob, activé dès que BLOB_READ_WRITE_TOKEN est défini.
"""
import secrets
from datetime import date
from pathlib import Path

import requests
from PIL import Image

from core import clock
from core import conf, env
from core.i18n import t

REPO = Path(__file__).resolve().parent.parent.parent
UPLOADS = REPO / "storage" / "uploads"
MEDIA = REPO / "public" / "media"
ALLOWED = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


def _blob_token() -> str:
    return env.get("BLOB_READ_WRITE_TOKEN", "") or ""


def blob_public_url() -> str:
    """Adresse publique du Blob : BLOB_PUBLIC_URL, sinon déduite du jeton (vercel_blob_rw_<store>_<secret>)."""
    base = (env.get("BLOB_PUBLIC_URL", "") or "").rstrip("/")
    if base:
        return base
    parts = _blob_token().split("_")
    if len(parts) >= 5 and parts[3]:
        return f"https://{parts[3].lower()}.public.blob.vercel-storage.com"
    return ""


def _blob_put(pathname: str, data: bytes, content_type: str) -> str:
    r = requests.put(f"https://blob.vercel-storage.com/{pathname}", data=data, timeout=30, headers={
        "authorization": f"Bearer {_blob_token()}", "x-api-version": "7", "x-content-type": content_type,
        "x-add-random-suffix": "0"})
    r.raise_for_status()
    return r.json()["url"]


def check_image(upload) -> str:
    """Valide une image envoyée ; retourne son extension. ValueError avec un message affichable."""
    if upload is None:
        raise ValueError(t("submit.error_screenshot_required"))
    if upload.size > int(conf.get("app.security.upload_max_bytes")):
        raise ValueError(t("submit.error_too_big"))
    try:
        with Image.open(upload) as img:
            fmt = img.format
            img.verify()
    except Exception:
        raise ValueError(t("submit.error_format"))
    if fmt not in ALLOWED:
        raise ValueError(t("submit.error_format"))
    upload.seek(0)
    return ALLOWED[fmt]


def store_screenshot(upload) -> str:
    """Range une capture de déclaration ; retourne le chemin relatif (ou l'URL Blob)."""
    ext = check_image(upload)
    relative = f"{clock.today():%Y/%m}/{secrets.token_hex(16)}.{ext}"
    data = upload.read()
    if _blob_token():
        return _blob_put("uploads/" + relative, data, "image/" + ("jpeg" if ext == "jpg" else ext))
    target = upload_path(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative


def upload_path(relative: str) -> Path:
    return UPLOADS / relative.replace("..", "").replace("\\", "/").lstrip("/")


def store_media(folder: str, filename: str, data: bytes, content_type: str) -> str:
    """Médias publics (logos partenaires, images d'actualités) : retourne le nom de fichier enregistré."""
    if _blob_token():
        _blob_put(f"media/{folder}/{filename}", data, content_type)
    else:
        (MEDIA / folder).mkdir(parents=True, exist_ok=True)
        (MEDIA / folder / filename).write_bytes(data)
    return filename


def publish_media_files(folder: str, filenames: list) -> None:
    """Envoie vers Vercel Blob des fichiers déjà écrits dans public/media/<folder> (posts générés sur GitHub Actions)."""
    if not _blob_token():
        return
    types = {"png": "image/png", "jpg": "image/jpeg", "mp4": "video/mp4"}
    for name in filter(None, filenames):
        f = MEDIA / folder / name
        if f.is_file():
            _blob_put(f"media/{folder}/{name}", f.read_bytes(), types.get(f.suffix.lstrip(".").lower(), "application/octet-stream"))
