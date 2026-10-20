"""Relais des profils Instagram (Cauri Studio) pour un appareil chez soi : téléphone Android (Termux) ou PC.

Sans connexion, Instagram renvoie les serveurs vers « Se connecter » pour une page de profil, pas une connexion de
particulier. Le studio pose un marqueur dans le Blob (relais/profils/job-<id>.json) ; l'appareil demande la liste
(GET), relève les posts photo de chaque profil, puis renvoie les liens (POST) : le tri part alors sur GitHub.
La base n'est lue que s'il y a un marqueur. Jeton : dérivé de CRON_SECRET (rien de secret sur l'appareil).
"""
import hashlib
import hmac
import json
import re

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core import env

PREFIXE = "relais/profils/"


def jeton() -> str:
    secret = env.get("CRON_SECRET", "")
    return hmac.new(secret.encode(), b"cauri-relais-profils", hashlib.sha256).hexdigest()[:40] if secret else ""


def _autorise(request) -> bool:
    j = jeton()
    return bool(j) and hmac.compare_digest(request.headers.get("X-Relais", ""), j)


def _reponse(data: dict, status: int = 200) -> JsonResponse:
    r = JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})
    r["Cache-Control"] = "no-store"
    return r


def termine(job_id: int, posts: list[str]) -> str:
    """Les posts du profil sont relevés : on les ajoute au tri et on le lance sur GitHub. Renvoie le nouvel état."""
    from core import db
    from core.studio import _lance
    j = db.one("SELECT id, statut, params FROM studio_jobs WHERE id = ?", [job_id])
    if not j or j["statut"] != "attente_pc":
        return "deja_traite"
    p = json.loads(j["params"] or "{}")
    liens = list(dict.fromkeys((p.get("liens") or []) + posts))[:40]
    p.update({"liens": liens, "profils_lus": p.get("profils") or [], "profils": []})
    if not liens:
        db.update("studio_jobs", {"statut": "erreur", "params": json.dumps(p, ensure_ascii=False),
                                  "erreur": "aucun post photo visible sur ce profil (seulement des vidéos ?)"}, "id = :id", {"id": job_id})
        return "erreur"
    db.update("studio_jobs", {"statut": "attente", "params": json.dumps(p, ensure_ascii=False)}, "id = :id", {"id": job_id})
    erreur = _lance(job_id)
    if erreur:
        db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": job_id})
        return "erreur"
    return "lance"


def a_relever() -> list[dict]:
    """[{job, profils, marqueur}] d'après les marqueurs du Blob (sans réveiller la base)."""
    from core import storage
    out = []
    for m in storage.blob_list(PREFIXE):
        ident = re.search(r"job-(\d+)", m["pathname"])
        if not ident:
            continue
        try:
            profils = requests.get(m["url"], timeout=15).json().get("profils") or []
        except (ValueError, requests.RequestException):
            profils = []
        out.append({"job": int(ident.group(1)), "profils": profils, "marqueur": m["url"]})
    return out


@csrf_exempt
def profils(request):
    """GET : profils à relever. POST {job, liens} : liens des posts relevés -> tri lancé."""
    if not _autorise(request):
        return _reponse({"erreur": "non autorisé"}, 401)
    from core import storage
    if request.method == "GET":
        return _reponse({"profils": [{"job": x["job"], "profils": x["profils"]} for x in a_relever()]})
    try:
        c = json.loads(request.body or b"{}")
        job_id = int(c["job"])
    except (ValueError, KeyError, TypeError):
        return _reponse({"erreur": "job manquant"}, 400)
    liens = [f"https://www.instagram.com/p/{code}/" for code in
             dict.fromkeys(re.findall(r"/p/([A-Za-z0-9_-]{6,})", " ".join(map(str, c.get("liens") or []))))]
    etat = termine(job_id, liens)
    storage.blob_delete([x["marqueur"] for x in a_relever() if x["job"] == job_id])
    return _reponse({"ok": True, "etat": etat, "liens": len(liens)})
