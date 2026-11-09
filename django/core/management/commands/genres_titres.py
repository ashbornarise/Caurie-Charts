"""Étiquette le genre des titres (Apple Music, puis Google pour les cas ambigus) pour les classements par genre.

  manage.py genres_titres                 400 titres, les plus classés d'abord
  manage.py genres_titres --limite=2000   premier passage complet
  manage.py genres_titres --sans-ia       Apple Music seulement
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run


class Command(BaseCommand):
    help = "Étiquette le genre des titres pour les classements par genre."

    def add_arguments(self, p):
        p.add_argument("--limite", type=int, default=400)
        p.add_argument("--sans-ia", action="store_true")
        p.add_argument("--reprendre", action="store_true", help="Revoir les titres sans genre ou « afrobeats » jamais vérifiés par Google")

    def handle(self, *args, **o):
        def task():
            from core.services import genres
            b = genres.etiqueter(o["limite"], avec_ia=not o["sans_ia"], reprendre=o["reprendre"])
            out(f"{b['titres']} titre(s) : {b['apple']} par Apple Music, {b['ia']} vérifié(s) par Google, {b['sans']} sans genre ; {b.get('artistes_ia', 0)} artiste(s) envoyés à la vérification Google")
        run("genres-titres", task)
