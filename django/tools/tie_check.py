"""Vérifie que l'ordre PHP d'un classement en direct ne diffère de Django que par des égalités parfaites."""
import re
import sys

import django
import requests

django.setup()
from core.services import live_chart as lc  # noqa: E402

CASES = {
    "/classements/afrique-de-l-ouest": (None, None, 100, "prime", 20, "latest"),
    "/classements/afrique-de-l-ouest?classement=buzz": (None, None, 50, "buzz", 20, "week"),
    "/classements/afrique-de-l-ouest?classement=legend": (None, None, 100, "legend", 20, "week"),
    "/classements/afrique-de-l-ouest/mois?vue=direct": (None, None, 100, "prime", 20, "month"),
}
for url, args in CASES.items():
    html = requests.get("http://localhost:8000" + url, timeout=60).text
    php = re.findall(r'class="entry__title" href="/(?:titre|artiste)/([^"]+)"', html)
    rows = lc._compute(*args)["rows"]
    key = {r["track_slug"]: (round(r["points"], 9), len(r["seen"]), r["best"]) for r in rows}
    dj = [r["track_slug"] for r in rows]
    bad = [(i + 1, a, b) for i, (a, b) in enumerate(zip(php, dj)) if a != b and key.get(a) != key.get(b)]
    same_set = set(php) == set(dj[:len(php)])
    print(("OK " if not bad and same_set else "DIF"), url, len(php), "lignes", bad[:5], "" if same_set else "ensembles différents")
