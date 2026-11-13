"""« Cauri raconte » v2 (13/11/2026) — retours du fondateur sur Asake v1 : « trop générique, pas assez dans l'univers de
l'artiste, accent pas vraiment français, fade, plat, sans ambiance ni mouvement ; présenter ses projets 10 à 15 s ».

- Dossier de l'artiste : discographie Deezer (albums, EP, invités, titres phares, pochettes), écoutes Spotify de chaque
  titre (Kworb), article Wikipédia complet (débuts, carrière), en plus des chiffres de la v1.
- Récit en blocs : chapitres, phrases dites (avec balises d'émotion ElevenLabs v3), projets présentés en musique.
- Voix : Guillou-Martial (ElevenLabs, accent africain, jeune ; choisie par le fondateur le 13/11), un peu accélérée.
- Montage : chaque projet = pochette en 3D + son titre phare à plein volume pendant 12 s ; ensuite, sa musique reste
  sous la voix et ses images deviennent celles de l'époque ; bruitages (montée, impact, souffles) aux transitions.
"""
import base64
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request

from core import db, env
from core.services.platforms import log_write

VOIX_EL = "IoJlyfNV7PnlZKiAVm4M"      # Guillou-Martial (Ali-Alioum 0A3E10Jixa9t7sGTSjr7, Tony-Punchy fsYODoWLWYJ5ai6CAN3M en réserve)
MODELE_EL = "eleven_v3"
ACCEL = 1.08                           # « plus rapide » : sans changer le timbre (atempo)
DUREE_PROJET = 12.0
PAUSE = 0.22
SFX = {"chapitre": "raconte/sfx/swoosh-cine.mp3", "carte": "raconte/sfx/whoosh-fast.mp3", "montee": "raconte/sfx/riser-drama.mp3",
       "impact": "raconte/sfx/impact-big.mp3", "fin": "raconte/sfx/reverse-impact.mp3", "sortie": "raconte/sfx/sparkle-whoosh.mp3"}
EXCLUS = re.compile(r"\b(live|sped up|slowed|remix|instrumental|acoustic|version|deluxe edition)\b", re.I)

SYSTEME = """Tu écris le récit d'une vidéo verticale « Cauri raconte » (environ 1 min 45) sur un artiste, pour Cauri Charts,
« la référence de la musique ouest-africaine ». Le fondateur veut qu'on « ressente le travail bien fait sur son histoire » :
un vrai récit documentaire, plongé dans l'univers de l'artiste (son quartier, ses débuts, ses influences, ses rencontres, le
déclic, chaque projet et ce qu'il a changé), raconté avec énergie par une voix jeune.

Le récit est une suite de BLOCS, de trois sortes :
- {"type": "chapitre", "numero": "CHAPITRE 1", "titre": "LAGOS"} : 3 ou 4 chapitres, titre en 1 à 3 mots en capitales.
- {"type": "voix", "texte": "...", "voix": "...", "carte": null ou {"grand": "...", "petit": "...", "or": false}} : 1 à 2 phrases
  courtes, orales, en français normal. « voix » = UNIQUEMENT une balise d'émotion pour la voix, choisie parmi [excited]
  [mysterious] [whispers] [confident] [laughs] [sighs] [curious] [serious] (ou "" si neutre) ; jamais de phonétique (la voix
  est française ; la prononciation des noms est gérée ailleurs). Le « texte » n'a jamais de balise.
- {"type": "projet", "album_id": 123, "etiquette": "1ER ALBUM · 2022", "morceau": "titre", "chiffre": "..."} : un de ses
  projets, présenté en musique (on entend son titre phare 12 secondes). 2 à 4 projets, pris dans « discographie » (album_id
  exact), « morceau » = un de ses « titres_phares » (orthographe exacte), « chiffre » = un chiffre vrai sur ce projet ou ce
  morceau tiré des données (écoutes Spotify…), sinon "". Le bloc « voix » juste avant un projet l'annonce (« Et là… »).

Exemple du TON attendu (un autre artiste, faits inventés pour l'exemple seulement — n'en reprends rien) :
{"type": "voix", "texte": "Lomé, 2015. Un gamin rappe dans la cour de sa grand-mère, un vieux micro scotché à un balai.", "voix": "[mysterious]"}
{"type": "voix", "texte": "Personne ne le prend au sérieux. Sauf un homme.", "voix": "[whispers]"}
{"type": "voix", "texte": "Et ce jour-là, tout bascule.", "voix": "[excited]"}
Chaque bloc fait avancer l'histoire (cause, conséquence, tension, surprise). Jamais de liste façon fiche (« 2018 : … ; 2019 : … »),
jamais un bloc creux du genre « Et là… » seul : la phrase qui annonce un projet dit ce qu'il représente (« Septembre 2022 : son
premier album. Celui qui va tout changer. »). Une balise d'émotion sur au moins un bloc voix sur deux, variée.

Règles absolues :
- UNIQUEMENT les faits fournis (Wikipédia, discographie, chiffres, faits vérifiés). Aucune date, chiffre, lieu, salle, record,
  citation ou nuance (« d'affilée », « le premier », « domine ») absents des données. Jamais « Billboard » (dis « le classement
  américain »). Jamais « le plus grand de tous ».
- Construction : accroche-question forte (1er bloc voix, moins de 12 mots) ; chapitre 1 = d'où il vient et ses débuts ;
  le déclic ; les projets dans l'ordre chronologique ; « Le savais-tu ? » + un fait peu connu ; où il en est aujourd'hui (nos
  classements, ses chiffres) ; « La leçon : » en une phrase ; dernier bloc voix exact : « Et toi, qui mérite le prochain épisode ?
  Dis-le en commentaire. »
- EXACTEMENT 4 chapitres (débuts / déclic / les projets / aujourd'hui), AU MOINS 18 blocs voix, 220 à 270 mots dits en tout. Rythme rapide, phrases vivantes, présent de narration.
- 4 à 6 cartes (grand = chiffre court ou 1 à 3 mots en capitales, petit < 45 caractères), or=true pour les 2 plus fortes ;
  jamais sur le 1er ni le dernier bloc voix.
- titre : haut (« COMMENT » ou « POURQUOI »), nom (l'artiste en capitales), bas (fin de la question d'accroche, < 45 caractères).
- legende_fr : 2 à 3 phrases avec une question aux abonnés ; legende_en : sa traduction.
Réponds en JSON strict : {"titre": {"haut": "", "nom": "", "bas": ""}, "blocs": [...], "legende_fr": "", "legende_en": ""}"""


# ---------------------------------------------------------------- dossier de l'artiste

def _cle(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\s*[\(\[].*?[\)\]]", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _deezer(chemin: str):
    with urllib.request.urlopen("https://api.deezer.com/" + chemin, timeout=20) as r:
        return json.load(r)


def _n(v) -> str:
    from core.services.social.studio_raconte import _n as n
    return n(v)


def discographie(nom: str, ecoutes: dict) -> dict:
    """Albums et EP (Deezer) avec date, pochette, invités et titres phares (+ écoutes Spotify) ; singles marquants."""
    trouve = [a for a in (_deezer("search/artist?q=" + urllib.parse.quote(nom)).get("data") or []) if _cle(a["name"]) == _cle(nom)]
    if not trouve:
        return {"projets": [], "singles": []}
    aid = trouve[0]["id"]
    tout = _deezer(f"artist/{aid}/albums?limit=100").get("data") or []
    projets, singles = [], []
    for x in sorted(tout, key=lambda x: x.get("release_date") or ""):
        if EXCLUS.search(x["title"]):
            continue
        if x.get("record_type") in ("album", "ep") and len(projets) < 8:
            try:
                al = _deezer(f"album/{x['id']}")
            except Exception:  # noqa: BLE001
                continue
            pistes = (al.get("tracks") or {}).get("data") or []
            invites = sorted({c["name"] for c in al.get("contributors") or [] if _cle(c["name"]) != _cle(nom)})
            for p in pistes:
                for m in re.findall(r"(?:feat\.?|ft\.?|with)\s+([^\)\]]+)", p.get("title") or "", re.I):
                    invites += [y.strip() for y in re.split(r",|&| x | and ", m) if y.strip() and _cle(y) != _cle(nom)]
            phares = sorted(pistes, key=lambda p: -(p.get("rank") or 0))[:4]
            projets.append({"album_id": x["id"], "titre": x["title"], "type": x["record_type"], "date": x.get("release_date"),
                            "cover": al.get("cover_xl") or x.get("cover_xl"), "nb_titres": al.get("nb_tracks"),
                            "invites": list(dict.fromkeys(invites))[:8],
                            "titres_phares": [{"titre": p["title"], **({"ecoutes_spotify": _n(ecoutes[_cle(p["title"])])} if _cle(p["title"]) in ecoutes else {})}
                                              for p in phares]})
        elif x.get("record_type") == "single":
            singles.append({"titre": x["title"], "date": x.get("release_date"), "fans_deezer": x.get("fans") or 0,
                            **({"ecoutes_spotify": _n(ecoutes[_cle(x["title"])])} if _cle(x["title"]) in ecoutes else {})})
    singles = sorted(singles, key=lambda s: -s["fans_deezer"])[:8]
    for s in singles:
        s.pop("fans_deezer", None)
    return {"projets": projets, "singles_marquants": sorted(singles, key=lambda s: s["date"] or "")}


def wikipedia(nom: str, qid: str | None) -> str | None:
    """L'article Wikipédia complet (anglais : plus détaillé), sans discographie ni références, 7 000 caractères au plus."""
    titre = None
    if qid:
        try:
            with urllib.request.urlopen(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", timeout=20) as r:
                liens = json.load(r)["entities"][qid].get("sitelinks") or {}
            titre = (liens.get("enwiki") or {}).get("title")
        except Exception:  # noqa: BLE001
            titre = None
    titre = titre or nom
    try:
        q = urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "format": "json", "titles": titre})
        req = urllib.request.Request("https://en.wikipedia.org/w/api.php?" + q, headers={"User-Agent": "CauriCharts/1.0 (cauricharts.com)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            pages = list((json.load(r).get("query") or {}).get("pages", {}).values())
        texte = str((pages[0] if pages else {}).get("extract") or "")
    except Exception:  # noqa: BLE001
        return None
    texte = re.split(r"\n==\s*(Discography|References|External links|Filmography|Tours|See also)\s*==", texte)[0]
    texte = re.sub(r"\n+", "\n", texte).strip()
    return texte[:7000] or None


def dossier(artist_id: int, angle: str = "") -> dict:
    """Les données de la v1 + la discographie détaillée + l'article Wikipédia complet."""
    from core.services import kworb
    from core.services.social import portrait
    from core.services.social.studio_raconte import _propre, recherche
    d = recherche(artist_id, angle)
    a = portrait.artiste(artist_id)
    ecoutes = {}
    try:
        k = kworb.chiffres(a.get("spotify_id"), 300) or {}
        ecoutes = {_cle(t["titre"]): t["streams"] for t in k.get("titres") or []}
    except Exception:  # noqa: BLE001
        pass
    try:
        d["discographie"] = discographie(a["name"], ecoutes)
    except Exception as exc:  # noqa: BLE001
        log_write("studio", "warning", f"raconte : discographie Deezer indisponible ({exc})")
        d["discographie"] = {"projets": [], "singles_marquants": []}
    qid = portrait.wikidata_id(a["name"], a["country"])
    wp = wikipedia(a["name"], qid)
    if wp:
        d["article_wikipedia"] = _propre(wp)
        d.pop("biographie_wikipedia", None)
    if d["discographie"]["projets"]:
        d["_sources"] = d["_sources"].replace("Sources : ", "Sources : Deezer · ", 1)
    return d


# ---------------------------------------------------------------- écriture

def ecrit(donnees: dict) -> dict:
    from core.services import ai
    from core.services.platforms import HttpClient
    from core.services.social.studio_raconte import _chiffres_dits, _ecrit_juste, _phonetique, _propre
    client = ai.FallbackClient([ai.GeminiClient(HttpClient(180))] + [c for c in [ai.make()] if c])
    if not client.is_available():
        raise RuntimeError("aucune IA configurée pour écrire le récit")
    publiques = json.dumps({k: v for k, v in donnees.items() if not k.startswith("_")}, ensure_ascii=False, indent=1)
    os.environ["GEMINI_REFLEXION"] = "high"   # récit long et précis : Gemini réfléchit vraiment (le reste reste en « minimal »)
    try:
        d = ai.extract_json(client.ask(SYSTEME, "Données vérifiées (n'utilise rien d'autre) :\n" + publiques, 8000)["text"]) or {}
    finally:
        os.environ.pop("GEMINI_REFLEXION", None)
    try:
        v = client.ask("Tu es vérificateur des faits d'un média musical. Tu compares un récit aux données, bloc par bloc.",
                       "Données (seule vérité) :\n" + publiques + "\n\nRécit :\n" + json.dumps(d, ensure_ascii=False)
                       + "\n\nToute affirmation absente des données, exagérée ou contraire (années, lieux, salles, nombres, « N°1 », "
                       "« record », « premier », « domine », « d'affilée »…) doit être corrigée pour coller aux données, ou retirée. "
                       "Vérifie que chaque album_id existe dans la discographie et que chaque « morceau » est un de ses titres_phares. "
                       "Garde le ton, les balises d'émotion et la construction. Rends le même JSON corrigé, rien d'autre.", 6000)
        d2 = ai.extract_json(v["text"]) or {}
        if len(d2.get("blocs") or []) >= 10:
            d = d2
    except Exception as exc:  # noqa: BLE001
        log_write("studio", "warning", f"raconte : relecture des faits indisponible ({exc})")
    projets = {p["album_id"]: p for p in donnees.get("discographie", {}).get("projets", [])}
    blocs = []
    for x in d.get("blocs") or []:
        t = x.get("type")
        if t == "chapitre" and str(x.get("titre") or "").strip():
            blocs.append({"type": "chapitre", "numero": str(x.get("numero") or "").upper()[:20], "titre": _propre(x["titre"]).upper()[:28]})
        elif t == "projet":
            try:
                p = projets[int(x.get("album_id"))]
            except (TypeError, ValueError, KeyError):
                continue
            phares = [m["titre"] for m in p["titres_phares"]]
            morceau = next((m for m in phares if _cle(m) == _cle(x.get("morceau"))), phares[0] if phares else "")
            blocs.append({"type": "projet", "album_id": p["album_id"], "titre": p["titre"], "cover": p["cover"],
                          "etiquette": _propre(x.get("etiquette") or f"{p['type'].upper()} · {(p['date'] or '')[:4]}").upper()[:30],
                          "morceau": morceau, "chiffre": _ecrit_juste(_propre(x.get("chiffre")))[:60],
                          "invites": ("avec " + ", ".join(p["invites"][:3])) if p["invites"] else ""})
        elif t == "voix":
            texte = _chiffres_dits(_ecrit_juste(_propre(re.sub(r"\[[^\]]*\]", "", str(x.get("texte") or "")))))
            if not texte:
                continue
            balise = re.match(r"\s*(\[[a-z ]{3,20}\])", str(x.get("voix") or ""))
            voix = (balise.group(1) + " " if balise else "") + _phonetique(texte)
            c = x.get("carte") if isinstance(x.get("carte"), dict) and str((x.get("carte") or {}).get("grand") or "").strip() else None
            blocs.append({"type": "voix", "texte": texte[:260], "voix": voix[:300],
                          "carte": {"grand": str(c["grand"]).strip()[:18].upper(), "petit": _ecrit_juste(str(c.get("petit") or ""))[:60],
                                    "or": bool(c.get("or"))} if c else None})
    # l'appel final clôt la vidéo : rien après lui
    fin = next((i for i, b in enumerate(blocs) if b["type"] == "voix" and "prochain épisode" in b["texte"]), None)
    if fin is not None:
        blocs = blocs[:fin + 1]
    voix = [b for b in blocs if b["type"] == "voix"]
    if len(voix) < 8:
        raise RuntimeError("le récit écrit par l'IA est trop court : relance le projet")
    voix[0]["carte"] = voix[-1]["carte"] = None
    t = d.get("titre") or {}
    return {"v": 2, "titre": {"haut": str(t.get("haut") or "COMMENT").upper()[:14], "nom": str(t.get("nom") or donnees["artiste"]).upper()[:22],
                              "bas": _propre(t.get("bas")).upper()[:60]},
            "phrases": blocs[:40], "fin": {"titre": "TON ARTISTE ?", "texte": "Écris-le en commentaire : prochain épisode"},
            "sources": donnees["_sources"][:220], "legende_fr": _propre(d.get("legende_fr"))[:900], "legende_en": _propre(d.get("legende_en"))[:900]}


# ---------------------------------------------------------------- voix (ElevenLabs)

def _ffmpeg() -> str:
    from core.services.social.studio_montage import ffmpeg
    return ffmpeg()


def _duree(chemin: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", chemin], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def dit(texte: str, sortie: str) -> list[dict]:
    """Un bloc dit par Guillou-Martial : mp3 accéléré + mots minutés (balises d'émotion retirées du minutage)."""
    cle = env.get("ELEVENLABS_API_KEY", "")
    if not cle:
        raise RuntimeError("ELEVENLABS_API_KEY absente")
    corps = {"text": texte, "model_id": MODELE_EL, "language_code": "fr"}
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOIX_EL}/with-timestamps?output_format=mp3_44100_128",
                                 data=json.dumps(corps).encode(), headers={"xi-api-key": cle, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    brut = sortie + ".brut.mp3"
    open(brut, "wb").write(base64.b64decode(d["audio_base64"]))
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", brut, "-af", f"atempo={ACCEL}", "-ar", "44100", "-ac", "2", "-b:a", "192k", sortie], check=True)
    al = d.get("normalized_alignment") or d["alignment"]
    mots, cur, d0, f0, crochet = [], "", None, None, False
    for c, s, e in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if c == "[":
            crochet = True
        if crochet:
            crochet = c != "]"
            continue
        if c.isspace():
            if cur.strip():
                mots.append({"m": cur, "d": d0 / ACCEL, "f": f0 / ACCEL})
            cur, d0 = "", None
            continue
        if d0 is None:
            d0 = s
        cur, f0 = cur + c, e
    if cur.strip():
        mots.append({"m": cur, "d": d0 / ACCEL, "f": f0 / ACCEL})
    return [m for m in mots if any(ch.isalnum() for ch in m["m"])]


# ---------------------------------------------------------------- images et musiques des projets

def video_morceau(artist_id: int, artiste: str, titre: str, dossier: str) -> str | None:
    """Le clip officiel du morceau (base), sinon la 1re vidéo YouTube « artiste titre official »."""
    from core.services.social import refrain as RF
    for r in db.all("""SELECT tpi.external_id, t.title FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id
                       WHERE t.artist_id = ? AND tpi.platform = 'youtube' AND tpi.is_official = 1 AND tpi.kind = 'clip'""", [artist_id]):
        if _cle(r["title"]) == _cle(titre):
            v = RF.telecharge(r["external_id"], dossier)
            if v:
                return v
    sortie = os.path.join(dossier, "yt-" + _cle(titre)[:30] + ".mp4")
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-playlist", "-q", "--no-warnings", "-f", "bv*+ba/b",
           "-S", "res:1080,br", "--merge-output-format", "mp4", "-o", sortie, f"ytsearch1:{artiste} {titre} official video"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("studio", "warning", f"raconte : vidéo de « {titre} » introuvable ({str(exc)[:200]})")
        return None
    return sortie if os.path.isfile(sortie) else None


def _photo(url: str | None, dossier: str, nom: str) -> str | None:
    from core.services.social.studio_raconte import _image
    corps = _image(url)
    if not corps:
        return None
    brut = os.path.join(dossier, nom + ".src")
    open(brut, "wb").write(corps)
    chemin = os.path.join(dossier, nom)
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", brut, "-vf", "scale='min(1600,iw)':-2", chemin], check=True)
    return chemin


# ---------------------------------------------------------------- montage

def construit(job_id: int, p: dict, dossier: str, prefixe: str) -> dict:
    from core.services.social import refrain as RF
    from core.services.social.studio_raconte import POSES, _sous_titres, clips, plans
    recit, aid = p["recit"], int(p["artiste_id"])
    blocs = recit["phrases"]
    t, mots, morceaux, chapitres, projets, cartes, sfx, voix_bornes = 0.1, [], [], [], [], [], [], []
    chap_attente, k = None, 0
    # 1) la voix et la ligne du temps
    for i, b in enumerate(blocs):
        if b.get("type") == "chapitre":
            chap_attente = b
            continue
        if b.get("type") == "projet":
            if voix_bornes:
                sfx.append({"src": SFX["montee"], "d": round(max(0, t - 1.8), 3), "vol": 0.35})
            projets.append({**b, "d": round(t, 3), "f": round(t + DUREE_PROJET, 3)})
            sfx.append({"src": SFX["impact"], "d": round(t, 3), "vol": 0.5})
            t += DUREE_PROJET + 0.35
            continue
        mp3 = os.path.join(dossier, f"v{k:02d}.mp3")
        dits = dit(b.get("voix") or b["texte"], mp3)
        d = _duree(mp3)
        mots += _sous_titres(b["texte"], dits, t, d)
        morceaux.append((t, mp3))
        voix_bornes.append((t, t + d, b))
        if chap_attente:   # jamais sur le titre d'ouverture (0 à 3,6 s)
            cd0 = max(t, 3.7)
            chapitres.append({"d": round(cd0, 3), "f": round(cd0 + 2.4, 3), "numero": chap_attente.get("numero") or "", "titre": chap_attente["titre"]})
            sfx.append({"src": SFX["chapitre"], "d": round(cd0, 3), "vol": 0.45})
            chap_attente = None
        c = b.get("carte")
        if c and k > 0 and i < len(blocs) - 1:
            cd = t + 0.15
            cartes.append({"d": round(cd, 3), "f": round(min(max(t + d + 0.25, cd + 1.6), cd + 4.2), 3), "grand": c["grand"], "petit": c.get("petit") or "",
                           "or": bool(c.get("or"))})
            sfx.append({"src": SFX["carte"], "d": round(cd, 3), "vol": 0.3})
        t += d + PAUSE
        k += 1
    fin_voix = t - PAUSE
    duree = round(fin_voix + 3.4, 2)
    fin_d = voix_bornes[-1][0]
    sfx.append({"src": SFX["fin"], "d": round(max(0, fin_d - 0.6), 3), "vol": 0.4})
    # voix.mp3 : chaque bloc à sa place (silences pendant les projets)
    entrees = []
    for j, (d0, chemin) in enumerate(morceaux):
        entrees += ["-i", chemin]
    filtres = "".join(f"[{j}:a]adelay={int(d0 * 1000)}|{int(d0 * 1000)}[a{j}];" for j, (d0, _) in enumerate(morceaux))
    filtres += "".join(f"[a{j}]" for j in range(len(morceaux))) + f"amix=inputs={len(morceaux)}:normalize=0,apad=whole_dur={duree}[out]"
    subprocess.run([_ffmpeg(), "-v", "error", "-y", *entrees, "-filter_complex", filtres, "-map", "[out]", "-t", f"{duree}", "-ar", "44100",
                    "-ac", "2", "-b:a", "192k", os.path.join(dossier, "voix.mp3")], check=True)
    # 2) projets : pochette, clip du titre phare, son au refrain
    epoques = []          # (début, sources d'images de l'époque)
    musiques = []
    base = [s for s in (RF.telecharge(v, dossier) for v in clips(aid, 2)) if s]
    for j, pr in enumerate(projets):
        cover = _photo(pr.get("cover"), dossier, f"cover{j}.jpg")
        pr["cover"] = f"{prefixe}/cover{j}.jpg" if cover else "raconte/logo.png"
        v = video_morceau(aid, p.get("artiste") or "", pr.get("morceau") or pr["titre"], dossier)
        if not v:
            continue
        try:
            t0, _ = RF.refrain(v, duree=DUREE_PROJET)
        except Exception:  # noqa: BLE001
            t0 = _duree(v) * 0.3
        son = os.path.join(dossier, f"m{j}.mp3")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0, t0 - 0.5):.2f}", "-i", v, "-vn", "-af", "afade=t=in:d=0.6",
                        "-ar", "44100", "-ac", "2", "-b:a", "192k", son], check=True)
        suivant = projets[j + 1]["d"] if j + 1 < len(projets) else duree
        musiques.append({"src": f"{prefixe}/m{j}.mp3", "d": pr["d"], "f": round(pr["f"], 3), "depuis": 0, "plein": True})
        musiques.append({"src": f"{prefixe}/m{j}.mp3", "d": round(pr["f"], 3), "f": round(suivant, 3), "depuis": DUREE_PROJET})
        epoques.append((pr["f"], [v] + base[:1]))
    # musique d'avant le 1er projet : son clip le plus en vue, au refrain
    premier = projets[0]["d"] if projets else duree
    if base:
        try:
            t0, _ = RF.refrain(base[0], duree=30)
        except Exception:  # noqa: BLE001
            t0 = _duree(base[0]) * 0.3
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0, t0 - 2):.2f}", "-i", base[0], "-vn", "-af", "afade=t=in:d=1.5",
                        "-ar", "44100", "-ac", "2", "-b:a", "192k", os.path.join(dossier, "intro.mp3")], check=True)
        musiques.insert(0, {"src": f"{prefixe}/intro.mp3", "d": 0, "f": round(premier, 3), "depuis": 0})
    # 3) images : photo d'ouverture, puis les plans de l'époque entre les projets, photo de fin
    photo = _photo(p.get("photo"), dossier, "photo.jpg")
    les_plans = []
    debut = 3.6 if photo else 0.0
    if photo:
        les_plans.append({"src": f"{prefixe}/photo.jpg", "d": 0, "f": debut, "image": True})
    trous, cur = [], debut
    for pr in projets:
        if pr["d"] > cur + 0.4:
            trous.append((cur, pr["d"]))
        cur = pr["f"]
    trous.append((cur, fin_d if photo else duree))
    for n, (a, b) in enumerate(trous):
        sources = next((s for (d0, s) in reversed(epoques) if d0 <= a + 0.01), base) or base
        if sources and b - a > 0.6:
            les_plans += plans(sources, dossier, prefixe + "", a, b) if n == 0 else _plans_suffixe(sources, dossier, prefixe, a, b, n)
    if photo:
        les_plans.append({"src": f"{prefixe}/photo.jpg", "d": round(fin_d, 3), "f": duree, "image": True})
    # 4) mascotte : jamais pendant un projet ni sur une carte
    occupe = [(x["d"] - 0.3, x["f"]) for x in cartes] + [(x["d"] - 0.5, x["f"] + 0.5) for x in projets]
    mascottes = [{"src": POSES["question"], "d": 0.2, "f": 3.4, "cote": "gauche", "h": 900}]
    for pose, r, cote in (("surpris", 0.3, "droite"), ("presente", 0.55, "droite"), ("surpris", 0.8, "gauche")):
        cible = fin_d * r
        for (a, b, _) in voix_bornes:
            if a >= cible and not any(x <= a <= y or x <= a + 3 <= y for x, y in occupe) and a + 3.2 < fin_d:
                mascottes.append({"src": POSES[pose], "d": round(a, 3), "f": round(a + 3.2, 3), "cote": cote, "h": 880})
                occupe.append((a, a + 3.2))
                break
    mascottes.append({"src": POSES["appel"], "d": round(fin_d + 0.3, 3), "f": duree, "cote": "gauche", "h": 820})
    return {"voix": f"{prefixe}/voix.mp3", "musique": musiques[0]["src"] if musiques else f"{prefixe}/voix.mp3", "duree": duree, "mots": mots,
            "titre": recit["titre"], "plans": les_plans, "cartes": cartes, "mascottes": mascottes, "musiques": musiques, "fond": 0.13,
            "projets": [{k2: x[k2] for k2 in ("d", "f", "cover", "titre", "etiquette", "invites", "chiffre", "morceau") if x.get(k2) is not None} for x in projets],
            "chapitres": chapitres, "sfx": sfx,
            "fin": {"d": round(fin_d, 3), "titre": recit["fin"]["titre"], "texte": recit["fin"]["texte"]}, "sources": recit.get("sources") or ""}


def _plans_suffixe(sources, dossier, prefixe, a, b, n):
    """plans() nomme ses fichiers p00, p01… : un sous-dossier par intervalle évite d'écraser ceux d'avant."""
    from core.services.social.studio_raconte import plans
    sous = os.path.join(dossier, f"e{n}")
    os.makedirs(sous, exist_ok=True)
    return plans(sources, sous, f"{prefixe}/e{n}", a, b)
