"""Administration (traduction des contrôleurs Admin PHP).

Toutes les pages exigent une connexion ; certaines actions exigent le rôle admin. Aucune position de classement
n'est jamais écrite à la main : on valide ou exclut des titres signalés, puis le classement est recalculé.
"""
import io
import json
import re
import secrets
from datetime import date, datetime, timedelta

from django.http import Http404, HttpResponse, HttpResponseBadRequest

from core import clock
from core import audit, db, repos, storage
from core.backoffice import auth
from core.helpers import fmt_date, fmt_number, path, slugify
from core.i18n import t
from core.repos import now_utc, php_round
from core.services.chart_service import ChartService
from core.services.charts import Flags, Period, _d, formula_all, formula_effective_for, formula_next_version
from core.services.imports import chart_importer
from core.services.imports.service import ImportService
from core.views import redirect, render, req_str

PLATFORMS = ["youtube", "audiomack", "boomplay", "spotify", "apple_music", "deezer"]
CSV_SOURCES = ["audiomack", "boomplay", "apple_music"]


class Redirect(Exception):
    def __init__(self, to: str):
        self.to = to


class Forbidden(Exception):
    pass


# ---------------------------------------------------------------- outils

def require_user(request, role: str = "editor") -> dict:
    user = auth.current_user(request)
    if not user:
        raise Redirect(path("admin/connexion"))
    if role == "admin" and user["role"] != "admin":
        raise Forbidden()
    request.cauri_user = user
    return user


def admin_view(role: str = "editor"):
    """Décorateur : connexion obligatoire (le jeton CSRF des POST est vérifié par le middleware de Django)."""
    def deco(fn):
        def wrapper(request, *args, **kwargs):
            from core.views_errors import render_error
            try:
                require_user(request, role)
                return fn(request, *args, **kwargs)
            except Redirect as r:
                return redirect(r.to)
            except Forbidden:
                return render_error(request, 403)
        return wrapper
    return deco


def admin_render(request, template: str, data: dict | None = None, status: int = 200, user=...):
    data = dict(data or {})
    data.setdefault("user", getattr(request, "cauri_user", None) if user is ... else user)
    data.setdefault("title", t("admin.title"))
    resp = render(request, "admin/" + template, data, status, layout="admin/layout")
    resp["Cache-Control"] = "no-store"
    resp["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def back(request, to: str, kind: str = "success", message: str | None = None):
    if message is not None:
        request.session["_flash"] = request.session.get("_flash", []) + [{"type": kind, "message": message}]
    return redirect(to)


def uid(request) -> int:
    return int(request.cauri_user["id"])


def ip(request) -> str:
    return auth.client_ip(request)


def _valid_date(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _num(v: str):
    try:
        return float(v.replace(",", "."))
    except (AttributeError, ValueError):
        return None


# ---------------------------------------------------------------- connexion

def _guest(request, template: str, data: dict, status: int = 200):
    return admin_render(request, template, {**data, "flash": [], "title": t("admin.login")}, status, user=None)


def login(request):
    if request.method == "POST":
        result = auth.attempt(request, req_str(request, "email"), request.POST.get("password", ""))
        if result == "ok":
            return redirect(path("admin"))
        if result == "2fa":
            return redirect(path("admin/2fa"))
        if result == "locked":
            return _guest(request, "login", {"error": t("admin.login_locked")}, 429)
        return _guest(request, "login", {"error": t("admin.login_invalid"), "email": req_str(request, "email")}, 401)
    if auth.current_user(request):
        return redirect(path("admin"))
    return _guest(request, "login", {})


def two_factor(request):
    if request.method == "POST":
        result = auth.verify_second_factor(request, req_str(request, "code"))
        if result == "ok":
            return redirect(path("admin"))
        if result == "expired":
            return _guest(request, "login", {"error": t("admin.2fa_expired")}, 401)
        if result == "locked":
            return _guest(request, "login", {"error": t("admin.login_locked")}, 429)
        return _guest(request, "two-factor", {"error": t("admin.2fa_invalid")}, 401)
    if not (request.COOKIES.get("cauri_sid") and request.session.get("2fa_user")):
        return redirect(path("admin/connexion"))
    return _guest(request, "two-factor", {})


def logout(request):
    if request.method != "POST":
        return HttpResponseBadRequest()
    auth.logout(request)
    return redirect(path("admin/connexion"))


# ---------------------------------------------------------------- tableau de bord, journal, messages

@admin_view()
def dashboard(request):
    return admin_render(request, "dashboard", {
        "pending": db.all("""SELECT c.code, ws.week_start, COUNT(*) AS n FROM weekly_scores ws JOIN countries c ON c.id = ws.country_id
                             WHERE ws.review_status = 'pending' AND ws.score > 0 GROUP BY c.code, ws.week_start ORDER BY ws.week_start DESC"""),
        "drafts": db.all("""SELECT c.code, r.period_type, r.period_key, COUNT(*) AS runs, MIN(r.id) AS first_id
                            FROM chart_runs r JOIN countries c ON c.id = r.country_id WHERE r.status = 'draft'
                            GROUP BY c.code, r.period_type, r.period_key ORDER BY MAX(r.period_end) DESC, c.code LIMIT 20"""),
        "submissions": int(db.value("SELECT COUNT(*) FROM submissions WHERE status = 'pending'")),
        "messages": int(db.value("SELECT COUNT(*) FROM contact_messages WHERE status = 'new'")),
        "lastSnapshot": db.value("SELECT MAX(captured_on) FROM snapshots"),
        "quota": db.one("SELECT units_used FROM api_quota WHERE api = 'youtube' ORDER BY day DESC LIMIT 1"),
    })


@admin_view("admin")
def audit_log(request):
    try:
        page = max(1, int(req_str(request, "page", "1")))
    except ValueError:
        page = 1
    rows = db.all(f"""SELECT l.*, u.name AS user_name FROM audit_log l LEFT JOIN users u ON u.id = l.user_id
                      ORDER BY l.id DESC LIMIT 100 OFFSET {(page - 1) * 100}""")
    return admin_render(request, "audit", {"rows": rows, "page": page})


@admin_view()
def messages(request):
    return admin_render(request, "messages", {"rows": db.all("SELECT * FROM contact_messages ORDER BY status = 'new' DESC, id DESC LIMIT 200")})


@admin_view()
def message_status(request, mid: str):
    status = req_str(request, "status")
    if status in ("new", "answered", "closed"):
        db.update("contact_messages", {"status": status}, "id = :id", {"id": int(mid)})
        audit.log(uid(request), "message.status", "contact_message", int(mid), None, {"status": status}, ip(request))
    return back(request, path("admin/messages"))


# ---------------------------------------------------------------- classements

@admin_view()
def charts(request):
    rows = db.all("""SELECT c.code, r.period_type, r.period_key, r.period_start, r.period_end,
                        MIN(r.status) AS status, MAX(r.published_at) AS published_at, MAX(r.corrected_at) AS corrected_at,
                        MAX(CASE WHEN ct.code = 'prime' THEN r.id END) AS prime_id, MAX(r.is_provisional) AS provisional,
                        (SELECT COUNT(*) FROM weekly_scores ws WHERE ws.country_id = c.id AND ws.week_start = r.period_start
                            AND r.period_type = 'week' AND ws.review_status = 'pending' AND ws.score > 0) AS pending
                     FROM chart_runs r JOIN countries c ON c.id = r.country_id JOIN chart_types ct ON ct.id = r.chart_type_id
                     GROUP BY c.id, c.code, r.period_type, r.period_key, r.period_start, r.period_end
                     ORDER BY r.period_end DESC, array_position(ARRAY['week','month','year']::varchar[], r.period_type::varchar), c.code
                     LIMIT 150""")
    return admin_render(request, "charts", {"rows": rows, "countries": repos.countries()})


@admin_view()
def chart_run(request, rid: str):
    run = repos.run_by_id(int(rid), False)
    if not run:
        raise Http404
    siblings = db.all("""SELECT r.id, ct.code, ct.name, r.status FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
                         WHERE r.country_id IS NOT DISTINCT FROM ?::smallint AND r.period_type = ? AND r.period_key = ? ORDER BY ct.sort_order""",
                      [run["country_id"], run["period_type"], run["period_key"]])
    flagged = []
    if run["period_type"] == "week":
        flagged = db.all("""SELECT ws.*, t.title, t.slug, a.name AS artist_name, tr.decision, tr.reason, u.name AS decided_by
                            FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                            LEFT JOIN track_reviews tr ON tr.track_id = ws.track_id AND tr.week_start = ws.week_start
                            LEFT JOIN users u ON u.id = tr.user_id
                            WHERE ws.country_id IS NOT DISTINCT FROM ?::smallint AND ws.week_start = ? AND ws.flags <> '[]'
                            ORDER BY ws.review_status = 'pending' DESC, ws.score DESC""", [run["country_id"], run["period_start"]])
    pending = ChartService().pending_count(run["country_id"], run["period_start"]) if run["period_type"] == "week" and run["country_id"] else 0
    return admin_render(request, "chart-run", {"run": run, "entries": repos.entries(int(run["id"])), "siblings": siblings,
                                               "flagged": flagged, "blocking": Flags.BLOCKING, "pending": pending})


@admin_view("admin")
def decide(request):
    run_id = int(req_str(request, "run_id") or 0)
    try:
        ChartService().decide(int(req_str(request, "track_id") or 0), req_str(request, "week_start"), req_str(request, "decision"),
                              req_str(request, "reason"), uid(request), ip(request))
        return back(request, path(f"admin/classements/{run_id}"), "success", t("admin.decision_saved"))
    except Exception as exc:  # noqa: BLE001
        return back(request, path(f"admin/classements/{run_id}"), "error", str(exc))


@admin_view("admin")
def publish(request):
    run_id = int(req_str(request, "run_id") or 0)
    try:
        n = ChartService().publish(req_str(request, "country"), req_str(request, "period_type"), req_str(request, "period_key"), uid(request), ip(request))
        msg = t("admin.published", n=n)
        if req_str(request, "period_type") == "week":
            # Classement officiel publié : envoyé dans la chaîne Telegram (une seule fois)
            from core.services import telegram
            try:
                country = req_str(request, "country").lower()
                msg += " Telegram : " + telegram.send_chart("wa" if country in ("", "wa") else country)
            except Exception as exc:  # noqa: BLE001
                msg += f" Telegram : échec ({exc})"
            # Clips du podium (N°1, N°2, N°3) envoyés au studio pour validation
            from core.services.social import officiel
            try:
                njobs = len(officiel.clips_podium(req_str(request, "country"), req_str(request, "period_key")))
                if njobs:
                    msg += f" Studio : {njobs} clip(s) du podium en attente (relais PC)."
            except Exception as exc:  # noqa: BLE001
                msg += f" Studio clips : échec ({exc})"
        return back(request, path(f"admin/classements/{run_id}"), "success", msg)
    except Exception as exc:  # noqa: BLE001
        return back(request, path(f"admin/classements/{run_id}"), "error", str(exc))


@admin_view("admin")
def recompute(request):
    run_id = int(req_str(request, "run_id") or 0)
    correction = req_str(request, "correction") or None
    try:
        service = ChartService()
        period = Period.from_key(req_str(request, "period_type"), req_str(request, "period_key"))
        if period.type == "week":
            service.compute_week(req_str(request, "country"), period.start, correction, uid(request))
        else:
            # Mois et années ne contiennent que des semaines publiées : ils restent publiés
            service.compute_aggregate(req_str(request, "country"), period, correction if period.type == "month" else None, uid(request), True)
        audit.log(uid(request), "chart.recompute", "country_period", f"{req_str(request, 'country')}:{period.key}", correction, {}, ip(request))
        return back(request, path(f"admin/classements/{run_id}"), "success", t("admin.recomputed"))
    except Exception as exc:  # noqa: BLE001
        return back(request, path(f"admin/classements/{run_id}"), "error", str(exc))


def _php_numbers(v):
    """json_encode de PHP écrit 5.0 sous la forme 5 : même rendu pour les nombres entiers."""
    if isinstance(v, dict):
        return {k: _php_numbers(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_php_numbers(x) for x in v]
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _next_monday(min_date: date) -> date:
    d = min_date
    while d.isoweekday() != 1:
        d += timedelta(days=1)
    return d


@admin_view("admin")
def formula(request):
    if request.method == "POST":
        return _save_formula(request)
    min_date = clock.today() + timedelta(days=14)
    return admin_render(request, "formula", {"versions": formula_all(), "current": formula_effective_for(clock.today().isoformat()),
                                             "countries": repos.countries(False), "minDate": min_date.isoformat(),
                                             "nextMonday": _next_monday(min_date).isoformat()})


def _save_formula(request):
    """Nouvelle version : en vigueur au moins deux semaines plus tard (METHODOLOGIE.md, section 8), toujours un lundi."""
    f = formula_effective_for(clock.today().isoformat())
    effective = req_str(request, "effective_from")
    note = req_str(request, "note")
    errors = []
    d = _valid_date(effective)
    if not d or d < clock.today() + timedelta(days=14) or d.isoweekday() != 1:
        errors.append(t("admin.formula_date_rule"))
    if note == "":
        errors.append(t("admin.formula_note_required"))
    for k in ("audio", "youtube", "declaration"):
        v = _num(req_str(request, f"w_{k}"))
        if v is None or v < 0 or v > 10:
            errors.append(t("admin.formula_weight_invalid", name=k))
        else:
            f["weights"][k] = php_round(v, 3)
    country_weights = {}
    for c in repos.countries(False):
        for k in ("audio", "youtube"):
            raw = req_str(request, f"cw_{c['code']}_{k}")
            if raw != "":
                v = _num(raw)
                if v is None or v < 0 or v > 10:
                    errors.append(t("admin.formula_weight_invalid", name=f"{c['code']} {k}"))
                else:
                    country_weights.setdefault(c["code"], {})[k] = php_round(v, 3)
    f["country_weights"] = country_weights
    for k, (mn, mx) in {"spike_factor": (1, 50), "declaration_tolerance": (0, 1)}.items():
        v = _num(req_str(request, k))
        if v is None or v < mn or v > mx:
            errors.append(t("admin.formula_weight_invalid", name=k))
        else:
            f["anti_fraud"][k] = v
    if errors:
        return back(request, path("admin/formule"), "error", " ".join(errors))
    version = formula_next_version()
    f["version"] = version
    db.insert("formula_versions", {"version": version, "formula_json": json.dumps(_php_numbers(f), ensure_ascii=False), "effective_from": effective,
                                   "note": note[:500], "created_by": uid(request)})
    audit.log(uid(request), "formula.create", "formula_version", version, note, {"weights": f["weights"], "effective_from": effective}, ip(request))
    return back(request, path("admin/formule"), "success", t("admin.formula_saved", version=version, date=fmt_date(effective)))


# ---------------------------------------------------------------- déclarations et relevés

def _submission(sid: int) -> dict:
    s = db.one("""SELECT s.*, t.title AS track_title, u.name AS reviewer FROM submissions s LEFT JOIN tracks t ON t.id = s.track_id
                  LEFT JOIN users u ON u.id = s.reviewed_by WHERE s.id = ?""", [sid])
    if not s:
        raise Http404
    return s


@admin_view()
def submissions(request):
    status = req_str(request, "statut") if req_str(request, "statut") in ("pending", "validated", "rejected") else "pending"
    rows = db.all("""SELECT s.*, t.title AS track_title FROM submissions s LEFT JOIN tracks t ON t.id = s.track_id
                     WHERE s.status = ? ORDER BY s.created_at DESC LIMIT 200""", [status])
    return admin_render(request, "submissions", {"rows": rows, "status": status})


def _public_data(track_id: int, platform: str, start: str, end: str):
    row = db.one("""SELECT
        (SELECT SUM(x.plays) FROM (SELECT (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on <= ? ORDER BY captured_on DESC LIMIT 1) AS plays
           FROM track_platform_ids tpi WHERE tpi.track_id = ? AND tpi.platform = ?) x) AS end_plays,
        (SELECT SUM(y.plays) FROM (SELECT (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on < ? ORDER BY captured_on DESC LIMIT 1) AS plays
           FROM track_platform_ids tpi WHERE tpi.track_id = ? AND tpi.platform = ?) y) AS start_plays""",
                 [end, track_id, platform, start, track_id, platform])
    if row and row["end_plays"] is not None and row["start_plays"] is not None:
        return int(row["end_plays"]) - int(row["start_plays"])
    return None


@admin_view()
def submission(request, sid: str):
    s = _submission(int(sid))
    if request.method == "POST":
        return _review(request, s)
    return admin_render(request, "submission", {
        "s": s,
        "tracks": db.all("SELECT t.id, t.title, a.name AS artist_name FROM tracks t JOIN artists a ON a.id = t.artist_id ORDER BY a.name COLLATE cauri_ci, t.title COLLATE cauri_ci LIMIT 2000"),
        "public": _public_data(int(s["track_id"]), s["platform"], s["period_start"], s["period_end"]) if s["track_id"] else None,
    })


def _review(request, s: dict):
    decision = req_str(request, "decision")
    track_id = int(req_str(request, "track_id") or 0) or None
    note = req_str(request, "note")
    here = path(f"admin/declarations/{s['id']}")
    if decision not in ("validated", "rejected"):
        return back(request, here, "error", t("form.required"))
    if decision == "validated" and not track_id:
        return back(request, here, "error", t("admin.submission_track_required"))
    if decision == "rejected" and note == "":
        return back(request, here, "error", t("admin.reason_required"))
    artist_id = int(db.value("SELECT artist_id FROM tracks WHERE id = ?", [track_id])) if track_id else None
    db.update("submissions", {"status": decision, "track_id": track_id, "artist_id": artist_id, "reviewed_by": uid(request),
                              "reviewed_at": now_utc(), "review_note": note or None}, "id = :id", {"id": s["id"]})
    audit.log(uid(request), "submission." + decision, "submission", s["id"], note or None, {"track_id": track_id}, ip(request))
    message = t("admin.submission_saved")
    if decision == "validated":
        _update_top_country(artist_id, s)
        message += " " + _recompute_draft_weeks(request, track_id, s["period_start"], s["period_end"])
    return back(request, path("admin/declarations"), "success", message)


def _update_top_country(artist_id, s: dict) -> None:
    """Pays d'écoute principal déclaré : statistique de la fiche artiste, sans effet sur le classement."""
    try:
        breakdown = json.loads(s["country_breakdown"] or "null")
    except ValueError:
        breakdown = None
    if not artist_id or not breakdown:
        return
    code = max(breakdown, key=lambda k: breakdown[k])
    country_id = db.value("SELECT id FROM countries WHERE code = ?", [code])
    if country_id:
        db.update("artists", {"top_country_id": country_id, "top_country_share": breakdown[code], "top_country_updated_at": s["period_end"]},
                  "id = :id", {"id": artist_id})


def _recompute_draft_weeks(request, track_id: int, start: str, end: str) -> str:
    code = db.value("""SELECT c.code FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id
                       WHERE t.id = ?""", [track_id])
    service, done, published = ChartService(), [], []
    p = Period.week_of(start)
    while p.start <= end:
        status = db.value("""SELECT r.status FROM chart_runs r JOIN countries c ON c.id = r.country_id JOIN chart_types ct ON ct.id = r.chart_type_id
                             WHERE c.code = ? AND ct.code = 'prime' AND r.period_type = 'week' AND r.period_key = ?""", [code, p.key])
        if status == "draft":
            service.compute_week(code, p.start, None, uid(request))
            done.append(p.key)
        elif status == "published":
            published.append(p.key)
        p = Period.week_of((_d(p.start) + timedelta(days=7)).isoformat())
    msg = t("admin.weeks_recomputed", weeks=", ".join(done)) if done else ""
    if published:
        msg += " " + t("admin.weeks_published_untouched", weeks=", ".join(published))
    return msg.strip()


@admin_view()
def screenshot(request, sid: str):
    """Capture d'écran servie uniquement aux utilisateurs connectés."""
    s = _submission(int(sid))
    p = s["screenshot_path"] or ""
    if p.startswith("https://"):
        return redirect(p, 302)  # Vercel Blob : adresse longue et imprévisible
    f = storage.upload_path(p)
    if not f.is_file():
        raise Http404
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(f.suffix.lstrip(".").lower(), "application/octet-stream")
    resp = HttpResponse(f.read_bytes(), content_type=mime)
    resp["Cache-Control"] = "private, no-store"
    return resp


@admin_view()
def snapshots(request):
    if request.method == "POST":
        return _save_snapshot(request)
    return admin_render(request, "snapshots", {
        "platformIds": db.all("""SELECT tpi.id, tpi.platform, tpi.external_id, t.title, a.name AS artist_name, c.code,
                                    (SELECT captured_on || ' : ' || plays FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY captured_on DESC LIMIT 1) AS last
                                 FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id
                                 JOIN countries c ON c.id = a.submission_country_id
                                 WHERE tpi.platform <> 'spotify' ORDER BY c.sort_order, a.name COLLATE cauri_ci, t.title COLLATE cauri_ci, tpi.platform"""),
        "recent": db.all("""SELECT s.*, tpi.platform, t.title, u.name AS user_name FROM snapshots s
                            JOIN track_platform_ids tpi ON tpi.id = s.track_platform_id JOIN tracks t ON t.id = tpi.track_id
                            LEFT JOIN users u ON u.id = s.created_by WHERE s.source = 'manual' ORDER BY s.created_at DESC LIMIT 50"""),
        "today": clock.today().isoformat(),
    })


def _save_snapshot(request):
    """Relevé manuel (Audiomack, Boomplay... sans API) : compteur cumulé lu sur la plateforme."""
    tpi_id = int(req_str(request, "track_platform_id") or 0)
    day, plays = req_str(request, "captured_on"), req_str(request, "plays")
    d = _valid_date(day)
    if not tpi_id or not d or d > clock.today() or not plays.isdigit():
        return back(request, path("admin/releves"), "error", t("admin.snapshot_invalid"))
    previous = db.one("SELECT captured_on, plays FROM snapshots WHERE track_platform_id = ? AND captured_on < ? ORDER BY captured_on DESC LIMIT 1", [tpi_id, day])
    db.run("""INSERT INTO snapshots (track_platform_id, captured_on, plays, source, created_by) VALUES (?, ?, ?, 'manual', ?)
              ON CONFLICT (track_platform_id, captured_on) DO UPDATE SET plays = EXCLUDED.plays, source = 'manual', created_by = EXCLUDED.created_by""",
           [tpi_id, day, int(plays), uid(request)])
    audit.log(uid(request), "snapshot.manual", "track_platform", tpi_id, None, {"day": day, "plays": int(plays)}, ip(request))
    warning = " " + t("admin.snapshot_lower", previous=fmt_number(int(previous["plays"]))) if previous and int(plays) < int(previous["plays"]) else ""
    return back(request, path("admin/releves"), "error" if warning else "success", t("admin.snapshot_saved") + warning)


# ---------------------------------------------------------------- catalogue

@admin_view()
def catalog(request):
    q = req_str(request, "q")[:100]
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return admin_render(request, "catalog", {
        "q": q, "countries": repos.countries(False),
        "artists": db.all("""SELECT a.*, c.code, (SELECT COUNT(*) FROM tracks t WHERE t.artist_id = a.id) AS tracks
                             FROM artists a JOIN countries c ON c.id = a.submission_country_id WHERE a.name ILIKE ? ORDER BY c.sort_order, a.name COLLATE cauri_ci LIMIT 300""", [like]),
        "tracks": db.all("""SELECT t.*, a.name AS artist_name, (SELECT string_agg(platform::text, ',') FROM track_platform_ids p WHERE p.track_id = t.id) AS platforms
                            FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE t.title ILIKE ? OR a.name ILIKE ? ORDER BY t.created_at DESC, t.id DESC LIMIT 300""",
                         [like, like]),
    })


@admin_view("admin")
def save_country(request, cid: str):
    platforms = [p for p in PLATFORMS if p in request.POST.getlist("platforms[]")]
    try:
        size = int(req_str(request, "chart_size") or 0)
    except ValueError:
        size = 0
    if size < 5 or size > 100 or not platforms:
        return back(request, path("admin/catalogue"), "error", t("admin.country_invalid"))
    data = {"chart_size": size, "platforms": ",".join(platforms), "locale": "en" if req_str(request, "locale") == "en" else "fr",
            "is_active": 1 if request.POST.get("is_active") == "1" else 0}
    db.update("countries", data, "id = :id", {"id": int(cid)})
    audit.log(uid(request), "country.update", "country", int(cid), None, data, ip(request))
    return back(request, path("admin/catalogue"), "success", t("admin.saved"))


@admin_view()
def artist_form(request, aid: str):
    if request.method == "POST":
        return _save_artist(request, aid)
    artist = ({"id": None, "name": "", "submission_country_id": None, "label_owner": "", "is_emerging": 0, "bio": "", "image_url": ""}
              if aid == "nouveau" else db.one("SELECT * FROM artists WHERE id = ?", [int(aid)]))
    if not artist:
        raise Http404
    try:
        candidates = json.loads(artist.get("photo_candidates") or "[]") if artist.get("id") else []
    except ValueError:
        candidates = []
    return admin_render(request, "artist-form", {"artist": artist, "countries": repos.countries(False), "candidates": candidates})


@admin_view()
def artist_photo(request, aid: str):
    """Galerie de photos : chercher maintenant, choisir une candidate (verrouillée), ou rendre le choix à la machine."""
    from core.services.imports.photos import ArtistPhotos, best
    from core.services.platforms import HttpClient
    artist = db.one("SELECT id, name, image_url, youtube_channel_id, image_locked, photo_candidates FROM artists WHERE id = ?", [int(aid)])
    if not artist or request.method != "POST":
        return HttpResponseBadRequest()
    action, back_to = req_str(request, "action"), path(f"admin/artistes/{int(aid)}") + "#photos"
    if action == "chercher":
        cands = ArtistPhotos(HttpClient(30)).collect(artist)
        data = {"photo_candidates": json.dumps(cands, ensure_ascii=False), "photo_checked_at": now_utc()}
        pick = best([c for c in cands if c["source"] != "presse"])
        if pick and not artist["image_locked"]:
            data.update({"image_url": pick["site"], "image_hd_url": pick["url"], "image_source": pick["source"], "image_credit": pick.get("credit")})
        db.update("artists", data, "id = :id", {"id": artist["id"]})
        return back(request, back_to, "success", f"{len(cands)} photos trouvées.")
    if action == "choisir":
        try:
            cands = json.loads(artist["photo_candidates"] or "[]")
            c = cands[int(req_str(request, "index"))]
        except (ValueError, IndexError):
            return HttpResponseBadRequest()
        db.update("artists", {"image_url": c["site"], "image_hd_url": c["url"], "image_source": c["source"],
                              "image_credit": c.get("credit"), "image_locked": 1}, "id = :id", {"id": artist["id"]})
        audit.log(uid(request), "artist.photo", "artist", artist["id"], c["source"], {"url": c["url"]}, ip(request))
        return back(request, back_to, "success", "Photo choisie et verrouillée : la nuit ne la remplacera plus.")
    if action == "deverrouiller":
        db.update("artists", {"image_locked": 0, "photo_checked_at": None}, "id = :id", {"id": artist["id"]})
        return back(request, back_to, "success", "Photo déverrouillée : la meilleure photo sera choisie la nuit prochaine.")
    return HttpResponseBadRequest()


def _save_artist(request, aid: str):
    ident = None if aid == "nouveau" else int(aid)
    name = req_str(request, "name")[:150]
    country_id = int(req_str(request, "submission_country_id") or 0)
    image = req_str(request, "image_url")
    if name == "" or not db.value("SELECT id FROM countries WHERE id = ?", [country_id]) or (image and not image.startswith("https://")):
        return back(request, path("admin/artistes/" + (str(ident) if ident else "nouveau")), "error", t("admin.artist_invalid"))
    data = {"name": name, "submission_country_id": country_id,
            "label_owner": re.sub(r"[^a-z0-9_-]", "", req_str(request, "label_owner").lower()) or None,
            "is_emerging": 1 if request.POST.get("is_emerging") == "1" else 0,
            "bio": req_str(request, "bio")[:3000] or None, "image_url": image or None}
    if ident:
        old = db.one("SELECT submission_country_id, label_owner, image_url FROM artists WHERE id = ?", [ident]) or {}
        if image and image != old.get("image_url"):
            # Photo saisie à la main : elle devient la photo de l'artiste et la nuit ne la remplace plus
            data.update({"image_hd_url": image, "image_source": "admin", "image_locked": 1, "image_credit": None})
        old.pop("image_url", None)
        db.update("artists", data, "id = :id", {"id": ident})
        audit.log(uid(request), "artist.update", "artist", ident, None, {"before": old, "after": {k: data[k] for k in old if k in data}}, ip(request))
    else:
        data["slug"] = chart_importer.unique_slug("artists", slugify(name))
        ident = db.insert("artists", data)
        audit.log(uid(request), "artist.create", "artist", ident, None, {}, ip(request))
    return back(request, path("admin/catalogue"), "success", t("admin.saved"))


@admin_view()
def track_form(request, tid: str):
    if request.method == "POST":
        return _save_track(request, tid)
    track = ({"id": None, "title": "", "artist_id": int(req_str(request, "artist") or 0), "featuring": "", "release_date": "", "cover_url": "", "is_active": 1}
             if tid == "nouveau" else db.one("SELECT * FROM tracks WHERE id = ?", [int(tid)]))
    if not track:
        raise Http404
    return admin_render(request, "track-form", {
        "track": track,
        "artists": db.all("SELECT a.id, a.name, c.code FROM artists a JOIN countries c ON c.id = a.submission_country_id ORDER BY a.name COLLATE cauri_ci"),
        "platformIds": db.all("SELECT * FROM track_platform_ids WHERE track_id = ? ORDER BY platform", [track["id"]]) if track["id"] else [],
        "platforms": PLATFORMS,
    })


def _save_track(request, tid: str):
    ident = None if tid == "nouveau" else int(tid)
    here = path("admin/titres/" + (str(ident) if ident else "nouveau"))
    title = req_str(request, "title")[:200]
    artist_id = int(req_str(request, "artist_id") or 0)
    release, cover = req_str(request, "release_date"), req_str(request, "cover_url")
    artist = db.one("SELECT name FROM artists WHERE id = ?", [artist_id])
    if title == "" or not artist or (release and not _valid_date(release)) or (cover and not cover.startswith("https://")):
        return back(request, here, "error", t("admin.track_invalid"))
    data = {"title": title, "artist_id": artist_id, "featuring": req_str(request, "featuring")[:255] or None,
            "release_date": release or None, "cover_url": cover or None, "is_active": 1 if request.POST.get("is_active") == "1" else 0}
    from django.db import IntegrityError
    try:
        with db.atomic():
            if ident:
                db.update("tracks", data, "id = :id", {"id": ident})
            else:
                data["slug"] = chart_importer.unique_slug("tracks", slugify(artist["name"] + " " + title))
                ident = db.insert("tracks", data)
            # Identifiants plateformes : suppression cochée, puis ajout éventuel
            for pid in request.POST.getlist("delete_pid[]"):
                db.run("DELETE FROM track_platform_ids WHERE id = ? AND track_id = ?", [int(pid), ident])
            platform, external = req_str(request, "new_platform"), req_str(request, "new_external_id")
            if platform and external:
                url = req_str(request, "new_url")
                if platform not in PLATFORMS or (url and not url.startswith("https://")):
                    raise ValueError(t("admin.track_invalid"))
                pub = req_str(request, "new_published_at")
                db.insert("track_platform_ids", {"track_id": ident, "platform": platform, "external_id": external[:191],
                                                 "kind": re.sub(r"[^a-z_]", "", req_str(request, "new_kind")) or "main",
                                                 "url": url or None, "published_at": pub if _valid_date(pub) else None})
    except IntegrityError:
        return back(request, here, "error", t("admin.platform_duplicate"))
    except ValueError as exc:
        return back(request, here, "error", str(exc))
    audit.log(uid(request), "track.create" if tid == "nouveau" else "track.update", "track", ident, None, {}, ip(request))
    return back(request, path(f"admin/titres/{ident}"), "success", t("admin.saved"))


# ---------------------------------------------------------------- imports

@admin_view()
def imports(request):
    return admin_render(request, "import", {
        "coverage": db.all("""SELECT o.source, c.code, MAX(o.observed_on) AS last_day, COUNT(DISTINCT o.observed_on) AS days, COUNT(*) AS rows_count
                              FROM chart_observations o JOIN countries c ON c.id = o.country_id
                              WHERE o.observed_on >= CURRENT_DATE - 30 GROUP BY o.source, c.code, c.sort_order ORDER BY o.source, c.sort_order"""),
        "pending": db.all("""SELECT a.id, a.name, a.slug, a.guessed_country_id, gc.code AS guessed_code,
                                a.base_country, a.origin_source, a.origin_confidence, a.origin_note,
                                a.image_url, a.fans, a.youtube_subscribers, a.discovered_via,
                                (SELECT sc.id FROM countries sc WHERE sc.code = a.base_country) AS suggested_country_id,
                                (SELECT string_agg(DISTINCT c2.code || ' ' || o2.source, ', ')
                                   FROM chart_observations o2 JOIN tracks t2 ON t2.id = o2.track_id JOIN countries c2 ON c2.id = o2.country_id
                                  WHERE t2.artist_id = a.id) AS seen_in,
                                (SELECT MIN(o3.position) FROM chart_observations o3 JOIN tracks t3 ON t3.id = o3.track_id WHERE t3.artist_id = a.id) AS best_position,
                                (SELECT t4.title FROM tracks t4 WHERE t4.artist_id = a.id ORDER BY t4.id LIMIT 1) AS a_track,
                                (SELECT COUNT(*) FROM chart_observations o5 JOIN tracks t5 ON t5.id = o5.track_id WHERE t5.artist_id = a.id) AS obs
                             FROM artists a LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                             WHERE a.status = 'pending'
                             -- Artistes présents dans un classement ces 14 derniers jours d'abord (ceux qui comptent pour le Top), mieux placés en tête
                             ORDER BY EXISTS (SELECT 1 FROM chart_observations ro JOIN tracks rt ON rt.id = ro.track_id
                                                     WHERE rt.artist_id = a.id AND ro.observed_on >= CURRENT_DATE - 14) DESC,
                                      best_position NULLS LAST, a.base_country IS NULL, COALESCE(a.fans, 0) DESC, a.name COLLATE cauri_ci LIMIT 300"""),
        "autoClips": db.all("""SELECT p.id, p.external_id, p.url, t.title, a.name AS artist FROM track_platform_ids p
                               JOIN tracks t ON t.id = p.track_id JOIN artists a ON a.id = t.artist_id
                               WHERE p.platform = 'youtube' AND p.match_status = 'auto' AND a.status = 'active' ORDER BY p.id DESC LIMIT 100"""),
        "noClip": db.all("""SELECT t.id, t.title, a.name AS artist, c.code FROM tracks t JOIN artists a ON a.id = t.artist_id
                            JOIN countries c ON c.id = a.submission_country_id
                            WHERE a.status = 'active' AND t.is_active = 1
                              AND NOT EXISTS (SELECT 1 FROM track_platform_ids p WHERE p.track_id = t.id AND p.platform = 'youtube')
                            ORDER BY t.id DESC LIMIT 100"""),
        "countries": repos.countries(False), "sources": CSV_SOURCES, "today": clock.today().isoformat(),
    })


@admin_view()
def import_classify(request):
    """Vérification par l'IA des artistes « à vérifier » : un lot de 30 (délai d'une requête), avec le même garde-fou
    que la nuit — l'IA ne valide seule que si un indice collecté (chaîne YouTube, Wikidata, scène) confirme sa réponse."""
    from core.services import ai
    from core.services.imports.classifier import ArtistClassifier
    from core.services.platforms import HttpClient
    client = ai.make()
    if not client:
        return back(request, path("admin/import") + "#artistes", "error", "IA non configurée (GROQ_API_KEY).")
    try:
        s = ArtistClassifier(HttpClient(20), client).run(12, ai_budget=12)
    except Exception as exc:  # noqa: BLE001
        import sys
        import traceback
        traceback.print_exc(file=sys.stderr)
        return back(request, path("admin/import") + "#artistes", "error", f"Vérification interrompue : {exc}")
    audit.log(uid(request), "artist.ai_classify", None, None, None, s, ip(request))
    return back(request, path("admin/import") + "#artistes", "success",
                f"{s['checked']} artistes examinés : {s['active']} validés automatiquement, {s['out_of_scope']} hors zone, "
                f"{s['pending']} restent à vérifier (indices insuffisants). Recliquez pour le lot suivant.")


@admin_view("admin")
def import_run(request):
    service = ImportService()
    lines = service.import_all(None, None, uid(request))
    n = int(req_str(request, "youtube") or 0)
    if n > 0:
        lines.append("YouTube : " + json.dumps(service.match_youtube(min(n, 90)), ensure_ascii=False))
    return back(request, path("admin/import"), "success", " · ".join(lines))


@admin_view()
def import_artist(request, aid: str):
    """Confirme le pays de soumission d'un artiste découvert, ou le marque hors périmètre."""
    ident = int(aid)
    to = path("admin/import") + "#artistes"
    if req_str(request, "action") == "out":
        db.update("artists", {"status": "out_of_scope"}, "id = :id AND status = 'pending'", {"id": ident})
        audit.log(uid(request), "artist.out_of_scope", "artist", ident, None, {}, ip(request))
        return back(request, to, "success", t("admin.import_artist_out"))
    country_id = int(req_str(request, "country_id") or 0)
    if not db.value("SELECT id FROM countries WHERE id = ?", [country_id]):
        return back(request, to, "error", t("admin.import_country_required"))
    db.update("artists", {"status": "active", "submission_country_id": country_id}, "id = :id", {"id": ident})
    audit.log(uid(request), "artist.confirm_country", "artist", ident, None, {"country_id": country_id}, ip(request))
    return back(request, to, "success", t("admin.import_artist_confirmed"))


@admin_view()
def import_clip(request, pid: str):
    ident = int(pid)
    if req_str(request, "action") == "remove":
        track_id = db.value("SELECT track_id FROM track_platform_ids WHERE id = ?", [ident])
        db.run("DELETE FROM track_platform_ids WHERE id = ? AND match_status = 'auto'", [ident])
        # Pas de nouvelle recherche automatique avant 14 jours
        db.update("tracks", {"youtube_checked_at": now_utc()}, "id = :id", {"id": int(track_id or 0)})
        audit.log(uid(request), "clip.remove", "track_platform", ident, None, {}, ip(request))
    else:
        db.update("track_platform_ids", {"match_status": "confirmed"}, "id = :id", {"id": ident})
        audit.log(uid(request), "clip.confirm", "track_platform", ident, None, {}, ip(request))
    return back(request, path("admin/import") + "#clips", "success", t("admin.saved"))


def youtube_id(value: str):
    value = value.strip()
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", value)
    if m:
        return m.group(1)
    return value if re.fullmatch(r"[A-Za-z0-9_-]{11}", value) else None


@admin_view()
def import_manual_clip(request, tid: str):
    from django.db import IntegrityError
    to = path("admin/import") + "#sans-clip"
    vid = youtube_id(req_str(request, "video"))
    if not vid:
        return back(request, to, "error", t("admin.import_bad_video"))
    try:
        with db.atomic():
            db.insert("track_platform_ids", {"track_id": int(tid), "platform": "youtube", "external_id": vid, "kind": "clip",
                                             "url": "https://www.youtube.com/watch?v=" + vid, "match_status": "confirmed"})
    except IntegrityError:
        return back(request, to, "error", t("admin.platform_duplicate"))
    audit.log(uid(request), "clip.manual", "track", int(tid), None, {"video": vid}, ip(request))
    return back(request, to, "success", t("admin.saved"))


@admin_view()
def import_csv(request):
    to = path("admin/import") + "#csv"
    source = req_str(request, "source")
    country = db.value("SELECT code FROM countries WHERE id = ?", [int(req_str(request, "country_id") or 0)])
    d = _valid_date(req_str(request, "observed_on"))
    if source not in CSV_SOURCES or not country or not d or d > clock.today():
        return back(request, to, "error", t("admin.import_csv_invalid"))
    try:
        rows = chart_importer.parse_csv(req_str(request, "rows"))
        s = chart_importer.import_chart(country, source, {"observed_on": d.isoformat(), "rows": rows}, uid(request))
    except ValueError as exc:
        return back(request, to, "error", str(exc))
    return back(request, to, "success", t("admin.import_csv_done", rows=s["rows"], new=s["new_tracks"], artists=s["new_artists"]))


# ---------------------------------------------------------------- actualités

@admin_view()
def news_list(request):
    return admin_render(request, "news", {"rows": db.all("""SELECT n.*, c.code FROM news n LEFT JOIN countries c ON c.id = n.country_id
                                                            ORDER BY COALESCE(n.published_at, n.created_at) DESC LIMIT 200""")})


@admin_view()
def news_form(request, nid: str):
    if request.method == "POST":
        return _save_news(request, nid)
    item = ({"id": None, "title": "", "summary": "", "body": "", "category": "annonce", "country_id": None, "source_name": "", "source_url": "",
             "status": "draft", "published_at": now_utc()[:16]} if nid == "nouveau" else db.one("SELECT * FROM news WHERE id = ?", [int(nid)]))
    if not item:
        raise Http404
    return admin_render(request, "news-form", {"item": item, "countries": repos.countries(False), "categories": repos.NEWS_CATEGORIES})


def _save_news(request, nid: str):
    ident = None if nid == "nouveau" else int(nid)
    here = path("admin/actualites/" + (str(ident) if ident else "nouveau"))
    title, summary = req_str(request, "title")[:200], req_str(request, "summary")[:400]
    source_url = req_str(request, "source_url")
    published = req_str(request, "published_at").replace("T", " ")
    category = req_str(request, "category")
    pub_dt = None
    if published:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                pub_dt = datetime.strptime(published, fmt)
                break
            except ValueError:
                continue
    if title == "" or summary == "" or category not in repos.NEWS_CATEGORIES or (source_url and not re.match(r"^https?://", source_url)) \
            or (published and pub_dt is None):
        return back(request, here, "error", t("admin.news_invalid"))
    data = {"title": title, "summary": summary, "body": req_str(request, "body")[:20000] or None, "category": category,
            "country_id": int(req_str(request, "country_id") or 0) or None, "source_name": req_str(request, "source_name")[:120] or None,
            "source_url": source_url or None, "status": "published" if req_str(request, "status") == "published" else "draft",
            "published_at": pub_dt.strftime("%Y-%m-%d %H:%M:%S") if pub_dt else now_utc()}
    if ident:
        db.update("news", data, "id = :id", {"id": ident})
    else:
        base = slug = slugify(title)
        i = 2
        while db.value("SELECT id FROM news WHERE slug = ?", [slug]):
            slug, i = f"{base}-{i}", i + 1
        ident = db.insert("news", {**data, "slug": slug, "created_by": uid(request)})
    audit.log(uid(request), "news.save", "news", ident, None, {"status": data["status"]}, ip(request))
    return back(request, path("admin/actualites"), "success", t("admin.saved"))


# ---------------------------------------------------------------- partenaires

@admin_view()
def partners_list(request):
    return admin_render(request, "partners", {"rows": repos.partners_all()})


@admin_view()
def partner_form(request, pid: str):
    if request.method == "POST":
        return _save_partner(request, pid)
    item = ({"id": None, "name": "", "url": "", "tier": "officiel", "description": "", "logo_path": None, "sort_order": 0, "is_active": 1}
            if pid == "nouveau" else repos.partner(int(pid)))
    if not item:
        raise Http404
    return admin_render(request, "partner-form", {"item": item, "tiers": repos.PARTNER_TIERS})


def _store_logo(upload) -> str:
    """Logo PNG, JPEG ou WebP (jamais de SVG), réencodé en PNG et limité à 480 × 240 px."""
    from PIL import Image
    if upload.size > 3_000_000:
        raise ValueError(t("submit.error_too_big"))
    try:
        src = Image.open(upload)
        if src.format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError
        src.load()
    except Exception:  # noqa: BLE001
        raise ValueError(t("submit.error_format"))
    w, h = src.size
    scale = min(1, 480 / w, 240 / h)
    dst = src.convert("RGBA").resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    dst.save(buf, "PNG", compress_level=6)
    name = secrets.token_hex(12) + ".png"
    storage.store_media("partners", name, buf.getvalue(), "image/png")
    return name


def _save_partner(request, pid: str):
    ident = None if pid == "nouveau" else int(pid)
    here = path("admin/partenaires/" + (str(ident) if ident else "nouveau"))
    name, url, tier = req_str(request, "name")[:120], req_str(request, "url"), req_str(request, "tier")
    if name == "" or tier not in repos.PARTNER_TIERS or (url and not re.match(r'^https?://[^\s<>"]+$', url, re.I)):
        return back(request, here, "error", t("admin.partner_invalid"))
    try:
        order = int(req_str(request, "sort_order") or 0)
    except ValueError:
        order = 0
    data = {"name": name, "url": url or None, "tier": tier, "description": req_str(request, "description")[:240] or None,
            "sort_order": order, "is_active": 1 if req_str(request, "is_active") == "1" else 0}
    upload = request.FILES.get("logo")
    if upload:
        try:
            data["logo_path"] = _store_logo(upload)
        except ValueError as exc:
            return back(request, here, "error", str(exc))
    if ident:
        db.update("partners", data, "id = :id", {"id": ident})
    else:
        ident = db.insert("partners", data)
    audit.log(uid(request), "partner.save", "partner", ident, None, {"name": name, "active": data["is_active"]}, ip(request))
    return back(request, path("admin/partenaires"), "success", t("admin.partner_saved"))


@admin_view("admin")
def partner_delete(request, pid: str):
    p = repos.partner(int(pid))
    if p and p["logo_path"]:
        f = storage.MEDIA / "partners" / p["logo_path"].split("/")[-1]
        if f.is_file():
            f.unlink()
    db.run("DELETE FROM partners WHERE id = ?", [int(pid)])
    audit.log(uid(request), "partner.delete", "partner", int(pid), None, {}, ip(request))
    return back(request, path("admin/partenaires"), "success", t("admin.partner_deleted"))


# ---------------------------------------------------------------- posts réseaux sociaux

@admin_view()
def posts(request):
    from core import env
    from core.services.social import themes
    rows = db.all("SELECT * FROM social_posts ORDER BY slot_date DESC, id DESC LIMIT 45")
    for p in rows:
        try:
            slides = json.loads(p["carousel"] or "[]") or []
        except ValueError:
            slides = []
        p["slides"] = [s if isinstance(s, dict) else {"file": s, "label": ""} for s in slides]
    return admin_render(request, "posts", {"posts": rows, "themes": themes.labels(), "exportDir": env.get("SOCIAL_EXPORT_DIR", "")})


@admin_view()
def posts_generate(request):
    from core.services import ai
    from core.services.social.generator import PostGenerator
    from core.services.social.themes import THEMES
    theme = req_str(request, "theme")
    if theme != "rotation" and theme not in THEMES:
        return HttpResponseBadRequest()
    # Une rubrique à la fois : la génération (visuels 4K, texte IA) doit tenir dans le délai d'une requête
    generator = PostGenerator(ai.make())
    try:
        post = generator.generate_next() if theme == "rotation" else generator.generate(theme)
    except Exception as exc:  # noqa: BLE001 — l'erreur exacte s'affiche dans l'admin plutôt qu'une page 500
        import sys
        import traceback
        traceback.print_exc(file=sys.stderr)  # journaux Vercel (disque en lecture seule : pas de fichier)
        return back(request, path("admin/posts"), "error", f"Génération impossible : {type(exc).__name__} : {exc}")
    done = [post["title"]] if post else []
    audit.log(uid(request), "social.generate", "social_post", None, post["theme"] if post else theme, {"titles": done}, ip(request))
    return back(request, path("admin/posts"), "success" if done else "error",
                t("admin.posts_generated", n=len(done)) if done else t("admin.posts_no_data"))


@admin_view()
def posts_request(request):
    """Post « sur demande » : l'IA traduit la phrase en réglages, les chiffres viennent de la base (custom.py)."""
    import secrets
    from core.services import ai
    from core.services.social import custom
    from core.services.social.generator import PostGenerator
    text = req_str(request, "demande").strip()[:500]
    if len(text) < 8:
        return back(request, path("admin/posts"), "error", "Décrivez le post voulu, par exemple « les 20 titres les plus écoutés de l’année au Ghana ».")
    client = ai.make()
    if not client:
        return back(request, path("admin/posts"), "error", "IA non configurée : ajoutez GROQ_API_KEY (et AI_PROVIDER=groq) dans les variables de Vercel.")
    try:
        params = custom.interpret(client, text)
        facts = custom.facts(params)
        if not facts:
            return back(request, path("admin/posts"), "error", "Pas de données réelles pour cette demande. " + params["explanation"])
        post = PostGenerator(client).generate("demande-" + secrets.token_hex(3), facts=facts)
    except Exception as exc:  # noqa: BLE001
        import sys
        import traceback
        traceback.print_exc(file=sys.stderr)
        return back(request, path("admin/posts"), "error", f"Génération impossible : {type(exc).__name__} : {exc}")
    audit.log(uid(request), "social.request", "social_post", post["id"], text, {"params": {k: v for k, v in params.items() if k != "request"}}, ip(request))
    warn = (" Impossible avec nos données, donc non pris en compte : " + ", ".join(params["unsupported"]) + ".") if params["unsupported"] else ""
    return back(request, path("admin/posts") + f"#post-{int(post['id'])}", "error" if warn else "success",
                f"Post créé : « {post['title']} ». {params['explanation']}{warn}")


@admin_view()
def post_zip(request, pid: str):
    """Dossier complet d'un post en ZIP. Sur Vercel (réponse limitée à 4,5 Mo), l'archive passe par le Blob."""
    import os
    import secrets
    from urllib.parse import quote
    from django.http import FileResponse
    from core import storage
    from core.services.social.export import zip_post
    post = db.one("SELECT * FROM social_posts WHERE id = ?", [int(pid)])
    if not post:
        return HttpResponseBadRequest()
    name, file = zip_post(post)
    if storage.blob_token():
        with open(file, "rb") as fh:
            link = storage.blob_put(f"media/zips/{int(pid)}-{secrets.token_hex(6)}/{quote(name)}", fh.read(), "application/zip")
        os.unlink(file)
        return redirect(link)
    return FileResponse(open(file, "rb"), as_attachment=True, filename=name, content_type="application/zip")


@admin_view()
def post_telegram(request, pid: str):
    from core.services import telegram
    post = db.one("SELECT * FROM social_posts WHERE id = ?", [int(pid)])
    if not post:
        return HttpResponseBadRequest()
    try:
        result, kind = telegram.send_post(post, force=req_str(request, "force") == "1"), "success"
    except Exception as exc:  # noqa: BLE001
        result, kind = f"échec ({exc})", "error"
    return back(request, path("admin/posts") + f"#post-{int(pid)}", kind, "Telegram : " + result)


@admin_view()
def post_buffer(request, pid: str):
    """Programme le post sur Instagram, Facebook et TikTok par Buffer : ce soir 18 h, ou demain si l'heure est passée."""
    from datetime import timezone
    from core.services import buffer
    post = db.one("SELECT * FROM social_posts WHERE id = ?", [int(pid)])
    if not post:
        return HttpResponseBadRequest()
    due = buffer.evening(clock.today())
    if due <= datetime.now(timezone.utc) + timedelta(minutes=15):
        due += timedelta(days=1)
    try:
        result, kind = buffer.schedule(post, due, force=req_str(request, "force") == "1"), "success"
        db.update("social_posts", {"status": "approved"}, "id = :id AND status = 'draft'", {"id": int(pid)})
        audit.log(uid(request), "social.buffer", "social_post", int(pid), result[:190], {}, ip(request))
    except Exception as exc:  # noqa: BLE001
        result, kind = f"échec ({exc})", "error"
    return back(request, path("admin/posts") + f"#post-{int(pid)}", kind, f"Buffer ({due:%d/%m %H:%M} UTC) : " + result)


@admin_view()
def post_status(request, pid: str):
    status = req_str(request, "status")
    if status not in ("draft", "approved", "published", "rejected") or not db.value("SELECT 1 FROM social_posts WHERE id = ?", [int(pid)]):
        return HttpResponseBadRequest()
    db.update("social_posts", {"status": status}, "id = :id", {"id": int(pid)})
    audit.log(uid(request), "social.status", "social_post", int(pid), status, {}, ip(request))
    return back(request, path("admin/posts") + f"#post-{int(pid)}", "success", t("admin.saved"))
