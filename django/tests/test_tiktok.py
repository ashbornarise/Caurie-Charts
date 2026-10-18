"""Tests TikTok avec HTTP et accès SQL bouchonnés."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from django.test import Client

from core.services import tiktok


class Reponse:
    def __init__(self, contenu):
        self.contenu = contenu

    def raise_for_status(self):
        pass

    def json(self):
        return self.contenu


def test_echange_code(monkeypatch):
    appels, updates = [], []
    monkeypatch.setattr(tiktok, "creer_table", lambda: None)
    monkeypatch.setattr(tiktok.db, "one", lambda *a: {"id": 7, "code": "code-test"})
    monkeypatch.setattr(tiktok.db, "run", lambda *a: updates.append(a))
    monkeypatch.setattr(tiktok.requests, "post", lambda *a, **kw: (appels.append((a, kw)) or Reponse({"data": {
        "access_token": "jeton", "refresh_token": "renouvellement", "expires_in": 3600,
        "refresh_expires_in": 86400, "open_id": "ouvert"}})))
    assert tiktok.echange_code()
    assert appels[0][0][0] == tiktok.TOKEN_URL
    assert appels[0][1]["data"]["code"] == "code-test"
    assert updates[0][1][0:2] == ["jeton", "renouvellement"]


def test_rafraichissement(monkeypatch):
    updates, appels = [], []
    maintenant = datetime.now(timezone.utc)
    ligne = {"id": 3, "access_token": "ancien", "refresh_token": "refresh",
             "access_expire": maintenant + timedelta(minutes=10)}
    monkeypatch.setattr(tiktok, "_ligne_active", lambda: ligne)
    monkeypatch.setattr(tiktok.db, "run", lambda *a: updates.append(a))
    monkeypatch.setattr(tiktok.requests, "post", lambda *a, **kw: (appels.append(kw) or Reponse({"data": {
        "access_token": "nouveau", "expires_in": 3600, "refresh_expires_in": 7200}})))
    assert tiktok.rafraichit() == "nouveau"
    assert appels[0]["data"]["grant_type"] == "refresh_token"
    assert updates


def test_stats_protege_erreurs_http(monkeypatch):
    monkeypatch.setattr(tiktok, "_ligne_active", lambda: {"id": 1})
    monkeypatch.setattr(tiktok, "rafraichit", lambda ligne: "jeton")
    def erreur(*args, **kwargs):
        raise OSError("secret non journalisé")
    monkeypatch.setattr(tiktok.requests, "get", erreur)
    resultat = tiktok.stats("2026-10-01", "2026-10-07")
    assert resultat["followers_count"] == "non disponible"
    assert resultat["videos"] == []


def test_stats_filtre_periode_et_pagine(monkeypatch):
    monkeypatch.setattr(tiktok, "_ligne_active", lambda: {"id": 1})
    monkeypatch.setattr(tiktok, "rafraichit", lambda ligne: "jeton")
    monkeypatch.setattr(tiktok.requests, "get", lambda *a, **kw: Reponse({"data": {"user": {
        "follower_count": 21, "following_count": 2, "likes_count": 30, "video_count": 2}}}))
    pages = iter([{"data": {"videos": [{"id": "in", "create_time": 1790899200}], "has_more": True, "cursor": 1}},
                  {"data": {"videos": [{"id": "out", "create_time": 1788220800}], "has_more": False, "cursor": 2}}])
    monkeypatch.setattr(tiktok.requests, "post", lambda *a, **kw: Reponse(next(pages)))
    resultat = tiktok.stats("2026-10-01", "2026-10-31")
    assert resultat["follower_count"] == 21
    assert [v["id"] for v in resultat["videos"]] == ["in"]


def test_vue_retour_refuse_state_inconnu(monkeypatch):
    monkeypatch.setattr(tiktok, "creer_table", lambda: None)
    monkeypatch.setattr("core.views_tiktok.db.one", lambda *a: None)
    reponse = Client(HTTP_HOST="localhost").get("/tiktok/retour", {"code": "code", "state": "inconnu"})
    assert reponse.status_code == 400
    assert b"non disponible" in reponse.content


def test_vue_connecter_cree_state_et_redirect(monkeypatch):
    ajouts = []
    monkeypatch.setattr(tiktok, "creer_table", lambda: None)
    monkeypatch.setattr("core.views_tiktok.db.run", lambda *a: ajouts.append(a))
    reponse = Client(HTTP_HOST="localhost").get("/tiktok/connecter")
    params = parse_qs(urlparse(reponse["Location"]).query)
    assert reponse.status_code == 302
    assert params["client_key"] == [tiktok.CLIENT_KEY_DEFAUT]
    assert params["scope"] == ["user.info.basic,user.info.profile,user.info.stats,video.list"]
    assert params["state"][0] in ajouts[0][1]
