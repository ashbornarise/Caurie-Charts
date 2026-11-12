"""Régie du live TikTok (« La Nuit Cauri Charts », 20/11/2026) — une platine de DJ pour piloter l'écran du live.

- Régie : /studio/<chemin>/live (Studio, empreinte / Face ID). Scènes, top 3 par pays, versus avec votes, mur des
  réclamations, final, sons et extraits de clips des artistes (lecture, fondu, volume, flou quand la fiche s'affiche).
- Écran : /live/<jeton>/ecran — la page que LIVE Studio (ou OBS) filme en 1080 × 1920. Le jeton se déduit du chemin secret
  du Studio : l'écran est public mais introuvable sans le lien.
- L'état partagé vit dans live_cache (toutes les instances Vercel le voient) ; l'écran le relit deux fois par seconde.
- Bibliothèque de sons et de clips : clé « live-biblio » de live_cache, remplie par la commande live_bibliotheque.
"""
import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata

from django.http import Http404, HttpResponse
from django.middleware.csrf import get_token

from core import db
from core import studio as S

CLE_ETAT, CLE_BIBLIO, CLE_DONNEES = "live-etat", "live-biblio", "live-donnees"
ETAT_DEFAUT = {
    "scene": "attente", "debut": "2026-11-20T20:00:00Z", "pays": 0, "etape": 0, "mystere": None, "finale": 0,
    "votes": {"a": 0, "b": 0}, "versus": {"a": "Himra", "b": "Didi B", "aId": 5, "bId": 8, "fin": "2026-12-26T14:00:00Z"},
    "mur": [], "carte": None, "dernier": [], "gong": 0,
    # platine : un son et un clip à la fois, chacun avec son propre réglage
    "son": None, "sonVol": 0.8, "sonJoue": False, "sonTop": 0,
    "clip": None, "clipJoue": False, "flou": False, "fiche": False,
}
_memo = {"t": 0.0, "v": None}


def jeton_ecran() -> str | None:
    secret = S.chemin_secret()
    return hmac.new(secret.encode(), b"ecran-live", hashlib.sha256).hexdigest()[:28] if secret else None


def _lit(cle: str, defaut=None):
    try:
        v = db.value("SELECT valeur FROM live_cache WHERE cle = ? AND expire > NOW()", [cle])
        return json.loads(v) if v else defaut
    except Exception:  # noqa: BLE001 — table absente : état par défaut
        return defaut


def _ecrit(cle: str, valeur, jours: int = 3) -> None:
    db.run("""INSERT INTO live_cache (cle, valeur, expire) VALUES (?, ?, NOW() + (? || ' days')::interval)
              ON CONFLICT (cle) DO UPDATE SET valeur = EXCLUDED.valeur, expire = EXCLUDED.expire""",
           [cle, json.dumps(valeur, ensure_ascii=False), str(jours)])


def etat_courant() -> dict:
    # mémoire de l'instance 0,4 s : l'écran interroge souvent, la base ne voit qu'une partie des appels
    if _memo["v"] is not None and time.time() - _memo["t"] < 0.4:
        return _memo["v"]
    e = {**ETAT_DEFAUT, **(_lit(CLE_ETAT, {}) or {})}
    _memo.update(t=time.time(), v=e)
    return e


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower())


def donnees() -> dict:
    """Fiches des artistes classés, top 3 par pays (dernier classement Icon publié), N°1 Afrique de l'Ouest. Mise en cache 10 min."""
    d = _lit(CLE_DONNEES)
    if d:
        return d
    sem = db.value("""SELECT MAX(r.period_key) FROM chart_runs r JOIN chart_types t ON t.id = r.chart_type_id
        WHERE t.code = 'icon' AND r.status = 'published' AND r.period_key LIKE '%%-W%%'""")
    from core.services.social import gabarits as G
    couleurs = next(v for v in vars(G).values() if isinstance(v, dict) and "tg" in v and isinstance(v["tg"], list))
    from core import storage
    blob = storage.blob_public_url().rstrip("/") + "/media/artists/plans/"
    photos = {r["artist_id"]: blob + r["fichier"] for r in db.all(
        """SELECT DISTINCT ON (artist_id) artist_id, fichier FROM artist_photos WHERE valide_le IS NOT NULL
           ORDER BY artist_id, score DESC NULLS LAST, id DESC""")}
    arts = db.all("""SELECT a.id, a.name, a.image_url, a.image_hd_url, c.code pays, c.name_fr pays_nom,
          MIN(e.position) FILTER (WHERE t.code = 'prime') meilleure_place, COUNT(*) FILTER (WHERE t.code = 'prime' AND e.position = 1) n1,
          MIN(e.position) FILTER (WHERE t.code = 'icon') rang_artiste, COUNT(DISTINCT r.period_key) semaines
        FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id JOIN chart_types t ON t.id = r.chart_type_id
        JOIN artists a ON a.id = e.artist_id JOIN countries c ON c.id = r.country_id
        WHERE r.status = 'published' AND t.code IN ('prime', 'icon') GROUP BY a.id, c.code, c.name_fr""")
    fiches = {}
    for a in arts:
        f = fiches.get(a["id"])
        if not f or (a["rang_artiste"] or 99) < (f["rang_artiste"] or 99):
            fiches[a["id"]] = a
    phares = {r["artist_id"]: r["title"] for r in db.all(
        """SELECT DISTINCT ON (e.artist_id) e.artist_id, tr.title FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
           JOIN chart_types t ON t.id = r.chart_type_id JOIN tracks tr ON tr.id = e.track_id
           WHERE t.code = 'prime' AND r.status = 'published' ORDER BY e.artist_id, e.position, r.period_key DESC""")}
    spotify = {r["artist_id"]: r for r in db.all(
        """SELECT DISTINCT ON (artist_id) artist_id, auditeurs FROM spotify_artistes ORDER BY artist_id, releve_le DESC""")}
    artistes = sorted(({"id": a["id"], "nom": a["name"], "cle": _norm(a["name"]), "pays": a["pays"].lower(), "pays_nom": a["pays_nom"],
                        "meilleure_place": a["meilleure_place"], "n1": a["n1"], "semaines": a["semaines"], "titre_phare": phares.get(a["id"]),
                        "auditeurs": (spotify.get(a["id"]) or {}).get("auditeurs"),
                        "photo": photos.get(a["id"]) or a["image_hd_url"] or a["image_url"]} for a in fiches.values()),
                      key=lambda f: f["nom"].lower())
    par_id = {f["id"]: f for f in artistes}
    pays = []
    for c in db.all("SELECT code, name_fr FROM countries WHERE is_active = 1 ORDER BY sort_order"):
        r = db.one("""SELECT r.id FROM chart_runs r JOIN chart_types t ON t.id = r.chart_type_id JOIN countries c ON c.id = r.country_id
            WHERE t.code = 'icon' AND c.code = ? AND r.status = 'published' AND r.period_key = ?""", [c["code"], sem])
        if not r:
            continue
        top = [dict(x) for x in db.all("""SELECT e.position pos, e.previous_position prec, a.id, a.name nom FROM chart_entries e
            JOIN artists a ON a.id = e.artist_id WHERE e.chart_run_id = ? ORDER BY e.position LIMIT 3""", [r["id"]])]
        if len(top) < 3:
            continue
        for x in top:
            x["photo"] = (par_id.get(x["id"]) or {}).get("photo")
        code = c["code"].lower()
        pays.append({"code": code, "nom": c["name_fr"], "artistes": top,
                     "couleurs": ["#%02x%02x%02x" % tuple(v) for v in couleurs.get(code, [(123, 92, 255)] * 3)]})
    wa = db.one("""SELECT e.position, a.id, a.name nom, tr.title titre FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
        JOIN chart_types t ON t.id = r.chart_type_id JOIN artists a ON a.id = e.artist_id JOIN tracks tr ON tr.id = e.track_id
        WHERE t.code = 'prime-wa' AND r.status = 'published' ORDER BY r.period_end DESC, e.position LIMIT 1""")
    n1wa = {**dict(wa), "photo": (par_id.get(wa["id"]) or {}).get("photo")} if wa else None
    d = {"semaine": sem, "pays": pays, "artistes": artistes, "n1_afrique_ouest": n1wa}
    try:
        db.run("""INSERT INTO live_cache (cle, valeur, expire) VALUES (?, ?, NOW() + interval '10 minutes')
                  ON CONFLICT (cle) DO UPDATE SET valeur = EXCLUDED.valeur, expire = EXCLUDED.expire""",
               [CLE_DONNEES, json.dumps(d, ensure_ascii=False)])
    except Exception:  # noqa: BLE001
        pass
    return d


# ---------------------------------------------------------------- votes et réclamations (commentaires saisis ou lus)

def _commentaire(e: dict, user: str, texte: str) -> None:
    t = _norm(texte)
    e["dernier"] = ([{"user": user[:30], "texte": texte[:80]}] + e.get("dernier", []))[:6]
    if e["scene"] == "versus":
        votants = set(e.get("votants", []))
        if user not in votants:
            if _norm(e["versus"]["a"]) in t or t == "1":
                e["votes"]["a"] += 1; votants.add(user)
            elif _norm(e["versus"]["b"]) in t or "didi" in t or t == "2":
                e["votes"]["b"] += 1; votants.add(user)
        e["votants"] = list(votants)[-5000:]
        return
    for a in sorted(donnees()["artistes"], key=lambda a: -len(a["cle"])):
        if len(a["cle"]) >= 4 and a["cle"] in t:
            m = next((x for x in e["mur"] if x["id"] == a["id"]), None)
            if m:
                m["n"] += 1
            else:
                e["mur"].append({"id": a["id"], "n": 1})
            e["mur"].sort(key=lambda x: -x["n"])
            break


# ---------------------------------------------------------------- pages et API

def regie(request, chemin):
    S._verifie(chemin)
    u = S._utilisateur(request)
    if not u:
        from django.shortcuts import redirect
        return redirect(f"/studio/{chemin}")
    nonce = secrets.token_urlsafe(18)
    html = S._JINJA.get_template("live-regie.html").render(base=f"/studio/{chemin}", nonce=nonce, csrf=get_token(request),
                                                          ecran=f"/live/{jeton_ecran()}/ecran")
    return S._reponse(HttpResponse(html), nonce)


def regie_etat(request, chemin):
    """GET : l'état ; POST : {set: {...}} pour modifier, {raz: 'votes'|'mur'}, {commentaire: {user, texte}}, {rafraichir: 1}."""
    S._verifie(chemin)
    if not S._utilisateur(request):
        return S._json({"erreur": "verrouillé"}, 403)
    e = {**etat_courant()}
    if request.method == "POST":
        m = S._corps(request)
        if m.get("rafraichir"):
            db.run("DELETE FROM live_cache WHERE cle = ?", [CLE_DONNEES])
        if m.get("commentaire"):
            _commentaire(e, str(m["commentaire"].get("user") or "régie"), str(m["commentaire"].get("texte") or ""))
        if m.get("raz") == "votes":
            e["votes"], e["votants"] = {"a": 0, "b": 0}, []
        if m.get("raz") == "mur":
            e["mur"] = []
        for k, v in (m.get("set") or {}).items():
            if k in ETAT_DEFAUT:
                e[k] = v
        _ecrit(CLE_ETAT, e)
        _memo.update(t=time.time(), v=e)
    return S._json({k: v for k, v in e.items() if k != "votants"})


def regie_donnees(request, chemin):
    S._verifie(chemin)
    if not S._utilisateur(request, verrou=False):
        return S._json({"erreur": "verrouillé"}, 403)
    return S._json({**donnees(), "biblio": _lit(CLE_BIBLIO, {})})


def _verifie_jeton(jeton: str) -> None:
    j = jeton_ecran()
    if not j or not secrets.compare_digest(jeton, j):
        raise Http404


def ecran(request, jeton):
    _verifie_jeton(jeton)
    nonce = secrets.token_urlsafe(18)
    html = S._JINJA.get_template("live-ecran.html").render(base=f"/live/{jeton}", nonce=nonce)
    r = S._reponse(HttpResponse(html), nonce)
    r["Content-Security-Policy"] = r["Content-Security-Policy"].replace("frame-ancestors 'none'", "frame-ancestors 'self'")
    return r


def ecran_etat(request, jeton):
    _verifie_jeton(jeton)
    return S._json({k: v for k, v in etat_courant().items() if k != "votants"})


def ecran_donnees(request, jeton):
    _verifie_jeton(jeton)
    return S._json({**donnees(), "biblio": _lit(CLE_BIBLIO, {})})
