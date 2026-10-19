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

from core import db, env
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
    # Actualité musicale AFRICAINE (flux testés le 18/10/2026 : tous répondent avec des articles des 3 derniers jours).
    # « afrique » : leurs sujets passent en priorité dans la sélection ; « exclure » : titres qui ne sont pas de l'actu.
    # Écartés au test : Pulse (flux généraux sans rubrique musique), OkayAfrica, TRACE, GhanaWeb, YEN/Legit (rubriques
    # non filtrées), Pan African Music (dernier article de 2025), Africanews et BBC Afrique (pas de flux culture).
    {"name": "NotJustOk", "url": "https://notjustok.com/feed/", "poids": 2, "afrique": True,
     "exclure": r"\blyrics\b|\bchelsea\b|\bpremier league\b"},
    {"name": "BellaNaija", "url": "https://www.bellanaija.com/category/music/feed/", "poids": 2, "afrique": True},
    {"name": "Music In Africa", "url": "https://www.musicinafrica.net/rss", "poids": 2, "afrique": True},
    {"name": "The Native", "url": "https://thenativemag.com/feed/", "poids": 2, "afrique": True},
    {"name": "Graphic Showbiz", "url": "https://www.graphic.com.gh/entertainment.feed?type=rss", "poids": 2, "afrique": True},
    {"name": "Senego", "url": "https://senego.com/rubrique/people/feed", "poids": 1, "afrique": True},
]
# Veille Google Actualités sur la musique africaine elle-même (genres, scènes nationales), en français et en anglais
AFRIQUE_REQUETES = [
    ("https://news.google.com/rss/search?hl=fr&gl=FR&ceid=FR:fr&q=",
     '(afrobeats OR "coupé-décalé" OR "musique africaine" OR "musique ivoirienne" OR "musique togolaise" OR '
     '"musique béninoise" OR "musique sénégalaise" OR "musique camerounaise" OR "rap ivoirien" OR "zouglou" OR '
     '"rap togolais" OR "mbalax") when:2d'),
    ("https://news.google.com/rss/search?hl=en-NG&gl=NG&ceid=NG:en&q=",
     '(afrobeats OR "Nigerian music" OR "Ghanaian music" OR amapiano OR "African music") when:2d'),
]
# Les plus grands visages de la musique, du moment et de tous les temps (veille Google Actualités en français)
STARS = ["Beyoncé", "Taylor Swift", "Rihanna", "Drake", "Bad Bunny", "The Weeknd", "Ed Sheeran", "Billie Eilish", "Dua Lipa",
         "Kendrick Lamar", "Travis Scott", "Ariana Grande", "Justin Bieber", "Bruno Mars", "Lady Gaga", "Adele", "Eminem",
         "Kanye West", "Jay-Z", "Nicki Minaj", "Cardi B", "Sabrina Carpenter", "Doja Cat", "Post Malone", "Shakira",
         "Karol G", "SZA", "Olivia Rodrigo", "Coldplay", "BTS", "Blackpink", "Rosé", "Lisa", "Miley Cyrus", "Harry Styles",
         "Michael Jackson", "Madonna", "Céline Dion", "Stromae", "Aya Nakamura", "Ninho", "Jul", "Gims",
         "Burna Boy", "Wizkid", "Davido", "Tems", "Rema", "Asake", "Ayra Starr", "Tyla", "Fally Ipupa", "Black Sherif",
         # grandes stars francophones et africaines hors Afrique de l'Ouest (18/10/2026)
         "Dadju", "Tayc", "Ferre Gola", "Innoss'B", "Koffi Olomide", "Héritier Watanabe", "Diamond Platnumz",
         "Black Coffee", "Uncle Waffles", "Tiakola", "Werenoi", "Damso", "Niska", "SDM"]
GOOGLE_NEWS = "https://news.google.com/rss/search?hl=fr&gl=FR&ceid=FR:fr&q="


# Noms trop courts ou trop communs pour une recherche seule (homonymes) : la forme qu'emploie la presse musicale
REQUETE_STAR = {"SDM": "rappeur SDM", "Black Coffee": "DJ Black Coffee"}


def _flux_stars() -> list:
    from urllib.parse import quote
    lots = [STARS[i:i + 9] for i in range(0, len(STARS), 9)]
    return ([{"name": "Google Actualités", "url": GOOGLE_NEWS + quote("(" + " OR ".join(f'"{REQUETE_STAR.get(n, n)}"' for n in lot) + ") musique when:2d"), "poids": 1, "stars": True}
             for lot in lots]
            + [{"name": "Google Actualités", "url": base + quote(q), "poids": 1, "afrique": True} for base, q in AFRIQUE_REQUETES]
            + _flux_nos_artistes())


def _flux_nos_artistes() -> list:
    """Veille Google Actualités sur les artistes de NOS classements (décision du 19/10/2026 : l'actu doit d'abord être
    ouest-africaine). Les plus vus des 30 derniers jours, par lots ; les scènes francophones (CI, TG, SN, BJ) en français."""
    from urllib.parse import quote
    try:
        lignes = db.all("""SELECT name, upper(origin_country) AS code FROM artists
                           WHERE status = 'active' AND length(name) >= 4 AND origin_country IS NOT NULL
                           ORDER BY youtube_subscribers DESC NULLS LAST LIMIT 120""")
    except Exception:  # noqa: BLE001
        return []
    flux = []
    for langue, codes, base in (("fr", {"CI", "TG", "SN", "BJ", "ML", "BF", "GN", "NE", "CM"}, GOOGLE_NEWS),
                                ("en", {"NG", "GH", "LR", "SL", "GM"}, "https://news.google.com/rss/search?hl=en-NG&gl=NG&ceid=NG:en&q=")):
        noms = [r["name"] for r in lignes if r["code"] in codes][:24]
        for i in range(0, len(noms), 8):
            q = "(" + " OR ".join(f'"{n}"' for n in noms[i:i + 8]) + ") (musique OR music OR concert OR album OR clip) when:2d"
            flux.append({"name": "Google Actualités", "url": base + quote(q), "poids": 1, "afrique": True})
    return flux


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
            return [{**it, "source": feed["name"], "poids": feed["poids"], "afrique": bool(feed.get("afrique"))}
                    for it in parse_feed(xml or "")
                    if not (feed.get("exclure") and re.search(feed["exclure"], it.get("title") or "", re.I))]
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
        h["afrique"] = any(i.get("afrique") for i in h["items"])   # vue par un média africain
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
        ' "une": "accroche de couverture, 28 caractères max, en MAJUSCULES, qui donne ENVIE de savoir la suite : le détail le plus fou '
        'de l\'info (un chiffre, un refus, une première, un clash), jamais un résumé plat. Ex. : « 10 MILLIONS EN 24 H », '
        '« ELLE A DIT NON À 50 M$ », « PERSONNE N\'AVAIT FAIT ÇA », « RIHANNA : 9E ALBUM ». Interdit : mentir, exagérer, inventer",\n'
        ' "accent": "LE mot ou chiffre du titre à mettre en couleur sur la couverture (le plus fort : un chiffre, un nom, un mot choc), recopié tel quel",\n'
        ' "titre": "phrase de 6 à 9 mots (60 caractères max) qui dit EXACTEMENT ce qui se passe, l\'élément le plus surprenant en premier, '
        'avec le chiffre clé s\'il y en a un",\n'
        ' "accroche": "110 caractères max : la question que le lecteur se pose (pourquoi ? comment ? et maintenant ?), pour qu\'il '
        'fasse défiler",\n'
        ' "resume": "3 phrases, 330 caractères max, qui racontent : 1) le fait, 2) pourquoi c\'est énorme (contexte, comparaison, '
        'record battu), 3) ce qui va se passer ensuite. Ton vivant, comme un ami passionné qui raconte, sans jamais rien ajouter '
        'aux articles",\n'
        ' "choc": 0-100 (100 = info mondiale majeure : sortie surprise d\'une star, record historique, annonce Grammy, décès d\'une légende ; '
        'note aussi plus haut l\'argent (contrats, fortunes, cachets), les clashs publics, les révélations, les premières historiques),\n'
        ' "sensible": true si décès, santé, justice, violence,\n'
        ' "question": "une question courte au public, qui pousse à commenter, terminée par ⁉️ (ex. Vous attendiez cet album ⁉️)",\n'
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
                    "titre": coupe(f.get("titre") or h["items"][0]["title"], 140), "accent": coupe(f.get("accent"), 30),
                    "accroche": coupe(f.get("accroche"), 130), "resume": coupe(f.get("resume"), 420),
                    "question": coupe(f.get("question") or "Vous en pensez quoi ⁉️", 110),
                    "choc": int(f.get("choc") or 0), "sensible": bool(f.get("sensible"))})
    return out


# ---------------------------------------------------------------- photo (Deezer, photo d'artiste officielle)

_PHOTOS: dict = {}


def photo(artiste: str):
    """Image de couverture de l'artiste : une image du pôle média (plans de clips officiels, photos de scène libres)
    qui n'a pas servi depuis 10 jours ; à défaut, sa photo de notre base ou de Deezer. Une seule image par artiste et
    par exécution : toutes les diapositives d'un post montrent la même."""
    if not artiste:
        return None
    if artiste not in _PHOTOS:
        from core.services.social import medias
        _PHOTOS[artiste] = medias.choisit(artiste, _photo_portrait(artiste), alterne=len(_PHOTOS))
    return _PHOTOS[artiste]


def _plus_grande(url):
    """La plus grande version servie par la source : Apple Music à sa taille d'origine, Deezer en 1 200 px (son maximum)."""
    if not url:
        return url
    if "mzstatic.com" in url:
        return re.sub(r"/\d+x\d+(bb|cc)?\.(jpg|png|webp)$", r"/3000x3000bb.", url)
    if "dzcdn.net" in url:
        return re.sub(r"/\d+x\d+-", "/1200x1200-", url)
    return url


def _photo_portrait(artiste: str):
    """Photo de l'artiste (dans sa plus grande taille) : notre base, sinon Deezer par nom exact."""
    return _plus_grande(_photo_portrait_brute(artiste))


def _photo_portrait_brute(artiste: str):
    """Photo de l'artiste : d'abord celle de notre base (vérifiée), sinon Deezer par nom exact (homonymes possibles)."""
    try:
        nous = db.value("""SELECT COALESCE(NULLIF(image_hd_url, ''), NULLIF(image_url, '')) FROM artists
                           WHERE LOWER(name) = LOWER(?) AND status = 'active' LIMIT 1""", [artiste])
        if nous:
            return nous
    except Exception:  # noqa: BLE001
        pass
    try:
        from urllib.parse import quote
        a = _deezer_artiste(artiste)
        if a and "/artist//" not in (a.get("picture_xl") or "/artist//"):
            return a["picture_xl"]
    except Exception as exc:  # noqa: BLE001
        log_write("monde", "warning", f"photo {artiste} : {exc}")
    return None


def _deezer_artiste(artiste: str) -> dict | None:
    """L'artiste Deezer de ce nom exact qui a le plus de fans : « Jul » donnait un homonyme à 1 285 fans au lieu du rappeur
    (11 millions de fans, 5e résultat de la recherche) — 17/10/2026."""
    from urllib.parse import quote
    r = json.loads(http_get("https://api.deezer.com/search/artist?limit=10&q=" + quote(artiste)) or "{}")
    memes = [a for a in (r.get("data") or []) if _sans_accents(a.get("name", "")).lower() == _sans_accents(artiste).lower()]
    return max(memes, key=lambda a: int(a.get("nb_fan") or 0)) if memes else None


_FANS: dict = {}


def fans(artiste: str) -> int:
    """Nombre de fans Deezer de l'artiste (donnée réelle) : mesure de notoriété mondiale."""
    if not artiste:
        return 0
    if artiste not in _FANS:
        _FANS[artiste] = 0
        try:
            from urllib.parse import quote
            a = _deezer_artiste(artiste)
            if a:
                _FANS[artiste] = int(a.get("nb_fan") or 0)
        except Exception:  # noqa: BLE001
            pass
    return _FANS[artiste]


_NOS_ARTISTES: set | None = None


def nos_artistes() -> set:
    """Noms (sans accents, en minuscules) des artistes actifs suivis en base : la scène ouest-africaine."""
    global _NOS_ARTISTES
    if _NOS_ARTISTES is None:
        try:
            _NOS_ARTISTES = {_sans_accents(r["name"]).lower() for r in db.all("SELECT name FROM artists WHERE status = 'active'")
                             if len(r["name"] or "") >= 3}
        except Exception:  # noqa: BLE001
            _NOS_ARTISTES = set()
    return _NOS_ARTISTES


def africain(f: dict) -> bool:
    """L'info parle-t-elle d'un artiste africain (stars africaines de la liste, ou artiste suivi dans nos classements) ?"""
    a = _sans_accents(f.get("artiste") or "").lower().strip()
    return bool(a) and (a in AFRICAINS or a in nos_artistes())


BONUS_AFRIQUE = 15   # léger coup de pouce : notre public est d'abord ouest-africain


def score(f: dict) -> float:
    """Note d'une info : son poids « choc », le nombre de médias, et surtout la notoriété de l'artiste (les plus grands visages devant).
    Léger bonus aux artistes africains (et un peu moins aux infos venues d'un média africain)."""
    import math
    star = any(_sans_accents(n).lower() == _sans_accents(f.get("artiste", "")).lower() for n in STARS)
    bonus = BONUS_AFRIQUE if africain(f) else (5 if f.get("afrique") else 0)
    return f["choc"] + 12 * len(f["sources"]) + 9 * math.log10(1 + fans(f.get("artiste", ""))) + (25 if star else 0) + bonus


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


STYLE_GRAINE = ""   # posée par construit() / formats._post : un même style sur toutes les images d'un post

# Polices de titre (fichier, facteur de taille : les polices étroites montent plus haut) et police du texte associée
POLICES = [("Anton-Regular.ttf", 1.0, "Poppins"), ("BebasNeue-Regular.ttf", 1.18, "Lato"), ("ArchivoBlack-Regular.ttf", .74, "Poppins"),
           ("AlfaSlabOne-Regular.ttf", .76, "PT_Sans"), ("Bungee-Regular.ttf", .70, "Lato"), ("AbrilFatface-Regular.ttf", .86, "PT_Sans")]
TEXTES = {"Poppins": ("Poppins-Bold.ttf", "Poppins-Regular.ttf"), "Lato": ("Lato-Bold.ttf", "Lato-Regular.ttf"),
          "PT_Sans": ("PT_Sans-Web-Bold.ttf", "PT_Sans-Web-Regular.ttf")}
ACCENTS = [(255, 190, 40), (90, 220, 255), (255, 70, 170), (190, 255, 80), (255, 120, 90), (255, 255, 255)]
BANDEAUX = [(139, 82, 255), (20, 120, 210), (229, 33, 59), (14, 12, 20), (0, 150, 120)]


def style(graine: str) -> dict:
    """Style d'un post, tiré de façon stable de sa graine : police, couleurs, traitement du titre, mise en page."""
    import random
    r = random.Random(hashlib.sha1(("style-" + graine).encode()).hexdigest())
    police, facteur, texte = r.choice(POLICES)
    accent = r.choice(ACCENTS)
    return {"police": police, "facteur": facteur, "gras": TEXTES[texte][0], "normal": TEXTES[texte][1], "accent": accent,
            "titre": r.choice(["derniere", "premiere", "surligne", "alterne", "derniere"]),
            "align": r.choice(["gauche", "gauche", "centre"]), "position": r.choice(["bas", "bas", "haut", "affiche", "affiche"]),
            "bandeau": r.choice(["bloc", "pastille", "souligne"]), "couleur_bandeau": r.choice(BANDEAUX)}


def couverture_choc(f: dict, kicker: str, est_flash: bool, fmt: str = "feed", diapo: dict | None = None):
    """Image d'un post : photo du sujet plein cadre, bandeau, titre géant qui dit exactement de quoi on parle, phrase,
    sources. Le STYLE change d'un post à l'autre (police, couleurs, titre surligné ou bicolore, texte en haut ou en bas,
    aligné à gauche ou centré) ; la lisibilité reste garantie (zone floutée + assombrie, ombre). Rendu ×2 (4K)."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFilter, ImageStat
    from core.services.social import image as PI
    from core.services.social.editorial import INK, VIOLET
    st = style(STYLE_GRAINE or f.get("cle") or kicker)
    k = 2
    W, H = (1080 * k, 1350 * k) if fmt == "feed" else (1080 * k, 1920 * k)
    haut, bas, cote = (70 * k, 90 * k, 80 * k) if fmt == "feed" else (250 * k, 440 * k, 90 * k)
    en_haut = st["position"] == "haut"
    affiche = st["position"] == "affiche"   # fond de couleur unie, photo en carte encadrée, texte dessous
    img = Image.new("RGB", (W, H), st["couleur_bandeau"] if affiche else INK)
    # la photo d'un artiste seulement si son nom est bien dans le titre de l'info (jamais la photo d'un autre)
    texte_sujet = " ".join([(diapo or {}).get("titre") or "", f.get("titre", "") or "", f.get("une", "") or ""])
    nom_ok = f.get("photo_ok") or (f.get("artiste") and _sans_accents(f["artiste"]).lower() in _sans_accents(texte_sujet).lower())
    url = None if ((diapo or {}).get("fond") or not nom_ok) else photo(f["artiste"])
    src = (diapo or {}).get("fond") or f.get("illustration_fond")
    if not src and not url:   # pas de photo sûre : l'objet du sujet, sinon (plus bas) une scène de concert
        src = objet(f, f.get("cle", "") + (diapo or {}).get("graine", ""))
    if not src:
        try:
            src = BytesIO(http_get(url, binary=True)) if url else _scene(f.get("cle", "") + (diapo or {}).get("graine", ""))
        except Exception:  # noqa: BLE001
            src = _scene(f.get("cle", ""))
    if src and affiche:
        try:
            ph = Image.open(src).convert("RGB")
            bw, bh = W - 2 * cote, int(H * (.43 if fmt == "feed" else .30))
            r = max(bw / ph.width, bh / ph.height)
            ph = ph.resize((int(ph.width * r), int(ph.height * r)), Image.LANCZOS)
            x1 = (ph.width - bw) // 2
            ph = ph.crop((x1, 0, x1 + bw, bh))
            y_carte = haut + 130 * k
            ImageDraw.Draw(img).rounded_rectangle([cote - 12 * k, y_carte - 12 * k, cote + bw + 12 * k, y_carte + bh + 12 * k], radius=34 * k, fill=(255, 255, 255))
            masque = Image.new("L", (bw, bh), 0)
            ImageDraw.Draw(masque).rounded_rectangle([0, 0, bw, bh], radius=26 * k, fill=255)
            img.paste(ph, (cote, y_carte), masque)
        except Exception as exc:  # noqa: BLE001
            log_write("monde", "warning", f"photo affiche : {exc}")
    elif src:
        try:
            ph = Image.open(src).convert("RGB")
            r = max(W / ph.width, H * .78 / ph.height)
            ph = ph.resize((int(ph.width * r), int(ph.height * r)), Image.LANCZOS)
            # texte en haut : la photo descend (le visage reste dégagé sous le texte)
            img.paste(ph, ((W - ph.width) // 2, H - ph.height if en_haut else 0))
        except Exception as exc:  # noqa: BLE001
            log_write("monde", "warning", f"photo couverture : {exc}")
    else:
        img = Image.blend(img, Image.new("RGB", (W, H), VIOLET), .55)

    def rampe(debut, fin, fort=1.0):
        m = Image.new("L", (1, 256))
        for y in range(256):
            v = max(0, min(1, (y / 255 - debut) / (fin - debut)))
            m.putpixel((0, 255 - y if en_haut else y), int(255 * fort * v))
        return m.resize((W, H))
    if not affiche:
        # zone du texte : floutée (le texte d'une pochette ne se mélange jamais au nôtre), puis assombrie
        img = Image.composite(img.filter(ImageFilter.GaussianBlur(22 * k)), img, rampe(.50, .64))
        zone = (0, 0, W, int(H * .45)) if en_haut else (0, int(H * .55), W, H)
        lum = ImageStat.Stat(img.crop(zone).convert("L")).mean[0] / 255
        img = Image.blend(img, Image.new("RGB", (W, H), INK), min(.35, max(.05, (lum - .3) * .8)))
        img = Image.composite(Image.new("RGB", (W, H), INK), img, rampe(.46, .74, .95))
    d = ImageDraw.Draw(img)
    fd = PI.FONT_DIR / st["police"]
    fb, fs = PI.FONT_DIR / st["gras"], PI.FONT_DIR / st["normal"]
    fband = PI.FONT_DIR / "Anton-Regular.ttf"
    accent = st["accent"]
    if affiche and st["couleur_bandeau"] in ((229, 33, 59),) and accent in ((255, 70, 170), (255, 120, 90)):
        accent = (255, 190, 40)

    # ---- bandeau (bloc, pastille ou souligné) + « CAURI CHARTS »
    etiquette = (diapo or {}).get("etiquette") or ("FLASH" if est_flash else "CAURI MONDE")
    coul = ROUGE if est_flash else ((diapo or {}).get("couleur") or st["couleur_bandeau"])
    if affiche and coul == st["couleur_bandeau"]:
        coul = INK if coul != INK else (139, 82, 255)
    fe = PI.font(str(fband), 60 * k)
    x0, y0 = cote, haut
    wl = d.textlength(etiquette, font=fe)
    kicker = re.sub(r"^(cauri monde|flash)\s*·?\s*", "", kicker, flags=re.I)
    fk = PI.font(str(fb), 25 * k)
    wk = d.textlength(kicker.upper(), font=fk)
    if st["bandeau"] == "pastille":
        d.rounded_rectangle([x0, y0, x0 + wl + 48 * k, y0 + 88 * k], radius=44 * k, fill=coul)
        d.text((x0 + 24 * k, y0 + 44 * k), etiquette, font=fe, fill="white", anchor="lm")
        d.rounded_rectangle([x0 + wl + 60 * k, y0 + 14 * k, x0 + wl + 100 * k + wk, y0 + 74 * k], radius=30 * k, fill=(255, 255, 255))
        d.text((x0 + wl + 80 * k, y0 + 44 * k), kicker.upper(), font=fk, fill=INK, anchor="lm")
        fin_bandeau = x0 + wl + 100 * k + wk
    elif st["bandeau"] == "souligne":
        d.text((x0, y0 + 44 * k), etiquette, font=fe, fill="white", anchor="lm")
        d.rectangle([x0, y0 + 84 * k, x0 + wl, y0 + 94 * k], fill=accent if not est_flash else ROUGE)
        d.text((x0 + wl + 24 * k, y0 + 44 * k), kicker.upper(), font=fk, fill=(235, 235, 245), anchor="lm")
        fin_bandeau = x0 + wl + 24 * k + wk
    else:
        d.rectangle([x0, y0, x0 + wl + 44 * k, y0 + 92 * k], fill=coul)
        d.text((x0 + 22 * k, y0 + 46 * k), etiquette, font=fe, fill="white", anchor="lm")
        d.rectangle([x0 + wl + 44 * k, y0, x0 + wl + 84 * k + wk, y0 + 92 * k], fill=(255, 255, 255))
        d.text((x0 + wl + 64 * k, y0 + 46 * k), kicker.upper(), font=fk, fill=INK, anchor="lm")
        fin_bandeau = x0 + wl + 84 * k + wk
    fm = PI.font(str(fband), 34 * k)
    wm = d.textlength("CAURI CHARTS", font=fm)
    if W - cote - wm - 40 * k > fin_bandeau + 30 * k:   # pastille sombre : lisible sur toutes les photos
        d.rounded_rectangle([W - cote - wm - 40 * k, y0 + 14 * k, W - cote, y0 + 78 * k], radius=32 * k, fill=INK)
        d.text((W - cote - 20 * k, y0 + 46 * k), "CAURI CHARTS", font=fm, fill="white", anchor="rm")

    # ---- textes : phrase (taille fixe), puis titre le plus grand possible dans le budget de hauteur
    une = ((diapo or {}).get("titre") or f["une"] or f["artiste"]).upper()
    largeur = W - 2 * cote
    ft2 = PI.font(str(fb if not diapo else fs), (38 if not diapo else 30) * k)
    interl2 = (52 if not diapo else 44) * k
    phrase, l2 = ((diapo or {}).get("texte") or f["titre"]), []
    for para in phrase.split("\n"):
        cur = ""
        for m in para.split():
            essai = (cur + " " + m).strip()
            if d.textlength(essai, font=ft2) <= largeur:
                cur = essai
            else:
                l2.append(cur); cur = m
        l2.append(cur)
    l2 = [x for x in l2 if x][:3 if not diapo else (6 if "\n" in phrase else 4)]
    budget = H * (.42 if fmt == "feed" else .55)
    carte_bas = haut + 130 * k + int(H * (.43 if fmt == "feed" else .30)) + 12 * k
    if affiche:   # le texte vit sous la carte photo : tout l'espace restant, jamais par-dessus
        budget = H - carte_bas - 40 * k
    fixe = bas + 34 * k + 40 * k + len(l2) * interl2 + 34 * k
    max_lignes = 4 if diapo else 3
    surligne = st["titre"] == "surligne"
    marge_x = 18 * k if surligne else 0
    for px0 in range(160 if not diapo else 104, 44, -4):
        px = int(px0 * st["facteur"])
        ft = PI.font(str(fd), px * k)
        mots, lignes, cur = une.split(), [], ""
        for m in mots:
            essai = (cur + " " + m).strip()
            if d.textlength(essai, font=ft) <= largeur - 2 * marge_x:
                cur = essai
            else:
                lignes.append(cur); cur = m
        lignes.append(cur)
        pas = int(px * k * (1.12 if surligne else .96))
        if (len(lignes) <= max_lignes and all(d.textlength(l, font=ft) <= largeur - 2 * marge_x for l in lignes)
                and fixe + len(lignes) * pas <= budget):
            break
    fsrc = PI.font(str(fb), 24 * k)
    src = ("SOURCES · " + " · ".join(s.upper() for s in f["sources"][:4])) if f.get("sources") else "CAURICHARTS.COM"
    wsrc = d.textlength(src, font=fsrc)

    # positions : bloc en bas (titre → phrase → sources) ou en haut sous le bandeau
    if en_haut or affiche:
        base0 = (carte_bas + 50 * k if affiche else haut + 140 * k) + pas * .82
        bases = [base0 + i * pas for i in range(len(lignes))]
        y_phr = bases[-1] + 34 * k
        y_src = y_phr + len(l2) * interl2 + 30 * k
    else:
        y_src = H - bas - 34 * k
        y_phr = y_src - 40 * k - len(l2) * interl2
        bases = [y_phr - 34 * k - (len(lignes) - 1 - i) * pas for i in range(len(lignes))]
    centre = st["align"] == "centre"
    x_txt, anc_t, anc_p = (W // 2, "ms", "ma") if centre else (cote, "ls", "la")

    def couleur(i):
        n = len(lignes)
        if surligne or n == 1:
            return (255, 255, 255) if not surligne else INK
        if st["titre"] == "premiere":
            return accent if i == 0 else (255, 255, 255)
        if st["titre"] == "alterne":
            return accent if i % 2 else (255, 255, 255)
        return accent if i == n - 1 else (255, 255, 255)

    # titre surligné : un pavé de couleur derrière chaque ligne (contraste maximal)
    if surligne:
        fond_ligne = accent if accent != (255, 255, 255) else (255, 255, 255)
        for l, b in zip(lignes, bases):
            bb = d.textbbox((x_txt, b), l, font=ft, anchor=anc_t)
            d.rectangle([bb[0] - marge_x, bb[1] - 10 * k, bb[2] + marge_x, bb[3] + 12 * k], fill=fond_ligne)
    ops = [((x_txt, b), l, ft, anc_t, couleur(i)) for i, (l, b) in enumerate(zip(lignes, bases))]
    ops += [((x_txt, y_phr + i * interl2), l, ft2, anc_p, (235, 235, 245)) for i, l in enumerate(l2)]
    ombre = Image.new("L", (W, H), 0)
    do = ImageDraw.Draw(ombre)
    for j, (xy, l, fnt, anc, _) in enumerate(ops):
        if surligne and j < len(lignes):
            continue   # pas d'ombre sur un texte posé sur son pavé
        do.text((xy[0], xy[1] + 6 * k), l, font=fnt, anchor=anc, fill=200)
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, ombre.filter(ImageFilter.GaussianBlur(10 * k)))
    d = ImageDraw.Draw(img)
    if surligne:   # les pavés ont été recouverts par l'ombre : on les repose
        for l, b in zip(lignes, bases):
            bb = d.textbbox((x_txt, b), l, font=ft, anchor=anc_t)
            d.rectangle([bb[0] - marge_x, bb[1] - 10 * k, bb[2] + marge_x, bb[3] + 12 * k], fill=accent)
    for xy, l, fnt, anc, col in ops:
        d.text(xy, l, font=fnt, anchor=anc, fill=col)
    xs = (W - wsrc - 36 * k) // 2 if centre else cote
    d.rounded_rectangle([xs, y_src - 6 * k, xs + wsrc + 36 * k, y_src + 46 * k], radius=26 * k, fill=(255, 255, 255))
    d.text((xs + 18 * k, y_src + 20 * k), src, font=fsrc, fill=INK, anchor="lm")
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
    if fiches and fiches[0].get("question"):
        lignes.append(fiches[0]["question"] + " Dites-le en commentaire ‼️")
    from core.services.social import medias
    images = medias.credits([_PHOTOS.get(f.get("artiste")) for f in fiches])
    if images:
        lignes.append(images)
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
    global STYLE_GRAINE
    STYLE_GRAINE = nom
    fichiers = []
    from core.services.social import pourtoi
    nom_ok = _sans_accents(une_fiche["artiste"]).lower() in _sans_accents(une_fiche["titre"] + " " + une_fiche["une"]).lower()
    photo_une = photo(une_fiche["artiste"]) if nom_ok else None
    illustration_ia = False
    # Couvertures 2026 (19/10/2026) : couverture « actu » (photo plein cadre, mots surlignés) + une diapo de lecture.
    # Photo : un plan large VALIDÉ de l'artiste (banque artist_photos), sinon sa photo vérifiée, sinon l'illustration IA.
    from core.services.social import couverture2026 as C26
    from core.services.social import plans as PL
    plan = None
    if nom_ok:
        try:
            a_id = db.value("SELECT id FROM artists WHERE lower(name) = lower(?) ORDER BY youtube_subscribers DESC NULLS LAST LIMIT 1",
                            [une_fiche["artiste"]])
            plan = PL.photo_large(a_id) if a_id else None
        except Exception:  # noqa: BLE001
            plan = None
    # Jamais une miniature YouTube en couverture : elles montrent souvent des mannequins ou des figurants (19/10/2026)
    photo_cover = plan or (_photo_portrait(une_fiche["artiste"]) if nom_ok else None)
    if not photo_cover and not une_fiche.get("illustration_fond"):
        from core.services.social.illustration import genere
        fond_ia = genere(f"musique {une_fiche.get('rubrique', '')}", "monde")
        if fond_ia:
            une_fiche = {**une_fiche, "illustration_fond": fond_ia}
            illustration_ia = True
    etiquette = "FLASH" if est_flash else {"monde": "ACTU", "records": "RECORD", "sorties": "ÇA SORT"}.get(une_fiche["rubrique"], "ACTU")
    sources = "Sources : " + ", ".join(une_fiche["sources"][:3]) if une_fiche.get("sources") else ""
    surligne = [m for m in [une_fiche.get("accent")] if m]
    a = PI.save_jpeg(C26.actu(photo_cover, etiquette, une_fiche["titre"], surligne, sources, "feed",
                              fond_ia=une_fiche.get("illustration_fond"), couleur=ROUGE if est_flash else C26.VIOLET), PI.DIR / f"{nom}-0.jpg")
    b = PI.save_jpeg(C26.actu(photo_cover, etiquette, une_fiche["titre"], surligne, sources, "story",
                              fond_ia=une_fiche.get("illustration_fond"), couleur=ROUGE if est_flash else C26.VIOLET), PI.DIR / f"{nom}-0-916.jpg")
    fichiers.append({"file": Path(a).name, "tiktok": Path(b).name, "label": une_fiche["titre"]})
    for k, f in enumerate(fiches):
        fond = photo_cover if k == 0 else None
        a = PI.save_jpeg(C26.texte(RUBRIQUES[f["rubrique"]], f["titre"], f["resume"], sources if k == 0 else "", fond, "feed"),
                         PI.DIR / f"{nom}-{k + 1}.jpg")
        b = PI.save_jpeg(C26.texte(RUBRIQUES[f["rubrique"]], f["titre"], f["resume"], sources if k == 0 else "", fond, "story"),
                         PI.DIR / f"{nom}-{k + 1}-916.jpg")
        fichiers.append({"file": Path(a).name, "tiktok": Path(b).name, "label": f["titre"]})
    # Image 16:9 de l'article du site : l'artiste détouré sur un décor généré (pourtoi.affiche), seulement avec une
    # photo à l'identité vérifiée (photo_une : nom dans le titre + medias.choisit / notre base). Sinon, ou en cas
    # d'échec, l'article garde la couverture du post comme avant.
    article = None
    if photo_une:
        try:
            sur = "Flash" if est_flash else None
            article = Path(PI.save_jpeg(pourtoi.affiche(photo_une, une_fiche["titre"], une_fiche.get("accent"), "article",
                                                        pourtoi.ACCENTS[0] if est_flash else None, surtitre=sur,
                                                        fond=une_fiche["artiste"].split()[-1]),
                                        PI.DIR / f"{nom}-article.jpg")).name
            if not rendu_seul:
                from core import storage
                storage.publish_media_files("social", [article])
        except Exception as exc:  # noqa: BLE001
            log_write("monde", "warning", f"image d'article {une_fiche['artiste']} : {exc}")
            article = None
    legende = _legende(fiches, entete)
    if illustration_ia:
        from core.services.social.bilingue import mention_illustration
        legende = mention_illustration(legende)
    hashtags = "#CauriMonde #CauriCharts #ActuMusique #Musique #" + re.sub(r"\W", "", _sans_accents(une_fiche["artiste"]).title())[:30]
    faits = {"day": jour.isoformat(), "fiches": [{k: v for k, v in f.items() if k not in ("items", "mots", "noms", "date")} for f in fiches],
             "due": due.isoformat() if due else None}
    if illustration_ia:
        faits["illustration_ia"] = True
    if rendu_seul:
        return {"fichiers": fichiers, "legende": legende, "cover": cover, "fiches": fiches, "hashtags": hashtags, "faits": faits,
                "image_article": article}
    post = E.save_post(theme, jour.isoformat(), kicker, legende, hashtags, fichiers, faits)
    return {**post, "image_article": article} if isinstance(post, dict) else post


def archive(fiches: list, image: str | None = None, article: str | None = None) -> None:
    """Chaque info publiée devient aussi un article dans Actualités (le site comme un journal) et ne repassera plus.
    article : image 16:9 générée pour le site (pourtoi.affiche) ; à défaut, la couverture du post (image)."""
    from core.views import now_utc
    from core.services.social import medias
    image = article or image
    for f in fiches:
        credit = medias.CREDITS.get(_PHOTOS.get(f.get("artiste")) or "") if article else None
        guid = f"monde-{f['cle']}"
        if db.value("SELECT 1 FROM news WHERE external_guid = ?", [guid]):
            continue
        src = f["items"][0]
        slug = re.sub(r"[^a-z0-9]+", "-", _sans_accents(f["titre"]).lower()).strip("-")[:180] + "-" + f["cle"][:6]
        db.insert("news", {"title": f["titre"][:200], "slug": slug, "summary": (f["accroche"] or f["resume"])[:400],
                           "body": f["resume"] + "\n\nSources : " + ", ".join(f["sources"]) + "."
                                   + (f"\n\nPhoto : {credit}" if credit else ""), "category": CATEGORIE_SITE[f["rubrique"]],
                           "country_id": None, "source_name": ", ".join(f["sources"])[:120], "source_url": src["url"][:500],
                           "image_path": ("social/" + image)[:120] if image else None, "origin": "manual", "external_guid": guid,
                           "status": "published", "published_at": now_utc()})


AFRICAINS_PAR_EDITION = 3   # sur 4 (décision du 19/10/2026 : « la référence de la musique ouest-africaine »)


def tendances_youtube() -> set:
    """Artistes et titres des tendances musique YouTube du jour (NG, GH, CI, SN), en minuscules sans accents."""
    global _TENDANCES
    if _TENDANCES is None:
        _TENDANCES = set()
        try:
            import requests
            cles = [k for k in (env.get("YOUTUBE_API_KEY", ""), env.get("YOUTUBE_API_KEY_2", "")) if k]
            for pays in ("NG", "GH", "CI", "SN"):
                d = {}
                for cle in cles:   # 1 unité de quota par pays ; clé de secours si la première est épuisée
                    r = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=15, params={
                        "part": "snippet", "chart": "mostPopular", "regionCode": pays, "videoCategoryId": "10",
                        "maxResults": 30, "key": cle})
                    if r.ok:
                        d = r.json(); break
                for it in d.get("items", []):
                    sn = it.get("snippet", {})
                    _TENDANCES.add(_sans_accents(sn.get("channelTitle", "")).lower().replace(" - topic", "").replace("vevo", "").strip())
                    _TENDANCES.add(_sans_accents(sn.get("title", "")).lower())
        except Exception as exc:  # noqa: BLE001
            log_write("monde", "warning", f"tendances YouTube : {exc}")
    return _TENDANCES


_TENDANCES = None


def buzz(f: dict) -> bool:
    """Un vrai signal de buzz : au moins 2 médias, ou l'artiste est dans les tendances YouTube du jour, ou c'est
    un de nos propres chiffres (records, caps de streams)."""
    if len(f.get("sources") or []) >= 2 or f.get("rubrique") == "records" and f.get("chiffre"):
        return True
    a = _sans_accents(f.get("artiste") or "").lower().strip()
    return bool(a) and any(a == t or (len(a) >= 4 and a in t) for t in tendances_youtube())


def deja_vu_aujourdhui(artiste: str) -> bool:
    """L'artiste a-t-il déjà eu son info dans les 20 dernières heures (édition ou flash) ? Jamais deux fois par jour."""
    a = (artiste or "").strip()
    if len(a) < 3:
        return False
    return bool(db.value("""SELECT 1 FROM news WHERE external_guid LIKE 'monde-%' AND published_at >= NOW() - INTERVAL '20 hours'
                            AND title ILIKE ?""", [f"%{a}%"]))


def selection(tries: list, n: int) -> list:
    """Les n infos de l'édition : au moins AFRICAINS_PAR_EDITION africaines quand il y en a (les meilleures notes),
    le reste aux meilleures infos tout court ; les infos avec un signal de buzz passent avant les autres."""
    tries = sorted(tries, key=lambda f: not buzz(f))           # tri stable : la note décide à signal égal
    afr = [f for f in tries if africain(f) or f.get("afrique")][:max(AFRICAINS_PAR_EDITION, n - 1)]
    choix = afr[:AFRICAINS_PAR_EDITION]
    for f in tries:
        if len(choix) >= n:
            break
        if f not in choix:
            choix.append(f)
    return sorted(choix, key=lambda f: tries.index(f))


def au_moins_un_africain(tries: list, n: int) -> list:
    """Les n premières infos (déjà triées), dont au moins une sur un artiste africain quand il y en a une : elle prend
    la dernière place (jamais celle de l'info du moment)."""
    choix = tries[:n]
    if not choix or any(africain(f) for f in choix):
        return choix
    afr = next((f for f in tries[n:] if africain(f)), None)
    return choix[:-1] + [afr] if afr else choix


def edition(jour: date, quand: str, rendu_seul: bool = False) -> dict | None:
    """Édition de 8 h (« monde ») ou de 20 h (« records » + « sorties ») : les infos les plus reprises, jamais déjà publiées."""
    if not rendu_seul and db.value("SELECT 1 FROM social_posts WHERE slot_date = ? AND (theme = ? OR theme LIKE ?)",
                                   [jour.isoformat(), f"monde-{quand}", f"monde-{quand}-%"]):
        return None   # édition déjà faite aujourd'hui (une seule par créneau)
    histoires = [h for h in regroupe(collecte(30 if quand == "matin" else 24)) if not deja_publie(h["cle"])]
    # les 24 plus reprises, plus jusqu'à 6 vues par un média africain (sinon les grands médias mondiaux prennent toute la place)
    histoires = histoires[:24] + [h for h in histoires[24:] if h.get("afrique")][:6]
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
    for f in tries:   # une seule info par artiste et par édition, et jamais un artiste déjà traité dans la journée
        a = _sans_accents(f["artiste"]).lower()
        if a and (a in vus_artistes or deja_vu_aujourdhui(f["artiste"])):
            continue
        vus_artistes.add(a); choix.append(f)
    choix = selection(choix, PAR_EDITION)
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
            archive([f], posts[-1].get("image_square"), posts[-1].get("image_article"))
    return posts[0] if rendu_seul else {"title": f"{len(posts)} posts Cauri Monde ({quand})", "posts": posts}


def flash(rendu_seul: bool = False, forcer: bool = False) -> dict | None:
    """L'info choc des 3 dernières heures, reprise par ≥ 2 médias, jamais publiée : un post « FLASH » immédiat."""
    histoires = [h for h in regroupe(collecte(4 if not forcer else 30)) if (confirme(h) or forcer) and not deja_publie(h["cle"])]
    if not histoires:
        return None
    fiches = sorted(redige(histoires[:8]), key=lambda f: f["choc"], reverse=True)
    f = next((x for x in fiches if (x["choc"] >= SEUIL_FLASH or forcer) and not deja_vu_aujourdhui(x.get("artiste"))), None)
    if not f:
        return None
    maintenant = datetime.now(timezone.utc)
    kicker = f"FLASH · {maintenant:%d/%m · %H:%M} GMT"
    entete = f"🚨 FLASH · {f['titre']}"
    post = construit([f], maintenant.date(), f"flash-{maintenant:%H%M}", kicker, entete,
                     "Info confirmée par " + " et ".join(f["sources"][:3]) + ". Suivez Cauri Charts pour ne rien manquer.", rendu_seul)
    if not rendu_seul:
        archive([f], post.get("image_square"), post.get("image_article"))
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
    grands = {f["name"] for f in FEEDS if f["poids"] >= 2}
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
CHERCHES = list(dict.fromkeys(STARS + ["Tiakola", "Damso", "SDM", "Werenoi", "Gazo", "Himra", "Didi B", "Josey", "Innoss'B", "Dadju", "Tayc",
                    "Joé Dwèt Filé", "Shatta Wale", "Stonebwoy", "Sarkodie", "KiDi", "Omah Lay", "CKay", "Fireboy DML",
                    "Kizz Daniel", "Oxlade", "Seyi Vibez", "Olamide", "Victony", "Shallipopi", "Toofan", "Magic System",
                    "Booba", "PNL", "Orelsan", "Angèle", "Soolking", "Naps", "Zola"]))   # sans doublons
AFRICAINS = {_sans_accents(n).lower() for n in [
    "Ferre Gola", "Koffi Olomide", "Héritier Watanabe", "Diamond Platnumz", "Black Coffee", "Uncle Waffles",
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
    for r in db.all("""SELECT id, facts FROM social_posts WHERE (theme LIKE 'monde-%' OR theme LIKE 'format-%') AND slot_date >= CURRENT_DATE - 1
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
