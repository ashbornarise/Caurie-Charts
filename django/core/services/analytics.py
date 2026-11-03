"""Analyses de Cauri Charts : ce que la machine mesure pour apprendre ce qui marche.

  post_metrics  : statistiques de chaque publication (Buffer : vues, portée, réactions, commentaires, partages,
                  enregistrements, temps de visionnage), relevées chaque nuit et gardées jour par jour ;
  page_views    : vues du site par page, par jour et par site d'origine, comptées côté serveur, sans cookie ni
                  donnée personnelle (ni adresse IP, ni identifiant) ;
  pipeline_runs : durée et échecs de chaque nuit.
Les exports CSV (Admin > Analyses) réunissent publications, rubriques, mises en page et résultats.
"""
import json
import re
from urllib.parse import urlparse

from core import clock, db

BOTS = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|preview|monitor|curl|python|wget|headless|lighthouse", re.I)
SKIP = ("/admin", "/assets", "/media", "/static", "/partage", "/widget", "/robots.txt", "/sitemap.xml", "/favicon")


def count_view(request, response) -> None:
    """Une vue de page : seulement les pages HTML publiques réussies, vues par un humain (pas un robot)."""
    try:
        path = request.path
        if request.method != "GET" or response.status_code != 200 or path.startswith(SKIP):
            return
        if "text/html" not in response.headers.get("Content-Type", "") or BOTS.search(request.META.get("HTTP_USER_AGENT", "")):
            return
        ref = urlparse(request.META.get("HTTP_REFERER", "")).hostname or ""
        ref = "" if "cauricharts" in ref else ref.removeprefix("www.")[:100]
        db.run("""INSERT INTO page_views (day, path, referrer, views) VALUES (?, ?, ?, 1)
                  ON CONFLICT (day, path, referrer) DO UPDATE SET views = page_views.views + 1""",
               [clock.today().isoformat(), path[:200], ref])
    except Exception:  # noqa: BLE001 — la mesure ne doit jamais casser une page
        pass


def vu_humain(request) -> bool:
    """Vue envoyée par le navigateur (ui.js) après 1,5 s de page réellement affichée : la plupart des robots
    n'exécutent pas ce script, d'où un compte honnête des visiteurs humains (pages vues et visites), sans cookie."""
    try:
        d = json.loads(request.body or b"{}")
    except ValueError:
        return False
    path = str(d.get("p") or "")[:200]
    if not path.startswith("/") or path.startswith(SKIP) or BOTS.search(request.META.get("HTTP_USER_AGENT", "")):
        return False
    ref = urlparse(str(d.get("r") or "")).hostname or ""
    ref = "" if "cauricharts" in ref else ref.removeprefix("www.")[:100]
    visite = 1 if d.get("n") else 0
    sql = """INSERT INTO vues_humaines (day, path, referrer, views, visites) VALUES (?, ?, ?, 1, ?)
             ON CONFLICT (day, path, referrer) DO UPDATE SET views = vues_humaines.views + 1, visites = vues_humaines.visites + EXCLUDED.visites"""
    args = [clock.today().isoformat(), path, ref, visite]
    try:
        db.run(sql, args)
    except Exception:  # noqa: BLE001 — première fois : la table n'existe pas encore
        db.run("""CREATE TABLE IF NOT EXISTS vues_humaines (day DATE NOT NULL, path VARCHAR(200) NOT NULL, referrer VARCHAR(100) NOT NULL DEFAULT '',
                  views INTEGER NOT NULL DEFAULT 0, visites INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, path, referrer))""")
        db.run(sql, args)
    return True


def record_run(report: list) -> None:
    db.insert("pipeline_runs", {"seconds": int(sum(r["seconds"] for r in report)), "failed": sum(1 for r in report if not r["ok"]),
                                # 4e case : les messages des étapes en échec ou avec avertissement (03/11/2026 : ils se perdaient
                                # avec le serveur GitHub, on ne les voyait que dans le mail du matin)
                                "steps": json.dumps([[r["step"], r["ok"], round(r["seconds"]),
                                                      [str(x)[:300] for x in (r.get("lines") or []) if not r["ok"] or re.search(r"ERREUR|échec|Échec", str(x))][:8]]
                                                     for r in report], ensure_ascii=False)})


POSTS = """query($org: OrganizationId!, $after: String) {
  posts(input: {organizationId: $org, filter: {status: [sent]}}, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges { node { id sentAt channelService text metadata { __typename ... on InstagramPostMetadata { type } ... on FacebookPostMetadata { type } }
                   metrics { type value } } } } }"""


def collect_post_metrics() -> str:
    """Statistiques de toutes les publications envoyées par Buffer, enregistrées pour aujourd'hui."""
    from core.services import buffer
    if not buffer.configured():
        return "Buffer non configuré"
    # Publications Cauri programmées par Buffer : identifiant Buffer → post Cauri
    origin = {}
    for r in db.all("SELECT entity_id, data FROM audit_log WHERE action = 'buffer.post' AND data IS NOT NULL"):
        try:
            origin[json.loads(r["data"])["buffer_id"]] = int(r["entity_id"])
        except (ValueError, KeyError, TypeError):
            pass
    org = buffer.call("query { account { organizations { id } } }")["account"]["organizations"][0]["id"]
    after, n, today = None, 0, clock.today().isoformat()
    for _ in range(20):
        try:
            data = buffer.call(POSTS, {"org": org, "after": after})["posts"]
        except Exception as exc:  # noqa: BLE001 — repli sans métadonnées si le schéma diffère
            if after is None and "metadata" in str(exc):
                return _collect_simple(org, origin, today)
            raise
        for e in data["edges"]:
            p = e["node"]
            metrics = {m["type"]: m["value"] for m in p.get("metrics") or []}
            if not metrics:
                continue
            db.run("""INSERT INTO post_metrics (buffer_post_id, captured_on, social_post_id, channel, post_type, sent_at, metrics, text_start)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                      ON CONFLICT (buffer_post_id, captured_on) DO UPDATE SET metrics = EXCLUDED.metrics""",
                   [p["id"], today, origin.get(p["id"]), p["channelService"], ((p.get("metadata") or {}).get("type")),
                    (p.get("sentAt") or "")[:19].replace("T", " ") or None, json.dumps(metrics), (p.get("text") or "")[:300]])
            n += 1
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return f"statistiques relevées pour {n} publications"


def _collect_simple(org: str, origin: dict, today: str) -> str:
    from core.services import buffer
    q = POSTS.replace(" metadata { __typename ... on InstagramPostMetadata { type } ... on FacebookPostMetadata { type } }", "")
    after, n = None, 0
    for _ in range(20):
        data = buffer.call(q, {"org": org, "after": after})["posts"]
        for e in data["edges"]:
            p = e["node"]
            metrics = {m["type"]: m["value"] for m in p.get("metrics") or []}
            if metrics:
                db.run("""INSERT INTO post_metrics (buffer_post_id, captured_on, social_post_id, channel, sent_at, metrics, text_start)
                          VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (buffer_post_id, captured_on) DO UPDATE SET metrics = EXCLUDED.metrics""",
                       [p["id"], today, origin.get(p["id"]), p["channelService"], (p.get("sentAt") or "")[:19].replace("T", " ") or None,
                        json.dumps(metrics), (p.get("text") or "")[:300]])
                n += 1
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return f"statistiques relevées pour {n} publications"


# ------------------------------------------------------------ lectures pour la page Admin > Analyses

def latest_post_metrics() -> list:
    """Dernier relevé de chaque publication, avec la rubrique, la mise en page et l'heure du post Cauri d'origine."""
    from core.services.social.carousel import slide_variant
    rows = db.all("""SELECT DISTINCT ON (m.buffer_post_id) m.*, s.theme, s.title, s.slot_date, s.carousel
                     FROM post_metrics m LEFT JOIN social_posts s ON s.id = m.social_post_id
                     ORDER BY m.buffer_post_id, m.captured_on DESC""")
    out = []
    for r in rows:
        m = json.loads(r["metrics"])
        layout = None
        try:
            first = (json.loads(r["carousel"] or "[]") or [{}])[0].get("file", "")
            layout = slide_variant(first.rsplit("-", 1)[0]) if first else None
        except (ValueError, AttributeError, IndexError):
            pass
        out.append({**{k: r[k] for k in ("buffer_post_id", "channel", "post_type", "sent_at", "theme", "title", "slot_date", "text_start")},
                    "layout": layout, "hour": int(str(r["sent_at"])[11:13]) if r["sent_at"] else None,
                    "views": m.get("views") or m.get("impressions") or 0, "reach": m.get("reach") or 0,
                    "reactions": (m.get("reactions") or 0) + (m.get("likes") or 0), "comments": m.get("comments") or 0,
                    "shares": (m.get("shares") or 0) + (m.get("reposts") or 0), "saves": m.get("saves") or 0,
                    "follows": m.get("follows") or 0, "watch_avg": m.get("averageTimeWatched")})
    return sorted(out, key=lambda r: str(r["sent_at"] or ""), reverse=True)


def by(rows: list, key: str) -> list:
    """Moyennes par rubrique, mise en page, réseau ou heure : ce qui marche le mieux en tête."""
    groups: dict = {}
    for r in rows:
        k = r.get(key) if r.get(key) is not None else "inconnu"
        g = groups.setdefault(k, {"key": k, "posts": 0, "views": 0, "reach": 0, "interactions": 0})
        g["posts"] += 1
        g["views"] += r["views"]
        g["reach"] += r["reach"]
        g["interactions"] += r["reactions"] + r["comments"] + r["shares"] + r["saves"]
    for g in groups.values():
        g["avg_views"] = round(g["views"] / g["posts"])
        g["avg_interactions"] = round(g["interactions"] / g["posts"], 1)
    return sorted(groups.values(), key=lambda g: -g["avg_views"])
