"""Couvertures « HISTOIRE VRAIE » façon magazine (22/11/2026, références du fondateur : VOGUE vertical, POPULAR, mosaïque
Adidas, lettres-fenêtre DARK, papier déchiré). Aucune n'a besoin de détourage. Le fondateur choisira lesquelles garder.

Chaque gabarit : fonction(photo, titre, accent, mot, contexte, fmt) -> Image
  photo    : URL, chemin ou image PIL (vraie photo de l'artiste, jamais générée)
  titre    : l'accroche (déclaration choc, jamais une question)
  accent   : le mot ou groupe de mots du titre mis en valeur (ou None)
  mot      : le mot géant (PREMIER, le nom de l'artiste…) ; court de préférence (≤ 8 lettres)
  contexte : petite ligne « BLACK SHERIF · GHANA · WIRELESS FESTIVAL »
  fmt      : « feed » (4:5) ou « story » (9:16)
Règles tenues : jamais les yeux cachés (le mot géant évite le visage), charte blanc / violet / bleu ciel, logo lisible."""
from __future__ import annotations

import random
import unicodedata

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from core.services.social import couverture2026 as C

VIOLET, CIEL, BLANC, NUIT = C.VIOLET, C.CIEL, C.BLANC, C.NUIT
ENCRE = (18, 16, 40)
CIEL_PALE = (222, 238, 255)
PAPIER = (246, 243, 236)
STYLES = ("vogue", "popular", "mosaique", "fenetre", "dechire")


def _f(nom: str, taille: float, poids: str | None = None):
    return C.police(nom, max(8, int(taille)), poids)


def _anton(t):
    return _f("Anton-Regular.ttf", t)


def _mont(t, poids="Black"):
    return _f("Montserrat.ttf", t, poids)


def _coupe(d, texte: str, f, largeur: float) -> list:
    """Lignes d'au plus `largeur` px ; « ? », « ! », « : » jamais seuls en début de ligne."""
    mots = []
    for m in (texte or "").split():
        if mots and m in ("?", "!", ":", ";", "»"):
            mots[-1] += " " + m
        else:
            mots.append(m)
    out, cour = [], ""
    for m in mots:
        essai = (cour + " " + m).strip()
        if d.textlength(essai, font=f) > largeur and cour:
            out.append(cour); cour = m
        else:
            cour = essai
    return out + ([cour] if cour else [])


def _ajuste(d, texte: str, police, largeur: float, tmax: float, tmin: float, lignes_max: int):
    """La plus grande taille où le texte tient en `lignes_max` lignes : (police, lignes, taille)."""
    t = tmax
    while True:
        f = police(t)
        ls = _coupe(d, texte, f, largeur)
        if len(ls) <= lignes_max or t <= tmin:
            return f, ls, t
        t -= 2


def _norm(m: str) -> str:
    m = unicodedata.normalize("NFKD", m or "")
    return "".join(ch for ch in m if not unicodedata.combining(ch)).lower().strip(".,!?«»'’\"")


def _accent_mots(accent: str | None) -> set:
    return {_norm(m) for m in (accent or "").split()}


def _texte_surligne(d, x, y, lignes, f, taille, coul, fond_acc, coul_acc, cibles: set, inter: float) -> float:
    """Lignes de texte, les mots de l'accent sur un bloc de couleur."""
    norm = _norm
    esp = d.textlength(" ", font=f)
    for l in lignes:
        mots = l.split(" ")
        xx, pos = x, []
        for m in mots:
            pos.append(xx); xx += d.textlength(m, font=f) + esp
        acc = [bool(m.strip()) and norm(m) in cibles for m in mots]
        k = 0
        while k < len(mots):   # un seul bloc pour des mots d'accent qui se suivent
            if acc[k]:
                j = k
                while j + 1 < len(mots) and acc[j + 1]:
                    j += 1
                fin = pos[j] + d.textlength(mots[j], font=f)
                d.rectangle((pos[k] - .08 * taille, y + .12 * taille, fin + .1 * taille, y + 1.12 * taille), fill=fond_acc)
                k = j + 1
            else:
                k += 1
        for m, xm, a in zip(mots, pos, acc):
            d.text((xm, y), m, font=f, fill=coul_acc if a else coul)
        y += inter
    return y


def _logo(c: Image.Image, x: int, y: int, d_: int, texte=BLANC, pastille=None) -> None:
    """Logo rond + « cauricharts » ; pastille : un fond derrière pour qu'il reste lisible sur un fond clair ou chargé."""
    if pastille is not None:
        f = C.police("Jost.ttf", int(d_ * .42), "SemiBold")
        lw = ImageDraw.Draw(c).textlength("cauricharts", font=f)
        ImageDraw.Draw(c).rounded_rectangle((x - d_ * .14, y - d_ * .14, x + d_ + 16 + lw + d_ * .3, y + d_ * 1.14),
                                            radius=int(d_ * .64), fill=pastille)
    C._logo(c, x, y, d_)
    if texte != BLANC:   # C._logo écrit en blanc : on réécrit le nom dans la couleur voulue
        ImageDraw.Draw(c).text((x + d_ + 16, y + d_ * .28), "cauricharts", font=C.police("Jost.ttf", int(d_ * .42), "SemiBold"), fill=texte)


def palette(im) -> dict:
    """Couleurs du gabarit tirées de la PHOTO (22/11/2026, « les couleurs du design doivent s'adapter à l'image ») :
    la teinte vive la plus présente (peau, gris, blancs et noirs écartés), déclinée en vif / foncé / clair / pâle.
    Sans teinte nette : le violet de la marque."""
    import colorsys
    if im is None:
        return _decline(VIOLET)
    petit = im.convert("RGB").resize((90, 90))
    cases = {}
    for r, g, b in petit.getdata():
        h_, s_, v_ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s_ < .32 or v_ < .22:
            continue                                   # gris, blancs, noirs
        deg = h_ * 360
        if 8 <= deg <= 42 and s_ < .72:
            continue                                   # tons de peau et beiges
        cases.setdefault(int(deg // 15), []).append((h_, s_ * v_))
    if not cases:
        return _decline(VIOLET)
    _k, pts = max(cases.items(), key=lambda kv: sum(p[1] for p in kv[1]))
    if sum(p[1] for p in pts) < 90 * 90 * .02:          # moins de ~2 % de l'image : pas de vraie couleur dominante
        return _decline(VIOLET)
    hs = sorted(p[0] for p in pts)
    return _decline(tuple(int(x * 255) for x in colorsys.hsv_to_rgb(hs[len(hs) // 2], .72, .78)))


def _decline(rgb) -> dict:
    import colorsys
    h_, s_, v_ = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))
    f = lambda s2, v2: tuple(int(x * 255) for x in colorsys.hsv_to_rgb(h_, s2, v2))  # noqa: E731
    vif = f(max(s_, .62), min(max(v_, .62), .82))
    lum = (.299 * vif[0] + .587 * vif[1] + .114 * vif[2]) / 255
    return {"vif": vif, "fonce": f(.80, .22), "clair": f(.26, .98), "pale": f(.09, 1.0), "accent": f(.55, 1.0),
            "sur_vif": ENCRE if lum > .62 else BLANC}


def _photo(photo, w, h):
    im = C._image(photo)
    return (C.cadrer(im, w, h)[0] if im is not None else Image.new("RGB", (w, h), (60, 50, 90))), im


def _visage(im_cadre: Image.Image):
    v = C._visages(im_cadre)
    return v[0] if v else None


def _duo(im, sombre, clair):
    return ImageOps.colorize(ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1), sombre, clair)


def _marge_haut(fmt, u):   # stories : l'interface d'Instagram/TikTok occupe le haut et le bas
    return int((60 if fmt == "feed" else 230) * u)


def _marge_bas(fmt, u):
    return int((60 if fmt == "feed" else 380) * u)


# ---------------------------------------------------------------- V : « VOGUE », mot vertical géant
def vogue(photo, titre, accent, mot, contexte, fmt="feed") -> Image.Image:
    w, h = C.FORMATS[fmt]; u = w / 1080
    im = C._image(photo)
    base = C.cadrer(im, w, h)[0] if im is not None else Image.new("RGB", (w, h), (60, 50, 90))
    v = _visage(base)
    gauche = not v or (v[0] + v[2] / 2) >= .5           # le mot du côté opposé au visage
    if v and im is not None:   # photo élargie puis décalée : le visage s'écarte de la bande du mot (jamais les yeux dessous)
        large = C.cadrer(im, int(w * 1.5), h)[0]
        vl = _visage(large)
        if vl:
            cible = .64 if gauche else .36
            x = int((vl[0] + vl[2] / 2) * large.width - cible * w)
            base = large.crop((min(max(0, x), large.width - w), 0, min(max(0, x), large.width - w) + w, h))
    pal = palette(base)
    c = _duo(base, pal["fonce"], pal["clair"])
    d0 = ImageDraw.Draw(c)
    # bande blanche dégradée du côté du mot
    xb = int(w * .26)
    bande = Image.new("L", (w, h), 0); bd = ImageDraw.Draw(bande)
    for i in range(xb + int(130 * u)):
        a = int(255 * max(0, min(1, (xb + 130 * u - i) / (260 * u))))
        x = i if gauche else w - 1 - i
        bd.line((x, 0, x, h), fill=a)
    c.paste(Image.new("RGB", (w, h), BLANC), (0, 0), bande)
    # mot vertical : plein sur le blanc, au trait sur la photo
    mot = (mot or "").upper()[:10]
    longueur = int(h - _marge_haut(fmt, u) - _marge_bas(fmt, u) - 40 * u)
    t = 420
    while t > 60 and d0.textlength(mot, font=_anton(t * u)) > longueur:
        t -= 6
    f = _anton(t * u)
    tw = int(d0.textlength(mot, font=f)); bb = f.getbbox(mot)
    plein = Image.new("L", (tw + 40, bb[3] + 40), 0); ImageDraw.Draw(plein).text((20, 20), mot, font=f, fill=255)
    trait = Image.new("L", plein.size, 0)
    ImageDraw.Draw(trait).text((20, 20), mot, font=f, fill=0, stroke_width=max(2, int(4 * u)), stroke_fill=255)
    trait = ImageChops.subtract(trait, plein)
    plein, trait = plein.rotate(90, expand=True), trait.rotate(90, expand=True)
    x0 = int(56 * u) if gauche else w - plein.width - int(56 * u)
    y0 = _marge_haut(fmt, u) + (h - _marge_haut(fmt, u) - _marge_bas(fmt, u) - plein.height) // 2
    mp = Image.new("L", (w, h), 0); mp.paste(plein, (x0, y0))
    mt = Image.new("L", (w, h), 0); mt.paste(trait, (x0, y0))
    c.paste(Image.new("RGB", (w, h), pal["vif"]), (0, 0), ImageChops.multiply(mp, bande))
    c.paste(Image.new("RGB", (w, h), BLANC), (0, 0), ImageChops.multiply(mt, ImageOps.invert(bande)))
    # voile léger sous le texte pour la lecture
    d = ImageDraw.Draw(c)
    col_w = int(w * .40)
    xr = (w - col_w - int(56 * u)) if gauche else int(56 * u)
    ytop = _marge_haut(fmt, u) + int(90 * u)
    fs = _anton(38 * u)
    for l in ["HISTOIRE VRAIE"] + [x.strip() for x in (contexte or "").upper().split("·") if x.strip()][:2]:
        d.text((xr, ytop), l, font=fs, fill=BLANC); ytop += int(46 * u)
    fb, ls, tb = _ajuste(d, titre.upper(), _anton, col_w, 86 * u, 48 * u, 5)
    yb = h - _marge_bas(fmt, u) - len(ls) * int(tb * 1.1) - int(20 * u)
    voile = Image.new("L", (w, h), 0)
    ImageDraw.Draw(voile).rectangle((xr - int(30 * u), yb - int(40 * u), xr + col_w + int(30 * u), h), fill=90)
    c.paste(Image.new("RGB", (w, h), pal["fonce"]), (0, 0), voile.filter(ImageFilter.GaussianBlur(int(50 * u))))
    d = ImageDraw.Draw(c)
    cibles = _accent_mots(accent)
    for l in ls:
        xx = xr
        for m in l.split(" "):
            n = _norm(m)
            d.text((xx, yb), m, font=fb, fill=pal["accent"] if n in cibles else BLANC)
            xx += d.textlength(m + " ", font=fb)
        yb += int(tb * 1.1)
    lx = (w - int(330 * u)) if gauche else int(56 * u)
    _logo(c, lx, _marge_haut(fmt, u) - int(10 * u), int(70 * u), pastille=pal["fonce"])
    return c


# ---------------------------------------------------------------- A : « POPULAR », photo en haut, mot géant sur la jointure
def popular(photo, titre, accent, mot, contexte, fmt="feed") -> Image.Image:
    w, h = C.FORMATS[fmt]; u = w / 1080
    haut = int(h * (.64 if fmt == "feed" else .58))
    ph, _ = _photo(photo, w, haut)
    pal = palette(ph)
    c = Image.new("RGB", (w, h), pal["vif"]); c.paste(ph, (0, 0))
    encre = pal["sur_vif"]
    d = ImageDraw.Draw(c)
    mot = (mot or "").upper()[:10]
    t = 460
    while t > 60 and (d.textlength(mot, font=_anton(t * u)) > w - 40 * u
                      or d.textbbox((0, 0), mot, font=_anton(t * u))[3] - d.textbbox((0, 0), mot, font=_anton(t * u))[1] > h * .22):
        t -= 6
    f = _anton(t * u); bb = d.textbbox((0, 0), mot, font=f)
    y = haut - int((bb[3] - bb[1]) * .45) - bb[1]
    # jamais sur le visage : si le mot monterait sur la tête, on le descend
    v = _visage(ph)
    if v and (v[1] + v[3]) * haut > y + bb[1]:
        y = int((v[1] + v[3]) * haut) + int(10 * u) - bb[1]
    d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], y), mot, font=f, fill=BLANC, stroke_width=max(1, int(2 * u)), stroke_fill=pal["fonce"])
    m = int(64 * u)
    yy = y + bb[3] + int(22 * u)
    C_pastille(d, m, yy, "HISTOIRE VRAIE", u, NUIT)
    fb, ls, tb = _ajuste(d, titre, lambda t_: _mont(t_), w - 2 * m, 56 * u, 36 * u, 3)
    yy += int(66 * u)
    yy = _texte_surligne(d, m, yy, ls, fb, tb, encre, pal["fonce"], BLANC, _accent_mots(accent), int(tb * 1.18))
    if contexte:
        d.text((m, yy + int(14 * u)), contexte.upper(), font=_mont(26 * u, "ExtraBold"), fill=encre)
    _logo(c, int(50 * u), _marge_haut(fmt, u) - int(10 * u), int(70 * u), pastille=pal["fonce"])
    return c


def C_pastille(d, x, y, txt, u, fond=VIOLET, coul=BLANC):
    fe = _mont(26 * u, "ExtraBold")
    tw = d.textlength(txt, font=fe)
    d.rounded_rectangle((x, y, x + tw + 34 * u, y + 48 * u), radius=int(8 * u), fill=fond)
    d.text((x + 17 * u, y + 9 * u), txt, font=fe, fill=coul)


# ---------------------------------------------------------------- M : mosaïque sur bleu ciel
def mosaique(photo, titre, accent, mot, contexte, fmt="feed") -> Image.Image:
    w, h = C.FORMATS[fmt]; u = w / 1080
    pw, ph_ = int(w * .66), int(h * (.58 if fmt == "feed" else .48))
    px, py = (w - pw) // 2, _marge_haut(fmt, u) + int(130 * u)
    photo_c, _ = _photo(photo, pw, ph_)
    pal = palette(photo_c)
    c = Image.new("RGB", (w, h), pal["pale"])
    v = _visage(photo_c)
    n_c, n_l = 4, 5
    tw_, th_ = pw // n_c, ph_ // n_l
    rnd = random.Random(hash(titre) & 0xFFFF)
    d = ImageDraw.Draw(c)

    def sur_visage(box):
        if not v:
            return False
        fx0, fy0, fx1, fy1 = (v[0] - v[2] * .4) * pw, (v[1] - v[3] * .5) * ph_, (v[0] + v[2] * 1.4) * pw, (v[1] + v[3] * 1.3) * ph_
        return not (box[2] < fx0 or box[0] > fx1 or box[3] < fy0 or box[1] > fy1)

    for i in range(n_c):
        for j in range(n_l):
            box = (i * tw_, j * th_, (i + 1) * tw_, (j + 1) * th_)
            fixe = sur_visage(box)
            if not fixe and rnd.random() < .12:
                continue
            dx = 0 if fixe else rnd.choice([0, 0, 0, int(18 * u), -int(18 * u)])
            dy = 0 if fixe else rnd.choice([0, 0, int(18 * u), -int(18 * u)])
            c.paste(photo_c.crop(box), (px + box[0] + dx, py + box[1] + dy))
            if rnd.random() < .22:
                d.rectangle((px + box[0] + dx, py + box[1] + dy, px + box[2] + dx, py + box[3] + dy), outline=BLANC, width=max(2, int(3 * u)))
    for fx, fy, s in ((.04, .30, 120), (.82, .24, 110), (.87, .50, 80), (.06, .56, 90)):
        x, y, s = int(w * fx), py + int(ph_ * (fy - .2) / .6), int(s * u)
        d.rectangle((x, y, x + s, y + s), fill=pal["fonce"])
    m = int(64 * u)
    _logo(c, m, _marge_haut(fmt, u), int(70 * u), pastille=pal["fonce"])
    d.text((m + int(330 * u), _marge_haut(fmt, u) + int(18 * u)), "HISTOIRE VRAIE", font=_mont(30 * u), fill=ENCRE)
    fb, ls, tb = _ajuste(d, titre, lambda t_: _mont(t_), w - 2 * m, 60 * u, 36 * u, 3)
    yb = py + ph_ + int(50 * u)
    yb = _texte_surligne(d, m, yb, ls, fb, tb, ENCRE, pal["vif"], pal["sur_vif"], _accent_mots(accent), int(tb * 1.18))
    if contexte:
        d.text((m, yb + int(12 * u)), contexte.upper(), font=_mont(24 * u, "ExtraBold"), fill=(90, 90, 120))
    return c


# ---------------------------------------------------------------- D : lettres-fenêtre, la photo dans le mot géant
def fenetre(photo, titre, accent, mot, contexte, fmt="feed") -> Image.Image:
    w, h = C.FORMATS[fmt]; u = w / 1080
    im0 = C._image(photo)
    pal = palette(im0)
    c = Image.new("RGB", (w, h)); gd = ImageDraw.Draw(c)
    for x in range(w):
        k = min(1, x / (w * .85))
        gd.line((x, 0, x, h), fill=tuple(int(a + (b - a) * k) for a, b in zip(pal["fonce"], pal["pale"])))
    mot = (mot or "").upper().replace(" ", "")[:8]
    rangs = [mot] if len(mot) <= 3 else [mot[:(len(mot) + 1) // 2], mot[(len(mot) + 1) // 2:]]
    zone_w = int(w * .70)
    y0, y1 = _marge_haut(fmt, u) + int(10 * u), h - _marge_bas(fmt, u)
    ligne_h = (y1 - y0) // len(rangs)
    masque = Image.new("L", (w, h), 0); md = ImageDraw.Draw(masque)
    boites = []
    for k, r in enumerate(rangs):
        for t in range(900, 80, -10):
            f = _anton(t * u); bb = md.textbbox((0, 0), r, font=f)
            if bb[2] - bb[0] <= zone_w and bb[3] - bb[1] <= ligne_h - 24 * u:
                break
        x, y = int(46 * u) - bb[0], y0 + k * ligne_h - bb[1]
        md.text((x, y), r, font=f, fill=255)
        boites.append((x + bb[0], y + bb[1], x + bb[2], y + bb[3]))
    # la photo est placée pour que le visage tombe dans la 1re rangée de lettres
    im = im0
    zw, zh = boites[0][2] - boites[0][0], boites[0][3] - boites[0][1]
    ph_, _c = (C.cadrer(im, zone_w, h) if im is not None else (Image.new("RGB", (zone_w, h), (60, 50, 90)), None))
    photo_c = _duo(ph_, pal["fonce"], pal["clair"])
    plan = Image.new("RGB", (w, h), pal["fonce"]); plan.paste(photo_c, (int(46 * u), 0))
    c.paste(plan, (0, 0), masque)
    d = ImageDraw.Draw(c)
    xr = int(w * .745); cw = w - xr - int(36 * u)
    yy = _marge_haut(fmt, u) + int(30 * u)
    for l in ("HISTOIRE", "VRAIE"):
        d.text((xr, yy), l, font=_anton(64 * u), fill=ENCRE); yy += int(70 * u)
    yy += int(30 * u)
    fb, ls, tb = _ajuste(d, titre, lambda t_: _mont(t_), cw, 34 * u, 22 * u, 7)
    yy = _texte_surligne(d, xr, yy, ls, fb, tb, ENCRE, pal["vif"], pal["sur_vif"], _accent_mots(accent), int(tb * 1.3))
    if contexte:
        fs = _mont(19 * u, "Medium")
        for l in _coupe(d, contexte, fs, cw):
            d.text((xr, yy + int(24 * u)), l, font=fs, fill=(70, 70, 95)); yy += int(26 * u)
    _logo(c, xr - int(4 * u), h - _marge_bas(fmt, u) - int(90 * u), int(58 * u), pastille=pal["fonce"])
    return c


# ---------------------------------------------------------------- C : papier déchiré
def _bord(w, y, u, rnd, sens):
    pas = int(26 * u)
    xs = range(0, w + 2 * pas, pas) if sens > 0 else range(w + pas, -2 * pas, -pas)
    return [(x, y + rnd.randint(-int(16 * u), int(16 * u))) for x in xs]


def dechire(photo, titre, accent, mot, contexte, fmt="feed") -> Image.Image:
    w, h = C.FORMATS[fmt]; u = w / 1080
    base, im = _photo(photo, w, h)
    v = _visage(base)
    if v and im is not None and (v[1] + v[3] * 1.25) > .62:   # visage trop bas : la photo remonte (papier sous le menton)
        grand = C.cadrer(im, w, int(h * 1.4))[0]
        vg = _visage(grand)
        if vg:
            y = int((vg[1] + vg[3] * 1.25) * grand.height - .56 * h)
            y = min(max(0, y), grand.height - h)
            base = grand.crop((0, y, w, y + h))
    pal = palette(im if im is not None else base)   # couleur de la photo entière, la même en 4:5 et en 9:16
    c = ImageOps.autocontrast(ImageOps.grayscale(base), cutoff=1).convert("RGB")
    v = _visage(base)
    y0 = int(h * (.60 if fmt == "feed" else .56))
    if v:   # le papier passe toujours sous le menton
        y0 = max(y0, int((v[1] + v[3] * 1.25) * h))
    y1 = h + int(40 * u) if fmt == "feed" else h - _marge_bas(fmt, u) + int(80 * u)
    y1 = max(y1, y0 + int(440 * u))   # le papier porte toujours tout le texte
    rnd = random.Random(7)
    poly = _bord(w, y0, u, rnd, 1) + _bord(w, y1, u, rnd, -1)
    ombre = Image.new("L", (w, h), 0); ImageDraw.Draw(ombre).polygon([(x, y + int(14 * u)) for x, y in poly], fill=150)
    c.paste(Image.new("RGB", (w, h), (0, 0, 0)), (0, 0), ombre.filter(ImageFilter.GaussianBlur(int(14 * u))))
    papier = Image.new("L", (w, h), 0); ImageDraw.Draw(papier).polygon(poly, fill=255)
    tex = Image.blend(Image.new("RGB", (w, h), PAPIER), Image.effect_noise((w, h), 10).convert("RGB"), .05)
    c.paste(tex, (0, 0), papier)
    d = ImageDraw.Draw(c)
    m = int(64 * u)
    y = y0 + int(46 * u)
    C_pastille(d, m, y, "HISTOIRE VRAIE", u, pal["vif"], pal["sur_vif"])
    y += int(72 * u)
    fb, ls, tb = _ajuste(d, titre, lambda t_: _mont(t_), w - 2 * m, 64 * u, 36 * u, 3)
    y = _texte_surligne(d, m, y, ls, fb, tb, NUIT, pal["vif"], pal["sur_vif"], _accent_mots(accent), int(tb * 1.16))
    if contexte:
        d.text((m, y + int(20 * u)), contexte.upper(), font=_mont(24 * u, "ExtraBold"), fill=(120, 110, 100))
    _logo(c, int(50 * u), _marge_haut(fmt, u) - int(10 * u), int(70 * u), pastille=(20, 20, 30))
    return c


GABARITS = {"vogue": vogue, "popular": popular, "mosaique": mosaique, "fenetre": fenetre, "dechire": dechire}


def couverture(style: str, photo, titre, accent, mot, contexte, fmt="feed") -> Image.Image:
    return GABARITS[style](photo, titre, accent, mot, contexte, fmt)
