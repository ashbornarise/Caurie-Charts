"""Idées du jour pour Cauri Studio : formats « souvenirs et records » avec les vrais clips officiels.

Le fondateur veut « ressortir l'euphorie, les sentiments d'avant » : le studio propose chaque jour des posts tout
prêts (sujet, vrais chiffres, accroche, liens des clips officiels). Rien n'est téléchargé ici : c'est le fondateur qui
lance la fabrication dans le studio (case des droits), puis valide l'envoi.

Catégories (rotation quotidienne — 8 à 12 idées/jour) :
  il_y_a          : clip sorti cette semaine il y a 5 / 10 ans ;
  top_annee       : les 5 clips les plus vus sortis une année (compilation) ;
  top_pays        : les 5 clips les plus vus d'un pays de tous les temps (compilation) ;
  clip_annee      : le clip qui a marqué une année (simple) ;
  top_pays_annee  : les 5 clips les plus vus d'un pays pour une année (compilation) ;
  artiste_jour    : un artiste + ses 3 meilleurs clips (compilation) ;
  cap_vues        : clip ayant dépassé un cap (10M, 50M, 100M…) (simple) ;
  premier_clip    : le tout premier clip officiel d'un artiste célèbre (simple) ;
  ce_mois         : clip le plus vu sorti ce mois-ci dans l'histoire (simple) ;
  duel            : deux artistes du même pays, leurs N°1 comparés (compilation 2 clips) ;
  generation      : un artiste d'hier vs un artiste d'aujourd'hui du même pays (compilation 2 clips) ;
  pepite          : clip peu connu (pas le N°1) d'un artiste célèbre (simple).
Données : clips officiels YouTube relevés par Cauri (track_platform_ids) et leurs dernières vues (snapshots).
Seulement nos artistes suivis : les textes disent « selon nos relevés » quand c'est un classement.
"""
from datetime import date

from core import db
from core.helpers import country_name

ANNEES = list(range(2014, 2024))
ANNEES_LARGE = list(range(2008, 2026))
PAYS = ["NG", "GH", "TG", "CI", "SN", "BJ", "ML", "BF", "GN", "CV"]


def creer_table() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS studio_propositions (
        cle TEXT PRIMARY KEY, jour DATE NOT NULL, job_id BIGINT, cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


def _clips(condition: str, params: list, limite: int = 25) -> list[dict]:
    lignes = db.all(f"""SELECT a.id AS artist_id, a.name AS artiste, t.id AS track_id, t.title AS titre, tpi.external_id AS video_id,
                             tpi.published_at AS sortie, c.code AS pays,
                             (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY s.captured_on DESC LIMIT 1) AS vues
                      FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id
                      LEFT JOIN countries c ON c.id = a.submission_country_id
                      WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active'
                        AND tpi.external_id IS NOT NULL AND {condition}
                      ORDER BY vues DESC NULLS LAST LIMIT {int(limite)}""", params)
    for r in lignes:
        r["titre"] = propre_titre(r["titre"] or "")
    return lignes


def _un_par_artiste(clips: list, n: int) -> list:
    vus, out = set(), []
    for c in clips:
        if c["artist_id"] in vus or not c.get("vues"):
            continue
        vus.add(c["artist_id"]); out.append(c)
        if len(out) == n:
            break
    return out


def vues(n) -> str:
    n = float(n or 0)
    if n >= 1e9:
        v = f"{n / 1e9:.1f}".replace(".0", "").replace(".", ",")
        return f"{v} milliard" + ("s" if n >= 2e9 else "")
    if n >= 1e6:
        v = f"{n / 1e6:.0f}" if n >= 1e7 else f"{n / 1e6:.1f}".replace(".0", "").replace(".", ",")
        return f"{v} millions" if n >= 2e6 else f"{v} million"
    return f"{int(n):,}".replace(",", " ")


def propre_titre(t: str) -> str:
    import re
    t = re.sub(r"\s*[\(\[][^\)\]]*(official|officiel|officielle|video|vidéo|clip|audio|lyrics?|visuali[sz]er|hd|4k)[^\)\]]*[\)\]]", "", t, flags=re.I)
    t = re.sub(r"\s+[-–|]\s*(official|version officielle|clip officiel|vid[ée]o officielle).*$", "", t, flags=re.I)
    return t.strip(" -–|") or t


def _lien(c: dict) -> str:
    return f"https://www.youtube.com/watch?v={c['video_id']}"


def _element(c: dict, rang: int | None = None) -> dict:
    return {"lien": _lien(c), "video_id": c["video_id"], "rang": rang, "titre": c["titre"], "artiste": c["artiste"],
            "vues": int(c["vues"] or 0), "annee": str(c["sortie"])[:4] if c.get("sortie") else "",
            "vignette": f"https://i.ytimg.com/vi/{c['video_id']}/mqdefault.jpg"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ CATÉGORIES EXISTANTES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def il_y_a(jour: date, ans: int, seuil: int) -> dict | None:
    cond = ("tpi.published_at BETWEEN (?::date - (? || ' years')::interval - INTERVAL '6 days') "
            "AND (?::date - (? || ' years')::interval + INTERVAL '6 days')")
    clips = [c for c in _clips(cond, [jour.isoformat(), ans, jour.isoformat(), ans], 5) if (c["vues"] or 0) >= seuil]
    if not clips:
        return None
    c = clips[0]
    return {"cle": f"il-y-a-{ans}:{c['track_id']}", "format": "il_y_a", "mode": "simple",
            "titre": f"Il y a {ans} ans : « {c['titre']} » de {c['artiste']}",
            "sous_titre": f"Sorti le {c['sortie']:%d/%m/%Y} · {vues(c['vues'])} de vues aujourd'hui" if hasattr(c["sortie"], "strftime")
                          else f"{vues(c['vues'])} de vues aujourd'hui",
            "etiquette": f"IL Y A {ans} ANS", "accroche": f"Il y a {ans} ans, {c['artiste']} sortait « {c['titre']} »",
            "artiste": c["artiste"], "credit": f"clip officiel de {c['artiste']} (YouTube)",
            "legende_fr": (f"Il y a {ans} ans, {c['artiste']} sortait « {c['titre']} ». Aujourd'hui, le clip compte "
                           f"{vues(c['vues'])} de vues sur YouTube.\n\nVous vous souvenez où vous étiez quand ce son tournait partout ? "
                           "Dites-le en commentaire."),
            "elements": [_element(c)]}


def top_annee(annee: int) -> dict | None:
    top = _un_par_artiste(_clips("EXTRACT(YEAR FROM tpi.published_at) = ?", [annee], 40), 5)
    if len(top) < 5:
        return None
    top = list(reversed(top))
    lignes = "\n".join(f"N°{5 - k} · « {c['titre']} », {c['artiste']} ({vues(c['vues'])} de vues)" for k, c in enumerate(top))
    return {"cle": f"top-annee:{annee}", "format": "top_annee", "mode": "compilation",
            "titre": f"Top 5 des clips les plus vus sortis en {annee}",
            "sous_titre": " · ".join(c["artiste"] for c in reversed(top)),
            "etiquette": f"TOP 5 · {annee}", "accroche": f"Les clips les plus vus de {annee}",
            "legende_fr": (f"Retour en {annee} : les 5 clips ouest-africains les plus vus sortis cette année-là, selon nos relevés "
                           f"(vues YouTube d'aujourd'hui).\n\n{lignes}\n\nLequel tournait en boucle chez vous ?"),
            "elements": [_element(c, 5 - k) for k, c in enumerate(top)]}


def top_pays(code: str) -> dict | None:
    top = _un_par_artiste(_clips("c.code = ?", [code], 40), 5)
    if len(top) < 5:
        return None
    top = list(reversed(top))
    pays = country_name(code)
    lignes = "\n".join(f"N°{5 - k} · « {c['titre']} », {c['artiste']} ({vues(c['vues'])} de vues)" for k, c in enumerate(top))
    return {"cle": f"top-pays:{code}", "format": "top_pays", "mode": "compilation",
            "titre": f"Les 5 clips les plus vus de tous les temps · {pays}",
            "sous_titre": " · ".join(c["artiste"] for c in reversed(top)),
            "etiquette": f"RECORD · {pays.upper()}", "accroche": f"Les clips les plus vus de l'histoire · {pays}",
            "legende_fr": (f"{pays} : les 5 clips les plus vus de tous les temps, un par artiste, selon nos relevés.\n\n{lignes}\n\n"
                           "Il en manque un ? Dites-le en commentaire."),
            "elements": [_element(c, 5 - k) for k, c in enumerate(top)]}


def clip_annee(annee: int) -> dict | None:
    top = _un_par_artiste(_clips("EXTRACT(YEAR FROM tpi.published_at) = ?", [annee], 10), 1)
    if not top:
        return None
    c = top[0]
    return {"cle": f"clip-annee:{annee}:{c['track_id']}", "format": "clip_annee", "mode": "simple",
            "titre": f"Le clip qui a marqué {annee} : « {c['titre']} »",
            "sous_titre": f"{c['artiste']} · {vues(c['vues'])} de vues",
            "etiquette": f"LE CLIP DE {annee}", "accroche": f"En {annee}, tout le monde dansait sur « {c['titre']} »",
            "artiste": c["artiste"], "credit": f"clip officiel de {c['artiste']} (YouTube)",
            "legende_fr": (f"{annee}. « {c['titre']} » de {c['artiste']} : le clip ouest-africain le plus vu sorti cette année-là "
                           f"selon nos relevés, {vues(c['vues'])} de vues aujourd'hui.\n\nCe son vous ramène où ?"),
            "elements": [_element(c)]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ NOUVELLES CATÉGORIES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def top_pays_annee(code: str, annee: int) -> dict | None:
    """Top 5 clips d'un pays pour une année donnée."""
    top = _un_par_artiste(_clips("c.code = ? AND EXTRACT(YEAR FROM tpi.published_at) = ?", [code, annee], 30), 5)
    if len(top) < 3:
        return None
    top = list(reversed(top))
    n = len(top)
    pays = country_name(code)
    lignes = "\n".join(f"N°{n - k} · « {c['titre']} », {c['artiste']} ({vues(c['vues'])} de vues)" for k, c in enumerate(top))
    return {"cle": f"top-pays-annee:{code}:{annee}", "format": "top_pays_annee", "mode": "compilation",
            "titre": f"Top clips {pays} en {annee}",
            "sous_titre": " · ".join(c["artiste"] for c in reversed(top)),
            "etiquette": f"{pays.upper()} · {annee}", "accroche": f"Les clips les plus vus du {pays} en {annee}",
            "legende_fr": (f"{pays}, {annee} : les clips les plus vus sortis cette année-là, selon nos relevés.\n\n{lignes}\n\n"
                           f"C'était quoi votre son préféré du {pays} en {annee} ?"),
            "elements": [_element(c, n - k) for k, c in enumerate(top)]}


def artiste_jour(jour: date) -> dict | None:
    """Un artiste et ses 3 meilleurs clips — tourne chaque jour parmi les artistes avec le plus de clips."""
    artistes = db.all(
        "SELECT a.id, a.name, c.code AS pays, COUNT(tpi.id) AS nb "
        "FROM artists a JOIN tracks t ON t.artist_id = a.id JOIN track_platform_ids tpi ON tpi.track_id = t.id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active' "
        "GROUP BY a.id, a.name, c.code HAVING COUNT(tpi.id) >= 3 ORDER BY nb DESC")
    if not artistes:
        return None
    a = artistes[jour.toordinal() % len(artistes)]
    top = _clips("a.id = ?", [a["id"]], 3)
    if len(top) < 3:
        return None
    top = list(reversed(top))
    pays = country_name(a["pays"]) if a["pays"] else ""
    total_vues = sum(int(c["vues"] or 0) for c in top)
    return {"cle": f"artiste-jour:{a['id']}:{jour.isocalendar()[1]}", "format": "artiste_jour", "mode": "compilation",
            "titre": f"Artiste du jour : {a['name']}",
            "sous_titre": f"{pays} · {vues(total_vues)} de vues cumulées",
            "etiquette": f"ARTISTE DU JOUR", "accroche": f"{a['name']}, ses 3 clips les plus vus",
            "legende_fr": (f"Aujourd'hui on met à l'honneur {a['name']}"
                           + (f" ({pays})" if pays else "") +
                           f" : ses 3 clips les plus vus selon nos relevés, {vues(total_vues)} de vues cumulées.\n\n"
                           f"Quel est votre clip préféré de {a['name']} ? Dites-le en commentaire."),
            "elements": [_element(c, 3 - k) for k, c in enumerate(top)]}


def cap_vues(jour: date) -> dict | None:
    """Clip ayant dépassé un cap remarquable (100M, 50M, 10M)."""
    for seuil, label_fr, label_en in [(100_000_000, "100 millions", "100M"), (50_000_000, "50 millions", "50M"),
                                       (10_000_000, "10 millions", "10M")]:
        clips = _clips("1=1", [], 200)
        franchis = [c for c in clips if seuil <= (c["vues"] or 0) < seuil * 2]
        if not franchis:
            continue
        c = franchis[jour.toordinal() % len(franchis)]
        return {"cle": f"cap-vues:{c['track_id']}:{seuil}", "format": "cap_vues", "mode": "simple",
                "titre": f"Cap des {label_fr} ! « {c['titre']} » de {c['artiste']}",
                "sous_titre": f"{vues(c['vues'])} de vues",
                "etiquette": f"CAP {label_en} 🔥", "accroche": f"« {c['titre']} » a dépassé les {label_fr} de vues !",
                "artiste": c["artiste"], "credit": f"clip officiel de {c['artiste']} (YouTube)",
                "legende_fr": (f"« {c['titre']} » de {c['artiste']} a franchi le cap des {label_fr} de vues sur YouTube ! "
                               f"Le clip en compte {vues(c['vues'])} aujourd'hui.\n\n"
                               "Vous faites partie de ces vues ? Dites-le en commentaire."),
                "elements": [_element(c)]}
    return None


def premier_clip(jour: date) -> dict | None:
    """Le tout premier clip officiel d'un artiste aujourd'hui célèbre."""
    artistes = db.all(
        "SELECT a.id, a.name, c.code AS pays "
        "FROM artists a JOIN tracks t ON t.artist_id = a.id JOIN track_platform_ids tpi ON tpi.track_id = t.id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active' "
        "AND tpi.published_at IS NOT NULL "
        "GROUP BY a.id, a.name, c.code HAVING COUNT(tpi.id) >= 5 "
        "ORDER BY a.name", [])
    if not artistes:
        return None
    a = artistes[jour.toordinal() % len(artistes)]
    clip = db.one(
        "SELECT a.name AS artiste, t.title AS titre, tpi.external_id AS video_id, tpi.published_at AS sortie, "
        "a.id AS artist_id, c.code AS pays, "
        "(SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY s.captured_on DESC LIMIT 1) AS vues "
        "FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE a.id = ? AND tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND tpi.published_at IS NOT NULL "
        "ORDER BY tpi.published_at ASC LIMIT 1", [a["id"]])
    if not clip or not clip.get("video_id"):
        return None
    clip["titre"] = propre_titre(clip["titre"] or "")
    annee = str(clip["sortie"])[:4] if clip.get("sortie") else "?"
    return {"cle": f"premier-clip:{a['id']}", "format": "premier_clip", "mode": "simple",
            "titre": f"Le premier clip de {a['name']} ({annee})",
            "sous_titre": f"« {clip['titre']} » · {vues(clip['vues'])} de vues aujourd'hui" if clip.get("vues") else f"« {clip['titre']} »",
            "etiquette": "PREMIER CLIP", "accroche": f"Avant la gloire : le tout premier clip de {a['name']}",
            "artiste": a["name"], "credit": f"clip officiel de {a['name']} (YouTube)",
            "legende_fr": (f"Tout le monde connaît {a['name']} aujourd'hui. Mais vous souvenez-vous de son tout premier clip ? "
                           f"« {clip['titre']} »"
                           + (f", sorti en {annee}" if annee != "?" else "") +
                           (f", compte {vues(clip['vues'])} de vues" if clip.get("vues") else "") +
                           " sur YouTube.\n\nVous connaissiez ce clip ? Dites-le en commentaire."),
            "elements": [_element(clip)]}


def ce_mois(jour: date) -> dict | None:
    """Le clip le plus vu sorti le même mois dans l'histoire."""
    mois = jour.month
    noms_mois = {1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
                 7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"}
    clips = _un_par_artiste(_clips(
        "EXTRACT(MONTH FROM tpi.published_at) = ? AND EXTRACT(YEAR FROM tpi.published_at) < ?",
        [mois, jour.year], 20), 5)
    if not clips:
        return None
    c = clips[jour.day % len(clips)]
    annee = str(c["sortie"])[:4] if c.get("sortie") else "?"
    return {"cle": f"ce-mois:{mois}:{c['track_id']}", "format": "ce_mois", "mode": "simple",
            "titre": f"Un {noms_mois[mois]} inoubliable : « {c['titre']} » ({annee})",
            "sous_titre": f"{c['artiste']} · {vues(c['vues'])} de vues",
            "etiquette": f"{noms_mois[mois].upper()} · FLASHBACK",
            "accroche": f"En {noms_mois[mois]} {annee}, {c['artiste']} sortait « {c['titre']} »",
            "artiste": c["artiste"], "credit": f"clip officiel de {c['artiste']} (YouTube)",
            "legende_fr": (f"Comme chaque {noms_mois[mois]}, on replonge dans les classiques. "
                           f"En {noms_mois[mois]} {annee}, {c['artiste']} sortait « {c['titre']} ». "
                           f"Le clip compte {vues(c['vues'])} de vues aujourd'hui.\n\n"
                           f"C'était votre son de l'époque ?"),
            "elements": [_element(c)]}


def duel(jour: date) -> dict | None:
    """Deux artistes du même pays, leurs N°1 comparés."""
    code = PAYS[jour.toordinal() % len(PAYS)]
    top = _un_par_artiste(_clips("c.code = ?", [code], 30), 10)
    if len(top) < 2:
        return None
    idx = (jour.toordinal() // len(PAYS)) % (len(top) - 1)
    a, b = top[idx], top[(idx + 1) % len(top)]
    if a["artist_id"] == b["artist_id"]:
        return None
    pays = country_name(code)
    gagnant = a if (a["vues"] or 0) >= (b["vues"] or 0) else b
    return {"cle": f"duel:{a['artist_id']}:{b['artist_id']}", "format": "duel", "mode": "compilation",
            "titre": f"{a['artiste']} vs {b['artiste']} · {pays}",
            "sous_titre": f"Qui a le clip le plus vu ?",
            "etiquette": f"DUEL · {pays.upper()}", "accroche": f"{a['artiste']} ou {b['artiste']} : qui domine le {pays} ?",
            "legende_fr": (f"DUEL {pays.upper()} : {a['artiste']} vs {b['artiste']} !\n\n"
                           f"« {a['titre']} » de {a['artiste']} : {vues(a['vues'])} de vues\n"
                           f"« {b['titre']} » de {b['artiste']} : {vues(b['vues'])} de vues\n\n"
                           f"Avantage {gagnant['artiste']} ! Mais les commentaires vont trancher…\n"
                           "Team A ou Team B ? Dites-le en commentaire."),
            "elements": [_element(a, 1), _element(b, 2)]}


def generation(jour: date) -> dict | None:
    """Un artiste d'avant 2018 vs un artiste d'après 2020 du même pays."""
    code = PAYS[(jour.toordinal() + 3) % len(PAYS)]
    anciens = _un_par_artiste(_clips("c.code = ? AND EXTRACT(YEAR FROM tpi.published_at) <= 2018", [code], 20), 5)
    nouveaux = _un_par_artiste(_clips("c.code = ? AND EXTRACT(YEAR FROM tpi.published_at) >= 2020", [code], 20), 5)
    if not anciens or not nouveaux:
        return None
    a = anciens[jour.day % len(anciens)]
    b = nouveaux[jour.day % len(nouveaux)]
    if a["artist_id"] == b["artist_id"]:
        return None
    pays = country_name(code)
    annee_a = str(a["sortie"])[:4] if a.get("sortie") else "avant"
    annee_b = str(b["sortie"])[:4] if b.get("sortie") else "maintenant"
    return {"cle": f"generation:{code}:{a['artist_id']}:{b['artist_id']}", "format": "generation", "mode": "compilation",
            "titre": f"Générations {pays} : {a['artiste']} ({annee_a}) vs {b['artiste']} ({annee_b})",
            "sous_titre": f"Hier et aujourd'hui",
            "etiquette": f"GÉNÉRATIONS · {pays.upper()}", "accroche": f"{a['artiste']} puis {b['artiste']} : le {pays} évolue",
            "legende_fr": (f"Le {pays} d'hier et d'aujourd'hui :\n\n"
                           f"Hier : « {a['titre']} » de {a['artiste']} ({annee_a}) — {vues(a['vues'])} de vues\n"
                           f"Aujourd'hui : « {b['titre']} » de {b['artiste']} ({annee_b}) — {vues(b['vues'])} de vues\n\n"
                           f"Le son change, le talent reste. Quelle génération vous préférez ?"),
            "elements": [_element(a, 1), _element(b, 2)]}


def pepite(jour: date) -> dict | None:
    """Clip peu connu (pas le N°1) d'un artiste célèbre — la pépite cachée."""
    artistes = db.all(
        "SELECT a.id, a.name, c.code AS pays "
        "FROM artists a JOIN tracks t ON t.artist_id = a.id JOIN track_platform_ids tpi ON tpi.track_id = t.id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active' "
        "GROUP BY a.id, a.name, c.code HAVING COUNT(tpi.id) >= 8 ORDER BY a.name", [])
    if not artistes:
        return None
    a = artistes[jour.toordinal() % len(artistes)]
    clips = _clips("a.id = ?", [a["id"]], 20)
    if len(clips) < 4:
        return None
    # pas le N°1 ni le N°2, mais un clip du milieu
    idx = 2 + (jour.day % (len(clips) - 2)) if len(clips) > 2 else 0
    c = clips[min(idx, len(clips) - 1)]
    return {"cle": f"pepite:{c['track_id']}", "format": "pepite", "mode": "simple",
            "titre": f"Pépite cachée : « {c['titre']} » de {a['name']}",
            "sous_titre": f"{vues(c['vues'])} de vues",
            "etiquette": "PÉPITE CACHÉE", "accroche": f"Vous connaissez {a['name']}, mais connaissez-vous « {c['titre']} » ?",
            "artiste": a["name"], "credit": f"clip officiel de {a['name']} (YouTube)",
            "legende_fr": (f"Tout le monde connaît les tubes de {a['name']}. Mais ce clip-là, "
                           f"« {c['titre']} », mérite qu'on s'y arrête : {vues(c['vues'])} de vues sur YouTube.\n\n"
                           "Vous connaissiez ? Si oui, vous êtes un vrai fan."),
            "elements": [_element(c)]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━ CATÉGORIES VIRALES (montages, compilations, moments forts) ━━━━━━━━━━━━━━━━━━━━━━━━━

def retro_annee(annee: int) -> dict | None:
    """Rétrospective : les 10 clips qui ont marqué une année (compilation longue)."""
    top = _un_par_artiste(_clips("EXTRACT(YEAR FROM tpi.published_at) = ?", [annee], 60), 10)
    if len(top) < 8:
        return None
    top = list(reversed(top))
    n = len(top)
    lignes = "\n".join(f"N°{n - k} · {c['artiste']} — « {c['titre']} » ({vues(c['vues'])} de vues)" for k, c in enumerate(top))
    return {"cle": f"retro:{annee}", "format": "retro_annee", "mode": "compilation",
            "titre": f"Rétrospective {annee} : les {n} clips qui ont marqué l'année",
            "sous_titre": f"{n} artistes · {n} clips",
            "etiquette": f"RÉTROSPECTIVE · {annee}", "accroche": f"{annee} en {n} clips inoubliables",
            "legende_fr": (f"RÉTROSPECTIVE {annee} : les {n} clips ouest-africains qui ont marqué cette année-là, "
                           f"selon nos relevés (vues YouTube d'aujourd'hui).\n\n{lignes}\n\n"
                           f"On a oublié un clip de {annee} ? Dites-le en commentaire !"),
            "elements": [_element(c, n - k) for k, c in enumerate(top)]}


def battle_pays(jour: date) -> dict | None:
    """Battle : le N°1 de deux pays comparés — qui domine ?"""
    idx = jour.toordinal() % (len(PAYS) - 1)
    code_a, code_b = PAYS[idx], PAYS[(idx + 1) % len(PAYS)]
    top_a = _un_par_artiste(_clips("c.code = ?", [code_a], 5), 1)
    top_b = _un_par_artiste(_clips("c.code = ?", [code_b], 5), 1)
    if not top_a or not top_b:
        return None
    a, b = top_a[0], top_b[0]
    pays_a, pays_b = country_name(code_a), country_name(code_b)
    gagnant = pays_a if (a["vues"] or 0) >= (b["vues"] or 0) else pays_b
    return {"cle": f"battle-pays:{code_a}:{code_b}", "format": "battle_pays", "mode": "compilation",
            "titre": f"{pays_a} vs {pays_b} : le clip le plus vu",
            "sous_titre": f"{a['artiste']} vs {b['artiste']}",
            "etiquette": f"{code_a} VS {code_b}", "accroche": f"{pays_a} contre {pays_b} : qui a le clip N°1 ?",
            "legende_fr": (f"BATTLE : {pays_a.upper()} vs {pays_b.upper()} !\n\n"
                           f"{pays_a} : « {a['titre']} » de {a['artiste']} — {vues(a['vues'])} de vues\n"
                           f"{pays_b} : « {b['titre']} » de {b['artiste']} — {vues(b['vues'])} de vues\n\n"
                           f"Avantage {gagnant} ! Mais le vrai juge, c'est vous.\n"
                           f"Team {pays_a} ou Team {pays_b} ? En commentaire !"),
            "elements": [_element(a, 1), _element(b, 2)]}


def classique_eternel(jour: date) -> dict | None:
    """Le clip le plus ancien qui a encore des millions de vues — un classique intemporel."""
    clips = _clips("tpi.published_at < '2016-01-01'", [], 50)
    grands = [c for c in clips if (c["vues"] or 0) >= 5_000_000]
    if not grands:
        return None
    grands.sort(key=lambda c: c["sortie"] or "9999")
    c = grands[jour.toordinal() % len(grands)]
    annee = str(c["sortie"])[:4] if c.get("sortie") else "?"
    age = jour.year - int(annee) if annee.isdigit() else "?"
    return {"cle": f"classique:{c['track_id']}", "format": "classique_eternel", "mode": "simple",
            "titre": f"Classique éternel : « {c['titre']} » ({annee})",
            "sous_titre": f"{c['artiste']} · {age} ans · {vues(c['vues'])} de vues",
            "etiquette": "CLASSIQUE ÉTERNEL", "accroche": f"{age} ans et toujours aussi fort : « {c['titre']} »",
            "artiste": c["artiste"], "credit": f"clip officiel de {c['artiste']} (YouTube)",
            "legende_fr": (f"Sorti en {annee}, « {c['titre']} » de {c['artiste']} a {age} ans. "
                           f"Et pourtant : {vues(c['vues'])} de vues sur YouTube.\n\n"
                           "Certains clips ne vieillissent jamais. Celui-là en fait partie.\n"
                           "Vous l'écoutez encore ? Dites-le en commentaire."),
            "elements": [_element(c)]}


def revelation(jour: date) -> dict | None:
    """L'artiste révélation : peu de clips mais un carton immédiat."""
    artistes = db.all(
        "SELECT a.id, a.name, c.code AS pays, COUNT(tpi.id) AS nb, "
        "MAX((SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY s.captured_on DESC LIMIT 1)) AS max_vues "
        "FROM artists a JOIN tracks t ON t.artist_id = a.id JOIN track_platform_ids tpi ON tpi.track_id = t.id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active' "
        "GROUP BY a.id, a.name, c.code HAVING COUNT(tpi.id) BETWEEN 1 AND 5 "
        "ORDER BY max_vues DESC NULLS LAST LIMIT 30", [])
    revelations = [a for a in artistes if (a["max_vues"] or 0) >= 10_000_000]
    if not revelations:
        return None
    a = revelations[jour.toordinal() % len(revelations)]
    clip = _clips("a.id = ?", [a["id"]], 1)
    if not clip:
        return None
    c = clip[0]
    pays = country_name(a["pays"]) if a["pays"] else ""
    return {"cle": f"revelation:{a['id']}", "format": "revelation", "mode": "simple",
            "titre": f"Révélation : {a['name']} — {vues(c['vues'])} de vues dès le début",
            "sous_titre": f"{pays} · {a['nb']} clip(s) seulement",
            "etiquette": "RÉVÉLATION", "accroche": f"{a['name']} : {a['nb']} clip(s) et déjà {vues(c['vues'])} de vues",
            "artiste": a["name"], "credit": f"clip officiel de {a['name']} (YouTube)",
            "legende_fr": (f"RÉVÉLATION : {a['name']}"
                           + (f" ({pays})" if pays else "") +
                           f" n'a que {a['nb']} clip(s) sur YouTube, mais « {c['titre']} » "
                           f"cumule déjà {vues(c['vues'])} de vues !\n\n"
                           "Le talent n'attend pas. Vous connaissiez cet artiste ?"),
            "elements": [_element(c)]}


def top_absolu(jour: date) -> dict | None:
    """Le Top 10 absolu : les clips les plus vus de toute l'Afrique de l'Ouest."""
    top = _un_par_artiste(_clips("1=1", [], 30), 10)
    if len(top) < 10:
        return None
    top = list(reversed(top))
    lignes = "\n".join(f"N°{10 - k} · {c['artiste']} — « {c['titre']} » ({vues(c['vues'])} de vues)" for k, c in enumerate(top))
    total = sum(int(c["vues"] or 0) for c in top)
    return {"cle": f"top-absolu:{jour.isocalendar()[1]}", "format": "top_absolu", "mode": "compilation",
            "titre": "Top 10 absolu : les clips les plus vus d'Afrique de l'Ouest",
            "sous_titre": f"{vues(total)} de vues cumulées",
            "etiquette": "TOP 10 ABSOLU", "accroche": "Les 10 clips les plus vus de toute l'Afrique de l'Ouest",
            "legende_fr": (f"LE TOP 10 ABSOLU : les clips officiels les plus vus d'Afrique de l'Ouest, "
                           f"selon nos relevés. {vues(total)} de vues cumulées !\n\n{lignes}\n\n"
                           "C'est votre top à vous aussi ? Dites-le en commentaire."),
            "elements": [_element(c, 10 - k) for k, c in enumerate(top)]}


def evolution_artiste(jour: date) -> dict | None:
    """L'évolution d'un artiste : son premier clip vs son plus gros hit — avant/après."""
    artistes = db.all(
        "SELECT a.id, a.name, c.code AS pays "
        "FROM artists a JOIN tracks t ON t.artist_id = a.id JOIN track_platform_ids tpi ON tpi.track_id = t.id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active' "
        "AND tpi.published_at IS NOT NULL "
        "GROUP BY a.id, a.name, c.code HAVING COUNT(tpi.id) >= 8 ORDER BY a.name", [])
    if not artistes:
        return None
    a = artistes[(jour.toordinal() + 7) % len(artistes)]
    premier = db.one(
        "SELECT t.title AS titre, tpi.external_id AS video_id, tpi.published_at AS sortie, a.id AS artist_id, "
        "a.name AS artiste, c.code AS pays, "
        "(SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY s.captured_on DESC LIMIT 1) AS vues "
        "FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE a.id = ? AND tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 "
        "AND tpi.published_at IS NOT NULL ORDER BY tpi.published_at ASC LIMIT 1", [a["id"]])
    hit = _clips("a.id = ?", [a["id"]], 1)
    if not premier or not hit or not premier.get("video_id"):
        return None
    premier["titre"] = propre_titre(premier["titre"] or "")
    h = hit[0]
    if premier["video_id"] == h["video_id"]:
        return None
    annee_debut = str(premier["sortie"])[:4] if premier.get("sortie") else "?"
    annee_hit = str(h["sortie"])[:4] if h.get("sortie") else "?"
    return {"cle": f"evolution:{a['id']}", "format": "evolution_artiste", "mode": "compilation",
            "titre": f"L'évolution de {a['name']} : de {annee_debut} à {annee_hit}",
            "sous_titre": f"Avant / Après",
            "etiquette": "ÉVOLUTION", "accroche": f"{a['name']} : du premier clip au hit mondial",
            "legende_fr": (f"L'ÉVOLUTION DE {a['name'].upper()} :\n\n"
                           f"Avant ({annee_debut}) : « {premier['titre']} » — {vues(premier['vues'])} de vues\n"
                           f"Après ({annee_hit}) : « {h['titre']} » — {vues(h['vues'])} de vues\n\n"
                           f"Le chemin parcouru est immense. Respect.\n"
                           "Vous préférez l'ancien ou le nouveau style ?"),
            "elements": [_element(premier, 1), _element(h, 2)]}


def meme_titre(jour: date) -> dict | None:
    """Deux clips d'artistes différents avec un mot-clé commun dans le titre (Love, Money, Baby…)."""
    mots = ["Love", "Baby", "Money", "Dance", "Fire", "King", "Queen", "Party", "Night", "Girl",
            "Boy", "Heart", "God", "Mama", "Papa", "Street", "Life", "Beautiful", "Crazy", "One"]
    mot = mots[jour.toordinal() % len(mots)]
    clips = _un_par_artiste(_clips("t.title ILIKE ?", [f"%{mot}%"], 20), 10)
    if len(clips) < 2:
        return None
    idx = (jour.day * 3) % (len(clips) - 1)
    a, b = clips[idx], clips[(idx + 1) % len(clips)]
    if a["artist_id"] == b["artist_id"]:
        return None
    return {"cle": f"meme-titre:{mot}:{a['track_id']}:{b['track_id']}", "format": "meme_titre", "mode": "compilation",
            "titre": f"Même mot, deux hits : « {mot} »",
            "sous_titre": f"{a['artiste']} vs {b['artiste']}",
            "etiquette": f"MÊME MOT · {mot.upper()}", "accroche": f"« {mot} » : deux artistes, deux tubes",
            "legende_fr": (f"Le mot « {mot} » a inspiré des tubes :\n\n"
                           f"« {a['titre']} » de {a['artiste']} — {vues(a['vues'])} de vues\n"
                           f"« {b['titre']} » de {b['artiste']} — {vues(b['vues'])} de vues\n\n"
                           "Même mot, deux ambiances. Lequel vous préférez ?"),
            "elements": [_element(a, 1), _element(b, 2)]}


def roi_du_pays(jour: date) -> dict | None:
    """Le roi/la reine du pays : l'artiste avec le plus de vues cumulées dans un pays."""
    code = PAYS[(jour.toordinal() + 5) % len(PAYS)]
    artistes = db.all(
        "SELECT a.id, a.name, "
        "SUM((SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY s.captured_on DESC LIMIT 1)) AS total "
        "FROM artists a JOIN tracks t ON t.artist_id = a.id JOIN track_platform_ids tpi ON tpi.track_id = t.id "
        "LEFT JOIN countries c ON c.id = a.submission_country_id "
        "WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active' "
        "AND c.code = ? GROUP BY a.id, a.name ORDER BY total DESC NULLS LAST LIMIT 5", [code])
    if not artistes:
        return None
    roi = artistes[0]
    top = _clips("a.id = ?", [roi["id"]], 3)
    if len(top) < 2:
        return None
    top = list(reversed(top))
    n = len(top)
    pays = country_name(code)
    return {"cle": f"roi:{code}:{roi['id']}", "format": "roi_du_pays", "mode": "compilation",
            "titre": f"Le roi du {pays} : {roi['name']}",
            "sous_titre": f"{vues(roi['total'])} de vues cumulées",
            "etiquette": f"ROI · {pays.upper()}", "accroche": f"{roi['name']} domine le {pays} avec {vues(roi['total'])} de vues",
            "legende_fr": (f"QUI EST LE ROI DU {pays.upper()} ?\n\n"
                           f"Avec {vues(roi['total'])} de vues cumulées sur YouTube, {roi['name']} domine.\n\n"
                           + "\n".join(f"• « {c['titre']} » — {vues(c['vues'])} de vues" for c in reversed(top)) +
                           "\n\nVous êtes d'accord ou il manque quelqu'un ?"),
            "elements": [_element(c, n - k) for k, c in enumerate(top)]}


def decennie(jour: date) -> dict | None:
    """Les 2010s ou les 2020s : top 5 clips d'une décennie."""
    dec = 2010 if jour.isocalendar()[1] % 2 == 0 else 2020
    fin = dec + 9
    label = f"{dec}s"
    top = _un_par_artiste(_clips(
        "EXTRACT(YEAR FROM tpi.published_at) BETWEEN ? AND ?", [dec, min(fin, jour.year)], 60), 5)
    if len(top) < 5:
        return None
    top = list(reversed(top))
    lignes = "\n".join(f"N°{5 - k} · {c['artiste']} — « {c['titre']} » ({vues(c['vues'])} de vues)" for k, c in enumerate(top))
    return {"cle": f"decennie:{dec}", "format": "decennie", "mode": "compilation",
            "titre": f"Le meilleur des {label} : Top 5 clips",
            "sous_titre": " · ".join(c["artiste"] for c in reversed(top)),
            "etiquette": f"TOP · {label.upper()}", "accroche": f"Les 5 clips qui ont défini les {label}",
            "legende_fr": (f"LES {label.upper()} EN 5 CLIPS : les clips ouest-africains les plus vus de la décennie, "
                           f"selon nos relevés.\n\n{lignes}\n\n"
                           f"Les {label}, c'était mieux avant ? Ou c'est maintenant le meilleur moment ?"),
            "elements": [_element(c, 5 - k) for k, c in enumerate(top)]}


def moment_fort(jour: date) -> dict | None:
    """Moment fort : le clip qui a explosé le plus vite (le plus de vues pour un clip récent — moins de 2 ans)."""
    clips = _clips(
        "tpi.published_at >= (?::date - INTERVAL '2 years')", [jour.isoformat()], 30)
    if not clips:
        return None
    # trier par vues/jour depuis la sortie
    for c in clips:
        sortie = c.get("sortie")
        if sortie and hasattr(sortie, "date"):
            jours = max((jour - sortie.date()).days, 1)
        elif sortie:
            from datetime import date as d
            try:
                jours = max((jour - d.fromisoformat(str(sortie)[:10])).days, 1)
            except ValueError:
                jours = 365
        else:
            jours = 365
        c["vues_par_jour"] = (c["vues"] or 0) / jours
    clips.sort(key=lambda c: c["vues_par_jour"], reverse=True)
    explosions = _un_par_artiste(clips, 5)
    if not explosions:
        return None
    c = explosions[jour.day % len(explosions)]
    vpj = int(c["vues_par_jour"])
    return {"cle": f"moment-fort:{c['track_id']}", "format": "moment_fort", "mode": "simple",
            "titre": f"Moment fort : « {c['titre']} » explose !",
            "sous_titre": f"{c['artiste']} · {vpj:,} vues/jour".replace(",", " "),
            "etiquette": "MOMENT FORT 🔥", "accroche": f"« {c['titre']} » de {c['artiste']} : {vpj:,} vues par jour !".replace(",", " "),
            "artiste": c["artiste"], "credit": f"clip officiel de {c['artiste']} (YouTube)",
            "legende_fr": (f"MOMENT FORT : « {c['titre']} » de {c['artiste']} fait {vpj:,} vues par jour en moyenne "
                           f"depuis sa sortie ! Le clip cumule {vues(c['vues'])} de vues.\n\n"
                           "Ce clip est partout en ce moment. Vous l'avez vu passer ?").replace(",", " "),
            "elements": [_element(c)]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ PROPOSITIONS DU JOUR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ajoute(idees: list, faites: set, generateurs: list) -> None:
    """Ajoute la première idée non-déjà-faite de chaque générateur."""
    for gen in generateurs:
        try:
            idee = gen()
        except Exception:  # noqa: BLE001
            continue
        if idee and idee["cle"] not in faites:
            idees.append(idee)


def propositions(jour: date) -> list[dict]:
    """Les idées du jour (15 à 20), sans celles déjà fabriquées ces 60 derniers jours."""
    creer_table()
    faites = {r["cle"] for r in db.all("SELECT cle FROM studio_propositions WHERE jour >= ?::date - 60", [jour.isoformat()])}
    semaine = jour.isocalendar()[1]
    jord = jour.toordinal()
    idees = []

    # ── souvenirs (il y a X ans) ──
    for ans in (5, 10, 3, 7):
        seuil = {3: 500_000, 5: 1_000_000, 7: 500_000, 10: 200_000}[ans]
        i = il_y_a(jour, ans, seuil)
        if i and i["cle"] not in faites:
            idees.append(i)
            break

    # ── top année (tourne par semaine) ──
    for k in range(len(ANNEES_LARGE)):
        i = top_annee(ANNEES_LARGE[(semaine + k) % len(ANNEES_LARGE)])
        if i and i["cle"] not in faites:
            idees.append(i); break

    # ── top pays all-time (tourne par jour) ──
    for k in range(len(PAYS)):
        i = top_pays(PAYS[(jord + k) % len(PAYS)])
        if i and i["cle"] not in faites:
            idees.append(i); break

    # ── clip de l'année (tourne par jour) ──
    for k in range(len(ANNEES_LARGE)):
        i = clip_annee(ANNEES_LARGE[(jord + 3 + k) % len(ANNEES_LARGE)])
        if i and i["cle"] not in faites:
            idees.append(i); break

    # ── top pays × année ──
    for k in range(len(PAYS)):
        code = PAYS[(jord + k) % len(PAYS)]
        annee = ANNEES_LARGE[(semaine + k) % len(ANNEES_LARGE)]
        i = top_pays_annee(code, annee)
        if i and i["cle"] not in faites:
            idees.append(i); break

    # ── rétrospective année (compilation 10 clips) ──
    for k in range(len(ANNEES_LARGE)):
        i = retro_annee(ANNEES_LARGE[(jord + k) % len(ANNEES_LARGE)])
        if i and i["cle"] not in faites:
            idees.append(i); break

    # ── décennie (2010s / 2020s) ──
    _ajoute(idees, faites, [lambda: decennie(jour)])

    # ── top 10 absolu ──
    _ajoute(idees, faites, [lambda: top_absolu(jour)])

    # ── artiste du jour ──
    _ajoute(idees, faites, [lambda: artiste_jour(jour)])

    # ── roi du pays ──
    _ajoute(idees, faites, [lambda: roi_du_pays(jour)])

    # ── cap de vues ──
    _ajoute(idees, faites, [lambda: cap_vues(jour)])

    # ── moment fort (clip qui explose) ──
    _ajoute(idees, faites, [lambda: moment_fort(jour)])

    # ── révélation ──
    _ajoute(idees, faites, [lambda: revelation(jour)])

    # ── premier clip ──
    _ajoute(idees, faites, [lambda: premier_clip(jour)])

    # ── évolution artiste (avant/après) ──
    _ajoute(idees, faites, [lambda: evolution_artiste(jour)])

    # ── ce mois dans l'histoire ──
    _ajoute(idees, faites, [lambda: ce_mois(jour)])

    # ── classique éternel ──
    _ajoute(idees, faites, [lambda: classique_eternel(jour)])

    # ── duel ──
    _ajoute(idees, faites, [lambda: duel(jour)])

    # ── battle des pays ──
    _ajoute(idees, faites, [lambda: battle_pays(jour)])

    # ── générations ──
    _ajoute(idees, faites, [lambda: generation(jour)])

    # ── même titre ──
    _ajoute(idees, faites, [lambda: meme_titre(jour)])

    # ── pépite cachée ──
    _ajoute(idees, faites, [lambda: pepite(jour)])

    return [i for i in idees if i and i["cle"] not in faites]


def marque(cle: str, jour: date, job_id: int) -> None:
    creer_table()
    if db.value("SELECT 1 FROM studio_propositions WHERE cle = ?", [cle]):
        db.run("UPDATE studio_propositions SET job_id = ?, jour = ? WHERE cle = ?", [job_id, jour.isoformat(), cle])
    else:
        db.run("INSERT INTO studio_propositions (cle, jour, job_id) VALUES (?, ?, ?)", [cle, jour.isoformat(), job_id])
