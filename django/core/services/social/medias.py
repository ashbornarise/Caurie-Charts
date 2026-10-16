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
from urllib.parse import quote

from core import db
from core.services.platforms import log_write

CREDITS: dict = {}
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
            # « X performed at Burna Boy concert » : l'artiste n'est pas le sujet de la photo
            if nom not in titre or f"at {nom}" in titre or f"for {nom}" in titre:
                continue
            if r.get("width") and (r["width"] < 900 or (r.get("height") or 0) < 700):   # taille parfois absente
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


def _cle(url: str) -> str:
    return "img-" + hashlib.md5(url.encode()).hexdigest()[:16]


def choisit(artiste: str, secours: str | None = None, alterne: int = 0) -> str | None:
    """Une image de l'artiste pas encore utilisée ces 10 jours ; alterne plans de clips et photos de scène."""
    from core.services.social import monde as M
    clips, scenes = plans_de_clips(artiste), scenes_libres(artiste)
    ordre = (clips + scenes) if alterne % 2 == 0 else (scenes + clips)
    for c in ordre:
        if not M.vu(_cle(c["url"])):
            M.marque_vu([_cle(c["url"])])
            CREDITS[c["url"]] = c["credit"]
            return c["url"]
    if ordre:   # tout a déjà servi : on reprend la plus ancienne source plutôt que rien
        CREDITS[ordre[0]["url"]] = ordre[0]["credit"]
        return ordre[0]["url"]
    return secours


def credits(urls: list) -> str:
    """Ligne de crédits des images d'un post (vide si aucune image n'en demande)."""
    vus = []
    for u in urls:
        c = CREDITS.get(u)
        if c and c not in vus:
            vus.append(c)
    return " · ".join(vus)
