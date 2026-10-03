"""Kit de distinction : la carte « nommé·e » (portrait noir et blanc qui sort d'un cadre en feuille de métal violet)
déclinée en 7 formats, plus le certificat A4 et l'enveloppe.

  telephone 1080 × 1920 · pc 1920 × 1080 · carre 1080 × 1080 · post 1080 × 1350 · carte 63 × 88 mm (300 ppp)
  certificat A4 paysage (300 ppp) · enveloppe DL 220 × 110 mm (300 ppp)
Ordre de lecture : photo → nom → rang et classement → titre → mois → données → numéro de collection et code-barres.
Le portrait sort du cadre si rembg est installé (chaîne de nuit) ; sinon il reste dans le cadre, sans effet.
"""
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from core.services.social import award as A
from core.services.social import image as PI

NIGHT, NIGHT_2 = (12, 8, 30), (30, 18, 70)  # fond nuit violette
LILAC, WHITE = (206, 186, 255), (248, 246, 255)
MONTHS = ["JAN", "FÉV", "MARS", "AVR", "MAI", "JUIN", "JUIL", "AOÛT", "SEPT", "OCT", "NOV", "DÉC"]
FORMATS = {"telephone": (1080, 1920), "pc": (1920, 1080), "carre": (1080, 1080), "post": (1080, 1350), "carte": (744, 1039)}


def code(number: int | None, period_key: str) -> str:
    y, m = period_key.split("-")[:2]
    return f"CC-{number or 0:04d} · {MONTHS[int(m) - 1]}-{y}"


def leaf(size, seed=0) -> Image.Image:
    """Feuille de métal violet froissée : relief « en crêtes » sur plusieurs échelles, éclairé (pentes et reflets),
    avec de grandes zones plus claires ou plus sombres, comme une feuille d'or posée à la main."""
    import numpy as np
    w, h = size
    rng = np.random.default_rng(seed)

    def octave(sc):
        small = rng.random((max(2, h // sc), max(2, w // sc))).astype(np.float32)
        return np.clip(np.asarray(Image.fromarray(small, "F").resize((w, h), Image.BICUBIC)), 0, 1)
    hgt = np.zeros((h, w), np.float32)
    for sc, wt in ((70, 1.0), (30, .55), (12, .3), (5, .12)):
        hgt += wt * (1 - np.abs(octave(sc) * 2 - 1)) ** 1.6   # plis de la feuille
    gy, gx = np.gradient(hgt * w / 90)
    shade = np.clip(0.5 + (-gx * 0.7 - gy * 0.7) * 1.4, 0, 1)
    spec = shade ** 6
    big = octave(max(8, min(w, h) // 3))                  # grandes zones de lumière
    v = np.clip(0.38 * shade + 0.30 * spec + 0.42 * big, 0, 1)
    ramp = np.array([A.VIO_DARK, A.VIO, A.VIO_LIGHT, (255, 255, 255)], np.float32)
    xs = np.linspace(0, 1, len(ramp))
    return Image.fromarray(np.stack([np.interp(v, xs, ramp[:, c]) for c in range(3)], -1).astype(np.uint8), "RGB")


def _portrait(photo_url, w: int, h: int, mask: Image.Image | None = None):
    """Portrait noir et blanc contrasté (cadré sur le sujet) et, si possible, son masque de détourage."""
    src = PI.photo(photo_url)
    if src is None:
        return None, None
    if mask is not None and mask.size != src.size:
        mask = mask.resize(src.size, Image.LANCZOS)
    try:
        if mask is not None:
            raise StopIteration  # masque déjà fourni

        from core.services.social import une
        if une.available():
            mask = une._mask(src)
    except StopIteration:
        pass
    except Exception:  # noqa: BLE001 — sans détourage, le portrait reste dans le cadre
        mask = None
    box = (mask.point(lambda x: 255 if x > 60 else 0).getbbox() if mask else None) or (0, 0, src.width, src.height)
    # Cadrage : le sujet occupe la largeur, la tête en haut
    bw_, bh_ = box[2] - box[0], box[3] - box[1]
    scale = max(w / (bw_ * 1.25), h / (bh_ * 1.15), w / src.width, h / src.height)
    cx = (box[0] + box[2]) / 2 * scale
    top = box[1] * scale - h * .02
    big = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.LANCZOS)
    x0 = int(min(max(0, cx - w / 2), big.width - w))
    y0 = int(min(max(0, top), big.height - h))
    pic = big.crop((x0, y0, x0 + w, y0 + h))
    pic = ImageOps.autocontrast(ImageOps.grayscale(pic), cutoff=1)
    pic = ImageOps.colorize(pic, (8, 6, 16), (250, 248, 255), mid=(120, 116, 132))
    m = None
    if mask:
        m = mask.resize(big.size, Image.LANCZOS).crop((x0, y0, x0 + w, y0 + h)).filter(ImageFilter.GaussianBlur(1))
    return pic, m


def framed(photo_url, w: int, seed=0, mask=None) -> Image.Image:
    """Bloc « portrait + cadre » (RGBA) : cadre carré en feuille de métal, tête qui dépasse en haut si détourée,
    bande basse froissée portant le « C » de Cauri (comme une statuette)."""
    over = int(w * .14)                    # marge au-dessus du cadre, où passe la tête
    H = w + over
    t = int(w * .085)                      # épaisseur du cadre
    out = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    inner = (t, over + t, w - t, over + w - t)
    pic, mask = _portrait(photo_url, w - 2 * t, H - t, mask)   # le portrait couvre du haut de l'image au bas du cadre
    if pic is not None:
        clip = Image.new("L", (w, H), 0)
        ImageDraw.Draw(clip).rectangle(inner, fill=255)
        layer = Image.new("RGBA", (w, H), (0, 0, 0, 0))
        layer.paste(pic, (t, 0))
        out.paste(layer, (0, 0), ImageChops.multiply(clip, layer.getchannel("A")))
    else:
        ImageDraw.Draw(out).rectangle(inner, fill=NIGHT_2 + (255,))
    # Cadre en feuille de métal
    frame_mask = Image.new("L", (w, H), 0)
    fd = ImageDraw.Draw(frame_mask)
    fd.rectangle([0, over, w, over + w], fill=255)
    fd.rectangle(inner, fill=0)
    # Bande basse déchirée : la feuille remonte sur les épaules
    rnd = random.Random(seed)
    band_top = over + int(w * .78)
    pts = [(t, over + w - t)]
    x = t
    while x < w - t:
        pts.append((x, band_top + rnd.randint(-int(w * .02), int(w * .02))))
        x += max(4, int(w * .018))
    pts += [(w - t, band_top), (w - t, over + w - t)]
    fd.polygon(pts, fill=255)
    foil = leaf((w, H), seed)
    out.paste(foil, (0, 0), frame_mask)
    # La tête devant le haut du cadre (détourage)
    if pic is not None and mask is not None:
        head = Image.new("L", (w, H), 0)
        head.paste(mask, (t, 0))
        keep = Image.new("L", (w, H), 0)
        ImageDraw.Draw(keep).rectangle([0, 0, w, over + t + int(w * .02)], fill=255)
        head = ImageChops.multiply(head, keep)
        layer = Image.new("RGBA", (w, H), (0, 0, 0, 0))
        layer.paste(pic, (t, 0))
        out.paste(layer, (0, 0), head)
    # Le « C » de Cauri en creux sur la bande basse
    cm = A.c_mark(int(w * .13))
    if cm:
        cx, cy = w // 2, int((band_top + over + w - t) / 2)
        shadow = Image.new("L", (w, H), 0)
        shadow.paste(cm, (cx - cm.width // 2 + 3, cy - cm.height // 2 + 4))
        out.paste((40, 20, 90, 255), (0, 0), shadow.filter(ImageFilter.GaussianBlur(2)))
        out.paste(NIGHT + (255,), (cx - cm.width // 2, cy - cm.height // 2), cm)
    return out


def _bg(size) -> Image.Image:
    W, H = size
    img = Image.new("RGB", size, NIGHT)
    glow = Image.radial_gradient("L").resize((int(W * 1.4), int(H * 1.2))).point(lambda v: int((255 - v) * .55))
    img.paste(NIGHT_2, (int(-W * .2), int(-H * .25)), glow)
    return Image.blend(img, Image.merge("RGB", [Image.effect_noise(size, 30).convert("L").point(lambda v: v // 5)] * 3), .12)


def _text_block(img, d, x, y, width, info, scale, align="m"):
    """Nom, rang et classement, titre, mois, données, mention, logo. Retourne la hauteur occupée."""
    s = scale
    ax = x + width / 2 if align == "m" else x
    anchor = "m" if align == "m" else "l"
    y0 = y
    name = info["artist"].upper()
    npx = A._fit(name, A.CINZEL, 92 * s, width, "Bold", .03)
    y += int(npx * .95)
    A._spaced(d, (ax, y), name, A._f(A.CINZEL, npx, "Bold"), fill=WHITE, spacing=.03, anchor=anchor)
    rank_line = f"N°{info['rank']} · {info['chart'].upper()}"
    y += int(56 * s)
    A._spaced(d, (ax, y), rank_line, A._f(A.SANS.replace("Regular", "Bold"), A._fit(rank_line, A.SANS, 30 * s, width, spacing=.08)),
              fill=LILAC, spacing=.08, anchor=anchor)
    if info.get("title"):
        t = f"« {info['title']} »"
        y += int(52 * s)
        A._spaced(d, (ax, y), t, A._f(A.GARAMOND, A._fit(t, A.GARAMOND, 40 * s, width, "Medium Italic"), "Medium Italic"), fill=WHITE, anchor=anchor)
    y += int(46 * s)
    A._spaced(d, (ax, y), info["period"].upper(), A._f(A.CINZEL, 24 * s, "Regular"), fill=(190, 180, 220), spacing=.3, anchor=anchor)
    st = info.get("stats") or {}
    if st.get("last") is not None or int(st.get("weeks") or 0) > 1:
        cells = [("CE MOIS", f"{info['rank']:02d}"), ("PRÉCÉDENT", "NOUV." if st.get("last") is None else f"{int(st['last']):02d}"),
                 ("MEILLEUR", f"{int(st['peak']):02d}" if st.get("peak") else "—"), ("MOIS", str(st.get("weeks") or "—"))]
        y += int(40 * s)
        cw = width / 4
        for k, (lab, val) in enumerate(cells):
            cx = x + cw * (k + .5)
            A._spaced(d, (cx, y + 18 * s), lab, A._f(A.SANS, 14 * s), fill=(170, 160, 200), spacing=.15)
            A._spaced(d, (cx, y + 60 * s), val, A._f(A.CINZEL, 36 * s, "Bold"), fill=WHITE, spacing=.04)
        y += int(70 * s)
    y += int(40 * s)
    A._spaced(d, (ax, y), "DISTINCTION FONDÉE SUR LA PERFORMANCE AU CLASSEMENT", A._f(A.SANS, A._fit("DISTINCTION FONDÉE SUR LA PERFORMANCE AU CLASSEMENT", A.SANS, 15 * s, width, spacing=.2)),
              fill=(150, 140, 185), spacing=.2, anchor=anchor)
    return y - y0


def _footer(img, d, x, y, width, info, scale, logo_w=None):
    """Logo, numéro de collection, code-barres et lien de vérification."""
    s = scale
    logo = PI.white_logo()
    lw = int(logo_w or 230 * s)
    if logo:
        lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
        img.paste(lg, (int(x), int(y)), lg)
    bc_w, bc_h = int(200 * s), int(58 * s)
    bc = A.barcode(code(info["number"], info["period_key"]).replace(" · ", ""), bc_w, bc_h, WHITE)
    bx = int(x + width - bc_w)
    img.paste(bc, (bx, int(y)), bc)
    A._spaced(d, (bx + bc_w, y + bc_h + 24 * s), code(info["number"], info["period_key"]), A._f(A.SANS, 14 * s), fill=(190, 180, 220), spacing=.12, anchor="r")
    num = f"DISTINCTION N° {info['number']:04d}" if info.get("number") else "DISTINCTION OFFICIELLE"
    A._spaced(d, (bx + bc_w, y - 16 * s), num, A._f(A.CINZEL, 20 * s, "Bold"), fill=LILAC, spacing=.2, anchor="r")
    if info.get("verify"):
        A._spaced(d, (x, y + (lg.height if logo else 0) + 34 * s), "VÉRIFIER : " + info["verify"].replace("https://", "").upper(),
                  A._f(A.SANS, 13 * s), fill=(150, 140, 185), spacing=.12, anchor="l")


def render(fmt: str, info: dict) -> Image.Image:
    """info : artist, title, rank, chart, period, period_key, number, stats, photo_url, verify."""
    W, H = FORMATS[fmt]
    img = _bg((W, H))
    d = ImageDraw.Draw(img)
    seed = hash(info["artist"]) % 1000
    if fmt in ("telephone", "post", "carte"):
        s = W / 1080
        fw = int(W * {"telephone": .80, "post": .62, "carte": .80}[fmt])
        top = int(H * (.07 if fmt == "telephone" else .045))
        if fmt == "telephone":
            top = int(H * .11)          # zone haute réservée par Instagram et TikTok
        block = framed(info["photo_url"], fw, seed, info.get("mask"))
        img.paste(block, ((W - fw) // 2, top), block)
        y = top + block.height + int(26 * s)
        if fmt == "carte":
            name = info["artist"].upper()
            npx = A._fit(name, A.CINZEL, 74 * s, W * .86, "Bold", .03)
            A._spaced(d, (W / 2, y + npx * .9), name, A._f(A.CINZEL, npx, "Bold"), fill=WHITE, spacing=.03)
            rl = f"N°{info['rank']} · {info['chart'].upper()}"
            A._spaced(d, (W / 2, y + npx * .9 + 48 * s), rl, A._f(A.SANS.replace("Regular", "Bold"), A._fit(rl, A.SANS, 26 * s, W * .86, spacing=.08)), fill=LILAC, spacing=.08)
            A._spaced(d, (W / 2, y + npx * .9 + 90 * s), info["period"].upper(), A._f(A.CINZEL, 22 * s, "Regular"), fill=(190, 180, 220), spacing=.3)
            _footer(img, d, W * .06, H - 110 * s, W * .88, info, s * .9, logo_w=170 * s)
        else:
            _text_block(img, d, W * .08, y, W * .84, info, s)
            fy = H - int((300 if fmt == "telephone" else 130) * s)
            _footer(img, d, W * .08, fy, W * .84, info, s)
    elif fmt == "carre":
        s = W / 1080
        fw = int(W * .46)
        block = framed(info["photo_url"], fw, seed, info.get("mask"))
        img.paste(block, (int(W * .05), int((H - block.height) / 2 - 20 * s)), block)
        tx = int(W * .55)
        _text_block(img, d, tx, int(H * .2), W * .40, info, s * .78, align="l")
        _footer(img, d, tx, H - int(150 * s), W * .40, info, s * .8, logo_w=180 * s)
    else:  # pc
        s = H / 1080
        fh = int(H * .80)
        fw = int(fh / 1.14)
        block = framed(info["photo_url"], fw, seed, info.get("mask"))
        img.paste(block, (int(W * .07), int((H - block.height) / 2)), block)
        tx = int(W * .07 + fw + W * .06)
        tw = W - tx - int(W * .07)
        _text_block(img, d, tx, int(H * .18), tw, info, s, align="l")
        _footer(img, d, tx, H - int(170 * s), tw, info, s)
    return img


def pattern_mask(w: int, h: int, cell: int) -> Image.Image:
    """Motif géométrique (losanges, croix et cauris) en bandes, inspiré des tissus ouest-africains."""
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    lw = max(2, cell // 18)
    for j in range(-1, h // cell + 2):
        for i in range(-1, w // cell + 2):
            cx, cy = i * cell + (cell // 2 if j % 2 else 0), j * cell
            r = cell * .48
            d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], outline=255, width=lw)
            r2 = r * .55
            d.polygon([(cx, cy - r2), (cx + r2, cy), (cx, cy + r2), (cx - r2, cy)], fill=255)
            d.polygon([(cx, cy - r2 * .55), (cx + r2 * .55, cy), (cx, cy + r2 * .55), (cx - r2 * .55, cy)], fill=0)
            k = r * .78
            for dx, dy in ((0, -k), (k, 0), (0, k), (-k, 0)):
                d.ellipse([cx + dx - lw * 1.6, cy + dy - lw * 1.6, cx + dx + lw * 1.6, cy + dy + lw * 1.6], fill=255)
    return m


def _seal(r: int) -> Image.Image:
    """Médaillon en métal violet au « C » de Cauri, avec ses rubans."""
    S = int(r * 2.2)
    im = Image.new("RGBA", (S, int(S * 1.35)), (0, 0, 0, 0))
    cx, cy = S // 2, S // 2
    rib = Image.new("L", im.size, 0)
    rd = ImageDraw.Draw(rib)
    for sx in (-1, 1):
        x0 = cx + sx * r * .35
        rd.polygon([(x0 - r * .28, cy), (x0 + r * .28, cy), (x0 + r * .28 + sx * r * .1, im.height - 4),
                    (x0 + sx * r * .1, im.height - r * .22), (x0 - r * .28 + sx * r * .1, im.height - 4)], fill=255)
    im.paste(A.VIO_DARK + (255,), (0, 0), rib)
    disc = Image.new("L", im.size, 0)
    dd = ImageDraw.Draw(disc)
    teeth = [(cx + (r if k % 2 == 0 else r * .92) * __import__("math").cos(k * 3.14159 / 24), cy + (r if k % 2 == 0 else r * .92) * __import__("math").sin(k * 3.14159 / 24)) for k in range(48)]
    dd.polygon(teeth, fill=255)
    im.paste(leaf(im.size, 7).convert("RGBA"), (0, 0), disc)
    d = ImageDraw.Draw(im)
    d.ellipse([cx - r * .74, cy - r * .74, cx + r * .74, cy + r * .74], fill=NIGHT + (255,))
    d.ellipse([cx - r * .68, cy - r * .68, cx + r * .68, cy + r * .68], outline=LILAC + (255,), width=max(2, r // 40))
    cm = A.c_mark(int(r * .7))
    if cm:
        im.paste(LILAC + (255,), (cx - cm.width // 2, cy - cm.height // 2 - int(r * .06)), cm)
    A._spaced(d, (cx, cy + r * .52), "OFFICIEL", A._f(A.CINZEL, r * .12, "Bold"), fill=LILAC + (255,), spacing=.3)
    return im


def certificat(info: dict, size=(3508, 2480)) -> Image.Image:
    """Certificat A4 paysage (300 ppp) : papier ivoire, bande à motifs en feuille violette, médaillon, texte."""
    W, H = size
    s = W / 3508
    ivory = (250, 247, 240)
    img = Image.new("RGB", size, ivory)
    img = Image.blend(img, Image.merge("RGB", [Image.effect_noise(size, 30).convert("L").point(lambda v: 200 + v // 5)] * 3), .06)
    band_x = int(W * .64)
    pm = pattern_mask(W - band_x, H, int(250 * s))
    band = leaf((W - band_x, H), 3)
    img.paste(band, (band_x, 0), pm)
    d = ImageDraw.Draw(img)
    d.rectangle([int(60 * s), int(60 * s), W - int(60 * s), H - int(60 * s)], outline=A.VIO, width=max(2, int(5 * s)))
    x = int(230 * s)
    logo = PI.white_logo()
    if logo:
        lw = int(520 * s)
        lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
        img.paste(NIGHT, (x, int(200 * s)), lg.getchannel("A"))
    ink = (24, 16, 48)
    d.text((x, int(720 * s)), "Certificat", font=A._f(A.CINZEL, 230 * s, "Bold"), fill=ink, anchor="ls")
    A._spaced(d, (x + 6 * s, int(820 * s)), "DE DISTINCTION OFFICIELLE", A._f(A.SANS, 52 * s), fill=A.VIO, spacing=.3, anchor="l")
    A._spaced(d, (x, int(1010 * s)), "CE CERTIFICAT EST DÉCERNÉ À", A._f(A.SANS.replace("Regular", "Bold"), 44 * s), fill=ink, spacing=.12, anchor="l")
    name = info["artist"]
    d.text((x, int(1240 * s)), name, font=A._f(A.GARAMOND, A._fit(name, A.GARAMOND, 210 * s, band_x - x - 160 * s, "Bold Italic"), "Bold Italic"), fill=ink, anchor="ls")
    d.line([(x, int(1290 * s)), (band_x - int(160 * s), int(1290 * s))], fill=A.VIO, width=max(2, int(5 * s)))
    body = (f"N°{info['rank']} du {info['chart']} en {info['period'].lower()}"
            + (f" avec « {info['title']} »" if info.get("title") else "") + ". Distinction fondée sur la performance au classement, "
            "calculée chaque semaine à partir de chiffres d’écoute et de vues selon une formule publique.")
    f = A._f(A.SANS, 48 * s)
    words, line, yy = body.split(), "", int(1420 * s)
    for wd in words:
        if f.getlength(line + " " + wd) > band_x - x - 200 * s:
            d.text((x, yy), line.strip(), font=f, fill=(60, 54, 80))
            yy += int(70 * s)
            line = ""
        line += " " + wd
    d.text((x, yy), line.strip(), font=f, fill=(60, 54, 80))
    # Signatures et preuves
    by = H - int(330 * s)
    for k, lab in enumerate(("DATE · " + info["period"].upper(), "CAURI CHARTS")):
        lx = x + k * int(820 * s)
        d.line([(lx, by), (lx + int(640 * s), by)], fill=ink, width=max(2, int(3 * s)))
        A._spaced(d, (lx, by + 60 * s), lab, A._f(A.SANS, 34 * s), fill=ink, spacing=.15, anchor="l")
    bc = A.barcode(code(info["number"], info["period_key"]).replace(" · ", ""), int(520 * s), int(130 * s), ink)
    bx_ = band_x - int(720 * s)
    img.paste(bc, (bx_, H - int(560 * s)), bc)
    A._spaced(d, (bx_, H - int(395 * s)), code(info["number"], info["period_key"]), A._f(A.SANS, 30 * s), fill=ink, spacing=.15, anchor="l")
    if info.get("verify"):
        A._spaced(d, (x, H - int(170 * s)), "VÉRIFIER : " + info["verify"].replace("https://", ""), A._f(A.SANS, 26 * s), fill=(90, 80, 120), spacing=.05, anchor="l")
    seal = _seal(int(300 * s))
    img.paste(seal, (band_x - seal.width // 2, int(260 * s)), seal)
    return img


def enveloppe(info: dict, size=(2598, 1299)) -> Image.Image:
    """Enveloppe DL (220 × 110 mm, 300 ppp), face avant : papier nuit violette, expéditeur, destinataire, cachet."""
    W, H = size
    s = W / 2598
    img = _bg(size)
    d = ImageDraw.Draw(img)
    fm = Image.new("L", size, 0)
    ImageDraw.Draw(fm).rectangle([int(40 * s), int(40 * s), W - int(40 * s), H - int(40 * s)], outline=255, width=max(2, int(6 * s)))
    img.paste(leaf(size, 5), (0, 0), fm)
    logo = PI.white_logo()
    if logo:
        lw = int(420 * s)
        lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
        img.paste(lg, (int(130 * s), int(120 * s)), lg)
    A._spaced(d, (int(130 * s), int(170 * s) + (lg.height if logo else 0)), "DISTINCTION OFFICIELLE", A._f(A.SANS, 30 * s), fill=LILAC, spacing=.3, anchor="l")
    num = f"N° {info['number']:04d}" if info.get("number") else ""
    A._spaced(d, (W - int(130 * s), int(170 * s)), num, A._f(A.CINZEL, 52 * s, "Bold"), fill=LILAC, spacing=.2, anchor="r")
    x = int(W * .48)
    A._spaced(d, (x, int(H * .52)), "À L’ATTENTION DE", A._f(A.SANS, 30 * s), fill=(190, 180, 220), spacing=.3, anchor="l")
    name = info["artist"].upper()
    A._spaced(d, (x, int(H * .52) + 130 * s), name, A._f(A.CINZEL, A._fit(name, A.CINZEL, 110 * s, W - x - 160 * s, "Bold", .04), "Bold"), fill=WHITE, spacing=.04, anchor="l")
    A._spaced(d, (x, int(H * .52) + 200 * s), f"N°{info['rank']} · {info['chart'].upper()} · {info['period'].upper()}", A._f(A.SANS, 30 * s), fill=LILAC, spacing=.12, anchor="l")
    bc = A.barcode(code(info["number"], info["period_key"]).replace(" · ", ""), int(380 * s), int(90 * s), WHITE)
    img.paste(bc, (W - int(130 * s) - bc.width, H - int(230 * s)), bc)
    A._spaced(d, (W - int(130 * s), H - int(110 * s)), code(info["number"], info["period_key"]), A._f(A.SANS, 24 * s), fill=(190, 180, 220), spacing=.15, anchor="r")
    seal = _seal(int(190 * s))
    img.paste(seal, (int(180 * s), H - seal.height - int(80 * s)), seal)
    return img
