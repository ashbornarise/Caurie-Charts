"""Course des Cauris (27/11/2026) : voitures d'artistes, départ donné par la régie, pas de manche automatique."""
import pytest

from core import live as L

DONNEES = {"artistes": [{"id": 8, "nom": "Didi B", "cle": "didi b", "photo": "didi.jpg"},
                        {"id": 5, "nom": "Himra", "cle": "himra", "photo": "himra.jpg"}]}


@pytest.fixture
def jeu(monkeypatch):
    t = {"ms": 5_000_000}
    monkeypatch.setattr(L, "_maintenant", lambda: t["ms"])
    monkeypatch.setattr(L, "donnees", lambda: DONNEES)
    return t


def test_preparer_affiche_la_grille_sans_partir(jeu):
    e = {}
    L.course_action(e, "prepare", None, [8, 5])
    c = e["course"]
    assert c["attente"] and c["pays"] == ["a8", "a5"] and c["noms"] == {"a8": "Didi B", "a5": "Himra"}
    assert c["artistes"]["a8"]["photo"] == "didi.jpg" and c["artistes"]["a5"]["num"] == "2"
    jeu["ms"] += 60_000
    assert L.course_pos(c, "a8") == 0   # une minute plus tard, personne n'a bougé


def test_le_public_choisit_son_pilote_avant_le_depart(jeu):
    e = {}
    L.course_action(e, "prepare", None, [8, 5])
    assert L.course_commentaire(e, "ama", "Ama", "allez didi !", L._norm("allez didi !"))
    assert L.course_commentaire(e, "kofi", "Kofi", "2", "2")
    assert e["course"]["joueurs"] == {"ama": "a8", "kofi": "a5"}
    assert e["course"]["bonus"] == {"a8": 0.0, "a5": 0.0}   # inscrits, mais personne n'avance avant le départ


def test_lancer_puis_avancer(jeu):
    e = {}
    L.course_action(e, "prepare", None, [8, 5])
    L.course_action(e, "lance")
    assert not e["course"]["attente"]
    jeu["ms"] += (L.COURSE_DEPART + 1) * 1000
    L.course_commentaire(e, "ama", "Ama", "himra", "himra")
    assert e["course"]["bonus"]["a5"] > 0


def test_pas_de_manche_suivante_automatique(jeu):
    e = {}
    L.course_action(e, "prepare", None, [8, 5])
    L.course_action(e, "lance")
    jeu["ms"] += (L.COURSE_DEPART + 1) * 1000
    e["course"]["bonus"]["a8"] = 100
    L.course_tick(e)
    assert e["course"]["phase"] == "fin" and e["course"]["gagnant"] == "a8"
    jeu["ms"] += 600_000
    L.course_tick(e)
    assert e["course"]["phase"] == "fin" and e["course"]["manche"] == 1   # toujours l'écran de victoire
    L.course_action(e, "suivante")
    assert e["course"]["manche"] == 2 and e["course"]["attente"] and e["course"]["pays"] == ["a8", "a5"]   # revanche, en attente


def test_mode_pays_toujours_possible(jeu):
    e = {}
    L.course_action(e, "prepare", ["tg", "bj"], None)
    assert e["course"]["pays"] == ["tg", "bj"] and not e["course"]["artistes"] and e["course"]["attente"]
