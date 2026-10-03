"""Carrousels éditoriaux façon magazine : Cauri Hebdo (chaque dimanche) et présentation de Cauri Charts.

Diapositives à fond plein, titre géant en Anton, étiquette de rubrique, texte court ou liste numérotée ; la couverture
du Hebdo est une « une de magazine » avec la photo du n°1. Formats 4:5 (Instagram, Facebook) et 9:16 (TikTok), en 4K.
Le post est enregistré comme les autres (social_posts) : il apparaît dans Admin > Posts et part par Buffer.
"""
import json
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from core import db, storage
from core.helpers import country_name
from core.services.social import carousel as C
from core.services.social import image as PI

INK, WHITE, VIOLET, GOLD, CREAM = (14, 12, 20), (255, 255, 255), (139, 82, 255), (255, 190, 40), (248, 244, 233)
FONTS = {"display": str(PI.FONT_DIR / "Anton-Regular.ttf"), "bold": str(PI.FONT_DIR / "Poppins-Bold.ttf"),
         "sans": str(PI.FONT_DIR / "Poppins-Regular.ttf")}


def _wrap(fr: PI.Frame, text: str, path: str, px: int, w: float) -> list:
    return fr.wrap(text, path, px, w, 8)


def slide(fr: PI.Frame, s: dict, last: bool) -> Image.Image:
    """s : bg, fg, acc, tag, big, et body (texte) ou rows [(numéro, ligne principale, ligne secondaire)], cta."""
    W, H = fr.bw, fr.bh
    img = Image.new("RGB", (fr.w, fr.h), s["bg"])
    d = ImageDraw.Draw(img, "RGBA")
    pad = max(70, fr.side)
    w = W - 2 * pad
    fg, acc = (*s["fg"], 255), (*s["acc"], 255)
    fr.text(d, 34, pad, fr.top + 90, fg, FONTS["display"], "CAURI CHARTS")
    fr.rect(d, pad, fr.top + 112, W - pad, fr.top + 116, fg)
    tw = fr.width(s["tag"], FONTS["bold"], 26) + 32
    ty = fr.top + 190
    fr.rect(d, pad, ty, pad + tw, ty + 52, acc)
    fr.text(d, 26, pad + 16, ty + 37, INK if s["acc"] in (GOLD, CREAM) else WHITE, FONTS["bold"], s["tag"])
    size = 170 if s.get("rows") is None else (110 if len(s["rows"]) > 4 else 130)
    while size > 64:
        lines = _wrap(fr, s["big"], FONTS["display"], size, w)
        if len(lines) <= (4 if s.get("rows") is None else (1 if len(s["rows"]) > 4 else 2)) and all(fr.width(l, FONTS["display"], size) <= w for l in lines):
            break
        size -= 4
    y = ty + (100 if s.get("rows") is None else 80) + size
    for line in lines:
        fr.text(d, size, pad - 4, y, fg, FONTS["display"], line)
        y += size * 1.13
    y += 30
    foot = H - fr.bottom - 70
    if s.get("rows"):
        room = foot - 40 - y
        row_h = min(150, room / max(1, len(s["rows"])))
        num_px, main_px, sub_px = min(84, row_h * 0.62), min(40, row_h * 0.32), min(26, row_h * 0.2)
        for num, main, sub in s["rows"]:
            fr.rect(d, pad, y, W - pad, y + 2, (*s["fg"], 70))
            nw = fr.width("10", FONTS["display"], num_px) + 24
            fr.text(d, num_px, pad, y + row_h * 0.72, acc, FONTS["display"], str(num))
            fr.text(d, main_px, pad + nw, y + row_h * 0.45, fg, FONTS["bold"], fr.fit(main, FONTS["bold"], main_px, w - nw))
            if sub:
                fr.text(d, sub_px, pad + nw, y + row_h * 0.45 + sub_px * 1.5, (*s["fg"], 190), FONTS["sans"], fr.fit(sub, FONTS["sans"], sub_px, w - nw))
            y += row_h
    elif s.get("body"):
        px = 36 if H > 1500 else 32
        for line in _wrap(fr, s["body"], FONTS["sans"], px, w):
            fr.text(d, px, pad, y, fg, FONTS["sans"], line)
            y += px * 1.45
    if s.get("cta"):
        cw = fr.width(s["cta"], FONTS["bold"], 34) + 60
        fr.rect(d, pad, foot - 70, pad + cw, foot, acc)
        fr.text(d, 34, pad + 30, foot - 22, INK if s["acc"] in (GOLD, CREAM) else WHITE, FONTS["bold"], s["cta"])
    else:
        fr.text(d, 24, pad, foot, fg, FONTS["bold"], "cauricharts.com")
        if not last:
            arrow = "GLISSEZ »"
            fr.text(d, 24, W - pad - fr.width(arrow, FONTS["bold"], 24), foot, fg, FONTS["bold"], arrow)
    return img


def render(name: str, slides: list, cover: dict | None = None) -> list:
    """Diapositives 4:5 et 9:16 ; cover (kicker, headline, subtitle, photo) : une de magazine en première position."""
    PI.DIR.mkdir(parents=True, exist_ok=True)
    out = []
    total = len(slides) + (1 if cover else 0)
    for fmt, (size, safe) in C.FORMATS.items():
        fr = PI.Frame(*size, safe)
        imgs = []
        if cover:
            imgs.append(C._best_cover(fr, PI.style(name), cover, cover.get("photo"), total))
        imgs += [slide(fr, s, i == len(slides) - 1) for i, s in enumerate(slides)]
        for i, im in enumerate(imgs):
            suffix = "" if fmt == "feed" else "-916"
            saved = PI.save_jpeg(im, PI.DIR / f"{name}-{i + 1}{suffix}.jpg")
            if fmt == "feed":
                out.append({"file": Path(saved).name, "label": cover["headline"] if (cover and i == 0) else (slides[i - (1 if cover else 0)]["big"])})
            else:
                out[i]["tiktok"] = Path(saved).name
    return out


def save_post(theme: str, day: str, title: str, caption: str, hashtags: str, slides: list, facts: dict) -> dict:
    storage.publish_media_files("social", [s["file"] for s in slides] + [s["tiktok"] for s in slides])
    db.run("DELETE FROM social_posts WHERE slot_date = ? AND theme = ? AND status = 'draft'", [day, theme])
    pid = db.insert("social_posts", {"slot_date": day, "theme": theme, "title": title[:160], "caption": caption, "hashtags": hashtags[:300],
                                     "facts": json.dumps(facts, ensure_ascii=False, default=str), "image_square": slides[0]["file"],
                                     "image_story": slides[0]["tiktok"], "carousel": json.dumps(slides, ensure_ascii=False),
                                     "video": None, "status": "approved"})
    return db.one("SELECT * FROM social_posts WHERE id = ?", [pid])


# ---------------------------------------------------------------- Cauri Hebdo

def hebdo_post(f: dict, day: date) -> dict | None:
    """Le magazine de la semaine en carrousel, à partir des mêmes faits que l'article (magazine.facts)."""
    from core.services.magazine import de
    from core.services.social.generator import own_image
    # Seulement les artistes au pays confirmé, avec leur vrai rang du classement (les numéros restent ceux du site)
    top = [r for r in f["top"] if r.get("status") == "active"]
    if len(top) < 10:
        return None
    year, week, _ = day.isocalendar()
    one = top[0]
    who = lambda r: f"{r['artist_name']}" + (f" · {country_name(r['artist_country'])}" if r.get("artist_country") else "")  # noqa: E731
    slides = [
        {"bg": INK, "fg": WHITE, "acc": GOLD, "tag": "LE PODIUM", "big": "EN TÊTE DU TOP",
         "rows": [(r["rank"], r["title"], who(r)) for r in top[:3]]},
        {"bg": VIOLET, "fg": WHITE, "acc": GOLD, "tag": "LE TOP 10", "big": "LA SUITE DU TOP",
         "rows": [(r["rank"], r["title"], who(r)) for r in top[3:10]]},
    ]
    if f.get("countries"):
        parts = " · ".join(f"{country_name(c)} {n}" for c, n in f["countries"].most_common(6))
        slides.append({"bg": CREAM, "fg": INK, "acc": VIOLET, "tag": "LA CARTE DU TOP 20", "big": f"{len(f['countries'])} PAYS DANS LE TOP 20",
                       "body": parts + ". Au plus 5 titres d'un même pays : toute la région a sa place."})
    if f.get("buzz"):
        slides.append({"bg": GOLD, "fg": INK, "acc": INK, "tag": "ÇA MONTE", "big": "À SURVEILLER",
                       "rows": [(i + 1, r["title"], who(r)) for i, r in enumerate([b for b in f["buzz"] if b.get("status") == "active"][:3])]})
    if f.get("leaders"):
        slides.append({"bg": INK, "fg": WHITE, "acc": VIOLET, "tag": "PAYS PAR PAYS", "big": "LES N°1",
                       "rows": [(r["country"], r["title"], f"{r['artist_name']} · {country_name(r['country'])}") for r in f["leaders"][:6] if r.get("status") == "active"]})
    slides.append({"bg": VIOLET, "fg": WHITE, "acc": GOLD, "tag": "CAURI HEBDO", "big": "L'ARTICLE COMPLET EST EN LIGNE",
                   "body": "Le classement complet, la méthode et la note de fiabilité de chaque pays sur cauricharts.com. Rendez-vous dimanche prochain.",
                   "cta": "S'ABONNER"})
    name = f"{day.isoformat()}-hebdo-{year}-s{week:02d}"
    cover = {"kicker": f"Cauri Hebdo · semaine {week}", "headline": one["artist_name"],
             "subtitle": f"« {one['title']} » · n°{one['rank']} Afrique de l'Ouest", "photo": one.get("artist_image") or own_image(one) or one.get("cover_url")}
    files = render(name, slides, cover)
    caption = (f"Cauri Hebdo, semaine {week}. « {one['title']} » {de(one['artist_name'])} prend la tête du Top 20 Afrique de l'Ouest.\n\n"
               "Le podium, le Top 10, la carte des pays, ceux qui montent et les n°1 de chaque pays : tout est dans le carrousel.\n\n"
               "Article complet et classement en direct : lien en bio.")
    tags = "#CauriHebdo #CauriCharts #Top20 #AfriqueDeLOuest #Afrobeats #" + "".join(ch for ch in one["artist_name"] if ch.isalnum())
    return save_post("hebdo", day.isoformat(), f"Cauri Hebdo, semaine {week}", caption, tags, files, {"kind": "hebdo", "week": week})


# ---------------------------------------------------------------- présentation

PRESENTATION = [
    {"bg": INK, "fg": WHITE, "acc": GOLD, "tag": "QUI SOMMES-NOUS", "big": "LA MUSIQUE OUEST-AFRICAINE, MESURÉE.",
     "body": "Le classement musical de 16 pays, bâti sur des données réelles. Chaque semaine."},
    {"bg": VIOLET, "fg": WHITE, "acc": GOLD, "tag": "01 · LA CARTE", "big": "16 PAYS",
     "body": "Togo · Bénin · Ghana · Côte d'Ivoire · Sénégal · Nigeria · Burkina Faso · Mali · Niger · Guinée · "
             "Guinée-Bissau · Cap-Vert · Gambie · Liberia · Sierra Leone · Mauritanie"},
    {"bg": CREAM, "fg": INK, "acc": VIOLET, "tag": "02 · LES SOURCES", "big": "DES DONNÉES RÉELLES",
     "body": "Deezer, Apple Music, Shazam et YouTube, relevés chaque nuit. Aucun chiffre inventé, chaque chiffre a sa source et sa date."},
    {"bg": INK, "fg": WHITE, "acc": VIOLET, "tag": "03 · LE CLASSEMENT PHARE", "big": "TOP 20 AFRIQUE DE L'OUEST",
     "body": "Chaque pays pèse autant. Au plus 5 titres d'un même pays : les grandes scènes restent visibles et laissent de la place aux autres."},
    {"bg": GOLD, "fg": INK, "acc": INK, "tag": "04 · TRANSPARENCE", "big": "UNE NOTE DE FIABILITÉ",
     "body": "Chaque classement affiche sa fiabilité sur 100 : nombre de plateformes, jours relevés, titres confirmés par deux sources."},
    {"bg": INK, "fg": WHITE, "acc": GOLD, "tag": "05 · NOTRE RÈGLE", "big": "PERSONNE N'ACHÈTE UNE PLACE",
     "body": "Ni artiste, ni label, ni sponsor. La méthode est publique et chaque erreur est corrigée publiquement."},
    {"bg": VIOLET, "fg": WHITE, "acc": GOLD, "tag": "06 · ARTISTES", "big": "VOTRE FICHE VOUS ATTEND",
     "body": "Revendiquez votre page, déclarez vos chiffres, partagez votre rang. Gratuit, sur cauricharts.com."},
    {"bg": INK, "fg": WHITE, "acc": GOLD, "tag": "RENDEZ-VOUS", "big": "LE TOP CHAQUE DIMANCHE",
     "body": "Abonnez-vous et activez les notifications. Classements complets sur cauricharts.com", "cta": "S'ABONNER"},
]


def presentation_post(day: date) -> dict:
    files = render(f"{day.isoformat()}-presentation", PRESENTATION)
    caption = ("La musique ouest-africaine, mesurée.\n\nCauri Charts, c'est le classement musical de 16 pays d'Afrique de l'Ouest, bâti sur des "
               "données réelles : Deezer, Apple Music, Shazam et YouTube, relevés chaque nuit.\n\nNotre règle : personne n'achète une place. "
               "Ni artiste, ni label, ni sponsor. La méthode est publique et chaque classement affiche sa note de fiabilité.\n\n"
               "Artistes : votre fiche existe peut-être déjà. Revendiquez-la, déclarez vos chiffres, partagez votre rang.\n\n"
               "Le Top 20 Afrique de l'Ouest tombe chaque dimanche. Abonnez-vous et activez les notifications.\n\nLien en bio : cauricharts.com")
    tags = "#CauriCharts #Afrobeats #MusiqueAfricaine #Togo #Benin #Ghana #CoteDIvoire #Senegal #Nigeria #AfriqueDeLOuest"
    return save_post("presentation", day.isoformat(), "La musique ouest-africaine, mesurée", caption, tags, files, {"kind": "presentation"})


def next_sunday(day: date) -> date:
    return day + timedelta(days=(6 - day.weekday()) % 7)
