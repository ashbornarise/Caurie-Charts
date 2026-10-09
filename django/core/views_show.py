"""Monthly Show : la remise des prix Cauri Charts en direct (page publique /show, rappel par e-mail, fichier agenda).

La date, le mois révélé et la vidéo de présentation se règlent dans conf « show » (variables SHOW_*).
Les inscriptions (show_leads) servent uniquement à envoyer le rappel du direct ; purge selon la politique de confidentialité.
"""
from datetime import datetime, timedelta, timezone

from django.http import Http404, HttpResponse

from core import conf, db, repos
from core.helpers import brand, country_name, path, url
from core.i18n import locale, t
from core.services import live_chart
from core.services.distinctions import month_label
from core.views import EMAIL_RE, flash, ip_hash, now_utc, redirect, render, req_str, use_locale


def _mois(key: str) -> str:
    """« d'octobre 2026 » / « de novembre 2026 » en français, « October 2026 » en anglais."""
    if locale() == "en":
        y, m = key.split("-")[:2]
        return datetime(int(y), int(m), 1).strftime("%B %Y")
    label = month_label(key).lower()
    return ("d'" if label[0] in "aeiouéèh" else "de ") + label


def _start() -> datetime:
    return datetime.fromisoformat(conf.get("show.start_utc").replace("Z", "+00:00"))


def _context(old=None, errors=None) -> dict:
    start = _start()
    c = conf.get("show")
    return {
        "show": c, "start_iso": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "start": start,
        "month": _mois(c["key"]), "when": _date_label(start)[:1].upper() + _date_label(start)[1:], "contenders": _contenders(),
        "count": int(db.value("SELECT COUNT(*) FROM show_leads WHERE show_key = ?", [c["key"]]) or 0),
        "country_options": {r["code"]: country_name(r["code"]) for r in repos.countries()},
        "old": old or {}, "errors": errors or {},
        "meta": {"title": f"{t('show.title')} · {brand()}", "description": t("show.meta_description", month=_mois(c["key"]), date=_date_label(start)),
                 "image": c.get("trailer_poster") or None},
    }


def _contenders() -> list:
    """Les prétendants au BIG 5 : le Top 5 Afrique de l'Ouest en direct (mis en cache une heure)."""
    from django.core.cache import cache
    rows = cache.get("show-contenders")
    if rows is None:
        rows = [r for r in live_chart.build(None, None, 20, "prime", 10, "latest")["rows"]
                if not r.get("is_artist") and r.get("status") == "active"][:5]
        cache.set("show-contenders", rows, 3600)
    return rows


def show_page(request):
    use_locale(request)
    if not conf.get("show.public"):
        raise Http404()
    if request.method == "POST":
        return _subscribe(request)
    return render(request, "show", _context())


def _subscribe(request):
    key = conf.get("show.key")
    old = {"name": req_str(request, "name")[:100], "email": req_str(request, "email")[:190].lower(),
           "country": req_str(request, "country")[:2].upper(), "prediction": req_str(request, "prediction")[:200], "consent": req_str(request, "consent")}
    if req_str(request, "website"):
        return redirect(path("show"))  # pot de miel : robot
    errors = {}
    if not old["name"]:
        errors["name"] = t("form.required")
    if not EMAIL_RE.match(old["email"]):
        errors["email"] = t("form.invalid_email")
    if not old["consent"]:
        errors["consent"] = t("form.required")
    h = ip_hash(request)
    if int(db.value("SELECT COUNT(*) FROM show_leads WHERE ip_hash = ? AND created_at > ?", [h, now_utc(-86400)]) or 0) >= 5:
        errors["email"] = t("form.rate_limited")
    if errors:
        return render(request, "show", _context(old, errors), 422)
    codes = {c["code"] for c in repos.countries()}
    if not db.one("SELECT 1 FROM show_leads WHERE show_key = ? AND email = ?", [key, old["email"]]):
        db.insert("show_leads", {"show_key": key, "name": old["name"], "email": old["email"],
                                 "country_code": old["country"] if old["country"] in codes else None,
                                 "prediction": old["prediction"] or None, "locale": locale(), "ip_hash": h})
        from core import mail
        start = _start()
        mail.send(old["email"], t("show.mail_subject"),
                  t("show.mail_body", name=old["name"][:60], month=_mois(key), date=_date_label(start),
                    link=url("show"), ics=url("show/agenda.ics")))
    flash(request, "success", t("show.subscribed"))
    return redirect(path("show") + "#rappel")


def _date_label(start: datetime) -> str:
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    if locale() == "en":
        return f"{start.strftime('%A')} {start.day} {start.strftime('%B')} {start.year}, {start.hour % 12 or 12} {'pm' if start.hour >= 12 else 'am'} GMT"
    return f"{jours[start.weekday()]} {start.day} {mois[start.month - 1]} {start.year}, {start.hour} h GMT"


def show_ics(request):
    """Le direct dans l'agenda du téléphone (Google Agenda, Apple Calendrier, Outlook)."""
    if not conf.get("show.public"):
        raise Http404()
    start = _start()
    end = start + timedelta(minutes=int(conf.get("show.duration_minutes")))
    fmt = "%Y%m%dT%H%M%SZ"
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Cauri Charts//Monthly Show//FR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "BEGIN:VEVENT", f"UID:monthly-show-{conf.get('show.key')}@cauricharts.com",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}", f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:Cauri Charts Monthly Show · {month_label(conf.get('show.key'))}",
        f"DESCRIPTION:{t('show.ics_description')} {url('show')}", f"URL:{url('show')}",
        "BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY", "DESCRIPTION:Cauri Charts Monthly Show", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])
    r = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    r["Content-Disposition"] = 'attachment; filename="cauri-charts-monthly-show.ics"'
    return r
