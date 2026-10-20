"""Cauri Studio — éditeur vidéo privé (20/10/2026).

Adresse secrète /studio/<STUDIO_CHEMIN> (404 sinon, jamais indexée). Accès : session admin existante (éditeur ou plus)
ou passkey WebAuthn (empreinte, Face ID, code de l'appareil). Le lien collé est téléchargé, analysé et habillé sur
GitHub Actions (studio_montage.py) ; l'aperçu revient ici, puis « Envoyer partout » programme le post via Buffer.
"""
import json
import re
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


VERROU = 300   # secondes sans activité avant de redemander l'empreinte (et à chaque ouverture de l'appli, côté page)


def _utilisateur(request, verrou: bool = True):
    """L'utilisateur connecté, si le studio est déverrouillé : empreinte / Face ID validée il y a moins de VERROU secondes
    (sauf tant qu'aucun appareil n'est enregistré, pour pouvoir en enregistrer un). Chaque appel prolonge le délai."""
    import time
    u = auth.current_user(request)
    if not u or u.get("role") not in ROLES:
        return None
    if verrou:
        ok = float(request.session.get("studio_ok", 0) or 0)
        if time.time() - ok > VERROU:
            try:
                if db.value("SELECT 1 FROM studio_passkeys WHERE user_id = ?", [u["id"]]):
                    return None
            except Exception:  # noqa: BLE001 — table pas encore créée : rien à verrouiller
                pass
        request.session["studio_ok"] = time.time()
    return u


def _deverrouille(request) -> None:
    import time
    request.session["studio_ok"] = time.time()


def verrouiller(request, chemin):
    """Appelé par l'appli à chaque nouvelle ouverture : la prochaine action redemande l'empreinte."""
    _verifie(chemin)
    if request.method == "POST":
        request.session["studio_ok"] = 0
    return _json({"ok": True})


def _csp(nonce: str = "") -> str:
    """Politique de sécurité propre au studio : le script de la page seulement avec son jeton (nonce), les styles de la page,
    la police Montserrat, et les vidéos/vignettes du Blob (la politique du site bloquait tout cela, écran sans mise en forme)."""
    script = f"script-src 'self' 'nonce-{nonce}'; " if nonce else "script-src 'self'; "
    return ("default-src 'self'; " + script +
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; media-src 'self' https://*.public.blob.vercel-storage.com; "
            "connect-src 'self'; worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


def _reponse(r, nonce: str = ""):
    r["Content-Security-Policy"] = _csp(nonce)
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


def _rp(request) -> tuple[str, str | list]:
    """(rp_id, origines acceptées). Sur cauricharts.com, la passkey est liée au domaine principal : elle marche avec
    et sans « www »."""
    hote = request.get_host().split(":")[0]
    if hote == "cauricharts.com" or hote.endswith(".cauricharts.com"):
        return "cauricharts.com", ["https://cauricharts.com", "https://www.cauricharts.com"]
    return hote, f"{'https' if request.is_secure() or hote != 'localhost' else 'http'}://{request.get_host()}"


# ---------------------------------------------------------------- pages

def studio(request, chemin):
    _verifie(chemin)
    u = _utilisateur(request)
    if u:
        creer_tables()
    nonce = secrets.token_urlsafe(18)
    html = _JINJA.get_template("studio.html").render(
        base=f"/studio/{chemin}", connecte=bool(u), nonce=nonce, nom=(u or {}).get("name") or "", csrf=get_token(request),
        formats=[("story", "9:16 · Reels / TikTok / Story"), ("feed", "4:5 · fil Instagram"), ("square", "1:1 · carré")],
        max_duree=MAX_DUREE, a_passkey=bool(u and db.value("SELECT 1 FROM studio_passkeys WHERE user_id = ?", [u["id"]])))
    return _reponse(HttpResponse(html), nonce)


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
    _deverrouille(request)
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
    _deverrouille(request)
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
    fmt = c.get("format") if c.get("format") in FORMATS else "origine"
    params = {"format": fmt, "debut": debut, "fin": fin}
    for k in ("etiquette", "accroche", "artiste", "credit", "legende_fr", "legende_en", "contexte"):
        params[k] = str(c.get(k) or "").strip()[:600]
    params["valider"] = bool(c.get("valider", True))   # montrer l'accroche avant de fabriquer (sauf « Refaire »)
    params["reseaux"] = [r for r in (c.get("reseaux") or []) if r in PLATEFORMES_POST] or list(PLATEFORMES_POST)   # choix dès la création
    creer_tables()
    job_id = db.insert("studio_jobs", {"lien": lien[:1000], "params": json.dumps(params, ensure_ascii=False), "auteur": u["id"]})
    erreur = _lance(job_id)
    if erreur:
        db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": job_id})
    return _json({"id": job_id, "erreur": erreur})


PLATEFORMES_POST = ("instagram", "facebook", "tiktok", "telegram")


def reseaux_choisis(c: dict) -> list | None:
    """Plateformes cochées dans la fenêtre d'envoi ; None = toutes (rien de décoché)."""
    r = [x for x in (c.get("reseaux") or []) if x in PLATEFORMES_POST]
    if not r:
        raise ValueError("coche au moins une plateforme")
    return None if set(r) == set(PLATEFORMES_POST) else r


def theme_libre(job_id: int, quand) -> str:
    """format-studio-<n°>, puis -2, -3… pour chaque republication du même jour (un post par jour et par thème)."""
    base = f"format-studio-{job_id}"
    n = int(db.value("SELECT COUNT(*) FROM social_posts WHERE slot_date = ? AND (theme = ? OR theme LIKE ?)",
                     [quand.date().isoformat(), base, base + "-%"]) or 0)
    return base if n == 0 else f"{base}-{n + 1}"


def _job_public(j: dict) -> dict:
    from core import storage
    base = storage.blob_public_url()
    p = j["params"] if isinstance(j["params"], dict) else json.loads(j["params"] or "{}")
    return {"id": j["id"], "statut": j["statut"], "erreur": j.get("erreur"), "lien": j["lien"], "params": p,
            "video": f"{base}/media/social/{j['video']}" if j.get("video") else None,
            "vignette": f"{base}/media/social/{j['vignette']}" if j.get("vignette") else None,
            "cree_le": str(j.get("cree_le") or "")[:16], "post_id": j.get("post_id"),
            "photos": [f"{base}/media/artists/candidats/{n}" for n in (p.get("photos") or [])]}


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
    jobs = [_job_public(j) for j in db.all("SELECT * FROM studio_jobs ORDER BY id DESC LIMIT 60")]
    return _json({"jobs": [j for j in jobs if j["params"].get("type") != "photos"][:20]})   # les photos ont leur onglet


def envoyer(request, chemin, ident):
    """Crée le post (légende FR + EN, crédit) et le programme partout via Buffer dans 2 minutes.
    Toute erreur revient en clair dans l'appli (au lieu d'une page « Erreur 500 ») et dans le journal."""
    _verifie(chemin)
    try:
        return _envoyer(request, ident)
    except Http404:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback
        from core.services.platforms import log_write
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()[:300]
        log_write("social", "error", f"studio, envoi de la tâche {ident} : {detail}")
        return _json({"erreur": f"envoi impossible : {detail}"}, 500)


def _envoyer(request, ident):
    u = _utilisateur(request)
    if not u or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    j = db.one("SELECT * FROM studio_jobs WHERE id = ?", [int(ident)])
    if not j or j["statut"] not in ("pret", "envoye") or not j.get("video"):
        return _json({"erreur": "vidéo pas prête"}, 400)
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
             "source": j["lien"], "notifier": bool(c.get("notifier")), "reseaux": reseaux_choisis(c)}
    if en:
        faits["en"] = {"title": accroche, "caption": en + (f"\n\n🎥 Source: {credit}" if credit else "")}
    pid = db.insert("social_posts", {"slot_date": maintenant.date().isoformat(), "theme": theme_libre(j["id"], maintenant),
                                     "title": accroche[:160] or "Vidéo Cauri Studio", "caption": legende, "hashtags": tags[:300],
                                     "image_square": j["vignette"], "image_story": j["vignette"], "carousel": "[]",
                                     "video": j["video"], "status": "approved", "facts": json.dumps(faits, ensure_ascii=False)})
    post = db.one("SELECT * FROM social_posts WHERE id = ?", [pid])
    from core.services import buffer
    try:
        resultat = buffer.schedule(post, maintenant + timedelta(minutes=2))
    except Exception as exc:  # noqa: BLE001
        resultat = f"échec ({exc})"
    # Dès qu'un réseau a reçu la vidéo, elle est « envoyée » (un nouvel envoi ferait un doublon) ; les refus sont signalés
    recus = [r["reason"].split("-")[2] for r in db.all("SELECT reason FROM audit_log WHERE reason LIKE ?", [f"post-{pid}-%"])
             if r["reason"].count("-") >= 2]
    if not recus:
        db.run("DELETE FROM social_posts WHERE id = ?", [pid])   # rien n'est parti : on peut réessayer proprement
        return _json({"erreur": f"aucun réseau n'a accepté la vidéo : {resultat}"}, 502)
    db.update("studio_jobs", {"statut": "envoye", "post_id": pid}, "id = :id", {"id": j["id"]})
    refus = [m.strip() for m in str(resultat).split(",") if ":" in m and "déjà" not in m]
    return _json({"ok": True, "post_id": pid, "recus": sorted(set(recus)), "refus": refus})


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


# ---------------------------------------------------------------- section Photos (banque des artistes)

def artistes(request, chemin):
    """Recherche d'un artiste suivi (nom), pour ranger les photos dans sa banque."""
    _verifie(chemin)
    if not _utilisateur(request):
        return _json({"erreur": "connexion requise"}, 401)
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return _json({"artistes": []})
    lignes = db.all("""SELECT id, name, upper(origin_country) AS pays, COALESCE(NULLIF(image_hd_url, ''), image_url) AS photo FROM artists
                       WHERE status = 'active' AND name ILIKE ? ORDER BY youtube_subscribers DESC NULLS LAST LIMIT 8""", [f"%{q}%"])
    return _json({"artistes": [{"id": r["id"], "nom": r["name"], "pays": r["pays"] or "", "photo": r["photo"] or ""} for r in lignes]})


def photos_nouveau(request, chemin):
    """Nouvelle récupération : depuis un lien (le serveur télécharge) ou depuis le téléphone (l'appli envoie ensuite)."""
    _verifie(chemin)
    u = _utilisateur(request)
    if not u or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    c = _corps(request)
    lien = str(c.get("lien") or "").strip()
    params = {"type": "photos", "photos": [], "artiste_id": c.get("artiste_id"), "artiste_nom": str(c.get("artiste_nom") or "")[:120]}
    creer_tables()
    liens = list(dict.fromkeys(re.findall(r"https?://[^\s,;]+", lien)))[:30]
    if any(est_profil(x) for x in liens):
        return _json({"erreur": "un lien de profil ne passe pas sans compte Instagram : ouvre le profil et colle les liens "
                                "des posts photo (plusieurs d'un coup, un par ligne)"}, 400)
    if len(liens) > 1 or (liens and c.get("arriere_plan")):
        # tri en arrière-plan : on peut en lancer plusieurs à la suite, chacun devient un dossier « À trier »
        if not c.get("artiste_id"):
            return _json({"erreur": "choisis d'abord l'artiste : le tri en arrière-plan range ses photos dans son dossier"}, 400)
        params.update({"mode": "profil", "artiste_id": int(c["artiste_id"]), "liens": liens})
        job_id = db.insert("studio_jobs", {"lien": liens[0][:1000], "params": json.dumps(params, ensure_ascii=False), "auteur": u["id"]})
        erreur = _lance(job_id)
        if erreur:
            db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": job_id})
        return _json({"id": job_id, "profil": True, "liens": len(liens), "erreur": erreur})
    if lien:
        url = urlparse(lien)
        if url.scheme not in ("http", "https") or not url.hostname:
            return _json({"erreur": "lien invalide"}, 400)
        job_id = db.insert("studio_jobs", {"lien": lien[:1000], "params": json.dumps(params, ensure_ascii=False), "auteur": u["id"]})
        erreur = _lance(job_id)
        if erreur:
            db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": job_id})
        return _json({"id": job_id, "erreur": erreur})
    job_id = db.insert("studio_jobs", {"lien": "téléphone", "params": json.dumps(params, ensure_ascii=False), "auteur": u["id"],
                                       "statut": "telechargement"})
    return _json({"id": job_id, "erreur": None})


def photos_importer(request, chemin, ident):
    """Une photo envoyée depuis le téléphone (corps brut, réduite à 2 400 px par l'appli : < 4 Mo)."""
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    from core.services.social import studio_photos
    if len(request.body) > 4_300_000:
        return _json({"erreur": "photo trop lourde"}, 413)
    nom = studio_photos.importe(int(ident), request.body)
    return _json({"ok": bool(nom), "nom": nom})


def _erreur_lisible(vue):
    """Toute erreur imprévue revient en clair dans l'appli (et dans le journal) au lieu d'une page « Erreur 500 »."""
    import functools

    @functools.wraps(vue)
    def enveloppe(request, *args, **kwargs):
        try:
            return vue(request, *args, **kwargs)
        except Http404:
            raise
        except Exception as exc:  # noqa: BLE001
            import traceback
            from core.services.platforms import log_write
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()[:300]
            log_write("social", "error", f"studio, {vue.__name__} : {detail}")
            return _json({"erreur": f"{vue.__name__.replace('_', ' ')} impossible : {detail}"}, 500)
    return enveloppe


def _job_photos(ident):
    j = db.one("SELECT * FROM studio_jobs WHERE id = ?", [int(ident)])
    if not j:
        raise Http404
    return j


def photos_enregistrer(request, chemin, ident):
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    from core.services.social import studio_photos
    c = _corps(request)
    try:
        artiste = int(c.get("artiste_id") or 0)
        job = _job_photos(ident)
        gardees = studio_photos.enregistre(job, [int(i) for i in c.get("indices") or []], artiste,
                                           bool(c.get("detourable")), str(c.get("note") or "").strip())
    except (ValueError, TypeError) as exc:
        return _json({"erreur": str(exc) or "choisis un artiste"}, 400)
    p = job["params"] if isinstance(job["params"], dict) else json.loads(job["params"] or "{}")
    if p.get("mode") == "profil":            # le dossier « à trier » est validé : il sort de la liste
        p.update({"trie_le": datetime.now().isoformat(timespec="minutes"), "a_trier": False})
        db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False)}, "id = :id", {"id": job["id"]})
    return _json({"ok": True, "gardees": len(gardees)})


def photos_suggestions(request, chemin, ident):
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    from core.services.social import studio_photos
    c = _corps(request)
    return _json(studio_photos.suggestions(_job_photos(ident), [int(i) for i in c.get("indices") or []],
                                           str(c.get("contexte") or "").strip()))


def photos_publier(request, chemin, ident):
    """Prépare le carrousel (fabriqué sur GitHub : détourage, netteté) puis l'envoie via Buffer."""
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    j = _job_photos(ident)
    c = _corps(request)
    p = json.loads(j["params"] or "{}")
    indices = [int(i) for i in c.get("indices") or []]
    if not indices:
        return _json({"erreur": "choisis au moins une photo"}, 400)
    try:
        reseaux = reseaux_choisis(c)
    except ValueError as exc:
        return _json({"erreur": str(exc)}, 400)
    p.update({"publier_indices": indices, "notifier": bool(c.get("notifier")), "reseaux": reseaux,
              **{k: str(c.get(k) or "").strip()[:900] for k in ("etiquette", "accroche", "legende_fr", "legende_en")}})
    db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False), "statut": "attente", "erreur": None}, "id = :id", {"id": j["id"]})
    erreur = _lance(j["id"])
    if erreur:
        db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": j["id"]})
    return _json({"ok": not erreur, "erreur": erreur})



# ---------------------------------------------------------------- validation de l'accroche avant le montage

TEXTES = ("etiquette", "accroche", "artiste", "credit", "legende_fr", "legende_en")


def _textes(p: dict, c: dict) -> dict:
    for k in TEXTES:
        if k in c:
            p[k] = str(c.get(k) or "").strip()[:900]
    return p


def apercu_job(request, chemin, ident):
    """Recalcule l'aperçu (image clé + habillage) avec les textes modifiés — rapide, sur Vercel."""
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    import io
    import requests
    from PIL import Image
    from core import storage
    from core.services.social.studio_montage import apercu
    j = db.one("SELECT * FROM studio_jobs WHERE id = ?", [int(ident)])
    if not j:
        raise Http404
    p = _textes(json.loads(j["params"] or "{}"), _corps(request))
    if not p.get("cle"):
        return _json({"erreur": "pas d'image clé"}, 400)
    base = storage.blob_public_url()
    fond = Image.open(io.BytesIO(requests.get(f"{base}/media/social/{p['cle']}", timeout=30).content))
    vue = apercu(fond, p.get("format_final") or "origine", p.get("etiquette") or "", p.get("accroche") or "", p.get("artiste") or "",
                 p.get("credit") or "")
    out = io.BytesIO(); vue.save(out, format="JPEG", quality=90)
    nom = f"studio-{j['id']}-apercu-{secrets.token_hex(2)}.jpg"
    storage.store_media("social", nom, out.getvalue(), "image/jpeg")
    db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False), "vignette": nom}, "id = :id", {"id": j["id"]})
    return _json({"vignette": f"{base}/media/social/{nom}"})


def valider_job(request, chemin, ident):
    """Textes validés : le montage démarre (GitHub)."""
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    j = db.one("SELECT * FROM studio_jobs WHERE id = ?", [int(ident)])
    if not j or j["statut"] != "a_valider":
        return _json({"erreur": "rien à valider"}, 400)
    p = _textes(json.loads(j["params"] or "{}"), _corps(request))
    p["valide"] = True
    db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False), "statut": "attente"}, "id = :id", {"id": j["id"]})
    erreur = _lance(j["id"])
    if erreur:
        db.update("studio_jobs", {"statut": "erreur", "erreur": erreur}, "id = :id", {"id": j["id"]})
    return _json({"ok": not erreur, "erreur": erreur})


# ---------------------------------------------------------------- dossiers des artistes (banque de photos)

def banque(request, chemin):
    """Les artistes qui ont des photos dans la banque, avec leur nombre de photos."""
    _verifie(chemin)
    if not _utilisateur(request):
        return _json({"erreur": "connexion requise"}, 401)
    from core import storage
    from core.services.social import plans
    plans.creer_table(); plans.colonnes()
    base = storage.blob_public_url()
    lignes = db.all("""SELECT a.id, a.name, COUNT(p.id) AS n, MAX(p.fichier) AS une FROM artist_photos p JOIN artists a ON a.id = p.artist_id
                       GROUP BY a.id, a.name ORDER BY COUNT(p.id) DESC, a.name""")
    return _json({"dossiers": [{"id": r["id"], "nom": r["name"], "n": r["n"], "une": f"{base}/media/artists/plans/{r['une']}"} for r in lignes]})


def banque_artiste(request, chemin, ident):
    _verifie(chemin)
    if not _utilisateur(request):
        return _json({"erreur": "connexion requise"}, 401)
    from core import storage
    base = storage.blob_public_url()
    lignes = db.all("""SELECT id, fichier, note, plan_large, score, utilise_le FROM artist_photos WHERE artist_id = ?
                       ORDER BY COALESCE(score, 0.5) DESC, id DESC""", [int(ident)])
    return _json({"photos": [{"id": r["id"], "url": f"{base}/media/artists/plans/{r['fichier']}", "note": r.get("note") or "",
                              "entiere": bool(r["plan_large"]), "score": r.get("score"),
                              "utilisee": str(r.get("utilise_le") or "")[:10]} for r in lignes]})


def banque_retirer(request, chemin, ident):
    _verifie(chemin)
    if not _utilisateur(request) or request.method != "POST":
        return _json({"erreur": "connexion requise"}, 401)
    db.run("DELETE FROM artist_photos WHERE id = ?", [int(ident)])
    return _json({"ok": True})



# ---------------------------------------------------------------- profil complet en arrière-plan

def est_profil(lien: str) -> bool:
    """Lien d'un profil Instagram (instagram.com/compte) et pas d'un post, d'un reel ou d'une story."""
    u = urlparse(lien)
    if (u.hostname or "").lower().removeprefix("www.").removeprefix("m.") != "instagram.com":
        return False
    morceaux = [m for m in u.path.split("/") if m]
    return len(morceaux) == 1 and morceaux[0].lower() not in ("p", "reel", "reels", "tv", "stories", "explore", "accounts")


def photos_profils(request, chemin):
    """Les profils lancés récemment et leur état."""
    _verifie(chemin)
    if not _utilisateur(request):
        return _json({"erreur": "connexion requise"}, 401)
    out = []
    from core import storage
    base = storage.blob_public_url()
    for j in db.all("SELECT * FROM studio_jobs WHERE params LIKE ? ORDER BY id DESC LIMIT 12", ['%"mode": "profil"%']):
        p = json.loads(j["params"] or "{}")
        if p.get("trie_le"):
            continue                         # dossier déjà validé
        une = f"{base}/media/artists/candidats/{p['photos'][0]}" if p.get("photos") else ""
        out.append({"id": j["id"], "statut": j["statut"], "artiste": p.get("artiste_nom") or "", "artiste_id": p.get("artiste_id"),
                    "n": len(p.get("photos") or []), "reconnues": len(p.get("preselection") or []), "une": une,
                    "page": p.get("page") or "", "liens": len(p.get("liens") or [1]), "erreur": j.get("erreur"),
                    "a_trier": bool(p.get("a_trier"))})
    return _json({"profils": out, "a_trier": sum(1 for x in out if x["a_trier"] and x["statut"] == "pret")})


# toutes les actions JSON du studio : erreurs lisibles
for _nom in ("fabriquer", "photos_profils", "photos_nouveau", "photos_importer", "photos_enregistrer", "photos_suggestions", "photos_publier",
             "apercu_job", "valider_job", "banque", "banque_artiste", "banque_retirer", "artistes", "reglages"):
    globals()[_nom] = _erreur_lisible(globals()[_nom])
