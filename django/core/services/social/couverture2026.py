"""Couvertures 2026 (validées le 19/10/2026), à la place des anciens canevas « magazine années 80 ».

- lockup()  : classements, records, chiffres — composition typographique centrée sur plusieurs tailles (façon ChartFR),
              police Jost, l'artiste détouré en bas dans un faisceau de lumière.
- actu()    : actualité — l'artiste détouré, étiquette pastille, titre en minuscules aligné à gauche avec des mots
              surlignés (façon Kultur), police Montserrat.
Logo rond en haut ou en bas à gauche, JAMAIS sur le texte ; jamais de numéro de page. Sans photo, une illustration IA
« colors room » (personnes anonymes) sert de fond. Les bords d'une photo cadrée serré sont fondus, jamais coupés net,
et on n'invente jamais une partie du corps d'une vraie personne.
"""
import io
import re

import requests
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from core.services.platforms import log_write
from core.services.social.pourtoi import FORMATS, RES

BLANC, NUIT = (255, 255, 255), (8, 8, 18)
VIOLET, CIEL, OR = (124, 58, 237), (56, 189, 248), (255, 205, 110)
_SESSION = None


def police(nom: str, taille: int, poids: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(RES / "fonts" / nom), taille)
    if poids:
        try:
            f.set_variation_by_name(poids)
        except Exception:  # noqa: BLE001 — police non variable
            pass
    return f


def sans_bandes(im: Image.Image) -> Image.Image:
    """Retire les bandes noires « cinéma » des images de clips (haut, bas, côtés)."""
    g = im.convert("L"); g.thumbnail((400, 400)); k = im.width / g.width
    px = g.load(); w, h = g.size
    ligne = lambda y: sum(px[x, y] for x in range(w)) / w           # noqa: E731
    col = lambda x: sum(px[x, y] for y in range(h)) / h             # noqa: E731
    haut = next((y for y in range(h // 3) if ligne(y) > 14), 0)
    bas = next((y for y in range(h - 1, h * 2 // 3, -1) if ligne(y) > 14), h - 1)
    gauche = next((x for x in range(w // 3) if col(x) > 14), 0)
    droite = next((x for x in range(w - 1, w * 2 // 3, -1) if col(x) > 14), w - 1)
    marge = 2   # quelques pixels de plus : le bord de la bande est souvent flou
    return im.crop((int((gauche + marge) * k) if gauche else 0, int((haut + marge) * k) if haut else 0,
                    int((droite - marge) * k) if droite < w - 1 else im.width,
                    int((bas - marge) * k) if bas < h - 1 else im.height))


def _image(photo) -> Image.Image | None:
    if photo is None:
        return None
    try:
        if isinstance(photo, Image.Image):
            return sans_bandes(photo.convert("RGB"))
        if str(photo).startswith("http"):
            r = requests.get(str(photo), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return sans_bandes(Image.open(io.BytesIO(r.content)).convert("RGB"))
        return sans_bandes(Image.open(photo).convert("RGB"))
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"couverture 2026, photo illisible : {exc}")
        return None


def detoure(im: Image.Image) -> Image.Image | None:
    """La personne seule (RGBA), bords de la photo d'origine fondus ; None si rembg manque ou si le sujet est trop petit."""
    global _SESSION
    try:
        from rembg import new_session, remove
        _SESSION = _SESSION or new_session("u2net_human_seg")
        src = im.copy(); src.thumbnail((1600, 1600))
        cut = remove(src, session=_SESSION)
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"détourage : {exc}")
        return None
    alpha = cut.getchannel("A")
    if sum(alpha.histogram()[128:]) < 0.06 * cut.width * cut.height:
        return None
    fondu = Image.new("L", cut.size, 255); d = ImageDraw.Draw(fondu); m = int(cut.width * 0.16)
    for i in range(m):   # là où le sujet touche les bords (cadrage serré) : fondu au lieu d'une coupe nette
        v = int(255 * (i / m) ** 1.4)
        d.line((i, 0, i, cut.height), fill=v); d.line((cut.width - 1 - i, 0, cut.width - 1 - i, cut.height), fill=v)
    cut.putalpha(ImageChops.multiply(alpha, fondu))
    return cut.crop(cut.getbbox())


def _fond_projecteur(w: int, h: int, teinte=(255, 190, 90)) -> Image.Image:
    """Fond sombre avec un faisceau de lumière chaude (dessiné, gratuit : pas d'appel à l'IA)."""
    c = Image.new("RGB", (w, h), NUIT)
    lum = Image.new("L", (w, h), 0); d = ImageDraw.Draw(lum)
    d.polygon([(w * .42, 0), (w * .58, 0), (w * .86, h), (w * .14, h)], fill=70)            # faisceau
    d.ellipse((w * .12, h * .55, w * .88, h * 1.05), fill=120)                               # flaque de lumière
    lum = lum.filter(ImageFilter.GaussianBlur(w // 9))
    c.paste(Image.new("RGB", (w, h), tuple(int(t * .55) for t in teinte)), (0, 0), lum)
    return c


def _logo(c: Image.Image, x: int, y: int, d_: int) -> None:
    disque = Image.new("RGBA", (d_, d_), (0, 0, 0, 0)); ImageDraw.Draw(disque).ellipse((0, 0, d_ - 1, d_ - 1), fill=VIOLET + (255,))
    lg = Image.open(RES / "marque" / "logo-blanc.png").convert("RGBA"); lg = lg.crop(lg.getbbox())
    lg = lg.crop((0, 0, lg.height, lg.height)).resize((int(d_ * .55), int(d_ * .55)), Image.LANCZOS)
    disque.paste(lg, ((d_ - lg.width) // 2, (d_ - lg.height) // 2), lg); c.paste(disque, (x, y), disque)
    ImageDraw.Draw(c).text((x + d_ + 16, y + d_ * .28), "cauricharts", font=police("Jost.ttf", int(d_ * .42), "SemiBold"), fill=BLANC)


def _pose_sujet(c: Image.Image, sujet: Image.Image, part: float, halo=(255, 190, 90)) -> None:
    w, h = c.size
    k = min(h * part / sujet.height, w * .92 / sujet.width)
    s = sujet.resize((int(sujet.width * k), int(sujet.height * k)), Image.LANCZOS)
    x, y = (w - s.width) // 2, h - s.height
    lueur = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(lueur).ellipse((x + s.width * .1, y + s.height * .05, x + s.width * .9, h), fill=halo + (80,))
    lueur = lueur.filter(ImageFilter.GaussianBlur(w // 15)); c.paste(lueur, (0, 0), lueur)
    c.paste(s, (x, y), s)
    bas = int(h * .19); g = Image.new("L", (1, bas))
    for i in range(bas):
        g.putpixel((0, i), int(235 * (i / (bas - 1)) ** 1.6))
    c.paste(Image.new("RGB", (w, bas), NUIT), (0, h - bas), g.resize((w, bas)))


def _fond(photo_im, fond_ia, w, h):
    """(toile, sujet détouré ou None) : photo détourée sur projecteur ; sinon illustration IA ; sinon projecteur seul."""
    sujet = detoure(photo_im) if photo_im is not None else None
    if sujet is not None:
        return _fond_projecteur(w, h), sujet
    fond = _image(fond_ia) or photo_im
    if fond is not None:
        c = ImageOps.fit(fond, (w, h), Image.LANCZOS, centering=(0.5, 0.35))
        voile = Image.new("L", (1, h))
        for y in range(h):   # assombrit le haut (texte) et le bas (logo), garde le centre
            t = y / h
            voile.putpixel((0, y), int(200 * max(0, 1 - t / .55) ** 1.3 + 160 * max(0, (t - .8) / .2) ** 1.5))
        c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), voile.resize((w, h)))
        return c, None
    return _fond_projecteur(w, h), None


def lockup(photo, lignes: list, fmt: str = "feed", fond_ia=None) -> Image.Image:
    """lignes : [(texte, niveau)] avec niveau ∈ petit, moyen, grand, or (grand en doré). Ex. ChartFR :
    [("NOUVEAU RECORD :", "petit"), ("MELODRAMA", "or"), ("devient le titre resté", "petit"), ("LE PLUS LONGTEMPS", "moyen"),
     ("TOP 10", "grand"), ("de tous les temps", "petit")]"""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    c, sujet = _fond(_image(photo), fond_ia, w, h)
    if sujet is not None:
        _pose_sujet(c, sujet, 0.60 if fmt == "feed" else 0.55)
    d = ImageDraw.Draw(c)
    tailles = {"petit": (44, "Medium"), "moyen": (66, "Bold"), "grand": (128, "Black"), "or": (150, "Black")}
    y = int((60 if fmt == "feed" else 240) * u)
    for texte, niveau in lignes:
        t, poids = tailles.get(niveau, tailles["moyen"])
        t = int(t * u)
        f = police("Jost.ttf", t, poids)
        while t > 28 * u and d.textlength(texte, font=f) > w - 100 * u:   # un mot trop long rétrécit, jamais coupé
            t -= int(4 * u) or 1; f = police("Jost.ttf", t, poids)
        x = (w - d.textlength(texte, font=f)) / 2
        d.text((x + 3 * u, y + 4 * u), texte, font=f, fill=(0, 0, 0))
        d.text((x, y), texte, font=f, fill=OR if niveau == "or" else BLANC)
        y = d.textbbox((x, y), texte, font=f)[3] + int((14 if niveau != "petit" else 18) * u)
    _logo(c, int(46 * u), h - int((120 if fmt == "feed" else 260) * u), int(74 * u))
    return c


def actu(photo, etiquette: str, titre: str, surligne: list | None = None, chapo: str = "", fmt: str = "feed",
         fond_ia=None, couleur=VIOLET) -> Image.Image:
    """Actualité : étiquette pastille, titre en minuscules aligné à gauche, mots de `surligne` sur une bande de couleur."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    im = _image(photo) or _image(fond_ia)
    if im is not None:
        # Photo ENTIÈRE en plein cadre (le décor fait partie de l'image, façon Kultur), recadrée sur la personne
        cx = 0.5
        sujet = detoure(im) if photo is not None else None
        if sujet is not None:
            try:
                from rembg import remove
                petit = im.copy(); petit.thumbnail((400, 400))
                bb = remove(petit, session=_SESSION, only_mask=True).point(lambda v: 255 if v > 128 else 0).getbbox()
                cx = ((bb[0] + bb[2]) / 2) / petit.width if bb else 0.5
            except Exception:  # noqa: BLE001
                pass
        c = ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(cx, 0.3))
    else:
        c = _fond_projecteur(w, h, (170, 120, 255))
    voile = Image.new("L", (1, h))
    for y in range(h):   # bas sombre pour le texte, léger voile en haut pour le logo
        t = y / h
        voile.putpixel((0, y), int(max(235 * max(0, (t - .45) / .55) ** 1.1, 120 * max(0, 1 - t / .14))))
    c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), voile.resize((w, h)))
    d = ImageDraw.Draw(c)
    marges = int(60 * u)
    ft = police("Montserrat.ttf", int(70 * u), "ExtraBold")
    fc = police("Montserrat.ttf", int(32 * u), "Medium")
    fe = police("Montserrat.ttf", int(27 * u), "ExtraBold")
    # mise en page de bas en haut : chapô, titre, étiquette
    mots, lignes, cour = titre.split(), [], ""
    for m in mots:
        essai = (cour + " " + m).strip()
        if d.textlength(essai, font=ft) > w - 2 * marges and cour:
            lignes.append(cour); cour = m
        else:
            cour = essai
    lignes.append(cour)
    inter = int(88 * u)
    bas = h - int((130 if fmt == "feed" else 300) * u)
    y_chapo = bas - (int(46 * u) if chapo else 0)
    y_titre = y_chapo - inter * len(lignes) - int(10 * u)
    cibles = {re.sub(r"\W", "", s.lower()) for s in (surligne or []) for s in s.split()}
    y = y_titre
    for ligne in lignes:
        x = marges
        for m in ligne.split():
            lm = d.textlength(m, font=ft)
            if re.sub(r"\W", "", m.lower()) in cibles:
                d.rectangle((x - 8 * u, y + 8 * u, x + lm + 8 * u, y + inter - 6 * u), fill=couleur)
            d.text((x, y), m, font=ft, fill=BLANC)
            x += lm + d.textlength(" ", font=ft)
        y += inter
    if chapo:
        d.text((marges, y_chapo + 8 * u), chapo, font=fc, fill=(230, 230, 240))
    tw = d.textlength(etiquette, font=fe)
    ye = y_titre - int(70 * u)
    d.rounded_rectangle((marges, ye, marges + tw + 36 * u, ye + 50 * u), radius=int(25 * u), fill=CIEL)
    d.text((marges + 18 * u, ye + 9 * u), etiquette, font=fe, fill=NUIT)
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u), int(84 * u))
    return c


def texte(etiquette: str, titre: str, corps: str, pied: str = "", photo=None, fmt: str = "feed", couleur=VIOLET) -> Image.Image:
    """Diapositive de lecture : la photo floutée et assombrie en fond (ou le projecteur), étiquette, titre, texte, sources."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    im = _image(photo)
    if im is not None:
        c = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(int(28 * u)))
        c = Image.blend(c, Image.new("RGB", (w, h), NUIT), 0.72)
    else:
        c = _fond_projecteur(w, h, (170, 120, 255))
    d = ImageDraw.Draw(c)
    m = int(70 * u)
    fe = police("Montserrat.ttf", int(27 * u), "ExtraBold")
    ft = police("Montserrat.ttf", int(62 * u), "ExtraBold")
    fc = police("Montserrat.ttf", int(36 * u), "Medium")
    fp = police("Montserrat.ttf", int(26 * u), "Medium")

    def lignes(t, f, largeur):
        out, cour = [], ""
        for mot in (t or "").split():
            essai = (cour + " " + mot).strip()
            if d.textlength(essai, font=f) > largeur and cour:
                out.append(cour); cour = mot
            else:
                cour = essai
        return out + ([cour] if cour else [])

    y = int((200 if fmt == "feed" else 520) * u)
    tw = d.textlength(etiquette, font=fe)
    d.rounded_rectangle((m, y, m + tw + 36 * u, y + 50 * u), radius=int(25 * u), fill=CIEL)
    d.text((m + 18 * u, y + 9 * u), etiquette, font=fe, fill=NUIT)
    y += int(90 * u)
    for l in lignes(titre, ft, w - 2 * m):
        d.text((m, y), l, font=ft, fill=BLANC); y += int(78 * u)
    d.rectangle((m, y + 18 * u, m + 120 * u, y + 26 * u), fill=couleur)
    y += int(70 * u)
    for l in lignes(corps, fc, w - 2 * m):
        d.text((m, y), l, font=fc, fill=(232, 232, 242)); y += int(54 * u)
    if pied:
        d.text((m, h - int((200 if fmt == "feed" else 380) * u)), pied, font=fp, fill=(190, 190, 210))
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u), int(84 * u))
    return c


def classement(lignes: list, titre: str, sous_titre: str, fmt: str = "feed") -> Image.Image:
    """Liste du classement (style 2026) : dégradé violet profond, n°1 dans une pastille blanche, photos rondes.
    lignes : [{"position", "title", "artist_name", "image"}] (8 au plus en 4:5, 10 en 9:16)."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    c = Image.new("RGB", (w, h)); d = ImageDraw.Draw(c)
    for y in range(h):
        t = y / h
        d.line((0, y, w, y), fill=tuple(int(a + (b - a) * t) for a, b in zip((70, 22, 170), (10, 8, 30))))
    m = int(60 * u)
    y = int((70 if fmt == "feed" else 230) * u)
    d.text((m, y), titre, font=police("Jost.ttf", int(70 * u), "Black"), fill=BLANC)
    y += int(96 * u)
    d.text((m + 2, y), sous_titre, font=police("Jost.ttf", int(30 * u), "Medium"), fill=(215, 205, 255))
    y += int(80 * u)
    for r in lignes[:8 if fmt == "feed" else 10]:
        premier = r["position"] == 1
        hl = int((150 if premier else 104) * u)
        if premier:
            d.rounded_rectangle((m - 20 * u, y, w - m + 20 * u, y + hl), radius=hl // 2, fill=BLANC)
        fpos = police("Jost.ttf", int((66 if premier else 52) * u), "Black")
        d.text((m + (10 * u if premier else 0), y + hl / 2 - fpos.size * .62), str(r["position"]), font=fpos,
               fill=VIOLET if premier else BLANC)
        dd = int((110 if premier else 76) * u)
        im = _image(r.get("image"))
        if im is not None:
            ph = ImageOps.fit(im, (dd, dd), Image.LANCZOS, centering=(0.5, 0.3))
            masque = Image.new("L", (dd, dd)); ImageDraw.Draw(masque).ellipse((0, 0, dd - 1, dd - 1), fill=255)
            c.paste(ph, (int(m + 110 * u), int(y + (hl - dd) / 2)), masque)
        x = int(m + 110 * u + dd + 24 * u)
        ft = police("Montserrat.ttf", int((42 if premier else 33) * u), "ExtraBold")
        fa = police("Montserrat.ttf", int((28 if premier else 23) * u), "Medium")
        titre_l = r["title"]
        while d.textlength(titre_l, font=ft) > w - x - m and len(titre_l) > 4:
            titre_l = titre_l.rstrip("…")[:-1].rstrip() + "…"
        d.text((x, y + hl * (.18 if premier else .14)), titre_l, font=ft, fill=NUIT if premier else BLANC)
        d.text((x, y + hl * (.58 if premier else .56)), r["artist_name"], font=fa,
               fill=(90, 80, 120) if premier else (210, 200, 240))
        y += hl + int((22 if premier else 8) * u)
    _logo(c, int(46 * u), h - int((120 if fmt == "feed" else 260) * u), int(74 * u))
    fs = police("Jost.ttf", int(30 * u), "SemiBold")
    d.text((w - m - d.textlength("cauricharts.com", font=fs), h - int((98 if fmt == "feed" else 238) * u)),
           "cauricharts.com", font=fs, fill=BLANC)
    return c
