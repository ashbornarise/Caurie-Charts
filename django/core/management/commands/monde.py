"""Cauri Monde : l'actualité musicale mondiale sur nos pages (Instagram, TikTok, Facebook, Telegram) + Actualités du site.

  manage.py monde --edition matin      édition de 8 h (l'actu du monde)
  manage.py monde --edition soir       édition de 20 h (projets, records, sorties)
  manage.py monde --edition flash      l'info choc du moment (≥ 2 médias), publiée tout de suite
  manage.py monde --edition matin --essai   rendu seul, rien n'est publié
"""
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.social import monde as M


class Command(BaseCommand):
    help = "Publie Cauri Monde (8 h, 20 h) ou un flash."

    def add_arguments(self, p):
        p.add_argument("--edition", choices=("matin", "soir", "flash"), required=True)
        p.add_argument("--essai", action="store_true")

    def handle(self, *args, **o):
        def task():
            maintenant = datetime.now(timezone.utc)
            if o["edition"] == "flash":
                post = M.flash(rendu_seul=o["essai"])
                due = maintenant + timedelta(minutes=2)
            else:
                post = M.edition(maintenant.date(), o["edition"], rendu_seul=o["essai"])
                heure = 8 if o["edition"] == "matin" else 20
                due = max(maintenant.replace(hour=heure, minute=0, second=0, microsecond=0), maintenant + timedelta(minutes=5))
            if not post:
                out("rien à publier")
                return
            if o["essai"]:
                out("essai : " + ", ".join(f["file"] for f in post["fichiers"]))
                return
            out(post["title"])
            for l in M.publie(post, due):
                out(l)
        run("monde", task)
