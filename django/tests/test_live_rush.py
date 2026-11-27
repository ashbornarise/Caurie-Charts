"""Cauri Rush (27/11/2026) : la logique du jeu, sans base ni réseau (l'heure est simulée)."""
import pytest

from core import live_rush as R

PAYS = {"tg": "Togo", "bj": "Bénin", "gh": "Ghana", "ci": "Côte d'Ivoire"}
DATA = {"pays": [{"code": "tg", "nom": "Togo", "artistes": [{"id": 14, "nom": "Sethlo", "cle": "sethlo", "photo": "x.jpg"},
                                                             {"id": 473, "nom": "Joachin Migos", "cle": "joachin migos", "photo": ""}]},
                 {"code": "ci", "nom": "Côte d'Ivoire", "artistes": [{"id": 8, "nom": "Didi B", "cle": "didi b", "photo": ""},
                                                                     {"id": 5, "nom": "Himra", "cle": "himra", "photo": ""}]}]}


@pytest.fixture
def horloge(monkeypatch):
    t = {"ms": 1_000_000}
    monkeypatch.setattr(R, "_now", lambda: t["ms"])
    return t


def _partie(horloge, type_="classement"):
    e = {}
    R.action(e, "demarre", type_, DATA, PAYS)
    horloge["ms"] += (R.DEPART + 1) * 1000   # après le compte à rebours
    return e


def test_duels_du_classement(horloge):
    d = R.duels("classement", DATA, PAYS)
    assert d[0]["equipes"][0]["nom"] == "Sethlo" and d[0]["equipes"][1]["nom"] == "Joachin Migos"
    assert any(x["titre"] == "Les N°1 s'affrontent" for x in d)


def test_rejoindre_en_ecrivant_1_2_ou_un_nom(horloge):
    e = _partie(horloge)
    assert R.commentaire(e, "ama", "Ama", "1")
    horloge["ms"] += 2000
    assert R.commentaire(e, "kofi", "Kofi", "allez joachin !")
    assert e["rush"]["fans"] == {"ama": "1", "kofi": "2"}
    assert not R.commentaire(e, "yao", "Yao", "bonsoir tout le monde")   # pas un choix d'équipe


def test_qui_tape_sans_ecrire_va_dans_l_equipe_qui_a_le_moins_de_fans(horloge):
    e = _partie(horloge)
    R.commentaire(e, "a", "A", "1"); horloge["ms"] += 2000; R.commentaire(e, "b", "B", "1")
    R.likes(e, {"silencieux": 30}, 30)
    assert e["rush"]["fans"]["silencieux"] == "2"


def test_sprint_final_double_les_jaime(horloge):
    e = _partie(horloge)
    R.commentaire(e, "a", "A", "1")
    avant = e["rush"]["bonus"]["1"]
    R.likes(e, {"a": 30}, 30)
    normal = e["rush"]["bonus"]["1"] - avant
    horloge["ms"] = e["rush"]["t"] + (R.DUREE - 5) * 1000    # dans les 20 dernières secondes
    avant = e["rush"]["bonus"]["1"]
    R.likes(e, {"a": 30}, 30)
    assert e["rush"]["bonus"]["1"] - avant == pytest.approx(2 * normal)


def test_anti_robot_plafond_par_paquet(horloge):
    e = _partie(horloge)
    R.commentaire(e, "a", "A", "1")
    avant = e["rush"]["bonus"]["1"]
    R.likes(e, {"a": 100000}, 100000)
    assert e["rush"]["bonus"]["1"] - avant == pytest.approx(R.MAX_PAQUET)


def test_victoire_au_sommet_puis_attente(horloge):
    e = _partie(horloge)
    R.commentaire(e, "a", "Ama", "2")
    e["rush"]["bonus"]["2"] = 100
    R.tick(e)
    r = e["rush"]
    assert r["phase"] == "fin" and r["gagnant"] == "2" and r["meilleur"] == "Ama" and r["victoires"] == {"Joachin Migos": 1}
    horloge["ms"] += (R.PAUSE + 1) * 1000
    R.tick(e)
    assert e["rush"]["phase"] == "attente"


def test_fin_du_temps_la_tete_gagne(horloge):
    e = _partie(horloge)
    e["rush"]["bonus"]["1"] = 5
    horloge["ms"] = e["rush"]["t"] + R.DUREE * 1000 + 10
    R.tick(e)
    assert e["rush"]["gagnant"] == "1"


def test_cadeau_pousse_sans_rien_promettre_et_revanche(horloge):
    e = _partie(horloge)
    R.cadeau(e, "rose_fan", "Rose", 1)
    assert e["rush"]["boost"]["pas"] == 3.0
    R.action(e, "revanche", "", DATA, PAYS)
    assert e["rush"]["manche"] == 2 and e["rush"]["bonus"] == {"1": 0.0, "2": 0.0}


def test_pas_deux_fois_le_meme_duel(horloge):
    e = {}
    R.action(e, "demarre", "classement", DATA, PAYS)
    premier = e["rush"]["cle"]
    R.action(e, "suivante", "", DATA, PAYS)
    assert e["rush"]["cle"] != premier


def test_l_ecran_ne_recoit_pas_la_liste_des_joueurs(horloge):
    e = _partie(horloge)
    R.commentaire(e, "a", "A", "1")
    p = R.public(e["rush"])
    assert "fans" not in p and "vu" not in p and set(p["pos"]) == {"1", "2"}


def test_drapeau_emoji_choisit_le_pays(horloge):
    e = {}
    R.demarre(e, R.duels("pays", DATA, PAYS)[0], "pays")   # Togo contre Bénin
    horloge["ms"] += (R.DEPART + 1) * 1000
    assert R.commentaire(e, "x", "X", "\U0001F1E7\U0001F1EF")   # 🇧🇯
    assert e["rush"]["fans"]["x"] == "2"
