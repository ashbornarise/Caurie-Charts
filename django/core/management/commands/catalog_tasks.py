"""Tâches du catalogue lancées une à une (la chaîne quotidienne « daily » les enchaîne toutes).

  manage.py catalog_tasks news          actualités (flux RSS de config/news.php)
  manage.py catalog_tasks discover      découverte d'artistes (Wikidata, réseau Deezer)
  manage.py catalog_tasks enrich [--limit=300]   profils Deezer (photo, fans)
  manage.py catalog_tasks watch         liste de suivi (config/watchlist.php)
  manage.py catalog_tasks channels      chaînes YouTube des artistes
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.platforms import HttpClient


class Command(BaseCommand):
    help = "Actualités, découverte, profils, liste de suivi, chaînes YouTube."

    def add_arguments(self, p):
        p.add_argument("task", choices=["news", "discover", "enrich", "watch", "channels"])
        p.add_argument("--limit", type=int, default=80)

    def handle(self, *args, **o):
        def task():
            http = HttpClient(60)
            if o["task"] == "news":
                from core.services.news import FeedImporter
                lines = FeedImporter().run()
            elif o["task"] == "discover":
                from core.services.imports.discovery import ArtistDiscovery
                lines = ArtistDiscovery(http).run()
            elif o["task"] == "enrich":
                from core.services.imports.matching import ArtistEnricher
                s = ArtistEnricher(http).run(o["limit"])
                lines = [f"Profils vérifiés : {s['checked']}, trouvés sur Deezer : {s['found']}"]
            elif o["task"] == "watch":
                from core.services.imports.watch import ArtistWatch
                lines = ArtistWatch(http).run()
            else:
                from core.services.imports.channel_sync import YouTubeChannelSync
                lines = YouTubeChannelSync(http).run()
            for line in lines:
                out(line)
        run(o["task"], task)
