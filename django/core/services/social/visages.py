"""Reconnaissance du visage de l'artiste sur une photo (20/10/2026).

Détection YuNet + empreinte SFace (OpenCV, modèles libres du dépôt opencv_zoo, calculés sur place : aucune photo
n'est envoyée à un service). On compare chaque photo aux photos de l'artiste déjà validées dans sa banque ; sans
référence, le visage qui revient le plus souvent sur son propre profil sert de référence.
Uniquement sur GitHub Actions (OpenCV et numpy ne sont pas sur Vercel)."""
from __future__ import annotations

import io
import os

import requests

DOSSIER = os.path.expanduser("~/.u2net")
MODELES = {
    "yunet": "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface": "face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
SEUIL = 0.50          # similarité cosinus SFace (OpenCV : ≥ 0.363) ; plus strict : 0.45 a donné de faux « c'est lui »
DIFFERENT = 0.22      # en dessous, avec un visage net et de face : ce n'est pas lui
NET = 0.88            # confiance du détecteur pour un visage bien visible (pas de lunettes noires, pas de profil)
_OUTILS: dict = {}


def _modele(nom: str) -> str:
    chemin = os.path.join(DOSSIER, os.path.basename(MODELES[nom]))
    if not os.path.exists(chemin) or os.path.getsize(chemin) < 100_000:
        os.makedirs(DOSSIER, exist_ok=True)
        r = requests.get("https://github.com/opencv/opencv_zoo/raw/main/models/" + MODELES[nom], timeout=120)
        r.raise_for_status()
        with open(chemin, "wb") as f:
            f.write(r.content)
    return chemin


def _outils():
    if not _OUTILS:
        import cv2
        _OUTILS["det"] = cv2.FaceDetectorYN.create(_modele("yunet"), "", (320, 320), 0.6)
        _OUTILS["rec"] = cv2.FaceRecognizerSF.create(_modele("sface"), "")
    return _OUTILS["det"], _OUTILS["rec"]


def empreintes(donnees: bytes) -> list:
    """Empreintes des visages de la photo (du plus grand au plus petit)."""
    return [f for f, _c in analyse(donnees)]


def analyse(donnees: bytes) -> list:
    """[(empreinte, confiance du détecteur)] des visages de la photo, du plus grand au plus petit."""
    import cv2
    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(donnees)) as im:
        im = im.convert("RGB")
        im.thumbnail((1280, 1280))
        img = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    det, rec = _outils()
    h, w = img.shape[:2]
    det.setInputSize((w, h))
    _n, visages = det.detect(img)
    if visages is None:
        return []
    out = []
    for v in sorted(visages, key=lambda v: -v[2] * v[3]):
        if min(v[2], v[3]) < 40:          # visage minuscule : pas assez fiable
            continue
        out.append((rec.feature(rec.alignCrop(img, v)).flatten(), float(v[14])))
    return out


def similarite(a, b) -> float:
    import numpy as np
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def meilleure(visages: list, refs: list) -> float:
    return max((similarite(v, r) for v in visages for r in refs), default=0.0)


def verdict(faces: list, refs: list) -> str:
    """« lui », « pas_lui » ou « doute » (pas de visage, lunettes, profil : on ne tranche pas sur le visage)."""
    if not faces or not refs:
        return "doute"
    sim = meilleure([faces[0][0]], refs)
    if sim >= SEUIL:
        return "lui"
    if faces[0][1] >= NET and sim < DIFFERENT:
        return "pas_lui"
    return "doute"


def references_banque(artist_id: int, limite: int = 6) -> list:
    """Empreintes des photos déjà validées de l'artiste (ajoutées à la main, pas celles d'un profil)."""
    from core import db, storage
    refs = []
    try:
        lignes = db.all("SELECT fichier FROM artist_photos WHERE artist_id = ? AND COALESCE(source, '') <> 'profil' "
                        "ORDER BY COALESCE(score, 0.5) DESC LIMIT ?", [artist_id, limite])
    except Exception:  # noqa: BLE001
        return refs
    for l in lignes:
        try:
            r = requests.get(f"{storage.blob_public_url()}/media/artists/plans/{l['fichier']}", timeout=30)
            if r.ok:
                v = empreintes(r.content)
                if len(v) == 1:            # une seule personne sur la référence : pas d'ambiguïté
                    refs.append(v[0])
        except Exception:  # noqa: BLE001
            continue
    return refs


def visage_dominant(listes: list[list], minimum: int = 3) -> list:
    """Sans référence : le visage qui revient sur le plus de photos du profil (l'artiste sur son propre compte).
    Renvoie [] si aucun visage ne revient au moins 3 fois (on ne devine pas)."""
    tous = [v for visages in listes for v in visages[:1]]
    meilleur, n_max = None, 0
    for v in tous:
        n = sum(1 for visages in listes if meilleure(visages, [v]) >= SEUIL)
        if n > n_max:
            meilleur, n_max = v, n
    return [meilleur] if meilleur is not None and n_max >= minimum else []
