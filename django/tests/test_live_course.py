"""La Course des Cauris (16/11/2026) : 4 pays par manche, que du positif, insultes ignorées."""
import time

from core import live


def _etat():
    e = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in live.ETAT_DEFAUT.items()}
    live.course_action(e, "demarre")
    return e


def test_manche_de_quatre_pays():
    e = _etat()
    c = e["course"]
    assert c["on"] and c["phase"] == "course" and len(c["pays"]) == 4
    assert c["pays"] == live.COURSE_GROUPES[0]


def test_commentaire_fait_avancer_son_pays():
    e = _etat()
    assert live.course_commentaire(e, "a1", "Awa", "Allez la Côte d'Ivoire !", live._norm("Allez la Côte d'Ivoire !"))
    assert e["course"]["pos"]["ci"] == 1
    assert live.course_commentaire(e, "a2", "Kofi", "🇹🇬🇹🇬", live._norm("🇹🇬🇹🇬"))
    assert e["course"]["pos"]["tg"] == 1
    assert live.course_commentaire(e, "a3", "Paul", "CMR", live._norm("CMR"))
    assert e["course"]["pos"]["cm"] == 1


def test_pays_hors_manche_et_texte_libre_ignores():
    e = _etat()
    assert not live.course_commentaire(e, "a1", "Awa", "Nigeria", live._norm("Nigeria"))   # pas dans cette manche
    assert not live.course_commentaire(e, "a1", "Awa", "trop bien ce live", live._norm("trop bien ce live"))
    assert all(v == 0 for v in e["course"]["pos"].values())


def test_conakry_n_est_pas_une_insulte_mais_les_insultes_ne_comptent_pas():
    assert not live._insulte("Conakry représente")
    assert live._insulte("le togo c'est nul", True) and not live._insulte("c'est pas nul")
    e = _etat()
    assert live.course_commentaire(e, "a1", "Awa", "Togo nul", live._norm("Togo nul"))
    assert e["course"]["pos"]["tg"] == 0


def test_anti_spam_et_victoire():
    e = _etat()
    t = live._norm("bénin")
    live.course_commentaire(e, "a1", "Awa", "bénin", t)
    live.course_commentaire(e, "a1", "Awa", "bénin", t)   # trop tôt : ne compte pas
    assert e["course"]["pos"]["bj"] == 1
    e["course"]["pos"]["bj"] = 99
    e["course"]["vu"] = {}
    live.course_commentaire(e, "a1", "Awa", "bénin", t)
    assert e["course"]["phase"] == "fin" and e["course"]["gagnant"] == "bj"
    assert e["course"]["victoires"]["bj"] == 1


def test_cadeau_turbo_pour_son_pays_et_likes_aident_le_dernier():
    e = _etat()
    live.course_commentaire(e, "a1", "Awa", "civ", live._norm("civ"))
    live.course_cadeau(e, "a1", "Awa", 1)   # une rose
    assert e["course"]["pos"]["ci"] == 1 + 3
    live.course_likes(e, 100)
    assert e["course"]["aide"]["code"] != "ci"
    assert max(e["course"]["pos"][p] for p in e["course"]["pays"] if p != "ci") == 2


def test_fin_du_temps_puis_manche_suivante():
    e = _etat()
    e["course"]["pos"]["cm"] = 10
    e["course"]["fin"] = int(time.time() * 1000) - 1
    live.course_tick(e)
    assert e["course"]["gagnant"] == "cm"
    e["course"]["tFin"] = int(time.time() * 1000) - (live.COURSE_PAUSE + 1) * 1000
    live.course_tick(e)
    assert e["course"]["manche"] == 2 and e["course"]["pays"] == live.COURSE_GROUPES[1]
    assert e["course"]["victoires"] == {"cm": 1}


def test_etat_public_ne_montre_pas_les_joueurs():
    e = _etat()
    live.course_commentaire(e, "a1", "Awa", "togo", live._norm("togo"))
    p = live._public(e)
    assert "joueurs" not in p["course"] and "vu" not in p["course"] and "courseFan" not in p
    assert p["course"]["top"][0]["nom"] == "Awa"
