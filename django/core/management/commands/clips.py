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
        p.add_argument("--n", type=int, default=3)
        p.add_argument("--essai", action="store_true")

    def handle(self, *args, **o):
        def task():
            for line in C.du_jour(n=o["n"], essai=o["essai"]) or ["aucune vidéo fabriquée"]:
                out(line)
        run("clips", task)
