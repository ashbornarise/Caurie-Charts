"""Semaine du vendredi au jeudi, publiée le vendredi soir (décision du fondateur du 07/11/2026)."""
from core.services.charts import Period


def test_avant_la_bascule_du_lundi_au_dimanche():
    w = Period.week_of("2026-11-07")
    assert (w.key, w.start, w.end, w.publication_day()) == ("2026-W45", "2026-11-02", "2026-11-08", "2026-11-10")


def test_semaine_de_transition_de_4_jours():
    w = Period.week_of("2026-11-10")
    assert (w.key, w.start, w.end, w.publication_day()) == ("2026-W46", "2026-11-09", "2026-11-12", "2026-11-13")
    assert Period.week_from_key("2026-W46") == w


def test_vendredi_au_jeudi_ensuite():
    w = Period.week_of("2026-11-18")
    assert (w.key, w.start, w.end, w.publication_day()) == ("2026-W47", "2026-11-13", "2026-11-19", "2026-11-20")
    assert Period.week_from_key("2026-W47") == w
    assert w.previous().key == "2026-W46" and w.previous().previous().key == "2026-W45"


def test_derniere_semaine_terminee():
    assert Period.last_completed_week("2026-11-10").key == "2026-W45"   # dernier mardi de publication
    assert Period.last_completed_week("2026-11-13").key == "2026-W46"   # premier vendredi
    assert Period.last_completed_week("2026-11-17").key == "2026-W46"
    assert Period.last_completed_week("2026-11-20").key == "2026-W47"


def test_mois_et_annee():
    m = Period.month("2026-11")
    assert (m.start, m.end) == ("2026-10-26", "2026-11-26")
    assert m.week_starts() == ["2026-10-26", "2026-11-02", "2026-11-09", "2026-11-13", "2026-11-20"]
    d = Period.month("2026-12")
    assert (d.start, d.end) == ("2026-11-27", "2026-12-31")
    assert Period.month("2026-10").week_starts() == ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]
    assert Period.year("2027").start == "2027-01-01"
