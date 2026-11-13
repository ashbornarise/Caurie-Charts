"""Cauri Studio, « Cauri raconte » (13/11/2026) : la mascotte raconte un artiste en une minute — voix off Henri,
clips officiels, chiffres réels dans des cartes de verre, sous-titres mot à mot. Les vidéos faites à la main (Didi B,
Jeune Lion) « cartonnent sur Facebook » : le fondateur les veut en outil du Studio.

Deux temps, sur le PC (relais : YouTube refuse les serveurs, le rendu Remotion est local) :
1. prepare() : vrais chiffres (nos classements officiels, Spotify via Kworb, Wikipédia/Wikidata, YouTube, rivaux du
   pays), faits peu connus cherchés par Gemini + Google (gardés seulement avec 2 sources), puis récit écrit par l'IA
   à partir de ces données SEULEMENT -> « a_valider » (le fondateur relit le texte, la prononciation et les cartes).
2. fabrique() : voix Henri phrase par phrase (edge-tts, gratuit), plans des clips officiels, mascotte détourée (4 poses),
   musique = le titre le plus écouté au refrain, rendu Remotion « CauriRaconte », mastering -> « pret ».
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date

from core import db, storage
from core.services.platforms import log_write

REMOTION = r"C:\Users\agbal\Studio-AV\remotion"
PYTHON_STUDIO = "python"        # Python du Studio-AV (pedalboard, plugins VST3)
AV = r"C:\Users\agbal\Studio-AV\av.py"
VOIX = "fr-FR-HenriNeural"
DEBIT = "+6%"
POSES = {"question": "raconte/m1-question.png", "presente": "raconte/m2-presente.png",
         "surpris": "raconte/m3-surpris.png", "appel": "raconte/m4-appel.png"}

# Prononciation d'Henri (retours du fondateur, 12/11/2026) : écrit en phonétique pour la voix, orthographe juste à l'écran
PHONETIQUE = {"Asake": "Achaké", "Juru": "Jourou", "Shogun": "Shogoune", "Lagos": "Légosse", "Phyno": "Faïno", "Khaid": "Kaïd",
              "Burna Boy": "Beurna Boï", "Rema": "Réma", "Olamide": "Olamidé", "YBNL": "Ouaille Bi Ène Èl", "Afrobeats": "Afrobits",
              "Amapiano": "Amapiano", "Spotify": "Spotifaï", "Billboard": "Billboard", "Grammy": "Grammie", "Grammys": "Grammies",
              "Wizkid": "Ouizkid", "Mr Money": "Mister Money", "Lungu Boy": "Lounngou Boï", "Work of Art": "Weurk of Art",
              "Ololade": "Ololadé", "Fuji": "Foudji"}

SYSTEME = """Tu écris le texte d'une vidéo verticale « Cauri raconte » (une minute, voix off française posée et captivante,
façon récit de chaîne YouTube culturelle) sur un artiste, pour Cauri Charts, « la référence de la musique ouest-africaine ».

Deux épisodes validés par le fondateur, à imiter pour le ton, le rythme et la construction (voix déjà en phonétique) :
---
Pourquoi Didi B n'est pas un rappeur comme les autres ?
Le savais-tu ? Avant le micro, il y a eu la caméra. À treize ans, Didi B tenait le premier rôle du film Les Frères Kadogo,
primé au Fesspaco. Fils d'un pianiste et d'une chorégraphe, il est né sur scène. En 2009, il fonde Kiff No Beat avec ses
cousins. Puis il se lance seul. Sur Spotify, Himra fait plus d'écoutes que lui. Mais Didi B a fait ce qu'aucun autre rappeur
ivoirien n'a fait : remplir le stade Félix Houphouët-Boigny. Plus de trente mille places. [...] La leçon : les chiffres font
un artiste. La scène fait une légende. Et toi, qui mérite le prochain épisode ? Dis-le en commentaire.
---
Comment Jeune Lion a fait 48 millions d'écoutes en parlant de Dieu ?
La Côte d'Ivoire est une terre de reggae : Alpha Blondy, Tiken Jah Fakoly. Jeune Lion, rappeur franco-ivoirien né à Marcory,
mélange ce reggae avec le coupé-décalé et la trap. Le savais-tu ? [...] Là où beaucoup misent sur la fête, lui parle d'âme et
de foi. Et ça paie. [...] La leçon : pas besoin de suivre la mode. Une identité forte finit toujours par trouver son public.
---
Règles absolues :
- Un fil conducteur, une histoire, pas une liste de chiffres : chaque chiffre sert l'histoire (2 à 4 chiffres au plus).
- Utilise UNIQUEMENT les faits et chiffres fournis. N'invente rien : aucune date, aucun chiffre, aucun « record », aucune
  anecdote, aucune citation absents des données. Ne déduis pas : « semaines_presentes » n'est pas « semaines à la 1re place ».
  N'ajoute aucune nuance absente des données (« d'affilée », « record », « le premier », « domine »), même pour faire joli.
- Jamais « le plus grand de tous », jamais le mot « Billboard » (dis « le classement américain »). Un superlatif seulement s'il
  est prouvé par les données. Compare honnêtement avec les rivaux du pays, même si un rival est devant (comme Himra pour Didi B).
- Construction : accroche-question (moins de 10 mots) ; contexte ; « Le savais-tu ? » + un fait peu connu tiré des données ;
  ce qui le distingue des autres de sa scène ; une leçon en une phrase qui commence par « La leçon : » ; et l'appel final
  exact : « Et toi, qui mérite le prochain épisode ? Dis-le en commentaire. »
- 9 à 13 phrases courtes, 140 à 170 mots en tout. Phrases orales, rythmées. Pas de markdown, pas d'astérisques.
- 3 à 5 phrases portent une « carte » à l'écran : grand = un chiffre court ou 1 à 3 mots en capitales (« 4,66 MD », « N°1 »,
  « DANSEUR »), petit = le contexte en moins de 45 caractères. or=true pour les 2 cartes les plus fortes. Pas de carte sur la
  1re ni sur la dernière phrase.
- « voix » : la phrase écrite pour être bien prononcée par une voix française (noms anglais ou yoruba en phonétique
  française : Asake -> Achaké, Lagos -> Légosse, Burna Boy -> Beurna Boï, Spotify -> Spotifaï). "" si rien à changer.
- titre : haut (1 mot : « COMMENT » ou « POURQUOI »), nom (l'artiste en capitales), bas (la fin de la question d'accroche,
  moins de 45 caractères, en capitales). Ensemble, les trois forment la question de la 1re phrase.
- legende_fr : 2 à 3 phrases pour Facebook/Instagram/TikTok, avec une question aux abonnés ; legende_en : sa traduction.
Réponds en JSON strict : {"titre": {"haut": "", "nom": "", "bas": ""}, "phrases": [{"texte": "", "voix": "",
"carte": null ou {"grand": "", "petit": "", "or": false}}], "legende_fr": "", "legende_en": ""}"""


# ---------------------------------------------------------------- 1. recherche + récit

def _n(v) -> str:
    v = float(v or 0)
    if v >= 1e9:
        return f"{v / 1e9:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " milliard" + ("s" if v >= 2e9 else "")
    if v >= 1e6:
        return f"{v / 1e6:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " millions"
    if v >= 1e3:
        return f"{v / 1e3:.0f} mille"
    return str(int(v))


def officiel(artist_id: int) -> list[dict]:
    """Ses places dans nos classements officiels publiés (meilleure place, semaines, N°1), par classement et pays."""
    return db.all("""SELECT COALESCE(c.name_fr, 'Afrique de l''Ouest') AS pays, ct.name AS classement, MIN(e.position) AS meilleure, COUNT(DISTINCT r.period_key) AS semaines,
                            COUNT(*) FILTER (WHERE e.position = 1) AS n1,
                            (SELECT t.title FROM chart_entries e2 JOIN chart_runs r2 ON r2.id = e2.chart_run_id JOIN tracks t ON t.id = e2.track_id
                              WHERE e2.artist_id = e.artist_id AND r2.chart_type_id = r.chart_type_id AND r2.country_id = r.country_id
                              AND r2.status = 'published' ORDER BY e2.position, r2.period_key DESC LIMIT 1) AS titre
                     FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id JOIN chart_types ct ON ct.id = r.chart_type_id
                     LEFT JOIN countries c ON c.id = r.country_id
                     WHERE e.artist_id = ? AND r.status = 'published' AND ct.is_public = 1
                     GROUP BY c.name_fr, ct.name, r.chart_type_id, r.country_id, e.artist_id ORDER BY meilleure, semaines DESC LIMIT 8""",
                  [artist_id])


def rivaux(a: dict, n: int = 3) -> list[dict]:
    """Les artistes les plus suivis de son pays, avec leurs chiffres Spotify (Kworb) : la comparaison honnête."""
    from core.services import kworb
    out = []
    for r in db.all("""SELECT a.name, a.spotify_id FROM artists a WHERE a.status = 'active' AND a.id <> ? AND a.spotify_id IS NOT NULL
                       AND a.submission_country_id = ? ORDER BY a.youtube_subscribers DESC NULLS LAST LIMIT 6""",
                    [a["id"], a["submission_country_id"]]):
        try:
            k = kworb.chiffres(r["spotify_id"], 1)
        except Exception:  # noqa: BLE001
            k = None
        if k:
            out.append({"nom": r["name"], "streams_spotify": _n(k["total"]), "auditeurs_mensuels": _n(k["auditeurs"]) if k.get("auditeurs") else None,
                        "_total": k["total"]})
        if len(out) >= n:
            break
    return sorted(out, key=lambda x: -x["_total"])


def faits_google(nom: str, pays: str) -> list[dict]:
    """2 à 4 faits peu connus, cherchés par Gemini + Google ; gardés seulement s'ils citent 2 sources différentes."""
    from core.services import ai
    from core.services.platforms import HttpClient
    os.environ.setdefault("GEMINI_GROUNDING", "1")
    q = (f"Artiste : {nom} ({pays}). Donne 4 faits vérifiables et peu connus du grand public sur sa carrière (débuts, "
         "tournant, record, collaboration marquante, salle remplie, distinction). Pour chaque fait, au moins 2 sources "
         "différentes (nom du média). JSON strict : {\"faits\": [{\"fait\": \"...\", \"annee\": \"...\", \"sources\": [\"...\", \"...\"]}]}")
    try:
        r = ai.GeminiClient(HttpClient(120)).ask("Tu es documentaliste musical. Tu ne gardes que des faits confirmés par la recherche.",
                                                 q, 1500, web_searches=5)
        d = ai.extract_json(r["text"]) or {}
    except Exception as exc:  # noqa: BLE001
        log_write("studio", "warning", f"raconte : faits Google indisponibles pour {nom} ({exc})")
        return []
    out = []
    for f in d.get("faits") or []:
        src = {str(s).strip().lower() for s in f.get("sources") or [] if str(s).strip()}
        if len(src) >= 2 and str(f.get("fait") or "").strip():
            out.append({"fait": str(f["fait"]).strip()[:300], "annee": str(f.get("annee") or "")[:20],
                        "sources": [str(s).strip()[:60] for s in f["sources"]][:3]})
    return out[:4]


def recherche(artist_id: int, angle: str = "") -> dict:
    from core.services.social import portrait
    a = portrait.artiste(artist_id)
    if not a:
        raise RuntimeError("artiste introuvable")
    f = portrait.facts(a)
    sp = f.get("spotify") or {}
    d = {"artiste": a["name"], "pays": a["country"], "angle": angle.strip()[:300],
         "classements_officiels_cauri": [{"classement": f"{o['classement']} ({'artistes' if 'Icon' in o['classement'] or 'Artistes' in o['classement'] else 'titres'}) · {o['pays']}",
                                          "meilleure_place": o["meilleure"], "semaines_presentes": o["semaines"], "fois_numero_1": o["n1"],
                                          "titre_le_mieux_classe": o["titre"]} for o in officiel(artist_id)],
         "titres_en_classement_cette_semaine": [{"titre": t["title"], "meilleure_place_sur_une_plateforme": t["best"],
                                                 "present_dans_n_classements_de_plateformes": t["charts"]} for t in f.get("tracks") or []],
         "spotify": {"ecoutes_totales": _n(sp["total"]), "ecoutes_par_jour": _n(sp["jour"]),
                     "auditeurs_mensuels": _n(sp["auditeurs"]) if sp.get("auditeurs") else None,
                     "titres_les_plus_ecoutes": [{"titre": t["titre"], "ecoutes": _n(t["streams"])} for t in sp.get("titres") or []]} if sp else None,
         "youtube": {"abonnes": _n(f["youtube_subscribers"]) if f.get("youtube_subscribers") else None,
                     "vues_totales": _n(f["youtube_views_total"]) if f.get("youtube_views_total") else None},
         "distinctions_wikidata": [f"{x['award']}{' (' + str(x['year']) + ')' if x.get('year') else ''}" for x in f.get("awards") or []],
         "biographie_wikipedia": (f.get("bio") or {}).get("text"),
         "rivaux_du_pays_spotify": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rivaux(a)],
         "faits_peu_connus_verifies": [{**x, "fait": _propre(x["fait"])} for x in faits_google(a["name"], a["country"])]}
    sources = ["Spotify via Kworb" if sp else "", "Wikipédia" if f.get("bio") else "", "YouTube", "classements Cauri Charts"]
    if d["faits_peu_connus_verifies"]:
        sources.append(", ".join(sorted({s for x in d["faits_peu_connus_verifies"] for s in x["sources"]}))[:120])
    d["_sources"] = f"Sources : {' · '.join(s for s in sources if s)} ({date.today():%d/%m/%Y})"
    d["_photo"] = f.get("photo")
    return d


def _propre(texte: str) -> str:
    """Sans markdown ; « Billboard » jamais dit en public (positionnement, 2026)."""
    texte = re.sub(r"\*+|__|`", "", str(texte or ""))
    texte = re.sub(r"\bBillboard 200\b", "classement américain des albums", texte)
    texte = re.sub(r"\bBillboard\b", "classement américain", texte)
    return re.sub(r"\s+", " ", texte).strip()


def _chiffres_dits(texte: str) -> str:
    """« 4,66 MD » -> « 4,66 milliards », « 5,4 M » -> « 5,4 millions » (la voix lirait les lettres)."""
    espace = "[\\s  ]*"
    texte = re.sub(r"(\d+(?:[,.]\d+)?)" + espace + r"(?:M[dD]s?|Mrds?)\b", r"\1 milliards", texte)
    texte = re.sub(r"(\d+(?:[,.]\d+)?)" + espace + r"M\b", r"\1 millions", texte)
    return re.sub(r"(\d+(?:[,.]\d+)?)" + espace + r"k\b", r"\1 mille", texte)


def _ecrit_juste(texte: str) -> str:
    """La phonétique ne va jamais à l'écran : « Spotifaï » redevient « Spotify » dans les sous-titres."""
    for mot, dit in PHONETIQUE.items():
        if dit != mot:
            texte = re.sub(rf"\b{re.escape(dit)}\b", mot, texte)
    return texte


def _phonetique(texte: str) -> str:
    for mot, dit in sorted(PHONETIQUE.items(), key=lambda x: -len(x[0])):
        texte = re.sub(rf"\b{re.escape(mot)}\b", dit, texte)
    return texte


def ecrit(donnees: dict) -> dict:
    from core.services import ai
    from core.services.platforms import HttpClient
    # 13/11/2026 : DeepSeek déformait les données (« N°1 pendant 5 semaines » pour 5 semaines classé) : Gemini écrit,
    # puis relit chaque phrase contre les données ; les autres IA restent en secours
    client = ai.FallbackClient([ai.GeminiClient(HttpClient(120))] + [c for c in [ai.make()] if c])
    if not client.is_available():
        raise RuntimeError("aucune IA configurée pour écrire le récit")
    publiques = json.dumps({k: v for k, v in donnees.items() if not k.startswith("_")}, ensure_ascii=False, indent=1)
    r = client.ask(SYSTEME, "Données vérifiées (n'utilise rien d'autre) :\n" + publiques, 3000)
    d = ai.extract_json(r["text"]) or {}
    try:
        v = client.ask("Tu es vérificateur des faits d'un média musical. Tu compares un récit aux données, phrase par phrase.",
                       "Données (seule vérité) :\n" + publiques + "\n\nRécit :\n" + json.dumps(d, ensure_ascii=False)
                       + "\n\nPour chaque phrase et chaque carte : toute affirmation absente des données, exagérée ou contraire aux données "
                       "(nombre de semaines, « N°1 », « domine », « record », « devant », capacités de salle, années…) doit être "
                       "corrigée pour coller exactement aux données, ou retirée. Garde le ton et la construction. Pas de "
                       "« Billboard ». Rends le même JSON, corrigé, et rien d'autre.", 3000)
        d2 = ai.extract_json(v["text"]) or {}
        if len(d2.get("phrases") or []) >= 5:
            d = d2
    except Exception as exc:  # noqa: BLE001 — sans relecture, le fondateur relit de toute façon
        log_write("studio", "warning", f"raconte : relecture des faits indisponible ({exc})")
    phrases = []
    for x in d.get("phrases") or []:
        t = _chiffres_dits(_ecrit_juste(_propre(x.get("texte"))))
        if not t:
            continue
        carte = x.get("carte") if isinstance(x.get("carte"), dict) and str((x.get("carte") or {}).get("grand") or "").strip() else None
        voix = _chiffres_dits(_propre(x.get("voix")) or t)
        phrases.append({"texte": t[:240], "voix": _phonetique(voix)[:260],
                        "carte": {"grand": str(carte["grand"]).strip()[:18].upper(), "petit": _ecrit_juste(str(carte.get("petit") or "").strip())[:60],
                                  "or": bool(carte.get("or"))} if carte else None})
    for ph in (phrases[0], phrases[-1]) if phrases else ():
        ph["carte"] = None
    if len(phrases) < 5:
        raise RuntimeError("le récit écrit par l'IA est trop court : relance le projet")
    t = d.get("titre") or {}
    return {"titre": {"haut": str(t.get("haut") or "COMMENT").upper()[:14], "nom": str(t.get("nom") or donnees["artiste"]).upper()[:22],
                      "bas": _propre(t.get("bas")).upper()[:60]},
            "phrases": phrases[:16], "fin": {"titre": "TON ARTISTE ?", "texte": "Écris-le en commentaire : prochain épisode"},
            "sources": donnees["_sources"][:200], "legende_fr": _propre(d.get("legende_fr"))[:900],
            "legende_en": _propre(d.get("legende_en"))[:900]}


def _image(url: str | None) -> bytes | None:
    if not url:
        return None
    try:
        import requests
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        return r.content if r.status_code == 200 and len(r.content) > 5000 else None
    except Exception:  # noqa: BLE001
        return None


def prepare(job_id: int, job: dict, p: dict, maj) -> dict:
    maj(job_id, statut="analyse", erreur=None)
    from core.services.social import raconte_v2   # v2 (13/11/2026) : dossier complet, chapitres, projets en musique
    donnees = raconte_v2.dossier(int(p["artiste_id"]), p.get("angle") or "")
    recit = raconte_v2.ecrit(donnees)
    vignette = None
    if donnees.get("_photo"):
        corps = _image(donnees["_photo"])
        if corps:
            vignette = f"studio-{job_id}-raconte-photo-{os.urandom(2).hex()}.jpg"
            storage.store_media("social", vignette, corps, "image/jpeg")
    p.update({"recit": recit, "donnees": {k: v for k, v in donnees.items() if not k.startswith("_")}, "photo": donnees.get("_photo"),
              "artiste": donnees["artiste"], "accroche": f"{recit['titre']['haut']} {donnees['artiste']} {recit['titre']['bas']}".strip()[:160],
              "legende_fr": recit["legende_fr"], "legende_en": recit["legende_en"],
              "credit": f"clips officiels de {donnees['artiste']} (YouTube)"})
    champs = {"statut": "a_valider", "params": p}
    if vignette:
        champs["vignette"] = vignette
    maj(job_id, **champs)
    return {"statut": "a_valider", "video": None}


# ---------------------------------------------------------------- 2. fabrication

def _ffmpeg() -> str:
    from core.services.social.studio_montage import ffmpeg
    return ffmpeg()


def _duree(chemin: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", chemin],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def _tts(texte: str, sortie: str) -> list[dict]:
    """Une phrase dite par Henri : mp3 + minutage de chaque mot (WordBoundary)."""
    import edge_tts

    async def _go():
        c = edge_tts.Communicate(texte, VOIX, rate=DEBIT, boundary="WordBoundary")
        mots, audio = [], bytearray()
        async for ch in c.stream():
            if ch["type"] == "audio":
                audio += ch["data"]
            elif ch["type"] == "WordBoundary":
                mots.append({"m": ch["text"], "d": ch["offset"] / 1e7, "f": (ch["offset"] + ch["duration"]) / 1e7})
        open(sortie, "wb").write(bytes(audio))
        return mots
    return asyncio.run(_go())


def _sous_titres(texte: str, mots_dits: list[dict], t0: float, duree: float) -> list[dict]:
    """Les mots écrits (orthographe juste) calés sur la voix : un pour un si les comptes concordent, sinon au prorata."""
    ecrits = texte.split()
    if not ecrits:
        return []
    if len(ecrits) == len(mots_dits):
        return [{"m": w, "d": round(t0 + m["d"], 3), "f": round(t0 + m["f"], 3)} for w, m in zip(ecrits, mots_dits)]
    a = mots_dits[0]["d"] if mots_dits else 0.05
    b = mots_dits[-1]["f"] if mots_dits else max(0.3, duree - 0.1)
    poids = [len(w) + 2 for w in ecrits]
    tot, cur, out = sum(poids), a, []
    for w, k in zip(ecrits, poids):
        long = (b - a) * k / tot
        out.append({"m": w, "d": round(t0 + cur, 3), "f": round(t0 + cur + long * 0.92, 3)})
        cur += long
    return out


def voix(recit: dict, dossier: str) -> tuple[list[dict], list[tuple[float, float]], float]:
    """voix.mp3 (phrases enchaînées, 0,3 s entre chacune) ; mots minutés ; (début, fin) de chaque phrase ; durée."""
    pause, morceaux, mots, bornes, t = 0.30, [], [], [], 0.08
    for i, ph in enumerate(recit["phrases"]):
        mp3 = os.path.join(dossier, f"v{i:02d}.mp3")
        dits = _tts(ph.get("voix") or ph["texte"], mp3)
        d = _duree(mp3)
        mots += _sous_titres(ph["texte"], dits, t, d)
        bornes.append((t, t + d))
        morceaux.append(mp3)
        t += d + pause
    liste = os.path.join(dossier, "voix.txt")
    silence = os.path.join(dossier, "silence.mp3")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{pause}", "-q:a", "4", silence], check=True)
    debut = os.path.join(dossier, "debut.mp3")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.08", "-q:a", "4", debut], check=True)
    with open(liste, "w", encoding="utf-8") as fl:
        fl.write(f"file '{debut}'\n")
        for i, m in enumerate(morceaux):
            fl.write(f"file '{m}'\n")
            if i < len(morceaux) - 1:
                fl.write(f"file '{silence}'\n")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", liste, "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    os.path.join(dossier, "voix.mp3")], check=True)
    return mots, bornes, t - pause


def clips(artist_id: int, n: int = 3) -> list[str]:
    """Les clips officiels YouTube de ses titres : d'abord ceux en classement, puis les plus récents."""
    lignes = db.all("""SELECT tpi.external_id FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id
                       WHERE t.artist_id = ? AND tpi.platform = 'youtube' AND tpi.is_official = 1 AND tpi.kind = 'clip'
                       ORDER BY (SELECT COUNT(*) FROM chart_observations o WHERE o.track_id = t.id AND o.observed_on >= CURRENT_DATE - 30) DESC,
                                tpi.published_at DESC NULLS LAST LIMIT 8""", [artist_id])
    return list(dict.fromkeys(r["external_id"] for r in lignes))[:n]


def _cadre(video: str) -> str | None:
    """Bandes noires (format cinéma) : le recadrage utile, au-dessus des sous-titres incrustés (86 % de la hauteur)."""
    total = _duree(video)
    r = subprocess.run([_ffmpeg(), "-v", "info", "-ss", f"{total * 0.4:.1f}", "-t", "6", "-i", video, "-vf", "cropdetect=24:16:0", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
    if not m:
        return None
    w, h, x, y = map(int, m[-1])
    hauteur = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0", video],
                             capture_output=True, text=True).stdout.strip()
    H = int(hauteur or 0)
    if H and h < H * 0.9:
        return f"crop={w}:{int(h * 0.86)}:{x}:{y}"
    return None


def plans(sources: list[str], dossier: str, prefixe: str, d0: float, d1: float) -> list[dict]:
    """Des plans de 2,6 à 3,4 s pris dans les clips, à tour de rôle, entre d0 et d1."""
    infos = []
    for s in sources:
        infos.append({"src": s, "duree": _duree(s), "cadre": _cadre(s), "pris": 0})
    out, t, k = [], d0, 0
    longueurs = [3.2, 2.8, 3.4, 2.6, 3.0]
    while t < d1 - 0.5 and infos:
        c = infos[k % len(infos)]
        long = min(longueurs[k % len(longueurs)], d1 - t)
        if d1 - (t + long) < 1.2:   # pas de plan minuscule à la fin
            long = d1 - t
        # positions réparties dans le clip, jamais deux fois au même endroit
        ratio = 0.12 + (0.76 * ((c["pris"] * 0.381966) % 1))
        debut = max(0.0, c["duree"] * ratio)
        c["pris"] += 1
        nom = f"p{k:02d}.mp4"
        vf = ",".join(x for x in (c["cadre"], "scale=-2:1080", "fps=30") if x)
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{debut:.2f}", "-i", c["src"], "-t", f"{long + 0.2:.2f}", "-an", "-vf", vf,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", os.path.join(dossier, nom)], check=True)
        out.append({"src": f"{prefixe}/{nom}", "d": round(t, 3), "f": round(t + long, 3)})
        t += long
        k += 1
    return out


def _photo_locale(url: str | None, dossier: str, nom: str) -> str | None:
    corps = _image(url)
    try:
        if corps:
            chemin = os.path.join(dossier, nom)
            brut = chemin + ".src"
            open(brut, "wb").write(corps)
            subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", brut, "-vf", "scale='min(1600,iw)':-2", chemin], check=True)
            return chemin
    except Exception:  # noqa: BLE001
        return None
    return None


def construit(job_id: int, p: dict, dossier: str, prefixe: str) -> dict:
    """Toutes les pièces dans public/raconte/job-<id>/ et les props de la composition CauriRaconte."""
    from core.services.social import refrain as RF
    recit = p["recit"]
    mots, bornes, fin_voix = voix(recit, dossier)
    duree = round(fin_voix + 3.2, 2)
    fin_d = bornes[-1][0] if len(bornes) > 2 else max(0.0, fin_voix - 3)
    # clips officiels
    sources = []
    for vid in clips(int(p["artiste_id"])):
        s = RF.telecharge(vid, dossier)
        if s:
            sources.append(s)
    if not sources:
        raise RuntimeError("aucun clip officiel téléchargé pour cet artiste")
    debut_plans = bornes[1][0] if len(bornes) > 1 else 3.6
    photo = _photo_locale(p.get("photo"), dossier, "photo.jpg")
    les_plans = []
    if photo:
        les_plans.append({"src": f"{prefixe}/photo.jpg", "d": 0, "f": round(debut_plans, 3), "image": True})
    else:
        debut_plans = 0.0
    les_plans += plans(sources, dossier, prefixe, debut_plans, fin_d if photo else duree)
    if photo:
        les_plans.append({"src": f"{prefixe}/photo.jpg", "d": round(fin_d, 3), "f": duree, "image": True})
    # musique : le premier clip, à partir de son refrain
    try:
        t0, _ = RF.refrain(sources[0], duree=40)
    except Exception:  # noqa: BLE001
        t0 = _duree(sources[0]) * 0.3
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0, t0 - 2):.2f}", "-i", sources[0], "-t", f"{duree + 1:.2f}", "-vn",
                    "-af", "afade=t=in:d=1.5", "-ar", "44100", "-ac", "2", "-b:a", "192k", os.path.join(dossier, "musique.mp3")], check=True)
    # cartes calées sur leur phrase
    cartes = []
    for (a, b), ph in zip(bornes, recit["phrases"]):
        c = ph.get("carte")
        if not c or a < 3.4 or a >= fin_d - 0.2:
            continue
        d = a + 0.15
        f = min(max(b + 0.25, d + 1.6), d + 4.2, fin_d)
        if f - d >= 1.0:
            cartes.append({"d": round(d, 3), "f": round(f, 3), "grand": c["grand"], "petit": c.get("petit") or "", "or": bool(c.get("or"))})
    # mascotte : question à l'ouverture, surprise au premier tiers, présentation aux deux tiers, appel à la fin
    def _a(r):
        i = min(len(bornes) - 2, max(1, round((len(bornes) - 1) * r)))
        return bornes[i][0]
    mascottes = [{"src": POSES["question"], "d": 0.2, "f": 3.4, "cote": "gauche", "h": 900}]
    for pose, r, cote in (("surpris", 0.36, "droite"), ("presente", 0.66, "droite")):
        d = _a(r)
        if not any(c["d"] - 0.3 <= d <= c["f"] for c in cartes):
            mascottes.append({"src": POSES[pose], "d": round(d, 3), "f": round(min(d + 3.4, fin_d), 3), "cote": cote, "h": 900})
        else:   # pas sur une carte : juste après
            d2 = next((c["f"] for c in cartes if c["d"] - 0.3 <= d <= c["f"]), d)
            if d2 + 2 < fin_d:
                mascottes.append({"src": POSES[pose], "d": round(d2, 3), "f": round(min(d2 + 3.2, fin_d), 3), "cote": cote, "h": 900})
    mascottes.append({"src": POSES["appel"], "d": round(fin_d + 0.3, 3), "f": duree, "cote": "gauche", "h": 820})
    return {"voix": f"{prefixe}/voix.mp3", "musique": f"{prefixe}/musique.mp3", "duree": duree, "mots": mots,
            "titre": recit["titre"], "plans": les_plans, "cartes": cartes, "mascottes": mascottes,
            "fin": {"d": round(fin_d, 3), "titre": recit["fin"]["titre"], "texte": recit["fin"]["texte"]}, "sources": recit.get("sources") or ""}


def rendu(props: dict, dossier: str, sortie: str) -> None:
    fichier = os.path.join(dossier, "props.json")
    json.dump(props, open(fichier, "w", encoding="utf-8"), ensure_ascii=False)
    r = subprocess.run(f'npx remotion render src/index.ts CauriRaconte "{sortie}" --props="{fichier}" --concurrency=2',
                       cwd=REMOTION, shell=True, capture_output=True, text=True, timeout=3600, encoding="utf-8", errors="replace")
    if r.returncode or not os.path.isfile(sortie):
        raise RuntimeError("rendu Remotion en échec : " + (r.stderr or r.stdout)[-400:])


def fabrique(job_id: int, job: dict, p: dict, maj) -> dict:
    from core.services.social.encodage import copie_tiktok, nom_tiktok
    maj(job_id, statut="montage", erreur=None)
    prefixe = f"raconte/job-{job_id}"
    dossier = os.path.join(REMOTION, "public", "raconte", f"job-{job_id}")
    shutil.rmtree(dossier, ignore_errors=True)
    os.makedirs(dossier)
    try:
        from core.services.social import raconte_v2
        props = (raconte_v2.construit if (p.get("recit") or {}).get("v") == 2 else construit)(job_id, p, dossier, prefixe)
        with tempfile.TemporaryDirectory(prefix=f"cauri-raconte-{job_id}-") as tmp:
            brut = os.path.join(tmp, "brut.mp4")
            rendu(props, dossier, brut)
            video = brut
            try:   # vrai limiteur FabFilter Pro-L 2 (Studio-AV), sinon le niveau du rendu reste
                subprocess.run([PYTHON_STUDIO, AV, "master", brut, "--vst"], check=True, capture_output=True, timeout=900)
                if os.path.isfile(brut.replace(".mp4", "-master.mp4")):
                    video = brut.replace(".mp4", "-master.mp4")
            except (subprocess.SubprocessError, OSError):
                pass
            nom = f"studio-{job_id}-raconte-{os.urandom(3).hex()}"
            vignette = os.path.join(tmp, nom + ".jpg")
            subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", "1.6", "-i", video, "-frames:v", "1", "-q:v", "3", vignette], check=True)
            storage.store_media("social", nom + ".mp4", open(video, "rb").read(), "video/mp4")
            tt = copie_tiktok(video)
            if tt:
                storage.store_media("social", nom_tiktok(nom + ".mp4"), open(tt, "rb").read(), "video/mp4")
            storage.store_media("social", nom + ".jpg", open(vignette, "rb").read(), "image/jpeg")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    maj(job_id, statut="pret", video=nom + ".mp4", vignette=nom + ".jpg")
    return {"statut": "pret", "video": nom + ".mp4"}


def traite(job_id: int, job: dict, p: dict, maj) -> dict:
    return fabrique(job_id, job, p, maj) if p.get("valide") else prepare(job_id, job, p, maj)


def recit_valide(r: dict) -> dict | None:
    """Le récit relu dans le Studio (texte, prononciation, cartes ; v2 : chapitres et projets), nettoyé."""
    if not isinstance(r, dict) or not isinstance(r.get("phrases"), list):
        return None
    t = r.get("titre") or {}
    phrases = []
    for x in r["phrases"][:40]:
        if not isinstance(x, dict):
            continue
        sorte = x.get("type") or "voix"
        if sorte == "chapitre":
            if str(x.get("titre") or "").strip():
                phrases.append({"type": "chapitre", "numero": str(x.get("numero") or "")[:20], "titre": str(x["titre"]).strip()[:28]})
            continue
        if sorte == "projet":
            if x.get("album_id") and str(x.get("titre") or "").strip():
                phrases.append({"type": "projet", **{k: str(x.get(k) or "")[:300] for k in ("titre", "cover", "etiquette", "morceau", "chiffre", "invites")},
                                "album_id": x["album_id"]})
            continue
        if not str(x.get("texte") or "").strip():
            continue
        c = x.get("carte") if isinstance(x.get("carte"), dict) and str((x.get("carte") or {}).get("grand") or "").strip() else None
        phrases.append({"type": "voix", "texte": str(x["texte"]).strip()[:260],
                        "voix": _chiffres_dits(str(x.get("voix") or _phonetique(str(x["texte"]))).strip())[:300],
                        "carte": {"grand": str(c["grand"]).strip()[:18], "petit": str(c.get("petit") or "").strip()[:60], "or": bool(c.get("or"))} if c else None})
    if sum(1 for x in phrases if x["type"] == "voix") < 3:
        return None
    fin = r.get("fin") or {}
    out = {"titre": {"haut": str(t.get("haut") or "")[:14], "nom": str(t.get("nom") or "")[:22], "bas": str(t.get("bas") or "")[:60]},
           "phrases": phrases, "fin": {"titre": str(fin.get("titre") or "TON ARTISTE ?")[:24], "texte": str(fin.get("texte") or "")[:80]},
           "sources": str(r.get("sources") or "")[:220]}
    if r.get("v") == 2:
        out["v"] = 2
    return out
