"""Débuts et fins au choix pour les vidéos du Studio (10/11/2026 : « crée un système qui peut générer des débuts et fins,
au cas où je ne trouve pas mon plaisir… 10 modèles »).

- 10 débuts (DEBUTS) et 10 fins (FINS), chacun rendu image par image (PIL) en calque plein cadre transparent (FFV1),
  posé par studio_montage.monte() : le début à t = 0, la fin sur la dernière image figée et floutée.
- Chaque modèle lit un « style » : palette (couleurs du pays, charte Cauri ou nuit), police des titres, vitesse.
- genere(graine) fabrique une variante nouvelle (modèle + style tirés au sort, mais reproductibles) : son identifiant
  « modele~graine » se rejoue à l'identique au montage. « pastille » et « carte-verre » sont l'habillage historique
  (studio_habillage), gardés tels quels.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

from core.services.social import couverture2026 as C
from core.services.social import top_titres as T
from core.services.social.studio_habillage import DEVISE, FPS, _alpha, _encode, _ombre, _rebond, _sortie

DEBUTS = {
    "pastille": "Pastille (actuel)", "rideau": "Rideau aux couleurs", "pochette": "Pochette qui s'ouvre",
    "machine": "Machine à écrire", "gros-mots": "Mots géants", "bande-annonce": "Bande-annonce",
    "flash-info": "Flash info", "verre": "Carte de verre", "glitch": "Glitch", "polaroid": "Polaroïd",
}
FINS = {
    "carte-verre": "Carte de verre (actuel)", "logo": "Logo seul", "devise": "Devise mot à mot",
    "rideau-pays": "Rideau aux couleurs", "abonne": "Abonne-toi", "recap": "Tu viens d'écouter",
    "iris": "Iris", "generique": "Générique", "bandeau": "Bandeau défilant", "vague": "Vague",
}
HISTORIQUES = {"pastille", "carte-verre"}
POLICES_TITRE = [("Anton-Regular.ttf", None), ("Unbounded.ttf", "Black"), ("BebasNeue-Regular.ttf", None),
                 ("ArchivoBlack-Regular.ttf", None), ("DelaGothicOne-Regular.ttf", None), ("Syne.ttf", "ExtraBold"),
                 ("BricolageGrotesque.ttf", "ExtraBold"), ("Montserrat.ttf", "Black"), ("Outfit.ttf", "Black"),
                 ("SpaceGrotesk.ttf", "Bold")]
FIN_DUREE_TOTALE = 3.1            # = studio_habillage.FIN_AVANCE + FIN_DUREE
BLANC = (255, 255, 255)


# ---------------------------------------------------------------- style

def style(pays=None, palette="pays", police=None, vitesse=1.0) -> dict:
    a, b, bandes = T.couleurs(pays) if palette == "pays" else (C.VIOLET, C.CIEL, [C.VIOLET, BLANC, C.CIEL])
    nuit = palette == "nuit"
    return {"a": a, "b": b, "bandes": bandes, "at": T.accent_texte(a), "nuit": nuit,
            "police": police or ("Montserrat.ttf", "ExtraBold"), "vitesse": vitesse, "palette": palette}


def depuis_id(ident: str, pays=None) -> tuple[str, dict]:
    """« rideau » -> (rideau, style par défaut) ; « rideau~4821 » -> (rideau, style tiré de la graine 4821)."""
    nom, _, graine = (ident or "").partition("~")
    if not graine:
        return nom, style(pays)
    r = random.Random(int(graine) if graine.isdigit() else graine)
    return nom, style(pays, r.choice(["pays", "pays", "charte", "nuit"]), r.choice(POLICES_TITRE), r.choice([.85, 1.0, 1.15]))


def genere(sorte: str = "debut", graine=None, exclus=()) -> str:
    """Une variante neuve : « modele~graine » (modèle et style tirés au sort, rejouables à l'identique)."""
    r = random.Random(graine)
    noms = [n for n in (DEBUTS if sorte == "debut" else FINS) if n not in HISTORIQUES]
    for _ in range(50):
        ident = f"{r.choice(noms)}~{r.randint(1000, 99999)}"
        if ident not in exclus:
            return ident
    return ident


# ---------------------------------------------------------------- outils de dessin

def _f(st, taille, u):
    nom, poids = st["police"]
    return C.police(nom, max(8, int(taille * u)), poids)


def _texte(txt, f, couleur=BLANC + (255,)) -> Image.Image:
    """Texte détouré, calé sur la ligne de base (les accents ne décalent plus la ligne : « FÊTE »)."""
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, _t, r, _b = d.textbbox((0, 0), txt, font=f, anchor="ls")
    asc, desc = f.getmetrics()
    p = max(4, f.size // 10)
    im = Image.new("RGBA", (r - l + 2 * p, asc + desc + 2 * p), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((p - l, p + asc), txt, font=f, fill=couleur, anchor="ls")
    return im


def _lignes(txt, f, largeur):
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    out, cour = [], ""
    for m in txt.split():
        essai = (cour + " " + m).strip()
        if d.textlength(essai, font=f) > largeur and cour:
            out.append(cour); cour = m
        else:
            cour = essai
    return out + ([cour] if cour else [])


def _ajuste(txt, st, u, largeur, depart, mini, max_lignes):
    for t in range(depart, mini - 1, -6):
        f = _f(st, t, u)
        l = _lignes(txt, f, largeur)
        if len(l) <= max_lignes:
            return f, l
    return f, l[:max_lignes]


def _bloc(lignes, f, couleur, interligne=1.04, centre=True) -> Image.Image:
    ims = [_texte(l, f, couleur) for l in lignes]
    pas = int(f.size * interligne * 1.02)
    h0 = max(i.height for i in ims)
    w = max(i.width for i in ims)
    h = pas * (len(ims) - 1) + h0
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for k, i in enumerate(ims):
        out.alpha_composite(i, ((w - i.width) // 2 if centre else 0, k * pas))
    return out


def _colle(c, im, x, y, a=1.0):
    """alpha_composite qui accepte les positions hors cadre."""
    if im is None or a <= 0.003:
        return
    x, y = int(x), int(y)
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, c.width - x), min(im.height, c.height - y)
    if r <= l or b <= t:
        return
    morceau = im.crop((l, t, r, b)) if (l or t or r < im.width or b < im.height) else im
    c.alpha_composite(_alpha(morceau, a), (x + l, y + t))


def _centre(c, im, cx, cy, s=1.0, a=1.0, rot=0.0):
    if s <= 0.01:
        return
    if abs(s - 1) > 0.005:
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    _colle(c, im, cx - im.width / 2, cy - im.height / 2, a)


def _pastille(txt, f, fond, couleur=BLANC + (255,), padx=26, pady=12, u=1.0):
    t = _texte(txt, f, couleur)
    w, h = t.width + int(2 * padx * u), t.height + int(2 * pady * u)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=fond)
    im.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2))
    return im


def _carre_image(im, cote, rayon=0.05):
    from PIL import ImageOps
    if im is None:
        return None
    sq = ImageOps.fit(im.convert("RGB"), (cote, cote), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", (cote, cote), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, cote - 1, cote - 1), radius=int(cote * rayon), fill=255)
    sq.putalpha(m)
    return sq


def _rond_image(im, d_, anneau=None, ep=10):
    if im is None:
        return None
    sq = C.cadre_personne(im, d_, d_).convert("RGBA")
    m = Image.new("L", (d_, d_), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d_ - 1, d_ - 1), fill=255)
    sq.putalpha(m)
    if not anneau:
        return sq
    out = Image.new("RGBA", (d_ + 2 * ep, d_ + 2 * ep), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, out.width - 1, out.height - 1), fill=anneau + (255,))
    out.alpha_composite(sq, (ep, ep))
    return out


def _encre(st):
    return BLANC if st["nuit"] else C.NUIT


def _papier(st, clair=(255, 255, 255)):
    return (12, 12, 26) if st["nuit"] else clair


def _voile(W, H, couleur, a):
    return Image.new("RGBA", (W, H), couleur + (int(255 * max(0, min(1, a))),))


def _icone(taille):
    from core.services.social.studio_montage import _icone_carree
    return _icone_carree(taille)


def _degrade(w, h, c1, c2, vertical=True):
    g = Image.linear_gradient("L").resize((w, h)) if vertical else Image.linear_gradient("L").rotate(90).resize((w, h))
    return Image.composite(Image.new("RGBA", (w, h), c2 + (255,)), Image.new("RGBA", (w, h), c1 + (255,)), g)


def _txt_principal(ctx):
    return C.propre(ctx.get("accroche") or ctx.get("titre") or ctx.get("artiste") or "Cauri Charts")


def _eti(ctx):
    return C.propre(ctx.get("etiquette") or "Cauri Charts").upper()[:30]


def _visuel(ctx):
    return C._image(ctx.get("cover")) or C._image(ctx.get("photo"))


def _portrait(ctx):
    return C._image(ctx.get("photo")) or C._image(ctx.get("cover"))


# ================================================================ DÉBUTS
# chaque modèle : (W, H, ctx, st) -> (durée en s, fonction t -> image RGBA plein cadre)

def d_pastille(W, H, ctx, st):
    from core.services.social import studio_habillage as HB
    el = HB._elements_ouverture(W, ctx.get("etiquette") or "", _txt_principal(ctx), ctx.get("artiste") or "")
    marge = int(70 * W / 1080)
    y = int(H * .62) - el[3] - marge
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        c.alpha_composite(HB._image_ouverture(W, el, t, 3.2, marge), (0, max(0, y)))
        return c
    return 3.9, image


def d_rideau(W, H, ctx, st):
    u = W / 1080
    bandes = st["bandes"]
    hb = H / 3
    fond_mid = bandes[1]
    clair = T._clair(fond_mid) > .6
    coul = (st["at"] if clair else BLANC) + (255,)
    fe = C.police("Montserrat.ttf", int(28 * u), "ExtraBold")
    eti = _texte(" ".join(_eti(ctx)), fe, coul)
    place = hb - eti.height - 110 * u          # hauteur libre dans la bande du milieu
    for depart in range(120, 40, -8):
        f, l = _ajuste(_txt_principal(ctx).upper(), st, u, W - 120 * u, depart, 40, 3)
        bloc = _bloc(l, f, coul)
        if bloc.height <= place:
            break
    y_eti = hb + (hb - eti.height - 24 * u - bloc.height) / 2 + eti.height / 2
    y_bloc = y_eti + eti.height / 2 + 24 * u + bloc.height / 2
    def image(t):
        t *= st["vitesse"]
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(c)
        for i, band in enumerate(bandes):
            k_in = _sortie((t - .1 * i) / .45)
            k_out = _sortie((t - 1.75 - .08 * i) / .45)
            x0 = -W + W * k_in + W * k_out
            if 0 < k_in and k_out < 1:
                d.rectangle((x0, i * hb, x0 + W, (i + 1) * hb + 1), fill=band + (255,))
        k = _sortie((t - .5) / .4)
        ko = _sortie((t - 1.7) / .35)
        cx = W / 2 + W * ko
        _centre(c, eti, cx, y_eti, a=k * (1 - ko))
        _centre(c, bloc, cx, y_bloc + 30 * u * (1 - k), a=k)
        return c
    return 2.45 / st["vitesse"], image


def d_pochette(W, H, ctx, st):
    u = W / 1080
    cote = int(W * .58)
    vis = _carre_image(_visuel(ctx), cote)
    if vis is None:
        vis = Image.new("RGBA", (cote, cote), st["a"] + (255,))
    vis = _ombre(vis, int(30 * u), 150)
    f, l = _ajuste(C.propre(ctx.get("titre") or _txt_principal(ctx)), st, u, W - 160 * u, 92, 50, 2)
    titre = _ombre(_bloc(l, f, BLANC + (255,)), int(12 * u), 140)
    art = _ombre(_texte(C.propre(ctx.get("artiste") or ""), C.police("Montserrat.ttf", int(40 * u), "SemiBold"),
                        (235, 235, 245, 255)), int(10 * u), 130) if ctx.get("artiste") else None
    voile = _voile(W, H, (8, 8, 18), .55)
    def image(t):
        t *= st["vitesse"]
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ko = _sortie((t - 1.9) / .5)
        _colle(c, voile, 0, 0, _sortie(t / .3) * (1 - ko))
        k = _rebond((t - .1) / .55)
        s = (0.6 + 0.4 * k) * (1 - .55 * ko)
        cy = H * .38 + (H * .3) * ko
        _centre(c, vis, W / 2 - W * .3 * ko, cy, s=s, a=min(1, (t - .1) / .2) * (1 - ko))
        kt = _sortie((t - .45) / .4)
        y = H * .38 + cote / 2 + 70 * u
        _centre(c, titre, W / 2, y + titre.height / 2 + 30 * u * (1 - kt), a=kt * (1 - ko))
        if art:
            ka = _sortie((t - .65) / .4)
            _centre(c, art, W / 2, y + titre.height + 40 * u + 30 * u * (1 - ka), a=ka * (1 - ko))
        return c
    return 2.5 / st["vitesse"], image


def d_machine(W, H, ctx, st):
    u = W / 1080
    txt = _txt_principal(ctx)
    f = C.police("SpaceGrotesk.ttf", int(70 * u), "Bold")
    lignes = _lignes(txt, f, W - 140 * u)[:4]
    fe = C.police("SpaceGrotesk.ttf", int(30 * u), "Bold")
    eti = _pastille(_eti(ctx), fe, st["at"] + (255,), u=u)
    n = sum(len(l) for l in lignes)
    vit = 0.045 / st["vitesse"]
    duree = .5 + n * vit + 1.4
    y0 = H * .64 - len(lignes) * f.size * 1.15
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ko = _sortie((t - (duree - .4)) / .4)
        a = 1 - ko
        _colle(c, eti, 60 * u, y0 - eti.height - 26 * u, _sortie(t / .25) * a)
        reste = max(0, int((t - .4) / vit))
        y = y0
        d_ = ImageDraw.Draw(c)
        curseur = None
        for l in lignes:
            morceau = l[:reste]
            reste -= len(l)
            if morceau:
                im = _ombre(_texte(morceau, f), int(10 * u), 150)
                _colle(c, im, 60 * u - int(10 * u) * 3, y - int(10 * u) * 3, a)
                curseur = (60 * u + ImageDraw.Draw(c).textlength(morceau, font=f) + 8 * u, y)
            if reste < 0:
                break
            y += f.size * 1.15
        if curseur and int(t * 2.5) % 2 == 0 and a > .5:
            d_.rectangle((curseur[0], curseur[1] + 8 * u, curseur[0] + 8 * u, curseur[1] + f.size * 1.05),
                         fill=st["b"] + (255,))
        return c
    return duree, image


def d_gros_mots(W, H, ctx, st):
    u = W / 1080
    mots = _txt_principal(ctx).upper().split()[:9]
    ims = []
    for m in mots:
        for t in range(260, 70, -10):
            f = _f(st, t, u)
            if ImageDraw.Draw(Image.new("RGBA", (4, 4))).textlength(m, font=f) < W - 120 * u:
                break
        ims.append(_ombre(_texte(m, f), int(18 * u), 170))
    pas = .3 / st["vitesse"]
    art = _pastille(C.propre(ctx.get("artiste") or "").upper(), C.police("Montserrat.ttf", int(40 * u), "ExtraBold"),
                    st["at"] + (255,), u=u) if ctx.get("artiste") else None
    duree = pas * len(ims) + 1.3
    flash = _voile(W, H, st["a"], .28)
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        i = min(len(ims) - 1, int(t / pas))
        loc = t - i * pas
        ko = _sortie((t - (duree - .35)) / .35)
        if loc < .06 and t < pas * len(ims):
            _colle(c, flash, 0, 0, 1 - loc / .06)
        s = 1.25 - .25 * _sortie(loc / .14) if i < len(ims) - 1 or loc < pas else 1.0
        _centre(c, ims[i], W / 2, H * .45, s=s, a=1 - ko)
        if art and t > pas * len(ims) - .1:
            ka = _rebond((t - pas * len(ims) + .1) / .35)
            _centre(c, art, W / 2, H * .45 + ims[-1].height / 2 + 50 * u, s=max(.05, ka), a=1 - ko)
        return c
    return duree, image


def d_bande_annonce(W, H, ctx, st):
    u = W / 1080
    bh = int(H * .14)
    fe = C.police("Cinzel.ttf", int(30 * u), "Bold")
    eti = _texte("  ".join(_eti(ctx).split()), fe, (230, 230, 240, 255))
    ft, l = None, None
    for t in range(104, 50, -6):
        ft = C.police("Cinzel.ttf", int(t * u), "Black")
        l = _lignes(_txt_principal(ctx).upper(), ft, W - 140 * u)
        if len(l) <= 3:
            break
    bloc = _ombre(_bloc(l[:3], ft, BLANC + (255,), 1.12), int(16 * u), 170)
    trait = Image.new("RGBA", (int(120 * u), max(2, int(3 * u))), st["b"] + (255,))
    vign = Image.new("L", (W // 8, H // 8), 0)
    ImageDraw.Draw(vign).ellipse((-W // 16, -H // 32, W // 8 + W // 16, H // 8 + H // 32), fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(W // 40)).resize((W, H)).point(lambda p: int((255 - p) * .75))
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0)); vignette.putalpha(vign)
    def image(t):
        t *= st["vitesse"]
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ko = _sortie((t - 2.55) / .45)
        k = _sortie(t / .6) * (1 - ko)
        _colle(c, vignette, 0, 0, k)
        _colle(c, _voile(W, H, (0, 0, 0), .35), 0, 0, k)
        d = ImageDraw.Draw(c)
        d.rectangle((0, 0, W, bh * k), fill=(0, 0, 0, 255))
        d.rectangle((0, H - bh * k, W, H), fill=(0, 0, 0, 255))
        ke = _sortie((t - .45) / .6) * (1 - ko)
        _centre(c, eti, W / 2, H * .44 - bloc.height / 2 - 40 * u, a=ke)
        kt = _sortie((t - .7) / .9)
        _centre(c, bloc, W / 2, H * .48, s=1.06 - .06 * kt, a=kt * (1 - ko))
        kl = _sortie((t - 1.1) / .6)
        if kl > 0:
            tr = trait.crop((0, 0, max(1, int(trait.width * kl)), trait.height))
            _colle(c, tr, W / 2 - trait.width / 2, H * .48 + bloc.height / 2 + 30 * u, 1 - ko)
        return c
    return 3.0 / st["vitesse"], image


def d_flash_info(W, H, ctx, st):
    u = W / 1080
    y0 = int(H * .66)
    fe = C.police("Montserrat.ttf", int(30 * u), "Black")
    eti = _pastille(_eti(ctx), fe, st["at"] + (255,), padx=22, pady=10, u=u)
    f, l = _ajuste(_txt_principal(ctx), st, u, W - 160 * u, 66, 40, 2)
    bloc = _bloc(l, f, C.NUIT + (255,), 1.1, centre=False)
    bh = bloc.height + int(56 * u)
    defile = "   ·   ".join(["CAURI CHARTS", C.propre(ctx.get("artiste") or "").upper(), C.propre(DEVISE).upper()] * 3)
    fd = C.police("Montserrat.ttf", int(26 * u), "Bold")
    ticker = _texte(defile, fd, BLANC + (255,))
    th = int(54 * u)
    def image(t):
        t *= st["vitesse"]
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(c)
        ko = _sortie((t - 3.1) / .4)
        k1 = _sortie(t / .35)
        x_out = -W * ko
        d.rectangle((x_out - W + W * k1, y0, x_out - W + W * k1 + W, y0 + int(10 * u)), fill=st["a"] + (255,))
        k2 = _sortie((t - .15) / .4)
        xb = x_out - W + (W - 40 * u) * k2
        d.rectangle((xb, y0 + int(10 * u), xb + W - 40 * u, y0 + int(10 * u) + bh), fill=(255, 255, 255, 245))
        _colle(c, bloc, xb + W - 40 * u - (W - 40 * u) + 60 * u, y0 + int(10 * u) + 28 * u, _sortie((t - .45) / .3))
        ke = _rebond((t - .3) / .4)
        _centre(c, eti, 60 * u + eti.width / 2 + x_out, y0 - eti.height / 2 - 6 * u, s=max(.05, ke), a=min(1, max(0, t - .3) * 4))
        ytk = y0 + int(10 * u) + bh
        kt = _sortie((t - .35) / .35)
        d.rectangle((x_out, ytk, x_out + W * kt, ytk + th), fill=C.NUIT + (240,))
        if kt > .5:
            off = (t * 160 * u) % (ticker.width / 3)
            _colle(c, ticker, 20 * u - off + x_out, ytk + (th - ticker.height) / 2, 1)
        return c
    return 3.5 / st["vitesse"], image


def d_verre(W, H, ctx, st):
    u = W / 1080
    cw = int(W * .78)
    rond = _rond_image(_portrait(ctx), int(250 * u), st["at"], int(8 * u))
    fe = C.police("Montserrat.ttf", int(26 * u), "ExtraBold")
    eti = _texte(" ".join(_eti(ctx)), fe, st["at"] + (255,))
    f, l = _ajuste(_txt_principal(ctx), st, u, cw - 100 * u, 76, 44, 3)
    bloc = _bloc(l, f, C.NUIT + (255,), 1.08)
    art = _texte(C.propre(ctx.get("artiste") or ""), C.police("Montserrat.ttf", int(36 * u), "SemiBold"),
                 (70, 70, 90, 255)) if ctx.get("artiste") else None
    haut_r = rond.height if rond else 0
    ch = int(haut_r / 2 + 60 * u + eti.height + 20 * u + bloc.height + (art.height + 20 * u if art else 0) + 60 * u)
    carte = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(carte).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=int(46 * u), fill=(255, 255, 255, 222),
                                            outline=(255, 255, 255, 255), width=max(2, int(2 * u)))
    y = int(haut_r / 2 + 50 * u)
    carte.alpha_composite(eti, ((cw - eti.width) // 2, y)); y += eti.height + int(16 * u)
    carte.alpha_composite(bloc, ((cw - bloc.width) // 2, y)); y += bloc.height + int(16 * u)
    if art:
        carte.alpha_composite(art, ((cw - art.width) // 2, y))
    carte = _ombre(carte, int(30 * u), 120)
    def image(t):
        t *= st["vitesse"]
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ko = _sortie((t - 2.45) / .4)
        k = _rebond((t - .05) / .5)
        cy = H * .52
        _centre(c, carte, W / 2, cy + 40 * u * (1 - k) + 60 * u * ko, s=.92 + .08 * min(1, k), a=min(1, t / .2) * (1 - ko))
        if rond:
            kr = _rebond((t - .3) / .45)
            _centre(c, rond, W / 2, cy - carte.height / 2 + int(30 * u) * 3 + 60 * u * ko, s=max(.05, kr), a=(1 - ko) * min(1, max(0, t - .3) * 5))
        return c
    return 2.85 / st["vitesse"], image


def d_glitch(W, H, ctx, st):
    u = W / 1080
    f, l = _ajuste(_txt_principal(ctx).upper(), st, u, W - 110 * u, 140, 60, 3)
    blanc = _bloc(l, f, BLANC + (255,))
    rouge = _bloc(l, f, (255, 40, 80, 200))
    cyan = _bloc(l, f, (40, 230, 255, 200))
    fe = C.police("SpaceGrotesk.ttf", int(30 * u), "Bold")
    eti = _pastille(_eti(ctx), fe, (0, 0, 0, 200), (255, 255, 255, 255), u=u)
    lignes = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lignes)
    for yy in range(0, H, max(3, int(6 * u))):
        dl.line((0, yy, W, yy), fill=(0, 0, 0, 60))
    rng = random.Random(7)
    sauts = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.random()) for _ in range(200)]
    def image(t):
        t *= st["vitesse"]
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        actif = t < .7 or t > 1.95
        ko = _sortie((t - 2.1) / .3)
        a = min(1, t / .1) * (1 - ko)
        jx, jy, jr = sauts[int(t * FPS) % 200]
        amp = (30 * u if actif else 4 * u) * (1 + 2 * (t > 1.95))
        _colle(c, lignes, 0, 0, a * (.9 if actif else .35))
        cy = H * .46
        _centre(c, rouge, W / 2 - amp + jx * amp, cy + jy * amp * .3, a=a * .9)
        _centre(c, cyan, W / 2 + amp - jx * amp, cy - jy * amp * .3, a=a * .9)
        if actif and jr > .55:          # tranche décalée
            tr = blanc.crop((0, int(blanc.height * jr * .6), blanc.width, int(blanc.height * (jr * .6 + .25))))
            _centre(c, blanc, W / 2, cy, a=a)
            _colle(c, tr, W / 2 - blanc.width / 2 + jx * 60 * u, cy - blanc.height / 2 + blanc.height * jr * .6, a)
        else:
            _centre(c, blanc, W / 2, cy, a=a)
        _centre(c, eti, W / 2 + (jx * 12 * u if actif else 0), cy - blanc.height / 2 - 60 * u, a=a)
        return c
    return 2.4 / st["vitesse"], image


def d_polaroid(W, H, ctx, st):
    u = W / 1080
    cote = int(W * .6)
    vis = _carre_image(_portrait(ctx), cote, 0) or Image.new("RGBA", (cote, cote), st["a"] + (255,))
    bord = int(34 * u)
    bas = int(170 * u)
    pw, ph = cote + 2 * bord, cote + bord + bas
    pol = Image.new("RGBA", (pw, ph), (252, 252, 248, 255))
    pol.alpha_composite(vis, (bord, bord))
    fc = C.police("PlayfairDisplay-Italic.ttf", int(54 * u))
    l = _lignes(C.propre(ctx.get("titre") or ctx.get("artiste") or _txt_principal(ctx)), fc, cote)[:2]
    if len(l) == 2:
        fc = C.police("PlayfairDisplay-Italic.ttf", int(40 * u))
        l = _lignes(C.propre(ctx.get("titre") or ctx.get("artiste") or _txt_principal(ctx)), fc, cote)[:2]
    cap = _bloc(l, fc, (30, 30, 40, 255), 1.1)
    pol.alpha_composite(cap, ((pw - cap.width) // 2, bord + cote + (bas - cap.height) // 2))
    pol = _ombre(pol, int(26 * u), 150)
    fe = C.police("Montserrat.ttf", int(28 * u), "ExtraBold")
    eti = _pastille(_eti(ctx), fe, st["at"] + (255,), u=u)
    def image(t):
        t *= st["vitesse"]
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        k = _rebond(t / .6)
        ko = _sortie((t - 2.3) / .45)
        cy = -ph + (H * .45 + ph) * k
        _centre(c, pol, W / 2 + W * 1.1 * ko, cy, rot=-16 + 12 * min(1, k) - 20 * ko, a=min(1, t / .15))
        ke = _sortie((t - .55) / .35)
        _centre(c, eti, W / 2 + W * 1.1 * ko, H * .45 - ph / 2 - 10 * u, rot=-4, a=ke)
        return c
    return 2.8 / st["vitesse"], image


# ================================================================ FINS
# chaque modèle : (W, H, ctx, st) -> fonction t -> image RGBA plein cadre, sur FIN_DUREE_TOTALE secondes

def f_carte_verre(W, H, ctx, st):
    from core.services.social import studio_habillage as HB
    fond = HB._fond_fin(W, H)
    carte, icone, elements = HB._carte_fin(W, H)
    return lambda t: HB._image_fin(W, H, fond, carte, icone, elements, t)


def _marque(u, couleur=C.NUIT, taille=70):
    return _texte("cauricharts", C.police("Jost.ttf", int(taille * u), "SemiBold"), couleur + (255,))


def _devise(u, couleur, taille=29, largeur=None):
    f = C.police("DMSans.ttf", int(taille * u), "Medium")
    l = _lignes(C.propre(DEVISE), f, largeur) if largeur else [C.propre(DEVISE)]
    return _bloc(l, f, couleur, 1.25)


def _site(u, fond=C.VIOLET, couleur=BLANC):
    return _pastille("cauricharts.com", C.police("Montserrat.ttf", int(26 * u), "ExtraBold"), fond + (255,),
                     couleur + (255,), 32, 14, u)


def f_logo(W, H, ctx, st):
    u = W / 1080
    ic = _ombre(_icone(int(220 * u)), int(22 * u), 110)
    nom = _marque(u, _encre(st), 84)
    dev = _devise(u, _encre(st) + (190,), 28, W - 200 * u)
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _colle(c, _voile(W, H, _papier(st), .93), 0, 0, _sortie(t / .45))
        k = _rebond((t - .3) / .55)
        _centre(c, ic, W / 2, H * .42, s=max(.05, k), a=min(1, max(0, t - .3) * 5))
        kn = _sortie((t - .7) / .4)
        _centre(c, nom, W / 2, H * .42 + 170 * u + 20 * u * (1 - kn), a=kn)
        kd = _sortie((t - .95) / .4)
        _centre(c, dev, W / 2, H * .42 + 260 * u + 20 * u * (1 - kd), a=kd)
        return c
    return image


def f_devise(W, H, ctx, st):
    u = W / 1080
    mots = C.propre(DEVISE).split()
    f = C.police("Unbounded.ttf", int(78 * u), "Black")
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    pos, x, y, lignes = [], 0, 0, [[]]
    for m in mots:
        lm = d.textlength(m, font=f)
        if x + lm > W - 160 * u and x:
            x, y = 0, y + f.size * 1.18
            lignes.append([])
        pos.append((m, x, y)); lignes[-1].append((m, x, lm))
        x += lm + d.textlength(" ", font=f)
    larg = {round(y): max(px + d.textlength(m, font=f) for m, px, py in pos if round(py) == round(y)) for _, _, y in pos}
    hb = y + f.size * 1.18
    y_top = H * .42 - hb / 2
    ims = []
    for i, (m, px, py) in enumerate(pos):
        dernier = i >= len(pos) - 1
        im = _texte(m, f, BLANC + (255,))
        if dernier:   # dernier mot en dégradé couleur
            g = _degrade(im.width, im.height, st["b"] if st["palette"] != "pays" else T.couleurs(None)[1], st["a"], vertical=False)
            g.putalpha(im.getchannel("A"))
            im = g
        ims.append((im, (W - larg[round(py)]) / 2 + px - f.size // 10, y_top + py))
    ic = _icone(int(110 * u))
    nom = _marque(u, BLANC, 48)
    pas = 1.5 / max(1, len(ims))
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _colle(c, _voile(W, H, C.NUIT, .94), 0, 0, _sortie(t / .4))
        for i, (im, x, y) in enumerate(ims):
            k = _sortie((t - .3 - i * pas) / .3)
            _colle(c, im, x, y + 26 * u * (1 - k), k)
        kl = _sortie((t - 2.0) / .4)
        _centre(c, ic, W / 2 - nom.width / 2 - 20 * u, H * .82, a=kl)
        _centre(c, nom, W / 2 + ic.width / 2 + 0 * u, H * .82, a=kl)
        return c
    return image


def f_rideau_pays(W, H, ctx, st):
    u = W / 1080
    ic = _icone(int(150 * u))
    nom = _marque(u, C.NUIT, 70)
    dev = _devise(u, C.NUIT + (190,), 27, W * .62)
    site = _site(u, st["at"])
    cw, ch = int(W * .76), int(150 * u + nom.height + dev.height + site.height + 170 * u)
    carte = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(carte).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=int(44 * u), fill=(255, 255, 255, 250))
    y = int(50 * u)
    for el in (ic, nom, dev, site):
        carte.alpha_composite(el, ((cw - el.width) // 2, y)); y += el.height + int(22 * u)
    carte = _ombre(carte, int(30 * u), 130)
    bandes = st["bandes"]
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(c)
        for i, band in enumerate(bandes):
            k = _sortie((t - .08 * i) / .5)
            d.rectangle((i * W / 3, 0, (i + 1) * W / 3 + 1, H * k), fill=band + (255,))
        kc = _rebond((t - .55) / .55)
        _centre(c, carte, W / 2, H / 2 + 50 * u * (1 - min(1, kc)), s=.9 + .1 * min(1, kc), a=min(1, max(0, t - .55) * 4))
        return c
    return image


def _lucide_user_plus(taille, couleur, ep):
    """Icône « user-plus » au trait (style Lucide), dessinée à la main."""
    s = taille / 24
    im = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, int(ep))
    d.ellipse((5 * s, 3 * s, 13 * s, 11 * s), outline=couleur, width=w)
    d.arc((1 * s, 14 * s, 17 * s, 30 * s), 180, 360, fill=couleur, width=w)
    d.line((19 * s, 8 * s, 19 * s, 14 * s), fill=couleur, width=w)
    d.line((16 * s, 11 * s, 22 * s, 11 * s), fill=couleur, width=w)
    return im


def f_abonne(W, H, ctx, st):
    u = W / 1080
    titre = _bloc(["Abonne-toi"], C.police("Unbounded.ttf", int(100 * u), "Black"), _encre(st) + (255,))
    sous = _bloc(_lignes("Chaque vendredi, le classement officiel de la musique ouest-africaine",
                         C.police("DMSans.ttf", int(34 * u), "Medium"), W - 220 * u),
                 C.police("DMSans.ttf", int(34 * u), "Medium"), _encre(st) + (200,), 1.3)
    ic = _lucide_user_plus(int(190 * u), st["at"] + (255,), 2.2 * u * 190 / 24 / 3)
    bouton = _pastille("@cauricharts", C.police("Montserrat.ttf", int(42 * u), "ExtraBold"), st["at"] + (255,), u=u,
                       padx=48, pady=20)
    logo = _icone(int(90 * u))
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _colle(c, _voile(W, H, _papier(st), .92), 0, 0, _sortie(t / .4))
        ki = _rebond((t - .2) / .5)
        _centre(c, ic, W / 2, H * .3, s=max(.05, ki), a=min(1, max(0, t - .2) * 5))
        kt = _sortie((t - .45) / .4)
        _centre(c, titre, W / 2, H * .43 + 30 * u * (1 - kt), a=kt)
        ks = _sortie((t - .7) / .4)
        _centre(c, sous, W / 2, H * .43 + titre.height / 2 + sous.height / 2 + 40 * u, a=ks)
        kb = _rebond((t - 1.0) / .45)
        pouls = 1 + .04 * math.sin(max(0, t - 1.5) * 9) if t > 1.5 else 1
        _centre(c, bouton, W / 2, H * .66, s=max(.05, kb) * pouls, a=min(1, max(0, t - 1.0) * 5))
        _centre(c, logo, W / 2, H * .82, a=_sortie((t - 1.3) / .4))
        return c
    return image


def f_recap(W, H, ctx, st):
    u = W / 1080
    cote = int(W * .5)
    vis = _carre_image(_visuel(ctx), cote) or Image.new("RGBA", (cote, cote), st["a"] + (255,))
    vis = _ombre(vis, int(26 * u), 120)
    haut = _texte(" ".join("TU VIENS D'ÉCOUTER"), C.police("Montserrat.ttf", int(26 * u), "ExtraBold"), st["at"] + (255,))
    f, l = _ajuste(C.propre(ctx.get("titre") or _txt_principal(ctx)), st, u, W - 180 * u, 80, 44, 2)
    titre = _bloc(l, f, _encre(st) + (255,))
    art = _texte(C.propre(ctx.get("artiste") or ""), C.police("Montserrat.ttf", int(38 * u), "SemiBold"), _encre(st) + (200,))
    ic = _icone(int(80 * u))
    nom = _marque(u, _encre(st), 46)
    site = _site(u, st["at"])
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _colle(c, _voile(W, H, _papier(st, (250, 250, 253)), .95), 0, 0, _sortie(t / .4))
        _centre(c, haut, W / 2, H * .16, a=_sortie((t - .25) / .35))
        kv = _rebond((t - .3) / .55)
        _centre(c, vis, W / 2, H * .36, s=max(.05, .7 + .3 * kv), a=min(1, max(0, t - .3) * 4))
        kt = _sortie((t - .6) / .4)
        y = H * .36 + cote / 2 + 60 * u
        _centre(c, titre, W / 2, y + titre.height / 2 + 20 * u * (1 - kt), a=kt)
        _centre(c, art, W / 2, y + titre.height + 40 * u + 20 * u * (1 - kt), a=_sortie((t - .75) / .4))
        kl = _sortie((t - 1.2) / .4)
        _centre(c, ic, W / 2 - nom.width / 2 - 14 * u, H * .82, a=kl)
        _centre(c, nom, W / 2 + ic.width / 2, H * .82, a=kl)
        _centre(c, site, W / 2, H * .89, a=_sortie((t - 1.4) / .4))
        return c
    return image


def f_iris(W, H, ctx, st):
    u = W / 1080
    R0 = math.hypot(W, H) / 2 + 10
    r1 = int(200 * u)
    ic = _icone(int(220 * u))
    nom = _marque(u, _encre(st), 76)
    dev = _devise(u, _encre(st) + (190,), 28, W - 220 * u)
    site = _site(u, st["at"])
    pe = 4   # masque calculé en petit puis agrandi (rapide)
    def image(t):
        k = _sortie((t - .1) / .7)
        r = R0 + (r1 - R0) * k
        m = Image.new("L", (W // pe, H // pe), 255)
        ImageDraw.Draw(m).ellipse(((W / 2 - r) / pe, (H * .4 - r) / pe, (W / 2 + r) / pe, (H * .4 + r) / pe), fill=0)
        m = m.resize((W, H), Image.BILINEAR)
        c = Image.new("RGBA", (W, H), _papier(st) + (0,))
        c.putalpha(m)
        if t > .8:      # le cercle se remplit de la couleur, l'icône arrive
            kf = _sortie((t - .8) / .3)
            rr = r1 * kf
            ImageDraw.Draw(c).ellipse((W / 2 - rr, H * .4 - rr, W / 2 + rr, H * .4 + rr), fill=st["a"] + (255,))
            _centre(c, ic, W / 2, H * .4, s=max(.05, _rebond((t - 1.0) / .45)), a=min(1, (t - 1.0) * 5) if t > 1 else 0)
        kn = _sortie((t - 1.2) / .4)
        _centre(c, nom, W / 2, H * .4 + r1 + 90 * u + 20 * u * (1 - kn), a=kn)
        _centre(c, dev, W / 2, H * .4 + r1 + 180 * u, a=_sortie((t - 1.4) / .4))
        _centre(c, site, W / 2, H * .4 + r1 + 280 * u, a=_sortie((t - 1.6) / .4))
        return c
    return image


def f_generique(W, H, ctx, st):
    u = W / 1080
    fc = C.police("Cinzel.ttf", int(30 * u), "Regular")
    fb = C.police("Cinzel.ttf", int(54 * u), "Bold")
    rangs = [(_texte("UNE VIDÉO", fc, (200, 200, 210, 255)), 10)]
    rangs.append((_texte("CAURI CHARTS", fb, BLANC + (255,)), 60))
    if ctx.get("artiste"):
        rangs += [(_texte("ARTISTE", fc, (200, 200, 210, 255)), 70),
                  (_texte(C.propre(ctx["artiste"]).upper()[:28], fb, BLANC + (255,)), 50)]
    if ctx.get("titre"):
        rangs += [(_texte("TITRE", fc, (200, 200, 210, 255)), 70),
                  (_texte(C.propre(ctx["titre"]).upper()[:28], fb, BLANC + (255,)), 50)]
    dev = _devise(u, (210, 210, 220, 255), 28, W - 240 * u)
    ic = _icone(int(140 * u))
    site = _texte("CAURICHARTS.COM", C.police("Cinzel.ttf", int(34 * u), "Bold"), st["b"] + (255,))
    bh = int(H * .12)
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _colle(c, _voile(W, H, (0, 0, 0), .95), 0, 0, _sortie(t / .45))
        d = ImageDraw.Draw(c)
        kb = _sortie(t / .5)
        d.rectangle((0, 0, W, bh * kb), fill=(0, 0, 0, 255)); d.rectangle((0, H - bh * kb, W, H), fill=(0, 0, 0, 255))
        hauteur = sum(im.height + esp * u for im, esp in rangs)
        y = H * .45 - hauteur / 2 - (t - .3) * 40 * u
        a_g = _sortie((t - .3) / .5) * (1 - _sortie((t - 1.45) / .35))
        for im, esp in rangs:
            y += esp * u
            _centre(c, im, W / 2, y + im.height / 2, a=a_g)
            y += im.height
        kf = _sortie((t - 1.75) / .5)
        _centre(c, ic, W / 2, H * .42, s=.9 + .1 * kf, a=kf)
        _centre(c, dev, W / 2, H * .42 + 130 * u, a=_sortie((t - 1.95) / .4))
        _centre(c, site, W / 2, H * .42 + 200 * u, a=_sortie((t - 2.15) / .4))
        return c
    return image


def f_bandeau(W, H, ctx, st):
    u = W / 1080
    th = int(110 * u)
    fd = C.police("Montserrat.ttf", int(38 * u), "ExtraBold")
    ticker = _texte(("   ·   ".join(["CAURICHARTS.COM", C.propre(DEVISE).upper()]) + "   ·   ") * 4, fd, BLANC + (255,))
    ic = _icone(int(th + 40 * u))
    haut = _pastille("Le classement complet sur le site", C.police("Montserrat.ttf", int(34 * u), "ExtraBold"),
                     (255, 255, 255, 235), C.NUIT + (255,), 34, 16, u)
    haut = _ombre(haut, int(18 * u), 110)
    y = int(H * .78)
    def image(t):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(c)
        k = _sortie(t / .45)
        d.rectangle((0, y, W, y + th * k), fill=st["a"] + (255,))
        d.rectangle((0, y + th * k, W, y + th * k + int(8 * u) * k), fill=st["b"] + (255,))
        if k > .9:
            off = (t * 230 * u) % (ticker.width / 4)
            _colle(c, ticker, W * .25 - off, y + (th - ticker.height) / 2, 1)
            d.rectangle((0, y, W * .2, y + th), fill=st["a"] + (255,))
        _centre(c, ic, W * .1 + 10 * u, y + th / 2, s=max(.05, _rebond((t - .2) / .45)), a=min(1, max(0, t - .2) * 5))
        _centre(c, haut, W / 2, H * .28 + 30 * u * (1 - _sortie((t - .5) / .4)), a=_sortie((t - .5) / .4))
        return c
    return image


def f_vague(W, H, ctx, st):
    u = W / 1080
    a, b = (st["a"], st["b"]) if st["palette"] == "pays" else (C.VIOLET, C.CIEL)
    grad = _degrade(W, H, b, a)
    nom = _ombre(_marque(u, BLANC, 104), int(16 * u), 110)
    dev = _devise(u, (255, 255, 255, 235), 32, W - 200 * u)
    site = _pastille("cauricharts.com", C.police("Montserrat.ttf", int(30 * u), "ExtraBold"), (255, 255, 255, 255),
                     C.NUIT + (255,), 36, 16, u)
    ic = _icone(int(130 * u))
    pe = 4
    def image(t):
        k = _sortie(t / .9)
        niveau = H * (1.05 - 1.15 * k)
        m = Image.new("L", (W // pe, H // pe), 0)
        pts = [(x, (niveau + 40 * u * math.sin(x * pe / W * 6.28 * 1.5 + t * 6)) / pe) for x in range(0, W // pe + 2, 4)]
        ImageDraw.Draw(m).polygon(pts + [(W // pe + 2, H // pe + 2), (0, H // pe + 2)], fill=245)
        c = grad.copy()
        c.putalpha(m.resize((W, H), Image.BILINEAR))
        _centre(c, ic, W / 2, H * .34, s=max(.05, _rebond((t - .7) / .45)), a=min(1, max(0, t - .7) * 5))
        kn = _sortie((t - .9) / .4)
        _centre(c, nom, W / 2, H * .45 + 30 * u * (1 - kn), a=kn)
        _centre(c, dev, W / 2, H * .53, a=_sortie((t - 1.1) / .4))
        _centre(c, site, W / 2, H * .62, a=_sortie((t - 1.3) / .4))
        return c
    return image


_D = {"pastille": d_pastille, "rideau": d_rideau, "pochette": d_pochette, "machine": d_machine, "gros-mots": d_gros_mots,
      "bande-annonce": d_bande_annonce, "flash-info": d_flash_info, "verre": d_verre, "glitch": d_glitch,
      "polaroid": d_polaroid}
_F = {"carte-verre": f_carte_verre, "logo": f_logo, "devise": f_devise, "rideau-pays": f_rideau_pays, "abonne": f_abonne,
      "recap": f_recap, "iris": f_iris, "generique": f_generique, "bandeau": f_bandeau, "vague": f_vague}


# ---------------------------------------------------------------- rendu

def debut(ident: str, taille, ctx: dict, pays=None):
    """(durée, fonction t -> image) du début « modele » ou « modele~graine »."""
    nom, st = depuis_id(ident, pays or ctx.get("pays"))
    W, H = taille
    return _D.get(nom, d_pastille)(W, H, ctx, st)


def fin(ident: str, taille, ctx: dict, pays=None):
    nom, st = depuis_id(ident, pays or ctx.get("pays"))
    W, H = taille
    return FIN_DUREE_TOTALE, _F.get(nom, f_carte_verre)(W, H, ctx, st)


def video(sorte: str, ident: str, taille, ctx: dict, dossier: str) -> tuple[str, float]:
    """Calque transparent (FFV1) du début ou de la fin, plein cadre : (chemin, durée)."""
    duree, image = (debut if sorte == "debut" else fin)(ident, taille, ctx)
    n = int(duree * FPS) + 1
    chemin = os.path.join(dossier, f"{sorte}.mkv")
    return _encode((image(i / FPS) for i in range(n)), tuple(taille), chemin), duree


def image_cle(sorte: str, ident: str, taille, ctx: dict, fond: Image.Image | None = None) -> Image.Image:
    """Une image représentative (moment où tout est affiché), posée sur ``fond`` : vignette du choix dans le Studio."""
    duree, image = (debut if sorte == "debut" else fin)(ident, taille, ctx)
    t = {"gros-mots": duree - .5, "machine": duree - .5}.get(ident.split("~")[0], min(duree * .55, 1.6) if sorte == "debut" else 2.6)
    base = (fond.convert("RGBA").resize(taille) if fond else Image.new("RGBA", taille, (40, 40, 60, 255)))
    base.alpha_composite(image(t))
    return base.convert("RGB")
