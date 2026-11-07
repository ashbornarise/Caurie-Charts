"""Formule v4 normalisée (décision du fondateur du 06/11/2026) : 50 % YouTube, 50 % écoute partagés entre les sources
relevées ; une source absente du pays n'est pas un zéro."""
from core.services import chart_service as CS
from core.services.charts import ChartRanker, Period

F = {"normalisation": {"youtube": 0.5, "streaming": 0.5}}


def _item(tid, yt=0, apple=0, boom=0):
    b = {}
    if yt:
        b["youtube"] = {"delta": yt}
    if apple:
        b["chart:apple_music"] = {"delta": apple}
    if boom:
        b["chart:boomplay"] = {"delta": boom}
    return {"track_id": tid, "score": yt * 0.5 + (apple + boom) * 150, "prev_score": 0, "breakdown": b}


def _calcule(items, monkeypatch):
    monkeypatch.setattr(CS.db, "all", lambda *a, **k: [])
    monkeypatch.setattr(CS.db, "run", lambda *a, **k: None)
    CS.ChartService.__new__(CS.ChartService)._normalise(items, F, 4, Period.week_of("2026-11-09"))
    return {i["track_id"]: i for i in items}


def test_apple_et_boomplay_25_pourcent_chacun(monkeypatch):
    r = _calcule([_item(1, yt=1000, apple=80, boom=60), _item(2, yt=3000, apple=20, boom=40)], monkeypatch)
    assert r[1]["breakdown"]["_v4"]["poids"] == {"youtube": 0.5, "apple_music": 0.25, "boomplay": 0.25}
    # titre 1 : 25 % des vues, 80 % d'Apple, 60 % de Boomplay -> 0,5×0,25 + 0,25×0,8 + 0,25×0,6 = 0,475
    assert r[1]["score"] == 4750 and r[2]["score"] == 5250
    assert r[1]["score_brut"] == 1000 * 0.5 + 140 * 150   # le score brut reste pour les alertes et le Buzz


def test_une_seule_source_d_ecoute_porte_50_pourcent(monkeypatch):
    r = _calcule([_item(1, yt=1000, boom=50), _item(2, yt=1000, boom=50)], monkeypatch)
    assert r[1]["breakdown"]["_v4"]["poids"] == {"youtube": 0.5, "boomplay": 0.5}


def test_source_absente_n_est_pas_un_zero(monkeypatch):
    # aucun clip suivi dans le pays : Apple porte tout, sans pénaliser les titres
    r = _calcule([_item(1, apple=90), _item(2, apple=10)], monkeypatch)
    assert r[1]["breakdown"]["_v4"]["poids"] == {"apple_music": 1.0} and r[1]["score"] == 9000


def test_zero_si_relevee_mais_absent(monkeypatch):
    r = _calcule([_item(1, yt=1000, apple=50), _item(2, yt=1000)], monkeypatch)
    assert r[2]["breakdown"]["_v4"]["parts"]["apple_music"] == 0


def test_buzz_titres_verifies_seulement():
    f = {"buzz": {"min_growth_pct": 50, "min_score": 0}, "buzz_verifies": True, "diversity": {"top": 0, "min_sources": 1}}
    items = [{"track_id": 1, "artist_id": 1, "score": 10, "score_brut": 300, "prev_brut": 100, "prev_score": 5,
              "sources_count": 2, "flags": [], "review_status": "pending"},
             {"track_id": 2, "artist_id": 2, "score": 9, "score_brut": 250, "prev_brut": 100, "prev_score": 5,
              "sources_count": 2, "flags": [], "review_status": "ok"}]
    assert [e["track_id"] for e in ChartRanker(f).buzz(items, [], 10)] == [2]


def test_buzz_sans_titres_anciens():
    # 07/11/2026 : « Dati the wood » (2014) était au Buzz du Togo ; seuls les titres de moins d'un an y entrent
    f = {"buzz": {"min_growth_pct": 50, "min_score": 0, "max_age_days": 365}, "diversity": {"top": 0, "min_sources": 1}}
    items = [{"track_id": 1, "artist_id": 1, "score": 300, "prev_score": 100, "sources_count": 2, "flags": [],
              "review_status": "ok", "release_date": "2014-10-25"},
             {"track_id": 2, "artist_id": 2, "score": 300, "prev_score": 100, "sources_count": 2, "flags": [],
              "review_status": "ok", "release_date": "2026-09-20"}]
    assert [e["track_id"] for e in ChartRanker(f).buzz(items, [], 10, ref="2026-11-08")] == [2]


def test_fresh_seuil_minimum():
    f = {"fresh": {"max_age_days": 56, "min_score": 500}, "diversity": {"top": 0, "min_sources": 1}}
    items = [{"track_id": 1, "artist_id": 1, "score": 12.5, "sources_count": 1, "flags": [], "review_status": "ok", "release_date": "2026-10-20"},
             {"track_id": 2, "artist_id": 2, "score": 900, "sources_count": 1, "flags": [], "review_status": "ok", "release_date": "2026-10-20"}]
    assert [e["track_id"] for e in ChartRanker(f).fresh(items, "2026-11-08", 10)] == [2]
