from datetime import date

from core.services import rapport_pdf, stats_reseaux


def test_stats_indisponibles_si_api_meta_et_telegram_en_erreur(monkeypatch):
    monkeypatch.setattr(stats_reseaux.env, "get", lambda key, default="": {
        "META_ACCESS_TOKEN": "fake", "META_PAGE_ID": "page", "META_IG_ID": "ig",
        "TELEGRAM_CHAT_ID": "chat"}.get(key, default))
    monkeypatch.setattr(stats_reseaux, "_get", lambda *args, **kwargs: {})
    monkeypatch.setattr(stats_reseaux.telegram, "call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("hors ligne")))
    monkeypatch.setattr(stats_reseaux.db, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(stats_reseaux.db, "all", lambda *args, **kwargs: [])
    valeurs = stats_reseaux.collecter(date(2026, 10, 18))
    assert valeurs["instagram"]["followers_count"] == "non disponible"
    assert valeurs["instagram"]["insights"]["reach"] == "non disponible"
    assert valeurs["facebook"]["insights"]["page_impressions_unique"] == "non disponible"
    assert valeurs["telegram"]["member_count"] == "non disponible"


def test_pdf_factice_produit_un_fichier_non_vide(tmp_path):
    pytest = __import__("pytest")
    pytest.importorskip("playwright")
    data = {"semaine": {"debut": "2026-10-12", "fin": "2026-10-18", "posts_crees": 3, "visites": 40,
                        "posts_par_reseau": {"instagram": {"crees": 2, "envoyes": 2}},
                        "metriques_posts": [{"titre": "Exemple de publication", "reseau": "Instagram", "vues": 80, "portee": 65}],
                        "visites_par_jour": [{"jour": "2026-10-12", "vues": 4}], "pages_plus_vues": []},
            "semaine_precedente": {}, "depenses_semaine": [], "echeances_mois_prochain": [],
            "reseaux_stats": {"instagram": {"followers_count": 123}, "facebook": {"followers_count": 45},
                              "telegram": {"member_count": 12}}}
    sortie = tmp_path / "exemple.pdf"
    rapport_pdf.generer(data, "Résumé d’exemple.", sortie, exemple=True)
    assert sortie.exists() and sortie.stat().st_size > 0
