"""Vidéos du jour : extraits de clips officiels coupés au refrain (3 par jour, 13 h, 17 h, 21 h), à lancer depuis le
poste de travail (YouTube bloque souvent les serveurs de GitHub). Les posts partent ensuite seuls, à leur heure.

  manage.py clips             fabrique et programme les vidéos du jour
  manage.py clips --n 2       seulement 2 vidéos
  manage.py clips --essai     rendu seul, rien n'est programmé
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.social import clips as C


class Command(BaseCommand):
    help = "Fabrique et programme les vidéos du jour (clips officiels coupés au refrain)."

    def add_arguments(self, p):
        p.add_argument("--n", type=int, default=1)   # 1 clip, 3 jours par semaine (24/10/2026)
        p.add_argument("--essai", action="store_true")
        p.add_argument("--force", action="store_true", help="publier même hors lundi/mercredi/vendredi")
        p.add_argument("--jour", help="AAAA-MM-JJ (par défaut aujourd'hui)")

    def handle(self, *args, **o):
        def task():
            from datetime import date
            jour = date.fromisoformat(o["jour"]) if o.get("jour") else None
            for line in C.du_jour(jour, n=o["n"], essai=o["essai"], force=o["force"]) or ["aucune vidéo fabriquée"]:
                out(line)
        run("clips", task)
