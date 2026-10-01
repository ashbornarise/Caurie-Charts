"""Copie chaque post dans un dossier facile à parcourir (traduction de Social\\PostExport).

SOCIAL_EXPORT_DIR (par exemple Documents\\Cauri Charts - Posts) : Année \\ Semaine NN (du lundi au dimanche) \\
JJ-MM Jour - Rubrique - Titre, avec la légende prête à coller et un sous-dossier par plateforme, en 4K :
« Instagram et Facebook » (carrousel et post 4:5, story et Reel 9:16) et « TikTok » (carrousel photo et vidéo 9:16).
Désactivé si SOCIAL_EXPORT_DIR est vide (serveur).
"""
import glob
import json
import os
import re
import shutil
from datetime import date, timedelta

from core import env
from core.services.social import image as PI
from core.services.social.carousel import clips_dir
from core.services.social.themes import labels

DAYS = {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi", 5: "Vendredi", 6: "Samedi", 7: "Dimanche"}
# Sous-dossiers par plateforme (Instagram et Facebook ont les mêmes formats : 4:5 au fil, 9:16 en story et en Reel)
META = "Instagram et Facebook"
TIKTOK = "TikTok"
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _short(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def file_name(label: str) -> str:
    """Libellé utilisable comme nom de fichier Windows (sans caractères interdits ni emoji, 90 caractères au plus)."""
    name = re.sub(r'[\\/:*?"<>|]+', " ", PI.clean(label))
    return re.sub(r"\s+", " ", name).strip(" .")[:90]


def export(post: dict):
    root = (env.get("SOCIAL_EXPORT_DIR", "") or "").rstrip("/\\")
    if not root:
        return None
    d = date.fromisoformat(str(post["slot_date"])[:10])
    monday = d - timedelta(days=d.isoweekday() - 1)
    iso_year, iso_week, _ = d.isocalendar()
    week = f"Semaine {iso_week:02d} ({_short(monday)} - {_short(monday + timedelta(days=6))})"
    rubric = labels().get(post["theme"], post["theme"])
    # Espaces insécables de la typographie française → espaces simples, pour reconnaître la rubrique
    title = re.sub(r"[   \t ]+", " ", PI.clean(post["title"]))
    title = re.sub(r"\s*[:·\-–]?\s*" + re.escape(rubric) + r"\s*[:·\-–]?\s*", " ", title, flags=re.I)  # pas de répétition de la rubrique
    title = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|!]+', " ", title)).strip()
    if len(title) < 2 or re.match(r"^(de|du|des|la|le|les)\b", title, re.I):
        title = ""  # reste d'un titre qui ne faisait que répéter la rubrique
    name = f"{d:%d-%m} {DAYS[d.isoweekday()]} - {rubric}" + (f" - {title[:60]}" if title else "")
    folder = os.path.join(root, str(iso_year), week, name)
    # Même rubrique le même jour : l'ancienne version est remplacée
    for old in glob.glob(os.path.join(glob.escape(os.path.dirname(folder)), f"{d:%d-%m} * - {glob.escape(rubric)}*")):
        if os.path.isdir(old) and old != folder:
            shutil.rmtree(old, ignore_errors=True)  # OneDrive peut retenir le dossier un instant : retiré au passage suivant
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        return None
    for old in glob.glob(os.path.join(glob.escape(folder), "*")):
        # nouvelle version du post du même jour : on remplace
        if os.path.isfile(old):
            os.unlink(old)
        elif os.path.isdir(old):
            shutil.rmtree(old, ignore_errors=True)

    def copy(file, sub: str, as_name: str) -> None:
        """Copie dans le sous-dossier de la plateforme, avec l'extension du fichier généré (jpg, png, mp4)."""
        src = PI.DIR / os.path.basename(file) if file else None
        if src and src.is_file():
            os.makedirs(os.path.join(folder, sub), exist_ok=True)
            shutil.copyfile(src, os.path.join(folder, sub, as_name + src.suffix))

    # Un dossier par plateforme, chaque fichier déjà au bon format : rien à recadrer au moment de publier
    try:
        slides = json.loads(post.get("carousel") or "[]") or []
    except ValueError:
        slides = []
    leader = ""
    for i, slide in enumerate(slides):
        f = slide["file"] if isinstance(slide, dict) else slide
        label = slide["label"] if isinstance(slide, dict) else ("Couverture" if i == 0 else "Diapositive")
        copy(f, os.path.join(META, "Carrousel 4-5"), f"{i + 1:02d} - {file_name(label)}")
        if isinstance(slide, dict):
            copy(slide.get("tiktok"), os.path.join(TIKTOK, "Carrousel photo 9-16"), f"{i + 1:02d} - {file_name(label)}")
        if i == 1:
            leader = " - " + file_name(label)
    count = max(0, len(slides) - 1)

    # Clips officiels : ceux qui manquent pour la vidéo (30 s de clip par titre), avec le lien de référence
    missing = [s for s in slides if isinstance(s, dict) and s.get("clip") is False]
    if slides and isinstance(slides[0], dict):
        cdir = clips_dir() or os.path.join(root, "Clips")
        lines = ["﻿CLIPS OFFICIELS POUR LA VIDÉO", ""]
        if not missing:
            lines.append("Tous les clips sont là : chaque titre passe 30 secondes avec son clip dans la vidéo.")
        else:
            lines += ["Pour que chaque titre passe 30 secondes avec son clip officiel, déposez ces fichiers dans :", "  " + cdir,
                      f"puis régénérez le post (admin > Posts, ou « python manage.py generate_posts --theme={post['theme']} »).", ""]
            for s in missing:
                lines += ["• " + s["label"], "    Nom du fichier : " + str(s.get("expect"))]
                if s.get("youtube"):
                    lines.append("    Clip officiel (référence) : " + s["youtube"])
            lines += ["", "Les fichiers doivent venir de l’artiste, de son label ou de votre catalogue (jamais téléchargés sur YouTube).", "",
                      "MESSAGE À ENVOYER (WhatsApp, e-mail) :",
                      "Bonjour ! Votre titre est dans le Top de la semaine de Cauri Charts, le classement musical de l’Afrique de l’Ouest. "
                      "Pour le mettre en avant dans notre vidéo sur Instagram et TikTok, pouvez-vous nous envoyer le fichier vidéo du clip officiel "
                      "(MP4) et nous autoriser à en diffuser un extrait de 30 secondes, avec votre nom et le lien vers le clip ? Merci !"]
        with open(os.path.join(folder, "00 - Clips à demander.txt"), "w", encoding="utf-8", newline="") as fh:
            fh.write("\r\n".join(lines) + "\r\n")
    copy(post.get("image_square"), META, f"Post unique 4-5{leader}")
    copy(post.get("image_story"), META, f"Story 9-16{leader}")
    with_clips = len(slides) - 1 - len(missing)
    sound = (f" avec {with_clips} clip(s), son inclus" if with_clips > 0 else " (sans son, musique à ajouter dans l'application)")
    copy(post.get("video"), META, f"Reel 9-16 - Vidéo du Top {count}{sound}")
    copy(post.get("video"), TIKTOK, f"Vidéo 9-16 - Top {count}{sound}")
    with open(os.path.join(folder, "00 - Légende à copier.txt"), "w", encoding="utf-8", newline="") as fh:
        fh.write("﻿" + post["title"] + "\r\n\r\n" + post["caption"].replace("\n", "\r\n") + "\r\n\r\n" + post["hashtags"] + "\r\n")
    return folder
