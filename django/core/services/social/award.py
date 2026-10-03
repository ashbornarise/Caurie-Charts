"""Distinctions Cauri Charts : une carte royale pour chacun des 5 premiers de chaque classement.

  carte  : 4:5 (1600 × 2000, ou 2400 × 3000 pour l'impression 20 × 25 cm à 300 ppp), à envoyer à l'artiste ;
           couronne de cauris (symbole de richesse et de royauté en Afrique de l'Ouest), lauriers, dorure, sceau de cire ;
  cadre  : la carte encadrée, posée sur une tablette de marbre, pour le post « ce qu'ils ont reçu » ;
  coffret: la carte dans un coffret doublé de satin (variante).
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from core.services.social import image as PI

VIO, VIO_DARK, VIO_LIGHT = (139, 82, 255), (46, 16, 108), (222, 206, 255)  # violet Cauri Charts (#8B52FF), métal améthyste
INK, CREAM, GREY = (8, 6, 12), (246, 243, 252), (176, 168, 194)
CHARTS = {"prime": "Top 20 · Afrique de l’Ouest", "buzz": "Ça monte · Afrique de l’Ouest", "fresh": "Nouveautés · Afrique de l’Ouest",
          "icon": "Top artistes · Afrique de l’Ouest", "legend": "Classiques · Afrique de l’Ouest"}
CINZEL, GARAMOND = str(PI.FONT_DIR / "Cinzel.ttf"), str(PI.FONT_DIR / "CormorantGaramond-Italic.ttf")
SANS = str(PI.FONT_DIR / "Poppins-Regular.ttf")


@lru_cache(maxsize=64)
def _f(path: str, px: int, weight: str = "") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, max(8, int(px)))
    if weight:
        try:
            f.set_variation_by_name(weight)
        except (OSError, ValueError):
            pass
    return f


def _gold(size, seed=0) -> Image.Image:
    """Métal violet (améthyste) : dégradé avec un reflet en diagonale et un grain fin."""
    w, h = size
    g = Image.linear_gradient("L").resize((max(1, w), max(1, h)))
    sheen = Image.linear_gradient("L").rotate(35, expand=True).resize((max(1, w), max(1, h)))
    ramp = [VIO_DARK, VIO, VIO_LIGHT, (255, 255, 255), VIO_LIGHT, VIO, VIO_DARK, VIO, VIO_LIGHT]

    def lut(c):
        out = []
        for v in range(256):
            t = v / 255 * (len(ramp) - 1)
            i = min(int(t), len(ramp) - 2)
            out.append(int(ramp[i][c] + (ramp[i + 1][c] - ramp[i][c]) * (t - i)))
        return out
    mix = ImageChops.add(g.point(lambda v: v // 3), sheen.point(lambda v: v * 2 // 3))
    img = Image.merge("RGB", [mix.point(lut(c)) for c in range(3)])
    noise = Image.effect_noise((max(1, w), max(1, h)), 22).convert("L")
    return Image.blend(img, Image.merge("RGB", [noise] * 3), 0.06)


def _paint(img: Image.Image, mask: Image.Image, emboss=True) -> None:
    """Applique le métal violet à travers un masque, avec une ombre portée discrète (effet gravé)."""
    if emboss:
        sh = mask.filter(ImageFilter.GaussianBlur(3)).point(lambda v: int(v * 0.6))
        img.paste((0, 0, 0), (2, 4), sh)
    img.paste(_gold(img.size), (0, 0), mask)


def _spaced(d, xy, text, font, fill=255, spacing=0.0, anchor="m"):
    """Texte espacé (capitales gravées), centré sur x par défaut."""
    sp = font.size * spacing
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + sp * (len(text) - 1)
    x, y = xy
    x = x - total / 2 if anchor == "m" else (x - total if anchor == "r" else x)
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill, anchor="ls")
        x += w + sp
    return total


def _fit(text, path, px, width, weight="", spacing=0.0):
    while px > 18:
        f = _f(path, px, weight)
        if f.getlength(text) + f.size * spacing * (len(text) - 1) <= width:
            break
        px -= 2
    return px


def cowrie(w: int, h: int, color=CREAM) -> Image.Image:
    """Un cauri vu de face : coquille ovale, fente dentelée au centre."""
    s = 4
    W, H = w * s, h * s
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, W - 1, H - 1], fill=color + (255,))
    hl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(hl).ellipse([W * .12, H * .06, W * .62, H * .55], fill=90)
    im.paste((255, 255, 255), (0, 0), ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(W * .08)), im.getchannel("A")))
    dark = tuple(int(c * 0.35) for c in color)
    # Fente étroite et légèrement ondulée, bordée de petites dents alternées
    slit = [(W * (.5 + .025 * math.sin(k / 3)), H * (.1 + k * .8 / 24)) for k in range(25)]
    d.line(slit, fill=dark + (255,), width=max(2, W // 14))
    for i in range(11):
        y = H * (.16 + i * .068)
        x = W * (.5 + .025 * math.sin((y / H - .1) * 24 / .8 / 3))
        d.line([(x - W * .11, y), (x - W * .03, y)], fill=dark + (255,), width=max(1, W // 34))
        d.line([(x + W * .03, y + H * .03), (x + W * .11, y + H * .03)], fill=dark + (255,), width=max(1, W // 34))
    return im.resize((w, h), Image.LANCZOS)


def gem(w: int) -> Image.Image:
    """Diamant violet taille brillant, vu de profil : table, couronne à facettes, pavillon en pointe."""
    S = 4
    W, H = w * S, int(w * .82) * S
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gy, ty = H * .34, 0
    tl, tr = W * .27, W * .73
    pts = {"tl": (tl, ty), "tr": (tr, ty), "gl": (0, gy), "gr": (W, gy), "c": (W * .5, H),
           "m1": (W * .5, ty), "g1": (W * .2, gy), "g2": (W * .4, gy), "g3": (W * .6, gy), "g4": (W * .8, gy)}
    shades = [(70, 30, 160), (190, 150, 255), (139, 82, 255), (236, 226, 255), (110, 60, 220), (60, 22, 140),
              (160, 110, 255), (96, 46, 200), (210, 186, 255), (78, 34, 170), (139, 82, 255), (52, 18, 120)]
    facets = [  # couronne
        ["gl", "tl", "g1"], ["tl", "g2", "g1"], ["tl", "m1", "g2"], ["m1", "g3", "g2"], ["m1", "tr", "g3"], ["tr", "g4", "g3"], ["tr", "gr", "g4"],
        # pavillon
        ["gl", "g1", "c"], ["g1", "g2", "c"], ["g2", "g3", "c"], ["g3", "g4", "c"], ["g4", "gr", "c"]]
    for f, col in zip(facets, shades):
        d.polygon([pts[k] for k in f], fill=col + (255,))
    for f in facets:
        d.line([pts[k] for k in f] + [pts[f[0]]], fill=(240, 232, 255, 200), width=max(1, S))
    d.line([pts["gl"], pts["gr"]], fill=(255, 255, 255, 230), width=2 * S)
    return im.resize((w, int(w * .82)), Image.LANCZOS)


def sparkle(img: Image.Image, x: float, y: float, r: float) -> None:
    """Éclat de lumière à quatre branches, avec un halo."""
    R = int(r * 2.2)
    m = Image.new("L", (2 * R, 2 * R), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(R, R - r), (R + r * .13, R - r * .13), (R + r, R), (R + r * .13, R + r * .13),
               (R, R + r), (R - r * .13, R + r * .13), (R - r, R), (R - r * .13, R - r * .13)], fill=255)
    halo = Image.new("L", (2 * R, 2 * R), 0)
    ImageDraw.Draw(halo).ellipse([R - r * .45, R - r * .45, R + r * .45, R + r * .45], fill=150)
    glow = ImageChops.lighter(m, halo.filter(ImageFilter.GaussianBlur(r * .25)))
    img.paste((255, 255, 255), (int(x - R), int(y - R)), glow)


def _crown(width: int) -> Image.Image:
    """Masque d'une couronne à cinq pointes, une perle au sommet de chaque pointe, cauris sertis dans le bandeau."""
    w, h = width, int(width * 0.62)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    base_top, base_bot = h * .70, h * .97
    pts = [(w * .06, base_top)]
    peaks = [(.06, .30), (.28, .16), (.5, .02), (.72, .16), (.94, .30)]
    valleys = [(.17, .52), (.39, .46), (.61, .46), (.83, .52)]
    for i, (px, py) in enumerate(peaks):
        pts.append((w * px, h * (py + .12)))
        if i < len(valleys):
            pts.append((w * valleys[i][0], h * valleys[i][1]))
    pts.append((w * .94, base_top))
    d.polygon(pts, fill=255)
    d.rounded_rectangle([w * .04, base_top, w * .96, base_bot], radius=h * .05, fill=255)
    r = w * .035
    for px, py in peaks:
        d.ellipse([w * px - r, h * (py + .12) - 2.2 * r, w * px + r, h * (py + .12)], fill=255)
    # Bandeau : filets et alvéoles des cauris (évidées)
    d.line([(w * .06, base_top + h * .045), (w * .94, base_top + h * .045)], fill=0, width=max(1, w // 140))
    d.line([(w * .06, base_bot - h * .045), (w * .94, base_bot - h * .045)], fill=0, width=max(1, w // 140))
    return m


def _laurel(height: int, flip=False) -> Image.Image:
    """Masque d'une branche de laurier en arc."""
    w, h = int(height * .55), height
    m = Image.new("L", (w * 2, h * 2), 0)
    d = ImageDraw.Draw(m)
    S = 2
    cx, cy, R = w * S * 1.05, h * S * .5, h * S * .46
    pts = [(cx - R * math.cos(a), cy + R * math.sin(a)) for a in [math.radians(x) for x in range(-70, 75, 4)]]
    d.line(pts, fill=255, width=max(2, int(h * S * .012)))
    for i, a in enumerate(range(-62, 70, 13)):
        t = math.radians(a)
        x, y = cx - R * math.cos(t), cy + R * math.sin(t)
        for side in (-1, 1):
            leaf = Image.new("L", (int(h * S * .16), int(h * S * .06)), 0)
            ImageDraw.Draw(leaf).ellipse([0, 0, leaf.width - 1, leaf.height - 1], fill=255)
            ang = -a + (35 if side > 0 else -35) + 90 * 0
            lr = leaf.rotate(ang + (180 if side < 0 else 0), expand=True, resample=Image.BICUBIC)
            off = h * S * .05
            lx = x - math.cos(t + side * .9) * off - lr.width / 2
            ly = y + math.sin(t + side * .9) * off * side - lr.height / 2
            m.paste(255, (int(lx), int(ly)), lr)
    m = m.resize((w, h), Image.LANCZOS)
    return ImageOps.mirror(m) if flip else m


KIND_LABELS = {"title": ("TITRE N°{n}", "Song #{n}"), "artist": ("ARTISTE N°{n}", "Artist #{n}"),
               "debut": ("ENTRÉE DIRECTE N°{n}", "Debut #{n}")}


def _ring_text(d, center, radius, text, font, fill, bottom=False):
    """Texte disposé en cercle : en haut (sens horaire) ou en bas (lisible de gauche à droite), comme sur une médaille."""
    cx, cy = center
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths)
    sign = -1 if bottom else 1
    a = math.radians(90 if bottom else -90) - sign * total / radius / 2
    for ch, w in zip(text, widths):
        mid = a + sign * w / radius / 2
        size = int(font.size * 1.6)
        glyph = Image.new("L", (size, size), 0)
        ImageDraw.Draw(glyph).text((size / 2, size / 2), ch, font=font, fill=255, anchor="mm")
        rot = glyph.rotate(-math.degrees(mid) + (90 if bottom else -90), resample=Image.BICUBIC)
        x, y = cx + radius * math.cos(mid), cy + radius * math.sin(mid)
        d.paste(fill, (int(x - size / 2), int(y - size / 2)), rot)
        a += sign * w / radius


def seal_mask(r: int) -> Image.Image:
    """Le sceau Cauri Charts (masque à peindre) : double anneau, devise en couronne, couronne, diamant au centre.
    Identique sur toutes les distinctions, c'est la signature de la maison."""
    S = r * 2
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([0, 0, S - 1, S - 1], outline=255, width=max(2, r // 22))
    d.ellipse([r * .1, r * .1, S - r * .1, S - r * .1], outline=255, width=max(1, r // 60))
    d.ellipse([r * .36, r * .36, S - r * .36, S - r * .36], outline=255, width=max(1, r // 50))
    f = _f(CINZEL, r * .135, "Bold")
    _ring_text(m, (r, r), r * .80, "CAURI CHARTS", f, 255)
    _ring_text(m, (r, r), r * .68, "OFFICIEL", f, 255, bottom=True)
    for ang in (0, 180):  # étoiles de séparation
        x, y = r + r * .74 * math.cos(math.radians(ang)), r + r * .74 * math.sin(math.radians(ang)) - r * .02
        d.regular_polygon((x, y, r * .05), 4, rotation=45, fill=255)
    cr = _crown(int(r * .62))
    m.paste(255, (int(r - cr.width / 2), int(r * .52)), cr)
    return m  # le diamant est serti au centre au moment de peindre (voir card)


def barcode(data: str, w: int, h: int, color=CREAM) -> Image.Image:
    """Code-barres Code 128 (numéro de la distinction), barres claires sur fond transparent."""
    from barcode import Code128
    bits = "".join(Code128(data).build())
    im = Image.new("RGBA", (len(bits), 1), (0, 0, 0, 0))
    im.putdata([color + (255,) if b == "1" else (0, 0, 0, 0) for b in bits])
    return im.resize((w, h), Image.NEAREST)


def card(rank: int, chart: str, artist: str, title: str | None, photo_url, week: str, size=(1600, 2000),
         kind: str | None = None, number: int | None = None, link: str | None = None) -> Image.Image:
    """Distinction officielle. Ordre de lecture : CAURI CHARTS → N°1 → artiste → œuvre → classement → semaine.
    Le gabarit ne change jamais ; seuls la photo, le rang, l'artiste, le titre, le classement, la semaine et le numéro varient."""
    W, H = size
    s = W / 1600
    kind = kind or ("artist" if not title else "title")
    img = Image.new("RGB", (W, H), INK)
    # 1. Photo grande et immersive, noir et blanc aux ombres violettes, fondue dans le noir
    ph_y, ph_h = int(170 * s), int(1040 * s)
    photo = PI.photo(photo_url)
    if photo:
        band = Image.new("RGB", (W, ph_h))
        PI.paste_cover(band, photo, W, ph_h, 0.10)
        band = ImageOps.colorize(ImageOps.autocontrast(ImageOps.grayscale(band), cutoff=1), (6, 4, 12), (242, 240, 248), mid=(104, 94, 124))
        fade = Image.linear_gradient("L").resize((W, ph_h)).point(lambda v: 255 if v < 120 else int(255 * (1 - ((v - 120) / 135) ** 1.4)))
        top = Image.linear_gradient("L").rotate(180).resize((W, ph_h)).point(lambda v: max(0, min(255, int((v - 175) * 3.2))))
        img.paste(band, (0, ph_y), ImageChops.subtract(fade, top))
    d = ImageDraw.Draw(img)
    gold = Image.new("L", (W, H), 0)
    g = ImageDraw.Draw(gold)
    # Filet violet très fin tout autour
    g.rectangle([30 * s, 30 * s, W - 30 * s, H - 30 * s], outline=255, width=max(1, int(2 * s)))
    # 2. En-tête : logo blanc et mention officielle
    logo = PI.white_logo()
    if logo:
        lw = int(250 * s)
        lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
        img.paste(lg, ((W - lw) // 2, int(78 * s)), lg)
    _spaced(d, (W / 2, 78 * s + (lg.height if logo else 60) + 50 * s), "DISTINCTION OFFICIELLE", _f(CINZEL, 30 * s, "Bold"), fill=CREAM, spacing=.42)
    # 3. N°1 énorme, à cheval sur le bas de la photo : lisible à deux mètres
    ry = int(1350 * s)
    rank_t = f"N°{rank}"
    rf = _f(CINZEL, 400 * s, "Black")
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).text((W / 2, ry), rank_t, font=rf, fill=255, anchor="ms")
    img.paste((0, 0, 0), (0, int(10 * s)), sh.filter(ImageFilter.GaussianBlur(18 * s)).point(lambda v: int(v * .8)))
    gold.paste(255, (0, 0), sh)
    # 4. Artiste (crème), 5. œuvre (or, italique)
    name = artist.upper()
    ny = ry + int(150 * s)
    npx = _fit(name, CINZEL, 120 * s, W - 260 * s, "Bold", .05)
    nm = Image.new("L", (W, H), 0)
    _spaced(ImageDraw.Draw(nm), (W / 2, ny), name, _f(CINZEL, npx, "Bold"), spacing=.05)
    y = ny + int(84 * s)
    tm = Image.new("L", (W, H), 0)
    tl = ImageDraw.Draw(tm)
    if title:
        t = f"« {title} »"
        tl.text((W / 2, y), t, font=_f(GARAMOND, _fit(t, GARAMOND, 74 * s, W - 300 * s, "Medium Italic"), "Medium Italic"), fill=255, anchor="ms")
        y += int(66 * s)
    # 6. Catégorie et classement, 7. semaine
    y += int(18 * s)
    g.line([(W / 2 - 360 * s, y), (W / 2 - 50 * s, y)], fill=255, width=max(1, int(1.6 * s)))
    g.line([(W / 2 + 50 * s, y), (W / 2 + 360 * s, y)], fill=255, width=max(1, int(1.6 * s)))
    rule_y = y
    fr, en = KIND_LABELS.get(kind, KIND_LABELS["title"])
    lab = f"{fr.format(n=rank)}  ·  {CHARTS.get(chart, chart).upper()}"
    _paint(img, gold)
    img.paste(CREAM, (0, 0), nm)
    img.paste(VIO_LIGHT, (0, 0), tm)
    gm = gem(int(64 * s))
    img.paste(gm, (int(W / 2 - gm.width / 2), int(rule_y - gm.height * .38)), gm)
    rw = rf.getlength(rank_t)
    for fx, fy_, fr_ in ((.08, -.80, 46), (.93, -.52, 30), (.47, -.06, 22)):  # éclats sur le métal du N°
        sparkle(img, W / 2 - rw / 2 + rw * fx, ry + 400 * s * fy_, fr_ * s)
    d = ImageDraw.Draw(img)
    _spaced(d, (W / 2, y + 62 * s), lab, _f(CINZEL, _fit(lab, CINZEL, 32 * s, W - 300 * s, "Bold", .14), "Bold"), fill=CREAM, spacing=.14)
    _spaced(d, (W / 2, y + 108 * s), week.upper(), _f(CINZEL, 28 * s, "Regular"), fill=GREY, spacing=.26)
    # 8. Pied : code-barres (gauche), numéro et authenticité (centre), sceau (droite)
    fy = H - int(225 * s)
    import re
    wk = re.findall(r"\d+", week)
    code = f"CC{number or 0:04d}S{''.join(wk)}"
    label = f"CC-{number or 0:04d} · S{'-'.join(wk)}" if wk else f"CC-{number or 0:04d}"
    bc = barcode(code, int(250 * s), int(84 * s))
    bx = int(96 * s)
    img.paste(bc, (bx, fy + int(42 * s)), bc)
    d = ImageDraw.Draw(img)
    _spaced(d, (bx + bc.width / 2, fy + 158 * s), label, _f(SANS, 17 * s), fill=GREY, spacing=.22)
    seal_r = int(100 * s)
    sm = seal_mask(seal_r)
    sg = Image.new("L", (W, H), 0)
    sx, sy = int(W - 90 * s - 2 * seal_r), fy - int(17 * s)
    sg.paste(sm, (sx, sy))
    _paint(img, sg, emboss=False)
    sgem = gem(int(seal_r * .26))
    img.paste(sgem, (int(sx + seal_r - sgem.width / 2), int(sy + seal_r * 1.12)), sgem)
    d = ImageDraw.Draw(img)
    if number:
        _spaced(d, (W / 2, fy + 78 * s), f"DISTINCTION N° {number:04d}", _f(CINZEL, 30 * s, "Bold"), fill=VIO_LIGHT, spacing=.3)
    _spaced(d, (W / 2, fy + 124 * s), "Classement calculé sur des données réelles · cauricharts.com", _f(SANS, 20 * s), fill=GREY, spacing=.05)
    _spaced(d, (W / 2, fy + 158 * s), en.format(n=rank).upper() + " · OFFICIAL CHART DISTINCTION", _f(SANS, 15 * s), fill=(122, 114, 140), spacing=.3)
    return img


def cadre(card_img: Image.Image, size=(2160, 2700), seed: str = "") -> Image.Image:
    """La carte encadrée (baguette noire, filet or), posée contre un mur sombre sur une tablette de marbre noir."""
    W, H = size
    rnd = random.Random(seed or "cadre")
    # Mur : anthracite, halo d'un spot au-dessus du cadre, grain
    wall = Image.new("RGB", (W, H), (22, 21, 22))
    spot = Image.radial_gradient("L").resize((int(W * 1.6), int(H * 1.3))).point(lambda v: int((255 - v) * .55))
    wall.paste((78, 66, 102), (int(-W * .3), int(-H * .38)), spot)
    noise = Image.effect_noise((W, H), 30).convert("L").filter(ImageFilter.GaussianBlur(1.2))
    wall = Image.blend(wall, Image.merge("RGB", [noise.point(lambda v: v // 4)] * 3), 0.10)
    # Tablette de marbre noir veiné
    ty = int(H * .90)
    marble = Image.new("RGB", (W, H - ty), (14, 14, 16))
    vd = ImageDraw.Draw(marble)
    for _ in range(26):
        x0, y0 = rnd.uniform(-200, W), rnd.uniform(0, H - ty)
        pts = [(x0, y0)]
        for _k in range(8):
            x0 += rnd.uniform(80, 220)
            y0 += rnd.uniform(-30, 30)
            pts.append((x0, y0))
        vd.line(pts, fill=(rnd.randint(70, 120),) * 3, width=rnd.choice((1, 1, 2)))
    marble = Image.blend(Image.new("RGB", marble.size, (14, 14, 16)), marble.filter(ImageFilter.GaussianBlur(1.4)), .55)
    hl = Image.linear_gradient("L").resize(marble.size).point(lambda v: int((255 - v) * .25))
    marble.paste((120, 112, 104), (0, 0), hl)
    wall.paste(marble, (0, ty))
    ImageDraw.Draw(wall).line([(0, ty), (W, ty)], fill=(70, 66, 62), width=3)
    # Cadre
    fw = int(W * .74)
    border, lip = int(fw * .045), int(fw * .008)
    inner_w = fw - 2 * border
    inner_h = int(inner_w * card_img.height / card_img.width)
    fh = inner_h + 2 * border
    fx, fy = (W - fw) // 2, ty - fh + int(H * .012)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rectangle([fx + 40, fy + 50, fx + fw + 40, fy + fh + 20], fill=190)
    wall.paste((0, 0, 0), (0, 0), shadow.filter(ImageFilter.GaussianBlur(60)))
    frame = Image.new("RGB", (fw, fh), (10, 10, 11))
    fd = ImageDraw.Draw(frame)
    for i in range(border):  # biseau : plus clair en haut à gauche
        c = int(14 + 26 * (1 - i / border) ** 2)
        fd.rectangle([i, i, fw - 1 - i, fh - 1 - i], outline=(c, c, c + 1))
    fd.rectangle([border - lip, border - lip, fw - border + lip - 1, fh - border + lip - 1], fill=VIO)
    frame.paste(card_img.resize((inner_w, inner_h), Image.LANCZOS), (border, border))
    # Reflet de la vitre en diagonale
    glare = Image.new("L", (fw, fh), 0)
    ImageDraw.Draw(glare).polygon([(fw * .55, 0), (fw * .78, 0), (fw * .28, fh), (fw * .05, fh)], fill=26)
    frame.paste((255, 255, 255), (0, 0), glare.filter(ImageFilter.GaussianBlur(40)))
    wall.paste(frame, (fx, fy))
    # Ombre de contact sur la tablette
    cs = Image.new("L", (W, H), 0)
    ImageDraw.Draw(cs).ellipse([fx - 30, fy + fh - 12, fx + fw + 30, fy + fh + 40], fill=200)
    wall.paste((0, 0, 0), (0, 0), cs.filter(ImageFilter.GaussianBlur(18)))
    return wall


def coffret(card_img: Image.Image, size=(2160, 2700), seed: str = "") -> Image.Image:
    """Variante : la carte posée dans un coffret noir doublé de satin bordeaux, vue de dessus."""
    W, H = size
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W, H), (226, 218, 204))
    noise = Image.effect_noise((W, H), 18).convert("L").filter(ImageFilter.GaussianBlur(1))
    bg = Image.blend(bg, Image.merge("RGB", [noise] * 3).point(lambda v: v + 120), 0.08)
    bw, bh = int(W * 0.78), int(H * 0.74)
    bx, by = (W - bw) // 2, int(H * 0.12)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([bx + 30, by + 50, bx + bw + 30, by + bh + 60], radius=30, fill=150)
    bg.paste(Image.new("RGB", (W, H), (60, 50, 40)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(45)))
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=26, fill=(16, 14, 18))
    m = 46
    inner = [bx + m, by + m, bx + bw - m, by + bh - m]
    d.rounded_rectangle(inner, radius=14, fill=(92, 18, 32))
    satin = Image.linear_gradient("L").resize((inner[2] - inner[0], inner[3] - inner[1]))
    bg.paste(Image.new("RGB", satin.size, (130, 40, 55)), (inner[0], inner[1]), satin.point(lambda v: int(v * 0.35)))
    d.rounded_rectangle([bx + 10, by + 10, bx + bw - 10, by + bh - 10], radius=22, outline=VIO, width=4)
    cw = int(bw * 0.70)
    c = card_img.resize((cw, int(cw * card_img.height / card_img.width)), Image.LANCZOS).convert("RGBA")
    rc = c.rotate(rnd.uniform(-4, 4), expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", rc.size, (0, 0, 0, 0))
    sh.putalpha(rc.getchannel("A").point(lambda v: int(v * 0.55)).filter(ImageFilter.GaussianBlur(25)))
    px, py = (W - rc.width) // 2, by + (bh - rc.height) // 2
    bg.paste((0, 0, 0), (px + 25, py + 35), sh)
    bg.paste(rc, (px, py), rc)
    return bg
