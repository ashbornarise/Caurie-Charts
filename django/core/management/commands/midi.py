"""Passage de la mi-journée (06/11/2026) : nouvelles sorties Deezer et classements quotidiens d'Apple Music, Deezer et
Shazam, pour que le classement en direct suive les sorties et les télés sans attendre la nuit. Sans quota YouTube.

  manage.py midi
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.imports import sorties
from core.services.imports.service import ImportService


class Command(BaseCommand):
    help = "Sorties Deezer et classements Apple Music, Deezer, Shazam (mi-journée)."

    def handle(self, *args, **o):
        def task():
            for l in sorties.releve():
                out(l)
            for l in ImportService().import_all(None, ["apple_music", "deezer", "shazam"]):
                out(l)
        run("midi", task)
