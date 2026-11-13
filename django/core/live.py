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
from contextlib import contextmanager

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
    # régie v2 (13/11) : le son sort de la régie ; l'écran affiche le titre en cours et les effets visuels
    "enCours": None, "fx": None, "bandeau": "", "minuteur": 0, "carteExt": None,
    # régie v3 « télécommande » (13/11) : l'écran joue tout (clip avec son, son seul, YouTube) ; une seule régie a la main
    "media": None, "volume": 0.85, "paysListe": ["ci", "ng", "tg", "gh"], "maitre": None, "chat": [],
    # v3.1 : la mascotte passe à l'écran entre les étapes (ce qui vient de se passer, ce qui arrive, anecdotes)
    "mascotte": None, "lecture": None,
    # chat TikTok (connecteur du PC) : cadeaux, classement des donateurs, spectateurs, « j'aime », abonnés
    "donateurs": {}, "cadeau": None, "likes": 0, "spectateurs": None, "pic": 0, "abonnes": 0, "reglesCadeaux": True, "topFans": True,
    # jeux et studio (13/11) : devine le titre, qui est-ce, mot mystère, roue, sondage, « d'où tu nous regardes », tirage au sort,
    # roi du live, objectif de « j'aime », bienvenue aux abonnés ; disposition des éléments et déroulé modifiables
    "jeu": None, "devineurs": {}, "roi": True, "roiActuel": None, "disposition": {}, "pos": 0,
    "deroule": ["attente", "rituel", "top3", "versus", "mur", "finale", "fin"],
    "chatteurs": [], "tirage": None, "objectifLikes": 0, "bienvenue": True, "abonne": None,
}
JEUX_DEVINE = ("blind", "photo", "mot")
# « D'où tu nous regardes ? » : mots du chat -> pays (les codes de 2 lettres ne comptent que s'ils sont écrits seuls)
PAYS_CHAT = {"ci": ["cotedivoire", "ivoire", "abidjan", "bouake", "yamoussoukro", "babi"], "ng": ["nigeria", "naija", "lagos", "abuja"],
             "tg": ["togo", "lome", "kara"], "gh": ["ghana", "accra", "kumasi"], "bj": ["benin", "cotonou", "portonovo"],
             "sn": ["senegal", "dakar"], "ml": ["mali", "bamako"], "bf": ["burkina", "ouaga", "bobo"], "gn": ["guinee", "conakry"],
             "ne": ["niger", "niamey"], "cm": ["cameroun", "douala", "yaounde"], "fr": ["france", "paris", "lyon", "marseille"],
             "us": ["usa", "etatsunis", "amerique"], "ca": ["canada", "montreal", "quebec"], "be": ["belgique", "bruxelles"],
             "cd": ["rdc", "kinshasa", "congo"], "ga": ["gabon", "libreville"], "ma": ["maroc", "casablanca"], "lr": ["liberia"],
             "sl": ["sierraleone"], "gm": ["gambie"], "cv": ["capvert"], "mr": ["mauritanie"], "gw": ["guineebissau"]}
PAYS_NOMS = {"ci": "Côte d'Ivoire", "ng": "Nigeria", "tg": "Togo", "gh": "Ghana", "bj": "Bénin", "sn": "Sénégal", "ml": "Mali",
             "bf": "Burkina Faso", "gn": "Guinée", "ne": "Niger", "cm": "Cameroun", "fr": "France", "us": "États-Unis", "ca": "Canada",
             "be": "Belgique", "cd": "RD Congo", "ga": "Gabon", "ma": "Maroc", "lr": "Liberia", "sl": "Sierra Leone", "gm": "Gambie",
             "cv": "Cap-Vert", "mr": "Mauritanie", "gw": "Guinée-Bissau"}
# l'ordre compte : « nigeria » avant « niger », « guineebissau » avant « guinee »
_PAYS_MOTS = sorted(((m, c) for c, mots in PAYS_CHAT.items() for m in mots), key=lambda mc: -len(mc[0]))

# Anecdotes vérifiées (sources croisées le 12/11/2026, vidéos « Cauri raconte ») : la mascotte les raconte en direct.
ANECDOTES = {
    8: ["À 13 ans, Didi B tenait le premier rôle du film « Les Frères Kadogo », primé au Fespaco.",
        "Didi B est le seul rappeur ivoirien à avoir rempli le stade Félix Houphouët-Boigny : plus de 30 000 places.",
        "Avant sa carrière solo, Didi B a fondé le groupe Kiff No Beat en 2009, avec ses cousins.",
        "Sur son album « Shogun in Lagos », Didi B invite 6 artistes nigérians, dont Davido et Phyno."],
    5: ["« Himra », ce sont les lettres de son prénom, Rahim, dans le désordre.",
        "En octobre 2025, Himra a remporté 5 trophées au Primud en une seule nuit, dont le Primud d'or.",
        "Le 28 janvier 2026, Himra a rempli le Zénith de Paris.",
        "Le 26 décembre, Himra joue au stade d'Ébimpé : plus de 60 000 places."],
    711: ["Dans « Nyamien Son No Fall », Nyamien veut dire Dieu en baoulé.",
          "Le clip de « 446 », Jeune Lion avec Freeze Corleone, dépasse 1,3 million de vues.",
          "Jeune Lion est né à Marcory, à Abidjan, et mélange reggae, coupé-décalé et trap."],
}
_memo: dict = {}
MAITRE_DELAI = 20   # secondes sans signe de vie avant qu'une autre régie puisse prendre la main sans forcer


def jeton_ecran() -> str | None:
    secret = S.chemin_secret()
    return hmac.new(secret.encode(), b"ecran-live", hashlib.sha256).hexdigest()[:28] if secret else None


def _lit(cle: str, defaut=None, verrou: bool = False):
    try:
        v = db.value("SELECT valeur FROM live_cache WHERE cle = ? AND expire > NOW()" + (" FOR UPDATE" if verrou else ""), [cle])
        return json.loads(v) if v else defaut
    except Exception:  # noqa: BLE001 — table absente : état par défaut
        if verrou:   # écriture : surtout ne pas repartir de l'état par défaut (on effacerait le live)
            raise
        return defaut


def _ecrit(cle: str, valeur, jours: int = 3) -> None:
    db.run("""INSERT INTO live_cache (cle, valeur, expire) VALUES (?, ?, NOW() + (? || ' days')::interval)
              ON CONFLICT (cle) DO UPDATE SET valeur = EXCLUDED.valeur, expire = EXCLUDED.expire""",
           [cle, json.dumps(valeur, ensure_ascii=False), str(jours)])


def _cle(mode: str = "") -> str:
    return CLE_ETAT + ("-test" if mode == "test" else "")   # mode répétition : un état et un écran à part


def _mode(request) -> str:
    return "test" if request.GET.get("mode") == "test" else ""


def etat_courant(mode: str = "") -> dict:
    # mémoire de l'instance 0,4 s : l'écran interroge souvent, la base ne voit qu'une partie des appels
    m = _memo.get(mode)
    if m and time.time() - m[0] < 0.4:
        return m[1]
    e = {**ETAT_DEFAUT, **(_lit(_cle(mode), {}) or {})}
    _memo[mode] = (time.time(), e)
    return e


@contextmanager
def _verrou(mode: str = ""):
    """Lecture fraîche de l'état, verrouillée jusqu'à l'écriture (SELECT … FOR UPDATE) : la régie, le connecteur TikTok
    et l'écran écrivent en même temps sans s'effacer (un cadeau ou un pari n'est jamais perdu). e["_pas"] = True : ne rien écrire."""
    with db.atomic():
        e = {**ETAT_DEFAUT, **(_lit(_cle(mode), {}, verrou=True) or {})}
        yield e
        if not e.pop("_pas", False):
            _ecrit(_cle(mode), e)
    _memo[mode] = (time.time(), e)


def _public(e: dict) -> dict:
    p = {k: v for k, v in e.items() if k not in ("votants", "chatteurs")}
    j = p.get("jeu")
    if isinstance(j, dict) and ("paris" in j or "votants" in j):   # les listes de joueurs restent sur le serveur
        p["jeu"] = {**{k: v for k, v in j.items() if k not in ("paris", "votants")}, "nParis": len(j.get("paris") or j.get("votants") or {})}
    p["nChatteurs"] = len(e.get("chatteurs") or [])
    return p


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
    d = {"semaine": sem, "pays": pays, "artistes": artistes, "n1_afrique_ouest": n1wa, "anecdotes": {str(k): v for k, v in ANECDOTES.items()}}
    try:
        db.run("""INSERT INTO live_cache (cle, valeur, expire) VALUES (?, ?, NOW() + interval '10 minutes')
                  ON CONFLICT (cle) DO UPDATE SET valeur = EXCLUDED.valeur, expire = EXCLUDED.expire""",
               [CLE_DONNEES, json.dumps(d, ensure_ascii=False)])
    except Exception:  # noqa: BLE001
        pass
    return d


# ---------------------------------------------------------------- votes et réclamations (commentaires saisis ou lus)

def _point(e: dict, user: str, nom: str, n: int = 1) -> None:
    d = e.setdefault("devineurs", {})
    x = d.get(user) or {"nom": nom, "points": 0}
    d[user] = {"nom": nom or x["nom"], "points": int(x["points"]) + n}
    if len(d) > 300:
        e["devineurs"] = dict(sorted(d.items(), key=lambda kv: -kv[1]["points"])[:300])


def _choix(t: str, options: list):
    """Le numéro d'une case (« 3 ») ou son nom écrit en commentaire."""
    if t.isdigit() and 1 <= int(t) <= len(options):
        return int(t) - 1
    for k, o in sorted(enumerate(options), key=lambda ko: -len(_norm(str(ko[1])))):
        no = _norm(str(o))
        if len(no) >= 3 and no in t:
            return k
    return None


def _jeu_commentaire(e: dict, user: str, nom: str, t: str) -> bool:
    """Un jeu est en cours : le commentaire est une réponse, un pari ou un vote. Renvoie True s'il a été pris par le jeu."""
    j = e.get("jeu") or {}
    ty, now = j.get("type"), int(time.time() * 1000)
    if ty in JEUX_DEVINE and j.get("phase") == "jeu":
        fin = int(j.get("t") or 0) + int(j.get("duree") or 30) * 1000 + 3000
        if not j.get("gagnant") and now <= fin and any(len(k) >= 3 and k in t for k in j.get("cles") or []):
            r = j.get("reponse") or {}
            e["jeu"] = {**j, "phase": "fin", "gagnant": {"user": user, "nom": nom, "t": now}}
            _point(e, user, nom, 1)
            e["fx"] = {"type": "confettis", "t": now}
            quoi = r.get("artiste") or r.get("mot") or ""
            e["mascotte"] = {"titre": f"BRAVO {nom.upper()} !", "texte": f"Bonne réponse : {quoi}" + (f", « {r['titre']} »" if r.get("titre") else "") + ".",
                             "pose": "m4-appel", "duree": 7000, "t": now}
        return True
    if ty == "roue" and j.get("phase") == "paris":
        i = _choix(t, j.get("segments") or [])
        paris = j.setdefault("paris", {})
        if i is not None and user not in paris and len(paris) < 5000:
            paris[user] = [i, nom]
        return True
    if ty in ("sondage", "dou") and j.get("phase") == "vote":
        votants = j.setdefault("votants", {})
        if user in votants or len(votants) >= 20000:
            return True
        if ty == "sondage":
            i = _choix(t, j.get("options") or [])
            if i is not None:
                votants[user] = 1; j["votes"][i] = int(j["votes"][i]) + 1
        else:
            code = t if t in PAYS_CHAT else next((c for m, c in _PAYS_MOTS if m in t), None)
            if code:
                votants[user] = 1; tp = j.setdefault("pays", {}); tp[code] = int(tp.get(code) or 0) + 1
        return True
    return e.get("scene") == "jeu"   # jeu terminé mais encore à l'écran : les réponses tardives ne vont pas au mur


def _jeu_action(e: dict, a: str) -> None:
    j, now = e.get("jeu") or {}, int(time.time() * 1000)
    if a == "reveler" and j.get("phase") in ("jeu", "vote"):
        e["jeu"] = {**j, "phase": "fin", "tFin": now}
    if a == "lancer" and j.get("type") == "roue" and j.get("phase") == "paris" and j.get("segments"):
        r = secrets.randbelow(len(j["segments"]))   # le tirage se fait ici, pas dans le navigateur
        paris = j.get("paris") or {}
        bons = [(u, v[1]) for u, v in paris.items() if v[0] == r]
        for u, n in bons:
            _point(e, u, n, 1)
        e["jeu"] = {**j, "phase": "tourne", "resultat": r, "t": now, "gagnants": [n for _, n in bons][:30], "nGagnants": len(bons), "nParisFin": len(paris)}
    if a == "tirage":
        ch = (e.get("chatteurs") or [])[-200:]
        if ch:
            u, n = ch[secrets.randbelow(len(ch))]
            e["tirage"] = {"user": u, "nom": n, "t": now, "parmi": len(ch)}


def _commentaire(e: dict, user: str, texte: str, nom: str | None = None) -> None:
    t = _norm(texte)
    nom = (nom or user)[:30]
    e["dernier"] = ([{"user": user[:30], "texte": texte[:80]}] + e.get("dernier", []))[:6]
    if not user.startswith("régie"):
        e["chat"] = (e.get("chat") or [])[-119:] + [int(time.time())]   # rythme du chat (conseils de l'agent)
        e["chatteurs"] = [c for c in (e.get("chatteurs") or []) if c[0] != user][-299:] + [[user, nom]]   # pour le tirage au sort
    if _jeu_commentaire(e, user, nom, t):
        return
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
    from django.shortcuts import redirect
    return redirect(f"/live/{jeton_regie()}/regie")   # une seule régie : le lien secret (recherche Deezer comprise)


def regie_etat(request, chemin):
    """GET : l'état ; POST : {set: {...}} pour modifier, {raz: 'votes'|'mur'}, {commentaire: {user, texte}}, {rafraichir: 1}."""
    S._verifie(chemin)
    if not S._utilisateur(request):
        return S._json({"erreur": "verrouillé"}, 403)
    return _maj_etat(request)


def _maj_etat(request):
    """Une seule régie a la main (la première ; une autre peut « prendre la main »). Les autres regardent : 409."""
    mode = _mode(request)
    ident = (request.headers.get("X-Regie") or "")[:40]
    libre_pour = lambda e: (lambda mt: not mt.get("id") or mt.get("id") == ident or time.time() - float(mt.get("vu") or 0) > MAITRE_DELAI)(e.get("maitre") or {})
    if request.method == "GET":
        e = {**etat_courant(mode)}
        maitre = e.get("maitre") or {}
        if ident and maitre.get("id") == ident and time.time() - float(maitre.get("vu") or 0) > 5:   # signe de vie : au plus toutes les 5 s
            with _verrou(mode) as e:
                if (e.get("maitre") or {}).get("id") == ident:
                    e["maitre"] = {"id": ident, "vu": time.time()}
                else:
                    e["_pas"] = True
        maitre = e.get("maitre") or {}
        return S._json({**_public(e), "aLaMain": bool(ident) and (maitre.get("id") == ident or libre_pour(e))})
    m = S._corps(request)
    if m.get("rafraichir"):
        db.run("DELETE FROM live_cache WHERE cle = ?", [CLE_DONNEES])
    refus = False
    with _verrou(mode) as e:
        if ident and not libre_pour(e) and not m.get("prendre"):
            refus = True; e["_pas"] = True
        else:
            if ident:
                e["maitre"] = {"id": ident, "vu": time.time()}
            if m.get("commentaire"):
                _commentaire(e, str(m["commentaire"].get("user") or "régie"), str(m["commentaire"].get("texte") or ""))
            if m.get("raz") == "votes":
                e["votes"], e["votants"] = {"a": 0, "b": 0}, []
            if m.get("raz") == "mur":
                e["mur"] = []
            for k, v in (m.get("set") or {}).items():
                if k in ETAT_DEFAUT and k != "maitre":
                    if k == "jeu" and isinstance(v, dict):   # l'heure du serveur fait foi (fin des réponses)
                        v = {**v, "t": int(time.time() * 1000) + (1500 if v.get("type") in JEUX_DEVINE else 0)}
                    e[k] = v
            if m.get("raz") == "devineurs":
                e["devineurs"] = {}
            if m.get("jeuAction"):
                _jeu_action(e, str(m["jeuAction"]))
    return S._json({**_public(e), "aLaMain": not refus}, 409 if refus else 200)


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
    html = S._JINJA.get_template("live-ecran.html").render(base=f"/live/{jeton}", nonce=nonce, mode=_mode(request))
    r = S._reponse(HttpResponse(html), nonce)
    # clips YouTube (artistes hors classement) : lecteur officiel intégré
    r["Content-Security-Policy"] = (r["Content-Security-Policy"].replace("frame-ancestors 'none'", "frame-ancestors 'self'")
        .replace("script-src 'self'", "script-src 'self' https://www.youtube.com https://s.ytimg.com")
        .replace("media-src 'self'", "media-src 'self' https://*.dzcdn.net")
        .replace("default-src 'self';", "default-src 'self'; frame-src https://www.youtube-nocookie.com https://www.youtube.com;"))
    r["Referrer-Policy"] = "strict-origin-when-cross-origin"   # YouTube refuse de jouer un clip intégré sans l'origine (erreur 153)
    return r


def ecran_etat(request, jeton):
    _verifie_jeton(jeton)
    return S._json(_public(etat_courant(_mode(request))))


def ecran_donnees(request, jeton):
    _verifie_jeton(jeton)
    return S._json({**donnees(), "biblio": _lit(CLE_BIBLIO, {})})


# ---------------------------------------------------------------- régie par lien secret (13/11/2026, demande du fondateur)
# Sans empreinte ni mot de passe, pour qu'un assistant puisse tenir la régie : le lien (28 caractères aléatoires, déduits
# du chemin secret du Studio) suffit. Le garder privé ; changer STUDIO_CHEMIN le révoque.

def jeton_regie() -> str | None:
    secret = S.chemin_secret()
    return hmac.new(secret.encode(), b"regie-live", hashlib.sha256).hexdigest()[:28] if secret else None


def _verifie_regie(jeton: str) -> None:
    j = jeton_regie()
    if not j or not secrets.compare_digest(jeton, j):
        raise Http404


def _page_regie(request, api: str):
    nonce = secrets.token_urlsafe(18)
    gabarit = "live-regie-dj.html" if request.path.endswith("/dj") else "live-regie.html"
    html = S._JINJA.get_template(gabarit).render(api=api, nonce=nonce, csrf=get_token(request), ecran=f"/live/{jeton_ecran()}/ecran")
    r = S._reponse(HttpResponse(html), nonce)
    r["Content-Security-Policy"] = (r["Content-Security-Policy"]
        .replace("connect-src 'self'", "connect-src 'self' https://*.public.blob.vercel-storage.com https://*.dzcdn.net")
        .replace("frame-ancestors 'none'", "frame-ancestors 'self'"))
    return r


def regie_lien(request, jeton):
    _verifie_regie(jeton)
    return _page_regie(request, f"/live/{jeton}/regie")


def regie_lien_etat(request, jeton):
    _verifie_regie(jeton)
    return _maj_etat(request)


def regie_lien_donnees(request, jeton):
    _verifie_regie(jeton)
    return S._json({**donnees(), "biblio": _lit(CLE_BIBLIO, {})})


# ---------------------------------------------------------------- plan B : un artiste absent de notre base (Deezer, gratuit)
# Le public peut réclamer n'importe qui : la régie le cherche sur Deezer (photo, fans, 10 titres phares avec extrait de 30 s).
# Deezer n'autorise pas l'appel direct depuis le navigateur pour la recherche ; les extraits, eux, se lisent directement.

def _deezer(chemin: str) -> dict:
    import urllib.request
    with urllib.request.urlopen("https://api.deezer.com/" + chemin, timeout=8) as r:
        return json.loads(r.read())


def regie_cherche(request, jeton):
    _verifie_regie(jeton)
    from urllib.parse import quote
    q = (request.GET.get("q") or "").strip()[:80]
    if len(q) < 2:
        return S._json({"artistes": []})
    try:
        d = _deezer(f"search/artist?limit=6&q={quote(q)}")
    except Exception:  # noqa: BLE001
        return S._json({"artistes": [], "erreur": "Deezer ne répond pas"})
    return S._json({"artistes": [{"id": a["id"], "nom": a["name"], "fans": a.get("nb_fan"), "photo": a.get("picture_xl") or a.get("picture_big")}
                                 for a in d.get("data") or []]})


def regie_titres(request, jeton, ident):
    _verifie_regie(jeton)
    try:
        a = _deezer(f"artist/{int(ident)}")
        t = _deezer(f"artist/{int(ident)}/top?limit=10")
    except Exception:  # noqa: BLE001
        return S._json({"titres": [], "erreur": "Deezer ne répond pas"})
    return S._json({"artiste": {"id": a.get("id"), "nom": a.get("name"), "fans": a.get("nb_fan"), "photo": a.get("picture_xl") or a.get("picture_big")},
                    "titres": [{"titre": x["title"], "url": x["preview"], "duree": x.get("duration"), "rang": x.get("rank"),
                                "pochette": (x.get("album") or {}).get("cover_big")} for x in t.get("data") or [] if x.get("preview")]})



# ---------------------------------------------------------------- YouTube : clips officiels des artistes hors classement
def _yt_recherche(q: str, n: int = 6) -> list:
    import urllib.error
    import urllib.request
    from urllib.parse import quote
    from core import env
    for cle in [env.get("YOUTUBE_API_KEY", ""), env.get("YOUTUBE_API_KEY_2", "")]:
        if not cle:
            continue
        url = ("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&videoEmbeddable=true&videoSyndicated=true"
               f"&maxResults={n}&q={quote(q)}&key={cle}")
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                return json.loads(r.read()).get("items") or []
        except urllib.error.HTTPError as e:
            if e.code == 403:   # quota épuisé : seconde clé
                continue
            return []
        except Exception:  # noqa: BLE001
            return []
    return []


def regie_clip(request, jeton):
    """Les vidéos candidates pour un titre, dans l'ordre : clip officiel, autres vidéos du titre (paroles, audio, live),
    puis vidéos de l'artiste. Beaucoup de labels interdisent la lecture de leurs clips hors de YouTube (erreur 150) :
    l'écran essaie les candidates une à une. Mémorisé 30 jours (une recherche = 100 unités de quota sur 10 000 par jour)."""
    _verifie_regie(jeton)
    import html as H
    artiste = (request.GET.get("artiste") or "").strip()[:80]
    titre = re.split(r"\s*[\(\[]\s*(feat|ft|with|extrait)", (request.GET.get("titre") or "").strip(), flags=re.I)[0][:80]
    if not artiste:
        return S._json({"clips": []})
    cle = "yt2-" + hashlib.sha1(_norm(artiste + "|" + titre).encode()).hexdigest()[:20]
    deja = _lit(cle)
    if deja is not None:
        return S._json({"clips": deja})
    na, nt = _norm(artiste), _norm(titre)[:8]
    def info(x, officiel):
        return {"id": x["id"]["videoId"], "titre": H.unescape(x["snippet"]["title"]), "officiel": officiel}
    clips, vus = [], set()
    def ajoute(x, officiel):
        if x["id"]["videoId"] not in vus:
            vus.add(x["id"]["videoId"]); clips.append(info(x, officiel))
    if titre:
        res = _yt_recherche(f"{artiste} {titre}", 8)
        for x in res:
            sn = x["snippet"]; ch, ti = _norm(sn["channelTitle"]), _norm(H.unescape(sn["title"]))
            if nt and nt in ti and (na in ch or "vevo" in ch):
                ajoute(x, True)
        for x in res:
            if nt and nt in _norm(H.unescape(x["snippet"]["title"])):
                ajoute(x, False)
    for x in _yt_recherche(f"{artiste} live", 4):
        if na in _norm(H.unescape(x["snippet"]["title"])) or na in _norm(x["snippet"]["channelTitle"]):
            ajoute(x, False)
    clips = clips[:7]
    _ecrit(cle, clips, jours=30)
    return S._json({"clips": clips})


def regie_youtube(request, jeton):
    """Recherche de clips intégrables (videoEmbeddable) : on évite d'afficher un clip refusé ou bloqué en direct."""
    _verifie_regie(jeton)
    import urllib.request
    from urllib.parse import quote
    from core import env
    q = (request.GET.get("q") or "").strip()[:80]
    cle = env.get("YOUTUBE_API_KEY", "") or env.get("YOUTUBE_API_KEY_2", "")
    if len(q) < 2 or not cle:
        return S._json({"clips": []})
    url = ("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&videoEmbeddable=true&videoSyndicated=true"
           f"&maxResults=6&q={quote(q + ' official video')}&key={cle}")
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            d = json.loads(r.read())
    except Exception:  # noqa: BLE001
        return S._json({"clips": [], "erreur": "YouTube ne répond pas"})
    return S._json({"clips": [{"id": x["id"]["videoId"], "titre": x["snippet"]["title"], "chaine": x["snippet"]["channelTitle"],
                               "vignette": ((x["snippet"].get("thumbnails") or {}).get("high") or {}).get("url")}
                              for x in d.get("items") or [] if (x.get("id") or {}).get("videoId")]})


# ---------------------------------------------------------------- commentaires TikTok envoyés par le connecteur local
from django.views.decorators.csrf import csrf_exempt  # noqa: E402


def _cadeau(e: dict, g: dict) -> None:
    """Un cadeau : classement des donateurs, remerciement à l'écran et, si les règles sont actives, un effet selon sa
    valeur (espacé pour ne pas saturer l'écran : petits effets toutes les 8 s au plus, mascotte toutes les 20 s)."""
    user, nom = str(g.get("user") or "?")[:30], str(g.get("nom") or g.get("user") or "?")[:40]
    d, n, cad = int(g.get("diamants") or 1), int(g.get("n") or 1), str(g.get("cadeau") or "cadeau")[:30]
    don = e.setdefault("donateurs", {})
    don[user] = {"nom": nom, "diamants": int((don.get(user) or {}).get("diamants") or 0) + d}
    if len(don) > 300:   # on garde les 300 plus généreux
        e["donateurs"] = dict(sorted(don.items(), key=lambda kv: -kv[1]["diamants"])[:300])
    now = int(time.time() * 1000)
    # le roi du live : le plus gros donateur garde la couronne jusqu'à ce qu'un autre le dépasse
    roi = max(e["donateurs"].items(), key=lambda kv: kv[1]["diamants"])
    ancien = e.get("roiActuel") or {}
    if roi[0] != ancien.get("user"):
        e["roiActuel"] = {"user": roi[0], "nom": roi[1]["nom"], "t": now}
        if ancien and e.get("roi", True) and now - int(e.get("mascAuto") or 0) > 15000:
            e["mascotte"] = {"titre": "NOUVEAU ROI DU LIVE !", "texte": f"{roi[1]['nom']} prend la couronne avec {roi[1]['diamants']} diamants.",
                             "pose": "m4-appel", "duree": 7000, "t": now}; e["mascAuto"] = now
    e["cadeau"] = {"user": user, "nom": nom, "cadeau": cad, "n": n, "diamants": d, "t": now}
    e["dernier"] = ([{"user": user, "texte": f"envoie {n} × {cad}"}] + e.get("dernier", []))[:6]
    if not e.get("reglesCadeaux", True):
        return
    dernier_fx, dernier_masc = int(e.get("fxAuto") or 0), int(e.get("mascAuto") or 0)
    if d >= 500:
        e["gong"] = now; e["fx"] = {"type": "confettis", "t": now}; e["fxAuto"] = now
        e["mascotte"] = {"titre": f"MERCI {nom.upper()} !", "texte": f"{n} × {cad} : tu fais trembler la Nuit Cauri Charts !", "pose": "m4-appel", "duree": 8000, "t": now}; e["mascAuto"] = now
    elif d >= 100 and now - dernier_fx > 8000:
        e["fx"] = {"type": "cauris", "t": now}; e["fxAuto"] = now
        if now - dernier_masc > 20000:
            e["mascotte"] = {"titre": f"Merci {nom} !", "texte": f"{n} × {cad}, quelle générosité !", "pose": "m4-appel", "duree": 6000, "t": now}; e["mascAuto"] = now
    elif d >= 5 and now - dernier_fx > 8000:
        e["fx"] = {"type": "coeurs", "t": now}; e["fxAuto"] = now


@csrf_exempt
def regie_commentaires(request, jeton):
    """Le connecteur du PC (tiktok-live-connector) envoie les commentaires par paquets : {liste: [{user, texte}], mode}."""
    _verifie_regie(jeton)
    if request.method != "POST":
        return S._json({"ok": False}, 405)
    m = S._corps(request)
    mode = "test" if m.get("mode") == "test" else ""
    with _verrou(mode) as e:
        _paquet(e, m)
    return S._json({"ok": True})


def _paquet(e: dict, m: dict) -> None:
    for c in (m.get("liste") or [])[:200]:
        _commentaire(e, str(c.get("user") or "?")[:30], str(c.get("texte") or "")[:200], str(c.get("nom") or "")[:30] or None)
    for g in (m.get("cadeaux") or [])[:100]:
        _cadeau(e, g)
    for u in (m.get("abonnes") or [])[:100]:
        e["abonnes"] = int(e.get("abonnes") or 0) + 1
        e["abonne"] = {"nom": str(u)[:30], "t": int(time.time() * 1000)}
        e["dernier"] = ([{"user": str(u)[:30], "texte": "s'abonne !"}] + e.get("dernier", []))[:6]
    e["likes"] = int(e.get("likes") or 0) + int(m.get("likes") or 0)
    if m.get("spectateurs") is not None:
        e["spectateurs"] = int(m["spectateurs"]); e["pic"] = max(int(e.get("pic") or 0), e["spectateurs"])



@csrf_exempt
def ecran_statut(request, jeton):
    """L'écran signale ce qui joue vraiment (clip YouTube, vidéo de repli, extrait) : la régie l'affiche."""
    _verifie_jeton(jeton)
    if request.method != "POST":
        return S._json({"ok": False}, 405)
    m = S._corps(request); mode = "test" if m.get("mode") == "test" else ""
    with _verrou(mode) as e:
        e["lecture"] = {"t": int(time.time()), "media": m.get("media"), "etat": str(m.get("etat") or "")[:40], "detail": str(m.get("detail") or "")[:120]}
    return S._json({"ok": True})
