"""Indice de fiabilité d'un classement (0 à 100), affiché avec lui : sur quoi repose-t-il, et à quel point ?

Quatre mesures, toutes vérifiables dans les relevés des 7 derniers jours :
- sources (40 pts) : nombre de classements de plateformes indépendants relevés pour le pays (4 et plus = plein) ;
- régularité (20 pts) : nombre de jours relevés sur 7 ;
- recoupement (30 pts) : part des titres du Top vus sur au moins deux sources ;
- fraîcheur (10 pts) : âge du dernier relevé.
Les sources calculées par Cauri (popularité Deezer, vues YouTube des artistes suivis) ne comptent pas comme
sources indépendantes : un pays qui ne repose que sur elles reste « indicatif ».
"""
from datetime import date

from core import clock, db

COMPUTED = ("deezer_popularity", "youtube_views")
LEVELS = [(70, "élevée", "Classement solide : plusieurs plateformes concordent."),
          (45, "moyenne", "Classement fiable sur le haut du Top ; le bas bouge encore."),
          (0, "faible", "Classement indicatif : trop peu de sources pour ce pays aujourd'hui.")]


def measure(country_id, rows: list | None = None) -> dict:
    flt, params = ("", []) if country_id is None else (" AND country_id = ?", [country_id])
    stats = db.one(f"""SELECT COUNT(DISTINCT source) FILTER (WHERE source NOT IN ('{"','".join(COMPUTED)}')) AS sources,
                              COUNT(DISTINCT observed_on) AS days, MAX(observed_on) AS last
                       FROM chart_observations WHERE observed_on >= CURRENT_DATE - 7{flt}""", params) or {}
    sources, days = int(stats.get("sources") or 0), int(stats.get("days") or 0)
    top = [r for r in (rows or []) if not r.get("is_artist")][:20]
    seen_twice = sum(1 for r in top if len({s["source"] for s in (r.get("seen") or [])}) >= 2)
    corroboration = seen_twice / len(top) if top else 0.0
    last = stats.get("last")
    age = (clock.today() - date.fromisoformat(str(last)[:10])).days if last else 99
    score = round(40 * min(sources, 4) / 4 + 20 * min(days, 7) / 7 + 30 * corroboration + 10 * max(0, 3 - age) / 3)
    if sources == 0:
        score = min(score, 30)  # uniquement des sources calculées : jamais plus qu'indicatif
    level, text = next((name, txt) for floor, name, txt in LEVELS if score >= floor)
    return {"score": score, "level": level, "text": text, "sources": sources, "days": days,
            "corroborated": seen_twice, "top": len(top), "age": age}
