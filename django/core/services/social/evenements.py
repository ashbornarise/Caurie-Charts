"""Veille et formats à blanc pour les grands événements ouest-africains."""
import html
import re
import tempfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from core.services.news import http_get, parse_feed, og_image
from core.services.platforms import log_write

TERMES = re.compile(r"gala|festival|concert|awards?|cérémonie|ceremony|remise de prix|grand prix|sacre|coronation", re.I)
PAYS = ["Bénin", "Burkina Faso", "Cap-Vert", "Côte d'Ivoire", "Gambie", "Ghana", "Guinée", "Guinée-Bissau",
        "Liberia", "Mali", "Mauritanie", "Niger", "Nigeria", "Sénégal", "Sierra Leone", "Togo"]
LIEUX = PAYS + ["Abidjan", "Cotonou", "Ouagadougou", "Praia", "Banjul", "Accra", "Conakry", "Bissau", "Monrovia",
                "Bamako", "Nouakchott", "Niamey", "Lagos", "Abuja", "Dakar", "Freetown", "Lomé", "Lome",
                "Dominique Ouattara", "Children of Africa"]
VIDES = set("the and for with from dans pour avec des les une aux sur this that ceremony gala festival concert awards award de du la le et en au of in on at by to a an".split())


def _date(v):
    if isinstance(v, datetime):
        d = v
    else:
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def _actualite_google():
    """Deux recherches RSS gratuites couvrent les mots-clés dans les pays ciblés."""
    from urllib.parse import quote_plus
    result = []
    pays = ' OR '.join(f'"{p}"' for p in PAYS)
    termes_fr = 'gala OR festival OR concert OR awards OR cérémonie OR "remise de prix" OR sacre'
    termes_en = 'gala OR festival OR concert OR awards OR ceremony OR coronation'
    for hl, gl, ceid, termes in (("fr", "FR", "FR:fr", termes_fr), ("en", "NG", "NG:en", termes_en)):
        url = f"https://news.google.com/rss/search?hl={hl}&gl={gl}&ceid={ceid}&q=" + quote_plus(f"({termes}) ({pays}) when:7d")
        try:
            for it in parse_feed(http_get(url) or ""):
                titre = it["title"]
                if " - " in titre:
                    titre, source = titre.rsplit(" - ", 1)
                else:
                    source = "Google Actualités"
                result.append({**it, "title": html.unescape(titre), "source": source.strip(), "poids": 2})
        except Exception as exc:  # noqa: BLE001
            log_write("evenements", "warning", f"Google Actualités {hl} : {exc}")
    return result


def _mots(titre):
    import unicodedata
    t = unicodedata.normalize("NFKD", titre.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z0-9]{3,}", t) if w not in VIDES}


def _nom_evenement(titres):
    """Retient le nom propre placé autour du terme d'événement dans les titres."""
    choix = []
    for titre in titres:
        for m in TERMES.finditer(titre):
            # Un nom propre adjacent distingue l'événement nommé d'un simple article parlant de concert.
            apres = titre[m.end():m.end() + 85].strip(" :-–,«»\"'")
            motif = r"[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’-]*(?:\s+(?:(?:of|the|de|du|des|la|le|les|d')\s+)?[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’-]*){1,5}"
            propre = re.match(rf"({motif})", apres)
            avant = titre[max(0, titre.rfind(".", 0, m.start()) + 1):m.start()].strip(" :-–,«»\"'")
            prefixe = list(re.finditer(motif, avant))
            prefixe = prefixe[-1].group(0) if prefixe else ""
            cand = (m.group() + " " + propre.group(1).strip()) if propre else (prefixe + " " + m.group() if prefixe else "")
            cand = re.sub(r"\s+", " ", cand).strip()
            mots = cand.split()
            if len(mots) > 7:
                cand = " ".join(mots[:7])
            if len(mots) >= 2:
                choix.append(cand)
    if not choix:
        return ""
    return max(set(choix), key=lambda x: (choix.count(x), min(len(x.split()), 8), len(x)))


def regroupe(items):
    """Événements vus dans au moins deux médias, regroupés sur les noms présents aux titres."""
    lots = []
    for it in sorted(items, key=lambda x: _date(x.get("date") or x.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        titre = it.get("title") or ""
        d = _date(it.get("date") or it.get("published_at"))
        if not d or d < datetime.now(timezone.utc) - timedelta(days=7) or not TERMES.search(titre):
            continue
        nom = _nom_evenement([titre])
        if not nom:
            continue
        mots = _mots(nom)
        for lot in lots:
            communs = mots & lot["mots"]
            if len(communs) >= 2 and len(communs) / max(1, len(mots | lot["mots"])) >= .5:
                lot["items"].append({**it, "date": d})
                lot["mots"] |= mots
                lot["noms"].append(nom)
                break
        else:
            lots.append({"items": [{**it, "date": d}], "mots": mots, "noms": [nom]})
    out = []
    for lot in lots:
        sources = sorted({x.get("source", "") for x in lot["items"] if x.get("source")})
        if len(sources) < 2:
            continue
        nom = max(set(lot["noms"]), key=lot["noms"].count)
        out.append({"nom": nom, "items": lot["items"], "sources": sources,
                    "importance": sum({x.get("source"): int(x.get("poids", 1)) for x in lot["items"]}.values()),
                    "date": max(x["date"] for x in lot["items"])})
    return sorted(out, key=lambda x: (x["importance"], len(x["sources"]), x["date"]), reverse=True)


def collecte():
    """Articles RSS du service Monde et Google Actualités sur les sept derniers jours."""
    from core.services.social import monde
    debut = datetime.now(timezone.utc) - timedelta(days=7)
    items = list(monde.collecte(168)) + _actualite_google()
    valides = []
    for it in items:
        d = _date(it.get("date") or it.get("published_at"))
        texte = f"{it.get('title') or ''} {it.get('summary') or ''}"
        local = any(re.search(rf"(?<!\w){re.escape(l)}(?!\w)", texte, re.I) for l in LIEUX)
        if d and debut <= d <= datetime.now(timezone.utc) and TERMES.search(it.get("title") or "") and local:
            valides.append({**it, "date": d})
    return regroupe(valides)


def _image_article(it):
    """Télécharge l'og:image d'un article et vérifie son décodage avant réutilisation."""
    try:
        url = og_image(http_get(it.get("url", "")) or "")
        if not url:
            return None
        raw = http_get(url, binary=True)
        im = Image.open(BytesIO(raw))
        im.load()
        if im.width < 320 or im.height < 220:
            return None
        return im.convert("RGB"), url
    except Exception:  # noqa: BLE001
        return None


def _credit_image(im, source):
    im = im.copy()
    d = ImageDraw.Draw(im)
    texte = f"Photo : {source}"
    try:
        font = ImageFont.truetype("arial.ttf", max(16, im.width // 48))
    except OSError:
        font = ImageFont.load_default()
    boite = d.textbbox((0, 0), texte, font=font)
    y = im.height - (boite[3] - boite[1]) - 24
    d.rectangle((0, y - 12, im.width, im.height), fill=(0, 0, 0))
    d.text((16, y), texte, font=font, fill=(255, 255, 255))
    return im


def titre_evenement(e):
    nom = e["nom"].split()[:5]
    return " ".join(["Les", "images", "de", "l'événement", *nom])


def fabrique_photos(e, dossier, prefix="codex-evenement", limite=6, minimum=3):
    """Construit couverture Pour toi et 3 à 6 images créditées, sans créer de post."""
    from core.services.social import pourtoi
    from core.services.social.image import save_jpeg
    from pathlib import Path
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    titre = titre_evenement(e)
    resultats = []
    vus = set()
    for it in e["items"]:
        source = it.get("source") or "Source de l'article"
        trouve = _image_article(it)
        if not trouve or trouve[1] in vus:
            continue
        vus.add(trouve[1])
        resultats.append((_credit_image(trouve[0], source), source, it))
        if len(resultats) == limite:
            break
    if len(resultats) < minimum:
        return None
    couverture = pourtoi.une(resultats[0][0], titre, fmt="feed", surtitre="Retour en images")
    path = dossier / f"{prefix}-couverture.jpg"
    save_jpeg(couverture, path)
    sorties = [str(path)]
    for i, (im, _source, _it) in enumerate(resultats, 1):
        p = dossier / f"{prefix}-photo-{i}.jpg"
        save_jpeg(im, p)
        sorties.append(str(p))
    return {"couverture": sorties[0], "photos": sorties[1:], "titre": titre}


def legende(e):
    faits = []
    for it in e["items"][:4]:
        fait = (it.get("summary") or it.get("title") or "").strip()
        if fait and fait not in faits:
            faits.append(fait)
    question = "Quel moment de cet événement vous a le plus marqué ?"
    sources = ", ".join(e["sources"])
    return f"{' '.join(faits)}\n\nSources : {sources}.\n\n{question}"


def videos(e):
    """Recherche YouTube gratuite : ne consomme rien sous 2 000 unités restantes."""
    from core.services.platforms import clients
    yt = clients()["youtube"]
    if not yt.is_available() or yt.remaining_quota() < 2000:
        return []
    debut = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    q = e["nom"]
    data = yt._get("search", {"part": "snippet", "type": "video", "maxResults": 10, "order": "viewCount",
                              "publishedAfter": debut, "q": q}, 100)
    return [{"id": x.get("id", {}).get("videoId"), "titre": x.get("snippet", {}).get("title", ""),
             "chaine": x.get("snippet", {}).get("channelTitle", ""), "date": x.get("snippet", {}).get("publishedAt", "")}
            for x in data.get("items", []) if x.get("id", {}).get("videoId")]


def moment_video(e, out, candidats=None):
    """Réutilise la transcription, le contrôle des bornes et le montage 9:16 avec son d'Interviews."""
    from core.services.social import interviews as I
    try:
        candidats = candidats if candidats is not None else videos(e)
    except Exception as exc:  # noqa: BLE001
        log_write("evenements", "warning", f"recherche vidéo : {exc}")
        return None
    for video in candidats:
        with tempfile.TemporaryDirectory(prefix="cauri-evenement-") as tmp:
            st = I.sous_titres(video["id"], tmp)
            if not st:
                continue
            mots, _langue = st
            phrases = I.lignes(mots)
            choix = _choisit_moment(e["nom"], video, phrases)
            if not choix:
                continue
            src = I.telecharge_passage(video["id"], choix["debut"], choix["fin"], tmp)
            if not src:
                continue
            credit = f"Extrait : {video['chaine']} (YouTube)"
            if I.monte(src, choix["fin"] - choix["debut"], choix["accroche"], e["nom"], credit,
                       I.morceaux(mots, choix["debut"], choix["fin"]), out, tmp, label="MOMENTS FORTS"):
                return {**video, **choix, "source": f"https://youtube.com/watch?v={video['id']}", "credit": credit}
    return None


def _choisit_moment(nom, video, phrases):
    """L'IA propose un passage événementiel, puis les mêmes contrôles bornent sa transcription."""
    import json
    from core.services import ai
    client = ai.make()
    if not client or not phrases:
        return None
    lignes = "\n".join(f"[{p['debut']:.1f}] {p['texte']}" for p in phrases[:900])
    consigne = (f"Transcription réelle d'une vidéo de l'événement {nom}, publiée par {video['chaine']} : {video['titre']}.\n"
                "Choisis le passage de 25 à 50 secondes le plus fort montrant un moment marquant de l'événement. "
                "N'invente aucun fait. Rends uniquement ce JSON : {\"debut\": seconde, \"fin\": seconde, "
                "\"accroche\": 5 à 10 mots en français fidèles à la transcription, \"resume\": résumé fidèle, "
                "\"question\": question courte}. Si aucun passage ne convient : {\"aucun\": true}.\n" + lignes)
    try:
        r = client.ask("Tu sélectionnes des moments forts uniquement à partir de transcriptions réelles.", consigne, max_tokens=1800)
        t = r["text"]
        choix = json.loads(t[t.find("{"):t.rfind("}") + 1])
        if choix.get("aucun"):
            return None
        return I.verifie(choix, phrases)
    except Exception as exc:  # noqa: BLE001
        log_write("evenements", "warning", f"choix du passage : {exc}")
        return None


def du_jour(jour):
    """Produit au plus un événement, prêt à examiner, sans enregistrer ni publier de post."""
    evenements = collecte()
    return evenements[0] if evenements else None
