"""Photos des artistes : toutes les photos candidates de plusieurs sources, la meilleure retenue automatiquement.

Sources, de la plus sûre à la plus large :
  presse   : photo envoyée par l'artiste ou son équipe (page « Revendiquer ma fiche »), validée dans l'admin ;
  apple    : photo officielle Apple Music (jusqu'à 2400 px), retenue seulement si Apple liste aussi un de nos titres
             de l'artiste (pas d'homonyme) ;
  commons  : Wikimedia Commons (licence libre, crédit obligatoire), par Wikidata, seulement pour une personne
             de nationalité d'un des 16 pays couverts ;
  youtube  : avatar de la chaîne officielle déjà rattachée à l'artiste (1200 px, 1 unité de quota) ;
  deezer   : photo du profil Deezer (1000 px).
Une photo verrouillée (choisie dans l'admin ou envoyée par l'artiste) n'est jamais remplacée la nuit.
  image_url : version légère pour le site ; image_hd_url : version la plus grande pour les posts 4K.
"""
import io
import json
import re
from urllib.parse import quote

from core import budget, conf, db, env
from core.repos import now_utc
from core.services.imports import normalizer as N

UA = {"User-Agent": "CauriCharts/1.0 (https://cauricharts.com ; contact@cauricharts.com)"}
SIZE = re.compile(r"/[0-9]+x[0-9]+[a-z]*(-[0-9]+)?\.(jpg|jpeg|png|webp)$")
# Préférence à taille égale : une photo officielle de studio vaut mieux qu'une photo de concert
WEIGHT = {"presse": 3.0, "admin": 3.0, "lien": 2.0, "apple": 1.0, "commons": 0.85, "youtube": 0.8, "deezer": 0.7}


def sized(url: str, px: int) -> str:
    """Adresse mzstatic (Apple) à la taille voulue : Apple redimensionne à la volée, sans dépasser l'original."""
    return SIZE.sub(f"/{px}x{px}bb.jpg", url)


def best(candidates: list) -> dict | None:
    ok = [c for c in candidates if int(c.get("side") or 0) >= 600]
    return max(ok, key=lambda c: min(int(c["side"]), 2400) * WEIGHT.get(c["source"], 0.5), default=None)


class ArtistPhotos:
    def __init__(self, http):
        self.http = http

    def _json(self, url: str, headers: dict | None = None):
        r = self.http.request("GET", url, {**UA, **(headers or {})})
        try:
            return json.loads(r["body"]) if r["status"] == 200 else None
        except ValueError:
            return None

    # ------------------------------------------------------------ sources

    def apple(self, name: str, titles: list) -> dict | None:
        body = self._json("https://itunes.apple.com/search?entity=musicArtist&limit=5&term=" + quote(name)) or {}
        wanted = {N.title(t) for t in titles if N.title(t)}
        for a in body.get("results") or []:
            if N.artist_key(a.get("artistName", "")) != N.artist_key(name):
                continue
            songs = self._json(f"https://itunes.apple.com/lookup?entity=song&limit=200&id={int(a['artistId'])}") or {}
            found = {N.title(s.get("trackName", "")) for s in songs.get("results") or [] if s.get("wrapperType") == "track"}
            if not wanted & found:
                continue  # homonyme : aucun titre en commun avec notre catalogue
            page = self.http.request("GET", a.get("artistLinkUrl", ""), {"User-Agent": "Mozilla/5.0 (CauriCharts)"})
            m = re.search(r'<meta property="og:image" content="([^"]+)"', page["body"] if page["status"] == 200 else "")
            if not m or "mzstatic" not in m.group(1):
                return None
            hd = sized(m.group(1), 2400)
            return {"source": "apple", "url": hd, "site": sized(m.group(1), 1000), "side": self._side(hd), "apple_id": int(a["artistId"])}
        return None

    def commons(self, name: str) -> dict | None:
        countries = set((conf.get("discovery") or {}).get("wikidata_countries", {}).values())
        found = self._json("https://www.wikidata.org/w/api.php?action=wbsearchentities&language=fr&type=item&limit=3&format=json&search="
                           + quote(name)) or {}
        for item in found.get("search") or []:
            if N.artist_key(item.get("label", "")) != N.artist_key(name):
                continue
            claims = (self._json(f"https://www.wikidata.org/wiki/Special:EntityData/{item['id']}.json") or {}).get("entities", {}).get(item["id"], {}).get("claims", {})
            nat = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P27", [])}
            if not (nat & countries) or not claims.get("P18"):
                continue  # pas d'un pays couvert (homonyme probable), ou pas de photo
            file = claims["P18"][0]["mainsnak"]["datavalue"]["value"]
            info = self._json("https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=size|extmetadata&format=json&titles="
                              + quote("File:" + file)) or {}
            page = next(iter((info.get("query") or {}).get("pages", {}).values()), {})
            ii = (page.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata") or {}
            author = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
            lic = (meta.get("LicenseShortName") or {}).get("value", "")
            base = "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(file.replace(" ", "_"))
            return {"source": "commons", "url": base + "?width=2400", "site": base + "?width=1000",
                    "side": min(int(ii.get("width") or 0), int(ii.get("height") or 0)),
                    "credit": f"Photo : {author or 'Wikimedia Commons'}, {lic or 'licence libre'} (Wikimedia Commons)"[:250]}
        return None

    def youtube(self, channel_id: str | None) -> dict | None:
        from core.services.platforms import YouTubeQuota
        key = env.get("YOUTUBE_API_KEY", "")
        if not channel_id or not key or not YouTubeQuota.spend(1):
            return None
        items = (self._json(f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={quote(channel_id)}&key={quote(key)}") or {}).get("items") or []
        thumbs = (items[0].get("snippet") or {}).get("thumbnails") if items else None
        url = ((thumbs or {}).get("high") or {}).get("url")
        if not url or "=" not in url:
            return None
        base = url.split("=")[0]
        return {"source": "youtube", "url": base + "=s1200", "site": base + "=s800", "side": 1200}

    # ------------------------------------------------------------ choix

    def _side(self, url: str) -> int:
        from PIL import Image
        from core.services.news import http_get
        try:
            return min(Image.open(io.BytesIO(http_get(url, binary=True))).size)
        except Exception:  # noqa: BLE001
            return 0

    def collect(self, a: dict) -> list:
        titles = [r["title"] for r in db.all("SELECT title FROM tracks WHERE artist_id = ? ORDER BY id LIMIT 60", [a["id"]])]
        out = []
        for fn in (lambda: self.apple(a["name"], titles), lambda: self.commons(a["name"]), lambda: self.youtube(a.get("youtube_channel_id"))):
            try:
                c = fn()
            except Exception:  # noqa: BLE001 — une source en panne n'empêche pas les autres
                c = None
            if c:
                out.append(c)
        if a.get("image_url") and "dzcdn" in str(a["image_url"]):
            out.append({"source": "deezer", "url": a["image_url"], "site": a["image_url"], "side": 1000})
        # Les photos presse envoyées par les artistes restent dans la galerie (validation dans l'admin)
        try:
            kept = [c for c in json.loads(a.get("photo_candidates") or "[]") if c.get("source") == "presse"]
        except ValueError:
            kept = []
        return kept + out

    def run(self, limit: int = 120) -> list:
        # Artistes confirmés, ceux présents dans un classement récent d'abord ; recherche refaite tous les 30 jours
        artists = db.all(f"""SELECT a.id, a.name, a.image_url, a.youtube_channel_id, a.image_locked, a.photo_candidates FROM artists a
                             WHERE a.status = 'active'
                               AND (a.photo_checked_at IS NULL OR a.photo_checked_at < LOCALTIMESTAMP - INTERVAL '30 days')
                             ORDER BY EXISTS (SELECT 1 FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                                              WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 14) DESC,
                                      a.photo_checked_at NULLS FIRST, a.fans DESC NULLS LAST LIMIT {max(0, int(limit))}""")
        checked = changed = 0
        by_source: dict = {}
        for a in artists:
            if budget.over():
                break  # temps de l'étape écoulé : la suite la nuit prochaine
            checked += 1
            cands = self.collect(a)
            for c in cands:
                by_source[c["source"]] = by_source.get(c["source"], 0) + 1
            data = {"photo_checked_at": now_utc(), "photo_candidates": json.dumps(cands, ensure_ascii=False)}
            pick = best([c for c in cands if c["source"] != "presse"])  # une photo presse attend toujours la validation
            if pick and not a["image_locked"]:
                data.update({"image_url": pick["site"], "image_hd_url": pick["url"], "image_source": pick["source"],
                             "image_credit": pick.get("credit")})
                if pick.get("apple_id"):
                    data["apple_id"] = pick["apple_id"]
                changed += 1
            db.update("artists", data, "id = :id", {"id": a["id"]})
        sources = ", ".join(f"{k} {v}" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1]))
        return [f"{checked} artistes examinés, {changed} photos choisies (candidates : {sources or 'aucune'})"]


def set_deezer_photo(artist_id: int, url) -> None:
    """Photo Deezer (1000 px) : posée seulement si l'artiste n'a ni photo verrouillée, ni photo d'une meilleure source."""
    if url:
        db.run("""UPDATE artists SET image_url = ?, image_source = 'deezer' WHERE id = ? AND image_locked = 0
                  AND COALESCE(image_source, 'deezer') = 'deezer'""", [url, int(artist_id)])
