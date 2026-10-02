"""Admin > Équipe : comptes de l'administration (réservé au rôle admin).

Ajout d'un compte avec mot de passe généré, affiché une seule fois dans la page (jamais dans un cookie ni un e-mail),
changement de rôle, désactivation, réinitialisation du mot de passe. Garde-fous : on ne peut ni se désactiver
soi-même ni retirer le dernier administrateur actif. Toute action est écrite au journal d'audit.
"""
import base64
import re
import secrets

from django.http import HttpResponseBadRequest

from core import audit, db
from core.backoffice import auth
from core.backoffice.views import admin_render, admin_view, back, ip, uid
from core.helpers import path
from core.views import req_str

ROLES = {"admin": "Administrateur (tout, y compris la formule, le journal et l’équipe)",
         "editor": "Éditeur (classements, déclarations, actualités, posts, messages)"}
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _password() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(15)).decode().rstrip("=") + "a1!"


def _page(request, shown=None, errors=None, old=None, status=200):
    rows = db.all("SELECT id, email, name, role, is_active, last_login_at, created_at, (totp_secret IS NOT NULL) AS has_2fa FROM users ORDER BY is_active DESC, role, name")
    return admin_render(request, "team", {"rows": rows, "roles": ROLES, "shown": shown, "errors": errors or {}, "old": old or {},
                                          "me": uid(request), "title": "Équipe"}, status)


def _active_admins() -> int:
    return int(db.value("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"))


@admin_view("admin")
def team(request):
    if request.method != "POST":
        return _page(request)
    old = {"email": req_str(request, "email").lower()[:190], "name": req_str(request, "name")[:150], "role": req_str(request, "role")}
    errors = {}
    if not EMAIL.fullmatch(old["email"]):
        errors["email"] = "Adresse e-mail invalide."
    elif db.value("SELECT 1 FROM users WHERE email = ?", [old["email"]]):
        errors["email"] = "Un compte existe déjà avec cette adresse."
    if not old["name"]:
        errors["name"] = "Champ obligatoire."
    if old["role"] not in ROLES:
        errors["role"] = "Choisissez un rôle."
    # Mot de passe choisi par l'admin, ou généré si le champ reste vide
    chosen = str(request.POST.get("password") or "")
    if chosen and auth.password_problem(chosen):
        errors["password"] = auth.password_problem(chosen)
    if errors:
        return _page(request, errors=errors, old=old, status=422)
    password = chosen or _password()
    new_id = db.insert("users", {"email": old["email"], "name": old["name"], "role": old["role"], "is_active": 1,
                                 "password_hash": auth.hash_password(password)})
    audit.log(uid(request), "user.create", "user", new_id, None, {"role": old["role"], "email": old["email"]}, ip(request))
    # Mot de passe affiché dans la réponse même : il ne passe ni par un cookie ni par une redirection
    return _page(request, shown={"id": new_id, "email": old["email"], "name": old["name"], "password": password, "created": True})


@admin_view("admin")
def welcome(request, member_id: str):
    """Fiche d'accueil PDF : le mot de passe renvoyé par la page n'y figure que s'il est bien celui du compte."""
    from django.http import HttpResponse
    from core.backoffice import welcome_pdf
    target = db.one("SELECT id, email, name, role, password_hash FROM users WHERE id = ?", [int(member_id)])
    if not target or request.method != "POST":
        return HttpResponseBadRequest()
    password = str(request.POST.get("password") or "")
    if password and not auth.verify_password(password, target["password_hash"]):
        password = ""
    audit.log(uid(request), "user.welcome_pdf", "user", target["id"], None, {"with_password": bool(password)}, ip(request))
    slug = re.sub(r"[^a-z0-9]+", "-", target["name"].lower()).strip("-") or "membre"
    resp = HttpResponse(welcome_pdf.build(target, password or None), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="cauri-charts-fiche-accueil-{slug}.pdf"'
    resp["Cache-Control"] = "no-store"
    return resp


@admin_view("admin")
def member(request, member_id: str):
    target = db.one("SELECT id, email, name, role, is_active FROM users WHERE id = ?", [int(member_id)])
    action = req_str(request, "action")
    if not target or request.method != "POST":
        return HttpResponseBadRequest()
    me = uid(request)
    is_last_admin = target["role"] == "admin" and target["is_active"] and _active_admins() <= 1
    if action in ("desactiver", "editor") and int(target["id"]) == me:
        return back(request, path("admin/equipe"), "error", "Vous ne pouvez pas retirer vos propres droits.")
    if action in ("desactiver", "editor") and is_last_admin:
        return back(request, path("admin/equipe"), "error", "Impossible : c’est le dernier administrateur actif.")
    if action == "desactiver":
        db.update("users", {"is_active": 0}, "id = :id", {"id": target["id"]})
    elif action == "activer":
        db.update("users", {"is_active": 1}, "id = :id", {"id": target["id"]})
    elif action in ROLES:
        db.update("users", {"role": action}, "id = :id", {"id": target["id"]})
    elif action == "mot-de-passe":
        password = _password()
        db.update("users", {"password_hash": auth.hash_password(password)}, "id = :id", {"id": target["id"]})
        audit.log(me, "user.reset", "user", target["id"], None, {}, ip(request))
        return _page(request, shown={"id": target["id"], "email": target["email"], "name": target["name"], "password": password, "created": False})
    else:
        return HttpResponseBadRequest()
    audit.log(me, "user." + action, "user", target["id"], None, {}, ip(request))
    return back(request, path("admin/equipe"), "success", f"Compte de {target['name']} mis à jour.")
