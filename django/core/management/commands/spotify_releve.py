"""Relevé Spotify de la semaine (Apify) : auditeurs des artistes qui buzzent, titres des playlists suivies."""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services import spotify_apify


class Command(BaseCommand):
    help = "Relève les chiffres Spotify de la semaine (offre gratuite d'Apify, plafond mensuel)."

    def handle(self, *args, **options):
        def task():
            lignes = spotify_apify.auditeurs() + spotify_apify.playlists()
            for l in lignes:
                out(l)
            return lignes
        run("spotify_releve", task)
