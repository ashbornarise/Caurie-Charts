"""Fichiers envoyés (captures des déclarations, logos, images d'actualités).

En local : dossiers du dépôt (storage/uploads hors du dossier public, public/media pour les médias).
Sur Vercel (disque en lecture seule) : Vercel Blob, activé dès que BLOB_READ_WRITE_TOKEN est défini.
"""
import os
import secrets
import tempfile
import time
from datetime import date
from pathlib import Path

import requests
from PIL import Image

from core import clock
from core import conf, env
from core.i18n import t

REPO = Path(__file__).resolve().parent.parent.parent
UPLOADS = REPO / "storage" / "uploads"
# Vercel : disque en lecture seule sauf /tmp ; les fichiers y sont générés puis envoyés dans le Blob
MEDIA = Path(tempfile.gettempdir()) / "cauri-media" if os.environ.get("VERCEL") else REPO / "public" / "media"
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


# Pannes passagères du Blob (503 du 5 octobre 2026 : un post de la nuit perdu pour un seul visuel) : on réessaie
RETRY_WAITS = (2, 5, 15)
_sleep = time.sleep


def _blob_put(pathname: str, data: bytes, content_type: str, max_age: int | None = None) -> str:
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            r = requests.put(f"https://blob.vercel-storage.com/{pathname}", data=data, timeout=30, headers={
                "authorization": f"Bearer {_blob_token()}", "x-api-version": "7", "x-content-type": content_type,
                "x-add-random-suffix": "0", **({"x-cache-control-max-age": str(max_age)} if max_age else {})})
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
                return r.json()["url"]
            error = requests.HTTPError(f"{r.status_code} Server Error: {r.reason} for url: {r.url}", response=r)
        except (requests.ConnectionError, requests.Timeout) as exc:
            error = exc
        if attempt == len(RETRY_WAITS):
            raise error
        _sleep(RETRY_WAITS[attempt])


def blob_token() -> str:
    return _blob_token()


def blob_put(pathname: str, data: bytes, content_type: str, max_age: int | None = None) -> str:
    """Dépose un fichier dans le Blob ; retourne son adresse publique. max_age : durée de cache du CDN (≥ 60 s)
    pour un fichier réécrit souvent (sinon le CDN peut servir l'ancienne version longtemps)."""
    return _blob_put(pathname, data, content_type, max_age)


# État du guet Cauri Monde (monde.etat_guet) : lu toutes les 10 min à la place de la base, pour qu'elle dorme.
# Toute écriture sur social_posts le déclare périmé (db.run / insert / update) : le guet suivant relit la base.
GUET = "monde/guet.json"
_guet_invalide_a = 0.0


def invalide_guet() -> None:
    global _guet_invalide_a
    if not _blob_token() or time.monotonic() - _guet_invalide_a < 30:
        return
    _guet_invalide_a = time.monotonic()
    try:
        _blob_put(GUET, b'{"perime": true}', "application/json", 60)
    except Exception:  # noqa: BLE001 — au pire, l'état est relu au bout de 3 h
        pass


def blob_list(prefix: str) -> list:
    """Fichiers du Blob sous un préfixe : [{pathname, url, size, uploadedAt}] (une opération par page de 1 000)."""
    out, cursor = [], None
    while True:
        params = {"prefix": prefix, "limit": 1000, **({"cursor": cursor} if cursor else {})}
        r = requests.get("https://blob.vercel-storage.com", params=params, timeout=30,
                         headers={"authorization": f"Bearer {_blob_token()}", "x-api-version": "7"})
        r.raise_for_status()
        data = r.json()
        out += data.get("blobs", [])
        cursor = data.get("cursor")
        if not data.get("hasMore"):
            return out


def blob_delete(urls: list) -> None:
    """Supprime des fichiers du Blob (les suppressions ne sont pas facturées)."""
    for i in range(0, len(urls), 500):
        requests.post("https://blob.vercel-storage.com/delete", json={"urls": urls[i:i + 500]}, timeout=60,
                      headers={"authorization": f"Bearer {_blob_token()}", "x-api-version": "7"}).raise_for_status()


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
    from concurrent.futures import ThreadPoolExecutor
    types = {"png": "image/png", "jpg": "image/jpeg", "mp4": "video/mp4"}
    paths = [MEDIA / folder / name for name in dict.fromkeys(filter(None, filenames))]
    paths = [f for f in paths if f.is_file()]

    def put(f):
        _blob_put(f"media/{folder}/{f.name}", f.read_bytes(), types.get(f.suffix.lstrip(".").lower(), "application/octet-stream"))

    # Envois en parallèle : un post compte une vingtaine de visuels 4K
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(put, paths))
