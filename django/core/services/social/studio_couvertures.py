"""Couvertures au choix pour les vidéos du Studio (10/11/2026) : TikTok accepte certaines vidéos sans couverture, d'autres
non ; le fondateur choisit un modèle par vidéo. Trois modèles, en 9:16 (TikTok, Reels) et 4:5 :
- « accroche »  : la photo (ou une image de la vidéo) en plein cadre, carte de verre avec l'étiquette et le titre ;
- « pochette »  : la pochette du titre en grand sur fond flouté, titre et artistes dessous, pastille aux couleurs du pays ;
- « gros-titre » : fond blanc, titre géant, artiste surligné à la couleur de son pays, photo ronde.
La couverture peut aussi ouvrir la vidéo (1 s) : TikTok et Instagram la prennent alors comme vignette."""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from core.services.social import couverture2026 as C
from core.services.social import top_titres as T

MODELES = {"accroche": "Accroche", "pochette": "Pochette", "gros-titre": "Gros titre"}
TAILLES = {"story": (1080, 1920), "feed": (1080, 1350)}
BLANC, NUIT = (255, 255, 255), (14, 14, 28)


def _lignes(d, texte, f, largeur):
    mots, out, cour = texte.split(), [], ""
    for m in mots:
        essai = (cour + " " + m).strip()
        if d.textlength(essai, font=f) > largeur and cour:
            out.append(cour); cour = m
        else:
            cour = essai
    return out + ([cour] if cour else [])


def _taille_titre(d, texte, largeur, depart, mini, max_lignes, police="Montserrat.ttf", poids="ExtraBold"):
    for t in range(depart, mini - 1, -4):
        f = C.police(police, t, poids)
        l = _lignes(d, texte, f, largeur)
        if len(l) <= max_lignes:
            return f, l
    return f, l[:max_lignes]


def accroche(photo, titre, etiquette, artiste, pays, fmt="story"):
    a, _b, _ = T.couleurs(pays)
    return C.actu(photo, (etiquette or "CAURI CHARTS").upper()[:28], titre, [artiste] if artiste else [], "", fmt,
                  couleur=T.accent_texte(a)).convert("RGB")


def pochette(cover, titre, artistes, pays, fmt="story", etiquette=""):
    w, h = TAILLES[fmt]
    a, b, bandes = T.couleurs(pays)
    im = C._image(cover)
    fond = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(70))
    fond = Image.blend(fond, Image.new("RGB", (w, h), (8, 8, 18)), .35).convert("RGBA")
    cote = int(w * (.72 if fmt == "story" else .56))
    y0 = int(h * (.17 if fmt == "story" else .10))
    m = Image.new("L", (cote, cote), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, cote - 1, cote - 1), radius=int(cote * .05), fill=255)
    ombre = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(ombre).rounded_rectangle(((w - cote) // 2, y0 + 30, (w + cote) // 2, y0 + cote + 30), radius=int(cote * .05), fill=(0, 0, 0, 150))
    fond.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(40)))
    fond.paste(ImageOps.fit(im, (cote, cote), Image.LANCZOS), ((w - cote) // 2, y0), m)
    d = ImageDraw.Draw(fond)
    y = y0 + cote + int(h * .05)
    if etiquette:
        fe = C.police("Montserrat.ttf", 30, "ExtraBold")
        tw = d.textlength(etiquette.upper(), font=fe)
        d.rounded_rectangle(((w - tw) / 2 - 22, y, (w + tw) / 2 + 22, y + 56), radius=28, fill=T.accent_texte(a))
        d.text((w / 2, y + 28), etiquette.upper(), font=fe, fill=BLANC, anchor="mm")
        y += 84
    f, lignes = _taille_titre(d, C.propre(titre), w - 140, 96, 56, 2, "Unbounded.ttf", None)
    for l in lignes:
        d.text((w / 2, y), l, font=f, fill=BLANC, anchor="mt"); y += int(f.size * 1.12)
    fa = C.police("Montserrat.ttf", 40, "SemiBold")
    d.text((w / 2, y + 14), C.propre(artistes), font=fa, fill=(235, 235, 245), anchor="mt")
    for i, band in enumerate(bandes):   # liseré du drapeau en bas
        d.rectangle((i * w / 3, h - 16, (i + 1) * w / 3, h), fill=band)
    C._logo(fond, 50, int(h * (.05 if fmt == "story" else .035)), 78)
    return fond.convert("RGB")


def gros_titre(photo, titre, artistes, pays, fmt="story", etiquette=""):
    w, h = TAILLES[fmt]
    a, b, bandes = T.couleurs(pays)
    at = T.accent_texte(a)
    c = Image.new("RGBA", (w, h), (250, 250, 253, 255))
    voile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dv = ImageDraw.Draw(voile)
    dv.ellipse((w * .35, -h * .15, w * 1.4, h * .35), fill=a + (70,)); dv.ellipse((-w * .5, h * .7, w * .6, h * 1.2), fill=b + (60,))
    c.alpha_composite(voile.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(c)
    for i, band in enumerate(bandes):
        d.rectangle((i * w / 3, 0, (i + 1) * w / 3, 16), fill=band if T._clair(band) < .95 else (236, 236, 242))
    T._logo_sombre(c, 60, int(h * (.05 if fmt == "story" else .04)), 76)
    d = ImageDraw.Draw(c)
    # photo ronde
    r = int(w * (.34 if fmt == "story" else .22))
    cx, cy = w // 2, int(h * (.33 if fmt == "story" else .27))
    im = C.cadre_personne(C._image(photo), 2 * r, 2 * r).convert("RGB") if photo else Image.new("RGB", (2 * r, 2 * r), a)
    mk = Image.new("L", (2 * r, 2 * r), 0); ImageDraw.Draw(mk).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    d.ellipse((cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=at)
    c.paste(im, (cx - r, cy - r), mk)
    d = ImageDraw.Draw(c)
    y = cy + r + int(h * .06)
    if etiquette:
        fe = C.police("Montserrat.ttf", 30, "ExtraBold")
        d.text((w / 2, y), " ".join(etiquette.upper()), font=fe, fill=at, anchor="mt"); y += 70
    f, lignes = _taille_titre(d, C.propre(titre).upper(), w - 120, 190, 70, 3, "Unbounded.ttf", None)
    for l in lignes:
        d.text((w / 2, y), l, font=f, fill=NUIT, anchor="mt"); y += int(f.size * 1.08)
    fa = C.police("Montserrat.ttf", 46, "ExtraBold")
    nom = C.propre(artistes)
    tw = d.textlength(nom, font=fa)
    d.rounded_rectangle(((w - tw) / 2 - 18, y + 22, (w + tw) / 2 + 18, y + 22 + 70), radius=14, fill=at)
    d.text((w / 2, y + 57), nom, font=fa, fill=BLANC, anchor="mm")
    return c.convert("RGB")


def rendu(modele: str, fmt: str = "story", photo=None, cover=None, titre="", artistes="", pays=None, etiquette="") -> Image.Image:
    if modele == "pochette" and cover:
        return pochette(cover, titre, artistes, pays, fmt, etiquette)
    if modele == "gros-titre":
        return gros_titre(photo or cover, titre, artistes, pays, fmt, etiquette)
    return accroche(photo or cover, titre, etiquette, artistes.split(" ft")[0] if artistes else "", pays, fmt)


def pour_taille(modele: str, taille, **kw) -> Image.Image:
    """La couverture à la taille exacte de la vidéo (format « origine » compris) : modèle 9:16 ou 4:5 le plus proche,
    recadré au centre."""
    w, h = taille
    fmt = "story" if h / w > 1.5 else "feed"
    im = rendu(modele, fmt, **kw)
    return ImageOps.fit(im, (w, h), Image.LANCZOS) if im.size != (w, h) else im
