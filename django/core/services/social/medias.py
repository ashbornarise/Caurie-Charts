"""Pôle média : des images qui changent chaque jour pour les couvertures, toujours avec leur source.

Constat du 16/10/2026 : la même photo d'artiste revenait d'un post à l'autre et n'intriguait plus. Pour un artiste, on
rassemble plusieurs images réelles, puis on prend celle qui n'a pas servi depuis 10 jours :
  1. plans de clips officiels : image d'aperçu YouTube (1280 × 720) des clips de l'artiste — notre base d'abord,
     sinon une recherche YouTube (stars mondiales), mise en cache pour la journée ;
  2. photos de scène et de concert sous licence libre (Openverse : Wikimedia Commons, Flickr…), photographe crédité ;
  3. la photo de l'artiste de notre base (ou Deezer), en dernier recours.
Le crédit de chaque image est gardé (CREDITS[url]) et repris dans la légende du post."""
import hashlib
import json
import re
from urllib.parse import quote

from core import db
from core.services.platforms import log_write

CREDITS: dict = {}
MUSIQUE = re.compile(r"concert|live|stage|scene|perform|singer|chanteu|rapper|rappeur|musician|musicien|festival|show|tour|"
                     r"music|musique|gig|artist|artiste|album|award|grammy|headies|afrima|mic\b|microphone", re.I)
# Nom d'un seul mot (« Amadeus », « Josey ») : trop d'homonymes. Il faut en plus un indice ouest-africain dans le titre
# ou les mots-clés de la photo (« Amadeus » donnait une chanteuse européenne dans une vidéo maison, 19/10/2026)
AFRIQUE = re.compile(r"afro|africa|afrique|nigeria|naija|lagos|abuja|ghana|accra|kumasi|togo|lome|benin|cotonou|"
                     r"ivoire|ivory|abidjan|senegal|dakar|mali|bamako|burkina|ouaga|niger|guinea|guinee|conakry|"
                     r"cameroun|cameroon|highlife|amapiano|coupe.?decale|mbalax|headies|afrima|afronation|felabration", re.I)
_CACHE: dict = {}


def _sans_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def _http(url: str) -> str:
    from core.services.news import http_get
    return http_get(url) or ""


def plans_de_clips(artiste: str, n: int = 6) -> list[dict]:
    """Images d'aperçu des clips officiels de l'artiste (les plus récents d'abord)."""
    rows = db.all("""SELECT tpi.external_id, t.title FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id
                     JOIN artists a ON a.id = t.artist_id
                     WHERE LOWER(a.name) = LOWER(?) AND tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1
                     ORDER BY tpi.published_at DESC NULLS LAST LIMIT ?""", [artiste, n])
    out = [{"url": f"https://i.ytimg.com/vi/{r['external_id']}/maxresdefault.jpg", "credit": f"Image : clip officiel « {r['title']} » (YouTube)",
            "type": "clip"} for r in rows]
    if out:
        return out
    # Star absente de notre base : recherche YouTube (100 unités de quota), une fois par jour et par artiste
    cle = "yt:" + artiste.lower()
    if cle not in _CACHE:
        _CACHE[cle] = []
        try:
            from core.services.platforms import clients
            yt = clients()["youtube"]
            if yt.is_available() and yt.remaining_quota() > 2000:
                for v in yt.search_track(f"{artiste} official music video")[:n]:
                    titre = (v.get("title") or "")
                    if _sans_accents(artiste) in _sans_accents(titre) and "official" in titre.lower():
                        _CACHE[cle].append({"url": f"https://i.ytimg.com/vi/{v['external_id']}/maxresdefault.jpg",
                                            "credit": f"Image : clip officiel « {titre[:70]} » (YouTube)", "type": "clip"})
        except Exception as exc:  # noqa: BLE001 — sans YouTube, les autres sources suffisent
            log_write("monde", "warning", f"plans de clips {artiste} : {exc}")
    return _CACHE[cle]


def scenes_libres(artiste: str, n: int = 8) -> list[dict]:
    """Photos de scène sous licence libre (Openverse), où l'artiste est bien le sujet (son nom dans le titre)."""
    cle = "ov:" + artiste.lower()
    if cle in _CACHE:
        return _CACHE[cle]
    out = []
    try:
        d = json.loads(_http(f"https://api.openverse.org/v1/images/?q={quote(artiste)}&page_size=20&mature=false") or "{}")
        nom = _sans_accents(artiste)
        for r in d.get("results") or []:
            titre = _sans_accents(r.get("title") or "")
            # Le nom comme mot entier, et un contexte musical : « Josey » donnait un joueur de football (Josey Jewell, 17/10)
            if not re.search(rf"\b{re.escape(nom)}\b", titre) or f"at {nom}" in titre or f"for {nom}" in titre:
                continue
            contexte = titre + " " + _sans_accents(" ".join(t.get("name", "") for t in (r.get("tags") or [])))
            if not MUSIQUE.search(contexte):
                continue
            if " " not in nom.strip() and not AFRIQUE.search(contexte):
                continue
            if r.get("width") and (r["width"] < 900 or (r.get("height") or 0) < 700):   # taille parfois absente
                continue
            # Licences « pas d'usage commercial » (NC) ou « pas de modification » (ND) : exclues — on est un média et on
            # pose du texte sur l'image
            if any(k in (r.get("license") or "").lower() for k in ("nc", "nd")):
                continue
            lic = f"CC {(r.get('license') or '').upper()} {r.get('license_version') or ''}".strip()
            out.append({"url": r["url"], "type": "scene",
                        "credit": f"Photo : {r.get('creator') or 'auteur inconnu'}, {lic} ({r.get('source') or 'Openverse'})"})
            if len(out) >= n:
                break
    except Exception as exc:  # noqa: BLE001
        log_write("monde", "warning", f"photos libres {artiste} : {exc}")
    _CACHE[cle] = out
    return out


# Chaînes officielles de festivals et d'organisateurs dont les vidéos sous licence libre sont fiables (en plus des
# chaînes des artistes eux-mêmes) — les comptes de « reposts » cochent parfois « licence libre » sans en avoir le droit
CHAINES_CONCERT = ["One Africa Music Fest"]


def videos_concert(artiste: str, n: int = 3) -> list[dict]:
    """Vidéos de concert de l'artiste sous licence Creative Commons (YouTube), publiées par une chaîne officielle :
    la sienne ou celle d'un festival connu. Une recherche (100 unités de quota) par artiste et par exécution."""
    cle = "cc:" + artiste.lower()
    if cle in _CACHE:
        return _CACHE[cle]
    _CACHE[cle] = []
    try:
        from core import conf
        from core.services.platforms import clients
        yt = clients()["youtube"]
        if not yt.is_available() or yt.remaining_quota() < 1500:
            return []
        chaines = {_sans_accents(c) for c in (conf.get("social.concert.chaines") or CHAINES_CONCERT)}
        d = yt._get("search", {"part": "snippet", "type": "video", "maxResults": 15, "videoLicense": "creativeCommon",
                               "order": "viewCount", "q": f"{artiste} live performance"}, 100)
        nom = _sans_accents(artiste)
        for it in d.get("items", []):
            sn, vid = it["snippet"], it["id"].get("videoId")
            titre, chaine = _sans_accents(sn.get("title", "")), sn.get("channelTitle", "")
            # Chaîne officielle : celle d'un festival reconnu, ou exactement le nom de l'artiste (+ officiel, VEVO, music, TV) —
            # « Jai'Len Josey » n'est pas Josey (17/10/2026)
            ch = re.sub(r"\b(officiel|official|vevo|music|musique|tv)\b", "", _sans_accents(chaine)).replace(" ", "")
            officielle = _sans_accents(chaine) in chaines or ch == nom.replace(" ", "")
            if vid and re.search(rf"\b{re.escape(nom)}\b", titre) and officielle:
                _CACHE[cle].append({"id": vid, "titre": sn.get("title", ""), "chaine": chaine,
                                    "credit": f"Vidéo : {chaine}, licence CC BY (YouTube)"})
                if len(_CACHE[cle]) >= n:
                    break
    except Exception as exc:  # noqa: BLE001
        log_write("monde", "warning", f"vidéos de concert {artiste} : {exc}")
    return _CACHE[cle]


def _cle(url: str) -> str:
    return "i" + hashlib.md5(url.encode()).hexdigest()[:15]   # 16 caractères : taille de monde_vus.cle


_LISIBLES: dict = {}


def lisible(url: str) -> bool:
    """L'image se télécharge et s'ouvre vraiment (certains sites, comme Flickr, refusent les robots)."""
    if url not in _LISIBLES:
        try:
            from io import BytesIO
            from PIL import Image
            from core.services.news import http_get
            Image.open(BytesIO(http_get(url, binary=True))).verify()
            _LISIBLES[url] = True
        except Exception:  # noqa: BLE001
            _LISIBLES[url] = False
    return _LISIBLES[url]


def choisit(artiste: str, secours: str | None = None, alterne: int = 0) -> str | None:
    """Une image de l'artiste pas encore utilisée ces 10 jours ; alterne plans de clips et photos de scène."""
    from core.services.social import monde as M
    clips, scenes = plans_de_clips(artiste), scenes_libres(artiste)
    ordre = (clips + scenes) if alterne % 2 == 0 else (scenes + clips)
    for c in ordre:
        if not M.vu(_cle(c["url"])) and lisible(c["url"]):
            M.marque_vu([_cle(c["url"])])
            CREDITS[c["url"]] = c["credit"]
            return c["url"]
    deja = [c for c in ordre if lisible(c["url"])]
    if deja:   # tout a déjà servi : on reprend une image lisible plutôt que rien
        CREDITS[deja[0]["url"]] = deja[0]["credit"]
        return deja[0]["url"]
    return secours


def credits(urls: list) -> str:
    """Ligne de crédits des images d'un post (vide si aucune image n'en demande)."""
    vus = []
    for u in urls:
        c = CREDITS.get(u)
        if c and c not in vus:
            vus.append(c)
    return " · ".join(vus)
