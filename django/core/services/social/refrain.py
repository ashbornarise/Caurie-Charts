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
