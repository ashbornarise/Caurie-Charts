"""Cauri Studio : adresse secrète, accès protégé, contrôles du formulaire, montage et envoi (base et réseau simulés)."""
import json

import pytest
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.http import Http404
from django.test import RequestFactory

from core import studio
from core.services.social import studio_montage as S

CHEMIN = "a" * 30
RF = RequestFactory()


def _req(methode, donnees=None):
    r = RF.post("/", data=json.dumps(donnees or {}), content_type="application/json") if methode == "post" else RF.get("/")
    r.session = SessionStore()
    return r


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(studio, "chemin_secret", lambda: CHEMIN)
    monkeypatch.setattr(studio, "creer_tables", lambda: None)


def test_mauvais_chemin_404():
    with pytest.raises(Http404):
        studio.studio(_req("get"), "b" * 30)


def test_page_de_connexion_sans_session(monkeypatch):
    monkeypatch.setattr(studio, "_utilisateur", lambda r: None)
    r = studio.studio(_req("get"), CHEMIN)
    assert r.status_code == 200 and "Déverrouiller" in r.content.decode()
    assert r["X-Robots-Tag"] == "noindex, nofollow"


def test_api_refusee_sans_session(monkeypatch):
    monkeypatch.setattr(studio, "_utilisateur", lambda r: None)
    assert studio.fabriquer(_req("post"), CHEMIN).status_code == 401


def test_fabriquer_exige_droits_et_lien(monkeypatch):
    monkeypatch.setattr(studio, "_utilisateur", lambda r: {"id": 1, "role": "admin"})
    r = studio.fabriquer(_req("post", {"lien": "https://tiktok.com/x"}), CHEMIN)
    assert r.status_code == 400 and "droits" in json.loads(r.content)["erreur"]
    assert studio.fabriquer(_req("post", {"lien": "pas un lien", "droits": True}), CHEMIN).status_code == 400
    assert studio.fabriquer(_req("post", {"lien": "https://x.com/a", "droits": True, "debut": 0, "fin": 500}), CHEMIN).status_code == 400


def test_fabriquer_cree_la_tache_et_lance(monkeypatch):
    monkeypatch.setattr(studio, "_utilisateur", lambda r: {"id": 1, "role": "admin"})
    inserts = []
    monkeypatch.setattr(studio.db, "insert", lambda t, d: inserts.append((t, d)) or 42)
    monkeypatch.setattr(studio, "_lance", lambda i: None)
    r = studio.fabriquer(_req("post", {"lien": "https://www.tiktok.com/@a/video/1", "droits": True, "format": "feed",
                                       "debut": 2, "fin": 20}), CHEMIN)
    assert json.loads(r.content) == {"id": 42, "erreur": None}
    t, d = inserts[0]
    assert t == "studio_jobs" and json.loads(d["params"])["format"] == "feed"


def test_calque_laisse_le_bas_libre_en_9_16():
    img, (x, y, w, h), titre = S.calque("story", "MOMENT VIRAL", "Asake enflamme la scène", "Asake", "@asake sur TikTok")
    assert img.size == (1080, 1920)
    assert y + h <= 1920 * 0.8          # la vidéo ne descend pas dans la zone de l'interface TikTok / Reels


def test_credit_auto():
    assert S.credit_auto({"uploader": "asakemusic", "extractor_key": "TikTok"}) == "@asakemusic sur TikTok"
    assert S.credit_auto({"channel": "Ayra Starr", "extractor_key": "Youtube"}) == "Ayra Starr sur Youtube"
