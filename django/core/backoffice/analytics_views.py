"""Admin > Analyses : vues du site, résultats des publications, santé des nuits, exports pour l'analyse."""
import csv
import io
import json

from django.http import HttpResponse

from core import db
from core.backoffice.views import admin_render, admin_view
from core.services import analytics as A

LAYOUTS = {"bandeau": "Bandeau", "degrade": "Dégradé"}


@admin_view()
def analyses(request):
    posts = A.latest_post_metrics()
    days = db.all("""SELECT day, SUM(views) AS views FROM page_views WHERE day >= CURRENT_DATE - 29 GROUP BY day ORDER BY day""")
    peak = max([int(d["views"]) for d in days] or [1])
    return admin_render(request, "analyses", {
        "title": "Analyses",
        "days": days, "peak": peak,
        "total_30": sum(int(d["views"]) for d in days),
        "pages": db.all("""SELECT path, SUM(views) AS views FROM page_views WHERE day >= CURRENT_DATE - 29
                           GROUP BY path ORDER BY views DESC LIMIT 15"""),
        "artists": db.all("""SELECT a.name, a.slug, SUM(v.views) AS views FROM page_views v
                             JOIN artists a ON v.path = '/artiste/' || a.slug WHERE v.day >= CURRENT_DATE - 29
                             GROUP BY a.name, a.slug ORDER BY views DESC LIMIT 10"""),
        "referrers": db.all("""SELECT CASE WHEN referrer = '' THEN 'accès direct' ELSE referrer END AS referrer, SUM(views) AS views
                               FROM page_views WHERE day >= CURRENT_DATE - 29 GROUP BY 1 ORDER BY views DESC LIMIT 10"""),
        "posts": posts[:40],
        "by_theme": A.by(posts, "theme"), "by_layout": A.by(posts, "layout"), "by_channel": A.by(posts, "channel"),
        "by_type": A.by(posts, "post_type"), "by_hour": A.by(posts, "hour"),
        "runs": [dict(r, steps=json.loads(r["steps"])) for r in db.all("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 14")],
        "layouts": LAYOUTS,
    })


@admin_view()
def analyses_export(request, what: str):
    """Exports CSV (séparateur « ; », UTF-8 avec BOM pour Excel) : publications et leurs résultats, ou vues du site."""
    out = io.StringIO()
    out.write("﻿")
    w = csv.writer(out, delimiter=";")
    if what == "publications":
        cols = ["sent_at", "channel", "post_type", "theme", "layout", "hour", "title", "views", "reach", "reactions", "comments",
                "shares", "saves", "follows", "watch_avg", "slot_date", "buffer_post_id", "text_start"]
        w.writerow(cols)
        for r in A.latest_post_metrics():
            w.writerow([r.get(c) if r.get(c) is not None else "" for c in cols])
    elif what == "vues":
        w.writerow(["jour", "page", "origine", "vues"])
        for r in db.all("SELECT day, path, referrer, views FROM page_views ORDER BY day, path"):
            w.writerow([r["day"], r["path"], r["referrer"], r["views"]])
    elif what == "historique":
        w.writerow(["jour_releve", "buffer_post_id", "reseau", "type", "statistiques_json"])
        for r in db.all("SELECT captured_on, buffer_post_id, channel, post_type, metrics FROM post_metrics ORDER BY captured_on, buffer_post_id"):
            w.writerow([r["captured_on"], r["buffer_post_id"], r["channel"], r["post_type"] or "", r["metrics"]])
    else:
        return HttpResponse(status=404)
    resp = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="cauri-charts-{what}.csv"'
    return resp


def _event_image(upload) -> str:
    """Image envoyée depuis l'ordinateur : JPEG, PNG ou WebP, réencodée en JPEG (1200 px max), rangée sur le Blob."""
    import io
    import secrets
    from PIL import Image, ImageOps
    from core import storage
    from core.helpers import url
    if upload.size > 8_000_000:
        raise ValueError("Image trop lourde (8 Mo maximum).")
    try:
        src = Image.open(upload)
        if src.format not in ("PNG", "JPEG", "WEBP", "MPO"):
            raise ValueError
        src = ImageOps.exif_transpose(src).convert("RGB")
    except Exception:  # noqa: BLE001
        raise ValueError("Format d'image non reconnu (JPEG, PNG ou WebP).")
    src.thumbnail((1200, 1200), Image.LANCZOS)
    out = io.BytesIO()
    src.save(out, "JPEG", quality=86, optimize=True, progressive=True)
    name = f"{secrets.token_hex(8)}.jpg"
    storage.store_media("actu", name, out.getvalue(), "image/jpeg")
    return url("media/actu/" + name)


@admin_view()
def artist_news(request, eid: str | None = None):
    """Créer (sans eid) ou modifier (avec eid) une actualité ; masquer, republier ou supprimer."""
    from datetime import date
    from django.core.cache import cache
    from core import audit
    from core.backoffice.views import back, ip, uid
    from core.helpers import path
    from core.services import artist_news as N
    from core.services.imports import normalizer as Nm
    from core.views import req_str
    here = path("admin/actu-artistes" + (f"/{int(eid)}" if eid else ""))
    ev = db.one("SELECT e.*, a.name AS artist_name FROM artist_events e JOIN artists a ON a.id = e.artist_id WHERE e.id = ?", [int(eid)]) if eid else None
    if eid and not ev:
        return back(request, path("admin/actu-artistes"), "error", "Actualité introuvable.")
    if request.method == "POST":
        action = req_str(request, "action")
        if ev and action in ("published", "hidden"):
            db.update("artist_events", {"status": action}, "id = :id", {"id": ev["id"]})
            cache.clear()
            return back(request, path("admin/actu-artistes"), "success", "Actualité " + ("republiée." if action == "published" else "masquée."))
        if ev and action == "delete":
            if req_str(request, "confirm") != "1":
                return back(request, here, "error", "Cochez « Je confirme » pour supprimer.")
            db.run("DELETE FROM artist_events WHERE id = ?", [ev["id"]])
            audit.log(uid(request), "artist_event.delete", "artist_event", ev["id"], None, {"title": ev["title"]}, ip(request))
            cache.clear()
            return back(request, path("admin/actu-artistes"), "success", "Actualité supprimée.")
        a = db.one("SELECT id, name FROM artists WHERE match_key = ? ORDER BY status = 'active' DESC LIMIT 1", [Nm.artist_key(req_str(request, "artist"))])
        src, img = req_str(request, "source_url"), req_str(request, "image_url")
        try:
            day = date.fromisoformat(req_str(request, "event_date"))
        except ValueError:
            day = None
        # Les actus automatiques (YouTube, Deezer) gardent leur source ; la rédaction doit en donner une
        if ev and img == (ev["image_url"] or ""):
            img = ev["image_url"] or ""  # image déjà enregistrée : conservée telle quelle
            keep = True
        else:
            keep = False
        if not src and ev and ev["origin"] != "redaction":
            src = ev["source_url"] or ""
        if not a or not day or not req_str(request, "title") or not src.startswith("https://") or (img and not keep and not img.startswith("https://")):
            return back(request, here, "error", "Artiste introuvable, date, titre ou lien de source (https) manquant.")
        data = {"artist_id": a["id"], "kind": req_str(request, "kind") if req_str(request, "kind") in N.KINDS else "autre",
                "title": req_str(request, "title")[:200], "event_date": day.isoformat(),
                "summary": req_str(request, "summary")[:500] or None, "image_url": img or None,
                "source_name": req_str(request, "source_name")[:100] or None, "source_url": src[:500]}
        upload = request.FILES.get("image_file")
        if upload:
            try:
                data["image_url"] = _event_image(upload)
            except ValueError as exc:
                return back(request, here, "error", str(exc))
        elif req_str(request, "remove_image") == "1":
            data["image_url"] = None
        if ev:
            db.update("artist_events", data, "id = :id", {"id": ev["id"]})
            audit.log(uid(request), "artist_event.update", "artist_event", ev["id"], None, {"artist": a["name"]}, ip(request))
            msg = f"Actualité de {a['name']} modifiée."
        else:
            new = db.insert("artist_events", {**data, "origin": "redaction"})
            audit.log(uid(request), "artist_event.create", "artist_event", new, None, {"artist": a["name"]}, ip(request))
            msg = f"Actualité publiée pour {a['name']}."
        cache.clear()
        return back(request, path("admin/actu-artistes"), "success", msg)
    rows = db.all("""SELECT e.*, a.name AS artist_name FROM artist_events e JOIN artists a ON a.id = e.artist_id
                     ORDER BY e.origin = 'redaction' DESC, e.event_date DESC LIMIT 120""")
    artists = db.all("SELECT name FROM artists WHERE status = 'active' ORDER BY name LIMIT 2000")
    return admin_render(request, "artist-news", {"title": "Actu des artistes", "rows": rows, "artists": artists, "kinds": N.KINDS, "ev": ev})


@admin_view()
def distinctions(request, did: str | None = None, kind: str | None = None):
    """Distinctions officielles : cartes à envoyer, fichiers d'impression, suivi des envois."""
    from core.backoffice.views import back
    from core.helpers import path, url
    from urllib.parse import quote
    from core.services import distinctions as D
    from core.views import req_str
    if did:
        d = db.one("SELECT * FROM award_distinctions WHERE id = ?", [int(did)])
        if not d:
            return back(request, path("admin/distinctions"), "error", "Distinction introuvable.")
        if request.method == "POST" and req_str(request, "action") == "contact":
            email, insta = req_str(request, "contact_email").strip(), req_str(request, "instagram").strip().lstrip("@")
            if email and ("@" not in email or len(email) > 190):
                return back(request, path("admin/distinctions"), "error", "Adresse e-mail invalide.")
            db.run("UPDATE artists SET contact_email = ?, instagram = ? WHERE id = ?", [email or None, insta[:60] or None, d["artist_id"]])
            if email and req_str(request, "send") == "1":
                ok = D.deliver(d)
                return back(request, path("admin/distinctions"), "success" if ok else "error",
                            f"Distinction envoyée à {email}." if ok else "Contact enregistré, mais l'e-mail n'est pas parti (SMTP).")
            return back(request, path("admin/distinctions"), "success", f"Contact de {d['artist_name']} enregistré.")
        if request.method == "POST" and req_str(request, "status") in ("new", "sent"):
            sent = req_str(request, "status") == "sent"
            db.run("UPDATE award_distinctions SET status = ?, sent_at = CASE WHEN ? THEN LOCALTIMESTAMP ELSE NULL END WHERE id = ?",
                   [req_str(request, "status"), sent, d["id"]])
            note = ""
            if sent:
                try:
                    note = " Post : " + D.announce(d) + "."
                except Exception as exc:  # noqa: BLE001 — l'envoi reste enregistré même si le post échoue
                    note = f" Post non programmé : {exc}."
            return back(request, path("admin/distinctions"), "success", f"Distinction N° {d['id']:04d} : " + ("envoyée." if sent else "à envoyer.") + note)
        if kind in ("carte", "impression", "dorure", "cadre"):
            data, ctype, name = D.files(d, kind)
            resp = HttpResponse(data, content_type=ctype)
            resp["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
            return resp
    rows = db.all("""SELECT d.*, a.contact_email, a.instagram FROM award_distinctions d JOIN artists a ON a.id = d.artist_id
                     ORDER BY d.id DESC LIMIT 300""")
    for r in rows:
        r["public"] = D.public_url(r)
        r["message"] = D.message(r)
        r["image"] = url("media/distinctions/" + r["image_name"]) if r["image_name"] else None
        r["month"] = D.month_label(r["period_key"])
    return admin_render(request, "distinctions", {"title": "Distinctions", "rows": rows, "pending": D.pending_runs()})


@admin_view()
def controles(request):
    rows = db.all("""SELECT ran_at, agent, level, message, link FROM agent_findings WHERE ran_at >= LOCALTIMESTAMP - INTERVAL '14 days'
                     ORDER BY ran_at DESC, level, agent LIMIT 300""")
    return admin_render(request, "controles", {"title": "Contrôles", "rows": rows,
                                               "counts": {lv: sum(1 for r in rows if r["level"] == lv) for lv in ("corrige", "alerte", "info")}})
