"""Couvertures « Pour toi » : le style des posts qui marchent dans le fil Instagram (analyse du 17/10/2026, 8 posts de
120rap, Instrurap, Interlude, Billboard Paris, HypeTribe, GamesChanger…).

  - une photo plein cadre, un visage qui remplit l'écran (qualité presse) ;
  - un titre énorme de 4 à 8 mots en bas, en capitales condensées, UN mot (ou chiffre) en couleur ;
  - un petit logo, rien d'autre : ni sous-titre, ni sources, ni date sur l'image (tout cela va dans la légende) ;
  - « trio » : trois visages côte à côte, chacun avec son nom et son chiffre, pour les classements et comparaisons.
La musique est ajoutée à la main dans Instagram (le fondateur) : c'est elle qui fait pousser le post."""
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RES = Path(__file__).resolve().parents[4] / "resources"
FORMATS = {"feed": (2160, 2700), "story": (2160, 3840), "article": (1920, 1080)}   # article : image 16:9 du site
ACCENTS = [(255, 59, 48), (255, 122, 26), (47, 168, 255), (46, 224, 122), (155, 102, 255), (255, 214, 10)]
BLANC = (255, 255, 255)


def police(taille: int, nom: str = "Anton-Regular.ttf"):
    return ImageFont.truetype(str(RES / "fonts" / nom), taille)


def charge(src) -> Image.Image | None:
    """Image depuis une adresse web, un chemin local ou des octets."""
    try:
        if isinstance(src, Image.Image):
            return src.convert("RGB")
        if isinstance(src, (bytes, bytearray)):
            return Image.open(BytesIO(src)).convert("RGB")
        if str(src).startswith("http"):
            from core.services.news import http_get
            return Image.open(BytesIO(http_get(str(src), binary=True))).convert("RGB")
        return Image.open(src).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def cadre(im: Image.Image, w: int, h: int, haut: float = 0.18) -> Image.Image:
    """Recadre en w × h en gardant le haut de l'image (les visages sont rarement en bas d'une photo d'artiste)."""
    r = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x = (im.width - w) // 2
    y = int(max(0, min(im.height - h, (im.height - h) * haut)))
    out = im.crop((x, y, x + w, y + h))
    out = ImageEnhance.Contrast(out).enhance(1.06)
    return ImageEnhance.Color(out).enhance(1.05)


def _degrade(img: Image.Image, debut: float, fort: int = 240) -> None:
    w, h = img.size
    ombre = Image.new("L", (1, h), 0)
    for y in range(h):
        t = (y / h - debut) / (1 - debut)
        ombre.putpixel((0, y), int(fort * max(0.0, min(1.0, t)) ** 1.25))
    noir = Image.new("RGB", (w, h), (8, 8, 12))
    img.paste(noir, (0, 0), ombre.resize((w, h)))


def _mots_accent(titre: str, accent: str | None) -> set:
    """Mot(s) mis en couleur : celui demandé, sinon le premier chiffre, sinon le dernier mot."""
    mots = titre.split()
    if accent:
        return {m.upper() for m in accent.split()}
    for m in mots:
        if re.search(r"\d", m):
            return {m.upper()}
    return {mots[-1].upper()} if mots else set()


def _titre(d: ImageDraw.ImageDraw, titre: str, accent: str | None, couleur, x: int, bas: int, largeur: int, max_lignes: int = 3,
           taille_max: int = 300) -> int:
    """Titre en capitales, la plus grande taille qui tient en max_lignes, aligné en bas à « bas ». Rend le haut du bloc."""
    titre = titre.upper().strip()
    colores = _mots_accent(titre, accent.upper() if accent else None)
    for taille in range(taille_max, 90, -6):
        f = police(taille)
        lignes, cur = [], ""
        for m in titre.split():
            essai = (cur + " " + m).strip()
            if d.textlength(essai, font=f) <= largeur:
                cur = essai
            else:
                lignes.append(cur); cur = m
        lignes.append(cur)
        if len(lignes) <= max_lignes and all(d.textlength(l, font=f) <= largeur for l in lignes):
            break
    interligne = int(taille * 0.98)
    y = bas - interligne * len(lignes)
    haut = y
    for l in lignes:
        cx = x + (largeur - d.textlength(l, font=f)) / 2
        for i, m in enumerate(l.split()):
            mot = m + (" " if i < len(l.split()) - 1 else "")
            fill = couleur if m.strip("«»?!.,:") in colores or m in colores else BLANC
            d.text((cx + 6, y + 8), mot, font=f, fill=(0, 0, 0))   # ombre portée légère
            d.text((cx, y), mot, font=f, fill=fill)
            cx += d.textlength(mot, font=f)
        y += interligne
    return haut


def _marque(img: Image.Image, x: int, y: int, taille: int = 330) -> None:
    logo = Image.open(RES / "marque" / "logo-blanc.png").convert("RGBA")
    logo = logo.resize((taille, round(logo.height * taille / logo.width)), Image.LANCZOS)
    img.paste(logo, (x, y), logo)


def _filet(d, x0, x1, y, couleur, texte="CAURI CHARTS"):
    """Filet horizontal coupé au centre par le nom du média (comme les posts de référence)."""
    f = police(40, "Poppins-Bold.ttf")
    tw = d.textlength(texte, font=f)
    cx = (x0 + x1) / 2
    d.line([(x0, y), (cx - tw / 2 - 30, y)], fill=BLANC, width=5)
    d.line([(cx + tw / 2 + 30, y), (x1, y)], fill=BLANC, width=5)
    d.text((cx - tw / 2, y - 26), texte, font=f, fill=couleur)


def une(photo, titre: str, accent: str | None = None, fmt: str = "feed", couleur=None, haut: float = 0.18,
        surtitre: str | None = None) -> Image.Image:
    """Un visage plein cadre, le titre énorme en bas, un mot en couleur, le logo en haut à gauche."""
    w, h = FORMATS[fmt]
    couleur = couleur or ACCENTS[len(titre) % len(ACCENTS)]
    im = charge(photo)
    img = cadre(im, w, h, haut) if im else Image.new("RGB", (w, h), (20, 20, 28))
    _degrade(img, 0.42 if fmt == "feed" else 0.5)
    d = ImageDraw.Draw(img)
    if fmt == "article":                               # 16:9 du site : titre plus petit, sur deux lignes
        marge = 90
        y_titre = _titre(d, titre, accent, couleur, marge, h - 80, w - 2 * marge, max_lignes=2, taille_max=170)
        _filet(d, marge, w - marge, y_titre - 50, couleur)
        _marque(img, 70, 60, 220)
        return img
    marge = 120
    bas = h - (230 if fmt == "feed" else 560)          # 9:16 : au-dessus de la légende et des boutons des applis
    y_titre = _titre(d, titre, accent, couleur, marge, bas, w - 2 * marge)
    _filet(d, marge, w - marge, y_titre - 70, couleur)
    if surtitre:
        f = police(56, "Poppins-Bold.ttf")
        d.text(((w - d.textlength(surtitre.upper(), font=f)) / 2, y_titre - 190), surtitre.upper(), font=f, fill=BLANC)
    _marque(img, 110, 110 if fmt == "feed" else 260)
    return img


# ---------------------------------------------------------------- affiche : l'artiste détouré sur un décor généré
def _detoure(im: Image.Image):
    """(photo RGBA recadrée sur le sujet, masque) ou None : sans rembg, sujet trop petit ou détourage raté."""
    try:
        from core.services.social import une as U
        if not U.available():
            return None
        masque = U._mask(im)
    except Exception:  # noqa: BLE001
        return None
    boite = masque.point(lambda v: 255 if v > 60 else 0).getbbox()
    if not boite:
        return None
    bw, bh = boite[2] - boite[0], boite[3] - boite[1]
    if bw * bh < im.width * im.height * 0.08 or bw < im.width * 0.18 or bh < im.height * 0.25:
        return None
    # bord du masque resserré d'un pixel et adouci : pas de liseré de l'ancien fond
    masque = masque.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    sujet = im.convert("RGBA")
    sujet.putalpha(masque)
    sujet = sujet.crop(boite)
    # bords de la photo que le sujet touche (buste coupé en bas, bras ou cheveux coupés sur un côté)
    bords = {"bas": boite[3] >= im.height - 3, "gauche": boite[0] <= 2, "droite": boite[2] >= im.width - 3}
    return sujet, bords


def _tete(alpha: Image.Image) -> tuple:
    """Bas et centre (x) de la tête dans le sujet détouré, d'après le profil de largeur du masque : la tête s'élargit,
    le cou se resserre, les épaules s'élargissent. À défaut de cou net, une estimation prudente (tête haute)."""
    import numpy as np
    a = np.asarray(alpha, dtype=np.uint8) > 100
    h, w = a.shape
    cols = np.arange(w)
    larg = np.zeros(h)
    centre = np.full(h, w / 2)
    for y in range(h):
        xs = cols[a[y]]
        if xs.size:
            larg[y], centre[y] = xs[-1] - xs[0], (xs[-1] + xs[0]) / 2
    k = max(3, h // 60)
    lisse = np.convolve(larg, np.ones(k) / k, mode="same")
    defaut = int(min(h * 0.55, w * 0.95))
    bas = defaut
    fin = int(min(h * 0.75, w * 1.4))
    debut = int(h * 0.12)
    if fin > debut + 4:
        zone = lisse[debut:fin]
        y_min = debut + int(np.argmin(zone))
        tete = lisse[debut:y_min].max() if y_min > debut else 0
        apres = lisse[y_min:min(h, y_min + h // 4)].max() if y_min < h - 1 else 0
        # un vrai cou : plus étroit que la tête et que les épaules qui suivent
        if tete and lisse[y_min] < 0.85 * tete and apres > 1.2 * lisse[y_min]:
            bas = int(y_min + h * 0.03)
    haut_tete = a[: max(1, bas)].any(axis=1)
    cx = float(np.median(centre[: max(1, bas)][haut_tete])) if haut_tete.any() else w / 2
    return min(bas, defaut), cx


def _degrade_fond(w: int, h: int, haut, bas) -> Image.Image:
    col = Image.new("RGB", (1, 256))
    col.putdata([tuple(int(haut[c] + (bas[c] - haut[c]) * (i / 255) ** 1.1) for c in range(3)) for i in range(256)])
    return col.resize((w, h), Image.BICUBIC)


def _lumiere(img: Image.Image, cx: float, cy: float, rayon: float, couleur, force: int) -> None:
    """Halo lumineux doux (cercle très flou) ajouté en mode « écran »."""
    from PIL import ImageChops
    calque = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(calque).ellipse([cx - rayon, cy - rayon, cx + rayon, cy + rayon],
                                   fill=tuple(int(c * force / 255) for c in couleur))
    calque = calque.filter(ImageFilter.GaussianBlur(rayon * 0.45))
    img.paste(ImageChops.screen(img, calque))


def _mot_fond(img: Image.Image, mot: str, y: int, largeur: int, couleur) -> None:
    """Le grand mot du magazine, derrière l'artiste : blanc presque transparent, contour à la couleur d'accent."""
    mot = mot.upper().strip()
    if not mot:
        return
    w, _ = img.size
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    taille = 900
    while taille > 120 and d.textlength(mot, font=police(taille)) > largeur:
        taille -= 10
    f = police(taille)
    x = (w - d.textlength(mot, font=f)) / 2
    d.text((x, y), mot, font=f, fill=(255, 255, 255, 46), stroke_width=max(3, taille // 140), stroke_fill=(*couleur, 120))
    img.paste(calque, (0, 0), calque)


def affiche(photo, titre: str, accent: str | None = None, fmt: str = "feed", couleur=None, surtitre: str | None = None,
            fond: str | None = None) -> Image.Image:
    """Affiche « magazine » générée : l'artiste DÉTOURÉ et retouché (net, contrasté, éclairé par un liseré à la couleur
    d'accent) sur un décor fabriqué (dégradé, lumières, anneau, grand mot `fond` derrière lui, grain), le titre énorme
    en bas avec un mot en couleur, le logo. Le visage n'est jamais coupé ni recouvert : sa position vient du masque.
    Formats feed (4:5), story (9:16) et article (16:9, artiste à droite, titre à gauche). Sans rembg, ou si le
    détourage échoue, la une photo plein cadre sert de repli (même signature, même rendu qu'avant)."""
    from PIL import ImageChops
    w, h = FORMATS[fmt]
    couleur = tuple(couleur or ACCENTS[len(titre) % len(ACCENTS)])
    im = charge(photo)
    det = _detoure(im) if im else None
    if not det:
        return une(photo, titre, accent, fmt, couleur, surtitre=surtitre)
    sujet, bords = det
    touche_bas = bords["bas"]
    large = fmt == "article"
    # ---- décor : nuit profonde teintée par l'accent, lumières, anneau
    sombre = tuple(int(c * 0.16 + 8) for c in couleur)
    img = _degrade_fond(w, h, sombre, (6, 6, 10))
    _lumiere(img, w * (0.15 if large else 0.05), h * 0.05, max(w, h) * 0.35, (110, 170, 255), 90)    # bleu ciel
    _lumiere(img, w * 0.98, h * (0.95 if large else 0.75), max(w, h) * 0.30, (150, 100, 255), 80)    # violet
    # ---- mise en page du titre (calculée d'abord : la tête doit rester au-dessus ou à côté)
    essai = ImageDraw.Draw(Image.new("RGB", (w, h)))
    if large:
        marge, col_titre = 90, int(w * 0.50)
        cadre_titre = dict(x=marge, bas=h - 80, largeur=col_titre - marge, max_lignes=3, taille_max=180)
    else:
        marge = 120
        cadre_titre = dict(x=marge, bas=h - (230 if fmt == "feed" else 560), largeur=w - 2 * marge, max_lignes=3, taille_max=300)
    y_titre = _titre(essai, titre, accent, couleur, cadre_titre["x"], cadre_titre["bas"], cadre_titre["largeur"],
                     cadre_titre["max_lignes"], cadre_titre["taille_max"])
    # ---- place de l'artiste
    tb, tcx = _tete(sujet.getchannel("A"))
    haut = int(h * (0.10 if large else 0.085 if fmt == "feed" else 0.13))     # 9:16 : sous le profil de l'application
    limite = (h - 40) if large else (y_titre - 130)   # bas de tête autorisé (16:9 : le titre est à côté, pas dessous)
    s = (h * (0.97 if large else 0.86)) / sujet.height
    s = min(s, (w * (0.62 if large else 0.90)) / sujet.width)        # du décor visible autour de l'artiste
    if haut + tb * s > limite:
        s = (limite - haut) / tb
    if touche_bas and haut + sujet.height * s < h:          # un buste coupé doit toucher le bas de l'image
        s2 = (h - haut) / sujet.height
        s = s2 if haut + tb * s2 <= limite else s
    if not large and bords["gauche"] and bords["droite"]:     # coupé des deux côtés : il doit couvrir toute la largeur
        s_l = w / sujet.width
        s = max(s, s_l) if haut + tb * s_l <= limite else s
    sw, sh = max(1, round(sujet.width * s)), max(1, round(sujet.height * s))
    sujet = sujet.resize((sw, sh), Image.LANCZOS)
    tcx *= s
    cible = w * 0.72 if large else w / 2
    x = int(cible - tcx)
    x = max(-int(sw * 0.25), min(w - int(sw * 0.75), x)) if not large else max(col_titre - int(sw * 0.15), min(w - int(sw * 0.6), x))
    # un côté coupé dans la photo d'origine ne doit pas se voir : il est collé au bord de l'image (ou au-delà)
    # (16:9 : seul le bord droit compte, le gauche se perd dans le voile sombre du titre)
    if bords["droite"] and (large or not bords["gauche"]):
        x = max(x, w - sw)
    elif large:
        pass
    elif bords["gauche"] and not bords["droite"]:
        x = min(x, 0)
    elif bords["gauche"] and bords["droite"]:
        x = (w - sw) // 2 if sw >= w else x
    # sujet entier (pas coupé en bas) : posé plus bas pour ne pas flotter, la tête toujours au-dessus de la limite
    y = haut if touche_bas else int(max(haut, min(limite - tb * s, h * 0.96 - sh)))
    # ---- retouche : netteté modérée, contraste, couleurs, éclairage si la photo est sombre
    rgb = sujet.convert("RGB")
    from PIL import ImageStat
    lum = ImageStat.Stat(rgb.convert("L"), sujet.getchannel("A")).mean[0]
    rgb = ImageEnhance.Brightness(rgb).enhance(min(1.22, max(1.0, 118 / max(lum, 1))))
    rgb = ImageEnhance.Contrast(rgb).enhance(1.08)
    rgb = ImageEnhance.Color(rgb).enhance(1.07)
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=2.2, percent=85, threshold=3))
    alpha = sujet.getchannel("A")
    if y + sh < h - 4:      # le bas du sujet (coupé ou non) s'arrête avant le bas de l'image : il se fond dans le noir
        fondu = max(8, int(sh * 0.16))
        rampe = Image.new("L", (1, sh), 255)
        rampe.putdata([255 if r < sh - fondu else int(255 * ((sh - r) / fondu) ** 1.6) for r in range(sh)])
        alpha = ImageChops.multiply(alpha, rampe.resize((sw, sh)))
    # éclairage de contour : un liseré de lumière à la couleur d'accent sur le bord de la silhouette
    # (érosion par flou + seuil : un MinFilter de cette taille prend des dizaines de secondes en 4K)
    erode = alpha.filter(ImageFilter.GaussianBlur(max(2, sw / 220))).point(lambda v: 255 if v > 235 else 0)
    bord = ImageChops.subtract(alpha, erode)
    bord = bord.filter(ImageFilter.GaussianBlur(max(2, sw / 260))).point(lambda v: int(v * 0.75))
    rgb = Image.composite(ImageChops.screen(rgb, Image.new("RGB", rgb.size, couleur)), rgb, bord)
    sujet = rgb.convert("RGBA")
    sujet.putalpha(alpha)
    # ---- derrière l'artiste : grand mot, anneau et halo à la couleur d'accent
    tete_y = y + tb * s * 0.45
    _lumiere(img, x + tcx, tete_y, sw * 0.50, couleur, 115)
    if fond is None:
        fond = surtitre or (accent or titre.split()[-1] if titre.split() else "")
    if large:
        _mot_fond(img, fond, int(h * 0.02), int(w * 0.94), couleur)
    else:
        _mot_fond(img, fond, int(h * (0.05 if fmt == "feed" else 0.11)), int(w * 0.94), couleur)
    anneau = Image.new("RGBA", img.size, (0, 0, 0, 0))
    r = sw * 0.42
    ImageDraw.Draw(anneau).ellipse([x + tcx - r, tete_y - r, x + tcx + r, tete_y + r], outline=(*couleur, 150),
                                   width=max(4, w // 400))
    img.paste(anneau, (0, 0), anneau)
    halo = Image.new("L", img.size, 0)
    halo.paste(alpha, (x, y))
    halo = halo.filter(ImageFilter.GaussianBlur(max(w, h) / 70)).point(lambda v: int(min(255, v * 1.6) * 0.55))
    img.paste(Image.new("RGB", img.size, couleur), (0, 0), halo)
    # ombre douce au sol puis l'artiste
    ombre = Image.new("L", img.size, 0)
    ombre.paste(alpha.point(lambda v: int(v * 0.55)), (x + w // 120, y + h // 90))
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), ombre.filter(ImageFilter.GaussianBlur(w / 90)))
    img.paste(sujet, (x, y), sujet)
    # ---- titre lisible : ombre du bas (et de la gauche en 16:9), puis le texte
    if large:
        voile = Image.new("L", (w, 1))
        voile.putdata([int(225 * max(0.0, min(1.0, 1 - (px / w - 0.30) / 0.30)) ** 1.3) for px in range(w)])
        img.paste(Image.new("RGB", (w, h), (6, 6, 10)), (0, 0), voile.resize((w, h)))
        _degrade(img, 0.60, 200)
    else:
        _degrade(img, max(0.40, (y_titre - 260) / h), 235)
    d = ImageDraw.Draw(img)
    y_titre = _titre(d, titre, accent, couleur, cadre_titre["x"], cadre_titre["bas"], cadre_titre["largeur"],
                     cadre_titre["max_lignes"], cadre_titre["taille_max"])
    if large:
        f = police(34, "Poppins-Bold.ttf")
        d.line([(marge, y_titre - 34), (marge + 140, y_titre - 34)], fill=couleur, width=6)
        if surtitre:
            d.text((marge + 165, y_titre - 56), surtitre.upper(), font=f, fill=BLANC)
        _marque(img, 70, 60, 220)
    else:
        _filet(d, marge, w - marge, y_titre - 70, couleur)
        if surtitre:
            f = police(56, "Poppins-Bold.ttf")
            d.text(((w - d.textlength(surtitre.upper(), font=f)) / 2, y_titre - 190), surtitre.upper(), font=f, fill=BLANC)
        _marque(img, 110, 110 if fmt == "feed" else 260)
    # grain léger (aspect papier glacé, pas de dégradé « numérique »)
    bruit = Image.effect_noise((w, h), 38).convert("RGB")
    return Image.blend(img, bruit, 0.035)


def citation(photo, texte: str, auteur: str, contexte: str = "", fmt: str = "feed", couleur=None, note: str = "") -> Image.Image:
    """Citation choc (style Instrurap) : visage à gauche plein cadre, la phrase en grandes capitales serif à droite,
    le nom de l'auteur au-dessus, le contexte en dessous. note : « traduit de l'anglais » le cas échéant."""
    w, h = FORMATS[fmt]
    couleur = couleur or (214, 190, 150)       # beige doré des citations de référence
    im = charge(photo)
    img = cadre(im, w, h, 0.15) if im else Image.new("RGB", (w, h), (14, 14, 18))
    # voile sombre progressif sur la droite, où se pose le texte
    voile = Image.new("L", (w, 1))
    for x in range(w):
        voile.putpixel((x, 0), int(235 * max(0.0, min(1.0, (x / w - 0.30) / 0.30))))
    img.paste(Image.new("RGB", (w, h), (10, 10, 14)), (0, 0), voile.resize((w, h)))
    d = ImageDraw.Draw(img)
    x0, largeur = int(w * 0.50), int(w * 0.44)
    texte = "« " + texte.strip().strip("«»\"“” ").upper() + " »"
    for taille in range(170, 60, -6):
        f = ImageFont.truetype(str(RES / "fonts" / "DMSerifDisplay-Regular.ttf"), taille)
        lignes, cur = [], ""
        for m in texte.split():
            essai = (cur + " " + m).strip()
            if d.textlength(essai, font=f) <= largeur:
                cur = essai
            else:
                lignes.append(cur); cur = m
        lignes.append(cur)
        if len(lignes) * taille * 1.08 <= h * 0.42:
            break
    hauteur = len(lignes) * int(taille * 1.08)
    y = (h - hauteur) // 2
    fa = police(46, "Poppins-Bold.ttf")
    d.text((x0 + (largeur - d.textlength(auteur.upper(), font=fa)) / 2, y - 150), auteur.upper(), font=fa, fill=BLANC)
    d.line([(x0 + largeur * 0.3, y - 70), (x0 + largeur * 0.7, y - 70)], fill=(200, 200, 200), width=3)
    for i, l in enumerate(lignes):
        fill = couleur if i in (len(lignes) // 2,) else BLANC
        d.text((x0 + (largeur - d.textlength(l, font=f)) / 2, y), l, font=f, fill=fill)
        y += int(taille * 1.08)
    d.line([(x0 + largeur * 0.3, y + 40), (x0 + largeur * 0.7, y + 40)], fill=(200, 200, 200), width=3)
    fc = police(38, "Poppins-Regular.ttf")
    for k, ligne in enumerate([contexte, note]):
        if ligne:
            d.text((x0 + (largeur - d.textlength(ligne, font=fc)) / 2, y + 80 + k * 56), ligne, font=fc, fill=(205, 205, 210))
    _marque(img, 110, 110 if fmt == "feed" else 260, 300)
    return img


def trio(personnes: list, titre: str, accent: str | None = None, fmt: str = "feed", couleur=None) -> Image.Image:
    """Trois visages côte à côte ; sous chacun, son nom et son chiffre (en couleur). personnes : [{photo, nom, chiffre, legende}]."""
    w, h = FORMATS[fmt]
    couleur = couleur or (47, 168, 255)
    img = Image.new("RGB", (w, h), (8, 8, 12))
    n = len(personnes[:3]) or 1
    col = w // n
    hp = int(h * (0.58 if fmt == "feed" else 0.55))
    for i, p in enumerate(personnes[:3]):
        im = charge(p.get("photo"))
        if im:
            img.paste(cadre(im, col, hp, 0.12), (i * col, 0))
    _degrade(img, 0.38, 255)
    d = ImageDraw.Draw(img)
    for i in range(1, n):                                    # fines séparations entre les visages
        d.line([(i * col, 0), (i * col, hp * 0.9)], fill=(8, 8, 12), width=10)
    y_nom = hp - 150
    for i, p in enumerate(personnes[:3]):
        cx = i * col + col / 2
        f = police(110)
        nom = p["nom"].upper()
        while d.textlength(nom, font=f) > col - 60 and f.size > 50:
            f = police(f.size - 6)
        d.text((cx - d.textlength(nom, font=f) / 2 + 5, y_nom + 6), nom, font=f, fill=(0, 0, 0))
        d.text((cx - d.textlength(nom, font=f) / 2, y_nom), nom, font=f, fill=BLANC)
        fc = police(150)
        ch = str(p.get("chiffre") or "")
        d.text((cx - d.textlength(ch, font=fc) / 2, y_nom + 140), ch, font=fc, fill=couleur)
        if p.get("legende"):
            fl = police(44, "Poppins-Bold.ttf")
            lg = p["legende"].upper()
            while d.textlength(lg, font=fl) > col - 60 and fl.size > 24:
                fl = police(fl.size - 3, "Poppins-Bold.ttf")
            d.text((cx - d.textlength(lg, font=fl) / 2, y_nom + 330), lg, font=fl, fill=(220, 220, 230))
    marge = 120
    bas = h - (200 if fmt == "feed" else 560)
    _titre(d, titre, accent, couleur, marge, bas, w - 2 * marge, max_lignes=2, taille_max=260)
    _marque(img, 110, 110 if fmt == "feed" else 260, 300)
    return img


def bandeaux(personnes: list, titre: str, fmt: str = "feed", couleur=None) -> Image.Image:
    """Quatre bandeaux horizontaux avec photo, nom et chiffre réel. Chaque personne : photo, nom, chiffre, legende."""
    w, h = FORMATS[fmt]
    couleur = couleur or (47, 168, 255)
    img = Image.new("RGB", (w, h), (8, 8, 12))
    items = personnes[:4]
    marge = int(w * 0.045)
    haut_titre = int(h * 0.19)
    espace = int(h * 0.018)
    hauteur = (h - haut_titre - marge - espace * 3) // 4
    for i, p in enumerate(items):
        y = haut_titre + i * (hauteur + espace)
        im = charge(p.get("photo"))
        if im:
            img.paste(cadre(im, int(w * 0.34), hauteur, 0.12), (marge, y))
        voile = Image.new("L", (w - 2 * marge, hauteur), 190)
        img.paste(Image.new("RGB", (w - 2 * marge, hauteur), (12, 12, 18)), (marge, y), voile)
        d = ImageDraw.Draw(img)
        x = marge + int(w * 0.37)
        nom = p["nom"].upper()
        fn = police(90)
        while d.textlength(nom, font=fn) > w * 0.54 and fn.size > 42:
            fn = police(fn.size - 6)
        d.text((x, y + hauteur * 0.12), nom, font=fn, fill=BLANC)
        chiffre = str(p.get("chiffre") or "")
        fc = police(150)
        while d.textlength(chiffre, font=fc) > w * 0.52 and fc.size > 60:
            fc = police(fc.size - 6)
        d.text((x, y + hauteur * 0.42), chiffre, font=fc, fill=couleur)
    d = ImageDraw.Draw(img)
    _titre(d, titre, None, couleur, marge, haut_titre - 12, w - 2 * marge, max_lignes=2, taille_max=180)
    _marque(img, 75, 55, 180)
    return img


def record(photo, phrase: str, chiffre: str, fmt: str = "feed", couleur=None) -> Image.Image:
    """Photo plein cadre et pastille contenant le chiffre vérifié."""
    img = une(photo, phrase, fmt=fmt, couleur=couleur or ACCENTS[0])
    d = ImageDraw.Draw(img)
    w, h = img.size
    r = int(w * 0.16)
    cx, cy = w - r - int(w * 0.08), int(h * 0.23)
    d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=couleur or ACCENTS[0], outline=BLANC, width=max(5, w // 300))
    f = police(max(55, int(w * 0.095)))
    while d.textlength(chiffre, font=f) > r * 1.65 and f.size > 34:
        f = police(f.size - 5)
    d.text((cx - d.textlength(chiffre, font=f) / 2, cy - f.size / 2), chiffre, font=f, fill=BLANC)
    return img
