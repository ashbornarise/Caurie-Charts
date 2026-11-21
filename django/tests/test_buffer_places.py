"""File Buffer : 10 posts programmés au plus PAR RÉSEAU (22/11/2026 : le contrôle additionnait les réseaux et le Studio
refusait tout envoi avec 27 posts programmés, 9 par réseau)."""
from core.services import buffer


def test_places_par_reseau(monkeypatch):
    def call(q, v, http=None):
        if "limits" in q:
            return {"account": {"organizations": [{"id": "o", "limits": {"scheduledPosts": 10}}]}}
        return {"posts": {"edges": [{"node": {"id": str(k), "channelId": c}} for k, c in enumerate(["ig"] * 9 + ["fb"] * 9 + ["tt"] * 9)]}}
    monkeypatch.setattr(buffer, "call", call)
    monkeypatch.setattr(buffer, "channels", lambda http=None: [{"id": "ig", "service": "instagram"}, {"id": "fb", "service": "facebook"},
                                                               {"id": "tt", "service": "tiktok"}])
    assert buffer.places_par_reseau() == {"ig": 1, "fb": 1, "tt": 1}
