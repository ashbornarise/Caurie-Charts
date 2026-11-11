"""Paroles de Musixmatch (11/11/2026) : le fournisseur des paroles de Spotify, souvent plus complet que ce que Spotify
affiche. Sans compte, Musixmatch renvoie une fausse chanson (« NOKIA ») ; avec les jetons du compte du fondateur
(cookie « musixmatchUserToken », MUSIXMATCH_TOKENS dans le fichier de secrets, jamais dans le code) l'API répond.
API non publique : en cas d'échec, studio_paroles passe à la source suivante."""
import json
import re

import requests

from core import env

BASE = "https://apic.musixmatch.com/ws/1.1/"
APP = "mxm-com-v1.0"
ENTETES = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127 Safari/537.36",
           "Origin": "https://www.musixmatch.com", "Referer": "https://www.musixmatch.com/"}


def _jeton() -> str | None:
    try:
        return json.loads(env.get("MUSIXMATCH_TOKENS", "") or "{}").get(APP)
    except ValueError:
        return None


def _get(methode: str, **params) -> dict:
    params.update({"app_id": APP, "usertoken": _jeton(), "format": "json"})
    return requests.get(BASE + methode, params=params, headers=ENTETES, timeout=20).json()["message"]


def paroles(titre: str, artiste: str) -> list | None:
    """[{"debut" (None si non minutées), "texte"}] ou None."""
    if not _jeton():
        return None
    m = _get("matcher.track.get", q_track=titre, q_artist=artiste)
    if m["header"]["status_code"] != 200:
        return None
    piste = m["body"]["track"]
    if piste.get("track_name", "").upper() == "NOKIA":   # réponse factice : jeton refusé
        return None
    if piste.get("has_subtitles"):
        s = _get("track.subtitle.get", commontrack_id=piste["commontrack_id"], subtitle_format="lrc")
        if s["header"]["status_code"] == 200:
            lignes = []
            for x in re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)", s["body"]["subtitle"]["subtitle_body"]):
                if x.group(3).strip():
                    lignes.append({"debut": int(x.group(1)) * 60 + float(x.group(2)), "texte": x.group(3).strip()})
            if lignes:
                return lignes
    if piste.get("has_lyrics"):
        l = _get("track.lyrics.get", commontrack_id=piste["commontrack_id"])
        if l["header"]["status_code"] == 200:
            texte = l["body"]["lyrics"]["lyrics_body"].split("*******")[0]   # mention de licence en fin de texte
            lignes = [{"debut": None, "texte": t.strip()} for t in texte.splitlines() if t.strip()]
            return lignes or None
    return None
