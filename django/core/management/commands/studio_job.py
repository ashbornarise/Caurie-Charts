"""Fabrique une vidéo Cauri Studio (téléchargement, analyse, habillage) : GitHub Actions, ou le PC si une plateforme
refuse les serveurs.  python manage.py studio_job --id 12"""
from django.core.management.base import BaseCommand, CommandError

from core.services.social import studio_montage


class Command(BaseCommand):
    help = "Fabrique la vidéo d'une tâche Cauri Studio."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, required=True)

    def handle(self, *args, **options):
        from core.studio import creer_tables
        creer_tables()
        try:
            r = studio_montage.traite(options["id"])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"tâche {options['id']} : {exc}")
        self.stdout.write(f"tâche {options['id']} : {r['statut']} ({r['video']})")
