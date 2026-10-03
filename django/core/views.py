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
from core.helpers import PERIOD_SLUGS, brand, chart_path, country_name, period_label, url
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
            "logo": url("assets/img/brand/logo-share.png"), "areaServed": [c["code"] for c in repos.countries()]}


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
            "image": url("assets/img/og-default.png"), "type": "website", "jsonld": []}
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
        "periodType": period_type, "highlights": highlights, "aside": aside(country), "numberOnes": repos.number_ones(),
        "hotArtists": repos.hot_artists(None if regional else int(country["id"])),
        "homeNews": repos.news_latest(3, None if regional else int(country["id"])),
        "partners": repos.partners_active(),
        "meta": {
            "title": brand() + " · " + t("home.meta_title", country=country_name(country["code"]), size=country["chart_size"]),
            "description": t("home.meta_description_region" if regional else "home.meta_description", country=country_name(country["code"])),
            "image": share_url(int(run["id"]), "square") if run else None,
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
        "meta": {
            "title": title + (" · " + period_label(run) if run else "") + " · " + brand(),
            "description": t(f"chart.description.{chart_code}", country=country_name(country["code"])),
            "image": share_url(int(run["id"]), "square") if run else None,
        },
    })


# ---------------------------------------------------------------- catalogue

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
        "live": repos.artist_live(int(a["id"])), "iconRank": icon_rank, "artist": a, "tracks": tracks,
        "bestPeak": min(x["peak"] for x in charted) if charted else None,
        "totalWeeks": sum(int(x["weeks"] or 0) for x in tracks),
        "iconHistory": repos.artist_icon_history(int(a["id"])),
        "meta": {"title": a["name"] + " · " + brand(),
                 "description": t("artist.meta_description", name=a["name"], country=country_name(a["country_code"])), "type": "profile",
                 "image": a["image_url"] if str(a.get("image_url") or "").startswith("https://") else None,
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
    return render(request, "track", {
        "spotify": spotify, "track": tr, "positions": positions, "links": repos.track_links(int(tr["id"])),
        "peak": min(p["position"] for p in positions) if positions else None,
        "meta": {"title": tr["title"] + " · " + tr["artist_name"] + " · " + brand(),
                 "description": t("track.meta_description", title=tr["title"], artist=tr["artist_name"]), "type": "music.song",
                 "image": tr["cover_url"] if str(tr.get("cover_url") or "").startswith("https://") else None,
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
        raise Http404
    image = url("media/news/" + item["image_path"]) if item.get("image_path") else None
    slides = edition_slides(item)
    if slides:
        image = slides[0]  # la une du numéro en image de partage
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
    from core.helpers import e
    urls = [url("/"), url("methodologie"), url("a-propos"), url("contact"), url("declarer")]
    for c in repos.countries():
        for code, ch in conf.get("charts").items():
            if ch["public"] and not ch.get("regional"):
                for p in ch["periods"]:
                    urls.append(url(chart_path(c["code"], code, p)))
    urls += [url(p) for p in ("actualites", "partenaires", "integrer", "mentions-legales", "confidentialite", "cookies")]
    data = repos.sitemap_entries()
    dated = {url("artiste/" + a["slug"]): a["updated_at"] for a in data["artists"]}
    dated.update({url("actualites/" + n["slug"]): n["published_at"] for n in data["news"]})
    urls += list(dated) + [url("titre/" + x["slug"]) for x in data["tracks"]]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in dict.fromkeys(urls):
        last = f"<lastmod>{str(dated[u])[:10]}</lastmod>" if dated.get(u) else ""
        xml += f"  <url><loc>{e(u)}</loc>{last}</url>\n"
    return HttpResponse(xml + "</urlset>", content_type="application/xml; charset=utf-8")


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
