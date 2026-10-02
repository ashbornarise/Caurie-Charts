"""Chaîne quotidienne complète (une seule tâche planifiée, chaque nuit).

  manage.py daily
  manage.py daily --weekly        force le calcul du classement officiel de la semaine passée
  manage.py daily --posts         force la génération des trois posts
  manage.py daily --youtube=6     recherches de clips YouTube (100 unités de quota chacune)
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.pipeline import DailyPipeline


class Command(BaseCommand):
    help = "Chaîne quotidienne complète."

    def add_arguments(self, p):
        p.add_argument("--weekly", action="store_true")
        p.add_argument("--posts", action="store_true")
        p.add_argument("--youtube", type=int, default=6)

    def handle(self, *args, **o):
        def task():
            report = DailyPipeline(out).run(o["weekly"], o["posts"], o["youtube"])
            failed = [r for r in report if not r["ok"]]
            out("")
            out(f"Terminé : {len(report)} étapes, {len(failed)} en erreur" + (f" ({', '.join(r['step'] for r in failed)})" if failed else ""))
        run("daily", task)
