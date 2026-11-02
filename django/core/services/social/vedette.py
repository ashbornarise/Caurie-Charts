"""Posts « mise en valeur » d'un artiste avec les meilleures photos de notre banque (demande du fondateur, 02/11/2026).

Un seul moteur (rendre) réglé par un modèle : 10 modèles de base, et chaque exemple importé devient un modèle de plus
(Gemini lit l'image et la traduit en réglages), gardé pour les prochaines fois (table vedette_modeles).

Réglages d'un modèle :
  fond          photo | photo_sombre | flou | uni | degrade        couleurs : fond1, fond2, titre, accent (hex)
  sujet         plein (photo entière) | detoure (artiste détouré)  sujet_taille (part de la hauteur), sujet_x (0 à 1)
  titre_pos     haut | centre | bas            titre_derriere : le titre passe derrière l'artiste (effet « NUMBER ONE »)
  police        fichier de resources/fonts     casse : maj | normal     titre_taille : 0,5 à 1,4 (1 = toute la largeur)
  contour       titre en contour (lettres vides)                 repete : nombre de répétitions du titre (effet écho)
  nb            photo en noir et blanc         voile : 0 à 1 (assombrit pour lire le texte)
  cadre         aucun | verre (carte en verre en bas) | bandeau (bande blanche en bas)
  alignement    centre | gauche                logo_clair : logo et petits textes en sombre (fonds clairs)
Textes : titre (le grand texte), sur_titre (nom de l'artiste, feat.), bas (une ligne : chiffres, classement), credit.
Rien n'est inventé : chiffres et titres viennent de nos données ; la photo est une vraie photo validée de la banque.
"""
import io
import json
import re

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from core import db
from core.services.social import couverture2026 as C
from core.services.social.pourtoi import FORMATS, RES

POLICES = sorted(p.name for p in (RES / "fonts").glob("*.ttf"))

BASE = {
    "geant": {"nom": "Titre géant derrière l'artiste", "fond": "photo_sombre", "voile": .35, "sujet": "detoure", "sujet_taille": .9,
              "sujet_x": .5, "titre_pos": "haut", "titre_derriere": True, "police": "ArchivoBlack-Regular.ttf", "casse": "maj",
              "titre": "#FFFFFF", "accent": "#FFFFFF"},
    "magazine": {"nom": "Couverture magazine", "fond": "degrade", "fond1": "#EAF5FF", "fond2": "#FFFFFF", "sujet": "detoure",
                 "sujet_taille": .82, "sujet_x": .5, "titre_pos": "haut", "titre_derriere": True, "police": "DMSerifDisplay-Regular.ttf",
                 "casse": "normal", "titre": "#0E1228", "accent": "#7A3CF5", "logo_clair": True},
    "verre": {"nom": "Carte en verre", "fond": "photo", "sujet": "plein", "cadre": "verre", "titre_pos": "bas",
              "police": "Montserrat.ttf", "poids": "ExtraBold", "casse": "normal", "titre": "#0E1228", "accent": "#7A3CF5",
              "titre_taille": .6, "alignement": "gauche"},
    "contour": {"nom": "Contour en écho", "fond": "degrade", "fond1": "#7A3CF5", "fond2": "#120A2E", "sujet": "detoure",
                "sujet_taille": .86, "titre_pos": "centre", "titre_derriere": True, "contour": True, "repete": 3,
                "police": "Anton-Regular.ttf", "casse": "maj", "titre": "#FFFFFF", "accent": "#B794FF"},
    "noirblanc": {"nom": "Noir et blanc, titre violet", "fond": "photo", "nb": True, "voile": .45, "sujet": "plein", "titre_pos": "bas",
                  "police": "BebasNeue-Regular.ttf", "casse": "maj", "titre": "#B794FF", "accent": "#FFFFFF", "alignement": "gauche"},
    "affiche": {"nom": "Affiche couleur", "fond": "uni", "fond1": "#38BDF8", "sujet": "detoure", "sujet_taille": .8, "sujet_x": .64,
                "titre_pos": "haut", "titre_derriere": False, "police": "Unbounded.ttf", "poids": "Black", "casse": "maj",
                "titre": "#0E1228", "accent": "#FFFFFF", "alignement": "gauche", "titre_taille": .75, "logo_clair": True},
    "minimal": {"nom": "Plein cadre minimal", "fond": "photo", "voile": .3, "sujet": "plein", "titre_pos": "bas",
                "police": "Syne.ttf", "poids": "ExtraBold", "casse": "normal", "titre": "#FFFFFF", "accent": "#38BDF8",
                "alignement": "gauche", "titre_taille": .55},
    "bandeau": {"nom": "Bandeau blanc", "fond": "photo", "sujet": "plein", "cadre": "bandeau", "titre_pos": "bas",
                "police": "LeagueSpartan.ttf", "poids": "Black", "casse": "maj", "titre": "#0E1228", "accent": "#7A3CF5", "titre_taille": .8},
    "flou": {"nom": "Fond flou, artiste net", "fond": "flou", "voile": .3, "sujet": "detoure", "sujet_taille": .88,
             "titre_pos": "centre", "titre_derriere": True, "police": "ClimateCrisis.ttf", "casse": "maj", "titre": "#FFFFFF",
             "accent": "#FFFFFF", "titre_taille": .9},
    "chiffre": {"nom": "Chiffre géant", "fond": "degrade", "fond1": "#120A2E", "fond2": "#5B2BD6", "sujet": "detoure",
                "sujet_taille": .84, "titre_pos": "centre", "titre_derriere": True, "police": "DelaGothicOne-Regular.ttf",
                "casse": "maj", "titre": "#38BDF8", "accent": "#FFFFFF", "chiffre": True},
}


def tables() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS vedette_modeles (id SERIAL PRIMARY KEY, nom VARCHAR(80) NOT NULL, reglages TEXT NOT NULL,
              exemple VARCHAR(200) NULL, cree_le TIMESTAMPTZ DEFAULT NOW())""")


def modeles() -> dict:
    """Les 10 modèles de base, puis les modèles tirés des exemples importés (« m12 »…)."""
    tables()
    out = {k: dict(v) for k, v in BASE.items()}
    for r in db.all("SELECT id, nom, reglages, exemple FROM vedette_modeles ORDER BY id"):
        try:
            out[f"m{r['id']}"] = {**json.loads(r["reglages"]), "nom": r["nom"], "exemple": r["exemple"]}
        except ValueError:
            continue
    return out


def photos(artist_id: int, n: int = 12) -> list:
    """Les meilleures photos validées de l'artiste (note de qualité, plans larges d'abord pour le détourage)."""
    from core import storage
    base = storage.blob_public_url()
    return [{"id": r["id"], "url": f"{base}/media/artists/plans/{r['fichier']}", "credit": r.get("credit") or "",
             "entiere": bool(r["plan_large"])}
            for r in db.all("""SELECT id, fichier, credit, plan_large FROM artist_photos WHERE artist_id = ?
                               ORDER BY COALESCE(score, 0.5) DESC, plan_large DESC, id DESC LIMIT ?""", [artist_id, n])]


def textes_proposes(artist_id: int) -> dict:
    """Textes tirés de nos vraies données : titre du moment, meilleure place de la semaine, auditeurs Spotify."""
    a = db.one("SELECT id, name, slug FROM artists WHERE id = ?", [artist_id]) or {}
    titre = db.one("""SELECT t.title, MIN(o.position) AS pos, c.code FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                      JOIN countries c ON c.id = o.country_id WHERE t.artist_id = ? AND o.observed_on >= CURRENT_DATE - 7
                      GROUP BY t.title, c.code ORDER BY MIN(o.position) LIMIT 1""", [artist_id])
    sp = None
    try:
        sp = db.value("SELECT auditeurs FROM spotify_artistes WHERE artist_id = ? ORDER BY releve_le DESC LIMIT 1", [artist_id])
    except Exception:  # noqa: BLE001
        pass
    bas = []
    if sp:
        from core.jinja import _fmt_court
        bas.append(f"{_fmt_court(sp)} auditeurs Spotify par mois")
    if titre and titre.get("pos"):
        from core.helpers import country_name
        bas.append(f"N°{int(titre['pos'])} · {country_name(titre['code'])} cette semaine")
    nom_titre = re.split(r"\s+(?:feat\.?|ft\.?|featuring|&|x)\s+|\s*[(\[]", C.propre((titre or {}).get("title") or ""), flags=re.I)[0].strip()
    return {"titre": nom_titre or a.get("name") or "", "sur_titre": a.get("name") or "", "bas": " · ".join(bas),
            "chiffre": _fmt_chiffre(sp) if sp else ""}


def _fmt_chiffre(n) -> str:
    n = int(n or 0)
    return f"{n / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + "M" if n >= 1_000_000 else (f"{round(n / 1000)}K" if n >= 1000 else str(n))


# ---------------------------------------------------------------- rendu

def _hex(c, defaut=(255, 255, 255)) -> tuple:
    c = str(c or "").lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) if re.fullmatch(r"[0-9a-fA-F]{6}", c) else defaut


def _police(m: dict, taille: int):
    nom = m.get("police") if m.get("police") in POLICES else "Montserrat.ttf"
    return C.police(nom, max(8, int(taille)), m.get("poids"))


def _ajuste(m: dict, lignes: list, largeur: int, hauteur_max: int):
    """La plus grande taille où chaque ligne tient dans la largeur et l'ensemble dans la hauteur."""
    taille = int(hauteur_max / max(1, len(lignes)) / 1.05)
    while taille > 20:
        f = _police(m, taille)
        larg = max(f.getbbox(l)[2] - f.getbbox(l)[0] for l in lignes)
        if larg <= largeur:
            return f, taille
        taille = int(taille * .94)
    return _police(m, taille), taille


def _coupe(titre: str, maj: bool) -> list:
    t = (titre or "").strip()
    t = t.upper() if maj else t
    if "\n" in t:
        return [l.strip() for l in t.split("\n") if l.strip()][:3]
    mots = t.split()
    if len(mots) <= 1 or len(t) <= 12:
        return [t]
    # deux lignes équilibrées
    meilleur, ecart = [t], 10 ** 6
    for i in range(1, len(mots)):
        a, b = " ".join(mots[:i]), " ".join(mots[i:])
        if abs(len(a) - len(b)) < ecart:
            meilleur, ecart = [a, b], abs(len(a) - len(b))
    return meilleur


def _fond(m: dict, im, w: int, h: int) -> Image.Image:
    f = m.get("fond", "photo")
    if f in ("photo", "photo_sombre", "flou") and im is not None:
        c = C.cadre_personne(im, w, h)
        if m.get("nb"):
            c = ImageOps.grayscale(c).convert("RGB")
        if f == "flou":
            c = c.filter(ImageFilter.GaussianBlur(w / 30))
        voile = float(m.get("voile") or (.45 if f == "photo_sombre" else 0))
        if voile:
            c = Image.blend(c, Image.new("RGB", (w, h), (8, 8, 18)), min(.8, voile))
        return c
    a, b = _hex(m.get("fond1"), (234, 245, 255)), _hex(m.get("fond2") or m.get("fond1"), (255, 255, 255))
    if f == "uni":
        return Image.new("RGB", (w, h), a)
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        k = y / (h - 1)
        grad.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3)))
    return grad.resize((w, h))


def _logo(c: Image.Image, u: float, clair: bool) -> None:
    d_ = int(92 * u)
    C._logo(c, int(60 * u), int(60 * u), d_)
    if clair:   # le mot « cauricharts » écrit en blanc par C._logo : on le repasse en sombre sur fond clair
        ImageDraw.Draw(c).text((int(60 * u) + d_ + 16, int(60 * u) + d_ * .28), "cauricharts",
                               font=C.police("Jost.ttf", int(d_ * .42), "SemiBold"), fill=(14, 18, 40))


_CACHE: dict = {}


def _prepare(photo, detourer: bool):
    """Photo améliorée et artiste détouré, calculés une seule fois par photo (10 modèles = 1 détourage)."""
    cle = str(photo)
    if cle not in _CACHE:
        _CACHE.clear()
        _CACHE[cle] = {"im": C._image_nette(photo) if photo is not None else None}
    e = _CACHE[cle]
    if detourer and "sujet" not in e:
        e["sujet"] = C.detoure(e["im"]) if e["im"] is not None else None
    return e["im"], (e.get("sujet") if detourer else None)


def rendre(m: dict, photo, textes: dict, fmt: str = "feed") -> Image.Image:
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    textes = {k: (C.propre(v) if isinstance(v, str) and k != "credit" else v) for k, v in (textes or {}).items()}   # jamais d'émoji
    im, sujet = _prepare(photo, m.get("sujet") == "detoure")
    c = _fond(m, im, w, h).convert("RGBA")
    if m.get("sujet") == "detoure" and sujet is None and im is not None:
        # détourage impossible : la photo entière, assombrie, plutôt qu'une image ratée
        c = Image.blend(C.cadre_personne(im, w, h), Image.new("RGB", (w, h), (8, 8, 18)), .35).convert("RGBA")
    maj = m.get("casse", "maj") == "maj"
    titre_txt = textes.get("chiffre") if m.get("chiffre") and textes.get("chiffre") else textes.get("titre", "")
    lignes = _coupe(titre_txt, maj)
    couleur, accent = _hex(m.get("titre")), _hex(m.get("accent"))
    gauche = m.get("alignement") == "gauche"
    marge = int(70 * u)
    cadre = m.get("cadre", "aucun")
    clair = bool(m.get("logo_clair"))

    # zone du titre
    larg = int((w - 2 * marge) * min(1.4, max(.4, float(m.get("titre_taille") or 1))))
    haut_max = int(h * (.34 if cadre == "aucun" else .16) * min(1.4, max(.4, float(m.get("titre_taille") or 1))))
    if m.get("chiffre"):
        haut_max = int(h * .42)
    f, taille = _ajuste(m, lignes, larg, haut_max)
    pas = int(taille * 1.02)
    bloc = pas * len(lignes)
    pos = m.get("titre_pos", "haut")
    if cadre == "bandeau":
        y0 = h - int(h * .2) + (int(h * .2) - bloc) // 2
    elif cadre == "verre":
        y0 = h - int(h * .26) + int(60 * u)
    elif pos == "haut":
        y0 = int(250 * u) if textes.get("sur_titre") else int(200 * u)   # sous le logo et le nom de l'artiste
    elif pos == "centre":
        y0 = int(h * .36) - bloc // 2
    else:
        y0 = h - bloc - int(h * .11)

    calque = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dc = ImageDraw.Draw(calque)

    def ecrit(y, alpha=255):
        for i, l in enumerate(lignes):
            bb = f.getbbox(l)
            lw = bb[2] - bb[0]
            x = marge if gauche else (w - lw) // 2 - bb[0]
            if m.get("contour"):
                dc.text((x, y + i * pas - bb[1]), l, font=f, fill=(0, 0, 0, 0), stroke_width=max(2, int(taille / 40)),
                        stroke_fill=couleur + (alpha,))
            else:
                dc.text((x, y + i * pas - bb[1]), l, font=f, fill=couleur + (alpha,))

    if cadre == "bandeau":
        dc.rectangle((0, h - int(h * .2), w, h), fill=(255, 255, 255, 255))
    if cadre == "verre":
        boite = (marge, h - int(h * .28), w - marge, h - int(h * .05))
        zone = c.crop(boite).filter(ImageFilter.GaussianBlur(28 * u))
        c.paste(zone, boite[:2])
        dc.rounded_rectangle(boite, radius=int(40 * u), fill=(255, 255, 255, 185), outline=(255, 255, 255, 230), width=int(3 * u))
    repete = int(m.get("repete") or 0)
    for k in range(repete, 0, -1):   # échos du titre au-dessus et au-dessous
        ecrit(y0 - k * bloc, 255 // (k + 2)); ecrit(y0 + k * bloc, 255 // (k + 2))
    ecrit(y0)

    if sujet is not None and m.get("titre_derriere"):
        c.alpha_composite(calque); calque = None
    if sujet is not None:
        hs = int(h * float(m.get("sujet_taille") or .85))
        sj = sujet.resize((max(1, int(sujet.width * hs / sujet.height)), hs), Image.LANCZOS)
        if sj.width > w * 1.05:
            ws = int(w * 1.05); sj = sj.resize((ws, int(sj.height * ws / sj.width)), Image.LANCZOS)
        x = int(w * float(m.get("sujet_x") or .5) - sj.width / 2)
        ombre = Image.new("RGBA", sj.size, (0, 0, 0, 0)); ombre.putalpha(sj.getchannel("A").point(lambda a: int(a * .45)))
        c.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(24 * u)), (x + int(12 * u), h - sj.height + int(10 * u)))
        c.alpha_composite(sj, (x, h - sj.height))
    if calque is not None:
        c.alpha_composite(calque)

    d = ImageDraw.Draw(c)
    petit = C.police("Montserrat.ttf", int(34 * u), "Bold")
    sombre = cadre in ("bandeau", "verre") or clair
    ton = (14, 18, 40) if sombre else (255, 255, 255)
    st = (textes.get("sur_titre") or "").upper()
    if st:
        bb = petit.getbbox(st)
        y_st = y0 - int(64 * u)
        if cadre == "verre":
            y_st = h - int(h * .28) + int(24 * u)
        elif pos == "haut" or (sujet is not None and m.get("titre_derriere")):
            y_st = int(180 * u)   # titre derrière l'artiste : le nom en haut, jamais sur son visage
        x = marge + (int(30 * u) if cadre == "verre" else 0) if gauche or cadre == "verre" else (w - (bb[2] - bb[0])) // 2
        d.text((x, max(int(170 * u), y_st)) if y_st != int(180 * u) else (x, y_st), st, font=petit, fill=accent if not sombre else _hex(m.get("accent"), (122, 60, 245)))
    bas = textes.get("bas") or ""
    if bas:
        fb = C.police("Montserrat.ttf", int(30 * u), "SemiBold")
        bb = fb.getbbox(bas)
        y_b = h - int(h * .055) - (bb[3] - bb[1]) if cadre != "bandeau" else h - int(46 * u)
        if cadre == "aucun" and pos == "bas":
            y_b = h - int(h * .045)
        x = (marge + (int(30 * u) if cadre == "verre" else 0)) if (gauche or cadre == "verre") else (w - (bb[2] - bb[0])) // 2
        if cadre == "aucun":   # pastille sous la ligne du bas : lisible même sur les pieds de l'artiste
            pastille = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            fond_p = (255, 255, 255, 200) if sombre else (8, 8, 18, 150)
            ImageDraw.Draw(pastille).rounded_rectangle((x - int(18 * u), y_b - int(22 * u), x + bb[2] - bb[0] + int(18 * u), y_b + bb[3] + int(6 * u)),
                                                       radius=int(30 * u), fill=fond_p)
            c.alpha_composite(pastille); d = ImageDraw.Draw(c)
        d.text((x, y_b - int(10 * u)), bas, font=fb, fill=ton)
    _logo(c, u, clair and cadre == "aucun")
    if textes.get("credit"):
        fc = C.police("Montserrat.ttf", int(20 * u), "Medium")
        cr = textes["credit"][:60]
        d.text((w - marge - fc.getbbox(cr)[2], int(78 * u)), cr, font=fc, fill=(14, 18, 40) if clair else (235, 235, 245))
    return c.convert("RGB")


# ---------------------------------------------------------------- modèle tiré d'un exemple importé

def modele_depuis_exemple(image: bytes, nom: str) -> dict:
    """Gemini lit l'exemple et le traduit en réglages du moteur ; le modèle est gardé pour les prochaines fois."""
    import base64

    import requests

    from core import env, storage
    from core.services import ia_budget
    from core.services.social.comptes import MODELES, URL
    tables()
    cle = env.get("GEMINI_API_KEY", "")
    if not cle or not ia_budget.peut("gemini"):
        raise RuntimeError("Gemini indisponible ou budget du jour atteint : réessaie demain")
    im = Image.open(io.BytesIO(image)).convert("RGB"); im.thumbnail((1080, 1080))
    tampon = io.BytesIO(); im.save(tampon, format="JPEG", quality=85)
    schema = {k: v for k, v in BASE["geant"].items() if k != "nom"}
    consigne = ("Voici une affiche de musique. Décris sa mise en page avec ces réglages, au format JSON, sans rien ajouter :\n"
                + json.dumps(schema, ensure_ascii=False) +
                "\nValeurs possibles : fond = photo|photo_sombre|flou|uni|degrade ; sujet = plein|detoure ; titre_pos = haut|centre|bas ; "
                "cadre = aucun|verre|bandeau ; alignement = centre|gauche ; casse = maj|normal ; couleurs en hexadécimal ; "
                "voile, sujet_taille, sujet_x, titre_taille entre 0 et 1,4 ; titre_derriere, contour, nb, logo_clair en true/false ; "
                "repete : entier de 0 à 3. police : la plus proche parmi " + ", ".join(POLICES) + ".")
    corps = {"contents": [{"role": "user", "parts": [{"text": consigne},
                                                     {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(tampon.getvalue()).decode()}}]}],
             "generationConfig": {"temperature": .2, "responseMimeType": "application/json", "thinkingConfig": {"thinkingLevel": "low"}}}
    d = {}
    for modele in MODELES:
        r = requests.post(URL.format(modele), headers={"x-goog-api-key": cle}, json=corps, timeout=90)
        d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 200:
            break
    ia_budget.gemini_usage(d)
    texte = "".join(p.get("text", "") for p in (((d.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []))
    bloc = re.search(r"\{.*\}", texte, re.S)
    if not bloc:
        raise RuntimeError("Gemini n'a pas su lire cet exemple")
    brut = json.loads(bloc.group(0))
    reglages = {k: brut[k] for k in schema if k in brut}
    if reglages.get("police") not in POLICES:
        reglages["police"] = "Montserrat.ttf"
    nom_fichier = f"vedette-exemple-{re.sub(r'[^a-z0-9]+', '-', nom.lower())[:40]}-{abs(hash(image)) % 10 ** 6}.jpg"
    storage.store_media("social", nom_fichier, tampon.getvalue(), "image/jpeg")
    mid = db.insert("vedette_modeles", {"nom": nom[:80] or "Mon modèle", "reglages": json.dumps(reglages, ensure_ascii=False),
                                         "exemple": nom_fichier})
    return {"id": f"m{mid}", "nom": nom, **reglages}


# ---------------------------------------------------------------- tâches du Studio (fabriquées sur GitHub : détourage)

def traite(job_id: int, job: dict, p: dict, maj) -> dict:
    """Étape 1 : un aperçu par modèle choisi (format carré-portrait), déposés sur le Blob ; le fondateur choisit."""
    from core import storage
    maj(job_id, statut="montage")
    tous = modeles()
    choisis = [k for k in (p.get("modeles") or list(BASE)) if k in tous][:12]
    base = storage.blob_public_url()
    apercus = []
    for k in choisis:
        im = rendre(tous[k], p["photo"], p.get("textes") or {}, "feed")
        im.thumbnail((1080, 1350))
        out = io.BytesIO(); im.save(out, format="JPEG", quality=86)
        nom = f"vedette-{job_id}-{k}.jpg"
        storage.store_media("social", nom, out.getvalue(), "image/jpeg")
        apercus.append({"modele": k, "nom": tous[k].get("nom"), "url": f"{base}/media/social/{nom}"})
    p["apercus"] = apercus
    db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False), "statut": "a_choisir",
                              "vignette": f"vedette-{job_id}-{choisis[0]}.jpg" if choisis else None}, "id = :id", {"id": job_id})
    return {"statut": "a_choisir", "video": f"{len(apercus)} aperçu(s)"}


def publie(job_id: int, job: dict, p: dict, maj) -> dict:
    """Étape 2 : le modèle choisi en carré-portrait et en story, légende FR + EN, envoi via Buffer."""
    from datetime import datetime, timedelta, timezone

    from core.services import buffer
    from core.services.social import editorial as E
    from core.services.social import image as PI
    from core.studio import theme_libre
    maj(job_id, statut="montage")
    m = modeles().get(p.get("choix")) or BASE["geant"]
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"vedette-{job_id}-final"
    for fmt, suf in (("feed", ""), ("story", "-916")):
        PI.save_jpeg(rendre(m, p["photo"], p.get("textes") or {}, fmt), PI.DIR / f"{nom}{suf}.jpg")
    db.run("UPDATE artist_photos SET utilise_le = NOW() WHERE id = ?", [p.get("photo_id")])
    t = p.get("textes") or {}
    artiste = p.get("artiste_nom") or t.get("sur_titre") or ""
    credit = f"\n\n📸 {t['credit']}" if t.get("credit") else ""
    legende = (p.get("legende_fr") or t.get("titre") or artiste) + credit
    maintenant = datetime.now(timezone.utc)
    faits = {"kind": "format-studio-photos", "studio_job": job_id, "due": (maintenant + timedelta(minutes=2)).isoformat(),
             "notifier": bool(p.get("notifier")), "reseaux": p.get("reseaux"), "artiste": artiste, "etiquette": "vedette"}
    if p.get("legende_en"):
        faits["en"] = {"title": t.get("titre") or artiste, "caption": p["legende_en"] + credit}
    post = E.save_post(theme_libre(job_id, maintenant), maintenant.date().isoformat(), (t.get("titre") or artiste)[:160], legende,
                       "#cauricharts", [{"file": f"{nom}.jpg", "tiktok": f"{nom}-916.jpg", "label": artiste}], faits)
    resultat = buffer.schedule(post, maintenant + timedelta(minutes=2))
    recus = [r["reason"] for r in db.all("SELECT reason FROM audit_log WHERE reason LIKE ?", [f"post-{post['id']}-%"])]
    maj(job_id, statut="envoye" if recus else "erreur", post_id=post["id"],
        erreur=None if recus else f"aucun réseau n'a accepté le visuel : {resultat}"[:500])
    return {"statut": "envoye", "video": f"post {post['id']}"}
