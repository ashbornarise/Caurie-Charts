"""Kworb (kworb.net) : les compteurs publics de Spotify, relevés chaque jour (streams, auditeurs mensuels, titres).

Données réelles, sans clé d'API. Kworb ne suit que les artistes présents dans les classements Spotify : pour les autres,
chiffres() renvoie None et rien n'est affiché (jamais de chiffre inventé). Utilisé par les portraits d'artistes et par
Cauri Monde (caps de streams)."""
import html
import re

from core.services.news import http_get

BASE = "https://kworb.net/spotify/"
_PAGES: dict = {}


def _page(url: str) -> str:
    if url not in _PAGES:
        _PAGES[url] = http_get(url) or ""
    return _PAGES[url]


def _nombre(s: str) -> float:
    return float(s.replace(",", ""))


def auditeurs() -> dict:
    """Auditeurs mensuels (top 2 500) : id Spotify → (auditeurs, record)."""
    rows = re.findall(r'artist/([A-Za-z0-9]{22})_songs\.html">[^<]+</a></div></td><td>([\d,]+)</td><td>[-\d,]+</td><td>\d+</td>'
                      r'<td class="smaller">([\d,]+)</td>', _page(BASE + "listeners.html"))
    return {i: (int(_nombre(a)), int(_nombre(p))) for i, a, p in rows}


def chiffres(spotify_id: str) -> dict | None:
    """Les chiffres Spotify d'un artiste : total de streams, streams par jour, auditeurs mensuels et record,
    titres les plus écoutés, prochain cap rond et délai estimé. None si Kworb ne suit pas cet artiste."""
    if not spotify_id or not re.fullmatch(r"[A-Za-z0-9]{22}", spotify_id):
        return None
    page = _page(f"{BASE}artist/{spotify_id}_songs.html")
    m = re.search(r'<td class="text">Streams</td><td>([\d,]+)</td>', page)
    if not m:
        return None
    total = _nombre(m.group(1))
    titres = []
    for feat, titre, streams, jour in re.findall(r'<td class="text"><div>(\* )?<a href="https://open\.spotify\.com/track/[^"]+"[^>]*>([^<]+)</a></div></td>'
                                                 r'<td>([\d,]+)</td><td>([\d,]*)</td>', page):
        titres.append({"titre": html.unescape(titre), "streams": _nombre(streams), "jour": _nombre(jour) if jour else 0.0, "feat": bool(feat)})
    jour = sum(t["jour"] for t in titres)
    aud = auditeurs().get(spotify_id)
    # prochain cap rond : tous les 10 milliards au-delà de 10 Md, chaque milliard au-delà de 1 Md, sinon tous les 100 millions
    pas = 10e9 if total >= 10e9 else (1e9 if total >= 1e9 else 1e8)
    cap = (total // pas + 1) * pas
    jours = round((cap - total) / jour) if jour > 0 else None
    return {"total": total, "jour": jour, "auditeurs": aud[0] if aud else None, "record_auditeurs": aud[1] if aud else None,
            "titres": sorted(titres, key=lambda t: -t["streams"])[:3], "cap": cap, "jours_cap": jours}


def volume(n: float) -> str:
    """4 480 000 000 → « 4,48 milliards » ; 616 233 720 → « 616 millions »."""
    if n >= 1e9:
        v = f"{n / 1e9:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        return v + (" milliards" if n >= 2e9 else " milliard")
    if n >= 1e6:
        return f"{n / 1e6:.0f}".replace(".", ",") + " millions"
    return f"{n:,.0f}".replace(",", " ")
