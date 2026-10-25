"""Publication TikTok : découpage en morceaux (règles de TikTok) et requêtes envoyées."""
import pytest

from core.services import tiktok_publie as T
from core.services.platforms import PlatformException


def test_decoupage_selon_les_regles():
    assert T._source(4_194_304) == {"source": "FILE_UPLOAD", "video_size": 4_194_304, "chunk_size": 4_194_304, "total_chunk_count": 1}
    s = T._source(50_000_123)
    assert s["chunk_size"] == 10 * 1024 * 1024 and s["total_chunk_count"] == 50_000_123 // (10 * 1024 * 1024)


class Rep:
    def __init__(self, data=None, status=200, content=b""):
        self.data, self.status_code, self.content = data, status, content

    def json(self):
        return self.data


def test_publication_directe(monkeypatch):
    envoyes, puts = [], []
    monkeypatch.setattr(T, "jeton", lambda: "J")
    monkeypatch.setattr(T.requests, "get", lambda url, timeout: Rep(content=b"x" * 3000))
    monkeypatch.setattr(T.requests, "post", lambda url, json, timeout, headers: envoyes.append((url, json)) or Rep(
        {"data": {"publish_id": "p1", "upload_url": "https://up"}, "error": {"code": "ok"}}))
    monkeypatch.setattr(T.requests, "put", lambda url, data, timeout, headers: puts.append(headers) or Rep(status=201))
    assert T.publier("https://v.mp4", "Titre", {"privacy_level": "SELF_ONLY", "disable_comment": True}) == "p1"
    url, corps = envoyes[0]
    assert url.endswith("/post/publish/video/init/") and corps["post_info"]["privacy_level"] == "SELF_ONLY"
    assert corps["post_info"]["disable_comment"] is True and puts[0]["Content-Range"] == "bytes 0-2999/3000"


def test_brouillon_sans_reglages(monkeypatch):
    envoyes = []
    monkeypatch.setattr(T, "jeton", lambda: "J")
    monkeypatch.setattr(T.requests, "get", lambda url, timeout: Rep(content=b"x" * 10))
    monkeypatch.setattr(T.requests, "post", lambda url, json, timeout, headers: envoyes.append(url) or Rep(
        {"data": {"publish_id": "p2", "upload_url": "https://up"}, "error": {"code": "ok"}}))
    monkeypatch.setattr(T.requests, "put", lambda *a, **k: Rep(status=201))
    assert T.publier("https://v.mp4", "T", {}, brouillon=True) == "p2" and envoyes[0].endswith("/inbox/video/init/")


def test_visibilite_obligatoire(monkeypatch):
    monkeypatch.setattr(T, "jeton", lambda: "J")
    monkeypatch.setattr(T.requests, "get", lambda url, timeout: Rep(content=b"x"))
    with pytest.raises(PlatformException):
        T.publier("https://v.mp4", "T", {})
