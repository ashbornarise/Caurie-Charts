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


def _base_disponible() -> bool:
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
