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
FORMATS = {"feed": (2160, 2700), "story": (2160, 3840)}
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
    marge = 120
    bas = h - (230 if fmt == "feed" else 560)          # 9:16 : au-dessus de la légende et des boutons des applis
    y_titre = _titre(d, titre, accent, couleur, marge, bas, w - 2 * marge)
    _filet(d, marge, w - marge, y_titre - 70, couleur)
    if surtitre:
        f = police(56, "Poppins-Bold.ttf")
        d.text(((w - d.textlength(surtitre.upper(), font=f)) / 2, y_titre - 190), surtitre.upper(), font=f, fill=BLANC)
    _marque(img, 110, 110 if fmt == "feed" else 260)
    return img


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
