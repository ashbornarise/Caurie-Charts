"""« Cauri raconte » v3 (15/11/2026) — retours du fondateur sur l'épisode Wizkid (v2, 2 min) :
« 3 à 5 minutes ; beaucoup de plans de lui et de photos de toutes les époques, pas une pochette qui dure toute la
vidéo ; on ne fait qu'effleurer son histoire : à chaque palier un secret ou un mythe ; où il a commencé, tout son
trajet, ses succès, ses projets ; parler de ses contrats (taux de change) ; sons de fond plus forts et qui changent
souvent ; une accroche dans les premières secondes ; voix enthousiaste ; plus de barre de progression ; un vrai
travail de YouTubeur (façon Poisson Fécond) ».

- Médiathèque de l'artiste : tous les clips officiels, lives, coulisses et courts métrages de ses chaînes YouTube
  officielles, de toutes les époques (année de sortie du titre quand on la connaît), + photos datées de Wikimedia
  Commons (libres de droits, créditées) + sa banque de photos Cauri.
- Mythes et secrets (Gemini + Google, 2 sources au moins), contrats et montants connus (2 sources), convertis en
  naira, FCFA et cedis (ExchangeRate-API, clé EXCHANGERATE_API_KEY).
- Récit documentaire (600 à 750 mots, 5 à 6 chapitres = les paliers), chaque phrase choisit ses images dans la
  médiathèque (comme un monteur) et chaque chapitre sa musique de l'époque.
- Montage : accroche en plans très courts sur ses clips les plus vus, plans de 1,6 à 2,6 s (plein cadre ou cadre
  16:9 sur fond flou), photos d'archive datées, cartes « Mythe ou réalité ? », cartes de contrat, musique de fond
  normalisée et plus présente, qui change à chaque chapitre (et au bout de 40 s au plus).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests

from core import db, env
from core.services.platforms import log_write

DUREE_PROJET = 9.0
PAUSE = 0.18
FOND = 0.17              # musique normalisée à −14 LUFS : ~15 dB sous la voix (v2 : 0,045 sur des clips non normalisés, « trop bas »)
SEGMENT_MAX = 40.0       # « change de sons souvent » : une musique de fond ne reste jamais plus de 40 s
UA = {"User-Agent": "CauriCharts/1.0 (https://www.cauricharts.com)"}
MAUVAIS = re.compile(r"\b(audio|lyrics?|visuali[sz]er|trailer|teaser|reaction|r[ée]action|karaoke|8d|sped|slowed|instrumental|cover|"
                     r"remix|mashup|tiktok|shorts?)\b", re.I)
SFX = {"chapitre": "raconte/sfx/swoosh-cine.mp3", "carte": "raconte/sfx/whoosh-fast.mp3", "montee": "raconte/sfx/riser-drama.mp3",
       "impact": "raconte/sfx/impact-big.mp3", "fin": "raconte/sfx/reverse-impact.mp3", "sortie": "raconte/sfx/sparkle-whoosh.mp3"}


def _cle(s: str) -> str:
    from core.services.social.raconte_v2 import _cle as c
    return c(s)


def _ffmpeg() -> str:
    from core.services.social.studio_montage import ffmpeg
    return ffmpeg()


def _duree(chemin: str) -> float:
    from core.services.social.raconte_v2 import _duree as d
    return d(chemin)


# ---------------------------------------------------------------- taux de change

_TAUX: dict = {}


def taux_usd() -> dict:
    """Taux du jour depuis 1 USD (ExchangeRate-API, offre gratuite : 1 appel par jour suffit, gardé en cache)."""
    jour = date.today().isoformat()
    if _TAUX.get("jour") == jour:
        return _TAUX["taux"]
    cache = os.path.join(tempfile.gettempdir(), "cauri-taux-usd.json")
    try:
        c = json.load(open(cache, encoding="utf-8"))
        if c.get("jour") == jour:
            _TAUX.update(c)
            return c["taux"]
    except (OSError, ValueError):
        pass
    cle = env.get("EXCHANGERATE_API_KEY", "")
    if not cle:
        return {}
    try:
        d = requests.get(f"https://v6.exchangerate-api.com/v6/{cle}/latest/USD", timeout=20).json()
        taux = {k: d["conversion_rates"][k] for k in ("NGN", "XOF", "GHS", "EUR") if k in d.get("conversion_rates", {})}
    except Exception as exc:  # noqa: BLE001
        log_write("studio", "warning", f"raconte : taux de change indisponibles ({exc})")
        return {}
    _TAUX.update({"jour": jour, "taux": taux})
    json.dump(_TAUX, open(cache, "w", encoding="utf-8"))
    return taux


def _gros(v: float) -> str:
    for seuil, mot in ((1e9, "milliard"), (1e6, "million")):
        if v >= seuil:
            x = f"{v / seuil:.1f}".rstrip("0").rstrip(".")
            return x.replace(".", ",") + " " + mot + ("s" if float(x) >= 2 else "")
    return f"{v:,.0f}".replace(",", " ")


def convertit(usd: float) -> dict:
    """1 000 000 $ -> {'usd': '1 million $', 'ngn': '1,5 milliard de nairas', 'xof': '560 millions de FCFA', ...}."""
    t = taux_usd()
    out = {"usd": _gros(usd) + " $"}
    if t.get("NGN"):
        out["ngn"] = _gros(usd * t["NGN"]) + " de nairas"
    if t.get("XOF"):
        out["xof"] = _gros(usd * t["XOF"]) + " de FCFA"
    if t.get("GHS"):
        out["ghs"] = _gros(usd * t["GHS"]) + " de cedis"
    return out


# ---------------------------------------------------------------- recherche (Gemini + Google, 2 sources)

def _cherche(question: str, jetons: int = 2500) -> dict:
    from core.services import ai
    from core.services.platforms import HttpClient
    os.environ.setdefault("GEMINI_GROUNDING", "1")
    try:
        r = ai.GeminiClient(HttpClient(180)).ask("Tu es documentaliste musical. Tu ne gardes que des faits confirmés par la recherche, "
                                                 "chacun appuyé par au moins 2 médias différents.", question, jetons, web_searches=8)
        return ai.extract_json(r["text"]) or {}
    except Exception as exc:  # noqa: BLE001
        log_write("studio", "warning", f"raconte : recherche indisponible ({exc})")
        return {}


def _deux_sources(x: dict) -> bool:
    return len({str(s).strip().lower() for s in x.get("sources") or [] if str(s).strip()}) >= 2


REDDIT = "fatihtahta~reddit-scraper-search-fast"   # 0,0015 $ par fil (Reddit refuse les PC en direct : 403)
PRIX_FIL = 0.0015


def rumeurs_forums(nom: str, pays: str) -> list[dict]:
    """Ce que les fans racontent sur les forums (15/11/2026, demande du fondateur) : Reddit via Apify (~0,05 $),
    Nairaland et les autres forums via la recherche Google de Gemini (Nairaland refuse aussi les PC : 403).
    Ces rumeurs ne prouvent rien : elles servent à CHOISIR les mythes, le verdict reste établi par 2 médias."""
    out = []
    jeton = env.get("APIFY_TOKEN", "")
    try:
        from core.services import spotify_apify as SA
        if jeton and SA.depense() + 0.1 < SA.PLAFOND_MOIS:
            r = requests.post(f"https://api.apify.com/v2/acts/{REDDIT}/run-sync-get-dataset-items", timeout=420,
                              params={"token": jeton, "timeout": 360},
                              json={"queries": [f"{nom} rumor", f"{nom} myth", f"{nom} untold story", f"{nom} truth"], "sort": "relevance",
                                    "timeframe": "all", "maxPosts": 10, "scrapeComments": False})
            fils = r.json() if r.ok else []
            SA._compte(PRIX_FIL * len(fils))
            mot = re.compile(rf"(?<![a-z0-9]){re.escape(nom)}(?![a-z0-9])", re.I)   # « Wizkid », pas le jeu « Wizkids »
            for f in fils if isinstance(fils, list) else []:
                titre = str(f.get("title") or "").strip()
                if titre and not f.get("over_18") and mot.search(titre + " " + str(f.get("body") or "")[:300]):
                    out.append({"forum": "Reddit r/" + str(f.get("subreddit") or f.get("communityName") or "").replace("r/", ""),
                                "rumeur": titre[:200], "extrait": str(f.get("body") or f.get("selftext") or "")[:280],
                                "score": f.get("score") or f.get("upVotes") or 0})
    except Exception as exc:  # noqa: BLE001
        log_write("studio", "warning", f"raconte : Reddit indisponible ({exc})")
    out = sorted(out, key=lambda x: -(x["score"] or 0))[:15]
    d = _cherche(f"Cherche sur nairaland.com (et les autres forums de fans de {pays}) les rumeurs, mythes et histoires qui circulent sur "
                 f"l'artiste {nom}. Liste jusqu'à 8 rumeurs telles que les fans les racontent, avec le forum et le titre du fil. "
                 'JSON strict : {"rumeurs": [{"rumeur": "", "forum": "", "fil": ""}]}', 2000)
    for x in d.get("rumeurs") or []:
        if str(x.get("rumeur") or "").strip():
            out.append({"forum": str(x.get("forum") or "forum")[:40], "rumeur": str(x["rumeur"])[:200], "extrait": str(x.get("fil") or "")[:160]})
    return out[:22]


def mythes(nom: str, pays: str, forums: list | None = None) -> list[dict]:
    """Mythes, rumeurs et secrets sur l'artiste, avec le vrai/faux établi par 2 sources au moins."""
    forums = rumeurs_forums(nom, pays) if forums is None else forums
    piste = ("\n\nRumeurs repérées sur les forums de fans (Reddit, Nairaland…) — elles ne prouvent rien, mais choisis en priorité "
             "celles-ci et vérifie-les dans la presse :\n" + json.dumps(forums, ensure_ascii=False)) if forums else ""
    d = _cherche(f"Artiste : {nom} ({pays}). Trouve 8 mythes, rumeurs ou secrets qui circulent sur lui (débuts, nom de scène, famille, "
                 "argent, rivalités, records, anecdotes de studio, collaborations), à chaque étape de sa carrière. Pour chacun : "
                 "l'affirmation telle que les gens la racontent, le verdict établi (VRAI, FAUX ou À MOITIÉ), l'explication courte, l'année "
                 "concernée et au moins 2 sources différentes (nom du média). JSON strict : {\"mythes\": [{\"affirmation\": \"\", "
                 "\"verdict\": \"VRAI\", \"explication\": \"\", \"annee\": \"\", \"sources\": [\"\", \"\"]}]}" + piste, 3500)
    out = []
    for m in d.get("mythes") or []:
        v = str(m.get("verdict") or "").upper().replace("A MOITIE", "À MOITIÉ")
        if _deux_sources(m) and v in ("VRAI", "FAUX", "À MOITIÉ") and str(m.get("affirmation") or "").strip():
            from core.services.social.studio_raconte import _propre   # jamais « Billboard » à l'écran (carte du mythe)
            out.append({"affirmation": _propre(m["affirmation"])[:200], "verdict": v, "explication": _propre(m.get("explication") or "")[:300],
                        "annee": str(m.get("annee") or "")[:12], "sources": [str(s)[:60] for s in m["sources"]][:3]})
    return out[:8]


def contrats(nom: str) -> list[dict]:
    """Contrats, signatures et montants rendus publics (2 sources), convertis en monnaies ouest-africaines."""
    d = _cherche(f"Artiste : {nom}. Liste ses contrats et accords connus (labels, distribution, marques, sponsors, cachets record) avec "
                 "l'année et, seulement s'il a été rendu public par la presse, le montant en dollars américains. Au moins 2 sources "
                 "différentes par contrat. JSON strict : {\"contrats\": [{\"quoi\": \"\", \"avec\": \"\", \"annee\": \"\", "
                 "\"montant_usd\": null, \"sources\": [\"\", \"\"]}]}", 2500)
    out = []
    for c in d.get("contrats") or []:
        if not (_deux_sources(c) and str(c.get("quoi") or "").strip()):
            continue
        x = {"quoi": str(c["quoi"]).strip()[:160], "avec": str(c.get("avec") or "")[:80], "annee": str(c.get("annee") or "")[:12],
             "sources": [str(s)[:60] for s in c["sources"]][:3]}
        try:
            usd = float(str(c.get("montant_usd") or "").replace(",", "").replace(" ", "").replace("$", ""))
        except ValueError:
            usd = 0
        if usd >= 1000:
            x["montant_usd"] = usd
            x["equivalents"] = convertit(usd)
        out.append(x)
    return out[:6]


# ---------------------------------------------------------------- médiathèque : vidéos et photos de toutes les époques

def _yt(args: list, timeout: int = 180) -> str:
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-warnings", "--ignore-errors", *args]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace").stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _plat(cible: str, n: int) -> list[dict]:
    out = []
    fmt = "%(id)s\t%(title)s\t%(channel)s\t%(view_count)s\t%(duration)s\t%(channel_url)s"
    for l in _yt(["--flat-playlist", "--playlist-end", str(n), "--print", fmt, cible]).splitlines():
        p = l.split("\t")
        if len(p) == 6 and len(p[0]) == 11:
            out.append({"yt": p[0], "titre": p[1], "chaine": p[2], "vues": int(float(p[3])) if p[3] not in ("NA", "None", "") else 0,
                        "duree": float(p[4]) if p[4] not in ("NA", "None", "") else 0, "url": p[5] if p[5].startswith("http") else ""})
    return out


def chaines_officielles(nom: str) -> list[tuple[str, str]]:
    """(nom, adresse) des chaînes qui publient ses clips officiels : celles qui reviennent sur « <nom> official video »."""
    from collections import Counter
    k = _cle(nom)
    compte, urls = Counter(), {}
    for v in _plat(f"ytsearch25:{nom} official video", 25):
        if v["url"] and v["chaine"] and (k in _cle(v["titre"]) or k in _cle(v["chaine"])) and v["vues"] >= 300_000:
            compte[v["chaine"]] += 2 if k in _cle(v["chaine"]) or "vevo" in v["chaine"].lower() else 1
            urls[v["chaine"]] = v["url"]
    return [(c, urls[c]) for c, n in compte.most_common(3) if n >= 2]


def _sorte(titre: str) -> str:
    t = titre.lower()
    if re.search(r"\(live\)|\blive at\b|concert|tour|performance|festival|tonight show|fallon|awards", t):
        return "live"
    if re.search(r"making|behind|coulisses|bts|documentary|short film|interview|vlog|talks|reflects|describes|day in the live|studio", t):
        return "coulisses"
    return "clip"


def titres_wikipedia(nom: str, article: str) -> list[dict]:
    """Les titres cités dans l'article Wikipédia avec leur année (les débuts manquent souvent chez Deezer : rééditions)."""
    if not article:
        return []
    from core.services import ai
    from core.services.platforms import HttpClient
    try:
        r = ai.GeminiClient(HttpClient(120)).ask(
            "Tu extrais des données d'un texte, sans rien ajouter.",
            f"Article sur {nom} :\n{article[:7000]}\n\nListe chaque chanson ou single de {nom} cité dans l'article avec l'année "
            'indiquée dans le texte. JSON strict : {"titres": [{"titre": "", "annee": "2010"}]}', 1500)
        d = ai.extract_json(r["text"]) or {}
    except Exception:  # noqa: BLE001
        return []
    return [{"titre": str(x["titre"])[:80], "annee": str(x.get("annee") or "")[:4]} for x in d.get("titres") or []
            if str(x.get("titre") or "").strip() and re.fullmatch(r"(19|20)\d\d", str(x.get("annee") or "")[:4])][:30]


def videotheque(nom: str, disco: dict, wiki: list[dict] | None = None) -> list[dict]:
    """Ses vidéos officielles (clips, lives, coulisses), de toutes les époques, avec l'année de sortie du titre si connue."""
    annees = {_cle(x["titre"]): x["annee"] for x in wiki or []}   # Wikipédia d'abord : la vraie année (Deezer date les rééditions)
    for p in disco.get("projets") or []:
        for t in p.get("titres_phares") or []:
            annees.setdefault(_cle(t["titre"]), (p.get("date") or "")[:4])
    for s in disco.get("singles_marquants") or []:
        annees.setdefault(_cle(s["titre"]), (s.get("date") or "")[:4])
    vues, out = set(), []

    def garde(v, source):
        if v["yt"] in vues or MAUVAIS.search(v["titre"]) or (v["duree"] and (v["duree"] < 60 or v["duree"] > 1500)):
            return
        vues.add(v["yt"])
        titre = re.sub(rf"^\s*{re.escape(nom)}\s*[-–:]\s*", "", v["titre"], flags=re.I).strip()
        base = _cle(re.split(r"\s+(?:ft\.?|feat\.?|x)\s+", titre, flags=re.I)[0])
        out.append({"yt": v["yt"], "titre": titre[:90], "vues": v["vues"], "sorte": _sorte(v["titre"]), "annee": annees.get(base, ""), "source": source})

    # 1) ses chaînes officielles, en entier (VEVO, chaîne du label…)
    for ch, url in chaines_officielles(nom):
        for v in _plat(url + "/videos", 250):
            garde(v, ch)
    # 2) les titres de la discographie absents des chaînes (souvent les débuts, publiés ailleurs)
    connus = {_cle(re.split(r"\s+(?:ft\.?|feat\.?)\s+|\s*\(", x["titre"], flags=re.I)[0]) for x in out}
    manquants = [t for t, a in sorted(annees.items(), key=lambda x: x[1] or "9999") if t not in connus][:18]
    noms = {_cle(x["titre"]): x["titre"] for x in wiki or []}
    noms.update({_cle(t["titre"]): t["titre"] for p in disco.get("projets") or [] for t in p.get("titres_phares") or []})
    noms.update({_cle(s["titre"]): s["titre"] for s in disco.get("singles_marquants") or []})
    for t in manquants:
        for v in _plat(f"ytsearch3:{nom} {noms.get(t, t)} official video", 3):
            if t in _cle(v["titre"]) and v["vues"] >= 150_000:
                garde(v, "recherche")
                if out and out[-1]["yt"] == v["yt"] and not out[-1]["annee"]:
                    out[-1]["annee"] = annees.get(t, "")
                break
    # 3) année de publication pour les vidéos sans année de titre (lives, coulisses)
    sans = [x for x in out if not x["annee"]][:40]

    def date_de(x):
        d = _yt(["--skip-download", "--print", "%(upload_date)s", f"https://www.youtube.com/watch?v={x['yt']}"], 90).strip()[:4]
        x["annee"] = d if d.isdigit() else ""
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(date_de, sans))
    out.sort(key=lambda x: (x["annee"] or "9999", -x["vues"]))
    return out[:70]


def photos_commons(nom: str) -> list[dict]:
    """Photos libres de droits (Wikimedia Commons) dont le titre porte son nom, avec leur date et l'auteur à créditer."""
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
            "action": "query", "format": "json", "generator": "search", "gsrsearch": f'intitle:"{nom}" filetype:bitmap', "gsrnamespace": 6,
            "gsrlimit": 40, "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600}).json()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for p in (r.get("query") or {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata") or {}
        if ii.get("width", 0) < 500 or ii.get("height", 0) < 500 or re.search(r"album cover|cover|logo|signature|poster|booth", p["title"], re.I):
            continue
        quand = re.sub(r"<[^>]+>", "", str((m.get("DateTimeOriginal") or {}).get("value") or ""))
        annee = (re.search(r"(19|20)\d\d", quand + " " + p["title"]) or [""])[0]
        auteur = re.sub(r"<[^>]+>", "", str((m.get("Artist") or {}).get("value") or "")).strip()[:40]
        out.append({"url": ii.get("thumburl") or ii.get("url"), "titre": p["title"].replace("File:", "").rsplit(".", 1)[0][:90], "annee": annee,
                    "credit": f"Photo : {auteur or 'Wikimedia Commons'} ({(m.get('LicenseShortName') or {}).get('value', 'CC')})"})
    return [x for x in out if x["url"]][:14]


def photos_banque(artist_id: int) -> list[dict]:
    """Sa banque de photos Cauri (récentes, validées)."""
    from core import storage
    base = f"{storage.blob_public_url()}/media/artists/plans/"
    return [{"url": base + r["fichier"], "titre": "photo récente (banque Cauri)", "annee": "", "credit": ""}
            for r in db.all("SELECT fichier FROM artist_photos WHERE artist_id = ? ORDER BY COALESCE(score, 0.5) DESC, id LIMIT 14", [artist_id])]


def mediatheque(artist_id: int, nom: str, disco: dict, article: str = "") -> list[dict]:
    """Tout ce que le récit peut montrer, chaque élément avec un identifiant court (v… vidéos, p… photos)."""
    medias = []
    for i, v in enumerate(videotheque(nom, disco, titres_wikipedia(nom, article))):
        medias.append({"id": f"v{i + 1}", "type": v["sorte"], "titre": v["titre"], "annee": v["annee"], "vues": v["vues"], "yt": v["yt"]})
    try:
        banque = photos_banque(artist_id)
    except Exception:  # noqa: BLE001
        banque = []
    for i, ph in enumerate(photos_commons(nom) + banque):
        medias.append({"id": f"p{i + 1}", "type": "photo", "titre": ph["titre"], "annee": ph["annee"], "url": ph["url"], "credit": ph["credit"]})
    return medias


def dossier(artist_id: int, angle: str = "") -> dict:
    from core.services.social import raconte_v2
    d = raconte_v2.dossier(artist_id, angle)
    nom, pays = d["artiste"], d.get("pays") or ""
    d["rumeurs_des_forums_non_verifiees"] = rumeurs_forums(nom, pays)   # pistes seulement (Reddit, Nairaland)
    with ThreadPoolExecutor(3) as pool:
        f_m = pool.submit(mythes, nom, pays, d["rumeurs_des_forums_non_verifiees"])
        f_c = pool.submit(contrats, nom)
        f_v = pool.submit(mediatheque, artist_id, nom, d.get("discographie") or {}, d.get("article_wikipedia") or "")
        d["mythes_et_secrets_verifies"] = f_m.result()
        d["contrats_connus"] = f_c.result()
        d["_medias"] = f_v.result()
    d["mediatheque"] = [{k: v for k, v in m.items() if k in ("id", "type", "titre", "annee")} for m in d["_medias"]]
    sources = {s for x in d["mythes_et_secrets_verifies"] + d["contrats_connus"] for s in x["sources"]}
    if sources:
        d["_sources"] = d["_sources"].rstrip(")").rsplit(" (", 1)[0] + " · " + ", ".join(sorted(sources))[:160] + f" ({date.today():%d/%m/%Y})"
    if any(m["type"] == "photo" and m.get("credit", "").startswith("Photo : ") and "Commons" not in m["credit"] for m in d["_medias"]):
        d["_sources"] += " · photos Wikimedia Commons"
    return d


# ---------------------------------------------------------------- écriture

SYSTEME = """Tu écris le récit d'un documentaire vertical « Cauri raconte » de 3 min 30 à 4 min 30 sur un artiste, pour Cauri Charts,
« la référence de la musique ouest-africaine ». C'est un épisode demandé par nos abonnés : il faut RESPECTER LA LÉGENDE de
l'artiste, raconter tout son trajet en profondeur (où il a commencé, avec qui, le quartier, les premières galères, le déclic,
chaque grand projet et ce qu'il a changé, les contrats, les records, aujourd'hui), comme un vrai YouTubeur documentaire
(façon Poisson Fécond) : rythme, tension, révélations, phrases vivantes au présent de narration, voix jeune et ENTHOUSIASTE.

Le récit est une suite de BLOCS :
- {"type": "chapitre", "numero": "CHAPITRE 1", "titre": "OJUELEGBA", "annees": "1990 – 2009", "musique": "v12"} : 5 ou 6 chapitres =
  les paliers de sa carrière. « musique » = l'id d'une VIDÉO de la médiathèque, d'un titre de cette époque (ou de la suivante),
  différente à chaque chapitre : c'est la musique de fond du chapitre.
- {"type": "voix", "texte": "...", "voix": "[excited]", "medias": ["v3", "p2"], "carte": null, "mythe": null, "contrat": null} :
  1 à 2 phrases courtes et orales. « voix » = UNIQUEMENT une balise d'émotion parmi [excited] [mysterious] [whispers] [confident]
  [laughs] [curious] [serious] [amazed] (ou ""). « medias » = 1 à 3 ids de la médiathèque À MONTRER pendant la phrase, comme un
  monteur : la bonne époque (année du média proche de ce que dit la phrase), le bon sujet (un live quand on parle de scène,
  une photo d'époque quand on parle de ses débuts). Varie au maximum : chaque id au plus 3 fois dans tout le récit, utilise le
  plus d'ids différents possible.
  « carte » = null ou {"grand": "11,8 MDS", "petit": "écoutes sur Spotify", "or": false} (6 à 9 cartes, or=true pour les 3 plus fortes).
  « mythe » = null ou {"n": 0} : la phrase POSE le mythe n°0 de « mythes_et_secrets_verifies » sous forme de question
  (« On raconte que… Vrai ou faux ? ») ; la phrase suivante donne le verdict et l'explication.
  « contrat » = null ou {"n": 0} : la phrase parle du contrat n°0 de « contrats_connus » (montant seulement s'il est fourni,
  et dis-le aussi en nairas ou en francs CFA avec les « equivalents » fournis, arrondis : « soit plus d'un milliard de nairas »).
- {"type": "projet", "album_id": 123, "etiquette": "ALBUM · 2020", "morceau": "titre", "media": "v20", "chiffre": "..."} : un grand
  projet présenté en musique (on entend 9 s de son titre phare). 3 à 5 projets (album_id exact de « discographie », « morceau » =
  un de ses titres_phares, « media » = l'id de la vidéo de ce morceau dans la médiathèque si elle existe, sinon ""). Le bloc
  voix juste avant annonce ce que le projet représente.

Construction :
1. ACCROCHE (avant le chapitre 1) : 2 à 3 blocs voix, 25 mots au plus en tout. La 1re phrase choque ou intrigue (une image forte,
   un chiffre fou, une question), balise [excited] ; puis une promesse qui retient jusqu'au bout (« Et reste jusqu'à la fin :
   il y a un mythe sur lui que presque tout le monde croit… »). medias = ses vidéos les plus spectaculaires.
2. Un chapitre par palier, dans l'ordre chronologique ; CHAQUE chapitre contient au moins un « mythe » ou un secret (« Le savais-tu ? »).
3. Dernier chapitre : aujourd'hui (nos classements Cauri Charts, ses chiffres, ce qu'il représente pour l'Afrique de l'Ouest),
   « La leçon : » en une phrase, et le dernier bloc voix exact : « Et toi, quelle légende mérite le prochain épisode ? Dis-le en commentaire. »

Règles absolues :
- « rumeurs_des_forums_non_verifiees » : ce que disent les fans sur Reddit ou Nairaland. Tu peux t'en servir comme accroche
  (« Sur les forums, des fans jurent que… ») SEULEMENT si un mythe vérifié tranche la question ; jamais comme un fait.
- UNIQUEMENT les faits fournis (Wikipédia, discographie, chiffres, mythes, contrats, faits vérifiés). Aucune date, chiffre, lieu,
  salle, record, citation ou nuance absents des données. Jamais « Billboard » (dis « le classement américain »). Jamais « le plus
  grand de tous ». Un mythe garde le verdict fourni.
- 600 à 750 mots dits en tout, AU MOINS 45 blocs voix, phrases de 8 à 22 mots, une balise d'émotion sur au moins 2 blocs sur 3,
  beaucoup de [excited] et [amazed] : le ton est passionné, jamais plat.
- titre : haut (« COMMENT » ou « POURQUOI » ou « LA LÉGENDE DE »), nom (l'artiste en capitales), bas (fin de l'accroche, < 45 caractères).
- legende_fr : 2 à 3 phrases avec une question aux abonnés ; legende_en : sa traduction.
Réponds en JSON strict : {"titre": {"haut": "", "nom": "", "bas": ""}, "blocs": [...], "legende_fr": "", "legende_en": ""}"""


def ecrit(donnees: dict) -> dict:
    from core.services import ai
    from core.services.platforms import HttpClient
    from core.services.social.studio_raconte import _chiffres_dits, _ecrit_juste, _phonetique, _propre
    client = ai.FallbackClient([ai.GeminiClient(HttpClient(300))] + [c for c in [ai.make()] if c])
    if not client.is_available():
        raise RuntimeError("aucune IA configurée pour écrire le récit")
    publiques = json.dumps({k: v for k, v in donnees.items() if not k.startswith("_")}, ensure_ascii=False, indent=1)
    os.environ["GEMINI_REFLEXION"] = "high"
    try:
        d = ai.extract_json(client.ask(SYSTEME, "Données vérifiées (n'utilise rien d'autre) :\n" + publiques, 16000)["text"]) or {}
        try:
            v = client.ask("Tu es vérificateur des faits d'un média musical. Tu compares un récit aux données, bloc par bloc.",
                           "Données (seule vérité) :\n" + publiques + "\n\nRécit :\n" + json.dumps(d, ensure_ascii=False)
                           + "\n\nToute affirmation absente des données, exagérée ou contraire (années, lieux, salles, nombres, montants, "
                           "« N°1 », « record », « premier », « domine », « d'affilée »…) doit être corrigée pour coller aux données, ou "
                           "retirée. Les verdicts des mythes restent ceux des données. Vérifie les album_id, les « morceau » (titres_phares) "
                           "et que chaque id de « medias », « musique » et « media » existe dans la médiathèque. Garde le ton, la longueur, "
                           "les balises d'émotion et la construction. Rends le même JSON corrigé, rien d'autre.", 16000)
            d2 = ai.extract_json(v["text"]) or {}
            if len(d2.get("blocs") or []) >= 0.8 * len(d.get("blocs") or []):
                d = d2
        except Exception as exc:  # noqa: BLE001
            log_write("studio", "warning", f"raconte : relecture des faits indisponible ({exc})")
    finally:
        os.environ.pop("GEMINI_REFLEXION", None)
    ids = {m["id"] for m in donnees.get("mediatheque") or []}
    videos = {m["id"] for m in donnees.get("mediatheque") or [] if m["type"] != "photo"}
    projets = {p["album_id"]: p for p in donnees.get("discographie", {}).get("projets", [])}
    les_mythes, les_contrats = donnees.get("mythes_et_secrets_verifies") or [], donnees.get("contrats_connus") or []
    blocs = []
    for x in d.get("blocs") or []:
        t = x.get("type")
        if t == "chapitre" and str(x.get("titre") or "").strip():
            blocs.append({"type": "chapitre", "numero": str(x.get("numero") or "").upper()[:20], "titre": _propre(x["titre"]).upper()[:28],
                          "annees": str(x.get("annees") or "")[:20], "musique": x.get("musique") if x.get("musique") in videos else ""})
        elif t == "projet":
            try:
                p = projets[int(x.get("album_id"))]
            except (TypeError, ValueError, KeyError):
                continue
            phares = [m["titre"] for m in p["titres_phares"]]
            morceau = next((m for m in phares if _cle(m) == _cle(x.get("morceau"))), phares[0] if phares else "")
            blocs.append({"type": "projet", "album_id": p["album_id"], "titre": p["titre"], "cover": p["cover"],
                          "etiquette": _propre(x.get("etiquette") or f"{p['type'].upper()} · {(p['date'] or '')[:4]}").upper()[:30],
                          "morceau": morceau, "media": x.get("media") if x.get("media") in videos else "",
                          "chiffre": _ecrit_juste(_propre(x.get("chiffre")))[:60],
                          "invites": ("avec " + ", ".join(p["invites"][:3])) if p["invites"] else ""})
        elif t == "voix":
            texte = _chiffres_dits(_ecrit_juste(_propre(re.sub(r"\[[^\]]*\]", "", str(x.get("texte") or "")))))
            if not texte:
                continue
            balise = re.match(r"\s*(\[[a-z ]{3,20}\])", str(x.get("voix") or ""))
            c = x.get("carte") if isinstance(x.get("carte"), dict) and str((x.get("carte") or {}).get("grand") or "").strip() else None
            b = {"type": "voix", "texte": texte[:260], "voix": ((balise.group(1) + " ") if balise else "") + _phonetique(texte)[:300],
                 "medias": [m for m in (x.get("medias") or []) if m in ids][:3],
                 "carte": {"grand": str(c["grand"]).strip()[:18].upper(), "petit": _ecrit_juste(str(c.get("petit") or ""))[:60],
                           "or": bool(c.get("or"))} if c else None}
            for cle, liste in (("mythe", les_mythes), ("contrat", les_contrats)):
                try:
                    n = int((x.get(cle) or {}).get("n"))
                    b[cle] = {k: v for k, v in liste[n].items() if k != "sources"}
                except (TypeError, ValueError, IndexError, AttributeError):
                    pass
            blocs.append(b)
    fin = next((i for i, b in enumerate(blocs) if b["type"] == "voix" and "prochain épisode" in b["texte"]), None)
    if fin is not None:
        blocs = blocs[:fin + 1]
    voix = [b for b in blocs if b["type"] == "voix"]
    if len(voix) < 25:
        raise RuntimeError("le récit écrit par l'IA est trop court pour un documentaire : relance le projet")
    voix[-1]["carte"] = None
    t = d.get("titre") or {}
    return {"v": 3, "titre": {"haut": str(t.get("haut") or "LA LÉGENDE DE").upper()[:16], "nom": str(t.get("nom") or donnees["artiste"]).upper()[:22],
                              "bas": _propre(t.get("bas")).upper()[:60]},
            "phrases": blocs[:120], "fin": {"titre": "TA LÉGENDE ?", "texte": "Écris-la en commentaire : prochain épisode"},
            "sources": donnees["_sources"][:300], "legende_fr": _propre(d.get("legende_fr"))[:900], "legende_en": _propre(d.get("legende_en"))[:900]}


# ---------------------------------------------------------------- fabrication

def _statique(video: str) -> bool:
    """Vidéo « audio » (pochette fixe) : presque aucun changement d'image sur 60 s."""
    total = _duree(video)
    r = subprocess.run([_ffmpeg(), "-v", "info", "-ss", f"{total * 0.25:.1f}", "-t", "60", "-i", video, "-vf",
                        "scale=160:-2,select='gt(scene,0.18)',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True)
    return len(re.findall(r"pts_time", r.stderr)) < 4


def _telecharge(m: dict, dossier: str) -> str | None:
    from core.services.social import refrain as RF
    if m["type"] == "photo":
        from core.services.social.raconte_v2 import _photo
        try:
            return _photo(m["url"], dossier, m["id"] + ".jpg")
        except Exception:  # noqa: BLE001
            return None
    v = RF.telecharge(m["yt"], dossier)
    if v:
        m["statique"] = _statique(v)
    return v


def _cadre(video: str) -> str | None:
    from core.services.social.studio_raconte import _cadre as c
    try:
        return c(video)
    except Exception:  # noqa: BLE001
        return None


def _plan(src: dict, dossier: str, nom: str, debut: float, long: float, style: str) -> None:
    """Un plan vertical 1080×1920 : « plein » (recadré) ou « cadre » (image entière sur le même plan flouté)."""
    cad = src.get("_cadre")
    pre = (cad + ",") if cad else ""
    if style == "plein":
        vf = f"{pre}scale=-2:1920,crop=1080:1920,fps=30,setsar=1"
    else:
        vf = (f"{pre}split[a][b];[a]scale=-2:1920,crop=1080:1920,boxblur=28:2,eq=brightness=-0.16:saturation=1.25[f];"
              f"[b]scale=1080:-2[v];[f][v]overlay=0:(H-h)/2-60,fps=30,setsar=1")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{debut:.2f}", "-i", src["_chemin"], "-t", f"{long + 0.2:.2f}", "-an",
                    "-filter_complex" if style != "plein" else "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                    "-pix_fmt", "yuv420p", os.path.join(dossier, nom)], check=True)


def _fond_photo(chemin: str, sortie: str) -> None:
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", chemin, "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:3,eq=brightness=-0.2:saturation=1.3",
                    "-q:v", "4", sortie], check=True)


def _musique(src: str, sortie: str, depuis: float, duree: float) -> None:
    """Extrait normalisé à −14 LUFS : toutes les musiques au même niveau, la voix reste devant."""
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0, depuis):.2f}", "-i", src, "-t", f"{duree + 1:.2f}", "-vn",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.5", "-ar", "44100", "-ac", "2", "-b:a", "192k", sortie], check=True)


def construit(job_id: int, p: dict, dossier: str, prefixe: str) -> dict:
    from core.services.social import refrain as RF
    from core.services.social.raconte_v2 import _photo, dit
    from core.services.social.studio_raconte import POSES, _sous_titres
    recit, blocs = p["recit"], p["recit"]["phrases"]
    medias = {m["id"]: dict(m) for m in p.get("medias") or []}
    # 1) toutes les images et musiques demandées par le récit (+ les plus vues pour l'accroche), en parallèle
    voulus = {i for b in blocs for i in (b.get("medias") or [])} | {b.get("musique") for b in blocs if b.get("musique")} | \
             {b.get("media") for b in blocs if b.get("media")}
    stars = [m["id"] for m in sorted((m for m in medias.values() if m["type"] != "photo"), key=lambda m: -(m.get("vues") or 0))[:6]]
    voulus |= set(stars)
    voulus = [i for i in voulus if i in medias]
    with ThreadPoolExecutor(3) as pool:
        for i, chemin in zip(voulus, pool.map(lambda i: _telecharge(medias[i], dossier), voulus)):
            medias[i]["_chemin"] = chemin
    prets = {i: m for i, m in medias.items() if m.get("_chemin")}
    videos_ok = [i for i, m in prets.items() if m["type"] != "photo" and not m.get("statique")]
    if len(videos_ok) < 3:
        raise RuntimeError("moins de 3 vidéos téléchargées : YouTube bloque peut-être ce PC, relance dans quelques heures")
    for i in videos_ok:
        prets[i]["_cadre"] = _cadre(prets[i]["_chemin"])
        prets[i]["_duree"] = _duree(prets[i]["_chemin"])
        prets[i]["_pris"] = 0
    for i, m in prets.items():
        if m["type"] == "photo":
            _fond_photo(m["_chemin"], os.path.join(dossier, f"{i}-fond.jpg"))

    # 2) la voix, en une prise par passage entre deux projets (même méthode que la v2)
    t, mots, morceaux, sfx, voix_bornes, projets, chapitres = 0.25, [], [], [], [], [], []
    passages, cur = [], []
    for b in blocs:
        if b.get("type") == "projet":
            if cur:
                passages.append(cur)
                cur = []
            passages.append(b)
        else:
            cur.append(b)
    if cur:
        passages.append(cur)
    k = 0
    for passage in passages:
        if isinstance(passage, dict):
            sfx.append({"src": SFX["montee"], "d": round(max(0, t - 1.6), 3), "vol": 0.2})
            projets.append({**passage, "d": round(t, 3), "f": round(t + DUREE_PROJET, 3)})
            sfx.append({"src": SFX["impact"], "d": round(t, 3), "vol": 0.32})
            t += DUREE_PROJET + 0.3
            continue
        dites = [b for b in passage if b.get("type") == "voix"]
        if not dites:
            continue
        textes = []
        for n, b in enumerate(dites):
            v = b.get("voix") or b["texte"]
            bal = re.match(r"\s*(\[[a-z ]{3,20}\])\s*", v)
            sans = v[bal.end():] if bal else v
            textes.append(((bal.group(1) + " ") if bal else "") + sans)   # v3 : chaque phrase garde son émotion (ton plus vivant)
        brut = os.path.join(dossier, f"v{k:02d}.mp3")
        memo = os.path.join(dossier, f"v{k:02d}.json")
        dits = None
        try:   # relance après un échec : la même prise n'est pas redemandée (caractères ElevenLabs comptés)
            m0 = json.load(open(memo, encoding="utf-8"))
            if m0.get("texte") == " ".join(textes) and os.path.isfile(brut):
                dits = m0["mots"]
        except (OSError, ValueError):
            pass
        if dits is None:
            dits = dit(" ".join(textes), brut)
            json.dump({"texte": " ".join(textes), "mots": dits}, open(memo, "w", encoding="utf-8"), ensure_ascii=False)
        mp3 = os.path.join(dossier, f"v{k:02d}n.mp3")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", brut, "-af", "loudnorm=I=-15:TP=-1.5:LRA=9", "-ar", "44100", "-ac", "2",
                        "-b:a", "192k", mp3], check=True)
        d = _duree(mp3)
        morceaux.append((t, mp3))
        pos, chap = 0, None
        for b, txt in zip(dites, textes):
            n_mots = len([m for m in re.sub(r"\[[^\]]*\]", " ", txt).split() if any(ch.isalnum() for ch in m)])
            part = dits[pos:pos + n_mots] or dits[-1:]
            pos += n_mots
            a = t + (part[0]["d"] if part else 0)
            z = t + (part[-1]["f"] if part else d)
            mots += _sous_titres(b["texte"], part, t, z - a)
            voix_bornes.append([a, z, b])
        for b in passage:
            if b.get("type") == "chapitre":
                chap = b
                continue
            if chap:
                a = next(x[0] for x in voix_bornes if x[2] is b)
                cd0 = max(a - 0.1, 3.8)
                chapitres.append({"d": round(cd0, 3), "f": round(cd0 + 2.6, 3), "numero": chap.get("numero") or "", "titre": chap["titre"],
                                  "annees": chap.get("annees") or "", "musique": chap.get("musique") or ""})
                sfx.append({"src": SFX["chapitre"], "d": round(cd0, 3), "vol": 0.26})
                chap = None
        t += d + PAUSE
        k += 1
    fin_voix = t - PAUSE
    duree = round(fin_voix + 3.6, 2)
    fin_d = voix_bornes[-1][0]
    for i, x in enumerate(voix_bornes):   # chaque phrase occupe l'écran jusqu'à la suivante
        x[1] = voix_bornes[i + 1][0] if i + 1 < len(voix_bornes) and voix_bornes[i + 1][0] - x[1] < 2 else x[1] + PAUSE
    entrees = []
    for _, chemin in morceaux:
        entrees += ["-i", chemin]
    filtres = "".join(f"[{j}:a]adelay={int(d0 * 1000)}|{int(d0 * 1000)}[a{j}];" for j, (d0, _) in enumerate(morceaux))
    filtres += "".join(f"[a{j}]" for j in range(len(morceaux))) + f"amix=inputs={len(morceaux)}:normalize=0,apad=whole_dur={duree}[out]"
    subprocess.run([_ffmpeg(), "-v", "error", "-y", *entrees, "-filter_complex", filtres, "-map", "[out]", "-t", f"{duree}", "-ar", "44100",
                    "-ac", "2", "-b:a", "192k", os.path.join(dossier, "voix.mp3")], check=True)

    # 3) les plans : chaque phrase montre ses médias, coupés court ; l'accroche en plans éclair sur ses vidéos les plus vues
    n_plan = [0]
    styles = ["plein", "plein", "cadre"]

    def coupe(mid: str, a: float, b: float) -> dict | None:
        m = prets.get(mid)
        if not m or b - a < 0.3:
            return None
        nom = f"p{n_plan[0]:03d}"
        n_plan[0] += 1
        if m["type"] == "photo":
            return {"src": f"{prefixe}/{os.path.basename(m['_chemin'])}", "fond": f"{prefixe}/{mid}-fond.jpg", "d": round(a, 3), "f": round(b, 3),
                    "image": True, "annee": m.get("annee") or "", "credit": m.get("credit") or ""}
        if mid not in videos_ok:
            return None
        ratio = 0.1 + (0.78 * ((m["_pris"] * 0.381966 + hash(mid) % 7 * 0.07) % 1))
        m["_pris"] += 1
        if "_haut" not in m:   # vieux clips en 240-480p : jamais agrandis plein cadre (flous), toujours en cadre 16:9
            out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0", m["_chemin"]],
                                 capture_output=True, text=True).stdout
            m["_haut"] = int((re.search(r"\d+", out or "") or [0])[0] or 0)
        style = styles[n_plan[0] % 3] if m["type"] != "live" and m["_haut"] >= 700 else "cadre"
        _plan(m, dossier, nom + ".mp4", m["_duree"] * ratio, b - a, style)
        return {"src": f"{prefixe}/{nom}.mp4", "d": round(a, 3), "f": round(b, 3),
                "annee": m.get("annee") if m["type"] != "clip" else "", "libelle": {"live": "LIVE", "coulisses": "COULISSES"}.get(m["type"], "")}

    occupe_projets = [(x["d"], x["f"]) for x in projets]
    les_plans, flashs = [], []
    stars_ok = [i for i in stars if i in videos_ok] or videos_ok[:4]
    accroche_fin = chapitres[0]["d"] if chapitres else 6.0
    t0, j = 0.0, 0
    while t0 < accroche_fin - 0.2:
        long = 0.55 if t0 < 3.6 else 0.9
        c = coupe(stars_ok[j % len(stars_ok)], t0, min(t0 + long, accroche_fin))
        if c:
            les_plans.append(c)
            flashs.append(round(t0, 3))
        t0 += long
        j += 1
    derniers = [m for m in videos_ok]
    rot = [0]
    for a, z, b in voix_bornes:
        if a < accroche_fin - 0.05 or b is voix_bornes[-1][2]:
            continue
        ids = [i for i in (b.get("medias") or []) if i in prets and (prets[i]["type"] == "photo" or i in videos_ok)]
        if not ids:   # rien de prêt : une vidéo de l'époque la plus proche, à tour de rôle
            ids = [derniers[rot[0] % len(derniers)]]
            rot[0] += 1
        cur, n = a, 0
        while cur < z - 0.25:
            mid = ids[n % len(ids)]
            long = 2.6 if prets[mid]["type"] == "photo" else (1.7 if n % 2 else 2.3)
            fin = min(cur + long, z)
            if z - fin < 0.9:
                fin = z
            if not any(x <= cur < y for x, y in occupe_projets):
                c = coupe(mid, cur, fin)
                if c:
                    les_plans.append(c)
            cur, n = fin, n + 1
    # fin : la meilleure photo, sinon le clip le plus vu
    photo = _photo(p.get("photo"), dossier, "photo.jpg") if p.get("photo") else None
    if photo:
        _fond_photo(photo, os.path.join(dossier, "photo-fond.jpg"))
        les_plans.append({"src": f"{prefixe}/photo.jpg", "fond": f"{prefixe}/photo-fond.jpg", "d": round(fin_d, 3), "f": duree, "image": True})
    else:
        c = coupe(stars_ok[0], fin_d, duree)
        if c:
            les_plans.append(c)

    # 4) musiques : chaque chapitre a la sienne (changée toutes les 40 s au plus), les projets à plein volume
    def extrait(mid: str, nom: str, long: float) -> str | None:
        m = prets.get(mid)
        if not m or m["type"] == "photo":
            return None
        try:
            r0, _ = RF.refrain(m["_chemin"], duree=min(long, 30))
        except Exception:  # noqa: BLE001
            r0 = m.get("_duree", _duree(m["_chemin"])) * 0.3
        _musique(m["_chemin"], os.path.join(dossier, nom), r0 - 1.0, long)
        return f"{prefixe}/{nom}"

    musiques, n_mus = [], [0]
    pool_musique = [i for i in sorted(prets, key=lambda i: -(prets[i].get("vues") or 0)) if prets[i]["type"] != "photo"]

    def bed(mid: str, a: float, b: float):
        """Fond musical de a à b, en tranches de 40 s au plus (la tranche suivante prend un autre titre de l'époque)."""
        cur = a
        while cur < b - 0.5:
            fin = min(b, cur + SEGMENT_MAX)
            if b - fin < 8:
                fin = b
            src = extrait(mid, f"m{n_mus[0]:02d}.mp3", fin - cur)
            n_mus[0] += 1
            if src:
                musiques.append({"src": src, "d": round(cur, 3), "f": round(fin, 3), "depuis": 0})
            autres = [x for x in pool_musique if x != mid and not any(mm.get("_mid") == x for mm in musiques[-3:])]
            if musiques:
                musiques[-1]["_mid"] = mid
            mid = autres[n_mus[0] % len(autres)] if autres else mid
            cur = fin

    bornes = [0.0] + [c["d"] for c in chapitres] + [duree]
    choix = [stars_ok[0]] + [c.get("musique") or pool_musique[(n + 1) % len(pool_musique)] for n, c in enumerate(chapitres)]
    for n in range(len(bornes) - 1):
        a, b = bornes[n], bornes[n + 1]
        trous, cur = [], a
        for pr in projets:
            if a <= pr["d"] < b:
                trous.append((cur, pr["d"]))
                cur = pr["f"]
        trous.append((cur, b))
        for (x, y) in trous:
            if y - x > 0.5:
                bed(choix[n] if choix[n] in prets else pool_musique[0], x, y)
    for j2, pr in enumerate(projets):
        mid = pr.get("media") if pr.get("media") in prets else None
        if not mid:
            from core.services.social.raconte_v2 import video_morceau
            v = video_morceau(int(p["artiste_id"]), p.get("artiste") or "", pr.get("morceau") or pr["titre"], dossier)
            if v:
                mid = f"proj{j2}"
                prets[mid] = {"type": "clip", "_chemin": v, "_duree": _duree(v)}
        src = extrait(mid, f"proj{j2}.mp3", DUREE_PROJET + 1) if mid else None
        if src:
            musiques.append({"src": src, "d": pr["d"], "f": pr["f"], "depuis": 0, "plein": True})
        cover = _photo(pr.get("cover"), dossier, f"cover{j2}.jpg") if pr.get("cover") else None
        pr["cover"] = f"{prefixe}/cover{j2}.jpg" if cover else "raconte/logo.png"
    for mm in musiques:
        mm.pop("_mid", None)

    # 5) cartes, mythes, contrats, calés sur leur phrase
    cartes, les_mythes, les_contrats = [], [], []
    for a, z, b in voix_bornes:
        if b is voix_bornes[-1][2] or a < 3.8:
            continue
        if b.get("mythe"):
            m = b["mythe"]
            suivante = next((x for x in voix_bornes if x[0] > a + 0.01), None)
            fin_m = (suivante[1] if suivante else z) + 0.2
            verdict = suivante[0] if suivante else z   # le tampon tombe quand la voix donne la réponse
            les_mythes.append({"d": round(a, 3), "f": round(min(fin_m, a + 11), 3), "v": round(verdict, 3),
                               "affirmation": m.get("affirmation") or "", "verdict": m.get("verdict") or "VRAI"})
            sfx.append({"src": SFX["carte"], "d": round(a, 3), "vol": 0.2})
            sfx.append({"src": SFX["impact"], "d": round(verdict, 3), "vol": 0.3})
        elif b.get("contrat"):
            c = b["contrat"]
            eq = c.get("equivalents") or {}
            quoi = re.split(r"\s*[/(]", c.get("quoi") or "")[0].strip()   # « Contrat de partenariat / Ambassadeur (…) » -> court
            les_contrats.append({"d": round(a, 3), "f": round(max(z, a + 3.2), 3), "quoi": quoi[:48], "avec": re.split(r"\s*\(", c.get("avec") or "")[0][:40],
                                 "annee": c.get("annee") or "", "montant": eq.get("usd") or "",
                                 "devises": [x for x in (eq.get("ngn"), eq.get("xof")) if x]})
            sfx.append({"src": SFX["carte"], "d": round(a, 3), "vol": 0.18})
        elif b.get("carte"):
            c = b["carte"]
            cartes.append({"d": round(a + 0.12, 3), "f": round(min(max(z, a + 1.8), a + 4.4), 3), "grand": c["grand"], "petit": c.get("petit") or "",
                           "or": bool(c.get("or"))})
            sfx.append({"src": SFX["carte"], "d": round(a + 0.12, 3), "vol": 0.16})
    sfx.append({"src": SFX["fin"], "d": round(max(0, fin_d - 0.6), 3), "vol": 0.24})
    # jauge des secrets (idée du fondateur, 15/11) : un cauri par mythe tranché ou « Le savais-tu ? » dévoilé
    jauge = sorted({m["v"] for m in les_mythes} | {round(a + 0.3, 3) for a, z, b in voix_bornes
                                                   if re.match(r"\s*le savais[- ]tu", b.get("texte") or "", re.I) and a > 3.8})
    jauge = [x for i, x in enumerate(jauge) if i == 0 or x - jauge[i - 1] > 3.2][:8]
    for x in jauge:
        sfx.append({"src": SFX["sortie"], "d": round(x, 3), "vol": 0.22})

    # 6) mascotte : quelques apparitions (jamais sur une carte, un mythe ou un projet)
    occupe = [(x["d"] - 0.3, x["f"]) for x in cartes + les_mythes + les_contrats] + [(x["d"] - 0.5, x["f"] + 0.5) for x in projets]
    mascottes = []
    for pose, r, cote in (("presente", 0.12, "droite"), ("surpris", 0.4, "gauche"), ("presente", 0.68, "droite"), ("surpris", 0.88, "gauche")):
        cible = fin_d * r
        for (a, z, _) in voix_bornes:
            if a >= cible and not any(x <= a <= y or x <= a + 3 <= y for x, y in occupe) and a + 3.2 < fin_d:
                mascottes.append({"src": POSES[pose], "d": round(a, 3), "f": round(a + 3.2, 3), "cote": cote, "h": 860})
                occupe.append((a, a + 3.2))
                break
    mascottes.append({"src": POSES["appel"], "d": round(fin_d + 0.3, 3), "f": duree, "cote": "gauche", "h": 820})
    return {"voix": f"{prefixe}/voix.mp3", "musique": musiques[0]["src"] if musiques else f"{prefixe}/voix.mp3", "duree": duree, "mots": mots,
            "titre": recit["titre"], "plans": les_plans, "cartes": cartes, "mascottes": mascottes, "musiques": musiques, "fond": FOND,
            "projets": [{k2: x[k2] for k2 in ("d", "f", "cover", "titre", "etiquette", "invites", "chiffre", "morceau") if x.get(k2) is not None}
                        for x in projets],
            "chapitres": [{k2: c[k2] for k2 in ("d", "f", "numero", "titre", "annees")} for c in chapitres], "sfx": sfx,
            "mythes": les_mythes, "contrats": les_contrats, "flashs": flashs, "sansBarre": True, "jauge": jauge,
            "fin": {"d": round(fin_d, 3), "titre": recit["fin"]["titre"], "texte": recit["fin"]["texte"]}, "sources": recit.get("sources") or ""}
