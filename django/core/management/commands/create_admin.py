"""Crée (ou réinitialise) un compte de l'administration.

  manage.py create_admin email@exemple.com "Nom"                 rôle admin, mot de passe généré
  manage.py create_admin email@exemple.com "Nom" --role=editor
  manage.py create_admin email@exemple.com "Nom" --password="..." --totp

--totp active la double authentification et affiche le secret à scanner.
"""
import base64
import re
import secrets

from django.core.management.base import BaseCommand

from core import audit, conf, db
from core.backoffice import auth
from core.management.commands._cli import out, run


class Command(BaseCommand):
    help = "Crée ou réinitialise un compte de l'administration."

    def add_arguments(self, p):
        p.add_argument("email")
        p.add_argument("name")
        p.add_argument("--role", default="admin")
        p.add_argument("--password")
        p.add_argument("--totp", action="store_true")

    def handle(self, *args, **o):
        def task():
            email, name = o["email"].lower(), o["name"]
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or not name:
                raise ValueError('Usage : manage.py create_admin email@exemple.com "Nom" [--role=admin|editor] [--password=...] [--totp]')
            role = "editor" if o["role"] == "editor" else "admin"
            generated = not o["password"]
            password = (base64.urlsafe_b64encode(secrets.token_bytes(15)).decode().rstrip("=") + "a1!") if generated else o["password"]
            problem = auth.password_problem(password)
            if problem:
                raise ValueError(f"Mot de passe trop faible : {problem}")
            secret = auth.totp_secret() if o["totp"] else None
            existing = db.one("SELECT id FROM users WHERE email = ?", [email])
            data = {"name": name, "password_hash": auth.hash_password(password), "role": role, "is_active": 1}
            if secret:
                data["totp_secret"] = secret
            if existing:
                db.update("users", data, "id = :id", {"id": existing["id"]})
                uid = int(existing["id"])
            else:
                uid = db.insert("users", {**data, "email": email})
            audit.log(None, "user.reset" if existing else "user.create", "user", uid, "manage.py create_admin", {"role": role})
            out(("Compte mis à jour" if existing else "Compte créé") + f" : {email} ({role})")
            if generated:
                out(f"Mot de passe (affiché une seule fois) : {password}")
            if secret:
                out(f"Secret 2FA : {secret}")
                out("URI à ajouter dans l'application d'authentification : " + auth.totp_uri(secret, email, str(conf.get("app.name"))))
            out("Connexion : " + conf.get("app.url") + "/admin")
        run("create-admin", task)
