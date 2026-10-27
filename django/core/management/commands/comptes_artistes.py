"""Trouve les comptes Instagram et TikTok officiels des artistes (Gemini + recherche Google), les plus suivis d'abord."""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.social import comptes


class Command(BaseCommand):
    help = "Complète les comptes Instagram / TikTok officiels des artistes (mentions et collaborations)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=40)
        parser.add_argument("--nom", default="", help="un seul artiste (nom exact)")

    def handle(self, *args, **options):
        def task():
            comptes.colonnes()
            liste = (comptes.db.all("SELECT * FROM artists WHERE lower(name) = lower(?) LIMIT 1", [options["nom"]])
                     if options["nom"] else comptes.a_chercher(options["limit"]))
            trouves = 0
            for a in liste:
                try:
                    champs = comptes.completer(a)
                except Exception as exc:  # noqa: BLE001 — quota Gemini épuisé : on reprendra demain
                    out(f"{a['name']} : {exc}")
                    if "quota" in str(exc).lower() or "429" in str(exc):
                        break
                    continue
                trouves += bool(champs)
                out(f"{a['name']} : " + (", ".join(f"{k} @{v}" for k, v in champs.items()) or "rien de sûr"))
            out(f"{trouves} artiste(s) complété(s) sur {len(liste)}.")
        run("comptes_artistes", task)
