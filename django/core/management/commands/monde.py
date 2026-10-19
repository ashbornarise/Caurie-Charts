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
        p.add_argument("--edition", choices=("matin", "soir", "flash", "file"), required=True)
        p.add_argument("--essai", action="store_true")

    def handle(self, *args, **o):
        def task():
            maintenant = datetime.now(timezone.utc)
            if o["edition"] == "file":   # les posts arrivés à leur heure
                for line in M.publie_file() or ["rien à envoyer"]:
                    out(line)
                return
            if o["edition"] == "flash" and not o["essai"] and maintenant.isoweekday() in (2, 3) and 17 <= maintenant.hour < 23:
                # Classement officiel : publié à la main pays par pays le mardi ; le post part dès que la semaine est publiée
                from core.services.social import officiel
                try:
                    if officiel.post(maintenant.date(), maintenant + timedelta(minutes=5)):
                        out("classement officiel : post programmé")
                except Exception as exc:  # noqa: BLE001
                    out(f"classement officiel : {exc}")
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
            if "posts" in post:   # édition : un post par info, envoyés à leur heure par la file d'attente
                for line in M.publie_file():
                    out(line)
                return
            for line in M.publie(post, due):
                out(line)
        run("monde", task)
