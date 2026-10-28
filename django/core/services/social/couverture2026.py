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
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

from core.services.platforms import log_write
from core.services.social.pourtoi import FORMATS, RES

BLANC, NUIT = (255, 255, 255), (8, 8, 18)
VIOLET, CIEL, OR = (124, 58, 237), (56, 189, 248), (255, 205, 110)
_SESSION = None


def propre(t: str) -> str:
    """Caractères absents de Montserrat/Jost remplacés (tiret insécable de « hip‑hop », espaces fines…)."""
    for a, b in (("‑", "-"), ("‐", "-"), ("‒", "-"), ("­", ""), (" ", " "), (" ", " "),
                 ("​", ""), ("⁠", "")):
        t = (t or "").replace(a, b)
    # Émojis : absents des polices du visuel (ils sortaient en carrés vides, post Toofan du 27/10/2026) ; ils restent
    # dans la légende du post
    t = re.sub("[🀀-🫿☀-➿⬀-⯿️‍⃣]", "", t)
    return re.sub(r"[ 	]{2,}", " ", t).strip()


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
    # Une vraie bande « cinéma » est SYMÉTRIQUE (haut et bas, ou gauche et droite). Un ciel de nuit noir en haut d'une
    # photo n'en est pas une : on le coupait, et la tête avec (Wizkid, 20/10/2026).
    sym = lambda a, b: a > 0 and b > 0 and abs(a - b) <= max(3, .3 * max(a, b))   # noqa: E731
    if not sym(haut, h - 1 - bas):
        haut, bas = 0, h - 1
    if not sym(gauche, w - 1 - droite):
        gauche, droite = 0, w - 1
    marge = 2   # quelques pixels de plus : le bord de la bande est souvent flou
    return im.crop((int((gauche + marge) * k) if gauche else 0, int((haut + marge) * k) if haut else 0,
                    int((droite - marge) * k) if droite < w - 1 else im.width,
                    int((bas - marge) * k) if bas < h - 1 else im.height))


def _image_nette(photo) -> Image.Image | None:
    """Comme _image, puis agrandie / retouchée si elle est petite (ameliore.py, résultat gardé dans le Blob)."""
    im = _image(photo)
    if im is None:
        return None
    from core.services.social.ameliore import ameliore
    return ameliore(im)


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


_FIN = None


def _detourage_fin(src: Image.Image) -> Image.Image | None:
    """Détourage BiRefNet (bien plus propre sur les cheveux et les bords, mais 1 à 3 min par photo) calculé UNE fois
    par image puis gardé dans le Blob (media/detoures/<empreinte>.png) ; None s'il échoue (mémoire, modèle absent)."""
    import hashlib
    global _FIN
    from core import storage
    petit = src.copy(); petit.thumbnail((64, 64))
    cle = hashlib.sha1(petit.convert("RGB").tobytes() + str(src.size).encode()).hexdigest()[:24]
    base = storage.blob_public_url()
    if base:
        try:
            r = requests.get(f"{base}/media/detoures/{cle}.png", timeout=20)
            if r.ok:
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception:  # noqa: BLE001
            pass
    try:
        from rembg import new_session, remove
        _FIN = _FIN or new_session("birefnet-general")
        cut = remove(src, session=_FIN)
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"détourage fin indisponible : {str(exc)[:120]}")
        return None
    try:
        out = io.BytesIO(); cut.save(out, format="PNG")
        storage.store_media("detoures", f"{cle}.png", out.getvalue(), "image/png")
    except Exception:  # noqa: BLE001
        pass
    return cut


def detoure(im: Image.Image, fin: bool = True) -> Image.Image | None:
    """La personne seule (RGBA), bords de la photo d'origine fondus ; None si rembg manque ou si le sujet est trop petit.
    fin : BiRefNet mis en cache (couvertures) ; sinon le modèle rapide (u2net, pour un simple recadrage)."""
    global _SESSION
    src = im.copy(); src.thumbnail((1600, 1600))
    cut = _detourage_fin(src) if fin else None
    if cut is None:
        try:
            from rembg import new_session, remove
            _SESSION = _SESSION or new_session("u2net_human_seg")
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


def _boite_personne(im: Image.Image):
    """(gauche, haut, droite, bas) de la personne en parts de l'image (masque rembg rapide), ou None."""
    global _SESSION
    try:
        from rembg import new_session, remove
        _SESSION = _SESSION or new_session("u2net_human_seg")
        petit = im.copy(); petit.thumbnail((400, 400))
        bb = remove(petit, session=_SESSION, only_mask=True).point(lambda v: 255 if v > 128 else 0).getbbox()
        return (bb[0] / petit.width, bb[1] / petit.height, bb[2] / petit.width, bb[3] / petit.height) if bb else None
    except Exception:  # noqa: BLE001
        return None


def _visages(im: Image.Image):
    """Visages [(x, y, w, h)] en parts de l'image (YuNet, OpenCV), du plus grand au plus petit ; None sans OpenCV."""
    try:
        import cv2
        import numpy as np
        from core.services.social import visages as V
        det, _rec = V._outils()
        petit = im.convert("RGB"); petit.thumbnail((1280, 1280))
        img = cv2.cvtColor(np.array(petit), cv2.COLOR_RGB2BGR)
        det.setInputSize((petit.width, petit.height))
        _n, faces = det.detect(img)
    except Exception:  # noqa: BLE001
        return None
    out = [(f[0] / petit.width, f[1] / petit.height, f[2] / petit.width, f[3] / petit.height)
           for f in (faces if faces is not None else []) if f[14] >= .6]
    # une « tête » qui déborde du cadre est presque toujours une fausse détection (décor, tissu) : on l'ignore
    out = [f for f in out if f[0] > -.01 and f[1] > -.01 and f[0] + f[2] < 1.01 and f[1] + f[3] < 1.01]
    return sorted(out, key=lambda f: -f[2] * f[3])


def photo_ok(im: Image.Image) -> bool:
    """Garde-fou avant une couverture (Awa, 20/10/2026) : tête entière dans la photo d'origine (pas déjà coupée en
    haut), pas de deuxième personne qui prend de la place. Sans OpenCV, on ne bloque pas."""
    v = _visages(im)
    if v is None:
        return True
    if not v:
        return False                             # aucun visage visible : pas une couverture d'artiste
    x, y, fw, fh = v[0]
    # le crâne (coiffure, bandana, chapeau) touche le bord haut ; en gros plan beauté (visage > 25 % de la hauteur),
    # des cheveux qui sortent du cadre sont un choix : il suffit que le front soit dans l'image
    if y - (.2 if fh > .25 else .6) * fh < .01:
        return False
    if y + fh > .98 or x < .0 or x + fw > 1.0:   # visage coupé sur un bord
        return False
    # une autre personne bien visible (visage au moins 40 % aussi grand) : elle vole la photo (garde du corps…)
    return not any(o[2] >= .4 * fw for o in v[1:])


def cadrer(im: Image.Image, w: int, h: int):
    """(image recadrée, hauteur du visage dans le cadre en part) : photo ENTIÈRE (décor d'origine) au format, centrée
    sur le visage, le haut de la tête toujours dans l'image avec de l'air (« tu as coupé des photos au niveau de la
    tête », 20/10/2026)."""
    v = _visages(im)
    bb = _boite_personne(im)
    k = max(w / im.width, h / im.height)
    sw, sh = round(im.width * k), round(im.height * k)
    grande = im.resize((sw, sh), Image.LANCZOS)
    if v:
        fx, fy, fw, fh = v[0]
        cx, haut, bas_visage = fx + fw / 2, fy - .45 * fh, fy + fh
        if bb and fy - 1.2 * fh < bb[1] < haut:  # chapeau, coiffure : le masque monte plus haut que le front
            haut = bb[1]
    elif bb:
        cx, haut, bas_visage = (bb[0] + bb[2]) / 2, bb[1], None
    else:
        cx, haut, bas_visage = .5, None, None
    x = min(max(0, round(cx * sw - w / 2)), sw - w)
    y = round((sh - h) * .25) if haut is None else min(max(0, round(haut * sh - .07 * h)), sh - h)
    if bas_visage is not None and bas_visage * sh > y + h:   # jamais le visage coupé en bas
        y = min(sh - h, round(bas_visage * sh - h * .9))
    centre = None if not v else ((v[0][1] + v[0][3] / 2) * sh - y) / h
    return grande.crop((x, y, x + w, y + h)), centre


def cadre_personne(im: Image.Image, w: int, h: int) -> Image.Image:
    return cadrer(im, w, h)[0]


def decor_ia(photo, consigne: str = "") -> Image.Image | None:
    """Décor refait par une IA d'image : la personne reste identique, le fond est recréé (style colors room) en
    respectant l'angle de la caméra, la perspective, la profondeur de champ et la lumière de la photo."""
    import base64
    from core import env
    im = _image(photo)
    key = env.get("GEMINI_API_KEY", "")
    if im is None or not key:
        return None
    src = im.convert("RGB"); src.thumbnail((1536, 1536)); buf = io.BytesIO(); src.save(buf, format="JPEG", quality=92)
    texte = ("Edit this photo. Keep the person EXACTLY as they are: same face, identity, skin, hair, pose, clothes, "
             "accessories and body proportions, no beautification, no change to the person. Replace only the background "
             "with a premium editorial set in the 'colors room' style: a seamless room of one vivid, glossy, saturated "
             "colour (sky blue, violet or warm amber) with smooth light. The new background MUST follow the original camera: "
             "same camera angle and height, same horizon line and perspective, a real floor plane with depth and distance, "
             "same lens and depth of field (background slightly out of focus if the original is), light direction and "
             "colour matching the person, realistic contact shadows on the floor. Photorealistic magazine cover quality, "
             "no text, no logo. " + (consigne or ""))
    try:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{env.get('ILLUSTRATION_MODELE', 'gemini-2.5-flash-image')}:generateContent",
                          headers={"x-goog-api-key": key}, timeout=120,
                          json={"contents": [{"parts": [{"text": texte},
                                                        {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}]}],
                                "generationConfig": {"responseModalities": ["IMAGE"]}})
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        data = next(p["inlineData"]["data"] for p in parts if p.get("inlineData", {}).get("data"))
        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"décor IA indisponible ({type(exc).__name__})")
        return None


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


VARIANTES = ("projecteur", "couleur", "cote", "bas")
# Couleur du faisceau et du grand titre : (lumière, accent du titre)
LUMIERES = [((255, 190, 90), OR), ((170, 110, 255), (205, 170, 255)), ((60, 180, 255), (120, 210, 255)),
            ((255, 80, 90), (255, 130, 130)), ((60, 220, 150), (130, 240, 190))]
# Fonds « colors room » : (fond, texte, accent) — couleurs unies et vives, accent toujours bien contrasté
COULEURS = [((112, 48, 230), BLANC, (255, 214, 10)), ((30, 160, 245), BLANC, (12, 20, 60)), ((255, 110, 20), BLANC, (20, 10, 40)),
            ((225, 30, 60), BLANC, (255, 214, 10)), ((0, 170, 110), BLANC, (255, 240, 120)), ((240, 50, 150), BLANC, (255, 230, 90))]


def _graine(lignes: list) -> int:
    import hashlib
    return int(hashlib.sha256("|".join(t for t, _ in lignes).encode("utf-8")).hexdigest(), 16)


def _fond_couleur(w: int, h: int, couleur) -> Image.Image:
    """Pièce d'une seule couleur vive : mur uni, sol un peu plus sombre, coins assombris (dessiné, sans IA)."""
    c = Image.new("RGB", (w, h), couleur)
    sol = Image.new("L", (1, h))
    for y in range(h):
        sol.putpixel((0, y), int(70 * max(0, (y / h - .62) / .38)))
    c.paste(Image.new("RGB", (w, h), tuple(int(v * .55) for v in couleur)), (0, 0), sol.resize((w, h)))
    vig = Image.new("L", (w, h), 0); ImageDraw.Draw(vig).ellipse((-w * .3, -h * .2, w * 1.3, h * 1.15), fill=255)
    vig = ImageChops.invert(vig.filter(ImageFilter.GaussianBlur(w // 6))).point(lambda v: int(v * .5))
    c.paste(Image.new("RGB", (w, h), (0, 0, 0)), (0, 0), vig)
    return c


def _place(c: Image.Image, sujet: Image.Image, hauteur: int, x_centre: float, ombre_portee: bool, halo=None,
           largeur_max: float = .95) -> None:
    """Pose le sujet détouré, pieds/buste au bas de l'image, centré sur x_centre (part de la largeur)."""
    w, h = c.size
    k = min(hauteur / sujet.height, w * largeur_max / sujet.width)
    s = sujet.resize((int(sujet.width * k), int(sujet.height * k)), Image.LANCZOS)
    x, y = int(w * x_centre - s.width / 2), h - s.height
    x = max(-int(s.width * .15), min(x, w - int(s.width * .85)))
    if halo:
        lueur = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ImageDraw.Draw(lueur).ellipse((x + s.width * .1, y + s.height * .05, x + s.width * .9, h), fill=halo + (80,))
        lueur = lueur.filter(ImageFilter.GaussianBlur(w // 15)); c.paste(lueur, (0, 0), lueur)
    if ombre_portee:
        om = Image.new("RGBA", s.size, (0, 0, 0, 0)); om.putalpha(s.getchannel("A").point(lambda v: v * 110 // 255))
        om = om.filter(ImageFilter.GaussianBlur(w // 70)); c.paste(om, (x + w // 40, y + w // 60), om)
    c.paste(s, (x, y), s)


def lockup(photo, lignes: list, fmt: str = "feed", fond_ia=None, variante: str | None = None,
           surligne: list | None = None) -> Image.Image:
    """lignes : [(texte, niveau)] avec niveau ∈ petit, moyen, grand, or (grand en couleur d'accent). Ex. ChartFR :
    [("NOUVEAU RECORD :", "petit"), ("MELODRAMA", "or"), ("devient le titre resté", "petit"), ("LE PLUS LONGTEMPS", "moyen"),
     ("TOP 10", "grand"), ("de tous les temps", "petit")]
    4 mises en page qui tournent selon le sujet (19/10/2026 : « toutes les photos exactement pareilles ») :
    projecteur (fond sombre, faisceau doré), couleur (pièce d'une couleur vive), cote (texte à gauche, artiste à droite),
    bas (artiste en grand, texte en bas)."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    g = _graine(lignes)
    im = _image_nette(photo)
    # Avec une bonne photo, on NE touche PAS à l'arrière-plan : photo entière, texte en bas (20/10/2026). Le détourage
    # (projecteur, bas) ne sert plus que sur demande explicite (variante=...).
    if im is not None and variante in (None, "plein"):
        return _lockup_plein(im, lignes, fmt, surligne)
    sujet = detoure(im) if im is not None else None
    # « texte en bas » et « de côté » seulement avec un plan large (visage tout en haut) : sur un portrait serré,
    # le texte tomberait sur le visage
    # (« cote » reste disponible à la demande mais sort de la rotation : rendu jugé trop faible le 19/10/2026)
    # Fond de couleur et « texte en bas » : seulement une personne ENTIÈRE (plan large) ; un portrait serré finit net en bas
    # de l'image, ce qui se voit sur la couleur (« les personnes sont coupées », 19/10/2026) -> projecteur, où le noir l'absorbe
    # Fond de couleur unie retiré de la rotation (19/10/2026) : le moindre défaut de détourage s'y voit. La variété vient
    # de la couleur du projecteur (LUMIERES) et de la mise en page (texte en haut, ou en bas pour un plan large).
    permises = ("projecteur", "bas") if sujet is not None and sujet.height / sujet.width >= 1.4 else ("projecteur",)
    v = variante or (permises[g % len(permises)] if sujet is not None else "projecteur")
    # personne en pied (silhouette fine) : sous un texte en haut elle n'aurait que la moitié de l'image et paraîtrait
    # minuscule (Wizkid, 20/10/2026) -> artiste en grand, texte en bas sur les jambes (jamais sur le visage)
    if variante is None and sujet is not None and sujet.height / sujet.width >= 2.0:
        v = "bas"
    lumiere, accent_l = LUMIERES[(g // 11) % len(LUMIERES)]
    fond_c, texte_c, accent = (None, BLANC, accent_l)
    if v in ("couleur", "cote"):
        # la couleur du fond qui tranche le plus avec la tenue de l'artiste (robe violette sur fond violet, 19/10/2026),
        # puis la graine pour varier entre les deux meilleures
        moy = ImageStat.Stat(sujet.convert("RGB"), mask=sujet.getchannel("A").point(lambda a: 255 if a > 128 else 0)).mean
        ecart = lambda col: sum((a - b) ** 2 for a, b in zip(col[0], moy))   # noqa: E731
        meilleures = sorted(COULEURS, key=ecart, reverse=True)[:2]
        fond_c, texte_c, accent = meilleures[(g // 7) % 2]
    if sujet is None:
        c, _ = _fond(im, fond_ia, w, h)
    elif v in ("couleur", "cote"):
        c = _fond_couleur(w, h, fond_c)
    else:
        c = _fond_projecteur(w, h, lumiere)
    d = ImageDraw.Draw(c)
    echelle = .72 if v == "cote" else 1
    largeur = (w * .46 if v == "cote" else w - 100 * u)
    tailles = {"petit": (44, "Medium"), "moyen": (66, "Bold"), "grand": (128, "Black"), "or": (150, "Black")}
    plan, y = [], int((60 if fmt == "feed" else 240) * u)
    for texte, niveau in lignes:
        t, poids = tailles.get(niveau, tailles["moyen"])
        t = int(t * u * echelle)
        f = police("Jost.ttf", t, poids)
        while t > 24 * u and d.textlength(texte, font=f) > largeur:   # un mot trop long rétrécit, jamais coupé
            t -= int(3 * u) or 1; f = police("Jost.ttf", t, poids)
        plan.append([texte, f, niveau, d.textlength(texte, font=f)])
        y = d.textbbox((0, y), texte, font=f)[3] + int((14 if niveau != "petit" else 18) * u * echelle)
    hauteur_texte = y - int((60 if fmt == "feed" else 240) * u)
    if v == "bas" and sujet is not None:
        _place(c, sujet, int(h * .92), .5, False, halo=lumiere)
        voile = Image.new("L", (1, h))
        for yy in range(h):
            voile.putpixel((0, yy), int(240 * max(0, (yy / h - .42) / .58) ** 1.1))
        c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), voile.resize((w, h)))
        y0 = h - hauteur_texte - int((150 if fmt == "feed" else 330) * u)
    elif v == "cote" and sujet is not None:
        _place(c, sujet, int(h * .95), .73, True, largeur_max=.66)
        y0 = int((h - hauteur_texte) * .42)
    else:
        if sujet is not None:
            _place(c, sujet, int(min(.60 if fmt == "feed" else .55, (h - y - 30 * u) / h) * h), .5, v == "couleur",
                   halo=lumiere if v == "projecteur" else None)
        y0 = int((60 if fmt == "feed" else 240) * u)
    # Bas de l'image fondu dans le sol : noir sur les fonds sombres, couleur du sol sur les fonds de couleur
    bas = int(h * .19); gb = Image.new("L", (1, bas))
    for i in range(bas):
        gb.putpixel((0, i), int(235 * (i / (bas - 1)) ** 1.6))
    sol = tuple(int(x * .45) for x in fond_c) if v in ("couleur", "cote") else NUIT
    c.paste(Image.new("RGB", (w, bas), sol), (0, h - bas), gb.resize((w, bas)))
    d = ImageDraw.Draw(c)
    y = y0
    for texte, f, niveau, lt in plan:
        x = int(70 * u) if v == "cote" else (w - lt) / 2
        couleur = accent if niveau == "or" else texte_c
        if v in ("projecteur", "bas"):
            d.text((x + 3 * u, y + 4 * u), texte, font=f, fill=(0, 0, 0))
        d.text((x, y), texte, font=f, fill=couleur)
        y = d.textbbox((x, y), texte, font=f)[3] + int((14 if niveau != "petit" else 18) * u * echelle)
    _logo(c, int(46 * u), (int(50 * u) if v == "bas" else h - int((120 if fmt == "feed" else 260) * u)), int(74 * u))
    return c


def _phrase(t: str) -> str:
    """Capitales « années 80 » -> casse normale (HEAVEN BABY -> Heaven Baby) ; N°, sigles courts gardés."""
    return t if not t.isupper() or len(t) <= 4 else " ".join(m if len(m) <= 3 and m.isalpha() and m in ("DJ", "MC") else m.capitalize() for m in t.split())


def _surligne_ligne(d, x: float, y: float, texte_l: str, f, cibles: set, couleur, u: float, haut_l: int,
                    encre=BLANC) -> None:
    """Écrit une ligne ; les mots de `cibles` qui se suivent sont surlignés d'UN seul bloc continu."""
    mots = texte_l.split(); esp = d.textlength(" ", font=f); pos = []
    xx = x
    for m in mots:
        lm = d.textlength(m, font=f); pos.append((xx, lm, re.sub(r"\W", "", m.lower()) in cibles)); xx += lm + esp
    k = 0
    while k < len(pos):
        if pos[k][2]:
            j = k
            while j + 1 < len(pos) and pos[j + 1][2]:
                j += 1
            d.rectangle((pos[k][0] - 8 * u, y + 6 * u, pos[j][0] + pos[j][1] + 8 * u, y + haut_l + 2 * u), fill=couleur)
            k = j + 1
        else:
            k += 1
    for (xx, _lm, c_), m in zip(pos, mots):
        d.text((xx, y), m, font=f, fill=BLANC if c_ else encre)


def _voile(c: Image.Image, y_texte0: int, y_texte1: int, en_haut: bool, plafond: int = 250) -> None:
    """Voile sombre côté texte, plus fort si le décor derrière est chargé (rayures, rue) ; léger voile côté logo."""
    w, h = c.size
    zone = c.crop((0, max(0, y_texte0), w, min(h, y_texte1))).convert("L")
    charge = ImageStat.Stat(zone.filter(ImageFilter.FIND_EDGES)).mean[0] if zone.height > 0 else 20
    fort = int(min(plafond, 215 + charge * 1.2))
    v = Image.new("L", (1, h))
    for yy in range(h):
        t = yy / h
        if en_haut:
            fin = min(1, (y_texte1 + 120) / h)
            a = fort * min(1, max(0, (fin - t) / max(.01, fin - y_texte1 / h + .08))) ** 1.1
        else:
            debut = max(0, (y_texte0 - 260) / h)
            a = fort * min(1, max(0, (t - debut) / max(.01, y_texte0 / h + .05 - debut))) ** 1.15
            a = max(a, 110 * max(0, 1 - t / .13))
        v.putpixel((0, yy), int(a))
    c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), v.resize((w, h)))


def _lockup_plein(im: Image.Image, lignes: list, fmt: str, surligne: list | None = None) -> Image.Image:
    """Lockup sur la photo entière (charte 2026, avis d'Awa 20/10/2026) : étiquette pastille, « N°x » en très grand,
    titre en casse normale aligné à gauche, nom de l'artiste surligné d'un bloc ; texte en bas, ou en haut quand le
    visage est bas dans le cadre ; voile adapté au décor."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    c, centre = cadrer(im.convert("RGB"), w, h)
    d = ImageDraw.Draw(c)
    marge = int(64 * u)
    cibles = {re.sub(r"\W", "", m.lower()) for s_ in (surligne or []) for m in s_.split()}
    etiquette = next((t for t, n in lignes if n == "petit"), "")
    corps = [(t, n) for t, n in lignes if not (n == "petit" and t == etiquette)]
    styles = {"or": (int(190 * u), police("Montserrat.ttf", int(190 * u), "Black"), CIEL),
              "grand": (int(120 * u), police("Montserrat.ttf", int(120 * u), "Black"), BLANC),
              "moyen": (int(62 * u), police("Montserrat.ttf", int(62 * u), "ExtraBold"), BLANC),
              "petit": (int(42 * u), police("Montserrat.ttf", int(42 * u), "SemiBold"), (232, 232, 242))}
    plan = []
    for t, n in corps:
        t = _phrase(t)
        taille, f, coul = styles.get(n, styles["moyen"])
        while d.textlength(t, font=f) > w - 2 * marge and taille > 24 * u:
            taille -= int(3 * u) or 1; f = police("Montserrat.ttf", taille, "Black" if n in ("or", "grand") else "ExtraBold" if n == "moyen" else "Medium")
        bb = d.textbbox((0, 0), t, font=f)
        plan.append((t, n, f, coul, bb[1], bb[3] - bb[1], int((18 if n == "or" else 14) * u)))
    fe = police("Montserrat.ttf", int(28 * u), "ExtraBold")
    h_eti = int(52 * u) + int(26 * u) if etiquette else 0
    total = h_eti + sum(ht + esp for *_x, ht, esp in plan)
    en_haut = centre is not None and centre > .55            # visage bas dans le cadre : le texte monte
    y0 = int((170 if fmt == "feed" else 300) * u) if en_haut else h - int((110 if fmt == "feed" else 330) * u) - total
    _voile(c, y0, y0 + total, en_haut, plafond=175)   # la photo doit vivre (Awa : « aplat presque noir »)
    d = ImageDraw.Draw(c)
    y = y0
    if etiquette:
        tw = d.textlength(etiquette.upper(), font=fe)
        d.rounded_rectangle((marge, y, marge + tw + 36 * u, y + 52 * u), radius=int(26 * u), fill=CIEL)
        d.text((marge + 18 * u, y + 10 * u), etiquette.upper(), font=fe, fill=NUIT)
        y += h_eti
    for t, n, f, coul, dy, ht, esp in plan:
        if n == "or":
            d.text((marge + 3 * u, y - dy + 5 * u), t, font=f, fill=(0, 0, 0))
            d.text((marge, y - dy), t, font=f, fill=coul)
        else:
            _surligne_ligne(d, marge, y - dy, t, f, cibles, VIOLET, u, ht + dy)
        y += ht + esp
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u) if not en_haut else h - int(130 * u), int(80 * u))
    return c


def actu(photo, etiquette: str, titre: str, surligne: list | None = None, chapo: str = "", fmt: str = "feed",
         fond_ia=None, couleur=VIOLET, variante: str | None = None) -> Image.Image:
    """Actualité : étiquette pastille, titre en minuscules aligné à gauche, mots de `surligne` sur une bande de couleur."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    im = _image_nette(photo) or _image(fond_ia)
    if im is not None:
        # Photo ENTIÈRE en plein cadre (le décor fait partie de l'image, façon Kultur), recadrée sur la personne,
        # le haut de la tête toujours dans l'image
        c, centre = cadrer(im.convert("RGB"), w, h)
    else:
        c, centre = _fond_projecteur(w, h, (170, 120, 255)), None
    d = ImageDraw.Draw(c)
    marges = int(60 * u)
    ft = police("Montserrat.ttf", int(70 * u), "ExtraBold")
    fc = police("Montserrat.ttf", int(32 * u), "Medium")
    fe = police("Montserrat.ttf", int(27 * u), "ExtraBold")
    # mise en page de bas en haut : chapô, titre, étiquette
    mots, lignes, cour = propre(titre).split(), [], ""
    for m in mots:
        essai = (cour + " " + m).strip()
        if d.textlength(essai, font=ft) > w - 2 * marges and cour:
            lignes.append(cour); cour = m
        else:
            cour = essai
    lignes.append(cour)
    inter = int(88 * u)
    hauteur_bloc = int(70 * u) + inter * len(lignes) + int(10 * u) + (int(46 * u) if chapo else 0)
    en_haut = centre is not None and centre > .55            # visage bas dans le cadre : le texte monte
    if en_haut:
        y_titre = int((170 if fmt == "feed" else 300) * u) + int(70 * u)
        y_chapo = y_titre + inter * len(lignes) + int(10 * u)
    else:
        bas = h - int((130 if fmt == "feed" else 300) * u)
        y_chapo = bas - (int(46 * u) if chapo else 0)
        y_titre = y_chapo - inter * len(lignes) - int(10 * u)
    # variété (Awa, 20/10/2026) : un post sur deux en « carte de verre » (charte : blanc, effet verre), sinon voile sombre
    verre = (variante or ("verre" if _graine([(titre, "")]) % 2 else "voile")) == "verre"
    if verre:
        bx0, by0 = marges - int(26 * u), y_titre - int(70 * u) - int(30 * u)
        bx1, by1 = w - marges + int(26 * u), y_titre - int(70 * u) + hauteur_bloc + int(30 * u)
        zone = c.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(int(26 * u)))
        zone = Image.blend(zone, Image.new("RGB", zone.size, BLANC), .74)
        masque = Image.new("L", zone.size, 0)
        ImageDraw.Draw(masque).rounded_rectangle((0, 0, zone.width - 1, zone.height - 1), radius=int(34 * u), fill=255)
        ombre = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ImageDraw.Draw(ombre).rounded_rectangle((bx0, by0 + int(10 * u), bx1, by1 + int(10 * u)), radius=int(34 * u), fill=(0, 0, 0, 90))
        c.paste(ombre.filter(ImageFilter.GaussianBlur(int(18 * u))), (0, 0), ombre.filter(ImageFilter.GaussianBlur(int(18 * u))))
        c.paste(zone, (bx0, by0), masque)
        haut_v = Image.new("L", (1, h))
        for yy in range(h):
            haut_v.putpixel((0, yy), int(110 * max(0, 1 - yy / h / .13)))
        c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), haut_v.resize((w, h)))
    else:
        _voile(c, y_titre - int(70 * u), y_titre - int(70 * u) + hauteur_bloc, en_haut)
    d = ImageDraw.Draw(c)
    cibles = {re.sub(r"\W", "", m.lower()) for s_ in (surligne or []) for m in s_.split()}
    y = y_titre
    for ligne in lignes:
        _surligne_ligne(d, marges, y, ligne, ft, cibles, couleur, u, inter - 14 * int(u or 1), encre=NUIT if verre else BLANC)
        y += inter
    if chapo:
        d.text((marges, y_chapo + 8 * u), chapo, font=fc, fill=(70, 70, 95) if verre else (230, 230, 240))
    tw = d.textlength(etiquette, font=fe)
    ye = y_titre - int(70 * u)
    d.rounded_rectangle((marges, ye, marges + tw + 36 * u, ye + 50 * u), radius=int(25 * u), fill=VIOLET if verre else CIEL)
    d.text((marges + 18 * u, ye + 9 * u), etiquette, font=fe, fill=BLANC if verre else NUIT)
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u) if not en_haut else h - int(130 * u), int(84 * u))
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
    fc = police("Montserrat.ttf", int(42 * u), "Medium")
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
    for l in lignes(propre(titre), ft, w - 2 * m):
        d.text((m, y), l, font=ft, fill=BLANC); y += int(78 * u)
    d.rectangle((m, y + 18 * u, m + 120 * u, y + 26 * u), fill=couleur)
    y += int(70 * u)
    paragraphes = [p for p in re.split(r"\n+|(?= N°\d)", propre(corps)) if p.strip()]   # listes « N°10 … N°9 … » : une ligne chacune
    for para in paragraphes:
        for l in lignes(para.strip(), fc, w - 2 * m):
            d.text((m, y), l, font=fc, fill=(232, 232, 242)); y += int(60 * u)
        y += int(14 * u)
    if pied:
        d.text((m, h - int((200 if fmt == "feed" else 380) * u)), pied, font=fp, fill=(190, 190, 210))
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u), int(84 * u))
    return c


def chiffres(etiquette: str, titre: str, lignes: list, photo=None, fmt: str = "feed", pied: str = "",
             verre: bool = False) -> Image.Image:
    """Diapositive « chiffres » (style magazine, 20/10/2026) : chaque valeur en grand, son explication en petit dessous.
    Sombre : photo floutée et assombrie, valeurs en bleu ciel. verre : la vraie photo NETTE en plein cadre et une carte
    de verre blanche en bas (charte : blanc, effet verre), valeurs en violet. lignes : [(valeur, explication)]."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    if verre:
        return _chiffres_verre(etiquette, titre, lignes, photo, fmt, w, h, u)
    im = _image(photo)
    if im is not None:
        c = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(int(30 * u)))
        c = Image.blend(c, Image.new("RGB", (w, h), NUIT), 0.70)
    else:
        c = _fond_projecteur(w, h, (170, 120, 255))
    d = ImageDraw.Draw(c)
    m = int(70 * u)
    fe = police("Montserrat.ttf", int(27 * u), "ExtraBold")
    ft = police("Montserrat.ttf", int(58 * u), "ExtraBold")
    fd = police("Montserrat.ttf", int(32 * u), "Medium")
    lignes = [(propre(str(v)), propre(str(e))) for v, e in lignes][:5]
    taille_v = int((96 if len(lignes) <= 3 else 76) * u)
    hauteur = int(88 * u) + int(96 * u) + sum(int(taille_v * 1.08) + int(42 * u) * (1 if len(e) < 46 else 2) + int(30 * u) for _v, e in lignes)
    y = max(int((190 if fmt == "feed" else 500) * u), (h - hauteur) // 2 - int(20 * u))   # bloc centré : pas de grand vide en bas
    tw = d.textlength(etiquette, font=fe)
    d.rounded_rectangle((m, y, m + tw + 36 * u, y + 50 * u), radius=int(25 * u), fill=CIEL)
    d.text((m + 18 * u, y + 9 * u), etiquette, font=fe, fill=NUIT)
    y += int(88 * u)
    d.text((m, y), propre(titre), font=ft, fill=BLANC)
    y += int(96 * u)
    for valeur, expl in lignes:
        t = taille_v
        fv = police("Montserrat.ttf", t, "Black")
        while d.textlength(valeur, font=fv) > w - 2 * m and t > 30 * u:
            t -= int(4 * u) or 1; fv = police("Montserrat.ttf", t, "Black")
        d.text((m, y), valeur, font=fv, fill=CIEL)
        y += int(t * 1.08)
        mots, cour, rangs = expl.split(), "", []
        for mot in mots:
            essai = (cour + " " + mot).strip()
            if d.textlength(essai, font=fd) > w - 2 * m and cour:
                rangs.append(cour); cour = mot
            else:
                cour = essai
        rangs += [cour] if cour else []
        for r_ in rangs[:2]:
            d.text((m, y), r_, font=fd, fill=(225, 225, 238)); y += int(42 * u)
        y += int(30 * u)
    if pied:
        d.text((m, h - int((200 if fmt == "feed" else 380) * u)), pied, font=police("Montserrat.ttf", int(26 * u), "Medium"),
               fill=(190, 190, 210))
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u), int(84 * u))
    return c


def _chiffres_verre(etiquette, titre, lignes, photo, fmt, w, h, u) -> Image.Image:
    im = _image(photo)
    c = cadrer(im.convert("RGB"), w, h)[0] if im is not None else _fond_projecteur(w, h, (170, 120, 255))
    d = ImageDraw.Draw(c)
    m = int(64 * u)
    fe = police("Montserrat.ttf", int(26 * u), "ExtraBold")
    ft = police("Montserrat.ttf", int(50 * u), "ExtraBold")
    fd = police("Montserrat.ttf", int(30 * u), "Medium")
    lignes = [(propre(str(v)), propre(str(e))) for v, e in lignes][:4]
    tv = int(70 * u)
    hauteur = int(50 * u) + int(28 * u) + int(66 * u) + len(lignes) * (int(tv * 1.05) + int(40 * u) + int(22 * u)) + int(24 * u)
    bx0, bx1 = m - int(24 * u), w - m + int(24 * u)
    by1 = h - int((70 if fmt == "feed" else 300) * u)
    by0 = by1 - hauteur - int(40 * u)
    zone = c.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(int(26 * u)))
    zone = Image.blend(zone, Image.new("RGB", zone.size, BLANC), .80)
    masque = Image.new("L", zone.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle((0, 0, zone.width - 1, zone.height - 1), radius=int(36 * u), fill=255)
    ombre = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(ombre).rounded_rectangle((bx0, by0 + int(12 * u), bx1, by1 + int(12 * u)), radius=int(36 * u), fill=(0, 0, 0, 90))
    ombre = ombre.filter(ImageFilter.GaussianBlur(int(18 * u)))
    c.paste(ombre, (0, 0), ombre)
    c.paste(zone, (bx0, by0), masque)
    haut_v = Image.new("L", (1, h))
    for yy in range(h):
        haut_v.putpixel((0, yy), int(110 * max(0, 1 - yy / h / .13)))
    c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), haut_v.resize((w, h)))
    d = ImageDraw.Draw(c)
    y = by0 + int(34 * u)
    tw = d.textlength(etiquette, font=fe)
    d.rounded_rectangle((m, y, m + tw + 34 * u, y + 48 * u), radius=int(24 * u), fill=VIOLET)
    d.text((m + 17 * u, y + 9 * u), etiquette, font=fe, fill=BLANC)
    y += int(48 * u) + int(28 * u)
    d.text((m, y), propre(titre), font=ft, fill=NUIT)
    y += int(66 * u)
    for valeur, expl in lignes:
        t = tv; fv = police("Montserrat.ttf", t, "Black")
        while d.textlength(valeur, font=fv) > w - 2 * m and t > 30 * u:
            t -= int(4 * u) or 1; fv = police("Montserrat.ttf", t, "Black")
        d.text((m, y), valeur, font=fv, fill=VIOLET)
        y += int(tv * 1.05)
        e = expl
        while d.textlength(e, font=fd) > w - 2 * m and len(e) > 10:
            e = e[:-2].rstrip() + "…"
        d.text((m, y), e, font=fd, fill=(60, 60, 85))
        y += int(40 * u) + int(22 * u)
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


def citation(photo, phrase: str, auteur: str, contexte: str = "", fmt: str = "feed", note: str = "") -> Image.Image:
    """Citation (style 2026) : la photo plein cadre assombrie, la phrase en grand entre guillemets, l'auteur en pastille."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    im = _image_nette(photo)
    c = ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, 0.3)) if im is not None else _fond_projecteur(w, h, (170, 120, 255))
    c = Image.blend(c, Image.new("RGB", (w, h), NUIT), 0.35)
    voile = Image.new("L", (1, h))
    for y in range(h):
        voile.putpixel((0, y), int(230 * max(0, (y / h - .30) / .70) ** 0.9))
    c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), voile.resize((w, h)))
    d = ImageDraw.Draw(c)
    m = int(70 * u)
    taille = 74 if len(phrase) < 90 else 60 if len(phrase) < 150 else 50
    f = police("Montserrat.ttf", int(taille * u), "ExtraBold")
    mots, lignes, cour = f"« {propre(phrase)} »".split(), [], ""
    for mot in mots:
        essai = (cour + " " + mot).strip()
        if d.textlength(essai, font=f) > w - 2 * m and cour:
            lignes.append(cour); cour = mot
        else:
            cour = essai
    lignes.append(cour)
    inter = int(taille * 1.22 * u)
    y = h - int((210 if fmt == "feed" else 400) * u) - inter * len(lignes)
    d.text((m - 6 * u, y - int(150 * u)), "“", font=police("Montserrat.ttf", int(220 * u), "ExtraBold"), fill=VIOLET)
    for l in lignes:
        d.text((m, y), l, font=f, fill=BLANC); y += inter
    fe = police("Montserrat.ttf", int(30 * u), "ExtraBold")
    tw = d.textlength(auteur.upper(), font=fe)
    d.rounded_rectangle((m, y + 24 * u, m + tw + 40 * u, y + 80 * u), radius=int(28 * u), fill=CIEL)
    d.text((m + 20 * u, y + 34 * u), auteur.upper(), font=fe, fill=NUIT)
    bas = contexte or note
    if bas:
        d.text((m + tw + 60 * u, y + 38 * u), bas[:60], font=police("Montserrat.ttf", int(26 * u), "Medium"), fill=(220, 220, 235))
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u), int(84 * u))
    return c


def photo_simple(photo, fmt: str = "feed", credit: str = "") -> Image.Image:
    """Photo en plein cadre (carrousel du studio) : recadrée sur la personne, petit logo en haut, crédit discret en bas."""
    w, h = FORMATS.get(fmt, FORMATS["feed"])
    u = w / 1080
    im = _image_nette(photo)
    if im is None:
        return _fond_projecteur(w, h, (170, 120, 255))
    cx = 0.5
    sujet = detoure(im, fin=False)
    if sujet is not None:
        try:
            from rembg import remove
            petit = im.copy(); petit.thumbnail((400, 400))
            bb = remove(petit, session=_SESSION, only_mask=True).point(lambda v: 255 if v > 128 else 0).getbbox()
            cx = ((bb[0] + bb[2]) / 2) / petit.width if bb else 0.5
        except Exception:  # noqa: BLE001
            pass
    c = ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(cx, 0.3))
    voile = Image.new("L", (1, h))
    for y in range(h):
        t = y / h
        voile.putpixel((0, y), int(max(110 * max(0, 1 - t / .14), 150 * max(0, (t - .86) / .14))))
    c.paste(Image.new("RGB", (w, h), NUIT), (0, 0), voile.resize((w, h)))
    _logo(c, int(50 * u), int((50 if fmt == "feed" else 200) * u), int(84 * u))
    if credit:
        ImageDraw.Draw(c).text((int(50 * u), h - int((70 if fmt == "feed" else 330) * u)), f"Photo : {credit}"[:70],
                               font=police("Montserrat.ttf", int(26 * u), "Medium"), fill=(230, 230, 240))
    return c
