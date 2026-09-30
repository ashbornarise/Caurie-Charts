"""Faits de la semaine calculés à partir du dernier Prime Chart publié d'un pays (traduction de Services\\Insights)."""
from datetime import date, datetime, timedelta

from core import clock
from core import db, repos
from core.i18n import t


def for_country(country: dict) -> dict:
    cid = int(country["id"]) if country.get("id") is not None else None
    chart_code = "prime-wa" if cid is None else "prime"
    run = repos.latest_run(cid, chart_code, "week")
    if not run:
        return {"run": None, "facts": []}
    entries = repos.entries(int(run["id"]))
    facts = []

    top = entries[0] if entries else None
    if top:
        streak = 0
        for row in db.all(
            """SELECT e.track_id FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
               JOIN chart_entries e ON e.chart_run_id = r.id AND e.position = 1
               WHERE r.country_id IS NOT DISTINCT FROM ?::smallint AND ct.code = ? AND r.period_type = 'week'
                 AND r.status = 'published' AND r.period_end <= ?
               ORDER BY r.period_end DESC LIMIT 52""", [cid, chart_code, run["period_end"]]):
            if int(row["track_id"]) != int(top["track_id"]):
                break
            streak += 1
        facts.append({"type": "number_one", "entry": top, "value": streak})

    climber = None
    for e in entries:
        if e["previous_position"] is not None and int(e["previous_position"]) > int(e["position"]):
            gain = int(e["previous_position"]) - int(e["position"])
            if not climber or gain > climber["value"]:
                climber = {"type": "climber", "entry": e, "value": gain}
    if climber:
        facts.append(climber)

    new = [e for e in entries if e["previous_position"] is None and int(e["weeks_on_chart"]) == 1]
    if new:
        facts.append({"type": "best_new", "entry": new[0], "value": len(new)})

    buzz = repos.latest_run(cid, "buzz", "week") if cid is not None else None
    if buzz:
        b = (repos.entries(int(buzz["id"]), 1) or [None])[0]
        if b:
            facts.append({"type": "buzz", "entry": b, "value": float(b["growth_pct"] or 0)})

    by_artist: dict = {}
    for e in entries:
        by_artist.setdefault(e["artist_slug"], {"entry": e, "value": 0})["value"] += 1
    ranked = sorted(by_artist.values(), key=lambda x: -x["value"])
    if ranked and ranked[0]["value"] > 1:
        facts.append({"type": "most_tracks", "entry": ranked[0]["entry"], "value": ranked[0]["value"]})

    end = datetime.strptime(run["period_end"][:10], "%Y-%m-%d").date()
    return {"run": run, "facts": facts, "next": (end + timedelta(days=9)).isoformat()}


def did_you_know(count: int = 6) -> str:
    return t("dyk." + str(clock.today().isocalendar()[1] % count + 1))
