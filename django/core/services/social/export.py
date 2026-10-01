"""Copie chaque post dans un dossier facile à parcourir (traduction de Social\\PostExport).

SOCIAL_EXPORT_DIR (par exemple Documents\\Cauri Charts - Posts) : Année \\ Semaine NN (du lundi au dimanche) \\
JJ-MM Jour - Rubrique - Titre, avec la légende prête à coller et un sous-dossier par plateforme, en 4K :
« Instagram et Facebook » (carrousel et post 4:5, story et Reel 9:16) et « TikTok » (carrousel photo et vidéo 9:16).
Désactivé si SOCIAL_EXPORT_DIR est vide (serveur) ; le même dossier se télécharge en ZIP depuis l'admin (zip_post).
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
from core.services.social.themes import label

DAYS = {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi", 5: "Vendredi", 6: "Samedi", 7: "Dimanche"}
# Sous-dossiers par plateforme (Instagram et Facebook ont les mêmes formats : 4:5 au fil, 9:16 en story et en Reel)
META = "Instagram et Facebook"
TIKTOK = "TikTok"
# Fichiers texte lisibles par le Bloc-notes de Windows : BOM UTF-8 et fins de ligne CRLF
BOM, CRLF = "﻿", "\r\n"
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _short(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def file_name(label: str) -> str:
    """Libellé utilisable comme nom de fichier Windows (sans caractères interdits ni emoji, 90 caractères au plus)."""
    name = re.sub(r'[\\/:*?"<>|]+', " ", PI.clean(label))
    return re.sub(r"\s+", " ", name).strip(" .")[:90]


def folder_name(post: dict) -> tuple:
    """(année ISO, « Semaine NN (…) », « JJ-MM Jour - Rubrique - Titre ») du dossier d'un post."""
    d = date.fromisoformat(str(post["slot_date"])[:10])
    monday = d - timedelta(days=d.isoweekday() - 1)
    iso_year, iso_week, _ = d.isocalendar()
    week = f"Semaine {iso_week:02d} ({_short(monday)} - {_short(monday + timedelta(days=6))})"
    rubric = label(post["theme"])
    # Espaces insécables de la typographie française → espaces simples, pour reconnaître la rubrique
    title = re.sub(r"[  \t ]+", " ", PI.clean(post["title"]))
    title = re.sub(r"\s*[:·\-–]?\s*" + re.escape(rubric) + r"\s*[:·\-–]?\s*", " ", title, flags=re.I)  # pas de répétition de la rubrique
    title = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|!]+', " ", title)).strip()
    if len(title) < 2 or re.match(r"^(de|du|des|la|le|les)\b", title, re.I):
        title = ""  # reste d'un titre qui ne faisait que répéter la rubrique
    return str(iso_year), week, f"{d:%d-%m} {DAYS[d.isoweekday()]} - {rubric}" + (f" - {title[:60]}" if title else "")


def contents(post: dict, clips_folder: str = "") -> tuple:
    """Contenu du dossier d'un post : ([(chemin dans le dossier, fichier généré)], {chemin: texte}).
    Un sous-dossier par plateforme, chaque fichier déjà au bon format : rien à recadrer au moment de publier."""
    files, texts = [], {}

    def add(file, sub: str, as_name: str) -> None:
        if file:
            base = os.path.basename(file)
            files.append((os.path.join(sub, as_name + os.path.splitext(base)[1]), base))

    try:
        slides = json.loads(post.get("carousel") or "[]") or []
    except ValueError:
        slides = []
    leader = ""
    for i, slide in enumerate(slides):
        f = slide["file"] if isinstance(slide, dict) else slide
        label = slide["label"] if isinstance(slide, dict) else ("Couverture" if i == 0 else "Diapositive")
        add(f, os.path.join(META, "Carrousel 4-5"), f"{i + 1:02d} - {file_name(label)}")
        if isinstance(slide, dict):
            add(slide.get("tiktok"), os.path.join(TIKTOK, "Carrousel photo 9-16"), f"{i + 1:02d} - {file_name(label)}")
        if i == 1:
            leader = " - " + file_name(label)
    count = max(0, len(slides) - 1)

    # Clips officiels : ceux qui manquent pour la vidéo (30 s de clip par titre), avec le lien de référence
    missing = [s for s in slides if isinstance(s, dict) and s.get("clip") is False]
    if slides and isinstance(slides[0], dict):
        lines = [BOM + "CLIPS OFFICIELS POUR LA VIDÉO", ""]
        if not missing:
            lines.append("Tous les clips sont là : chaque titre passe 30 secondes avec son clip dans la vidéo.")
        else:
            lines += ["Pour que chaque titre passe 30 secondes avec son clip officiel, déposez ces fichiers dans :",
                      "  " + (clips_folder or "le dossier Clips"),
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
        texts["00 - Clips à demander.txt"] = CRLF.join(lines) + CRLF
    add(post.get("image_square"), META, f"Post unique 4-5{leader}")
    add(post.get("image_story"), META, f"Story 9-16{leader}")
    with_clips = len(slides) - 1 - len(missing)
    sound = (f" avec {with_clips} clip(s), son inclus" if with_clips > 0 else " (sans son, musique à ajouter dans l'application)")
    add(post.get("video"), META, f"Reel 9-16 - Vidéo du Top {count}{sound}")
    add(post.get("video"), TIKTOK, f"Vidéo 9-16 - Top {count}{sound}")
    texts["00 - Légende à copier.txt"] = (BOM + post["title"] + CRLF * 2 + post["caption"].replace("\n", CRLF)
                                       + CRLF * 2 + post["hashtags"] + CRLF)
    return files, texts


def export(post: dict):
    root = (env.get("SOCIAL_EXPORT_DIR", "") or "").rstrip("/\\")
    if not root:
        return None
    iso_year, week, name = folder_name(post)
    folder = os.path.join(root, iso_year, week, name)
    d = date.fromisoformat(str(post["slot_date"])[:10])
    rubric = label(post["theme"])
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
    files, texts = contents(post, clips_dir() or os.path.join(root, "Clips"))
    for rel, base in files:
        src = PI.DIR / base
        if src.is_file():
            os.makedirs(os.path.dirname(os.path.join(folder, rel)), exist_ok=True)
            shutil.copyfile(src, os.path.join(folder, rel))
    for rel, text in texts.items():
        with open(os.path.join(folder, rel), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return folder


def zip_post(post: dict):
    """Archive ZIP du dossier d'un post (même contenu que l'export local), fichiers lus sur le disque ou dans le Blob.
    Retourne (nom de l'archive, chemin du fichier ZIP temporaire)."""
    import tempfile
    import zipfile

    import requests

    from core import storage
    _, _, name = folder_name(post)
    base_url = storage.blob_public_url()
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    files, texts = contents(post)
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_STORED) as z:  # images et vidéo déjà compressées
        for rel, text in texts.items():
            z.writestr(f"{name}/{rel}".replace("\\", "/"), text.encode("utf-8"))
        for rel, media in files:
            local = PI.DIR / media
            arc = f"{name}/{rel}".replace("\\", "/")
            if local.is_file():
                z.write(local, arc)
            elif base_url:
                r = requests.get(f"{base_url}/media/social/{media}", timeout=60)
                if r.ok:
                    z.writestr(arc, r.content)
    return name + ".zip", tmp.name
