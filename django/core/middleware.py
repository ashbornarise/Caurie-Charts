"""Langue, requête courante et en-têtes de sécurité (mêmes en-têtes et même CSP que Response::send en PHP)."""
from core import conf
from core.i18n import set_locale
from core.jinja import current_request


def csp() -> str:
    tr = conf.get("app.tracking", {})
    script, connect, frame = ["'self'"], ["'self'"], []
    if tr.get("ga_id"):
        script.append("https://www.googletagmanager.com")
        connect += ["https://*.google-analytics.com", "https://*.analytics.google.com", "https://www.googletagmanager.com"]
    if tr.get("meta_pixel_id"):
        script.append("https://connect.facebook.net")
        connect.append("https://www.facebook.com")
    if tr.get("youtube_embeds"):
        frame.append("https://www.youtube-nocookie.com")
        frame.append("https://www.youtube.com")  # lecteur YouTube standard (clips du Monthly Show)
        script.append("https://www.youtube.com")  # API du lecteur YouTube (clips du Monthly Show)
    if tr.get("spotify_playlist"):
        frame.append("https://open.spotify.com")
    media = ["'self'"]
    from core import env as _env
    if _env.get("TURNSTILE_SITE_KEY", ""):
        script.append("https://challenges.cloudflare.com")   # captcha invisible du vote du Monthly Show
        frame.append("https://challenges.cloudflare.com")
    if conf.get("show.trailer_url", "").startswith("https://"):
        media.append("https://" + conf.get("show.trailer_url").split("/")[2])  # vidéo du Monthly Show (Blob)
    return ("default-src 'self'; img-src 'self' data: https:; media-src " + " ".join(media) + "; style-src 'self'; script-src " + " ".join(script)
            + "; connect-src " + " ".join(connect)
            + "; frame-src " + (" ".join(frame) if frame else "'none'")
            + "; form-action 'self'; frame-ancestors 'none'; base-uri 'self'")


MAINTENANCE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cauri Charts · maintenance</title><style>body{margin:0;font-family:system-ui,sans-serif;background:#f7f8fc;color:#0e1228;display:grid;
place-items:center;min-height:100vh;text-align:center;padding:24px}h1{font-size:1.6rem;margin:0 0 8px}p{color:#5c6288;max-width:440px}
b{color:#8B52FF}</style></head><body><main><h1>Cauri Charts revient très vite</h1><p>Le site est en courte maintenance.
Les classements de la musique ouest-africaine reviennent dans quelques instants.</p><p><b>@cauricharts</b> sur Instagram et TikTok</p>
</main></body></html>"""

# Pages jamais mises en cache par le réseau de Vercel : administration, formulaires (jeton CSRF), espace connecté
NO_EDGE_CACHE = ("/admin", "/contact", "/envoie-ta-video", "/declarer", "/revendiquer", "/connexion", "/api/", "/show", "/tiktok/", "/studio")


def edge_cache(request, response) -> None:
    """Pages publiques gardées 10 min par le réseau de Vercel (puis rafraîchies en arrière-plan) : un robot ou un
    visiteur qui revoit une page ne réinterroge pas la base Neon, dont le transfert mensuel est limité."""
    from django.conf import settings
    if request.method not in ("GET", "HEAD") or response.status_code != 200 or response.cookies:
        return
    if request.COOKIES.get(settings.SESSION_COOKIE_NAME) or request.path.startswith(NO_EDGE_CACHE) or request.path.endswith("/revendiquer"):
        return
    if "Cache-Control" in response.headers:
        return  # la vue a déjà choisi (images, plan du site…)
    response.headers["Cache-Control"] = "public, max-age=0, s-maxage=600, stale-while-revalidate=86400"
    # consigne propre au réseau de Vercel (n'est pas transmise au navigateur)
    response.headers["Vercel-CDN-Cache-Control"] = "max-age=600, stale-while-revalidate=86400"
    response._cauri_edge = True   # EdgeVaryMiddleware retirera « Vary: Cookie », qui empêche toute mise en cache


class CauriMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = current_request.set(request)
        set_locale(conf.get("app.locale", "fr"))
        try:
            response = self.get_response(request)
            from core.services.analytics import count_view
            count_view(request, response)  # vues anonymes, agrégées, sans cookie
        finally:
            current_request.reset(token)
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", csp())
        edge_cache(request, response)
        return response

    def process_exception(self, request, exception):
        """Page 404 du site (comme en PHP), y compris en mode débogage."""
        from django.db.utils import OperationalError
        from django.http import Http404, HttpResponse
        if isinstance(exception, Http404):
            from core.views_errors import render_error
            return render_error(request, 404)
        from core.services import neon_watch
        if isinstance(exception, OperationalError) and neon_watch.blocked(exception):
            # Base bloquée (quota de l'offre gratuite) : alerte immédiate et page de maintenance, jamais mise en cache
            neon_watch.alert_blocked(exception)
            resp = HttpResponse(MAINTENANCE, status=503, content_type="text/html; charset=utf-8")
            resp["Retry-After"] = "3600"
            resp["Cache-Control"] = "no-store"
            return resp
        return None


class EdgeVaryMiddleware:
    """Tout à l'extérieur : sur une page publique mise en cache (edge_cache), retire « Cookie » de l'en-tête Vary que
    la session de Django ajoute, et qui empêchait Vercel de garder la page (chaque visite recalculait tout, CPU épuisé
    le 11/10/2026). Ces pages sont identiques pour tous : les pages avec session ou formulaire ne sont jamais en cache."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(response, "_cauri_edge", False) and response.has_header("Vary"):
            rest = [v.strip() for v in response["Vary"].split(",") if v.strip() and v.strip().lower() != "cookie"]
            if rest:
                response["Vary"] = ", ".join(rest)
            else:
                del response["Vary"]
        return response
