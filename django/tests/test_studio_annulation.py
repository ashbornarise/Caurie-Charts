"""Studio : annulation réelle (le montage s'arrête à l'étape suivante, ne repasse jamais « prêt »)."""
import pytest

from core.services.social import studio_montage as SM


def test_tache_annulee_arrete_le_montage(monkeypatch):
    monkeypatch.setattr(SM.db, "value", lambda *a, **k: "annule")
    monkeypatch.setattr(SM.db, "update", lambda *a, **k: pytest.fail("état réécrit après annulation"))
    with pytest.raises(SM.TacheAnnulee):
        SM._maj(7, statut="pret")


def test_tache_active_continue(monkeypatch):
    ecrit = {}
    monkeypatch.setattr(SM.db, "value", lambda *a, **k: "montage")
    monkeypatch.setattr(SM.db, "update", lambda table, champs, *a, **k: ecrit.update(champs))
    SM._maj(7, statut="pret", video="v.mp4")
    assert ecrit == {"statut": "pret", "video": "v.mp4"}
