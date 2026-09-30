"""Environnement Jinja2 : les gabarits disposent des mêmes fonctions que les gabarits PHP."""
from contextvars import ContextVar
from datetime import date

from django.middleware.csrf import get_token
from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined
from markupsafe import Markup

from core import clock
from core import conf, helpers
from core.i18n import locale, t

current_request: ContextVar = ContextVar("current_request", default=None)
_env: Environment | None = None


def csrf_field() -> Markup:
    req = current_request.get()
    token = get_token(req) if req is not None else ""
    return Markup(f'<input type="hidden" name="csrfmiddlewaretoken" value="{helpers.e(token)}">')


def partial(template: str, /, **data) -> Markup:
    """Équivalent de View::partial('nom', [...]) : gabarit rendu avec ses propres variables."""
    return Markup(_env.get_template(template + ".html").render(**data))


def request_path() -> str:
    req = current_request.get()
    return req.path if req is not None else "/"


def request_uri() -> str:
    req = current_request.get()
    return req.get_full_path() if req is not None else "/"


class SoftUndefined(Undefined):
    """Variable absente = vide (comme `$x ?? ''` en PHP), sans erreur."""
    __slots__ = ()


def environment(**options) -> Environment:
    global _env
    options.pop("undefined", None)
    env = Environment(**options, undefined=SoftUndefined, trim_blocks=False, lstrip_blocks=False,
                      extensions=["jinja2.ext.do", "jinja2.ext.loopcontrols"])
    env.globals.update({
        "t": t, "locale": locale, "config": conf.get, "partial": partial, "csrf_field": csrf_field,
        "request_path": request_path, "request_uri": request_uri,
        "e": helpers.e, "url": helpers.url, "path": helpers.path, "asset": helpers.asset, "brand": helpers.brand,
        "fmt_number": helpers.fmt_number, "fmt_date": helpers.fmt_date, "month_name": helpers.month_name,
        "slugify": helpers.slugify, "initials": helpers.initials, "country_name": helpers.country_name,
        "chart_name": helpers.chart_name, "period_label": helpers.period_label, "movement": helpers.movement,
        "is_group_label": helpers.is_group_label, "chart_path": helpers.chart_path, "rank_chart_svg": helpers.rank_chart_svg,
        "flag": helpers.flag, "legal": helpers.legal, "platform_name": helpers.platform_name, "url_with": helpers.url_with,
        "spotify_url": helpers.spotify_url, "period_slug": helpers.period_slug, "rawurlencode": helpers.rawurlencode,
        "ucfirst": helpers.ucfirst, "dict": dict, "from_json": helpers.from_json, "to_json": helpers.to_json, "php_str": helpers.php_str, "add_days": helpers.add_days, "number_format": helpers.number_format, "php_round": _php_round, "today": lambda: clock.today().isoformat(), "nl2br": helpers.nl2br, "paragraphs": helpers.paragraphs, "url_host": helpers.url_host, "share_url": helpers.share_url, "Markup": Markup, "live_sources": _live_sources, "now_year": lambda: clock.today().year, "trim": lambda s: str(s or "").strip(),
        "enumerate": enumerate, "len": len, "min": min, "max": max, "int": int, "str": str, "round": round,
        "sorted": sorted, "list": list, "range": range, "zip": zip, "abs": abs, "float": float,
    })
    _env = env
    return env


def _live_sources() -> dict:
    from core.services.live_chart import SOURCES
    return SOURCES


def _php_round(x, precision: int = 0):
    from core.repos import php_round
    return php_round(float(x), precision)
