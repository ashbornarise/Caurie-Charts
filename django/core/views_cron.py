"""Réveil de la chaîne de nuit : Vercel appelle /cron/nuit chaque nuit (vercel.json), qui demande à GitHub de lancer
la chaîne quotidienne. Les tâches planifiées de GitHub partent souvent avec des heures de retard ; celles de Vercel
partent dans l'heure. Une seule chaîne par jour : rien n'est lancé si une autre tourne ou a réussi aujourd'hui."""
from datetime import datetime, timezone

import requests
from django.http import HttpResponse

from core import env

REPO = "ashbornarise/Caurie-Charts"
WORKFLOW = "daily.yml"


def _reply(text: str, status: int = 200) -> HttpResponse:
    r = HttpResponse(text, status=status, content_type="text/plain; charset=utf-8")
    r["Cache-Control"] = "no-store"  # jamais gardé par le réseau de Vercel
    return r


def _dispatch(request, workflow: str, label: str):
    secret = env.get("CRON_SECRET", "")
    if secret and request.headers.get("Authorization", "") != f"Bearer {secret}":
        return _reply("non autorisé", 401)
    token = env.get("GH_DISPATCH_TOKEN", "")
    if not token:
        return _reply("GH_DISPATCH_TOKEN absent", 500)
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    today = datetime.now(timezone.utc).date().isoformat()
    runs = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/runs",
                        params={"created": f">={today}", "per_page": 20}, headers=h, timeout=20).json().get("workflow_runs") or []
    busy = [r for r in runs if r.get("status") != "completed" or r.get("conclusion") == "success"]
    if busy:
        return _reply(f"déjà lancé aujourd'hui ({busy[0].get('status')})")
    r = requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/dispatches",
                      json={"ref": "main"}, headers=h, timeout=20)
    return _reply(f"{label} lancé" if r.status_code == 204 else f"échec GitHub {r.status_code}", 200 if r.status_code == 204 else 502)


def nuit(request):
    return _dispatch(request, WORKFLOW, "chaîne de nuit")


def rattrapage(request):
    """5 h UTC : publie ce que la nuit a généré sans le programmer (attend la fin de la nuit si elle tourne encore)."""
    return _dispatch(request, "rattrapage.yml", "rattrapage du matin")


def monde(request):
    """Cauri Monde, appelé par un réveil externe (cron-job.org, gratuit) :
    /cron/monde?q=matin (7 h 30) et ?q=soir (19 h 30) lancent l'édition sur GitHub ;
    ?q=flash (toutes les 10 min) fait le guet ici en quelques secondes et ne lance GitHub que pour une vraie info choc."""
    secret = env.get("CRON_SECRET", "")
    if secret and request.headers.get("Authorization", "") != f"Bearer {secret}" and request.GET.get("cle") != secret:
        return _reply("non autorisé", 401)
    q = request.GET.get("q", "")
    if q not in ("matin", "soir", "flash"):
        return _reply("q = matin, soir ou flash", 400)
    if q == "flash":
        from core.services.social import monde as M
        fiche = M.guette()
        if not fiche:
            return _reply("rien de choc pour l'instant")
    token = env.get("GH_DISPATCH_TOKEN", "")
    if not token:
        return _reply("GH_DISPATCH_TOKEN absent", 500)
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    r = requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/monde.yml/dispatches",
                      json={"ref": "main", "inputs": {"edition": q}}, headers=h, timeout=20)
    return _reply(f"Cauri Monde ({q}) lancé" if r.status_code == 204 else f"échec GitHub {r.status_code}", 200 if r.status_code == 204 else 502)
