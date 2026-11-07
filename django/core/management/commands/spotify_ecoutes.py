"""Écoutes Spotify de chaque titre de nos artistes (07/11/2026) : Kworb chaque jour (gratuit), Apify pour les artistes
absents de Kworb (--apify, dans le plafond mensuel). Elles comptent dans le classement depuis la formule v5 (semaine 47).

  manage.py spotify_ecoutes            Kworb
  manage.py spotify_ecoutes --apify    Kworb puis Apify
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.imports import spotify_ecoutes


class Command(BaseCommand):
    help = "Relève les écoutes Spotify de chaque titre des artistes suivis."

    def add_arguments(self, p):
        p.add_argument("--apify", action="store_true", help="Compléter avec Apify pour les artistes absents de Kworb")

    def handle(self, *args, **o):
        def task():
            lignes = spotify_ecoutes.kworb()
            if o["apify"]:
                lignes += spotify_ecoutes.apify()
            for l in lignes:
                out(l)
            return lignes
        run("spotify_ecoutes", task)
