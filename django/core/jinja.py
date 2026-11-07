"""Environnement Jinja2 : les gabarits disposent des mêmes fonctions que les gabarits PHP."""
from contextvars import ContextVar
from datetime import date

from django.middleware.csrf import get_token
from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined
from markupsafe import Markup

from core import clock
from core import conf, helpers
from core.env import get as env_get
from core.i18n import locale, t, tr, tr_filtre
from core.icons import icon

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
        "t": t, "tr": tr, "locale": locale, "config": conf.get, "icon": icon, "env": lambda k: env_get(k, "") or "", "partial": partial, "csrf_field": csrf_field,
        "request_path": request_path, "request_uri": request_uri,
        "e": helpers.e, "url": helpers.url, "path": helpers.path, "asset": helpers.asset, "brand": helpers.brand,
        "fmt_number": helpers.fmt_number, "fmt_date": helpers.fmt_date, "jour_date": helpers.jour_date, "month_name": helpers.month_name,
        "slugify": helpers.slugify, "initials": helpers.initials, "country_name": helpers.country_name,
        "chart_name": helpers.chart_name, "period_label": helpers.period_label, "movement": helpers.movement,
        "is_group_label": helpers.is_group_label, "chart_path": helpers.chart_path, "rank_chart_svg": helpers.rank_chart_svg,
        "flag": helpers.flag, "news_image": helpers.news_image, "legal": helpers.legal, "platform_name": helpers.platform_name, "url_with": helpers.url_with,
        "spotify_url": helpers.spotify_url, "period_slug": helpers.period_slug, "rawurlencode": helpers.rawurlencode,
        "ucfirst": helpers.ucfirst, "dict": dict, "from_json": helpers.from_json, "to_json": helpers.to_json, "php_str": helpers.php_str, "add_days": helpers.add_days, "number_format": helpers.number_format, "php_round": _php_round, "today": lambda: clock.today().isoformat(), "nl2br": helpers.nl2br, "paragraphs": helpers.paragraphs, "url_host": helpers.url_host, "share_url": helpers.share_url, "Markup": Markup, "live_sources": _live_sources, "spotify_auditeurs": _spotify_auditeurs, "clips_youtube": _clips_youtube, "yt_vignette": lambda tid: (lambda v: f"https://i.ytimg.com/vi/{v}/hqdefault.jpg" if v else "")(_clips_youtube([tid]).get(int(tid)) if tid else None), "fmt_court": _fmt_court, "now_year": lambda: clock.today().year, "trim": lambda s: str(s or "").strip(),
        "enumerate": enumerate, "len": len, "min": min, "max": max, "int": int, "str": str, "round": round,
        "sorted": sorted, "list": list, "range": range, "zip": zip, "abs": abs, "float": float,
    })
    _env = env
    env.filters["tr"] = tr_filtre   # textes produits par le code : {{ x|tr }} (06/11/2026)
    return env


def _fmt_court(n) -> str:
    """1 234 567 → « 1,2 M » ; 45 300 → « 45 k » (chiffres des cartes)."""
    n = int(n or 0)
    if n >= 1_000_000:
        if locale() == "en":
            return f"{n / 1_000_000:.1f}".replace(".0", "") + "M"
        return f"{n / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + " M"
    if n >= 10_000:
        return f"{round(n / 1000)} k"
    return helpers.fmt_number(n)


def _clips_youtube(track_ids) -> dict:
    """Clip YouTube officiel de chaque titre (vignettes du Top, 06/11/2026) : {track_id: identifiant de la vidéo}, une requête."""
    ids = [int(i) for i in (track_ids or []) if i]
    if not ids:
        return {}
    try:
        from core import db
        return {int(r["track_id"]): r["external_id"] for r in db.all(
            f"""SELECT DISTINCT ON (track_id) track_id, external_id FROM track_platform_ids
                WHERE platform = 'youtube' AND track_id IN ({','.join(['?'] * len(ids))})
                ORDER BY track_id, is_official DESC, published_at NULLS LAST""", ids)}
    except Exception:  # noqa: BLE001 — sans vignette plutôt qu'une page cassée
        return {}


def _spotify_auditeurs(slug) -> int | None:
    """Auditeurs mensuels Spotify (dernier relevé) d'un artiste, par son adresse : une seule requête, gardée 1 h."""
    from django.core.cache import cache
    table = cache.get("spotify:auditeurs")
    if table is None:
        try:
            from core import db
            table = {r["slug"]: int(r["auditeurs"]) for r in db.all(
                """SELECT DISTINCT ON (s.artist_id) a.slug, s.auditeurs FROM spotify_artistes s JOIN artists a ON a.id = s.artist_id
                   WHERE s.auditeurs IS NOT NULL ORDER BY s.artist_id, s.releve_le DESC""")}
        except Exception:  # noqa: BLE001 — table pas encore créée : aucun chiffre plutôt qu'une page cassée
            table = {}
        cache.set("spotify:auditeurs", table, 3600)
    return table.get(slug)


def _live_sources() -> dict:
    from core.services.live_chart import SOURCES
    return SOURCES


def _php_round(x, precision: int = 0):
    from core.repos import php_round
    return php_round(float(x), precision)
