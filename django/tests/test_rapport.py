from datetime import date

from core.services import rapport


def test_garde_fou_refuse_les_chiffres_absents(monkeypatch):
    data = {"semaine": {"debut": "2026-10-05", "fin": "2026-10-11", "posts_crees": 12,
                        "visites": 4, "releves_classements": 3, "classements_officiels_publies": 1,
                        "nuits": 5, "etapes_en_echec": [], "videos_fans": 0}}

    class IA:
        def ask(self, *args, **kwargs):
            return {"text": "La semaine compte 999 posts."}

    texte = rapport.rediger(data, IA())
    assert "999" not in texte
    assert "12 posts créés" in texte


def test_echeances_du_mois_suivant():
    couts = [{"nom": "à échéance", "prochaine_echeance": "2026-11-30"},
             {"nom": "trop tôt", "prochaine_echeance": "2026-10-31"},
             {"nom": "inconnue", "prochaine_echeance": None}]
    assert rapport.echeances_mois_suivant(couts, date(2026, 10, 18)) == [couts[0]]
