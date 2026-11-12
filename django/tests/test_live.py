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
    monkeypatch.setattr(live, "_lit", lambda cle, defaut=None: stock.get(cle, defaut))
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
