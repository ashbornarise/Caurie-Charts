"""Aperçus de liens (Open Graph, 1200 × 630) générés pour chaque page : WhatsApp, Facebook, X, LinkedIn, Telegram.

  classement : le nom du classement et son Top 3 avec les pochettes ;
  titre      : la pochette, le titre, l'artiste et sa meilleure place ;
  artiste    : la photo, le nom, le pays et ses chiffres YouTube ;
  défaut     : la marque et la promesse du site.
Les images sont servies avec un cache d'un jour : chaque aperçu n'est calculé qu'une fois par jour.
"""
import io

from PIL import Image, ImageDraw, ImageFilter

from core.helpers import country_name
from core.services.social import image as PI

W, H = 1200, 630
INK, WHITE, VIOLET, GOLD, GREY = (14, 12, 20), (255, 255, 255), (139, 82, 255), (255, 196, 40), (190, 184, 205)
ANTON, BOLD, SANS = (str(PI.FONT_DIR / n) for n in ("Anton-Regular.ttf", "Poppins-Bold.ttf", "Poppins-Regular.ttf"))


def _font(path, px):
    return PI.font(path, px)


def _fit(text: str, path: str, px: int, width: int) -> tuple[str, int]:
    while px > 18 and _font(path, px).getlength(text) > width:
        px -= 2
    while _font(path, px).getlength(text) > width and len(text) > 4:
        text = text[:-2].rstrip() + "…"
    return text, px


def _square(url, size: int) -> Image.Image | None:
    ph = PI.photo(url) if url else None
    if ph is None:
        return None
    img = Image.new("RGB", (size, size))
    PI.paste_cover(img, ph, size, size, 0.2)
    return img


def _brand(d: ImageDraw.ImageDraw, img: Image.Image, dark: bool = True) -> None:
    logo = PI.white_logo()
    if logo:
        lg = logo.resize((150, round(logo.size[1] * 150 / logo.size[0])), Image.LANCZOS)
        img.paste(lg, (60, 46), lg)
    d.text((W - 60, 78), "cauricharts.com", font=_font(BOLD, 22), fill=GREY, anchor="rs")


def _base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), INK)
    glow = Image.new("RGB", (W, H), (60, 30, 130)).filter(ImageFilter.GaussianBlur(2))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([W - 700, -300, W + 300, 500], fill=150)
    img.paste(glow, (0, 0), mask.filter(ImageFilter.GaussianBlur(120)))
    return img, ImageDraw.Draw(img, "RGBA")


def chart(title: str, subtitle: str, rows: list) -> Image.Image:
    img, d = _base()
    _brand(d, img)
    t, px = _fit(title.upper(), ANTON, 64, W - 120)
    d.text((60, 190), t, font=_font(ANTON, px), fill=WHITE, anchor="ls")
    d.text((60, 232), subtitle, font=_font(SANS, 24), fill=GREY, anchor="ls")
    x, size = 60, 200
    for i, r in enumerate(rows[:3]):
        cover = _square(r.get("cover_url") or r.get("artist_image"), size)
        if cover:
            img.paste(cover, (x, 280))
        else:
            d.rectangle([x, 280, x + size, 280 + size], fill=(40, 34, 60))
        d.rectangle([x, 280 + size - 52, x + 52, 280 + size], fill=GOLD)
        d.text((x + 26, 280 + size - 10), str(r.get("rank") or i + 1), font=_font(ANTON, 40), fill=INK, anchor="ms")
        name, npx = _fit(r.get("title") or r.get("artist_name") or "", BOLD, 26, 340)
        d.text((x, 280 + size + 40), name, font=_font(BOLD, npx), fill=WHITE, anchor="ls")
        who, wpx = _fit(r.get("artist_name") or "", SANS, 20, 340)
        d.text((x, 280 + size + 68), who, font=_font(SANS, wpx), fill=GREY, anchor="ls")
        x += 370
    return img


def card(title: str, lines: list, photo_url, tag: str) -> Image.Image:
    """Grande photo à gauche, texte à droite (titre ou artiste)."""
    img, d = _base()
    ph = _square(photo_url, H)
    if ph:
        img.paste(ph, (0, 0))
        shade = Image.new("L", (1, 256))
        shade.putdata([int(255 * (i / 255) ** 1.4) for i in range(256)])
        img.paste(Image.new("RGB", (340, H), INK), (H - 340, 0), shade.rotate(-90, expand=True).resize((340, H)))
    x = H + 30 if ph else 60
    width = W - x - 60
    logo = PI.white_logo()
    if logo:
        lg = logo.resize((140, round(logo.size[1] * 140 / logo.size[0])), Image.LANCZOS)
        img.paste(lg, (x, 50), lg)
    tw = _font(BOLD, 22).getlength(tag) + 28
    d.rectangle([x, 150, x + tw, 190], fill=GOLD)
    d.text((x + 14, 179), tag, font=_font(BOLD, 22), fill=INK, anchor="ls")
    t, px = _fit(title.upper(), ANTON, 76, width)
    d.text((x - 2, 290), t, font=_font(ANTON, px), fill=WHITE, anchor="ls")
    y = 350
    for i, line in enumerate(lines[:4]):
        txt, lpx = _fit(line, BOLD if i == 0 else SANS, 28 if i == 0 else 24, width)
        d.text((x, y), txt, font=_font(BOLD if i == 0 else SANS, lpx), fill=WHITE if i == 0 else GREY, anchor="ls")
        y += 46
    d.text((x, H - 50), "cauricharts.com", font=_font(BOLD, 22), fill=GREY, anchor="ls")
    return img


def default() -> Image.Image:
    img, d = _base()
    _brand(d, img)
    d.text((60, 300), "LE CLASSEMENT MUSICAL", font=_font(ANTON, 84), fill=WHITE, anchor="ls")
    d.text((60, 390), "DE L’AFRIQUE DE L’OUEST", font=_font(ANTON, 84), fill=GOLD, anchor="ls")
    d.text((60, 460), "16 pays · Apple Music, Deezer, Shazam, YouTube · chaque semaine", font=_font(SANS, 28), fill=GREY, anchor="ls")
    return img


def jpeg(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=86, optimize=True)
    return out.getvalue()


def for_page(kind: str, key: str) -> bytes:
    from core import db, repos
    from core.services import live_chart
    if kind == "classement":
        country = None if key == "wa" else repos.country(key)
        rows = [r for r in live_chart.build(country["id"] if country else None, None, 3, "prime", 20, "latest")["rows"] if not r.get("is_artist")]
        name = "Top 20 Afrique de l’Ouest" if not country else f"Top {country['chart_size']} {country_name(country['code'])}"
        return jpeg(chart(name, "Le classement en direct · Cauri Charts", rows))
    if kind == "titre":
        tr = repos.track(key)
        if tr:
            best = db.one("""SELECT o.position, o.source, c.code FROM chart_observations o JOIN countries c ON c.id = o.country_id
                             WHERE o.track_id = ? ORDER BY o.position, o.observed_on DESC LIMIT 1""", [tr["id"]])
            lines = [tr["artist_name"]]
            if best:
                lines.append(f"Meilleure place : n°{best['position']} {live_chart.SOURCES.get(best['source'], best['source'])} {country_name(best['code'])}")
            return jpeg(card(tr["title"], lines, tr.get("cover_url"), "TITRE"))
    if kind == "artiste":
        a = repos.artist(key)
        if a:
            lines = [country_name(a.get("country_code")) if a.get("country_code") else "Afrique de l’Ouest"]
            if a.get("youtube_views_total"):
                lines.append(f"{int(a['youtube_views_total']):,} vues sur YouTube".replace(",", " "))
            if a.get("youtube_subscribers"):
                lines.append(f"{int(a['youtube_subscribers']):,} abonnés".replace(",", " "))
            return jpeg(card(a["name"], lines, a.get("image_hd_url") or a.get("image_url"), "ARTISTE"))
    return jpeg(default())
