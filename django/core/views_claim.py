"""« Revendiquer ma fiche » : un artiste, son management ou son label demande à gérer sa fiche.

La demande arrive dans Admin > Messages (type « claim ») ; l'équipe vérifie les preuves (comptes officiels,
e-mail du domaine du label…) avant toute modification. Rien n'est changé automatiquement sur la fiche.
"""
from django.http import Http404

from core import db, repos
from core.helpers import brand
from core.views import EMAIL_RE, flash, ip_hash, now_utc, redirect, render, req_str, use_locale

ROLES = {"artiste": "L’artiste", "management": "Son management", "label": "Son label ou distributeur", "autre": "Autre (préciser)"}


def claim(request, slug: str):
    artist = repos.artist(slug)
    if not artist:
        raise Http404
    use_locale(request)
    meta = {"title": f"Revendiquer la fiche de {artist['name']} · {brand()}", "description": f"Vous êtes {artist['name']} ou son équipe ? "
            "Demandez à gérer la fiche : photo, biographie, liens officiels."}
    if request.method != "POST":
        return render(request, "claim", {"artist": artist, "roles": ROLES, "old": {}, "errors": {}, "meta": meta})
    old = {k: req_str(request, k)[:n] for k, n in (("name", 150), ("email", 190), ("role", 20), ("phone", 40),
                                                   ("proof", 2000), ("message", 3000))}
    if req_str(request, "website"):
        return redirect(f"/artiste/{slug}")  # pot de miel : robot
    errors = {}
    if not old["name"]:
        errors["name"] = "Champ obligatoire."
    if not EMAIL_RE.match(old["email"]):
        errors["email"] = "Adresse e-mail invalide."
    if old["role"] not in ROLES:
        errors["role"] = "Choisissez votre lien avec l’artiste."
    if len(old["proof"]) < 8:
        errors["proof"] = "Indiquez au moins un compte officiel (Instagram, YouTube, TikTok…) qui permet de vérifier."
    h = ip_hash(request)
    if int(db.value("SELECT COUNT(*) FROM contact_messages WHERE ip_hash = ? AND created_at > ?", [h, now_utc(-86400)])) >= 5:
        errors["message"] = "Trop de demandes aujourd’hui, réessayez demain."
    if errors:
        return render(request, "claim", {"artist": artist, "roles": ROLES, "old": old, "errors": errors, "meta": meta}, 422)
    body = "\n".join([f"Fiche : /artiste/{slug} ({artist['name']})", f"Lien avec l’artiste : {ROLES[old['role']]}",
                      f"Téléphone / WhatsApp : {old['phone'] or '-'}", "", "Preuves (comptes officiels) :", old["proof"], "",
                      "Demande :", old["message"] or "-"])
    db.insert("contact_messages", {"type": "claim", "name": old["name"], "email": old["email"],
                                   "subject": f"Revendication : {artist['name']}"[:200], "message": body, "ip_hash": h})
    flash(request, "success", "Demande envoyée. Nous vérifions les preuves et revenons vers vous par e-mail sous sept jours.")
    return redirect(f"/artiste/{slug}")
