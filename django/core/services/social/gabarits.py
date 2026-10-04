"""Vingt gabarits graphiques communs à tous les posts « à texte » : vœux de début de mois, nouvel an, jours fériés,
annonces… Chaque gabarit reçoit le même contenu et le met en page à sa façon ; un post en tire un au sort (stable).

Contenu : {kicker, title, sub, date, number?, photo?, icon?, country?}
  kicker : petite rubrique (« BON DÉBUT DE MOIS ») ; title : le mot fort (« Novembre ») ; sub : une phrase ;
  date : ligne de date ; number : grand chiffre facultatif (« 01 », « 2027 ») ; photo : adresse https facultative ;
  icon : nom d'une icône 3D de resources/icones3d ; country : code pays (couleurs du drapeau).
Formats : « post » 1080 × 1350 et « story » 1080 × 1920 (zones de l'application respectées), dessinés en 4K.

Ressources : polices OFL (resources/fonts), papiers déchirés et texture (resources/papier, maquettes Freepik et
« 12 Isolated Paper Rips »), icônes 3D (resources/icones3d, Zé Moreira via Dealjumbo).
"""
import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from core.services.social import image as PI

FONTS = PI.FONT_DIR
D, B, S = "Anton-Regular.ttf", "Poppins-Bold.ttf", "Poppins-Regular.ttf"
SERIF, ITAL, CINZEL, ABRIL, BEBAS, BUNGEE, SLAB = ("DMSerifDisplay-Regular.ttf", "CormorantGaramond-Italic.ttf", "Cinzel.ttf",
                                                   "AbrilFatface-Regular.ttf", "BebasNeue-Regular.ttf", "Bungee-Regular.ttf",
                                                   "AlfaSlabOne-Regular.ttf")
VIOLET, SKY, INK, PAPER, GOLD = (139, 82, 255), (60, 170, 255), (14, 12, 24), (246, 246, 250), (232, 186, 74)
FORMATS = {"post": ((1080, 1350), {"top": 0, "bottom": 0, "side": 0}), "story": ((1080, 1920), PI.SAFE_916),
           "magazine": ((1080, 1463), {"top": 0, "bottom": 0, "side": 0})}  # page de magazine (A4 rogné, maquettes)
# Couleurs principales des drapeaux (bandes simplifiées)
FLAGS = {
    "bj": [(0, 135, 81), (252, 209, 22), (232, 17, 45)], "bf": [(239, 43, 45), (0, 158, 73), (252, 209, 22)],
    "cv": [(0, 56, 147), (255, 255, 255), (207, 32, 39)], "ci": [(247, 127, 0), (255, 255, 255), (0, 158, 96)],
    "gm": [(206, 17, 38), (12, 28, 140), (58, 119, 40)], "gh": [(206, 17, 38), (252, 209, 22), (0, 107, 63)],
    "gn": [(206, 17, 38), (252, 209, 22), (0, 148, 96)], "gw": [(206, 17, 38), (252, 209, 22), (0, 158, 73)],
    "lr": [(191, 10, 48), (255, 255, 255), (0, 40, 104)], "ml": [(20, 181, 58), (252, 209, 22), (206, 17, 38)],
    "mr": [(0, 98, 51), (255, 196, 0), (210, 16, 52)], "ne": [(224, 82, 6), (255, 255, 255), (13, 176, 43)],
    "ng": [(0, 135, 81), (255, 255, 255), (0, 135, 81)], "sl": [(30, 181, 58), (255, 255, 255), (0, 114, 198)],
    "sn": [(0, 133, 63), (253, 239, 66), (227, 27, 35)], "tg": [(0, 106, 78), (255, 206, 0), (210, 16, 52)],
}


# Palettes de la marque (blanc dominant, bleu, violet, noir ; or pour les fêtes)
PALETTES = [
    {"name": "Violet Cauri", "accent": VIOLET},
    {"name": "Violet profond", "accent": (112, 60, 230)},
    {"name": "Indigo", "accent": (92, 106, 255)},
]


class Canvas:
    """Toile en 4K ; la mise en page s'écrit en px de la base 1080."""

    def __init__(self, fmt: str, bg=PAPER):
        (self.W, self.H), safe = FORMATS[fmt]
        self.fmt = fmt
        self.top, self.bottom, self.side = safe.get("top", 0), safe.get("bottom", 0), safe.get("side", 0)
        self.img = Image.new("RGBA", (self.s(self.W), self.s(self.H)), (*bg, 255))
        self.d = ImageDraw.Draw(self.img)

    @staticmethod
    def s(v) -> int:
        return round(v * PI.SCALE)

    @property
    def pad(self) -> int:
        return max(72, self.side)

    @property
    def y0(self) -> int:  # haut utile
        return self.top + 64

    @property
    def y1(self) -> int:  # bas utile
        return self.H - self.bottom - 64

    def font(self, name, px):
        return PI.font(str(FONTS / name), self.s(px))

    def width(self, text, name, px) -> float:
        return self.d.textlength(text, font=self.font(name, px)) / PI.SCALE

    def fit(self, text, name, px, w, floor=14) -> int:
        while px > floor and self.width(text, name, px) > w:
            px -= 2
        return px

    def wrap(self, text, name, px, w, mx=3) -> list:
        words, lines, cur = text.split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if self.width(t, name, px) <= w or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = wd
        lines.append(cur)
        return lines[:mx]

    def text(self, x, y, text, name, px, fill, anchor="ls", spacing=0):
        if spacing:
            x0 = x - (self.width(text, name, px) + spacing * (len(text) - 1)) / {"l": 0, "m": 2, "r": 1}[anchor[0]] \
                if anchor[0] != "l" else x
            for ch in text:
                self.d.text((self.s(x0), self.s(y)), ch, font=self.font(name, px), fill=fill, anchor="l" + anchor[1])
                x0 += self.width(ch, name, px) + spacing
            return
        self.d.text((self.s(x), self.s(y)), text, font=self.font(name, px), fill=fill, anchor=anchor)

    def center(self, y, text, name, px, fill, spacing=0):
        self.text(self.W / 2, y, text, name, px, fill, "ms", spacing)

    def rect(self, x1, y1, x2, y2, fill=None, outline=None, width=0, r=0):
        box = [self.s(x1), self.s(y1), self.s(x2), self.s(y2)]
        if r:
            self.d.rounded_rectangle(box, self.s(r), fill=fill, outline=outline, width=self.s(width))
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=self.s(width))

    def ellipse(self, x1, y1, x2, y2, fill=None, outline=None, width=0):
        self.d.ellipse([self.s(x1), self.s(y1), self.s(x2), self.s(y2)], fill=fill, outline=outline, width=self.s(width))

    def line(self, pts, fill, width=2):
        self.d.line([(self.s(x), self.s(y)) for x, y in pts], fill=fill, width=self.s(width))

    def paste(self, im: Image.Image, x, y):
        self.img.alpha_composite(im.convert("RGBA"), (self.s(x), self.s(y)))

    def gradient(self, c1, c2, angle=90):
        """Dégradé linéaire sur toute la toile (angle en degrés, 90 = de haut en bas)."""
        w, h = self.img.size
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        a = math.radians(angle)
        t = (xx * math.cos(a) + yy * math.sin(a))
        t = (t - t.min()) / (t.max() - t.min())
        arr = np.array(c1, np.float32) * (1 - t[..., None]) + np.array(c2, np.float32) * t[..., None]
        self.img = Image.fromarray(np.dstack([arr.astype(np.uint8), np.full((h, w), 255, np.uint8)]), "RGBA")
        self.d = ImageDraw.Draw(self.img)

    def blobs(self, colors, seed, n=5, blur=140, alpha=200):
        """Taches de couleur floues (dégradé « maillé »)."""
        rnd = random.Random(seed)
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for i in range(n):
            r = rnd.uniform(0.25, 0.5) * self.W
            cx, cy = rnd.uniform(0, self.W), rnd.uniform(0, self.H)
            ld.ellipse([self.s(cx - r), self.s(cy - r), self.s(cx + r), self.s(cy + r)], fill=(*colors[i % len(colors)], alpha))
        self.img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(self.s(blur))))
        self.d = ImageDraw.Draw(self.img)

    def grain(self, amount=10, seed=1):
        rng = np.random.default_rng(seed)
        arr = np.asarray(self.img).astype(np.int16)
        noise = rng.integers(-amount, amount + 1, arr.shape[:2], dtype=np.int16)[..., None]
        arr[..., :3] = np.clip(arr[..., :3] + noise, 0, 255)
        self.img = Image.fromarray(arr.astype(np.uint8), "RGBA")
        self.d = ImageDraw.Draw(self.img)

    def shadow(self, box, r=24, blur=40, alpha=90, dy=24):
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        x1, y1, x2, y2 = box
        ImageDraw.Draw(layer).rounded_rectangle([self.s(x1), self.s(y1 + dy), self.s(x2), self.s(y2 + dy)], self.s(r),
                                                fill=(0, 0, 0, alpha))
        self.img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(self.s(blur))))
        self.d = ImageDraw.Draw(self.img)

    def logo(self, x, y, w, color=(255, 255, 255)):
        lg = _logo(color)
        if lg:
            lw = self.s(w)
            self.img.alpha_composite(lg.resize((lw, round(lg.height * lw / lg.width)), Image.LANCZOS), (self.s(x), self.s(y)))
            self.d = ImageDraw.Draw(self.img)

    def photo(self, url, box, mask: str = "rect", r=0):
        ph = PI.photo(url) if url else None
        if not ph:
            return False
        x1, y1, x2, y2 = (self.s(v) for v in box)
        part = Image.new("RGB", (x2 - x1, y2 - y1))
        PI.paste_cover(part, ph, x2 - x1, y2 - y1, 0.15)
        m = Image.new("L", part.size, 0)
        md = ImageDraw.Draw(m)
        if mask == "circle":
            md.ellipse([0, 0, part.width - 1, part.height - 1], fill=255)
        else:
            md.rounded_rectangle([0, 0, part.width - 1, part.height - 1], self.s(r), fill=255)
        self.img.paste(part, (x1, y1), m)
        self.d = ImageDraw.Draw(self.img)
        return True

    def icon(self, name, x, y, w, angle=0):
        im = _icon(name or "calendar")
        if im is None:
            return
        im = im.resize((self.s(w), round(im.height * self.s(w) / im.width)), Image.LANCZOS)
        if angle:
            im = im.rotate(angle, Image.BICUBIC, expand=True)
        self.img.alpha_composite(im, (self.s(x), self.s(y)))
        self.d = ImageDraw.Draw(self.img)

    def soft(self, seed, strength=1.0):
        """Fond blanc aéré, avec de très légères taches bleu ciel et violettes (le blanc domine)."""
        self.img = Image.new("RGBA", self.img.size, (255, 255, 255, 255))
        self.d = ImageDraw.Draw(self.img)
        self.blobs([SKY, VIOLET, (160, 210, 255)], seed, 4, 230, round(70 * strength))

    def glass(self, box, r=40, tint=SKY, veil=150, tint_a=40, blur=28):
        """Panneau de verre dépoli : fond flouté, voile blanc teinté bleu ciel, reflet en haut, liseré lumineux."""
        x1, y1, x2, y2 = box
        self.shadow(box, r, 46, 34, 26)
        g = self.img.crop((self.s(x1), self.s(y1), self.s(x2), self.s(y2))).filter(ImageFilter.GaussianBlur(self.s(blur)))
        g.alpha_composite(Image.new("RGBA", g.size, (255, 255, 255, veil)))
        g.alpha_composite(Image.new("RGBA", g.size, (*tint, tint_a)))
        hl = Image.new("L", g.size, 0)
        hd = ImageDraw.Draw(hl)
        for yy in range(int(g.height * 0.45)):
            hd.line([(0, yy), (g.width, yy)], fill=round(70 * (1 - yy / (g.height * 0.45))))
        g.alpha_composite(Image.merge("RGBA", (*[Image.new("L", g.size, 255)] * 3, hl)))
        m = Image.new("L", g.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, g.width - 1, g.height - 1], self.s(r), fill=255)
        self.img.paste(g, (self.s(x1), self.s(y1)), m)
        self.d = ImageDraw.Draw(self.img)
        self.rect(x1, y1, x2, y2, outline=(255, 255, 255, 230), width=2, r=r)

    def sphere(self, cx, cy, r, color=VIOLET, shadow=True):
        """Bille en polymère brillant (éclairée en haut à gauche, reflet spéculaire)."""
        R = self.s(r)
        yy, xx = np.mgrid[-R:R, -R:R].astype(np.float32) / R
        d2 = xx ** 2 + yy ** 2
        nz = np.sqrt(np.clip(1 - d2, 0, 1))
        L = np.array([-0.45, -0.6, 0.66], np.float32)
        L /= np.linalg.norm(L)
        diff = np.clip(xx * L[0] + yy * L[1] + nz * L[2], 0, 1)
        Hv = L + np.array([0, 0, 1], np.float32)
        Hv /= np.linalg.norm(Hv)
        spec = np.clip(xx * Hv[0] + yy * Hv[1] + nz * Hv[2], 0, 1) ** 60
        rim = np.clip(1 - nz, 0, 1) ** 3 * 0.35
        col = np.array(color, np.float32)
        rgb = col * (0.32 + 0.8 * diff[..., None]) + 255 * (0.95 * spec[..., None] + rim[..., None] * 0.6)
        a = np.clip((1 - np.sqrt(d2)) * R / 1.5, 0, 1) * 255
        ball = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8), "RGBA")
        if shadow:
            sh = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse([self.s(cx - r * 0.8), self.s(cy + r * 0.85), self.s(cx + r * 0.8), self.s(cy + r * 1.1)],
                                       fill=(40, 30, 90, 60))
            self.img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(self.s(r * 0.18))))
        self.img.alpha_composite(ball, (self.s(cx) - R, self.s(cy) - R))
        self.d = ImageDraw.Draw(self.img)

    def reseau(self, name, x, y, w, angle=0):
        """Logo 3D d'un réseau social ou réaction (resources/reseaux : instagram, tiktok, youtube, facebook, coeur…)."""
        f = PI.REPO / "resources" / "reseaux" / f"{name}.png"
        if not f.is_file():
            return
        im = Image.open(f).convert("RGBA")
        im = im.resize((self.s(w), round(im.height * self.s(w) / im.width)), Image.LANCZOS)
        if angle:
            im = im.rotate(angle, Image.BICUBIC, expand=True)
        self.img.alpha_composite(im, (self.s(x), self.s(y)))
        self.d = ImageDraw.Draw(self.img)

    def done(self) -> Image.Image:
        return self.img.convert("RGB")


@lru_cache(maxsize=4)
def _logo(color):
    lg = PI.white_logo()
    if lg is None:
        return None
    solid = Image.new("RGBA", lg.size, (*color, 0))
    solid.putalpha(lg.getchannel("A"))
    return solid


@lru_cache(maxsize=24)
def _icon(name):
    f = PI.REPO / "resources" / "icones3d" / f"{name}.png"
    return Image.open(f).convert("RGBA") if f.is_file() else None


def _texture(w, h):
    return _texture_src(w, h).copy()


@lru_cache(maxsize=4)
def _texture_src(w, h):
    t = Image.open(PI.REPO / "resources" / "papier" / "texture.jpg").convert("RGB")
    r = max(w / t.width, h / t.height)
    t = t.resize((math.ceil(t.width * r), math.ceil(t.height * r)), Image.LANCZOS)
    return t.crop((0, 0, w, h)).convert("RGBA")


def _rip(name, w):
    im = Image.open(PI.REPO / "resources" / "papier" / f"{name}.png").convert("RGBA")
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def _big(c: Canvas, text, name, px, w):
    return c.fit(text, name, px, w)


# ── Les 20 gabarits (charte : blanc dominant, bleu ciel en verre, touches de violet verre et polymère) ──────────────

def _lines(c: Canvas, x, y, text, name, px, fill, w, mx=3, gap=1.42, anchor="ls"):
    """Paragraphe ; renvoie le y après la dernière ligne."""
    for line in c.wrap(text, name, px, w, mx):
        if anchor == "ms":
            c.center(y, line, name, px, fill)
        else:
            c.text(x, y, line, name, px, fill, anchor)
        y += px * gap
    return y


def _suivez(c: Canvas, y, ink=INK):
    """Ligne « suivez-nous » : logos 3D Instagram, TikTok, YouTube, Facebook et @cauricharts, centrée."""
    names, w, gap = ("instagram", "tiktok", "youtube", "facebook"), 54, 14
    label = "@cauricharts"
    total = len(names) * (w + gap) + c.width(label, B, 24)
    x = (c.W - total) / 2
    for n in names:
        c.reseau(n, x, y - w * 0.8, w)
        x += w + gap
    c.text(x + 4, y, label, B, 24, (*ink, 230))


def _foot(c: Canvas, k: dict, center=False):
    if center:
        c.center(c.y1, k["date"] + "  ·  cauricharts.com", S, 22, (*INK, 150))
    else:
        c.text(c.pad, c.y1, k["date"], B, 22, (*INK, 190))
        c.text(c.W - c.pad, c.y1, "cauricharts.com", S, 22, (*INK, 140), "rs")


def g01_papier(c: Canvas, k: dict, p: dict):
    """Papier texturé, titre sur un papier déchiré posé de travers, bille violette."""
    c.img = _texture(*c.img.size)
    c.d = ImageDraw.Draw(c.img)
    c.logo(c.pad, c.y0, 200, INK)
    c.text(c.pad, c.y0 + 190, k["kicker"].upper(), B, 30, (*p["accent"], 255), spacing=4)
    strip = _rip("bout-12", c.s(c.W - 80))
    sd = ImageDraw.Draw(strip)
    sw, sh = strip.width / PI.SCALE, strip.height / PI.SCALE
    px = c.fit(k["title"].upper(), D, 190, sw - 160)
    sd.text((c.s(sw / 2), c.s(sh * 0.5 + px * 0.36)), k["title"].upper(), font=c.font(D, px), fill=(*INK, 255), anchor="ms")
    strip = strip.rotate(-3, Image.BICUBIC, expand=True)
    mid = (c.y0 + c.y1) / 2
    c.img.alpha_composite(strip, (c.s(40), c.s(mid - sh / 2 - 40)))
    c.d = ImageDraw.Draw(c.img)
    c.sphere(c.W - c.pad - 60, mid - sh / 2 - 60, 56, p["accent"])
    _lines(c, c.pad, mid + sh / 2 + 90, k["sub"], S, 36, (*INK, 255), c.W - 2 * c.pad)
    _foot(c, k)


def g02_verre(c: Canvas, k: dict, p: dict):
    """Grande carte de verre bleu ciel sur fond blanc, billes violettes derrière."""
    c.soft(k["seed"], 1.4)
    mid = (c.y0 + c.y1) / 2
    c.sphere(c.W - 210, mid - 330, 150, p["accent"])
    c.sphere(190, mid + 300, 110, SKY)
    x1, x2, y1, y2 = c.pad - 10, c.W - c.pad + 10, mid - 320, mid + 320
    c.glass((x1, y1, x2, y2), 44)
    c.center(y1 + 110, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=5)
    px = c.fit(k["title"], ABRIL, 170, x2 - x1 - 100)
    c.center(y1 + 150 + px * 0.9, k["title"], ABRIL, px, (*INK, 255))
    _lines(c, 0, y1 + 220 + px, k["sub"], S, 32, (*INK, 210), x2 - x1 - 120, anchor="ms")
    c.center(y2 - 50, k["date"], B, 22, (*INK, 170))
    c.logo(c.W / 2 - 110, c.y0, 220, INK)
    _suivez(c, c.y1)


def g03_affiche(c: Canvas, k: dict, p: dict):
    """Affiche suisse : grille fine, grand chiffre violet, titre aligné à gauche."""
    c.img = Image.new("RGBA", c.img.size, (255, 255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    for i in range(1, 6):
        x = c.W * i / 6
        c.line([(x, 0), (x, c.H)], (*SKY, 50), 1)
    num = k.get("number") or k["title"][:2].upper()
    px = c.fit(num, D, 640, c.W - 2 * c.pad)
    c.text(c.pad - 12, c.y0 + px * 0.86, num, D, px, (*p["accent"], 255))
    y = c.y0 + px * 0.86 + 40
    c.rect(c.pad, y, c.W - c.pad, y + 10, (*INK, 255))
    tpx = c.fit(k["title"].upper(), D, 150, c.W - 2 * c.pad)
    c.text(c.pad, y + 30 + tpx * 0.9, k["title"].upper(), D, tpx, (*INK, 255))
    y += 60 + tpx
    c.text(c.pad, y + 20, k["kicker"].upper(), B, 28, (*INK, 255), spacing=3)
    _lines(c, c.pad, y + 90, k["sub"], S, 30, (*INK, 200), c.W * 0.7)
    c.logo(c.pad, c.y1 - 70, 180, INK)
    c.text(c.W - c.pad, c.y1 - 20, k["date"].upper(), B, 22, (*INK, 255), "rs")


def g04_billes(c: Canvas, k: dict, p: dict):
    """Composition de billes en polymère (violet, bleu ciel, blanc) et titre sur bandeau de verre."""
    c.soft(k["seed"], 0.8)
    rnd = random.Random(k["seed"])
    mid = (c.y0 + c.y1) / 2
    for _ in range(7):
        r = rnd.uniform(40, 140)
        c.sphere(rnd.uniform(60, c.W - 60), rnd.choice((rnd.uniform(c.y0 + 250, mid - 260), rnd.uniform(mid + 260, c.y1 - 140))), r,
                 rnd.choice((p["accent"], SKY, (235, 236, 248), p["accent"])))
    for name, x, y, w, a in (("instagram", 120, mid - 420, 120, 12), ("coeur", c.W - 230, mid + 270, 110, -10),
                             ("tiktok", c.W - 200, mid - 380, 100, -8)):
        c.reseau(name, x, y, w, a)
    c.glass((0, mid - 220, c.W, mid + 220), 0, veil=170)
    c.center(mid - 120, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=6)
    px = c.fit(k["title"].upper(), D, 170, c.W - 2 * c.pad)
    c.center(mid - 100 + px * 0.88, k["title"].upper(), D, px, (*INK, 255))
    _lines(c, 0, mid - 40 + px, k["sub"], S, 28, (*INK, 200), c.W - 2 * c.pad, 2, anchor="ms")
    c.logo(c.W / 2 - 100, c.y0, 200, INK)
    _foot(c, k, True)


def g05_icone(c: Canvas, k: dict, p: dict):
    """Icône 3D géante sur un socle de verre, fond blanc."""
    c.soft(k["seed"], 1.0)
    mid = (c.y0 + c.y1) / 2
    c.glass((c.W / 2 - 300, mid - 520, c.W / 2 + 300, mid + 60), 300, blur=20)
    c.icon(k.get("icon") or "gift", c.W / 2 - 220, mid - 470, 440, 0)
    c.center(mid + 150, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=5)
    px = c.fit(k["title"], ABRIL, 150, c.W - 2 * c.pad)
    c.center(mid + 170 + px * 0.9, k["title"], ABRIL, px, (*INK, 255))
    _lines(c, 0, mid + 230 + px, k["sub"], S, 30, (*INK, 200), c.W - 2 * c.pad - 40, 2, anchor="ms")
    c.logo(c.pad, c.y0, 180, INK)
    c.text(c.W - c.pad, c.y0 + 50, k["date"], B, 22, (*INK, 170), "rs")


def g06_ticket(c: Canvas, k: dict, p: dict):
    """Billet d'événement en verre, talon détachable et code-barres."""
    c.soft(k["seed"], 1.6)
    x1, x2 = c.pad - 20, c.W - c.pad + 20
    mid = (c.y0 + c.y1) / 2
    y1, y2 = mid - 420, mid + 420
    c.glass((x1, y1, x2, y2), 30, veil=190)
    cut = y2 - 230
    for x in range(int(x1) + 30, int(x2) - 20, 28):
        c.line([(x, cut), (x + 14, cut)], (*INK, 90), 3)
    c.rect(x1, y1, x2, y1 + 100, (*p["accent"], 255), r=30)
    c.rect(x1, y1 + 60, x2, y1 + 100, (*p["accent"], 255))
    c.text(x1 + 50, y1 + 66, k["kicker"].upper(), B, 28, (255, 255, 255, 255), spacing=3)
    px = c.fit(k["title"].upper(), D, 190, x2 - x1 - 100)
    c.text(x1 + 50, y1 + 150 + px * 0.86, k["title"].upper(), D, px, (*INK, 255))
    _lines(c, x1 + 50, y1 + 200 + px, k["sub"], S, 30, (*INK, 210), x2 - x1 - 100)
    c.text(x1 + 50, cut + 80, "ADMIS · " + k["date"].upper(), B, 24, (*INK, 255))
    c.text(x1 + 50, cut + 130, "cauricharts.com", S, 22, (*INK, 160))
    rnd = random.Random(k["seed"])
    bx = x2 - 330
    for _ in range(46):
        w = rnd.choice((2, 2, 4, 6))
        c.rect(bx, cut + 50, bx + w, cut + 170, (*INK, 255))
        bx += w + rnd.choice((3, 5))
    c.logo(c.W / 2 - 100, c.y0 - 20, 200, INK)


def g07_polaroid(c: Canvas, k: dict, p: dict):
    """Photo souvenir (polaroid) de travers sur papier, titre manuscrit."""
    c.img = _texture(*c.img.size)
    c.d = ImageDraw.Draw(c.img)
    mid = (c.y0 + c.y1) / 2
    pw, ph = 640, 760
    card = Image.new("RGBA", (c.s(pw), c.s(ph)), (255, 255, 255, 255))
    sub = Canvas.__new__(Canvas)
    sub.img, sub.d = card, ImageDraw.Draw(card)
    inner = (34, 34, pw - 34, ph - 170)
    if not (k.get("photo") and Canvas.photo(sub, k["photo"], inner)):
        g = Image.new("RGBA", (c.s(inner[2] - inner[0]), c.s(inner[3] - inner[1])), (226, 240, 255, 255))
        card.alpha_composite(g, (c.s(34), c.s(34)))
        ic = _icon(k.get("icon") or "gift")
        if ic:
            ic = ic.resize((c.s(380), round(ic.height * c.s(380) / ic.width)), Image.LANCZOS)
            card.alpha_composite(ic, ((card.width - ic.width) // 2, c.s(34) + (g.height - ic.height) // 2))
    ImageDraw.Draw(card).text((c.s(pw / 2), c.s(ph - 70)), k["title"], font=c.font(ITAL, 84), fill=(*INK, 255), anchor="ms")
    sh = Image.new("RGBA", (card.width + c.s(120), card.height + c.s(120)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([c.s(60), c.s(80), c.s(60 + pw), c.s(80 + ph)], fill=(0, 0, 0, 90))
    sh = sh.filter(ImageFilter.GaussianBlur(c.s(26)))
    sh.alpha_composite(card, (c.s(60), c.s(60)))
    sh = sh.rotate(-5, Image.BICUBIC, expand=True)
    c.img.alpha_composite(sh, (c.s(c.W / 2) - sh.width // 2, c.s(mid - ph / 2 - 120)))
    c.d = ImageDraw.Draw(c.img)
    c.sphere(c.W / 2 + pw / 2 - 10, mid - ph / 2 - 100, 44, p["accent"])
    c.center(c.y0 + 60, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=5)
    _lines(c, 0, mid + ph / 2 + 30, k["sub"], S, 30, (*INK, 220), c.W - 2 * c.pad, 2, anchor="ms")
    c.logo(c.W / 2 - 90, c.y1 - 70, 180, INK)


def g08_journal(c: Canvas, k: dict, p: dict):
    """Une de journal blanche : bandeau-titre, filets, colonnes."""
    c.img = Image.new("RGBA", c.img.size, (252, 252, 250, 255))
    c.d = ImageDraw.Draw(c.img)
    y = c.y0 + 10
    c.center(y + 100, "LA GAZETTE CAURI", CINZEL, 86, (*INK, 255))
    c.line([(c.pad, y + 130), (c.W - c.pad, y + 130)], (*INK, 255), 4)
    c.line([(c.pad, y + 140), (c.W - c.pad, y + 140)], (*INK, 255), 1)
    c.text(c.pad, y + 172, k["date"].upper(), B, 20, (*INK, 255))
    c.text(c.W - c.pad, y + 172, "ÉDITION SPÉCIALE", B, 20, (*p["accent"], 255), "rs")
    c.line([(c.pad, y + 190), (c.W - c.pad, y + 190)], (*INK, 255), 1)
    c.center(y + 250, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=4)
    px = c.fit(k["title"].upper(), D, 230, c.W - 2 * c.pad)
    c.center(y + 270 + px * 0.88, k["title"].upper(), D, px, (*INK, 255))
    yy = y + 320 + px
    colw = (c.W - 2 * c.pad - 40) / 2
    if not (k.get("photo") and c.photo(k["photo"], (c.pad, yy, c.pad + colw, yy + 380))):
        c.glass((c.pad, yy, c.pad + colw, yy + 380), 20, blur=10, tint_a=60)
        c.icon(k.get("icon") or "megaphone", c.pad + 60, yy + 30, colw - 120)
    _lines(c, c.pad + colw + 40, yy + 30, k["sub"], SERIF, 32, (*INK, 255), colw, 7)
    c.line([(c.pad, c.y1 - 60), (c.W - c.pad, c.y1 - 60)], (*INK, 255), 1)
    c.logo(c.pad, c.y1 - 44, 150, INK)
    c.text(c.W - c.pad, c.y1, "cauricharts.com", S, 20, (*INK, 200), "rs")


def g09_ornement(c: Canvas, k: dict, p: dict):
    """Carte de vœux élégante : blanc cassé, double cadre fin violet et bleu ciel, capitales romaines."""
    c.img = Image.new("RGBA", c.img.size, (253, 252, 250, 255))
    c.d = ImageDraw.Draw(c.img)
    m = 44
    c.rect(m, c.top + m, c.W - m, c.H - c.bottom - m, outline=(*VIOLET, 255), width=3)
    c.rect(m + 16, c.top + m + 16, c.W - m - 16, c.H - c.bottom - m - 16, outline=(*SKY, 255), width=1)
    mid = (c.y0 + c.y1) / 2
    for sx in (-1, 1):
        c.line([(c.W / 2 + sx * 40, mid - 250), (c.W / 2 + sx * 280, mid - 250)], (*SKY, 255), 2)
    c.sphere(c.W / 2, mid - 250, 18, VIOLET, False)
    c.center(mid - 170, k["kicker"].upper(), CINZEL, 32, (*INK, 255), spacing=6)
    px = c.fit(k["title"], ITAL, 200, c.W - 2 * c.pad)
    c.center(mid + px * 0.3, k["title"], ITAL, px, (*VIOLET, 255))
    y = _lines(c, 0, mid + px * 0.3 + 90, k["sub"], SERIF, 32, (*INK, 220), c.W - 2 * c.pad - 60, anchor="ms")
    c.center(y + 40, k["date"].upper(), CINZEL, 22, (*INK, 170), spacing=4)
    c.logo(c.W / 2 - 90, c.y1 - 110, 180, INK)


def g10_calendrier(c: Canvas, k: dict, p: dict):
    """Page de calendrier à anneaux posée sur fond blanc et bleu ciel."""
    c.soft(k["seed"], 1.5)
    mid = (c.y0 + c.y1) / 2
    x1, x2 = c.pad + 20, c.W - c.pad - 20
    y1, y2 = mid - 400, mid + 380
    c.shadow((x1, y1, x2, y2), 34, 44, 50)
    c.rect(x1, y1, x2, y2, (255, 255, 255, 255), r=34)
    c.rect(x1, y1, x2, y1 + 170, (*p["accent"], 255), r=34)
    c.rect(x1, y1 + 120, x2, y1 + 170, (*p["accent"], 255))
    for i in range(6):
        x = x1 + 90 + i * (x2 - x1 - 180) / 5
        c.rect(x - 12, y1 - 40, x + 12, y1 + 30, (200, 205, 220, 255), r=12)
    tpx = c.fit(k["title"].upper(), D, 110, x2 - x1 - 80)
    c.center(y1 + 130, k["title"].upper(), D, tpx, (255, 255, 255, 255))
    num = k.get("number") or "01"
    npx = c.fit(num, D, 400, x2 - x1 - 100)
    c.center(y1 + 190 + npx * 0.88, num, D, npx, (*INK, 255))
    _lines(c, 0, y1 + 240 + npx, k["sub"], S, 28, (*INK, 200), x2 - x1 - 100, 2, anchor="ms")
    c.center(y1 - 80, k["kicker"].upper(), B, 28, (*INK, 255), spacing=5)
    c.logo(c.W / 2 - 90, c.y1 - 60, 180, INK)


def g11_diagonales(c: Canvas, k: dict, p: dict):
    """Fines bandes diagonales bleu ciel et violet sur blanc (ou couleurs du drapeau), bandeau de verre."""
    cols = FLAGS.get((k.get("country") or "").lower()) or [SKY, (255, 255, 255), p["accent"], (255, 255, 255)]
    c.img = Image.new("RGBA", c.img.size, (255, 255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    w = 70
    for i in range(-24, 40):
        col = cols[i % len(cols)]
        x = i * w
        c.d.polygon([(c.s(x), 0), (c.s(x + w), 0), (c.s(x + w - c.H * 0.6), c.s(c.H)), (c.s(x - c.H * 0.6), c.s(c.H))],
                    fill=(*col, 255))
    mid = (c.y0 + c.y1) / 2
    c.glass((c.pad - 30, mid - 270, c.W - c.pad + 30, mid + 270), 36, veil=215, blur=36)
    c.text(c.pad + 20, mid - 170, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=4)
    px = c.fit(k["title"].upper(), D, 190, c.W - 2 * c.pad - 40)
    c.text(c.pad + 20, mid - 140 + px * 0.88, k["title"].upper(), D, px, (*INK, 255))
    _lines(c, c.pad + 20, mid - 90 + px, k["sub"], S, 28, (*INK, 210), c.W - 2 * c.pad - 40, 2)
    c.rect(c.pad - 20, c.y0 - 20, c.pad + 230, c.y0 + 100, (255, 255, 255, 235), r=20)
    c.logo(c.pad, c.y0, 190, INK)
    c.rect(c.pad - 20, c.y1 - 44, c.W - c.pad + 20, c.y1 + 20, (255, 255, 255, 235), r=16)
    _foot(c, k)


def g12_disque(c: Canvas, k: dict, p: dict):
    """Grand disque de verre bleu ciel, anneau violet en polymère."""
    c.soft(k["seed"], 1.2)
    mid = (c.y0 + c.y1) / 2
    r = c.W * 0.40
    for i in range(5, 0, -1):
        rr = r + i * 50
        c.ellipse(c.W / 2 - rr, mid - rr, c.W / 2 + rr, mid + rr, outline=(*SKY, 40 + 12 * (5 - i)), width=2)
    c.sphere(c.W / 2 + r * 0.78, mid - r * 0.72, 70, p["accent"])
    c.glass((c.W / 2 - r, mid - r, c.W / 2 + r, mid + r), r, veil=160, tint_a=55)
    c.center(mid - 130, k["kicker"].upper(), B, 26, (*p["accent"], 255), spacing=4)
    px = c.fit(k["title"].upper(), D, 160, r * 1.6)
    c.center(mid + px * 0.35, k["title"].upper(), D, px, (*INK, 255))
    _lines(c, 0, mid + px * 0.35 + 70, k["sub"], S, 26, (*INK, 210), r * 1.5, 3, anchor="ms")
    c.logo(c.W / 2 - 95, c.y0, 190, INK)
    _suivez(c, c.y1)


def g13_scinde(c: Canvas, k: dict, p: dict):
    """Moitié haute en verre bleu ciel (photo ou icône), moitié basse blanche."""
    split = c.H * 0.52
    c.soft(k["seed"], 2.2)
    if not (k.get("photo") and c.photo(k["photo"], (0, 0, c.W, split))):
        c.sphere(170, max(c.top + 160, split * 0.3), 90, p["accent"])
        c.icon(k.get("icon") or "megaphone", c.W / 2 - 200, max(c.top + 60, split / 2 - 220), 400)
    c.rect(0, split, c.W, c.H, (255, 255, 255, 255))
    c.rect(0, split, c.W, split + 10, (*p["accent"], 255))
    y = split + 90
    c.text(c.pad, y, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=4)
    px = c.fit(k["title"].upper(), D, 170, c.W - 2 * c.pad)
    c.text(c.pad, y + 20 + px * 0.88, k["title"].upper(), D, px, (*INK, 255))
    _lines(c, c.pad, y + 70 + px, k["sub"], S, 30, (*INK, 210), c.W - 2 * c.pad)
    c.rect(c.pad - 20, c.top + 30, c.pad + 220, c.top + 150, (255, 255, 255, 200), r=20)
    c.logo(c.pad, c.top + 50, 180, INK)
    _foot(c, k)


def g14_typo(c: Canvas, k: dict, p: dict):
    """Typographie géante sur blanc : le titre répété, en contour bleu ciel et en plein violet, carte de verre."""
    c.img = Image.new("RGBA", c.img.size, (255, 255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    word = k["title"].upper()
    px = c.fit(word, D, 400, c.W - 60)
    y = c.top + 40
    i = 0
    while y < c.H - c.bottom:
        y += px * 0.92
        layer = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        if i % 3 == 1:
            ld.text((c.s(c.W / 2), c.s(y)), word, font=c.font(D, px), fill=(*p["accent"], 255), anchor="ms")
        else:
            ld.text((c.s(c.W / 2), c.s(y)), word, font=c.font(D, px), fill=(*SKY, 255), anchor="ms",
                    stroke_width=c.s(3), stroke_fill=(*SKY, 255))
            ld.text((c.s(c.W / 2), c.s(y)), word, font=c.font(D, px), fill=(0, 0, 0, 0), anchor="ms")
        c.img.alpha_composite(layer)
        i += 1
    c.d = ImageDraw.Draw(c.img)
    mid = (c.y0 + c.y1) / 2
    c.glass((c.pad - 20, mid - 170, c.W - c.pad + 20, mid + 170), 30, veil=200, blur=34)
    c.center(mid - 80, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=5)
    yy = _lines(c, 0, mid - 15, k["sub"], S, 30, (*INK, 240), c.W - 2 * c.pad - 40, 3, anchor="ms")
    c.center(mid + 140, k["date"].upper(), B, 20, (*INK, 170))


def g15_confettis(c: Canvas, k: dict, p: dict):
    """Fête : confettis bleu ciel, violet et or sur blanc, grand chiffre en violet."""
    c.soft(k["seed"], 0.8)
    rnd = random.Random(k["seed"])
    cols = [SKY, VIOLET, GOLD, (150, 120, 255), (120, 200, 255)]
    for _ in range(170):
        x, y = rnd.uniform(0, c.W), rnd.uniform(0, c.H)
        col = rnd.choice(cols)
        if rnd.random() < 0.5:
            r = rnd.uniform(4, 10)
            c.ellipse(x - r, y - r, x + r, y + r, (*col, 230))
        else:
            a = rnd.uniform(0, math.pi)
            ln = rnd.uniform(12, 26)
            c.line([(x, y), (x + ln * math.cos(a), y + ln * math.sin(a))], (*col, 230), 6)
    mid = (c.y0 + c.y1) / 2
    c.reseau("emoji-amour", c.W - c.pad - 130, mid - 420, 150, 10)
    c.reseau("coeur", c.pad - 30, mid + 280, 120, -12)
    c.glass((c.pad - 20, mid - 330, c.W - c.pad + 20, mid + 330), 40, veil=200)
    c.center(mid - 230, k["kicker"].upper(), B, 30, (*INK, 255), spacing=6)
    num = k.get("number")
    if num:
        npx = c.fit(num, ABRIL, 280, c.W - 2 * c.pad)
        c.center(mid + npx * 0.2, num, ABRIL, npx, (*p["accent"], 255))
        y = mid + npx * 0.2 + 20
        tpx = c.fit(k["title"], ITAL, 90, c.W - 2 * c.pad)
        c.center(y + tpx, k["title"], ITAL, tpx, (*INK, 255))
        y += tpx + 80
    else:
        tpx = c.fit(k["title"], ABRIL, 160, c.W - 2 * c.pad)
        c.center(mid + tpx * 0.3, k["title"], ABRIL, tpx, (*p["accent"], 255))
        y = mid + tpx * 0.3 + 90
    _lines(c, 0, y, k["sub"], S, 28, (*INK, 220), c.W - 2 * c.pad - 40, 2, anchor="ms")
    c.logo(c.W / 2 - 100, c.y0, 200, INK)
    _foot(c, k, True)


def g16_minimal(c: Canvas, k: dict, p: dict):
    """Blanc minimal : beaucoup d'air, un filet violet, petit titre élégant, une bille."""
    c.img = Image.new("RGBA", c.img.size, (255, 255, 255, 255))
    c.d = ImageDraw.Draw(c.img)
    c.logo(c.pad, c.y0, 170, INK)
    c.text(c.W - c.pad, c.y0 + 46, k["date"].upper(), B, 20, (*INK, 150), "rs", spacing=2)
    mid = (c.y0 + c.y1) / 2
    c.sphere(c.W - c.pad - 90, mid - 300, 90, p["accent"])
    c.rect(c.pad, mid - 140, c.pad + 90, mid - 132, (*p["accent"], 255))
    c.text(c.pad, mid - 80, k["kicker"].upper(), B, 24, (*INK, 160), spacing=5)
    px = c.fit(k["title"], SERIF, 150, c.W - 2 * c.pad)
    c.text(c.pad, mid + px * 0.75, k["title"], SERIF, px, (*INK, 255))
    _lines(c, c.pad, mid + px * 0.75 + 70, k["sub"], S, 30, (*INK, 180), c.W * 0.66)
    c.text(c.pad, c.y1, "cauricharts.com", S, 20, (*INK, 120))


def g17_drapeau(c: Canvas, k: dict, p: dict):
    """Blanc, liseré aux couleurs du drapeau (ou de Cauri) en haut et en bas, carte de verre."""
    cols = FLAGS.get((k.get("country") or "").lower()) or [SKY, (255, 255, 255), p["accent"]]
    c.soft(k["seed"], 1.0)
    for band in ((0, 26), (c.H - 26, c.H)):
        for i, col in enumerate(cols):
            c.rect(c.W * i / len(cols), band[0], c.W * (i + 1) / len(cols), band[1], (*col, 255))
    mid = (c.y0 + c.y1) / 2
    x1, x2, y1, y2 = c.pad - 10, c.W - c.pad + 10, mid - 300, mid + 300
    c.glass((x1, y1, x2, y2), 26, veil=200)
    c.center(y1 + 100, k["kicker"].upper(), B, 28, (*p["accent"], 255), spacing=5)
    px = c.fit(k["title"], ABRIL, 150, x2 - x1 - 80)
    c.center(y1 + 130 + px * 0.9, k["title"], ABRIL, px, (*INK, 255))
    _lines(c, 0, y1 + 190 + px, k["sub"], S, 28, (*INK, 210), x2 - x1 - 100, 3, anchor="ms")
    c.center(y2 - 40, k["date"].upper(), B, 20, (*INK, 160))
    c.logo(c.W / 2 - 110, c.y0, 220, INK)


def g18_vinyle(c: Canvas, k: dict, p: dict):
    """Vinyle noir posé sur blanc, étiquette violette, pochette de verre bleu ciel derrière."""
    c.soft(k["seed"], 1.0)
    mid = (c.y0 + c.y1) / 2 - 60
    r = c.W * 0.36
    c.glass((c.W / 2 - r - 120, mid - r - 40, c.W / 2 + r - 120, mid + r + 40), 20, veil=170, tint_a=60)
    cx = c.W / 2 + 90
    c.shadow((cx - r, mid - r, cx + r, mid + r), r, 30, 60, 18)
    c.ellipse(cx - r, mid - r, cx + r, mid + r, (16, 15, 20, 255))
    for i in range(28):
        rr = r - 14 - i * 9
        c.ellipse(cx - rr, mid - rr, cx + rr, mid + rr, outline=(255, 255, 255, 16 + (i % 3) * 6), width=1)
    lr = r * 0.42
    c.ellipse(cx - lr, mid - lr, cx + lr, mid + lr, (*p["accent"], 255))
    c.ellipse(cx - 10, mid - 10, cx + 10, mid + 10, (255, 255, 255, 255))
    c.text(cx, mid - lr * 0.4, k["kicker"].upper(), B, 16, (255, 255, 255, 255), "ms", spacing=2)
    px = c.fit(k["title"].upper(), D, 70, lr * 1.5)
    c.text(cx, mid + lr * 0.6, k["title"].upper(), D, px, (255, 255, 255, 255), "ms")
    tpx = c.fit(k["title"], ABRIL, 110, c.W - 2 * c.pad)
    c.center(mid + r + 140, k["title"], ABRIL, tpx, (*INK, 255))
    _lines(c, 0, mid + r + 200, k["sub"], S, 28, (*INK, 210), c.W - 2 * c.pad, 2, anchor="ms")
    c.logo(c.pad, c.y0, 180, INK)
    c.text(c.W - c.pad, c.y0 + 50, k["date"], B, 22, (*INK, 170), "rs")


def g19_rubans(c: Canvas, k: dict, p: dict):
    """Rubans de texte bleu ciel et violet qui se croisent sur blanc, titre au centre."""
    c.soft(k["seed"], 0.6)
    text = ("  " + k["kicker"].upper() + "  •") * 8
    for angle, col, y in ((-8, p["accent"], c.H * 0.24), (6, SKY, c.H * 0.78)):
        band = Image.new("RGBA", (c.s(c.W * 1.6), c.s(110)), (*col, 255))
        ImageDraw.Draw(band).text((c.s(10), c.s(55)), text, font=c.font(D, 60), fill=(255, 255, 255, 255), anchor="lm")
        band = band.rotate(angle, Image.BICUBIC, expand=True)
        c.img.alpha_composite(band, (c.s(c.W / 2) - band.width // 2, c.s(y) - band.height // 2))
    c.d = ImageDraw.Draw(c.img)
    mid = (c.y0 + c.y1) / 2
    px = c.fit(k["title"].upper(), D, 210, c.W - 2 * c.pad)
    c.center(mid + px * 0.3, k["title"].upper(), D, px, (*INK, 255))
    _lines(c, 0, mid + px * 0.3 + 70, k["sub"], S, 28, (*INK, 210), c.W - 2 * c.pad, 2, anchor="ms")
    c.center(mid - px * 0.6, k["date"].upper(), B, 24, (*p["accent"], 255), spacing=3)
    c.logo(c.pad, c.y0 - 20, 160, INK)


def g20_dechire(c: Canvas, k: dict, p: dict):
    """Photo (ou verre bleu ciel et billes) déchirée, titre sur le papier."""
    if not (k.get("photo") and c.photo(k["photo"], (0, 0, c.W, c.H))):
        c.soft(k["seed"], 2.4)
        c.sphere(c.W - 220, c.y0 + 240, 150, p["accent"])
        c.sphere(200, c.y0 + 380, 80, SKY)
        c.icon(k.get("icon") or "trophy", c.W / 2 - 170, c.y0 + 90, 340, -6)
    mid = (c.y0 + c.y1) / 2 + 60
    top = _rip("bout-12", c.s(c.W + 120)).rotate(-2, Image.BICUBIC, expand=True)
    c.img.alpha_composite(top, (c.s(-60), c.s(mid - 320)))
    c.d = ImageDraw.Draw(c.img)
    th = top.height / PI.SCALE
    c.text(c.pad, mid - 320 + th * 0.36, k["kicker"].upper(), B, 26, (*p["accent"], 255), spacing=4)
    px = c.fit(k["title"].upper(), D, 160, c.W - 2 * c.pad)
    c.text(c.pad, mid - 320 + th * 0.36 + 20 + px * 0.88, k["title"].upper(), D, px, (*INK, 255))
    y = mid - 320 + th + 60
    lines = c.wrap(k["sub"], B, 28, c.W - 2 * c.pad - 40, 3)
    c.glass((c.pad - 24, y - 50, c.pad + 24 + max(c.width(ln, B, 28) for ln in lines), y + 40 * (len(lines) - 1) + 26), 16,
            veil=200, blur=20)
    _lines(c, c.pad, y, k["sub"], B, 28, (*INK, 255), c.W - 2 * c.pad - 40, 3, gap=1.43)
    c.logo(c.pad, c.y0, 190, INK)
    _foot(c, k)


LAYOUTS = [g01_papier, g02_verre, g03_affiche, g04_billes, g05_icone, g06_ticket, g07_polaroid, g08_journal, g09_ornement,
           g10_calendrier, g11_diagonales, g12_disque, g13_scinde, g14_typo, g15_confettis, g16_minimal, g17_drapeau,
           g18_vinyle, g19_rubans, g20_dechire]
NAMES = {f.__name__: f for f in LAYOUTS}


def pick(seed: str) -> str:
    return random.Random(seed + "-gabarit").choice(LAYOUTS).__name__


def render(content: dict, layout: str | None = None, fmt: str = "post", palette: dict | None = None) -> Image.Image:
    """Dessine un visuel ; gabarit tiré au sort (stable) d'après content['seed'] si layout n'est pas donné."""
    k = {"kicker": "", "title": "", "sub": "", "date": "", **content}
    k.setdefault("seed", k["title"] + k["date"])
    fn = NAMES[layout or pick(k["seed"])]
    p = palette or random.Random(k["seed"] + "-palette").choice(PALETTES)
    c = Canvas(fmt)
    fn(c, k, p)
    return c.done()
