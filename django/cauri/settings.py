"""Réglages Django de Cauri Charts.

Les valeurs viennent du même fichier .env que le site PHP (racine du dépôt), puis du fichier de secrets
(SECRETS_FILE). En production (Vercel), elles viennent des variables d'environnement.
"""
from pathlib import Path

from core import env

BASE_DIR = Path(__file__).resolve().parent.parent          # dossier django/
REPO_DIR = BASE_DIR.parent                                  # racine du dépôt (assets, médias partagés)

env.load(REPO_DIR / ".env")
if env.get("SECRETS_FILE"):
    env.load(Path(env.get("SECRETS_FILE")))

DEBUG = env.bool("APP_DEBUG", False)
SECRET_KEY = env.get("DJANGO_SECRET_KEY") or env.get("APP_KEY") or ""
if not SECRET_KEY:
    if env.get("VERCEL") or env.get("APP_ENV") == "production":
        raise RuntimeError("DJANGO_SECRET_KEY manquante : à définir dans les variables d'environnement de Vercel.")
    SECRET_KEY = "dev-uniquement-a-remplacer"
ALLOWED_HOSTS = [h.strip() for h in env.get("ALLOWED_HOSTS", "localhost,127.0.0.1,.vercel.app,cauricharts.com,www.cauricharts.com").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env.get("CSRF_TRUSTED_ORIGINS", "https://cauricharts.com,https://www.cauricharts.com").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "core.middleware.CauriMiddleware",
]

ROOT_URLCONF = "cauri.urls"
WSGI_APPLICATION = "cauri.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.jinja2.Jinja2",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": False,
    "OPTIONS": {"environment": "core.jinja.environment", "autoescape": True},
}]


def _database():
    url = env.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5433/cauricharts")
    from urllib.parse import urlparse, unquote
    u = urlparse(url)
    cfg = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": unquote(u.username or ""),
        "PASSWORD": unquote(u.password or ""),
        "HOST": u.hostname or "",
        "PORT": str(u.port or 5432),
        "CONN_MAX_AGE": 0 if env.get("VERCEL") else 60,
    }
    if "sslmode=require" in url:
        cfg["OPTIONS"] = {"sslmode": "require"}
    return cfg


DATABASES = {"default": _database()}

# Session paresseuse : le cookie « cauri_sid » n'est posé qu'au premier besoin (formulaire, langue, admin),
# comme sur le site PHP. Sessions signées dans le cookie : pas de table, adapté à Vercel.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_NAME = "cauri_sid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_USE_SESSIONS = True          # jeton CSRF dans la session : aucun cookie de plus
CSRF_COOKIE_SECURE = not DEBUG
CSRF_FAILURE_VIEW = "core.views_errors.csrf_failure"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

LANGUAGE_CODE = "fr"
TIME_ZONE = env.get("APP_TIMEZONE", "Africa/Lome")
USE_I18N = False
USE_TZ = False

# Mêmes adresses que le site PHP : /assets/… (fichiers statiques) et /media/… (fichiers générés)
STATIC_URL = "/assets/"
# Fichiers servis tels quels depuis public/assets (par Vercel en production, par WhiteNoise ailleurs) : pas de collectstatic
STATICFILES_DIRS = [REPO_DIR / "public" / "assets"]
STATIC_ROOT = None
WHITENOISE_USE_FINDERS = True
MEDIA_URL = "/media/"
MEDIA_ROOT = REPO_DIR / "public" / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
