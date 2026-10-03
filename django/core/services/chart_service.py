"""Calcule, stocke et publie les classements à partir des relevés (traduction de Services\\Charts\\ChartService).

Chaque exécution enregistre la formule utilisée : un classement se rejoue à l'identique.
Aucune position n'est jamais écrite à la main.
"""
import json
import math
from datetime import date, timedelta

from core import audit, conf, db
from core.repos import now_utc, php_round
from core.services.charts import ChartRanker, Period, ScoreCalculator, _d, formula_effective_for


def _json(value) -> str:
    """json_encode de PHP : un tableau vide s'écrit [] (et non {})."""
    return json.dumps(value if value else [], ensure_ascii=False)


def _minus_days(day: str, n: int) -> str:
    return (_d(day) - timedelta(days=n)).isoformat()


class ChartService:
    def __init__(self):
        self.chart_types = {r["code"]: int(r["id"]) for r in db.all("SELECT id, code FROM chart_types")}

    def country(self, code: str) -> dict:
        c = db.one("SELECT * FROM countries WHERE code = ?", [code.upper()])
        if not c:
            raise ValueError(f"Pays inconnu : {code}")
        return c

    # ------------------------------------------------------------ semaine

    def compute_week(self, country_code: str, week_start: str, correction: str | None = None, user_id: int | None = None) -> dict:
        """Scores de la semaine puis tous les classements hebdomadaires du pays."""
        country = self.country(country_code)
        period = Period.week_of(week_start)
        formula = formula_effective_for(period.start)
        items = self._score_week(country, period, formula)
        ranker = ChartRanker(formula)
        size = int(country["chart_size"])
        charts = conf.get("charts")
        cid = int(country["id"])

        prime = ranker.prime(items, self._size("prime", size), self._history("prime", cid, "week", period.start))
        results = {"prime": prime}
        prime_ids = [e["track_id"] for e in prime]
        if charts["buzz"]["computed"]:
            results["buzz"] = ranker.buzz(items, prime_ids, self._size("buzz", size), self._history("buzz", cid, "week", period.start))
        if charts["fresh"]["computed"]:
            results["fresh"] = ranker.fresh(items, period.end, self._size("fresh", size), self._history("fresh", cid, "week", period.start))
        if charts["icon"]["computed"]:
            results["icon"] = ranker.icon(items, self._size("icon", size), self._history("icon", cid, "week", period.start))
        if charts["legend"]["computed"]:
            # Cumul des semaines déjà publiées, plus la semaine calculée
            weeks = self._published_weeks(cid, "1970-01-01", _minus_days(period.start, 1)) + [period.start]
            legend_items = self._cumulative_items(cid, weeks, period.start)
            results["legend"] = ranker.cumulative(legend_items, self._size("legend", size), self._history("legend", cid, "week", period.start))

        with db.atomic():
            for code, entries in results.items():
                self._save_run(code, cid, period, formula, entries, False, correction, user_id)

        # Semaine publiée puis corrigée : le mois et l'année qui la contiennent suivent
        if correction is not None:
            self._refresh_aggregates(country_code, period, correction, user_id)

        pending = sum(1 for i in items if i["review_status"] == "pending" and i["score"] > 0)
        return {"country": country["code"], "period": period.key, "tracks_scored": len(items), "pending": pending,
                "entries": {k: len(v) for k, v in results.items()}}

    def _score_week(self, country: dict, period: Period, formula: dict) -> list:
        cid = int(country["id"])
        active = [p.strip() for p in (country["platforms"] or "").split(",") if p.strip()]
        calc = ScoreCalculator(formula)
        tracks = db.all("""SELECT t.id, t.artist_id, t.release_date, a.is_emerging
                           FROM tracks t JOIN artists a ON a.id = t.artist_id
                           WHERE a.submission_country_id = ? AND t.is_active = 1 AND a.status = 'active'""", [cid])
        if not tracks:
            return []
        deltas = self._platform_deltas(cid, period)
        chart_points = self._chart_points(cid, period, int(formula.get("chart_depth") or 100))
        declarations = self._declarations(cid, period)
        history = self._score_history(cid, period.start, int(formula["anti_fraud"]["spike_history_weeks"]))
        decisions = {int(r["track_id"]): r["decision"] for r in db.all("SELECT track_id, decision FROM track_reviews WHERE week_start = ?", [period.start])}

        items, now = [], now_utc()
        for t in tracks:
            tid = int(t["id"])
            track_deltas = {p: v for p, v in (deltas.get(tid, {}).get("plays") or {}).items() if p in active}
            track_decl = declarations.get(tid, [])
            track_chart = chart_points.get(tid, {})
            if not track_deltas and not track_decl and not track_chart:
                continue
            th = history.get(tid, {"prev": 0.0, "list": []})
            result = calc.score({"track_id": tid, "deltas": track_deltas, "youtube_likes": deltas.get(tid, {}).get("likes"),
                                 "declarations": track_decl, "chart_points": track_chart, "history": th["list"],
                                 "decision": decisions.get(tid)}, country["code"])
            db.run("""INSERT INTO weekly_scores (track_id, country_id, week_start, score, sources_count, breakdown, flags, review_status, formula_version, computed_at)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                      ON CONFLICT (track_id, week_start) DO UPDATE SET country_id = EXCLUDED.country_id, score = EXCLUDED.score,
                        sources_count = EXCLUDED.sources_count, breakdown = EXCLUDED.breakdown, flags = EXCLUDED.flags,
                        review_status = EXCLUDED.review_status, formula_version = EXCLUDED.formula_version, computed_at = EXCLUDED.computed_at""",
                   [tid, cid, period.start, result["score"], result["sources_count"], _json(result["breakdown"]),
                    _json(result["flags"]), result["review_status"], formula["version"], now])
            items.append({**result, "track_id": tid, "artist_id": int(t["artist_id"]), "prev_score": th["prev"],
                          "release_date": t["release_date"], "is_emerging": bool(t["is_emerging"])})
        return items

    def _platform_deltas(self, cid: int, period: Period) -> dict:
        """Variation de la semaine : dernier relevé de la semaine moins le dernier relevé d'avant."""
        rows = db.all(
            """SELECT tpi.track_id, tpi.platform, tpi.published_at,
                (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on BETWEEN ? AND ? ORDER BY s.captured_on DESC LIMIT 1) AS end_plays,
                (SELECT likes FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on BETWEEN ? AND ? ORDER BY s.captured_on DESC LIMIT 1) AS end_likes,
                (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on < ? ORDER BY s.captured_on DESC LIMIT 1) AS base_plays,
                (SELECT likes FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on < ? ORDER BY s.captured_on DESC LIMIT 1) AS base_likes
               FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id
               WHERE a.submission_country_id = ? AND tpi.is_official = 1 AND tpi.platform <> 'spotify'""",
            [period.start, period.end, period.start, period.end, period.start, period.start, cid])
        out: dict = {}
        for r in rows:
            if r["end_plays"] is None:
                continue
            new_this_week = r["published_at"] is not None and str(r["published_at"])[:10] >= period.start
            if r["base_plays"] is None and not new_this_week:
                continue  # premier relevé d'un contenu ancien : sert de point de départ
            tid = int(r["track_id"])
            o = out.setdefault(tid, {"plays": {}})
            o["plays"][r["platform"]] = o["plays"].get(r["platform"], 0) + int(r["end_plays"]) - int(r["base_plays"] or 0)
            if r["platform"] == "youtube" and r["end_likes"] is not None:
                o["likes"] = (o.get("likes") or 0) + int(r["end_likes"]) - int(r["base_likes"] or 0)
        return out

    def _chart_points(self, cid: int, period: Period, depth: int) -> dict:
        """Points de position (v1.2) : moyenne sur les jours de (profondeur + 1 - position), sommée sur les pays."""
        rows = db.all("""SELECT o.track_id, o.source, o.country_id, AVG(GREATEST(0, ? + 1 - o.position)) AS pts
                         FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                         WHERE a.submission_country_id = ? AND a.status = 'active' AND o.observed_on BETWEEN ? AND ?
                         GROUP BY o.track_id, o.source, o.country_id""", [depth, cid, period.start, period.end])
        out: dict = {}
        for r in rows:
            d = out.setdefault(int(r["track_id"]), {})
            d[r["source"]] = d.get(r["source"], 0) + float(r["pts"])
        return out

    def _declarations(self, cid: int, period: Period) -> dict:
        rows = db.all("""SELECT s.track_id, s.platform, s.streams, s.period_start, s.period_end
                         FROM submissions s JOIN tracks t ON t.id = s.track_id JOIN artists a ON a.id = t.artist_id
                         WHERE s.status = 'validated' AND a.submission_country_id = ? AND s.period_start <= ? AND s.period_end >= ?""",
                      [cid, period.end, period.start])
        out: dict = {}
        for r in rows:
            streams = ScoreCalculator.prorate(int(r["streams"]), r["period_start"], r["period_end"], period.start, period.end)
            if streams > 0:
                out.setdefault(int(r["track_id"]), []).append({"platform": r["platform"], "streams": streams})
        return out

    def _score_history(self, cid: int, week_start: str, weeks: int) -> dict:
        start, previous_week = _minus_days(week_start, 7 * weeks), _minus_days(week_start, 7)
        out: dict = {}
        for r in db.all("SELECT track_id, week_start, score FROM weekly_scores WHERE country_id = ? AND week_start >= ? AND week_start < ? ORDER BY week_start DESC",
                        [cid, start, week_start]):
            h = out.setdefault(int(r["track_id"]), {"prev": 0.0, "list": []})
            h["list"].append(float(r["score"]))
            if r["week_start"] == previous_week:
                h["prev"] = float(r["score"])
        return out

    def _published_weeks(self, cid: int, start: str, end: str) -> list:
        return [r["period_start"] for r in db.all(
            """SELECT period_start FROM chart_runs WHERE chart_type_id = ? AND country_id = ? AND period_type = 'week'
               AND status = 'published' AND period_start BETWEEN ? AND ? ORDER BY period_start""",
            [self.chart_types["prime"], cid, start, end])]

    def _cumulative_items(self, cid: int, weeks: list, last_week: str) -> list:
        if not weeks:
            return []
        rows = db.all(
            f"""SELECT ws.track_id, t.artist_id, t.release_date,
                   SUM(ws.score) AS score, MAX(ws.sources_count) AS sources_count,
                   SUM(CASE WHEN ws.week_start = ? THEN ws.score ELSE 0 END) AS last_week,
                   MAX(CASE WHEN ws.review_status = 'pending' THEN 1 ELSE 0 END) AS has_pending
                FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id
                WHERE ws.country_id = ? AND ws.week_start IN ({', '.join(['?'] * len(weeks))}) AND ws.review_status <> 'excluded'
                GROUP BY ws.track_id, t.artist_id, t.release_date""", [last_week, cid] + weeks)
        return [{"track_id": int(r["track_id"]), "artist_id": int(r["artist_id"]), "score": php_round(float(r["score"]), 2),
                 "sources_count": int(r["sources_count"]), "prev_score": php_round(float(r["score"]) - float(r["last_week"]), 2),
                 "release_date": r["release_date"], "is_emerging": False, "flags": [],
                 "review_status": "pending" if r["has_pending"] else "ok", "breakdown": []} for r in rows]

    def _history(self, chart_code: str, cid, period_type: str, before: str) -> dict:
        """Position au classement précédent, meilleure position et nombre de périodes au classement."""
        type_id = self.chart_types[chart_code]
        kind = "artist_id" if conf.get(f"charts.{chart_code}.kind") == "artists" else "track_id"
        rows = db.all(f"""SELECT e.{kind} AS id, e.position, r.period_start
                          FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
                          WHERE r.chart_type_id = ? AND r.country_id IS NOT DISTINCT FROM ?::smallint AND r.period_type = ? AND r.period_start < ?
                          ORDER BY r.period_start""", [type_id, cid, period_type, before])
        last_start = db.value("""SELECT MAX(period_start) FROM chart_runs WHERE chart_type_id = ? AND country_id IS NOT DISTINCT FROM ?::smallint
                                 AND period_type = ? AND period_start < ?""", [type_id, cid, period_type, before])
        out: dict = {}
        for r in rows:
            if r["id"] is None:
                continue
            h = out.setdefault(int(r["id"]), {"position": None, "peak": math.inf, "weeks": 0})
            h["peak"] = min(h["peak"], int(r["position"]))
            h["weeks"] += 1
            if r["period_start"] == last_start:
                h["position"] = int(r["position"])
        return out

    def _size(self, chart_code: str, country_size: int) -> int:
        s = conf.get(f"charts.{chart_code}.size")
        return int(s if s is not None else country_size)

    # ------------------------------------------------------------ mois et année

    def compute_aggregate(self, country_code: str, period: Period, correction=None, user_id=None, publish: bool = False):
        """Somme des scores des semaines PUBLIÉES ; un mois n'est calculé qu'une fois complet."""
        country = self.country(country_code)
        cid = int(country["id"])
        weeks = self._published_weeks(cid, period.start, period.end)
        if not weeks:
            return None
        provisional = len(weeks) < len(period.official_week_starts())
        if period.type == "month" and provisional:
            return None
        last_week = weeks[-1]
        items = self._cumulative_items(cid, weeks, last_week)
        prev = period.previous()
        prev_totals = {int(r["track_id"]): float(r["s"]) for r in db.all(
            """SELECT track_id, SUM(score) AS s FROM weekly_scores WHERE country_id = ? AND week_start BETWEEN ? AND ?
               AND review_status <> 'excluded' GROUP BY track_id""", [cid, prev.start, prev.end])}
        for item in items:
            item["prev_score"] = prev_totals.get(item["track_id"], 0.0)
        formula = formula_effective_for(last_week)
        entries = ChartRanker(formula).cumulative(items, int(country["chart_size"]), self._history("prime", cid, period.type, period.start))
        with db.atomic():
            # Le cumul provisoire de l'année se met à jour sans correction : il ne contient que des semaines publiées
            self._save_run("prime", cid, period, formula, entries, provisional, correction, user_id, period.type == "year")
            if publish:
                db.run("""UPDATE chart_runs SET status = 'published', published_at = COALESCE(published_at, ?), published_by = COALESCE(published_by, ?)
                          WHERE chart_type_id = ? AND country_id = ? AND period_type = ? AND period_key = ?""",
                       [now_utc(), user_id, self.chart_types["prime"], cid, period.type, period.key])
        return {"country": country["code"], "period": period.key, "provisional": provisional, "entries": len(entries)}

    def _month_status(self, country_code: str, month_key: str):
        return db.one("""SELECT r.id, r.status FROM chart_runs r JOIN countries c ON c.id = r.country_id
                         WHERE c.code = ? AND r.chart_type_id = ? AND r.period_type = 'month' AND r.period_key = ?""",
                      [country_code, self.chart_types["prime"], month_key])

    def _refresh_aggregates(self, country_code: str, week: Period, correction, user_id) -> None:
        month = Period.month(week.month_key())
        if self._month_status(country_code, month.key):
            self.compute_aggregate(country_code, month, correction, user_id, True)
        self.compute_aggregate(country_code, Period.year(week.end[:4]), None, user_id, True)
        self.compute_regional_week(week, user_id)

    def _after_week_published(self, country_code: str, week: Period, user_id) -> None:
        month = Period.month(week.month_key())
        run = self._month_status(country_code, month.key)
        if not run or run["status"] == "draft":
            self.compute_aggregate(country_code, month, None, user_id, True)  # ne fait rien tant que le mois est incomplet
        self.compute_aggregate(country_code, Period.year(week.end[:4]), None, user_id, True)
        self.compute_regional_week(week, user_id)

    # ------------------------------------------------------------ régional

    def compute_regional_week(self, week: Period, user_id=None):
        """Tous les titres des pays publiés, classés par leur score de la semaine ; publié quand tous le sont."""
        if not self.chart_types.get("prime-wa") or not conf.get("charts.prime-wa.computed"):
            return None
        countries = int(db.value("SELECT COUNT(*) FROM countries WHERE is_active = 1"))
        published = [r["country_id"] for r in db.all(
            """SELECT r.country_id FROM chart_runs r JOIN countries c ON c.id = r.country_id AND c.is_active = 1
               WHERE r.chart_type_id = ? AND r.period_type = 'week' AND r.period_key = ? AND r.status = 'published'""",
            [self.chart_types["prime"], week.key])]
        if not published:
            return None
        rows = db.all(
            f"""SELECT ws.track_id, t.artist_id, t.release_date, ws.score, ws.sources_count, ws.breakdown, a.base_country AS country,
                   (SELECT p.score FROM weekly_scores p WHERE p.track_id = ws.track_id AND p.week_start = ?) AS prev_score
                FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                WHERE ws.week_start = ? AND ws.country_id IN ({', '.join(['?'] * len(published))}) AND ws.review_status <> 'excluded'""",
            [_minus_days(week.start, 7), week.start] + published)
        items = [{"track_id": int(r["track_id"]), "artist_id": int(r["artist_id"]), "score": float(r["score"]),
                  "sources_count": int(r["sources_count"]), "prev_score": float(r["prev_score"] or 0), "release_date": r["release_date"],
                  "is_emerging": False, "flags": [], "review_status": "ok", "country": r["country"],
                  "breakdown": json.loads(r["breakdown"] or "[]") or []} for r in rows]
        complete = len(published) == countries
        formula = formula_effective_for(week.start)
        entries = ChartRanker(formula).prime(items, int(conf.get("charts.prime-wa.size", 20)), self._history("prime-wa", None, "week", week.start),
                                             conf.get("charts.prime-wa.country_cap"))
        with db.atomic():
            self._save_run("prime-wa", None, week, formula, entries, not complete, None, user_id, True)
            if complete:
                self._publish_regional(week)
        if complete:
            self.compute_regional_aggregate(Period.month(week.month_key()), user_id)
            self.compute_regional_aggregate(Period.year(week.end[:4]), user_id)
        return {"period": week.key, "countries": len(published), "published": complete, "entries": len(entries)}

    def compute_regional_aggregate(self, period: Period, user_id=None):
        type_id = self.chart_types["prime-wa"]
        rows = db.all("""SELECT ws.track_id, t.artist_id, a.base_country AS country, SUM(ws.score) AS score, MAX(ws.sources_count) AS countries
                         FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                         JOIN chart_runs r ON r.chart_type_id = ? AND r.country_id IS NULL AND r.period_type = 'week'
                            AND r.status = 'published' AND r.period_start = ws.week_start
                         WHERE ws.week_start BETWEEN ? AND ? AND ws.review_status <> 'excluded'
                         GROUP BY ws.track_id, t.artist_id, a.base_country""", [type_id, period.start, period.end])
        weeks = int(db.value("""SELECT COUNT(*) FROM chart_runs WHERE chart_type_id = ? AND country_id IS NULL AND period_type = 'week'
                                AND status = 'published' AND period_start BETWEEN ? AND ?""", [type_id, period.start, period.end]))
        provisional = weeks < len(period.official_week_starts())
        if not rows or (period.type == "month" and provisional):
            return None
        totals = {int(r["track_id"]): {"score": float(r["score"]), "artist_id": int(r["artist_id"]), "countries": int(r["countries"]),
                                       "country": r["country"]} for r in rows}
        formula = formula_effective_for(period.end)
        entries = ChartRanker(formula).summed_points(totals, int(conf.get("charts.prime-wa.size", 20)), self._history("prime-wa", None, period.type, period.start),
                                                     conf.get("charts.prime-wa.country_cap"))
        with db.atomic():
            self._save_run("prime-wa", None, period, formula, entries, provisional, None, user_id, True)
            self._publish_regional(period)
        return {"period": period.key, "entries": len(entries), "provisional": provisional}

    def _publish_regional(self, period: Period) -> None:
        db.run("""UPDATE chart_runs SET status = 'published', published_at = COALESCE(published_at, ?)
                  WHERE chart_type_id = ? AND country_id IS NULL AND period_type = ? AND period_key = ?""",
               [now_utc(), self.chart_types["prime-wa"], period.type, period.key])

    # ------------------------------------------------------------ enregistrement, publication, décisions

    def _save_run(self, chart_code: str, cid, period: Period, formula: dict, entries: list, provisional: bool,
                  correction, user_id, refresh: bool = False) -> None:
        type_id = self.chart_types[chart_code]
        existing = db.one("""SELECT id, status FROM chart_runs WHERE chart_type_id = ? AND country_id IS NOT DISTINCT FROM ?::smallint
                             AND period_type = ? AND period_key = ?""", [type_id, cid, period.type, period.key])
        now = now_utc()
        fields = {"period_start": period.start, "period_end": period.end, "formula_version": int(formula["version"]),
                  "formula_json": json.dumps(formula, ensure_ascii=False), "methodology_version": str(conf.get("app.methodology_version")),
                  "is_provisional": 1 if provisional else 0, "computed_at": now}
        if existing:
            run_id = int(existing["id"])
            if existing["status"] == "published" and not (refresh and correction is None):
                if correction is None or correction.strip() == "":
                    raise RuntimeError(f"Classement déjà publié ({chart_code} {period.key}) : une correction motivée est obligatoire.")
                fields["correction_note"], fields["corrected_at"] = correction, now
                audit.log(user_id, "chart.correct", "chart_run", run_id, correction)
            db.update("chart_runs", fields, "id = :id", {"id": run_id})
            db.run("DELETE FROM chart_entries WHERE chart_run_id = ?", [run_id])
        else:
            run_id = db.insert("chart_runs", {**fields, "chart_type_id": type_id, "country_id": cid, "period_type": period.type,
                                              "period_key": period.key, "status": "draft"})
        for e in entries:
            flags = list(e["flags"]) + (["pending_review"] if e["review_status"] == "pending" else [])
            db.insert("chart_entries", {
                "chart_run_id": run_id, "position": e["position"], "track_id": e["track_id"], "artist_id": e["artist_id"],
                "score": e["score"], "previous_position": e["previous_position"], "peak_position": e["peak_position"],
                "weeks_on_chart": e["weeks_on_chart"], "sources_count": e["sources_count"], "growth_pct": e["growth_pct"],
                "flags": _json(list(dict.fromkeys(flags))), "details": _json(e["details"]),
            })

    def pending_count(self, cid: int, week_start: str) -> int:
        return int(db.value("SELECT COUNT(*) FROM weekly_scores WHERE country_id = ? AND week_start = ? AND review_status = 'pending' AND score > 0",
                            [cid, week_start]))

    def publish(self, country_code: str, period_type: str, period_key: str, user_id: int, ip: str | None = None) -> int:
        """Publie ensemble les classements hebdomadaires d'un pays ; mois et année suivent automatiquement."""
        if period_type != "week":
            raise RuntimeError("Les mois et les années se publient automatiquement avec leurs semaines.")
        country = self.country(country_code)
        cid = int(country["id"])
        period = Period.from_key(period_type, period_key)
        pending = self.pending_count(cid, period.start)
        if pending > 0:
            raise RuntimeError(f"{pending} titre(s) à vérifier : validez ou excluez-les avant de publier.")
        count = db.run("""UPDATE chart_runs SET status = 'published', published_at = ?, published_by = ?
                          WHERE country_id = ? AND period_type = ? AND period_key = ? AND status = 'draft'""",
                       [now_utc(), user_id, cid, period_type, period_key])
        audit.log(user_id or None, "chart.publish", "country_period", f"{country['code']}:{period_type}:{period_key}", None, {"runs": count}, ip)
        self._after_week_published(country["code"], period, user_id or None)
        return count

    def decide(self, track_id: int, week_start: str, decision: str, reason: str, user_id: int, ip: str | None = None) -> None:
        """Titre signalé validé ou exclu (raison obligatoire, exclusion publique) ; la semaine est recalculée."""
        if decision not in ("validated", "excluded") or reason.strip() == "":
            raise ValueError("Décision invalide ou raison manquante.")
        row = db.one("""SELECT c.code, r.status FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id
                        LEFT JOIN chart_runs r ON r.country_id = c.id AND r.period_type = 'week' AND r.period_start = ? AND r.chart_type_id = ?
                        WHERE t.id = ?""", [week_start, self.chart_types["prime"], track_id])
        if not row:
            raise ValueError("Titre inconnu.")
        db.run("""INSERT INTO track_reviews (track_id, week_start, decision, reason, user_id) VALUES (?, ?, ?, ?, ?)
                  ON CONFLICT (track_id, week_start) DO UPDATE SET decision = EXCLUDED.decision, reason = EXCLUDED.reason,
                    user_id = EXCLUDED.user_id, created_at = CURRENT_TIMESTAMP""", [track_id, week_start, decision, reason, user_id])
        audit.log(user_id, "track." + ("exclude" if decision == "excluded" else "validate"), "track", track_id, reason, {"week_start": week_start}, ip)
        correction = f"Décision sur un titre signalé : {reason}" if row["status"] == "published" else None
        self.compute_week(row["code"], week_start, correction, user_id)
