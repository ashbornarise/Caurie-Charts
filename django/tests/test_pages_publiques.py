"""Les pages publiques s'affichent en français et en anglais (06/11/2026 : une erreur de gabarit dans le pied de page
a mis tout le site en erreur 500 ; aucun test n'affichait une page complète)."""
import pytest
from django.test import Client

PAGES = ["/", "/a-propos", "/methodologie", "/classements/afrique-de-l-ouest", "/cookies", "/contact", "/pays", "/tendances", "/artistes", "/artistes?pays=tg&tri=spotify", "/artistes?q=did", "/classements/ci/prime", "/classement-complet", "/classement-complet?pays=ci", "/classement-complet?pays=ci&semaine=2026-W44&page=2"]


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("langue", ["", "/en"])
def test_page_s_affiche(page, langue, monkeypatch):
    from core.services import analytics
    monkeypatch.setattr(analytics, "count_view", lambda *a, **k: None)   # pas de fausse visite en base
    from django.conf import settings
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["*"])
    r = Client().get(langue + page if (page != "/" or not langue) else "/en/")
    assert r.status_code == 200, f"{langue + page} : {r.status_code}"
    assert b'class="site-footer pied' in r.content
