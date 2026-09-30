"""Calcul du score et des classements (traduction de tests/ChartCalculationTest.php)."""
import copy

from core import conf
from core.services.charts import ChartRanker, Flags, ScoreCalculator

FORMULA = conf.get("formula")


def formula():
    return copy.deepcopy(FORMULA)


def item(i, score, sources=2, **extra):
    return {"track_id": i, "artist_id": 100 + i, "score": score, "sources_count": sources, "prev_score": 0.0, "release_date": None,
            "is_emerging": False, "flags": [], "review_status": "ok", "breakdown": [], **extra}


def ids(entries):
    return [e["track_id"] for e in entries]


# --- Variations et poids ---

def test_score_additionne_variation_x_poids():
    r = ScoreCalculator(formula()).score({"deltas": {"youtube": 10000, "audiomack": 3000, "boomplay": 2000}}, "TG")
    assert r["score"] == 10000 * 0.5 + 3000 + 2000
    assert r["sources_count"] == 3
    assert r["review_status"] == "ok"


def test_spotify_hors_score():
    r = ScoreCalculator(formula()).score({"deltas": {"spotify": 50000, "youtube": 1000}}, "TG")
    assert r["score"] == 500.0
    assert r["sources_count"] == 1


def test_poids_par_pays():
    f = formula()
    f["country_weights"] = {"GH": {"youtube": 0.8}}
    calc = ScoreCalculator(f)
    assert calc.score({"deltas": {"youtube": 1000}}, "GH")["score"] == 800.0
    assert calc.score({"deltas": {"youtube": 1000}}, "TG")["score"] == 500.0


def test_variation_negative():
    r = ScoreCalculator(formula()).score({"deltas": {"youtube": -500, "audiomack": 100}}, "TG")
    assert r["score"] == 100.0
    assert Flags.NEGATIVE_DELTA in r["flags"]
    assert r["sources_count"] == 1


def test_source_sans_donnee_ignoree():
    r = ScoreCalculator(formula()).score({"deltas": {"youtube": None, "audiomack": 400}}, "TG")
    assert r["score"] == 400.0
    assert r["sources_count"] == 1


# --- Déclarations ---

def test_declaration_recoupee():
    r = ScoreCalculator(formula()).score({"deltas": {"youtube": 2000}, "declarations": [{"platform": "spotify", "streams": 700}]}, "TG")
    assert r["score"] == 1000.0 + 700
    assert r["sources_count"] == 2


def test_declaration_sans_donnee_publique():
    r = ScoreCalculator(formula()).score({"deltas": {}, "declarations": [{"platform": "spotify", "streams": 5000}]}, "TG")
    assert r["score"] == 0.0
    assert Flags.DECLARATION_UNCORROBORATED in r["flags"]


def test_declaration_ecart_30_pourcent():
    calc = ScoreCalculator(formula())
    bad = calc.score({"deltas": {"audiomack": 1000}, "declarations": [{"platform": "audiomack", "streams": 1400}]}, "TG")
    assert Flags.DECLARATION_MISMATCH in bad["flags"]
    assert bad["review_status"] == "pending"
    assert bad["score"] == 1000.0, "la donnée publique prévaut"
    ok = calc.score({"deltas": {"audiomack": 1000}, "declarations": [{"platform": "audiomack", "streams": 1250}]}, "TG")
    assert Flags.DECLARATION_MISMATCH not in ok["flags"]
    assert ok["review_status"] == "ok"


def test_prorata_semaine():
    assert ScoreCalculator.prorate(1000, "2026-09-14", "2026-09-27", "2026-09-21", "2026-09-27") == 500
    assert ScoreCalculator.prorate(1000, "2026-08-01", "2026-08-31", "2026-09-21", "2026-09-27") == 0


# --- Anti-fraude ---

def test_pic_5_fois_la_mediane():
    calc = ScoreCalculator(formula())
    r = calc.score({"deltas": {"audiomack": 6000}, "history": [1000, 1100, 900, 1000]}, "TG")
    assert Flags.SPIKE in r["flags"]
    assert r["review_status"] == "pending"
    normal = calc.score({"deltas": {"audiomack": 4900}, "history": [1000, 1100, 900, 1000]}, "TG")
    assert Flags.SPIKE not in normal["flags"]


def test_pas_de_controle_sans_historique():
    r = ScoreCalculator(formula()).score({"deltas": {"audiomack": 60000}, "history": [100]}, "TG")
    assert Flags.SPIKE not in r["flags"]


def test_mediane_sur_4_semaines():
    r = ScoreCalculator(formula()).score({"deltas": {"audiomack": 5500}, "history": [1000, 1000, 1000, 1000, 90000, 90000]}, "TG")
    assert Flags.SPIKE in r["flags"]


def test_ratio_vues_jaime():
    calc = ScoreCalculator(formula())
    assert Flags.YOUTUBE_RATIO in calc.score({"deltas": {"youtube": 200000}, "youtube_likes": 40}, "TG")["flags"]
    assert Flags.YOUTUBE_RATIO not in calc.score({"deltas": {"youtube": 200000}, "youtube_likes": 3000}, "TG")["flags"]
    assert Flags.YOUTUBE_RATIO not in calc.score({"deltas": {"youtube": 5000}, "youtube_likes": 0}, "TG")["flags"]


def test_decision_admin_fixe_le_statut():
    calc = ScoreCalculator(formula())
    spike = {"deltas": {"audiomack": 9000}, "history": [1000, 1000, 1000]}
    assert calc.score({**spike, "decision": "validated"}, "TG")["review_status"] == "validated"
    assert calc.score({**spike, "decision": "excluded"}, "TG")["review_status"] == "excluded"


# --- Classement et égalités ---

def test_prime_tri_et_taille():
    entries = ChartRanker(formula()).prime([item(1, 100), item(2, 300), item(3, 200), item(4, 50)], 3)
    assert ids(entries) == [2, 3, 1]
    assert [e["position"] for e in entries] == [1, 2, 3]


def test_egalite_plus_de_sources():
    assert ids(ChartRanker(formula()).prime([item(1, 500, 2), item(2, 500, 3)], 10)) == [2, 1]


def test_egalite_meilleure_progression():
    entries = ChartRanker(formula()).prime([item(1, 500, 2, prev_score=450.0), item(2, 500, 2, prev_score=100.0)], 10)
    assert ids(entries) == [2, 1]


def test_egalite_parfaite_ordre_stable():
    assert ids(ChartRanker(formula()).prime([item(9, 500), item(3, 500)], 10)) == [3, 9]


def test_exclus_et_scores_nuls_non_classes():
    entries = ChartRanker(formula()).prime([item(1, 900, 2, review_status="excluded"), item(2, 0), item(3, 10)], 10)
    assert ids(entries) == [3]


def test_titre_a_verifier_visible_dans_le_brouillon():
    assert ChartRanker(formula()).prime([item(1, 900, 2, review_status="pending")], 10)[0]["review_status"] == "pending"


def test_memoire_des_classements():
    entries = ChartRanker(formula()).prime([item(1, 900), item(2, 800)], 10, {
        1: {"position": 4, "peak": 2, "weeks": 5},
        2: {"position": None, "peak": 1, "weeks": 3},  # retour après une absence
    })
    assert [entries[0]["previous_position"], entries[0]["peak_position"], entries[0]["weeks_on_chart"]] == [4, 1, 6]
    assert [entries[1]["previous_position"], entries[1]["peak_position"], entries[1]["weeks_on_chart"]] == [None, 1, 4]


# --- Règle de diversité ---

def test_mono_source_plafonne_a_la_sixieme_place():
    items = [item(1, 10000, 1)] + [item(i, 1000 - i, 2) for i in range(2, 9)]
    entries = ChartRanker(formula()).prime(items, 10)
    assert entries[5]["track_id"] == 1
    assert Flags.DIVERSITY_CAPPED in entries[5]["flags"]
    assert ids(entries)[:5] == [2, 3, 4, 5, 6]


def test_mono_source_hors_top5_garde_sa_place():
    items = [item(i, 1000 - i, 2) for i in range(1, 7)] + [item(7, 500, 1)]
    entries = ChartRanker(formula()).prime(items, 10)
    assert entries[6]["track_id"] == 7
    assert entries[6]["flags"] == []


def test_top5_complete_sans_trou():
    entries = ChartRanker(formula()).prime([item(1, 9000, 1), item(2, 8000, 1), item(3, 100, 2), item(4, 50, 2)], 10)
    assert ids(entries) == [3, 4, 1, 2]
    assert Flags.DIVERSITY_FALLBACK in entries[2]["flags"]


# --- Buzz, Fresh, Icon, régional ---

def test_buzz():
    items = [item(1, 10000, 2, prev_score=5000.0), item(2, 6000, 2, prev_score=2000.0), item(3, 3000, 2, prev_score=1500.0),
             item(4, 1500, 2, prev_score=100.0), item(5, 3000, 2, prev_score=2500.0), item(6, 9000, 2, prev_score=0.0)]
    entries = ChartRanker(formula()).buzz(items, [1], 10)
    assert ids(entries) == [2, 3]
    assert entries[0]["growth_pct"] == 200.0


def test_fresh():
    items = [item(1, 900, 2, release_date="2026-09-01"), item(2, 800, 2, release_date="2026-01-01"),
             item(3, 700, 2, release_date="2025-06-01", is_emerging=True), item(4, 600, 2, release_date="2026-10-15")]
    assert ids(ChartRanker(formula()).fresh(items, "2026-09-27", 10)) == [1, 3]


def test_icon():
    items = [item(1, 500, 2, artist_id=7), item(2, 400, 2, artist_id=7), item(3, 800, 2, artist_id=8)]
    entries = ChartRanker(formula()).icon(items, 10)
    assert [e["artist_id"] for e in entries] == [7, 8]
    assert entries[0]["score"] == 900.0
    assert entries[0]["sources_count"] == 2


def test_regional_points():
    lst = ChartRanker.regional_points({"TG": [{"position": 1, "track_id": 1}, {"position": 2, "track_id": 2}],
                                       "BJ": [{"position": 1, "track_id": 2}, {"position": 11, "track_id": 1}]})
    assert lst[0]["track_id"] == 2
    assert lst[0]["points"] == 19
    assert lst[1]["points"] == 10, "la 11e place ne rapporte rien"


def test_mediane():
    assert ScoreCalculator.median([3, 1, 2]) == 2.0
    assert ScoreCalculator.median([4, 1, 2, 3]) == 2.5
