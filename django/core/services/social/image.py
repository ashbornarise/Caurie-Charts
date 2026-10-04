"""Visuels des posts, esprit magazine de classements (traduction de Social\\PostImage, GD → Pillow).

Photo de l'artiste en plein cadre, dégradé sombre, titre géant en Anton (police libre OFL, resources/fonts),
titre du post, puis la liste des meilleures performances. Rendu en 4K (2160 px de large) : post 4:5 (2160 × 2700,
fil Instagram et Facebook) et story 9:16 (2160 × 3840). La mise en page est écrite sur une base de 1080 px.
"""
import io
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from core import storage
from core.services import share_image
from core.services.news import http_get

REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
DIR = storage.MEDIA / "social"
SCALE = 2  # base 1080 px → 2160 px de large (4K)
# Zones couvertes par l'interface des applications en 9:16 (base 1080 × 1920) : profil et boutons en haut,
# légende, musique et réponse en bas, boutons d'action à droite (TikTok, Reels). Rien d'important n'y est posé.
SAFE_916 = {"top": 250, "bottom": 440, "side": 130}
_FONTS: dict = {}


def gd_alpha(a: int) -> int:
    """Transparence GD (0 opaque … 127 transparent) → opacité Pillow (255 … 0)."""
    return 255 - round(max(0, min(127, a)) * 255 / 127)


def font(path: str, px: int) -> ImageFont.FreeTypeFont:
    key = (path, px)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(path, px)
    return _FONTS[key]


FONT_DIR = REPO / "resources" / "fonts"
# Habillage tiré au hasard pour chaque post (le même sur tous ses visuels) : polices, couleurs, filtre photo.
# Polices libres (licence OFL, resources/fonts) : embarquées, car le serveur n'en a aucune.
FONT_SETS = [
    {"name": "Magazine", "display": "Anton-Regular.ttf", "bold": "Poppins-Bold.ttf", "sans": "Poppins-Regular.ttf", "serif": "DMSerifDisplay-Regular.ttf"},
    {"name": "Affiche", "display": "BebasNeue-Regular.ttf", "bold": "Lato-Bold.ttf", "sans": "Lato-Regular.ttf", "serif": "AbrilFatface-Regular.ttf"},
    {"name": "Bloc", "display": "ArchivoBlack-Regular.ttf", "bold": "PT_Sans-Web-Bold.ttf", "sans": "PT_Sans-Web-Regular.ttf", "serif": "PT_Serif-Web-Bold.ttf"},
    {"name": "Rétro", "display": "AlfaSlabOne-Regular.ttf", "bold": "Poppins-Bold.ttf", "sans": "Poppins-Regular.ttf", "serif": "AlfaSlabOne-Regular.ttf"},
    {"name": "Néon", "display": "Bungee-Regular.ttf", "bold": "Lato-Bold.ttf", "sans": "Lato-Regular.ttf", "serif": "DMSerifDisplay-Regular.ttf"},
    {"name": "Élégant", "display": "AbrilFatface-Regular.ttf", "bold": "Lato-Bold.ttf", "sans": "Lato-Regular.ttf", "serif": "DMSerifDisplay-Regular.ttf"},
]
# accent (chiffres, rubrique), texte posé sur l'accent, ombre des dégradés, fond sans photo
PALETTES = [
    {"name": "Violet Cauri", "accent": (139, 82, 255), "on": (255, 255, 255), "shade": (8, 5, 18), "base": (42, 14, 120)},
    {"name": "Or", "accent": (255, 190, 40), "on": (20, 14, 0), "shade": (16, 10, 2), "base": (120, 70, 0)},
    {"name": "Corail", "accent": (255, 92, 100), "on": (255, 255, 255), "shade": (20, 5, 8), "base": (130, 20, 40)},
    {"name": "Émeraude", "accent": (0, 210, 150), "on": (0, 25, 18), "shade": (3, 16, 12), "base": (0, 90, 70)},
    {"name": "Bleu", "accent": (60, 170, 255), "on": (0, 15, 30), "shade": (4, 10, 22), "base": (10, 40, 120)},
    {"name": "Orange", "accent": (255, 120, 30), "on": (255, 255, 255), "shade": (18, 8, 2), "base": (130, 50, 0)},
    {"name": "Citron", "accent": (215, 255, 60), "on": (20, 25, 0), "shade": (8, 10, 4), "base": (60, 80, 0)},
]
FILTERS = ["naturel", "noir et blanc", "duotone", "chaud", "froid", "contrasté", "doux"]


def style(seed: str) -> dict | None:
    """Habillage d'un post, tiré au hasard mais stable pour un même nom de post. None si une police manque."""
    rnd = random.Random(seed)
    fs, pal = rnd.choice(FONT_SETS), rnd.choice(PALETTES)
    paths = {k: str(FONT_DIR / fs[k]) for k in ("display", "bold", "sans", "serif")}
    if not all(Path(p).is_file() for p in paths.values()):
        return None
    flt = rnd.choice(FILTERS)
    return {**paths, **{k: pal[k] for k in ("accent", "on", "shade", "base")}, "filter": flt,
            "name": f"{fs['name']} · {pal['name']} · {flt}"}


def filtered(img: Image.Image | None, f: dict) -> Image.Image | None:
    """Filtre photo de l'habillage."""
    if img is None:
        return None
    kind = f.get("filter")
    if kind == "noir et blanc":
        return ImageEnhance.Contrast(ImageOps.grayscale(img)).enhance(1.15).convert("RGB")
    if kind == "duotone":
        light = tuple(min(255, int(c * 0.55 + 255 * 0.45)) for c in f["accent"])
        return ImageOps.colorize(ImageOps.grayscale(img), black=f["shade"], white=light)
    if kind in ("chaud", "froid"):
        tint = Image.new("RGB", img.size, (255, 150, 60) if kind == "chaud" else (60, 140, 255))
        return Image.blend(ImageEnhance.Color(img).enhance(1.1), tint, 0.14)
    if kind == "contrasté":
        return ImageEnhance.Color(ImageEnhance.Contrast(img).enhance(1.25)).enhance(1.2)
    if kind == "doux":
        return ImageEnhance.Brightness(ImageEnhance.Contrast(img).enhance(0.88)).enhance(1.05)
    return img


def width(text: str, path: str, px: int) -> int:
    return int(round(font(path, px).getlength(text)))


def draw_text(draw: ImageDraw.ImageDraw, px: int, x: int, y: int, color, path: str, text: str) -> None:
    """Texte posé sur sa ligne de base (comme imagettftext)."""
    draw.text((x, y), text, font=font(path, px), fill=color, anchor="ls")


def wrap(text: str, path: str, px: int, w: int, mx: int) -> list:
    lines, line = [], ""
    for word in re.split(r"\s+", text.strip()):
        attempt = word if line == "" else f"{line} {word}"
        if width(attempt, path, px) > w and line != "":
            lines.append(line)
            line = word
        else:
            line = attempt
    if line != "":
        lines.append(line)
    if len(lines) > mx:
        lines = lines[:mx]
        lines[mx - 1] = fit_width(lines[mx - 1] + "…", path, px, w)
    return lines


def fit_width(text: str, path: str, px: int, w: int) -> str:
    while len(text) > 4 and width(text, path, px) > w:
        text = text.rstrip("…")[:-2].rstrip() + "…"
    return text


def clean(text: str) -> str:
    """Retire les emojis et pictogrammes (absents des polices : ils s'affichent en carrés)."""
    text = re.sub("[\U0001F000-\U0001FFFF☀-➿⬀-⯿︀-️‍⃣]", "", str(text))
    return re.sub(r"\s{2,}", " ", text).strip()


def gradient(img: Image.Image, y1: int, y2: int, rgb, a_from: int, a_to: int, w: int) -> None:
    """Dégradé vertical de y1 à y2, transparence GD de a_from à a_to (courbe douce)."""
    draw = ImageDraw.Draw(img, "RGBA")
    span = max(1, y2 - y1)
    for y in range(y1, y2):
        t = (y - y1) / span
        alpha = round(a_from + (a_to - a_from) * (t * t * (3 - 2 * t)))
        draw.line([(0, y), (w, y)], fill=(*rgb, gd_alpha(alpha)))


def white_logo():
    f = share_image.logo_file()
    if not f:
        return None
    src = Image.open(f).convert("RGBA")
    white = Image.new("RGBA", src.size, (255, 255, 255, 0))
    white.putalpha(src.getchannel("A"))
    return white


_PHOTOS: dict = {}


def hd(url: str) -> str:
    """Version la plus grande d'une photo d'artiste pour les visuels 4K : Apple 2400 px, Commons 2400 px, avatar YouTube 1200 px."""
    url = str(url)
    if "mzstatic.com" in url:
        return re.sub(r"/[0-9]+x[0-9]+[a-z]*(-[0-9]+)?\.(jpg|jpeg|png|webp)$", "/2400x2400bb.jpg", url)
    if "Special:FilePath" in url:
        return re.sub(r"\?width=[0-9]+$", "", url) + "?width=2400"
    if "ggpht.com" in url or "googleusercontent.com" in url:
        return url.split("=")[0] + "=s1200"
    return url


def trim_bars(im: Image.Image) -> Image.Image:
    """Retire les bandes noires unies sur les bords (image de clip au format cinéma) : sinon le recadrage tombe dessus
    et coupe la tête. Ne touche pas une photo qui perdrait plus de la moitié de sa surface."""
    from PIL import ImageOps
    g = ImageOps.grayscale(im).point(lambda v: 255 if v > 18 else 0)
    box = g.getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) < im.width * im.height * 0.5:
        return im
    return im.crop(box) if box != (0, 0, im.width, im.height) else im


def photo(url):
    """Photo téléchargée une seule fois par adresse (un post la réutilise sur une vingtaine de visuels). Ne pas la modifier."""
    if not url or not str(url).startswith("https://"):
        return None
    url = hd(url)
    if url not in _PHOTOS:
        data = http_get(url, binary=True)
        im = None
        if data:
            try:
                im = Image.open(io.BytesIO(data))
                im.load()
                im = trim_bars(im.convert("RGB"))
            except Exception:  # noqa: BLE001
                im = None
        if len(_PHOTOS) > 64:
            _PHOTOS.clear()
        _PHOTOS[url] = im
    return _PHOTOS[url]


def paste_cover(img: Image.Image, src: Image.Image, w: int, h: int, top_ratio: float = 0.25) -> None:
    """Recadre la source pour remplir w × h (centrée horizontalement, un quart du surplus au-dessus)."""
    pw, ph = src.size
    scale = max(w / pw, h / ph)
    cw, ch = int(w / scale), int(h / scale)
    left, top = int((pw - cw) / 2), int((ph - ch) * top_ratio)
    img.paste(src.resize((w, h), Image.LANCZOS, box=(left, top, left + cw, top + ch)), (0, 0))


class Frame:
    """Toile 4K dont la mise en page s'écrit en px de la base 1080 (positions, tailles de police), × SCALE au dessin."""

    def __init__(self, base_w: int, base_h: int, safe: dict | None = None):
        self.bw, self.bh = base_w, base_h
        self.w, self.h = base_w * SCALE, base_h * SCALE
        safe = safe or {}
        self.top, self.bottom, self.side = safe.get("top", 0), safe.get("bottom", 0), safe.get("side", 0)

    @staticmethod
    def s(v) -> int:
        return round(v * SCALE)

    def text(self, draw, px: int, x, y, color, path: str, text: str) -> None:
        draw_text(draw, self.s(px), self.s(x), self.s(y), color, path, text)

    def width(self, text: str, path: str, px: int) -> float:
        return width(text, path, self.s(px)) / SCALE

    def fit(self, text: str, path: str, px: int, w) -> str:
        return fit_width(text, path, self.s(px), self.s(w))

    def wrap(self, text: str, path: str, px: int, w, mx: int) -> list:
        return wrap(text, path, self.s(px), self.s(w), mx)

    def rect(self, draw, x1, y1, x2, y2, fill) -> None:
        draw.rectangle([self.s(x1), self.s(y1), self.s(x2), self.s(y2)], fill=fill)

    def gradient(self, img: Image.Image, y1, y2, rgb, a_from: int, a_to: int) -> None:
        gradient(img, self.s(y1), self.s(y2), rgb, a_from, a_to, self.w)


def save_jpeg(img: Image.Image, file: Path) -> str | None:
    """JPEG haute qualité : un PNG 4K d'une photo pèse 15 à 25 Mo, sans gain visible après compression des réseaux."""
    out = file.with_suffix(".jpg")
    try:
        img.convert("RGB").save(out, "JPEG", quality=92, subsampling=0, optimize=True)
        return str(out)
    except OSError:
        return None


def headline(facts: dict) -> str:
    if facts["kind"] == "ranking":
        return facts["big"]
    return {"artist": (facts.get("artist") or {}).get("name"), "cauri_chart": "Top de la semaine",
            "platform_trends": "Les tendances"}.get(facts["kind"]) or "Spécial week-end"


def _pos(seen: list) -> str:
    return " · ".join(f"{s['platform']} {s['country']} n°{s['position']}" for s in seen[:2])


def items(facts: dict) -> list:
    out = []
    if facts["kind"] == "cauri_chart":
        for e in facts["top"]:
            pp = e.get("previous_position")
            move = ("+" + str(pp - e["position"]) if pp > e["position"] else "") if pp else "Nouveau"
            out.append({"rank": int(e["position"]), "title": e["title"], "detail": (e["artist"] + (" · " + move if move else "")).strip()})
    elif facts["kind"] == "ranking":
        for i, e in enumerate(facts["top"]):
            detail = e.get("detail") or ""
            if e.get("track_id"):  # titre : l'artiste d'abord, puis le détail chiffré
                detail = e["artist"] + (" · " + detail if detail else "")
            out.append({"rank": i + 1, "title": e.get("row_title") or e["title"], "detail": detail or e.get("artist") or ""})
    elif facts["kind"] == "artist":
        for i, t in enumerate(facts["tracks"]):
            out.append({"rank": i + 1, "title": t["title"], "detail": _pos(t["seen"])})
    else:
        for i, e in enumerate(facts["top"]):
            out.append({"rank": i + 1, "title": e["title"], "detail": e["artist"] + " · " + _pos(e["seen"])})
    return out


def _fmt_int(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def render(facts: dict, text: dict, name: str) -> dict:
    f = style(name)
    if not f:
        return {}
    DIR.mkdir(parents=True, exist_ok=True)
    ph = filtered(photo(facts.get("image")), f)
    rows_all = [{**it, "title": clean(it["title"]), "detail": clean(it["detail"])} for it in items(facts)]
    head = headline(facts)
    subtitle = clean(text["title"])
    if facts["kind"] == "artist":
        # Le nom est déjà en géant : sous-titre factuel
        fans = (facts.get("artist") or {}).get("deezer_fans")
        subtitle = "Artiste de la semaine" + (f" · {_fmt_int(fans)} fans sur Deezer" if fans else "")
    elif head.lower() in subtitle.lower() or subtitle.upper() == str(facts.get("label") or "").upper():
        subtitle = ""
    logo = white_logo()
    out = {}
    for fmt, L in LAYOUTS.items():
        fr = Frame(*L["size"], L["safe"])
        w, h = fr.bw, fr.bh  # base 1080
        img = Image.new("RGB", (fr.w, fr.h), (12, 8, 24))
        # 1. Photo en plein cadre, ou fond violet profond
        if ph:
            paste_cover(img, ph, fr.w, fr.h)
        else:
            fr.gradient(img, 0, h, f["base"], 0, 0)
        # 2. Dégradés : léger en haut (logo), fort en bas (textes)
        fr.gradient(img, 0, fr.top + int(h * 0.16), (0, 0, 0), 70, 127)
        fr.gradient(img, int(h * L["shade"]), h, f["shade"], 127, 8)
        draw = ImageDraw.Draw(img, "RGBA")
        pad = max(64, fr.side)
        white, soft, violet = (255, 255, 255, 255), (255, 255, 255, gd_alpha(35)), (*f["accent"], 255)
        # 3. En-tête (sous la barre de profil en 9:16) : logo blanc à gauche, rubrique à droite
        if logo:
            lw = fr.s(190)
            lg = logo.resize((lw, round(logo.size[1] * lw / logo.size[0])), Image.LANCZOS)
            img.paste(lg, (fr.s(pad), fr.s(fr.top + L["head"])), lg)
        label = str(facts.get("label") or facts["headline"]).upper()
        lwid = fr.width(label, f["bold"], 20) + 36
        lx, ly = w - pad - lwid, fr.top + L["head"] + 8
        fr.rect(draw, lx, ly, lx + lwid, ly + 44, violet)
        fr.text(draw, 20, lx + 18, ly + 30, (*f["on"], 255), f["bold"], label)
        # 4. Bas de l'image (au-dessus de la légende en 9:16), de bas en haut : source, liste, titre du post, titre géant
        y = h - fr.bottom - L["foot"]
        fr.text(draw, 17, pad, y, soft, f["sans"], fr.fit("Source : " + facts["source"], f["sans"], 17, w - 2 * pad))
        y -= L["src_gap"]
        if len(rows_all) > L["rows"]:
            # Liste longue (Top 20 demandé) : tous les titres, en deux colonnes compactes, sans détail
            rows = rows_all[:20]
            half = (len(rows) + 1) // 2
            row_h, gap = (44 if fmt == "post" else 52), 28
            col_w = (w - 2 * pad - gap) / 2
            list_top = y - half * row_h
            for i, row in enumerate(rows):
                cx, ry = pad + (i // half) * (col_w + gap), list_top + (i % half) * row_h
                if i % half:
                    fr.rect(draw, cx, ry, cx + col_w, ry + 1, (255, 255, 255, gd_alpha(100)))
                px = 22 if fmt == "post" else 25
                fr.text(draw, px + 6, cx, ry + row_h * 0.72, violet, f["display"], str(row["rank"]))
                num_w = fr.width("20", f["display"], px + 6) + 12  # place du rang à deux chiffres, quelle que soit la police
                tx = cx + num_w
                fr.text(draw, px, tx, ry + row_h * 0.72, white, f["bold"], fr.fit(row["title"], f["bold"], px, col_w - num_w))
        else:
            rows = rows_all[: L["rows"]]
            row_h = L["row_h"]
            rank_px, rank_dy = L["rank"]
            title_px, title_dy = L["title"]
            detail_px, detail_dy = L["detail"]
            list_top = y - len(rows) * row_h
            for i, row in enumerate(rows):
                ry = list_top + i * row_h
                if i > 0:
                    fr.rect(draw, pad, ry, w - pad, ry + 1, (255, 255, 255, gd_alpha(100)))
                fr.text(draw, rank_px, pad, ry + rank_dy, violet, f["display"], str(row["rank"]))
                tx = pad + L["tx"]
                max_w = w - tx - pad
                fr.text(draw, title_px, tx, ry + title_dy, white, f["bold"], fr.fit(row["title"], f["bold"], title_px, max_w))
                fr.text(draw, detail_px, tx, ry + detail_dy, soft, f["sans"], fr.fit(row["detail"], f["sans"], detail_px, max_w))
        y = list_top - L["sub_gap"]
        if subtitle != "":
            size = L["sub"]
            for line in reversed(fr.wrap(subtitle, f["bold"], size, w - 2 * pad, 2)):
                fr.text(draw, size, pad, y, violet, f["bold"], line)
                y -= int(size * 1.3)
            y -= L["sub_after"]
        big = L["big"]
        big_lines = fr.wrap(head.upper(), f["display"], big, w - 2 * pad, 2)
        if len(big_lines) > 1 or fr.width(big_lines[0] if big_lines else "", f["display"], big) > w - 2 * pad:
            big = int(big * 0.78)
            big_lines = fr.wrap(head.upper(), f["display"], big, w - 2 * pad, 3)  # titre long : trois lignes plutôt que coupé
        for line in reversed(big_lines):
            fr.text(draw, big, pad - 4, y, white, f["display"], line)
            y -= int(big * 1.05)
        saved = save_jpeg(img, DIR / f"{name}-{fmt}.jpg")
        if saved:
            out[fmt] = Path(saved).name
    return out


# Mise en page des visuels uniques (px de la base 1080) : post du fil 4:5 et story 9:16
LAYOUTS = {
    "post": {"size": (1080, 1350), "safe": None, "shade": 0.20, "head": 52, "foot": 60, "src_gap": 46, "rows": 5, "row_h": 84,
             "rank": (46, 64), "tx": 80, "title": (30, 38), "detail": (21, 70), "sub_gap": 30, "sub": 32, "sub_after": 16, "big": 122},
    "story": {"size": (1080, 1920), "safe": SAFE_916, "shade": 0.26, "head": 20, "foot": 16, "src_gap": 52, "rows": 5, "row_h": 104,
              "rank": (56, 76), "tx": 92, "title": (33, 45), "detail": (23, 83), "sub_gap": 38, "sub": 36, "sub_after": 22, "big": 140},
}
