"""Idées du jour pour Cauri Studio : formats « souvenirs et records » avec les vrais clips officiels (20/10/2026).

Le fondateur veut « ressortir l'euphorie, les sentiments d'avant » : le studio propose chaque jour des posts tout
prêts (sujet, vrais chiffres, accroche, liens des clips officiels). Rien n'est téléchargé ici : c'est le fondateur qui
lance la fabrication dans le studio (case des droits), puis valide l'envoi.

  il_y_a      : le clip le plus vu sorti cette semaine il y a 5 / 10 ans, avec ses vues d'aujourd'hui (un clip) ;
  top_annee   : les 5 clips les plus vus sortis une année donnée, un par artiste (compilation, compte à rebours) ;
  top_pays    : les 5 clips les plus vus de tous les temps d'un pays (compilation) ;
  clip_annee  : le clip qui a marqué une année (le plus vu, un clip).
Données : clips officiels YouTube relevés par Cauri (track_platform_ids) et leurs dernières vues (snapshots).
Seulement nos artistes suivis : les textes disent « selon nos relevés » quand c'est un classement.
"""
from datetime import date

from core import db
from core.helpers import country_name

ANNEES = list(range(2014, 2024))          # années « souvenirs » qui tournent de semaine en semaine
PAYS = ["NG", "GH", "TG", "CI", "SN", "BJ", "ML", "BF"]


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
    """Titre YouTube nettoyé : sans « (Official Video) », « - version officielle HD », « [Clip officiel] »…"""
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
    top = list(reversed(top))                      # compte à rebours : N°5 d'abord
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


def propositions(jour: date) -> list[dict]:
    """Les idées du jour (4 à 5), sans celles déjà fabriquées ces 60 derniers jours."""
    creer_table()
    faites = {r["cle"] for r in db.all("SELECT cle FROM studio_propositions WHERE jour >= ?::date - 60", [jour.isoformat()])}
    semaine = jour.isocalendar()[1]
    idees = [il_y_a(jour, 5, 1_000_000), il_y_a(jour, 10, 200_000)]
    for k in range(len(ANNEES)):                   # une année par semaine, la suivante si déjà faite
        idee = top_annee(ANNEES[(semaine + k) % len(ANNEES)])
        if idee and idee["cle"] not in faites:
            idees.append(idee); break
    for k in range(len(PAYS)):
        idee = top_pays(PAYS[(jour.toordinal() + k) % len(PAYS)])
        if idee and idee["cle"] not in faites:
            idees.append(idee); break
    for k in range(len(ANNEES)):
        idee = clip_annee(ANNEES[(jour.toordinal() + 3 + k) % len(ANNEES)])
        if idee and idee["cle"] not in faites:
            idees.append(idee); break
    return [i for i in idees if i and i["cle"] not in faites]


def marque(cle: str, jour: date, job_id: int) -> None:
    creer_table()
    if db.value("SELECT 1 FROM studio_propositions WHERE cle = ?", [cle]):
        db.run("UPDATE studio_propositions SET job_id = ?, jour = ? WHERE cle = ?", [job_id, jour.isoformat(), cle])
    else:
        db.insert("studio_propositions", {"cle": cle, "jour": jour.isoformat(), "job_id": job_id})
