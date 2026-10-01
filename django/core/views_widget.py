"""Widget du classement à intégrer (blogs, radios) et page qui donne le code d'intégration.

Le code fourni contient l'iframe ET un lien texte vers le site : c'est ce lien, posé dans la page de l'hôte,
qui compte pour le référencement (un lien à l'intérieur d'une iframe n'est pas attribué au site qui l'affiche).
"""
from django.http import Http404

from core import repos
from core.helpers import brand, url
from core.middleware import csp
from core.services import chart_top
from core.views import render, req_str, use_locale

SIZES = (5, 10, 20)
THEMES = ("clair", "sombre")


def _params(request) -> tuple:
    try:
        n = int(req_str(request, "n", "10"))
    except ValueError:
        n = 10
    theme = req_str(request, "theme", "clair")
    return (n if n in SIZES else 10), (theme if theme in THEMES else "clair")


def widget(request, code: str):
    use_locale(request)
    n, theme = _params(request)
    data = chart_top.top(code, n)
    if not data:
        raise Http404
    response = render(request, "widget", {"data": data, "theme": theme, "n": n, "home": url(chart_top.page_path(code)),
                                          "utm": "utm_source=widget&utm_medium=embed"}, layout=None)
    # Affichable dans le site d'un tiers : seule exception à « frame-ancestors 'none' »
    response["Content-Security-Policy"] = csp().replace("frame-ancestors 'none'", "frame-ancestors *")
    response["Cache-Control"] = "public, max-age=1800"
    return response


def embed(request):
    use_locale(request)
    n, theme = _params(request)
    code = req_str(request, "pays", chart_top.REGION).lower()
    countries = {chart_top.REGION: "Afrique de l’Ouest", **{c["code"].lower(): c["name_fr"] for c in repos.countries()}}
    if code not in countries:
        code = chart_top.REGION
    src = url(f"widget/{code}", {"n": n, "theme": theme})
    height = 112 + 46 * n
    snippet = (f'<iframe src="{src}" width="100%" height="{height}" style="border:0;max-width:440px" loading="lazy" '
               f'title="Classement musical {countries[code]} · {brand()}"></iframe>\n'
               f'<p><a href="{url(chart_top.page_path(code))}">Classement musical {countries[code]} : {brand()}</a></p>')
    # Aperçu par une adresse relative : même origine que la page, quel que soit le domaine (avec ou sans www)
    preview = f"/widget/{code}?n={n}&theme={theme}"
    response = render(request, "embed", {"countries": countries, "code": code, "n": n, "theme": theme, "sizes": SIZES,
                                         "src": src, "preview": preview, "height": height, "snippet": snippet,
                                         "meta": {"title": "Intégrer le classement · " + brand(),
                                                  "description": "Affichez le classement musical d’Afrique de l’Ouest sur votre site, "
                                                                 "blog ou site de radio, mis à jour automatiquement."}})
    # Aperçu du widget dans la page même
    response["Content-Security-Policy"] = csp().replace("frame-src 'none'", "frame-src 'self'").replace("frame-src https", "frame-src 'self' https")
    return response
