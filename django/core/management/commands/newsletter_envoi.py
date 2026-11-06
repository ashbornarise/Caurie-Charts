"""Lettre du mardi aux abonnés confirmés (après la publication du classement). manage.py newsletter_envoi"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services import newsletter


class Command(BaseCommand):
    help = "Envoie la newsletter de la semaine publiée aux abonnés confirmés."

    def handle(self, *args, **o):
        run("newsletter", lambda: [out(l) for l in newsletter.envoyer()])
