"""Cauri Studio — éditeur vidéo privé (20/10/2026).

Adresse secrète /studio/<STUDIO_CHEMIN> (404 sinon, jamais indexée). Accès : session admin existante (éditeur ou plus)
ou passkey WebAuthn (empreinte, Face ID, code de l'appareil). Le lien collé est téléchargé, analysé et habillé sur
GitHub Actions (studio_montage.py) ; l'aperçu revient ici, puis « Envoyer partout » programme le post via Buffer.
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import jinja2
from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token

from core import db, env
from core.backoffice import auth
from core.services.social.studio_montage import FORMATS, MAX_DUREE

ROLES = ("editor", "admin", "owner")
_JINJA = jinja2.Environment(loader=jinja2.FileSystemLoader(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "templates")),
                            autoescape=True)


def chemin_secret() -> str | None:
    v = env.get("STUDIO_CHEMIN", "") or ""
    return v if len(v) >= 24 and v.replace("-", "").replace("_", "").isalnum() else None


def creer_tables() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS studio_jobs (
        id BIGSERIAL PRIMARY KEY, cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(), lien TEXT NOT NULL, params TEXT NOT NULL,
        statut VARCHAR(20) NOT NULL DEFAULT 'attente', video TEXT, vignette TEXT, erreur TEXT, auteur BIGINT, post_id BIGINT)""")
    db.run("""CREATE TABLE IF NOT EXISTS studio_passkeys (
        id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, credential_id TEXT UNIQUE NOT NULL, public_key TEXT NOT NULL,
        sign_count BIGINT NOT NULL DEFAULT 0, nom TEXT, cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


def _verifie(chemin: str) -> None:
    secret = chemin_secret()
    if not secret or not secrets.compare_digest(chemin, secret):
        raise Http404


def _utilisateur(request):
    u = auth.current_user(request)
    return u if u and u.get("role") in ROLES else None


def _reponse(r):
    r["X-Robots-Tag"] = "noindex, nofollow"
    r["Cache-Control"] = "no-store"
    r["Referrer-Policy"] = "no-referrer"
    return r


def _json(data, status: int = 200):
    return _reponse(JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False}))


def _corps(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def _rp(request) -> tuple[str, str]:
    hote = request.get_host().split(":")[0]
    origine = f"{'https' if request.is_secure() or hote != 'localhost' else 'http'}://{request.get_host()}"
    return hote, origine


# ---------------------------------------------------------------- pages

def studio(request, chemin):
    _verifie(chemin)
    u = _utilisateur(request)
    if u:
        creer_tables()
    html = _JINJA.get_template("studio.html").render(
        base=f"/studio/{chemin}", connecte=bool(u), nom=(u or {}).get("name") or "", csrf=get_token(request),
        formats=[("story", "9:16 · Reels / TikTok / Story"), ("feed", "4:5 · fil Instagram"), ("square", "1:1 · carré")],
        max_duree=MAX_DUREE, a_passkey=bool(u and db.value("SELECT 1 FROM studio_passkeys WHERE user_id = ?", [u["id"]])))
    return _reponse(HttpResponse(html))


def manifest(request, chemin):
    _verifie(chemin)
    base = f"/studio/{chemin}"
    return _reponse(HttpResponse(json.dumps({
        "name": "Cauri Studio", "short_name": "Cauri Studio", "start_url": base, "scope": base,
        "display": "standalone", "background_color": "#0a0814", "theme_color": "#2a1460", "lang": "fr",
        "icons": [{"src": "/assets/marque/studio-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/assets/marque/studio-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}),
        content_type="application/manifest+json"))


def service_worker(request, chemin):
    _verifie(chemin)
    hors = f"/studio/{chemin}/hors-ligne"
    js = ("const C='cauri-studio-v1';self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C)"
          f".then(c=>c.add('{hors}')))}});self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));"
          "self.addEventListener('fetch',e=>{if(e.request.mode==='navigate'){e.respondWith(fetch(e.request)"
          f".catch(()=>caches.match('{hors}')))}}}});")
    r = HttpResponse(js, content_type="application/javascript")
    r["Service-Worker-Allowed"] = f"/studio/{chemin}"
    return _reponse(r)


def hors_ligne(request, chemin):
    _verifie(chemin)
    return _reponse(HttpResponse('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">'
                                 '<body style="background:#0a0814;color:#fff;font-family:sans-serif;padding:32px">'
                                 '<h1>Cauri Studio</h1><p>Pas de connexion. Réessaie quand le réseau revient.</p>'))


# ---------------------------------------------------------------- passkeys (WebAuthn)

def passkey_inscription_options(request, chemin):
    _verifie(chemin)
    u = _utilisateur(request)
    if not u or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    import webauthn
    from webauthn.helpers.structs import AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement
    creer_tables()
    rp_id, _ = _rp(request)
    opts = webauthn.generate_registration_options(
        rp_id=rp_id, rp_name="Cauri Studio", user_id=str(u["id"]).encode(), user_name=u["email"],
        user_display_name=u.get("name") or u["email"],
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.PREFERRED,
                                                               user_verification=UserVerificationRequirement.REQUIRED))
    request.session["studio_defi_inscription"] = webauthn.helpers.bytes_to_base64url(opts.challenge)
    return _reponse(HttpResponse(webauthn.options_to_json(opts), content_type="application/json"))


def passkey_inscription(request, chemin):
    _verifie(chemin)
    u = _utilisateur(request)
    defi = request.session.pop("studio_defi_inscription", None)
    if not u or not defi or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    import webauthn
    rp_id, origine = _rp(request)
    try:
        v = webauthn.verify_registration_response(credential=request.body.decode(), expected_challenge=webauthn.base64url_to_bytes(defi),
                                                  expected_rp_id=rp_id, expected_origin=origine, require_user_verification=True)
    except Exception as exc:  # noqa: BLE001
        return _json({"erreur": f"empreinte refusée : {exc}"}, 400)
    db.insert("studio_passkeys", {"user_id": u["id"], "credential_id": webauthn.helpers.bytes_to_base64url(v.credential_id),
                                  "public_key": webauthn.helpers.bytes_to_base64url(v.credential_public_key),
                                  "sign_count": v.sign_count, "nom": (request.headers.get("User-Agent") or "")[:120]})
    return _json({"ok": True})


def passkey_connexion_options(request, chemin):
    _verifie(chemin)
    if request.method != "POST":
        return _json({"erreur": "méthode"}, 405)
    import webauthn
    from webauthn.helpers.structs import UserVerificationRequirement
    creer_tables()
    rp_id, _ = _rp(request)
    opts = webauthn.generate_authentication_options(rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED)
    request.session["studio_defi_connexion"] = webauthn.helpers.bytes_to_base64url(opts.challenge)
    return _reponse(HttpResponse(webauthn.options_to_json(opts), content_type="application/json"))


def passkey_connexion(request, chemin):
    _verifie(chemin)
    defi = request.session.pop("studio_defi_connexion", None)
    if not defi or request.method != "POST":
        return _json({"erreur": "défi expiré, recommence"}, 400)
    import webauthn
    corps = _corps(request)
    cle = db.one("SELECT * FROM studio_passkeys WHERE credential_id = ?", [corps.get("id") or ""])
    if not cle:
        return _json({"erreur": "appareil inconnu : connecte-toi une fois en admin pour enregistrer ton empreinte"}, 403)
    rp_id, origine = _rp(request)
    try:
        v = webauthn.verify_authentication_response(
            credential=request.body.decode(), expected_challenge=webauthn.base64url_to_bytes(defi), expected_rp_id=rp_id,
            expected_origin=origine, credential_public_key=webauthn.base64url_to_bytes(cle["public_key"]),
            credential_current_sign_count=int(cle["sign_count"]), require_user_verification=True)
    except Exception as exc:  # noqa: BLE001
        return _json({"erreur": f"empreinte refusée : {exc}"}, 403)
    user = db.one("SELECT id, email, name, role FROM users WHERE id = ? AND is_active = 1", [cle["user_id"]])
    if not user or user["role"] not in ROLES:
        return _json({"erreur": "compte désactivé"}, 403)
    db.update("studio_passkeys", {"sign_count": v.new_sign_count}, "id = :id", {"id": cle["id"]})
    auth._login(request, user, auth.client_ip(request))
    return _json({"ok": True})


# ---------------------------------------------------------------- fabrication

def _lance(job_id: int) -> str | None:
    """Déclenche le montage sur GitHub Actions ; message d'erreur ou None."""
    import requests
    from core.views_cron import REPO
    jeton = env.get("GH_DISPATCH_TOKEN", "")
    if not jeton:
        return "GH_DISPATCH_TOKEN absent : lance « python manage.py studio_job --id %d » sur le PC" % job_id
    r = requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/studio.yml/dispatches", timeout=20,
                      headers={"Authorization": f"Bearer {jeton}", "Accept": "application/vnd.github+json"},
                      json={"ref": "main", "inputs": {"job_id": str(job_id)}})
    return None if r.status_code == 204 else f"GitHub a refusé le lancement ({r.status_code})"


def fabriquer(request, chemin):
    _verifie(chemin)
    u = _utilisateur(request)
    if not u or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    c = _corps(request)
    lien = str(c.get("lien") or "").strip()
    url = urlparse(lien)
    if url.scheme not in ("http", "https") or not url.hostname:
        return _json({"erreur": "lien invalide"}, 400)
    if not c.get("droits"):
        return _json({"erreur": "coche la case des droits"}, 400)
    try:
        debut, fin = float(c.get("debut") or 0), float(c.get("fin") or 60)
    except (TypeError, ValueError):
        return _json({"erreur": "début et fin en secondes"}, 400)
    if debut < 0 or fin <= debut or fin - debut > MAX_DUREE:
        return _json({"erreur": f"extrait de 1 à {MAX_DUREE} secondes"}, 400)
    fmt = c.get("format") if c.get("format") in FORMATS else "story"
    params = {"format": fmt, "debut": debut, "fin": fin}
    for k in ("etiquette", "accroche", "artiste", "credit", "legende_fr", "legende_en"):
        params[k] = str(c.get(k) or "").strip()[:600]
    creer_tables()
    job_id = db.insert("studio_jobs", {"lien": lien[:1000], "params": json.dumps(params, ensure_ascii=False), "auteur": u["id"]})
    erreur = _lance(job_id)
    if erreur:
        db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": job_id})
    return _json({"id": job_id, "erreur": erreur})


def _job_public(j: dict) -> dict:
    from core import storage
    base = storage.blob_public_url()
    p = j["params"] if isinstance(j["params"], dict) else json.loads(j["params"] or "{}")
    return {"id": j["id"], "statut": j["statut"], "erreur": j.get("erreur"), "lien": j["lien"], "params": p,
            "video": f"{base}/media/social/{j['video']}" if j.get("video") else None,
            "vignette": f"{base}/media/social/{j['vignette']}" if j.get("vignette") else None,
            "cree_le": str(j.get("cree_le") or "")[:16], "post_id": j.get("post_id")}


def job(request, chemin, ident):
    _verifie(chemin)
    if not _utilisateur(request):
        return _json({"erreur": "connexion requise"}, 401)
    j = db.one("SELECT * FROM studio_jobs WHERE id = ?", [int(ident)])
    if not j:
        raise Http404
    return _json(_job_public(j))


def historique(request, chemin):
    _verifie(chemin)
    if not _utilisateur(request):
        return _json({"erreur": "connexion requise"}, 401)
    creer_tables()
    return _json({"jobs": [_job_public(j) for j in db.all("SELECT * FROM studio_jobs ORDER BY id DESC LIMIT 20")]})


def envoyer(request, chemin, ident):
    """Crée le post (légende FR + EN, crédit) et le programme partout via Buffer dans 2 minutes."""
    _verifie(chemin)
    u = _utilisateur(request)
    if not u or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    j = db.one("SELECT * FROM studio_jobs WHERE id = ?", [int(ident)])
    if not j or j["statut"] not in ("pret", "envoye") or not j.get("video"):
        return _json({"erreur": "vidéo pas prête"}, 400)
    if j["statut"] == "envoye":
        return _json({"erreur": "déjà envoyée"}, 400)
    p = j["params"] if isinstance(j["params"], dict) else json.loads(j["params"] or "{}")
    c = _corps(request)
    accroche = str(c.get("accroche") or p.get("accroche") or "").strip()
    fr = str(c.get("legende_fr") or p.get("legende_fr") or accroche).strip()
    en = str(c.get("legende_en") or p.get("legende_en") or "").strip()
    credit = str(c.get("credit") or p.get("credit") or "").strip()
    artiste = str(c.get("artiste") or p.get("artiste") or "").strip()
    legende = fr + (f"\n\n🎥 Source : {credit}" if credit else "")
    tags = "#CauriCharts" + (" #" + "".join(ch for ch in artiste if ch.isalnum()) if artiste else "") + " #Afrobeats #MusiqueAfricaine"
    maintenant = datetime.now(timezone.utc)
    faits = {"kind": "format-clip", "studio_job": j["id"], "due": (maintenant + timedelta(minutes=2)).isoformat(),
             "source": j["lien"]}
    if en:
        faits["en"] = {"title": accroche, "caption": en + (f"\n\n🎥 Source: {credit}" if credit else "")}
    pid = db.insert("social_posts", {"slot_date": maintenant.date().isoformat(), "theme": "format-studio",
                                     "title": accroche[:160] or "Vidéo Cauri Studio", "caption": legende, "hashtags": tags[:300],
                                     "image_square": j["vignette"], "image_story": j["vignette"], "carousel": "[]",
                                     "video": j["video"], "status": "approved", "facts": json.dumps(faits, ensure_ascii=False)})
    post = db.one("SELECT * FROM social_posts WHERE id = ?", [pid])
    try:
        from core.services.pipeline import publish
        lignes = publish(post, maintenant + timedelta(minutes=2))
    except Exception as exc:  # noqa: BLE001
        return _json({"erreur": f"post créé (n°{pid}) mais l'envoi a échoué : {exc}"}, 502)
    db.update("studio_jobs", {"statut": "envoye", "post_id": pid}, "id = :id", {"id": j["id"]})
    return _json({"ok": True, "post_id": pid, "lignes": lignes})


# ---------------------------------------------------------------- aperçu d'un lien, réglages

OEMBED = {"youtube.com": "https://www.youtube.com/oembed", "youtu.be": "https://www.youtube.com/oembed",
          "tiktok.com": "https://www.tiktok.com/oembed", "vimeo.com": "https://vimeo.com/api/oembed.json"}
PLATEFORMES = {"tiktok.com": "TikTok", "instagram.com": "Instagram", "facebook.com": "Facebook", "fb.watch": "Facebook",
               "youtube.com": "YouTube", "youtu.be": "YouTube", "x.com": "X", "twitter.com": "X", "vimeo.com": "Vimeo",
               "snapchat.com": "Snapchat", "threads.net": "Threads"}


def apercu_lien(request, chemin):
    """Carte d'aperçu dès qu'un lien est collé : plateforme, titre, compte, miniature (oEmbed quand la plateforme l'offre)."""
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    import requests
    lien = str(_corps(request).get("lien") or "").strip()
    hote = (urlparse(lien).hostname or "").lower().removeprefix("www.").removeprefix("m.").removeprefix("vm.")
    if not hote:
        return _json({"erreur": "lien invalide"}, 400)
    base = next((d for d in PLATEFORMES if hote == d or hote.endswith("." + d)), None)
    infos = {"plateforme": PLATEFORMES.get(base, hote), "titre": "", "auteur": "", "miniature": ""}
    service = OEMBED.get(base or "")
    if service:
        try:
            r = requests.get(service, params={"url": lien, "format": "json"}, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.ok:
                d = r.json()
                infos.update({"titre": (d.get("title") or "")[:160], "auteur": (d.get("author_name") or "")[:80],
                              "miniature": d.get("thumbnail_url") or ""})
        except Exception:  # noqa: BLE001
            pass
    return _json(infos)


def reglages(request, chemin):
    _verifie(chemin)
    u = _utilisateur(request)
    if not u:
        return _json({"erreur": "connexion requise"}, 401)
    creer_tables()
    cles = db.all("SELECT id, nom, cree_le FROM studio_passkeys WHERE user_id = ? ORDER BY id DESC", [u["id"]])
    return _json({"nom": u.get("name") or u["email"], "email": u["email"],
                  "appareils": [{"id": c["id"], "nom": _appareil(c.get("nom") or ""), "cree_le": str(c["cree_le"])[:10]} for c in cles]})


def _appareil(ua: str) -> str:
    for motif, nom in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Macintosh", "Mac"), ("Windows", "PC Windows")):
        if motif in ua:
            return nom
    return "Appareil"


def supprimer_appareil(request, chemin, ident):
    _verifie(chemin)
    u = _utilisateur(request)
    if not u or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    db.run("DELETE FROM studio_passkeys WHERE id = ? AND user_id = ?", [int(ident), u["id"]])
    return _json({"ok": True})


def deconnexion(request, chemin):
    _verifie(chemin)
    if request.method == "POST":
        auth.logout(request)
    return _json({"ok": True})
