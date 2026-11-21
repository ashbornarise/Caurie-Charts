"""Contrôle de notre Top face au marché (21/11/2026, après l'audit des tops S47 par les IA).

Notre N°1 du Nigeria (« Heaven Baby ») était 44e chez TurnTable et 131e sur Spotify Nigeria, et le N°1 des deux
(« INFERNO ») seulement 3e chez nous. Après le calcul de la semaine, on compare notre Top du pays aux classements de
référence relevés la même semaine (Spotify du pays : les places de la semaine ; TurnTable : le dernier relevé) :
  - un titre de notre Top 3 absent de LEUR Top 50 → alerte ;
  - un titre de leur Top 3 absent de NOTRE Top 20 → alerte.
Les alertes vont dans le rapport de la nuit, à regarder avant de publier le vendredi soir. Rien n'est corrigé tout seul.
"""
from core import db
from core.services.charts import Period

# Pays → classements de référence relevés (chart_observations.source)
REFERENCES = {"NG": ("spotify", "turntable")}


def _places(source: str, cid: int, period: Period) -> dict:
    """Meilleure place de chaque titre dans le classement de référence pendant la semaine (Spotify : top quotidien ;
    TurnTable : son top hebdomadaire daté de sa semaine)."""
    return {int(r["track_id"]): int(r["p"]) for r in db.all(
        """SELECT track_id, MIN(position) AS p FROM chart_observations WHERE source = ? AND country_id = ?
           AND observed_on BETWEEN ? AND ? AND track_id IS NOT NULL GROUP BY track_id""", [source, cid, period.start, period.end])}


def _semaine_comparee(source: str, cid: int, week: Period) -> Period:
    """TurnTable publie avec environ une semaine de retard : on compare son dernier top publié à NOTRE classement de la
    même semaine (le vendredi, c'est en général la semaine d'avant)."""
    if source != "turntable":
        return week
    jour = db.value("SELECT MAX(observed_on) FROM chart_observations WHERE source = ? AND country_id = ? AND observed_on <= ?",
                    [source, cid, week.end])
    return Period.week_of(str(jour)[:10]) if jour else week


def _notre_top(cid: int, key: str) -> list:
    return db.all("""SELECT e.position, e.track_id, t.title, a.name FROM chart_entries e
                     JOIN chart_runs r ON r.id = e.chart_run_id JOIN chart_types ct ON ct.id = r.chart_type_id AND ct.code = 'prime'
                     JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
                     WHERE r.country_id = ? AND r.period_type = 'week' AND r.period_key = ?
                     ORDER BY r.id DESC, e.position LIMIT 20""", [cid, key])


def spearman(nous: dict, eux: dict, absent: int = 999) -> float | None:
    """Accord de rang de Spearman sur l'union de notre Top et de leur classement (un titre absent d'un côté est classé
    dernier de ce côté). nous / eux : {track_id: rang}. None s'il y a moins de 5 titres."""
    ids = list(set(nous) | set(eux))
    if len(ids) < 5:
        return None

    def rangs(v: list) -> list:
        ordre = sorted(range(len(v)), key=lambda k: v[k])
        r = [0.0] * len(v)
        k = 0
        while k < len(ordre):   # rangs moyens pour les ex aequo (les absents)
            j = k
            while j + 1 < len(ordre) and v[ordre[j + 1]] == v[ordre[k]]:
                j += 1
            for m in range(k, j + 1):
                r[ordre[m]] = (k + j) / 2 + 1
            k = j + 1
        return r

    a = rangs([nous.get(i, absent) for i in ids])
    b = rangs([eux.get(i, absent) for i in ids])
    n = len(ids)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return cov / (va * vb) ** 0.5 if va and vb else None


def controle(week: Period) -> list:
    lignes = []
    for code, sources in REFERENCES.items():
        c = db.one("SELECT id FROM countries WHERE code = ?", [code])
        if not c:
            continue
        cid = int(c["id"])
        for source in sources:
            sem = _semaine_comparee(source, cid, week)
            notre = _notre_top(cid, sem.key)
            if not notre:
                continue
            nos_ids = {int(x["track_id"]) for x in notre}
            places = _places(source, cid, sem)
            if not places:
                lignes.append(f"⚠ {code} : aucun relevé {source} pour {sem.key}, contrôle impossible")
                continue
            rho = spearman({int(x["track_id"]): int(x["position"]) for x in notre}, places)
            if rho is not None:   # suivi publié chaque semaine (bilans à 4, 8, 12, 26 semaines)
                lignes.append(f"{code} {sem.key} : accord avec {source} (Spearman) = {rho:.2f}")
            for x in notre[:3]:
                p = places.get(int(x["track_id"]))
                if p is None or p > 50:
                    lignes.append(f"⚠ {code} : notre N°{x['position']} « {x['title']} » ({x['name']}) est "
                                  f"{'absent du Top 100/200' if p is None else f'{p}e'} chez {source}")
            for tid, p in sorted(places.items(), key=lambda kv: kv[1])[:3]:
                if tid not in nos_ids:
                    t = db.one("SELECT t.title, a.name, a.status FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE t.id = ?", [tid])
                    lignes.append(f"⚠ {code} : N°{p} chez {source}, « {t['title']} » ({t['name']}, {t['status']}) n'est pas dans notre Top 20")
        if not any(l.startswith(f"⚠ {code}") for l in lignes):
            lignes.append(f"{code} : notre Top colle au marché ({', '.join(sources)})")
    return lignes
