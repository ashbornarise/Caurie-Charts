"""Images de partage d'un classement (traduction de Services\\ShareImage).

Formats : carré 1080 x 1080 et story 1080 x 1920. Une seule mise en page (liste d'opérations de dessin)
rendue en PNG avec Pillow, ou en SVG si les polices TTF manquent.
"""
import base64
import io
from pathlib import Path

from core import conf
from core.helpers import brand, chart_name, country_name, e, movement, period_label, url_host
from core.i18n import t

FORMATS = {"square": (1080, 1080), "story": (1080, 1920)}
INK, ACCENT, MUTED, LINE = "#111111", "#8B52FF", "#6B6B6B", "#E5E5E5"
REPO = Path(__file__).resolve().parent.parent.parent.parent


def fonts() -> dict | None:
    fdir = REPO / "resources" / "fonts"
    serif = [conf.get("app.share.font_serif"), fdir / "serif-bold.ttf", fdir / "PT_Serif-Web-Bold.ttf", "C:/Windows/Fonts/georgiab.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSerif-Bold.ttf"]
    sans = [conf.get("app.share.font_sans"), fdir / "sans.ttf", fdir / "PT_Sans-Web-Regular.ttf", "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]
    bold = [fdir / "sans-bold.ttf", fdir / "PT_Sans-Web-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]

    def pick(lst):
        return next((str(p) for p in lst if p and Path(p).is_file()), None)
    found = {"serif": pick(serif), "sans": pick(sans)}
    found["bold"] = pick(bold) or found["sans"]
    return None if None in found.values() else found


def png_available() -> bool:
    return fonts() is not None


def logo_file() -> Path | None:
    f = REPO / "public" / "assets" / "img" / "brand" / "logo-share.png"
    return f if f.is_file() else None


def _fit(text: str, n: int) -> str:
    return text[: n - 1].rstrip() + "…" if len(text) > n else text


def layout(run: dict, entries: list[dict], fmt: str) -> list:
    w, h = FORMATS[fmt]
    story = fmt == "story"
    pad = 72
    ops = [("rect", 0, 0, w, h, "#FFFFFF")]
    y = 200 if story else 110
    logo = logo_file()
    if logo:
        # Logo horizontal (900 x 396) : hauteur 110 px en carré, 150 px en story
        lh = 150 if story else 110
        ops.append(("image", pad, y - (90 if story else 70), int(round(lh * 900 / 396)), lh, logo))
        y += 40 if story else 30
    else:
        ops.append(("text", pad, y, 34, "bold", INK, brand().upper()))
        ops.append(("rect", pad, y + 26, 64, 8, ACCENT))
    y += 150 if story else 110
    if run["chart_code"] == "prime-wa":
        title = country_name("WA") + " · Top " + str(len(entries[:20]))
    else:
        title = chart_name(run["chart_code"]) + " · " + country_name(run["country_code"])
    ops.append(("text", pad, y, 72 if story else 58, "serif", INK, _fit(title, 24 if story else 28)))
    y += 66 if story else 54
    ops.append(("text", pad, y, 30, "sans", MUTED, period_label(run)))
    y += 80 if story else 50

    row_h = 116 if story else 64
    for i, en in enumerate(entries[:10]):
        top = y + i * row_h
        if i == 0:
            ops.append(("rect", pad - 20, top, w - 2 * pad + 40, row_h - 8, ACCENT))
        else:
            ops.append(("rect", pad, top - 4, w - 2 * pad, 2, LINE))
        base = top + int(row_h * 0.62)
        ops.append(("text", pad, base, 56 if story else 38, "serif", INK, str(en["position"])))
        label = en["title"] if en["track_id"] else en["artist_name"]
        sub = en["artist_name"] if en["track_id"] else ""
        if story and sub:
            ops.append(("text", pad + 110, base - 14, 40, "bold", INK, _fit(label, 30)))
            ops.append(("text", pad + 110, base + 30, 30, "sans", INK if i == 0 else MUTED, _fit(sub, 40)))
        else:
            text = _fit(label, 26) + "  ·  " + _fit(sub, 22) if sub else _fit(label, 44)
            ops.append(("text", pad + 90, base, 30, "bold", INK, text))
        m = movement(en)
        move = {"up": f"+{m['value']}", "down": f"-{m['value']}", "same": "=",
                "new": t("move.new_short"), "re": t("move.re_short")}[m["type"]]
        ops.append(("text", w - pad, base, 32 if story else 26, "bold", INK if i == 0 else MUTED, move, "end"))

    footer = h - (170 if story else 56)
    ops.append(("text", pad, footer, 26, "sans", MUTED, t("share.footer")))
    ops.append(("text", w - pad, footer, 26, "bold", INK, url_host(conf.get("app.url")), "end"))
    return ops


def render_svg(ops: list, fmt: str) -> bytes:
    w, h = FORMATS[fmt]
    families = {"serif": "Georgia, 'Times New Roman', serif", "sans": "Arial, Helvetica, sans-serif",
                "bold": "Arial, Helvetica, sans-serif"}
    out = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    for op in ops:
        if op[0] == "rect":
            out += f'<rect x="{op[1]}" y="{op[2]}" width="{op[3]}" height="{op[4]}" fill="{op[5]}"/>'
        elif op[0] == "image":
            data = base64.b64encode(Path(op[5]).read_bytes()).decode()
            out += f'<image x="{op[1]}" y="{op[2]}" width="{op[3]}" height="{op[4]}" href="data:image/png;base64,{data}"/>'
        else:
            anchor = ' text-anchor="end"' if len(op) > 7 and op[7] == "end" else ""
            weight = ' font-weight="700"' if op[4] in ("bold", "serif") else ""
            out += (f'<text x="{op[1]}" y="{op[2]}" font-size="{op[3]}" font-family="{e(families[op[4]])}" '
                    f'fill="{op[5]}"{weight}{anchor}>{e(op[6])}</text>')
    return (out + "</svg>").encode()


def render_png(ops: list, fmt: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    w, h = FORMATS[fmt]
    f = fonts()
    img = Image.new("RGB", (w, h), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    cache: dict = {}
    for op in ops:
        if op[0] == "rect":
            draw.rectangle([op[1], op[2], op[1] + op[3] - 1, op[2] + op[4] - 1], fill=op[5])
        elif op[0] == "image":
            src = Image.open(op[5]).convert("RGBA").resize((op[3], op[4]), Image.LANCZOS)
            img.paste(src, (op[1], op[2]), src)
        else:
            key = (op[4], op[3])
            if key not in cache:
                cache[key] = ImageFont.truetype(f[op[4]], op[3])
            anchor = "rs" if len(op) > 7 and op[7] == "end" else "ls"
            draw.text((op[1], op[2]), op[6], font=cache[key], fill=op[5], anchor=anchor)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
