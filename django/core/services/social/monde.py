"""Cauri Monde : l'actualité musicale mondiale (artistes reconnus, grands événements, Grammy…), sans changer la devise
de Cauri Charts (« la référence de la musique ouest-africaine »).

Trois rubriques :
  - monde   : l'actu du monde de la musique (annonces, événements, cérémonies, industrie) → édition de 8 h ;
  - records : projets personnels des artistes, records, chiffres historiques            → édition de 20 h ;
  - sorties : albums, singles et projets qui sortent                                    → édition de 20 h ;
et le FLASH : une info choc donnée par au moins deux médias fiables part tout de suite, partout.

Données réelles uniquement : les flux RSS publics des grands médias musicaux (titres et résumés, toujours cités) ; le texte
français est réécrit avec nos mots par l'IA gratuite (core.services.ai), à partir de ces seules données publiques ; la
photo vient de Deezer (photo d'artiste), jamais d'une photo de presse.
"""
import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from core import db
from core.services.platforms import log_write
from core.services.news import http_get, parse_feed

# Grands médias musicaux (flux RSS publics, testés le 11/10/2026). poids = fiabilité pour confirmer un flash.
FEEDS = [
    {"name": "Billboard", "url": "https://www.billboard.com/c/music/music-news/feed/", "poids": 3},
    {"name": "Rolling Stone", "url": "https://www.rollingstone.com/music/music-news/feed/", "poids": 3},
    {"name": "Variety", "url": "https://variety.com/v/music/feed/", "poids": 3},
    {"name": "Pitchfork", "url": "https://pitchfork.com/feed/feed-news/rss", "poids": 3},
    {"name": "NME", "url": "https://www.nme.com/news/music/feed", "poids": 2},
    {"name": "Consequence", "url": "https://consequence.net/category/music/feed/", "poids": 2},
    {"name": "HipHopDX", "url": "https://hiphopdx.com/rss/news.xml", "poids": 2},
    {"name": "Music Business Worldwide", "url": "https://www.musicbusinessworldwide.com/feed/", "poids": 2},
    {"name": "RFI Musique", "url": "https://www.rfi.fr/fr/musique/rss", "poids": 3},
]
# Les plus grands visages de la musique, du moment et de tous les temps (veille Google Actualités en français)
STARS = ["Beyoncé", "Taylor Swift", "Rihanna", "Drake", "Bad Bunny", "The Weeknd", "Ed Sheeran", "Billie Eilish", "Dua Lipa",
         "Kendrick Lamar", "Travis Scott", "Ariana Grande", "Justin Bieber", "Bruno Mars", "Lady Gaga", "Adele", "Eminem",
         "Kanye West", "Jay-Z", "Nicki Minaj", "Cardi B", "Sabrina Carpenter", "Doja Cat", "Post Malone", "Shakira",
         "Karol G", "SZA", "Olivia Rodrigo", "Coldplay", "BTS", "Blackpink", "Rosé", "Lisa", "Miley Cyrus", "Harry Styles",
         "Michael Jackson", "Madonna", "Céline Dion", "Stromae", "Aya Nakamura", "Ninho", "Jul", "Gims",
         "Burna Boy", "Wizkid", "Davido", "Tems", "Rema", "Asake", "Ayra Starr", "Tyla", "Fally Ipupa", "Black Sherif"]
GOOGLE_NEWS = "https://news.google.com/rss/search?hl=fr&gl=FR&ceid=FR:fr&q="


def _flux_stars() -> list:
    from urllib.parse import quote
    lots = [STARS[i:i + 9] for i in range(0, len(STARS), 9)]
    return [{"name": "Google Actualités", "url": GOOGLE_NEWS + quote("(" + " OR ".join(f'"{n}"' for n in lot) + ") musique when:2d"), "poids": 1, "stars": True}
            for lot in lots]


RUBRIQUES = {"monde": "L'ACTU MONDE", "records": "PROJETS & RECORDS", "sorties": "ÇA SORT"}
CATEGORIE_SITE = {"monde": "evenement", "records": "industrie", "sorties": "sortie"}
SEUIL_FLASH = 80          # note « choc » minimale (0-100) donnée par la rédaction
SOURCES_FLASH = 2         # médias différents qui donnent la même info

VIDES = set("""the a an and or of to in on for with at by from as is are was were be been its it this that these those
new news his her their they he she after over into about up out more than who will has have had not but just
le la les un une des du de et ou en au aux sur pour par dans avec son sa ses leur leurs qui que est sont été
album single song songs track video music tour new year years first one two says said announces announced""".split())


def coupe(s: str, n: int) -> str:
    """Coupe proprement au dernier mot entier (jamais « sexuell »)."""
    s = str(s or "").strip()
    # caractères absents des polices (tiret insécable, espaces fines…) → équivalents simples
    for x, y in (("‑", "-"), ("‐", "-"), ("‒", "-"), (" ", " "), (" ", " "), (" ", " "), ("​", "")):
        s = s.replace(x, y)
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _sans_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _mots(titre: str) -> set:
    t = _sans_accents(titre).lower()
    return {w for w in re.findall(r"[a-z0-9']{3,}", t) if w not in VIDES}


def _noms(titre: str) -> set:
    """Mots en capitales du titre d'origine (noms d'artistes, d'événements) : les meilleurs indices pour regrouper."""
    return {_sans_accents(w).lower() for w in re.findall(r"\b[A-Z][\w'.&-]{2,}", titre)} - VIDES


# ---------------------------------------------------------------- collecte et regroupement

def collecte(heures: int = 36) -> list:
    """Articles des dernières `heures`, tous médias confondus (en parallèle, un flux en panne ne bloque rien)."""
    limite = datetime.now(timezone.utc) - timedelta(hours=heures)

    def un(feed):
        try:
            xml = http_get(feed["url"])
            return [{**it, "source": feed["name"], "poids": feed["poids"]} for it in parse_feed(xml or "")]
        except Exception as exc:  # noqa: BLE001
            log_write("monde", "warning", f"{feed['name']} : {exc}")
            return []
    with ThreadPoolExecutor(8) as ex:
        items = [it for lot in ex.map(un, FEEDS + _flux_stars()) for it in lot]
    # Google Actualités : le vrai média est en fin de titre (« … - Le Parisien »)
    for it in items:
        if it["source"] == "Google Actualités" and " - " in it["title"]:
            it["title"], it["source"] = it["title"].rsplit(" - ", 1)
            it["poids"] = 2
    out = []
    for it in items:
        d = it.get("published_at")
        if isinstance(d, str):
            try:
                d = datetime.fromisoformat(d.replace("Z", "+00:00"))
            except ValueError:
                d = None
        if d is not None and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        if d is None or d >= limite:
            out.append({**it, "date": d or datetime.now(timezone.utc)})
    return out


def regroupe(items: list) -> list:
    """Même info dans plusieurs médias → une seule histoire, avec la liste de ses sources."""
    histoires = []
    for it in sorted(items, key=lambda x: x["date"], reverse=True):
        m, n = _mots(it["title"]), _noms(it["title"])
        for h in histoires:
            commun_noms = len(n & h["noms"])
            jac = len(m & h["mots"]) / max(1, len(m | h["mots"]))
            if (commun_noms >= 2 and jac >= .18) or jac >= .4 or (commun_noms >= 1 and jac >= .3):
                h["items"].append(it); h["mots"] |= m; h["noms"] |= n
                break
        else:
            histoires.append({"items": [it], "mots": set(m), "noms": set(n)})
    for h in histoires:
        h["sources"] = sorted({i["source"] for i in h["items"]})
        h["poids"] = sum({i["source"]: i["poids"] for i in h["items"]}.values())
        h["date"] = max(i["date"] for i in h["items"])
        h["cle"] = hashlib.sha1(" ".join(sorted(h["noms"] or h["mots"])[:6]).encode()).hexdigest()[:12]
    return sorted(histoires, key=lambda h: (h["poids"], h["date"]), reverse=True)


# ---------------------------------------------------------------- rédaction (français, nos mots)

SYSTEME = ("Tu es le rédacteur en chef de Cauri Charts, média musical francophone (devise : « la référence de la musique "
           "ouest-africaine »), qui couvre aussi l'actualité mondiale des artistes reconnus. Tu écris en français, avec tes "
           "propres mots, sans rien inventer : uniquement les faits présents dans les titres et résumés fournis. Pas de rumeur "
           "présentée comme un fait. Réponds UNIQUEMENT en JSON valide.")


def redige(histoires: list) -> list:
    """Par paquets de 10 (l'IA gratuite décroche sur de trop longues listes)."""
    out = []
    for i in range(0, len(histoires), 10):
        out += _redige(histoires[i:i + 10])
    return out


def _redige(histoires: list) -> list:
    """Pour chaque histoire : rubrique, artiste, une (≤ 28 car.), titre qui dit exactement de quoi on parle, accroche,
    résumé, note « choc » (0-100), sensible (décès, santé, justice). Les histoires hors musique sont écartées."""
    if not histoires:
        return []
    from core.services import ai
    lots = []
    for i, h in enumerate(histoires):
        lots.append({"i": i, "sources": h["sources"],
                     "articles": [{"titre": x["title"][:200], "resume": (x.get("summary") or "")[:400]} for x in h["items"][:3]]})
    consigne = (
        "Voici des actualités musicales du monde (plusieurs articles = même info vue par plusieurs médias).\n"
        "Pour CHAQUE entrée, rends un objet JSON :\n"
        '{"i": n, "musique": true|false, "rubrique": "monde"|"records"|"sorties", "artiste": "nom principal ou événement",\n'
        ' "une": "accroche de couverture, 28 caractères max, percutante, en MAJUSCULES, dit le sujet (ex. RIHANNA : 9E ALBUM)",\n'
        ' "titre": "phrase de 70 caractères max qui dit EXACTEMENT ce qui se passe, avec le chiffre clé s\'il y en a un",\n'
        ' "accroche": "une phrase qui donne envie, 110 caractères max",\n'
        ' "resume": "2 à 3 phrases factuelles, 330 caractères max",\n'
        ' "choc": 0-100 (100 = info mondiale majeure : sortie surprise d\'une star, record historique, annonce Grammy, décès d\'une légende),\n'
        ' "sensible": true si décès, santé, justice, violence,\n'
        ' "ancien": true si le fait principal (cérémonie, record, sortie) date de plus de 30 jours, même si l\'article est récent}\n'
        "rubrique : sorties = un album/single/projet qui sort ou est annoncé avec date ; records = record, chiffre historique, "
        "projet personnel d'un artiste (marque, film, livre, tournée record) ; monde = le reste (cérémonies, événements, industrie).\n"
        "Français impeccable, aucun anglicisme (concerts et pas shows), noms propres exacts, phrases complètes.\n"
        "Rends une liste JSON, rien d'autre.\n\n" + json.dumps(lots, ensure_ascii=False))
    r = ai.make().ask(SYSTEME, consigne, max_tokens=6000)
    texte = r["text"].strip()
    texte = texte[texte.find("["): texte.rfind("]") + 1]
    try:
        fiches = json.loads(texte)
    except ValueError:
        log_write("monde", "error", "rédaction illisible : " + r["text"][:300])
        return []
    out = []
    for f in fiches:
        try:
            h = histoires[int(f["i"])]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if not f.get("musique", True) or f.get("ancien"):
            continue   # hors musique, ou vieille nouvelle remise en avant : pas de l'actualité
        out.append({**h, "rubrique": f.get("rubrique") if f.get("rubrique") in RUBRIQUES else "monde",
                    "artiste": coupe(f.get("artiste"), 60), "une": coupe(f.get("une"), 60).rstrip("…"),
                    "titre": coupe(f.get("titre") or h["items"][0]["title"], 140),
                    "accroche": coupe(f.get("accroche"), 130), "resume": coupe(f.get("resume"), 420),
                    "choc": int(f.get("choc") or 0), "sensible": bool(f.get("sensible"))})
    return out


# ---------------------------------------------------------------- photo (Deezer, photo d'artiste officielle)

def photo(artiste: str):
    if not artiste:
        return None
    try:
        from urllib.parse import quote
        r = json.loads(http_get("https://api.deezer.com/search/artist?limit=1&q=" + quote(artiste)) or "{}")
        a = (r.get("data") or [None])[0]
        if a and _sans_accents(a["name"]).lower() == _sans_accents(artiste).lower() and "/artist//" not in (a.get("picture_xl") or "/artist//"):
            return a["picture_xl"]
    except Exception as exc:  # noqa: BLE001
        log_write("monde", "warning", f"photo {artiste} : {exc}")
    return None


_FANS: dict = {}


def fans(artiste: str) -> int:
    """Nombre de fans Deezer de l'artiste (donnée réelle) : mesure de notoriété mondiale."""
    if not artiste:
        return 0
    if artiste not in _FANS:
        _FANS[artiste] = 0
        try:
            from urllib.parse import quote
            a = (json.loads(http_get("https://api.deezer.com/search/artist?limit=1&q=" + quote(artiste)) or "{}").get("data") or [None])[0]
            if a and _sans_accents(a["name"]).lower() == _sans_accents(artiste).lower():
                _FANS[artiste] = int(a.get("nb_fan") or 0)
        except Exception:  # noqa: BLE001
            pass
    return _FANS[artiste]


def score(f: dict) -> float:
    """Note d'une info : son poids « choc », le nombre de médias, et surtout la notoriété de l'artiste (les plus grands visages devant)."""
    import math
    star = any(_sans_accents(n).lower() == _sans_accents(f.get("artiste", "")).lower() for n in STARS)
    return f["choc"] + 12 * len(f["sources"]) + 9 * math.log10(1 + fans(f.get("artiste", ""))) + (25 if star else 0)


def deja_publie(cle: str) -> bool:
    return bool(db.value("SELECT 1 FROM news WHERE external_guid = ?", [f"monde-{cle}"]))


# ---------------------------------------------------------------- couverture choc (actu) : photo plein cadre, titre géant

ROUGE = (229, 33, 59)


SCENES = sorted((__import__("pathlib").Path(__file__).resolve().parents[4] / "resources" / "monde").glob("scene-*.jpg"))


OBJETS = (__import__("pathlib").Path(__file__).resolve().parents[4] / "resources" / "monde" / "objets")
THEMES_OBJETS = [   # sujet → photo d'objet (domaine public, resources/monde/objets/SOURCES.txt)
    ("trophee", r"grammy|award|prix|r[ée]compens|nomin|troph|c[ée]r[ée]monie|sacr|bet |mtv"),
    ("disque-or", r"record|certifi|platine|disque d.or|million|stream|chiffre|historique"),
    ("vinyle", r"album|single|sortie|sort |ep|projet|vinyle|mixtape"),
    ("micro", r"interpr[èe]t|chant|session|studio|micro|live|plateau|direct"),
    ("journal", r"annonce|industrie|label|contrat|proc[èe]s|justice|business|accord|rachat|plainte|accus"),
]


def objet(f: dict, graine: str):
    """Photo d'objet qui colle au sujet (trophée pour un prix, vinyle pour une sortie…), sinon None."""
    texte = _sans_accents(" ".join([f.get("titre", ""), f.get("resume", ""), f.get("rubrique", "")])).lower()
    for theme, motif in THEMES_OBJETS:
        if re.search(_sans_accents(motif), texte):
            l = sorted(OBJETS.glob(f"{theme}-*.jpg"))
            if l:
                return l[int(hashlib.sha1(graine.encode()).hexdigest(), 16) % len(l)]
    return None


def _scene(graine: str):
    """Vraie scène de concert (images libres Mixkit) quand l'info n'a pas de photo d'artiste."""
    return SCENES[int(hashlib.sha1(graine.encode()).hexdigest(), 16) % len(SCENES)] if SCENES else None


def couverture_choc(f: dict, kicker: str, est_flash: bool, fmt: str = "feed", diapo: dict | None = None):
    """Première image qui dit EXACTEMENT de quoi on parle : photo de l'artiste plein cadre, bandeau FLASH / CAURI MONDE,
    l'accroche en très grand, la phrase-titre, les médias qui donnent l'info. Rendu ×2 (4K) comme le reste."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFilter
    from core.services.social import image as PI
    from core.services.social.editorial import GOLD, INK, VIOLET
    k = 2
    W, H = (1080 * k, 1350 * k) if fmt == "feed" else (1080 * k, 1920 * k)
    haut, bas, cote = (70 * k, 90 * k, 80 * k) if fmt == "feed" else (250 * k, 440 * k, 90 * k)
    img = Image.new("RGB", (W, H), INK)
    # la photo d'un artiste seulement si son nom est bien dans le titre de l'info (jamais la photo d'un autre)
    nom_ok = f.get("artiste") and _sans_accents(f["artiste"]).lower() in _sans_accents((diapo or {}).get("titre") or f.get("titre", "") or f.get("une", "")).lower()
    url = None if ((diapo or {}).get("fond") or not nom_ok) else photo(f["artiste"])
    src = (diapo or {}).get("fond")
    if not src and not url:   # pas de photo sûre : l'objet du sujet, sinon (plus bas) une scène de concert
        src = objet(f, f.get("cle", "") + (diapo or {}).get("graine", ""))
    if not src:
        try:
            src = BytesIO(http_get(url, binary=True)) if url else _scene(f.get("cle", "") + (diapo or {}).get("graine", ""))
        except Exception:  # noqa: BLE001
            src = _scene(f.get("cle", ""))
    if src:
        try:
            ph = Image.open(src).convert("RGB")
            r = max(W / ph.width, H * .78 / ph.height)
            ph = ph.resize((int(ph.width * r), int(ph.height * r)), Image.LANCZOS)
            img.paste(ph, ((W - ph.width) // 2, 0))
        except Exception as exc:  # noqa: BLE001
            log_write("monde", "warning", f"photo couverture : {exc}")
    else:
        fond = Image.new("RGB", (W, H), VIOLET)
        img = Image.blend(img, fond, .55)
    # zone du texte : floutée (le texte d'une pochette ne se mélange jamais au nôtre), puis assombrie
    def rampe(debut, fin, fort=1.0):
        m = Image.new("L", (1, 256))
        for y in range(256):
            m.putpixel((0, y), int(255 * fort * max(0, min(1, (y / 255 - debut) / (fin - debut)))))
        return m.resize((W, H))
    img = Image.composite(img.filter(ImageFilter.GaussianBlur(22 * k)), img, rampe(.50, .64))
    # fond clair (pochette blanche…) : on assombrit d'autant plus que la zone du texte est lumineuse
    from PIL import ImageStat
    lum = ImageStat.Stat(img.crop((0, int(H * .55), W, H)).convert("L")).mean[0] / 255
    img = Image.blend(img, Image.new("RGB", (W, H), INK), min(.35, max(.05, (lum - .3) * .8)))
    img = Image.composite(Image.new("RGB", (W, H), INK), img, rampe(.46, .74, .95))
    d = ImageDraw.Draw(img)
    fd, fb, fs = PI.FONT_DIR / "Anton-Regular.ttf", PI.FONT_DIR / "Poppins-Bold.ttf", PI.FONT_DIR / "Poppins-Regular.ttf"
    # bandeau
    etiquette = (diapo or {}).get("etiquette") or ("FLASH" if est_flash else "CAURI MONDE")
    fe = PI.font(str(fd), 64 * k)
    x0, y0 = cote, haut
    wl = d.textlength(etiquette, font=fe)
    d.rectangle([x0, y0, x0 + wl + 44 * k, y0 + 92 * k], fill=(diapo or {}).get("couleur") or (ROUGE if est_flash else VIOLET))
    d.text((x0 + 22 * k, y0 + 46 * k), etiquette, font=fe, fill="white", anchor="lm")
    kicker = re.sub(r"^(cauri monde|flash)\s*·?\s*", "", kicker, flags=re.I)
    fk = PI.font(str(fb), 26 * k)
    d.rectangle([x0 + wl + 44 * k, y0, x0 + wl + 44 * k + d.textlength(kicker.upper(), font=fk) + 40 * k, y0 + 92 * k], fill=(255, 255, 255))
    d.text((x0 + wl + 64 * k, y0 + 46 * k), kicker.upper(), font=fk, fill=INK, anchor="lm")
    fm = PI.font(str(fd), 34 * k)
    fin_bandeau = x0 + wl + 84 * k + d.textlength(kicker.upper(), font=fk)
    wm = d.textlength("CAURI CHARTS", font=fm)
    if W - cote - wm - 40 * k > fin_bandeau + 30 * k:   # pastille sombre : lisible sur toutes les photos
        d.rounded_rectangle([W - cote - wm - 40 * k, y0 + 14 * k, W - cote, y0 + 78 * k], radius=32 * k, fill=INK)
        d.text((W - cote - 20 * k, y0 + 46 * k), "CAURI CHARTS", font=fm, fill="white", anchor="rm")
    # titre géant (2 à 3 lignes), dernière ligne en or
    une = ((diapo or {}).get("titre") or f["une"] or f["artiste"]).upper()
    largeur = W - 2 * cote
    # la phrase d'abord (taille fixe), puis le titre le plus grand possible SANS dépasser le tiers bas : le visage reste visible
    ft2 = PI.font(str(fb if not diapo else fs), (38 if not diapo else 30) * k)
    interl2 = (52 if not diapo else 44) * k
    phrase, l2, cur = ((diapo or {}).get("texte") or f["titre"]), [], ""
    for m in phrase.split():
        essai = (cur + " " + m).strip()
        if d.textlength(essai, font=ft2) <= largeur:
            cur = essai
        else:
            l2.append(cur); cur = m
    l2 = (l2 + [cur])[:3 if not diapo else 4]
    budget = H * (.42 if fmt == "feed" else .55)          # hauteur maximale du bloc de texte (TikTok : marge basse plus grande)
    fixe = bas + 34 * k + 40 * k + len(l2) * interl2 + 34 * k
    max_lignes = 4 if diapo else 3
    for px in range(160 if not diapo else 104, 50, -4):
        ft = PI.font(str(fd), px * k)
        mots, lignes, cur = une.split(), [], ""
        for m in mots:
            essai = (cur + " " + m).strip()
            if d.textlength(essai, font=ft) <= largeur:
                cur = essai
            else:
                lignes.append(cur); cur = m
        lignes.append(cur)
        if (len(lignes) <= max_lignes and all(d.textlength(l, font=ft) <= largeur for l in lignes)
                and fixe + len(lignes) * px * k * .96 <= budget):
            break
    pas = int(px * k * .96)          # interligne (lignes posées sur leur ligne de base)
    fsrc = PI.font(str(fb), 24 * k)
    y_src = H - bas - 34 * k
    y_phr = y_src - 40 * k - len(l2) * interl2
    base = y_phr - 34 * k            # ligne de base de la dernière ligne du titre, au-dessus de la phrase
    ops = [((cote, base - (len(lignes) - 1 - i) * pas), l, ft, "ls", GOLD if (i == len(lignes) - 1 and len(lignes) > 1) else (255, 255, 255))
           for i, l in enumerate(lignes)]
    ops += [((cote, y_phr + i * interl2), l, ft2, "la", (235, 235, 245)) for i, l in enumerate(l2)]
    ombre = Image.new("L", (W, H), 0)
    do = ImageDraw.Draw(ombre)
    for xy, l, fnt, anc, _ in ops:
        do.text((xy[0], xy[1] + 6 * k), l, font=fnt, anchor=anc, fill=200)
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, ombre.filter(ImageFilter.GaussianBlur(10 * k)))
    d = ImageDraw.Draw(img)
    for xy, l, fnt, anc, col in ops:
        d.text(xy, l, font=fnt, anchor=anc, fill=col)
    src = ("SOURCES · " + " · ".join(s.upper() for s in f["sources"][:4])) if f.get("sources") else "CAURICHARTS.COM"
    wsrc = d.textlength(src, font=fsrc)
    d.rounded_rectangle([cote, y_src - 6 * k, cote + wsrc + 36 * k, y_src + 46 * k], radius=26 * k, fill=(255, 255, 255))
    d.text((cote + 18 * k, y_src + 20 * k), src, font=fsrc, fill=INK, anchor="lm")
    return img


# ---------------------------------------------------------------- posts

def _slides(fiches: list, E, final: str) -> list:
    couleurs = [(E.INK, E.WHITE, E.GOLD), (E.VIOLET, E.WHITE, E.GOLD), (E.CREAM, E.INK, E.VIOLET), (E.GOLD, E.INK, E.INK)]
    slides = []
    for k, f in enumerate(fiches):
        bg, fg, acc = couleurs[k % len(couleurs)]
        slides.append({"bg": bg, "fg": fg, "acc": acc, "tag": f"{RUBRIQUES[f['rubrique']]} · {', '.join(f['sources'][:3]).upper()}",
                       "big": f["titre"].upper(), "body": f["resume"]})
    slides.append({"bg": E.INK, "fg": E.WHITE, "acc": E.GOLD, "tag": "CAURI CHARTS", "big": "LA RÉFÉRENCE DE LA MUSIQUE OUEST-AFRICAINE",
                   "body": final, "cta": "S'ABONNER"})
    return slides


def _legende(fiches: list, entete: str) -> str:
    lignes = [entete]
    for f in fiches:
        lignes.append(f"▪️ {f['titre']}\n{f['resume']}\n(Sources : {', '.join(f['sources'])})")
    lignes.append("Cauri Charts, la référence de la musique ouest-africaine. Le classement en direct : lien en bio.")
    return "\n\n".join(lignes)


PAR_EDITION = 4      # infos (donc posts) par édition
ECART_MIN = 45       # minutes entre deux posts d'une même édition


def construit(fiches: list, jour: date, theme: str, kicker: str, entete: str, final: str, rendu_seul: bool = False, due=None) -> dict:
    """Carrousel (couverture magazine qui dit le sujet + une diapositive par info) ; enregistré sauf rendu_seul."""
    from core.services.social import editorial as E
    une_fiche = fiches[0]
    cover = {"kicker": kicker, "headline": une_fiche["une"] or une_fiche["artiste"].upper(), "subtitle": une_fiche["titre"],
             "photo": photo(une_fiche["artiste"]), "edition": "Monde",
             "lines": [(i + 2, f["artiste"], f["titre"][:48]) for i, f in enumerate(fiches[1:4])]}
    # nom unique à chaque fabrication : une image refaite n'est jamais servie depuis le cache sous l'ancienne version
    nom = f"{jour.isoformat()}-{theme}-{datetime.now(timezone.utc):%H%M%S}"
    # toutes les images sur de vraies photos : l'artiste concerné en plein cadre, sinon une scène de concert
    from pathlib import Path
    from core.services.social import image as PI
    from core.services.social.editorial import GOLD, VIOLET
    PI.DIR.mkdir(parents=True, exist_ok=True)
    est_flash = theme.startswith("flash")
    total = len(fiches) + 2
    pages = [(une_fiche, kicker, None)]
    for i, f in enumerate(fiches):
        pages.append((f, f"{i + 2} / {total}", {"etiquette": RUBRIQUES[f["rubrique"]], "couleur": ROUGE if est_flash else (VIOLET, (20, 120, 210), (200, 70, 40))[i % 3],
                                                 "titre": f["titre"], "texte": f["resume"], "graine": str(i),
                                                 # une fois sur deux (et quand l'artiste n'a pas de photo), l'objet du sujet en fond
                                                 "fond": objet(f, f["cle"]) if (i % 2 == 1 or not photo(f["artiste"])) else None}))
    pages.append(({"artiste": "", "cle": nom, "sources": [], "une": "", "titre": ""}, f"{total} / {total}",
                  {"etiquette": "CAURI CHARTS", "couleur": (20, 20, 30), "titre": "La référence de la musique ouest-africaine", "texte": final, "graine": "fin"}))
    fichiers = []
    for n, (f, kk, dp) in enumerate(pages):
        a = PI.save_jpeg(couverture_choc(f, kk, est_flash, "feed", dp), PI.DIR / f"{nom}-{n}.jpg")
        b = PI.save_jpeg(couverture_choc(f, kk, est_flash, "tiktok", dp), PI.DIR / f"{nom}-{n}-916.jpg")
        fichiers.append({"file": Path(a).name, "tiktok": Path(b).name, "label": (dp or {}).get("titre") or une_fiche["une"] or une_fiche["artiste"]})
    legende = _legende(fiches, entete)
    hashtags = "#CauriMonde #CauriCharts #ActuMusique #Musique #" + re.sub(r"\W", "", _sans_accents(une_fiche["artiste"]).title())[:30]
    faits = {"day": jour.isoformat(), "fiches": [{k: v for k, v in f.items() if k not in ("items", "mots", "noms", "date")} for f in fiches],
             "due": due.isoformat() if due else None}
    if rendu_seul:
        return {"fichiers": fichiers, "legende": legende, "cover": cover, "fiches": fiches, "hashtags": hashtags, "faits": faits}
    return E.save_post(theme, jour.isoformat(), kicker, legende, hashtags, fichiers, faits)


def archive(fiches: list) -> None:
    """Chaque info publiée devient aussi un article dans Actualités (le site comme un journal) et ne repassera plus."""
    from core.views import now_utc
    for f in fiches:
        guid = f"monde-{f['cle']}"
        if db.value("SELECT 1 FROM news WHERE external_guid = ?", [guid]):
            continue
        src = f["items"][0]
        slug = re.sub(r"[^a-z0-9]+", "-", _sans_accents(f["titre"]).lower()).strip("-")[:180] + "-" + f["cle"][:6]
        db.insert("news", {"title": f["titre"][:200], "slug": slug, "summary": (f["accroche"] or f["resume"])[:400],
                           "body": f["resume"] + "\n\nSources : " + ", ".join(f["sources"]) + ".", "category": CATEGORIE_SITE[f["rubrique"]],
                           "country_id": None, "source_name": ", ".join(f["sources"])[:120], "source_url": src["url"][:500],
                           "image_path": None, "origin": "manual", "external_guid": guid, "status": "published", "published_at": now_utc()})


def edition(jour: date, quand: str, rendu_seul: bool = False) -> dict | None:
    """Édition de 8 h (« monde ») ou de 20 h (« records » + « sorties ») : les infos les plus reprises, jamais déjà publiées."""
    if not rendu_seul and db.value("SELECT 1 FROM social_posts WHERE slot_date = ? AND (theme = ? OR theme LIKE ?)",
                                   [jour.isoformat(), f"monde-{quand}", f"monde-{quand}-%"]):
        return None   # édition déjà faite aujourd'hui (une seule par créneau)
    histoires = [h for h in regroupe(collecte(30 if quand == "matin" else 24)) if not deja_publie(h["cle"])][:30]
    fiches = redige(histoires)
    if quand == "matin":
        choix = [f for f in fiches if f["rubrique"] == "monde"]
        choix += [f for f in fiches if f["rubrique"] != "monde"]
    else:
        # 20 h : records et projets d'abord — caps de streams réels (Kworb) et chercheur web, puis sorties
        extra = []
        try:
            extra = caps_streams()[:2] + recherche_records()
        except Exception as exc:  # noqa: BLE001
            log_write("monde", "warning", f"chercheur : {exc}")
        choix = extra + [f for f in fiches if f["rubrique"] in ("records", "sorties")] + [f for f in fiches if f["rubrique"] == "monde"]
    tries, vus_artistes = sorted(choix, key=lambda f: (not f["sensible"], score(f)), reverse=True), set()
    choix = []
    for f in tries:   # une seule info par artiste et par édition : de la variété
        a = _sans_accents(f["artiste"]).lower()
        if a and a in vus_artistes:
            continue
        vus_artistes.add(a); choix.append(f)
    choix = choix[:PAR_EDITION]
    if not choix:
        return None
    # UNE info = UN post = UN visage : celui qui aime Lady Gaga voit son post, celui qui aime Burna Boy le sien.
    # Les posts partent espacés (8 h, 8 h 45, 9 h 30… / 20 h, 20 h 45…) : le réveil de 10 min les envoie à leur heure.
    heure = 8 if quand == "matin" else 20
    depart = datetime(jour.year, jour.month, jour.day, heure, 0, tzinfo=timezone.utc)
    final = ("Ce soir à 20 h : les projets, records et sorties des stars." if quand == "matin"
             else "Demain dès 8 h : l'actu musicale du monde. Et chaque jour, le classement de l'Afrique de l'Ouest.")
    posts = []
    for i, f in enumerate(choix):
        due = depart + timedelta(minutes=ECART_MIN * i)
        kicker = f"Cauri Monde · {jour:%d/%m} · {due.hour} h" + (f" {due.minute:02d}" if due.minute else "")
        entete = f"🌍 Cauri Monde · {f['titre']}"
        posts.append(construit([f], jour, f"monde-{quand}-{i + 1}", kicker, entete, final, rendu_seul, due=due))
        if not rendu_seul:
            archive([f])
    return posts[0] if rendu_seul else {"title": f"{len(posts)} posts Cauri Monde ({quand})", "posts": posts}


def flash(rendu_seul: bool = False, forcer: bool = False) -> dict | None:
    """L'info choc des 3 dernières heures, reprise par ≥ 2 médias, jamais publiée : un post « FLASH » immédiat."""
    histoires = [h for h in regroupe(collecte(4 if not forcer else 30)) if (confirme(h) or forcer) and not deja_publie(h["cle"])]
    if not histoires:
        return None
    fiches = sorted(redige(histoires[:8]), key=lambda f: f["choc"], reverse=True)
    f = next((x for x in fiches if x["choc"] >= SEUIL_FLASH or forcer), None)
    if not f:
        return None
    maintenant = datetime.now(timezone.utc)
    kicker = f"FLASH · {maintenant:%d/%m · %H:%M} GMT"
    entete = f"🚨 FLASH · {f['titre']}"
    post = construit([f], maintenant.date(), f"flash-{maintenant:%H%M}", kicker, entete,
                     "Info confirmée par " + " et ".join(f["sources"][:3]) + ". Suivez Cauri Charts pour ne rien manquer.", rendu_seul)
    if not rendu_seul:
        archive([f])
    return post


# ---------------------------------------------------------------- publication et guet des flashs

def publie(post: dict, due) -> list:
    """Instagram, TikTok et Facebook (Buffer), puis la chaîne Telegram ; chaque canal à part (un échec ne bloque pas l'autre)."""
    from core.services import buffer, telegram
    lignes = []
    try:
        lignes.append("Buffer : " + buffer.schedule(post, due) if buffer.configured() else "Buffer non configuré")
    except Exception as exc:  # noqa: BLE001
        lignes.append(f"Buffer : échec ({exc})")
    try:
        lignes.append("Telegram : " + telegram.send_post(post) if telegram.configured() else "Telegram non configuré")
    except Exception as exc:  # noqa: BLE001
        lignes.append(f"Telegram : échec ({exc})")
    return lignes


def vu(cle: str) -> bool:
    return bool(db.value("SELECT 1 FROM monde_vus WHERE cle = ?", [cle]))


def marque_vu(cles: list) -> None:
    for c in cles:
        db.run("INSERT INTO monde_vus (cle) VALUES (?) ON CONFLICT DO NOTHING", [c])


def confirme(h: dict) -> bool:
    """Flash : au moins un grand média de référence parmi les sources, ou trois médias différents."""
    grands = {f["name"] for f in FEEDS}
    return len(h["sources"]) >= SOURCES_FLASH and (bool(grands & set(h["sources"])) or len(h["sources"]) >= 3)


def guette() -> dict | None:
    """Vérification légère (quelques secondes, appelée toutes les 10 min) : une info des 3 dernières heures, reprise par
    au moins 2 médias, jamais publiée ni déjà jugée ? La rédaction lui donne une note ; ≥ SEUIL_FLASH → à publier.
    Renvoie la fiche retenue (le rendu et la publication se font ensuite sur GitHub, plus puissant)."""
    neuves = [h for h in regroupe(collecte(3)) if confirme(h) and not deja_publie(h["cle"]) and not vu(h["cle"])]
    fiches = redige(neuves[:6]) if neuves else []
    marque_vu([h["cle"] for h in neuves[:6]])      # chaque info n'est jugée qu'une fois
    # un cap historique franchi aujourd'hui (≥ 10 milliards de streams) est un flash à lui seul
    try:
        caps = [f for f in caps_streams(0) if f["choc"] >= 85 and not vu(f["cle"])]
        marque_vu([f["cle"] for f in caps])
        fiches += caps
    except Exception as exc:  # noqa: BLE001
        log_write("monde", "warning", f"caps : {exc}")
    retenue = max(fiches, key=lambda f: f["choc"], default=None)
    return retenue if retenue and retenue["choc"] >= SEUIL_FLASH else None


# ---------------------------------------------------------------- le chercheur : records, certifications, caps de streams

# Artistes suivis de près pour leurs records (en plus de STARS) : la scène francophone et ouest-africaine qui fait des chiffres
CHERCHES = STARS + ["Tiakola", "Damso", "SDM", "Werenoi", "Gazo", "Himra", "Didi B", "Josey", "Innoss'B", "Dadju", "Tayc",
                    "Joé Dwèt Filé", "Shatta Wale", "Stonebwoy", "Sarkodie", "KiDi", "Omah Lay", "CKay", "Fireboy DML",
                    "Kizz Daniel", "Oxlade", "Seyi Vibez", "Olamide", "Victony", "Shallipopi", "Toofan", "Magic System",
                    "Booba", "PNL", "Orelsan", "Angèle", "Soolking", "Naps", "Zola"]
AFRICAINS = {_sans_accents(n).lower() for n in [
    "Burna Boy", "Wizkid", "Davido", "Tems", "Rema", "Asake", "Ayra Starr", "Tyla", "Fally Ipupa", "Black Sherif", "Didi B",
    "Josey", "Innoss'B", "Shatta Wale", "Stonebwoy", "Sarkodie", "KiDi", "Omah Lay", "CKay", "Fireboy DML", "Kizz Daniel",
    "Oxlade", "Seyi Vibez", "Olamide", "Victony", "Shallipopi", "Toofan", "Magic System", "Aya Nakamura", "Tiakola", "Dadju",
    "Tayc", "Gims"]}
MOTS_RECORDS = ("(record OR certifié OR \"disque de platine\" OR \"disque d'or\" OR \"disque de diamant\" OR milliard "
                "OR \"millions de streams\" OR démarrage OR \"numéro un\" OR historique)")


def _flux_records() -> list:
    from urllib.parse import quote
    lots = [CHERCHES[i:i + 6] for i in range(0, len(CHERCHES), 6)]
    return [{"name": "Google Actualités", "url": GOOGLE_NEWS + quote("(" + " OR ".join(f'"{n}"' for n in lot) + ") " + MOTS_RECORDS + " when:7d"),
             "poids": 1} for lot in lots]


def recherche_records() -> list:
    """Le chercheur web : les articles récents sur les records et certifications des artistes suivis.
    Seuls les faits des vrais articles trouvés sont gardés (sources citées) ; un record sans chiffre est écarté."""
    def un(feed):
        try:
            return [{**it, "source": feed["name"], "poids": feed["poids"]} for it in parse_feed(http_get(feed["url"]) or "")]
        except Exception:  # noqa: BLE001
            return []
    with ThreadPoolExecutor(6) as ex:
        items = [it for lot in ex.map(un, _flux_records()) for it in lot]
    for it in items:
        if " - " in it["title"]:
            it["title"], it["source"] = it["title"].rsplit(" - ", 1)
            it["poids"] = 2
        d = it.get("published_at")
        if isinstance(d, str):
            try:
                d = datetime.fromisoformat(d.replace("Z", "+00:00"))
            except ValueError:
                d = None
        if d is not None and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        it["date"] = d or datetime.now(timezone.utc)
    histoires = [h for h in regroupe(items) if not deja_publie(h["cle"])]
    fiches = redige(histoires[:20])
    return [{**f, "rubrique": "records"} for f in fiches if re.search(r"\d", f["titre"] + f["resume"])]


def _kworb() -> list:
    """Top 3 000 Spotify (Kworb, compteurs publics) : [(nom, total en millions, par jour en millions)]."""
    import html as H
    page = http_get("https://kworb.net/spotify/artists.html") or ""
    rows = re.findall(r'<a href="/spotify/artist/[^"]+">([^<]+)</a></div></td>\s*<td>([\d,.]+)</td>\s*<td>([\d,.]+)</td>', page)
    return [(H.unescape(n), float(t.replace(",", "")), float(dj.replace(",", ""))) for n, t, dj in rows]


def _volume(m: float) -> str:
    if m >= 1000:
        v = m / 1000
        txt = f"{v:,.1f}".replace(",", " ").replace(".0", "").replace(".", ",")
        return txt + (" milliards" if v >= 2 else " milliard")
    return f"{m:,.0f}".replace(",", " ") + " millions"


def caps_streams(jours_annonce: int = 3) -> list:
    """Caps ronds franchis aujourd'hui (ou dans ≤ jours_annonce jours) sur Spotify, calculés sur les vrais compteurs :
    tous les 10 milliards au-delà de 10 Md, chaque milliard en dessous ; artistes africains : tous les 500 millions."""
    out = []
    suivis = {_sans_accents(n).lower() for n in CHERCHES} | AFRICAINS
    for nom, total, jour in _kworb():
        afr = _sans_accents(nom).lower() in AFRICAINS
        if _sans_accents(nom).lower() not in suivis and total < 30000:
            continue   # seulement les visages que tout le monde connaît (ou les géants au-delà de 30 milliards)
        pas = 10000 if total >= 10000 else (500 if afr and total >= 500 else (1000 if total >= 1000 else None))
        if not pas or jour <= 0:
            continue
        cap = (total // pas) * pas
        if cap > 0 and total - jour < cap <= total:
            etat, cible = "franchi", cap
        else:
            cible = cap + pas
            if (cible - total) / jour > jours_annonce:
                continue
            etat = "bientot"
        cle = hashlib.sha1(f"kworb-{nom}-{cible:.0f}-{etat}".encode()).hexdigest()[:12]
        if deja_publie(cle):
            continue
        n_jours = max(1, round((cible - total) / jour))
        if etat == "franchi":
            titre = f"{nom} franchit les {_volume(cible)} de streams sur Spotify"
            une = f"{nom} : {_volume(cible)} de streams"
        else:
            titre = f"{nom} va franchir les {_volume(cible)} de streams sur Spotify d'ici {n_jours} jour{'s' if n_jours > 1 else ''}"
            une = f"{nom} : bientôt {_volume(cible)}"
        resume = (f"Selon les compteurs publics de Spotify relevés par Kworb, {nom} totalise {_volume(total)} de streams, "
                  f"avec {jour:.1f} millions de streams par jour en ce moment.").replace(".", ",", 0)
        out.append({"items": [{"title": titre, "url": "https://kworb.net/spotify/artists.html", "summary": resume}],
                    "sources": ["Spotify (via Kworb)"], "poids": 3, "date": datetime.now(timezone.utc), "cle": cle,
                    "rubrique": "records", "artiste": nom, "une": une.upper(), "titre": titre, "accroche": titre, "resume": resume,
                    "choc": (95 if cible >= 50000 else 85 if cible >= 10000 else 70) if etat == "franchi" else 55,
                    "sensible": False, "mots": set(), "noms": set()})
    return sorted(out, key=lambda f: -f["choc"])


# ---------------------------------------------------------------- file d'attente : un post à la fois, à son heure

def en_attente() -> list:
    """Posts Cauri Monde arrivés à leur heure et pas encore envoyés (requête légère, appelée toutes les 10 min)."""
    maintenant = datetime.now(timezone.utc)
    out = []
    for r in db.all("""SELECT id, facts FROM social_posts WHERE theme LIKE 'monde-%' AND slot_date >= CURRENT_DATE - 1
                       AND status = 'approved' ORDER BY id"""):
        try:
            due = json.loads(r["facts"]).get("due")
        except (ValueError, TypeError):
            continue
        if due and datetime.fromisoformat(due) <= maintenant and not vu(f"pub-{r['id']}"):
            out.append(r["id"])
    return out


def publie_file() -> list:
    """Envoie les posts arrivés à leur heure (Buffer : Instagram, TikTok, Facebook ; puis Telegram), un par un."""
    lignes = []
    for pid in en_attente():
        post = db.one("SELECT * FROM social_posts WHERE id = ?", [pid])
        marque_vu([f"pub-{pid}"])   # avant l'envoi : jamais deux fois, même si un canal échoue
        lignes += [f"{post['title']} ({post['theme']})"] + publie(post, datetime.now(timezone.utc) + timedelta(minutes=2))
    return lignes
