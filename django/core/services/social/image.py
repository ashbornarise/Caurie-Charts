"""Visuels des posts, esprit magazine de classements (traduction de Social\\PostImage, GD → Pillow).

Photo de l'artiste en plein cadre, dégradé sombre, titre géant en Anton (police libre OFL, resources/fonts),
titre du post, puis la liste des meilleures performances. Formats : carré 1080 × 1080 et story 1080 × 1920.
"""
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.services import share_image
from core.services.news import http_get

REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
DIR = REPO / "public" / "media" / "social"
FORMATS = {"square": (1080, 1080), "story": (1080, 1920)}
VIOLET = (139, 82, 255)
_FONTS: dict = {}


def gd_alpha(a: int) -> int:
    """Transparence GD (0 opaque … 127 transparent) → opacité Pillow (255 … 0)."""
    return 255 - round(max(0, min(127, a)) * 255 / 127)


def font(path: str, px: int) -> ImageFont.FreeTypeFont:
    key = (path, px)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(path, px)
    return _FONTS[key]


def fonts() -> dict | None:
    f = share_image.fonts()
    if not f:
        return None
    anton = REPO / "resources" / "fonts" / "Anton-Regular.ttf"
    return {**f, "display": str(anton) if anton.is_file() else f["bold"]}


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


def photo(url):
    if not url or not str(url).startswith("https://"):
        return None
    data = http_get(url, binary=True)
    if not data:
        return None
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        return im.convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def paste_cover(img: Image.Image, src: Image.Image, w: int, h: int, top_ratio: float = 0.25) -> None:
    """Recadre la source pour remplir w × h (centrée horizontalement, un quart du surplus au-dessus)."""
    pw, ph = src.size
    scale = max(w / pw, h / ph)
    cw, ch = int(w / scale), int(h / scale)
    left, top = int((pw - cw) / 2), int((ph - ch) * top_ratio)
    img.paste(src.resize((w, h), Image.LANCZOS, box=(left, top, left + cw, top + ch)), (0, 0))


def headline(facts: dict) -> str:
    return {"artist": (facts.get("artist") or {}).get("name"), "cauri_chart": "Top de la semaine",
            "platform_trends": "Les tendances"}.get(facts["kind"]) or "Spécial week-end"


def _pos(seen: list) -> str:
    return " · ".join(f"{s['platform']} {s['country']} n°{s['position']}" for s in seen[:2])


def items(facts: dict) -> list:
    out = []
    if facts["kind"] == "cauri_chart":
        for e in facts["top"]:
            pp = e.get("previous_position")
            move = ("▲ " + str(pp - e["position"]) if pp > e["position"] else "") if pp else "Nouveau"
            out.append({"rank": int(e["position"]), "title": e["title"], "detail": (e["artist"] + (" · " + move if move else "")).strip()})
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
    f = fonts()
    if not f:
        return {}
    DIR.mkdir(parents=True, exist_ok=True)
    ph = photo(facts.get("image"))
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
    for fmt, (w, h) in FORMATS.items():
        story = fmt == "story"
        img = Image.new("RGB", (w, h), (12, 8, 24))
        # 1. Photo en plein cadre, ou fond violet profond
        if ph:
            paste_cover(img, ph, w, h)
        else:
            gradient(img, 0, h, (42, 14, 120), 0, 0, w)
        # 2. Dégradés : léger en haut (logo), fort en bas (textes)
        gradient(img, 0, int(h * 0.16), (0, 0, 0), 70, 127, w)
        gradient(img, int(h * (0.30 if story else 0.18)), h, (8, 5, 18), 127, 8, w)
        draw = ImageDraw.Draw(img, "RGBA")
        pad = 64
        white, soft, violet = (255, 255, 255, 255), (255, 255, 255, gd_alpha(35)), (*VIOLET, 255)
        # 3. En-tête : logo blanc à gauche, rubrique à droite
        if logo:
            lw = 190
            lh = round(logo.size[1] * lw / logo.size[0])
            lg = logo.resize((lw, lh), Image.LANCZOS)
            img.paste(lg, (pad, 110 if story else 52), lg)
        label = str(facts.get("label") or facts["headline"]).upper()
        lwid = width(label, f["bold"], 20) + 36
        lx, ly = w - pad - lwid, 118 if story else 60
        draw.rectangle([lx, ly, lx + lwid, ly + 44], fill=violet)
        draw_text(draw, 20, lx + 18, ly + 30, white, f["bold"], label)
        # 4. Bas de l'image, de bas en haut : source, liste, titre du post, titre géant
        y = h - (150 if story else 56)
        draw_text(draw, 17, pad, y, soft, f["sans"], fit_width("Source : " + facts["source"], f["sans"], 17, w - 2 * pad))
        y -= 56 if story else 44
        rows = rows_all[: 5 if story else 4]
        row_h = 108 if story else 78
        list_top = y - len(rows) * row_h
        for i, row in enumerate(rows):
            ry = list_top + i * row_h
            if i > 0:
                draw.rectangle([pad, ry, w - pad, ry + 1], fill=(255, 255, 255, gd_alpha(100)))
            draw_text(draw, 58 if story else 44, pad, ry + (78 if story else 60), violet, f["display"], str(row["rank"]))
            tx = pad + (96 if story else 78)
            max_w = w - tx - pad
            draw_text(draw, 34 if story else 28, tx, ry + (46 if story else 36), white, f["bold"], fit_width(row["title"], f["bold"], 34 if story else 28, max_w))
            draw_text(draw, 24 if story else 20, tx, ry + (86 if story else 66), soft, f["sans"], fit_width(row["detail"], f["sans"], 24 if story else 20, max_w))
        y = list_top - (40 if story else 26)
        if subtitle != "":
            size = 38 if story else 30
            for line in reversed(wrap(subtitle, f["bold"], size, w - 2 * pad, 2)):
                draw_text(draw, size, pad, y, violet, f["bold"], line)
                y -= int(size * 1.3)
            y -= 24 if story else 14
        big = 150 if story else 112
        big_lines = wrap(head.upper(), f["display"], big, w - 2 * pad, 2)
        if len(big_lines) > 1 or width(big_lines[0] if big_lines else "", f["display"], big) > w - 2 * pad:
            big = int(big * 0.78)
            big_lines = wrap(head.upper(), f["display"], big, w - 2 * pad, 2)
        for line in reversed(big_lines):
            draw_text(draw, big, pad - 4, y, white, f["display"], line)
            y -= int(big * 1.05)
        file = f"{name}-{fmt}.png"
        img.save(DIR / file, "PNG", compress_level=6)
        out[fmt] = file
    return out
