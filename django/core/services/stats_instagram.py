"""Statistiques de chaque publication Instagram, lues dans l'API Instagram (11/11/2026).

Depuis la publication directe par Meta (10/11/2026), les posts Instagram ne passent plus par Buffer : ses statistiques
ne les voyaient plus. Chaque nuit, les publications des 30 derniers jours sont relevées dans post_metrics (même table
que Buffer, identifiant « ig:<id> ») : la page Admin > Analyses et le rapport du lundi les utilisent sans changement.
"""
import json
from datetime import datetime, timedelta, timezone

import requests

from core import clock, db, env
from core.services.platforms import log_write

GRAPH = "https://graph.facebook.com/v21.0"
METRIQUES = "reach,views,saved,shares,likes,comments,total_interactions,follows,profile_visits"
METRIQUES_BASE = "reach,views,saved,shares,likes,comments,total_interactions"


def _get(chemin: str, **params) -> dict:
    params["access_token"] = env.get("META_ACCESS_TOKEN", "")
    r = requests.get(f"{GRAPH}/{chemin}", params=params, timeout=30)
    d = r.json()
    if "error" in d:
        raise RuntimeError(d["error"].get("message", "erreur Instagram")[:200])
    return d


def _insights(media_id: str) -> dict:
    for liste in (METRIQUES, METRIQUES_BASE, "reach,views"):
        try:
            d = _get(f"{media_id}/insights", metric=liste)
            return {m["name"]: (m.get("values") or [{}])[0].get("value", 0) for m in d.get("data", [])}
        except RuntimeError:
            continue   # métrique non disponible pour ce type de publication : liste plus courte
    return {}


def _post_cauri(media: dict) -> int | None:
    """Le post Cauri d'origine : publication directe (audit meta_id), sinon la légende d'un post du même jour."""
    pid = db.value("""SELECT entity_id FROM audit_log WHERE action = 'buffer.post' AND reason LIKE 'post-%-instagram%'
                      AND data LIKE ? LIMIT 1""", [f'%"meta_id": "{media["id"]}"%'])
    if pid:
        return int(pid)
    cap = _norm(media.get("caption"))[:200]
    if not cap:
        return None
    jour = media["timestamp"][:10]
    for p in db.all("""SELECT id, title, caption FROM social_posts WHERE slot_date BETWEEN (?::date - 2) AND (?::date + 2)
                       ORDER BY id DESC""", [jour, jour]):
        c, t = _norm(p["caption"])[:40], _norm(p["title"])[:40]
        if (c and cap.startswith(c)) or (len(t) > 12 and t in cap):
            return int(p["id"])
    return None


def _norm(t: str | None) -> str:
    """Texte comparable : sans accents, sans émojis ni ponctuation (Instagram et Buffer retouchent les légendes)."""
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def collecter(jours: int = 30) -> str:
    ig = env.get("META_IG_ID", "")
    if not ig or not env.get("META_ACCESS_TOKEN", ""):
        return "Instagram : jeton ou compte absent"
    depuis = datetime.now(timezone.utc) - timedelta(days=jours)
    aujourdhui, n, apres = clock.today().isoformat(), 0, None
    for _ in range(10):
        params = {"fields": "id,caption,media_type,media_product_type,timestamp,permalink", "limit": 50}
        if apres:
            params["after"] = apres
        page = _get(f"{ig}/media", **params)
        fini = False
        for m in page.get("data", []):
            quand = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
            if quand < depuis:
                fini = True
                break
            valeurs = _insights(m["id"])
            if not valeurs:
                continue
            type_ = "reel" if m.get("media_product_type") == "REELS" else {"CAROUSEL_ALBUM": "carrousel", "IMAGE": "image",
                                                                          "VIDEO": "video"}.get(m.get("media_type"), "post")
            db.run("""INSERT INTO post_metrics (buffer_post_id, captured_on, social_post_id, channel, post_type, sent_at, metrics, text_start)
                      VALUES (?, ?, ?, 'instagram', ?, ?, ?, ?)
                      ON CONFLICT (buffer_post_id, captured_on) DO UPDATE SET metrics = EXCLUDED.metrics,
                      social_post_id = COALESCE(EXCLUDED.social_post_id, post_metrics.social_post_id)""",
                   [f"ig:{m['id']}", aujourdhui, _post_cauri(m), type_, quand.strftime("%Y-%m-%d %H:%M:%S"),
                    json.dumps(valeurs), (m.get("caption") or "")[:300]])
            n += 1
        apres = ((page.get("paging") or {}).get("cursors") or {}).get("after")
        if fini or not apres or not (page.get("paging") or {}).get("next"):
            break
    log_write("stats", "info", f"Instagram : statistiques de {n} publications relevées")
    return f"Instagram : statistiques de {n} publication(s) des {jours} derniers jours"
