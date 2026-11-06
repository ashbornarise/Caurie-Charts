"""Couverture des vidéos (06/11/2026) : image titrée à 1,5 s, vignette du Studio en couverture des Reels."""
import json

from core.services import buffer


def test_instant_de_couverture():
    assert buffer.couverture_ms({"facts": "{}"}) == 1500
    assert buffer.couverture_ms({"facts": json.dumps({"couverture_ms": 3200})}) == 3200


def test_vignette_studio_seulement(monkeypatch):
    monkeypatch.setattr("core.storage.blob_public_url", lambda: "https://blob")
    assert buffer.couverture_url({"image_square": "studio-292-ea8ac3.jpg"}) == "https://blob/media/social/studio-292-ea8ac3.jpg"
    assert buffer.couverture_url({"image_square": "2026-11-06-monde-soir-3-190537-0.jpg"}) is None


def test_buffer_envoie_la_couverture(monkeypatch):
    monkeypatch.setattr(buffer, "video_url", lambda post, service="": "https://blob/v.mp4")
    monkeypatch.setattr(buffer, "text", lambda post, service: "texte")
    post = {"id": 1, "theme": "format-studio-1", "facts": json.dumps({"kind": "format-clip"}), "video": "v.mp4"}
    d = buffer.payload(post, {"id": "c", "service": "instagram"}, None, reel=True)
    assert d["assets"][0]["video"]["metadata"] == {"thumbnailOffset": 1500}
    d = buffer.payload(post, {"id": "c", "service": "facebook"}, None, reel=True)
    assert "metadata" not in d["assets"][0]["video"]
