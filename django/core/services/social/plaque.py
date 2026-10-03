"""Distinctions en objet : la plaque encadrée et le bloc acrylique, rendus comme des photos de produit.

  plaque : cadre, fond velours noir, pochette du titre et vinyle à l'étiquette Cauri, logo, la ligne du classement
           (mois dernier, ce mois, artiste, titre, N°), plaque gravée numérotée — l'objet qu'on accroche au studio ;
  bloc   : bloc d'acrylique dépoli posé sur une marche, médaillon en métal violet au « C » de Cauri, texte gravé.
Les mêmes données que la carte (award.card) : tout vient du classement, rien n'est inventé.
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from core.services.social import award as A
from core.services.social import image as PI

SIZE = (2160, 2700)


def _noise(size, sigma, blur=0.0):
    n = Image.effect_noise(size, sigma).convert("L")
    return n.filter(ImageFilter.GaussianBlur(blur)) if blur else n


def _shadow(img, box, radius, offset=(30, 50), strength=190, blur=60):
    m = Image.new("L", img.size, 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(m).rounded_rectangle([x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]], radius=radius, fill=strength)
    img.paste((0, 0, 0), (0, 0), m.filter(ImageFilter.GaussianBlur(blur)))


def vinyl(d: int, label_text: str) -> Image.Image:
    """Disque vinyle vu de face : sillons, reflet, étiquette violette au « C » de Cauri Charts."""
    S = 2
    D = d * S
    im = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, D - 1, D - 1], fill=(14, 14, 16, 255))
    for r in range(int(D * .18), D // 2, max(2, D // 260)):
        c = 22 + (r % 7)
        dr.ellipse([D / 2 - r, D / 2 - r, D / 2 + r, D / 2 + r], outline=(c, c, c + 2, 255), width=1)
    # Reflet en éventail
    sheen = Image.new("L", (D, D), 0)
    ImageDraw.Draw(sheen).pieslice([0, 0, D, D], 200, 245, fill=70)
    ImageDraw.Draw(sheen).pieslice([0, 0, D, D], 20, 65, fill=45)
    sheen = ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(D * .03)), im.getchannel("A"))
    im.paste((255, 255, 255, 255), (0, 0), sheen)
    lr = int(D * .17)
    dr.ellipse([D / 2 - lr, D / 2 - lr, D / 2 + lr, D / 2 + lr], fill=A.VIO + (255,))
    cm = A.c_mark(int(lr * .62))
    if cm:
        im.paste((255, 255, 255, 255), (int(D / 2 - cm.width / 2), int(D / 2 - cm.height * .62)), cm)
    A._spaced(dr, (D / 2, D / 2 + lr * .66), label_text.upper()[:22], A._f(A.SANS, lr * .14), fill=(255, 255, 255, 235), spacing=.15)
    h = int(D * .012)
    dr.ellipse([D / 2 - h, D / 2 - h, D / 2 + h, D / 2 + h], fill=(10, 10, 10, 255))
    return im.resize((d, d), Image.LANCZOS)


def _wall(size, rnd):
    W, H = size
    wall = Image.new("RGB", size, (30, 31, 34))
    spot = Image.radial_gradient("L").resize((int(W * 1.5), int(H * 1.2))).point(lambda v: int((255 - v) * .5))
    wall.paste((92, 92, 100), (int(-W * .25), int(-H * .3)), spot)
    return Image.blend(wall, Image.merge("RGB", [_noise(size, 30, 1.0).point(lambda v: v // 4)] * 3), .12)


def plaque(rank: int, chart: str, artist: str, title: str | None, cover_url, period: str, number: int | None,
           stats: dict | None = None, frame: str = "white", size=SIZE) -> Image.Image:
    """La plaque encadrée, accrochée au mur sous un spot (photo de produit, 4:5)."""
    W, H = size
    s = W / 2160
    rnd = random.Random(f"{artist}{number}")
    img = _wall(size, rnd)
    # Cadre
    fx0, fy0, fx1, fy1 = int(190 * s), int(150 * s), int(W - 190 * s), int(H - 170 * s)
    _shadow(img, (fx0, fy0, fx1, fy1), 4, (int(28 * s), int(46 * s)), 200, int(55 * s))
    d = ImageDraw.Draw(img)
    bw = int(74 * s)
    base = (236, 234, 230) if frame == "white" else (16, 16, 18)
    for i in range(bw):  # moulure : plus claire en haut à gauche, biseau vers l'intérieur
        k = 1 - i / bw
        c = tuple(min(255, int(v * (0.86 + .16 * k))) for v in base) if frame == "white" else tuple(int(v + 30 * k ** 2) for v in base)
        d.rectangle([fx0 + i, fy0 + i, fx1 - i, fy1 - i], outline=c)
    ix0, iy0, ix1, iy1 = fx0 + bw, fy0 + bw, fx1 - bw, fy1 - bw
    # Fond velours noir
    velvet = Image.new("RGB", (ix1 - ix0, iy1 - iy0), (13, 13, 15))
    velvet = Image.blend(velvet, Image.merge("RGB", [_noise(velvet.size, 50, .8).point(lambda v: v // 7)] * 3), .5)
    img.paste(velvet, (ix0, iy0))
    d = ImageDraw.Draw(img)
    d.rectangle([ix0, iy0, ix1, iy0 + int(14 * s)], fill=(4, 4, 5))  # ombre du cadre sur le fond
    d.rectangle([ix0, iy0, ix0 + int(10 * s), iy1], fill=(6, 6, 7))
    iw = ix1 - ix0
    cx = (ix0 + ix1) / 2
    # Pochette et vinyle
    cs = int(600 * s)
    px, py = int(ix0 + 150 * s), int(iy0 + 110 * s)
    v = vinyl(int(cs * .96), artist)
    _shadow(img, (px + int(cs * .55), py + int(cs * .02), px + int(cs * .55) + v.width, py + v.height), v.width // 2, (8, 14), 170, 18)
    img.paste(v, (px + int(cs * .55), py + int(cs * .02)), v)
    cover = PI.photo(cover_url)
    sleeve = Image.new("RGB", (cs, cs), (30, 30, 34))
    if cover:
        PI.paste_cover(sleeve, cover, cs, cs, .5)
    _shadow(img, (px, py, px + cs, py + cs), 2, (10, 18), 200, 16)
    img.paste(sleeve, (px, py))
    d = ImageDraw.Draw(img)
    d.rectangle([px, py, px + cs - 1, py + cs - 1], outline=(245, 245, 245), width=max(2, int(6 * s)))
    # Logo
    logo = PI.white_logo()
    ly = int(py + cs + 90 * s)
    if logo:
        lw = int(820 * s)
        lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
        img.paste(lg, (int(cx - lw / 2), ly), lg)
        ly += lg.height
    A._spaced(d, (cx, ly + 58 * s), "DISTINCTION OFFICIELLE", A._f(A.CINZEL, 30 * s, "Bold"), fill=(230, 230, 236), spacing=.45)
    # La ligne du classement
    sx0, sx1 = int(ix0 + 120 * s), int(ix1 - 120 * s)
    sy0 = int(ly + 120 * s)
    rh = [int(70 * s), int(44 * s), int(130 * s)]
    sy1 = sy0 + sum(rh)
    big = int(250 * s)
    white = (245, 245, 248)
    d.rectangle([sx0, sy0, sx1, sy1], outline=white, width=max(2, int(4 * s)))
    d.line([(sx1 - big, sy0), (sx1 - big, sy1)], fill=white, width=max(2, int(4 * s)))
    d.line([(sx0, sy0 + rh[0]), (sx1 - big, sy0 + rh[0])], fill=white, width=max(2, int(3 * s)))
    d.line([(sx0, sy0 + rh[0] + rh[1]), (sx1 - big, sy0 + rh[0] + rh[1])], fill=white, width=max(2, int(3 * s)))
    lab = A.CHARTS.get(chart, chart)
    A._spaced(d, (sx0 + 22 * s, sy0 + 48 * s), lab.upper(), A._f(A.SANS, A._fit(lab.upper(), A.SANS, 30 * s, sx1 - big - sx0 - 260 * s)),
              fill=white, spacing=.04, anchor="l")
    A._spaced(d, (sx1 - big - 22 * s, sy0 + 46 * s), period.upper(), A._f(A.SANS, 22 * s), fill=white, spacing=.12, anchor="r")
    # En-têtes de colonnes
    stats = stats or {}
    has_hist = stats.get("last") is not None or int(stats.get("weeks") or 0) > 1
    c0 = sx0 + int(120 * s) if has_hist else sx0
    c1 = c0 + int(130 * s)
    heads = ([("MOIS DERNIER", sx0, c0)] if has_hist else []) + [("CE MOIS", c0, c1), ("ARTISTE", c1, None)]
    hy = sy0 + rh[0] + int(30 * s)
    for t, a0, a1 in heads:
        if a1:
            A._spaced(d, ((a0 + a1) / 2, hy), t, A._f(A.SANS, 15 * s), fill=white, spacing=.1)
        else:
            A._spaced(d, (a0 + 18 * s, hy), t, A._f(A.SANS, 15 * s), fill=white, spacing=.1, anchor="l")
    if title:
        A._spaced(d, (sx1 - big - 22 * s, hy), "TITRE", A._f(A.SANS, 15 * s), fill=white, spacing=.1, anchor="r")
    for x in ([c0] if has_hist else []) + [c1]:
        d.line([(x, sy0 + rh[0]), (x, sy1)], fill=white, width=max(2, int(3 * s)))
    # Ligne du titre, en violet Cauri
    ry0 = sy0 + rh[0] + rh[1]
    d.rectangle([c1 + 2, ry0 + 2, sx1 - big - 2, sy1 - 2], fill=A.VIO)
    if has_hist:
        last = "NOUV." if stats.get("last") is None else f"{int(stats['last'])}"
        A._spaced(d, ((sx0 + c0) / 2, ry0 + 82 * s), last, A._f(A.SANS.replace("Regular", "Bold"), 34 * s), fill=white)
    rr = int(42 * s)
    ccx, ccy = (c0 + c1) / 2, ry0 + rh[2] / 2
    d.ellipse([ccx - rr, ccy - rr, ccx + rr, ccy + rr], fill=white)
    d.text((ccx, ccy + 2 * s), str(rank), font=A._f(A.SANS.replace("Regular", "Bold"), 44 * s), fill=(10, 10, 12), anchor="mm")
    name = artist.upper()
    room = (sx1 - big - c1) * (.55 if title else .9)
    d.text((c1 + 26 * s, ry0 + 62 * s), name, font=A._f(A.SANS.replace("Regular", "Bold"), A._fit(name, A.SANS.replace("Regular", "Bold"), 44 * s, room)),
           fill=white, anchor="ls")
    if title:
        t = title.upper()
        d.text((sx1 - big - 24 * s, ry0 + 62 * s), t, font=A._f(A.SANS.replace("Regular", "Bold"), A._fit(t, A.SANS.replace("Regular", "Bold"), 30 * s, (sx1 - big - c1) * .4)),
               fill=white, anchor="rs")
    d.text((c1 + 26 * s, ry0 + 104 * s), "CAURI CHARTS", font=A._f(A.SANS, 18 * s), fill=(235, 228, 255), anchor="ls")
    d.text((sx1 - big / 2, (sy0 + sy1) / 2 + 6 * s), f"N°{rank}", font=A._f(A.CINZEL, A._fit(f"N°{rank}", A.CINZEL, 120 * s, big - 30 * s, "Black"), "Black"),
           fill=white, anchor="mm")
    # Plaque gravée
    pw, ph = int(1180 * s), int(420 * s)
    p0x, p0y = int(cx - pw / 2), int((sy1 + iy1) / 2 - ph / 2)
    _shadow(img, (p0x, p0y, p0x + pw, p0y + ph), 4, (6, 10), 160, 10)
    plate = Image.new("RGB", (pw, ph), (8, 8, 10))
    pl = ImageDraw.Draw(plate)
    pl.rectangle([int(14 * s), int(14 * s), pw - int(14 * s), ph - int(14 * s)], outline=(210, 210, 215), width=max(1, int(2 * s)))
    lines = [("DÉCERNÉE À", 24), (artist.upper(), 50), (f"POUR LA {'1re' if rank == 1 else f'{rank}e'} PLACE DU {lab.upper()}", 24),
             (f"EN {period.upper()}" + (f" AVEC « {title.upper()} »" if title else ""), 24),
             (f"DISTINCTION N° {number:04d} · CAURI CHARTS" if number else "SPÉCIMEN · CAURI CHARTS", 19)]
    yy = int((ph - sum((px_ + 26) * s for _t, px_ in lines)) / 2 + 44 * s)  # bloc de texte centré dans la plaque
    for t, px_ in lines:
        f = A._f(A.SANS.replace("Regular", "Bold") if px_ >= 30 else A.SANS, A._fit(t, A.SANS, px_ * s, pw - 80 * s))
        pl.text((pw / 2, yy), t, font=f, fill=(225, 225, 230), anchor="ms")
        yy += int((px_ + 26) * s)
    img.paste(plate, (p0x, p0y))
    # Vitre : reflet en diagonale et léger voile
    glass = Image.new("L", size, 0)
    gd = ImageDraw.Draw(glass)
    gd.polygon([(ix0 + iw * .58, iy0), (ix0 + iw * .80, iy0), (ix0 + iw * .30, iy1), (ix0 + iw * .08, iy1)], fill=26)
    gd.polygon([(ix0 + iw * .84, iy0), (ix0 + iw * .88, iy0), (ix0 + iw * .38, iy1), (ix0 + iw * .34, iy1)], fill=14)
    img.paste((255, 255, 255), (0, 0), glass.filter(ImageFilter.GaussianBlur(30 * s)))
    return img


def bloc(rank: int, chart: str, artist: str, title: str | None, period: str, number: int | None, size=SIZE) -> Image.Image:
    """Bloc d'acrylique dépoli posé sur une marche de pierre, au soleil (photo de produit, 4:5)."""
    W, H = size
    s = W / 2160
    # Mur clair et tablette de pierre au soleil
    fy = int(H * .78)
    img = Image.new("RGB", size, (226, 216, 202))
    img.paste((200, 188, 172), (0, 0), Image.linear_gradient("L").resize(size).point(lambda v: int(v * .55)))
    floor = Image.new("RGB", (W, H - fy), (190, 178, 162))
    floor.paste((150, 138, 122), (0, 0), Image.linear_gradient("L").resize(floor.size).point(lambda v: int(v * .7)))
    img.paste(floor, (0, fy))
    img = Image.blend(img, Image.merge("RGB", [_noise(size, 60, .6)] * 3), .08)
    d = ImageDraw.Draw(img)
    d.line([(0, fy), (W, fy)], fill=(240, 232, 220), width=int(5 * s))
    rays = Image.new("L", size, 0)
    rd = ImageDraw.Draw(rays)
    for k in range(4):
        x = W * (.15 + k * .22)
        rd.polygon([(x, 0), (x + W * .08, 0), (x - W * .25, H), (x - W * .33, H)], fill=55)
    img.paste((255, 246, 230), (0, 0), rays.filter(ImageFilter.GaussianBlur(70 * s)))
    # Le bloc : face avant, tranche droite et dessus, ombre portée sur la marche
    bw_, bh_ = int(1040 * s), int(1480 * s)
    bx, by = int((W - bw_) / 2 - 40 * s), fy + int(150 * s) - bh_
    th = int(70 * s)
    # Ombre portée sur la tablette (soleil en haut à gauche) et ombre de contact sous le bloc
    _shadow(img, (bx + int(80 * s), by + bh_ - int(40 * s), bx + bw_ + int(420 * s), by + bh_ + int(50 * s)), 40, (0, 0), 110, int(45 * s))
    _shadow(img, (bx - int(10 * s), by + bh_ - int(12 * s), bx + bw_ + th, by + bh_ + int(14 * s)), 10, (0, 0), 200, int(10 * s))
    behind = img.crop((bx, by, bx + bw_, by + bh_)).filter(ImageFilter.GaussianBlur(22 * s))
    face = Image.blend(behind, Image.new("RGB", behind.size, (246, 246, 250)), .72)
    grad = Image.linear_gradient("L").resize(face.size).point(lambda v: int(v * .18))
    face.paste((170, 172, 186), (0, 0), grad)
    face = Image.blend(face, Image.merge("RGB", [_noise(face.size, 40, .5)] * 3), .05)
    side = Image.new("RGB", (th, bh_), (226, 228, 236))
    side.paste((190, 192, 204), (0, 0), Image.linear_gradient("L").rotate(90, expand=True).resize(side.size))
    img.paste(side, (bx + bw_, by + int(th * .5)))
    top = Image.new("L", (W, H), 0)
    ImageDraw.Draw(top).polygon([(bx, by), (bx + bw_, by), (bx + bw_ + th, by + th * .5), (bx + th, by + th * .5)], fill=255)
    img.paste((250, 250, 253), (0, 0), top)
    img.paste(face, (bx, by))
    d = ImageDraw.Draw(img)
    d.rectangle([bx, by, bx + bw_, by + bh_], outline=(255, 255, 255), width=max(1, int(3 * s)))
    # Médaillon en métal violet, « C » de Cauri en relief
    cx, my, r = bx + bw_ / 2, by + int(380 * s), int(230 * s)
    med = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(med)
    md.ellipse([cx - r, my - r, cx + r, my + r], fill=255)
    md.ellipse([cx - r * .86, my - r * .86, cx + r * .86, my + r * .86], fill=0)
    cm = A.c_mark(int(r * 1.05))
    if cm:
        med.paste(255, (int(cx - cm.width / 2), int(my - cm.height / 2)), cm)
    disc = Image.new("L", (W, H), 0)
    ImageDraw.Draw(disc).ellipse([cx - r * .86, my - r * .86, cx + r * .86, my + r * .86], fill=255)
    deep = Image.new("RGB", (W, H), A.VIO_DARK)
    deep.paste(A.VIO, (0, 0), Image.radial_gradient("L").resize((W, H)).point(lambda v: 255 - v))
    img.paste(deep, (0, 0), disc)
    A._paint(img, med)
    # Texte gravé (gris violet profond, comme un dépoli marqué au laser)
    ink = (92, 70, 150)
    y = my + r + int(150 * s)
    A._spaced(d, (cx, y), period.upper(), A._f(A.CINZEL, 52 * s, "Regular"), fill=ink, spacing=.18)
    d.line([(cx - 90 * s, y + 40 * s), (cx + 90 * s, y + 40 * s)], fill=ink, width=max(1, int(3 * s)))
    lab = A.CHARTS.get(chart, chart).upper()
    A._spaced(d, (cx, y + 120 * s), "DISTINCTION OFFICIELLE", A._f(A.CINZEL, 40 * s, "Regular"), fill=ink, spacing=.12)
    A._spaced(d, (cx, y + 180 * s), f"N°{rank} · {lab}", A._f(A.CINZEL, A._fit(f"N°{rank} · {lab}", A.CINZEL, 40 * s, bw_ - 140 * s, "Regular", .08), "Regular"),
              fill=ink, spacing=.08)
    d.line([(cx - 90 * s, y + 230 * s), (cx + 90 * s, y + 230 * s)], fill=ink, width=max(1, int(3 * s)))
    name = artist.upper()
    A._spaced(d, (cx, y + 340 * s), name, A._f(A.CINZEL, A._fit(name, A.CINZEL, 86 * s, bw_ - 140 * s, "Bold", .06), "Bold"), fill=ink, spacing=.06)
    if title:
        t = f"« {title.upper()} »"
        A._spaced(d, (cx, y + 410 * s), t, A._f(A.CINZEL, A._fit(t, A.CINZEL, 34 * s, bw_ - 160 * s, "Regular", .1), "Regular"), fill=ink, spacing=.1)
    A._spaced(d, (cx, by + bh_ - 70 * s), f"N° {number:04d} · CAURI CHARTS" if number else "SPÉCIMEN · CAURI CHARTS", A._f(A.SANS, 20 * s), fill=ink, spacing=.3)
    # Reflet sur l'arête gauche
    edge = Image.new("L", (W, H), 0)
    ImageDraw.Draw(edge).rectangle([bx, by, bx + int(18 * s), by + bh_], fill=120)
    img.paste((255, 255, 255), (0, 0), edge.filter(ImageFilter.GaussianBlur(8 * s)))
    return img
