"""Réglages d'encodage vidéo communs (20/10/2026 : « nos vidéos perdent de leur qualité à l'envoi »).

Instagram et TikTok recompressent tout ce qu'on leur envoie : plus le fichier envoyé est riche, mieux il survit.
On encode donc en haute qualité (CRF 18, jusqu'à 12 Mb/s, profil High 4.2, 30 i/s constantes, image clé toutes les 2 s,
son AAC 192 kb/s en 48 kHz) — ce que recommandent les deux plateformes pour du 1080p.
Telegram refuse les vidéos de plus de 20 Mo envoyées par lien : une copie allégée « <nom>-tg.mp4 » est faite pour lui seul.
"""
import os
import subprocess

TELEGRAM_MAX = 19 * 1024 * 1024

VIDEO_HQ = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-maxrate", "12M", "-bufsize", "24M",
            "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p", "-r", "30", "-g", "60", "-keyint_min", "60"]
AUDIO_HQ = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
FIN = ["-movflags", "+faststart"]


def _ffmpeg() -> str:
    from core.services.social.refrain import ffmpeg
    return ffmpeg()


def duree(chemin: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", chemin],
                       capture_output=True, text=True, timeout=30)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 60.0


def nom_telegram(nom: str) -> str:
    return nom.rsplit(".", 1)[0] + "-tg.mp4"


def nom_tiktok(nom: str) -> str:
    return nom.rsplit(".", 1)[0] + "-tt.mp4"


def copie_tiktok(chemin: str) -> str | None:
    """TikTok (29/10/2026) : une vidéo 4:5 ou 3:4 s'y affiche petite, entre deux bandes. Copie 1080 x 1920 exacte, la vidéo
    en pleine largeur sur son propre fond flouté ; None si elle est déjà en 9:16 ou en cas d'échec."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", chemin], capture_output=True, text=True, timeout=30)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
    except ValueError:
        return None
    if abs(h / w - 16 / 9) < 0.02:
        return None
    sortie = nom_tiktok(chemin)
    filtre = ("[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "boxblur=28:6,eq=brightness=-0.3[fond];[b]scale=1080:-2:flags=lanczos[v];"
              "[fond][v]overlay=0:(H-h)/2,format=yuv420p[o]")
    r = subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", chemin, "-filter_complex", filtre, "-map", "[o]", "-map", "0:a?",
                        *VIDEO_HQ, *AUDIO_HQ, *FIN, sortie], capture_output=True, timeout=900)
    return sortie if r.returncode == 0 and os.path.isfile(sortie) else None


def copie_telegram(chemin: str) -> str | None:
    """Copie sous 19 Mo pour Telegram (débit calculé sur la durée), à côté de l'original ; None si inutile ou impossible."""
    if not os.path.isfile(chemin) or os.path.getsize(chemin) <= TELEGRAM_MAX:
        return None
    sortie = nom_telegram(chemin)
    kbps = max(700, int(TELEGRAM_MAX * 8 / 1024 / max(1.0, duree(chemin)) * 0.92) - 128)
    r = subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", chemin, "-c:v", "libx264", "-preset", "veryfast",
                        "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", *FIN, sortie], capture_output=True, timeout=900)
    return sortie if r.returncode == 0 and os.path.isfile(sortie) else None
