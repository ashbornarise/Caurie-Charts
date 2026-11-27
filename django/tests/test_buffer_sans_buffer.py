"""Buffer en limite de requêtes (26/11/2026, tâches Studio 459 et 460 en échec) : Instagram et Facebook partent quand même
en direct par l'API Meta ; TikTok attend que Buffer réponde."""
import pytest

from core.services import buffer, meta
from core.services.platforms import PlatformException


def _prepare(monkeypatch, meta_actif=True):
    def refus(http=None):
        raise PlatformException("Buffer : Too many requests from this client.")
    monkeypatch.setattr(buffer, "channels", refus)
    monkeypatch.setattr(buffer, "call", lambda *a, **k: (_ for _ in ()).throw(PlatformException("Buffer : Too many requests")))
    monkeypatch.setattr(buffer, "configured", lambda: True)
    monkeypatch.setattr(buffer, "instagram_ok", lambda post, service="instagram": True)
    monkeypatch.setattr(buffer, "facebook_ok", lambda post: True)
    monkeypatch.setattr(buffer.db, "value", lambda *a, **k: None)
    monkeypatch.setattr(buffer.audit, "log", lambda *a, **k: None)
    from core.services.social import hashtags
    monkeypatch.setattr(hashtags, "preparer", lambda post: post)
    monkeypatch.setattr(meta, "actif", lambda: meta_actif)
    envoyes = []
    monkeypatch.setattr(meta, "instagram", lambda post, reel: envoyes.append("instagram") or "ig1")
    monkeypatch.setattr(meta, "facebook", lambda post, reel: envoyes.append("facebook") or "fb1")
    return envoyes


def test_meta_direct_sans_buffer(monkeypatch):
    envoyes = _prepare(monkeypatch)
    r = buffer.schedule({"id": 459, "facts": "{}", "theme": "format-studio-photo"})
    assert envoyes == ["instagram", "facebook"]
    assert "instagram programmé" in r and "facebook programmé" in r
    assert "tiktok : non envoyé" in r


def test_sans_meta_l_erreur_remonte(monkeypatch):
    _prepare(monkeypatch, meta_actif=False)
    with pytest.raises(PlatformException):
        buffer.schedule({"id": 460, "facts": "{}", "theme": "format-studio-photo"})
