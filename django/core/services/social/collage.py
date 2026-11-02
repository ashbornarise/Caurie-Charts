"""Collages façon magazine avec de VRAIES photos d'artistes de la banque (demande du fondateur, 02/11/2026) : quand un
post n'a pas de photo concrète, plus de fond vide ni d'illustration générée par IA, mais un collage — papier, photos
aux bords déchirés légèrement inclinées, ombres, rubans adhésifs bleu ciel et violet (charte : blanc, ciel, violet).

  photos_tendance(n)        : meilleures photos des artistes du moment (Top des 7 derniers jours)
  photos_pays(code, n)      : meilleures photos des artistes d'un pays
  collage(urls, w, h, graine) -> Image
  fichier(urls, nom, ...)   -> chemin local d'un JPEG (pour les gabarits qui attendent une image)
"""
import io
import math
import random

import requests
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from core import db, storage
from core.services.social import couverture2026 as C

PAPIER = (247, 246, 242)
RUBANS = [(56, 189, 248, 150), (139, 82, 255, 140), (255, 255, 255, 170)]


def _urls(lignes: list) -> list:
    base = storage.blob_public_url()
    return [f"{base}/media/artists/plans/{r['fichier']}" for r in lignes]


def photos_tendance(n: int = 4) -> list:
    """Une photo (la mieux notée) par artiste du moment ayant des photos en banque."""
    lignes = db.all("""SELECT fichier FROM (SELECT DISTINCT ON (p.artist_id) p.fichier, p.artist_id, x.pos FROM artist_photos p
                          JOIN (SELECT t.artist_id, MIN(o.position) AS pos FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                                WHERE o.observed_on >= CURRENT_DATE - 7 GROUP BY t.artist_id) x ON x.artist_id = p.artist_id
                          ORDER BY p.artist_id, COALESCE(p.score, .5) DESC) y ORDER BY pos LIMIT ?""", [n])
    if len(lignes) < n:
        lignes += db.all("SELECT DISTINCT ON (artist_id) fichier, artist_id FROM artist_photos ORDER BY artist_id, COALESCE(score, .5) DESC LIMIT ?", [n])
    return _urls(lignes)[:n]


def photos_pays(code: str, n: int = 4) -> list:
    """Une photo par artiste du pays (les plus suivis d'abord) ; à défaut, les artistes du moment."""
    urls = _urls(db.all("""SELECT * FROM (SELECT DISTINCT ON (p.artist_id) p.fichier, p.artist_id, COALESCE(a.youtube_subscribers, 0) AS suivi
                                          FROM artist_photos p JOIN artists a ON a.id = p.artist_id
                                          JOIN countries c ON c.id = a.submission_country_id
                                          WHERE c.code = ? AND a.status = 'active' ORDER BY p.artist_id, COALESCE(p.score, .5) DESC) x
                           ORDER BY suivi DESC LIMIT ?""", [str(code).upper(), n]))
    return urls if len(urls) >= 2 else (urls + photos_tendance(n))[:n]


def _charge(url: str):
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:  # noqa: BLE001 — une photo illisible est simplement sautée
        return None


def _dechire(w: int, h: int, rnd: random.Random, amplitude: float) -> Image.Image:
    """Masque d'un morceau de papier aux bords déchirés (contour irrégulier)."""
    pas = max(6, int(min(w, h) / 40))
    pts = []
    for x in range(0, w + 1, pas):
        pts.append((x, rnd.uniform(0, amplitude)))
    for y in range(0, h + 1, pas):
        pts.append((w - rnd.uniform(0, amplitude), y))
    for x in range(w, -1, -pas):
        pts.append((x, h - rnd.uniform(0, amplitude)))
    for y in range(h, -1, -pas):
        pts.append((rnd.uniform(0, amplitude), y))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m.filter(ImageFilter.GaussianBlur(.6))


def _morceau(im: Image.Image, w: int, h: int, rnd: random.Random, u: float) -> Image.Image:
    """La photo cadrée sur l'artiste, posée sur un papier blanc déchiré (marge irrégulière), avec du grain."""
    photo = C.cadre_personne(im, w, h)
    marge = int(22 * u)
    W, H = w + 2 * marge, h + 2 * marge
    papier = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    papier.paste(photo, (marge, marge))
    papier.putalpha(_dechire(W, H, rnd, marge * .9))
    return papier


def collage(urls: list, w: int = 2160, h: int = 2700, graine: int = 0) -> Image.Image | None:
    """Collage de 2 à 4 photos ; None si aucune photo n'est lisible."""
    images = [i for i in (_charge(u) for u in urls[:4]) if i is not None]
    if not images:
        return None
    rnd = random.Random(graine)
    u = w / 1080
    fond = Image.new("RGB", (w, h), PAPIER)
    grain = Image.effect_noise((w // 4, h // 4), 18).resize((w, h)).convert("RGB")
    fond = ImageChops.multiply(fond, Image.merge("RGB", [grain.getchannel(0).point(lambda v: 225 + v // 8)] * 3))
    c = fond.convert("RGBA")
    # une grande bande de papier violet déchirée en travers (repère de la charte)
    bande = Image.new("RGBA", (int(w * 1.3), int(h * .2)), (139, 82, 255, 235))
    bande.putalpha(ImageChops.multiply(bande.getchannel("A"), _dechire(bande.width, bande.height, rnd, 40 * u)))
    bande = bande.rotate(rnd.uniform(-9, 9), resample=Image.BICUBIC, expand=True)
    c.alpha_composite(bande, (int(-w * .15), int(h * rnd.uniform(.35, .55))))
    n = len(images)
    gabarits = {
        1: [(.5, .48, .8, .7)],
        2: [(.33, .36, .56, .5), (.67, .66, .56, .5)],
        3: [(.3, .28, .5, .42), (.72, .42, .48, .4), (.4, .74, .52, .42)],
        4: [(.28, .26, .46, .38), (.72, .3, .44, .36), (.3, .72, .44, .36), (.72, .74, .46, .38)],
    }[n]
    for im, (cx, cy, fw, fh) in zip(images, gabarits):
        pw, ph = int(w * fw), int(h * fh)
        m = _morceau(im, pw, ph, rnd, u).rotate(rnd.uniform(-6, 6), resample=Image.BICUBIC, expand=True)
        x, y = int(w * cx - m.width / 2), int(h * cy - m.height / 2)
        ombre = Image.new("RGBA", m.size, (0, 0, 0, 0)); ombre.putalpha(m.getchannel("A").point(lambda a: int(a * .35)))
        c.alpha_composite(ombre.filter(ImageFilter.GaussianBlur(18 * u)), (x + int(14 * u), y + int(18 * u)))
        c.alpha_composite(m, (x, y))
        # ruban adhésif sur un coin
        rw, rh = int(150 * u), int(46 * u)
        ruban = Image.new("RGBA", (rw, rh), rnd.choice(RUBANS))
        ruban = ruban.rotate(rnd.choice([-38, -32, 32, 38]), resample=Image.BICUBIC, expand=True)
        coin = rnd.choice([(x - int(30 * u), y - int(10 * u)), (x + m.width - rw, y - int(10 * u))])
        c.alpha_composite(ruban, (max(0, coin[0]), max(0, coin[1])))
    return c.convert("RGB")


def fichier(urls: list, nom: str, w: int = 2160, h: int = 2700, graine: int = 0) -> str | None:
    """Chemin local d'un JPEG du collage (gabarits qui attendent un chemin d'image), ou None."""
    im = collage(urls, w, h, graine)
    if im is None:
        return None
    dossier = storage.MEDIA / "social"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"collage-{nom}.jpg"
    im.save(chemin, format="JPEG", quality=90)
    return str(chemin)


def adresse(urls: list, nom: str, w: int = 2160, h: int = 2700, graine: int = 0) -> str | None:
    """Adresse publique (Blob) du collage, pour les gabarits qui chargent une image par son adresse web."""
    im = collage(urls, w, h, graine)
    if im is None:
        return None
    out = io.BytesIO(); im.save(out, format="JPEG", quality=88)
    storage.store_media("social", f"collage-{nom}.jpg", out.getvalue(), "image/jpeg")
    return f"{storage.blob_public_url()}/media/social/collage-{nom}.jpg"


def graine_de(texte: str) -> int:
    return int(sum(ord(ch) * (i + 1) for i, ch in enumerate(texte or "")) % 100000) + int(math.pi * 1000)
