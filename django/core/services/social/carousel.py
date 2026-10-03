"""Carrousel façon magazine et vidéo du Top, en 4K (traduction de Social\\PostCarousel, GD → Pillow).

Deux jeux de diapositives : 4:5 (2160 × 2700, carrousel Instagram et Facebook) et 9:16 (2160 × 3840, carrousel
photo TikTok), et une vidéo 9:16 (Reels Instagram et Facebook, TikTok). En 9:16, les textes restent hors des zones
couvertes par l'interface des applications (image.SAFE_916).

Couverture, puis une diapositive par performance avec un chiffre exact. Vidéo (ffmpeg, facultatif) :
titre avec clip officiel fourni par l'artiste ou le label (dossier Clips) → 30 s de clip avec le classement
par-dessus ; sinon photo avec un lent zoom. Jamais de clip téléchargé sur YouTube.
"""
import glob
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from core import conf, env
from core.services.imports import normalizer as N
from core.services.platforms import log_write
from core.services.social import image as PI

FORMATS = {"feed": ((1080, 1350), None), "tiktok": ((1080, 1920), PI.SAFE_916)}
VIDEO = "tiktok"  # la vidéo reprend les diapositives 9:16
MAX_SLIDES = 20  # limite d'Instagram pour un carrousel


def render(facts: dict, cover: dict, items: list, name: str) -> dict:
    """{"slides": [4:5], "slides_916": [9:16], "video": mp4 9:16 ou None, "cover": bool}.
    Instagram accepte 20 images par carrousel : à partir de 20 titres, pas de couverture, tous les titres passent."""
    with_cover = len(items) < MAX_SLIDES
    f = PI.style(name)
    if not f:
        return {"slides": [], "slides_916": [], "video": None, "cover": with_cover}
    PI.DIR.mkdir(parents=True, exist_ok=True)
    items = items[:MAX_SLIDES]
    total = len(items) + 1
    cover_photo = facts.get("image") or (items[0].get("image") if items else None)
    out, segments = {}, []
    for fmt, (size, safe) in FORMATS.items():
        fr = PI.Frame(*size, safe)
        suffix = "" if fmt == "feed" else "-916"
        slides = [PI.save_jpeg(_best_cover(fr, f, cover, cover_photo, total), PI.DIR / f"{name}-1{suffix}.jpg")] if with_cover else []
        if fmt == VIDEO and slides:
            segments.append({"image": slides[0]})
        for i, item in enumerate(items):
            slide = PI.save_jpeg(_item_slide(fr, f, item, i + 2, total, facts["source"], variant=slide_variant(name)),
                                 PI.DIR / f"{name}-{i + 2}{suffix}.jpg")
            slides.append(slide)
            if fmt != VIDEO:
                continue
            clip = find_clip(item)
            if clip:
                # Clip fourni par l'artiste ou le label : il passe en fond, classement et chiffres par-dessus
                overlay = PI.DIR / f"{name}-{i + 2}-calque.png"
                _item_slide(fr, f, item, i + 2, total, facts["source"], transparent=True).save(overlay, "PNG")
                segments.append({"clip": clip, "overlay": str(overlay)})
            else:
                segments.append({"image": slide})
        out[fmt] = [os.path.basename(s) for s in slides if s]
    fr = PI.Frame(*FORMATS[VIDEO][0])
    return {"slides": out["feed"], "slides_916": out["tiktok"], "video": _video(segments, PI.DIR / f"{name}.mp4", fr.w, fr.h),
            "cover": with_cover}


def clips_dir() -> str:
    d = env.get("SOCIAL_CLIPS_DIR", "") or ""
    if not d and env.get("SOCIAL_EXPORT_DIR", ""):
        d = env.get("SOCIAL_EXPORT_DIR").rstrip("/\\") + "/Clips"
    return d


def find_clip(item: dict):
    """Fichier vidéo du dossier des clips dont le nom contient l'artiste et le titre (« Himra - DJOROBITE.mp4 »)."""
    d = clips_dir()
    if not d or not os.path.isdir(d):
        return None
    artist = N.text(item["artist"]).replace(" ", "")
    title = N.title(item["title"]).replace(" ", "")
    files = []
    for ext in ("mp4", "mov", "m4v", "webm", "MP4", "MOV"):
        files += sorted(glob.glob(os.path.join(d.rstrip("/\\"), f"*.{ext}")))
    for file in files:
        n = N.text(Path(file).stem).replace(" ", "")
        if title and title in n and artist in n:
            return file
    return None


def _canvas(fr: PI.Frame, f: dict, photo_url, transparent: bool = False):
    if transparent:
        # Calque posé sur un clip : fond transparent, seuls les dégradés et les textes sont dessinés
        return Image.new("RGBA", (fr.w, fr.h), (0, 0, 0, 0))
    img = Image.new("RGB", (fr.w, fr.h), f["shade"])
    ph = PI.filtered(PI.photo(photo_url), f)
    if ph:
        PI.paste_cover(img, ph, fr.w, fr.h)
    else:
        fr.gradient(img, 0, fr.bh, f["base"], 90, 0)
    return img


def _blur_zone(fr: PI.Frame, img: Image.Image, y1: int, y2: int, top: bool) -> None:
    """Floute une bande horizontale (px de base) ; le flou s'estompe progressivement vers la partie nette."""
    y1, y2 = fr.s(y1), fr.s(y2)
    h = y2 - y1
    band = img.crop((0, y1, fr.w, y2))
    shrink = 5 * PI.SCALE  # même flou qu'en 1080, quelle que soit la définition
    small = band.resize((fr.w // shrink, max(1, h // shrink)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    blur = small.resize((fr.w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2 * PI.SCALE))
    fade = int(h * 0.35)
    mask = Image.new("L", (fr.w, h))
    md = ImageDraw.Draw(mask)
    for y in range(h):
        d = h - 1 - y if top else y  # distance à la limite nette
        pct = 100 if d >= fade else round(100 * d / fade)
        md.line([(0, y), (fr.w, y)], fill=round(pct * 255 / 100))
    img.paste(blur, (0, y1), mask)


def _centered(fr: PI.Frame, draw, px: int, y: int, color, path: str, text: str) -> None:
    fr.text(draw, px, (fr.bw - fr.width(text, path, px)) / 2, y, color, path, text)


def _inner(fr: PI.Frame, margin: int) -> int:
    """Largeur utile pour un texte centré : marge habituelle, ou zone des boutons de l'application si plus large."""
    return fr.bw - 2 * max(margin, fr.side)


def _logo(fr: PI.Frame, img: Image.Image, x: int, y: int, width: int) -> None:
    logo = PI.white_logo()
    if logo:
        width = fr.s(width)
        lg = logo.resize((width, round(logo.size[1] * width / logo.size[0])), Image.LANCZOS)
        if img.mode == "RGBA":
            img.alpha_composite(lg, (fr.s(x), fr.s(y)))
        else:
            img.paste(lg, (fr.s(x), fr.s(y)), lg)


def _cover_slide(fr: PI.Frame, f: dict, cover: dict, photo_url, total: int) -> Image.Image:
    W, H = fr.bw, fr.bh
    img = _canvas(fr, f, photo_url)
    # Zone des titres : fond flouté puis assombri, pour que le texte reste lisible même sur une photo chargée
    _blur_zone(fr, img, 0, int(H * 0.50), True)
    fr.gradient(img, 0, int(H * 0.58), f["shade"], 8, 127)
    fr.gradient(img, int(H * 0.78), H, (0, 0, 0), 127, 60)
    draw = ImageDraw.Draw(img, "RGBA")
    white = (255, 255, 255, 255)
    y = fr.top + 120
    _centered(fr, draw, 40, y, white, f["bold"], fr.fit(PI.clean(cover["kicker"]), f["bold"], 40, _inner(fr, 70)))
    y += 20
    size = 150
    head = PI.clean(cover["headline"]).upper()
    while size > 70 and fr.width(head, f["display"], size) > _inner(fr, 55):
        size -= 6
    for line in fr.wrap(head, f["display"], size, _inner(fr, 55), 2):
        y += int(size * 1.02)
        _centered(fr, draw, size, y, white, f["display"], line)
    if cover.get("subtitle"):
        y += 70
        _centered(fr, draw, 50, y, white, f["serif"], fr.fit(PI.clean(cover["subtitle"]), f["serif"], 50, _inner(fr, 70)))
    _logo(fr, img, max(60, fr.side), H - fr.bottom - 190, 210)
    return img


def _best_cover(fr, f, cover, photo_url, total):
    """Une réaliste (photo entière, tête devant le titre) quand le détourage est disponible, sinon une classique."""
    from core.services.social import une
    try:
        img = une.cover(fr, f, cover, photo_url, total)
    except Exception as exc:  # noqa: BLE001 — la une classique prend le relais
        log_write("social", "error", f"une réaliste : {exc}")
        img = None
    return img or _magazine_cover(fr, f, cover, photo_url, total)


def magazine(name: str) -> bool:
    """Couverture « une de magazine » pour tous les posts (choix de la rédaction, octobre 2026)."""
    return True


def _tag(fr: PI.Frame, draw, x_right, y, px: int, text: str, fill, ink, path: str) -> float:
    """Étiquette pleine alignée à droite (« N°1 AFRIQUE DE L'OUEST ») ; renvoie le haut de l'étiquette."""
    w = fr.width(text, path, px) + 24
    h = px * 1.35
    fr.rect(draw, x_right - w, y - h, x_right, y, fill)
    fr.text(draw, px, x_right - w + 12, y - h * 0.26, ink, path, text)
    return y - h


def _magazine_cover(fr: PI.Frame, f: dict, cover: dict, photo_url, total: int) -> Image.Image:
    """Une de magazine : titre CAURI géant en tête, photo plein cadre, nom en très gros en bas, étiquettes de couleur."""
    W, H = fr.bw, fr.bh
    img = _canvas(fr, f, photo_url)
    fr.gradient(img, 0, fr.top + int(H * 0.22), (0, 0, 0), 40, 127)
    fr.gradient(img, int(H * 0.55), H, f["shade"], 127, 0)
    draw = ImageDraw.Draw(img, "RGBA")
    white, ink = (255, 255, 255, 255), (*f["on"], 255)
    accent = (*f["accent"], 255)
    side = max(48, fr.side)
    # 1. Titre du magazine : CAURI sur toute la largeur, CHARTS à la verticale contre la marge droite
    mast = "CAURI"
    room = W - 2 * side - 70
    size = 260
    while size > 120 and fr.width(mast, f["display"], size) > room:
        size -= 4
    top = fr.top + 36
    fr.text(draw, size, side - 6, top + size * 0.86, white, f["display"], mast)
    vert = Image.new("RGBA", (fr.s(size * 0.9), fr.s(60)), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vert)
    vpx = 46
    while vpx > 20 and fr.width("CHARTS", f["bold"], vpx) * 1.0 > size * 0.86:
        vpx -= 2
    vd.text((0, fr.s(48)), "CHARTS", font=PI.font(f["bold"], fr.s(vpx)), fill=accent, anchor="ls")
    vert = vert.rotate(90, expand=True)
    img.paste(vert, (fr.s(W - side - 58), fr.s(top + 6)), vert)
    # 2. Encart blanc à gauche : rang et périmètre, comme un badge de couverture
    kicker = PI.clean(cover.get("kicker") or "").upper()
    badge_top = top + size + 70
    bpx, bw = 30, 210
    lines = fr.wrap(kicker or "TOP DE LA SEMAINE", f["display"], bpx, bw - 28, 4)
    while bpx > 18 and any(fr.width(l, f["display"], bpx) > bw - 28 or l.endswith("…") for l in lines):
        bpx -= 2
        lines = fr.wrap(kicker or "TOP DE LA SEMAINE", f["display"], bpx, bw - 28, 4)
    bh = 30 + len(lines) * bpx * 1.2 + 36
    fr.rect(draw, 0, badge_top, bw, badge_top + bh, (255, 255, 255, 240))
    by = badge_top + 20 + bpx
    for line in lines:
        fr.text(draw, bpx, 14, by, (17, 17, 17, 255), f["display"], line)
        by += bpx * 1.2
    fr.rect(draw, 14, badge_top + bh - 30, bw - 14, badge_top + bh - 14, accent)
    # 3. Nom en très gros, en bas, sur deux lignes au plus
    head = PI.clean(cover["headline"]).upper()
    big = 210
    while big > 90 and max((fr.width(l, f["display"], big) for l in fr.wrap(head, f["display"], big, W - 2 * side, 2)), default=0) > W - 2 * side:
        big -= 6
    big_lines = fr.wrap(head, f["display"], big, W - 2 * side, 2)
    y = H - fr.bottom - 70
    for line in reversed(big_lines):
        fr.text(draw, big, side - 4, y, white, f["display"], line)
        y -= big * 0.98
    # 4. Étiquettes au-dessus du nom, alignées à droite (sous-titre découpé en deux lignes au plus)
    ty = y - 14
    subtitle = PI.clean(cover.get("subtitle") or "").upper()
    for line in reversed(fr.wrap(subtitle, f["bold"], 30, W * 0.62, 2)) if subtitle else []:
        ty = _tag(fr, draw, W - side, ty, 30, line, accent, ink, f["bold"]) - 8
    _tag(fr, draw, W - side, ty, 22, f"{total - 1} À DÉCOUVRIR · SWIPE", (17, 17, 17, 230), white, f["bold"])
    fr.text(draw, 18, side, H - fr.bottom - 26, (255, 255, 255, PI.gd_alpha(40)), f["sans"], "cauricharts.com")
    return img


def slide_variant(name: str) -> str:
    """Mise en page des diapositives d'un post : « bandeau » ou « dégradé », tirée au sort par post (stable)."""
    import random
    return "bandeau" if random.Random(name + "-diapo").random() < 0.5 else "degrade"


FONT_D, FONT_B, FONT_S = (str(PI.FONT_DIR / n) for n in ("Anton-Regular.ttf", "Poppins-Bold.ttf", "Poppins-Regular.ttf"))


def _photo(fr: PI.Frame, url, height: int, bg) -> Image.Image:
    """Photo nette (aucun flou, aucun filtre), recadrée sur le haut du sujet, sur la hauteur demandée."""
    img = Image.new("RGB", (fr.w, fr.h), bg)
    ph = PI.photo(url)
    if ph:
        part = Image.new("RGB", (fr.w, height))
        PI.paste_cover(part, ph, fr.w, height, 0.18)
        img.paste(part, (0, 0))
    else:
        fr.gradient(img, 0, fr.bh, (40, 30, 70), 90, 0)
    return img


def _item_slide(fr: PI.Frame, f: dict, item: dict, n: int, total: int, source: str, transparent: bool = False,
                variant: str = "degrade") -> Image.Image:
    """Diapositive d'un titre, sans flou : « bandeau » (photo en haut, bandeau plein en bas) ou « dégradé » (photo
    plein cadre, dégradé noir profond). Sur un clip vidéo (calque transparent), toujours le dégradé."""
    W, H = fr.bw, fr.bh
    base = H - fr.bottom
    pad = max(64, fr.side)
    ink, white = (14, 12, 18), (255, 255, 255)
    acc, on = (*f["accent"], 255), (*f["on"], 255)
    rank = str(item["rank"])
    artist, title = PI.clean(item["artist"]), PI.clean(item["title"])
    value, label = str(item.get("figure_value") or ""), str(item.get("figure_label") or "").upper()
    if variant == "bandeau" and not transparent:
        split = int(H * (0.62 if fr.bottom == 0 else 0.56))
        img = _photo(fr, item.get("image"), PI.Frame.s(split), ink)
        d = ImageDraw.Draw(img, "RGBA")
        fr.gradient(img, 0, fr.top + 200, (0, 0, 0), 70, 127)
        fr.rect(d, 0, split, W, H, (*ink, 255))
        fr.rect(d, 0, split, W, split + 8, acc)
        rank_px = 300 if fr.bottom == 0 else 280
        fr.text(d, rank_px, pad - 8, split + rank_px * 0.5, acc, FONT_D, rank)
        x = pad + fr.width(rank, FONT_D, rank_px) + 34
        room = W - x - pad
        fr.text(d, 30, x, split + 70, (255, 255, 255, 170), FONT_B, fr.fit(f"N°{rank}", FONT_B, 30, room))
        fr.text(d, 64, x, split + 140, (*white, 255), FONT_D, fr.fit(artist.upper(), FONT_D, 64, room))
        fr.text(d, 34, x, split + 190, (*white, 255), FONT_B, fr.fit(f"« {title} »", FONT_B, 34, room))
        if value:
            fr.rect(d, pad, base - 170, W - pad, base - 168, (255, 255, 255, 60))
            fr.text(d, 40, pad, base - 105, acc, FONT_D, value)
            fr.text(d, 24, pad + fr.width(value, FONT_D, 40) + 14, base - 108, (*white, 255), FONT_B,
                    fr.fit(label, FONT_B, 24, W - 2 * pad - fr.width(value, FONT_D, 40) - 14))
        fr.text(d, 17, pad, base - 44, (255, 255, 255, 150), FONT_S, fr.fit("Source : " + source + " · cauricharts.com", FONT_S, 17, W - 2 * pad))
        _logo(fr, img, pad, fr.top + 52, 180)
        return img
    # Dégradé : photo plein cadre nette, noir profond vers le bas, textes alignés à gauche
    img = _canvas(fr, f, None, True) if transparent else _photo(fr, item.get("image"), fr.h, ink)
    fr.gradient(img, int(H * 0.38), H, (6, 5, 9), 127, 0)
    fr.gradient(img, 0, fr.top + 200, (0, 0, 0), 60, 127)
    d = ImageDraw.Draw(img, "RGBA")
    fr.text(d, 220, pad - 6, base - 370, acc, FONT_D, rank)
    fr.text(d, 92, pad, base - 240, (*white, 255), FONT_D, fr.fit(artist.upper(), FONT_D, 92, W - 2 * pad))
    fr.text(d, 38, pad, base - 180, (*white, 255), FONT_B, fr.fit(f"« {title} »", FONT_B, 38, W - 2 * pad))
    if value:
        tag = fr.fit(f"{value}  {label}", FONT_B, 26, W - 2 * pad - 32)
        vw = fr.width(tag, FONT_B, 26) + 32
        fr.rect(d, pad, base - 130, pad + vw, base - 80, acc)
        fr.text(d, 26, pad + 16, base - 95, on, FONT_B, tag)
    fr.text(d, 17, pad, base - 30, (255, 255, 255, 150), FONT_S, fr.fit("Source : " + source + " · cauricharts.com", FONT_S, 17, W - 2 * pad))
    _logo(fr, img, pad, fr.top + 52, 180)
    return img


def _music(seed: str) -> str | None:
    """Morceau libre de droits tiré au sort (stable pour une même vidéo) ; licences dans resources/music/LISEZMOI.txt."""
    import random
    files = sorted(str(p) for p in MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg"))
    return random.Random(seed).choice(files) if files else None


def _ffmpeg() -> str | None:
    exe = env.get("FFMPEG_PATH", "ffmpeg") or "ffmpeg"
    return exe if (os.path.isfile(exe) or shutil.which(exe)) else None


def _probe(ffmpeg: str, file: str) -> dict:
    """Durée (secondes) et présence d'une piste audio, via ffprobe."""
    ffprobe = re.sub(r"ffmpeg(\.exe)?$", r"ffprobe\1", ffmpeg, flags=re.I)
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", file],
                           capture_output=True, text=True, timeout=60)
        data = json.loads(r.stdout) if r.returncode == 0 else {}
    except (OSError, ValueError, subprocess.SubprocessError):
        data = {}
    return {"duration": float((data.get("format") or {}).get("duration") or 0),
            "audio": any(s.get("codec_type") == "audio" for s in data.get("streams") or [])}


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def _video(segments: list, out: Path, w: int, h: int):
    """Couverture puis chaque titre : 30 s de clip (son compris) avec calque, ou photo 3 s avec un lent zoom. w × h : 4K 9:16."""
    ffmpeg = _ffmpeg()
    if not segments or not ffmpeg:
        return None
    clip_len = int(conf.get("ai.social.clip_seconds") or 30)
    clip_start = int(conf.get("ai.social.clip_start") or 30)
    still = 3  # rythme d'un reel : une image toutes les 3 secondes
    zw, zh = round(w * 1.1 / 2) * 2, round(h * 1.1 / 2) * 2  # marge du zoom
    args, filters, n = [], [], 0
    for i, seg in enumerate(segments):
        if "clip" in seg:
            info = _probe(ffmpeg, seg["clip"])
            # Extrait au cœur du clip (après l'intro) ; clip trop court : depuis le début
            start = clip_start if info["duration"] >= clip_start + clip_len else max(0, math.floor(info["duration"] - clip_len))
            length = min(clip_len, info["duration"] - start) if info["duration"] > 0 else clip_len
            args += ["-ss", str(start), "-t", _num(length), "-i", seg["clip"], "-loop", "1", "-t", _num(length), "-i", seg["overlay"]]
            c, o = n, n + 1
            n += 2
            filters.append(f"[{c}:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},fps=30,setsar=1,"
                           f"trim=duration={_num(length)},setpts=PTS-STARTPTS[c{i}];[c{i}][{o}:v]overlay=0:0:shortest=1,format=yuv420p[v{i}]")
            if info["audio"]:
                fade_out = max(0, length - 1.5)
                filters.append(f"[{c}:a]atrim=duration={_num(length)},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,"
                               f"afade=t=in:d=0.6,afade=t=out:st={_num(fade_out)}:d=1.5[a{i}]")
            else:
                args += ["-f", "lavfi", "-t", _num(length), "-i", "anullsrc=r=44100:cl=stereo"]
                filters.append(f"[{n}:a]anull[a{i}]")
                n += 1
        else:
            frames = still * 30
            args += ["-i", seg["image"], "-f", "lavfi", "-t", str(still), "-i", "anullsrc=r=44100:cl=stereo"]
            k, s = n, n + 1
            n += 2
            filters.append(f"[{k}:v]scale={zw}:{zh},zoompan=z='min(zoom+0.0009,1.1)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                           f":s={w}x{h}:fps=30,setsar=1,format=yuv420p[v{i}]")
            filters.append(f"[{s}:a]anull[a{i}]")
    concat = "".join(f"[v{i}][a{i}]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=1:a=1[out][aout]"
    # Musique libre de droits (resources/music) sous les photos : seulement si aucun clip n'apporte déjà son propre son
    music, audio_out = _music(out.name), "[aout]"
    if music and not any("clip" in seg for seg in segments):
        total = still * len(segments)
        args += ["-stream_loop", "-1", "-i", music]
        concat += f";[{n}:a]atrim=duration={total},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,"                   f"afade=t=in:d=1,afade=t=out:st={max(0, total - 2)}:d=2,volume=0.85[mus];[aout]anullsink"
        audio_out = "[mus]"
    # H.264 High 5.1 : 4K 30 i/s accepté tel quel par Instagram, Facebook et TikTok
    cmd = [ffmpeg, "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(filters) + ";" + concat,
           "-map", "[out]", "-map", audio_out, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high",
           "-level:v", "5.1", "-maxrate", "40M", "-bufsize", "80M", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-movflags", "+faststart", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "error", "ffmpeg a échoué", {"sortie": [str(exc)]})
        return None
    if r.returncode != 0:
        log_write("social", "error", "ffmpeg a échoué", {"sortie": (r.stdout + r.stderr).splitlines()[-5:]})
    return out.name if r.returncode == 0 and out.is_file() else None
