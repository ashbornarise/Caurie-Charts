"""Montage façon CapCut / TikTok Studio (23/11/2026, demande du fondateur).

Des photos (banque, téléphone) et des vidéos (téléphone, liens) mises bout à bout dans l'ordre choisi, une chanson
(lien, fichier, ou le son des vidéos), rendu 9:16, 4:5 ou 1:1 sans texte. Et le « collage » : plusieurs photos en une
seule image. Les gros fichiers du téléphone arrivent en morceaux de 3,5 Mo (limite des requêtes Vercel), recollés ici.
"""
import io
import json
import os
import subprocess
import tempfile

import requests
from PIL import Image, ImageOps

from core import db, storage

DOSSIER = "studio/montage"
FORMATS_M = {"story": (1080, 1920), "feed": (1080, 1350), "carre": (1080, 1080)}
FPS = 30
DUREE_MAX = 90.0
FONDU = 0.4


# ---------------------------------------------------------------- fichiers envoyés par le téléphone

def nom_morceau(job_id: int, nom: str, k: int) -> str:
    return f"{job_id}-{nom}.p{k:03d}"


def importe_morceau(job_id: int, nom: str, k: int, data: bytes) -> None:
    storage.store_media(DOSSIER, nom_morceau(job_id, nom, k), data, "application/octet-stream")


def _url(job_id: int, nom: str, k: int) -> str:
    return f"{storage.blob_public_url()}/media/{DOSSIER}/{nom_morceau(job_id, nom, k)}"


def _recolle(job_id: int, nom: str, parts: int, sortie: str) -> str:
    with open(sortie, "wb") as f:
        for k in range(parts):
            r = requests.get(_url(job_id, nom, k), timeout=120)
            r.raise_for_status()
            f.write(r.content)
    return sortie


# ---------------------------------------------------------------- collage (une image, tout de suite)

GABARITS = ("grille", "cote", "mosaique")


def collage(urls: list[str], gabarit: str = "grille", fmt: str = "feed", marge: int = 0) -> Image.Image:
    """2 à 6 photos en une image : grille régulière, côte à côte (colonnes) ou mosaïque (une grande + les autres).
    Chaque case est recadrée sur le visage. Aucun texte, aucun logo."""
    from core.services.social import couverture2026 as C26
    w, h = FORMATS_M.get(fmt, FORMATS_M["feed"])
    ims = []
    for u in urls[:6]:
        r = requests.get(u, timeout=30)
        r.raise_for_status()
        ims.append(ImageOps.exif_transpose(Image.open(io.BytesIO(r.content))).convert("RGB"))
    if len(ims) < 2:
        raise RuntimeError("choisis au moins 2 photos")
    n = len(ims)
    if gabarit == "cote":
        cases = [(i * w // n, 0, (i + 1) * w // n, h) for i in range(n)]
    elif gabarit == "mosaique":
        haut = int(h * .62)
        reste = n - 1
        cases = [(0, 0, w, haut)] + [(i * w // reste, haut, (i + 1) * w // reste, h) for i in range(reste)]
    else:
        cols = 2 if n <= 4 else 3
        rangs = -(-n // cols)
        cases = []
        for i in range(n):
            r_, c_ = divmod(i, cols)
            dans_rang = min(cols, n - r_ * cols)       # dernier rang incomplet : ses cases s'élargissent
            cases.append((c_ * w // dans_rang, r_ * h // rangs, (c_ + 1) * w // dans_rang, (r_ + 1) * h // rangs))
    toile = Image.new("RGB", (w, h), (255, 255, 255))
    for im, (x0, y0, x1, y1) in zip(ims, cases):
        cw, ch = x1 - x0 - 2 * marge, y1 - y0 - 2 * marge
        case, _ = C26.cadrer(im, cw, ch)
        toile.paste(case, (x0 + marge, y0 + marge))
    return toile


# ---------------------------------------------------------------- vidéo

def _ff() -> str:
    from core.services.social.studio_montage import ffmpeg
    return ffmpeg()


def _run(args: list[str], timeout: int = 600) -> None:
    r = subprocess.run([_ff(), "-y", "-loglevel", "error", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg : " + (r.stderr or "")[-300:])


def _duree(chemin: str) -> float:
    from core.services.social.studio_montage import _duree_fichier
    return float(_duree_fichier(chemin) or 0)


def _est_image(chemin: str) -> bool:
    try:
        with Image.open(chemin) as im:
            im.verify()
        return True
    except Exception:  # noqa: BLE001
        return False


def _source(job_id: int, el: dict, tmp: str, k: int) -> str:
    """Le fichier local d'un élément (photo de la banque, fichier du téléphone ou lien)."""
    if el.get("genre") == "photo":
        r = requests.get(el["url"], timeout=60)
        r.raise_for_status()
        c = os.path.join(tmp, f"src{k}.jpg")
        open(c, "wb").write(r.content)
        return c
    if el.get("genre") == "fichier":
        return _recolle(job_id, el["nom"], int(el["parts"]), os.path.join(tmp, f"src{k}.{el.get('ext') or 'bin'}"))
    from core.services.social.studio_montage import telecharge
    d = os.path.join(tmp, f"lien{k}")
    os.makedirs(d, exist_ok=True)
    chemin, _infos = telecharge(el["lien"], d)
    return chemin


def _segment_photo(src: str, dest: str, w: int, h: int, duree: float, mouvement: bool) -> None:
    from core.services.social import couverture2026 as C26
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    grand, _ = C26.cadrer(im, w * 2, h * 2)                  # recadré sur le visage, en double taille pour un zoom net
    png = dest + ".png"
    grand.save(png)
    n = max(1, int(round(duree * FPS)))
    zoom = f"zoompan=z='min(1+0.10*on/{n},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={w}x{h}:fps={FPS}" if mouvement \
        else f"scale={w}:{h},fps={FPS}"
    _run(["-loop", "1", "-t", f"{duree:.3f}", "-i", png, "-f", "lavfi", "-t", f"{duree:.3f}", "-i", "anullsrc=r=44100:cl=stereo",
          "-vf", zoom + ",setsar=1,format=yuv420p", "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          "-c:a", "aac", "-shortest", dest])


def _segment_video(src: str, dest: str, w: int, h: int, debut: float, duree: float) -> None:
    from core.services.social.studio_montage import _a_du_son
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},setsar=1,format=yuv420p"
    if _a_du_son(src):
        _run(["-ss", f"{debut:.3f}", "-t", f"{duree:.3f}", "-i", src, "-vf", vf, "-af", "aresample=44100,aformat=channel_layouts=stereo",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", dest])
    else:
        _run(["-ss", f"{debut:.3f}", "-t", f"{duree:.3f}", "-i", src, "-f", "lavfi", "-t", f"{duree:.3f}", "-i", "anullsrc=r=44100:cl=stereo",
              "-vf", vf, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-shortest", dest])


def _assemble(segments: list[tuple[str, float]], sortie: str, fondu: bool) -> float:
    """Bout à bout : coupe franche (concat, garde le son des vidéos) ou fondu enchaîné (xfade, image et son)."""
    if len(segments) == 1 or not fondu:
        liste = sortie + ".txt"
        open(liste, "w", encoding="utf-8").write("".join(f"file '{s[0].replace(os.sep, '/')}'\n" for s in segments))
        _run(["-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", sortie])
        return sum(d for _, d in segments)
    args, fv, fa = [], [], []
    for s, _ in segments:
        args += ["-i", s]
    t = segments[0][1]
    pv, pa = "[0:v]", "[0:a]"
    for i in range(1, len(segments)):
        off = t - FONDU
        fv.append(f"{pv}[{i}:v]xfade=transition=fade:duration={FONDU}:offset={off:.3f}[v{i}]")
        fa.append(f"{pa}[{i}:a]acrossfade=d={FONDU}[a{i}]")
        pv, pa = f"[v{i}]", f"[a{i}]"
        t = off + segments[i][1]
    _run([*args, "-filter_complex", ";".join(fv + fa), "-map", pv, "-map", pa, "-c:v", "libx264", "-preset", "veryfast",
          "-crf", "19", "-c:a", "aac", sortie], timeout=900)
    return t


def traite(job_id: int, job: dict, p: dict, maj) -> dict:
    w, h = FORMATS_M.get(p.get("format"), FORMATS_M["story"])
    elements = p.get("elements") or []
    if not elements:
        raise RuntimeError("aucun élément dans le montage")
    with tempfile.TemporaryDirectory(prefix=f"cauri-edit-{job_id}-") as tmp:
        maj(job_id, statut="telechargement", erreur=None)
        segments, total = [], 0.0
        for k, el in enumerate(elements):
            src = _source(job_id, el, tmp, k)
            dest = os.path.join(tmp, f"seg{k:02d}.mp4")
            if _est_image(src):
                d = max(0.8, min(15.0, float(el.get("duree") or p.get("duree_photo") or 2.5)))
                maj(job_id, statut="montage")
                _segment_photo(src, dest, w, h, d, p.get("mouvement", True))
            else:
                longueur = _duree(src) or 10.0
                debut = max(0.0, min(float(el.get("debut") or 0), max(0.0, longueur - 0.5)))
                fin = float(el.get("fin") or 0) or min(longueur, debut + 8.0)
                d = max(0.5, min(fin, longueur) - debut)
                maj(job_id, statut="montage")
                _segment_video(src, dest, w, h, debut, d)
            segments.append((dest, d))
            total += d
            if total >= DUREE_MAX:
                break
        fondu = p.get("transition", "fondu") == "fondu"
        brut = os.path.join(tmp, "brut.mp4")
        duree = _assemble(segments, brut, fondu)
        finale = os.path.join(tmp, "finale.mp4")
        son = p.get("son") or None
        if son:
            el = dict(son)
            el.setdefault("genre", "lien")
            chanson = _source(job_id, el, tmp, 99)
            depart = p.get("son_debut")
            if depart in (None, "", "auto"):
                try:
                    from core.services.social.refrain import refrain
                    depart = refrain(chanson, duree=min(duree, 35.0))[0]
                except Exception:  # noqa: BLE001
                    depart = 0.0
            depart = float(depart or 0)
            fin_fondu = max(0.0, duree - 1.5)
            _run(["-i", brut, "-ss", f"{depart:.3f}", "-i", chanson, "-map", "0:v", "-map", "1:a",
                  "-af", f"atrim=0:{duree:.3f},afade=t=in:d=0.3,afade=t=out:st={fin_fondu:.3f}:d=1.5,loudnorm=I=-14:TP=-1.5:LRA=11",
                  "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", finale], timeout=900)
            p["son_debut_utilise"] = round(depart, 1)
        elif p.get("garder_son", True):
            _run(["-i", brut, "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
                  "-movflags", "+faststart", finale])
        else:
            _run(["-i", brut, "-c:v", "copy", "-an", "-movflags", "+faststart", finale])
        vignette = os.path.join(tmp, "vignette.jpg")
        _run(["-ss", "0.5", "-i", finale, "-frames:v", "1", "-q:v", "3", vignette])
        nom = f"studio-montage-{job_id}-{os.urandom(2).hex()}"
        storage.store_media("social", nom + ".mp4", open(finale, "rb").read(), "video/mp4")
        storage.store_media("social", nom + ".jpg", open(vignette, "rb").read(), "image/jpeg")
        p["duree_finale"] = round(duree, 1)
        maj(job_id, statut="pret", video=nom + ".mp4", vignette=nom + ".jpg", params=p)
    return {"statut": "pret", "video": nom + ".mp4"}


def nouveau(params: dict, auteur: int) -> int:
    return db.insert("studio_jobs", {"lien": "montage", "params": json.dumps(params, ensure_ascii=False), "auteur": auteur,
                                     "statut": "telechargement"})
