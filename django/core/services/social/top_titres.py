"""« Les 10 titres les plus écoutés de X » : listes aux couleurs du pays de l'artiste (09/11/2026).

Demande du fondateur : « pour chaque artiste, selon son pays, ses couleurs ressortent ; chaque titre accompagné de sa
cover et une liste bien faite et intuitive ». Fond blanc (charte), voiles de couleur du drapeau, liseré du drapeau en haut,
cartes en verre : rang, pochette, titre (les invités sur une 2e ligne), écoutes et barre proportionnelle au N°1.
Pochettes : oEmbed public de Spotify (sans clé), 640 px.
"""
import re
from functools import lru_cache

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from core.helpers import country_name
from core.services.social import couverture2026 as C
from core.services.social.gabarits import FLAGS

BLANC, NUIT = (255, 255, 255), (14, 14, 28)
GRIS = (104, 104, 128)


# ---------------------------------------------------------------- couleurs du pays

def _clair(c) -> float:
    return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255


def couleurs(pays: str | None) -> tuple:
    """(couleur principale, 2e couleur, bandes du drapeau). Le blanc n'est jamais une couleur d'accent ;
    sans drapeau connu : violet et bleu ciel de Cauri."""
    bandes = FLAGS.get((pays or "").lower())
    if not bandes:
        return C.VIOLET, C.CIEL, [C.VIOLET, BLANC, C.CIEL]
    vives = [b for b in bandes if _clair(b) < .85]
    a = vives[0]
    b = next((x for x in vives[1:] if x != a), None)
    if b is None:   # Nigeria (vert, blanc, vert) : un vert plus profond en 2e couleur
        b = tuple(int(v * .62) for v in a)
    return a, b, bandes


def accent_texte(c) -> tuple:
    """Une couleur lisible sur blanc (le jaune du Ghana ou du Sénégal est assombri)."""
    return c if _clair(c) < .6 else tuple(int(v * .62) for v in c)


# ---------------------------------------------------------------- titres et pochettes

_SUFFIXES = re.compile(r"\s+-\s+(spotify single version|single version|remaster(ed)?.*|radio edit|.*version.*|from .*)$", re.I)


def nettoie(titre: str, artiste: str, feat: bool = False) -> tuple[str, str]:
    """« My Love (feat. Major Lazer, WizKid, Dua Lipa) - Spotify Single Version » →
    (« My Love », « avec Major Lazer, Dua Lipa »). L'artiste du post est retiré des invités."""
    t = _SUFFIXES.sub("", titre or "").strip()
    avec = []
    for m in re.finditer(r"\s*[\(\[](?:feat\.?|ft\.?|featuring|with|avec)\s+([^\)\]]+)[\)\]]", t, re.I):
        avec += [x.strip() for x in re.split(r",|&| x | et | and ", m.group(1)) if x.strip()]
    t = re.sub(r"\s*[\(\[](?:feat\.?|ft\.?|featuring|with|avec)\s+[^\)\]]+[\)\]]", "", t, flags=re.I).strip()
    soi = re.sub(r"\W", "", (artiste or "").lower())
    avec = [x for x in avec if re.sub(r"\W", "", x.lower()) != soi]
    if avec:
        return C.propre(t), "avec " + ", ".join(avec)
    return C.propre(t), (f"{artiste} en featuring" if feat else "")


@lru_cache(maxsize=64)
def pochette(track_id: str) -> Image.Image | None:
    if not track_id:
        return None
    try:
        r = requests.get("https://open.spotify.com/oembed", params={"url": f"https://open.spotify.com/track/{track_id}"},
                         timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        url = r.json().get("thumbnail_url") if r.ok else None
    except (requests.RequestException, ValueError):
        url = None
    if not url:
        return None
    grand = url.replace("ab67616d00001e02", "ab67616d0000b273")   # 300 px -> 640 px
    return C._image(grand) or C._image(url)


def court(n: float) -> str:
    """4 560 000 000 → « 4,56 Md » ; 156 000 000 → « 156 M »."""
    if n >= 1e9:
        return f"{n / 1e9:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " Md"
    if n >= 1e6:
        return f"{n / 1e6:.0f} M"
    return f"{n / 1e3:.0f} k"


# ---------------------------------------------------------------- dessin

def _fond(w: int, h: int, a, b, u: float) -> Image.Image:
    """Blanc lumineux, deux grandes taches floues aux couleurs du pays (effet verre liquide)."""
    c = Image.new("RGB", (w, h), (250, 250, 253))
    voile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(voile)
    r1, r2 = int(520 * u), int(460 * u)
    d.ellipse((w - r1 * 1.3, -r1 * .6, w + r1 * .7, r1 * 1.4), fill=a + (70,))
    d.ellipse((-r2 * .8, h - r2 * 1.5, r2 * 1.2, h + r2 * .5), fill=b + (60,))
    voile = voile.filter(ImageFilter.GaussianBlur(int(150 * u)))
    c.paste(voile, (0, 0), voile)
    return c


def _ombre_carte(c: Image.Image, box, rayon: int, u: float, force: int = 46) -> None:
    x0, y0, x1, y1 = [int(v) for v in box]
    m = int(40 * u)
    o = Image.new("L", (x1 - x0 + 2 * m, y1 - y0 + 2 * m), 0)
    ImageDraw.Draw(o).rounded_rectangle((m, m + int(10 * u), m + x1 - x0, m + y1 - y0 + int(10 * u)), radius=rayon, fill=force)
    o = o.filter(ImageFilter.GaussianBlur(int(18 * u)))
    c.paste(Image.new("RGB", o.size, (30, 30, 60)), (x0 - m, y0 - m), o)


def _carte(c: Image.Image, box, rayon: int, u: float, teinte=BLANC, opacite: float = .78) -> None:
    """Carte en verre : le fond flouté sous un blanc translucide, liseré clair."""
    x0, y0, x1, y1 = [int(v) for v in box]
    _ombre_carte(c, box, rayon, u)
    zone = c.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(int(20 * u)))
    zone = Image.blend(zone, Image.new("RGB", zone.size, teinte), opacite)
    masque = Image.new("L", zone.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle((0, 0, zone.width - 1, zone.height - 1), radius=rayon, fill=255)
    c.paste(zone, (x0, y0), masque)
    ImageDraw.Draw(c).rounded_rectangle((x0, y0, x1, y1), radius=rayon, outline=(255, 255, 255), width=max(2, int(2 * u)))


def _pochette(c: Image.Image, im, x: int, y: int, cote: int, rayon: int, u: float, couleur) -> None:
    if im is None:   # sans pochette : un carré aux couleurs du pays avec le logo Cauri
        im = Image.new("RGB", (cote, cote), couleur)
        ImageDraw.Draw(im).text((cote / 2, cote / 2), "C", font=C.police("Jost.ttf", int(cote * .5), "Black"), fill=BLANC, anchor="mm")
    im = ImageOps.fit(im.convert("RGB"), (cote, cote), Image.LANCZOS)
    masque = Image.new("L", (cote, cote), 0)
    ImageDraw.Draw(masque).rounded_rectangle((0, 0, cote - 1, cote - 1), radius=rayon, fill=255)
    _ombre_carte(c, (x, y, x + cote, y + cote), rayon, u, 70)
    c.paste(im, (x, y), masque)


def _coupe(d, texte: str, f, largeur: float) -> str:
    while d.textlength(texte, font=f) > largeur and len(texte) > 3:
        texte = texte.rstrip("…")[:-1].rstrip() + "…"
    return texte


def _drapeau(c: Image.Image, x: int, y: int, w: int, h: int, bandes, u: float) -> None:
    mini = Image.new("RGB", (w, h))
    dm = ImageDraw.Draw(mini)
    for i, b in enumerate(bandes):
        dm.rectangle((i * w / 3, 0, (i + 1) * w / 3, h), fill=b)
    masque = Image.new("L", (w, h), 0)
    ImageDraw.Draw(masque).rounded_rectangle((0, 0, w - 1, h - 1), radius=int(6 * u), fill=255)
    _ombre_carte(c, (x, y, x + w, y + h), int(6 * u), u, 50)
    c.paste(mini, (x, y), masque)


def _logo_sombre(c: Image.Image, x: int, y: int, d_: int) -> None:
    C._logo(c, x, y, d_)   # dessine « cauricharts » en blanc : on le repasse en encre sombre
    ImageDraw.Draw(c).text((x + d_ + 16, y + d_ * .28), "cauricharts", font=C.police("Jost.ttf", int(d_ * .42), "SemiBold"), fill=NUIT)


def liste(lignes: list, artiste: str, pays: str | None, fmt: str = "feed", titre: str = "",
          etiquette: str = "CLASSÉS PAR ÉCOUTES SPOTIFY", source: str = "Spotify (compteurs publics relevés par Kworb)") -> Image.Image:
    """Une diapo de la liste. lignes : [(rang, {titre, streams, spotify_id, feat})] dans l'ordre affiché.
    Le N°1 (s'il est sur la diapo) a une grande carte ; les barres des autres lignes se mesurent au plus écouté d'entre
    elles (face aux milliards d'un N°1 elles restaient vides)."""
    w, h = C.FORMATS.get(fmt, C.FORMATS["feed"])
    u = w / 1080
    a, b, bandes = couleurs(pays)
    at = accent_texte(a)
    c = _fond(w, h, a, b, u)
    d = ImageDraw.Draw(c)
    haut = 0 if fmt == "feed" else int(170 * u)
    # liseré du drapeau tout en haut
    for i, band in enumerate(bandes):
        d.rectangle((i * w / 3, 0, (i + 1) * w / 3, int(14 * u)), fill=band if _clair(band) < .95 else (236, 236, 242))
    m = int(64 * u)
    _logo_sombre(c, m - int(8 * u), haut + int(50 * u), int(72 * u))
    d = ImageDraw.Draw(c)
    # en-tête : pastille (à droite du logo), titre, artiste + drapeau + pays
    fe = C.police("Montserrat.ttf", int(23 * u), "ExtraBold")
    eti = etiquette
    tw = d.textlength(eti, font=fe)
    ye = haut + int(60 * u)
    d.rounded_rectangle((w - m - tw - 40 * u, ye, w - m, ye + 50 * u), radius=int(25 * u), fill=at)
    d.text((w - m - tw - 20 * u, ye + 25 * u), eti, font=fe, fill=BLANC, anchor="lm")
    y = haut + int(160 * u)
    ft = C.police("Montserrat.ttf", int(84 * u), "ExtraBold")
    d.text((m - 4 * u, y), titre, font=ft, fill=NUIT)
    y += int(104 * u)
    fa = C.police("Montserrat.ttf", int(34 * u), "SemiBold")
    _drapeau(c, m, y + int(4 * u), int(54 * u), int(36 * u), bandes, u)
    d = ImageDraw.Draw(c)
    d.text((m + 72 * u, y + 22 * u), f"{artiste}  ·  {country_name(pays) if pays else 'Afrique de l’Ouest'}",
           font=fa, fill=GRIS, anchor="lm")
    y += int(80 * u)

    bas = h - (int(110 * u) if fmt == "feed" else int(330 * u))
    premier = [t for r, t in lignes if r == 1]
    autres = [(r, t) for r, t in lignes if r != 1]
    record = max([t["streams"] for _r, t in autres] or [1])
    # lignes : hauteur commune, le N°1 en grande carte s'il est là
    gap = int(18 * u)
    h1 = int((290 if fmt == "feed" else 380) * u) if premier else 0
    place = bas - y - (h1 + gap if premier else 0)
    hl = min(int((176 if fmt == "feed" else 250) * u), (place - gap * (len(autres) - 1)) // max(1, len(autres)))
    ordre = ([(1, premier[0])] if premier else []) + autres
    for rang, t in ordre:
        if "sous" in t:   # albums (10/11/2026) : nom tel quel, 2e ligne fournie (année, titre phare), pochette par URL
            nom, avec = C.propre(t["titre"]), t["sous"]
        else:
            nom, avec = nettoie(t["titre"], artiste, bool(t.get("feat")))
        im = C._image(t["image"]) if t.get("image") else pochette(t.get("spotify_id") or "")
        if rang == 1:
            box = (m - 16 * u, y, w - m + 16 * u, y + h1)
            _carte(c, box, int(44 * u), u, BLANC, .70)
            d = ImageDraw.Draw(c)
            cote = int(h1 - 56 * u)
            _pochette(c, im, int(box[0] + 28 * u), int(y + 28 * u), cote, int(26 * u), u, a)
            d = ImageDraw.Draw(c)
            x = int(box[0] + 28 * u + cote + 34 * u)
            lx = box[2] - x - 30 * u
            pill = "N°1"
            fp = C.police("Montserrat.ttf", int(30 * u), "ExtraBold")
            pw = d.textlength(pill, font=fp)
            d.rounded_rectangle((x, y + 34 * u, x + pw + 36 * u, y + 84 * u), radius=int(25 * u), fill=at)
            d.text((x + 18 * u, y + 59 * u), pill, font=fp, fill=BLANC, anchor="lm")
            fn = C.police("Montserrat.ttf", int(50 * u), "ExtraBold")
            d.text((x, y + 100 * u), _coupe(d, nom, fn, lx), font=fn, fill=NUIT)
            yy = y + 162 * u
            if avec:
                fv = C.police("Montserrat.ttf", int(27 * u), "Medium")
                d.text((x, yy), _coupe(d, avec, fv, lx), font=fv, fill=GRIS)
            fs = C.police("Montserrat.ttf", int(54 * u), "ExtraBold")
            d.text((x, y + h1 - 96 * u), court(t["streams"]), font=fs, fill=at)
            sw = d.textlength(court(t["streams"]), font=fs)
            d.text((x + sw + 14 * u, y + h1 - 68 * u), "écoutes", font=C.police("Montserrat.ttf", int(28 * u), "SemiBold"), fill=GRIS)
            y += h1 + gap
            continue
        box = (m - 16 * u, y, w - m + 16 * u, y + hl)
        _carte(c, box, int(30 * u), u)
        d = ImageDraw.Draw(c)
        # rang
        fr = C.police("Montserrat.ttf", int(min(60, hl / u * .4) * u), "ExtraBold")
        xr = box[0] + 70 * u
        d.text((xr, y + hl / 2), str(rang), font=fr, fill=at, anchor="mm")
        # pochette
        cote = int(hl - 32 * u)
        xp = int(box[0] + 128 * u)
        _pochette(c, im, xp, int(y + 16 * u), cote, int(16 * u), u, a)
        d = ImageDraw.Draw(c)
        x = xp + cote + int(26 * u)
        fs = C.police("Montserrat.ttf", int(36 * u), "ExtraBold")
        chiffre = court(t["streams"])
        cw = d.textlength(chiffre, font=fs)
        lx = box[2] - 34 * u - cw - 30 * u - x
        for taille in (34, 31, 28, 26):   # un nom long rétrécit avant d'être coupé (albums, 10/11/2026)
            fn = C.police("Montserrat.ttf", int(taille * u), "ExtraBold")
            if d.textlength(nom, font=fn) <= lx:
                break
        fv = C.police("Montserrat.ttf", int(24 * u), "Medium")
        by =int(y + hl - max(26, min(34, hl / u * .22)) * u)          # barre en bas de la carte
        ligne_nom = y + (hl * .12 if avec else (by - y - 44 * u) / 2 - 2 * u)
        d.text((x, ligne_nom), _coupe(d, nom, fn, lx), font=fn, fill=NUIT)
        if avec:
            d.text((x, ligne_nom + 42 * u), _coupe(d, avec, fv, lx), font=fv, fill=GRIS)
        # barre proportionnelle au plus écouté de la diapo (hors N°1), couleurs du pays
        bx0 = x
        bx1 = box[2] - 34 * u
        d.rounded_rectangle((bx0, by, bx1, by + 10 * u), radius=int(5 * u), fill=(228, 228, 238))
        lg = max(int(14 * u), int((bx1 - bx0) * min(1, t["streams"] / record)))
        barre = Image.new("RGB", (lg, int(10 * u)))
        db_ = ImageDraw.Draw(barre)
        for xx in range(lg):
            k = xx / max(1, lg - 1)
            db_.line((xx, 0, xx, barre.height), fill=tuple(int(a[i] * (1 - k) + b[i] * k) for i in range(3)))
        mb = Image.new("L", barre.size, 0)
        ImageDraw.Draw(mb).rounded_rectangle((0, 0, lg - 1, barre.height - 1), radius=int(5 * u), fill=255)
        c.paste(barre, (int(bx0), by), mb)
        d.text((bx1, (y + by) / 2 - 22 * u), chiffre, font=fs, fill=at, anchor="ra")
        y += hl + gap
    # pied : source et site
    fpied = C.police("Montserrat.ttf", int(24 * u), "Medium")
    yb = h - (int(70 * u) if fmt == "feed" else int(270 * u))
    d.text((m, yb), "Source : " + source, font=fpied, fill=GRIS)
    fsite = C.police("Jost.ttf", int(28 * u), "SemiBold")
    d.text((w - m, yb - 2 * u), "cauricharts.com", font=fsite, fill=at, anchor="ra")
    return c


# ---------------------------------------------------------------- tableau (portraits, 10/11/2026)

def _entete(c: Image.Image, w: int, h: int, u: float, fmt: str, titre: str, etiquette: str, artiste: str,
            pays: str | None, a, at, bandes) -> int:
    """Liseré du drapeau, logo, pastille, titre et ligne « artiste · pays » (comme les listes) ; rend le y suivant."""
    d = ImageDraw.Draw(c)
    haut = 0 if fmt == "feed" else int(170 * u)
    for i, band in enumerate(bandes):
        d.rectangle((i * w / 3, 0, (i + 1) * w / 3, int(14 * u)), fill=band if _clair(band) < .95 else (236, 236, 242))
    m = int(64 * u)
    _logo_sombre(c, m - int(8 * u), haut + int(50 * u), int(72 * u))
    d = ImageDraw.Draw(c)
    fe = C.police("Montserrat.ttf", int(23 * u), "ExtraBold")
    tw = d.textlength(etiquette, font=fe)
    ye = haut + int(60 * u)
    d.rounded_rectangle((w - m - tw - 40 * u, ye, w - m, ye + 50 * u), radius=int(25 * u), fill=at)
    d.text((w - m - tw - 20 * u, ye + 25 * u), etiquette, font=fe, fill=BLANC, anchor="lm")
    y = haut + int(160 * u)
    for taille in (76, 68, 60):
        ft = C.police("Montserrat.ttf", int(taille * u), "ExtraBold")
        if d.textlength(titre, font=ft) <= w - 2 * m:
            break
    d.text((m - 4 * u, y), titre, font=ft, fill=NUIT)
    y += int(96 * u)
    _drapeau(c, m, y + int(4 * u), int(54 * u), int(36 * u), bandes, u)
    d = ImageDraw.Draw(c)
    d.text((m + 72 * u, y + 22 * u), f"{artiste}  ·  {country_name(pays) if pays else 'Afrique de l’Ouest'}",
           font=C.police("Montserrat.ttf", int(34 * u), "SemiBold"), fill=GRIS, anchor="lm")
    return y + int(80 * u)


def tableau(rangees: list, artiste: str, pays: str | None, fmt: str = "feed", titre: str = "",
            etiquette: str = "CAURI CHARTS", colonnes: tuple = ("Place", "Titre", "Classement", "Pays"),
            source: str = "classements Cauri Charts") -> Image.Image:
    """Tableau de classements : rangees = [{"place": "N°1", "titre", "image" (URL), "sous" (facultatif),
    "col3": texte, "pays": code ISO ou None, "col4": texte si pas de pays}] (6 au plus)."""
    w, h = C.FORMATS.get(fmt, C.FORMATS["feed"])
    u = w / 1080
    a, b, bandes = couleurs(pays)
    at = accent_texte(a)
    c = _fond(w, h, a, b, u)
    y = _entete(c, w, h, u, fmt, titre, etiquette, artiste, pays, a, at, bandes)
    m = int(64 * u)
    bas = h - (int(110 * u) if fmt == "feed" else int(330 * u))
    rangees = rangees[:6]
    box = (m - 16 * u, y, w - m + 16 * u, bas)
    _carte(c, box, int(36 * u), u, BLANC, .80)
    d = ImageDraw.Draw(c)
    # colonnes (base 1080) : place | pochette + titre | classement | pays
    x0 = box[0] + 26 * u
    xs = [x0, x0 + 128 * u, x0 + 560 * u, x0 + 780 * u]
    fh = C.police("Montserrat.ttf", int(20 * u), "ExtraBold")
    yh = y + 26 * u
    for x, lab in zip(xs, colonnes):
        d.text((x + (8 * u if x == x0 else 0), yh), " ".join(lab.upper()), font=fh, fill=(130, 130, 150))
    y_l = yh + int(46 * u)
    d.line((box[0] + 20 * u, y_l - 10 * u, box[2] - 20 * u, y_l - 10 * u), fill=(220, 220, 232), width=max(1, int(2 * u)))
    hl = min(int((150 if fmt == "feed" else 190) * u), int((bas - 20 * u - y_l) / max(1, len(rangees))))
    fp = C.police("Montserrat.ttf", int(40 * u), "ExtraBold")
    fn = C.police("Montserrat.ttf", int(30 * u), "ExtraBold")
    fs = C.police("Montserrat.ttf", int(22 * u), "Medium")
    f3 = C.police("Montserrat.ttf", int(25 * u), "SemiBold")
    for k, r in enumerate(rangees):
        yy = int(y_l + k * hl)
        if k % 2 == 0:   # lignes alternées, teinte légère du pays
            taille = (int(box[2] - box[0] - 24 * u), hl - int(6 * u))
            mk = Image.new("L", taille, 0)
            ImageDraw.Draw(mk).rounded_rectangle((0, 0, taille[0] - 1, taille[1] - 1), radius=int(18 * u), fill=24)
            c.paste(Image.new("RGB", taille, a), (int(box[0] + 12 * u), yy + int(3 * u)), mk)
            d = ImageDraw.Draw(c)
        cy = yy + hl / 2
        place = str(r.get("place") or "")
        if place in ("N°1", "1"):
            pw = d.textlength(place, font=fp)
            d.rounded_rectangle((xs[0], cy - 30 * u, xs[0] + pw + 24 * u, cy + 30 * u), radius=int(30 * u), fill=at)
            d.text((xs[0] + 12 * u, cy), place, font=fp, fill=BLANC, anchor="lm")
        else:
            d.text((xs[0] + 8 * u, cy), place, font=fp, fill=at, anchor="lm")
        cote = int(hl - 34 * u)
        _pochette(c, C._image(r["image"]) if r.get("image") else None, int(xs[1]), int(cy - cote / 2), cote, int(14 * u), u, a)
        d = ImageDraw.Draw(c)
        xt = xs[1] + cote + 20 * u
        lt = xs[2] - xt - 16 * u
        nom = C.propre(r.get("titre") or "")
        if r.get("sous"):
            d.text((xt, cy - 6 * u), _coupe(d, nom, fn, lt), font=fn, fill=NUIT, anchor="ls")
            d.text((xt, cy + 8 * u), _coupe(d, r["sous"], fs, lt), font=fs, fill=GRIS, anchor="lt")
        else:
            d.text((xt, cy), _coupe(d, nom, fn, lt), font=fn, fill=NUIT, anchor="lm")
        d.text((xs[2], cy), _coupe(d, str(r.get("col3") or ""), f3, xs[3] - xs[2] - 14 * u), font=f3, fill=NUIT, anchor="lm")
        if r.get("pays"):
            bd = FLAGS.get(r["pays"].lower())
            if bd:
                _drapeau(c, int(xs[3]), int(cy - 15 * u), int(40 * u), int(28 * u), bd, u)
                d = ImageDraw.Draw(c)
            d.text((xs[3] + (52 * u if bd else 0), cy), _coupe(d, country_name(r["pays"]), f3, box[2] - xs[3] - 70 * u),
                   font=f3, fill=NUIT, anchor="lm")
        elif r.get("col4"):
            d.text((xs[3], cy), str(r["col4"]), font=f3, fill=NUIT, anchor="lm")
    fpied = C.police("Montserrat.ttf", int(24 * u), "Medium")
    yb = h - (int(70 * u) if fmt == "feed" else int(270 * u))
    d.text((m, yb), "Source : " + source, font=fpied, fill=GRIS)
    d.text((w - m, yb - 2 * u), "cauricharts.com", font=C.police("Jost.ttf", int(28 * u), "SemiBold"), fill=at, anchor="ra")
    return c
