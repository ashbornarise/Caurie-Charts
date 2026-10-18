"""Regroupement et fenêtre temporelle de la veille événementielle."""
from datetime import datetime, timedelta, timezone

from core.services.social import evenements as E


def article(titre, source, date):
    return {"title": titre, "source": source, "date": date, "poids": 2, "url": "https://example.com/article"}


def test_regroupe_un_evenement_cite_par_deux_medias():
    maintenant = datetime.now(timezone.utc)
    items = [
        article("Dominique Ouattara accueille le gala Children of Africa à Abidjan", "Media A", maintenant),
        article("Le gala Children of Africa de Dominique Ouattara réunit les invités", "Media B", maintenant - timedelta(hours=3)),
        article("Un festival de cinéma s'ouvre à Dakar", "Media C", maintenant),
    ]

    resultats = E.regroupe(items)

    assert len(resultats) == 1
    assert resultats[0]["sources"] == ["Media A", "Media B"]
    assert "gala" in resultats[0]["nom"].lower()


def test_regroupe_ecarte_articles_hors_des_sept_derniers_jours():
    maintenant = datetime.now(timezone.utc)
    items = [
        article("Gala Children of Africa à Abidjan", "Media A", maintenant),
        article("Gala Children of Africa organisé à Abidjan", "Media B", maintenant - timedelta(days=8)),
    ]

    assert E.regroupe(items) == []
