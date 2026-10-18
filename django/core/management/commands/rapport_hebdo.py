"""Génère puis envoie (ou écrit en mode essai) le rapport hebdomadaire."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from core import env
from core.management.commands._cli import out, run
from core.services import rapport


class Command(BaseCommand):
    help = "Génère le rapport hebdomadaire Cauri Charts."

    def add_arguments(self, parser):
        parser.add_argument("--essai", action="store_true", help="Écrit le PDF sur disque sans envoyer d'e-mail.")

    def handle(self, *args, **options):
        def task():
            data = rapport.collecter()
            texte = rapport.rediger(data)
            from core.services import rapport_pdf
            html, _ = rapport.rendre(data, texte)
            cible_pdf = Path(r"C:\Users\agbal\OneDrive\Documents\Cauri Charts - Posts\Essais agents\rapport-hebdo-essai.pdf") if options["essai"] else Path(__import__("tempfile").gettempdir()) / "rapport-hebdo.pdf"
            rapport_pdf.generer(data, texte, cible_pdf)
            if options["essai"]:
                out(f"Rapport PDF d'essai écrit : {cible_pdf}")
                return
            from core.mail import send_html_piece_jointe
            destinataire = env.get("RAPPORT_EMAIL", "") or env.get("MAIL_ADMIN", "")
            if not destinataire:
                raise CommandError("RAPPORT_EMAIL et MAIL_ADMIN sont absents.")
            resume = f"Rapport de la semaine du {data['semaine']['debut']} au {data['semaine']['fin']} : {data['semaine']['posts_crees']} publications et {data['semaine']['visites']} visites enregistrées. Le détail des statistiques et des échéances figure dans le PDF."
            resume_html = f"<p>{resume}</p><p>Le rapport détaillé est en pièce jointe.</p>"
            if not send_html_piece_jointe(destinataire, "[Cauri Charts] Rapport hebdomadaire", resume, resume_html, str(cible_pdf)):
                raise CommandError("L'envoi du rapport a échoué ou le SMTP n'est pas configuré.")
            out(f"Rapport envoyé à {destinataire}.")
        run("rapport_hebdo", task)
