"""Classement automatique des artistes en attente (MusicBrainz, Wikidata, puis IA).

  manage.py classify_artists
  manage.py classify_artists --limit=300
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services import ai
from core.services.imports.classifier import ArtistClassifier
from core.services.platforms import HttpClient


class Command(BaseCommand):
    help = "Classe automatiquement le pays des artistes en attente."

    def add_arguments(self, p):
        p.add_argument("--limit", type=int, default=60)

    def handle(self, *args, **o):
        def task():
            client = ai.make()
            s = ArtistClassifier(HttpClient(20), client).run(o["limit"])
            out(f"Artistes examinés : {s['checked']} — confirmés : {s['active']}, hors périmètre : {s['out_of_scope']}, "
                f"à vérifier par l’équipe : {s['pending']} (recherches IA : {s['ai_calls']}"
                + ("" if client else ", IA inactive : GEMINI_API_KEY absente (gratuite sur aistudio.google.com)") + ")")
        run("classify-artists", task)
