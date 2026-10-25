"""Renouvelle le jeton d'accès TikTok (valable 24 h) : tâche GitHub toutes les 6 h, seule à détenir la clé secrète."""
from django.core.management.base import BaseCommand, CommandError

from core.management.commands._cli import out, run
from core.services import tiktok


class Command(BaseCommand):
    help = "Renouvelle le jeton TikTok du compte connecté (publication par le Studio)."

    def handle(self, *args, **options):
        def task():
            ligne = tiktok._ligne_active()
            if not ligne:
                out("Aucun compte TikTok connecté.")
                return
            if not tiktok.rafraichit(ligne):
                raise CommandError("Renouvellement du jeton TikTok refusé : reconnectez le compte sur /tiktok/connecter.")
            out("Jeton TikTok valide.")
        run("tiktok_jeton", task)
