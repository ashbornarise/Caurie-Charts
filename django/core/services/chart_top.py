"""Top d'un pays ou de l'Afrique de l'Ouest, sous une forme simple (widget à intégrer, chaîne Telegram).

Classement officiel publié de la semaine s'il existe, sinon tendances des classements des plateformes : la source
est toujours indiquée (« official »), jamais présentée comme un classement Cauri Charts quand ce n'en est pas un.
"""
from core import repos
from core.helpers import country_name
from core.services import live_chart

REGION = "wa"


def top(code: str, limit: int = 10) -> dict | None:
    code = (code or REGION).lower()
    regional = code == REGION
    country = None if regional else repos.country(code)
    if not regional and not country:
        return None
    cid = None if regional else country["id"]
    name = "Afrique de l’Ouest" if regional else country_name(country["code"])
    run = repos.latest_run(cid, "prime-wa" if regional else "prime", "week")
    if run:
        rows = [{"rank": int(e["position"]), "title": e["title"], "artist": e["artist_name"], "track_slug": e["track_slug"],
                 "artist_slug": e["artist_slug"], "cover": e["cover_url"], "previous": e.get("previous_position")}
                for e in repos.entries(int(run["id"]), limit)]
        return {"code": code, "name": name, "official": True, "run": run, "rows": rows,
                "since": run["period_start"], "until": run["period_end"]}
    live = live_chart.build(cid, None, limit, "prime", 20, "week")
    rows = [{"rank": int(r["rank"]), "title": r["title"], "artist": r["artist_name"], "track_slug": r["track_slug"],
             "artist_slug": r["artist_slug"], "cover": r.get("cover_url") or r.get("artist_image"), "previous": None}
            for r in live["rows"]]
    return {"code": code, "name": name, "official": False, "run": None, "rows": rows, "since": live.get("since"), "until": live.get("day")}


def page_path(code: str) -> str:
    """Page publique du classement correspondant (accueil pour la région)."""
    code = (code or REGION).lower()
    return "/" if code == REGION else f"/?pays={code}"
