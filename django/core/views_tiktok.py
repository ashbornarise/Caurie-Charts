"""Vues de connexion TikTok : le secret reste exclusivement côté tâche GitHub."""
import secrets
from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt

from core import db, env
from core.services import tiktok


def connecter(request):
    """Crée un état à usage unique puis lance Login Kit."""
    try:
        tiktok.creer_table()
        state = secrets.token_urlsafe(32)
        db.run("INSERT INTO tiktok_auth (state, recu_le) VALUES (?, NOW())", [state])
        params = {"client_key": env.get("TIKTOK_CLIENT_KEY", tiktok.CLIENT_KEY_DEFAUT),
                  # 25/10/2026 : publication par le Studio (Content Posting API) en plus des statistiques
                  "scope": "user.info.basic,user.info.stats,video.list,video.upload,video.publish",
                  "response_type": "code", "redirect_uri": tiktok.REDIRECT_URI, "state": state}
        return HttpResponseRedirect("https://www.tiktok.com/v2/auth/authorize/?" + urlencode(params))
    except Exception as exc:
        from core.services.platforms import log_write
        log_write("tiktok", "error", f"connecter : {exc}")
        return HttpResponse("Connexion TikTok non disponible", status=503, content_type="text/plain; charset=utf-8")


def retour(request):
    """Valide l'état conservé en base et mémorise le code pour la tâche GitHub."""
    code, state = request.GET.get("code", ""), request.GET.get("state", "")
    if not code or not state:
        return HttpResponse("Connexion TikTok non disponible", status=400, content_type="text/plain; charset=utf-8")
    try:
        tiktok.creer_table()
        ligne = db.one("SELECT id FROM tiktok_auth WHERE state = ? AND recu_le >= NOW() - INTERVAL '10 minutes' ORDER BY id DESC LIMIT 1", [state])
        if not ligne:
            return HttpResponse("Connexion TikTok non disponible", status=400, content_type="text/plain; charset=utf-8")
        db.run("UPDATE tiktok_auth SET code = ?, state = NULL, recu_le = NOW() WHERE id = ?", [code, ligne["id"]])
        return HttpResponse("Connexion TikTok reçue, merci", content_type="text/plain; charset=utf-8")
    except Exception as exc:
        from core.services.platforms import log_write
        log_write("tiktok", "error", f"retour : {exc}")
        return HttpResponse("Connexion TikTok non disponible", status=503, content_type="text/plain; charset=utf-8")


@csrf_exempt
def webhook(request):
    """Événements envoyés par TikTok (publication terminée ou refusée, autorisation retirée…), notés pour le Studio.
    Signature « TikTok-Signature: t=…,s=… » = HMAC-SHA256(secret, "t.corps") vérifiée quand le secret est présent."""
    import hashlib
    import hmac
    import json
    if request.method != "POST":
        return HttpResponse("ok")   # TikTok teste l'adresse en GET
    corps = request.body.decode("utf-8", "replace")
    secret = env.get("TIKTOK_CLIENT_SECRET", "") or ""
    verifie = False
    if secret:
        champs = dict(p.split("=", 1) for p in request.headers.get("TikTok-Signature", "").split(",") if "=" in p)
        attendu = hmac.new(secret.encode(), f"{champs.get('t', '')}.{corps}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(attendu, champs.get("s", "")):
            return HttpResponse("signature invalide", status=401)
        verifie = True
    try:
        d = json.loads(corps or "{}")
    except ValueError:
        d = {}
    db.run("""CREATE TABLE IF NOT EXISTS tiktok_evenements (id BIGSERIAL PRIMARY KEY, evenement TEXT, contenu TEXT,
              verifie BOOLEAN, recu_le TIMESTAMPTZ DEFAULT NOW())""")
    db.run("INSERT INTO tiktok_evenements (evenement, contenu, verifie) VALUES (?, ?, ?)",
           [str(d.get("event") or "")[:80], corps[:4000], verifie])
    return HttpResponse("ok")
