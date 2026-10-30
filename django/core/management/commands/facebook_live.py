"""Direct Facebook du show : manage.py facebook_live creer|etat|commentaires [--quand 2026-11-07T20:00]"""
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from core.services import facebook_live

TITRE = "The Monthly Show · Édition 1 — les classements d'octobre en direct"
DESCRIPTION = ("Cauri Charts, la référence de la musique ouest-africaine, présente The Monthly Show : les Top 5 de chaque pays "
               "révélés en direct, les distinctions du mois et vos votes à l'écran. Rendez-vous samedi à 20 h GMT. "
               "Votez sur cauricharts.com/show")


class Command(BaseCommand):
    help = "Crée le direct Facebook programmé du show, ou en donne l'état et les commentaires."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["creer", "etat", "commentaires"])
        parser.add_argument("--quand", default="2026-11-07T20:00", help="début, en heure GMT (AAAA-MM-JJTHH:MM)")
        parser.add_argument("--titre", default=TITRE)

    def handle(self, *args, **o):
        if o["action"] == "creer":
            quand = datetime.fromisoformat(o["quand"]).replace(tzinfo=timezone.utc)
            r = facebook_live.creer(quand, o["titre"], DESCRIPTION)
            self.stdout.write(f"Direct créé : {r['lien']} (début {r['debut']}, statut {r['statut']})")
            self.stdout.write(f"Clé de diffusion enregistrée dans {facebook_live.FICHIER_CLE} : node live/obs_facebook.mjs pour OBS")
        elif o["action"] == "etat":
            self.stdout.write(str(facebook_live.etat()))
        else:
            for c in facebook_live.commentaires():
                self.stdout.write(f"{c['nom']} : {c['texte']}")
