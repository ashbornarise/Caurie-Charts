"""Monthly Show (v2) : le conducteur de l'émission, calculé à partir des vrais classements.

Chaque classement est une scène : l'ambiance (pochettes floutées, lit musical sous licence, aucun nom), l'enjeu (le chiffre qui
raconte la course), #5 → #2 avec le clip officiel une minute chacun, le silence, puis le N°1 (clip et distinction).
Le format de la scène vient des données (Photo-finish, Le règne, Le couronnement, Blind test, Les légendes) ; l'ordre de
passage suit la logique de l'Eurovision : les victoires nettes d'abord, les courses serrées à la fin, puis le BIG 5.

programme() renvoie la suite des segments (type, début et durée en secondes, données, voix off). Le lecteur
(public/assets/js/show-player.js) le joue dans le navigateur, calé sur l'horloge : tous les spectateurs voient le même moment.
Données : le classement mensuel publié du mois révélé (conf show.key) s'il existe, sinon le classement en direct.
Musique : uniquement les clips officiels YouTube, joués en entier dans le lecteur intégré du site (visible, rien par-dessus) :
à l'appel de chaque nom, et en ambiance entre les scènes (titres classés 6 à 12 de chaque pays, pour ne rien dévoiler).
Plus aucun extrait Deezer (décision du fondateur, 10 oct. 2026) ; fonds Mixkit (public/assets/show/sons) en secours.
"""
from core import conf, db, repos
from core.helpers import country_name
from core.services import live_chart
from core.services.distinctions import month_label

SCENES = 6
CLIP = 60          # durée d'un clip à l'appel d'un nom
D = {"ouverture": 4, "ambiance": 30, "enjeu": 18, "duel": 30, "silence": 6, "n1_revel": 6, "distinction": 12, "generique": 30,
     "tubes": 20, "sondage": 15, "supporters": 45, "flash": 10, "tableau": 15, "prix": 18, "big5": 10, "cloture": 30}
LEGENDES = {"Oumou Sangaré", "Ali Farka Toure", "Cesária Evora", "Mory Kanté", "Salif Keita", "Youssou N'Dour", "Fela Kuti",
            "Angélique Kidjo", "Toumani Diabaté", "Tinariwen", "Amadou & Mariam", "Ismaël Lô", "Baaba Maal"}


# ---------------------------------------------------------------- données
def _media(track_id):
    """Clip officiel (YouTube, un vrai clip de préférence) et identifiant Deezer d'un titre."""
    yt = db.value("""SELECT external_id FROM track_platform_ids WHERE track_id = ? AND platform = 'youtube'
                     ORDER BY CASE kind WHEN 'clip' THEN 0 WHEN 'audio' THEN 1 WHEN 'lyrics' THEN 2 ELSE 3 END, published_at NULLS LAST
                     LIMIT 1""", [track_id])
    dz = db.value("SELECT external_id FROM track_platform_ids WHERE track_id = ? AND platform = 'deezer' LIMIT 1", [track_id])
    return yt, dz


def _ligne(r):
    yt, dz = _media(r["track_id"]) if r.get("track_id") else (None, None)
    return {"titre": r.get("title") or r.get("top_title"), "artiste": r["artist_name"], "photo": r.get("artist_image") or r.get("cover_url"),
            "pochette": r.get("cover_url") or r.get("artist_image"), "points": round(float(r.get("points") or 0), 1),
            "sources": len(r.get("seen") or []), "youtube": yt, "deezer": dz}


def _top_direct(cid, mode="prime", n=5):
    rows = [r for r in live_chart.build(cid, None, 20, mode, 20, "latest")["rows"] if r.get("status") == "active"]
    return [_ligne(r) for r in rows[:n]]


def _top_mensuel(cid, key):
    run = db.one("""SELECT r.id FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
                    WHERE ct.code = ? AND r.country_id IS NOT DISTINCT FROM ?::smallint AND r.period_type = 'month'
                      AND r.period_key = ? AND r.status = 'published'""", ["prime" if cid else "prime-wa", cid, key])
    if not run:
        return None
    out = []
    for e in repos.entries(int(run["id"]), 5):
        yt, dz = _media(e["track_id"])
        out.append({"titre": e["title"], "artiste": e["artist_name"], "photo": e.get("image_url") or e.get("cover_url"),
                    "pochette": e.get("cover_url"), "points": float(e.get("score") or 0), "sources": 0, "youtube": yt, "deezer": dz})
    return out


def _top(cid, key):
    return _top_mensuel(cid, key) or _top_direct(cid)


def _ecart(top):
    return round((top[0]["points"] - top[1]["points"]) / max(1.0, top[0]["points"]) * 100) if len(top) > 1 else 100


def _format(top):
    """Le format de la scène, choisi par la situation réelle du classement."""
    if top[0]["artiste"] == top[1]["artiste"]:
        return "regne"
    if top[0]["artiste"] in LEGENDES or top[1]["artiste"] in LEGENDES:
        return "legendes"
    e = _ecart(top)
    if e <= 4:
        return "photo_finish"
    if e >= 15:
        return "couronnement"
    return "blind_test"


ENJEU = {
    "photo_finish": "PHOTO-FINISH", "regne": "LE RÈGNE", "couronnement": "LE COURONNEMENT", "blind_test": "BLIND TEST", "legendes": "LES LÉGENDES",
}


def _enjeu(fmt, p):
    top = p["top"]
    a1, a2, e = top[0]["artiste"], top[1]["artiste"], _ecart(top)
    if fmt == "photo_finish":
        return f"{e} % d'écart", f"Le N°1 et le N°2 sont au coude-à-coude. Qui l'emporte en {p['nom']} ?"
    if fmt == "regne":
        n = sum(1 for x in top if x["artiste"] == a1)
        return f"{n} titres sur 5", f"Un seul artiste occupe {n} places du Top 5. Lequel de ses titres sera N°1 ?"
    if fmt == "couronnement":
        return f"{e} % d'avance", f"Cette fois, le N°1 est loin devant. Place au couronnement."
    if fmt == "legendes":
        return "Les classiques", f"En {p['nom']}, les légendes résistent dans les écoutes d'aujourd'hui."
    return "À l'oreille", "Écoutez bien : reconnaissez-vous les titres avant les noms ?"


# ---------------------------------------------------------------- conducteur
def programme() -> dict:
    key = conf.get("show.key")
    mois = month_label(key)
    pays = []
    for c in repos.countries():
        top = _top(c["id"], key)
        if len(top) >= 5:
            pays.append({"code": c["code"], "nom": country_name(c["code"]), "top": top})
    bientot = [country_name(c["code"]) for c in repos.countries() if c["code"] not in {p["code"] for p in pays}]
    for p in pays:
        p["format"], p["ecart"] = _format(p["top"]), _ecart(p["top"])

    # Choix des scènes : seulement les pays dont on a les clips (au moins 4 sur 5, dont le N°1) ; un pays par format
    # d'abord (variété), puis les courses les plus serrées, jamais deux fois le même format (le surplus passe en Blind test,
    # sinon au Flash)
    jouables = [p for p in pays if p["top"][0]["youtube"] and sum(1 for e in p["top"] if e["youtube"]) >= 4]
    choix, pris = [], set()
    for fmt in ("photo_finish", "regne", "couronnement", "blind_test", "legendes"):
        cand = sorted([p for p in jouables if p["format"] == fmt], key=lambda p: p["ecart"])
        if cand:
            choix.append(cand[0])
            pris.add(fmt)
    for p in sorted(jouables, key=lambda p: p["ecart"]):
        if len(choix) >= SCENES:
            break
        if p in choix:
            continue
        if p["format"] in pris and "blind_test" not in pris and p["format"] != "regne":
            p["format"] = "blind_test"
        if p["format"] not in pris:
            choix.append(p)
            pris.add(p["format"])
    flash = [p for p in pays if p not in choix]
    # Ordre de passage (Eurovision) : écart décroissant, la course la plus serrée juste avant le BIG 5
    choix.sort(key=lambda p: -p["ecart"])

    big5 = _top(None, key)
    tubes = _top_direct(None, "buzz", 3)
    prix = []
    for mode, nom, expl in (("buzz", "BIGGEST CLIMBER", "la plus forte progression du mois"),
                            ("fresh", "FRESH OF THE MONTH", "le meilleur titre sorti depuis moins de huit semaines"),
                            ("icon", "ARTIST OF THE MONTH", "l'artiste qui cumule le plus de points sur tous ses titres"),
                            ("legend", "LEGEND", "le titre qui tient le classement depuis le plus longtemps")):
        t = _top_direct(None, mode, 1)
        if t:
            prix.append({"nom": nom, "explication": expl, **t[0]})

    # Ambiance : de vrais titres de chaque pays (classés 6 à 12, pour ne rien dévoiler), « bouger » ou « penser » selon le moment
    amb = {}
    for c in repos.countries():
        if c["code"] in {x["code"] for x in pays}:
            rows = [r for r in live_chart.build(c["id"], None, 20, "prime", 20, "latest")["rows"] if r.get("status") == "active"][5:12]
            amb[c["code"]] = [{**_ligne(r), "pays": country_name(c["code"]), "code": c["code"]} for r in rows]
    for v in amb.values():
        v[:] = [e for e in v if e.get("youtube")]
    # playlist mêlée pays par pays ; « penser » = tempo lent connu, sinon le reste sert à « bouger »
    melange, i = [], 0
    while any(i < len(v) for v in amb.values()):
        melange += [v[i] for v in amb.values() if i < len(v)]
        i += 1
    penser = melange[1::2] or melange
    bouger = melange[0::2] or melange
    curseurs = {"bouger": 0, "penser": 0}

    def fond(humeur, code=None):
        """Le prochain titre d'ambiance : du pays demandé si possible, sinon de la playlist de l'humeur."""
        if code and amb.get(code):
            v = amb[code]
            e = v[curseurs.setdefault(code, 0) % len(v)]
            curseurs[code] += 1
        else:
            liste = bouger if humeur == "bouger" else penser
            if not liste:
                return None
            e = liste[curseurs[humeur] % len(liste)]
            curseurs[humeur] += 1
        return {"youtube": e["youtube"], "artiste": e["artiste"], "titre": e["titre"], "pays": e["pays"]}
    seg, t = [], 0

    HUMEUR = {"generique": "bouger", "sondage": "bouger", "supporters": "penser", "bientot": "penser", "tableau": "penser",
              "big5": "bouger", "cloture": "bouger", "enjeu": "penser", "duel": None}

    def add(kind, duree, voix="", **data):
        nonlocal t
        item = {"type": kind, "t": t, "d": duree, "voix": voix, **data}
        if kind in HUMEUR and HUMEUR[kind]:
            item["fond"] = fond(HUMEUR[kind], data.get("code") if kind == "enjeu" else None)
        seg.append(item)
        t += duree

    def scene(p, numero, ouverture=False):
        top, fmt = p["top"], p["format"]
        add("ambiance", D["ambiance"], "" if ouverture else f"Scène {numero}. Écoutez.", code=p["code"], nom=p["nom"], numero=numero,
            format=fmt, extraits=[{"pochette": e["pochette"]} for e in (top if fmt == "blind_test" else top[:4])], fond=fond("bouger", p["code"]))
        titre, texte = _enjeu(fmt, p)
        add("enjeu", D["enjeu"], f"{p['nom']}. {texte}", code=p["code"], nom=p["nom"], format=fmt, label=ENJEU[fmt], chiffre=titre, texte=texte)
        for rang in (5, 4, 3, 2):
            e = top[rang - 1]
            add("clip", CLIP, f"Numéro {rang} : {e['artiste']}.", code=p["code"], nom=p["nom"], rang=rang, **e)
        if fmt == "photo_finish":
            add("duel", D["duel"], "Il reste deux noms. Votez maintenant en commentaire.", code=p["code"], nom=p["nom"],
                duel=[top[0], top[1]], ecart=p["ecart"])
        add("silence", D["silence"], "", code=p["code"], nom=p["nom"])
        e = top[0]
        add("numero1", D["n1_revel"] + CLIP + D["distinction"], f"Le numéro un en {p['nom']} : {e['artiste']}, avec {e['titre']} !",
            code=p["code"], nom=p["nom"], mois=mois, revel=D["n1_revel"], clip=CLIP, **e)

    # ouverture à froid : on entre directement dans la première scène
    scene(choix[0], 1, ouverture=True)
    add("generique", D["generique"], f"Bonsoir l'Afrique de l'Ouest. Ce soir, {len(pays)} pays, un BIG 5, et les numéros un de {mois.lower()}. "
        "Ici, c'est la musique qui parle.", mois=mois, pays=len(pays))
    for i, p in enumerate(choix[1:], start=2):
        scene(p, i)
        if i == 3 and tubes:
            add("tubes", D["tubes"] * len(tubes), "Les tubes de demain : les titres qui montent le plus ce mois-ci.", titres=tubes, par=D["tubes"])
            add("sondage", D["sondage"], "Dans un instant, la scène suivante. Dites-nous en commentaire quel pays vous attendez.")
            add("supporters", D["supporters"], "Merci à celles et ceux qui soutiennent le direct. Envoyez un cadeau : votre nom s'affiche ici.")
        if i == len(choix) - 1:
            for f in flash:
                add("flash", D["flash"], f"{f['nom']} : {f['top'][0]['artiste']}.", code=f["code"], nom=f["nom"], **f["top"][0])
            if bientot:
                add("bientot", 12, "Bientôt, de nouveaux pays dans le classement.", pays=bientot)
            add("tableau", D["tableau"], "Le tableau de la soirée.")
    for x in prix:
        add("prix", D["prix"], f"{x['nom'].capitalize()} : {x['artiste']}. C'est {x['explication']}.", **x)
    add("big5", D["big5"], "Et maintenant, le BIG 5 de toute l'Afrique de l'Ouest.", mois=mois)
    for rang in (5, 4, 3, 2):
        e = big5[rang - 1]
        add("clip", CLIP, f"Numéro {rang} en Afrique de l'Ouest : {e['artiste']}.", code="WA", nom="Afrique de l'Ouest", rang=rang, big5=True, **e)
    add("silence", D["silence"] + 2, "", code="WA", nom="Afrique de l'Ouest")
    e = big5[0]
    add("numero1", D["n1_revel"] + CLIP + D["distinction"], f"Le numéro un de l'Afrique de l'Ouest en {mois.lower()} : {e['artiste']} !",
        code="WA", nom="Afrique de l'Ouest", mois=mois, big5=True, revel=D["n1_revel"], clip=CLIP, **e)
    add("cloture", D["cloture"], "Merci d'avoir suivi le Cauri Charts Monthly Show. Tous les classements et les distinctions sont sur "
        "cauricharts.com. Rendez-vous le mois prochain.", mois=mois)

    return {"key": key, "mois": mois, "duree": t, "segments": seg, "start_utc": conf.get("show.start_utc"),
            "scenes": [{"code": p["code"], "nom": p["nom"], "format": p["format"], "ecart": p["ecart"]} for p in choix],
            "n1": [{"code": p["code"], "nom": p["nom"], "artiste": p["top"][0]["artiste"]} for p in choix + flash], "bientot": bientot,
            "avant": [fond("bouger") for _ in range(6)]}
