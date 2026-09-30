"""Pages d'erreur (même rendu que le bloc try/catch de public/index.php)."""
import logging
import sys

from django.http import HttpResponse
from django.template.loader import get_template

from core import conf
from core.helpers import brand, url
from core.i18n import t

log = logging.getLogger("cauri")


def render_error(request, status: int, debug: str | None = None) -> HttpResponse:
    title = t(f"error.{status}") + (" · " + brand() if status != 500 else "")
    data = {"status": status, "debug": debug, "countries": [], "flash": [],
            "meta": {"title": title, "description": "", "url": url("/"), "image": "", "type": "website"}}
    content = get_template("error.html").render(data, request)
    html = get_template("layout.html").render({**data, "content": content}, request)
    return HttpResponse(html, status=status)


def not_found(request, exception=None):
    return render_error(request, 404)


def server_error(request):
    exc = sys.exc_info()[1]
    debug = f"{exc!r}" if conf.get("app.debug") and exc else None
    return render_error(request, 500, debug)


def csrf_failure(request, reason=""):
    return render_error(request, 419 if t("error.419") != "error.419" else 403)
