"""Paroles Spotify (11/11/2026) : le code TOTP exigé par open.spotify.com/api/token doit suivre la RFC 6238."""
from core.services.social import spotify_paroles as SP


def test_totp_rfc6238():
    # vecteur de test officiel (SHA-1, clé « 12345678901234567890 ») : 94287082 à t = 59 s -> 6 chiffres « 287082 »
    assert SP._totp(b"12345678901234567890", 59) == "287082"
    assert SP._totp(b"12345678901234567890", 1111111109) == "081804"


def test_sans_cookie(monkeypatch):
    monkeypatch.setattr(SP.env, "get", lambda k, d="": "")
    SP._cache.clear()
    try:
        SP.jeton()
        assert False
    except SP.SpotifyParolesErreur as e:
        assert "SPOTIFY_SP_DC" in str(e)
