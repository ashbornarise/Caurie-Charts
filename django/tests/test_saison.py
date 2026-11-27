"""Logos de saison (27/11/2026) : le bonnet de Noël du 27 novembre au 6 janvier, l'officiel revient le 7."""
from datetime import date
from pathlib import Path

from core import saison

MARQUE = Path(__file__).resolve().parents[2] / "resources" / "marque"


def test_dates_de_la_saison():
    assert not saison.noel(date(2026, 11, 26))
    assert saison.noel(date(2026, 11, 27)) and saison.noel(date(2026, 12, 25)) and saison.noel(date(2027, 1, 6))
    assert not saison.noel(date(2027, 1, 7)) and not saison.noel(date(2027, 6, 1))


def test_nom_du_fichier_de_saison():
    assert saison.nom("favicon-32.png", date(2026, 12, 1)) == "favicon-32-noel.png"
    assert saison.nom("favicon-32.png", date(2027, 2, 1)) == "favicon-32.png"


def test_repli_sur_l_officiel_si_le_fichier_manque(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"x")
    assert saison.chemin(tmp_path, "logo.png", date(2026, 12, 1)).name == "logo.png"


def test_monogramme_blanc_carre_hors_saison_et_en_saison():
    hors = saison.monogramme_blanc(MARQUE, date(2027, 3, 1))
    assert hors.width == hors.height                       # le C seul, découpé en carré
    noel = saison.monogramme_blanc(MARQUE, date(2026, 12, 1))
    assert noel.width == noel.height and noel.size != hors.size   # le C coiffé du bonnet
