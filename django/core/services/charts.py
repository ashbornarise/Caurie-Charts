"""Calcul des classements officiels : périodes, score, classement (traduction de Services\\Charts).

Period, ScoreCalculator et ChartRanker sont purs : aucune base de données, tout arrive en paramètre,
si bien que chaque classement est reproductible à partir des mêmes entrées (METHODOLOGIE.md).
"""
import calendar
import copy
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from core import conf, db
from core.repos import php_round


# Première semaine complète de relevés (lundi) : les relevés ont commencé le 30 septembre 2026
FIRST_OFFICIAL_WEEK = "2026-10-05"


def _d(s: str) -> date:
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


# ---------------------------------------------------------------- périodes

@dataclass(frozen=True)
class Period:
    """Semaine : lundi au dimanche. Une semaine appartient au mois (et à l'année) de son dimanche."""
    type: str
    key: str
    start: str
    end: str

    @staticmethod
    def week_of(day: str) -> "Period":
        d = _d(day)
        monday = d - timedelta(days=d.isoweekday() - 1)
        sunday = monday + timedelta(days=6)
        y, w, _ = monday.isocalendar()
        return Period("week", f"{y}-W{w:02d}", monday.isoformat(), sunday.isoformat())

    @staticmethod
    def last_completed_week(today: str) -> "Period":
        return Period.week_of((_d(today) - timedelta(days=7)).isoformat())

    @staticmethod
    def from_key(ptype: str, key: str) -> "Period":
        if ptype == "week":
            return Period.week_from_key(key)
        if ptype == "month":
            return Period.month(key)
        if ptype == "year":
            return Period.year(key)
        raise ValueError(f"Période inconnue : {ptype}")

    @staticmethod
    def week_from_key(key: str) -> "Period":
        m = re.fullmatch(r"(\d{4})-W(\d{2})", key)
        if not m:
            raise ValueError(f"Semaine invalide : {key}")
        return Period.week_of(date.fromisocalendar(int(m[1]), int(m[2]), 1).isoformat())

    @staticmethod
    def month(key: str) -> "Period":
        """Mois = semaines dont le dimanche tombe dans le mois."""
        if not re.fullmatch(r"\d{4}-\d{2}", key):
            raise ValueError(f"Mois invalide : {key}")
        y, m = int(key[:4]), int(key[5:7])
        first = date(y, m, 1)
        last = date(y, m, calendar.monthrange(y, m)[1])
        first_sunday = first + timedelta(days=(7 - first.isoweekday()) % 7)
        last_sunday = last - timedelta(days=last.isoweekday() % 7)
        return Period("month", key, (first_sunday - timedelta(days=6)).isoformat(), last_sunday.isoformat())

    @staticmethod
    def year(key: str) -> "Period":
        return Period("year", str(key), Period.month(f"{key}-01").start, Period.month(f"{key}-12").end)

    def week_starts(self) -> list[str]:
        out, d, end = [], _d(self.start), _d(self.end)
        while d <= end:
            out.append(d.isoformat())
            d += timedelta(days=7)
        return out

    def official_week_starts(self) -> list[str]:
        """Semaines du mois qui peuvent avoir un classement officiel : rien avant le début des relevés complets
        (FIRST_OFFICIAL_WEEK). Octobre 2026 compte ainsi ses semaines du 5 au 25, sans la semaine incomplète du 28 septembre."""
        return [w for w in self.week_starts() if w >= FIRST_OFFICIAL_WEEK]

    def previous(self) -> "Period":
        if self.type == "week":
            return Period.week_of((_d(self.start) - timedelta(days=7)).isoformat())
        if self.type == "month":
            y, m = int(self.key[:4]), int(self.key[5:7])
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
            return Period.month(f"{y}-{m:02d}")
        return Period.year(str(int(self.key) - 1))

    def month_key(self) -> str:
        return self.end[:7]


# ---------------------------------------------------------------- signalements

class Flags:
    """Les signalements « bloquants » retiennent la publication."""
    SPIKE = "spike"
    DECLARATION_MISMATCH = "declaration_mismatch"
    YOUTUBE_RATIO = "youtube_ratio"
    NEGATIVE_DELTA = "negative_delta"
    DECLARATION_UNCORROBORATED = "declaration_uncorroborated"
    DIVERSITY_CAPPED = "diversity_capped"
    DIVERSITY_FALLBACK = "diversity_fallback"
    COUNTRY_CAPPED = "country_capped"
    BLOCKING = [SPIKE, DECLARATION_MISMATCH, YOUTUBE_RATIO]

    @classmethod
    def has_blocking(cls, flags: list) -> bool:
        return any(f in cls.BLOCKING for f in flags)


def _unique(items: list) -> list:
    return list(dict.fromkeys(items))


# ---------------------------------------------------------------- formule

def _replace_recursive(base: dict, new: dict) -> dict:
    """array_replace_recursive de PHP."""
    out = copy.deepcopy(base)
    for k, v in new.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _replace_recursive(out[k], v)
        else:
            out[k] = v
    return out


def formula_effective_for(day: str) -> dict:
    """Formule en vigueur pour une date, complétée par les valeurs par défaut de config/formula.php."""
    row = db.one("SELECT version, formula_json FROM formula_versions WHERE effective_from <= ? ORDER BY effective_from DESC, version DESC LIMIT 1", [day])
    defaults = copy.deepcopy(conf.get("formula"))
    if not row:
        return defaults
    stored = json.loads(row["formula_json"] or "{}") or {}
    formula = _replace_recursive(defaults, stored) if isinstance(stored, dict) else defaults
    formula["version"] = int(row["version"])
    return formula


def formula_all() -> list:
    return db.all("SELECT f.*, u.name AS author FROM formula_versions f LEFT JOIN users u ON u.id = f.created_by ORDER BY version DESC")


def formula_next_version() -> int:
    return int(db.value("SELECT COALESCE(MAX(version), 0) + 1 FROM formula_versions"))


# ---------------------------------------------------------------- score

class ScoreCalculator:
    """Score hebdomadaire d'un titre (METHODOLOGIE.md, sections 3, 4 et 6)."""
    WEIGHT_CLASS = {"youtube": "youtube", "audiomack": "audio", "boomplay": "audio", "apple_music": "audio", "deezer": "audio"}

    def __init__(self, formula: dict):
        self.formula = formula

    def weight(self, cls: str, country_code: str) -> float:
        cw = (self.formula.get("country_weights") or {}).get(country_code, {}) or {}
        if cls in cw and cw[cls] is not None:
            return float(cw[cls])
        return float((self.formula.get("weights") or {}).get(cls) or 0.0)

    def score(self, inp: dict, country_code: str) -> dict:
        flags, breakdown, score, public_sources, sources = [], {}, 0.0, 0, {}
        deltas = inp.get("deltas") or {}
        for platform, delta in deltas.items():
            if delta is None or platform not in self.WEIGHT_CLASS:
                continue
            if delta < 0:
                # Compteur qui recule (vidéo supprimée, correction de la plateforme) : on ne retire rien
                flags.append(Flags.NEGATIVE_DELTA)
                delta = 0
            weight = self.weight(self.WEIGHT_CLASS[platform], country_code)
            points = delta * weight
            breakdown[platform] = {"delta": int(delta), "weight": weight, "points": php_round(points, 2)}
            score += points
            if delta > 0:
                public_sources += 1
                sources[platform] = True

        # Positions dans les classements des plateformes (v1.2) : donnée publique, comme les compteurs
        for source, chart_points in (inp.get("chart_points") or {}).items():
            weight = float((self.formula.get("chart_weights") or {}).get(source) or 0)
            if weight <= 0 or chart_points <= 0:
                continue
            points = chart_points * weight
            breakdown["chart:" + source] = {"delta": php_round(float(chart_points), 1), "weight": weight, "points": php_round(points, 2)}
            score += points
            if source not in sources:
                public_sources += 1
            sources[source] = True

        declared_sources = 0
        af = self.formula["anti_fraud"]
        tolerance = float(af["declaration_tolerance"])
        for decl in inp.get("declarations") or []:
            platform, streams = decl["platform"], int(decl["streams"])
            public = deltas.get(platform)
            if public is not None:
                # Donnée publique sur la même plateforme : elle prévaut, la déclaration sert de contrôle
                gap = abs(streams - public) / public if public > 0 else (1.0 if streams > 0 else 0.0)
                if gap > tolerance:
                    flags.append(Flags.DECLARATION_MISMATCH)
                continue
            if public_sources == 0:
                flags.append(Flags.DECLARATION_UNCORROBORATED)
                continue
            weight = self.weight("declaration", country_code)
            points = streams * weight
            breakdown["declaration:" + platform] = {"delta": streams, "weight": weight, "points": php_round(points, 2)}
            score += points
            if streams > 0 and platform not in sources:
                declared_sources += 1
                sources[platform] = True

        # Pic anormal : variation > facteur x médiane des N dernières semaines
        history = list(inp.get("history") or [])[: int(af["spike_history_weeks"])]
        if len(history) >= int(af["spike_min_history"]):
            med = self.median(history)
            if med > 0 and score > af["spike_factor"] * med:
                flags.append(Flags.SPIKE)

        # Ratio vues / « j'aime » sur YouTube
        views, likes = deltas.get("youtube"), inp.get("youtube_likes")
        if views is not None and likes is not None and views >= af["youtube_min_views"]:
            per_thousand = likes / views * 1000
            if per_thousand < af["youtube_min_likes_per_1000"] or per_thousand > af["youtube_max_likes_per_1000"]:
                flags.append(Flags.YOUTUBE_RATIO)

        flags = _unique(flags)
        decision = inp.get("decision")
        status = ("excluded" if decision == "excluded" else "validated" if decision == "validated"
                  else "pending" if Flags.has_blocking(flags) else "ok")
        return {"score": php_round(score, 2), "sources_count": public_sources + declared_sources,
                "breakdown": breakdown, "flags": flags, "review_status": status}

    @staticmethod
    def median(values: list) -> float:
        if not values:
            return 0.0
        v = sorted(values)
        n, mid = len(v), len(v) // 2
        return float(v[mid]) if n % 2 else (v[mid - 1] + v[mid]) / 2

    @staticmethod
    def prorate(streams: int, period_start: str, period_end: str, week_start: str, week_end: str) -> int:
        """Ramène une déclaration couvrant une période quelconque à la part qui chevauche la semaine."""
        ps, pe = _d(period_start), _d(period_end)
        o_start, o_end = max(ps, _d(week_start)), min(pe, _d(week_end))
        if o_end < o_start:
            return 0
        period_days = (pe - ps).days + 1
        overlap_days = (o_end - o_start).days + 1
        return php_round(streams * overlap_days / max(1, period_days))


# ---------------------------------------------------------------- classement

def _prev(item) -> float:
    return item.get("prev_score") or 0


class ChartRanker:
    """Transforme des scores en classements (METHODOLOGIE.md, sections 4 et 5)."""

    def __init__(self, formula: dict):
        self.formula = formula

    @staticmethod
    def sort_key(i: dict):
        """Départage : score, nombre de sources, progression, score précédent, puis identifiant (stable)."""
        ident = i.get("id") if i.get("id") is not None else i.get("track_id")
        return (-i["score"], -i["sources_count"], -(i["score"] - _prev(i)), -_prev(i), ident)

    @staticmethod
    def eligible(items: list) -> list:
        return [i for i in items if i["score"] > 0 and (i.get("review_status") or "ok") != "excluded"]

    def prime(self, items: list, size: int, previous: dict | None = None, country_cap: int | None = None) -> list:
        ordered = self.apply_diversity(sorted(self.eligible(items), key=self.sort_key))
        if country_cap:
            ordered = self.cap_per_country(ordered, size, country_cap)
        return self._finalize(ordered[:size], previous or {}, "track_id")

    @staticmethod
    def cap_per_country(ordered: list, size: int, cap: int) -> list:
        """Classement régional : au plus `cap` titres d'artistes d'un même pays dans le Top `size`. Les titres en trop
        descendent juste après le Top, dans leur ordre (marqués country_capped). Artiste sans pays connu : pas de plafond."""
        head, rest, count = [], [], {}
        for item in ordered:
            c = item.get("country")
            if len(head) < size and (not c or count.get(c, 0) < cap):
                head.append(item)
                if c:
                    count[c] = count.get(c, 0) + 1
            elif len(head) < size:
                rest.append({**item, "flags": list(item.get("flags") or []) + [Flags.COUNTRY_CAPPED]})
            else:
                rest.append(item)
        return head + rest

    def apply_diversity(self, sorted_items: list) -> list:
        top, mn = int(self.formula["diversity"]["top"]), int(self.formula["diversity"]["min_sources"])
        head, rest = [], []
        for i, item in enumerate(sorted_items):
            if len(head) < top and item["sources_count"] >= mn:
                head.append(item)
            else:
                rest.append((i + 1, item))
        result = list(head)
        for natural_rank, item in rest:
            if item["sources_count"] < mn:
                item = {**item, "flags": list(item.get("flags") or [])}
                if len(result) < top:
                    item["flags"].append(Flags.DIVERSITY_FALLBACK)
                elif natural_rank <= top:
                    item["flags"].append(Flags.DIVERSITY_CAPPED)
            result.append(item)
        return result

    def buzz(self, items: list, prime_track_ids: list, size: int, previous: dict | None = None) -> list:
        cfg, candidates = self.formula["buzz"], []
        for item in self.eligible(items):
            prev = float(_prev(item))
            if item["track_id"] in prime_track_ids or prev <= 0 or item["score"] < cfg["min_score"]:
                continue
            growth = (item["score"] - prev) / prev * 100
            if growth <= cfg["min_growth_pct"]:
                continue
            candidates.append({**item, "growth_pct": php_round(growth, 2)})
        candidates.sort(key=lambda a: (-a["growth_pct"], -a["score"], a["track_id"]))
        return self._finalize(candidates[:size], previous or {}, "track_id")

    def fresh(self, items: list, week_end: str, size: int, previous: dict | None = None) -> list:
        max_age = int(self.formula["fresh"]["max_age_days"])
        end = _d(week_end)
        limit = end - timedelta(days=max_age)

        def ok(i):
            released = _d(i["release_date"]) if i.get("release_date") else None
            return (released is not None and limit < released <= end) or bool(i.get("is_emerging"))
        candidates = sorted([i for i in self.eligible(items) if ok(i)], key=self.sort_key)
        return self._finalize(candidates[:size], previous or {}, "track_id")

    def icon(self, items: list, size: int, previous: dict | None = None) -> list:
        artists: dict = {}
        for item in self.eligible(items):
            aid = item["artist_id"]
            a = artists.setdefault(aid, {"id": aid, "artist_id": aid, "track_id": None, "score": 0.0, "sources_count": 0,
                                         "prev_score": 0.0, "flags": [], "breakdown": []})
            a["score"] += item["score"]
            a["prev_score"] += float(_prev(item))
            a["sources_count"] += 1  # nombre de titres
            a["breakdown"].append({"track_id": item["track_id"], "score": item["score"]})
        lst = list(artists.values())
        for a in lst:
            a["score"] = php_round(a["score"], 2)
        lst.sort(key=lambda a: (-a["score"], -a["sources_count"], a["artist_id"]))
        return self._finalize(lst[:size], previous or {}, "artist_id")

    def cumulative(self, items: list, size: int, previous: dict | None = None) -> list:
        return self._finalize(sorted(self.eligible(items), key=self.sort_key)[:size], previous or {}, "track_id")

    @staticmethod
    def regional_points(country_charts: dict, points_for: int = 10) -> list:
        totals: dict = {}
        for entries in country_charts.values():
            for e in entries:
                if e["position"] > points_for:
                    continue
                t = totals.setdefault(e["track_id"], {"track_id": e["track_id"], "points": 0, "countries": 0, "best": math.inf})
                t["points"] += points_for - e["position"] + 1
                t["countries"] += 1
                t["best"] = min(t["best"], e["position"])
        return sorted(totals.values(), key=lambda a: (-a["points"], -a["countries"], a["best"], a["track_id"]))

    def summed_points(self, totals: dict, size: int, previous: dict | None = None, country_cap: int | None = None) -> list:
        items = [{"track_id": tid, "artist_id": t["artist_id"], "score": float(t["score"]), "sources_count": int(t["countries"]),
                  "country": t.get("country"), "flags": [], "breakdown": []} for tid, t in totals.items()]
        items.sort(key=lambda a: (-a["score"], -a["sources_count"], a["track_id"]))
        if country_cap:
            items = self.cap_per_country(items, size, country_cap)
        return self._finalize(items[:size], previous or {}, "track_id")

    @staticmethod
    def _finalize(lst: list, previous: dict, key: str) -> list:
        entries = []
        for i, item in enumerate(lst):
            position = i + 1
            ident = item[key]
            prev = previous.get(ident)
            entries.append({
                "position": position,
                "track_id": ident if key == "track_id" else None,
                "artist_id": ident if key == "artist_id" else item.get("artist_id"),
                "score": php_round(float(item["score"]), 2),
                "previous_position": prev["position"] if prev else None,
                "peak_position": min(prev["peak"], position) if prev else position,
                "weeks_on_chart": prev["weeks"] + 1 if prev else 1,
                "sources_count": int(item["sources_count"]),
                "growth_pct": item.get("growth_pct"),
                "flags": _unique(item.get("flags") or []),
                "review_status": item.get("review_status") or "ok",
                "details": item.get("breakdown") or [],
            })
        return entries
