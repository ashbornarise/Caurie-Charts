"""Régie du live : adresse secrète, écran par jeton, état partagé, votes et mur (base simulée)."""
import json

import pytest
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.http import Http404
from django.test import RequestFactory

from core import live, studio

CHEMIN = "a" * 30
RF = RequestFactory()
DONNEES = {"semaine": "2026-W45", "pays": [], "n1_afrique_ouest": None,
           "artistes": [{"id": 5, "nom": "Himra", "cle": "himra"}, {"id": 711, "nom": "Jeune Lion", "cle": "jeunelion"},
                        {"id": 8, "nom": "Didi B", "cle": "didib"}]}


def _req(methode, donnees=None):
    r = RF.post("/", data=json.dumps(donnees or {}), content_type="application/json") if methode == "post" else RF.get("/")
    r.session = SessionStore()
    return r


@pytest.fixture(autouse=True)
def base(monkeypatch):
    stock = {}
    monkeypatch.setattr(studio, "chemin_secret", lambda: CHEMIN)
    monkeypatch.setattr(live, "_lit", lambda cle, defaut=None, verrou=False: stock.get(cle, defaut))
    monkeypatch.setattr(live.db, "atomic", __import__("contextlib").nullcontext)
    monkeypatch.setattr(live, "_ecrit", lambda cle, v, jours=3: stock.__setitem__(cle, json.loads(json.dumps(v))))
    monkeypatch.setattr(live, "donnees", lambda: DONNEES)
    live._memo.clear()
    return stock


def test_regie_refusee_sans_session(monkeypatch):
    monkeypatch.setattr(studio, "_utilisateur", lambda r, verrou=True: None)
    assert live.regie_etat(_req("post", {"set": {"scene": "mur"}}), CHEMIN).status_code == 403
    with pytest.raises(Http404):
        live.regie(_req("get"), "b" * 30)


def test_ecran_par_jeton_seulement():
    j = live.jeton_ecran()
    assert j and len(j) == 28
    assert live.ecran(_req("get"), j).status_code == 200
    with pytest.raises(Http404):
        live.ecran(_req("get"), "0" * 28)


def test_regie_par_lien_secret_sans_empreinte(base):
    j = live.jeton_regie()
    assert j and j != live.jeton_ecran()
    assert live.regie_lien(_req("get"), j).status_code == 200
    live.regie_lien_etat(_req("post", {"set": {"scene": "mur"}}), j)
    assert base[live.CLE_ETAT]["scene"] == "mur"
    with pytest.raises(Http404):
        live.regie_lien_etat(_req("post", {"set": {"scene": "fin"}}), live.jeton_ecran())   # le lien de l'écran ne pilote rien


def test_etat_partage_et_votes(monkeypatch, base):
    monkeypatch.setattr(studio, "_utilisateur", lambda r, verrou=True: {"id": 1, "role": "admin"})
    live.regie_etat(_req("post", {"set": {"scene": "versus", "inconnu": 1}}), CHEMIN)
    for user, txt in [("u1", "HIMRA !"), ("u1", "himra"), ("u2", "didi b"), ("u3", "2")]:
        live._memo.clear()
        live.regie_etat(_req("post", {"commentaire": {"user": user, "texte": txt}}), CHEMIN)
    e = base[live.CLE_ETAT]
    assert e["scene"] == "versus" and "inconnu" not in e
    assert e["votes"] == {"a": 1, "b": 2}        # un vote par personne
    live._memo.clear()
    assert json.loads(live.ecran_etat(_req("get"), live.jeton_ecran()).content)["votes"] == {"a": 1, "b": 2}


def test_mur_compte_les_artistes_hors_versus(monkeypatch, base):
    monkeypatch.setattr(studio, "_utilisateur", lambda r, verrou=True: {"id": 1, "role": "admin"})
    live.regie_etat(_req("post", {"set": {"scene": "mur"}}), CHEMIN)
    for txt in ["Jeune Lion svp", "jeune lion", "himra"]:
        live._memo.clear()
        live.regie_etat(_req("post", {"commentaire": {"user": "x", "texte": txt}}), CHEMIN)
    assert base[live.CLE_ETAT]["mur"] == [{"id": 711, "n": 2}, {"id": 5, "n": 1}]


def test_une_seule_regie_a_la_main(base):
    j = live.jeton_regie()
    def req(ident, corps):
        r = _req("post", corps); r.META["HTTP_X_REGIE"] = ident; return r
    assert live.regie_lien_etat(req("aaa", {"set": {"scene": "mur"}}), j).status_code == 200
    assert live.regie_lien_etat(req("bbb", {"set": {"scene": "fin"}}), j).status_code == 409      # l'autre regarde
    assert base[live.CLE_ETAT]["scene"] == "mur"
    assert live.regie_lien_etat(req("bbb", {"set": {"scene": "fin"}, "prendre": 1}), j).status_code == 200   # prendre la main
    assert base[live.CLE_ETAT]["scene"] == "fin" and base[live.CLE_ETAT]["maitre"]["id"] == "bbb"


def test_repetition_ne_touche_pas_l_antenne(base):
    j = live.jeton_regie()
    r = _req("post", {"set": {"scene": "versus"}}); r.GET = r.GET.copy(); r.GET["mode"] = "test"
    live.regie_lien_etat(r, j)
    assert base[live.CLE_ETAT + "-test"]["scene"] == "versus" and live.CLE_ETAT not in base


def test_cadeaux_classement_et_regles(base):
    j = live.jeton_regie()
    def envoi(corps):
        live._memo.clear(); return live.regie_commentaires(RF.post("/", data=json.dumps(corps), content_type="application/json"), j)
    envoi({"cadeaux": [{"user": "ama", "nom": "Ama", "cadeau": "Rose", "n": 3, "diamants": 3}], "spectateurs": 120, "likes": 40})
    e = base[live.CLE_ETAT]
    assert e["donateurs"]["ama"]["diamants"] == 3 and e["spectateurs"] == 120 and e["likes"] == 40 and not e.get("fx")   # petit cadeau : merci seulement
    envoi({"cadeaux": [{"user": "kofi", "nom": "Kofi", "cadeau": "Lion", "n": 1, "diamants": 29999}], "abonnes": ["x"]})
    e = base[live.CLE_ETAT]
    assert e["gong"] and e["fx"]["type"] == "confettis" and "KOFI" in e["mascotte"]["titre"] and e["abonnes"] == 1
    envoi({"set": {}, "cadeaux": [{"user": "ama", "cadeau": "Rose", "n": 1, "diamants": 1}]})
    assert base[live.CLE_ETAT]["donateurs"]["ama"]["diamants"] == 4


def _cmt(e, user, texte):
    live._commentaire(e, user, texte)


def test_devine_le_titre_premier_gagne():
    import time
    e = {**live.ETAT_DEFAUT, "jeu": {"type": "blind", "phase": "jeu", "cles": ["didib", "malade"], "t": time.time() * 1000, "duree": 30,
                                     "reponse": {"artiste": "Didi B", "titre": "Malade"}}, "mur": [], "devineurs": {}, "scene": "jeu"}
    _cmt(e, "a", "himra !"); assert e["jeu"]["phase"] == "jeu"
    _cmt(e, "b", "c'est Didi B"); assert e["jeu"]["gagnant"]["user"] == "b" and e["devineurs"]["b"]["points"] == 1
    _cmt(e, "c", "didi b"); assert e["jeu"]["gagnant"]["user"] == "b" and "c" not in e["devineurs"]
    assert e["mur"] == []   # pendant un jeu, les commentaires ne remplissent pas le mur


def test_roue_paris_et_tirage_serveur(monkeypatch):
    e = {**live.ETAT_DEFAUT, "jeu": {"type": "roue", "phase": "paris", "segments": ["Togo", "Ghana", "Nigeria"]}, "devineurs": {}}
    _cmt(e, "a", "2"); _cmt(e, "b", "nigeria"); _cmt(e, "a", "3")   # un seul pari par personne
    assert e["jeu"]["paris"] == {"a": [1, "a"], "b": [2, "b"]}
    monkeypatch.setattr(live.secrets, "randbelow", lambda n: 1)
    live._jeu_action(e, "lancer")
    assert e["jeu"]["resultat"] == 1 and e["jeu"]["gagnants"] == ["a"] and e["devineurs"]["a"]["points"] == 1
    assert "paris" not in live._public(e)["jeu"]


def test_sondage_et_pays_du_chat():
    e = {**live.ETAT_DEFAUT, "jeu": {"type": "sondage", "phase": "vote", "options": ["Feu", "Bof"], "votes": [0, 0]}}
    _cmt(e, "a", "1"); _cmt(e, "a", "2"); _cmt(e, "b", "bof")
    assert e["jeu"]["votes"] == [1, 1]
    e["jeu"] = {"type": "dou", "phase": "vote"}
    _cmt(e, "a", "Abidjan ici"); _cmt(e, "b", "Lomé"); _cmt(e, "c", "merci"); _cmt(e, "d", "Nigeria !")
    assert e["jeu"]["pays"] == {"ci": 1, "tg": 1, "ng": 1}


def test_roi_du_live_change_de_main():
    e = {**live.ETAT_DEFAUT, "donateurs": {}, "dernier": []}
    live._cadeau(e, {"user": "a", "nom": "Ama", "diamants": 10})
    assert e["roiActuel"]["user"] == "a" and not e.get("mascotte")
    live._cadeau(e, {"user": "b", "nom": "Kofi", "diamants": 50})
    assert e["roiActuel"]["user"] == "b" and "Kofi" in e["mascotte"]["texte"]


def test_tirage_au_sort_parmi_le_chat(monkeypatch):
    e = {**live.ETAT_DEFAUT, "chatteurs": [], "mur": [], "dernier": []}
    _cmt(e, "a", "salut"); _cmt(e, "b", "yo"); _cmt(e, "a", "re")
    assert [c[0] for c in e["chatteurs"]] == ["b", "a"]
    monkeypatch.setattr(live.secrets, "randbelow", lambda n: 0)
    live._jeu_action(e, "tirage"); assert e["tirage"]["user"] == "b"
