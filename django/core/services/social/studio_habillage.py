"""Habillage animé des vidéos du Studio (08/11/2026 : « la couverture noire avec les titres, on enlève »).

- ouverture() : plus de voile noir. Pastille en verre qui glisse depuis la gauche, accroche qui apparaît mot par mot
  (chaque mot monte avec une ombre douce collée aux lettres), nom de l'artiste sur un surlignage violet, trait
  bleu ciel -> violet qui se trace dessous ; tout redescend en fondu après quelques secondes. La vidéo reste visible.
- fin() : la dernière image se fige, se floute sous un voile blanc lumineux (blanc dominant, charte Cauri), une carte en
  verre arrive avec l'icône qui rebondit, « cauricharts », la devise et la pastille du site ; un reflet balaie la carte.
Les animations sont rendues image par image (PIL) et envoyées à ffmpeg en vidéo avec transparence (FFV1).
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter

FPS = 30
FIN_DUREE = 2.8        # secondes ajoutées après le clip pour la carte de fin
FIN_AVANCE = 0.3       # la carte commence un peu avant la dernière image du clip
DEVISE = "La référence de la musique ouest-africaine"


def _ffmpeg() -> str:
    from core.services.social.refrain import ffmpeg
    return ffmpeg()


def _sortie(i: float) -> float:          # ease-out cubique
    i = min(1.0, max(0.0, i))
    return 1 - (1 - i) ** 3


def _rebond(i: float) -> float:          # ease-out avec léger dépassement
    i = min(1.0, max(0.0, i))
    c = 1.7
    return 1 + (c + 1) * (i - 1) ** 3 + c * (i - 1) ** 2


def _alpha(im: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return im
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lambda p, _a=max(0.0, a): int(p * _a)))
    return out


def _ombre(im: Image.Image, rayon: int, force: int = 170) -> Image.Image:
    """L'élément avec une ombre douce qui épouse sa forme (pas de rectangle sombre derrière)."""
    m = rayon * 3
    grand = Image.new("RGBA", (im.width + 2 * m, im.height + 2 * m), (0, 0, 0, 0))
    a = Image.new("L", grand.size, 0)
    a.paste(im.getchannel("A"), (m, m + rayon // 3))
    a = a.filter(ImageFilter.GaussianBlur(rayon)).point(lambda p: min(255, int(p * force / 255 * 1.6)))
    sombre = Image.new("RGBA", grand.size, (4, 4, 14, 0))
    sombre.putalpha(a)
    sombre.alpha_composite(im, (m, m))
    return sombre


def _encode(images, taille: tuple[int, int], chemin: str) -> str:
    """Envoie les images RGBA à ffmpeg (vidéo FFV1 avec transparence)."""
    w, h = taille
    p = subprocess.Popen([_ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
                          "-r", str(FPS), "-i", "-", "-c:v", "ffv1", "-pix_fmt", "yuva444p", chemin],
                         stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for im in images:
            p.stdin.write(im.tobytes())
        p.stdin.close()
        err = p.stderr.read()
        if p.wait(timeout=600) != 0:
            raise RuntimeError("habillage : " + err.decode(errors="replace")[-300:])
    finally:
        if p.poll() is None:
            p.kill()
    return chemin


# ---------------------------------------------------------------- ouverture

def _elements_ouverture(W: int, etiquette: str, accroche: str, artiste: str):
    """Pastille, mots (chacun avec son ombre) et leurs positions, relatifs au haut du bloc."""
    import re
    from core.services.social import couverture2026 as C
    u = W / 1080
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    # pastille en verre : blanc translucide, liseré clair, point bleu ciel « en direct »
    fe = C.police("Montserrat.ttf", int(25 * u), "ExtraBold")
    # lettres espacées ; émojis retirés (ils sortaient en carrés vides, « Chétté 👑⚔️ », tâche 308 du 08/11/2026)
    eti = " ".join((C.propre(etiquette) or "VIDÉO").upper()[:32])
    tw = d.textlength(eti, font=fe)
    ph, pw = int(48 * u), int(tw + 74 * u)
    pastille = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    dp = ImageDraw.Draw(pastille)
    dp.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=ph // 2, fill=(255, 255, 255, 58), outline=(255, 255, 255, 170),
                         width=max(2, int(2 * u)))
    r = int(7 * u)
    dp.ellipse((int(20 * u) - r, ph // 2 - r, int(20 * u) + r, ph // 2 + r), fill=C.CIEL + (255,))
    dp.text((int(38 * u), ph // 2), eti, font=fe, fill=(255, 255, 255, 255), anchor="lm")
    pastille = _ombre(pastille, int(14 * u), 120)

    # accroche : 3 lignes au plus, la taille baisse s'il le faut
    texte = C.propre(accroche or "")
    cibles = {re.sub(r"\W", "", m.lower()) for m in (artiste or "").split()} - {""}
    for t in (64, 58, 52, 46, 42):
        f = C.police("Montserrat.ttf", int(t * u), "ExtraBold")
        lignes, cour = [], ""
        for mot in texte.split():
            essai = (cour + " " + mot).strip()
            if d.textlength(essai, font=f) > W - 110 * u and cour:
                lignes.append(cour); cour = mot
            else:
                cour = essai
        if cour:
            lignes.append(cour)
        if len(lignes) <= 3:
            break
    t = int(t * u)
    mots = []                                     # (image, x, y) — x, y : coin de l'image ombrée dans le bloc
    m_ombre = int(16 * u) * 3
    y = ph + int(26 * u)
    for ligne in lignes:
        x = 50 * u
        for mot in ligne.split():
            lm = d.textlength(mot, font=f)
            im = Image.new("RGBA", (int(lm + 20 * u), int(t * 1.35)), (0, 0, 0, 0))
            di = ImageDraw.Draw(im)
            if cibles and re.sub(r"\W", "", mot.lower()) in cibles:      # artiste : surlignage violet
                di.rounded_rectangle((0, int(t * .12), im.width - 1, int(t * 1.22)), radius=int(10 * u),
                                     fill=C.VIOLET + (235,))
                di.line((int(8 * u), int(t * .12) + 1, im.width - int(8 * u), int(t * .12) + 1),
                        fill=(255, 255, 255, 90), width=max(1, int(2 * u)))
            di.text((int(10 * u), int(t * .1)), mot, font=f, fill=(255, 255, 255, 255))
            mots.append((_ombre(im, int(16 * u)), int(x - 10 * u) - m_ombre, int(y) - m_ombre))
            x += lm + d.textlength(" ", font=f)
        y += t + int(14 * u)
    # trait dégradé bleu ciel -> violet sous l'accroche
    lt, et = int(170 * u), max(4, int(6 * u))
    trait = Image.new("RGBA", (lt, et), (0, 0, 0, 0))
    for xx in range(lt):
        k = xx / max(1, lt - 1)
        c = tuple(int(C.CIEL[i] * (1 - k) + C.VIOLET[i] * k) for i in range(3))
        ImageDraw.Draw(trait).line((xx, 0, xx, et), fill=c + (255,))
    y_trait = y + int(4 * u)
    hauteur = y_trait + et
    return pastille, mots, (trait, y_trait), hauteur


def hauteur_ouverture(W: int, etiquette: str, accroche: str, artiste: str) -> int:
    return _elements_ouverture(W, etiquette, accroche, artiste)[3]


def _image_ouverture(W: int, elements, t: float, t_sortie: float, marge: int) -> Image.Image:
    pastille, mots, (trait, y_trait), hauteur = elements
    u = W / 1080
    im = Image.new("RGBA", (W, hauteur + 2 * marge), (0, 0, 0, 0))
    s = _sortie((t - t_sortie) / 0.55) if t >= t_sortie else 0.0      # sortie : descend et s'efface
    dy_s, a_s = int(26 * u * s), 1 - s
    m_p = int(14 * u) * 3
    # pastille : glisse depuis la gauche
    k = _rebond(t / 0.5)
    x = int(-pastille.width + (50 * u - m_p + pastille.width) * k)
    if t > 0 and x + pastille.width > 0:
        p = _alpha(pastille, min(1, t / 0.25) * a_s)
        if x < 0:
            p, x = p.crop((-x, 0, p.width, p.height)), 0
        im.alpha_composite(p, (x, max(0, marge - m_p + dy_s)))
    # mots : l'un après l'autre
    for i, (mot, mx, my) in enumerate(mots):
        k = _sortie((t - 0.3 - 0.07 * i) / 0.38)
        if k <= 0:
            continue
        im.alpha_composite(_alpha(mot, k * a_s), (max(0, mx), max(0, marge + my + int(30 * u * (1 - k)) + dy_s)))
    # trait : se trace de gauche à droite
    k = _sortie((t - 0.35 - 0.07 * len(mots)) / 0.45)
    if k > 0:
        lw = max(1, int(trait.width * k))
        im.alpha_composite(_alpha(trait.crop((0, 0, lw, trait.height)), a_s), (int(50 * u), marge + y_trait + dy_s))
    return im


def ouverture(taille: tuple[int, int], haut_bloc: int, etiquette: str, accroche: str, artiste: str,
              t_sortie: float, dossier: str) -> tuple[str, int]:
    """(vidéo transparente du titre animé, y où la poser). t_sortie : moment où le titre commence à partir."""
    W, _H = taille
    el = _elements_ouverture(W, etiquette, accroche, artiste)
    marge = int(70 * W / 1080)
    n = int((t_sortie + 0.65) * FPS) + 1
    chemin = _encode((_image_ouverture(W, el, i / FPS, t_sortie, marge) for i in range(n)),
                     (W, el[3] + 2 * marge), os.path.join(dossier, "ouverture.mkv"))
    return chemin, haut_bloc - marge


def image_ouverture(taille: tuple[int, int], haut_bloc: int, etiquette: str, accroche: str, artiste: str) -> Image.Image:
    """Le titre entièrement affiché, sur un calque plein cadre (aperçu à valider dans le Studio)."""
    W, H = taille
    el = _elements_ouverture(W, etiquette, accroche, artiste)
    marge = int(70 * W / 1080)
    plein = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    plein.alpha_composite(_image_ouverture(W, el, 9.0, 99.0, marge), (0, max(0, haut_bloc - marge)))
    return plein


# ---------------------------------------------------------------- fin

def _carte_fin(W: int, H: int):
    from core.services.social import couverture2026 as C
    from core.services.social.studio_montage import _icone_carree
    u = W / 1080
    cw = int(min(W * .8, H * .62))
    icone = _ombre(_icone_carree(int(150 * u)), int(18 * u), 110)
    f_nom = C.police("Jost.ttf", int(70 * u), "SemiBold")
    f_dev = C.police("DMSans.ttf", int(29 * u), "Medium")
    f_site = C.police("Montserrat.ttf", int(26 * u), "ExtraBold")
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    devise = C.propre(DEVISE)
    # devise sur deux lignes si la carte est étroite
    lignes = [devise] if d.textlength(devise, font=f_dev) < cw - 80 * u else devise.rsplit(" ", 2)[0:1] + [" ".join(devise.rsplit(" ", 2)[1:])]
    ch = int(150 * u + 38 * u + 80 * u + 24 * u + len(lignes) * 40 * u + 34 * u + 56 * u + 70 * u)
    carte = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    dc = ImageDraw.Draw(carte)
    dc.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=int(44 * u), fill=(255, 255, 255, 178),
                         outline=(255, 255, 255, 235), width=max(2, int(2 * u)))
    # reflet du verre en haut de la carte
    hl = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(hl).rounded_rectangle((int(3 * u), int(3 * u), cw - int(3 * u), int(ch * .42)), radius=int(42 * u), fill=40)
    blanc = Image.new("RGBA", (cw, ch), (255, 255, 255, 0)); blanc.putalpha(hl.filter(ImageFilter.GaussianBlur(int(10 * u))))
    carte.alpha_composite(blanc)
    y = int(150 * u + 38 * u + 40 * u)            # l'icône est posée à part (elle rebondit)
    elements = []                                  # (image, x, y, début de l'apparition)
    def _texte(txt, f, couleur, y0, debut):
        tw = int(d.textlength(txt, font=f)) + 4
        im = Image.new("RGBA", (tw, int(f.size * 1.35)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((2, 0), txt, font=f, fill=couleur)
        elements.append((im, (cw - tw) // 2, y0, debut))
    _texte("cauricharts", f_nom, C.NUIT + (255,), y, 0.62)
    y += int(80 * u) + int(24 * u)
    for k, l in enumerate(lignes):
        _texte(l, f_dev, C.NUIT + (205,), y, 0.85 + 0.08 * k)
        y += int(40 * u)
    y += int(34 * u)
    site = "cauricharts.com"
    sw = int(d.textlength(site, font=f_site) + 64 * u)
    pill = Image.new("RGBA", (sw, int(56 * u)), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle((0, 0, sw - 1, int(56 * u) - 1), radius=int(28 * u), fill=C.VIOLET + (255,))
    ImageDraw.Draw(pill).text((sw // 2, int(28 * u)), site, font=f_site, fill=(255, 255, 255, 255), anchor="mm")
    elements.append((pill, (cw - sw) // 2, y, 1.05))
    return carte, icone, elements


def _fond_fin(W: int, H: int) -> Image.Image:
    """Voile blanc lumineux avec deux halos (bleu ciel, violet)."""
    from core.services.social import couverture2026 as C
    f = Image.new("RGBA", (W, H), (255, 255, 255, 120))
    for (cx, cy, r, c, a) in ((.2, .25, .55, C.CIEL, 120), (.85, .75, .6, C.VIOLET, 95)):
        halo = Image.new("L", (W // 4, H // 4), 0)
        R = r * W / 4
        ImageDraw.Draw(halo).ellipse((cx * W / 4 - R, cy * H / 4 - R, cx * W / 4 + R, cy * H / 4 + R), fill=a)
        halo = halo.filter(ImageFilter.GaussianBlur(int(W / 4 * .12))).resize((W, H), Image.BILINEAR)
        couche = Image.new("RGBA", (W, H), c + (0,)); couche.putalpha(halo)
        f.alpha_composite(couche)
    return f


def _image_fin(W: int, H: int, fond, carte, icone, elements, t: float) -> Image.Image:
    u = W / 1080
    im = _alpha(fond, _sortie(t / 0.55))
    k = _sortie((t - 0.25) / 0.5)
    if k > 0:
        s = 0.9 + 0.1 * k
        c = carte.resize((max(1, int(carte.width * s)), max(1, int(carte.height * s))), Image.BILINEAR)
        c = c.copy()
        # éléments de la carte (texte, pastille) qui montent en fondu
        for (el, ex, ey, debut) in elements:
            ke = _sortie((t - debut) / 0.4)
            if ke > 0:
                el_s = el.resize((max(1, int(el.width * s)), max(1, int(el.height * s))), Image.BILINEAR)
                c.alpha_composite(_alpha(el_s, ke), (int(ex * s), int((ey + 18 * u * (1 - ke)) * s)))
        # reflet qui balaie la carte
        kb = (t - 1.3) / 0.6
        if 0 < kb < 1:
            bande = Image.new("L", c.size, 0)
            x0 = int(-c.width * .4 + c.width * 1.6 * kb)
            ImageDraw.Draw(bande).polygon([(x0, 0), (x0 + int(90 * u), 0), (x0 + int(90 * u) - c.height // 3, c.height),
                                           (x0 - c.height // 3, c.height)], fill=95)
            bande = Image.composite(bande, Image.new("L", c.size, 0), c.getchannel("A").point(lambda p: 255 if p > 100 else 0))
            blanc = Image.new("RGBA", c.size, (255, 255, 255, 0)); blanc.putalpha(bande.filter(ImageFilter.GaussianBlur(int(6 * u))))
            c.alpha_composite(blanc)
        c = _alpha(c, k)
        x, y = (W - c.width) // 2, int(H * .5 - c.height / 2 + 30 * u * (1 - k))
        im.alpha_composite(c, (x, y))
        # icône : rebondit en haut de la carte
        ki = (t - 0.4) / 0.5
        if ki > 0:
            z = max(0.05, _rebond(ki))
            ic = icone.resize((max(1, int(icone.width * z * s)), max(1, int(icone.height * z * s))), Image.BILINEAR)
            cy_icone = y + int((38 * u + 75 * u) * s)
            im.alpha_composite(_alpha(ic, min(1, ki * 3)), ((W - ic.width) // 2, cy_icone - ic.height // 2))
    return im


def fin(taille: tuple[int, int], dossier: str) -> str:
    """Vidéo transparente de la carte de fin (FIN_AVANCE + FIN_DUREE secondes)."""
    W, H = taille
    fond = _fond_fin(W, H)
    carte, icone, elements = _carte_fin(W, H)
    n = int((FIN_AVANCE + FIN_DUREE) * FPS)
    return _encode((_image_fin(W, H, fond, carte, icone, elements, i / FPS) for i in range(n)), (W, H),
                   os.path.join(dossier, "fin.mkv"))


def apercu_fin(taille: tuple[int, int], fond_video: Image.Image) -> Image.Image:
    """La carte de fin telle qu'elle apparaît (pour vérifier le rendu sans monter toute une vidéo)."""
    W, H = taille
    carte, icone, elements = _carte_fin(W, H)
    base = fond_video.convert("RGBA").resize((W, H)).filter(ImageFilter.GaussianBlur(int(22 * W / 1080)))
    base.alpha_composite(_image_fin(W, H, _fond_fin(W, H), carte, icone, elements, 2.4))
    return base.convert("RGB")

