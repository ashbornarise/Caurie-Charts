"""Sécurité : TOTP, mots de passe, échappement (traduction de tests/SecurityTest.php)."""
import base64
import html
import secrets

from core.backoffice import auth
from core.helpers import e


def test_totp_vecteur_rfc6238():
    # Secret RFC « 12345678901234567890 », T = 59 s → 94287082 (8 chiffres), donc 287082 sur 6
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert auth.totp_code(secret, 59) == "287082"
    assert auth.totp_code(secret, 1111111109) == "081804"


def test_totp_periode_voisine():
    secret = auth.totp_secret()
    now = 1_800_000_000
    assert auth.totp_verify(secret, auth.totp_code(secret, now - 30), now)
    assert not auth.totp_verify(secret, auth.totp_code(secret, now - 90), now)
    assert not auth.totp_verify(secret, "abcdef", now)


def test_base32_aller_retour():
    raw = secrets.token_bytes(20)
    enc = base64.b32encode(raw).decode().rstrip("=")
    assert base64.b32decode(enc + "=" * (-len(enc) % 8)) == raw


def test_mot_de_passe_longueur_et_variete():
    assert auth.password_problem("court1A!") is not None
    assert auth.password_problem("toutenminusculeslong") is not None
    assert auth.password_problem("Cauri-Charts-2026") is None


def test_hachages_php_existants_reconnus():
    h = auth.hash_password("Cauri-Charts-2026")
    assert auth.verify_password("Cauri-Charts-2026", h)
    assert not auth.verify_password("mauvais", h)
    assert not auth.needs_rehash(h)


def test_echappement_html():
    out = e("<script>alert('x')</script>")
    assert "<" not in out and "'" not in out
    assert html.unescape(out) == "<script>alert('x')</script>"
