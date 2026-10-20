"""Relais du PC pour Cauri Studio : lit les profils Instagram en attente et passe la main au tri sur GitHub.

Même travail que le téléphone (outils/relais_telephone.py) : sans connexion, Instagram renvoie les serveurs vers
« Se connecter » pour une page de profil, pas un PC de particulier. Ne lit que les marqueurs du Blob : la base n'est
réveillée que s'il y a du travail. Tâche Windows toutes les 5 minutes.
    python manage.py relais_profils
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Relève les posts photo des profils Instagram en attente et lance leur tri sur GitHub."

    def handle(self, *args, **options):
        from core import storage, views_relais
        from core.services.social import studio_photos
        for x in views_relais.a_relever():
            posts = []
            for profil in x["profils"]:
                trouves = studio_photos._posts_du_profil(profil)
                posts += trouves
                self.stdout.write(f"tâche {x['job']} : {profil} -> {len(trouves)} posts photo")
            etat = views_relais.termine(x["job"], posts)
            storage.blob_delete([x["marqueur"]])
            self.stdout.write(f"tâche {x['job']} : {etat}")
