"""Espace presse : communiqués publiés (PDF dans public/presse, indexés par Google) et contact.
Un communiqué n'apparaît sur la page et dans le plan du site qu'à partir de sa date de publication (UTC)."""
from core.helpers import url
from core.views_util import now_utc

RELEASES = [
    {"date": "2026-10-04 08:00:00", "slug": "distinctions-officielles",
     "title": "Cauri Charts lance ses Distinctions officielles",
     "summary": "Chaque mois, le Top 5 de chaque classement d’Afrique de l’Ouest reçoit une distinction numérotée, "
                "calculée sur des données réelles.",
     "files": [("Communiqué (français, PDF)", "presse/cauri-charts-communique-distinctions-officielles.pdf"),
               ("Press release (English, PDF)", "presse/cauri-charts-press-release-official-distinctions.pdf"),
               ("Visuel : spécimen de distinction (JPG)", "presse/cauri-charts-specimen-distinction.jpg")],
     "article": "actualites/cauri-charts-lance-ses-distinctions-officielles"},
]


def published() -> list:
    now = now_utc()
    out = []
    for r in RELEASES:
        if r["date"] <= now:
            out.append({**r, "links": [(label, url(f)) for label, f in r["files"]]})
    return sorted(out, key=lambda r: r["date"], reverse=True)
