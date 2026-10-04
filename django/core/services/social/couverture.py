"""Vingt couvertures de magazine (Cauri Hebdo, couvertures de carrousel) dans la charte Cauri : le blanc domine,
bleu ciel en verre, touches de violet verre et polymère. L'artiste est détouré (rembg) et posé comme une photo de
studio, devant le titre du magazine ; sans détourage, les gabarits « photo entière » prennent le relais.

Contenu m : {mast, edition, issue, date, kicker, headline, deck, lines: [(rang, artiste, titre)], photo, rank, seed}
  Tous les textes viennent des données réelles (classement de la semaine) ; rien n'est inventé.
"""
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from core.services.social import image as PI
from core.services.social.gabarits import (ABRIL, B, CINZEL, D, INK, ITAL, PALETTES, S, SERIF, SKY, VIOLET, Canvas,
                                           _lines, _rip)


@lru_cache(maxsize=16)
def cutout(url: str):
    """Photo de l'artiste détourée (RGBA recadrée sur le sujet) ou None (pas de photo, pas de rembg)."""
    src = PI.photo(url) if url else None
    if src is None:
        return None
    try:
        from core.services.social import une
        if not une.available():
            return None
        mask = une._mask(src)
    except Exception:  # noqa: BLE001
        return None
    box = mask.point(lambda v: 255 if v > 40 else 0).getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) < src.width * src.height * 0.08:
        return None
    im = src.convert("RGBA")
    im.putalpha(mask)
    return im.crop(box)


def _place(c: Canvas, sub: Image.Image, cx, bottom, height, shadow=True, gray=False, max_w=None):
    """Pose le sujet détouré : hauteur visée (px de base), centré sur cx, coupé en bas à `bottom`."""
    r = height / (sub.height / PI.SCALE)
    if max_w and sub.width / PI.SCALE * r > max_w:
        r = max_w / (sub.width / PI.SCALE)
    w, h = c.s(sub.width / PI.SCALE * r), c.s(sub.height / PI.SCALE * r)
    im = sub.resize((w, h), Image.LANCZOS)
    if gray:
        a = im.getchannel("A")
        im = ImageOps.grayscale(im.convert("RGB")).convert("RGBA")
        im.putalpha(a)
    x, y = c.s(cx) - w // 2, c.s(bottom) - h
    if shadow:
        sh = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
        blob = Image.new("RGBA", im.size, (30, 24, 70, 0))
        blob.putalpha(im.getchannel("A").point(lambda v: int(v * 0.32)))
        sh.alpha_composite(blob, (x + c.s(18), y + c.s(22)))
        c.img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(c.s(26))))
    c.img.alpha_composite(im, (x, y))
    c.d = ImageDraw.Draw(c.img)
    return x / PI.SCALE, y / PI.SCALE, (x + w) / PI.SCALE, (y + h) / PI.SCALE


def _barcode(c: Canvas, x, y, m, w=170, h=70, color=INK):
    rnd = random.Random(m["seed"] + "-code")
    c.rect(x - 12, y - 12, x + w + 12, y + h + 44, (255, 255, 255, 240))
    bx = x
    while bx < x + w - 4:
        bw = rnd.choice((1.5, 1.5, 3, 4.5))
        c.rect(bx, y, bx + bw, y + h, (*color, 255))
        bx += bw + rnd.choice((2, 3, 4))
    c.text(x, y + h + 28, f"{m['issue']} · {m['year']}", S, 15, (*color, 255))


def _mast(c: Canvas, m, y, color, name=D, px=560, x=None, anchor="ls", w=None):
    w = w or c.W - 2 * c.pad + 20
    px = c.fit(m["mast"], name, px, w)
    c.text(c.pad - 8 if x is None else x, y + px * 0.86, m["mast"], name, px, color, anchor)
    return px


def _issue_line(c: Canvas, m, y, color=(*INK, 255), center=False):
    t = f"{m['edition']} · {m['issue']} · {m['date']}".upper()
    if center:
        c.center(y, t, B, 18, color, spacing=2)
    else:
        c.text(c.pad, y, t, B, 18, color, spacing=2)


def _lines_block(c: Canvas, m, x, y, w, color=(*INK, 255), acc=None, n=3, px=26, glass=True):
    acc = acc or (*VIOLET, 255)
    rows = m["lines"][:n]
    if glass and rows:
        c.glass((x - 22, y - px * 1.3, x + w + 22, y + px * 3.6 * len(rows) - px * 0.8), 18, veil=205, blur=22)
    for rank, artist, title in rows:
        c.text(x, y, f"N°{rank}", D, px + 8, acc)
        c.text(x, y + px * 1.25, c_fit(c, artist.upper(), B, px, w), B, px, color)
        c.text(x, y + px * 2.3, c_fit(c, f"« {title} »", S, px - 4, w), S, px - 4, color)
        y += px * 3.6
    return y


def c_fit(c: Canvas, text, name, px, w):
    if c.width(text, name, px) <= w:
        return text
    while text and c.width(text + "…", name, px) > w:
        text = text[:-1]
    return text.rstrip() + "…"


def _head(c: Canvas, m, x, y, w, color=(*INK, 255), acc=None, px=150, name=D, anchor="ls"):
    """Rubrique, nom en très gros, chapô ; renvoie le y du bas."""
    acc = acc or (*VIOLET, 255)
    c.text(x, y, m["kicker"].upper(), B, 24, acc, anchor, spacing=3) if anchor == "ls" else c.center(y, m["kicker"].upper(), B, 24, acc, 3)
    px = c.fit(m["headline"].upper(), name, px, w)
    yy = y + 14 + px * 0.88
    if anchor == "ls":
        c.text(x, yy, m["headline"].upper(), name, px, color)
    else:
        c.center(yy, m["headline"].upper(), name, px, color)
    return _lines(c, x, yy + 52, m["deck"], S, 28, color, w, 2, anchor=anchor)


def _badge(c: Canvas, m, cx, cy, r=86, color=VIOLET):
    if not m.get("rank"):
        return  # pastille réservée à une couverture consacrée à un titre classé
    c.sphere(cx, cy, r, color)
    c.text(cx, cy + r * 0.16, f"N°{m['rank']}", D, r * 0.62, (255, 255, 255, 255), "ms")


def _no_subject(c: Canvas, m, p, box):
    """Sans détourage : photo entière dans un cadre de verre (ou billes si pas de photo)."""
    x1, y1, x2, y2 = box
    c.glass((x1 - 14, y1 - 14, x2 + 14, y2 + 14), 30, blur=18)
    if not (m.get("photo") and c.photo(m["photo"], box, r=22)):
        c.sphere((x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) * 0.3, p["accent"])


# ── Les 20 couvertures ──────────────────────────────────────────────────────────────────────────────────────────

def c01_classique(c, m, p, sub):
    """Titre CAURI en tête, l'artiste devant, accroches à droite."""
    c.soft(m["seed"], 0.9)
    _issue_line(c, m, c.y0)
    px = _mast(c, m, c.y0 + 12, (*INK, 255))
    if sub:
        _place(c, sub, c.W * 0.46, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.45)
    else:
        _no_subject(c, m, p, (c.pad, c.y0 + px + 40, c.W * 0.66, c.H * 0.7))
    _lines_block(c, m, c.W - c.pad - 230, c.y0 + px + 120, 230)
    c.glass((c.pad - 30, c.y1 - 330, c.W * 0.7, c.y1 + 20), 24, veil=200, blur=24)
    _head(c, m, c.pad, c.y1 - 260, c.W * 0.7 - c.pad - 20, px=130)
    _barcode(c, c.W - c.pad - 170, c.y1 - 110, m)


def c02_halo(c, m, p, sub):
    """Halo de verre bleu ciel derrière l'artiste, titre violet."""
    c.soft(m["seed"], 1.1)
    _issue_line(c, m, c.y0, center=True)
    px = _mast(c, m, c.y0 + 12, (*p["accent"], 255))
    r = c.W * 0.38
    cy = c.H * 0.56
    c.glass((c.W / 2 - r, cy - r, c.W / 2 + r, cy + r), r, veil=120, tint_a=70)
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.5)
    else:
        _no_subject(c, m, p, (c.W / 2 - r * 0.8, cy - r * 0.8, c.W / 2 + r * 0.8, cy + r * 0.8))
    c.rect(0, c.y1 - 250, c.W, c.H, (255, 255, 255, 215))
    _head(c, m, c.W / 2, c.y1 - 190, c.W - 2 * c.pad, anchor="ms", px=120)
    _badge(c, m, c.W - c.pad - 60, c.y0 + px + 80, 70, p["accent"])


def c03_vertical(c, m, p, sub):
    """Titre vertical le long du bord gauche, artiste à droite."""
    c.soft(m["seed"], 0.8)
    band = Image.new("RGBA", (c.s(c.H - c.top - c.bottom), c.s(260)), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    px = 250
    while px > 100 and bd.textlength(m["mast"], font=c.font(D, px)) > band.width * 0.92:
        px -= 6
    bd.text((c.s(20), c.s(230)), m["mast"], font=c.font(D, px), fill=(*INK, 255), anchor="ls")
    band = band.rotate(90, expand=True)
    c.img.alpha_composite(band, (c.s(10), c.s(c.top)))
    c.d = ImageDraw.Draw(c.img)
    if sub:
        _place(c, sub, c.W * 0.6, c.H - c.bottom, (c.H - c.bottom - c.top) * 0.86, max_w=c.W * 0.78)
    else:
        _no_subject(c, m, p, (300, c.y0 + 80, c.W - c.pad, c.H * 0.68))
    _issue_line(c, m, c.y0)
    c.glass((290, c.y1 - 300, c.W - c.pad + 20, c.y1 + 20), 24, veil=205)
    _head(c, m, 320, c.y1 - 230, c.W - c.pad - 330, px=120)
    _lines_block(c, m, c.W - c.pad - 200, c.y0 + 90, 200, n=2, px=22)


def c04_rang(c, m, p, sub):
    """Grand chiffre du rang en violet derrière l'artiste."""
    c.soft(m["seed"], 0.7)
    _issue_line(c, m, c.y0)
    c.text(c.pad, c.y0 + 80, m["mast"], D, 90, (*INK, 255))
    rk = str(m["rank"])
    rpx = c.fit(rk, D, 1100, c.W * 0.9)
    c.text(c.W / 2, c.H * 0.78, rk, D, rpx, (*p["accent"], 235), "ms")
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, (c.H - c.bottom - c.y0) * 0.8)
    else:
        _no_subject(c, m, p, (c.pad + 80, c.y0 + 180, c.W - c.pad - 80, c.H * 0.72))
    c.rect(0, c.y1 - 220, c.W, c.H, (255, 255, 255, 225))
    _head(c, m, c.pad, c.y1 - 160, c.W - 2 * c.pad - 220, px=110)
    _barcode(c, c.W - c.pad - 170, c.y1 - 110, m)


def c05_cadre(c, m, p, sub):
    """Cadre violet épais façon grand hebdomadaire, titre blanc dans le bandeau."""
    c.soft(m["seed"], 1.0)
    bw = 34
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom - bw, (c.H - c.bottom - c.top) * 0.78)
    else:
        _no_subject(c, m, p, (c.pad + 40, c.y0 + 220, c.W - c.pad - 40, c.H * 0.7))
    for box in ((0, c.top, c.W, c.top + bw), (0, c.H - c.bottom - bw, c.W, c.H - c.bottom), (0, c.top, bw, c.H - c.bottom),
                (c.W - bw, c.top, c.W, c.H - c.bottom)):
        c.rect(*box, (*p["accent"], 255))
    c.rect(bw, c.top + bw, c.W - bw, c.top + bw + 190, (*p["accent"], 255))
    c.center(c.top + bw + 160, m["mast"], D, c.fit(m["mast"], D, 170, c.W - 200), (255, 255, 255, 255))
    _issue_line(c, m, c.top + bw + 225, center=True)
    c.glass((bw + 30, c.y1 - 300, c.W - bw - 30, c.y1 - 30), 20, veil=210)
    _head(c, m, c.W / 2, c.y1 - 235, c.W - 2 * bw - 100, anchor="ms", px=110)


def c06_mode(c, m, p, sub):
    """Magazine de mode : capitales romaines fines, beaucoup d'air, accroches discrètes."""
    c.img = Image.new("RGBA", c.img.size, (250, 250, 252, 255))
    c.d = ImageDraw.Draw(c.img)
    px = c.fit(m["mast"], CINZEL, 260, c.W - 2 * c.pad)
    c.center(c.y0 + px * 0.85, m["mast"], CINZEL, px, (*INK, 255))
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.4, shadow=False)
    else:
        _no_subject(c, m, p, (c.pad + 60, c.y0 + px + 40, c.W - c.pad - 60, c.H * 0.74))
    _issue_line(c, m, c.y0 + px + 34, center=True)
    c.glass((c.pad - 24, c.H * 0.46 - 40, c.W * 0.4, c.H * 0.46 + 330), 18, veil=210, blur=22)
    c.glass((c.W - c.pad - 330, c.H * 0.46 - 40, c.W - c.pad + 24, c.H * 0.46 + 250), 18, veil=210, blur=22)
    c.text(c.pad, c.H * 0.46, m["kicker"].upper(), B, 18, (*p["accent"], 255), spacing=3)
    tpx = c.fit(m["headline"], ITAL, 110, c.W * 0.4)
    c.text(c.pad, c.H * 0.46 + tpx * 0.95, m["headline"], ITAL, tpx, (*INK, 255))
    _lines(c, c.pad, c.H * 0.46 + tpx + 60, m["deck"], SERIF, 26, (*INK, 255), c.W * 0.32, 4)
    y = c.H * 0.46
    for rank, artist, title in m["lines"][:3]:
        c.text(c.W - c.pad, y, f"N°{rank}  {artist.upper()}", B, 20, (*INK, 255), "rs")
        c.text(c.W - c.pad, y + 30, c_fit(c, title, SERIF, 22, 300), SERIF, 22, (*INK, 200), "rs")
        y += 90


def c07_noir_blanc(c, m, p, sub):
    """Portrait noir et blanc sur blanc, accents violets."""
    c.img = Image.new("RGBA", c.img.size, (255, 255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    _issue_line(c, m, c.y0)
    px = _mast(c, m, c.y0 + 12, (*p["accent"], 255))
    if sub:
        _place(c, sub, c.W * 0.55, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.4, gray=True)
    else:
        _no_subject(c, m, p, (c.pad, c.y0 + px + 40, c.W - c.pad, c.H * 0.7))
    c.rect(c.pad, c.y1 - 290, c.pad + 12, c.y1 - 40, (*p["accent"], 255))
    _head(c, m, c.pad + 40, c.y1 - 240, c.W * 0.62, px=120)
    _badge(c, m, c.W - c.pad - 80, c.y1 - 150, 80, p["accent"])


def c08_nom_geant(c, m, p, sub):
    """Le nom de l'artiste en contour bleu ciel géant derrière lui."""
    c.soft(m["seed"], 0.6)
    name = m["headline"].upper()
    npx = c.fit(name, D, 520, c.W - 40)
    layer = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for k, yy in enumerate((c.H * 0.42, c.H * 0.42 + npx * 0.95)):
        ld.text((c.s(c.W / 2), c.s(yy)), name, font=c.font(D, npx), fill=(*SKY, 255) if k else (*SKY, 255), anchor="ms",
                stroke_width=c.s(3), stroke_fill=(*SKY, 255))
        if k == 0:
            ld.text((c.s(c.W / 2), c.s(yy)), name, font=c.font(D, npx), fill=(0, 0, 0, 0), anchor="ms")
    c.img.alpha_composite(layer)
    c.d = ImageDraw.Draw(c.img)
    c.text(c.pad, c.y0 + 70, m["mast"], D, 80, (*INK, 255))
    c.text(c.W - c.pad, c.y0 + 30, f"{m['edition']} · {m['issue']}".upper(), B, 18, (*INK, 255), "rs")
    c.text(c.W - c.pad, c.y0 + 58, m["date"].upper(), B, 18, (*INK, 160), "rs")
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, (c.H - c.bottom - c.y0) * 0.82)
    else:
        _no_subject(c, m, p, (c.pad + 80, c.y0 + 160, c.W - c.pad - 80, c.H * 0.72))
    c.glass((c.pad - 20, c.y1 - 170, c.W - c.pad + 20, c.y1 + 20), 22, veil=210)
    c.text(c.pad, c.y1 - 110, m["kicker"].upper(), B, 22, (*p["accent"], 255), spacing=3)
    _lines(c, c.pad, c.y1 - 60, m["deck"], B, 28, (*INK, 255), c.W - 2 * c.pad, 1)


def c09_bandeau_verre(c, m, p, sub):
    """Fond bleu ciel clair, titre dans un bandeau de verre devant le haut de la photo."""
    c.gradient((236, 244, 255), (255, 255, 255), 90)
    c.blobs([SKY, VIOLET], m["seed"], 3, 200, 60)
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, (c.H - c.bottom - c.y0) * 0.88)
    else:
        _no_subject(c, m, p, (c.pad, c.y0 + 240, c.W - c.pad, c.H * 0.72))
    c.glass((0, c.y0 - 20, c.W, c.y0 + 240), 0, veil=150, blur=30)
    _mast(c, m, c.y0, (*INK, 255), px=200)
    _issue_line(c, m, c.y0 + 225)
    c.rect(0, c.y1 - 240, c.W, c.H, (255, 255, 255, 220))
    _head(c, m, c.pad, c.y1 - 180, c.W - 2 * c.pad - 220, px=110)
    _barcode(c, c.W - c.pad - 170, c.y1 - 110, m)


def c10_projecteur(c, m, p, sub):
    """Halo de lumière bleu ciel derrière l'artiste, comme un projecteur de scène."""
    c.img = Image.new("RGBA", c.img.size, (255, 255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    glow = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i, a in ((1.0, 70), (0.7, 90), (0.45, 110)):
        r = c.W * 0.55 * i
        gd.ellipse([c.s(c.W / 2 - r), c.s(c.H * 0.5 - r), c.s(c.W / 2 + r), c.s(c.H * 0.5 + r)], fill=(*SKY, a))
    c.img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(c.s(120))))
    c.d = ImageDraw.Draw(c.img)
    _issue_line(c, m, c.y0, center=True)
    px = _mast(c, m, c.y0 + 12, (*INK, 255))
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.5)
    else:
        _no_subject(c, m, p, (c.pad + 60, c.y0 + px + 40, c.W - c.pad - 60, c.H * 0.72))
    c.glass((c.pad - 20, c.y1 - 280, c.W - c.pad + 20, c.y1 + 10), 26, veil=200)
    _head(c, m, c.W / 2, c.y1 - 215, c.W - 2 * c.pad - 40, anchor="ms", px=110)


def c11_billes(c, m, p, sub):
    """Billes de polymère violettes et bleu ciel qui flottent autour de l'artiste, pastille N°."""
    c.soft(m["seed"], 0.7)
    rnd = random.Random(m["seed"] + "b")
    _issue_line(c, m, c.y0)
    px = _mast(c, m, c.y0 + 12, (*INK, 255))
    for _ in range(5):
        c.sphere(rnd.choice((rnd.uniform(60, 220), rnd.uniform(c.W - 220, c.W - 60))), rnd.uniform(c.y0 + px + 60, c.H * 0.7),
                 rnd.uniform(30, 80), rnd.choice((p["accent"], SKY)))
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.45)
    else:
        _no_subject(c, m, p, (c.pad + 60, c.y0 + px + 40, c.W - c.pad - 60, c.H * 0.7))
    _badge(c, m, c.W - c.pad - 90, c.y0 + px + 130, 96, p["accent"])
    c.reseau("coeur", c.W - c.pad - 150, c.y1 - 420, 110, -10)
    c.reseau("like", c.pad - 10, c.y0 + px + 200, 100, 10)
    c.glass((c.pad - 30, c.y1 - 280, c.W * 0.72, c.y1 + 20), 24, veil=205)
    _head(c, m, c.pad, c.y1 - 210, c.W * 0.72 - c.pad - 20, px=110)


def c12_papier(c, m, p, sub):
    """Papier déchiré en bas, accroches imprimées dessus."""
    c.soft(m["seed"], 1.2)
    _issue_line(c, m, c.y0)
    px = _mast(c, m, c.y0 + 12, (*p["accent"], 255))
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.45)
    else:
        _no_subject(c, m, p, (c.pad, c.y0 + px + 40, c.W - c.pad, c.H * 0.7))
    sheet = _rip("bas", c.s(c.W))
    edge = c.y1 - 360
    if sheet.height < c.s(c.H - edge):
        sheet = sheet.resize((sheet.width, c.s(c.H - edge)), Image.LANCZOS)
    c.img.alpha_composite(sheet, (0, c.s(edge)))
    c.d = ImageDraw.Draw(c.img)
    _head(c, m, c.pad, edge + 110, c.W * 0.62, px=110)
    _lines_block(c, m, c.W - c.pad - 220, edge + 100, 220, n=2, px=22)


def c13_diagonale(c, m, p, sub):
    """Bandeau violet en diagonale qui barre le bas de la couverture."""
    c.soft(m["seed"], 0.9)
    _issue_line(c, m, c.y0)
    px = _mast(c, m, c.y0 + 12, (*INK, 255))
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.45)
    else:
        _no_subject(c, m, p, (c.pad, c.y0 + px + 40, c.W - c.pad, c.H * 0.7))
    band = Image.new("RGBA", (c.s(c.W * 1.4), c.s(120)), (*p["accent"], 255))
    bd = ImageDraw.Draw(band)
    t = f"   {m['kicker'].upper()}  •  {m['headline'].upper()}  •  « {m['title']} »" * 3 if m.get("title") else         f"   {m['kicker'].upper()}  •  {m['headline'].upper()}" * 4
    bd.text((c.s(20), c.s(60)), t, font=c.font(D, 58), fill=(255, 255, 255, 255), anchor="lm")
    band = band.rotate(7, Image.BICUBIC, expand=True)
    c.img.alpha_composite(band, (c.s(c.W / 2) - band.width // 2, c.s(c.H * 0.70) - band.height // 2))
    c.d = ImageDraw.Draw(c.img)
    c.glass((c.pad - 20, c.y1 - 180, c.W - c.pad + 20, c.y1 + 20), 22, veil=210)
    _lines(c, c.pad, c.y1 - 110, m["deck"], B, 28, (*INK, 255), c.W - 2 * c.pad - 210, 2)
    _barcode(c, c.W - c.pad - 150, c.y1 - 120, m, 150, 60)


def c14_colonne(c, m, p, sub):
    """Colonne éditoriale à gauche (le Top en chiffres), artiste à droite."""
    c.soft(m["seed"], 0.6)
    c.glass((0, c.top, c.W * 0.38, c.H - c.bottom), 0, veil=180, tint_a=55)
    if sub:
        _place(c, sub, c.W * 0.68, c.H - c.bottom, (c.H - c.bottom - c.y0) * 0.86, max_w=c.W * 0.7)
    else:
        _no_subject(c, m, p, (c.W * 0.42, c.y0 + 180, c.W - c.pad, c.H * 0.7))
    c.text(c.pad - 20, c.y0 + 100, m["mast"], D, c.fit(m["mast"], D, 120, c.W * 0.32), (*INK, 255))
    c.text(c.pad - 20, c.y0 + 140, f"{m['edition']} · {m['issue']}".upper(), B, 16, (*INK, 255), spacing=2)
    c.text(c.pad - 20, c.y0 + 166, m["date"].upper(), S, 15, (*INK, 170))
    _lines_block(c, m, c.pad - 20, c.y0 + 260, c.W * 0.3, n=4, px=24)
    c.rect(c.W * 0.38, c.y1 - 210, c.W, c.H, (255, 255, 255, 215))
    _head(c, m, c.W * 0.38 + 40, c.y1 - 150, c.W * 0.62 - c.pad - 40, px=100)


def c15_numero(c, m, p, sub):
    """Le numéro de l'édition en énorme chiffre de verre bleu ciel."""
    c.soft(m["seed"], 0.6)
    num = "".join(ch for ch in m["issue"] if ch.isdigit()) or str(m["rank"])
    npx = c.fit(num, D, 1000, c.W - 60)
    layer = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((c.s(c.W / 2), c.s(c.H * 0.74)), num, font=c.font(D, npx), fill=(*SKY, 110), anchor="ms")
    c.img.alpha_composite(layer)
    c.d = ImageDraw.Draw(c.img)
    _issue_line(c, m, c.y0)
    px = _mast(c, m, c.y0 + 12, (*INK, 255), px=240)
    if sub:
        _place(c, sub, c.W / 2, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.5)
    else:
        _no_subject(c, m, p, (c.pad + 60, c.y0 + px + 40, c.W - c.pad - 60, c.H * 0.7))
    c.rect(0, c.y1 - 230, c.W, c.H, (255, 255, 255, 220))
    _head(c, m, c.pad, c.y1 - 170, c.W - 2 * c.pad - 220, px=110)
    _barcode(c, c.W - c.pad - 170, c.y1 - 110, m)


def c16_podium(c, m, p, sub):
    """Panneau de verre avec le podium à gauche, artiste qui déborde à droite."""
    c.soft(m["seed"], 1.0)
    _issue_line(c, m, c.y0)
    px = _mast(c, m, c.y0 + 12, (*INK, 255))
    n = min(3, len(m["lines"]))
    c.glass((c.pad - 30, c.y0 + px + 60, c.W * 0.5, c.y0 + px + 200 + n * 26 * 3.6), 30, veil=185)
    c.text(c.pad, c.y0 + px + 120, "LE PODIUM", B, 22, (*p["accent"], 255), spacing=4)
    _lines_block(c, m, c.pad, c.y0 + px + 190, c.W * 0.5 - c.pad - 50, n=3, px=26, glass=False)
    if sub:
        _place(c, sub, c.W * 0.66, c.H - c.bottom, c.H - c.bottom - c.y0 - px * 0.45, max_w=c.W * 0.72)
    else:
        _no_subject(c, m, p, (c.W * 0.52, c.y0 + px + 60, c.W - c.pad, c.H * 0.7))
    c.rect(0, c.y1 - 230, c.W, c.H, (255, 255, 255, 220))
    _head(c, m, c.pad, c.y1 - 170, c.W - 2 * c.pad, px=110)


def c17_medaillon(c, m, p, sub):
    """Portrait en médaillon rond cerclé de violet (photo entière : marche sans détourage)."""
    c.soft(m["seed"], 1.0)
    _issue_line(c, m, c.y0, center=True)
    px = c.fit(m["mast"], ABRIL, 230, c.W - 2 * c.pad)
    c.center(c.y0 + 20 + px * 0.9, m["mast"], ABRIL, px, (*INK, 255))
    r = c.W * 0.33
    cy = c.y0 + px + 60 + r
    c.ellipse(c.W / 2 - r - 24, cy - r - 24, c.W / 2 + r + 24, cy + r + 24, (*p["accent"], 255))
    c.ellipse(c.W / 2 - r - 10, cy - r - 10, c.W / 2 + r + 10, cy + r + 10, (255, 255, 255, 255))
    if not (m.get("photo") and c.photo(m["photo"], (c.W / 2 - r, cy - r, c.W / 2 + r, cy + r), "circle")):
        c.sphere(c.W / 2, cy, r * 0.7, p["accent"])
    _badge(c, m, c.W / 2 + r * 0.78, cy - r * 0.78, 70, SKY)
    _head(c, m, c.W / 2, cy + r + 110, c.W - 2 * c.pad, anchor="ms", px=110)


def c18_plein_cadre(c, m, p, sub):
    """Photo entière plein cadre, voile blanc en bas, titre blanc en haut (marche sans détourage)."""
    if not (m.get("photo") and c.photo(m["photo"], (0, 0, c.W, c.H))):
        c.soft(m["seed"], 2.0)
    c.img.alpha_composite(_fade(c, (255, 255, 255), 0.55, 1.0))
    top = _fade(c, (0, 0, 0), 0.0, 0.25, True)
    c.img.alpha_composite(top)
    c.d = ImageDraw.Draw(c.img)
    _issue_line(c, m, c.y0, (255, 255, 255, 255))
    _mast(c, m, c.y0 + 12, (255, 255, 255, 255))
    _head(c, m, c.pad, c.y1 - 220, c.W - 2 * c.pad - 220, px=120)
    _barcode(c, c.W - c.pad - 170, c.y1 - 110, m)


def _fade(c: Canvas, rgb, y_from, y_to, reverse=False):
    """Voile de couleur qui monte (ou descend) entre deux hauteurs relatives."""
    w, h = c.img.size
    a = np.zeros((h, 1), np.float32)
    y1, y2 = int(h * y_from), int(h * y_to)
    ramp = np.linspace(0, 1, max(1, y2 - y1), dtype=np.float32)
    a[y1:y2, 0] = ramp[::-1] * 0.85 if reverse else ramp
    if not reverse:
        a[y2:, 0] = 1
    alpha = (np.repeat(a, w, axis=1) * (150 if reverse else 245)).astype(np.uint8)
    layer = Image.new("RGBA", (w, h), (*rgb, 0))
    layer.putalpha(Image.fromarray(alpha, "L"))
    return layer


def c19_journal(c, m, p, sub):
    """Cauri Hebdo façon journal : titre à l'ancienne, gros titre serif, photo au centre."""
    c.img = Image.new("RGBA", c.img.size, (252, 252, 250, 255))
    c.d = ImageDraw.Draw(c.img)
    px = c.fit(m["mast"] + " " + m["edition"].upper(), CINZEL, 120, c.W - 2 * c.pad)
    c.center(c.y0 + px * 0.9, m["mast"] + " " + m["edition"].upper(), CINZEL, px, (*INK, 255))
    y = c.y0 + px + 20
    c.line([(c.pad, y), (c.W - c.pad, y)], (*INK, 255), 4)
    c.text(c.pad, y + 34, m["date"].upper(), B, 17, (*INK, 255))
    c.text(c.W - c.pad, y + 34, m["issue"].upper(), B, 17, (*p["accent"], 255), "rs")
    c.line([(c.pad, y + 50), (c.W - c.pad, y + 50)], (*INK, 255), 1)
    hp = c.fit(m["headline"], ABRIL, 150, c.W - 2 * c.pad)
    c.center(y + 70 + hp * 0.9, m["headline"], ABRIL, hp, (*INK, 255))
    yy = _lines(c, 0, y + 130 + hp, m["deck"], SERIF, 30, (*INK, 255), c.W - 2 * c.pad, 2, anchor="ms")
    box = (c.pad, yy + 10, c.W - c.pad, c.y1 - 150)
    c.glass((box[0], box[1], box[2], box[3]), 10, veil=120, tint_a=60, blur=10)
    if sub:
        cx0, cy0, cx1, cy1 = (c.s(v) for v in box)
        clip = Canvas.__new__(Canvas)
        clip.W, clip.H = (box[2] - box[0]), (box[3] - box[1])
        clip.img = Image.new("RGBA", (cx1 - cx0, cy1 - cy0), (0, 0, 0, 0))
        clip.d = ImageDraw.Draw(clip.img)
        clip.top = clip.bottom = clip.side = 0
        _place(clip, sub, clip.W / 2, clip.H, clip.H * 0.96, shadow=False)
        c.img.alpha_composite(clip.img, (cx0, cy0))
        c.d = ImageDraw.Draw(c.img)
    elif not (m.get("photo") and c.photo(m["photo"], box, r=10)):
        c.sphere((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 120, p["accent"])
    cols = m["lines"][1:4]
    cw = (c.W - 2 * c.pad) / max(1, len(cols))
    for i, (rank, artist, title) in enumerate(cols):
        x = c.pad + i * cw
        c.text(x, c.y1 - 100, f"N°{rank} · {c_fit(c, artist.upper(), B, 18, cw - 90)}", B, 18, (*INK, 255))
        c.text(x, c.y1 - 70, c_fit(c, f"« {title} »", SERIF, 20, cw - 20), SERIF, 20, (*INK, 200))
    c.line([(c.pad, c.y1 - 130), (c.W - c.pad, c.y1 - 130)], (*INK, 255), 1)
    c.text(c.pad, c.y1, "cauricharts.com", S, 18, (*INK, 160))


def c20_affiche_bas(c, m, p, sub):
    """Titre CAURI géant en bas, artiste en haut sur fond de verre bleu ciel."""
    c.gradient((226, 238, 255), (255, 255, 255), 90)
    c.blobs([VIOLET, SKY], m["seed"], 3, 180, 70)
    _issue_line(c, m, c.y0)
    if sub:
        _place(c, sub, c.W / 2, c.y1 - 220, (c.y1 - 220 - c.y0) * 0.95)
    else:
        _no_subject(c, m, p, (c.pad + 60, c.y0 + 60, c.W - c.pad - 60, c.y1 - 300))
    c.rect(0, c.y1 - 260, c.W, c.H, (255, 255, 255, 255))
    mpx = c.fit(m["mast"], D, 360, c.W - 2 * c.pad + 20)
    c.text(c.pad - 8, c.y1 - 260 + mpx * 0.86, m["mast"], D, mpx, (*p["accent"], 255))
    c.text(c.pad, c.y1 - 260 + mpx + 40, f"{m['kicker'].upper()} · {m['headline'].upper()}", B, 26, (*INK, 255), spacing=2)
    _lines(c, c.pad, c.y1 - 260 + mpx + 84, m["deck"], S, 24, (*INK, 200), c.W - 2 * c.pad, 1)


LAYOUTS = [c01_classique, c02_halo, c03_vertical, c04_rang, c05_cadre, c06_mode, c07_noir_blanc, c08_nom_geant,
           c09_bandeau_verre, c10_projecteur, c11_billes, c12_papier, c13_diagonale, c14_colonne, c15_numero,
           c16_podium, c17_medaillon, c18_plein_cadre, c19_journal, c20_affiche_bas]
NAMES = {f.__name__: f for f in LAYOUTS}


def render(m: dict, layout: str | None = None, fmt: str = "post") -> Image.Image:
    m = {"mast": "CAURI", "edition": "Hebdo", "issue": "", "date": "", "kicker": "", "headline": "", "deck": "", "title": "",
         "lines": [], "rank": 1, "year": "", **m}
    m.setdefault("seed", m["headline"] + m["issue"])
    pool = [f for f in LAYOUTS if m.get("rank") or f is not c04_rang]  # le grand chiffre du rang exige un rang
    fn = NAMES[layout or random.Random(m["seed"] + "-couverture").choice(pool).__name__]
    p = random.Random(m["seed"] + "-palette").choice(PALETTES)
    c = Canvas(fmt)
    fn(c, m, p, cutout(m["photo"]) if m.get("photo") else None)
    return c.done()
