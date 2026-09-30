"""Rejoue les mêmes actions d'admin (POST) sur PHP (:8002) et Django (:8003), sur les copies de base,
puis compare les tables touchées. Usage : python tools/admin_actions.py
"""
import re
import subprocess
import sys
from datetime import date, timedelta

import requests

sys.path.insert(0, "tools")
from admin_parity import SITES, login  # noqa: E402

next_monday = date.today() + timedelta(days=14)
while next_monday.isoweekday() != 1:
    next_monday += timedelta(days=1)

ACTIONS = [
    ("/admin/actualites/nouveau", {"title": "Test de parité", "summary": "Résumé de test", "body": "Paragraphe 1\n\nParagraphe 2",
                                   "category": "annonce", "country_id": "1", "source_name": "", "source_url": "",
                                   "published_at": "2026-09-30T10:00", "status": "published"}),
    ("/admin/formule", {"w_audio": "1,1", "w_youtube": "0.9", "w_declaration": "0.5", "cw_TG_audio": "1.25", "cw_TG_youtube": "",
                        "spike_factor": "5", "declaration_tolerance": "0.3", "effective_from": next_monday.isoformat(), "note": "Essai de parité"}),
    ("/admin/import/csv", {"source": "audiomack", "country_id": "1", "observed_on": "2026-09-29", "rows": "1;Migbo;Sethlo\n2;Nouveau Titre Parite;Artiste Parite feat. Invite"}),
    ("/admin/releves", {"track_platform_id": "537", "captured_on": "2026-09-29", "plays": "999"}),
    ("/admin/pays/1", {"chart_size": "30", "platforms[]": ["youtube", "deezer"], "locale": "fr", "is_active": "1"}),
    ("/admin/artistes/nouveau", {"name": "Artiste Créé Parité", "submission_country_id": "2", "label_owner": "Nova Luz!", "is_emerging": "1", "bio": "", "image_url": ""}),
    ("/admin/titres/nouveau", {"title": "Titre Créé", "artist_id": "1", "featuring": "", "release_date": "2026-09-01", "cover_url": "", "is_active": "1",
                               "new_platform": "youtube", "new_external_id": "abcdefghijk", "new_kind": "clip", "new_url": "", "new_published_at": ""}),
    ("/admin/partenaires/nouveau", {"name": "Partenaire Test", "url": "https://exemple.org", "tier": "media", "description": "Desc", "sort_order": "3", "is_active": "1"}),
]
TABLES = ["news", "formula_versions", "chart_observations", "tracks", "artists", "track_platform_ids", "snapshots", "countries", "partners", "audit_log"]

sessions = {k: login(v) for k, v in SITES.items()}
for url, data in ACTIONS:
    codes = []
    for k, base in SITES.items():
        s = sessions[k]
        html = s.get(base + "/admin").text
        field, tok = re.search(r'name="(_csrf|csrfmiddlewaretoken)" value="([^"]+)"', html).groups()
        r = s.post(base + url, data={**data, field: tok}, allow_redirects=False)
        flash = s.get(base + (r.headers.get("location") or "/admin")).text
        m = re.search(r'class="flash flash--(\w+)"[^>]*>([^<]*)', flash)
        codes.append(f"{r.status_code} {m.group(1) + ' ' + m.group(2)[:70] if m else ''}")
    print(url, "|", " || ".join(codes))

print()
subprocess.run([sys.executable, "tools/compare_tables.py", *TABLES])
