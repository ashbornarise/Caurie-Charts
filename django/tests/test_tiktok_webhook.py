"""Adresse webhook TikTok : signature vérifiée, événement noté."""
import hashlib
import hmac

from django.test import RequestFactory

from core import views_tiktok as V


def _req(corps, signature=None):
    h = {"HTTP_TIKTOK_SIGNATURE": signature} if signature else {}
    return RequestFactory().post("/tiktok/webhook", data=corps, content_type="application/json", **h)


def test_signature_valide_notee(monkeypatch):
    notes = []
    monkeypatch.setattr(V.env, "get", lambda k, d=None: "secret" if k == "TIKTOK_CLIENT_SECRET" else d)
    monkeypatch.setattr(V.db, "run", lambda sql, p=None: notes.append(p))
    corps = '{"event":"post.publish.complete"}'
    s = hmac.new(b"secret", f"123.{corps}".encode(), hashlib.sha256).hexdigest()
    assert V.webhook(_req(corps, f"t=123,s={s}")).status_code == 200
    assert notes[-1][0] == "post.publish.complete" and notes[-1][2] is True


def test_signature_fausse_refusee(monkeypatch):
    monkeypatch.setattr(V.env, "get", lambda k, d=None: "secret" if k == "TIKTOK_CLIENT_SECRET" else d)
    monkeypatch.setattr(V.db, "run", lambda *a, **k: None)
    assert V.webhook(_req("{}", "t=1,s=faux")).status_code == 401


def test_get_repond_ok():
    assert V.webhook(RequestFactory().get("/tiktok/webhook")).status_code == 200
