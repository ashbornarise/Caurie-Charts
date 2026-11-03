"""Bannière des réseaux (02/11/2026) : mosaïque des artistes des tops qui ont une belle photo en banque, logo Cauri Charts
au centre dans un médaillon de verre. Facebook : photo de couverture ; Instagram / TikTok : trio de posts à épingler.

    python manage.py shell -c "from core.services.social import banniere; print(banniere.tout('C:/chemin'))"
"""
import io
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

from core import db, storage
from core.services.social import couverture2026 as C
from core.services.social.pourtoi import RES

NOTE_MIN = .85
EXCLUS = {"Axel Merryl"}   # sa meilleure photo en banque est une pochette avec du texte (02/11/2026)


def artistes(maximum: int = 24) -> list:
    """(nom, url) : la meilleure photo de chaque artiste des tops, si elle est assez belle."""
    from core.services import spotify_apify
    tops = spotify_apify.tops()
    base = storage.blob_public_url()
    lignes = db.all("""SELECT DISTINCT ON (a.id) a.id, a.name, p.fichier, COALESCE(p.score, 0) AS note FROM artist_photos p
                       JOIN artists a ON a.id = p.artist_id WHERE a.id = ANY(?) AND COALESCE(p.score, 0) >= ?
                       ORDER BY a.id, COALESCE(p.score, 0) DESC, p.plan_large DESC""", [tops, NOTE_MIN])
    rang = {aid: i for i, aid in enumerate(tops)}
    lignes.sort(key=lambda r: rang.get(r["id"], 999))
    lignes = [r for r in lignes if r["name"] not in EXCLUS]
    return [(r["name"], f"{base}/media/artists/plans/{r['fichier']}") for r in lignes][:maximum]


def _charge(url: str):
    try:
        r = requests.get(url, timeout=30); r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def mosaique(w: int, h: int, cols: int, rangs: int, gens: list, ecart: int = 6, centre=None) -> Image.Image:
    c = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(c)
    tw, th = (w - ecart * (cols + 1)) / cols, (h - ecart * (rangs + 1)) / rangs
    f = C.police("Montserrat.ttf", max(14, int(th * .07)), "Bold")
    n = cols * rangs
    # chaque artiste une seule fois dans les cases visibles ; les doublons vont derrière le médaillon central
    cx, cy, r = centre or (w / 2, h / 2, 0)
    def cache(k):
        x0, y0 = ecart + (k % cols) * (tw + ecart) + tw / 2, ecart + (k // cols) * (th + ecart) + th / 2
        return ((x0 - cx) ** 2 + (y0 - cy) ** 2) ** .5 < r
    ordre = sorted(range(n), key=cache)
    place = {case: gens[i % len(gens)] for i, case in enumerate(ordre)}
    for k in range(n):
        nom, im = place[k]
        x, y = int(ecart + (k % cols) * (tw + ecart)), int(ecart + (k // cols) * (th + ecart))
        case = C.cadre_personne(im, int(tw), int(th))
        c.paste(case, (x, y))
        bb = f.getbbox(nom)
        px, py = x + int(th * .05), y + int(th) - (bb[3] - bb[1]) - int(th * .08)
        d.rounded_rectangle((px - 10, py - 6, px + bb[2] - bb[0] + 10, py + bb[3] - bb[1] + 10), radius=999, fill=(255, 255, 255))
        d.text((px - bb[0], py - bb[1]), nom, font=f, fill=(14, 18, 40))
    return c


def medaillon(c: Image.Image, cx: int, cy: int, r: int) -> None:
    """Logo au centre : disque de verre blanc (flou de la mosaïque derrière), monogramme violet, « Cauri Charts »."""
    boite = (cx - r, cy - r, cx + r, cy + r)
    flou = c.crop(boite).filter(ImageFilter.GaussianBlur(r / 6))
    voile = Image.new("RGB", flou.size, (255, 255, 255))
    flou = Image.blend(flou, voile, .72)
    masque = Image.new("L", flou.size, 0); ImageDraw.Draw(masque).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    ombre = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(ombre).ellipse((cx - r + 8, cy - r + 16, cx + r + 8, cy + r + 16), fill=(20, 30, 70, 90))
    base = c.convert("RGBA"); base.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(r / 8)))
    base.paste(flou, boite[:2], masque)
    d = ImageDraw.Draw(base)
    d.ellipse(boite, outline=(255, 255, 255), width=max(3, r // 40))
    dr = int(r * .62)
    disque = Image.new("RGBA", (dr, dr), (0, 0, 0, 0))
    ImageDraw.Draw(disque).ellipse((0, 0, dr - 1, dr - 1), fill=(122, 60, 245, 255))
    lg = Image.open(RES / "marque" / "logo-blanc.png").convert("RGBA"); lg = lg.crop(lg.getbbox())
    lg = lg.crop((0, 0, lg.height, lg.height)).resize((int(dr * .56), int(dr * .56)), Image.LANCZOS)
    disque.paste(lg, ((dr - lg.width) // 2, (dr - lg.height) // 2), lg)
    base.alpha_composite(disque, (cx - dr // 2, cy - int(r * .62)))
    f = C.police("DMSerifDisplay-Regular.ttf", int(r * .24))
    t = "Cauri Charts"; bb = f.getbbox(t)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], cy + int(r * .1)), t, font=f, fill=(14, 18, 40))
    f2 = C.police("Montserrat.ttf", int(r * .082), "Bold")
    t2 = "LA RÉFÉRENCE DE LA MUSIQUE OUEST-AFRICAINE"; bb = f2.getbbox(t2)
    if bb[2] - bb[0] > r * 1.6:
        f2 = C.police("Montserrat.ttf", int(r * .082 * r * 1.6 / (bb[2] - bb[0])), "Bold"); bb = f2.getbbox(t2)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], cy + int(r * .42)), t2, font=f2, fill=(91, 43, 214))
    c.paste(base.convert("RGB"))


def _monogramme(taille: int) -> Image.Image:
    """Le monogramme seul (sans le mot « Cauri » qui suit : il faisait une tache blanche devant le C)."""
    lg = Image.open(RES / "marque" / "logo-blanc.png").convert("RGBA"); lg = lg.crop(lg.getbbox())
    a = lg.getchannel("A")
    fin = next((x for x in range(int(lg.height * .6), lg.width)
                if all(a.getpixel((x, y)) < 40 for y in range(0, lg.height, 2))), lg.height)
    lg = lg.crop((0, 0, fin, lg.height)); lg = lg.crop(lg.getbbox())
    k = taille / max(lg.size)
    return lg.resize((max(1, int(lg.width * k)), max(1, int(lg.height * k))), Image.LANCZOS)


def logo_bleu(c: Image.Image, cx: int, cy: int, r: int) -> None:
    """Seulement le logo, en bleu : disque bleu ciel, monogramme blanc, halo blanc (demande du fondateur, 02/11/2026)."""
    base = c.convert("RGBA")
    halo = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((cx - r * 1.45, cy - r * 1.45, cx + r * 1.45, cy + r * 1.45), fill=(255, 255, 255, 235))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(r * .35)))
    ombre = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(ombre).ellipse((cx - r, cy - r + r * .08, cx + r, cy + r + r * .08), fill=(15, 70, 140, 110))
    base.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(r * .12)))
    d = ImageDraw.Draw(base)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(29, 155, 240, 255), outline=(255, 255, 255, 255), width=max(4, r // 18))
    m = _monogramme(int(r * 1.05))
    base.alpha_composite(m, (cx - m.width // 2, cy - m.height // 2))
    c.paste(base.convert("RGB"))


def trou_noir(w: int, h: int, cols: int, rangs: int, gens: list, centre) -> Image.Image:
    """Cases en papier déchiré collées, rangées en grille (pas au hasard), toutes aspirées vers le centre comme par un
    trou noir : plus proches du centre = plus petites, tirées vers lui et inclinées vers lui ; anneaux bleu ciel."""
    import math
    import random

    from core.services.social import collage
    cx, cy, r = centre
    u = w / 1640
    c = Image.new("RGB", (w, h), (250, 251, 253)).convert("RGBA")
    anneaux = Image.new("RGBA", (w, h), (0, 0, 0, 0)); da = ImageDraw.Draw(anneaux)
    dmax = math.hypot(w / 2, h / 2)
    for k in range(1, 14):
        rr = r * 1.1 + k * k * dmax / 110
        da.ellipse((cx - rr * 1.25, cy - rr, cx + rr * 1.25, cy + rr), outline=(56, 189, 248, max(18, 70 - k * 4)), width=max(2, int(3 * u)))
    c.alpha_composite(anneaux.filter(ImageFilter.GaussianBlur(1.2)))
    tw, th = w / cols, h / rangs
    cases = []
    for k in range(cols * rangs):
        gx, gy = (k % cols + .5) * tw, (k // cols + .5) * th
        vx, vy = gx - cx, gy - cy
        f = min(1.0, math.hypot(vx, vy) / dmax)
        cases.append((k, gx, gy, vx, vy, f))
    seuil = max(r * 1.05, min(tw, th) * .6)   # cases aspirées derrière le logo : on y met les doublons
    cachees = [k for k, gx, gy, vx, vy, f in cases if math.hypot(vx * .8, vy * .8) < seuil]
    ordre = [k for k, *_ in sorted(cases, key=lambda t: t[0] in cachees)]
    place = {case: gens[i % len(gens)] for i, case in enumerate(ordre)}
    fnom = C.police("Montserrat.ttf", max(14, int(22 * u)), "Bold")
    rnd = random.Random(7)
    for k, gx, gy, vx, vy, f in sorted(cases, key=lambda t: -t[5]):   # les plus lointaines d'abord, le centre par-dessus
        nom, im = place[k]
        echelle = .55 + .5 * f                       # rétrécit en approchant du centre
        pull = .78 + .2 * f                          # tirée vers le centre
        x0, y0 = cx + vx * pull, cy + vy * pull
        pw, ph = int(tw * .82 * echelle), int(th * .82 * echelle)
        morceau = collage._morceau(im, pw, ph, rnd, u)
        dm = ImageDraw.Draw(morceau)
        bb = fnom.getbbox(nom)
        px, py = int(26 * u), morceau.height - (bb[3] - bb[1]) - int(34 * u)
        dm.rounded_rectangle((px - 8, py - 5, px + bb[2] - bb[0] + 8, py + bb[3] - bb[1] + 9), radius=999, fill=(255, 255, 255, 235))
        dm.text((px - bb[0], py - bb[1]), nom, font=fnom, fill=(14, 18, 40))
        angle = math.degrees(math.atan2(vx, abs(vy) + th)) * (-.35 if vy < 0 else .35)   # inclinée vers le centre
        piece = morceau.rotate(angle, resample=Image.BICUBIC, expand=True)
        x, y = int(x0 - piece.width / 2), int(y0 - piece.height / 2)
        ombre = Image.new("RGBA", piece.size, (0, 0, 0, 0)); ombre.putalpha(piece.getchannel("A").point(lambda a: int(a * .32)))
        c.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(14 * u)), (x + int(10 * u), y + int(14 * u)))
        c.alpha_composite(piece, (x, y))
        ruban = Image.new("RGBA", (int(110 * u * echelle), int(34 * u * echelle)), (56, 189, 248, 150) if k % 2 else (139, 82, 255, 140))
        ruban = ruban.rotate(angle + (35 if k % 2 else -35), resample=Image.BICUBIC, expand=True)
        c.alpha_composite(ruban, (max(0, x + piece.width // 2 - ruban.width // 2), max(0, y - ruban.height // 3)))
    return c.convert("RGB")


def tout(dossier: str) -> list:
    gens = [(n, im) for n, im in ((n, _charge(u)) for n, u in artistes()) if im is not None]
    if len(gens) < 6:
        raise RuntimeError("pas assez d'artistes avec une belle photo")
    out = Path(dossier); out.mkdir(parents=True, exist_ok=True)
    fichiers = []
    # Facebook : 1640 × 856 (le centre 1640 × 624 reste visible sur ordinateur et mobile)
    fb = trou_noir(1640, 856, 6, 3, gens, centre=(820, 428, 120))
    logo_bleu(fb, 820, 428, 120)
    fb.save(out / "cauri-banniere-facebook.jpg", quality=92); fichiers.append(str(out / "cauri-banniere-facebook.jpg"))
    # Instagram / TikTok : 3 posts 1080 × 1350 à épingler, qui forment une seule image (3240 × 1350)
    pano = trou_noir(3240, 1350, 6, 3, gens[1:] + gens[:1], centre=(1620, 675, 190))
    logo_bleu(pano, 1620, 675, 190)
    pano.save(out / "cauri-banniere-panorama.jpg", quality=92); fichiers.append(str(out / "cauri-banniere-panorama.jpg"))
    for i, nom in enumerate(("1-gauche", "2-centre", "3-droite")):
        p = out / f"cauri-banniere-instagram-{nom}.jpg"
        pano.crop((i * 1080, 0, (i + 1) * 1080, 1350)).save(p, quality=92); fichiers.append(str(p))
    return fichiers
