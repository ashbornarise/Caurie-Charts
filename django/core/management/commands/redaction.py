"""Comité de rédaction : relecture du jour (vérité, fraîcheur, qualité) et, le lundi, analyste + directeur."""
from django.core.management.base import BaseCommand

from core import db
from core.management.commands._cli import out, run
from core.services import redaction


class Command(BaseCommand):
    help = "Fait travailler le comité de rédaction (agents DeepSeek)."

    def add_arguments(self, parser):
        parser.add_argument("--semaine", action="store_true", help="analyste + directeur (boucle d'amélioration)")

    def handle(self, *args, **options):
        def task():
            lignes = redaction.relecture_du_jour()
            if options["semaine"]:
                lignes += redaction.analyste() + redaction.directeur()
            from core.services import ia_budget
            lignes.append("budget IA : " + ia_budget.bilan())
            for l in lignes:
                out(l)
                if "bloquer" in l or "directeur" in l or "analyste" in l or "budget IA" in l:   # repris dans Admin > Contrôles et le rapport
                    db.insert("agent_findings", {"agent": "rédaction", "level": "alerte" if "bloquer" in l else "info",
                                                 "message": l[:600], "link": "/admin"})
            return lignes[:3]
        run("redaction", task)
