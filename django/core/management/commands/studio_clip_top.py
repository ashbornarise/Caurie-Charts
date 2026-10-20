"""Crée un job studio pour le clip d'un artiste au top (hors classement officiel publié).

  manage.py studio_clip_top --url=https://www.youtube.com/watch?v=DBQONV9RATY \
      --artiste=Himra --titre="Plus de Love" --pays=CI --rang=1
"""
import json

from django.core.management.base import BaseCommand

from core import db
from core.helpers import country_name
from core.management.commands._cli import out, run


PREPOSITION = {"CI": "en Côte d'Ivoire", "GN": "en Guinée", "GW": "en Guinée-Bissau", "SL": "en Sierra Leone",
               "GM": "en Gambie", "MR": "en Mauritanie"}


def _au(code: str) -> str:
    return PREPOSITION.get(code, "au " + country_name(code))


class Command(BaseCommand):
    help = "Crée un job studio pour le clip d'un artiste au top."

    def add_arguments(self, p):
        p.add_argument("--url", required=True, help="Lien YouTube du clip")
        p.add_argument("--artiste", required=True)
        p.add_argument("--titre", required=True)
        p.add_argument("--pays", required=True, help="Code pays (TG, CI, NG…)")
        p.add_argument("--rang", type=int, default=1, help="Position (défaut 1)")

    def handle(self, *args, **o):
        def task():
            from core import storage
            from core.studio import creer_tables
            creer_tables()
            code = o["pays"].upper()
            rang = o["rang"]
            rang_txt = f"N°{rang}"
            params = json.dumps({
                "etiquette": f"{rang_txt} {_au(code).upper()}",
                "accroche": o["titre"].upper(),
                "artiste": o["artiste"],
                "credit": f"clip officiel de {o['artiste']} (YouTube)",
                "legende_fr": f"{rang_txt} {_au(code)} cette semaine — {o['titre']} de {o['artiste']}.",
                "legende_en": f"#{rang} in {country_name(code)} this week — {o['titre']} by {o['artiste']}.",
                "valider": False,
                "refrain_auto": True,
                "duree": 20,
                "debut": 0,
                "fin": 60,
                "format": "story",
                "contexte": f"top-{code}-{rang}",
            }, ensure_ascii=False)
            job_id = db.insert("studio_jobs", {"lien": o["url"], "params": params, "auteur": 1})
            db.update("studio_jobs", {"statut": "attente_pc"}, "id = :id", {"id": job_id})
            storage.blob_put(f"relais/studio/job-{job_id}.json", json.dumps({"job": job_id}).encode(), "application/json")
            out(f"Job {job_id} créé : {o['artiste']} — {o['titre']} ({rang_txt} {_au(code)}) [attente PC]")
            return [f"job {job_id}"]
        run("studio-clip-top", task)
