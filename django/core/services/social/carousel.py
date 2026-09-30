"""Carrousel façon magazine (1080 × 1350) et vidéo du Top (traduction de Social\\PostCarousel, GD → Pillow).

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

W, H = 1080, 1350


def render(facts: dict, cover: dict, items: list, name: str) -> dict:
    f = PI.fonts()
    if not f:
        return {"slides": [], "video": None}
    PI.DIR.mkdir(parents=True, exist_ok=True)
    total = len(items) + 1
    slides, segments = [], []
    cover_file = _save(_cover_slide(f, facts, cover, facts.get("image") or (items[0].get("image") if items else None), total), PI.DIR / f"{name}-1.png")
    slides.append(cover_file)
    segments.append({"image": cover_file})
    for i, item in enumerate(items):
        slide = _save(_item_slide(f, item, i + 2, total, facts["source"]), PI.DIR / f"{name}-{i + 2}.png")
        slides.append(slide)
        clip = find_clip(item)
        if clip:
            # Clip fourni par l'artiste ou le label : il passe en fond, classement et chiffres par-dessus
            overlay = PI.DIR / f"{name}-{i + 2}-calque.png"
            _item_slide(f, item, i + 2, total, facts["source"], transparent=True).save(overlay, "PNG")
            segments.append({"clip": clip, "overlay": str(overlay)})
        else:
            segments.append({"image": slide})
    slides = [s for s in slides if s]
    return {"slides": [os.path.basename(s) for s in slides], "video": _video(segments, PI.DIR / f"{name}.mp4")}


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


def _canvas(photo_url, transparent: bool = False):
    if transparent:
        # Calque posé sur un clip : fond transparent, seuls les dégradés et les textes sont dessinés
        return Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img = Image.new("RGB", (W, H), (24, 10, 60))
    ph = PI.photo(photo_url)
    if ph:
        PI.paste_cover(img, ph, W, H)
    else:
        PI.gradient(img, 0, H, (139, 82, 255), 90, 20, W)
    return img


def _blur_zone(img: Image.Image, y1: int, y2: int, top: bool) -> None:
    """Floute une bande horizontale ; le flou s'estompe progressivement vers la partie nette."""
    h = y2 - y1
    band = img.crop((0, y1, W, y2))
    small = band.resize((W // 5, max(1, h // 5)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    blur = small.resize((W, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
    fade = int(h * 0.35)
    mask = Image.new("L", (W, h))
    md = ImageDraw.Draw(mask)
    for y in range(h):
        d = h - 1 - y if top else y  # distance à la limite nette
        pct = 100 if d >= fade else round(100 * d / fade)
        md.line([(0, y), (W, y)], fill=round(pct * 255 / 100))
    img.paste(blur, (0, y1), mask)


def _centered(draw, px: int, y: int, color, path: str, text: str) -> None:
    PI.draw_text(draw, px, int((W - PI.width(text, path, px)) / 2), y, color, path, text)


def _counter(draw, f: dict, n: int, total: int) -> None:
    label = f"{n}/{total}"
    w = PI.width(label, f["bold"], 24) + 36
    x = W - 50 - w
    draw.rectangle([x, 50, x + w, 96], fill=(0, 0, 0, PI.gd_alpha(50)))
    PI.draw_text(draw, 24, x + 18, 82, (255, 255, 255, 255), f["bold"], label)


def _logo(img: Image.Image, x: int, y: int, width: int) -> None:
    logo = PI.white_logo()
    if logo:
        h = round(logo.size[1] * width / logo.size[0])
        lg = logo.resize((width, h), Image.LANCZOS)
        if img.mode == "RGBA":
            img.alpha_composite(lg, (x, y))
        else:
            img.paste(lg, (x, y), lg)


def _cover_slide(f: dict, facts: dict, cover: dict, photo_url, total: int) -> Image.Image:
    img = _canvas(photo_url)
    # Zone des titres : fond flouté puis assombri, pour que le texte reste lisible même sur une photo chargée
    _blur_zone(img, 0, int(H * 0.50), True)
    PI.gradient(img, 0, int(H * 0.58), (6, 4, 14), 8, 127, W)
    PI.gradient(img, int(H * 0.78), H, (0, 0, 0), 127, 60, W)
    draw = ImageDraw.Draw(img, "RGBA")
    white = (255, 255, 255, 255)
    y = 120
    _centered(draw, 40, y, white, f["bold"], PI.fit_width(PI.clean(cover["kicker"]), f["bold"], 40, W - 140))
    y += 20
    size = 150
    head = PI.clean(cover["headline"]).upper()
    while size > 70 and PI.width(head, f["display"], size) > W - 110:
        size -= 6
    for line in PI.wrap(head, f["display"], size, W - 110, 2):
        y += int(size * 1.02)
        _centered(draw, size, y, white, f["display"], line)
    if cover.get("subtitle"):
        y += 70
        _centered(draw, 50, y, white, f["serif"], PI.fit_width(PI.clean(cover["subtitle"]), f["serif"], 50, W - 140))
    _counter(draw, f, 1, total)
    _logo(img, 60, H - 190, 210)
    return img


def _item_slide(f: dict, item: dict, n: int, total: int, source: str, transparent: bool = False) -> Image.Image:
    img = _canvas(None if transparent else item.get("image"), transparent)
    PI.gradient(img, 0, 220, (0, 0, 0), 60, 127, W)
    if not transparent:
        _blur_zone(img, int(H * 0.50), H, False)  # photo seulement : sur un clip, le calque reste transparent
    PI.gradient(img, int(H * 0.40), H, (6, 4, 14), 127, 6, W)
    _logo(img, 56, 52, 180)
    draw = ImageDraw.Draw(img, "RGBA")
    _counter(draw, f, n, total)
    white, violet, soft = (255, 255, 255, 255), (*PI.VIOLET, 255), (255, 255, 255, PI.gd_alpha(40))
    # Rang « 1er », « 2e »… centré, suffixe en exposant
    rank = str(item["rank"])
    suffix = "er" if item["rank"] == 1 else "e"
    rs = 170
    w_rank, w_suf = PI.width(rank, f["serif"], rs), PI.width(suffix, f["serif"], 54)
    x = int((W - w_rank - w_suf - 6) / 2)
    y = H - 520
    PI.draw_text(draw, rs, x, y, white, f["serif"], rank)
    PI.draw_text(draw, 54, x + w_rank + 6, y - 100, white, f["serif"], suffix)
    y += 92
    _centered(draw, 70, y, white, f["serif"], PI.fit_width(PI.clean(item["artist"]), f["serif"], 70, W - 120))
    y += 42
    draw.rectangle([W // 2 - 9, y, W // 2 + 9, y + 18], fill=violet)
    y += 78
    _centered(draw, 50, y, white, f["bold"], PI.fit_width(PI.clean(item["title"]), f["bold"], 50, W - 120))
    y += 74
    # Chiffre exact : nombre en gras, libellé en capitales
    value = str(item["figure_value"]).upper()
    label = " " + str(item["figure_label"]).upper()
    wv, wl = PI.width(value, f["bold"], 42), PI.width(label, f["sans"], 42)
    if wv + wl > W - 100:
        label = " " + PI.fit_width(label.strip(), f["sans"], 42, W - 100 - wv)
        wl = PI.width(label, f["sans"], 42)
    x = int((W - wv - wl) / 2)
    PI.draw_text(draw, 42, x, y, white, f["bold"], value)
    PI.draw_text(draw, 42, x + wv, y, white, f["sans"], label)
    _centered(draw, 18, H - 44, soft, f["sans"], PI.fit_width("Source : " + source, f["sans"], 18, W - 120))
    return img


def _save(img: Image.Image, file: Path):
    out = file.with_suffix(".jpg")
    try:
        img.convert("RGB").save(out, "JPEG", quality=90)
        return str(out)
    except OSError:
        return None


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


def _video(segments: list, out: Path):
    """Couverture puis chaque titre : 30 s de clip (son compris) avec calque, ou photo 4 s avec un lent zoom."""
    ffmpeg = _ffmpeg()
    if not segments or not ffmpeg:
        return None
    clip_len = int(conf.get("ai.social.clip_seconds") or 30)
    clip_start = int(conf.get("ai.social.clip_start") or 30)
    still = 4
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
            filters.append(f"[{c}:v]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,fps=30,setsar=1,trim=duration={_num(length)},"
                           f"setpts=PTS-STARTPTS[c{i}];[c{i}][{o}:v]overlay=0:0:shortest=1,format=yuv420p[v{i}]")
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
            filters.append(f"[{k}:v]scale=1188:1485,zoompan=z='min(zoom+0.0009,1.1)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                           f":s=1080x1350:fps=30,setsar=1,format=yuv420p[v{i}]")
            filters.append(f"[{s}:a]anull[a{i}]")
    concat = "".join(f"[v{i}][a{i}]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=1:a=1[out][aout]"
    cmd = [ffmpeg, "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(filters) + ";" + concat,
           "-map", "[out]", "-map", "[aout]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "error", "ffmpeg a échoué", {"sortie": [str(exc)]})
        return None
    if r.returncode != 0:
        log_write("social", "error", "ffmpeg a échoué", {"sortie": (r.stdout + r.stderr).splitlines()[-5:]})
    return out.name if r.returncode == 0 and out.is_file() else None
