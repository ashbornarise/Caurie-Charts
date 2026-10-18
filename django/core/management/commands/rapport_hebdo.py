"""Génère puis envoie (ou écrit en mode essai) le rapport hebdomadaire."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from core import env
from core.management.commands._cli import out, run
from core.services import rapport


class Command(BaseCommand):
    help = "Génère le rapport hebdomadaire Cauri Charts."

    def add_arguments(self, parser):
        parser.add_argument("--essai", action="store_true", help="Écrit le rapport HTML sur disque sans envoyer d'e-mail.")

    def handle(self, *args, **options):
        def task():
            data = rapport.collecter()
            texte = rapport.rediger(data)
            html, _ = rapport.rendre(data, texte)
            if options["essai"]:
                cible = Path(r"C:\Users\agbal\OneDrive\Documents\Cauri Charts - Posts\Essais agents\rapport-hebdo-essai.html")
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_text(html, encoding="utf-8")
                out(f"Rapport d'essai écrit : {cible}")
                return
            from core.mail import send_html
            destinataire = env.get("RAPPORT_EMAIL", "") or env.get("MAIL_ADMIN", "")
            if not destinataire:
                raise CommandError("RAPPORT_EMAIL et MAIL_ADMIN sont absents.")
            if not send_html(destinataire, "[Cauri Charts] Rapport hebdomadaire", texte, html):
                raise CommandError("L'envoi du rapport a échoué ou le SMTP n'est pas configuré.")
            out(f"Rapport envoyé à {destinataire}.")
        run("rapport_hebdo", task)
