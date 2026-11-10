"""Cauri Studio — moteur : téléchargement, analyse (description automatique) et montage d'une vidéo republiée.

Appelé par `manage.py studio_job --id N` (GitHub Actions, ou le PC si une plateforme bloque les serveurs).
Habillage au style 2026 (logo rond, étiquette, accroche avec le nom surligné, crédit de la source), son normalisé.
Jamais de manipulation destinée à tromper la détection des droits (miroir, accélération, hauteur, filigrane retiré).
"""
import base64
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import requests
from PIL import Image, ImageDraw

from core import db, env, storage
from core.services.platforms import log_write

FORMATS = {"origine": None, "story": (1080, 1920), "feed": (1080, 1350), "square": (1080, 1080)}


def _verifie_en_ligne(nom: str) -> None:
    """La vidéo doit être lisible sur le Blob avant d'être dite « prête » (sinon : erreur, et on peut recommencer)."""
    import requests
    from core import storage
    base = storage.blob_public_url()
    if not base:
        return
    for _ in range(3):
        try:
            if requests.head(f"{base}/media/social/{nom}", timeout=20).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    raise RuntimeError("la vidéo n'a pas pu être mise en ligne : recommence")


def _source_basse(video: str, infos: dict) -> str | None:
    """« 720 × 1280 » si la source fait moins de 1000 px sur son petit côté (720p ou moins), sinon None."""
    w, h = infos.get("width") or 0, infos.get("height") or 0
    if not (w and h):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", video], capture_output=True, text=True, timeout=30)
        try:
            w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        except ValueError:
            return None
    return f"{w} × {h}" if min(w, h) < 1000 else None


def taille_origine(infos: dict, video: str) -> tuple[int, int]:
    """1080 de large, la hauteur selon les proportions de la vidéo d'origine (paire) ; vidéo horizontale : cadre 4:5."""
    w, h = infos.get("width") or 0, infos.get("height") or 0
    if not (w and h):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", video], capture_output=True, text=True, timeout=30)
        try:
            w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        except ValueError:
            w, h = 1080, 1920
    H = int(round(1080 * h / w / 2) * 2)
    # Vidéo horizontale (moins de 960 px de haut une fois à 1080 de large) : Facebook refuse les Reels de moins de 960 px
    # (post 203, 20/10/2026) -> cadre 4:5, la vidéo en pleine largeur au centre, fond flouté
    if H < 960:
        return 1080, 1350
    return 1080, min(1920, H)
MAX_DUREE = 90


class TacheAnnulee(Exception):
    """Le fondateur a annulé la tâche dans le Studio : le montage s'arrête à l'étape suivante (25/10/2026)."""


def _maj(job_id: int, **champs) -> None:
    # Annulation réelle : chaque étape vérifie d'abord que la tâche n'a pas été annulée ; elle ne repasse jamais « prête »
    if db.value("SELECT statut FROM studio_jobs WHERE id = ?", [job_id]) == "annule":
        raise TacheAnnulee(job_id)
    if "params" in champs and not isinstance(champs["params"], str):
        champs["params"] = json.dumps(champs["params"], ensure_ascii=False)
    db.update("studio_jobs", champs, "id = :id", {"id": job_id})


def ffmpeg() -> str:
    from core.services.social.refrain import ffmpeg as f
    return f()


# ---------------------------------------------------------------- téléchargement

def telecharge(lien: str, dossier: str) -> tuple[str, dict]:
    """(fichier mp4 avec le son, infos yt-dlp) ; lève RuntimeError avec un message clair en français."""
    sortie = os.path.join(dossier, "source.%(ext)s")
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-playlist", "--no-warnings",
           # 07/11/2026 : « res » = le plus petit côté ; [height<=1080] excluait le 1080p VERTICAL (1080 x 1920) et le Studio
           # prenait le 540 x 960 des reels
           "-f", "bv*+ba/b", "-S", "res:1080,br",
           "--merge-output-format", "mp4", "--write-info-json", "-o", sortie, lien]
    if re.search(r"tiktok\.com", lien, re.I):
        # TikTok refuse les serveurs (« Unexpected response from webpage request ») : on se présente comme Chrome (curl_cffi)
        cmd[3:3] = ["--impersonate", "chrome"]
    for essai in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        fichiers = [f for f in glob.glob(os.path.join(dossier, "source.*")) if not f.endswith(".json")]
        # 08/11/2026 : « unable to download video data: HTTP Error 404 » = raté passager des serveurs vidéo de YouTube
        # (le même lien passait au tour suivant) -> on redemande l'adresse du fichier au bout de quelques secondes
        if (r.returncode == 0 and fichiers) or essai == 2 or not re.search(r"HTTP Error (404|403|5\d\d)|timed out", r.stderr or "", re.I):
            break
        for f in glob.glob(os.path.join(dossier, "source.*")):
            os.remove(f)
        time.sleep(10 * (essai + 1))
    if r.returncode != 0 or not fichiers:
        msg = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["erreur inconnue"]
        texte = msg[0]
        if re.search(r"not a bot", texte, re.I):
            texte = ("YouTube bloque un moment les téléchargements depuis cette connexion. Réessaie plus tard. "
                     "Détail : " + texte)
        elif re.search(r"login|cookies|rate-limit|Sign in|private", texte, re.I):
            texte = ("La plateforme refuse le téléchargement depuis le serveur (connexion exigée). Lance la fabrication "
                     "depuis le PC : python manage.py studio_job --id <numéro>. Détail : " + texte)
        elif re.search(r"HTTP Error", texte):
            texte = "La plateforme n'a pas donné le fichier vidéo (3 essais). Relance dans quelques minutes. Détail : " + texte
        raise RuntimeError(texte[:400])
    infos = {}
    for j in glob.glob(os.path.join(dossier, "source*.info.json")):
        try:
            infos = json.load(open(j, encoding="utf-8"))
        except ValueError:
            pass
    return fichiers[0], infos


TRANSITION = 0.5   # fondu enchaîné entre deux passages du résumé (secondes)


def _duree_fichier(video: str) -> float:
    try:
        ff = ffmpeg()
        sonde = os.path.join(os.path.dirname(ff), os.path.basename(ff).replace("ffmpeg", "ffprobe")) if os.path.dirname(ff) else "ffprobe"
        r = subprocess.run([sonde, "-v", "error",
                            "-show_entries", "format=duration", "-of", "csv=p=0", video], capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def moments_forts(video: str, total: float, longueur: float) -> list[tuple[float, float]]:
    """Découpe la vidéo en n fenêtres régulières (5 % à 95 % de sa durée) et garde dans chacune le passage le plus
    énergique (volume sonore moyen le plus haut : parole animée, refrain, foule). Renvoie [(début, durée)]."""
    import numpy as np
    n = max(3, min(8, round(total / 9)))
    seg = (total + (n - 1) * TRANSITION) / n
    try:
        brut = subprocess.run([ffmpeg(), "-v", "error", "-i", video, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                              capture_output=True, timeout=600).stdout
        a = np.frombuffer(brut, np.int16).astype(np.float32)
        pas = 4000   # 0,5 s
        rms = np.array([np.sqrt(np.mean(a[i:i + pas] ** 2)) for i in range(0, len(a) - pas, pas)]) if len(a) > pas else np.zeros(1)
    except (OSError, subprocess.SubprocessError, ValueError):
        rms = np.zeros(1)
    lo, hi = longueur * .05, longueur * .95 - seg
    largeur = (hi - lo) / n
    out = []
    for k in range(n):
        g, d = lo + k * largeur, lo + (k + 1) * largeur
        meilleur, score = g, -1.0
        t = g
        while t <= max(g, d - seg * .5):
            i0, i1 = int(t * 2), int((t + seg) * 2)
            s = float(rms[i0:i1].mean()) if i1 <= len(rms) and i1 > i0 else 0.0
            if s > score:
                meilleur, score = t, s
            t += 1.0
        out.append((round(max(0.0, meilleur), 2), round(seg, 2)))
    return out


def resume_video(source: str, total: float, longueur: float, dossier: str) -> str:
    """Enchaîne les moments forts avec des fondus simples (image et son) : une seule vidéo de `total` secondes."""
    parts = moments_forts(source, total, longueur)
    args = [ffmpeg(), "-y", "-v", "error"]
    for d, s in parts:
        args += ["-ss", f"{d:.2f}", "-t", f"{s:.2f}", "-i", source]
    f, v, a, decal = [], "v0", "a0", parts[0][1]
    for i in range(len(parts)):
        f.append(f"[{i}:v]scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{i}]")
        f.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
    for i in range(1, len(parts)):
        f.append(f"[{v}][v{i}]xfade=transition=fade:duration={TRANSITION}:offset={decal - TRANSITION:.2f}[x{i}]")
        f.append(f"[{a}][a{i}]acrossfade=d={TRANSITION}[y{i}]")
        v, a = f"x{i}", f"y{i}"
        decal += parts[i][1] - TRANSITION
    sortie = os.path.join(dossier, "resume.mp4")
    subprocess.run(args + ["-filter_complex", ";".join(f), "-map", f"[{v}]", "-map", f"[{a}]", "-c:v", "libx264", "-crf", "18",
                           "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", sortie], check=True, capture_output=True, timeout=1500)
    return sortie


def credit_auto(infos: dict) -> str:
    """« @compte sur TikTok » à partir des infos yt-dlp."""
    compte = infos.get("uploader") or infos.get("channel") or infos.get("uploader_id") or ""
    plateforme = (infos.get("extractor_key") or infos.get("extractor") or "").replace("IE", "").split(":")[0]
    if compte and not compte.startswith("@") and plateforme.lower() in ("tiktok", "instagram", "twitter"):
        compte = "@" + compte
    return f"{compte} sur {plateforme}".strip() if compte else plateforme


def images_cles(video: str, dossier: str, debut: float, fin: float, n: int = 4) -> list[str]:
    out = []
    for k in range(n):
        t = debut + (fin - debut) * (k + 0.5) / n
        p = os.path.join(dossier, f"cle{k}.jpg")
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                        "-vf", "scale=640:-2", "-q:v", "4", p], capture_output=True, timeout=180)
        if os.path.isfile(p):
            out.append(p)
    return out


# ---------------------------------------------------------------- description automatique

from core.services.social.voix import VOIX  # noqa: E402  (voix de créateur de contenu, 06/11/2026)

CONSIGNE = VOIX + """

Ici, on te montre des images tirées d'une vidéo (dans l'ordre) et les informations publiques de sa publication d'origine.
Décris UNIQUEMENT ce qui est visible ou écrit dans ces informations : n'invente aucun fait, aucun chiffre, aucun nom.
Si tu ne reconnais pas la personne avec certitude, ne la nomme pas (sauf si son nom figure dans les informations).
Rends un objet JSON, rien d'autre :
{"etiquette": "2 ou 3 mots en majuscules (ex. MOMENT VIRAL, EN CONCERT, EN STUDIO, BACKSTAGE)",
 "accroche": "le TITRE selon les règles : l'info directe, les noms d'abord, 70 caractères maximum, sans point final ; jamais une description de ce qu'on voit (vêtements, décor)",
 "artiste": "nom de l'artiste principal si certain, sinon chaîne vide",
 "legende_fr": "en français, de la longueur de la légende d'origine (une ligne si le créateur a écrit une ligne, rien de plus qu'une phrase s'il n'a rien écrit, 3 phrases au plus sinon) : le contexte, ce qui rend ce moment important, puis une vraie question au public",
 "legende_en": "la même légende en anglais"}"""


def analyse(images: list[str], infos: dict) -> dict:
    """Suggestions de texte (Gemini voit les images) ; {} si l'IA est indisponible."""
    meta = {k: infos.get(k) for k in ("title", "description", "uploader", "channel", "track", "artist", "extractor_key")
            if infos.get(k)}
    if meta.get("description"):
        meta["description"] = str(meta["description"])[:600]
    cle = env.get("GEMINI_API_KEY", "")
    if not cle:
        return {}
    texte = CONSIGNE + "\n\nInformations : " + json.dumps(meta, ensure_ascii=False)
    if infos.get("contexte"):
        # commentaire du fondateur : information sûre, prioritaire, à utiliser telle quelle (sans broder au-delà)
        texte += ("\n\nContexte donné par la rédaction de Cauri Charts (fiable, à utiliser en priorité, sans rien inventer "
                  "au-delà) : " + str(infos["contexte"])[:600])
    parts = [{"text": texte}]
    for p in images[:4]:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(p, "rb").read()).decode()}})
    corps = {"contents": [{"parts": parts}],
             "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4, "maxOutputTokens": 8192}}
    texte, dernier = "", ""
    # la clé part dans un en-tête (jamais dans l'adresse : elle se retrouvait dans les messages d'erreur, 20/10/2026)
    for modele in dict.fromkeys([env.get("GEMINI_MODEL", "gemini-3.5-flash"), "gemini-flash-lite-latest", "gemini-3.8-flash"]):
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent",
                              headers={"x-goog-api-key": cle}, timeout=90, json=corps)
            if r.status_code != 200:
                dernier = f"{modele} : HTTP {r.status_code}"
                continue
            texte = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            break
        except Exception as exc:  # noqa: BLE001
            dernier = f"{modele} : {type(exc).__name__}"
    try:
        if not texte:
            raise RuntimeError(dernier or "aucune réponse")
        d = json.loads(texte[texte.find("{"): texte.rfind("}") + 1])
        return {k: str(d.get(k) or "").strip() for k in ("etiquette", "accroche", "artiste", "legende_fr", "legende_en")}
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"studio, analyse IA : {str(exc)[:200]}")
        return {}


# ---------------------------------------------------------------- montage

def calque(fmt: str, etiquette: str, accroche: str, artiste: str, credit: str,
           taille: tuple[int, int] | None = None, sans_logo: bool = False) -> tuple[Image.Image, tuple[int, int, int, int], Image.Image]:
    """(calque fixe, zone de la vidéo x, y, w, h, calque titre). Rien dans les 20 % du bas en 9:16 (interface TikTok/Reels).
    Calque fixe : le logo seul, toute la vidéo, avec une ombre douce collée aux lettres. Calque titre : le titre animé
    (studio_habillage) entièrement affiché, pour l'aperçu à valider.
    08/11/2026 : plus de dégradés sombres (« la couverture noire avec les titres, on enlève ») : la vidéo reste visible.
    « origine » : la vidéo remplit tout le cadre à ses proportions, l'habillage se pose par-dessus."""
    from core.services.social import couverture2026 as C
    from core.services.social import studio_habillage as HB
    W, H = taille or FORMATS[fmt]
    # 08/11/2026 : la source n'est plus écrite à l'écran (elle se mélangeait au titre) ; elle reste dans la légende du post
    haut, _y_credit, bas_bloc = _geometrie(fmt, W, H, "")
    haut_bloc = bas_bloc - HB.hauteur_ouverture(W, etiquette, accroche, artiste)
    fixe = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not sans_logo:
        C._logo(fixe, 50, haut, 76)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(HB._ombre(fixe, 10, 150).crop((30, 30, 30 + W, 30 + H)))
    titre_img = HB.image_ouverture((W, H), haut_bloc, etiquette, accroche, artiste)
    if fmt == "origine":
        return img, (0, 0, W, H), titre_img
    # autres formats : la vidéo entre le logo (en haut) et le titre (en bas)
    zone_haut = haut + 100
    zone_bas = haut_bloc - 24
    return img, (0, zone_haut, W, max(200, zone_bas - zone_haut)), titre_img


def _geometrie(fmt: str, W: int, H: int, credit: str) -> tuple[int, int, int]:
    """(y du logo, y du crédit, bas du bloc titre)."""
    portrait = H / W > 1.6
    haut = 110 if (fmt == "story" or (fmt == "origine" and portrait)) else 50
    bas_reserve = int(H * .20) if (fmt == "story" or (fmt == "origine" and portrait)) else 70
    y_credit = (H - bas_reserve - 46) if bas_reserve > 70 else H - 52
    bas_bloc = (y_credit - 22) if credit else (H - bas_reserve - 24)
    return haut, y_credit, bas_bloc


def duree_titre(duree: float) -> float:
    """Temps d'affichage de l'accroche, relatif à la vidéo : 15 % de sa durée, entre 2,5 et 7 s (puis fondu de 0,7 s),
    et toujours au moins 1,5 s de vidéo seule à la fin."""
    return max(1.5, min(max(2.5, min(7.0, duree * 0.15)), duree - 1.5))


def image_cadre(source: str, t: float, fmt: str, zone, taille, sortie: str) -> str | None:
    """Une image de la vidéo dans son cadre final (fond flouté + vidéo placée), sans habillage : base de l'aperçu."""
    W, H = taille
    x, y, w, h = zone
    filtre = (f"[0:v]split=2[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:6,"
              f"eq=brightness=-0.35[fond];[b]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[clip];"
              f"[fond][clip]overlay=(W-w)/2:{y}+({h}-h)/2[v]")
    r = subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", source, "-frames:v", "1",
                        "-filter_complex", filtre, "-map", "[v]", "-q:v", "2", sortie], capture_output=True, timeout=120)
    return sortie if r.returncode == 0 and os.path.isfile(sortie) else None


def apercu(fond: Image.Image, fmt: str, etiquette: str, accroche: str, artiste: str, credit: str) -> Image.Image:
    """L'image clé avec l'habillage complet (titre compris), telle qu'elle apparaîtra au début de la vidéo."""
    fixe, _zone, titre = calque(fmt, etiquette, accroche, artiste, credit, fond.size)
    im = fond.convert("RGBA")
    im.alpha_composite(fixe); im.alpha_composite(titre)
    return im.convert("RGB")


def bandes(source: str, debut: float, duree: float) -> str | None:
    """Recadrage « w:h:x:y » qui enlève les bandes noires cinéma du clip lui-même (sinon l'image reste petite au milieu
    du cadre, 20/10/2026) ; None s'il n'y en a pas."""
    import re as _re
    r = subprocess.run([ffmpeg(), "-v", "info", "-ss", f"{debut + 1:.2f}", "-t", f"{min(8.0, duree):.2f}", "-i", source,
                        "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"], capture_output=True, text=True, timeout=180)
    vus = _re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr or "")
    if not vus:
        return None
    w, h, x, y = map(int, vus[-1])
    largeur = _re.search(r"Stream.*Video.* (\d{3,5})x(\d{3,5})", r.stderr or "")
    if not largeur:
        return None
    W0, H0 = int(largeur.group(1)), int(largeur.group(2))
    if h >= H0 * .94 and w >= W0 * .94:      # pas de vraie bande
        return None
    # détection douteuse (scène très sombre)… sauf une vraie vidéo horizontale posée dans un cadre vertical : 16:9 dans du
    # 9:16 n'occupe que 32 % de la hauteur (07/11/2026 : le reel Sethlo n° 296 est parti avec ses bandes noires)
    if (h < H0 * .4 or w < W0 * .4) and not (1.3 <= w / max(1, h) <= 2.5 and w >= W0 * .9):
        return None
    return f"{w}:{h}:{x}:{y}"


def _icone_carree(taille_px: int) -> Image.Image:
    """Icône carrée arrondie violet + monogramme CC blanc, à la taille demandée."""
    from core.services.social.couverture2026 import VIOLET, RES
    d = taille_px
    r = int(d * 0.18)
    img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, d - 1, d - 1), radius=r, fill=VIOLET + (255,))
    lg = Image.open(RES / "marque" / "logo-blanc.png").convert("RGBA")
    lg = lg.crop(lg.getbbox())
    s = int(d * 0.72)
    lg = lg.resize((s, s), Image.LANCZOS)
    img.paste(lg, ((d - s) // 2, (d - s) // 2), lg)
    return img


def calque_logo(taille: tuple[int, int], fmt: str = "origine") -> tuple[Image.Image, int, int]:
    """Icône carrée arrondie (100 px) et position finale (x, y) sur la vidéo."""
    W, H = taille
    portrait = H / W > 1.6
    haut = 110 if (fmt == "story" or (fmt == "origine" and portrait)) else 50
    return _icone_carree(100), 50, haut


def _anime_logo(logo_icone: Image.Image, pos_finale: tuple[int, int],
                taille: tuple[int, int], duree: float, dossier: str, fps: int = 30) -> str:
    """Pré-rend l'animation du logo style émission TV / chaîne YouTube.

    UN SEUL logo, 3 phases :
      1. Arrive depuis la gauche de l'écran → va au centre + zoom IN (grandit)
      2. PAUSE au centre (grand)
      3. Repart vers le coin haut-gauche + zoom OUT (rétrécit) → se pose
    Le dernier frame (logo au repos dans le coin) est répété par FFmpeg.
    L'animation dure ~55 % de la vidéo (entre 3 et 7 s)."""
    W, H = taille
    fx, fy = pos_finale
    d = logo_icone.size[0]
    anim_dur = min(7.0, max(3.0, duree * 0.55))
    n = int(anim_dur * fps) + 1

    # Positions
    cx, cy = W / 2, H * 0.42
    fcx, fcy = fx + d / 2, fy + d / 2
    z_max = 5.5

    # Phases (en frames)
    f1_start = int(0.02 * n)
    f1_end = int(0.28 * n)
    f2_end = int(0.60 * n)
    f3_end = int(0.90 * n)

    for i in range(n):
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        if i < f1_start:
            pass
        elif i < f1_end:
            # Phase 1 : gauche → centre + zoom in (ease-out : vite au début, ralentit)
            p = (i - f1_start) / max(1, f1_end - f1_start)
            ep = 1 - (1 - p) ** 2.5
            x_now = -d + (cx) * ep
            y_now = cy
            z = 1.0 + (z_max - 1.0) * ep
            alpha = min(1.0, p * 3)
            sz = max(1, int(d * z))
            sc = logo_icone.resize((sz, sz), Image.LANCZOS)
            if alpha < 1.0:
                r, g, b, a = sc.split()
                a = a.point(lambda px, _a=alpha: int(px * _a))
                sc = Image.merge("RGBA", (r, g, b, a))
            frame.paste(sc, (int(x_now - sz / 2), int(y_now - sz / 2)), sc)
        elif i < f2_end:
            # Phase 2 : pause au centre (grand)
            sz = max(1, int(d * z_max))
            sc = logo_icone.resize((sz, sz), Image.LANCZOS)
            frame.paste(sc, (int(cx - sz / 2), int(cy - sz / 2)), sc)
        elif i < f3_end:
            # Phase 3 : centre → coin haut-gauche + zoom out (ease-in : lent → rapide)
            p = (i - f2_end) / max(1, f3_end - f2_end)
            ep = p ** 2.5
            x_now = cx + (fcx - cx) * ep
            y_now = cy + (fcy - cy) * ep
            z = z_max - (z_max - 1.0) * ep
            sz = max(1, int(d * z))
            sc = logo_icone.resize((sz, sz), Image.LANCZOS)
            frame.paste(sc, (int(x_now - sz / 2), int(y_now - sz / 2)), sc)
        else:
            # Repos dans le coin
            frame.paste(logo_icone, (fx, fy), logo_icone)

        frame.save(os.path.join(dossier, f"logo_{i:04d}.png"))

    anim = os.path.join(dossier, "logo_anim.mkv")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-framerate", str(fps),
                    "-i", os.path.join(dossier, "logo_%04d.png"),
                    "-c:v", "ffv1", "-pix_fmt", "yuva444p", anim],
                   capture_output=True, timeout=180)
    for i in range(n):
        try:
            os.remove(os.path.join(dossier, f"logo_{i:04d}.png"))
        except OSError:
            pass
    return anim


def monte(source: str, sortie: str, fmt: str, debut: float, fin: float, calque_png: str, zone,
          taille: tuple[int, int] | None = None, titre: dict | None = None, avec_fin: bool = True) -> None:
    """Montage final : fond flouté + clip + calque fixe + titre animé (studio_habillage) + carte de fin.
    ``titre`` : {etiquette, accroche, artiste, credit}. La carte de fin (08/11/2026) remplace l'ancien clip After Effects :
    la dernière image se fige et se floute sous un voile blanc, la carte en verre arrive par-dessus."""
    from core.services.social import studio_habillage as HB
    W, H = taille or FORMATS[fmt]
    x, y, w, h = zone
    duree = max(1.0, fin - debut)
    rogne = bandes(source, debut, duree)
    dossier = os.path.dirname(sortie)
    t_fin = max(0.0, duree - HB.FIN_AVANCE)              # début de la carte de fin
    total = duree + (HB.FIN_DUREE if avec_fin else 0)

    # ── base : fond flouté + clip ──
    filtre = ((f"[0:v]crop={rogne},split=2[a][b];" if rogne else "[0:v]split=2[a][b];")
              + f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"boxblur=28:6,eq=brightness=-0.35[fond];"
              + (f"[b]crop='min(iw,ih*1.9)':ih,scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[clip];" if W < H * 1.2
                 else f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[clip];")
              + f"[fond][clip]overlay=(W-w)/2:{y}+({h}-h)/2,fps=30[v0];")

    # ── calque fixe (logo, crédit) ──
    filtre += "[v0][1:v]overlay=0:0[v1];"
    entrees = []
    n = 2

    # ── titre animé : pastille, accroche mot par mot ──
    if titre:
        haut_bloc = _geometrie(fmt, W, H, "")[2] - HB.hauteur_ouverture(
            W, titre.get("etiquette") or "", titre.get("accroche") or "", titre.get("artiste") or "")
        anim, y_anim = HB.ouverture((W, H), haut_bloc, titre.get("etiquette") or "", titre.get("accroche") or "",
                                    titre.get("artiste") or "", duree_titre(duree), dossier)
        entrees += ["-i", anim]
        filtre += f"[{n}:v]format=yuva444p[ti];[v1][ti]overlay=0:{y_anim}:eof_action=pass:format=auto[v2];"
        n += 1
    else:
        filtre += "[v1]null[v2];"

    # ── carte de fin : image figée, flou progressif, carte en verre ──
    if avec_fin:
        entrees += ["-itsoffset", f"{t_fin:.3f}", "-i", HB.fin((W, H), dossier)]
        filtre += (f"[v2]tpad=stop_mode=clone:stop_duration={HB.FIN_DUREE + 1:.2f},trim=duration={total:.3f},split=2[n1][n2];"
                   f"[n2]gblur=sigma=26:enable='gte(t,{t_fin:.3f})'[fl];"
                   f"[n1][fl]blend=all_expr='A+(B-A)*clip((T-{t_fin:.3f})/0.6,0,1)':enable='gte(t,{t_fin:.3f})'[nb];"
                   f"[{n}:v]format=yuva444p[cf];[nb][cf]overlay=0:0:eof_action=repeat:format=auto[v3];")
        n += 1
    else:
        filtre += "[v2]null[v3];"

    # ── flash subtil (éclair blanc rapide au début) ──
    filtre += (f"[v3]drawbox=x=0:y=0:w={W}:h={H}:color=white@0.15:t=fill"
               f":enable='between(t,0.25,0.33)'[v4];")

    # ── finition : netteté, fondus (entrée au noir, sortie au blanc : la fin est claire) ──
    # netteté seule (07/11/2026) : le débruitage temporel (hqdn3d 5:5) lissait le mouvement ; mesuré sur la source du
    # reel Sethlo (n° 296), netteté 302 avec l'ancien réglage, 334 sans débruitage (source brute : 202)
    filtre += (f"[v4]unsharp=5:5:0.5:5:5:0,format=yuv420p,fade=t=in:d=0.25,"
               f"fade=t=out:st={max(0, total - 0.35):.2f}:d=0.35:color=white[v]")

    # son : le clip s'éteint quand la carte arrive
    af = (f"loudnorm=I=-14:TP=-1.5,apad=whole_dur={total:.3f},"
          f"afade=t=out:st={max(0, (t_fin if avec_fin else duree) - 0.2):.2f}:d={0.9 if avec_fin else 0.5}")
    from core.services.social.encodage import AUDIO_HQ, FIN, VIDEO_HQ
    cmd = [ffmpeg(), "-y", "-v", "error", "-ss", f"{debut:.2f}", "-t", f"{duree:.2f}", "-i", source,
           "-loop", "1", "-t", f"{total:.2f}", "-i", calque_png, *entrees,
           "-filter_complex", filtre, "-map", "[v]", "-map", "0:a?", "-af", af,
           *VIDEO_HQ, *AUDIO_HQ, *FIN, "-t", f"{total:.3f}", sortie]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    if r.returncode != 0:
        raise RuntimeError("montage : " + (r.stderr or "")[-300:])


# ---------------------------------------------------------------- ensemble

def traite(job_id: int) -> dict:
    job = db.one("SELECT * FROM studio_jobs WHERE id = ?", [job_id])
    if not job:
        raise RuntimeError("tâche introuvable")
    p = job["params"] if isinstance(job["params"], dict) else json.loads(job["params"] or "{}")
    if p.get("type") == "vedette":   # mise en valeur d'un artiste (02/11/2026) : aperçus des modèles, puis publication
        from core.services.social import vedette
        return vedette.publie(job_id, job, p, _maj) if p.get("choix") else vedette.traite(job_id, job, p, _maj)
    if p.get("type") == "paroles":   # vidéo paroles (10/11/2026), sur le PC
        from core.services.social import studio_paroles
        try:
            return studio_paroles.traite(job_id, job, p, _maj)
        except TacheAnnulee:
            return {"statut": "annule"}
        except Exception as exc:  # noqa: BLE001
            _maj(job_id, statut="erreur", erreur=str(exc)[:500])
            raise
    if p.get("type") == "photos":   # section Photos : récupérer les images d'un post pour la banque de l'artiste
        from core.services.social import studio_photos
        try:
            if p.get("publier_indices"):
                return studio_photos.publie(job_id, job, p, _maj)
            if p.get("mode") == "profil":
                return studio_photos.traite_profil(job_id, job, p, _maj)
            return studio_photos.traite(job_id, job, p, _maj)
        except TacheAnnulee:
            return {"statut": "annule"}
        except Exception as exc:  # noqa: BLE001
            try:
                _maj(job_id, statut="erreur", erreur=str(exc)[:500])
            except TacheAnnulee:
                return {"statut": "annule"}
            raise
    fmt = p.get("format") if p.get("format") in FORMATS else "origine"
    with tempfile.TemporaryDirectory(prefix=f"cauri-studio-{job_id}-") as tmp:
        try:
            _maj(job_id, statut="telechargement", erreur=None)
            source, infos = telecharge(job["lien"], tmp)
            basse = _source_basse(source, infos)
            if basse:   # affiché dans le Studio : conseil de prendre le clip officiel YouTube
                p["source_basse"] = basse
            longueur = float(infos.get("duration") or 0) or None
            debut = max(0.0, float(p.get("debut") or 0))
            fin = float(p.get("fin") or 60)
            if p.get("refrain_auto"):            # idée du jour : on prend le refrain du clip
                from core.services.social import refrain as RF
                debut, fin = RF.refrain(source, duree=float(p.get("duree") or 20))
            if p.get("resume"):                  # résumé : les temps forts de toute la vidéo, enchaînés (26/10/2026)
                total = fin - debut
                longueur = longueur or _duree_fichier(source)
                if longueur and longueur > total * 1.5:
                    _maj(job_id, statut="telechargement")
                    try:
                        source = resume_video(source, total, longueur, tmp)
                        debut, fin, longueur = 0.0, total, total
                    except Exception as exc:  # noqa: BLE001 — vidéo sans son, format exotique : extrait simple
                        log_write("studio", "warning", f"résumé impossible ({str(exc)[:200]}) : extrait simple")
            if longueur:
                fin = min(fin, longueur)
            fin = min(fin, debut + MAX_DUREE)
            if fin <= debut:
                raise RuntimeError("le début est après la fin de la vidéo")
            _maj(job_id, statut="analyse")
            sugg = analyse(images_cles(source, tmp, debut, fin), {**infos, "contexte": p.get("contexte") or ""})
            credit = p.get("credit") or credit_auto(infos)
            etiquette = p.get("etiquette") or sugg.get("etiquette") or "VIDÉO"
            accroche = p.get("accroche") or sugg.get("accroche") or (infos.get("title") or "")[:70]
            artiste = p.get("artiste") or sugg.get("artiste") or ""
            p.update({"credit": credit, "etiquette": etiquette, "accroche": accroche, "artiste": artiste,
                      "debut": debut, "fin": fin, "suggestion": sugg, "titre_source": (infos.get("title") or "")[:200],
                      "legende_fr": p.get("legende_fr") or sugg.get("legende_fr") or "",
                      "legende_en": p.get("legende_en") or sugg.get("legende_en") or ""})
            taille = taille_origine(infos, source) if fmt == "origine" else FORMATS[fmt]
            if p.get("valider") and not p.get("valide"):
                # 1er temps : on montre l'accroche sur une image de la vidéo ; le montage attend la validation (20/10/2026)
                _f, zone_a, _t = calque(fmt, etiquette, accroche, artiste, credit, taille)
                cle = image_cadre(source, debut + min(2.0, (fin - debut) / 2), fmt, zone_a, taille, os.path.join(tmp, "cle.jpg"))
                if cle:
                    nom_cle = f"studio-{job_id}-cle-{os.urandom(2).hex()}.jpg"
                    storage.store_media("social", nom_cle, open(cle, "rb").read(), "image/jpeg")
                    vue = apercu(Image.open(cle), fmt, etiquette, accroche, artiste, credit)
                    out = io.BytesIO(); vue.save(out, format="JPEG", quality=90)
                    nom_vue = f"studio-{job_id}-apercu-{os.urandom(2).hex()}.jpg"
                    storage.store_media("social", nom_vue, out.getvalue(), "image/jpeg")
                    p.update({"cle": nom_cle, "format_final": fmt})
                    _maj(job_id, statut="a_valider", vignette=nom_vue, params=p)
                    return {"statut": "a_valider", "video": nom_vue}
            _maj(job_id, statut="montage", params=p)
            img, zone, titre_img = calque(fmt, etiquette, accroche, artiste, credit, taille)
            png = os.path.join(tmp, "calque.png"); img.save(png)
            nom = f"studio-{job_id}-{os.urandom(3).hex()}"
            video = os.path.join(tmp, nom + ".mp4"); vignette = os.path.join(tmp, nom + ".jpg")
            monte(source, video, fmt, debut, fin, png, zone, taille,
                  {"etiquette": etiquette, "accroche": accroche, "artiste": artiste, "credit": credit})
            subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", "1.5", "-i", video, "-frames:v", "1", "-q:v", "3", vignette],
                           capture_output=True, timeout=60)
            storage.store_media("social", nom + ".mp4", open(video, "rb").read(), "video/mp4")
            _verifie_en_ligne(nom + ".mp4")   # le relais du PC déclarait « prête » une vidéo jamais mise en ligne (29/10/2026)
            from core.services.social.encodage import copie_tiktok
            tt = copie_tiktok(video)
            if tt:
                storage.store_media("social", os.path.basename(tt), open(tt, "rb").read(), "video/mp4")
            from core.services.social.encodage import copie_telegram
            tg = copie_telegram(video)   # Telegram : copie sous 20 Mo ; Instagram, TikTok et Facebook gardent la haute qualité
            if tg:
                storage.store_media("social", os.path.basename(tg), open(tg, "rb").read(), "video/mp4")
            storage.store_media("social", nom + ".jpg", open(vignette, "rb").read(), "image/jpeg")
            _maj(job_id, statut="pret", video=nom + ".mp4", vignette=nom + ".jpg", params=p)
            return {"statut": "pret", "video": nom + ".mp4"}
        except TacheAnnulee:
            return {"statut": "annule"}
        except Exception as exc:  # noqa: BLE001
            try:
                _maj(job_id, statut="erreur", erreur=str(exc)[:500])
            except TacheAnnulee:
                return {"statut": "annule"}
            raise

