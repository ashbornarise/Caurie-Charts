"""Pages publiques (traduction des contrôleurs PHP : Chart, Catalog, Page, News, Submission, Partner, Share, Seo)."""
import hashlib
import hmac
import json
import math
import re
from datetime import date, datetime, timedelta, timezone

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.template.loader import get_template

from core import clock
from core import conf, db, repos, storage
from core.helpers import PERIOD_SLUGS, brand, chart_path, country_name, news_image, path, period_label, url
from core.i18n import locale, set_locale, t
from core.services import insights, live_chart

# Pages de contenu placées dans la grille à deux colonnes (avec l'encadré latéral)
WITH_ASIDE = {"methodology", "about", "contact", "claim", "submit", "legal", "news", "news-item", "artist", "track", "partners-page"}


# ---------------------------------------------------------------- outils communs

def region() -> dict:
    """Pseudo-pays du classement régional des cinq pays (code « WA », sans ligne dans countries)."""
    return {"id": None, "code": "WA", "chart_size": int(conf.get("charts.prime-wa.size", 20)), "locale": conf.get("app.locale", "fr")}


def use_locale(request, country: dict | None = None) -> None:
    """Langue : choix explicite du visiteur, sinon langue du pays affiché, sinon langue par défaut."""
    chosen = request.session.get("locale") if request.COOKIES.get("cauri_sid") else None
    if isinstance(chosen, str) and chosen in conf.get("app.locales"):
        set_locale(chosen)
    elif country:
        set_locale(country["locale"])


def flash(request, kind: str, message: str) -> None:
    request.session["_flash"] = request.session.get("_flash", []) + [{"type": kind, "message": message}]


def take_flash(request) -> list:
    if not request.COOKIES.get("cauri_sid"):
        return []
    return request.session.pop("_flash", []) if "_flash" in request.session else []


def aside(country: dict) -> dict:
    return {
        "country": country,
        "insights": insights.for_country(country),
        "news": repos.news_latest(4, int(country["id"]) if country.get("id") is not None else None),
        "dyk": insights.did_you_know(),
    }


def site_ld() -> dict:
    """Organisation et site, présents sur chaque page (données structurées schema.org)."""
    return {"@type": "Organization", "@id": url("/") + "#organisation", "name": brand(), "url": url("/"),
            "logo": url("assets/img/brand/logo-share.png"), "areaServed": [c["code"] for c in repos.countries()],
            # Profils officiels : Google les relie au site (panneau de la marque dans les résultats)
            "sameAs": ["https://www.instagram.com/cauricharts/", "https://www.tiktok.com/@caurichartsofficial",
                       "https://www.facebook.com/profile.php?id=61594631234765"]}


def og_image(kind: str, key: str = "site") -> str:
    """Adresse de l'aperçu de lien généré pour la page (1200 × 630)."""
    return url(f"apercu/{kind}/{key}.jpg")


def apercu(request, kind: str, key: str):
    from core.services import og
    data = og.for_page(kind, key)
    resp = HttpResponse(data, content_type="image/jpeg")
    resp["Cache-Control"] = "public, max-age=600, s-maxage=3600, stale-while-revalidate=3600"
    return resp


def _une(items: list) -> list:
    """« À la une » : un article de la rédaction avec image en tête (Hebdo, Matin, annonces), puis les autres."""
    lead = next((n for n in items if (n.get("origin") or "manual") == "manual" and n.get("image_path")), None)         or next((n for n in items if n.get("image_path")), None)
    return ([lead] + [n for n in items if n is not lead])[:5] if lead else items[:5]


def _artist_news(artist_id=None, limit=6) -> list:
    try:
        from core.services import artist_news
        return artist_news.latest(limit, artist_id)
    except Exception:  # noqa: BLE001 — jamais bloquant pour la page
        return []


def json_ld(items: list):
    """Bloc JSON-LD prêt à insérer dans <script type="application/ld+json"> (« </ » neutralisé)."""
    from markupsafe import Markup
    graph = items + [{"@type": "WebSite", "name": brand(), "url": url("/"), "inLanguage": "fr",
                      "publisher": {"@id": url("/") + "#organisation"}}]
    body = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, default=str)
    return Markup(body.replace("</", "<\\/"))


def render(request, template: str, data: dict | None = None, status: int = 200, layout: str = "layout") -> HttpResponse:
    data = dict(data or {})
    if template in WITH_ASIDE and "aside" not in data:
        code = (data.get("artist") or {}).get("country_code") or (data.get("track") or {}).get("country_code") or conf.get("app.pilot_country")
        c = repos.country(code) or (repos.countries() or [None])[0]
        if c:
            data["aside"] = aside(c)
            data["asideWrap"] = True
    data.setdefault("countries", repos.countries())
    try:
        data.setdefault("footer", repos.footer_links())
    except Exception:  # noqa: BLE001 — le bas de page ne doit jamais casser une page
        data.setdefault("footer", {})
    data.setdefault("flash", take_flash(request))
    # Adresse canonique sans paramètres (?lang=, filtres) : une seule URL par page pour les moteurs de recherche
    meta = {"title": brand(), "description": t("meta.default_description"), "url": url(request.path),
            "image": og_image("defaut"), "type": "website", "jsonld": []}
    meta.update({k: v for k, v in (data.get("meta") or {}).items() if v is not None})  # les clés fournies priment
    meta["jsonld"] = json_ld([site_ld()] + list(meta["jsonld"]))
    data["meta"] = meta
    content = get_template(template + ".html").render(data, request)
    html = content if layout is None else get_template(layout + ".html").render({**data, "content": content}, request)
    return HttpResponse(html, status=status)


def redirect(to: str, status: int = 303) -> HttpResponse:
    r = HttpResponseRedirect(to)
    r.status_code = status
    return r


def ip_hash(request) -> str:
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "0.0.0.0")).split(",")[0].strip()
    return hmac.new(str(conf.get("app.key")).encode(), ip.encode(), hashlib.sha256).hexdigest()


def now_utc(delta_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)).strftime("%Y-%m-%d %H:%M:%S")


def req_str(request, key: str, default: str = "") -> str:
    v = request.POST.get(key) if key in request.POST else request.GET.get(key, default)
    return v.strip() if isinstance(v, str) else default


def share_url(run_id: int, fmt: str) -> str:
    return url(f"partage/{run_id}-{fmt}")


# ---------------------------------------------------------------- classements

def home(request):
    requested = req_str(request, "pays").lower()
    regional = requested in ("", "wa")
    country = region() if regional else repos.country(requested)
    if not country:
        raise Http404
    use_locale(request, None if regional else country)
    period_type = PERIOD_SLUGS.get(req_str(request, "periode", "semaine"), "week")
    chart_code = "prime-wa" if regional else "prime"
    run = repos.latest_run(country["id"], chart_code, period_type)
    entries = repos.entries(int(run["id"])) if run else []
    live = None if run else live_chart.build(country["id"], None, int(country["chart_size"]), "prime", 20, period_type)

    highlights = {}
    for code in ("buzz", "fresh", "icon"):
        r = None if regional else repos.latest_run(int(country["id"]), code, "week")
        highlights[code] = {
            "run": r,
            "entries": repos.entries(int(r["id"]), 3) if r else [],
            "live": [] if r else live_chart.build(country["id"], None, 3, code, int(country["chart_size"]))["rows"],
        }
    return render(request, "home", {
        "country": country, "regional": regional, "chartCode": chart_code, "run": run, "entries": entries, "live": live,
        "periodType": period_type, "highlights": highlights, "aside": aside(country), "numberOnes": repos.number_ones(), "officialTops": repos.official_tops(tous_pays=True) if regional and period_type == "week" else [],
        "hotArtists": repos.hot_artists(None if regional else int(country["id"])),
        "homeNews": _une(repos.news_latest(8, None if regional else int(country["id"]))),
        "artistNews": _artist_news(),
        "partners": repos.partners_active(),
        "meta": {
            "title": brand() + " · " + t("home.meta_title", country=country_name(country["code"]), size=country["chart_size"]),
            "description": t("home.meta_description_region" if regional else "home.meta_description", country=country_name(country["code"])),
            "image": og_image("classement", "wa" if regional else country["code"].lower()),
        },
    })


def regional(request, period: str = "semaine", key: str = ""):
    code = req_str(request, "classement")
    code = code if code in ("buzz", "fresh", "icon", "legend") else "prime-wa"
    return _render_chart(request, region(), code, period, key)


def show(request, country: str, chart: str, period: str = "semaine", key: str = ""):
    target = req_str(request, "k")
    if target and re.fullmatch(r"/classements/[a-z-]+/([a-z-]+/)?(semaine|mois|annee)/[\dW-]+", target):
        return redirect(target, 302)
    c = repos.country(country)
    cfg = conf.get(f"charts.{chart}")
    if not c or not cfg or cfg.get("regional"):
        raise Http404
    return _render_chart(request, c, chart, period, key)


def _render_chart(request, country: dict, chart_code: str, period: str, key: str):
    chart = conf.get(f"charts.{chart_code}")
    if not chart or not chart["public"]:
        raise Http404
    is_regional = country["id"] is None
    use_locale(request, None if is_regional else country)
    period_type = PERIOD_SLUGS.get(period or "semaine")
    if not period_type or period_type not in chart["periods"]:
        raise Http404
    run = repos.run(country["id"], chart_code, period_type, key) if key else repos.latest_run(country["id"], chart_code, period_type)
    if key and not run:
        raise Http404

    view, live, live_sources = "official", None, []
    live_period = "all" if req_str(request, "periode") == "tout" else period_type
    if not key and chart_code in ("prime", "prime-wa", "buzz", "fresh", "icon", "legend"):
        is_prime = chart_code in ("prime", "prime-wa")
        live_sources = live_chart.sources(country["id"]) if is_prime and not is_regional else []
        requested = req_str(request, "vue")
        if requested == "officiel":
            view = "official"
        elif requested == "direct":
            view = "live"
        elif requested in live_sources:
            view = requested
        else:
            view = "official" if run else "live"
        if view != "official":
            live = live_chart.build(country["id"], None if view == "live" else view,
                                    100 if (is_prime or chart_code == "legend") else 50,
                                    "prime" if is_prime else chart_code, int(country.get("chart_size") or 20), live_period)
            if is_prime and view == "live":
                live["rows"] = live["rows"][:100]

    reliability = None
    if chart_code in ("prime", "prime-wa"):
        from core.services import reliability as rel
        rows = live["rows"] if live and view == "live" else live_chart.build(country["id"], None, 20, "prime", 20)["rows"]
        reliability = rel.measure(country["id"], rows)

    title = chart["name"] if is_regional else t("chart.title", chart=chart["name"], country=country_name(country["code"]))
    return render(request, "chart", {"reliability": reliability,
        "view": view, "livePeriod": live_period, "live": live, "liveSources": [] if is_regional else live_sources,
        "country": country, "regional": is_regional, "chartCode": chart_code, "chart": chart, "periodType": period_type,
        "run": run, "entries": repos.entries(int(run["id"])) if run else [],
        "history": repos.published_runs(country["id"], chart_code, period_type), "aside": aside(country),
        "numerosUn": repos.numeros_un() if is_regional and view == "official" and period_type == "week" else None,
        "meta": {
            "title": title + (" · " + period_label(run) if run else "") + " · " + brand(),
            "description": t(f"chart.description.{chart_code}", country=country_name(country["code"])),
            "image": og_image("classement", "wa" if is_regional else country["code"].lower()),
        },
    })


# ---------------------------------------------------------------- catalogue

from core.services import spotify_apify  # noqa: E402 — auditeurs mensuels sur les pages artistes

def artist(request, slug: str):
    a = repos.artist(slug)
    if not a:
        raise Http404
    use_locale(request)
    tracks = repos.artist_tracks(int(a["id"]))
    charted = [x for x in tracks if x["peak"] is not None]
    icon_rank = None
    for row in live_chart.build(None, None, 500, "icon")["rows"]:
        if int(row["artist_id"]) == int(a["id"]):
            icon_rank = row["rank"]
            break
    return render(request, "artist", {
        "artistNews": _artist_news(int(a["id"]), 6),
        "live": repos.artist_live(int(a["id"])), "iconRank": icon_rank, "artist": a, "tracks": tracks,
        "bestPeak": min(x["peak"] for x in charted) if charted else None,
        "totalWeeks": sum(int(x["weeks"] or 0) for x in tracks),
        "iconHistory": repos.artist_icon_history(int(a["id"])),
        "spotify": spotify_apify.fiche(int(a["id"])),
        "meta": {"title": a["name"] + " · " + brand(),
                 "description": t("artist.meta_description", name=a["name"], country=country_name(a["country_code"])), "type": "profile",
                 "image": og_image("artiste", a["slug"]),
                 "jsonld": [{"@type": "MusicGroup", "name": a["name"], "url": url("artiste/" + a["slug"]),
                             **({"image": a["image_url"]} if str(a.get("image_url") or "").startswith("https://") else {}),
                             "foundingLocation": {"@type": "Country", "name": country_name(a["country_code"])},
                             "track": [{"@type": "MusicRecording", "name": x["title"], "url": url("titre/" + x["slug"])} for x in tracks[:10]]}]},
    })


def track(request, slug: str):
    tr = repos.track(slug)
    if not tr:
        raise Http404
    use_locale(request)
    positions = repos.track_positions(int(tr["id"]))
    spotify = db.one(
        """SELECT streams, period_start AS start, period_end AS "end" FROM submissions
           WHERE track_id = ? AND platform = 'spotify' AND status = 'validated' ORDER BY period_end DESC LIMIT 1""", [int(tr["id"])])
    recent = db.value("""SELECT 1 FROM chart_observations WHERE track_id = ? AND observed_on >= CURRENT_DATE - 30
                          AND source NOT IN ('deezer_popularity', 'youtube_views') LIMIT 1""", [int(tr["id"])])
    return render(request, "track", {
        "robots": None if recent else "noindex, follow",
        "spotify": spotify, "track": tr, "positions": positions, "links": repos.track_links(int(tr["id"])),
        "peak": min(p["position"] for p in positions) if positions else None,
        "meta": {"title": tr["title"] + " · " + tr["artist_name"] + " · " + brand(),
                 "description": t("track.meta_description", title=tr["title"], artist=tr["artist_name"]), "type": "music.song",
                 "image": og_image("titre", tr["slug"]),
                 "jsonld": [{"@type": "MusicRecording", "name": tr["title"], "url": url("titre/" + tr["slug"]),
                             "byArtist": {"@type": "MusicGroup", "name": tr["artist_name"], "url": url("artiste/" + tr["artist_slug"])},
                             **({"image": tr["cover_url"]} if str(tr.get("cover_url") or "").startswith("https://") else {}),
                             **({"datePublished": str(tr["release_date"])[:10]} if tr.get("release_date") else {})}]},
    })


# ---------------------------------------------------------------- pages

def formula_effective_for(day: str) -> dict:
    row = db.one("SELECT version, formula_json FROM formula_versions WHERE effective_from <= ? ORDER BY effective_from DESC, version DESC LIMIT 1", [day])
    defaults = json.loads(json.dumps(conf.get("formula")))
    if not row:
        return defaults

    def merge(a, b):
        for k, v in b.items():
            a[k] = merge(a.get(k, {}), v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return a
    formula = merge(defaults, json.loads(row["formula_json"] or "{}") or {})
    formula["version"] = int(row["version"])
    return formula


def methodology(request):
    use_locale(request)
    today = clock.today().isoformat()
    return render(request, "methodology", {
        "formula": formula_effective_for(today),
        "upcoming": db.all("SELECT version, effective_from, note FROM formula_versions WHERE effective_from > ? ORDER BY effective_from", [today]),
        "exclusions": repos.exclusions(),
        "corrections": db.all(
            """SELECT r.period_key, r.corrected_at, r.correction_note, ct.name AS chart_name, c.code AS country_code
               FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id JOIN countries c ON c.id = r.country_id
               WHERE r.corrected_at IS NOT NULL AND r.status = 'published' ORDER BY r.corrected_at DESC LIMIT 30"""),
        "meta": {"title": t("methodology.title") + " · " + brand(), "description": t("methodology.meta_description")},
    })


def about(request):
    use_locale(request)
    return render(request, "about", {"meta": {"title": t("about.title") + " · " + brand()}})


LEGAL_PAGES = {"mentions-legales": "mentions", "confidentialite": "confidentialite", "cookies": "cookies", "conditions": "conditions"}


def legal(request):
    use_locale(request)
    slug = request.path.strip("/")
    page = LEGAL_PAGES.get(slug)
    if not page:
        raise Http404
    from core.jinja import partial
    return render(request, "legal", {
        "slug": slug, "body": partial("legal/" + page), "pages": LEGAL_PAGES,
        "meta": {"title": t(f"legal.{page}") + " · " + brand(), "description": t(f"legal.{page}_description", brand=brand())},
    })


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def contact(request):
    use_locale(request)
    if request.method == "POST":
        return _contact_send(request)
    return render(request, "contact", {"old": {}, "errors": {},
                                       "type": "contestation" if req_str(request, "type") == "contestation" else "contact",
                                       "meta": {"title": t("contact.title") + " · " + brand()}})


def _contact_send(request):
    old = {
        "type": "contestation" if req_str(request, "type") == "contestation" else "contact",
        "name": req_str(request, "name")[:150], "email": req_str(request, "email")[:190],
        "subject": req_str(request, "subject")[:200], "message": req_str(request, "message")[:5000],
    }
    if req_str(request, "website"):
        return redirect("/contact")  # pot de miel : robot
    errors = {}
    if not old["name"]:
        errors["name"] = t("form.required")
    if not EMAIL_RE.match(old["email"]):
        errors["email"] = t("form.invalid_email")
    if not old["subject"]:
        errors["subject"] = t("form.required")
    if len(old["message"]) < 10:
        errors["message"] = t("form.too_short")
    h = ip_hash(request)
    if int(db.value("SELECT COUNT(*) FROM contact_messages WHERE ip_hash = ? AND created_at > ?", [h, now_utc(-86400)])) >= 5:
        errors["message"] = t("form.rate_limited")
    if errors:
        return render(request, "contact", {"old": old, "errors": errors, "type": old["type"], "meta": {"title": t("contact.title")}}, 422)
    db.insert("contact_messages", {**old, "ip_hash": h})
    from core import mail
    kind = "contestation" if old["type"] == "contestation" else "message"
    mail.notify_admin(f"{kind.capitalize()} : {old['subject']}", f"De : {old['name']} <{old['email']}>\n\n{old['message']}", old["email"])
    mail.acknowledge(old["email"], old["name"], kind)
    flash(request, "success", t("contact.sent"))
    return redirect("/contact")


def fan_video(request):
    """« Envoie ta vidéo de concert » : les fans proposent leurs vidéos (lien + autorisation écrite de publier avec crédit)."""
    use_locale(request)
    meta = {"title": "Envoie ta vidéo de concert · " + brand(),
            "description": "Tu as filmé un concert ? Envoie ta vidéo à Cauri Charts : les meilleures passent sur nos pages, avec ton nom."}
    if request.method != "POST":
        return render(request, "fan-video", {"old": {}, "errors": {}, "meta": meta})
    if req_str(request, "website"):
        return redirect("/envoie-ta-video")   # pot de miel : robot
    old = {k: req_str(request, k)[:n] for k, n in (("link", 500), ("artist", 150), ("event", 200), ("city", 120), ("event_date", 10),
                                                    ("name", 150), ("handle", 120), ("email", 190))}
    old["consent"] = request.POST.get("consent") == "1"
    errors = {}
    if not old["link"].startswith(("https://", "http://")):
        errors["link"] = "Colle le lien complet de ta vidéo (il commence par https://)."
    for f in ("artist", "name"):
        if not old[f]:
            errors[f] = t("form.required")
    if not EMAIL_RE.match(old["email"]):
        errors["email"] = t("form.invalid_email")
    if not old["consent"]:
        errors["consent"] = "Coche l'autorisation : sans elle, nous ne pouvons pas publier ta vidéo."
    date_concert = None
    if old["event_date"]:
        try:
            date_concert = datetime.strptime(old["event_date"], "%Y-%m-%d").date()
        except ValueError:
            errors["event_date"] = t("form.required")
    h = ip_hash(request)
    if int(db.value("SELECT COUNT(*) FROM fan_videos WHERE ip_hash = ? AND created_at > ?", [h, now_utc(-86400)])) >= 10:
        errors["link"] = t("form.rate_limited")
    if errors:
        return render(request, "fan-video", {"old": old, "errors": errors, "meta": meta}, 422)
    db.insert("fan_videos", {"name": old["name"], "email": old["email"], "handle": old["handle"] or None, "artist": old["artist"],
                             "event": old["event"] or None, "city": old["city"] or None, "event_date": date_concert,
                             "link": old["link"], "consent": 1, "ip_hash": h})
    from core import mail
    mail.notify_admin(f"Vidéo de concert proposée : {old['artist']}",
                      f"De : {old['name']} {old['handle']} <{old['email']}>\nConcert : {old['event']} · {old['city']} · {old['event_date']}\n"
                      f"Lien : {old['link']}\nAutorisation de publier avec crédit : oui", old["email"])
    flash(request, "success", "Merci ! Ta vidéo est bien arrivée. Si elle passe sur nos pages, on te prévient par e-mail.")
    return redirect("/envoie-ta-video")


def set_locale_view(request, loc: str):
    if loc in conf.get("app.locales"):
        request.session["locale"] = loc
    back = req_str(request, "retour", "/")
    if not back.startswith("/") or back.startswith("//"):
        back = "/"  # retour interne uniquement (pas de redirection ouverte)
    return redirect(back)


# ---------------------------------------------------------------- actualités

NEWS_PER_PAGE = 12


def news(request):
    use_locale(request)
    try:
        page = max(1, int(req_str(request, "page", "1")))
    except ValueError:
        page = 1
    return render(request, "news", {
        "items": repos.news_latest(NEWS_PER_PAGE, None, (page - 1) * NEWS_PER_PAGE), "page": page,
        "pages": math.ceil(repos.news_count_published() / NEWS_PER_PAGE),
        "meta": {"title": t("news.title") + " · " + brand(), "description": t("news.meta_description", brand=brand())},
    })


def artist_news_page(request):
    """Toute l'actu des artistes : sorties à venir, nouveaux clips YouTube (les plus vus d'abord), albums, concerts…"""
    use_locale(request)
    from core.services import artist_news
    kind = req_str(request, "type")
    kind = kind if kind in artist_news.KINDS else None
    try:
        items = artist_news.latest(60, None, 45, kind)
    except Exception:  # noqa: BLE001 — jamais bloquant pour la page
        items = []
    return render(request, "artist-news-page", {
        "items": items, "kind": kind, "kinds": {k: v for k, v in artist_news.KINDS.items() if k != "autre"},
        "meta": {"title": "L’actu des artistes d’Afrique de l’Ouest · " + brand(),
                 "description": "Nouveaux clips, albums, EP, concerts et distinctions des artistes d’Afrique de l’Ouest, sources à l’appui, mis à jour chaque nuit par " + brand() + "."},
    })


def presse(request):
    """Espace presse : communiqués (PDF consultables et indexés), visuels, contact."""
    use_locale(request)
    from core import press
    return render(request, "presse", {
        "releases": press.published(),
        "meta": {"title": "Espace presse · " + brand(),
                 "description": "Communiqués de presse, visuels et contact presse de Cauri Charts, la référence de la musique ouest-africaine."},
    })


def distinction(request, did: str, kind: str | None = None):
    """Page publique d'une distinction officielle : la carte, sa preuve (le classement), les fichiers à télécharger."""
    use_locale(request)
    from core.services import distinctions as D
    d = db.one("""SELECT d.*, a.slug AS artist_slug, t.slug AS track_slug FROM award_distinctions d JOIN artists a ON a.id = d.artist_id
                  LEFT JOIN tracks t ON t.id = d.track_id WHERE d.id = ?""", [int(did)])
    if not d:
        raise Http404
    if kind in ("impression", "reconnaissance", "kit") or kind in D.KIT:
        data, ctype, name = D.files(d, kind)
        resp = HttpResponse(data, content_type=ctype)
        from urllib.parse import quote
        resp["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
        resp["Cache-Control"] = "public, max-age=86400"
        return resp
    image = url("media/distinctions/" + d["image_name"]) if d["image_name"] else None
    month = D.month_label(d["period_key"])
    title = f"Distinction officielle N° {int(d['id']):04d} · {d['artist_name']}"
    return render(request, "distinction", {
        "d": d, "image": image, "month": month,
        "meta": {"title": title + " · " + brand(), "image": image,
                 "description": f"{d['artist_name']}, N°{d['rank']} du {d['chart_label']} en {month.lower()}"
                                + (f" avec « {d['title']} »" if d["title"] else "") + ". Distinction officielle Cauri Charts, calculée sur des données réelles."},
    })


def edition_slides(item: dict) -> list:
    """Diapositives (4:5) du carrousel d'un numéro de Cauri Hebdo ou Cauri Matin, la une en premier."""
    guid = str(item.get("external_guid") or "")
    if guid.startswith("cauri-hebdo-"):
        week = guid.rsplit("-W", 1)[-1].lstrip("0")
        rows = db.all("SELECT carousel, facts FROM social_posts WHERE theme = 'hebdo' ORDER BY slot_date DESC LIMIT 20")
        rows = [r for r in rows if str(json.loads(r["facts"] or "{}").get("week")) == week]
    elif guid.startswith("cauri-matin-"):
        rows = db.all("SELECT carousel, facts FROM social_posts WHERE theme = 'matin' AND slot_date = ? LIMIT 1", [guid.removeprefix("cauri-matin-")])
    else:
        return []
    try:
        files = [sl["file"] for sl in json.loads(rows[0]["carousel"] or "[]")] if rows else []
    except (ValueError, KeyError, TypeError):
        files = []
    return [url("media/social/" + f) for f in files if f]


def news_item(request, slug: str):
    use_locale(request)
    item = repos.news_by_slug(slug)
    if not item:
        # Anciennes adresses des numéros Cauri (titre dans l'adresse) : redirection permanente vers l'adresse stable
        m = re.search(r"^cauri-hebdo-.*-(\d{4})-s(\d{2})$", slug)
        if m and repos.news_by_slug(f"cauri-hebdo-{m.group(1)}-semaine-{m.group(2)}"):
            return redirect(path(f"actualites/cauri-hebdo-{m.group(1)}-semaine-{m.group(2)}"), 301)
        m = re.search(r"^cauri-matin-.*-(\d{4}-\d{2}-\d{2})$", slug)
        if m and repos.news_by_slug(f"cauri-matin-{m.group(1)}"):
            return redirect(path(f"actualites/cauri-matin-{m.group(1)}"), 301)
        raise Http404
    image = url(news_image(item["image_path"])) if item.get("image_path") else None
    slides = edition_slides(item)
    if slides:
        image = og_image("edition", item["slug"])  # aperçu léger 1200 × 630 avec la une du numéro
    return render(request, "news-item", {"item": item, "slides": slides, "meta": {
        "title": item["title"] + " · " + brand(), "description": item["summary"], "type": "article", "image": image,
        "jsonld": [{"@type": "NewsArticle", "headline": item["title"][:110], "description": item["summary"],
                    "datePublished": str(item["published_at"]).replace(" ", "T"), "url": url("actualites/" + item["slug"]),
                    **({"image": [image]} if image else {}),
                    "publisher": {"@type": "Organization", "name": brand(), "logo": {"@type": "ImageObject", "url": url("assets/img/brand/logo-share.png")}}}]}})


def partners(request):
    use_locale(request)
    return render(request, "partners-page", {"partners": repos.partners_active(),
                                             "meta": {"title": t("partners.title") + " · " + brand(),
                                                      "description": t("partners.meta_description", brand=brand())}})


# ---------------------------------------------------------------- déclarations

SUBMIT_PLATFORMS = ["spotify", "audiomack", "boomplay", "apple_music", "deezer", "youtube"]


def parse_breakdown(text: str):
    """« TG 60, CI 25, FR 15 » → {'TG': 60.0, …}, ou None si illisible ou total > 100 %."""
    if not text.strip():
        return {}
    out = {}
    for part in re.split(r"[,;\n]+", text):
        if not part.strip():
            continue
        m = re.fullmatch(r"\s*([A-Za-z]{2})\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*%?\s*", part)
        if not m:
            return None
        out[m.group(1).upper()] = float(m.group(2).replace(",", "."))
    return out if sum(out.values()) <= 100.5 else None


def submit(request):
    use_locale(request)
    if request.method != "POST":
        return _submit_render(request, {}, {})
    if req_str(request, "website"):
        return redirect("/declarer")
    old = {k: req_str(request, k) for k in ("artist", "track", "contact_name", "email", "platform", "period_start", "period_end", "streams", "breakdown")}
    old["artist"], old["track"], old["contact_name"] = old["artist"][:150], old["track"][:200], old["contact_name"][:150]
    old["email"], old["breakdown"] = old["email"][:190], old["breakdown"][:500]
    errors = {}
    for f in ("artist", "track", "contact_name"):
        if not old[f]:
            errors[f] = t("form.required")
    if not EMAIL_RE.match(old["email"]):
        errors["email"] = t("form.invalid_email")
    if old["platform"] not in SUBMIT_PLATFORMS:
        errors["platform"] = t("form.required")
    try:
        start = datetime.strptime(old["period_start"], "%Y-%m-%d").date()
        end = datetime.strptime(old["period_end"], "%Y-%m-%d").date()
        if end < start or end > clock.today() or (end - start).days > 92:
            raise ValueError
    except ValueError:
        errors["period_end"] = t("submit.error_period")
    if not old["streams"].isdigit() or int(old["streams"]) <= 0:
        errors["streams"] = t("submit.error_streams")
    breakdown = parse_breakdown(old["breakdown"])
    if old["breakdown"] and breakdown is None:
        errors["breakdown"] = t("submit.error_breakdown")
    if request.POST.get("consent") != "1":
        errors["consent"] = t("submit.error_consent")
    h = ip_hash(request)
    if int(db.value("SELECT COUNT(*) FROM submissions WHERE ip_hash = ? AND created_at > ?", [h, now_utc(-86400)])) >= 10:
        errors["streams"] = t("form.rate_limited")
    screenshot = None
    if not errors:
        try:
            screenshot = storage.store_screenshot(request.FILES.get("screenshot"))
        except ValueError as exc:
            errors["screenshot"] = str(exc)
    if errors:
        return _submit_render(request, old, errors, 422)
    match = db.one("""SELECT t.id, t.artist_id FROM tracks t JOIN artists a ON a.id = t.artist_id
                      WHERE t.title COLLATE cauri_ci = ? AND a.name COLLATE cauri_ci = ? LIMIT 1""", [old["track"], old["artist"]])
    db.insert("submissions", {
        "track_id": match["id"] if match else None, "artist_id": match["artist_id"] if match else None,
        "submitted_artist_name": old["artist"], "submitted_track_title": old["track"], "contact_name": old["contact_name"],
        "contact_email": old["email"], "platform": old["platform"], "period_start": old["period_start"], "period_end": old["period_end"],
        "streams": int(old["streams"]), "country_breakdown": json.dumps(breakdown) if breakdown else None,
        "screenshot_path": screenshot, "ip_hash": h,
    })
    flash(request, "success", t("submit.sent"))
    return redirect("/declarer")


def _submit_render(request, old, errors, status=200):
    return render(request, "submit", {"old": old, "errors": errors, "platforms": SUBMIT_PLATFORMS,
                                      "meta": {"title": t("submit.title") + " · " + brand(), "description": t("submit.intro")}}, status)


# ---------------------------------------------------------------- référencement

def robots(request):
    allow = conf.get("app.env") == "production"
    body = "User-agent: *\n" + ("Disallow: /admin\nDisallow: /partage/\n" if allow else "Disallow: /\n") + "Sitemap: " + url("sitemap.xml") + "\n"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def sitemap(request):
    """Plan du site avec ses images (photos d'artistes, pochettes, unes et pages des numéros, aperçus) pour Google Images."""
    from core.helpers import e
    urls = [url("/"), url("la-machine"), url("methodologie"), url("a-propos"), url("contact"), url("declarer")]
    images: dict = {url("/"): [(og_image("classement", "wa"), "Top 20 Afrique de l’Ouest · Cauri Charts")]}
    for c in repos.countries():
        for code, ch in conf.get("charts").items():
            if ch["public"] and not ch.get("regional"):
                for p in ch["periods"]:
                    urls.append(url(chart_path(c["code"], code, p)))
        images[url(chart_path(c["code"], "prime", "week"))] = [(og_image("classement", c["code"].lower()), f"Top {country_name(c['code'])} · Cauri Charts")]
    from core import press
    urls += [url("presse")] + [url(f) for r in press.published() for _l, f in r["files"] if f.endswith(".pdf")]
    urls += [url(p) for p in ("actualites", "actu-artistes", "partenaires", "integrer", "mentions-legales", "confidentialite", "cookies")]
    if conf.get("show.public"):
        urls.append(url("show"))
    data = repos.sitemap_entries()
    dated = {}
    for a in data["artists"]:
        u = url("artiste/" + a["slug"])
        dated[u] = a["updated_at"]
        images[u] = [(og_image("artiste", a["slug"]), f"{a['name']} · Cauri Charts")]
        if str(a.get("image") or "").startswith("https://"):
            images[u].append((a["image"], f"{a['name']}, photo"))
    for n in data["news"]:
        u = url("actualites/" + n["slug"])
        dated[u] = n["published_at"]
        imgs = [(sl, f"{n['title']} · page {i + 1}") for i, sl in enumerate(edition_slides(n))]
        if not imgs and n.get("image_path"):
            imgs = [(url(news_image(n["image_path"])), n["title"])]
        if imgs:
            images[u] = imgs[:10]
    track_urls = []
    for x in data["tracks"]:
        u = url("titre/" + x["slug"])
        track_urls.append(u)
        images[u] = [(og_image("titre", x["slug"]), f"{x['title']} · {x['artist']} · Cauri Charts")]
        if str(x.get("cover_url") or "").startswith("https://"):
            images[u].append((x["cover_url"], f"{x['title']} · {x['artist']}, pochette"))
    urls += list(dated) + track_urls
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
           'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n')
    today = clock.today().isoformat()
    for u in [url("/")] + [x for x in urls if "/classements/" in x]:
        dated.setdefault(u, today)  # classements : mis à jour chaque jour
    for u in dict.fromkeys(urls):
        last = f"<lastmod>{str(dated[u])[:10]}</lastmod>" if dated.get(u) else ""
        imgs = "".join(f"<image:image><image:loc>{e(i)}</image:loc></image:image>" for i, _ in images.get(u, []))
        prio = "1.0" if u == url("/") else "0.9" if ("/classements/" in u and "/semaine" in u) or "cauri-hebdo" in u or "cauri-matin" in u \
            else "0.7" if "/artiste/" in u or "/classements/" in u else "0.4" if "/titre/" in u else "0.5"
        xml += f"  <url><loc>{e(u)}</loc>{last}<priority>{prio}</priority>{imgs}</url>\n"
    resp = HttpResponse(xml + "</urlset>", content_type="application/xml; charset=utf-8")
    resp["Cache-Control"] = "public, max-age=3600, s-maxage=21600"
    return resp


def llms(request):
    """Résumé du site pour les moteurs de recherche IA : quoi, comment, et le classement de ce jour."""
    rows = [r for r in live_chart.build(None, None, 10, "prime", 20, "latest")["rows"] if not r.get("is_artist")]
    lines = [f"# {brand()}", "",
             "> Le classement musical hebdomadaire de 16 pays d'Afrique de l'Ouest (Togo, Bénin, Ghana, Côte d'Ivoire, Sénégal, "
             "Nigeria, Burkina Faso, Mali, Niger, Guinée, Guinée-Bissau, Cap-Vert, Gambie, Liberia, Sierra Leone, Mauritanie), "
             "calculé chaque jour à partir des classements publics d'Apple Music, Deezer, Shazam et YouTube, selon une méthode publique.", "",
             f"## Top 10 Afrique de l'Ouest au {clock.today():%d/%m/%Y}", ""]
    lines += [f"{r['rank']}. {r['title']} - {r['artist_name']} ({url('titre/' + r['track_slug'])})" for r in rows]
    lines += ["", "## Pages principales", "",
              f"- Top 20 Afrique de l'Ouest : {url('classements/afrique-de-l-ouest')}",
              *[f"- Top {country_name(c['code'])} : {url(chart_path(c['code'], 'prime'))}" for c in repos.countries()],
              f"- Méthodologie et indice de fiabilité : {url('methodologie')}",
              f"- Actualités, Cauri Hebdo et Cauri Matin : {url('actualites')}",
              f"- À propos : {url('a-propos')}", ""]
    resp = HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
    resp["Cache-Control"] = "public, max-age=3600"
    return resp


def google_verification(request, token: str):
    """Fichier de vérification Google Search Console (propriété du site)."""
    if token != "1c5bd27ce1969a86":
        raise Http404
    return HttpResponse(f"google-site-verification: google{token}.html", content_type="text/html; charset=utf-8")


def favicon(request):
    from django.http import FileResponse
    resp = FileResponse(open(storage.REPO / "public" / "favicon.ico", "rb"), content_type="image/x-icon")
    resp["Cache-Control"] = "public, max-age=604800"
    return resp


# ---------------------------------------------------------------- images de partage

def share_image(request, run_id: str, fmt: str):
    import os
    import tempfile
    from pathlib import Path
    from core.helpers import slugify
    from core.services import share_image as si

    ext = "png" if si.png_available() and req_str(request, "type") != "svg" else "svg"
    run = repos.run_by_id(int(run_id))
    if not run or fmt not in si.FORMATS:
        raise Http404
    use_locale(request, repos.country(run["country_code"]))
    # Cache disque : storage/cache/share en local, dossier temporaire sur Vercel (disque en lecture seule)
    base = Path(tempfile.gettempdir()) / "cauri-share" if os.environ.get("VERCEL") else storage.REPO / "storage" / "cache" / "share"
    stamp = hashlib.md5((str(run["computed_at"]) + locale()).encode()).hexdigest()[:10]
    cache_file = base / f"{run['id']}-{fmt}-{stamp}.{ext}"
    if cache_file.is_file():
        body = cache_file.read_bytes()
    else:
        ops = si.layout(run, repos.entries(int(run["id"]), 10), fmt)
        body = si.render_png(ops, fmt) if ext == "png" else si.render_svg(ops, fmt)
        try:
            base.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(body)
        except OSError:
            pass
    filename = f"{slugify(brand())}-{run['country_code'].lower()}-{run['chart_code']}-{run['period_key']}.{ext}"
    resp = HttpResponse(body, content_type="image/png" if ext == "png" else "image/svg+xml")
    resp["Cache-Control"] = "public, max-age=86400"
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


def not_found_fallback(request, unmatched: str = ""):
    raise Http404


def media(request, file_path: str):
    """Médias générés (vignettes, logos, posts) : fichier local, sinon Vercel Blob."""
    from django.http import FileResponse
    safe = file_path.replace("\\", "/").lstrip("/")
    if ".." in safe.split("/"):
        raise Http404
    local = storage.MEDIA / safe
    if local.is_file():
        return FileResponse(open(local, "rb"))
    base = storage.blob_public_url()
    if base:
        return redirect(f"{base}/media/{safe}", 302)
    raise Http404


SERIES = {
    "cauri-matin": ("cauri-matin-", "Cauri Matin", "Tous les numéros de Cauri Matin : le n°1 de l’Afrique de l’Ouest au réveil, les plus fortes montées, les nouveaux entrés et l’actu de la région."),
    "cauri-hebdo": ("cauri-hebdo-", "Cauri Hebdo", "Tous les numéros de Cauri Hebdo : la semaine de la musique d’Afrique de l’Ouest, chaque dimanche."),
    "cauri-monde": ("monde-", "Cauri Monde", "L’actualité musicale mondiale vue par Cauri Charts : les stars, les records, les sorties, les grands événements."),
}


def news_series(request, serie: str):
    """Une série du média (Cauri Matin, Cauri Hebdo, Cauri Monde) : tous ses numéros, du plus récent au plus ancien."""
    use_locale(request)
    if serie not in SERIES:
        raise Http404
    prefix, title, note = SERIES[serie]
    try:
        page = max(1, int(req_str(request, "page", "1")))
    except ValueError:
        page = 1
    return render(request, "news", {
        "items": repos.news_latest(NEWS_PER_PAGE, None, (page - 1) * NEWS_PER_PAGE, prefix), "page": page,
        "pages": math.ceil(repos.news_count_published(prefix) / NEWS_PER_PAGE), "heading": title, "note": note, "base": serie,
        "meta": {"title": title + " · " + brand(), "description": note},
    })


def machine(request):
    """Article « De 0 à 1 » : comment la machine Cauri Charts collecte, calcule, écrit, illustre et publie seule (version web du PDF)."""
    use_locale(request)
    title = "De 0 à 1 : treize jours pour construire une rédaction qui ne dort jamais · " + brand()
    desc = ("Comment Cauri Charts collecte, calcule, écrit, illustre et publie seul l'information musicale de l'Afrique de l'Ouest "
            "et du monde : données, formule, crons, agents IA et diffusion.")
    article = {"@type": "Article", "headline": "De 0 à 1 : treize jours pour construire une rédaction qui ne dort jamais",
               "description": desc, "datePublished": "2026-10-12", "inLanguage": "fr",
               "image": url("assets/machine/og.jpg"), "author": {"@type": "Organization", "name": brand()},
               "publisher": {"@type": "Organization", "name": brand()}}
    return render(request, "machine", {"meta": {"title": title, "description": desc, "type": "article",
                                                "image": url("assets/machine/og.jpg"), "jsonld": [article]}}, layout=None)


def world_listeners(request):
    """Les artistes d’Afrique de l’Ouest les plus écoutés sur Spotify : nos relevés de la semaine (auditeurs, hausse,
    1re ville), complétés par Kworb pour le top mondial ; filtre par pays (?pays=NG)."""
    use_locale(request)
    from django.core.cache import cache
    pays = (req_str(request, "pays") or "").upper()[:2] or None
    cle = f"spotify-classement-{pays or 'tous'}"
    data = cache.get(cle)
    if data is None:
        data = spotify_apify.classement(pays)
        cache.set(cle, data, 3 * 3600)
    return render(request, "world", {
        **data, "paysChoisi": pays,
        "meta": {"title": "Les plus écoutés sur Spotify · " + brand(),
                 "description": "Les artistes d’Afrique de l’Ouest les plus écoutés sur Spotify : auditeurs mensuels, hausses de la semaine et villes d’écoute."},
    })
