"""Cartes de distinction Cauri Charts : une carte personnalisée pour chacun des 5 premiers de chaque classement.

  carte    : 4:5, à envoyer à l'artiste (fichier 4K) et à imprimer (format 10 × 12,5 cm à 300 ppp) ;
  coffret  : la carte posée dans un coffret noir et or, vue de dessus, pour le post « ce qu'ils ont reçu ».
"""
import random

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from core.services.social import image as PI

GOLD, GOLD_DARK, INK, CREAM = (214, 172, 82), (150, 112, 40), (12, 10, 14), (246, 238, 220)
CHARTS = {"prime": "Top 20 Afrique de l’Ouest", "buzz": "Ça monte · Afrique de l’Ouest", "fresh": "Nouveautés · Afrique de l’Ouest",
          "icon": "Top artistes · Afrique de l’Ouest", "legend": "Classiques · Afrique de l’Ouest"}
ANTON, BOLD, SANS, SERIF = (str(PI.FONT_DIR / n) for n in ("Anton-Regular.ttf", "Poppins-Bold.ttf", "Poppins-Regular.ttf", "DMSerifDisplay-Regular.ttf"))


def _f(path, px):
    return PI.font(path, int(px))


def _center(d, x, y, text, path, px, fill):
    d.text((x, y), text, font=_f(path, px), fill=fill, anchor="ms")


def _fit(text, path, px, width):
    while px > 20 and _f(path, px).getlength(text) > width:
        px -= 2
    return px


def card(rank: int, chart: str, artist: str, title: str | None, photo_url, week: str, size=(1600, 2000)) -> Image.Image:
    W, H = size
    s = W / 1600
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img, "RGBA")
    # Cadre or double, comme un certificat
    for m, w in ((40, 6), (64, 2)):
        d.rectangle([m * s, m * s, W - m * s, H - m * s], outline=GOLD, width=max(1, int(w * s)))
    # En-tête : marque et classement
    logo = PI.white_logo()
    if logo:
        lw = int(260 * s)
        lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
        img.paste(lg, ((W - lw) // 2, int(120 * s)), lg)
    _center(d, W / 2, 330 * s, CHARTS.get(chart, chart).upper(), BOLD, 34 * s, GOLD)
    # Photo ronde cerclée d'or
    ph = PI.photo(photo_url)
    r = int(330 * s)
    cx, cy = W // 2, int(760 * s)
    d.ellipse([cx - r - 14 * s, cy - r - 14 * s, cx + r + 14 * s, cy + r + 14 * s], fill=GOLD)
    if ph:
        sq = Image.new("RGB", (2 * r, 2 * r))
        PI.paste_cover(sq, ph, 2 * r, 2 * r, 0.15)
        mask = Image.new("L", (2 * r, 2 * r), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
        img.paste(sq, (cx - r, cy - r), mask)
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(40, 34, 50))
    # Rang dans une médaille sous la photo
    mr = int(120 * s)
    my = cy + r + int(40 * s)
    d.ellipse([cx - mr, my - mr, cx + mr, my + mr], fill=GOLD, outline=CREAM, width=int(5 * s))
    _center(d, cx, my + 52 * s, f"N°{rank}", ANTON, 120 * s, INK)
    # Nom, titre, semaine
    y = my + mr + int(140 * s)
    px = _fit(artist.upper(), ANTON, 150 * s, W - 260 * s)
    _center(d, W / 2, y, artist.upper(), ANTON, px, CREAM)
    if title:
        t = f"« {title} »"
        _center(d, W / 2, y + 90 * s, t, SERIF, _fit(t, SERIF, 64 * s, W - 260 * s), GOLD)
    _center(d, W / 2, H - 230 * s, week.upper(), BOLD, 30 * s, CREAM)
    d.line([(W / 2 - 220 * s, H - 190 * s), (W / 2 + 220 * s, H - 190 * s)], fill=GOLD, width=max(1, int(2 * s)))
    _center(d, W / 2, H - 140 * s, "Classement calculé sur des données réelles · cauricharts.com", SANS, 24 * s, (190, 180, 160))
    return img


def coffret(card_img: Image.Image, size=(2160, 2700), seed: str = "") -> Image.Image:
    """La carte posée dans un coffret noir doublé de satin, vue de dessus, sur une table claire."""
    W, H = size
    rnd = random.Random(seed)
    # Table : lin clair avec un léger grain
    bg = Image.new("RGB", (W, H), (226, 218, 204))
    noise = Image.effect_noise((W, H), 18).convert("L").filter(ImageFilter.GaussianBlur(1))
    bg = Image.blend(bg, Image.merge("RGB", [noise] * 3).point(lambda v: v + 120), 0.08)
    # Coffret : ombre portée, boîte noire, satin bordeaux intérieur
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
    d.rounded_rectangle([bx + 10, by + 10, bx + bw - 10, by + bh - 10], radius=22, outline=GOLD, width=4)
    # Carte légèrement inclinée, avec son ombre
    cw = int(bw * 0.70)
    c = card_img.resize((cw, int(cw * card_img.height / card_img.width)), Image.LANCZOS).convert("RGBA")
    angle = rnd.uniform(-4, 4)
    rc = c.rotate(angle, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", rc.size, (0, 0, 0, 0))
    sh.putalpha(rc.getchannel("A").point(lambda v: int(v * 0.55)).filter(ImageFilter.GaussianBlur(25)))
    px, py = (W - rc.width) // 2, by + (bh - rc.height) // 2
    bg.paste((0, 0, 0), (px + 25, py + 35), sh)
    bg.paste(rc, (px, py), rc)
    # Ruban or et étiquette sous la boîte
    d = ImageDraw.Draw(bg)
    _center(d, W / 2, by + bh + 160, "CAURI CHARTS · DISTINCTION", BOLD, 44, (90, 70, 40))
    return ImageOps.autocontrast(bg, cutoff=0.5)
