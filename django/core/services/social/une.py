"""Une de magazine réaliste : la photo entière de l'artiste, le titre CAURI derrière sa tête, « CHARTS » vertical.

Seule la tête repasse devant le bas des lettres (détourage rembg limité à la bande du titre) : une imperfection du
détourage ailleurs ne se voit pas. Le titre est blanc ou noir selon la photo, un voile et un dégradé assurent le
contraste. Formats 4:5 et 9:16 (zones de l'application respectées). Sans rembg installé, None : l'ancienne une sert.
"""
import io

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageStat

from core.services.social import image as PI

GOLD, INK, WHITE = (255, 196, 40), (17, 17, 17), (255, 255, 255)
_SESSION = None


def available() -> bool:
    try:
        import rembg  # noqa: F401
        return True
    except ImportError:
        return False


def _mask(src: Image.Image) -> Image.Image:
    global _SESSION
    from rembg import new_session, remove
    if _SESSION is None:
        _SESSION = new_session("isnet-general-use")
    return remove(src, session=_SESSION, only_mask=True).convert("L")


def _lum(rgb) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def cover(fr: PI.Frame, f: dict, cover: dict, photo_url, total: int) -> Image.Image | None:
    src = PI.photo(photo_url)
    if src is None or not available():
        return None
    S = PI.SCALE
    bw, bh, W, H = fr.bw, fr.bh, fr.w, fr.h
    display, bold = str(PI.FONT_DIR / "Anton-Regular.ttf"), str(PI.FONT_DIR / "Poppins-Bold.ttf")
    mask = _mask(src)
    box = mask.point(lambda x: 255 if x > 60 else 0).getbbox() or (0, 0, src.width, src.height)
    pad, my = max(48, fr.side), fr.top + 34
    # Titre CAURI + « CHARTS » vertical collé à droite
    size = 300
    while fr.width("CAURI", display, size) + 14 + 34 * 1.3 > bw - 2 * pad:
        size -= 4
    cap, mast_w = size * 0.72, fr.width("CAURI", display, size)
    base = my + size * 0.86
    # Cadrage : la tête commence aux deux tiers de la hauteur des lettres (elle ne mord que le bas du titre)
    head_target = (base - cap * 0.34) * S
    scale = max(W / src.width, H / src.height)
    for _ in range(6):
        sh = int(src.height * scale)
        top = int(box[1] * scale - head_target)
        if top + H <= sh:
            break
        scale *= 1.12
    sw, sh = int(src.width * scale), int(src.height * scale)
    left = int(min(max(0, (box[0] + box[2]) / 2 * scale - W / 2), sw - W))
    big, bigm = src.resize((sw, sh), Image.LANCZOS), mask.resize((sw, sh), Image.LANCZOS)
    if top < 0:
        # Décor prolongé au-dessus de la tête : haut de la photo en miroir, très flou, fondu vers la vraie photo
        need, blend = -top, 200 * S
        ext = Image.new("RGB", (sw, sh + need))
        mirror = ImageOps.flip(big.crop((0, 0, sw, min(sh, need + blend)))).resize((sw, need + blend))
        ext.paste(mirror.filter(ImageFilter.GaussianBlur(40 * S)), (0, 0))
        ramp = Image.new("L", (1, blend))
        ramp.putdata([int(255 * (i / (blend - 1)) ** 1.2) for i in range(blend)])
        fade = Image.new("L", (sw, sh), 255)
        fade.paste(ramp.resize((sw, blend)), (0, 0))
        ext.paste(big, (0, need), fade)
        mext = Image.new("L", ext.size, 0)
        mext.paste(bigm, (0, need))
        big, bigm, top = ext, mext, 0
    photo = big.crop((left, top, left + W, top + H))
    photo = ImageEnhance.Color(ImageEnhance.Contrast(photo).enhance(1.08)).enhance(1.06)
    photo = photo.filter(ImageFilter.UnsharpMask(radius=2 * S, percent=70, threshold=3))
    m = bigm.crop((left, top, left + W, top + H))
    img = photo.copy()
    band = (0, 0, W, int((base + 24) * S))
    light = _lum(ImageStat.Stat(photo.crop(band)).mean) > 150
    ink = INK if light else WHITE
    veil = Image.new("L", (1, 256))
    veil.putdata([int(255 * (1 - i / 255) ** 1.4) for i in range(256)])
    shade = veil.resize((W, int(H * 0.30)))
    img.paste(Image.new("RGB", shade.size, WHITE if light else (0, 0, 0)), (0, 0), shade.point(lambda x: int(x * 0.35)))
    d = ImageDraw.Draw(img, "RGBA")
    fr.text(d, size, pad, base, (*ink, 255), display, "CAURI")
    vs = 40
    while fr.width("CHARTS", bold, vs) > cap and vs > 14:
        vs -= 1
    v = Image.new("RGBA", (int(fr.width("CHARTS", bold, vs) * S) + 4, int(vs * 1.3 * S)), (0, 0, 0, 0))
    ImageDraw.Draw(v).text((0, int(vs * 1.02 * S)), "CHARTS", font=PI.font(bold, int(vs * S)), fill=(*ink, 255), anchor="ls")
    v = v.rotate(90, expand=True)
    img.paste(v, (int((pad + mast_w + 10) * S), int((base - cap) * S + (cap * S - v.height))), v)
    # La tête repasse devant le bas du titre
    head = m.crop(band).filter(ImageFilter.GaussianBlur(1.2 * S))
    fade = Image.new("L", head.size, 0)
    fd = ImageDraw.Draw(fade)
    edge = 24 * S
    for y in range(head.height):
        fd.line([(0, y), (head.width, y)], fill=255 if y < head.height - edge else int(255 * (head.height - y) / edge))
    img.paste(photo.crop(band), (0, 0), Image.composite(head, Image.new("L", head.size, 0), fade))
    # Dégradé noir en bas, nom en très gros, étiquettes or
    g = Image.new("L", (1, 256))
    g.putdata([int(255 * (i / 255) ** 1.5) for i in range(256)])
    zone = int(H * 0.42)
    img.paste(Image.new("RGB", (W, zone), (8, 6, 10)), (0, H - zone), g.resize((W, zone)).point(lambda x: int(x * 0.92)))
    d = ImageDraw.Draw(img, "RGBA")
    name = PI.clean(cover["headline"]).upper()
    words, lines, bigpx = name.split(), [name], 230
    while fr.width(max(lines, key=len), display, bigpx) > bw - 2 * pad and bigpx > 90:
        bigpx -= 6
        if bigpx < 180 and len(words) > 1 and len(lines) == 1:
            lines, bigpx = [" ".join(words[: (len(words) + 1) // 2]), " ".join(words[(len(words) + 1) // 2:])], 230
    y = bh - fr.bottom - 56
    for line in reversed(lines):
        fr.text(d, bigpx, pad, y, (*WHITE, 255), display, line)
        y -= bigpx * 0.96
    ty = y - 6
    tags = [t for t in (PI.clean(cover.get("kicker") or "").upper(), PI.clean(cover.get("subtitle") or "").upper()) if t]
    for i, t in enumerate(reversed(tags)):
        px = 30 if i == len(tags) - 1 else 24
        t = fr.fit(t, bold, px, bw - 2 * pad - 30)
        tw, hgt = fr.width(t, bold, px) + 26, px * 1.4
        fr.rect(d, bw - pad - tw, ty - hgt, bw - pad, ty, (*GOLD, 255))
        fr.text(d, px, bw - pad - tw + 13, ty - hgt * 0.27, (*INK, 255), bold, t)
        ty -= hgt + 8
    fr.text(d, 18, pad, bh - fr.bottom - 22, (255, 255, 255, 210), bold, f"cauricharts.com · {total - 1} à découvrir, glissez")
    noise = Image.merge("RGB", [Image.effect_noise(img.size, 40).convert("L")] * 3)
    return Image.blend(img, ImageOps.autocontrast(noise), 7 / 255)
