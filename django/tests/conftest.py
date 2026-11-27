"""Tests de Cauri Charts (traduction de tests/*Test.php) : python -m pytest django/tests"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cauri.settings")
os.environ.setdefault("HASHTAGS_IA", "0")
os.environ.setdefault("VOIX_IA", "0")   # pas d'appel à l'IA pour les accroches   # pas d'appel à l'IA pour les hashtags pendant les tests
# 27/11/2026 : le .env charge SECRETS_FILE (vraie base Neon, Blob, Buffer, Meta…) et des tests ont écrit en production.
# Les variables d'environnement priment sur le .env : les tests ne voient qu'une base locale et aucune clé de publication.
os.environ["DATABASE_URL"] = os.environ.get("TESTS_DATABASE_URL", "postgresql://postgres@127.0.0.1:5433/cauricharts")
os.environ.setdefault("PGCONNECT_TIMEOUT", "2")   # pas de base locale : on le sait en 2 s au lieu d'attendre (suite de 15 min sinon)
for _cle in ("BLOB_READ_WRITE_TOKEN", "GH_DISPATCH_TOKEN", "BUFFER_API_KEY", "META_ACCESS_TOKEN", "TELEGRAM_BOT_TOKEN",
             "SMTP_PASSWORD", "CRON_SECRET", "TIKTOK_CLIENT_SECRET"):
    os.environ[_cle] = ""

import django  # noqa: E402

django.setup()


class FakeHttp:
    """Faux client HTTP : enregistre les appels et rejoue des réponses préparées."""

    def __init__(self, responder):
        self.responder, self.calls = responder, []

    def request(self, method, url, headers=None, body=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body})
        return self.responder(method, url, headers or {}, body)


def youtube_responder(method, url, headers=None, body=None):
    ids = parse_qs(urlparse(url).query)["id"][0].split(",")
    items = [{"id": i, "statistics": {"viewCount": "1000", "likeCount": "40", "commentCount": "3"}} for i in ids]
    return {"status": 200, "body": json.dumps({"items": items})}


# 10/11/2026 : sur GitHub il n'y a pas de base PostgreSQL ; les tests qui lisent la vraie base sont ignorés (avec la
# raison) au lieu d'échouer, et tournent normalement sur le PC où la base existe.
BASE_REQUISE = ("test_pages_publiques.py", "test_redaction.py", "test_newsletter.py", "test_guet.py")


def _base_de_production() -> bool:
    """27/11/2026 : le .env charge SECRETS_FILE, donc le DATABASE_URL de la vraie base Neon ; des tests y ont écrit
    (avis du comité de rédaction). Les tests ne touchent jamais une base hébergée (Neon) : seulement une base locale."""
    from django.conf import settings
    hote = str(settings.DATABASES.get("default", {}).get("HOST") or "")
    return "neon.tech" in hote or ("." in hote and hote not in ("127.0.0.1", "localhost"))


def _base_disponible() -> bool:
    if _base_de_production():
        return False
    try:
        from django.db import connection
        connection.ensure_connection()
        return True
    except Exception:  # noqa: BLE001
        return False


def pytest_collection_modifyitems(config, items):
    import pytest
    if _base_disponible():
        return
    saut = pytest.mark.skip(reason="base PostgreSQL absente (GitHub) : test lancé sur le PC")
    for item in items:
        if item.fspath.basename in BASE_REQUISE:
            item.add_marker(saut)
