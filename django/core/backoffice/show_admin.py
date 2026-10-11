"""Admin > Show : la régie du vote du public (opérateur « D » du scénario Édition 1).

Préparer les votes depuis le conducteur réel, ouvrir / sceller / fermer chaque vote, voir les vrais chiffres (voix valides et
mises de côté), indiquer la bonne réponse des pronostics, activer les codes secrets, sortir les gagnants des distinctions.
"""
import json

from core import audit, conf, db
from core.backoffice.views import admin_render, admin_view, back, ip, uid
from core.helpers import path
from core.views import now_utc, req_str

STATUTS = ("brouillon", "ouvert", "scelle", "ferme")


@admin_view()
def show(request):
    from core.services import show_vote as V
    key = conf.get("show.key")
    if request.method == "POST":
        action = req_str(request, "action")
        if action == "preparer":
            from core.services import show
            n = V.preparer_votes(key, show.programme())
            audit.log(uid(request), "show.preparer", "show_poll", None, None, {"crees": n}, ip(request))
            return back(request, path("admin/show"), "success", f"{n} vote(s) préparé(s) depuis le conducteur, et les codes secrets.")
        if action == "statut":
            pid, statut = int(req_str(request, "poll") or 0), req_str(request, "statut")
            if statut in STATUTS:
                champs = {"status": statut}
                if statut == "ouvert":
                    champs["opened_at"] = now_utc()
                if statut == "ferme":
                    champs["closed_at"] = now_utc()
                db.update("show_polls", champs, "id = :id", {"id": pid})
                audit.log(uid(request), "show.vote", "show_poll", pid, None, {"statut": statut}, ip(request))
            return back(request, path("admin/show") + f"#v{pid}")
        if action == "reponse":
            pid = int(req_str(request, "poll") or 0)
            db.update("show_polls", {"answer": req_str(request, "answer")[:60] or None}, "id = :id", {"id": pid})
            return back(request, path("admin/show") + f"#v{pid}", "success", "Bonne réponse enregistrée.")
        if action == "code":
            cid, statut = int(req_str(request, "code") or 0), req_str(request, "statut")
            if statut == "actif":
                db.run("UPDATE show_codes SET status = 'expire' WHERE show_key = ? AND status = 'actif'", [key])
                db.update("show_codes", {"status": "actif", "activated_at": now_utc()}, "id = :id", {"id": cid})
            elif statut == "expire":
                db.update("show_codes", {"status": "expire"}, "id = :id", {"id": cid})
            return back(request, path("admin/show") + "#codes")
        if action == "voix":
            vid, f = int(req_str(request, "vote") or 0), 1 if req_str(request, "flag") == "1" else 0
            db.update("show_votes", {"flagged": f}, "id = :id", {"id": vid})
            return back(request, path("admin/show") + "#suspectes")
    polls = db.all("SELECT * FROM show_polls WHERE show_key = ? ORDER BY sort_order, id", [key])
    for p in polls:
        p["opts"] = json.loads(p["options"] or "[]")
        p["res"] = V.resultats({**p, "options": p["opts"]}, admin=True)
    return admin_render(request, "show", {
        "title": "Show · régie du vote", "key": key, "polls": polls,
        "codes": db.all("SELECT c.*, (SELECT COUNT(*) FROM show_code_entries e WHERE e.code_id = c.id) AS n FROM show_codes c WHERE show_key = ? ORDER BY id", [key]),
        "comptes": int(db.value("SELECT COUNT(*) FROM show_accounts WHERE verified_at IS NOT NULL") or 0),
        "suspectes": db.all("""SELECT v.id, v.option_key, v.flagged, v.created_at, a.pseudo, a.email, p.slug FROM show_votes v
                               JOIN show_accounts a ON a.id = v.account_id JOIN show_polls p ON p.id = v.poll_id
                               WHERE p.show_key = ? AND v.flagged = 1 ORDER BY v.id DESC LIMIT 100""", [key]),
        "gagnants": V.distinctions_public(key), "statuts": STATUTS,
    })
