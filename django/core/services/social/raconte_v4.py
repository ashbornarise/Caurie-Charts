"""« Cauri raconte » v4 (15/11/2026) — retours du fondateur sur l'épisode Wizkid v3 :
« le scénario est bon mais ça fait trop IA ; le mythe en vrai ou faux, pas vraiment ; les sons qui chantent quand la voix
parle, ça dérange : il faut les contrôler, des fois en fond, d'autres non ; l'effet sonore des mythes ne va pas ; les
questions en bulle au niveau de la tête de la mascotte, comme dans les bandes dessinées ; des textes se chevauchent ;
chaque section : une pause, un titre fort, puis ça commence ; pour chaque projet cité, c'est SON son qui doit être joué ;
la jauge : écran noir, au milieu, barre sphérique et royale, le cauri bouge un peu puis se débloque, AVANT qu'on raconte
le mythe (le spectateur sait que quelque chose arrive) ».

- Écriture : Gemini écrit à partir des seules données (règles de narration humaine tirées d'une consultation DeepSeek),
  relecture des faits, puis DeepSeek réécrit le ton « YouTubeur » ; tout nouveau chiffre ou nom propre est refusé.
- Secrets en 3 temps : jauge royale en écran noir (pause, son de déverrouillage) → la rumeur racontée, question en bulle
  de BD au-dessus de la mascotte (ambiance de suspense, musique coupée) → « LA VÉRITÉ » (son de révélation).
- Chapitres : pause de 2,5 s, titre plein écran, le titre de l'époque chanté ; puis la voix repart.
- Musique sous la voix : INSTRUMENTALE (chant retiré par iZotope RX 12 Music Rebalance), réglable par chapitre dans le
  Studio (instrumentale / chantée douce / aucune) ; projets : le vrai morceau cité, chanté, à plein volume.
- Clips gardés en cache (public/raconte/cache) : une relance ne retélécharge rien (YouTube bloque vite ce PC).
- Banque de sons Mixkit (licence libre, sans mention) : public/raconte/sfx2 et « Sons pub/12 - Mixkit ».
"""
import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import requests

from core import env
from core.services.platforms import log_write
from core.services.social import raconte_v3 as V3
from core.services.social.raconte_v3 import _cle, _duree, _ffmpeg

REMOTION = r"C:\Users\agbal\Studio-AV\remotion"
CACHE = os.path.join(REMOTION, "public", "raconte", "cache")
PYTHON_STUDIO = "python"
RX = r"C:\Program Files\Common Files\VST3\iZotope\RX 12 Music Rebalance.vst3"
DUREE_PROJET = 9.0
DUREE_CHANTE = 3.6   # s de refrain quand un titre est cité (16/11 : « pour la nostalgie et l'intrigue »)
CHANTES_MAX = 8
PAUSE = 0.18
PAUSE_SECRET = 2.6
PAUSE_CHAPITRE = 2.5
FOND = {"instru": 0.24, "chant": 0.09, "aucune": 0.0}   # instrumentale : plus présente, elle ne gêne pas la voix
SEGMENT_MAX = 40.0
SFX = {"titre": "raconte/sfx2/boom-titre.mp3", "unlock": "raconte/sfx2/unlock.mp3", "swell": "raconte/sfx2/swell.mp3",
       "suspense": "raconte/sfx2/mystere-basse.mp3", "bulle": "raconte/sfx2/bulle-pop.mp3", "verite": "raconte/sfx2/verite.mp3",
       "projet": "raconte/sfx2/whoosh-impact.mp3", "carte": "raconte/sfx2/whoosh.mp3", "fin": "raconte/sfx/reverse-impact.mp3",
       "sparkle": "raconte/sfx2/sparkle.mp3", "boom": "raconte/sfx2/impact-epique.mp3", "parasite": "raconte/sfx2/parasite-court.mp3",
       "glitch": "raconte/sfx2/parasite-glitch.mp3", "battement": "raconte/sfx2/heartbeat.mp3", "sonnette": "raconte/sfx2/machine-sonnette.mp3",
       "frappes": ["raconte/sfx2/machine-frappe1.mp3", "raconte/sfx2/machine-frappe2.mp3", "raconte/sfx2/machine-frappe3.mp3"]}

# 17/11/2026 (Shatta Wale) : ouverture « thriller » : « une voix bien plus assise, presque sadique, des sons dramatiques et
# graves, avant un gros boom, du bruit, puis CHAPITRE 1 qui s'écrit comme sur une machine des années 90, et là ça commence ».
# Les temps de frappe sont les mêmes que dans TitreChapitreVue (style « machine ») de CauriRaconte.tsx.
MACHINE = {"bruit": 1.3, "depart": 0.3, "car_num": 0.07, "entre": 0.35, "car_titre": 0.1, "tenue": 1.2}


# 17/11/2026 : « dans les scènes où on voit les fesses, on floute ces endroits seuls » (TikTok et Meta brident les vidéos
# « suggestives »). NudeNet (modèle libre, sur le PC) repère les zones, floutées image par image ; le reste du plan reste net.
ZONES_FLOUTEES = {"BUTTOCKS_EXPOSED": 0.35, "BUTTOCKS_COVERED": 0.45, "FEMALE_BREAST_EXPOSED": 0.35, "FEMALE_GENITALIA_EXPOSED": 0.3,
                  "FEMALE_GENITALIA_COVERED": 0.5, "MALE_GENITALIA_EXPOSED": 0.3, "ANUS_EXPOSED": 0.3}
_DETECTEUR = []


def floute_zones(chemin: str, pas: int = 3, tenue: int = 5) -> int:
    """Floute dans la vidéo les zones sensibles détectées ; renvoie le nombre d'images retouchées (0 : fichier inchangé)."""
    try:
        import cv2
        from nudenet import NudeDetector
    except ImportError:
        if not _DETECTEUR:
            log_write("studio", "warning", "raconte : NudeNet absent, aucun floutage des zones sensibles (pip install nudenet)")
            _DETECTEUR.append(None)
        return 0
    if not _DETECTEUR or _DETECTEUR[0] is None:
        _DETECTEUR[:] = [NudeDetector()]
    det = _DETECTEUR[0]
    cap = cv2.VideoCapture(chemin)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    images, zones, actives = [], {}, []
    i = 0
    while True:
        ok, im = cap.read()
        if not ok:
            break
        images.append(im)
        if i % pas == 0:
            boites = []
            for z in det.detect(im):
                if z.get("score", 0) >= ZONES_FLOUTEES.get(z.get("class"), 9):
                    boites.append(z["box"])
            if boites:
                for j in range(max(0, i - pas), i + tenue + 1):
                    zones.setdefault(j, []).extend(boites)
        i += 1
    cap.release()
    if not zones or not images:
        return 0
    h, w = images[0].shape[:2]
    for j, im in enumerate(images):
        for x, y, bw, bh in zones.get(j, []):
            mx, my = int(bw * 0.2), int(bh * 0.2)
            x0, y0, x1, y1 = max(0, x - mx), max(0, y - my), min(w, x + bw + mx), min(h, y + bh + my)
            if x1 - x0 > 4 and y1 - y0 > 4:
                k = max(31, (min(x1 - x0, y1 - y0) // 3) | 1)
                im[y0:y1, x0:x1] = cv2.GaussianBlur(im[y0:y1, x0:x1], (k, k), 0)
                actives.append(j)
    tmp = chemin + ".flou.mp4"
    pr = subprocess.Popen([_ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}",
                           "-i", "-", "-i", chemin, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-c:a", "copy", tmp], stdin=subprocess.PIPE)
    for im in images:
        pr.stdin.write(im.tobytes())
    pr.stdin.close()
    if pr.wait() == 0 and os.path.isfile(tmp):
        os.replace(tmp, chemin)
        return len(set(actives))
    return 0


def _machine_temps(numero: str, titre: str, bruit: float) -> tuple[list[float], float]:
    """(instants de frappe depuis le début du carton, durée du carton) ; espaces muets."""
    t0 = bruit + MACHINE["depart"]
    frappes = [t0 + i * MACHINE["car_num"] for i, c in enumerate(numero) if not c.isspace()]
    t1 = t0 + len(numero) * MACHINE["car_num"] + MACHINE["entre"]
    frappes += [t1 + i * MACHINE["car_titre"] for i, c in enumerate(titre) if not c.isspace()]
    fin_frappe = t1 + len(titre) * MACHINE["car_titre"]
    return frappes, fin_frappe + MACHINE["tenue"]
INTERDITS = re.compile(r"\b(vrai ou faux|c'est faux|faux !|le savais-tu|la leçon|bienvenue|reste jusqu'au bout|immense|majeur|incroyable|"
                       r"véritable|sans précédent|en effet|il convient|n'aura de cesse)\b", re.I)

dossier = V3.dossier

SYSTEME = """Tu écris le récit d'un documentaire vertical « Cauri raconte » (3 min 30 à 4 min 30) sur un artiste, pour Cauri Charts,
« la référence de la musique ouest-africaine ». Un épisode demandé par nos abonnés : on RESPECTE LA LÉGENDE, on raconte tout son
trajet en profondeur (où il a commencé, le déclic, chaque grand projet, les contrats, les records, aujourd'hui).

LE TON — le fondateur a dit « ça fait trop IA ». Écris comme un YouTubeur documentaire qui parle à un pote (façon Poisson Fécond) :
1. Ouvre sur une image ou un paradoxe concret tiré des données, JAMAIS sur un chiffre ou un « bienvenue ».
2. Tutoie le spectateur, glisse-toi dans sa tête (« Tu te dis sûrement… Sauf que… »).
3. Une émotion par fait (galère, fierté, ironie, surprise) au lieu d'empiler les dates. Pas de « En 2012… En 2013… » en série.
4. Contrastes en une phrase (« D'un côté… De l'autre… »).
5. Rythme : phrases très courtes pour l'impact (« 12 minutes. 20 000 billets. Fini. »), puis une phrase plus longue qui prend son élan.
6. Mots concrets et oraux ; INTERDITS : « immense », « majeur », « incroyable », « véritable », « sans précédent », « en effet »,
   « bienvenue », « reste jusqu'au bout », « le savais-tu », « la leçon », « vrai ou faux », « c'est faux ».
7. Fin de chaque chapitre sur un suspense qui donne envie de la suite (« Et c'est là qu'un certain Drake l'appelle… »).
8. Micro-scènes UNIQUEMENT avec des détails présents dans les données (jamais de foule, de météo, de dialogue inventés).

Le récit est une suite de BLOCS :
- {"type": "chapitre", "numero": "CHAPITRE 1", "titre": "OJUELEGBA", "annees": "1990 – 2009", "musique": "v12"} : 5 ou 6
  chapitres = les paliers. Le montage fait une pause et affiche le titre en plein écran. « musique » = id d'une VIDÉO de la
  médiathèque, un titre de cette époque, différent à chaque chapitre.
- {"type": "voix", "texte": "...", "voix": "[excited]", "medias": ["v3", "p2"], "carte": null, "contrat": null} : 1 à 2 phrases
  orales. « voix » = une balise d'émotion parmi [excited] [mysterious] [whispers] [confident] [laughs] [curious] [serious] [amazed]
  (ou ""). « medias » = 1 à 3 ids de la médiathèque à montrer pendant la phrase (bonne époque, bon sujet ; un id au plus 3 fois).
  « carte » = null ou {"grand": "11,8 MDS", "petit": "écoutes sur Spotify", "or": false} (5 à 7 cartes en tout).
  « contrat » = null ou {"n": 0} pour un contrat de « contrats_connus » (montant seulement s'il est fourni ; dis-le aussi en
  nairas ou en francs CFA avec les « equivalents », arrondis).
- LES SECRETS (4 à 6, au moins un par chapitre sauf le dernier), pris dans « mythes_et_secrets_verifies » (et, comme amorce
  seulement, « rumeurs_des_forums_non_verifiees »). Chaque secret a 2 temps écrits (le montage ajoute avant eux une jauge
  « secret débloqué ») :
  • LA RUMEUR : 1 ou 2 blocs voix avec "secret": {"n": 0, "temps": "rumeur"} : raconte la rumeur comme les gens la racontent
    (« Sur Reddit, des fans jurent que… », « Pendant des années, on a raconté que… »), avec suspense. Le 1er de ces blocs a
    "bulle": la rumeur en question courte, en CAPITALES, 70 caractères au plus (« DRAKE ET WIZKID EN STUDIO ENSEMBLE ? »).
  • LA VÉRITÉ : 1 à 3 blocs voix avec "secret": {"n": 0, "temps": "verite"} : la réponse avec la preuve tirée des données,
    racontée (« En réalité… », « Sauf que… », « Ce qu'on sait vraiment, c'est que… »). Jamais « vrai ou faux », jamais « faux ! ».
    Le verdict suit les données (vrai, faux ou à nuancer).
- {"type": "projet", "album_id": 123, "etiquette": "ALBUM · 2020", "morceau": "titre", "chiffre": "..."} : 3 à 5 grands projets
  présentés en musique (on entend 9 s de « morceau », qui doit être un de ses titres_phares). Le bloc voix juste avant
  l'annonce et dit ce qu'il représente.

Construction : ACCROCHE (avant le chapitre 1, 2 ou 3 blocs voix, 30 mots au plus, medias = ses vidéos les plus fortes) ; les
chapitres dans l'ordre chronologique ; dernier chapitre = aujourd'hui (nos classements Cauri Charts, ses chiffres, ce qu'il
représente pour l'Afrique de l'Ouest) ; une dernière idée forte et personnelle (pas « la leçon ») ; dernier bloc voix exact :
« Et toi, quelle légende mérite le prochain épisode ? Dis-le en commentaire. »

Règles absolues : UNIQUEMENT les faits fournis ; aucune date, chiffre, lieu, salle, record, citation ou nuance absents des données ;
jamais « Billboard » (dis « le classement américain ») ; jamais « le plus grand de tous ». 600 à 720 mots dits, au moins 45 blocs
voix, une balise d'émotion sur 2 blocs sur 3.
titre : haut (« LA LÉGENDE DE » ou « COMMENT » ou « POURQUOI »), nom (en capitales), bas (< 45 caractères).
legende_fr : 2 à 3 phrases avec une question aux abonnés ; legende_en : sa traduction.
Réponds en JSON strict : {"titre": {"haut": "", "nom": "", "bas": ""}, "blocs": [...], "legende_fr": "", "legende_en": ""}"""


# ---------------------------------------------------------------- écriture

def _deepseek(systeme: str, question: str, jetons: int = 9000) -> str | None:
    """DeepSeek : clé directe si elle est dans le fichier de secrets, sinon via OpenRouter (~0,01 $ par épisode)."""
    try:
        if env.get("DEEPSEEK_API_KEY", ""):
            r = requests.post("https://api.deepseek.com/chat/completions", timeout=400,
                              headers={"Authorization": "Bearer " + env.get("DEEPSEEK_API_KEY")},
                              json={"model": "deepseek-chat", "max_tokens": min(jetons, 8000),
                                    "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": question}]})
        else:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", timeout=900,
                              headers={"Authorization": "Bearer " + env.get("OPENROUTER_API_KEY", "")},
                              json={"model": "deepseek/deepseek-v4-pro", "max_tokens": jetons,
                                    "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": question}]})
        j = r.json()
        if "choices" not in j:
            raise RuntimeError(str(j)[:200])
        return j["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        log_write("studio", "warning", f"raconte : DeepSeek indisponible ({str(exc)[:150]})")
        return None


def _jetons_faits(texte: str) -> set:
    """Chiffres et noms propres d'un texte (pour refuser ce que la réécriture inventerait)."""
    t = str(texte or "")
    nombres = {re.sub(r"[\s  ]", "", n) for n in re.findall(r"\d[\d\s  ,.]*", t)}
    noms = {m for m in re.findall(r"(?<![.!?]\s)(?<!^)\b[A-ZÀ-Ý][\wÀ-ÿ'’-]{2,}", t)}
    return {n.strip(",.") for n in nombres if n.strip(",.")} | noms


def humanise(d: dict, donnees: dict) -> dict:
    """DeepSeek réécrit le ton (humain, oral) sans toucher aux faits ; bloc par bloc, tout ajout de chiffre ou de nom
    propre absent du bloc d'origine ET des données est refusé (le bloc garde le texte de Gemini)."""
    voix = [(i, b) for i, b in enumerate(d.get("blocs") or []) if b.get("type") == "voix"]
    if not voix:
        return d
    entree = [{"i": i, "texte": b.get("texte") or "", **({"secret": b["secret"]} if b.get("secret") else {})} for i, b in voix]
    rep = _deepseek("Tu es scénariste de documentaires YouTube francophones à millions de vues. Tu réécris le TON, jamais les faits.",
                    "Réécris chaque « texte » pour qu'il sonne comme un vrai YouTubeur documentaire qui parle à un pote (tutoiement, "
                    "phrases courtes et vivantes, contrastes, ironie légère, relances), et plus du tout comme une IA ou une fiche "
                    "Wikipédia. RÈGLES : garde EXACTEMENT les mêmes faits, chiffres, dates et noms ; n'ajoute AUCUN fait, détail de "
                    "scène, chiffre ou nom ; garde la même longueur à 20 % près ; pas de « vrai ou faux », « le savais-tu », « la "
                    "leçon », « immense », « majeur », « incroyable » ; le dernier bloc reste mot pour mot. Rends la même liste JSON "
                    "[{\"i\": .., \"texte\": \"..\"}], rien d'autre.\n\n" + json.dumps(entree, ensure_ascii=False))
    if not rep:
        return d
    m = re.search(r"\[.*\]", rep, re.S)
    try:
        neufs = {int(x["i"]): str(x["texte"]).strip() for x in json.loads(m.group(0)) if str(x.get("texte") or "").strip()} if m else {}
    except (ValueError, TypeError, KeyError):
        return d
    tout = json.dumps(donnees, ensure_ascii=False)
    refuses = 0
    for i, b in voix[:-1]:
        n = neufs.get(i)
        if not n:
            continue
        nouveaux = _jetons_faits(n) - _jetons_faits(b.get("texte"))
        if any(x not in tout for x in nouveaux):
            refuses += 1
            continue
        b["texte"] = n
    log_write("studio", "info", f"raconte v4 : ton réécrit par DeepSeek, {refuses} bloc(s) refusé(s) (fait ajouté)")
    return d


def _consigne_angle(donnees: dict) -> str:
    """17/11/2026 : « changer de thème, pas juste des thèmes positifs, intriguer de différentes manières » : quand un angle est
    donné, le récit est construit autour de lui (une chute, un scandale, un retour…) au lieu de toute la carrière."""
    angle = str(donnees.get("angle") or "").strip()
    if not angle:
        return ""
    return ("\n\nANGLE IMPOSÉ PAR LA RÉDACTION (prioritaire sur la construction ci-dessus) : « " + angle + " ».\n"
            "- Le récit raconte CET angle, pas toute la carrière : 1 chapitre court suffit pour dire qui il était au sommet, le reste "
            "suit l'angle dans l'ordre des faits. Les chapitres peuvent être sombres (chute, prison, saisie, scandale) : c'est voulu, "
            "pour intriguer autrement ; la fin peut retourner l'histoire si les faits le permettent.\n"
            "- « faits_verifies_par_la_redaction » sont les faits centraux de l'angle : utilise-les tous, avec leurs chiffres exacts.\n"
            "- Faits négatifs : ton factuel, jamais moqueur ni accusateur. Une accusation, une enquête ou une détention n'est PAS une "
            "condamnation : dis « soupçonné », « lié à », « interrogé », « libéré sous caution » ; ne dis « condamné » que si les "
            "données le disent, avec la peine exacte. Jamais d'insulte, jamais d'avis sur sa culpabilité.\n"
            "- Le titre suit l'angle (haut « COMMENT » ou « POURQUOI » de préférence).")


def ecrit(donnees: dict) -> dict:
    from core.services import ai
    from core.services.platforms import HttpClient
    from core.services.social.studio_raconte import _chiffres_dits, _ecrit_juste, _phonetique, _propre
    client = ai.FallbackClient([ai.GeminiClient(HttpClient(300))] + [c for c in [ai.make()] if c])
    publiques = json.dumps({k: v for k, v in donnees.items() if not k.startswith("_")}, ensure_ascii=False, indent=1)
    os.environ["GEMINI_REFLEXION"] = "high"
    try:
        d = ai.extract_json(client.ask(SYSTEME + _consigne_angle(donnees), "Données vérifiées (n'utilise rien d'autre) :\n" + publiques,
                                       16000)["text"]) or {}
        try:
            v = client.ask("Tu es vérificateur des faits d'un média musical. Tu compares un récit aux données, bloc par bloc.",
                           "Données (seule vérité) :\n" + publiques + "\n\nRécit :\n" + json.dumps(d, ensure_ascii=False)
                           + "\n\nToute affirmation absente des données, exagérée ou contraire (années, lieux, salles, nombres, montants, "
                           "« N°1 », « record », « premier », « d'affilée »…) doit être corrigée ou retirée. La vérité de chaque secret "
                           "suit les données. Vérifie les album_id, les « morceau » (titres_phares) et que chaque id de « medias » et "
                           "« musique » existe. Garde le ton, la longueur, les balises et la construction. Rends le même JSON, rien d'autre.",
                           16000)
            d2 = ai.extract_json(v["text"]) or {}
            if len(d2.get("blocs") or []) >= 0.8 * len(d.get("blocs") or []):
                d = d2
        except Exception as exc:  # noqa: BLE001
            log_write("studio", "warning", f"raconte : relecture des faits indisponible ({exc})")
    finally:
        os.environ.pop("GEMINI_REFLEXION", None)
    d = humanise(d, {k: v for k, v in donnees.items() if not k.startswith("_")})
    return nettoie(d, donnees, _propre, _chiffres_dits, _ecrit_juste, _phonetique)


def nettoie(d: dict, donnees: dict, _propre, _chiffres_dits, _ecrit_juste, _phonetique) -> dict:
    ids = {m["id"] for m in donnees.get("mediatheque") or []}
    videos = {m["id"] for m in donnees.get("mediatheque") or [] if m["type"] != "photo"}
    projets = {p["album_id"]: p for p in donnees.get("discographie", {}).get("projets", [])}
    les_mythes, les_contrats = donnees.get("mythes_et_secrets_verifies") or [], donnees.get("contrats_connus") or []
    blocs = []
    for x in d.get("blocs") or []:
        t = x.get("type")
        if t == "chapitre" and str(x.get("titre") or "").strip():
            blocs.append({"type": "chapitre", "numero": str(x.get("numero") or "").upper()[:20], "titre": _propre(x["titre"]).upper()[:28],
                          "annees": str(x.get("annees") or "")[:20], "musique": x.get("musique") if x.get("musique") in videos else "",
                          "musique_mode": x.get("musique_mode") if x.get("musique_mode") in FOND else "instru"})
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
            if INTERDITS.search(texte):
                log_write("studio", "info", f"raconte v4 : tournure à revoir : {texte[:80]}")
            balise = re.match(r"\s*(\[[a-z ]{3,20}\])", str(x.get("voix") or ""))
            c = x.get("carte") if isinstance(x.get("carte"), dict) and str((x.get("carte") or {}).get("grand") or "").strip() else None
            b = {"type": "voix", "texte": texte[:260], "voix": ((balise.group(1) + " ") if balise else "") + _phonetique(texte)[:300],
                 "medias": [m for m in (x.get("medias") or []) if m in ids][:3],
                 "carte": {"grand": str(c["grand"]).strip()[:18].upper(), "petit": _ecrit_juste(str(c.get("petit") or ""))[:60],
                           "or": bool(c.get("or"))} if c else None}
            try:
                n = int((x.get("contrat") or {}).get("n"))
                b["contrat"] = {k: v for k, v in les_contrats[n].items() if k != "sources"}
            except (TypeError, ValueError, IndexError, AttributeError):
                pass
            s = x.get("secret") if isinstance(x.get("secret"), dict) else None
            if s and s.get("temps") in ("rumeur", "verite"):
                try:
                    n = int(s.get("n"))
                    b["secret"] = {"n": n, "temps": s["temps"]}
                    if 0 <= n < len(les_mythes):
                        b["mythe"] = {k: v for k, v in les_mythes[n].items() if k != "sources"}
                except (TypeError, ValueError):
                    pass
                if s["temps"] == "rumeur" and str(x.get("bulle") or "").strip():
                    b["bulle"] = _propre(str(x["bulle"])).upper()[:80]
            blocs.append(b)
    fin = next((i for i, b in enumerate(blocs) if b["type"] == "voix" and "prochain épisode" in b["texte"]), None)
    if fin is not None:
        blocs = blocs[:fin + 1]
    voix = [b for b in blocs if b["type"] == "voix"]
    if len(voix) < 25:
        raise RuntimeError("le récit écrit par l'IA est trop court pour un documentaire : relance le projet")
    voix[-1]["carte"] = None
    t = d.get("titre") or {}
    return {"v": 4, "titre": {"haut": str(t.get("haut") or "LA LÉGENDE DE").upper()[:16], "nom": str(t.get("nom") or donnees["artiste"]).upper()[:22],
                              "bas": _propre(t.get("bas")).upper()[:60]},
            "phrases": blocs[:140], "fin": {"titre": "TA LÉGENDE ?", "texte": "Écris-la en commentaire : prochain épisode"},
            "sources": donnees["_sources"][:300], "legende_fr": _propre(d.get("legende_fr"))[:900], "legende_en": _propre(d.get("legende_en"))[:900]}


# ---------------------------------------------------------------- sons

def instrumentales(travaux: list[tuple[str, str]]) -> None:
    """Chant retiré (iZotope RX 12 Music Rebalance, qualité « Best ») pour chaque (wav d'entrée, wav de sortie), en un seul
    processus (le plugin met ~25 s à se charger)."""
    if not travaux:
        return
    code = ("import json,sys\nfrom pedalboard import load_plugin\nfrom pedalboard.io import AudioFile\n"
            f"pl=load_plugin(r'{RX}')\npl.vocal_mute=True\npl.quality='Best / Offline'\n"
            "for a,b in json.load(open(sys.argv[1],encoding='utf-8')):\n"
            "    f=AudioFile(a); x=f.read(f.frames); sr=f.samplerate; f.close()\n"
            "    pl.reset(); y=pl.process(x,sr)\n"
            "    o=AudioFile(b,'w',sr,y.shape[0]); o.write(y); o.close()\n")
    liste = os.path.join(os.path.dirname(travaux[0][1]), "rx.json")
    json.dump(travaux, open(liste, "w", encoding="utf-8"))
    try:
        subprocess.run([PYTHON_STUDIO, "-c", code, liste], check=True, capture_output=True, timeout=600 + 120 * len(travaux))
    except (subprocess.SubprocessError, OSError) as exc:
        log_write("studio", "warning", f"raconte v4 : instrumentales impossibles, chant gardé très bas ({str(exc)[:150]})")


def _extrait_wav(src: str, sortie: str, depuis: float, duree: float) -> None:
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0, depuis):.2f}", "-i", src, "-t", f"{duree + 1:.2f}", "-vn",
                    "-ar", "44100", "-ac", "2", sortie], check=True)


def _vers_mp3(wav: str, sortie: str) -> None:
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.5",
                    "-ar", "44100", "-ac", "2", "-b:a", "192k", sortie], check=True)


def _extrait_parle(x: dict, dossier: str, k: int) -> tuple[str, str, float] | None:
    """16/11/2026 (« fais passer le podcast là où il le dit, même quelques secondes ») : un passage d'interview où l'artiste
    parle lui-même. Vidéo verticale (image entière sur fond flou), bandeau « EXTRAIT · source » en haut, sa phrase en grand
    en bas ; le son de l'interview à la place de la voix off, musique coupée."""
    src = x["fichier"] if os.path.isabs(x["fichier"]) else os.path.join(CACHE, x["fichier"])
    if not os.path.isfile(src):
        return None
    duree = float(x["duree"])
    polices = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "resources", "fonts")
    anton = os.path.abspath(os.path.join(polices, "Anton-Regular.ttf")).replace("\\", "/").replace(":", "\\:")
    haut = os.path.join(dossier, f"x{k}-haut.txt")
    open(haut, "w", encoding="utf-8").write(("EXTRAIT · " + (x.get("source") or "")).upper())
    esc = lambda f: f.replace("\\", "/").replace(":", "\\:")
    lignes = ""   # la citation : une ligne par drawtext, chacune centrée
    morceaux_txt = [l for l in (x.get("citation") or "").split("\n") if l.strip()][:4]
    taille = min(78, int(2050 / max(10, max((len(l.strip()) for l in morceaux_txt), default=10))))   # les longues lignes rapetissent
    for j, ligne in enumerate(morceaux_txt):
        fl = os.path.join(dossier, f"x{k}-l{j}.txt")
        open(fl, "w", encoding="utf-8").write(ligne.strip())
        lignes += (f"drawtext=fontfile='{anton}':textfile='{esc(fl)}':fontsize={taille}:fontcolor=0xF5C14B:borderw=5:bordercolor=black@0.85:"
                   f"x=(w-tw)/2:y={1360 + j * int(taille * 1.28)},")
    vf = (f"split[a][b];[a]scale=-2:1920,crop=1080:1920,boxblur=28:2,eq=brightness=-0.22:saturation=1.2[f];[b]scale=1080:-2[v];"
          f"[f][v]overlay=0:(H-h)/2-80,"
          f"drawbox=x=0:y=300:w=iw:h=86:color=0x7B5CFF@0.92:t=fill,"
          f"drawtext=fontfile='{anton}':textfile='{esc(haut)}':fontsize=40:fontcolor=white:x=(w-tw)/2:y=322,"
          f"{lignes}fps=30,setsar=1")
    mp4, mp3 = os.path.join(dossier, f"x{k}.mp4"), os.path.join(dossier, f"x{k}.mp3")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{float(x.get('debut') or 0):.2f}", "-i", src, "-t", f"{duree:.2f}", "-an",
                    "-filter_complex", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", mp4], check=True)
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{float(x.get('debut') or 0):.2f}", "-i", src, "-t", f"{duree:.2f}", "-vn",
                    "-af", "loudnorm=I=-15:TP=-1.5:LRA=9,afade=t=in:d=0.15,afade=t=out:st=" + f"{max(0, duree - 0.3):.2f}" + ":d=0.3",
                    "-ar", "44100", "-ac", "2", "-b:a", "192k", mp3], check=True)
    return mp4, mp3, duree


# ---------------------------------------------------------------- images

def _telecharge(m: dict) -> str | None:
    """Clip ou photo, gardé en cache (une relance ne retélécharge rien)."""
    os.makedirs(CACHE, exist_ok=True)
    if m.get("fichier"):   # 16/11 : extrait préparé à la main (moment précis d'un reportage), dans le cache
        f = m["fichier"] if os.path.isabs(m["fichier"]) else os.path.join(CACHE, m["fichier"])
        return f if os.path.isfile(f) else None
    if m["type"] == "photo":
        nom = "ph-" + re.sub(r"[^a-z0-9]", "", _cle(m.get("url") or ""))[-40:] + ".jpg"
        chemin = os.path.join(CACHE, nom)
        if os.path.isfile(chemin):
            return chemin
        from core.services.social.raconte_v2 import _photo
        try:
            return _photo(m["url"], CACHE, nom)
        except Exception:  # noqa: BLE001
            return None
    chemin = os.path.join(CACHE, m["yt"] + ".mp4")
    if not os.path.isfile(chemin):
        from core.services.social import refrain as RF
        chemin = RF.telecharge(m["yt"], CACHE)
    if chemin:
        info = chemin + ".json"
        try:
            m["statique"] = json.load(open(info))["statique"]
        except (OSError, ValueError, KeyError):
            m["statique"] = V3._statique(chemin)
            json.dump({"statique": m["statique"]}, open(info, "w"))
    return chemin


def _morceau(p: dict, prets: dict, medias: dict, titre: str) -> str | None:
    """L'id de la vidéo du morceau EXACT cité (« pour chaque projet, c'est SON son »), téléchargée ; sinon recherche."""
    k = _cle(re.split(r"\s*\(|\s+feat|\s+ft\.?", titre or "", flags=re.I)[0])
    if not k:
        return None
    candidats = [i for i, m in medias.items() if m["type"] != "photo" and not m.get("fichier") and (
        _cle(re.split(r"\s*\(|\s+ft\.?|\s+feat", m["titre"], flags=re.I)[0]) == k
        or (len(k) >= 4 and re.search(r"[\"«“”»]\s*" + re.escape(titre.split("(")[0].strip()) + r"\s*[\"»”“«]", m["titre"], re.I)))]
    candidats.sort(key=lambda i: (medias[i]["type"] != "clip", -(medias[i].get("vues") or 0)))
    for i in candidats:
        if i not in prets:
            ch = _telecharge(medias[i])
            if ch:
                medias[i]["_chemin"] = ch
                prets[i] = medias[i]
        if i in prets:
            return i
    from core.services.social.raconte_v2 import video_morceau
    v = video_morceau(int(p["artiste_id"]), p.get("artiste") or "", titre, CACHE)
    if v:
        i = "m-" + k[:20]
        prets[i] = {"id": i, "type": "clip", "titre": titre, "_chemin": v, "_duree": _duree(v)}
        return i
    return None


# ---------------------------------------------------------------- montage

def construit(job_id: int, p: dict, dossier: str, prefixe: str) -> dict:
    from core.services.social import refrain as RF
    from core.services.social.raconte_v2 import _photo, dit
    from core.services.social.studio_raconte import POSES, _sous_titres
    recit, blocs = p["recit"], p["recit"]["phrases"]
    thriller = p.get("ouverture") == "thriller"   # 17/11/2026 : épisodes sombres (chute, scandale)
    medias = {m["id"]: dict(m) for m in p.get("medias") or []}
    # 1) médias demandés + les plus vus (accroche), en parallèle, depuis le cache
    voulus = {i for b in blocs for i in (b.get("medias") or [])} | {b.get("musique") for b in blocs if b.get("musique")}
    stars = [m["id"] for m in sorted((m for m in medias.values() if m["type"] != "photo" and not m.get("fichier")), key=lambda m: -(m.get("vues") or 0))[:6]]
    voulus = [i for i in voulus | set(stars) if i in medias]
    with ThreadPoolExecutor(3) as pool:
        for i, chemin in zip(voulus, pool.map(lambda i: _telecharge(medias[i]), voulus)):
            medias[i]["_chemin"] = chemin
    prets = {i: m for i, m in medias.items() if m.get("_chemin")}
    videos_ok = [i for i, m in prets.items() if m["type"] != "photo" and not m.get("statique")]
    if len(videos_ok) < 3:
        raise RuntimeError("moins de 3 vidéos disponibles : YouTube bloque peut-être ce PC, relance dans quelques heures")
    for i in videos_ok:
        prets[i]["_cadre"] = V3._cadre(prets[i]["_chemin"])
        prets[i]["_duree"] = _duree(prets[i]["_chemin"])
        prets[i]["_pris"] = 0
    for i, m in prets.items():
        if m["type"] == "photo":
            V3._fond_photo(m["_chemin"], os.path.join(dossier, f"{i}-fond.jpg"))

    # 2) déroulé : voix, pauses de chapitre (titre plein écran), pauses de secret (jauge), projets
    # 16/11/2026 : « joue souvent les musiques pour les titres, pour la nostalgie et l'intrigue » : après une phrase qui cite
    # un titre entre « », on entend 3,6 s de son refrain chanté sur son clip (une fois par titre, 8 au plus, jamais un projet)
    court = lambda t_: _cle(re.split(r"\s*\(|\s+feat|\s+ft\.?", t_ or "", flags=re.I)[0])
    deja_chante = {court(b.get("titre")) for b in blocs if b.get("type") == "projet"} | {court(b.get("morceau")) for b in blocs if b.get("type") == "projet"}
    n_chante = [0]

    def titres_cites(b):
        out = []
        for t_ in re.findall(r"«\s*([^»]{2,40}?)\s*»", b.get("texte") or ""):
            k_ = court(t_)
            if k_ and k_ not in deja_chante and n_chante[0] < CHANTES_MAX and b.get("type", "voix") == "voix" and not b.get("secret"):
                deja_chante.add(k_)
                n_chante[0] += 1
                out.append(t_)
        return out[:1]
    evts, cur, vus = [], [], set()
    for b in blocs:
        if b.get("type") == "projet":
            evts += [("voix", cur)] if cur else []
            cur = []
            evts.append(("projet", b))
        elif b.get("type") == "extrait":
            evts += [("voix", cur)] if cur else []
            cur = []
            evts.append(("extrait", b))
        elif b.get("type") == "chapitre":
            evts += [("voix", cur)] if cur else []
            cur = []
            evts.append(("titre", b))
        else:
            s = b.get("secret") or {}
            if s.get("temps") == "rumeur" and s.get("n") not in vus:
                vus.add(s.get("n"))
                evts += [("voix", cur)] if cur else []
                cur = []
                evts.append(("jauge", s.get("n")))
            cur.append(b)
            for titre_cite in titres_cites(b):
                evts += [("voix", cur)] if cur else []
                cur = []
                evts.append(("chante", titre_cite))
    if cur:
        evts.append(("voix", cur))
    total_secrets = max(1, len(vus))
    t, mots, morceaux, sfx, bornes = 0.25, [], [], [], []
    projets, titres, secrets, pauses, extraits, chantes = [], [], [], [], [], []
    k_voix, k_secret, chap_courant = 0, 0, None
    for genre, x in evts:
        if genre == "titre":
            if thriller:
                bruit = MACHINE["bruit"] if not titres else 0.0   # boom + parasites seulement avant le chapitre 1
                frappes, long_c = _machine_temps(x.get("numero") or "", x["titre"], bruit)
                if bruit:
                    sfx.append({"src": SFX["boom"], "d": round(t, 3), "vol": 0.85})
                    sfx.append({"src": SFX["parasite"], "d": round(t + 0.12, 3), "vol": 0.32, "dur": bruit})
                for j_, f_ in enumerate(frappes):
                    sfx.append({"src": SFX["frappes"][j_ % 3], "d": round(t + f_, 3), "vol": 0.55, "dur": 0.3})
                sfx.append({"src": SFX["sonnette"], "d": round(t + long_c - MACHINE["tenue"] + 0.1, 3), "vol": 0.4, "dur": 1.2})
                titres.append({"d": round(t, 3), "f": round(t + long_c, 3), "numero": x.get("numero") or "", "titre": x["titre"],
                               "annees": x.get("annees") or "", "style": "machine", "bruit": bruit, "_b": x})
                pauses.append((t, t + long_c))
                t += long_c + 0.15
                continue
            titres.append({"d": round(t, 3), "f": round(t + PAUSE_CHAPITRE, 3), "numero": x.get("numero") or "", "titre": x["titre"],
                           "annees": x.get("annees") or "", "_b": x})
            # 15/11/2026 : « plus de riser à chaque début » : le titre de chapitre arrive en silence, avec son titre chanté
            pauses.append((t, t + PAUSE_CHAPITRE))
            t += PAUSE_CHAPITRE + 0.15
            continue
        if genre == "jauge":
            secrets.append({"d": round(t, 3), "k": k_secret, "total": total_secrets, "_n": x})
            sfx.append({"src": SFX["unlock"], "d": round(t + 1.2, 3), "vol": 0.45, "dur": PAUSE_SECRET - 1.3})
            pauses.append((t, t + PAUSE_SECRET))
            k_secret += 1
            t += PAUSE_SECRET + 0.1
            continue
        if genre == "chante":
            mid = _morceau(p, prets, medias, x)
            m = prets.get(mid) if mid else None
            if m and m["type"] != "photo":
                try:
                    if "_duree" not in m:
                        m["_duree"] = _duree(m["_chemin"])
                    if "_cadre" not in m:
                        m["_cadre"] = V3._cadre(m["_chemin"])
                    try:
                        r0, _ = RF.refrain(m["_chemin"], duree=DUREE_CHANTE)
                    except Exception:  # noqa: BLE001
                        r0 = m["_duree"] * 0.3
                    nom = f"c{len(chantes):02d}"
                    wav, mp3 = os.path.join(dossier, nom + ".wav"), os.path.join(dossier, nom + ".mp3")
                    _extrait_wav(m["_chemin"], wav, r0, DUREE_CHANTE)
                    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", wav, "-t", f"{DUREE_CHANTE:.2f}", "-af",
                                    f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.25,afade=t=out:st={DUREE_CHANTE - 0.5:.2f}:d=0.5",
                                    "-ar", "44100", "-ac", "2", "-b:a", "192k", mp3], check=True)
                    V3._plan(m, dossier, nom + ".mp4", r0, DUREE_CHANTE, "plein" if m["type"] != "live" else "cadre")
                    morceaux.append((t, mp3))   # le refrain, à la place de la voix off
                    chantes.append({"src": f"{prefixe}/{nom}.mp4", "d": round(t, 3), "f": round(t + DUREE_CHANTE, 3),
                                    "libelle": "EN ÉCOUTE · " + x.upper()[:34]})
                    pauses.append((t, t + DUREE_CHANTE))
                    t += DUREE_CHANTE + 0.2
                except (subprocess.SubprocessError, OSError) as exc:
                    log_write("studio", "warning", f"raconte v4 : refrain de « {x} » impossible ({str(exc)[:120]})")
            continue
        if genre == "extrait":
            r = _extrait_parle(x, dossier, len(extraits))
            if r:
                mp4, mp3, dx = r
                morceaux.append((t, mp3))   # sa vraie voix, dans la piste de la voix off
                extraits.append({"src": f"{prefixe}/{os.path.basename(mp4)}", "d": round(t, 3), "f": round(t + dx, 3)})
                pauses.append((t, t + dx))   # musique coupée, aucun autre plan par-dessus
                t += dx + 0.3
            else:
                log_write("studio", "warning", f"raconte v4 : extrait introuvable ({x.get('fichier')})")
            continue
        if genre == "projet":
            projets.append({**x, "d": round(t, 3), "f": round(t + DUREE_PROJET, 3)})
            sfx.append({"src": SFX["projet"], "d": round(max(0, t - 0.4), 3), "vol": 0.28, "dur": 1.8})
            t += DUREE_PROJET + 0.3
            continue
        dites = [b for b in x if b.get("type") == "voix"]
        textes = []
        for b in dites:
            v = b.get("voix") or b["texte"]
            bal = re.match(r"\s*(\[[a-z ]{3,20}\])\s*", v)
            textes.append(((bal.group(1) + " ") if bal else "") + (v[bal.end():] if bal else v))
        import hashlib   # prises gardées dans le cache, par texte : une relance ne repaie jamais ElevenLabs
        cle_voix = hashlib.sha1((" ".join(textes) + ("|thriller" if thriller and not titres else "")).encode("utf-8")).hexdigest()[:16]
        os.makedirs(os.path.join(CACHE, "voix"), exist_ok=True)
        brut, memo = os.path.join(CACHE, "voix", cle_voix + ".mp3"), os.path.join(CACHE, "voix", cle_voix + ".json")
        dits = None
        try:
            m0 = json.load(open(memo, encoding="utf-8"))
            if m0.get("texte") == " ".join(textes) and os.path.isfile(brut):
                dits = m0["mots"]
        except (OSError, ValueError):
            pass
        if dits is None:
            if thriller and not titres:   # accroche du mode thriller : plus lente (pas d'accélération), plus libre
                dits = dit(" ".join(textes), brut, accel=0.97, stabilite=0.3)
            else:
                dits = dit(" ".join(textes), brut)
            json.dump({"texte": " ".join(textes), "mots": dits}, open(memo, "w", encoding="utf-8"), ensure_ascii=False)
        mp3 = os.path.join(dossier, f"v{k_voix:02d}n.mp3")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", brut, "-af", "loudnorm=I=-15:TP=-1.5:LRA=9", "-ar", "44100", "-ac", "2",
                        "-b:a", "192k", mp3], check=True)
        d = _duree(mp3)
        morceaux.append((t, mp3))
        pos = 0
        for b, txt in zip(dites, textes):
            n_mots = len([m for m in re.sub(r"\[[^\]]*\]", " ", txt).split() if any(ch.isalnum() for ch in m)])
            part = dits[pos:pos + n_mots] or dits[-1:]
            pos += n_mots
            a, z = t + (part[0]["d"] if part else 0), t + (part[-1]["f"] if part else d)
            mots += _sous_titres(b["texte"], part, t, z - a)
            bornes.append([a, z, b])
        t += d + PAUSE
        k_voix += 1
    fin_voix = t - PAUSE
    for ex in extraits:   # 16/11 : pendant qu'il parle lui-même, aucun sous-titre de la voix off par-dessus sa citation
        mots = [m for m in mots if m["f"] <= ex["d"] or m["d"] >= ex["f"]]
    duree = round(fin_voix + 3.6, 2)
    fin_d = bornes[-1][0]
    for i, x in enumerate(bornes):
        x[1] = bornes[i + 1][0] if i + 1 < len(bornes) and bornes[i + 1][0] - x[1] < 2 else x[1] + PAUSE
    entrees = []
    for _, chemin in morceaux:
        entrees += ["-i", chemin]
    filtres = "".join(f"[{j}:a]adelay={int(d0 * 1000)}|{int(d0 * 1000)}[a{j}];" for j, (d0, _) in enumerate(morceaux))
    filtres += "".join(f"[a{j}]" for j in range(len(morceaux))) + f"amix=inputs={len(morceaux)}:normalize=0,apad=whole_dur={duree}[out]"
    subprocess.run([_ffmpeg(), "-v", "error", "-y", *entrees, "-filter_complex", filtres, "-map", "[out]", "-t", f"{duree}", "-ar", "44100",
                    "-ac", "2", "-b:a", "192k", os.path.join(dossier, "voix.mp3")], check=True)

    # 3) secrets : bulle de BD (rumeur) au-dessus de la mascotte, « LA VÉRITÉ », ambiance de suspense, musique coupée
    bulles, verites, suspense, mascottes = [], [], [], []
    for s in secrets:
        rum = [x for x in bornes if (x[2].get("secret") or {}).get("n") == s["_n"] and x[2]["secret"]["temps"] == "rumeur"]
        ver = [x for x in bornes if (x[2].get("secret") or {}).get("n") == s["_n"] and x[2]["secret"]["temps"] == "verite"]
        if not rum:
            continue
        a, z = rum[0][0], rum[-1][1]
        texte = next((x[2].get("bulle") for x in rum if x[2].get("bulle")), "") or rum[0][2]["texte"][:80].upper()
        cote = "gauche" if len(bulles) % 2 == 0 else "droite"
        bulles.append({"d": round(a - 0.1, 3), "f": round(z, 3), "texte": texte, "cote": cote, "cri": "PSST !" if len(bulles) % 2 == 0 else "CHUT…"})
        mascottes.append({"src": POSES["question"], "d": round(a - 0.2, 3), "f": round(z + 0.1, 3), "cote": cote, "h": 820})
        sfx.append({"src": SFX["bulle"], "d": round(a - 0.1, 3), "vol": 0.4, "dur": 0.6})
        fin_suspense = ver[0][0] if ver else z
        suspense.append((s["d"], fin_suspense))
        if ver:
            verites.append({"d": round(ver[0][0], 3), "f": round(ver[0][0] + 2, 3)})
            sfx.append({"src": SFX["verite"], "d": round(ver[0][0] - 0.05, 3), "vol": 0.3, "dur": 1.6})

    # 4) cartes et contrats (jamais en même temps qu'une bulle, « la vérité », un titre ou une jauge : plus de chevauchement)
    occupes = [(b["d"] - 0.2, b["f"] + 0.2) for b in bulles] + [(v["d"] - 0.2, v["f"]) for v in verites] + \
              [(x["d"], x["f"]) for x in titres] + [(x["d"], x["d"] + PAUSE_SECRET) for x in secrets]
    libre = lambda a, b: not any(a < y and b > x for x, y in occupes)  # noqa: E731
    cartes, contrats = [], []
    for a, z, b in bornes:
        if b is bornes[-1][2] or a < 3.8:
            continue
        if b.get("contrat"):
            c = b["contrat"]
            eq = c.get("equivalents") or {}
            fin = max(z, a + 3.2)
            if libre(a, fin):
                quoi = re.split(r"\s*[/(]", c.get("quoi") or "")[0].strip()
                contrats.append({"d": round(a, 3), "f": round(fin, 3), "quoi": quoi[:48], "avec": re.split(r"\s*\(", c.get("avec") or "")[0][:40],
                                 "annee": c.get("annee") or "", "montant": eq.get("usd") or "", "devises": [x for x in (eq.get("ngn"), eq.get("xof")) if x]})
                occupes.append((a, fin))
                sfx.append({"src": SFX["carte"], "d": round(a, 3), "vol": 0.16, "dur": 1.2})
        elif b.get("carte"):
            c = b["carte"]
            d0, f0 = a + 0.12, min(max(z, a + 1.8), a + 4.4)
            if libre(d0, f0):
                cartes.append({"d": round(d0, 3), "f": round(f0, 3), "grand": c["grand"], "petit": c.get("petit") or "", "or": bool(c.get("or"))})
                occupes.append((d0, f0))
                sfx.append({"src": SFX["carte"], "d": round(d0, 3), "vol": 0.14, "dur": 1.2})

    # 5) plans : accroche en plans éclair, puis les médias de chaque phrase ; rien sous les écrans plein cadre
    n_plan = [0]
    styles = ["plein", "plein", "cadre"]

    def coupe(mid, a, b, nu=False):
        m = prets.get(mid)
        if not m or b - a < 0.3:
            return None
        nom = f"p{n_plan[0]:03d}"
        n_plan[0] += 1
        if m["type"] == "photo":
            copie = os.path.join(dossier, os.path.basename(m["_chemin"]))
            if not os.path.isfile(copie):
                shutil.copyfile(m["_chemin"], copie)
            return {"src": f"{prefixe}/{os.path.basename(copie)}", "fond": f"{prefixe}/{mid}-fond.jpg", "d": round(a, 3),
                    "f": round(b, 3), "image": True, **({} if nu else {"annee": m.get("annee") or "", "credit": m.get("credit") or ""})}
        if mid not in videos_ok:
            return None
        ratio = 0.1 + (0.78 * ((m["_pris"] * 0.381966 + hash(mid) % 7 * 0.07) % 1))
        m["_pris"] += 1
        if "_haut" not in m:
            out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0",
                                  m["_chemin"]], capture_output=True, text=True).stdout
            m["_haut"] = int((re.search(r"\d+", out or "") or [0])[0] or 0)
        style = styles[n_plan[0] % 3] if m["type"] != "live" and m["_haut"] >= 700 else "cadre"
        V3._plan(m, dossier, nom + ".mp4", m["_duree"] * ratio, b - a, style)
        return {"src": f"{prefixe}/{nom}.mp4", "d": round(a, 3), "f": round(b, 3),
                **({} if nu else {"annee": m.get("annee") if m["type"] != "clip" else "",
                                  "libelle": m.get("libelle") or {"live": "LIVE", "coulisses": "COULISSES"}.get(m["type"], "")})}

    plein_ecran = pauses + [(x["d"], x["f"]) for x in projets]
    les_plans, flashs = [], []
    stars_ok = [i for i in stars if i in videos_ok] or videos_ok[:4]
    accroche_fin = titres[0]["d"] if titres else 6.0
    t0, j = 0.0, 0
    while t0 < accroche_fin - 0.2:
        long = 0.55 if t0 < 3.6 else 0.9
        c = coupe(stars_ok[j % len(stars_ok)], t0, min(t0 + long, accroche_fin), nu=True)
        if c:
            les_plans.append(c)
            flashs.append(round(t0, 3))
        t0 += long
        j += 1
    rot = [0]
    for a, z, b in bornes:
        if a < accroche_fin - 0.05 or b is bornes[-1][2]:
            continue
        ids = [i for i in (b.get("medias") or []) if i in prets and (prets[i]["type"] == "photo" or i in videos_ok)]
        if not ids:
            hasard_ok = [i for i in videos_ok if not prets[i].get("fichier")] or videos_ok
            ids = [hasard_ok[rot[0] % len(hasard_ok)]]
            rot[0] += 1
        cur_t, n = a, 0
        while cur_t < z - 0.25:
            mid = ids[n % len(ids)]
            long = 2.6 if prets[mid]["type"] == "photo" else (1.7 if n % 2 else 2.3)
            fin = min(cur_t + long, z)
            if z - fin < 0.9:
                fin = z
            if not any(x <= cur_t < y for x, y in plein_ecran):
                c = coupe(mid, cur_t, fin, nu=not libre(cur_t, fin))   # sans étiquette sous une bulle ou une carte
                if c:
                    les_plans.append(c)
            cur_t, n = fin, n + 1
    les_plans += extraits + chantes   # les extraits parlés et les refrains (image déjà montée)
    photo = _photo(p.get("photo"), dossier, "photo.jpg") if p.get("photo") else None
    if photo:
        V3._fond_photo(photo, os.path.join(dossier, "photo-fond.jpg"))
        les_plans.append({"src": f"{prefixe}/photo.jpg", "fond": f"{prefixe}/photo-fond.jpg", "d": round(fin_d, 3), "f": duree, "image": True})

    # 5 bis) zones sensibles floutées dans chaque plan vidéo (17/11/2026)
    n_flous = 0
    for pl in les_plans:
        src = str(pl.get("src") or "")
        if not pl.get("image") and src.endswith(".mp4") and src.startswith(prefixe + "/"):
            chemin = os.path.join(dossier, src[len(prefixe) + 1:])
            if os.path.isfile(chemin):
                try:
                    n_flous += 1 if floute_zones(chemin) else 0
                except Exception as exc:  # noqa: BLE001
                    log_write("studio", "warning", f"raconte : floutage impossible pour {src} ({str(exc)[:120]})")
    log_write("studio", "info", f"raconte v4 : zones sensibles floutées dans {n_flous} plan(s)")

    # 6) musiques : instrumentales sous la voix (réglage par chapitre), titres de chapitre et projets chantés, suspense aux secrets
    musiques, rx, n_mus = [], [], [0]
    pool_musique = [i for i in sorted(prets, key=lambda i: -(prets[i].get("vues") or 0)) if prets[i]["type"] != "photo" and not prets[i].get("fichier")]

    def extrait(mid, long, instru):
        m = prets.get(mid)
        if not m or m["type"] == "photo":
            return None
        try:
            r0, _ = RF.refrain(m["_chemin"], duree=min(long, 30))
        except Exception:  # noqa: BLE001
            r0 = m.get("_duree", _duree(m["_chemin"])) * 0.3
        nom = f"m{n_mus[0]:02d}"
        n_mus[0] += 1
        wav = os.path.join(dossier, nom + ".wav")
        _extrait_wav(m["_chemin"], wav, r0 - 1.0, long)
        if instru:
            rx.append((wav, os.path.join(dossier, nom + "-i.wav"), os.path.join(dossier, nom + ".mp3")))
        else:
            _vers_mp3(wav, os.path.join(dossier, nom + ".mp3"))
        return f"{prefixe}/{nom}.mp3"

    def bed(mid, a, b, mode):
        if mode == "aucune" or b - a < 0.5:
            return
        cur_t = a
        while cur_t < b - 0.5:
            fin = min(b, cur_t + SEGMENT_MAX)
            if b - fin < 8:
                fin = b
            src = extrait(mid, fin - cur_t, mode == "instru")
            if src:
                musiques.append({"src": src, "d": round(cur_t, 3), "f": round(fin, 3), "depuis": 0, "vol": FOND[mode]})
            autres = [x for x in pool_musique if x != mid]
            mid = autres[n_mus[0] % len(autres)] if autres else mid
            cur_t = fin

    trous = sorted(plein_ecran + suspense)
    bornes_chap = [0.0] + [x["f"] for x in titres] + [duree]
    for n in range(len(bornes_chap) - 1):
        a, b = bornes_chap[n], (titres[n]["d"] if n < len(titres) else duree)
        chap = titres[n - 1]["_b"] if n > 0 else {}
        mid = chap.get("musique") if chap.get("musique") in prets else (stars_ok[0] if n == 0 else pool_musique[n % len(pool_musique)])
        mode = chap.get("musique_mode") or "instru"
        if thriller and n == 0:
            musiques.append({"src": SFX["suspense"], "d": 0.0, "f": round(b, 3), "depuis": 0, "vol": 0.55})
            musiques.append({"src": SFX["battement"], "d": 0.0, "f": round(b, 3), "depuis": 0, "vol": 0.35})
            continue
        cur_t = a
        for x, y in trous:
            if y <= cur_t or x >= b:
                continue
            bed(mid, cur_t, min(x, b), mode)
            cur_t = max(cur_t, y)
        bed(mid, cur_t, b, mode)
    for x in titres:   # le titre de l'époque, chanté, sous le titre de chapitre
        mid = x["_b"].get("musique") if x["_b"].get("musique") in prets else None
        src = extrait(mid, x["f"] - x["d"] + 0.5, False) if mid else None
        if src:
            musiques.append({"src": src, "d": x["d"] + x.get("bruit", 0), "f": x["f"], "depuis": 0, "vol": 0.16 if thriller else 0.4})   # s'efface avant que la voix reparte
    for a, b in suspense:
        musiques.append({"src": SFX["suspense"], "d": round(a + 0.4, 3), "f": round(b, 3), "depuis": 0, "vol": 0.14})
    for j2, pr in enumerate(projets):
        mid = _morceau(p, prets, medias, pr.get("morceau") or pr["titre"])
        if mid and "_duree" not in prets[mid]:
            prets[mid]["_duree"] = _duree(prets[mid]["_chemin"])
        src = extrait(mid, DUREE_PROJET + 1, False) if mid else None
        if src:
            musiques.append({"src": src, "d": pr["d"], "f": pr["f"], "depuis": 0, "plein": True})
        else:
            log_write("studio", "warning", f"raconte v4 : « {pr.get('morceau')} » introuvable, projet sans musique")
        cover = _photo(pr.get("cover"), dossier, f"cover{j2}.jpg") if pr.get("cover") else None
        pr["cover"] = f"{prefixe}/cover{j2}.jpg" if cover else "raconte/logo.png"
    instrumentales([(a, b) for a, b, _ in rx])
    for wav, instru, mp3 in rx:
        _vers_mp3(instru if os.path.isfile(instru) else wav, mp3)
        if not os.path.isfile(instru):   # sans RX : le chant reste, mais très bas
            for m in musiques:
                if m["src"].endswith(os.path.basename(mp3)):
                    m["vol"] = FOND["chant"]

    # 7) mascotte : ouverture et fin (les autres apparitions portent les bulles)
    fin_t1 = titres[0]["f"] if titres else accroche_fin + PAUSE_CHAPITRE
    mascottes.insert(0, {"src": POSES["presente"], "d": round(fin_t1 + 0.6, 3), "f": round(fin_t1 + 3.6, 3), "cote": "droite", "h": 820})
    mascottes.append({"src": POSES["appel"], "d": round(fin_d + 0.3, 3), "f": duree, "cote": "gauche", "h": 820})
    sfx.append({"src": SFX["fin"], "d": round(max(0, fin_d - 0.6), 3), "vol": 0.24})
    return {"voix": f"{prefixe}/voix.mp3", "musique": musiques[0]["src"] if musiques else f"{prefixe}/voix.mp3", "duree": duree, "mots": mots,
            "titre": recit["titre"], "plans": les_plans, "cartes": cartes, "mascottes": mascottes, "musiques": musiques, "fond": FOND["instru"],
            "projets": [{k2: x[k2] for k2 in ("d", "f", "cover", "titre", "etiquette", "invites", "chiffre", "morceau") if x.get(k2) is not None}
                        for x in projets],
            "chapitres": [], "titresChapitre": [{k2: x[k2] for k2 in ("d", "f", "numero", "titre", "annees", "style", "bruit") if k2 in x} for x in titres],
            "secrets": [{k2: x[k2] for k2 in ("d", "k", "total")} for x in secrets], "bulles": bulles, "verites": verites,
            "extraits": [{"d": x["d"], "f": x["f"]} for x in extraits + chantes],   # sous-titres cachés pendant qu'il parle lui-même
            "sfx": sfx, "mythes": [], "contrats": contrats, "flashs": flashs, "sansBarre": True,
            "fin": {"d": round(fin_d, 3), "titre": recit["fin"]["titre"], "texte": recit["fin"]["texte"]}, "sources": recit.get("sources") or ""}
