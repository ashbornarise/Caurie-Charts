"""Légendes bilingues : français puis anglais, sans jamais perdre le lien ni les hashtags."""
from core.services.social import bilingue


def _post(n_lignes: int) -> dict:
    return {"id": None, "title": "Titre du post", "facts": "{}", "hashtags": "#CauriCharts #Test",
            "caption": "\n".join(f"Ligne {i} du texte français" for i in range(n_lignes)) + "\n\nLien en bio : cauricharts.com"}


def test_sans_traduction_le_post_part_en_francais(monkeypatch):
    monkeypatch.setattr(bilingue, "en", lambda post, budget: None)
    t = bilingue.legende(_post(3))
    assert t.startswith("Titre du post") and bilingue.DRAPEAU_EN not in t
    assert t.endswith("#CauriCharts #Test") and t.count("cauricharts.com") == 1   # un seul lien, bilingue


def test_anglais_ajoute_et_hashtags_jamais_coupes(monkeypatch):
    monkeypatch.setattr(bilingue, "en", lambda post, budget: {"title": "Post title", "caption": "English line\n" * 400})
    t = bilingue.legende(_post(200))
    assert len(t) <= 2200
    assert f"{bilingue.DRAPEAU_EN} Post title" in t
    assert t.endswith("#CauriCharts #Test") and bilingue.LIEN in t
