"""Connexion à l'admin (traduction de Services\\Security\\Auth et Totp).

Mot de passe haché (Argon2id, compatible avec les hachages PHP existants « $argon2id$ » et « $2y$ »),
limitation des tentatives par IP et par e-mail, double authentification TOTP pour les comptes qui l'ont activée.
"""
import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from core import audit, conf, db
from core.repos import now_utc

MIN_PASSWORD_LENGTH = 12
_ph = PasswordHasher()  # Argon2id, paramètres par défaut proches de ceux de PHP
_DUMMY = _ph.hash("mot-de-passe-factice-pour-egaliser-le-temps")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    if hashed.startswith("$argon2"):
        try:
            return _ph.verify(hashed, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    if hashed.startswith(("$2y$", "$2a$", "$2b$")):
        try:
            return bcrypt.checkpw(password.encode(), ("$2b$" + hashed[4:]).encode())
        except ValueError:
            return False
    return False


def needs_rehash(hashed: str) -> bool:
    if not hashed.startswith("$argon2id$"):
        return True
    try:
        return _ph.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


def password_problem(password: str):
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Au moins {MIN_PASSWORD_LENGTH} caractères."
    classes = sum(bool(re.search(p, password)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^a-zA-Z\d]"))
    return "Mélanger au moins trois types : minuscules, majuscules, chiffres, symboles." if classes < 3 else None


# ---------------------------------------------------------------- TOTP (RFC 6238)

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def totp_secret(nbytes: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(nbytes)).decode().rstrip("=")


def totp_code(secret: str, at: int | None = None, period: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret.upper().rstrip("=") + "=" * (-len(secret.rstrip("=")) % 8))
    counter = int(at if at is not None else time.time()) // period
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = h[19] & 0x0F
    value = ((h[offset] & 0x7F) << 24) | (h[offset + 1] << 16) | (h[offset + 2] << 8) | h[offset + 3]
    return str(value % (10 ** digits)).zfill(digits)


def totp_verify(secret: str, code: str, at: int | None = None, window: int = 1) -> bool:
    """Accepte le code courant et celui de la période voisine (décalage d'horloge)."""
    code = re.sub(r"\s+", "", code or "")
    if not re.fullmatch(r"\d{6}", code):
        return False
    at = int(at if at is not None else time.time())
    return any(hmac.compare_digest(totp_code(secret, at + i * 30), code) for i in range(-window, window + 1))


def totp_uri(secret: str, account: str, issuer: str) -> str:
    return "otpauth://totp/" + quote(f"{issuer}:{account}", safe="") + "?" + urlencode({"secret": secret, "issuer": issuer})


# ---------------------------------------------------------------- connexion

def client_ip(request) -> str:
    """Adresse du visiteur (en-têtes du proxy de Vercel, sinon REMOTE_ADDR)."""
    ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    return ip or request.META.get("REMOTE_ADDR", "0.0.0.0")


def is_locked_out(email: str, ip: str) -> bool:
    mx = int(conf.get("app.security.login_max_attempts", 5))
    since = (datetime.now(timezone.utc) - timedelta(minutes=int(conf.get("app.security.login_window_minutes", 15)))).strftime("%Y-%m-%d %H:%M:%S")
    failures = int(db.value("SELECT COUNT(*) FROM login_attempts WHERE success = 0 AND attempted_at >= ? AND (ip = ? OR email = ?)",
                            [since, ip, email.lower()]))
    return failures >= mx


def _record(email: str, ip: str, success: bool) -> None:
    db.insert("login_attempts", {"ip": ip, "email": email, "success": 1 if success else 0, "attempted_at": now_utc()})


def attempt(request, email: str, password: str) -> str:
    """Première étape : 'ok', '2fa' (code TOTP attendu), 'locked' ou 'invalid'."""
    ip = client_ip(request)
    email = email.strip().lower()
    if is_locked_out(email, ip):
        return "locked"
    user = db.one("SELECT * FROM users WHERE email = ? AND is_active = 1", [email])
    # Vérification même sans compte, pour ne pas révéler son existence par le temps de réponse
    valid = verify_password(password, user["password_hash"] if user else _DUMMY) and bool(user)
    _record(email, ip, valid)
    if not valid:
        return "invalid"
    if needs_rehash(user["password_hash"]):
        db.update("users", {"password_hash": hash_password(password)}, "id = :id", {"id": user["id"]})
    request.session.cycle_key()
    if user["totp_secret"]:
        request.session["2fa_user"] = int(user["id"])
        request.session["2fa_started"] = int(time.time())
        return "2fa"
    _login(request, user, ip)
    return "ok"


def verify_second_factor(request, code: str) -> str:
    ip = client_ip(request)
    user_id = request.session.get("2fa_user")
    if not user_id or time.time() - int(request.session.get("2fa_started", 0)) > 300:
        request.session.pop("2fa_user", None)
        return "expired"
    user = db.one("SELECT * FROM users WHERE id = ? AND is_active = 1", [user_id])
    if not user or is_locked_out(user["email"], ip):
        return "locked"
    ok = totp_verify(str(user["totp_secret"]), code)
    _record(user["email"], ip, ok)
    if not ok:
        return "invalid"
    request.session.pop("2fa_user", None)
    _login(request, user, ip)
    return "ok"


def _login(request, user: dict, ip: str) -> None:
    request.session.cycle_key()
    request.session["user_id"] = int(user["id"])
    request.session["login_at"] = int(time.time())
    db.update("users", {"last_login_at": now_utc()}, "id = :id", {"id": user["id"]})
    audit.log(int(user["id"]), "auth.login", "user", user["id"], None, {}, ip)


def current_user(request):
    """Utilisateur connecté, ou None (session expirée après la durée configurée)."""
    if not request.COOKIES.get("cauri_sid"):
        return None
    uid = request.session.get("user_id")
    if not uid:
        return None
    if time.time() - int(request.session.get("login_at", 0)) > int(conf.get("app.security.session_lifetime", 7200)):
        logout(request)
        return None
    return db.one("SELECT id, email, name, role, totp_secret IS NOT NULL AS has_2fa FROM users WHERE id = ? AND is_active = 1", [uid])


def logout(request) -> None:
    request.session.flush()
