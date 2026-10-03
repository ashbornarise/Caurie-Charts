"""Kit de distinction : la carte « nommé·e » (portrait noir et blanc qui sort d'un cadre en feuille de métal argent, bleu et violet)
déclinée en 7 formats, plus le certificat A4 et l'enveloppe.

  telephone 1080 × 1920 · pc 1920 × 1080 · carre 1080 × 1080 · post 1080 × 1350 · carte 63 × 88 mm (300 ppp)
  certificat A4 portrait (300 ppp, plaque de prestige) · enveloppe DL 220 × 110 mm (300 ppp)
Thème : le blanc domine, accents bleu et violet, texte noir.
Ordre de lecture : photo → nom → rang et classement → titre → mois → données → numéro de collection et code-barres.
Le portrait sort du cadre si rembg est installé (chaîne de nuit) ; sinon il reste dans le cadre, sans effet.
"""
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from core.services.social import award as A
from core.services.social import image as PI

# Thème : le blanc domine, accents bleu et violet, texte noir
PAPER, PAPER_2 = (249, 250, 254), (226, 234, 252)
INK, SUB, BLUE = (14, 18, 40), (92, 98, 136), (52, 110, 230)
NIGHT, NIGHT_2 = INK, (226, 230, 242)   # (anciens noms) : encre du « C », fond de secours du portrait
LILAC, WHITE = A.VIO, INK               # (anciens noms) : accent violet, texte principal
MONTHS = ["JAN", "FÉV", "MARS", "AVR", "MAI", "JUIN", "JUIL", "AOÛT", "SEPT", "OCT", "NOV", "DÉC"]
FORMATS = {"telephone": (1080, 1920), "pc": (1920, 1080), "carre": (1080, 1080), "post": (1080, 1350), "carte": (744, 1039)}


def code(number: int | None, period_key: str) -> str:
    y, m = period_key.split("-")[:2]
    return f"CC-{number or 0:04d} · {MONTHS[int(m) - 1]}-{y}"


_LEAVES: dict = {}


def leaf(size, seed=0) -> Image.Image:
    """Feuille de métal froissée (calculée au plus en 900 px puis agrandie, et gardée en mémoire)."""
    w, h = int(size[0]), int(size[1])
    key = (w, h, seed)
    if key not in _LEAVES:
        f = min(1.0, 900 / max(w, h))
        small = _leaf((max(8, int(w * f)), max(8, int(h * f))), seed)
        if len(_LEAVES) > 24:
            _LEAVES.clear()
        _LEAVES[key] = small if f == 1.0 else small.resize((w, h), Image.BICUBIC)
    return _LEAVES[key].copy()


def _leaf(size, seed=0) -> Image.Image:
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
    # Argent bleuté et violet (holographique) : du bleu profond au blanc, reflets violets
    ramp = np.array([(64, 84, 160), BLUE, (178, 198, 248), (255, 255, 255), (206, 190, 255), A.VIO], np.float32)
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
    foil = Image.blend(_metal((w, H), seed), Image.new("RGB", (w, H), (246, 247, 252)), .35)
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
        out.paste((255, 255, 255, 200), (0, 0), shadow.filter(ImageFilter.GaussianBlur(2)))
        out.paste(NIGHT + (255,), (cx - cm.width // 2, cy - cm.height // 2), cm)
    return out


def _bg(size) -> Image.Image:
    """Papier blanc nacré, halo bleu très léger en haut et violet en bas."""
    W, H = size
    img = Image.new("RGB", size, PAPER)
    glow = Image.radial_gradient("L").resize((int(W * 1.6), int(H * 1.1))).point(lambda v: int((255 - v) * .55))
    img.paste(PAPER_2, (int(-W * .3), int(-H * .45)), glow)
    glow2 = Image.radial_gradient("L").resize((int(W * 1.4), int(H * .9))).point(lambda v: int((255 - v) * .22))
    img.paste((236, 228, 255), (int(-W * .2), int(H * .55)), glow2)
    return Image.blend(img, Image.merge("RGB", [Image.effect_noise(size, 20).convert("L").point(lambda v: 200 + v // 5)] * 3), .05)


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
    A._spaced(d, (ax, y), info["period"].upper(), A._f(A.CINZEL, 24 * s, "Regular"), fill=SUB, spacing=.3, anchor=anchor)
    st = info.get("stats") or {}
    if st.get("last") is not None or int(st.get("weeks") or 0) > 1:
        cells = [("CE MOIS", f"{info['rank']:02d}"), ("PRÉCÉDENT", "NOUV." if st.get("last") is None else f"{int(st['last']):02d}"),
                 ("MEILLEUR", f"{int(st['peak']):02d}" if st.get("peak") else "—"), ("MOIS", str(st.get("weeks") or "—"))]
        y += int(40 * s)
        cw = width / 4
        for k, (lab, val) in enumerate(cells):
            cx = x + cw * (k + .5)
            A._spaced(d, (cx, y + 18 * s), lab, A._f(A.SANS, 14 * s), fill=SUB, spacing=.15)
            A._spaced(d, (cx, y + 60 * s), val, A._f(A.CINZEL, 36 * s, "Bold"), fill=WHITE, spacing=.04)
        y += int(70 * s)
    y += int(40 * s)
    A._spaced(d, (ax, y), "DISTINCTION FONDÉE SUR LA PERFORMANCE AU CLASSEMENT", A._f(A.SANS, A._fit("DISTINCTION FONDÉE SUR LA PERFORMANCE AU CLASSEMENT", A.SANS, 15 * s, width, spacing=.2)),
              fill=SUB, spacing=.2, anchor=anchor)
    return y - y0


def _footer(img, d, x, y, width, info, scale, logo_w=None):
    """Logo, numéro de collection, code-barres et lien de vérification."""
    s = scale
    logo = PI.white_logo()
    lw = int(logo_w or 230 * s)
    if logo:
        lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
        img.paste(INK, (int(x), int(y)), lg.getchannel("A"))
    bc_w, bc_h = int(200 * s), int(58 * s)
    bc = A.barcode(code(info["number"], info["period_key"]).replace(" · ", ""), bc_w, bc_h, INK)
    bx = int(x + width - bc_w)
    img.paste(bc, (bx, int(y)), bc)
    A._spaced(d, (bx + bc_w, y + bc_h + 24 * s), code(info["number"], info["period_key"]), A._f(A.SANS, 14 * s), fill=SUB, spacing=.12, anchor="r")
    num = f"DISTINCTION N° {info['number']:04d}" if info.get("number") else "DISTINCTION OFFICIELLE"
    A._spaced(d, (bx + bc_w, y - 16 * s), num, A._f(A.CINZEL, 20 * s, "Bold"), fill=LILAC, spacing=.2, anchor="r")
    if info.get("verify"):
        A._spaced(d, (x, y + (lg.height if logo else 0) + 34 * s), "VÉRIFIER : " + info["verify"].replace("https://", "").upper(),
                  A._f(A.SANS, 13 * s), fill=SUB, spacing=.12, anchor="l")


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
            A._spaced(d, (W / 2, y + npx * .9 + 90 * s), info["period"].upper(), A._f(A.CINZEL, 22 * s, "Regular"), fill=SUB, spacing=.3)
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
    im.paste(A.VIO + (255,), (0, 0), rib)
    disc = Image.new("L", im.size, 0)
    dd = ImageDraw.Draw(disc)
    teeth = [(cx + (r if k % 2 == 0 else r * .92) * __import__("math").cos(k * 3.14159 / 24), cy + (r if k % 2 == 0 else r * .92) * __import__("math").sin(k * 3.14159 / 24)) for k in range(48)]
    dd.polygon(teeth, fill=255)
    im.paste(leaf(im.size, 7).convert("RGBA"), (0, 0), disc)
    d = ImageDraw.Draw(im)
    d.ellipse([cx - r * .74, cy - r * .74, cx + r * .74, cy + r * .74], fill=(252, 252, 255, 255))
    d.ellipse([cx - r * .68, cy - r * .68, cx + r * .68, cy + r * .68], outline=BLUE + (255,), width=max(2, r // 40))
    cm = A.c_mark(int(r * .7))
    if cm:
        im.paste(A.VIO + (255,), (cx - cm.width // 2, cy - cm.height // 2 - int(r * .06)), cm)
    A._spaced(d, (cx, cy + r * .52), "OFFICIEL", A._f(A.CINZEL, r * .12, "Bold"), fill=INK + (255,), spacing=.3)
    return im


def _metal(size, seed=0) -> Image.Image:
    """Métal argent bleuté pour les moulures et ornements (la feuille froissée, plus lisse)."""
    return leaf(size, seed).filter(ImageFilter.GaussianBlur(max(1, size[0] // 1200)))


def _emboss(img: Image.Image, mask: Image.Image, seed=0, depth=3) -> None:
    """Pose un ornement en métal : ombre portée, métal, arête claire en haut à gauche."""
    k = max(1, depth)
    box = mask.getbbox()
    if not box:
        return
    pad = 3 * k + 4
    x0, y0 = max(0, box[0] - pad), max(0, box[1] - pad)
    x1, y1 = min(img.width, box[2] + pad), min(img.height, box[3] + pad)
    m = mask.crop((x0, y0, x1, y1))   # tout se calcule sur la seule surface de l'ornement
    img.paste((150, 156, 180), (x0 + k, y0 + k), m.filter(ImageFilter.GaussianBlur(k)))
    img.paste(_metal(m.size, seed), (x0, y0), m)
    soft = m.filter(ImageFilter.GaussianBlur(1))
    hi = ImageChops.multiply(ImageChops.subtract(soft, ImageChops.offset(soft, k, k)), m)
    img.paste((255, 255, 255), (x0, y0), hi)


def _scroll(d, cx, cy, r, turns, start, width, fill=255):
    """Volute : spirale d'arcs de rayon décroissant."""
    import math
    a = start
    rr = r
    x, y = cx, cy
    for _ in range(int(turns * 8)):
        nx = x + rr * math.cos(math.radians(a))
        ny = y + rr * math.sin(math.radians(a))
        d.line([(x, y), (nx, ny)], fill=fill, width=width)
        d.ellipse([nx - width / 2, ny - width / 2, nx + width / 2, ny + width / 2], fill=fill)
        x, y = nx, ny
        a += 45
        rr *= 0.86


def _corner(size: int) -> Image.Image:
    """Ornement d'angle (masque) : filet en équerre, volutes, feuilles et un cauri, à recopier dans les 4 coins."""
    import math
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    w = max(3, size // 60)
    d.line([(size * .08, size * .08), (size * .95, size * .08)], fill=255, width=w * 2)
    d.line([(size * .08, size * .08), (size * .08, size * .95)], fill=255, width=w * 2)
    d.line([(size * .16, size * .16), (size * .7, size * .16)], fill=255, width=w)
    d.line([(size * .16, size * .16), (size * .16, size * .7)], fill=255, width=w)
    _scroll(d, size * .30, size * .30, size * .085, 2.2, 0, w)
    _scroll(d, size * .58, size * .12, size * .06, 1.6, 90, w)
    _scroll(d, size * .12, size * .58, size * .06, 1.6, 0, w)
    for k in range(5):  # feuilles le long de la diagonale
        t = .2 + k * .1
        cx, cy = size * t + size * .06, size * t + size * .06
        for side in (-1, 1):
            leafm = Image.new("L", (int(size * .12), int(size * .045)), 0)
            ImageDraw.Draw(leafm).ellipse([0, 0, leafm.width - 1, leafm.height - 1], fill=255)
            leafm = leafm.rotate(45 + side * 50, expand=True, resample=Image.BICUBIC)
            m.paste(255, (int(cx - leafm.width / 2 + side * size * .03), int(cy - leafm.height / 2 - side * size * .03)), leafm)
    cw = A.cowrie(int(size * .1), int(size * .14), (255, 255, 255)).getchannel("A").rotate(45, expand=True)
    m.paste(255, (int(size * .02), int(size * .02)), cw)
    return m


def _flourish(width: int, height: int) -> Image.Image:
    """Filet orné horizontal (masque) : deux traits qui se terminent en volutes, un losange au centre."""
    m = Image.new("L", (width, height), 0)
    d = ImageDraw.Draw(m)
    w = max(3, height // 14)
    cy = height / 2
    d.line([(width * .12, cy), (width * .42, cy)], fill=255, width=w)
    d.line([(width * .58, cy), (width * .88, cy)], fill=255, width=w)
    r = height * .32
    d.polygon([(width / 2, cy - r), (width / 2 + r, cy), (width / 2, cy + r), (width / 2 - r, cy)], fill=255)
    d.polygon([(width / 2, cy - r * .45), (width / 2 + r * .45, cy), (width / 2, cy + r * .45), (width / 2 - r * .45, cy)], fill=0)
    _scroll(d, width * .12, cy, height * .2, 1.8, 180, w)
    _scroll(d, width * .88, cy, height * .2, 1.8, 0, w)
    return m


def _crest(size: int) -> Image.Image:
    """Écusson Cauri (RGBA) : bouclier violet bordé d'argent, « C » blanc, cauris, bandeau « CAURI CHARTS »."""
    W, H = size, int(size * 1.25)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    pts = [(W * .12, H * .06), (W * .88, H * .06), (W * .88, H * .46), (W * .5, H * .80), (W * .12, H * .46)]
    ImageDraw.Draw(sh).polygon(pts, fill=255)
    rim = sh.filter(ImageFilter.MaxFilter(max(3, (W // 40) | 1)))
    im.paste(_metal((W, H), 4).convert("RGBA"), (0, 0), rim)
    body = Image.new("RGBA", (W, H), A.VIO + (255,))
    body.paste(A.VIO_DARK + (255,), (0, 0), Image.linear_gradient("L").resize((W, H)).point(lambda v: int(v * .7)))
    im.paste(body, (0, 0), sh)
    cm = A.c_mark(int(H * .36))
    if cm:
        im.paste((255, 255, 255, 255), (int(W / 2 - cm.width / 2), int(H * .14)), cm)
    for sx in (-1, 1):
        c = A.cowrie(int(W * .08), int(W * .11), (255, 255, 255))
        im.alpha_composite(c, (int(W / 2 + sx * W * .25 - c.width / 2), int(H * .2)))
    # Bandeau
    band = Image.new("L", (W, H), 0)
    bd = ImageDraw.Draw(band)
    by = H * .78
    bd.polygon([(W * .02, by), (W * .98, by), (W * .92, by + H * .07), (W * .98, by + H * .14), (W * .02, by + H * .14),
                (W * .08, by + H * .07)], fill=255)
    im.paste((252, 252, 255, 255), (0, 0), band)
    edge = ImageChops.subtract(band.filter(ImageFilter.MaxFilter(5)), band)
    im.paste(BLUE + (255,), (0, 0), edge)
    d = ImageDraw.Draw(im)
    A._spaced(d, (W / 2, by + H * .1), "CAURI CHARTS", A._f(A.CINZEL, H * .065, "Bold"), fill=A.VIO + (255,), spacing=.2)
    return im


def _seal_ring(r: int, year: str) -> Image.Image:
    """Sceau de prestige : disque argent dentelé, couronne de texte, « C » violet, année, rubans violet et bleu."""
    import math
    S = int(r * 2.3)
    im = Image.new("RGBA", (S, int(S * 1.45)), (0, 0, 0, 0))
    cx, cy = S // 2, S // 2
    rib = Image.new("L", im.size, 0)
    rd = ImageDraw.Draw(rib)
    for sx, col in ((-1, A.VIO), (1, BLUE)):
        x0 = cx + sx * r * .32
        poly = [(x0 - r * .26, cy), (x0 + r * .26, cy), (x0 + r * .26 + sx * r * .12, im.height - 6),
                (x0 + sx * r * .12, im.height - r * .26), (x0 - r * .26 + sx * r * .12, im.height - 6)]
        one = Image.new("L", im.size, 0)
        ImageDraw.Draw(one).polygon(poly, fill=255)
        im.paste(col + (255,), (0, 0), one)
    disc = Image.new("L", im.size, 0)
    teeth = [(cx + (r if k % 2 == 0 else r * .93) * math.cos(k * math.pi / 30), cy + (r if k % 2 == 0 else r * .93) * math.sin(k * math.pi / 30)) for k in range(60)]
    ImageDraw.Draw(disc).polygon(teeth, fill=255)
    im.paste(_metal(im.size, 9).convert("RGBA"), (0, 0), disc)
    d = ImageDraw.Draw(im)
    d.ellipse([cx - r * .80, cy - r * .80, cx + r * .80, cy + r * .80], outline=(255, 255, 255, 255), width=max(2, r // 45))
    d.ellipse([cx - r * .56, cy - r * .56, cx + r * .56, cy + r * .56], fill=(252, 252, 255, 255), outline=A.VIO + (255,), width=max(2, r // 35))
    ring = Image.new("RGB", im.size, (0, 0, 0))
    A._ring_text(ring, (cx, cy), r * .68, "CAURI CHARTS", A._f(A.CINZEL, r * .13, "Bold"), (255, 255, 255))
    A._ring_text(ring, (cx, cy), r * .68, "DISTINCTION OFFICIELLE", A._f(A.CINZEL, r * .10, "Bold"), (255, 255, 255), bottom=True)
    im.paste(INK + (255,), (0, 0), ring.convert("L"))
    cm = A.c_mark(int(r * .55))
    if cm:
        im.paste(A.VIO + (255,), (cx - cm.width // 2, cy - cm.height // 2 - int(r * .1)), cm)
    A._spaced(d, (cx, cy + r * .42), year, A._f(A.CINZEL, r * .14, "Bold"), fill=INK + (255,), spacing=.2)
    return im


def certificat(info: dict, size=(2480, 3508)) -> Image.Image:
    """Certificat de prestige, A4 portrait (300 ppp) : plaque blanc nacré, moulure argent bleuté, ornements d'angle,
    écusson Cauri, titre, nom, texte, signatures, sceau à rubans, date, numéro et code-barres. Le blanc domine."""
    W, H = size
    s = W / 2480
    img = Image.new("RGB", size, (246, 247, 252))
    # Métal blanc brossé et reflet central
    brush = Image.effect_noise((max(1, W // 40), H), 70).convert("L").resize((W, H), Image.BILINEAR)
    img = Image.blend(img, Image.merge("RGB", [brush.point(lambda v: 205 + v // 6)] * 3), .18)
    sheen = Image.radial_gradient("L").resize((int(W * 1.3), int(H * 1.1))).point(lambda v: int((255 - v) * .6))
    img.paste((255, 255, 255), (int(-W * .15), int(-H * .05)), sheen)
    # Moulure du cadre : anneaux argent bleuté, filets violet et bleu
    frame = Image.new("L", size, 0)
    fd = ImageDraw.Draw(frame)
    m0, m1 = int(40 * s), int(118 * s)
    fd.rectangle([m0, m0, W - m0, H - m0], fill=255)
    fd.rectangle([m1, m1, W - m1, H - m1], fill=0)
    _emboss(img, frame, 11, int(6 * s))
    d = ImageDraw.Draw(img)
    d.rectangle([m1 + int(14 * s), m1 + int(14 * s), W - m1 - int(14 * s), H - m1 - int(14 * s)], outline=A.VIO, width=max(2, int(5 * s)))
    d.rectangle([m1 + int(30 * s), m1 + int(30 * s), W - m1 - int(30 * s), H - m1 - int(30 * s)], outline=BLUE, width=max(1, int(2 * s)))
    # Ornements d'angle et milieux
    orn = Image.new("L", size, 0)
    cs = int(430 * s)
    c = _corner(cs)
    for k, (x, y) in enumerate(((m1, m1), (W - m1 - cs, m1), (m1, H - m1 - cs), (W - m1 - cs, H - m1 - cs))):
        cc = c if k == 0 else ImageOps.mirror(c) if k == 1 else ImageOps.flip(c) if k == 2 else ImageOps.flip(ImageOps.mirror(c))
        orn.paste(255, (x, y), cc)
    fl = _flourish(int(900 * s), int(110 * s))
    orn.paste(255, (int(W / 2 - fl.width / 2), m1 + int(40 * s)), fl)
    orn.paste(255, (int(W / 2 - fl.width / 2), H - m1 - int(40 * s) - fl.height), fl)
    _emboss(img, orn, 13, int(4 * s))
    d = ImageDraw.Draw(img)
    ink = INK
    # En-tête : CAURI CHARTS, écusson flanqué de filets ornés
    A._spaced(d, (W / 2, int(480 * s)), "CAURI CHARTS", A._f(A.CINZEL, 150 * s, "Bold"), fill=ink, spacing=.08)
    crest = _crest(int(330 * s))
    img.paste(crest, (int(W / 2 - crest.width / 2), int(560 * s)), crest)
    side = Image.new("L", size, 0)
    sf = _flourish(int(720 * s), int(120 * s))
    side.paste(255, (int(W / 2 - crest.width / 2 - sf.width + 40 * s), int(560 * s + crest.height * .35)), sf)
    side.paste(255, (int(W / 2 + crest.width / 2 - 40 * s), int(560 * s + crest.height * .35)), sf)
    _emboss(img, side, 17, int(3 * s))
    d = ImageDraw.Draw(img)
    # Titre
    y = int(560 * s + crest.height + 210 * s)
    d.text((W / 2, y), "Distinction Officielle", font=A._f(A.GARAMOND, 190 * s, "Bold Italic"), fill=A.VIO_DARK, anchor="ms")
    rule = Image.new("L", size, 0)
    rf = _flourish(int(1300 * s), int(90 * s))
    rule.paste(255, (int(W / 2 - rf.width / 2), y + int(40 * s)), rf)
    _emboss(img, rule, 19, int(3 * s))
    d = ImageDraw.Draw(img)
    y += int(250 * s)
    A._spaced(d, (W / 2, y), "CE CERTIFICAT ATTESTE QUE", A._f(A.CINZEL, 54 * s, "Regular"), fill=ink, spacing=.12)
    y += int(230 * s)
    name = info["artist"]
    npx = A._fit(name, A.CINZEL, 190 * s, W - 700 * s, "Regular", .02)
    A._spaced(d, (W / 2, y), name, A._f(A.CINZEL, npx, "Regular"), fill=ink, spacing=.02)
    d.line([(W / 2 - 800 * s, y + 50 * s), (W / 2 + 800 * s, y + 50 * s)], fill=BLUE, width=max(2, int(4 * s)))
    y += int(170 * s)
    rank_txt = "LA 1re PLACE" if int(info["rank"]) == 1 else f"LA {info['rank']}e PLACE"
    lines = [(f"A OCCUPÉ {rank_txt} DU", A.CINZEL, 52, "Regular", ink),
             (info["chart"], A.GARAMOND, 96, "SemiBold Italic", A.VIO_DARK),
             (f"AU MOIS DE {info['period'].upper()}" + (f" AVEC « {info['title'].upper()} »" if info.get("title") else ""), A.CINZEL, 52, "Regular", ink),
             ("SELON LE CLASSEMENT CAURI CHARTS, CALCULÉ CHAQUE SEMAINE", A.CINZEL, 44, "Regular", ink),
             ("SUR DES DONNÉES RÉELLES D’ÉCOUTE ET DE VUES, SELON UNE FORMULE PUBLIQUE", A.CINZEL, 44, "Regular", ink)]
    for text, font, px, weight, col in lines:
        size_px = A._fit(text, font, px * s, W - 760 * s, weight, .02)
        A._spaced(d, (W / 2, y), text, A._f(font, size_px, weight), fill=col, spacing=.02)
        y += int(px * s * 1.55)
    # Signatures (au nom de l'institution, sans signature de personne)
    sy = int(H - 950 * s)
    for sx, top, label in ((W * .27, "Cauri Charts", "LA DIRECTION, CAURI CHARTS"),
                           (W * .73, f"N° {info['number']:04d}" if info.get("number") else "N° —", "REGISTRE DES DISTINCTIONS")):
        d.text((sx, sy), top, font=A._f(A.GARAMOND, 88 * s, "Medium Italic"), fill=A.VIO_DARK, anchor="ms")
        d.line([(sx - 330 * s, sy + 34 * s), (sx + 330 * s, sy + 34 * s)], fill=ink, width=max(2, int(3 * s)))
        A._spaced(d, (sx, sy + 90 * s), label, A._f(A.CINZEL, 32 * s, "Regular"), fill=ink, spacing=.08)
    seal = _seal_ring(int(240 * s), info["period_key"][:4])
    img.paste(seal, (int(W / 2 - seal.width / 2), int(sy - 380 * s)), seal)
    # Date
    dy = int(H - 520 * s)
    d.text((W / 2, dy), info["period"], font=A._f(A.GARAMOND, 92 * s, "SemiBold Italic"), fill=ink, anchor="ms")
    d.line([(W / 2 - 420 * s, dy + 30 * s), (W / 2 - 300 * s, dy + 30 * s)], fill=ink, width=max(2, int(3 * s)))
    d.line([(W / 2 + 300 * s, dy + 30 * s), (W / 2 + 420 * s, dy + 30 * s)], fill=ink, width=max(2, int(3 * s)))
    A._spaced(d, (W / 2, dy + 90 * s), "DATE", A._f(A.CINZEL, 34 * s, "Regular"), fill=ink, spacing=.2)
    # Numéro, code-barres et vérification
    bc = A.barcode(code(info["number"], info["period_key"]).replace(" · ", ""), int(460 * s), int(84 * s), ink)
    img.paste(bc, (int(W / 2 - bc.width / 2), int(H - 380 * s)), bc)
    tail = code(info["number"], info["period_key"]) + ("   ·   VÉRIFIER : " + info["verify"].replace("https://", "") if info.get("verify") else "")
    A._spaced(d, (W / 2, int(H - 250 * s)), tail, A._f(A.SANS, A._fit(tail, A.SANS, 26 * s, W - 800 * s, spacing=.08)), fill=SUB, spacing=.08)
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
        img.paste(INK, (int(130 * s), int(120 * s)), lg.getchannel("A"))
    A._spaced(d, (int(130 * s), int(170 * s) + (lg.height if logo else 0)), "DISTINCTION OFFICIELLE", A._f(A.SANS, 30 * s), fill=LILAC, spacing=.3, anchor="l")
    num = f"N° {info['number']:04d}" if info.get("number") else ""
    A._spaced(d, (W - int(130 * s), int(170 * s)), num, A._f(A.CINZEL, 52 * s, "Bold"), fill=LILAC, spacing=.2, anchor="r")
    x = int(W * .48)
    A._spaced(d, (x, int(H * .52)), "À L’ATTENTION DE", A._f(A.SANS, 30 * s), fill=SUB, spacing=.3, anchor="l")
    name = info["artist"].upper()
    A._spaced(d, (x, int(H * .52) + 130 * s), name, A._f(A.CINZEL, A._fit(name, A.CINZEL, 110 * s, W - x - 160 * s, "Bold", .04), "Bold"), fill=WHITE, spacing=.04, anchor="l")
    A._spaced(d, (x, int(H * .52) + 200 * s), f"N°{info['rank']} · {info['chart'].upper()} · {info['period'].upper()}", A._f(A.SANS, 30 * s), fill=LILAC, spacing=.12, anchor="l")
    bc = A.barcode(code(info["number"], info["period_key"]).replace(" · ", ""), int(380 * s), int(90 * s), INK)
    img.paste(bc, (W - int(130 * s) - bc.width, H - int(230 * s)), bc)
    A._spaced(d, (W - int(130 * s), H - int(110 * s)), code(info["number"], info["period_key"]), A._f(A.SANS, 24 * s), fill=SUB, spacing=.15, anchor="r")
    seal = _seal(int(190 * s))
    img.paste(seal, (int(180 * s), H - seal.height - int(80 * s)), seal)
    return img


# ------------------------------------------------------------------ les trois cartes (85 × 55 mm, 300 ppp)
CARD = (1004, 650)


def _card_base(seed=0) -> Image.Image:
    W, H = CARD
    img = _bg(CARD)
    fm = Image.new("L", CARD, 0)
    ImageDraw.Draw(fm).rounded_rectangle([14, 14, W - 15, H - 15], radius=30, outline=255, width=10)
    _emboss(img, fm, seed, 2)
    ImageDraw.Draw(img).rounded_rectangle([34, 34, W - 35, H - 35], radius=20, outline=A.VIO, width=2)
    return img


def _logo_ink(img, x, y, w, color=INK):
    logo = PI.white_logo()
    if logo:
        lg = logo.resize((int(w), round(logo.size[1] * w / logo.size[0])), Image.LANCZOS)
        img.paste(color, (int(x), int(y)), lg.getchannel("A"))
        return lg.height
    return 0


def card_brand(info: dict) -> Image.Image:
    """Carte Cauri Charts seule : logo, « Distinction officielle », bande de motif en métal."""
    W, H = CARD
    img = _card_base(21)
    band = pattern_mask(W - 80, 110, 70)
    bm = Image.new("L", CARD, 0)
    bm.paste(band, (40, H - 160))
    _emboss(img, bm, 22, 2)
    lh = _logo_ink(img, W / 2 - 230, 120, 460)
    d = ImageDraw.Draw(img)
    A._spaced(d, (W / 2, 120 + lh + 70), "DISTINCTION OFFICIELLE", A._f(A.CINZEL, 34, "Bold"), fill=A.VIO, spacing=.3)
    A._spaced(d, (W / 2, 120 + lh + 112), "LA RÉFÉRENCE DE LA MUSIQUE OUEST-AFRICAINE", A._f(A.SANS, 17), fill=SUB, spacing=.2)
    return img


def card_code(info: dict) -> Image.Image:
    """Carte de collection au code-barres : numéro, artiste, classement, mois."""
    W, H = CARD
    img = _card_base(23)
    d = ImageDraw.Draw(img)
    _logo_ink(img, 70, 70, 170)
    num = f"N° {info['number']:04d}" if info.get("number") else "N° —"
    A._spaced(d, (W - 70, 120), "DISTINCTION", A._f(A.CINZEL, 22, "Bold"), fill=A.VIO, spacing=.3, anchor="r")
    A._spaced(d, (W - 70, 200), num, A._f(A.CINZEL, 74, "Bold"), fill=INK, spacing=.06, anchor="r")
    name = info["artist"].upper()
    A._spaced(d, (70, 330), name, A._f(A.CINZEL, A._fit(name, A.CINZEL, 64, W - 140, "Bold", .03), "Bold"), fill=INK, spacing=.03, anchor="l")
    line = f"N°{info['rank']} · {info['chart'].upper()} · {info['period'].upper()}"
    A._spaced(d, (70, 380), line, A._f(A.SANS, A._fit(line, A.SANS, 22, W - 140, spacing=.08)), fill=A.VIO, spacing=.08, anchor="l")
    bc = A.barcode(code(info["number"], info["period_key"]).replace(" · ", ""), W - 140, 110, INK)
    img.paste(bc, (70, 430), bc)
    A._spaced(d, (W / 2, 590), code(info["number"], info["period_key"]), A._f(A.SANS, 20), fill=SUB, spacing=.3)
    return img


def _qr(url: str, px: int) -> Image.Image | None:
    try:
        import io
        import segno
        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="png", scale=10, border=1, dark="#0e1228", light="#ffffff")
        return Image.open(io.BytesIO(buf.getvalue())).convert("RGB").resize((px, px), Image.NEAREST)
    except Exception:  # noqa: BLE001
        return None


def card_qr(info: dict) -> Image.Image:
    """Carte de vérification : photo de l'artiste en cercle (anneau de métal), QR code vers la page officielle."""
    W, H = CARD
    img = _card_base(25)
    d = ImageDraw.Draw(img)
    r = 190
    cx, cy = 70 + r, H / 2 + 10
    ring = Image.new("L", CARD, 0)
    ImageDraw.Draw(ring).ellipse([cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16], fill=255)
    ImageDraw.Draw(ring).ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    _emboss(img, ring, 27, 2)
    pic, _m = _portrait(info["photo_url"], 2 * r, 2 * r, info.get("mask"))
    if pic is not None:
        circle = Image.new("L", (2 * r, 2 * r), 0)
        ImageDraw.Draw(circle).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
        img.paste(pic, (int(cx - r), int(cy - r)), circle)
    x = cx + r + 60
    A._spaced(d, (x, 110), "VÉRIFIER CETTE DISTINCTION", A._f(A.CINZEL, A._fit("VÉRIFIER CETTE DISTINCTION", A.CINZEL, 22, W - x - 60, "Bold", .2), "Bold"),
              fill=A.VIO, spacing=.2, anchor="l")
    q = _qr(info.get("verify") or "https://www.cauricharts.com", 250)
    if q:
        img.paste(q, (int(x), 140))
    A._spaced(d, (x, 440), info["artist"].upper(), A._f(A.CINZEL, A._fit(info["artist"].upper(), A.CINZEL, 40, W - x - 60, "Bold", .03), "Bold"), fill=INK, spacing=.03, anchor="l")
    num = f"DISTINCTION N° {info['number']:04d}" if info.get("number") else "DISTINCTION OFFICIELLE"
    A._spaced(d, (x, 485), num, A._f(A.SANS, 20), fill=INK, spacing=.15, anchor="l")
    if info.get("verify"):
        u = info["verify"].replace("https://", "")
        A._spaced(d, (x, 525), u, A._f(A.SANS, A._fit(u, A.SANS, 18, W - x - 60)), fill=SUB, anchor="l")
    return img


# ------------------------------------------------------------------ photo de l'ensemble (coffret sur une table claire)
def _place(canvas, im, center, width, angle, shadow=True):
    w = int(width)
    h = int(im.height * w / im.width)
    pic = im.convert("RGBA").resize((w, h), Image.LANCZOS).rotate(angle, expand=True, resample=Image.BICUBIC)
    x, y = int(center[0] - pic.width / 2), int(center[1] - pic.height / 2)
    if shadow:
        sh = pic.getchannel("A").filter(ImageFilter.GaussianBlur(max(6, w // 40))).point(lambda v: int(v * .45))
        canvas.paste((60, 64, 90), (x + w // 60, y + w // 35), sh)
    canvas.paste(pic, (x, y), pic)


def ensemble(info: dict, objects: tuple = (), size=(2400, 1800)) -> Image.Image:
    """Tout le kit posé sur une table de marbre blanc : certificat, enveloppe, cartes, carte de collection,
    plaque et bloc. objects : (plaque, bloc) déjà rendus (facultatif)."""
    W, H = size
    img = Image.new("RGB", size, (238, 239, 244))
    veins = Image.new("L", size, 0)
    vd = ImageDraw.Draw(veins)
    rnd = random.Random(info.get("number") or 1)
    for _ in range(18):
        x0, y0 = rnd.uniform(-200, W), rnd.uniform(0, H)
        pts = [(x0, y0)]
        for _k in range(9):
            x0 += rnd.uniform(90, 260)
            y0 += rnd.uniform(-60, 60)
            pts.append((x0, y0))
        vd.line(pts, fill=rnd.randint(30, 70), width=rnd.choice((2, 3, 4)))
    img.paste((190, 194, 212), (0, 0), veins.filter(ImageFilter.GaussianBlur(3)))
    light = Image.radial_gradient("L").resize((int(W * 1.4), int(H * 1.4))).point(lambda v: int((255 - v) * .5))
    img.paste((255, 255, 255), (int(-W * .2), int(-H * .3)), light)
    if objects:
        _place(img, objects[0], (W * .16, H * .42), W * .27, 4)          # plaque
        _place(img, objects[1], (W * .86, H * .40), W * .26, -3)         # bloc
    _place(img, enveloppe(info), (W * .50, H * .80), W * .44, -2)
    _place(img, certificat(info), (W * .47, H * .38), W * .30, -4)
    _place(img, render("carte", info), (W * .70, H * .55), W * .13, 8)
    _place(img, card_qr(info), (W * .25, H * .82), W * .22, 6)
    _place(img, card_code(info), (W * .80, H * .82), W * .20, -7)
    _place(img, card_brand(info), (W * .66, H * .18), W * .18, 3)
    return img
