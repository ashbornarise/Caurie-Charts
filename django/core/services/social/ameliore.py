"""Photos d'artistes plus nettes (19/10/2026 : « la photo d'Innoss'B était tellement floue qu'on ne voyait rien »).

Les portraits officiels sont parfois petits (Deezer plafonne à 1 200 px, certains portraits Apple à 800 px) alors que
nos images font 2 160 px de large. Sous 1 600 px, la photo est agrandie ×4 par Real-ESRGAN (version légère, modèle ONNX, licence BSD,
onnxruntime déjà présent pour le détourage), puis une légère retouche
(netteté, contraste). Le visage n'est pas réinventé : Real-ESRGAN restaure les détails, il ne dessine pas une autre
personne. Chaque résultat est gardé dans le Blob (media/ameliorees/) : calculé une seule fois par photo.
"""
import hashlib
import io
import os
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageEnhance, ImageFilter

from core.services.platforms import log_write

# realesr-general-x4v3 (version légère de Real-ESRGAN, 5 Mo, fp16) : ~25 s par photo sur processeur, contre ~5 min pour
# RealESRGAN_x4plus, pour une netteté presque identique (essai sur Innoss'B, 19/10/2026)
MODELE = Path(os.path.expanduser("~/.u2net")) / "realesr-leger.onnx"
URL_MODELE = "https://huggingface.co/James040/realesrganfp16-onnx-5mb/resolve/main/onnx/model.onnx"
DEBRUITAGE = 0.4
SEUIL = 1600          # en dessous, on agrandit
ENTREE_MAX = 540      # côté max avant ×4 (2 160 px en sortie : la largeur de nos images)
_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort
        if not MODELE.is_file():
            MODELE.parent.mkdir(parents=True, exist_ok=True)
            r = requests.get(URL_MODELE, timeout=300)
            r.raise_for_status()
            MODELE.write_bytes(r.content)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = os.cpu_count() or 4
        _SESSION = ort.InferenceSession(str(MODELE), sess_options=opts, providers=["CPUExecutionProvider"])
    return _SESSION


def _x4(im: Image.Image) -> Image.Image:
    """Agrandissement ×4 de l'image entière (le modèle léger accepte toutes les tailles)."""
    s = _session()
    a = (np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0).transpose(2, 0, 1)[None].astype(np.float16)
    r = s.run(None, {"input": a, "denoise_strength": np.array([DEBRUITAGE], dtype=np.float16)})[0][0]
    return Image.fromarray((np.clip(r.astype(np.float32).transpose(1, 2, 0), 0, 1) * 255).round().astype(np.uint8))


def _retouche(im: Image.Image) -> Image.Image:
    """Légère retouche : netteté fine et un peu de contraste (jamais d'effet « peau plastique »)."""
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2))
    return ImageEnhance.Contrast(im).enhance(1.04)


def ameliore(im: Image.Image) -> Image.Image:
    """La photo, agrandie si elle est petite et légèrement retouchée ; l'originale si quoi que ce soit échoue."""
    im = im.convert("RGB")
    if min(im.size) >= SEUIL:
        return _retouche(im)
    petit = im.copy(); petit.thumbnail((64, 64))
    cle = hashlib.sha1(petit.tobytes() + str(im.size).encode()).hexdigest()[:24]
    from core import storage
    base = storage.blob_public_url()
    if base:
        try:
            r = requests.get(f"{base}/media/ameliorees/{cle}.jpg", timeout=20)
            if r.ok:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:  # noqa: BLE001
            pass
    try:
        src = im.copy()
        src.thumbnail((ENTREE_MAX, ENTREE_MAX), Image.LANCZOS)
        grand = _retouche(_x4(src))
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"amélioration de photo impossible : {str(exc)[:150]}")
        return im
    try:
        out = io.BytesIO(); grand.save(out, format="JPEG", quality=93)
        storage.store_media("ameliorees", f"{cle}.jpg", out.getvalue(), "image/jpeg")
    except Exception:  # noqa: BLE001
        pass
    return grand
