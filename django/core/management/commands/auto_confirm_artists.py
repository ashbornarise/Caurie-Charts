"""Auto-confirmation des artistes pending fréquemment observés dans les classements.

  manage.py auto_confirm_artists
  manage.py auto_confirm_artists --min-obs=20 --min-weeks=2 --min-ratio=0.7
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.imports.classifier import auto_confirm_by_observations


class Command(BaseCommand):
    help = "Confirme automatiquement les artistes en attente qui apparaissent souvent dans les classements d'un pays."

    def add_arguments(self, p):
        p.add_argument("--min-obs", type=int, default=30)
        p.add_argument("--min-weeks", type=int, default=2)
        p.add_argument("--min-ratio", type=float, default=0.7)

    def handle(self, *args, **o):
        def task():
            r = auto_confirm_by_observations(o["min_obs"], o["min_weeks"], o["min_ratio"])
            out(f"Auto-confirmation : {r['confirmed']} confirmés, {r['skipped']} écartés, {r['candidates']} candidats examinés")
        run("auto-confirm-artists", task)
