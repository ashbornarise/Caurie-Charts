"""Cauri Studio, « Vidéo paroles » (10/11/2026) : des photos + un son -> une vidéo où les paroles s'allument au rythme
de la voix (video_paroles.rendu). Fabriquée sur le PC (relais) : YouTube refuse les serveurs et l'isolation de la voix
utilise iZotope RX.

Deux temps, comme les vidéos de clips :
1. prepare() : son (lien ou fichier), passage (choisi ou refrain), paroles minutées, image d'essai -> « a_valider »
   Paroles, dans l'ordre : texte collé par le fondateur ; captures d'écran (Spotify…) lues par Gemini ; LRCLIB (gratuit,
   déjà minutées) ; sinon transcription Groq. Un texte connu est calé sur la voix isolée (Groq guidé + alignement dans l'ordre).
2. fabrique() : lignes relues -> rendu 4:5, mastering, copie muette (son officiel ajouté dans l'appli), copie TikTok -> « pret ».
"""
import base64
import difflib
import io
import json
import os
import re
import subprocess
import tempfile
import unicodedata

import requests

from core import db, env, storage
from core.services.platforms import log_write

PYTHON_STUDIO = "python"        # Python du Studio-AV (pedalboard, plugins VST3)
AV = r"C:\Users\agbal\Studio-AV\av.py"
RX = r"C:\Program Files\Common Files\VST3\iZotope\RX 12 Music Rebalance.vst3"
DOSSIER = "studio-paroles"      # fichiers envoyés depuis le téléphone (Blob media/studio-paroles/)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _ffmpeg() -> str:
    from core.services.social.refrain import ffmpeg
    return ffmpeg()


def importe(job_id: int, genre: str, data: bytes, extension: str) -> str:
    """Un fichier envoyé depuis le téléphone (photo, capture des paroles ou son) ; rend son nom dans le Blob."""
    j = db.one("SELECT params FROM studio_jobs WHERE id = ?", [job_id])
    p = json.loads(j["params"] or "{}") if j else {}
    liste = p.setdefault({"photo": "photos", "capture": "captures", "son": "sons"}[genre], [])
    nom = f"job-{job_id}-{genre}-{len(liste) + 1}.{extension}"
    types = {"jpg": "image/jpeg", "png": "image/png", "mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav", "mp4": "video/mp4"}
    storage.store_media(DOSSIER, nom, data, types.get(extension, "application/octet-stream"))
    liste.append(nom)
    db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False)}, "id = :id", {"id": job_id})
    return nom


def _url(nom: str) -> str:
    return f"{storage.blob_public_url()}/media/{DOSSIER}/{nom}"


# ---------------------------------------------------------------- paroles

def _lrclib(artistes: str, titre: str) -> list | None:
    """Paroles minutées de LRCLIB : [{"debut", "texte"}] ou None."""
    try:
        r = requests.get("https://lrclib.net/api/search", params={"artist_name": artistes.split(",")[0].split(" ft")[0],
                                                                    "track_name": titre},
                         timeout=20, headers={"User-Agent": "CauriCharts/1.0"}).json()
    except (requests.RequestException, ValueError):
        return None
    for x in r or []:
        if x.get("syncedLyrics") and _norm(x.get("trackName")) == _norm(titre):
            lignes = []
            for m in re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)", x["syncedLyrics"]):
                if m.group(3).strip():
                    lignes.append({"debut": int(m.group(1)) * 60 + float(m.group(2)), "texte": m.group(3).strip()})
            if lignes:
                return lignes
    return None


def _spotify(artistes: str, titre: str) -> list | None:
    """Paroles de Spotify : [{"debut" (None si non minutées), "texte"}] ou None (pas de cookie, pas de paroles, API cassée)."""
    from core.services.social import spotify_paroles as SP
    try:
        t = SP.cherche(titre, artistes.split(",")[0].split(" ft")[0].strip())
        if not t:
            return None
        d = SP.paroles(t["id"])
    except Exception as exc:  # noqa: BLE001 — API non publique : on retombe sur la transcription
        log_write("studio", "warning", f"paroles Spotify indisponibles pour « {titre} » : {str(exc)[:200]}")
        return None
    minute = d["sync"] == "LINE_SYNCED"
    return [{"debut": deb if minute else None, "texte": txt} for deb, txt in d["lignes"]] or None


def _lit_capture(nom: str, cle: str) -> list[str]:
    """Lignes de paroles visibles sur une capture, lues par Gemini."""
    from core.services.social.comptes import MODELES, URL
    consigne = ("Capture d'écran des paroles d'une chanson. Recopie EXACTEMENT les lignes de paroles entièrement visibles, "
                "une par ligne, de haut en bas, sans le titre, l'artiste, l'heure ni les boutons. Une ligne coupée en haut "
                "ou en bas de l'écran est ignorée. Réponds uniquement par les lignes.")
    image = base64.b64encode(requests.get(_url(nom), timeout=30).content).decode()
    for modele in MODELES:
        try:
            r = requests.post(URL.format(modele), params={"key": cle}, timeout=120, json={"contents": [{"parts": [
                {"text": consigne}, {"inline_data": {"mime_type": "image/jpeg", "data": image}}]}]}).json()
            texte = r["candidates"][0]["content"]["parts"][0]["text"]
            lignes = []
            for l in (x.strip() for x in texte.splitlines()):
                if not l:
                    continue
                # ligne coupée par la largeur de l'écran : parenthèse restée ouverte, ou suite en minuscule
                if lignes and (lignes[-1].count("(") > lignes[-1].count(")") or l[:1].islower() or l[:1] in "()'’,"):
                    lignes[-1] += " " + l
                else:
                    lignes.append(l)
            # dernière ligne coupée par le bas de l'écran (parenthèse ouverte) : elle sera lue sur la capture suivante
            if lignes and lignes[-1].count("(") > lignes[-1].count(")"):
                lignes.pop()
            return lignes
        except (requests.RequestException, KeyError, IndexError, ValueError):
            continue
    return []


def _captures(noms: list) -> list[str]:
    """Texte de captures d'écran de paroles (Spotify…), dans l'ordre. Les captures se chevauchent : chaque nouvelle
    capture est recollée au plus long recouvrement avec la fin du texte déjà lu (les vraies répétitions restent)."""
    cle = env.get("GEMINI_API_KEY", "")
    if not cle:
        return []
    out = []
    for n in noms[:15]:
        lignes = _lit_capture(n, cle)
        if not lignes:
            continue
        a, b = [_norm(x) for x in out], [_norm(x) for x in lignes]
        # le haut d'une capture montre souvent un bout de ligne coupée : on peut en ignorer jusqu'à 2
        meilleur = (0, 0)   # (lignes recouvertes, lignes ignorées en haut)
        for saut in range(0, min(3, len(b))):
            for k in range(min(len(a), len(b) - saut), 0, -1):
                if a[-k:] == b[saut:saut + k]:
                    if k > meilleur[0]:
                        meilleur = (k, saut)
                    break
        k, saut = meilleur
        out += lignes[saut + k:] if k else lignes
    return out


def _isole_voix(stereo: str, sortie: str) -> bool:
    """Voix seule par iZotope RX 12 Music Rebalance (Python du Studio) ; False si indisponible."""
    code = ("from pedalboard import load_plugin\nfrom pedalboard.io import AudioFile\n"
            f"pl=load_plugin(r'{RX}')\npl.vocal_solo=True\n"
            f"f=AudioFile(r'{stereo}'); x=f.read(f.frames); sr=f.samplerate; f.close()\ny=pl.process(x,sr)\n"
            f"o=AudioFile(r'{sortie}','w',sr,y.shape[0]); o.write(y); o.close()\n")
    try:
        subprocess.run([PYTHON_STUDIO, "-c", code], check=True, capture_output=True, timeout=1800)
        return os.path.isfile(sortie)
    except (subprocess.SubprocessError, OSError) as exc:
        log_write("studio", "warning", f"paroles : isolation de la voix impossible ({str(exc)[:150]})")
        return False


def _groq(wav16: str, t0: float, t1: float, prompt: str = "", tmp: str = "") -> list:
    """Mots reconnus par Groq whisper-large-v3 entre t0 et t1 (tranches de 12 s), en secondes du morceau."""
    cle = env.get("GROQ_API_KEY", "")
    mots = []
    for st in range(int(t0), int(t1), 10):
        t = os.path.join(tmp, f"g{st}.wav")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", str(st), "-t", "12", "-i", wav16, t], check=True)
        data = {"model": "whisper-large-v3", "response_format": "verbose_json", "timestamp_granularities[]": ["word"],
                "temperature": "0"}
        if prompt:
            data["prompt"] = prompt[:800]
        try:
            d = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": "Bearer " + cle},
                              files={"file": ("t.wav", open(t, "rb"), "audio/wav")}, data=data, timeout=120).json()
        except (requests.RequestException, ValueError):
            continue
        for w in d.get("words", []):
            s = w["start"] + st
            if (st > t0 and s < st + 1) or s >= st + 11:
                continue
            if mots and s < mots[-1]["f"] - .05:
                continue
            mots.append({"m": w["word"].strip(), "d": round(s, 2), "f": round(w["end"] + st, 2)})
    return mots


def _aligne(textes: list[str], reconnus: list, t0: float, t1: float, debuts: list | None = None) -> list:
    """Cale des lignes connues sur les mots reconnus, en avançant toujours dans le temps ; les mots non reconnus sont
    répartis entre leurs voisins calés. debuts : début connu de chaque ligne (LRCLIB), ou None."""
    attendus = [(i, m) for i, l in enumerate(textes) for m in l.split()]
    b = [_norm(w["m"]) for w in reconnus]
    temps, p = [None] * len(attendus), 0
    for k, (_i, m) in enumerate(attendus):
        x = _norm(m)
        for j in range(p, min(len(b), p + 25)):
            if b[j] and x and (b[j] == x or (len(x) > 3 and difflib.SequenceMatcher(None, b[j], x).ratio() >= .75)):
                temps[k] = [reconnus[j]["d"], reconnus[j]["f"]]
                p = j + 1
                break
    if debuts:   # repères connus (LRCLIB) : 1er mot de chaque ligne
        for i, d in enumerate(debuts):
            k = next(n for n, (li, _m) in enumerate(attendus) if li == i)
            if d is not None and (temps[k] is None or abs(temps[k][0] - d) > 1.5):
                temps[k] = [d, d + .3]
    # jamais de retour en arrière
    dernier = t0
    for k, x in enumerate(temps):
        if x:
            if x[0] < dernier:
                temps[k] = None
            else:
                dernier = x[0]
    cales = [k for k, x in enumerate(temps) if x]
    bornes = [(-1, [t0, t0])] + [(k, temps[k]) for k in cales] + [(len(attendus), [t1, t1])]
    for (ka, xa), (kb, xb) in zip(bornes, bornes[1:]):
        n = kb - ka
        for k in range(ka + 1, kb):
            d = xa[1] + (xb[0] - xa[1]) * (k - ka - 1) / max(1, n - 1) if n > 1 else xa[1]
            temps[k] = [d, d + max(.15, (xb[0] - xa[1]) / max(1, n) * .9)]
    lignes = []
    for i, l in enumerate(textes):
        ws = [{"m": m, "d": round(temps[k][0], 2), "f": round(max(temps[k][1], temps[k][0] + .12), 2)}
              for k, (li, m) in enumerate(attendus) if li == i]
        if ws:
            lignes.append({"debut": ws[0]["d"], "fin": ws[-1]["f"], "mots": ws})
    return lignes


def _relit(lignes: list, textes: list[str]) -> list:
    """Lignes corrigées par le fondateur : mêmes moments, mots répartis sur la durée de la ligne s'ils ont changé."""
    out = []
    for l, t in zip(lignes, textes):
        mots = t.split()
        if not mots:
            continue
        if [w["m"] for w in l["mots"]] == mots:
            out.append(l)
            continue
        d0, d1 = l["debut"], max(l["fin"], l["debut"] + .4 * len(mots))
        pas = (d1 - d0) / len(mots)
        ws = [{"m": m, "d": round(d0 + k * pas, 2), "f": round(d0 + (k + .9) * pas, 2)} for k, m in enumerate(mots)]
        out.append({"debut": ws[0]["d"], "fin": ws[-1]["f"], "mots": ws})
    return out


# ---------------------------------------------------------------- étapes

def _son(job: dict, p: dict, tmp: str) -> str:
    """Le son en WAV stéréo 44,1 kHz (lien YouTube…, ou fichier envoyé depuis le téléphone)."""
    from core.services.social import studio_montage as S
    if p.get("sons"):
        src = os.path.join(tmp, "son-source")
        open(src, "wb").write(requests.get(_url(p["sons"][0]), timeout=120).content)
    else:
        src, _infos = S.telecharge(job["lien"], tmp)
    stereo = os.path.join(tmp, "stereo.wav")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", src, "-vn", "-ac", "2", "-ar", "44100", stereo], check=True)
    return stereo


def _photo(p: dict):
    if p.get("photos"):
        return _url(p["photos"][0])
    if p.get("photo_id"):
        f = db.value("SELECT fichier FROM artist_photos WHERE id = ?", [int(p["photo_id"])])
        if f:
            return f"{storage.blob_public_url()}/media/artists/plans/{f}"
    return None


def _pochette(p: dict) -> str | None:
    if p.get("pochette"):
        return p["pochette"]
    t = db.one("""SELECT t.cover_url FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE lower(t.title) = lower(?)
                  AND t.cover_url IS NOT NULL ORDER BY t.release_date DESC NULLS LAST LIMIT 1""", [p.get("titre") or ""])
    return (t or {}).get("cover_url")


def prepare(job_id: int, job: dict, p: dict, maj) -> dict:
    from core.services.social import refrain as RF
    from core.services.social import video_paroles as V
    with tempfile.TemporaryDirectory(prefix=f"cauri-paroles-{job_id}-") as tmp:
        maj(job_id, statut="telechargement", erreur=None)
        stereo = _son(job, p, tmp)
        duree = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", stereo],
                                     capture_output=True, text=True).stdout.strip() or 0)
        maj(job_id, statut="analyse")
        if p.get("debut") is not None and p.get("fin"):
            t0, t1 = float(p["debut"]), float(p["fin"])
        else:
            t0, t1 = RF.refrain(stereo, duree=float(p.get("duree") or 34))
        t0, t1 = max(0.0, t0), min(duree or t1, t1, t0 + 60)
        voix = os.path.join(tmp, "voix.wav")
        wav16 = os.path.join(tmp, "voix16.wav")
        source_voix = voix if _isole_voix(stereo, voix) else stereo
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", source_voix, "-ac", "1", "-ar", "16000", wav16], check=True)
        # paroles connues : collées, captures, LRCLIB ; sinon transcription
        textes, debuts, origine = [], None, ""
        if (p.get("texte") or "").strip():
            textes, origine = [l.strip() for l in p["texte"].splitlines() if l.strip()], "texte collé"
        elif p.get("captures"):
            textes, origine = _captures(p["captures"]), "captures"
        if not textes:
            lrc = _lrclib(p.get("artistes") or "", p.get("titre") or "")
            if lrc:
                dans = [x for x in lrc if t0 - 1 <= x["debut"] < t1]
                textes, debuts, origine = [x["texte"] for x in dans], [x["debut"] for x in dans], "LRCLIB"
        if not textes:   # paroles affichées dans Spotify (11/11/2026) : texte exact, début de chaque ligne
            sp = _spotify(p.get("artistes") or "", p.get("titre") or "")
            if sp:
                dans = [x for x in sp if t0 - 1 <= x["debut"] < t1] if sp[0]["debut"] is not None else sp
                textes = [x["texte"] for x in dans]
                debuts = [x["debut"] for x in dans] if sp[0]["debut"] is not None else None
                origine = "Spotify"
        marge = 3.0
        reconnus = _groq(wav16, max(0, t0 - marge), t1 + marge, " ".join(textes), tmp)
        if not textes:   # dernier recours : la transcription elle-même, à relire
            origine, lignes = "transcription (à relire)", []
            cour = []
            for w in reconnus:
                if cour and (w["d"] - cour[-1]["f"] > .6 or len(cour) >= 7):
                    lignes.append(cour); cour = []
                cour.append(w)
            if cour:
                lignes.append(cour)
            lignes = [{"debut": l[0]["d"], "fin": l[-1]["f"], "mots": l} for l in lignes if t0 - .5 <= l[0]["d"] < t1]
        else:
            # un texte complet (collé, captures) : on cale tout, puis on garde les lignes du passage
            lignes = _aligne(textes, reconnus, max(0, t0 - marge), t1 + marge, debuts)
            lignes = [l for l in lignes if l["fin"] > t0 and l["debut"] < t1]
        if not lignes:
            raise RuntimeError("aucune parole trouvée sur ce passage : colle le texte ou ajoute des captures")
        # image d'essai (1 s au milieu du passage)
        essai = os.path.join(tmp, "essai.mp4")
        tm = lignes[len(lignes) // 2]["debut"] + .4
        V.rendu(stereo, _pochette(p), lignes, tm, tm + 1, p.get("titre") or "", p.get("artistes") or "", p.get("album") or "",
                p.get("pays"), essai, "feed", photo=_photo(p))
        img = os.path.join(tmp, "essai.jpg")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", ".6", "-i", essai, "-frames:v", "1", img], check=True)
        nom = f"studio-{job_id}-paroles-apercu-{os.urandom(2).hex()}.jpg"
        storage.store_media("social", nom, open(img, "rb").read(), "image/jpeg")
        p.update({"debut": t0, "fin": t1, "lignes": lignes, "paroles": [" ".join(w["m"] for w in l["mots"]) for l in lignes],
                  "origine_paroles": origine})
        maj(job_id, statut="a_valider", vignette=nom, params=p)
        return {"statut": "a_valider", "video": nom}


def fabrique(job_id: int, job: dict, p: dict, maj) -> dict:
    from core.services.social import video_paroles as V
    from core.services.social.encodage import copie_tiktok, nom_tiktok
    with tempfile.TemporaryDirectory(prefix=f"cauri-paroles-{job_id}-") as tmp:
        maj(job_id, statut="montage", erreur=None)
        stereo = _son(job, p, tmp)
        lignes = _relit(p["lignes"], p.get("paroles") or [])
        brut = os.path.join(tmp, "brut.mp4")
        V.rendu(stereo, _pochette(p), lignes, float(p["debut"]), float(p["fin"]), p.get("titre") or "", p.get("artistes") or "",
                p.get("album") or "", p.get("pays"), brut, "feed", photo=_photo(p))
        video = brut
        try:   # vrai limiteur FabFilter Pro-L 2 (Studio-AV), sinon le niveau du rendu (−14 LUFS) reste
            subprocess.run([PYTHON_STUDIO, AV, "master", brut, "--vst"], check=True, capture_output=True, timeout=900)
            if os.path.isfile(brut.replace(".mp4", "-master.mp4")):
                video = brut.replace(".mp4", "-master.mp4")
        except (subprocess.SubprocessError, OSError):
            pass
        nom = f"studio-{job_id}-paroles-{os.urandom(3).hex()}"
        muette = os.path.join(tmp, nom + "-muette.mp4")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", video, "-an", "-c:v", "copy", muette], check=True)
        vignette = os.path.join(tmp, nom + ".jpg")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", "2", "-i", video, "-frames:v", "1", "-q:v", "3", vignette], check=True)
        storage.store_media("social", nom + ".mp4", open(video, "rb").read(), "video/mp4")
        storage.store_media("social", nom + "-muette.mp4", open(muette, "rb").read(), "video/mp4")
        for v in (video, muette):   # TikTok : copie 9:16 de chaque version
            tt = copie_tiktok(v)
            if tt:
                cible = nom_tiktok(nom + ".mp4") if v == video else nom_tiktok(nom + "-muette.mp4")
                storage.store_media("social", cible, open(tt, "rb").read(), "video/mp4")
        storage.store_media("social", nom + ".jpg", open(vignette, "rb").read(), "image/jpeg")
        p.update({"video_muette": nom + "-muette.mp4"})
        maj(job_id, statut="pret", video=nom + ".mp4", vignette=nom + ".jpg", params=p)
        return {"statut": "pret", "video": nom + ".mp4"}


def traite(job_id: int, job: dict, p: dict, maj) -> dict:
    return fabrique(job_id, job, p, maj) if p.get("valide") else prepare(job_id, job, p, maj)
