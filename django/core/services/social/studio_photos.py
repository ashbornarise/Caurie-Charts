"""Cauri Studio — section Photos (20/10/2026) : récupérer les photos d'un post (Instagram, TikTok photo, X, Facebook…)
pour la banque de l'artiste.

Le serveur télécharge toutes les images du post (carrousel compris) avec gallery-dl ; si la plateforme refuse le serveur,
l'image principale du post (og:image) sert de repli. Les images sont proposées dans l'appli : seules celles que le
fondateur sélectionne entrent dans la banque (artist_photos), avec le crédit du compte d'origine.
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile

import requests
from PIL import Image

from core import db, storage

MAX_PHOTOS = 20
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic")


def _jpeg(chemin: str) -> bytes | None:
    try:
        with Image.open(chemin) as im:
            im = im.convert("RGB")
            if min(im.size) < 400:          # vignettes et avatars : pas pour nos couvertures
                return None
            out = io.BytesIO(); im.save(out, format="JPEG", quality=94)
            return out.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _gallery_dl(lien: str, dossier: str) -> tuple[list[str], dict]:
    """(images téléchargées, infos du compte) via gallery-dl."""
    cmd = [sys.executable, "-m", "gallery_dl", "--range", f"1-{MAX_PHOTOS}", "--write-metadata", "-D", dossier, lien]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    images = sorted(f for f in glob.glob(os.path.join(dossier, "*")) if f.lower().endswith(EXTENSIONS))
    infos = {}
    for m in glob.glob(os.path.join(dossier, "*.json"))[:1]:
        try:
            d = json.load(open(m, encoding="utf-8"))
            compte = d.get("username") or (d.get("author") or {}).get("name") if isinstance(d.get("author"), dict) else d.get("username")
            infos = {"compte": compte or d.get("owner_username") or d.get("uploader") or "", "plateforme": d.get("category", "")}
        except (ValueError, OSError):
            pass
    return images, infos


def _og_image(lien: str, dossier: str) -> list[str]:
    """Repli : l'image principale annoncée par la page (balise og:image)."""
    try:
        html = requests.get(lien, timeout=20, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}).text
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', html)
        if not m:
            return []
        r = requests.get(m.group(1).replace("&amp;", "&"), timeout=30)
        r.raise_for_status()
        p = os.path.join(dossier, "og.jpg"); open(p, "wb").write(r.content)
        return [p]
    except Exception:  # noqa: BLE001
        return []


def traite(job_id: int, job: dict, p: dict, maj) -> dict:
    """Télécharge les photos du post et les propose (Blob media/artists/candidats/)."""
    maj(job_id, statut="telechargement", erreur=None)
    with tempfile.TemporaryDirectory(prefix=f"cauri-photos-{job_id}-") as tmp:
        images, infos = _gallery_dl(job["lien"], tmp)
        if not images:
            images = _og_image(job["lien"], tmp)
        noms = []
        for k, chemin in enumerate(images[:MAX_PHOTOS]):
            donnees = _jpeg(chemin)
            if not donnees:
                continue
            nom = f"studio-{job_id}-{k + 1:02d}.jpg"
            storage.store_media("artists/candidats", nom, donnees, "image/jpeg")
            noms.append(nom)
    if not noms:
        raise RuntimeError("aucune photo récupérée : la plateforme refuse peut-être le serveur (post privé ou connexion exigée)")
    plateforme = infos.get("plateforme") or ""
    compte = infos.get("compte") or ""
    p.update({"photos": noms, "credit": p.get("credit") or (f"@{compte} sur {plateforme.capitalize()}" if compte else plateforme)})
    maj(job_id, statut="pret", params=p)
    return {"statut": "pret", "video": f"{len(noms)} photos"}


def enregistre(job: dict, indices: list[int], artist_id: int, detourable: bool, note: str = "") -> list[str]:
    """Copie les photos choisies dans la banque de l'artiste (Blob media/artists/plans/ + artist_photos)."""
    from core.services.social import plans
    p = job["params"] if isinstance(job["params"], dict) else json.loads(job["params"] or "{}")
    photos = p.get("photos") or []
    a = db.one("SELECT id, slug FROM artists WHERE id = ?", [artist_id])
    if not a:
        raise ValueError("artiste introuvable")
    plans.creer_table()
    db.run("ALTER TABLE artist_photos ADD COLUMN IF NOT EXISTS note TEXT")   # le commentaire du fondateur sur la photo
    base = storage.blob_public_url()
    gardees = []
    for i in indices:
        if not 0 <= i < len(photos):
            continue
        r = requests.get(f"{base}/media/artists/candidats/{photos[i]}", timeout=30)
        r.raise_for_status()
        nom = f"{re.sub(r'[^a-z0-9-]', '', a['slug'])}-lien-{job['id']}-{i + 1:02d}.jpg"
        storage.store_media("artists/plans", nom, r.content, "image/jpeg")
        if not db.value("SELECT 1 FROM artist_photos WHERE fichier = ?", [nom]):
            db.insert("artist_photos", {"artist_id": a["id"], "fichier": nom, "source": "lien", "source_ref": job["lien"][:120],
                                        "credit": (f"Photo : {p.get('credit')}" if p.get("credit") else "Photo partagée par l'artiste")[:300],
                                        "plan_large": bool(detourable), "note": (note or "")[:600] or None})
        gardees.append(nom)
    return gardees


# ---------------------------------------------------------------- envoi depuis le téléphone

def importe(job_id: int, donnees: bytes) -> str | None:
    """Une photo envoyée depuis le téléphone (déjà réduite par l'appli) : ajoutée aux candidates de la tâche."""
    tmp = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
    try:
        tmp.write(donnees); tmp.close()
        jpeg = _jpeg(tmp.name)
    finally:
        os.unlink(tmp.name)
    if not jpeg:
        return None
    job = db.one("SELECT params FROM studio_jobs WHERE id = ?", [job_id])
    p = json.loads(job["params"] or "{}")
    photos = p.get("photos") or []
    if len(photos) >= MAX_PHOTOS:
        return None
    nom = f"studio-{job_id}-{len(photos) + 1:02d}-{os.urandom(2).hex()}.jpg"
    storage.store_media("artists/candidats", nom, jpeg, "image/jpeg")
    p["photos"] = photos + [nom]
    db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False), "statut": "pret"}, "id = :id", {"id": job_id})
    return nom


def suggestions(job: dict, indices: list[int], contexte: str = "") -> dict:
    """Accroche et légendes proposées par l'IA à partir des photos choisies (Gemini les regarde)."""
    from core.services.social.studio_montage import analyse
    p = job["params"] if isinstance(job["params"], dict) else json.loads(job["params"] or "{}")
    photos = [p["photos"][i] for i in indices if 0 <= i < len(p.get("photos") or [])][:4]
    base = storage.blob_public_url()
    with tempfile.TemporaryDirectory(prefix="cauri-sugg-") as tmp:
        chemins = []
        for k, nom in enumerate(photos):
            try:
                r = requests.get(f"{base}/media/artists/candidats/{nom}", timeout=20)
                with Image.open(io.BytesIO(r.content)) as im:
                    im = im.convert("RGB"); im.thumbnail((640, 640))
                    c = os.path.join(tmp, f"{k}.jpg"); im.save(c, quality=85); chemins.append(c)
            except Exception:  # noqa: BLE001
                continue
        infos = {"uploader": p.get("credit") or "", "artist": p.get("artiste_nom") or "", "contexte": contexte or p.get("contexte") or ""}
        return analyse(chemins, infos)


# ---------------------------------------------------------------- publication du carrousel

def publie(job_id: int, job: dict, p: dict, maj) -> dict:
    """Carrousel Cauri : couverture actu (1re photo, accroche) puis les autres photos en plein cadre avec le logo ;
    légende FR + EN, crédit ; envoi via Buffer (notification sur Instagram et TikTok si demandé)."""
    from datetime import datetime, timedelta, timezone
    from core.services import buffer
    from core.services.social import couverture2026 as C
    from core.services.social import editorial as E
    from core.services.social import image as PI
    maj(job_id, statut="montage")
    base = storage.blob_public_url()
    choix = [p["photos"][i] for i in p.get("publier_indices", []) if 0 <= i < len(p.get("photos") or [])][:10]
    if not choix:
        raise RuntimeError("aucune photo choisie")
    urls = [f"{base}/media/artists/candidats/{n}" for n in choix]
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"studio-photos-{job_id}-{os.urandom(2).hex()}"
    fichiers = []
    for k, u in enumerate(urls):
        for fmt, suf in (("feed", ""), ("story", "-916")):
            im = (C.actu(u, (p.get("etiquette") or "PHOTOS").upper()[:28], p.get("accroche") or "", [p.get("artiste_nom") or ""],
                         f"Photo : {p.get('credit')}" if p.get("credit") else "", fmt) if k == 0
                  else C.photo_simple(u, fmt, p.get("credit") or ""))
            PI.save_jpeg(im, PI.DIR / f"{nom}-{k}{suf}.jpg")
        fichiers.append({"file": f"{nom}-{k}.jpg", "tiktok": f"{nom}-{k}-916.jpg", "label": p.get("accroche") or "Photos"})
    legende = (p.get("legende_fr") or p.get("accroche") or "") + (f"\n\n📸 {p.get('credit')}" if p.get("credit") else "")
    artiste = p.get("artiste_nom") or ""
    tags = "#CauriCharts" + (" #" + "".join(ch for ch in artiste if ch.isalnum()) if artiste else "") + " #Afrobeats #MusiqueAfricaine"
    maintenant = datetime.now(timezone.utc)
    faits = {"kind": f"format-studio-photos", "studio_job": job_id, "due": (maintenant + timedelta(minutes=2)).isoformat(),
             "source": job["lien"], "notifier": bool(p.get("notifier")), "reseaux": p.get("reseaux")}
    if p.get("legende_en"):
        faits["en"] = {"title": p.get("accroche") or "", "caption": p["legende_en"] + (f"\n\n📸 {p.get('credit')}" if p.get("credit") else "")}
    from core.studio import theme_libre
    post = E.save_post(theme_libre(job_id, maintenant), maintenant.date().isoformat(), (p.get("accroche") or "Photos")[:160], legende,
                       tags, fichiers, faits)
    resultat = buffer.schedule(post, maintenant + timedelta(minutes=2))
    recus = [r["reason"] for r in db.all("SELECT reason FROM audit_log WHERE reason LIKE ?", [f"post-{post['id']}-%"])]
    maj(job_id, statut="envoye" if recus else "erreur", post_id=post["id"],
        erreur=None if recus else f"aucun réseau n'a accepté le carrousel : {resultat}"[:500])
    return {"statut": "envoye", "video": f"post {post['id']}"}
