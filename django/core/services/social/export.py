"""Copie chaque post dans un dossier facile à parcourir (traduction de Social\\PostExport).

SOCIAL_EXPORT_DIR (par exemple Documents\\Cauri Charts - Posts) : Année \\ Semaine NN (du lundi au dimanche) \\
JJ-MM Jour - Rubrique - Titre, avec le carrousel numéroté, les visuels, la vidéo et la légende prête à coller.
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

DAYS = {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi", 5: "Vendredi", 6: "Samedi", 7: "Dimanche"}
THEMES = {"classement": "Tendances", "artiste": "Artiste de la semaine", "weekend": "Spécial week-end"}
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
    rubric = THEMES.get(post["theme"], post["theme"])
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
        if os.path.isfile(old):
            os.unlink(old)  # nouvelle version du post du même jour : on remplace

    def copy(file, as_name: str) -> None:
        if file and (PI.DIR / os.path.basename(file)).is_file():
            shutil.copyfile(PI.DIR / os.path.basename(file), os.path.join(folder, as_name))

    # « 01 - Couverture - … », « 02 - N°1 - Artiste - Titre », puis visuels, vidéo et légende
    try:
        slides = json.loads(post.get("carousel") or "[]") or []
    except ValueError:
        slides = []
    leader = ""
    for i, slide in enumerate(slides):
        f = slide["file"] if isinstance(slide, dict) else slide
        label = slide["label"] if isinstance(slide, dict) else ("Couverture" if i == 0 else "Diapositive")
        copy(f, f"{i + 1:02d} - {file_name(label)}.jpg")
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
    copy(post.get("image_square"), f"Visuel carré pour le fil{leader}.png")
    copy(post.get("image_story"), f"Visuel story{leader}.png")
    with_clips = len(slides) - 1 - len(missing)
    copy(post.get("video"), f"Vidéo du Top {count}" + (f" avec {with_clips} clip(s), son inclus" if with_clips > 0
                                                       else " (sans son, musique à ajouter dans Instagram ou TikTok)") + ".mp4")
    with open(os.path.join(folder, "00 - Légende à copier.txt"), "w", encoding="utf-8", newline="") as fh:
        fh.write("﻿" + post["title"] + "\r\n\r\n" + post["caption"].replace("\n", "\r\n") + "\r\n\r\n" + post["hashtags"] + "\r\n")
    return folder
