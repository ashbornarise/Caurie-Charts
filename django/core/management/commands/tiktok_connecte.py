"""Échange le dernier code TikTok reçu récemment."""
from django.core.management.base import BaseCommand, CommandError

from core.management.commands._cli import out, run
from core.services import tiktok


class Command(BaseCommand):
    help = "Échange le dernier code d'autorisation TikTok reçu (valable 10 minutes)."

    def handle(self, *args, **options):
        def task():
            tiktok.creer_table()
            ligne = __import__("core.db", fromlist=["one"]).one(
                "SELECT id FROM tiktok_auth WHERE code IS NOT NULL AND recu_le >= NOW() - INTERVAL '10 minutes' ORDER BY recu_le DESC LIMIT 1")
            if not ligne or not tiktok.echange_code():
                raise CommandError("Connexion TikTok non disponible.")
            out("Connexion TikTok établie.")
        run("tiktok_connecte", task)
