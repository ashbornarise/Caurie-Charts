"""Cauri Studio, « Médias » (27/11/2026, demande du fondateur) : le Studio devient le pont des médias.

Les médias (photos, vidéos, sons) arrivent de trois façons : un lien de réseau social récupéré par le Studio (YouTube par
le relais du PC, les autres réseaux sur GitHub), un fichier envoyé depuis le téléphone (en morceaux de 4 Mo, limite des
requêtes Vercel, recollés à la fin), ou une création du Studio (dossier automatique « Mes créations »). Ils sont rangés
dans des dossiers : un par artiste (avec les photos de la banque) et ceux que le fondateur crée. Chaque média se
télécharge directement sur le téléphone (?download=1 du Blob : vrai téléchargement, jamais d'archive ZIP).
"""
import glob
import json
import os
import re
import subprocess
import tempfile

import requests

from core import db, storage

DOSSIER = "studio/medias"
TAILLE_MAX = 100 * 1024 * 1024      # 100 Mo par fichier du téléphone : recollé dans une fonction Vercel (300 s au plus)
PARTS_MAX = 30
EXT_PHOTO = ("jpg", "jpeg", "png", "webp", "heic", "gif")
EXT_VIDEO = ("mp4", "mov", "webm", "mkv", "m4v", "3gp")
EXT_SON = ("mp3", "m4a", "aac", "wav", "ogg", "opus", "flac")
TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "heic": "image/heic",
         "gif": "image/gif", "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm", "mkv": "video/x-matroska",
         "m4v": "video/mp4", "3gp": "video/3gpp", "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac",
         "wav": "audio/wav", "ogg": "audio/ogg", "opus": "audio/ogg", "flac": "audio/flac"}


def creer_tables() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS studio_dossiers (
        id BIGSERIAL PRIMARY KEY, nom TEXT NOT NULL, artiste_id BIGINT, cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    db.run("""CREATE TABLE IF NOT EXISTS studio_medias (
        id BIGSERIAL PRIMARY KEY, dossier_id BIGINT, artiste_id BIGINT, genre VARCHAR(10) NOT NULL,
        url TEXT, vignette TEXT, nom TEXT, source TEXT, credit TEXT, taille BIGINT,
        statut VARCHAR(12) NOT NULL DEFAULT 'pret', job_id BIGINT, parts INTEGER, ext VARCHAR(6),
        cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


def genre_de(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    return "photo" if e in EXT_PHOTO else "video" if e in EXT_VIDEO else "son" if e in EXT_SON else "fichier"


def ext_propre(ext: str) -> str:
    e = re.sub(r"[^a-z0-9]", "", str(ext or "").lower())[:5]
    return e if e in TYPES else "bin"


def _url_social(nom) -> str:
    """Vidéo et vignette d'une tâche du Studio : nom de fichier dans media/social (ou adresse complète)."""
    if not nom:
        return ""
    return str(nom) if str(nom).startswith("http") else f"{storage.blob_public_url()}/media/social/{nom}"


def telecharger(url: str) -> str:
    """Adresse qui force le téléchargement (Content-Disposition: attachment)."""
    return f"{url}{'&' if '?' in url else '?'}download=1" if url else ""


# ---------------------------------------------------------------- dossiers

def dossier_cle(cle: str) -> tuple[str, int | None]:
    """« creations », « d12 » (dossier créé) ou « a34 » (artiste) -> (sorte, id)."""
    m = re.fullmatch(r"([da])(\d{1,12})", str(cle or ""))
    if m:
        return ("dossier" if m.group(1) == "d" else "artiste"), int(m.group(2))
    return ("creations", None) if cle == "creations" else ("", None)


def liste_dossiers() -> list[dict]:
    creer_tables()
    from core.services.social import plans
    plans.creer_table()
    base = storage.blob_public_url()
    out = []
    crea = db.one("""SELECT LEAST(COUNT(*), 300) AS n, MAX(id) AS dernier FROM studio_jobs
                     WHERE statut IN ('pret', 'envoye') AND (video IS NOT NULL OR vignette IS NOT NULL)""")
    une = db.value("""SELECT COALESCE(vignette, '') FROM studio_jobs WHERE statut IN ('pret', 'envoye') AND vignette IS NOT NULL
                      ORDER BY id DESC LIMIT 1""")
    out.append({"cle": "creations", "nom": "Mes créations", "n": int(crea["n"] or 0), "une": _url_social(une), "sorte": "creations"})
    for d in db.all("""SELECT d.id, d.nom, COUNT(m.id) AS n, MAX(COALESCE(m.vignette, CASE WHEN m.genre = 'photo' THEN m.url END)) AS une
                       FROM studio_dossiers d LEFT JOIN studio_medias m ON m.dossier_id = d.id AND m.statut = 'pret'
                       GROUP BY d.id, d.nom ORDER BY d.id DESC"""):
        out.append({"cle": f"d{d['id']}", "nom": d["nom"], "n": int(d["n"] or 0), "une": d["une"] or "", "sorte": "dossier"})
    artistes = {}
    for r in db.all("""SELECT a.id, a.name, COUNT(p.id) AS n, MAX(p.fichier) AS une FROM artist_photos p
                       JOIN artists a ON a.id = p.artist_id GROUP BY a.id, a.name"""):
        artistes[r["id"]] = {"cle": f"a{r['id']}", "nom": r["name"], "n": int(r["n"]), "sorte": "artiste",
                             "une": f"{base}/media/artists/plans/{r['une']}" if r["une"] else ""}
    for r in db.all("""SELECT m.artiste_id AS id, a.name, COUNT(m.id) AS n FROM studio_medias m JOIN artists a ON a.id = m.artiste_id
                       WHERE m.statut = 'pret' AND m.dossier_id IS NULL GROUP BY m.artiste_id, a.name"""):
        x = artistes.setdefault(r["id"], {"cle": f"a{r['id']}", "nom": r["name"], "n": 0, "une": "", "sorte": "artiste"})
        x["n"] += int(r["n"])
    out += sorted(artistes.values(), key=lambda x: (-x["n"], x["nom"].lower()))
    return out


def _media_public(m: dict) -> dict:
    return {"id": m["id"], "genre": m["genre"], "url": m.get("url") or "", "vignette": m.get("vignette") or "",
            "nom": m.get("nom") or "", "source": m.get("source") or "", "credit": m.get("credit") or "",
            "statut": m.get("statut") or "pret", "telecharger": telecharger(m.get("url") or ""), "retirable": True}


# un envoi coupé (onglet fermé, réseau perdu) n'encombre pas le dossier plus d'une heure
_VISIBLE = "statut <> 'annule' AND NOT (statut = 'envoi' AND cree_le < NOW() - INTERVAL '1 hour')"


def contenu(cle: str) -> dict:
    """Les médias d'un dossier, du plus récent au plus ancien (avec ceux encore en route)."""
    creer_tables()
    sorte, ident = dossier_cle(cle)
    items = []
    if sorte == "creations":
        for j in db.all("""SELECT id, video, vignette, params, statut FROM studio_jobs WHERE statut IN ('pret', 'envoye')
                           AND (video IS NOT NULL OR vignette IS NOT NULL) ORDER BY id DESC LIMIT 300"""):
            p = json.loads(j["params"] or "{}") if isinstance(j["params"], str) else (j["params"] or {})
            nom = p.get("accroche") or p.get("artiste") or p.get("type") or f"Projet {j['id']}"
            vignette, video = _url_social(j["vignette"]), _url_social(j["video"])
            url, genre = (video, "video") if video else (vignette, "photo")   # une vidéo = un seul média (sa vignette en aperçu)
            items.append({"id": f"j{j['id']}", "genre": genre, "url": url, "vignette": vignette, "nom": nom, "source": "",
                          "credit": "", "statut": "pret", "telecharger": telecharger(url), "retirable": False})
        return {"nom": "Mes créations", "medias": items}
    if sorte == "dossier":
        d = db.one("SELECT id, nom FROM studio_dossiers WHERE id = ?", [ident])
        if not d:
            return {"nom": "", "medias": []}
        lignes = db.all(f"SELECT * FROM studio_medias WHERE dossier_id = ? AND {_VISIBLE} ORDER BY id DESC", [ident])
        return {"nom": d["nom"], "medias": [_media_public(m) for m in lignes]}
    if sorte == "artiste":
        nom = db.value("SELECT name FROM artists WHERE id = ?", [ident]) or ""
        lignes = db.all(f"""SELECT * FROM studio_medias WHERE artiste_id = ? AND dossier_id IS NULL AND {_VISIBLE}
                            ORDER BY id DESC""", [ident])
        items = [_media_public(m) for m in lignes]
        base = storage.blob_public_url()
        for p in db.all("SELECT id, fichier, note FROM artist_photos WHERE artist_id = ? ORDER BY id DESC", [ident]):
            url = f"{base}/media/artists/plans/{p['fichier']}"
            items.append({"id": f"b{p['id']}", "genre": "photo", "url": url, "vignette": url, "nom": p.get("note") or nom,
                          "source": "banque", "credit": "", "statut": "pret", "telecharger": telecharger(url), "retirable": False})
        return {"nom": nom, "medias": items}
    return {"nom": "", "medias": []}


def nouveau_dossier(nom: str, artiste_id: int | None = None) -> int:
    creer_tables()
    return db.insert("studio_dossiers", {"nom": nom.strip()[:80] or "Nouveau dossier", "artiste_id": artiste_id})


def rangement(cle: str) -> dict:
    """{dossier_id, artiste_id} où ranger un média, d'après la clé du dossier choisi."""
    sorte, ident = dossier_cle(cle)
    if sorte == "dossier" and db.value("SELECT 1 FROM studio_dossiers WHERE id = ?", [ident]):
        return {"dossier_id": ident, "artiste_id": None}
    if sorte == "artiste" and db.value("SELECT 1 FROM artists WHERE id = ?", [ident]):
        return {"dossier_id": None, "artiste_id": ident}
    return {"dossier_id": None, "artiste_id": None}


# ---------------------------------------------------------------- envoi depuis le téléphone (morceaux)

def _nom_part(media_id: int, k: int) -> str:
    return f"parts/{media_id}.p{k:03d}"


def envoi_nouveau(nom: str, ext: str, parts: int, taille: int, cle: str) -> int:
    creer_tables()
    e = ext_propre(ext)
    return db.insert("studio_medias", {"genre": genre_de(e), "nom": nom.strip()[:120], "ext": e, "parts": parts,
                                       "taille": taille, "statut": "envoi", "source": "téléphone", **rangement(cle)})


def envoi_morceau(media_id: int, k: int, data: bytes) -> None:
    storage.blob_put(f"media/{DOSSIER}/{_nom_part(media_id, k)}", data, "application/octet-stream")


def envoi_fin(media_id: int) -> dict:
    """Recolle les morceaux en un seul fichier dans le Blob, puis efface les morceaux."""
    m = db.one("SELECT * FROM studio_medias WHERE id = ?", [media_id])
    if not m or m["statut"] != "envoi":
        raise ValueError("envoi introuvable ou déjà terminé")
    base = storage.blob_public_url()
    data = bytearray()   # un seul tampon (liste + join doublait la mémoire)
    for k in range(int(m["parts"] or 1)):
        r = requests.get(f"{base}/media/{DOSSIER}/{_nom_part(media_id, k)}", timeout=60)
        r.raise_for_status()
        data += r.content
    data = bytes(data)
    url = storage.blob_put(f"media/{DOSSIER}/{media_id}.{m['ext']}", data, TYPES.get(m["ext"], "application/octet-stream"))
    db.update("studio_medias", {"url": url, "vignette": url if m["genre"] == "photo" else None, "statut": "pret",
                                "taille": len(data)}, "id = :id", {"id": media_id})
    try:
        storage.blob_delete([f"{base}/media/{DOSSIER}/{_nom_part(media_id, k)}" for k in range(int(m["parts"] or 1))])
    except Exception:  # noqa: BLE001 — des morceaux oubliés ne gênent pas
        pass
    return _media_public({**m, "url": url, "vignette": url if m["genre"] == "photo" else "", "statut": "pret"})


# ---------------------------------------------------------------- récupération d'un lien (GitHub ou relais du PC)

def _vignette_video(chemin: str, tmp: str) -> bytes | None:
    from core.services.social.studio_montage import ffmpeg
    sortie = os.path.join(tmp, "vignette.jpg")
    try:
        subprocess.run([ffmpeg(), "-y", "-ss", "1", "-i", chemin, "-frames:v", "1", "-vf", "scale=540:-2", sortie],
                       capture_output=True, timeout=120)
        return open(sortie, "rb").read() if os.path.isfile(sortie) else None
    except Exception:  # noqa: BLE001
        return None


def _credit(infos: dict) -> str:
    compte = infos.get("uploader_id") or infos.get("channel") or infos.get("uploader") or infos.get("username") or ""
    plateforme = infos.get("extractor_key") or infos.get("category") or ""
    return f"@{str(compte).lstrip('@')} ({plateforme})" if compte else str(plateforme)


def recupere(job_id: int, job: dict, p: dict, maj) -> dict:
    """Télécharge les médias d'un lien (vidéo d'abord, sinon les photos du post) et les range dans le dossier choisi."""
    from core.services.social import studio_montage, studio_photos
    creer_tables()
    lien = job["lien"]
    place = {"dossier_id": p.get("dossier_id"), "artiste_id": p.get("artiste_id")}
    maj(job_id, statut="montage")
    db.run("DELETE FROM studio_medias WHERE job_id = ?", [job_id])   # tâche relancée : pas de doublons
    fichiers, infos, erreur_video = [], {}, ""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            f, infos = studio_montage.telecharge(lien, tmp)
            fichiers = [f]
        except RuntimeError as exc:
            erreur_video = str(exc)
        if not fichiers:   # post photo (ou carrousel de photos) : gallery-dl, puis le navigateur, puis l'image principale
            photos = os.path.join(tmp, "photos")
            os.makedirs(photos, exist_ok=True)
            fichiers, infos2 = studio_photos._gallery_dl(lien, photos)
            infos = infos or infos2 or {}
            if not fichiers and "instagram.com" in lien:
                try:
                    fichiers = studio_photos._instagram_navigateur(lien, photos)
                except Exception:  # noqa: BLE001
                    fichiers = []
            if not fichiers:
                fichiers = studio_photos._og_image(lien, photos)
        if not fichiers:
            raise RuntimeError(erreur_video or "aucune photo ni vidéo trouvée à ce lien")
        credit = _credit(infos)
        titre = str(infos.get("title") or infos.get("description") or "")[:120]
        ids = []
        for k, chemin in enumerate(fichiers[:20]):
            e = ext_propre(os.path.splitext(chemin)[1])
            if e == "bin":
                continue
            data = open(chemin, "rb").read()
            url = storage.blob_put(f"media/{DOSSIER}/lien-{job_id}-{k}.{e}", data, TYPES.get(e, "application/octet-stream"))
            genre = genre_de(e)
            vignette = url if genre == "photo" else None
            if genre == "video":
                v = _vignette_video(chemin, tmp)
                if v:
                    vignette = storage.blob_put(f"media/{DOSSIER}/lien-{job_id}-{k}-vignette.jpg", v, "image/jpeg")
            ids.append(db.insert("studio_medias", {"genre": genre, "url": url, "vignette": vignette, "nom": titre or f"Média {k + 1}",
                                                   "source": lien[:1000], "credit": credit, "taille": len(data), "ext": e,
                                                   "statut": "pret", "job_id": job_id, **place}))
    # « range » et pas « pret » : une récupération n'est pas une création à publier (ni « À valider », ni « Mes créations »)
    maj(job_id, statut="range", erreur=None)
    return {"statut": "range", "medias": len(ids), "video": None}
