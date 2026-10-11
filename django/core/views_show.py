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


def _en_direct(start: datetime) -> bool:
    """Le direct s'affiche 15 min avant le début (avant-show) et jusqu'à 45 min après."""
    now = datetime.now(timezone.utc)
    return start - timedelta(minutes=15) <= now <= start + timedelta(minutes=45)


def _player(request, start_iso: str, rehearsal: bool, layout="layout", template="show-live"):
    vitesse = req_str(request, "vitesse")
    data = {"start_iso": start_iso, "rehearsal": rehearsal, "speed": vitesse if vitesse in ("1", "2", "4", "8") else "1",
            "jump": req_str(request, "a")[:6] if req_str(request, "a").isdigit() else "0", "show": conf.get("show"),
            "robots": "noindex" if rehearsal else None,
            "meta": {"title": ("Répétition · " if rehearsal else "En direct · ") + t("show.title") + " · " + brand()}}
    return render(request, template, data, layout=layout)


def show_page(request):
    use_locale(request)
    if not conf.get("show.public"):
        raise Http404()
    if request.method == "POST":
        return _subscribe(request)
    start = _start()
    if _en_direct(start):
        return _player(request, start.strftime("%Y-%m-%dT%H:%M:%SZ"), False)
    return render(request, "show", _context())


def show_rehearsal(request):
    """Répétition générale : le show démarre tout de suite (?vitesse=2|4|8 pour accélérer, ?a=600 pour sauter à 10 min)."""
    use_locale(request)
    return _player(request, "now", True)


def show_antenna(request):
    """L'antenne seule, plein cadre, sans le site autour : la page que filme OBS pour les réseaux."""
    use_locale(request)
    start = "now" if req_str(request, "repetition") else _start().strftime("%Y-%m-%dT%H:%M:%SZ")
    return _player(request, start, bool(req_str(request, "repetition")), layout=None, template="show-antenne")


def show_programme(request):
    """Le conducteur en JSON (mis en cache 10 min) : segments, durées, données, voix off."""
    from django.core.cache import cache
    from django.http import JsonResponse
    from core.services import show
    data = cache.get("show-programme")
    if data is None:
        data = show.programme()
        cache.set("show-programme", data, 600)
    from core.icons import ICONS
    return JsonResponse({**data, "icones": ICONS, "clips_locaux": _clips_locaux()}, json_dumps_params={"ensure_ascii": False})


def _clips_locaux() -> dict:
    """Clips dont la régie a le fichier vidéo (fourni par l'artiste ou le label) : {id YouTube: adresse}."""
    import os
    d = conf.get("show.clips_dir")
    if not d or not os.path.isdir(d):
        return {}
    return {os.path.splitext(f)[0]: path(f"show/clip/{os.path.splitext(f)[0]}.mp4") for f in os.listdir(d) if f.lower().endswith(".mp4")}


def show_clip(request, vid: str):
    """Sert un fichier de clip local avec les requêtes partielles (avance rapide). Seulement si SHOW_CLIPS_DIR est configuré (régie)."""
    import os
    import re
    from django.http import FileResponse, HttpResponse
    d = conf.get("show.clips_dir")
    f = os.path.join(d, vid + ".mp4") if d else ""
    if not d or not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid) or not os.path.isfile(f):
        raise Http404()
    taille = os.path.getsize(f)
    m = re.match(r"bytes=(\d*)-(\d*)", request.META.get("HTTP_RANGE", ""))
    if not m:
        r = FileResponse(open(f, "rb"), content_type="video/mp4")
        r["Accept-Ranges"] = "bytes"
        return r
    debut = int(m.group(1) or 0)
    fin = min(int(m.group(2)) if m.group(2) else taille - 1, taille - 1, debut + 8 * 1024 * 1024)
    with open(f, "rb") as fh:
        fh.seek(debut)
        corps = fh.read(fin - debut + 1)
    r = HttpResponse(corps, status=206, content_type="video/mp4")
    r["Content-Range"] = f"bytes {debut}-{fin}/{taille}"
    r["Accept-Ranges"] = "bytes"
    r["Content-Length"] = str(len(corps))
    return r


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


# ---------------------------------------------------------------- vote du public (cauricharts.com/show/vote)
def _compte(request):
    from core.services import show_vote as V
    return V.compte(request.session.get("show_account"))


def _turnstile_ok(request) -> bool:
    """Captcha invisible Cloudflare Turnstile, seulement si les clés sont configurées (TURNSTILE_SITE_KEY / TURNSTILE_SECRET)."""
    from core import env
    secret = env.get("TURNSTILE_SECRET", "")
    if not secret:
        return True
    import json as _json
    import urllib.parse
    import urllib.request
    data = urllib.parse.urlencode({"secret": secret, "response": req_str(request, "cf-turnstile-response")}).encode()
    try:
        with urllib.request.urlopen("https://challenges.cloudflare.com/turnstile/v0/siteverify", data, timeout=8) as r:
            return bool(_json.loads(r.read().decode()).get("success"))
    except Exception:  # noqa: BLE001
        return False


def show_vote(request):
    """Page de vote : inscription par lien e-mail, votes ouverts, codes secrets, lien de parrainage."""
    from core import env
    from core.services import show_vote as V
    use_locale(request)
    if not conf.get("show.public"):
        raise Http404()
    if req_str(request, "ref"):
        request.session["show_ref"] = req_str(request, "ref")[:12]
    cpt = _compte(request)
    old, errors = {}, {}
    if request.method == "POST" and not cpt:
        old = {"email": req_str(request, "email")[:190].lower(), "pseudo": req_str(request, "pseudo")[:40].strip(),
               "country": req_str(request, "country")[:2].upper(), "affichage": req_str(request, "affichage"), "age": req_str(request, "age")}
        if req_str(request, "website"):
            return redirect(path("show/vote"))
        if not EMAIL_RE.match(old["email"]):
            errors["email"] = t("form.invalid_email")
        elif V.email_jetable(old["email"]):
            errors["email"] = "Les adresses jetables ne sont pas acceptées."
        if len(old["pseudo"]) < 2:
            errors["pseudo"] = t("form.required")
        if not old["age"]:
            errors["age"] = "Il faut avoir au moins 13 ans pour voter."
        h = ip_hash(request)
        if int(db.value("SELECT COUNT(*) FROM show_login_tokens WHERE (ip_hash = ? OR email = ?) AND created_at > ?",
                        [h, old["email"], now_utc(-3600)]) or 0) >= 6:
            errors["email"] = t("form.rate_limited")
        if not errors and not _turnstile_ok(request):
            errors["email"] = "Vérification anti-robot échouée, réessayez."
        if not errors:
            token = V.demander_lien(old["email"], old["pseudo"], old["country"] if old["country"] else None,
                                    bool(old["affichage"]), request.session.get("show_ref"), h)
            from core import mail
            mail.send(old["email"], "Ton lien pour voter au Cauri Charts Monthly Show",
                      f"Bonjour {old['pseudo'][:40]},\n\nVoici ton lien personnel pour voter (valable 30 minutes) :\n"
                      f"{request.build_absolute_uri(path('show/connexion/' + token))}\n\nLe vote du public est gratuit, ne demande aucun achat et ne change aucun "
                      "classement officiel.\n\nSi tu n'es pas à l'origine de cette demande, ignore simplement cet e-mail.")
            flash(request, "success", f"C'est envoyé : ouvre le lien reçu sur {old['email']} pour voter (pense aux spams).")
            return redirect(path("show/vote"))
    key = conf.get("show.key")
    polls = V.votes_ouverts(key)
    for p in polls:
        p["ma_voix"] = V.ma_voix(p["id"], cpt["id"]) if cpt else None
        p["res"] = V.resultats(p) if p["ma_voix"] or p["status"] == "scelle" else None
    return render(request, "show-vote", {
        "cpt": cpt, "polls": polls, "old": old, "errors": errors,
        "country_options": {r["code"]: country_name(r["code"]) for r in repos.countries()},
        "lien_parrain": url("show/vote") + "?ref=" + cpt["ref"] if cpt else None,
        "filleuls": int(db.value("SELECT COUNT(*) FROM show_accounts WHERE referred_by = ? AND verified_at IS NOT NULL", [cpt["id"]]) or 0) if cpt else 0,
        "turnstile": env.get("TURNSTILE_SITE_KEY", ""), "robots": "noindex",
        "meta": {"title": "Vote du public · " + t("show.title") + " · " + brand()},
    }, 422 if errors else 200)


def show_login(request, token: str):
    from core.services import show_vote as V
    cpt = V.valider_lien(token, ip_hash(request))
    if not cpt:
        flash(request, "error", "Ce lien a expiré ou a déjà servi. Demandes-en un nouveau.")
        return redirect(path("show/vote"))
    request.session["show_account"] = int(cpt["id"])
    flash(request, "success", f"Bienvenue {cpt['pseudo']} ! Tu peux voter.")
    return redirect(path("show/vote"))


def show_vote_post(request, slug: str):
    from core.services import show_vote as V
    if request.method != "POST":
        return redirect(path("show/vote"))
    cpt = _compte(request)
    if not cpt:
        flash(request, "error", "Connecte-toi d'abord avec ton e-mail.")
        return redirect(path("show/vote"))
    r = V.voter(slug, req_str(request, "option")[:60], cpt, ip_hash(request))
    flash(request, "success" if r == "ok" else "error", {"ok": "Ta voix est enregistrée.", "deja": "Tu as déjà voté ici.",
                                                        "ferme": "Ce vote est fermé.", "invalide": "Choix invalide."}[r])
    return redirect(path("show/vote") + "#" + slug)


def show_code(request):
    from core.services import show_vote as V
    cpt = _compte(request)
    if request.method == "POST" and cpt:
        r = V.saisir_code(req_str(request, "code")[:12], cpt)
        flash(request, "success" if r == "ok" else "error", {"ok": "Code validé !", "deja": "Code déjà saisi.",
                                                            "invalide": "Code inconnu ou expiré."}[r])
    return redirect(path("show/vote") + "#codes")


def show_logout(request):
    if request.method == "POST":
        request.session.pop("show_account", None)
    return redirect(path("show/vote"))


def show_results(request):
    """Résultats des votes ouverts pour l'écran du show (pourcentages seulement, rien sous le seuil, rien quand c'est scellé)."""
    from django.http import JsonResponse
    from core.services import show_vote as V
    key = conf.get("show.key")
    code = db.value("SELECT code FROM show_codes WHERE show_key = ? AND status = 'actif' ORDER BY activated_at DESC LIMIT 1", [key])
    r = JsonResponse({"votes": [V.resultats(p) for p in V.votes_ouverts(key)], "code": code,
                      "votants": int(db.value("""SELECT COUNT(DISTINCT v.account_id) FROM show_votes v JOIN show_polls p ON p.id = v.poll_id
                                                 WHERE p.show_key = ? AND v.flagged = 0""", [key]) or 0)})
    r["Cache-Control"] = "no-store"
    return r
