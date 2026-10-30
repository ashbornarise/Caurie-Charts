"""Direct Facebook du show mensuel (« The Monthly Show »), par l'API Meta déjà reliée (droit publish_video).

creer()        : direct programmé sur la page (7 jours à l'avance au plus) ; Facebook publie l'annonce « direct à venir »
                 et rappelle les abonnés. L'adresse et la clé de diffusion vont dans un fichier LOCAL (jamais dans le code)
                 que live/obs_facebook.mjs pose dans OBS.
etat()         : statut, spectateurs, lien public.
commentaires() : derniers commentaires du direct (pour les afficher à l'antenne).
"""
import json
import os
from datetime import datetime, timezone

from core.services import meta

FICHIER_CLE = os.environ.get("FACEBOOK_LIVE_FICHIER", r"C:\Users\agbal\Studio-AV\remotion\live\facebook-live.json")


def creer(quand: datetime, titre: str, description: str) -> dict:
    """Crée le direct programmé et enregistre sa clé dans FICHIER_CLE ; renvoie {id, lien, debut}."""
    ecart = (quand - datetime.now(timezone.utc)).total_seconds()
    if not 600 <= ecart <= 7 * 86400:
        raise ValueError("Facebook n'accepte un direct programmé qu'entre 10 minutes et 7 jours à l'avance")
    page = meta._env("META_PAGE_ID")
    r = meta._appel("POST", f"{page}/live_videos", meta.jeton_page(), status="SCHEDULED_UNPUBLISHED",
                    planned_start_time=int(quand.timestamp()), title=titre[:250], description=description[:5000])
    vid = r["id"]
    infos = meta._appel("GET", vid, meta.jeton_page(), fields="id,status,secure_stream_url,stream_url,permalink_url")
    url = infos.get("secure_stream_url") or infos.get("stream_url") or ""
    serveur, _, cle = url.rpartition("/")
    with open(FICHIER_CLE, "w", encoding="utf-8") as f:
        json.dump({"id": vid, "serveur": serveur + "/", "cle": cle, "debut": quand.isoformat(), "titre": titre}, f, ensure_ascii=False)
    return {"id": vid, "lien": "https://www.facebook.com" + (infos.get("permalink_url") or ""), "debut": quand.isoformat(),
            "statut": infos.get("status")}


def _id(vid: str | None) -> str:
    if vid:
        return vid
    with open(FICHIER_CLE, encoding="utf-8") as f:
        return json.load(f)["id"]


def etat(vid: str | None = None) -> dict:
    return meta._appel("GET", _id(vid), meta.jeton_page(), fields="status,live_views,permalink_url,title")


def commentaires(vid: str | None = None, n: int = 20) -> list:
    r = meta._appel("GET", f"{_id(vid)}/comments", meta.jeton_page(), live_filter="no_filter", order="reverse_chronological",
                    limit=n, fields="from{name},message,created_time")
    return [{"nom": (c.get("from") or {}).get("name", ""), "texte": c.get("message", ""), "quand": c.get("created_time")}
            for c in r.get("data") or []]
