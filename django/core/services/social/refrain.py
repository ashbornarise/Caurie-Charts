"""Clips au refrain : extrait vidéo 9:16 (30 à 45 s) du clip officiel d'un titre, coupé sur son refrain, habillé Cauri.

Décision du fondateur (16/10/2026) : les vidéos marchent bien mieux que les images (TikTok publié avec son :
2 357 vues sur 12 posts, contre 27 vues pour 18 carrousels Instagram) ; on découpe donc les clips officiels.
Garde-fous : seulement le clip OFFICIEL de l'artiste (track_platform_ids.kind = 'clip', is_official = 1), un extrait
court, la source citée sur l'image et dans la légende, et une liste noire (conf « social.refrain.exclus ») pour retirer
tout de suite un artiste ou un label qui le demande. Les clips téléchargés ne sont pas gardés : seul l'extrait l'est.

Refrain : la partie à la fois la plus forte et la plus répétée du morceau (matrice d'autosimilarité de l'empreinte
spectrale, calculée avec numpy). Téléchargement : yt-dlp (avec Node pour le JavaScript de YouTube) ; sur un poste
de travail, les serveurs de GitHub étant souvent bloqués par YouTube."""
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core import conf, db, env
from core.services.platforms import log_write

W, H = 1080, 1920
FONTS = Path(__file__).resolve().parents[4] / "resources" / "fonts"


def ffmpeg() -> str:
    return env.get("FFMPEG_PATH", "") or shutil.which("ffmpeg") or "ffmpeg"


def exclus() -> set:
    return {x.lower() for x in (conf.get("social.refrain.exclus") or [])}


def clip_officiel(track_id: int) -> dict | None:
    """Le clip officiel d'un titre (pas l'audio, les paroles ni le live)."""
    return db.one("""SELECT tpi.external_id, t.title, a.name AS artist, a.label_owner FROM track_platform_ids tpi
                     JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id
                     WHERE tpi.track_id = ? AND tpi.platform = 'youtube' AND tpi.is_official = 1 AND tpi.kind = 'clip'
                     ORDER BY tpi.published_at NULLS LAST LIMIT 1""", [track_id])


def telecharge(video_id: str, dossier: str) -> str | None:
    """Clip en 1080p au plus (mp4), dans un dossier temporaire."""
    out = os.path.join(dossier, f"{video_id}.mp4")
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-playlist", "-q", "--no-warnings",
           "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]", "--merge-output-format", "mp4",
           "-o", out, f"https://www.youtube.com/watch?v={video_id}"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "error", f"clip {video_id} non téléchargé : {str(exc)[:300]}")
        return None
    return out if os.path.isfile(out) else None


# ---------------------------------------------------------------- détection du refrain

def _audio(path: str, sr: int = 11025) -> np.ndarray:
    r = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True, timeout=300, check=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def refrain(path: str, duree: float = 35.0, sr: int = 11025, pas: float = 0.5) -> tuple[float, float]:
    """(début, fin) du refrain : fenêtre de « duree » secondes la plus forte et la plus répétée ailleurs dans le titre."""
    y = _audio(path, sr)
    total = len(y) / sr
    if total <= duree + 10:
        return 0.0, min(total, duree)
    hop, win = int(pas * sr), 4096
    n = (len(y) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(y[idx] * np.hanning(win), axis=1))
    # Empreinte : 12 classes de hauteur (chroma) + 6 bandes d'énergie, normalisée image par image
    freqs = np.fft.rfftfreq(win, 1 / sr)
    ok = (freqs > 60) & (freqs < 4000)
    pitch = np.round(12 * np.log2(freqs[ok] / 440.0)).astype(int) % 12
    chroma = np.zeros((n, 12))
    for k in range(12):
        chroma[:, k] = spec[:, ok][:, pitch == k].sum(axis=1)
    bandes = np.stack([spec[:, (freqs >= a) & (freqs < b)].sum(axis=1) for a, b in
                       ((20, 150), (150, 400), (400, 1000), (1000, 2500), (2500, 4000), (4000, 5500))], axis=1)
    f = np.concatenate([chroma, np.log1p(bandes)], axis=1)
    f = f / (np.linalg.norm(f, axis=1, keepdims=True) + 1e-9)
    sim = f @ f.T
    rms = np.sqrt((y[idx] ** 2).mean(axis=1))
    L = int(duree / pas)
    debut_min, fin_max = int(12 / pas), n - L - int(5 / pas)   # ni l'intro ni le générique de fin
    if fin_max <= debut_min:
        return 0.0, min(total, duree)
    # Répétition : pour chaque fenêtre, meilleure ressemblance moyenne (sur une diagonale de la matrice) avec une autre
    # partie du titre décalée d'au moins 15 s — moyennes glissantes par sommes cumulées, sans boucle sur les fenêtres
    rep = np.zeros(n)
    for lag in range(int(15 / pas), n - L):
        diag = np.diagonal(sim, lag)
        cs = np.concatenate([[0.0], np.cumsum(diag)])
        m = (cs[L:] - cs[:-L]) / L                       # m[i] : fenêtre i comparée à la fenêtre i + lag
        rep[: len(m)] = np.maximum(rep[: len(m)], m)
        rep[lag: lag + len(m)] = np.maximum(rep[lag: lag + len(m)], m)
    energie = np.convolve(rms, np.ones(L) / L, mode="valid")
    t_ = np.arange(debut_min, fin_max)
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9)  # noqa: E731
    note = z(rep[t_]) + 0.8 * z(energie[t_])
    t = int(t_[int(np.argmax(note))])
    debut = max(0.0, t * pas - 1.0)   # une seconde avant : on entre dans le refrain, on ne le coupe pas
    return round(debut, 2), round(min(total, debut + duree), 2)


# ---------------------------------------------------------------- habillage

def _font(nom: str, taille: int):
    try:
        return ImageFont.truetype(str(FONTS / nom), taille)
    except OSError:
        return ImageFont.load_default()


def _lignes(d, texte, police, largeur):
    mots, lignes, cur = texte.split(), [], ""
    for m in mots:
        essai = (cur + " " + m).strip()
        if d.textlength(essai, font=police) <= largeur:
            cur = essai
        else:
            lignes.append(cur); cur = m
    return lignes + [cur] if cur else lignes


def calque(haut: str, titre: str, artiste: str, chiffre: str, credit: str) -> Image.Image:
    """Calque transparent 1080 × 1920. Tout le texte utile est au-dessus de la vidéo ou juste sous elle : le bas de l'écran
    (légende et boutons de TikTok, Reels) reste libre."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((64, 140), f"CAURI CHARTS  ·  {haut.upper()}", font=_font("Poppins-Bold.ttf", 32), fill=(190, 175, 255, 255))
    import re
    titre = re.sub(r"\s*\([^)]*[^\x00-\xff][^)]*\)", "", titre)   # « (Nsesaeɛ Kɛseɛ) » : caractères absents des polices
    y = 196
    lignes = _lignes(d, titre, _font("Anton-Regular.ttf", 96), W - 128)
    taille = 96 if len(lignes) <= 2 else 74
    for l in _lignes(d, titre, _font("Anton-Regular.ttf", taille), W - 128)[:2]:
        d.text((64, y), l, font=_font("Anton-Regular.ttf", taille), fill=(255, 255, 255, 255))
        y += taille + 8
    d.text((64, y + 16), artiste, font=_font("Poppins-Bold.ttf", 42), fill=(255, 255, 255, 215))
    if chiffre:
        d.text((64, 1492), chiffre, font=_font("Anton-Regular.ttf", 66), fill=(90, 225, 150, 255))
    d.text((64, 1576), credit, font=_font("Poppins-Regular.ttf", 28), fill=(255, 255, 255, 185))
    return img


def vignette(video: str, out: str, t: float = 4.0) -> str | None:
    """Image de couverture du post vidéo (Telegram, aperçus) : une image prise dans l'extrait."""
    try:
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-q:v", "3", out],
                       capture_output=True, timeout=120, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out


def monte(clip: str, debut: float, fin: float, calque_png: str, out: str) -> str | None:
    """Vidéo 9:16 : fond = clip agrandi et flouté, clip entier au centre, calque par-dessus ; son du clip, fondus."""
    duree = fin - debut
    filtre = (f"[0:v]split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:2,"
              f"eq=brightness=-0.18,scale={W}:{H}[fond];[b]scale=-2:1000,crop={W}:1000[clip];[fond][clip]overlay=0:470[v0];"
              f"[v0][1:v]overlay=0:0,fps=30,format=yuv420p,fade=t=in:d=0.4,fade=t=out:st={max(0, duree - 0.6):.2f}:d=0.6[v];"
              f"[0:a]afade=t=in:d=0.5,afade=t=out:st={max(0, duree - 1.2):.2f}:d=1.2,loudnorm=I=-14:TP=-1.5[a]")
    cmd = [ffmpeg(), "-y", "-v", "error", "-ss", f"{debut:.2f}", "-t", f"{duree:.2f}", "-i", clip, "-loop", "1", "-t", f"{duree:.2f}",
           "-i", calque_png, "-filter_complex", filtre, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "23", "-maxrate", "4M", "-bufsize", "8M", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", out]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "error", f"montage du refrain : {str(exc)[:300]}")
        return None
    return out if os.path.isfile(out) else None


def _pochette(url: str | None, tmp: str) -> str | None:
    """Image 2160 × 3840 : pochette en grand au centre, fond = la même pochette agrandie, floutée et assombrie."""
    if not url:
        return None
    from core.services.news import http_get
    try:
        hd = re.sub(r"/\d+x\d+bb\.", "/1400x1400bb.", url)   # Apple Music : la plus grande taille disponible
        im = Image.open(__import__("io").BytesIO(http_get(hd, binary=True) or http_get(url, binary=True))).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    cote = H * 2   # fond : la pochette agrandie à la hauteur de l'écran, recadrée au centre en largeur
    fond = im.resize((cote, cote), Image.LANCZOS).crop(((cote - W * 2) // 2, 0, (cote + W * 2) // 2, cote))
    fond = fond.filter(ImageFilter.GaussianBlur(60)).point(lambda v: int(v * 0.45))
    c = int(W * 2 * 0.82)
    fond.paste(im.resize((c, c), Image.LANCZOS), ((W * 2 - c) // 2, int(H * 2 * 0.30)))
    p = os.path.join(tmp, "pochette.jpg")
    fond.save(p, quality=92)
    return p


CONCERT_S = 6.0


def _concert(artiste: str, tmp: str) -> dict | None:
    """6 s d'un concert de l'artiste sous licence libre (medias.videos_concert), au moment le plus animé (énergie du son :
    foule, refrain repris par le public), recadrées en 9:16 et SANS son."""
    from core.services.social import medias
    for v in medias.videos_concert(artiste, 2):
        src = telecharge(v["id"], tmp)
        if not src:
            continue
        try:
            y = _audio(src, 8000)
            pas = 8000 // 2
            rms = np.sqrt(np.convolve(y ** 2, np.ones(pas) / pas, mode="valid")[::pas])     # énergie par demi-seconde
            fen = int(CONCERT_S * 2)
            moy = np.convolve(rms, np.ones(fen) / fen, mode="valid")
            debut = 15 * 2 + int(np.argmax(moy[30:])) if len(moy) > 40 else 0
            out = os.path.join(tmp, "concert.mp4")
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-ss", f"{debut / 2:.1f}", "-t", f"{CONCERT_S}", "-i", src, "-an",
                            "-vf", f"scale=-2:{H},crop={W}:{H},fps=30,eq=brightness=-0.05", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "20", out], capture_output=True, timeout=300, check=True)
            return {"file": out, "credit": v["credit"]}
        except Exception as exc:  # noqa: BLE001 — sans ouverture de concert, la vidéo reste faite de photos
            log_write("social", "warning", f"concert {artiste} : {str(exc)[:200]}")
    return None


def maison(track_id: int, haut: str, chiffre: str, out: str, par_photo: float = 4.0, n_photos: int = 4) -> dict | None:
    """Vidéo maison 9:16 SANS image ni son de label (décision du 17/10/2026, après le blocage d'UMG sur Instagram) :
    photos libres (Openverse, crédit du photographe) et photo de notre base, en lent zoom, avec l'habillage Cauri.
    Muette : le son officiel s'ajoute dans l'application (bibliothèque sous licence), au refrain."""
    from core.services.social import medias
    t = db.one("""SELECT t.title, t.cover_url, a.name AS artist, COALESCE(NULLIF(a.image_hd_url, ''), a.image_url) AS photo,
                         a.image_credit FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE t.id = ?""", [track_id])
    if not t:
        return None
    images = [(s["url"], s["credit"]) for s in medias.scenes_libres(t["artist"], 8)]
    if t["photo"]:
        images.insert(1 if images else 0, (t["photo"], t.get("image_credit")))
    images = images[:n_photos]
    if not images:
        return None
    from core.services.news import http_get
    with tempfile.TemporaryDirectory(prefix="cauri-maison-") as tmp:
        fichiers, credits = [], []
        for i, (url, credit) in enumerate(images):
            try:
                im = Image.open(__import__("io").BytesIO(http_get(url, binary=True))).convert("RGB")
            except Exception:  # noqa: BLE001 — image illisible : on passe à la suivante
                continue
            # cadrage 9:16 centré sur le haut de l'image (les visages), 2× la taille finale pour un zoom net
            w, h = im.size
            cible = 9 / 16
            if w / h > cible:
                nw = int(h * cible); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
            else:
                nh = int(w / cible); im = im.crop((0, 0, w, min(h, nh)))
            p = os.path.join(tmp, f"p{i}.jpg"); im.resize((W * 2, H * 2), Image.LANCZOS).save(p, quality=92)
            fichiers.append(p)
            if credit:
                credits.append(credit)
        if not fichiers:
            return None
        # La pochette de la chanson, entière au centre sur son propre fond flou (jamais recadrée) : en 2e position
        pochette = _pochette(t.get("cover_url"), tmp)
        if pochette:
            fichiers.insert(min(1, len(fichiers)), pochette)
        while len(fichiers) < 3:   # une ou deux photos seulement : on les reprend avec d'autres mouvements (≥ 12 s)
            fichiers.append(fichiers[len(fichiers) % max(1, len(fichiers))])
        png = os.path.join(tmp, "calque.png")
        c = calque(haut, t["title"], t["artist"], chiffre, "Photos : voir la légende")
        # Dégradés sombres derrière les textes : lisibles sur toutes les photos
        ombre = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ombre)
        for y in range(0, 620):
            od.line([(0, y), (W, y)], fill=(0, 0, 0, int(190 * (1 - y / 620))))
        for y in range(1380, 1700):
            od.line([(0, y), (W, y)], fill=(0, 0, 0, int(170 * min(1, (y - 1380) / 120, (1700 - y) / 120))))
        Image.alpha_composite(ombre, c).save(png)
        frames = int(par_photo * 30)
        args, filtres = [], []
        # Ouverture : 6 s d'ambiance d'un concert sous licence libre (chaîne officielle), sans son, si on en trouve
        concert = _concert(t["artist"], tmp)
        if concert:
            args += ["-i", concert["file"]]
            credits.insert(0, concert["credit"])
        o = 1 if concert else 0
        for i, p in enumerate(fichiers):
            args += ["-i", p]   # une seule image : zoompan en tire d images (par_photo secondes)
            zoom, x = [("min(zoom+0.0012,1.15)", "iw/2-(iw/zoom/2)"), ("if(eq(on,1),1.15,max(zoom-0.0012,1))", "iw/2-(iw/zoom/2)"),
                       ("1.12", "(iw-iw/zoom)*on/" + str(frames))][i % 3]   # zoom avant, zoom arrière, panoramique
            filtres.append(f"[{i + o}:v]zoompan=z='{zoom}':d={frames}:x='{x}':y='ih/3-(ih/zoom/3)':s={W}x{H}:fps=30,"
                           f"eq=brightness=-0.06,setsar=1,fade=t=in:d=0.25[p{i}]")
        n = len(fichiers)
        duree = par_photo * n + (CONCERT_S if concert else 0)
        tete = "[0:v]fps=30,setsar=1[cc];[cc]" if concert else ""
        filtres.append(tete + "".join(f"[p{i}]" for i in range(n)) + f"concat=n={n + o}:v=1:a=0[film]")
        filtres.append(f"[film][{n + o}:v]overlay=0:0,format=yuv420p[v]")
        args += ["-loop", "1", "-t", f"{duree}", "-i", png, "-f", "lavfi", "-t", f"{duree}", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd = [ffmpeg(), "-y", "-v", "error", *args, "-filter_complex", ";".join(filtres), "-map", "[v]", "-map", f"{n + o + 1}:a",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", out]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            log_write("social", "error", f"vidéo maison : {str(exc)[:300]}")
            return None
    return {"file": out, "title": t["title"], "artist": t["artist"], "credits": " · ".join(dict.fromkeys(credits))}


def extrait(track_id: int, haut: str, chiffre: str, out: str, duree: float = 35.0) -> dict | None:
    """Du titre à la vidéo finie : clip officiel → refrain → montage habillé. Rien n'est gardé du clip complet."""
    c = clip_officiel(track_id)
    if not c or c["artist"].lower() in exclus() or (c.get("label_owner") or "").lower() in exclus():
        return None
    with tempfile.TemporaryDirectory(prefix="cauri-clip-") as tmp:
        src = telecharge(c["external_id"], tmp)
        if not src:
            return None
        debut, fin = refrain(src, duree)
        png = os.path.join(tmp, "calque.png")
        calque(haut, c["title"], c["artist"], chiffre, "Extrait du clip officiel · YouTube").save(png)
        if not monte(src, debut, fin, png, out):
            return None
    return {"file": out, "video_id": c["external_id"], "debut": debut, "fin": fin, "title": c["title"], "artist": c["artist"],
            "source": f"https://www.youtube.com/watch?v={c['external_id']}"}
