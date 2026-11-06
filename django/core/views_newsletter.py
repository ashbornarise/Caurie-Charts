"""Newsletter : inscription depuis le pied de page (formulaire envoyé en arrière-plan, les pages étant en cache),
confirmation et désinscription par lien (06/11/2026)."""
import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.i18n import tr
from core.services import newsletter
from core.views import render, use_locale


@csrf_exempt
def inscrire(request):
    """POST {email, langue, site (piège à robots)} : réponse JSON, jamais mise en cache. Pas de jeton CSRF possible sur
    des pages en cache : la double confirmation par e-mail protège des inscriptions abusives."""
    if request.method != "POST":
        return JsonResponse({"erreur": "méthode"}, status=405)
    try:
        c = json.loads(request.body or b"{}")
    except ValueError:
        c = {}
    if c.get("site"):   # champ caché rempli : robot
        return JsonResponse({"ok": True})
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()
    r = newsletter.inscrire(str(c.get("email") or ""), str(c.get("langue") or "fr"), "pied-de-page", ip)
    resp = JsonResponse({"statut": r}, status=200 if r in ("ok", "deja") else 400)
    resp["Cache-Control"] = "no-store"
    return resp


def _page(request, titre: str, texte: str) -> HttpResponse:
    use_locale(request)
    resp = render(request, "newsletter", {"titre": titre, "texte": texte, "robots": "noindex",
                                          "meta": {"title": titre + " · Cauri Charts"}})
    resp["Cache-Control"] = "no-store"
    return resp


def confirmer(request, jeton: str):
    use_locale(request)
    ok = newsletter.confirmer(jeton)
    if not ok:
        return _page(request, tr("Lien expiré"), tr("Ce lien n’est plus valable. Inscrivez-vous à nouveau depuis le bas de n’importe quelle page."))
    return _page(request, tr("Inscription confirmée"), tr("Merci ! Vous recevrez chaque mardi les N°1 officiels de l’Afrique de l’Ouest."))


def desinscrire(request, jeton: str):
    use_locale(request)
    newsletter.desinscrire(jeton)
    return _page(request, tr("Désinscription enregistrée"), tr("Vous ne recevrez plus la newsletter. Vous pouvez vous réinscrire à tout moment."))
