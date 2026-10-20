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


# ---------------------------------------------------------------- photos validées (banque des couvertures)

def creer_table() -> None:
    from core import db
    db.run("""CREATE TABLE IF NOT EXISTS artist_photos (
        id BIGSERIAL PRIMARY KEY, artist_id BIGINT NOT NULL, fichier VARCHAR(240) NOT NULL, source VARCHAR(40) NOT NULL,
        source_ref VARCHAR(120), credit VARCHAR(300), plan_large BOOLEAN NOT NULL DEFAULT TRUE,
        valide_le TIMESTAMPTZ NOT NULL DEFAULT NOW(), utilise_le TIMESTAMPTZ NULL)""")


def enregistre(artiste: str, chemin: str, video_id: str, seconde: int, coupe_bas: float = 0.0) -> str | None:
    """Range un plan VALIDÉ par un humain : Blob media/artists/plans/, ligne dans artist_photos avec le crédit du clip.
    coupe_bas : part de la hauteur retirée en bas (paroles incrustées dans certains clips)."""
    import io
    import re
    from core import db, storage
    a = db.one("SELECT id, slug FROM artists WHERE lower(name) = lower(?) ORDER BY youtube_subscribers DESC NULLS LAST LIMIT 1", [artiste])
    if not a:
        return None
    creer_table()
    with Image.open(chemin) as im:
        im = im.convert("RGB")
        if coupe_bas:
            im = im.crop((0, 0, im.width, int(im.height * (1 - coupe_bas))))
        out = io.BytesIO(); im.save(out, format="JPEG", quality=94)
    nom = f"{re.sub(r'[^a-z0-9-]', '', a['slug'])}-{video_id}-{seconde:04d}s.jpg"
    storage.store_media("artists/plans", nom, out.getvalue(), "image/jpeg")
    if not db.value("SELECT 1 FROM artist_photos WHERE fichier = ?", [nom]):
        db.insert("artist_photos", {"artist_id": a["id"], "fichier": nom, "source": "clip", "source_ref": video_id,
                                    "credit": f"Image tirée du clip officiel (youtube.com/watch?v={video_id})"})
    return nom


def note_qualite(donnees: bytes, entiere: bool) -> tuple[int, int, float]:
    """(largeur, hauteur, note de 0 à 1) : taille, netteté, cadrage vertical, personne entière (détourable)."""
    import io
    from PIL import Image, ImageFilter, ImageStat
    with Image.open(io.BytesIO(donnees)) as im:
        w, h = im.size
        g = im.convert("L"); g.thumbnail((600, 600))
        nettete = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).stddev[0]
    taille = min(1.0, min(w, h) / 1600)
    nette = min(1.0, nettete / 45)
    verticale = 1.0 if h >= w else 0.55
    return w, h, round(0.4 * taille + 0.3 * nette + 0.2 * verticale + (0.1 if entiere else 0), 3)


def colonnes() -> None:
    from core import db
    for col in ("note TEXT", "largeur INT", "hauteur INT", "score REAL"):
        db.run(f"ALTER TABLE artist_photos ADD COLUMN IF NOT EXISTS {col}")


def photo_large(artist_id: int, detourable: bool = False) -> str | None:
    """URL publique de la MEILLEURE photo de l'artiste pour ce post : parmi celles non utilisées ces 7 derniers jours,
    la mieux notée (taille, netteté, cadrage) ; sinon la moins récemment utilisée. detourable : seulement les photos où
    la personne est entière (plan_large) — un décor chargé (trône) reste pour le plein cadre."""
    from core import db, storage
    try:
        r = db.one("SELECT id, fichier FROM artist_photos WHERE artist_id = ?" + (" AND plan_large" if detourable else "")
                   + """ ORDER BY (utilise_le IS NULL OR utilise_le < NOW() - INTERVAL '7 days') DESC,
                         COALESCE(score, 0.5) DESC, utilise_le ASC NULLS FIRST, id LIMIT 1""", [artist_id])
    except Exception:  # noqa: BLE001 — table ou colonnes pas encore créées
        try:
            r = db.one("SELECT id, fichier FROM artist_photos WHERE artist_id = ?" + (" AND plan_large" if detourable else "")
                       + " ORDER BY utilise_le ASC NULLS FIRST, id LIMIT 1", [artist_id])
        except Exception:  # noqa: BLE001
            return None
    if not r:
        return None
    db.run("UPDATE artist_photos SET utilise_le = NOW() WHERE id = ?", [r["id"]])
    return f"{storage.blob_public_url()}/media/artists/plans/{r['fichier']}"
