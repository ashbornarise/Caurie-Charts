"""« Médias » du Studio (27/11/2026) : règles pures, sans base ni réseau."""
from core.services.social import studio_medias as M


def test_genre_selon_extension():
    assert M.genre_de("JPG") == "photo"
    assert M.genre_de(".mp4") == "video"
    assert M.genre_de("m4a") == "son"
    assert M.genre_de("exe") == "fichier"


def test_extension_nettoyee_et_refusee_si_inconnue():
    assert M.ext_propre("MoV") == "mov"
    assert M.ext_propre("j.p/g") == "jpg"
    assert M.ext_propre("exe") == "bin"
    assert M.ext_propre(None) == "bin"


def test_cle_de_dossier():
    assert M.dossier_cle("creations") == ("creations", None)
    assert M.dossier_cle("d12") == ("dossier", 12)
    assert M.dossier_cle("a34") == ("artiste", 34)
    assert M.dossier_cle("x1") == ("", None)
    assert M.dossier_cle("d1; DROP TABLE") == ("", None)


def test_lien_de_telechargement_direct():
    assert M.telecharger("https://b.example/x.mp4") == "https://b.example/x.mp4?download=1"
    assert M.telecharger("https://b.example/x.mp4?v=2") == "https://b.example/x.mp4?v=2&download=1"
    assert M.telecharger("") == ""


def test_credit_du_compte():
    assert M._credit({"uploader_id": "@sethloofficiel", "extractor_key": "Youtube"}) == "@sethloofficiel (Youtube)"
    assert M._credit({"extractor_key": "TikTok"}) == "TikTok"


# ---------------------------------------------------------------- 28/11/2026 : tests demandés par Yao (rapport « Médias »)
import json as _json
import pytest
from django.test import RequestFactory


def _vue(monkeypatch, connecte=True):
    from core import studio as S
    monkeypatch.setattr(S, "_verifie", lambda chemin: None)
    monkeypatch.setattr(S, "_utilisateur", lambda request, *a, **k: {"id": 1} if connecte else None)
    return S


@pytest.mark.parametrize("nom,args,methode", [
    ("medias", (), "get"), ("medias_dossier", (), "post"), ("medias_recuperer", (), "post"), ("medias_en_cours", (), "get"),
    ("medias_envoi", (), "post"), ("medias_morceau", ("1",), "post"), ("medias_fin", ("1",), "post"),
    ("medias_retirer", ("1",), "post"), ("medias_tache_fermer", ("1",), "post")])
def test_routes_medias_refusees_sans_connexion(monkeypatch, nom, args, methode):
    S = _vue(monkeypatch, connecte=False)
    req = getattr(RequestFactory(), methode)("/x")
    assert getattr(S, nom)(req, "secret", *args).status_code == 401


def test_fin_appelee_deux_fois_ne_casse_pas_le_media(monkeypatch):
    S = _vue(monkeypatch)
    from core import db
    ecrit = []
    monkeypatch.setattr(db, "value", lambda sql, params=None: "pret")
    monkeypatch.setattr(db, "run", lambda *a, **k: ecrit.append(a) or 0)
    r = S.medias_fin(RequestFactory().post("/x"), "secret", "7")
    assert r.status_code == 200 and _json.loads(r.content)["deja"] is True
    assert not ecrit   # jamais repassé en « erreur »


def test_fin_sur_un_envoi_inconnu(monkeypatch):
    S = _vue(monkeypatch)
    from core import db
    monkeypatch.setattr(db, "value", lambda sql, params=None: None)
    assert S.medias_fin(RequestFactory().post("/x"), "secret", "7").status_code == 400


def test_notification_quand_les_medias_sont_ranges(monkeypatch):
    from core import db
    from core.services import notif
    envois = []
    monkeypatch.setattr(db, "one", lambda sql, params=None: {"params": _json.dumps({"type": "medias", "dossier_id": 3})})
    monkeypatch.setattr(db, "value", lambda sql, params=None: "Sethlo")
    monkeypatch.setattr(notif, "envoie", lambda titre, texte, projet=None, etiquette=None: envois.append((titre, projet, etiquette)))
    notif.projet(12, "range")
    notif.projet(12, "pret")   # une récupération n'a pas d'état « prêt à publier »
    assert envois == [("Médias rangés : Sethlo", None, "medias-12")]   # aucun écran de projet vidéo ouvert
