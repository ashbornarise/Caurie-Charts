"""Monthly Show : le vote du public (cauricharts.com/show/vote).

Règles (scénario Édition 1, validé le 10 oct. 2026) :
- le vote du public ne touche JAMAIS aux classements : il décide seulement des catégories du public (choix du public,
  Clip du mois…) et sert aux pronostics ;
- seul le site compte des voix officielles ; les commentaires des réseaux ne font que l'ambiance ;
- un compte (lien de connexion par e-mail) = une voix par vote, imposé par la base (uq_show_vote) ;
- les cadeaux des réseaux ne valent jamais de voix ; participation gratuite, sans achat ;
- voix suspectes mises de côté (flagged), jamais supprimées, décomptées publiquement après le live.
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from core import conf, db

DUREE_LIEN = 30          # minutes de validité d'un lien de connexion
SEUIL_AFFICHAGE = 20     # en dessous, l'écran dit « le vote chauffe » au lieu d'afficher des pourcentages
JETABLES = {"yopmail.com", "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "temp-mail.org",
            "trashmail.com", "getnada.com", "sharklasers.com", "dispostable.com", "maildrop.cc", "throwawaymail.com"}


def _now(delta=0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=delta)).strftime("%Y-%m-%d %H:%M:%S")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def email_jetable(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in JETABLES


# ---------------------------------------------------------------- comptes
def demander_lien(email: str, pseudo: str, pays: str | None, affichage: bool, parrain: str | None, ip_hash: str) -> str:
    """Crée un lien de connexion (valable 30 min) ; renvoie le jeton en clair, à envoyer par e-mail."""
    token = secrets.token_urlsafe(24)
    db.insert("show_login_tokens", {"token_hash": _hash(token), "email": email.lower(), "ip_hash": ip_hash,
                                    "data": json.dumps({"pseudo": pseudo, "pays": pays, "affichage": affichage, "parrain": parrain}),
                                    "expires_at": _now(DUREE_LIEN * 60)})
    return token


def valider_lien(token: str, ip_hash: str) -> dict | None:
    """Consomme un lien de connexion ; crée le compte au premier passage. Renvoie le compte, ou None si invalide."""
    row = db.one("SELECT * FROM show_login_tokens WHERE token_hash = ?", [_hash(token)])
    if not row or row["used_at"] or str(row["expires_at"]) < _now():
        return None
    db.update("show_login_tokens", {"used_at": _now()}, "id = :id", {"id": row["id"]})
    compte = db.one("SELECT * FROM show_accounts WHERE email = ?", [row["email"]])
    if compte:
        if not compte["verified_at"]:
            db.update("show_accounts", {"verified_at": _now()}, "id = :id", {"id": compte["id"]})
        return compte
    d = json.loads(row["data"] or "{}")
    parrain = db.one("SELECT id FROM show_accounts WHERE ref = ?", [d.get("parrain")]) if d.get("parrain") else None
    cid = db.insert("show_accounts", {"email": row["email"], "pseudo": (d.get("pseudo") or "fan")[:40], "country_code": d.get("pays"),
                                      "display_ok": 1 if d.get("affichage") else 0, "ref": secrets.token_hex(4),
                                      "referred_by": parrain["id"] if parrain else None, "ip_hash": ip_hash, "verified_at": _now()})
    return db.one("SELECT * FROM show_accounts WHERE id = ?", [cid])


def compte(cid) -> dict | None:
    return db.one("SELECT * FROM show_accounts WHERE id = ?", [int(cid)]) if cid else None


# ---------------------------------------------------------------- votes
def votes_ouverts(key: str) -> list:
    polls = db.all("SELECT * FROM show_polls WHERE show_key = ? AND status IN ('ouvert', 'scelle') ORDER BY sort_order, id", [key])
    for p in polls:
        p["options"] = json.loads(p["options"] or "[]")
    return polls


def voter(poll_slug: str, option: str, cpt: dict, ip_hash: str) -> str:
    """Enregistre une voix. Renvoie 'ok', 'deja', 'ferme' ou 'invalide'."""
    key = conf.get("show.key")
    p = db.one("SELECT * FROM show_polls WHERE show_key = ? AND slug = ?", [key, poll_slug])
    if not p or p["status"] != "ouvert":
        return "ferme"
    if option not in {o["key"] for o in json.loads(p["options"] or "[]")}:
        return "invalide"
    if db.one("SELECT 1 FROM show_votes WHERE poll_id = ? AND account_id = ?", [p["id"], cpt["id"]]):
        return "deja"
    # signaux faibles : compte créé il y a moins de 5 min, ou beaucoup de voix depuis la même empreinte IP en peu de temps
    # (en Afrique de l'Ouest beaucoup de mobiles partagent une IP : on met de côté pour vérification, on ne bloque pas)
    recent = str(cpt["created_at"]) > _now(-300)
    rafale = int(db.value("SELECT COUNT(*) FROM show_votes WHERE poll_id = ? AND ip_hash = ? AND created_at > ?",
                          [p["id"], ip_hash, _now(-600)]) or 0) >= 15
    try:
        db.insert("show_votes", {"poll_id": p["id"], "account_id": cpt["id"], "option_key": option, "ip_hash": ip_hash,
                                 "flagged": 1 if (recent and rafale) or email_jetable(cpt["email"]) else 0})
    except Exception:  # noqa: BLE001 — contrainte d'unicité : déjà voté (double clic)
        return "deja"
    return "ok"


def ma_voix(poll_id: int, cid: int) -> str | None:
    return db.value("SELECT option_key FROM show_votes WHERE poll_id = ? AND account_id = ?", [poll_id, cid])


def resultats(poll: dict, admin: bool = False) -> dict:
    """Pourcentages des voix valides (les voix mises de côté ne comptent pas). En dessous du seuil, pas de chiffres publics."""
    rows = db.all("""SELECT option_key, COUNT(*) AS n, SUM(flagged) AS f FROM show_votes WHERE poll_id = ?
                     GROUP BY option_key""", [poll["id"]])
    valides = {r["option_key"]: int(r["n"]) - int(r["f"] or 0) for r in rows}
    total = sum(valides.values())
    ecartees = sum(int(r["f"] or 0) for r in rows)
    opts = poll["options"] if isinstance(poll["options"], list) else json.loads(poll["options"] or "[]")
    out = {"slug": poll["slug"], "titre": poll["title"], "statut": poll["status"], "total_suffisant": total >= SEUIL_AFFICHAGE,
           "options": [{"key": o["key"], "label": o["label"], "sub": o.get("sub"), "n": valides.get(o["key"], 0) if total >= SEUIL_AFFICHAGE else None, "pct": round(100 * valides.get(o["key"], 0) / total) if total else 0}
                       for o in opts]}
    if poll["status"] == "scelle" and not admin:
        out["options"] = [{**o, "pct": None} for o in out["options"]]   # dernière minute : résultat sous scellé
    if admin:
        out.update({"total": total, "ecartees": ecartees, "brut": valides})
    return out


# ---------------------------------------------------------------- codes secrets
def saisir_code(code: str, cpt: dict) -> str:
    key = conf.get("show.key")
    c = db.one("SELECT * FROM show_codes WHERE show_key = ? AND code = ? AND status = 'actif'", [key, code.strip().upper()])
    if not c:
        return "invalide"
    if db.one("SELECT 1 FROM show_code_entries WHERE code_id = ? AND account_id = ?", [c["id"], cpt["id"]]):
        return "deja"
    db.run("INSERT INTO show_code_entries (code_id, account_id) VALUES (?, ?) ON CONFLICT DO NOTHING", [c["id"], cpt["id"]])
    return "ok"


def preparer_codes(key: str, n: int = 6) -> None:
    """Un code toutes les 30 minutes (6 pour l'émission), préparés d'avance, activés par la régie."""
    if int(db.value("SELECT COUNT(*) FROM show_codes WHERE show_key = ?", [key]) or 0):
        return
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(n):
        db.insert("show_codes", {"show_key": key, "code": "".join(secrets.choice(alphabet) for _ in range(5))})


# ---------------------------------------------------------------- votes de la soirée, créés depuis les vrais classements
def preparer_votes(key: str, programme: dict) -> int:
    """Crée (une seule fois) les votes de l'émission à partir du conducteur réel. Renvoie le nombre de votes créés."""
    existants = {r["slug"] for r in db.all("SELECT slug FROM show_polls WHERE show_key = ?", [key])}
    seg = programme["segments"]
    big5 = [s for s in seg if s["type"] in ("clip", "numero1") and s.get("big5")]
    clips = [s for s in seg if s["type"] in ("clip", "numero1") and not s.get("big5") and s.get("youtube")]
    def opt(s):
        return {"key": f"{s['artiste']}|{s['titre']}"[:60], "label": s["artiste"], "sub": s["titre"], "image": s.get("photo")}
    votes = [
        ("presence", "presence", "Je suis là !", [{"key": "present", "label": "Je suis là"}]),
        ("pronostic-big5", "pronostic", "Qui sera N°1 de l'Afrique de l'Ouest ?", sorted([opt(s) for s in big5], key=lambda o: o["label"])),
        ("clip-du-mois", "choix", "Clip du mois (vote du public)", [opt(s) for s in clips][:12]),
        ("prochain-pays", "sondage", "Quel pays voulez-vous voir classé en premier ?", [{"key": p, "label": p} for p in programme.get("bientot", [])]),
    ]
    for s in seg:
        if s["type"] == "duel":
            votes.append((f"duel-{s['code'].lower()}", "pronostic", f"Photo-finish {s['nom']} : qui sera N°1 ?", [opt(d) for d in s["duel"]]))
    n = 0
    for i, (slug, kind, titre, options) in enumerate(votes):
        if slug in existants or not options:
            continue
        db.insert("show_polls", {"show_key": key, "slug": slug, "kind": kind, "title": titre, "options": json.dumps(options, ensure_ascii=False),
                                 "sort_order": i})
        n += 1
    preparer_codes(key)
    return n


def distinctions_public(key: str) -> dict:
    """Les gagnants mesurables (pseudos avec accord seulement), pour la régie."""
    presence = db.all("""SELECT a.pseudo, a.country_code, v.created_at FROM show_votes v JOIN show_polls p ON p.id = v.poll_id
                         JOIN show_accounts a ON a.id = v.account_id WHERE p.show_key = ? AND p.slug = 'presence' AND v.flagged = 0
                         AND a.display_ok = 1 ORDER BY v.created_at, v.id LIMIT 3""", [key])
    pays = db.all("""SELECT a.country_code, COUNT(DISTINCT a.id) AS n FROM show_votes v JOIN show_polls p ON p.id = v.poll_id
                     JOIN show_accounts a ON a.id = v.account_id WHERE p.show_key = ? AND v.flagged = 0 AND a.country_code IS NOT NULL
                     GROUP BY a.country_code ORDER BY n DESC LIMIT 5""", [key])
    parrains = db.all("""SELECT a.pseudo, COUNT(f.id) AS n FROM show_accounts a JOIN show_accounts f ON f.referred_by = a.id
                         WHERE f.verified_at IS NOT NULL AND a.display_ok = 1 GROUP BY a.id, a.pseudo ORDER BY n DESC LIMIT 3""")
    prono = db.all("""SELECT a.pseudo, COUNT(*) AS bons FROM show_votes v JOIN show_polls p ON p.id = v.poll_id
                      JOIN show_accounts a ON a.id = v.account_id
                      WHERE p.show_key = ? AND p.kind = 'pronostic' AND p.answer IS NOT NULL AND v.option_key = p.answer
                        AND v.flagged = 0 AND a.display_ok = 1
                      GROUP BY a.id, a.pseudo ORDER BY bons DESC, MIN(v.created_at) LIMIT 3""", [key])
    codes = int(db.value("SELECT COUNT(*) FROM show_codes WHERE show_key = ? AND status <> 'prepare'", [key]) or 0)
    fideles = db.all("""SELECT a.pseudo FROM show_code_entries e JOIN show_codes c ON c.id = e.code_id JOIN show_accounts a ON a.id = e.account_id
                        WHERE c.show_key = ? AND a.display_ok = 1 GROUP BY a.id, a.pseudo HAVING COUNT(*) >= ? ORDER BY a.pseudo""",
                     [key, max(1, codes)]) if codes else []
    return {"premiers": presence, "pays": pays, "ambassadeurs": parrains, "pronostiqueurs": prono, "fideles": fideles}
