"""Partenaires média (Nec+Ultra…) : accès privé et envoi automatique des classements.

  manage.py partenaires --ajouter "Nec+Ultra Media" --emails a@x.ci,b@x.ci --pays CI   crée l'accès, affiche le lien privé
  manage.py partenaires --liste
  manage.py partenaires --envoyer [--semaine 2026-W46] [--id 1] [--a moi@exemple.com]   (--a : essai, non marqué envoyé)
  manage.py partenaires --apercu dossier [--semaine 2026-W46] [--id 1]                  fichiers écrits en local, rien d'envoyé
  manage.py partenaires --desactiver 1
  manage.py partenaires --espace 1 --slug nec-ultra [--mot-de-passe X] [--couleurs "#111111,#C9A227"] [--logo URL]
      espace protégé /espace/<slug> ; sans --mot-de-passe, un mot de passe est créé et affiché une seule fois
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
        p.add_argument("--espace", type=int, metavar="ID")
        p.add_argument("--slug")
        p.add_argument("--mot-de-passe", dest="mdp")
        p.add_argument("--couleurs")
        p.add_argument("--logo")

    def handle(self, *args, **o):
        def task():
            from core import clock, db
            from core.services import partenaires as P
            from core.services.charts import Period
            P.assure_tables()
            semaine = o["semaine"] or Period.last_completed_week(clock.today().isoformat()).key
            if o["espace"]:
                import secrets as S
                from core.backoffice import auth
                champs = {}
                if o["slug"]:
                    champs["slug"] = o["slug"].strip().lower()
                mdp = o["mdp"] or ("-".join(S.token_hex(2) for _ in range(4)) if not db.value(
                    "SELECT mdp_hash FROM partenaires_acces WHERE id = ?", [o["espace"]]) else None)
                if mdp:
                    champs["mdp_hash"] = auth.hash_password(mdp)
                if o["couleurs"]:
                    c = [x.strip() for x in o["couleurs"].split(",")]
                    champs.update(couleur=c[0], couleur2=c[1] if len(c) > 1 else None)
                if o["logo"]:
                    champs["logo_url"] = o["logo"]
                if champs:
                    db.update("partenaires_acces", champs, "id = :id", {"id": o["espace"]})
                slug = db.value("SELECT slug FROM partenaires_acces WHERE id = ?", [o["espace"]])
                out(f"Espace : https://cauricharts.com/espace/{slug}" + (f" · mot de passe : {mdp}" if mdp else ""))
            elif o["ajouter"]:
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
