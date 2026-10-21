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
    upload = request.FILES.get("photo")
    old["photo_ok"] = request.POST.get("photo_ok") == "1"
    photo_data = None
    if upload:
        from core import storage
        try:
            if upload.size > 4 * 1024 * 1024:
                raise ValueError("Photo trop lourde (4 Mo au plus) : envoyez-la par e-mail à contact@cauricharts.com.")
            ext = storage.check_image(upload)
            photo_data = (upload.read(), ext)
        except ValueError as exc:
            errors["photo"] = str(exc)
        if photo_data and not old["photo_ok"]:
            errors["photo"] = "Cochez l’autorisation d’utiliser la photo."
    if errors:
        return render(request, "claim", {"artist": artist, "roles": ROLES, "old": old, "errors": errors, "meta": meta}, 422)
    photo_line = _store_press_photo(artist, photo_data, old) if photo_data else ""
    body = "\n".join([f"Fiche : /artiste/{slug} ({artist['name']})", *([photo_line] if photo_line else []),
                      f"Lien avec l’artiste : {ROLES[old['role']]}",
                      f"Téléphone / WhatsApp : {old['phone'] or '-'}", "", "Preuves (comptes officiels) :", old["proof"], "",
                      "Demande :", old["message"] or "-"])
    db.insert("contact_messages", {"type": "contestation", "name": old["name"], "email": old["email"],
                                   "subject": f"Revendication : {artist['name']}"[:200], "message": body, "ip_hash": h})
    from core import mail
    mail.notify_admin(f"Revendication : {artist['name']}", f"De : {old['name']} <{old['email']}>\n\n{body}", old["email"])
    mail.acknowledge(old["email"], old["name"], "demande de revendication")
    flash(request, "success", "Demande envoyée. Nous vérifions les preuves et revenons vers vous par e-mail sous sept jours.")
    return redirect(f"/artiste/{slug}")


def _store_press_photo(artist: dict, photo: tuple, old: dict) -> str:
    """Photo presse envoyée avec la revendication : déposée et ajoutée aux photos candidates de l'artiste
    (Admin > fiche artiste > Photo). Elle n'est jamais utilisée avant d'avoir été choisie dans l'admin."""
    import io
    import json
    import secrets
    from PIL import Image
    from core import storage
    data, ext = photo
    name = f"presse-{artist['slug']}-{secrets.token_hex(4)}.{ext}"
    storage.store_media("artists", name, data, "image/" + ("jpeg" if ext == "jpg" else ext))
    base = storage.blob_public_url()
    url = f"{base}/media/artists/{name}" if base else f"/media/artists/{name}"
    side = min(Image.open(io.BytesIO(data)).size)
    row = db.one("SELECT photo_candidates FROM artists WHERE id = ?", [artist["id"]]) or {}
    try:
        cands = json.loads(row.get("photo_candidates") or "[]")
    except ValueError:
        cands = []
    cands.insert(0, {"source": "presse", "url": url, "site": url, "side": side,
                     "credit": f"Photo fournie par {old['name']} ({ROLES.get(old['role'], old['role'])})"[:250]})
    db.update("artists", {"photo_candidates": json.dumps(cands, ensure_ascii=False)}, "id = :id", {"id": artist["id"]})
    return f"Photo presse envoyée ({side} px), à valider dans Admin > fiche de l'artiste > Photo : {url}"
