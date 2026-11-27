"""« Cauri Rush » (27/11/2026) : le nouveau jeu du live TikTok, conçu avec Groq, Gemini et DeepSeek
(docs/studio-refonte/05 et 06) à partir de l'idée du fondateur.

2 ou 3 équipes (pays, artistes, sujets, ou les duels du classement de la semaine) montent chacune leur couloir ; les
spectateurs poussent leur équipe en tapant l'écran (j'aime). On rejoint une équipe en écrivant « 1 », « 2 » ou « 3 »
(ou son nom, son drapeau) ; celui qui tape sans écrire rejoint l'équipe qui a le MOINS de supporters (équilibrage par
le nombre de fans, jamais par le score : pas de remontées sans fin). Les 20 dernières secondes, les j'aime comptent
double (sprint final). Un cadeau donne un coup de pouce, sans jamais rien promettre en échange (règles TikTok).
L'ancienne « course des Cauris » reste disponible à côté.
"""
import random
import time

DUREE = 120          # s par manche : la première équipe en haut gagne, sinon celle qui mène au bout du temps
DEPART = 4           # s de compte à rebours
PAUSE = 14           # s d'écran de victoire avant la manche suivante
SPRINT = 20          # s de sprint final (j'aime x2)
VITESSE = 0.12       # % de couloir par seconde pour tout le monde (personne ne gagne sans le public)
LIKES_PCT = 30       # j'aime pour +1 %
MAX_PAQUET = 1.5     # % au plus par personne et par paquet de 2 s (anti-robot)
ESPACE_MS = 1500     # un commentaire utile par personne toutes les 1,5 s
COULEURS = ["#8B52FF", "#F5C14B", "#2EC4B6"]

SUJETS = [("Coupé-décalé", "Afrobeats"), ("Clip", "Audio"), ("Rap", "Zouglou"), ("Matin", "Soir"), ("Lomé", "Cotonou"),
          ("Abidjan", "Accra"), ("Dakar", "Lomé"), ("Amapiano", "Afrobeats"), ("Danse", "Chant"), ("Ancien son", "Nouveau son"),
          ("Coupé-décalé", "Afrobeats", "Rap"), ("Togo", "Bénin", "Ghana")]
PAYS_DUELS = [("tg", "bj"), ("ci", "gh"), ("sn", "ci"), ("ng", "gh"), ("tg", "gh"), ("bj", "ci"), ("ci", "cm"), ("sn", "ml"),
              ("tg", "bj", "gh"), ("ci", "gh", "ng"), ("sn", "ci", "bf")]


def _now() -> int:
    return int(time.time() * 1000)


def _norm(s: str) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode().split())


# ---------------------------------------------------------------- les duels

def _equipe(i: int, nom: str, sous: str = "", image: str = "", cles: list | None = None, drapeau: str = "") -> dict:
    noms = [_norm(x) for x in (cles or []) + [nom]]
    mots = [m for n in noms for m in n.replace("-", " ").split() if len(m) >= 4]   # « allez joachin ! » pour Joachin Migos
    return {"id": str(i + 1), "nom": nom[:28], "sous": sous[:40], "image": image, "drapeau": drapeau, "couleur": COULEURS[i],
            "cles": [c for c in dict.fromkeys(noms + mots) if len(c) >= 2]}


def duels(type_: str, data: dict, pays_noms: dict) -> list[dict]:
    """Les duels possibles d'un type : [{cle, titre, equipes}]."""
    out = []
    if type_ == "pays":
        for codes in PAYS_DUELS:
            eq = [_equipe(i, pays_noms.get(c, c.upper()), drapeau=c, cles=[c, pays_noms.get(c, "")]) for i, c in enumerate(codes)]
            out.append({"cle": "p:" + "-".join(codes), "titre": " contre ".join(e["nom"] for e in eq), "equipes": eq})
    elif type_ == "sujets":
        for noms in SUJETS:
            eq = [_equipe(i, n) for i, n in enumerate(noms)]
            out.append({"cle": "s:" + "-".join(_norm(n) for n in noms), "titre": " contre ".join(noms), "equipes": eq})
    elif type_ in ("classement", "artistes"):
        # duels tirés du classement de la semaine : N°1 contre N°2 de chaque pays, puis les N°1 des pays entre eux
        for p in data.get("pays") or []:
            top = [a for a in (p.get("artistes") or []) if a.get("nom")][:2]
            if len(top) == 2:
                eq = [_equipe(i, a["nom"], f"N°{i + 1} · {p.get('nom', '')}", a.get("photo") or "", [a.get("cle") or ""]) for i, a in enumerate(top)]
                out.append({"cle": f"c:{p.get('code')}:{top[0].get('id')}-{top[1].get('id')}", "titre": f"Le duel du {p.get('nom', '')}", "equipes": eq})
        n1 = [(p, (p.get("artistes") or [None])[0]) for p in data.get("pays") or [] if p.get("artistes")]
        n1 = [(p, a) for p, a in n1 if a and a.get("nom")]
        for k in range(0, len(n1) - 1, 2):
            paire = n1[k:k + 2]
            eq = [_equipe(i, a["nom"], f"N°1 · {p.get('nom', '')}", a.get("photo") or "", [a.get("cle") or ""]) for i, (p, a) in enumerate(paire)]
            out.append({"cle": "n1:" + "-".join(str(a.get("id")) for _, a in paire), "titre": "Les N°1 s'affrontent", "equipes": eq})
    return out


# ---------------------------------------------------------------- la partie

def _pos(r: dict, eq: str, now: int | None = None) -> float:
    if r.get("phase") == "fin":
        return float((r.get("posFin") or {}).get(eq) or 0)
    now = now or _now()
    roule = max(0.0, (now - int(r["t"])) / 1000) * VITESSE
    return max(0.0, min(100.0, roule + float((r.get("bonus") or {}).get(eq) or 0)))


def demarre(e: dict, duel: dict, type_: str) -> None:
    ancien = e.get("rush") or {}
    now = _now()
    ids = [q["id"] for q in duel["equipes"]]
    e["rush"] = {"on": True, "type": type_, "cle": duel["cle"], "titre": duel["titre"], "equipes": duel["equipes"],
                 "manche": int(ancien.get("manche") or 0) + 1, "t": now + DEPART * 1000, "duree": DUREE, "sprint": SPRINT,
                 "phase": "course", "bonus": {i: 0.0 for i in ids}, "fans": {}, "nFans": {i: 0 for i in ids}, "top": {},
                 "vu": {}, "tete": None, "bascule": None, "boost": None, "gagnant": None, "deja": (ancien.get("deja") or [])[-30:] + [duel["cle"]],
                 "victoires": ancien.get("victoires") or {}}


def action(e: dict, a: str, type_: str, data: dict, pays_noms: dict) -> None:
    """Depuis la régie : demarre (un type), suivante, revanche, arrete."""
    r = e.get("rush") or {}
    if a == "arrete":
        e["rush"] = {**r, "on": False}
        return
    if a == "revanche" and r.get("equipes"):
        demarre(e, {"cle": r["cle"], "titre": r["titre"], "equipes": r["equipes"]}, r.get("type") or "")
        return
    type_ = type_ if type_ in ("pays", "artistes", "classement", "sujets") else (r.get("type") or "classement")
    liste = duels(type_, data, pays_noms) or duels("sujets", data, pays_noms)
    deja = set(r.get("deja") or [])
    frais = [d for d in liste if d["cle"] not in deja] or liste   # pas deux fois le même duel tant qu'il en reste
    e["course"] = {**(e.get("course") or {}), "on": False}       # un seul jeu à la fois
    demarre(e, frais[0] if type_ in ("classement", "artistes") else random.choice(frais), type_)


def _equipe_de(r: dict, texte: str) -> str | None:
    t = _norm(texte)
    if t in [q["id"] for q in r["equipes"]]:
        return t
    for q in r["equipes"]:
        if t.startswith(q["id"] + " ") or any(c == t or (len(c) >= 3 and c in t) for c in q["cles"]):
            return q["id"]
    if any(q.get("drapeau") for q in r["equipes"]):   # drapeau emoji : 2 lettres régionales
        ri = [ord(ch) - 0x1F1E6 for ch in texte or "" if 0x1F1E6 <= ord(ch) <= 0x1F1FF]
        for i in range(0, len(ri) - 1, 2):
            code = chr(97 + ri[i]) + chr(97 + ri[i + 1])
            for q in r["equipes"]:
                if q.get("drapeau") == code:
                    return q["id"]
    return None


def _rejoint(r: dict, user: str, eq: str) -> None:
    ancien = r["fans"].get(user)
    if ancien == eq:
        return
    if ancien:
        r["nFans"][ancien] = max(0, int(r["nFans"].get(ancien) or 0) - 1)
    r["fans"][user] = eq
    r["nFans"][eq] = int(r["nFans"].get(eq) or 0) + 1


def _pousse(r: dict, eq: str, pas: float, user: str = "", nom: str = "") -> None:
    if r.get("phase") != "course" or _now() < int(r["t"]):
        return
    r["bonus"][eq] = float(r["bonus"].get(eq) or 0) + pas
    if user:
        x = r["top"].get(user) or {"nom": (nom or user)[:24], "eq": eq, "p": 0.0}
        x["p"] = round(float(x["p"]) + pas, 2); x["eq"] = eq
        r["top"][user] = x
        if len(r["top"]) > 400:
            r["top"] = dict(sorted(r["top"].items(), key=lambda kv: -kv[1]["p"])[:300])


def commentaire(e: dict, user: str, nom: str, texte: str) -> bool:
    """Un commentaire « 1 », « 2 », « 3 », un nom ou un drapeau : rejoindre (ou changer) d'équipe, plus un petit élan."""
    r = e.get("rush") or {}
    if not r.get("on") or r.get("phase") != "course":
        return False
    eq = _equipe_de(r, texte)
    if not eq:
        return False
    now = _now()
    if now - int(r["vu"].get(user) or 0) < ESPACE_MS:
        return True
    r["vu"][user] = now
    if len(r["vu"]) > 3000:
        r["vu"] = dict(sorted(r["vu"].items(), key=lambda kv: -kv[1])[:2000])
    _rejoint(r, user, eq)
    _pousse(r, eq, 0.4, user, nom)
    return True


def likes(e: dict, par: dict | None, total: int) -> None:
    r = e.get("rush") or {}
    if not r.get("on") or r.get("phase") != "course" or _now() < int(r.get("t") or 0):
        return
    sprint = _now() >= int(r["t"]) + (int(r["duree"]) - int(r["sprint"])) * 1000
    for user, n in list((par or {}).items())[:500]:
        user, n = str(user)[:30], max(0, int(n or 0))
        if not n:
            continue
        eq = r["fans"].get(user)
        if not eq:   # il tape sans avoir écrit : l'équipe qui a le moins de supporters (équilibrage par le nombre)
            eq = min(r["equipes"], key=lambda q: (int(r["nFans"].get(q["id"]) or 0), random.random()))["id"]
            _rejoint(r, user, eq)
        _pousse(r, eq, min(MAX_PAQUET, n / LIKES_PCT) * (2 if sprint else 1), user)
    _bascule(r)


def cadeau(e: dict, user: str, nom: str, diamants: int) -> None:
    r = e.get("rush") or {}
    if not r.get("on") or r.get("phase") != "course":
        return
    eq = r["fans"].get(str(user)[:30])
    if not eq:
        eq = min(r["equipes"], key=lambda q: int(r["nFans"].get(q["id"]) or 0))["id"]
        _rejoint(r, str(user)[:30], eq)
    pas = 3.0 if diamants < 10 else min(12.0, 6.0 + diamants / 50)
    _pousse(r, eq, pas, str(user)[:30], nom)
    r["boost"] = {"eq": eq, "nom": str(nom)[:24], "pas": round(pas, 1), "t": _now()}
    _bascule(r)


def _bascule(r: dict) -> None:
    now = _now()
    tete = max(r["equipes"], key=lambda q: _pos(r, q["id"], now))["id"]
    if r.get("tete") and tete != r["tete"]:
        r["bascule"] = {"eq": tete, "t": now}
    r["tete"] = tete


def tick(e: dict) -> None:
    r = e.get("rush") or {}
    if not r.get("on"):
        return
    now = _now()
    if r["phase"] == "course":
        _bascule(r)
        fini = any(_pos(r, q["id"], now) >= 100 for q in r["equipes"]) or now >= int(r["t"]) + int(r["duree"]) * 1000
        if fini:
            r["posFin"] = {q["id"]: round(_pos(r, q["id"], now), 1) for q in r["equipes"]}
            g = max(r["equipes"], key=lambda q: (r["posFin"][q["id"]], float(r["bonus"].get(q["id"]) or 0)))
            r.update(phase="fin", gagnant=g["id"], tFin=now)
            r["victoires"][g["nom"]] = int(r["victoires"].get(g["nom"]) or 0) + 1
            fans = [x for x in r["top"].values() if x["eq"] == g["id"]]
            r["meilleur"] = max(fans, key=lambda x: x["p"])["nom"] if fans else None
    elif r["phase"] == "fin" and now > int(r.get("tFin") or 0) + PAUSE * 1000:
        r["phase"] = "attente"   # la régie choisit : manche suivante, revanche ou arrêt


def public(r: dict) -> dict:
    """Ce que l'écran affiche (jamais la liste des joueurs)."""
    if not isinstance(r, dict) or not r:
        return r
    now = _now()
    top = sorted(r.get("top", {}).values(), key=lambda x: -x["p"])[:3]
    return {**{k: v for k, v in r.items() if k not in ("fans", "vu", "top", "deja")}, "top": top,
            "pos": {q["id"]: round(_pos(r, q["id"], now), 2) for q in r.get("equipes") or []}, "srv": now,
            "vitesse": VITESSE}
