"""Relais du PC pour Cauri Studio : lit les profils Instagram en attente et passe la main au tri sur GitHub.

Sans connexion, Instagram renvoie les serveurs (GitHub, Vercel) vers « Se connecter » pour une page de profil, mais
pas un PC de particulier. Le studio pose un marqueur dans le Blob (relais/profils/job-<id>.txt) ; ce relais (tâche
Windows toutes les 5 minutes) ne regarde que ces marqueurs — la base n'est réveillée que s'il y a du travail.
    python manage.py relais_profils
"""
import json
import re

from django.core.management.base import BaseCommand

PREFIXE = "relais/profils/"


class Command(BaseCommand):
    help = "Relève les posts photo des profils Instagram en attente et lance leur tri sur GitHub."

    def handle(self, *args, **options):
        from core import storage
        marqueurs = storage.blob_list(PREFIXE)
        if not marqueurs:
            return
        from core import db
        from core.services.social import studio_photos
        from core.studio import _lance
        for m in marqueurs:
            ident = re.search(r"job-(\d+)", m["pathname"])
            j = db.one("SELECT id, statut, params FROM studio_jobs WHERE id = ?", [int(ident.group(1))]) if ident else None
            if not j or j["statut"] != "attente_pc":
                storage.blob_delete([m["url"]])
                continue
            p = json.loads(j["params"] or "{}")
            posts = []
            for profil in p.get("profils") or []:
                trouves = studio_photos._posts_du_profil(profil)
                posts += trouves
                self.stdout.write(f"tâche {j['id']} : {profil} -> {len(trouves)} posts photo")
            liens = list(dict.fromkeys((p.get("liens") or []) + posts))[:40]
            if not liens:
                p["profils"] = []
                db.update("studio_jobs", {"statut": "erreur", "params": json.dumps(p, ensure_ascii=False),
                                          "erreur": "aucun post photo visible sur ce profil (seulement des vidéos ?)"},
                          "id = :id", {"id": j["id"]})
            else:
                p.update({"liens": liens, "profils_lus": p.get("profils") or [], "profils": []})
                db.update("studio_jobs", {"statut": "attente", "params": json.dumps(p, ensure_ascii=False)},
                          "id = :id", {"id": j["id"]})
                erreur = _lance(j["id"])
                if erreur:
                    db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": j["id"]})
            storage.blob_delete([m["url"]])
