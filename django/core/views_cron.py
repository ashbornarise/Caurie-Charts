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


def nuit(request):
    secret = env.get("CRON_SECRET", "")
    if secret and request.headers.get("Authorization", "") != f"Bearer {secret}":
        return _reply("non autorisé", 401)
    token = env.get("GH_DISPATCH_TOKEN", "")
    if not token:
        return _reply("GH_DISPATCH_TOKEN absent", 500)
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    today = datetime.now(timezone.utc).date().isoformat()
    runs = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/runs",
                        params={"created": f">={today}", "per_page": 20}, headers=h, timeout=20).json().get("workflow_runs") or []
    busy = [r for r in runs if r.get("status") != "completed" or r.get("conclusion") == "success"]
    if busy:
        return _reply(f"déjà lancée aujourd'hui ({busy[0].get('status')})")
    r = requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
                      json={"ref": "main"}, headers=h, timeout=20)
    return _reply("chaîne de nuit lancée" if r.status_code == 204 else f"échec GitHub {r.status_code}", 200 if r.status_code == 204 else 502)
