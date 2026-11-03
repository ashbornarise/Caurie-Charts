"""Titres en double (03/11/2026) : « Ganging 3 » / « GANGING 03 », « Power House » / « Powerhouse ft Kwesi Arthur »…
Ils dispersent les vues d'un même son sur deux fiches et faussent les scores.

Même artiste + même titre une fois normalisé (accents, majuscules, « feat. », « official video », 06 = 6), en GARDANT
les vraies versions (remix, live, acoustique, instrumental…). Garde-fous :
  - les deux fiches ont un clip YouTube de durées très différentes (> 20 s) : sans doute deux versions, on ne fusionne pas
    (API YouTube, 1 unité pour 50 vidéos : une fois par semaine seulement) ;
  - le doublon est dans un classement publié ou une distinction : signalé au fondateur, jamais fusionné seul.
La fiche gardée est la plus relevée ; tout passe sur elle dans une transaction, puis le doublon est supprimé.
"""
import re
import unicodedata
from collections import defaultdict

from core import db, env

VERSIONS = r"remix|rmx|live|acoustic|acoustique|version|sped|slowed|instrumental|edit|refix|cover|reprise|extended|mix|" \
           r"freestyle|unplugged|demo|interlude|part|pt|vol"


def cle(titre: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", (titre or "").lower()) if unicodedata.category(c) != "Mn")
    marques = sorted(set(re.findall(VERSIONS, t)))
    t = re.sub(r"[\(\[].*?(feat|ft|prod)[^\)\]]*[\)\]]", "", t)
    t = re.sub(r"\b(feat|ft|featuring)\b.*", "", t)
    t = re.sub(r"\b(official|music|video|audio|clip|lyrics?|visuali[sz]er)\b", "", t)
    t = re.sub(r"\b0+(\d)", r"\1", t)
    return re.sub(r"[^a-z0-9]", "", t) + "|" + ",".join(marques)


def groupes() -> list:
    g = defaultdict(list)
    for r in db.all("""SELECT t.id, t.artist_id, t.title, (SELECT COUNT(*) FROM chart_observations o WHERE o.track_id = t.id) AS obs
                       FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE a.status <> 'out_of_scope'"""):
        k = cle(r["title"])
        if len(k.split("|")[0]) >= 2:
            g[(r["artist_id"], k)].append(r)
    return [sorted(v, key=lambda r: (-int(r["obs"]), int(r["id"]))) for v in g.values() if len(v) > 1]


def _durees(video_ids: list) -> dict:
    """Durée en secondes de chaque vidéo YouTube (1 unité pour 50)."""
    import requests
    from core.services.platforms import YouTubeQuota
    cle_api, out = env.get("YOUTUBE_API_KEY", ""), {}
    for i in range(0, len(video_ids), 50):
        lot = video_ids[i:i + 50]
        if not cle_api or not YouTubeQuota.spend(1):
            break
        d = requests.get("https://www.googleapis.com/youtube/v3/videos", params={"part": "contentDetails", "id": ",".join(lot),
                                                                                  "key": cle_api}, timeout=30).json()
        for it in d.get("items") or []:
            m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", it["contentDetails"].get("duration") or "")
            if m:
                h, mi, s = (int(x or 0) for x in m.groups())
                out[it["id"]] = h * 3600 + mi * 60 + s
    return out


def _fusionne(garde: int, doublon: int) -> None:
    with db.atomic():
        db.run("UPDATE track_platform_ids SET track_id = ? WHERE track_id = ?", [garde, doublon])
        db.run("UPDATE chart_observations SET track_id = ? WHERE track_id = ?", [garde, doublon])
        db.run("""DELETE FROM weekly_scores w WHERE w.track_id = ? AND EXISTS
                  (SELECT 1 FROM weekly_scores x WHERE x.track_id = ? AND x.country_id = w.country_id AND x.week_start = w.week_start)""",
               [doublon, garde])
        db.run("UPDATE weekly_scores SET track_id = ? WHERE track_id = ?", [garde, doublon])
        db.run("""DELETE FROM track_reviews r WHERE r.track_id = ? AND EXISTS
                  (SELECT 1 FROM track_reviews x WHERE x.track_id = ? AND x.week_start = r.week_start)""", [doublon, garde])
        db.run("UPDATE track_reviews SET track_id = ? WHERE track_id = ?", [garde, doublon])
        db.run("UPDATE submissions SET track_id = ? WHERE track_id = ?", [garde, doublon])
        db.run("DELETE FROM tracks WHERE id = ?", [doublon])


def nettoie(appliquer: bool = True) -> list:
    gs = groupes()
    clips = defaultdict(list)
    ids = [r["id"] for g in gs for r in g]
    if ids:
        for r in db.all(f"""SELECT track_id, external_id FROM track_platform_ids WHERE platform = 'youtube'
                            AND track_id IN ({','.join(['?'] * len(ids))})""", ids):
            clips[int(r["track_id"])].append(r["external_id"])
    durees = _durees([v for vs in clips.values() for v in vs])
    fusions, versions, a_voir = 0, 0, []
    for g in gs:
        garde = g[0]
        for d in g[1:]:
            publie = db.value("""SELECT 1 FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id AND r.status = 'published'
                                 WHERE e.track_id = ? UNION SELECT 1 FROM award_distinctions WHERE track_id = ? LIMIT 1""", [d["id"], d["id"]])
            dg = [durees[v] for v in clips.get(int(garde["id"]), []) if v in durees]
            dd = [durees[v] for v in clips.get(int(d["id"]), []) if v in durees]
            if dg and dd and min(abs(a - b) for a in dg for b in dd) > 20:
                versions += 1
                continue   # deux clips de durées très différentes : deux versions, on garde les deux
            if publie:
                a_voir.append(f"« {garde['title']} » / « {d['title']} »")
                continue
            if appliquer:
                _fusionne(int(garde["id"]), int(d["id"]))
            fusions += 1
    lignes = [f"Doublons : {fusions} fiche(s) fusionnée(s), {versions} gardée(s) comme versions différentes (durées YouTube), "
              f"{len(a_voir)} à trancher (déjà dans un classement publié)"]
    if a_voir:
        lignes.append("À trancher : " + " ; ".join(a_voir[:20]))
    return lignes
