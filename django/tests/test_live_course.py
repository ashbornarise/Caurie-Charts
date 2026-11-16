"""La Course des Cauris v2 (16/11/2026) : route verticale, 4 pays, même vitesse au départ, rose = boost, 10 pièces = bousculer."""
import time

from core import live


def _etat(depart_passe=True):
    e = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in live.ETAT_DEFAUT.items()}
    live.course_action(e, "demarre")
    if depart_passe:   # on saute le compte à rebours
        e["course"]["t"] = int(time.time() * 1000)
    return e


def _pos(e, p):
    return live.course_pos(e["course"], p)


def test_manche_de_quatre_pays_meme_vitesse():
    e = _etat()
    c = e["course"]
    assert c["on"] and c["phase"] == "course" and c["pays"] == live.COURSE_GROUPES[0]
    c["t"] -= 10_000   # 10 s de course
    assert {round(_pos(e, p), 1) for p in c["pays"]} == {round(10 * live.COURSE_VITESSE, 1)}


def test_compte_a_rebours_on_ne_bouge_pas():
    e = _etat(depart_passe=False)
    live.course_commentaire(e, "a1", "Awa", "CIV", live._norm("CIV"))
    assert _pos(e, "ci") == 0 and e["course"]["bonus"]["ci"] == 0


def test_commentaire_fait_accelerer_son_pays():
    e = _etat()
    assert live.course_commentaire(e, "a1", "Awa", "Allez la Côte d'Ivoire !", live._norm("Allez la Côte d'Ivoire !"))
    assert live.course_commentaire(e, "a2", "Kofi", "🇹🇬🇹🇬", live._norm("🇹🇬🇹🇬"))
    assert live.course_commentaire(e, "a3", "Paul", "CMR", live._norm("CMR"))
    b = e["course"]["bonus"]
    assert b["ci"] == b["tg"] == b["cm"] == live.COURSE_PAS and b["bj"] == 0


def test_pays_hors_manche_texte_libre_et_insultes_ignores():
    e = _etat()
    assert not live.course_commentaire(e, "a1", "Awa", "Nigeria", live._norm("Nigeria"))
    assert not live.course_commentaire(e, "a1", "Awa", "trop bien ce live", live._norm("trop bien ce live"))
    assert not live._insulte("Conakry représente") and not live._insulte("c'est pas nul")
    assert live.course_commentaire(e, "a1", "Awa", "Togo nul", live._norm("Togo nul"))
    assert all(v == 0 for v in e["course"]["bonus"].values())


def test_anti_spam_et_victoire():
    e = _etat()
    t = live._norm("bénin")
    live.course_commentaire(e, "a1", "Awa", "bénin", t)
    live.course_commentaire(e, "a1", "Awa", "bénin", t)   # trop tôt : ne compte pas
    assert e["course"]["bonus"]["bj"] == live.COURSE_PAS
    e["course"]["bonus"]["bj"] = 99.9
    e["course"]["vu"] = {}
    live.course_commentaire(e, "a1", "Awa", "bénin", t)
    c = e["course"]
    assert c["phase"] == "fin" and c["gagnant"] == "bj" and c["victoires"]["bj"] == 1 and c["posFin"]["bj"] == 100


def test_rose_boost_et_gros_cadeau_bouscule_celui_de_devant():
    e = _etat()
    live.course_commentaire(e, "a1", "Awa", "civ", live._norm("civ"))
    live.course_cadeau(e, "a1", "Awa", 1)   # une rose
    assert e["course"]["boost"]["code"] == "ci" and e["course"]["bonus"]["ci"] == live.COURSE_PAS + 3
    e["course"]["bonus"]["cm"] = 20   # le Cameroun est devant
    live.course_cadeau(e, "a1", "Awa", 10)
    assert e["course"]["choc"]["vers"] == "cm" and e["course"]["bonus"]["cm"] == 16


def test_le_leader_bouscule_le_plus_proche_derriere():
    e = _etat()
    live.course_commentaire(e, "a1", "Awa", "togo", live._norm("togo"))
    e["course"]["bonus"].update({"tg": 30, "ci": 10, "bj": 25, "cm": 5})
    live.course_cadeau(e, "a1", "Awa", 100)
    assert e["course"]["choc"]["vers"] == "bj" and e["course"]["bonus"]["bj"] == 25 - 8


def test_likes_aident_le_dernier():
    e = _etat()
    e["course"]["bonus"].update({"ci": 5, "tg": 5, "bj": 0, "cm": 5})
    live.course_likes(e, 160)
    assert e["course"]["aide"]["code"] == "bj" and e["course"]["bonus"]["bj"] == 2


def test_arrivee_a_vitesse_egale_puis_manche_suivante():
    e = _etat()
    e["course"]["bonus"]["cm"] = 1
    e["course"]["t"] -= int(100 / live.COURSE_VITESSE * 1000)
    assert live.course_a_avancer(e)
    live.course_tick(e)
    assert e["course"]["gagnant"] == "cm"
    e["course"]["tFin"] = int(time.time() * 1000) - (live.COURSE_PAUSE + 1) * 1000
    live.course_tick(e)
    assert e["course"]["manche"] == 2 and e["course"]["pays"] == live.COURSE_GROUPES[1] and e["course"]["victoires"] == {"cm": 1}


def test_etat_public_ne_montre_pas_les_joueurs():
    e = _etat()
    live.course_commentaire(e, "a1", "Awa", "togo", live._norm("togo"))
    p = live._public(e)
    assert "joueurs" not in p["course"] and "vu" not in p["course"] and "courseFan" not in p
    assert p["course"]["top"][0]["nom"] == "Awa" and p["course"]["srv"] > 0
