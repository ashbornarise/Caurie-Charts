"""Vidéo « paroles » (lyric video, 10/11/2026) : la pochette en grand, les paroles qui s'allument mot par mot au rythme
de la chanson, aux couleurs du pays de l'artiste.

Paroles minutées : LRCLIB (lignes) ou transcription Whisper (mots) relue par le fondateur. Le son : l'extrait du titre.
Rendu image par image (PIL) envoyé à ffmpeg, avec le son coupé au même endroit et mis à −14 LUFS.

lignes : [{"debut": s, "fin": s, "mots": [{"m": "mot", "d": s, "f": s}]}] en secondes DU MORCEAU ; t0, t1 : l'extrait.
"""
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from core.services.social import couverture2026 as C
from core.services.social import top_titres as T

FPS = 30
BLANC, NUIT, GRIS = (255, 255, 255), (14, 14, 28), (150, 150, 170)
TAILLES = {"story": (1080, 1920), "feed": (1080, 1350)}


def _ffmpeg() -> str:
    from core.services.social.refrain import ffmpeg
    return ffmpeg()


def _sortie(i: float) -> float:
    i = min(1.0, max(0.0, i))
    return 1 - (1 - i) ** 3


def _decor(cover: Image.Image, w: int, h: int, a, b) -> Image.Image:
    """Fond : la pochette floutée sous un voile blanc lumineux, deux taches aux couleurs du pays."""
    fond = ImageOps.fit(cover.convert("RGB"), (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(60))
    fond = Image.blend(fond, Image.new("RGB", (w, h), (250, 250, 253)), .72)
    voile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(voile)
    d.ellipse((w * .45, -h * .12, w * 1.5, h * .38), fill=a + (60,))
    d.ellipse((-w * .5, h * .72, w * .55, h * 1.15), fill=b + (55,))
    voile = voile.filter(ImageFilter.GaussianBlur(140))
    fond.paste(voile, (0, 0), voile)
    return fond


def _carte_pochette(cover: Image.Image, cote: int) -> Image.Image:
    """La pochette arrondie avec son ombre douce (RGBA, marge autour pour l'ombre)."""
    m = int(cote * .12)
    im = ImageOps.fit(cover.convert("RGB"), (cote, cote), Image.LANCZOS)
    masque = Image.new("L", (cote, cote), 0)
    ImageDraw.Draw(masque).rounded_rectangle((0, 0, cote - 1, cote - 1), radius=int(cote * .05), fill=255)
    out = Image.new("RGBA", (cote + 2 * m, cote + 2 * m), (0, 0, 0, 0))
    ombre = Image.new("L", out.size, 0)
    ImageDraw.Draw(ombre).rounded_rectangle((m, m + int(cote * .03), m + cote, m + cote + int(cote * .03)),
                                            radius=int(cote * .05), fill=120)
    ombre = ombre.filter(ImageFilter.GaussianBlur(int(cote * .04)))
    out.paste(Image.new("RGBA", out.size, (20, 20, 40, 255)), (0, 0), ombre)
    out.paste(im, (m, m), masque)
    return out


def _coupe_lignes(d, mots: list, f, largeur: float) -> list:
    """Répartit les mots d'une phrase en lignes d'affichage qui tiennent dans la largeur."""
    lignes, cour = [], []
    for w in mots:
        essai = " ".join(x["m"].strip() for x in cour + [w])
        if cour and d.textlength(essai, font=f) > largeur:
            lignes.append(cour); cour = [w]
        else:
            cour.append(w)
    if cour:
        lignes.append(cour)
    return lignes


def _phrase(d, mots: list, t: float, f, x_centre: float, y: int, couleur, largeur: float, opacite: float = 1.0,
            active: bool = True, lum=None, toile=None) -> int:
    """Dessine une phrase centrée et rend sa hauteur.
    Phrase en cours (active) : chaque mot se remplit de couleur de gauche à droite pendant qu'il est chanté (karaoké),
    puis reste en encre ; à venir en gris clair. lum : calque où sont dessinés les mots allumés (halo lumineux)."""
    lignes = _coupe_lignes(d, mots, f, largeur)
    hl = int(f.size * 1.28)
    a = int(255 * opacite)
    for ligne in lignes:
        txt = [w["m"].strip() for w in ligne]
        tw = d.textlength(" ".join(txt), font=f)
        x = x_centre - tw / 2
        for w, s in zip(ligne, txt):
            lw = d.textlength(s, font=f)
            if not active:
                d.text((x, y), s, font=f, fill=(120, 120, 142, int(a * .8)))
            elif t >= w["f"]:                                   # déjà chanté : encre, lueur douce
                d.text((x, y), s, font=f, fill=NUIT + (a,))
                if lum is not None:
                    lum.text((x, y), s, font=f, fill=couleur + (int(70 * opacite),))
            elif t >= w["d"]:                                   # en cours : remplissage progressif + halo fort
                k = (t - w["d"]) / max(.08, w["f"] - w["d"])
                d.text((x, y), s, font=f, fill=(118, 118, 140, a))
                calque = Image.new("RGBA", (int(lw) + 4, int(f.size * 1.4)), (0, 0, 0, 0))
                ImageDraw.Draw(calque).text((0, 0), s, font=f, fill=couleur + (a,))
                calque = calque.crop((0, 0, max(1, int(calque.width * min(1, k))), calque.height))
                toile.alpha_composite(calque, (int(x), int(y)))
                if lum is not None:
                    lum.text((x, y), s, font=f, fill=couleur + (255,))
            else:
                d.text((x, y), s, font=f, fill=(118, 118, 140, a))
            x += d.textlength(s + " ", font=f)
        y += hl
    return hl * len(lignes)


def rendu(source_audio: str, cover, lignes: list, t0: float, t1: float, titre: str, artistes: str, album: str,
          pays: str | None, sortie: str, fmt: str = "story") -> str:
    w, h = TAILLES[fmt]
    u = w / 1080
    a, b, _bandes = T.couleurs(pays)
    at = T.accent_texte(a)
    cov = C._image(cover) if not isinstance(cover, Image.Image) else cover
    fond = _decor(cov, w, h, a, b)
    cote = int((720 if fmt == "story" else 480) * u)
    carte = _carte_pochette(cov, cote)
    y_cov = int((290 if fmt == "story" else 100) * u)
    ft = C.police("Montserrat.ttf", int((64 if fmt == "story" else 54) * u), "ExtraBold")
    fv = C.police("Montserrat.ttf", int((40 if fmt == "story" else 34) * u), "Bold")
    fti = C.police("Montserrat.ttf", int(40 * u), "ExtraBold")
    fa = C.police("Montserrat.ttf", int(28 * u), "SemiBold")
    largeur = w - 2 * int(80 * u)
    y_par = y_cov + cote + int((110 if fmt == "story" else 70) * u)
    dur = t1 - t0
    phr = [l for l in lignes if l["fin"] > t0 - 4 and l["debut"] < t1 + 1 and l["mots"]]

    def image(i: int) -> Image.Image:
        t = t0 + i / FPS
        c = fond.copy()
        # pochette : respiration lente
        k = 1 + .025 * (i / max(1, dur * FPS))
        cw = int(carte.width * k)
        cc = carte.resize((cw, cw), Image.BILINEAR) if k != 1 else carte
        c.paste(cc, ((w - cw) // 2, y_cov - int(cote * .12) - (cw - carte.width) // 2), cc)
        # paroles sur un calque transparent ; les mots allumés sur un 2e calque flouté (halo lumineux)
        texte = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(texte)
        lum_im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        lum = ImageDraw.Draw(lum_im)
        # phrase en cours (ou la dernière commencée), la précédente au-dessus, la suivante en dessous
        idx = max([j for j, l in enumerate(phr) if l["debut"] - .15 <= t] or [0])
        cur = phr[idx] if phr else None
        if cur:
            entree = _sortie((t - (cur["debut"] - .15)) / .3)
            dy = int(40 * u * (1 - entree))
            if idx > 0:
                _phrase(d, phr[idx - 1]["mots"], t, fv, w / 2, y_par - int(10 * u) + dy, at, largeur, .35, False)
            y = y_par + int(80 * u) + dy
            hcur = _phrase(d, cur["mots"], t, ft, w / 2, y, at, largeur, entree, True, lum, texte)
            # la phrase suivante seulement si elle tient au-dessus du titre (jamais de texte sur le bas de l'écran)
            y_suiv = y + hcur + int(30 * u)
            if idx + 1 < len(phr) and y_suiv + len(_coupe_lignes(d, phr[idx + 1]["mots"], fv, largeur)) * fv.size * 1.28 \
                    < h - int((330 if fmt == "story" else 170) * u) - int(50 * u):
                _phrase(d, phr[idx + 1]["mots"], -1, fv, w / 2, y_suiv, at, largeur, .5, False)
        c = c.convert("RGBA")
        y_b0, y_b1 = max(0, y_par - int(120 * u)), min(h, y_par + int(760 * u))   # halo : seulement la bande des paroles
        halo = lum_im.crop((0, y_b0, w, y_b1)).filter(ImageFilter.GaussianBlur(int(22 * u)))
        c.alpha_composite(halo, (0, y_b0)); c.alpha_composite(halo.filter(ImageFilter.GaussianBlur(int(8 * u))), (0, y_b0))
        c.alpha_composite(texte)
        c = c.convert("RGB")
        d = ImageDraw.Draw(c)
        # bas : titre, artistes · album, logo
        yb = h - int((330 if fmt == "story" else 170) * u)
        d.text((w / 2, yb), titre, font=fti, fill=NUIT, anchor="mm")
        d.text((w / 2, yb + 50 * u), f"{artistes}  ·  {album}", font=fa, fill=(90, 90, 112), anchor="mm")
        d.rounded_rectangle((w / 2 - 60 * u, yb + 86 * u, w / 2 + 60 * u, yb + 92 * u), radius=int(3 * u), fill=at)
        T._logo_sombre(c, int(50 * u), int((150 if fmt == "story" else 30) * u), int(60 * u))
        if i < 8:   # ouverture en fondu depuis le blanc
            c = Image.blend(Image.new("RGB", (w, h), BLANC), c, i / 8)
        return c

    n = int(dur * FPS)
    cmd = [_ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
           "-ss", f"{t0:.2f}", "-t", f"{dur:.2f}", "-i", source_audio, "-map", "0:v", "-map", "1:a",
           "-af", f"loudnorm=I=-14:TP=-1.5,afade=t=in:d=0.4,afade=t=out:st={dur - .8:.2f}:d=0.8",
           "-vf", f"fade=t=out:st={dur - .5:.2f}:d=0.5",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-ar", "48000", "-movflags", "+faststart", "-shortest", sortie]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            p.stdin.write(image(i).tobytes())
        p.stdin.close()
        err = p.stderr.read()
        if p.wait(timeout=900) != 0:
            raise RuntimeError("vidéo paroles : " + err.decode(errors="replace")[-400:])
    finally:
        if p.poll() is None:
            p.kill()
    return sortie
