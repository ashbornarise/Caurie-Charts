"""Tests de Cauri Charts (traduction de tests/*Test.php) : python -m pytest django/tests"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cauri.settings")

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
