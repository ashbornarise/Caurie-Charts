"""Bibliothèque Cauri Charts (18/11/2026) : tout ce que Cauri Charts publie, au même endroit, trié par catégorie, pays,
artiste et date — posts (visuels, carrousels, vidéos), épisodes « Cauri raconte ». Vitrine publique et base du tableau de
bord investisseurs. Seuls les contenus validés et déjà sortis sont montrés (jamais les brouillons)."""
import json
import re
from datetime import date

from core import db, storage

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

# (code, libellé, ordre d'affichage)
CATEGORIES = {
    "raconte": ("Cauri raconte", 0),
    "studio": ("Vidéos du Studio", 1),
    "classements": ("Classements et données", 2),
    "portraits": ("Portraits", 3),
    "magazine": ("Formats magazine", 4),
    "monde": ("Cauri Monde", 5),
    "flash": ("Flashs actu", 6),
    "autres": ("Annonces", 7),
}

DONNEES = {"top", "classement", "hebdo", "numeros_un", "weekend", "matin", "frontieres", "featurings", "sorties", "revelations",
           "chiffres", "clips_progression", "clips_vues", "clips_likes", "nouveaux_clips", "ecoutes_monde", "shazam", "deezer",
           "apple_music", "youtube_tendances", "abonnes_youtube", "fans_deezer", "format-top10", "format-officiel", "format-top-spotify",
           "format-top-vote-100", "format-albums"}
PORTRAITS = {"portrait", "artiste", "format-qui-est"}


def categorie(theme: str) -> str:
    t = (theme or "").lower()
    if t.startswith("monde"):
        return "monde"
    if t.startswith("flash"):
        return "flash"
    if t.startswith(("format-studio", "format-clip", "format-paroles")):
        return "studio"
    if t in PORTRAITS:
        return "portraits"
    if t in DONNEES or t.startswith("top_"):
        return "classements"
    if t.startswith("format-"):
        return "magazine"
    return "autres"


def date_fr(d) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def _media(nom: str | None) -> str:
    if not nom:
        return ""
    if str(nom).startswith("http"):
        return str(nom)
    return storage.blob_public_url().rstrip("/") + "/media/social/" + str(nom).rsplit("/", 1)[-1]


def _legende(texte: str) -> str:
    """La partie française de la légende (avant l'anglais et les hashtags), sans lignes vides en série."""
    t = re.split(r"\n\s*🇬🇧|\n\s*#", texte or "", maxsplit=1)[0]
    return re.sub(r"\n{3,}", "\n\n", t).strip()[:700]


def _titre_post(titre: str, legende: str) -> str:
    """Cauri Monde et Flashs : « Cauri Monde · 18/11 · 21 h 30 » ne dit rien -> le titre de l'actu (« ▪️ … » de la légende)."""
    titre = (titre or "").strip()
    if re.match(r"^(Cauri Monde|FLASH|Cauri Matin|Cauri Hebdo)\b.*·", titre):
        m = re.search(r"^▪️\s*(.+)$", legende or "", re.M)
        if m:
            t = m.group(1).strip()
            return _phrase(t, legende) if t.isupper() else t
    return titre or "Cauri Charts"


PETITS_MOTS = {"le", "la", "les", "de", "des", "du", "un", "une", "et", "par", "sur", "en", "au", "aux", "pour", "dans", "avec",
               "son", "sa", "ses", "ce", "cette", "il", "elle", "selon", "après", "avant", "lors", "à", "a"}


def _phrase(t: str, texte: str) -> str:
    """« DAVIDO NOMMÉ ROI … D'OSUN » -> « Davido nommé roi … d'Osun » : un mot garde sa majuscule s'il l'a dans le texte."""
    propres = set(re.findall(r"\b[A-ZÀ-Ý][a-zà-ÿ]+", re.sub(r"^.*\n", "", texte or "", count=2)))
    def mot(w: str, premier: bool) -> str:
        base = w.lower()
        for pre in ("d'", "l'", "d’", "l’"):
            if base.startswith(pre) and base[len(pre):].capitalize() in propres:
                return pre + base[len(pre):].capitalize()
        if premier:
            return base.capitalize()
        return base.capitalize() if base.capitalize() in propres and base not in PETITS_MOTS else base
    return " ".join(mot(w, i == 0) for i, w in enumerate(t.split()))


def _source(legende: str) -> str:
    """« 🎥 Source : Himra sur Facebook » -> « Himra » (vidéos du Studio)."""
    m = re.search(r"Source\s*:\s*@?(.+?)\s+sur\s+\w+", legende or "")
    return m.group(1).strip()[:60] if m else ""


def _faits(p: dict) -> dict:
    try:
        f = json.loads(p.get("facts") or "{}")
        return f if isinstance(f, dict) else {}
    except ValueError:
        return {}


_PRESENTS = {"t": 0.0, "noms": None}


def presents() -> set | None:
    """Noms des fichiers encore dans le stockage (media/social/), gardés 10 min. Jusqu'au 18/11/2026, le ménage de nuit
    effaçait les médias de plus de 7 jours : ces anciens posts n'ont plus d'image et ne sont pas montrés. None : pas de Blob."""
    import time
    if not storage.blob_token():
        return None
    if _PRESENTS["noms"] is None or time.time() - _PRESENTS["t"] > 600:
        _PRESENTS["noms"] = {b["pathname"].rsplit("/", 1)[-1] for b in storage.blob_list("media/social/")}
        _PRESENTS["t"] = time.time()
    return _PRESENTS["noms"]


def _titre_episode(t: dict) -> str:
    """« COMMENT » « SHATTA WALE » « EST TOMBÉ… » -> « Comment Shatta Wale est tombé… » (le nom garde ses majuscules)."""
    haut, nom, bas = (str(t.get(k) or "").strip() for k in ("haut", "nom", "bas"))
    morceaux = [haut.capitalize() if haut.isupper() else haut, nom.title() if nom.isupper() else nom,
                bas.lower() if bas.isupper() else bas]
    return " ".join(m for m in morceaux if m)


def elements() -> list:
    """Tous les contenus publiés, du plus récent au plus ancien."""
    from core.services.social.generator import _slide_files
    noms = {a["id"]: a["name"] for a in db.all("SELECT id, name FROM artists")}
    pays = {c["code"]: c["name_fr"] for c in db.all("SELECT code, name_fr FROM countries")}
    out = []
    for p in db.all("""SELECT id, slot_date, theme, title, caption, facts, image_square, image_story, carousel, video FROM social_posts
                       WHERE status IN ('approved', 'published') AND slot_date <= CURRENT_DATE ORDER BY slot_date DESC, id DESC"""):
        f = _faits(p)
        slides = [s for s in _slide_files(p) if not re.search(r"-tt\.|-916\.", s)]
        code_pays = (p["theme"][4:6].upper() if (p["theme"] or "").startswith("top_") else "") or str(f.get("pays") or "").upper()[:2]
        artiste = f.get("artiste") if isinstance(f.get("artiste"), str) else noms.get(f.get("artist_id")) or ""
        artiste = artiste or (_source(p["caption"]) if categorie(p["theme"]) == "studio" else "")
        sorte = "video" if p.get("video") else ("carrousel" if len(slides) > 1 else "visuel")
        out.append({
            "id": f"p{p['id']}", "cat": categorie(p["theme"]), "type": sorte,
            "titre": _titre_post(p["title"], p["caption"]), "date": str(p["slot_date"]), "date_fr": date_fr(p["slot_date"]),
            "image": _media(p["image_square"] or (slides[0] if slides else "")), "video": _media(p.get("video")),
            "pages": [_media(s) for s in slides] if sorte == "carrousel" else [],
            "pays": code_pays, "pays_nom": pays.get(code_pays, ""), "artiste": artiste[:60], "legende": _legende(p["caption"]),
        })
    # épisodes « Cauri raconte » fabriqués dans le Studio
    for j in db.all("""SELECT id, params, video, vignette, cree_le FROM studio_jobs
                       WHERE statut IN ('pret', 'envoye') AND video IS NOT NULL AND params LIKE '%"type": "raconte"%' ORDER BY id DESC"""):
        try:
            pr = j["params"] if isinstance(j["params"], dict) else json.loads(j["params"] or "{}")
        except ValueError:
            continue
        t = (pr.get("recit") or {}).get("titre") or {}
        titre = _titre_episode(t) or pr.get("accroche") or "Cauri raconte"
        out.append({
            "id": f"r{j['id']}", "cat": "raconte", "type": "video", "titre": titre,
            "date": str(j["cree_le"])[:10], "date_fr": date_fr(str(j["cree_le"])[:10]),
            "image": _media(j.get("vignette")), "video": _media(j["video"]), "pages": [],
            "pays": "", "pays_nom": "", "artiste": pr.get("artiste") or "", "legende": _legende(pr.get("legende_fr") or ""),
        })
    out.sort(key=lambda e: (e["date"], e["id"]), reverse=True)
    # un même épisode refabriqué : on ne garde que la dernière version ; un média effacé : le contenu n'est pas montré
    ici = presents()
    nom = lambda u: (u or "").rsplit("/", 1)[-1]
    vus, propre = set(), []
    for e in out:
        cle = (e["cat"], e["artiste"]) if e["cat"] == "raconte" and e["artiste"] else e["id"]
        if ici is not None:
            if e["video"] and nom(e["video"]) not in ici:
                e["video"] = ""
                e["type"] = "visuel"
            e["pages"] = [x for x in e["pages"] if nom(x) in ici]
            if nom(e["image"]) not in ici:
                e["image"] = e["pages"][0] if e["pages"] else ""
            if not e["image"] and not e["video"]:
                continue
        if cle not in vus:
            vus.add(cle)
            e["cat_nom"] = CATEGORIES[e["cat"]][0]
            propre.append(e)
    return propre


def resume(els: list) -> dict:
    """Les chiffres de la vitrine (et du dossier investisseurs)."""
    cats = {}
    for e in els:
        cats[e["cat"]] = cats.get(e["cat"], 0) + 1
    dates = sorted(e["date"] for e in els)
    return {
        "total": len(els), "videos": sum(1 for e in els if e["type"] == "video"),
        "visuels": sum(1 for e in els if e["type"] != "video"),
        "pays": len({e["pays"] for e in els if e["pays"]}), "artistes": len({e["artiste"] for e in els if e["artiste"]}),
        "depuis": date_fr(dates[0]) if dates else "",
        "categories": [{"code": c, "nom": CATEGORIES[c][0], "n": n} for c, n in sorted(cats.items(), key=lambda x: CATEGORIES[x[0]][1])],
    }
