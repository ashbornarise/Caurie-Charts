"""Partenaires média (Nec+Ultra…) : accès privé et envoi automatique des classements.

  manage.py partenaires --ajouter "Nec+Ultra Media" --emails a@x.ci,b@x.ci --pays CI   crée l'accès, affiche le lien privé
  manage.py partenaires --liste
  manage.py partenaires --envoyer [--semaine 2026-W46] [--id 1] [--a moi@exemple.com]   (--a : essai, non marqué envoyé)
  manage.py partenaires --apercu dossier [--semaine 2026-W46] [--id 1]                  fichiers écrits en local, rien d'envoyé
  manage.py partenaires --desactiver 1
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run


class Command(BaseCommand):
    help = "Gère les partenaires média et leur envoi hebdomadaire."

    def add_arguments(self, p):
        p.add_argument("--ajouter", metavar="NOM")
        p.add_argument("--emails", default="")
        p.add_argument("--pays", default="")
        p.add_argument("--liste", action="store_true")
        p.add_argument("--envoyer", action="store_true")
        p.add_argument("--apercu", metavar="DOSSIER")
        p.add_argument("--semaine")
        p.add_argument("--id", type=int)
        p.add_argument("--a", default="", help="Destinataires d'essai, séparés par des virgules")
        p.add_argument("--forcer", action="store_true", help="Renvoyer une édition déjà envoyée")
        p.add_argument("--desactiver", type=int)

    def handle(self, *args, **o):
        def task():
            from core import clock, db
            from core.services import partenaires as P
            from core.services.charts import Period
            P.assure_tables()
            semaine = o["semaine"] or Period.last_completed_week(clock.today().isoformat()).key
            if o["ajouter"]:
                r = P.ajouter(o["ajouter"], o["emails"].split(","), o["pays"].split(","))
                out(f"Partenaire n°{r['id']} créé. Lien privé (à garder secret) : {r['lien']}")
            elif o["desactiver"]:
                db.run("UPDATE partenaires_acces SET actif = 0 WHERE id = ?", [o["desactiver"]])
                out(f"Partenaire n°{o['desactiver']} désactivé (son lien ne marche plus)")
            elif o["liste"]:
                for p in db.all("SELECT * FROM partenaires_acces ORDER BY id"):
                    out(f"n°{p['id']} {p['nom']} · {p['emails']} · pays {p['pays'] or 'Afrique de l’Ouest'} · "
                        f"{'actif' if p['actif'] else 'désactivé'} · {P.lien(p['jeton'])}")
            elif o["apercu"]:
                p = db.one("SELECT * FROM partenaires_acces WHERE id = ?", [o["id"]]) if o["id"] else \
                    {"nom": "Aperçu", "pays": o["pays"] or "CI", "jeton": "apercu"}
                dossier = Path(o["apercu"])
                dossier.mkdir(parents=True, exist_ok=True)
                fichiers = P.dossier(semaine, p)
                fichiers.pop("_donnees", None)
                for nom, data in fichiers.items():
                    (dossier / nom).write_bytes(data)
                out(f"{len(fichiers)} fichier(s) écrit(s) dans {dossier}" if fichiers else f"rien de publié pour {semaine}")
            elif o["envoyer"]:
                for ligne in P.envoyer(semaine, o["id"], [a for a in o["a"].split(",") if a] or None, o["forcer"]):
                    out(ligne)
        run("partenaires", task)
