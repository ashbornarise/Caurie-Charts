"""Guet Cauri Monde (toutes les 10 min) : il lit l'état du Blob et laisse dormir la base Neon (facture du 21/10/2026)."""
from datetime import datetime, timedelta, timezone

import pytest

from core import db, storage
from core.services.social import monde as M


def _sans_base(monkeypatch):
    for nom in ("all", "one", "value", "run", "insert"):
        monkeypatch.setattr(M.db, nom, lambda *a, **k: pytest.fail("la base a été réveillée"))


def _etat(**extra):
    return {"maj": datetime.now(timezone.utc).isoformat(), "prochain": None, "cles": ["abc123"],
            "artistes": [{"name": "Toofan", "code": "TG"}], **extra}


class Reponse:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


def test_guet_sans_nouveaute_ne_touche_pas_la_base(monkeypatch):
    _sans_base(monkeypatch)
    vus = {}
    monkeypatch.setattr(M, "collecte", lambda heures, artistes=None: vus.update(artistes=artistes) or [])
    monkeypatch.setattr(M, "_kworb", lambda: [])
    assert M.guette_leger(_etat()) is None
    assert vus["artistes"] == [{"name": "Toofan", "code": "TG"}]   # artistes de l'état, pas de la base


def test_info_deja_connue_ne_reveille_pas_la_base(monkeypatch):
    _sans_base(monkeypatch)
    histoire = {"cle": "abc123", "sources": ["A", "B", "C"]}
    monkeypatch.setattr(M, "collecte", lambda heures, artistes=None: ["x"])
    monkeypatch.setattr(M, "regroupe", lambda items: [histoire])
    monkeypatch.setattr(M, "_kworb", lambda: [])
    assert M.guette_leger(_etat()) is None


def test_info_nouvelle_passe_la_main_a_la_base(monkeypatch):
    histoire = {"cle": "neuve0000001", "sources": ["A", "B", "C"]}
    monkeypatch.setattr(M, "collecte", lambda heures, artistes=None: ["x"])
    monkeypatch.setattr(M, "regroupe", lambda items: [histoire])
    monkeypatch.setattr(M, "_kworb", lambda: [])
    appels = []
    monkeypatch.setattr(M, "guette", lambda: appels.append("guette") or {"choc": 90})
    monkeypatch.setattr(M, "etat_guet", lambda force=False: appels.append(("etat", force)) or _etat())
    assert M.guette_leger(_etat()) == {"choc": 90}
    assert appels == ["guette", ("etat", True)]


def test_caps_streams_avec_cles_connues_sans_base(monkeypatch):
    monkeypatch.setattr(M, "deja_publie", lambda cle: pytest.fail("la base a été réveillée"))
    monkeypatch.setattr(M, "_kworb", lambda: [("Burna Boy", 10001.0, 5.0)])
    caps = M.caps_streams(0, set())
    assert caps and caps[0]["artiste"] == "Burna Boy"
    assert M.caps_streams(0, {caps[0]["cle"]}) == []


def test_etat_frais_lu_sur_le_blob(monkeypatch):
    _sans_base(monkeypatch)
    monkeypatch.setattr(storage, "blob_public_url", lambda: "https://blob.test")
    monkeypatch.setattr("requests.get", lambda url, **k: Reponse(_etat()))
    assert M.etat_guet()["cles"] == ["abc123"]


@pytest.mark.parametrize("lu", [{"perime": True}, _etat(maj=(datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()), None])
def test_etat_perime_ou_absent_relu_dans_la_base(monkeypatch, lu):
    monkeypatch.setattr(storage, "blob_public_url", lambda: "https://blob.test")
    monkeypatch.setattr("requests.get", lambda url, **k: Reponse(lu, 200 if lu else 404))
    monkeypatch.setattr(M, "_etat_base", lambda: _etat(cles=["depuis-la-base"]))
    ecrit = {}
    monkeypatch.setattr(storage, "blob_put", lambda path, data, ct, max_age=None: ecrit.update(path=path, max_age=max_age))
    assert M.etat_guet()["cles"] == ["depuis-la-base"]
    assert ecrit == {"path": storage.GUET, "max_age": 60}


def test_file_due():
    passe = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    futur = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert M.file_due(_etat(prochain=passe))
    assert not M.file_due(_etat(prochain=futur))
    assert not M.file_due(_etat())


def test_ecrire_un_post_rend_le_guet_perime(monkeypatch):
    appels = []
    monkeypatch.setattr(storage, "invalide_guet", lambda: appels.append(1))
    db._posts_changes("INSERT INTO social_posts (title) VALUES (%s) RETURNING id")
    db._posts_changes("  update social_posts SET status = 'approved'")
    db._posts_changes("SELECT * FROM social_posts")
    db._posts_changes("INSERT INTO news (title) VALUES (%s)")
    assert len(appels) == 2
