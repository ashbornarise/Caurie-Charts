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


@admin_view()
def controles(request):
    rows = db.all("""SELECT ran_at, agent, level, message, link FROM agent_findings WHERE ran_at >= LOCALTIMESTAMP - INTERVAL '14 days'
                     ORDER BY ran_at DESC, level, agent LIMIT 300""")
    return admin_render(request, "controles", {"title": "Contrôles", "rows": rows,
                                               "counts": {lv: sum(1 for r in rows if r["level"] == lv) for lv in ("corrige", "alerte", "info")}})
