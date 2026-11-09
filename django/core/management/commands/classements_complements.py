"""Ajoute aux semaines déjà publiées les classements créés le 09/11/2026 (Top Artistes de la saison, genres), sans
recalculer ce qui est publié ; refait aussi les classements de l'Afrique de l'Ouest (Top Artistes compris).

  manage.py classements_complements                      les 2 dernières semaines terminées
  manage.py classements_complements --semaine=2026-W44
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run


class Command(BaseCommand):
    help = "Complète les semaines publiées avec les nouveaux classements (saison, genres)."

    def add_arguments(self, p):
        p.add_argument("--semaine")

    def handle(self, *args, **o):
        def task():
            from core import clock, db
            from core.services.chart_service import ChartService
            from core.services.charts import Period
            service = ChartService()
            if o["semaine"]:
                semaines = [Period.from_key("week", o["semaine"])]
            else:
                derniere = Period.last_completed_week(clock.today().isoformat())
                semaines = [derniere.previous(), derniere]
            for p in semaines:
                for c in db.all("SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order"):
                    r = service.completer_semaine(c["code"], p.key)
                    if r:
                        out(f"{p.key} {c['code']} : " + ", ".join(f"{k} ({n})" for k, n in r.items()))
                reg = service.compute_regional_week(p)
                if reg:
                    out(f"{p.key} Afrique de l'Ouest : {reg}")
        run("classements-complements", task)
