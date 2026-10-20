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

import requests
from PIL import Image, ImageDraw

from core import db, env, storage
from core.services.platforms import log_write

FORMATS = {"origine": None, "story": (1080, 1920), "feed": (1080, 1350), "square": (1080, 1080)}


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


def _maj(job_id: int, **champs) -> None:
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
           "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b",
           "--merge-output-format", "mp4", "--write-info-json", "-o", sortie, lien]
    if re.search(r"tiktok\.com", lien, re.I):
        # TikTok refuse les serveurs (« Unexpected response from webpage request ») : on se présente comme Chrome (curl_cffi)
        cmd[3:3] = ["--impersonate", "chrome"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    fichiers = [f for f in glob.glob(os.path.join(dossier, "source.*")) if not f.endswith(".json")]
    if r.returncode != 0 or not fichiers:
        msg = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["erreur inconnue"]
        texte = msg[0]
        if re.search(r"login|cookies|rate-limit|Sign in|private", texte, re.I):
            texte = ("La plateforme refuse le téléchargement depuis le serveur (connexion exigée). Lance la fabrication "
                     "depuis le PC : python manage.py studio_job --id <numéro>. Détail : " + texte)
        raise RuntimeError(texte[:400])
    infos = {}
    for j in glob.glob(os.path.join(dossier, "source*.info.json")):
        try:
            infos = json.load(open(j, encoding="utf-8"))
        except ValueError:
            pass
    return fichiers[0], infos


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
                        "-vf", "scale=640:-2", "-q:v", "4", p], capture_output=True, timeout=60)
        if os.path.isfile(p):
            out.append(p)
    return out


# ---------------------------------------------------------------- description automatique

CONSIGNE = """Tu es la rédaction de Cauri Charts, « la référence de la musique ouest-africaine ».
On te montre des images tirées d'une vidéo (dans l'ordre) et les informations publiques de sa publication d'origine.
Décris UNIQUEMENT ce qui est visible ou écrit dans ces informations : n'invente aucun fait, aucun chiffre, aucun nom.
Si tu ne reconnais pas la personne avec certitude, ne la nomme pas (sauf si son nom figure dans les informations).
Rends un objet JSON, rien d'autre :
{"etiquette": "2 ou 3 mots en majuscules (ex. MOMENT VIRAL, EN CONCERT, EN STUDIO, BACKSTAGE)",
 "accroche": "phrase courte en français, 70 caractères maximum, qui donne envie de regarder, sans point final",
 "artiste": "nom de l'artiste principal si certain, sinon chaîne vide",
 "legende_fr": "2 ou 3 phrases en français qui racontent la vidéo, puis une question au public",
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
           taille: tuple[int, int] | None = None) -> tuple[Image.Image, tuple[int, int, int, int], Image.Image]:
    """(calque fixe, zone de la vidéo x, y, w, h, calque titre). Rien dans les 20 % du bas en 9:16 (interface TikTok/Reels).
    Calque fixe : logo et crédit, toute la vidéo. Calque titre : dégradé du haut, étiquette et accroche, effacé en fondu
    après quelques secondes pour laisser la vidéo seule (20/10/2026).
    « origine » : la vidéo remplit tout le cadre à ses proportions, l'habillage se pose par-dessus (dégradés sombres)."""
    from core.services.social import couverture2026 as C
    W, H = taille or FORMATS[fmt]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    titre_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if fmt == "origine":
        haut_d, bas_d = Image.new("L", (1, H)), Image.new("L", (1, H))
        for yy in range(H):
            t = yy / H
            haut_d.putpixel((0, yy), int(215 * max(0, 1 - t / .42) ** 1.4))
            bas_d.putpixel((0, yy), int(170 * max(0, (t - .78) / .22) ** 1.6))
        titre_img.paste(Image.new("RGBA", (W, H), (8, 6, 16, 255)), (0, 0), haut_d.resize((W, H)))
        img.paste(Image.new("RGBA", (W, H), (8, 6, 16, 255)), (0, 0), bas_d.resize((W, H)))
    d = ImageDraw.Draw(img)
    dt = ImageDraw.Draw(titre_img)
    portrait = H / W > 1.6
    haut = 110 if (fmt == "story" or (fmt == "origine" and portrait)) else 50
    C._logo(img, 50, haut, 76)
    fe = C.police("Montserrat.ttf", 26, "ExtraBold")
    eti = (etiquette or "VIDÉO").upper()[:32]
    tw = d.textlength(eti, font=fe)
    y = haut + 100
    dt.rounded_rectangle((50, y, 50 + tw + 34, y + 46), radius=23, fill=C.CIEL + (255,))
    dt.text((67, y + 8), eti, font=fe, fill=C.NUIT + (255,))
    y += 66
    cibles = {re.sub(r"\W", "", m.lower()) for m in (artiste or "").split()}
    texte = C.propre(accroche or "")
    for taille in (60, 54, 48, 42):
        f = C.police("Montserrat.ttf", taille, "ExtraBold")
        lignes, cour = [], ""
        for mot in texte.split():
            essai = (cour + " " + mot).strip()
            if d.textlength(essai, font=f) > W - 100 and cour:
                lignes.append(cour); cour = mot
            else:
                cour = essai
        if cour:
            lignes.append(cour)
        if len(lignes) <= 3:
            break
    for ligne in lignes:
        x = 50
        for mot in ligne.split():
            lm = d.textlength(mot, font=f)
            if cibles and re.sub(r"\W", "", mot.lower()) in cibles:
                dt.rectangle((x - 7, y + 5, x + lm + 7, y + taille + 9), fill=C.VIOLET + (255,))
            dt.text((x, y), mot, font=f, fill=(255, 255, 255, 255))
            x += lm + d.textlength(" ", font=f)
        y += taille + 14
    zone_haut = 0 if fmt == "origine" else y + 24
    bas_reserve = int(H * .20) if (fmt == "story" or (fmt == "origine" and portrait)) else 70
    if credit:
        d.text((50, H - bas_reserve - 46 if bas_reserve > 70 else H - 52), f"Source : {credit}"[:70],
               font=C.police("Montserrat.ttf", 24, "Medium"), fill=(255, 255, 255, 210))
    if fmt == "origine":
        return img, (0, 0, W, H), titre_img
    zone_bas = H - bas_reserve - (60 if fmt == "story" else 0)
    return img, (0, zone_haut, W, max(200, zone_bas - zone_haut)), titre_img


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


def monte(source: str, sortie: str, fmt: str, debut: float, fin: float, calque_png: str, zone,
          taille: tuple[int, int] | None = None, titre_png: str | None = None) -> None:
    W, H = taille or FORMATS[fmt]
    x, y, w, h = zone
    duree = max(1.0, fin - debut)
    fin_titre = duree_titre(duree)
    filtre = (f"[0:v]split=2[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"boxblur=28:6,eq=brightness=-0.35[fond];"
              f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease,setsar=1[clip];"
              f"[fond][clip]overlay=(W-w)/2:{y}+({h}-h)/2[v0];[v0][1:v]overlay=0:0[v1];"
              + (f"[2:v]format=rgba,fade=t=out:st={fin_titre:.2f}:d=0.7:alpha=1[titre];[v1][titre]overlay=0:0[v2];"
                 if titre_png else "[v1]null[v2];")
              + f"[v2]fps=30,format=yuv420p,fade=t=in:d=0.25,fade=t=out:st={max(0, duree - 0.4):.2f}:d=0.4[v]")
    from core.services.social.encodage import AUDIO_HQ, FIN, VIDEO_HQ
    cmd = [ffmpeg(), "-y", "-v", "error", "-ss", f"{debut:.2f}", "-t", f"{duree:.2f}", "-i", source,
           "-loop", "1", "-t", f"{duree:.2f}", "-i", calque_png,
           *(["-loop", "1", "-t", f"{duree:.2f}", "-i", titre_png] if titre_png else []),
           "-filter_complex", filtre, "-map", "[v]", "-map", "0:a?",
           "-af", f"loudnorm=I=-14:TP=-1.5,afade=t=out:st={max(0, duree - 0.5):.2f}:d=0.5",
           *VIDEO_HQ, *AUDIO_HQ, *FIN, "-shortest", sortie]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    if r.returncode != 0:
        raise RuntimeError("montage : " + (r.stderr or "")[-300:])


# ---------------------------------------------------------------- ensemble

def traite(job_id: int) -> dict:
    job = db.one("SELECT * FROM studio_jobs WHERE id = ?", [job_id])
    if not job:
        raise RuntimeError("tâche introuvable")
    p = job["params"] if isinstance(job["params"], dict) else json.loads(job["params"] or "{}")
    if p.get("type") == "photos":   # section Photos : récupérer les images d'un post pour la banque de l'artiste
        from core.services.social import studio_photos
        try:
            if p.get("publier_indices"):
                return studio_photos.publie(job_id, job, p, _maj)
            if p.get("mode") == "profil":
                return studio_photos.traite_profil(job_id, job, p, _maj)
            return studio_photos.traite(job_id, job, p, _maj)
        except Exception as exc:  # noqa: BLE001
            _maj(job_id, statut="erreur", erreur=str(exc)[:500])
            raise
    fmt = p.get("format") if p.get("format") in FORMATS else "origine"
    with tempfile.TemporaryDirectory(prefix=f"cauri-studio-{job_id}-") as tmp:
        try:
            _maj(job_id, statut="telechargement", erreur=None)
            source, infos = telecharge(job["lien"], tmp)
            longueur = float(infos.get("duration") or 0) or None
            debut = max(0.0, float(p.get("debut") or 0))
            fin = float(p.get("fin") or 60)
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
            png_titre = os.path.join(tmp, "titre.png"); titre_img.save(png_titre)
            nom = f"studio-{job_id}-{os.urandom(3).hex()}"
            video = os.path.join(tmp, nom + ".mp4"); vignette = os.path.join(tmp, nom + ".jpg")
            monte(source, video, fmt, debut, fin, png, zone, taille, png_titre)
            subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", "1.5", "-i", video, "-frames:v", "1", "-q:v", "3", vignette],
                           capture_output=True, timeout=60)
            storage.store_media("social", nom + ".mp4", open(video, "rb").read(), "video/mp4")
            from core.services.social.encodage import copie_telegram
            tg = copie_telegram(video)   # Telegram : copie sous 20 Mo ; Instagram, TikTok et Facebook gardent la haute qualité
            if tg:
                storage.store_media("social", os.path.basename(tg), open(tg, "rb").read(), "video/mp4")
            storage.store_media("social", nom + ".jpg", open(vignette, "rb").read(), "image/jpeg")
            _maj(job_id, statut="pret", video=nom + ".mp4", vignette=nom + ".jpg", params=p)
            return {"statut": "pret", "video": nom + ".mp4"}
        except Exception as exc:  # noqa: BLE001
            _maj(job_id, statut="erreur", erreur=str(exc)[:500])
            raise
