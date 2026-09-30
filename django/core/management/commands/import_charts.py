"""Import des classements (une source ou un pays à la fois).

  manage.py import_charts
  manage.py import_charts --country=CI --source=apple_music
  manage.py import_charts --youtube=30     puis recherche de 30 clips YouTube au plus
"""
import json

from django.core.management.base import BaseCommand

from core import env
from core.management.commands._cli import out, run
from core.services.imports.service import ImportService


class Command(BaseCommand):
    help = "Importe les classements des plateformes."

    def add_arguments(self, p):
        p.add_argument("--country")
        p.add_argument("--source")
        p.add_argument("--youtube", type=int)

    def handle(self, *args, **o):
        def task():
            service = ImportService()
            for line in service.import_all([o["country"].upper()] if o["country"] else None, [o["source"]] if o["source"] else None):
                out(line)
            limit = o["youtube"] if o["youtube"] is not None else int(env.get("YOUTUBE_SEARCH_PER_RUN", "0") or 0)
            if limit > 0:
                out("YouTube : " + json.dumps(service.match_youtube(limit), ensure_ascii=False))
        run("import-charts", task)
