"""Au plus 3 titres par artiste dans un Top (formule v3, décision du fondateur du 06/11/2026)."""
from core.services.charts import ChartRanker

BASE = {"weights": {}, "diversity": {"top": 0, "min_sources": 1}, "buzz": {"min_growth_pct": 50, "min_score": 0},
        "fresh": {"max_age_days": 56}, "anti_fraud": {}}


def _titres():
    # Himra a les 5 meilleurs scores, puis trois autres artistes
    t = [{"track_id": i, "artist_id": 5, "score": 100 - i, "sources_count": 2, "flags": []} for i in range(1, 6)]
    t += [{"track_id": 10 + i, "artist_id": 100 + i, "score": 50 - i, "sources_count": 2, "flags": []} for i in range(1, 4)]
    return t


def test_trois_titres_par_artiste_au_plus():
    top = ChartRanker({**BASE, "artist_cap": 3}).cap_artist(sorted(_titres(), key=ChartRanker.sort_key), 5)
    tete = top[:5]
    assert [i["artist_id"] for i in tete].count(5) == 3
    assert [i["track_id"] for i in tete] == [1, 2, 3, 11, 12]
    # les titres en trop descendent juste après le Top, marqués
    assert "artist_capped" in top[5]["flags"] and top[5]["track_id"] == 4


def test_anciennes_formules_sans_plafond():
    top = ChartRanker(BASE).cap_artist(sorted(_titres(), key=ChartRanker.sort_key), 5)
    assert [i["artist_id"] for i in top[:5]] == [5] * 5
