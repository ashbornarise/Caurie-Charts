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
    if tr.get("spotify_playlist"):
        frame.append("https://open.spotify.com")
    return ("default-src 'self'; img-src 'self' data: https:; style-src 'self'; script-src " + " ".join(script)
            + "; connect-src " + " ".join(connect)
            + "; frame-src " + (" ".join(frame) if frame else "'none'")
            + "; form-action 'self'; frame-ancestors 'none'; base-uri 'self'")


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
        return response

    def process_exception(self, request, exception):
        """Page 404 du site (comme en PHP), y compris en mode débogage."""
        from django.http import Http404
        if isinstance(exception, Http404):
            from core.views_errors import render_error
            return render_error(request, 404)
        return None
