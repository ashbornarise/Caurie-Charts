"""Pays des artistes vérifié par Google : manage.py pays_google [--lots 4] [--taille 40] [--essai]"""
from django.core.management.base import BaseCommand

from core.services import pays_google


class Command(BaseCommand):
    help = "Vérifie le pays des artistes vus dans les classements avec Gemini + recherche Google (Google décide s'il est sûr)."

    def add_arguments(self, parser):
        parser.add_argument("--lots", type=int, default=4)
        parser.add_argument("--taille", type=int, default=pays_google.TAILLE)
        parser.add_argument("--essai", action="store_true", help="affiche sans rien modifier")

    def handle(self, *args, **o):
        for ligne in pays_google.verifier(o["lots"], o["taille"], appliquer=not o["essai"]):
            self.stdout.write(ligne)
