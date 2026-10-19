"""Plans larges d'artistes tirés de leurs clips officiels (décision du 19/10/2026).

Les photos d'Apple Music / Spotify sont des portraits serrés : détourés, ils sont coupés sur les côtés. Ici on prend
une image toutes les 2 s du clip officiel (sans le son), et on garde les plans nets où UNE personne est entière dans le
cadre (ni coupée sur les côtés, ni la tête coupée). Un clip montre aussi des danseurs et des invités : chaque plan
est proposé à la validation humaine avant de servir (règle « réel uniquement »).
"""
import glob
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageFilter, ImageStat

from core.services.platforms import log_write
from core.services.social.refrain import ffmpeg

PAS = 2.0          # une image toutes les 2 s
ECART = 8.0        # deux plans gardés sont séparés d'au moins 8 s (variété)


def _video(video_id: str, dossier: str) -> str | None:
    """Image seule du clip (pas de son : rien à reconnaître pour Content ID), 1080p au plus."""
    out = os.path.join(dossier, f"{video_id}.mp4")
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-playlist", "-q", "--no-warnings",
           "-f", "bv*[height<=1080][ext=mp4]/bv*[height<=1080]", "-o", out, f"https://www.youtube.com/watch?v={video_id}"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "error", f"plans {video_id} : {str(exc)[:200]}")
        return None
    return out if os.path.isfile(out) else None


def _note(im: Image.Image, session) -> float | None:
    """Note d'un plan, ou None s'il ne convient pas (personne coupée, absente, trop petite, flou, trop sombre)."""
    from rembg import remove
    petit = im.copy(); petit.thumbnail((320, 320))
    masque = remove(petit, session=session, only_mask=True).point(lambda v: 255 if v > 128 else 0)
    w, h = masque.size
    surface = ImageStat.Stat(masque).mean[0] / 255
    if not 0.06 <= surface <= 0.55:
        return None
    bord = max(2, w // 50)
    gauche = ImageStat.Stat(masque.crop((0, 0, bord, h))).mean[0] / 255
    droite = ImageStat.Stat(masque.crop((w - bord, 0, w, h))).mean[0] / 255
    haut = ImageStat.Stat(masque.crop((0, 0, w, max(2, h // 40)))).mean[0] / 255
    if gauche > 0.02 or droite > 0.02 or haut > 0.02:      # coupé sur un côté ou la tête coupée
        return None
    gris = petit.convert("L")
    lum = ImageStat.Stat(gris).mean[0]
    if lum < 35:
        return None
    nettete = ImageStat.Stat(gris.filter(ImageFilter.FIND_EDGES)).stddev[0]
    bb = masque.getbbox()
    centre = 1 - abs(((bb[0] + bb[2]) / 2) / w - 0.5) if bb else 0.5
    return nettete * (0.6 + 0.4 * centre) * (0.7 + surface)


def candidats(video_id: str, dossier_sortie: str, n: int = 6) -> list[str]:
    """Les n meilleurs plans larges du clip, en JPEG pleine taille dans dossier_sortie."""
    from rembg import new_session
    session = new_session("u2net_human_seg")
    os.makedirs(dossier_sortie, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cauri-plans-") as tmp:
        video = _video(video_id, tmp)
        if not video:
            return []
        subprocess.run([ffmpeg(), "-v", "error", "-i", video, "-vf", f"fps=1/{PAS}", "-q:v", "2",
                        os.path.join(tmp, "f%04d.jpg")], capture_output=True, timeout=900)
        notes = []
        for f in sorted(glob.glob(os.path.join(tmp, "f*.jpg"))):
            t = (int(os.path.basename(f)[1:5]) - 1) * PAS
            try:
                with Image.open(f) as im:
                    note = _note(im.convert("RGB"), session)
            except Exception:  # noqa: BLE001
                continue
            if note:
                notes.append((note, t, f))
        gardes = []
        for note, t, f in sorted(notes, reverse=True):
            if all(abs(t - t2) >= ECART for _, t2, _ in gardes):
                gardes.append((note, t, f))
            if len(gardes) >= n:
                break
        sortie = []
        for _, t, f in sorted(gardes, key=lambda g: g[1]):
            nom = os.path.join(dossier_sortie, f"{video_id}-{int(t):04d}s.jpg")
            with Image.open(f) as im:
                im.save(nom, quality=94)
            sortie.append(nom)
        return sortie
