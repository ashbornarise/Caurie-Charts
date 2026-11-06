"""Top 100 Boomplay par pays (06/11/2026) : lecture d'une playlist de classement rendue par l'outil Apify."""
from core.services.imports.sources import BoomplayChartSource


def test_lecture_playlist():
    p = {"record_type": "playlist", "id": 2676201, "tracks": [
        {"id": 214165091, "name": "LIL WAYNE", "position": 1, "link": "https://www.boomplay.com/songs/214165091",
         "artist": {"name": "Himra"}, "album": {"image": "https://x/cover.jpg"}},
        {"id": 2, "name": "Deux êtres", "position": 2, "artist": {"name": "Fally Ipupa"}, "album": {}},
        {"id": 3, "name": "", "position": 3, "artist": {"name": "Sans titre"}},
    ]}
    s = BoomplayChartSource.parse(p)
    assert [r["position"] for r in s["rows"]] == [1, 2]
    assert s["rows"][0] == {"position": 1, "title": "LIL WAYNE", "artist": "Himra", "external_id": "214165091",
                            "url": "https://www.boomplay.com/songs/214165091", "image": "https://x/cover.jpg"}


def test_pays_sans_classement():
    # Boomplay renvoie le Top Nigeria pour la Mauritanie ou la Gambie : ces pays ne sont pas relevés
    assert BoomplayChartSource().fetch("MR") is None
    assert "GM" not in BoomplayChartSource.PLAYLISTS
