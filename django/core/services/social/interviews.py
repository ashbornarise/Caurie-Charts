"""Moments d'interview : le passage le plus fort (25 à 50 s) d'une interview, d'un podcast ou d'un live YouTube où un
artiste africain parle de lui, en vidéo 9:16 sous-titrée, avec le SON de la parole.

Pourquoi : la parole est rarement bloquée par les détecteurs de droits, contrairement aux clips musicaux.
Étapes : recherche YouTube (100 unités, rien sous 2 000 unités restantes) → sous-titres automatiques (yt-dlp) →
l'IA choisit le passage et écrit l'accroche → vérifications (bornes présentes dans la transcription, aucun chiffre
inventé) → téléchargement du seul passage → montage (vidéo au centre, fond flouté, accroche, sous-titres, crédit).
Garde-fous : le nom de l'artiste en mot entier dans le titre, pas de clip, de live musical ni de paroles ; l'IA confirme
que c'est l'artiste qui parle ; la chaîne et le lien sont toujours cités. Les sous-titres incrustés sont la
transcription automatique de YouTube, telle quelle : aucune phrase n'est prêtée à l'artiste."""
import html
import json
import os
from datetime import date, timedelta
import re
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

from core import db
from core.services.platforms import log_write
from core.services.social import refrain as R
from core.services.social.medias import _sans_accents

QUOTA_MIN = 2000
DUREE_MIN, DUREE_MAX = 25.0, 50.0
# Stars africaines suivies même hors de notre base (en plus de nos artistes les plus suivis)
STARS = ["Burna Boy", "Wizkid", "Davido", "Tems", "Rema", "Ayra Starr", "Asake", "Tiwa Savage", "Black Sherif", "Sarkodie",
         "Stonebwoy", "Yemi Alade", "Fally Ipupa", "Angélique Kidjo", "Didi B", "Toofan", "King Promise", "Omah Lay"]
# Clips, lives musicaux, paroles, réactions de fans : ce n'est pas l'artiste qui parle de lui
EXCLUS = re.compile(r"official\s+(music\s+)?video|music\s+video|clip\s+officiel|\blyrics?\b|\baudio\b|visuali[sz]er|"
                    r"live\s+(performance|at|in|from|on\s+stage|session)|\bperform(s|ance|ing)\b|\bconcert\b|tiny\s+desk|"
                    r"colors\s+show|\bremix\b|\bft\.?\s|\bfeat\.?\s|\bdance\b|\breacts?\b|\breaction\b|#shorts|\bcover\b", re.I)
SYSTEME = ("Tu es le rédacteur vidéo de Cauri Charts, média musical francophone (« la référence de la musique "
           "ouest-africaine »). Tu travailles sur des transcriptions réelles : tu n'inventes jamais une phrase, un fait ni "
           "un chiffre ; l'accroche et le résumé disent fidèlement, en français, ce qui est dit. Réponds UNIQUEMENT en JSON.")


# ---------------------------------------------------------------- recherche

def _mot(nom: str, texte: str) -> bool:
    return bool(re.search(rf"(?<![\w]){re.escape(_sans_accents(nom))}(?![\w])", _sans_accents(texte)))


def titre_valable(titre: str, artiste: str) -> bool:
    """Interview de l'artiste lui-même : son nom en mot entier, pas un clip / live musical / paroles, pas « à propos de »."""
    if not _mot(artiste, titre) or EXCLUS.search(titre):
        return False
    nom = re.escape(_sans_accents(artiste))
    return not re.search(rf"\b(about|on|to|vs|versus|disses?|slams?|blasts?|calls\s+out|responds\s+to)\s+{nom}\b", _sans_accents(titre))


def _secondes(iso: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    j, h, mi, s = (int(x or 0) for x in m.groups())
    return j * 86400 + h * 3600 + mi * 60 + s


def recherche(artiste: str, n: int = 4) -> list[dict]:
    """Interviews / podcasts YouTube de l'artiste, les plus vus d'abord (101 unités de quota)."""
    from core.services.platforms import clients
    yt = clients()["youtube"]
    if not yt.is_available() or yt.remaining_quota() < QUOTA_MIN:
        log_write("social", "info", f"interviews : quota YouTube insuffisant ({yt.remaining_quota() if yt.is_available() else 0})")
        return []
    d = yt._get("search", {"part": "snippet", "type": "video", "maxResults": 20, "q": f"{artiste} interview|podcast"}, 100)
    cands = []
    for it in d.get("items", []):
        sn, vid = it.get("snippet", {}), it.get("id", {}).get("videoId")
        titre = re.sub(r"&#39;|&quot;|&amp;", lambda m: {"&#39;": "'", "&quot;": '"', "&amp;": "&"}[m.group()], sn.get("title", ""))
        if vid and sn.get("liveBroadcastContent", "none") == "none" and titre_valable(titre, artiste):
            cands.append({"id": vid, "titre": titre, "chaine": sn.get("channelTitle", "")})
    if not cands:
        return []
    det = yt._get("videos", {"part": "contentDetails,statistics", "id": ",".join(c["id"] for c in cands)}, 1)
    infos = {i["id"]: i for i in det.get("items", [])}
    out = []
    for c in cands:
        i = infos.get(c["id"]) or {}
        duree = _secondes((i.get("contentDetails") or {}).get("duration", ""))
        if 180 <= duree <= 4 * 3600:   # ni short ni extrait trop court
            out.append({**c, "duree": duree, "vues": int((i.get("statistics") or {}).get("viewCount") or 0)})
    return sorted(out, key=lambda c: -c["vues"])[:n]


# ---------------------------------------------------------------- transcription

def _t(s: str) -> float:
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


_TS = r"(\d{2}:\d{2}:\d{2}\.\d{3})"


def mots_vtt(vtt: str) -> list[tuple[float, str]]:
    """Mots horodatés d'un fichier VTT. Sous-titres automatiques de YouTube : chaque mot a son horodatage (<00:00:01.234>) ;
    sinon, les mots d'une réplique sont répartis sur sa durée. Les lignes répétées d'une réplique à l'autre sont ignorées."""
    blocs = re.findall(_TS + r" --> " + _TS + r"[^\n]*\n(.*?)(?:\n\n|\Z)", vtt.replace("\r", ""), re.S)
    mots_tag = "<c>" in vtt or re.search(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", vtt)
    out, derniere = [], None
    for debut, fin, texte in blocs:
        d, f = _t(debut), _t(fin)
        for ligne in texte.split("\n"):
            if mots_tag:
                if "<" not in ligne:
                    continue   # ligne déjà vue dans la réplique précédente
                t = d
                for morceau in re.split(r"(<\d{2}:\d{2}:\d{2}\.\d{3}>)", ligne):
                    m = re.fullmatch(r"<" + _TS + ">", morceau)
                    if m:
                        t = _t(m.group(1)); continue
                    for w in re.sub(r"<[^>]+>", "", morceau).split():
                        out.append((round(t, 2), w))
            else:
                ligne = re.sub(r"<[^>]+>", "", ligne).strip()
                if not ligne or ligne == derniere:
                    continue
                derniere = ligne
                ws = ligne.split()
                for k, w in enumerate(ws):
                    out.append((round(d + (f - d) * k / len(ws), 2), w))
    # Entités HTML (&gt;&gt; = changement d'interlocuteur), [Music], [Applause], tirets de dialogue : retirés
    out = [(t, html.unescape(w)) for t, w in out]
    mots = [(t, w) for t, w in out if not re.fullmatch(r"\[[^\]]*\]|>+|-+|&nbsp;", w)]
    return sorted(mots, key=lambda x: x[0])


def lignes(mots: list[tuple[float, str]], max_mots: int = 14, pause: float = 1.2) -> list[dict]:
    """Phrases horodatées pour l'IA : {debut, fin, texte} ; la fin d'une ligne est le début de la suivante."""
    out, cur = [], []
    for i, (t, w) in enumerate(mots):
        if cur and (len(cur) >= max_mots or t - cur[-1][0] > pause):
            out.append(cur); cur = []
        cur.append((t, w))
    if cur:
        out.append(cur)
    res = []
    for i, l in enumerate(out):
        fin = out[i + 1][0][0] if i + 1 < len(out) else l[-1][0] + 0.6
        res.append({"debut": l[0][0], "fin": round(min(fin, l[-1][0] + 1.5), 2), "texte": " ".join(w for _, w in l)})
    return res


def sous_titres(video_id: str, dossier: str) -> tuple[list, str] | None:
    """Sous-titres automatiques (anglais ou français) : (mots, langue). Ne télécharge pas la vidéo."""
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--skip-download", "--write-auto-subs", "--write-subs",
           "--sub-langs", "en,fr", "--sub-format", "vtt", "--ignore-errors", "--no-warnings", "-q",
           "--print", "%(language)s", "--no-simulate", "-o", os.path.join(dossier, "%(id)s.%(ext)s"),
           f"https://www.youtube.com/watch?v={video_id}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "warning", f"sous-titres {video_id} : {str(exc)[:200]}")
        return None
    langue = (r.stdout.strip().splitlines() or ["en"])[-1][:2].lower()
    # La langue d'origine d'abord : la piste « fr » d'une vidéo anglaise n'est qu'une traduction automatique
    for lg in dict.fromkeys([langue, "en", "fr"]):
        p = os.path.join(dossier, f"{video_id}.{lg}.vtt")
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                mots = mots_vtt(f.read())
            if len(mots) > 80:
                return mots, lg
    return None


# ---------------------------------------------------------------- choix du passage

def _nombres(texte: str, francais: bool) -> set:
    if francais:   # « 10 000 », « 10.000 », « 1,5 »
        texte = re.sub(r"(?<=\d)[\s  .](?=\d{3}\b)", "", texte).replace(",", ".")
    else:          # « 10,000 », « 1.5 »
        texte = re.sub(r"(?<=\d),(?=\d{3}\b)", "", texte)
    return {n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", texte)}


def verifie(choix: dict, phrases: list[dict]) -> dict | None:
    """Passage proposé par l'IA, contrôlé : début et fin sur des horodatages de la transcription (±0,8 s), 25 à 50 s,
    accroche de 5 à 10 mots sans aucun chiffre absent du passage. Rend {debut, fin, accroche, resume, texte} ou None."""
    try:
        debut, fin = float(choix["debut"]), float(choix["fin"])
    except (KeyError, TypeError, ValueError):
        return None
    accroche = re.sub(r"\s+", " ", str(choix.get("accroche") or "")).strip().strip("«»\"").strip()
    if not phrases or not accroche or choix.get("parle") is False:
        return None
    starts = [p["debut"] for p in phrases]
    ends = [p["fin"] for p in phrases]
    i = min(range(len(starts)), key=lambda k: abs(starts[k] - debut))
    # La fin vaut la fin d'une ligne, ou le début de la ligne suivante (consigne donnée à l'IA)
    ecart = lambda k: min(abs(ends[k] - fin), abs(starts[k + 1] - fin) if k + 1 < len(starts) else 1e9)  # noqa: E731
    j = min(range(len(ends)), key=ecart)
    if abs(starts[i] - debut) > 0.8 or ecart(j) > 0.8 or j < i:
        return None
    debut, fin = starts[i], ends[j]
    if not DUREE_MIN <= fin - debut <= DUREE_MAX:
        return None
    texte = " ".join(p["texte"] for p in phrases[i:j + 1])
    if not 5 <= len(accroche.split()) <= 10:
        return None
    if not _nombres(accroche, True) <= _nombres(texte, False):
        return None   # un chiffre de l'accroche n'est pas dans ce qui est dit
    return {"debut": debut, "fin": fin, "accroche": accroche, "resume": str(choix.get("resume") or "").strip(),
            "question": str(choix.get("question") or "").strip(), "texte": texte}


def etend(choix: dict, phrases: list[dict], cible: float = 30.0) -> dict:
    """Passage trop court (l'IA garde souvent une seule réplique) : on garde son début et on prolonge jusqu'à la fin de
    ligne qui donne au moins « cible » secondes. Le passage choisi reste dedans, l'accroche reste donc fidèle."""
    try:
        debut, fin = float(choix["debut"]), float(choix["fin"])
    except (KeyError, TypeError, ValueError):
        return choix
    if fin - debut >= DUREE_MIN or not phrases:
        return choix
    for p in phrases:
        if p["fin"] >= fin - 0.8 and p["fin"] - debut >= cible:
            return {**choix, "fin": p["fin"]} if p["fin"] - debut <= DUREE_MAX else choix
    return choix


def choisit(artiste: str, video: dict, phrases: list[dict]) -> dict | None:
    """L'IA choisit le passage le plus fort ; le choix est vérifié (verifie)."""
    from core.services import ai
    client = ai.make()
    if not client:
        return None
    transcription, total = [], 0
    for p in phrases:
        l = f"[{p['debut']:.1f}] {p['texte']}"
        total += len(l) + 1
        if total > 45000:   # longues émissions : la première heure environ suffit
            break
        transcription.append(l)
    transcription.append(f"[{phrases[min(len(transcription), len(phrases) - 1)]['fin']:.1f}] (fin)")
    consigne = (f"Transcription automatique horodatée (en secondes) de la vidéo YouTube « {video['titre']} » "
                f"(chaîne {video['chaine']}), où {artiste} parle.\n"
                f"Choisis LE passage de 28 à 45 secondes le plus fort pour un Reel : anecdote, révélation, chiffre ou "
                f"punchline de {artiste} sur lui-même ou sa carrière, compréhensible sans le reste de la vidéo, où c'est "
                f"{artiste} qui parle (pas l'animateur). « debut » est l'horodatage d'une ligne, « fin » l'horodatage de la "
                f"ligne qui suit la dernière ligne gardée. IMPORTANT : fin - debut doit être compris entre 28 et 45 secondes "
                f"(par exemple debut 312.4 et fin 349.9, soit 37,5 s) : garde plusieurs lignes à la suite.\n"
                'Rends UNIQUEMENT ce JSON : {"debut": secondes, "fin": secondes, '
                '"accroche": "6 à 9 mots en français, fidèles à ce qui est dit dans le passage, sans aucun chiffre qui n\'y '
                'est pas", "resume": "1 ou 2 phrases en français : ce que dit l\'artiste dans ce passage, rien de plus", '
                f'"question": "une question courte au public, en français", "parle": true si c\'est bien {artiste} qui parle}}\n'
                'Si aucun passage ne convient (artiste absent, sujet sensible : justice, santé, décès), rends {"aucun": true}.\n\n'
                + "\n".join(transcription))
    for essai in range(2):   # un refus des vérifications : on le dit à l'IA et elle propose une seconde fois
        t = ""
        try:
            r = client.ask(SYSTEME, consigne, max_tokens=4000)
            t = r["text"]
            o = json.loads(t[t.find("{"): t.rfind("}") + 1])
        except Exception as exc:  # noqa: BLE001
            log_write("social", "warning", f"interview {video['id']} : choix de l'IA illisible ({str(exc)[:200]})",
                      {"reponse": (t or "")[:300]})
            return None
        if o.get("aucun"):
            return None
        # 1er essai : le passage tel quel ; 2e essai : prolongé s'il est encore trop court
        ok = verifie(etend(o, phrases) if essai else o, phrases)
        if ok:
            return ok
        log_write("social", "info", f"interview {video['id']} : passage refusé par les vérifications", {"choix": o})
        consigne += (f"\n\nTa réponse précédente {json.dumps(o, ensure_ascii=False)} a été REFUSÉE. Rappel : debut et fin "
                     "sont des horodatages de la liste, fin - debut entre 28 et 45 secondes, accroche de 6 à 9 mots sans "
                     "aucun chiffre absent du passage. Propose un passage valable.")
    return None


# ---------------------------------------------------------------- montage

def telecharge_passage(video_id: str, debut: float, fin: float, dossier: str) -> str | None:
    """Seulement le passage (coupe exacte, ≤ 1080p)."""
    out = os.path.join(dossier, f"{video_id}-passage.mp4")
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-playlist", "-q", "--no-warnings",
           "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]", "--merge-output-format", "mp4",
           "--download-sections", f"*{debut:.2f}-{fin:.2f}", "--force-keyframes-at-cuts",
           "-o", out, f"https://www.youtube.com/watch?v={video_id}"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "error", f"passage {video_id} non téléchargé : {str(exc)[:300]}")
        return None
    return out if os.path.isfile(out) else None


def morceaux(mots: list[tuple[float, str]], debut: float, fin: float, max_mots: int = 6) -> list[dict]:
    """Sous-titres à l'écran : groupes de 6 mots au plus, temps relatifs au début du passage."""
    ws = [(t - debut, w) for t, w in mots if debut - 0.05 <= t < fin]
    groupes, cur = [], []
    for t, w in ws:
        if cur and (len(cur) >= max_mots or t - cur[-1][0] > 0.9):
            groupes.append(cur); cur = []
        cur.append((t, w))
    if cur:
        groupes.append(cur)
    out = []
    for i, g in enumerate(groupes):
        a = max(0.0, g[0][0])
        b = groupes[i + 1][0][0] if i + 1 < len(groupes) else min(fin - debut, g[-1][0] + 1.2)
        out.append({"a": round(a, 2), "b": round(min(b, g[-1][0] + 1.6), 2), "texte": " ".join(w for _, w in g)})
    return out


def _calque(accroche: str, artiste: str, credit: str, label: str = "MOMENT D'INTERVIEW") -> Image.Image:
    """Habillage 2026 (19/10/2026) : logo rond, étiquette pastille, accroche en minuscules avec le nom surligné."""
    import re
    from core.services.social import couverture2026 as C
    img = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    C._logo(img, 60, 70, 84)
    fe = C.police("Montserrat.ttf", 28, "ExtraBold")
    eti = f"{label} · {artiste.upper()}"[:48]
    tw = d.textlength(eti, font=fe)
    d.rounded_rectangle((60, 196, 60 + tw + 36, 246), radius=25, fill=C.CIEL + (255,))
    d.text((78, 205), eti, font=fe, fill=C.NUIT + (255,))
    cibles = {re.sub(r"\W", "", m.lower()) for m in artiste.split()}
    texte = C.propre(accroche)
    for taille in (70, 64, 58, 52):
        police = C.police("Montserrat.ttf", taille, "ExtraBold")
        lignes, cour = [], ""
        for mot in texte.split():
            essai = (cour + " " + mot).strip()
            if d.textlength(essai, font=police) > R.W - 120 and cour:
                lignes.append(cour); cour = mot
            else:
                cour = essai
        lignes.append(cour)
        if len(lignes) * (taille + 16) <= 290:
            break
    y = 270
    for ligne in lignes:
        x = 60
        for mot in ligne.split():
            lm = d.textlength(mot, font=police)
            if re.sub(r"\W", "", mot.lower()) in cibles:
                d.rectangle((x - 8, y + 6, x + lm + 8, y + taille + 10), fill=C.VIOLET + (255,))
            d.text((x, y), mot, font=police, fill=(255, 255, 255, 255))
            x += lm + d.textlength(" ", font=police)
        y += taille + 16
    d.text((60, 1460), credit, font=C.police("Montserrat.ttf", 26, "Medium"), fill=(255, 255, 255, 200))
    return img


def _sous_titre(texte: str) -> Image.Image:
    img = Image.new("RGBA", (R.W, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    from core.services.social import couverture2026 as C
    police = C.police("Montserrat.ttf", 58, "ExtraBold")
    ls = R._lignes(d, C.propre(texte), police, R.W - 140)[:2]
    y = 110 - len(ls) * 39
    for l in ls:
        w = d.textlength(l, font=police)
        d.text(((R.W - w) / 2, y), l, font=police, fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0, 255))
        y += 78
    return img


def monte(src: str, duree: float, accroche: str, artiste: str, credit: str, subs: list[dict], out: str, tmp: str,
          label: str = "MOMENT D'INTERVIEW") -> str | None:
    """9:16 : fond = vidéo agrandie et floutée, vidéo au centre, accroche en haut, sous-titres en bas ; son de la parole."""
    calque = os.path.join(tmp, "calque.png")
    _calque(accroche, artiste, credit, label).save(calque)
    entrees = ["-i", src, "-loop", "1", "-t", f"{duree:.2f}", "-i", calque]
    filtre = [f"[0:v]split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:2,"
              f"eq=brightness=-0.32,scale={R.W}:{R.H}[fond];[b]scale=-2:880,crop='min(iw,{R.W})':880[clip];"
              f"[fond][clip]overlay=(W-w)/2:560[v0];[v0][1:v]overlay=0:0[v1]"]
    for k, s in enumerate(subs):
        p = os.path.join(tmp, f"st{k}.png")
        _sous_titre(s["texte"]).save(p)
        entrees += ["-loop", "1", "-t", f"{duree:.2f}", "-i", p]
        filtre.append(f"[v{k + 1}][{k + 2}:v]overlay=0:1200:enable='between(t,{s['a']:.2f},{s['b']:.2f})'[v{k + 2}]")
    n = len(subs) + 1
    filtre.append(f"[v{n}]fps=30,format=yuv420p,fade=t=in:d=0.3,fade=t=out:st={max(0, duree - 0.5):.2f}:d=0.5[v]")
    filtre.append(f"[0:a]afade=t=in:d=0.2,afade=t=out:st={max(0, duree - 0.8):.2f}:d=0.8,loudnorm=I=-14:TP=-1.5[a]")
    from core.services.social.encodage import AUDIO_HQ, VIDEO_HQ, copie_telegram
    # haute qualité pour Instagram, TikTok et Facebook ; Telegram reçoit sa copie allégée « -tg » (< 20 Mo)
    cmd = [R.ffmpeg(), "-y", "-v", "error", *entrees, "-filter_complex", ";".join(filtre), "-map", "[v]", "-map", "[a]",
           "-t", f"{duree:.2f}", *VIDEO_HQ, *AUDIO_HQ, "-movflags", "+faststart", out]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=1500, check=True)
    except subprocess.CalledProcessError as exc:
        log_write("social", "error", f"montage interview : {(exc.stderr or '')[-300:]}")
        return None
    except (OSError, subprocess.SubprocessError) as exc:
        log_write("social", "error", f"montage interview : {str(exc)[:300]}")
        return None
    if not os.path.isfile(out):
        return None
    copie_telegram(out)
    return out


# ---------------------------------------------------------------- ensemble

def _mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def deja_vus(jours: int = 120) -> tuple[set, set]:
    """Vidéos YouTube déjà utilisées (120 jours) et artistes passés en interview ces 14 derniers jours."""
    vids, noms = set(), set()
    for r in db.all("""SELECT facts, slot_date FROM social_posts WHERE theme LIKE 'format-clip-%' AND slot_date >= CURRENT_DATE - ?""",
                    [jours]):
        try:
            f = json.loads(r["facts"] or "{}")
        except (ValueError, TypeError):
            continue
        if f.get("format") == "interview":
            vids.add(f.get("video_id"))
            if str(r["slot_date"]) >= str(date.today() - timedelta(days=14)):
                noms.add((f.get("artiste") or "").lower())
    return vids, noms


def artistes(jour=None) -> list[str]:
    """Nos artistes suivis les plus suivis sur YouTube, puis les stars africaines ; ordre qui tourne chaque jour."""
    try:
        rows = db.all("""SELECT name FROM artists WHERE status = 'active' AND youtube_subscribers IS NOT NULL
                         ORDER BY youtube_subscribers DESC LIMIT 12""")
    except Exception:  # noqa: BLE001
        rows = []
    noms = list(dict.fromkeys([r["name"] for r in rows] + STARS))
    noms = [n for n in noms if n.lower() not in R.exclus()]
    if jour and noms:
        k = jour.toordinal() % len(noms)
        noms = noms[k:] + noms[:k]
    return noms


def moment(artiste: str, out: str, exclus_ids: set | None = None, essais: int = 3) -> dict | None:
    """Vidéo « moment d'interview » de l'artiste, ou None (aucune interview, pas de sous-titres, aucun passage valable)."""
    try:
        videos = recherche(artiste)
    except Exception as exc:  # noqa: BLE001 — quota, réseau : la journée continue avec les clips
        log_write("social", "warning", f"interviews {artiste} : {str(exc)[:200]}")
        return None
    videos = [v for v in videos if v["id"] not in (exclus_ids or set())][:essais]
    for v in videos:
        with tempfile.TemporaryDirectory(prefix="cauri-itw-") as tmp:
            st = sous_titres(v["id"], tmp)
            if not st:
                continue
            mots, langue = st
            phrases = lignes(mots)
            c = choisit(artiste, v, phrases)
            if not c:
                continue
            src = telecharge_passage(v["id"], c["debut"], c["fin"], tmp)
            if not src:
                continue
            duree = c["fin"] - c["debut"]
            credit = f"Extrait : {v['chaine']} (YouTube)"
            if not monte(src, duree, c["accroche"], artiste, credit, morceaux(mots, c["debut"], c["fin"]), out, tmp):
                continue
        return {"file": out, "artist": artiste, "video_id": v["id"], "titre": v["titre"], "chaine": v["chaine"], "langue": langue,
                "debut": c["debut"], "fin": c["fin"], "accroche": c["accroche"], "resume": c["resume"], "question": c["question"],
                "texte": c["texte"], "source": f"https://www.youtube.com/watch?v={v['id']}&t={int(c['debut'])}s",
                "a": _mmss(c["debut"])}
    return None


def legende(res: dict) -> str:
    question = res.get("question") or "Vous en pensez quoi ? Dites-le en commentaire."
    return (f"🎙️ {res['artist']} : {res['accroche']}\n\n"
            + (f"{res['resume']}\n\n" if res.get("resume") else "")
            + f"👉 {question}\n\n"
            + f"Extrait de l'interview ({res['chaine']}, à {res['a']}) : youtube.com/watch?v={res['video_id']}\n"
            + "Sous-titres : transcription automatique de YouTube.")
