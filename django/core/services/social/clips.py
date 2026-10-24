"""Posts vidéo du jour : extraits de clips officiels coupés au refrain (refrain.py), 3 par jour, envoyés à leur heure
par la file d'attente (thème « format-clip-N », comme les autres formats).

Choix des titres (sans jamais reprendre un titre déjà passé en clip ces 21 derniers jours) :
  1. les N°1 du dernier classement officiel publié (« N°1 au Nigeria cette semaine », nouvelles vues de la semaine) ;
  2. le Top 20 Afrique de l'Ouest en direct (« N°3 en Afrique de l'Ouest ») ;
  3. les clips officiels sortis ces 7 derniers jours par nos artistes suivis, les plus vus d'abord (« Nouveau clip »).
La vidéo de 17 h devient un « moment d'interview » (interviews.py : un artiste qui parle de lui, avec le son de la
parole) quand un passage valable est trouvé ; sinon, extrait de clip ou vidéo maison comme les autres.
Téléchargement YouTube : à lancer depuis le poste de travail (manage.py clips), YouTube bloquant souvent les serveurs."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core import db, storage
from core.helpers import country_name
from core.services.platforms import log_write
from core.services.social import image as PI
from core.services.social import encodage as E
from core.services.social import refrain as R

HEURES = (19, 13, 21)     # heure de Lomé (= UTC) ; un seul clip par jour de publication : 19 h (pointe africaine)
# Décision du 24/10/2026 : 3 clips par semaine (lundi, mercredi, vendredi), seulement des clips récents qui ont déjà
# leur public — moins de CLIP_AGE_MAX jours et au moins CLIP_VUES_MIN vues sur YouTube.
JOURS_CLIPS = (1, 3, 5)
CLIP_AGE_MAX = 60
CLIP_VUES_MIN = 100_000


def _vues(n: float) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}".replace(".", ",").replace(",0", "") + " M"
    return f"{round(n / 1e3)} k" if n >= 1e3 else str(int(n))


def _deja(track_id: int, jours: int = 21) -> bool:
    for r in db.all("SELECT facts FROM social_posts WHERE theme LIKE 'format-clip-%' AND slot_date >= CURRENT_DATE - ?", [jours]):
        try:
            if json.loads(r["facts"]).get("track_id") == track_id:
                return True
        except (ValueError, TypeError):
            pass
    return False


MAX_ABONNES = 1_000_000   # au-delà, artiste presque toujours chez une major : vidéo maison


def _autorise(track_id: int) -> bool:
    """Extrait du clip autorisé ?
    - oui si l'artiste ou son label a donné son accord écrit (conf « social.refrain.autorises ») ;
    - jamais s'il est sur la liste noire (conf « social.refrain.exclus », ex. après un blocage) ;
    - sinon, règle du fondateur (17/10/2026) : les artistes indépendants hors Nigeria, avec moins d'un million d'abonnés
      YouTube, ne sont presque jamais bloqués (Piesie Esther est passée, Ayra Starr — Mavin/Universal — bloquée)."""
    from core import conf
    r = db.one("""SELECT a.name, a.label_owner, a.youtube_subscribers, COALESCE(a.base_country, gc.code) AS pays
                  FROM tracks t JOIN artists a ON a.id = t.artist_id LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                  WHERE t.id = ?""", [track_id])
    if not r:
        return False
    nom, label = r["name"].lower(), (r.get("label_owner") or "").lower()
    if nom in R.exclus() or (label and label in R.exclus()):
        return False
    ok = {x.lower() for x in (conf.get("social.refrain.autorises") or [])}
    if nom in ok or (label and label in ok):
        return True
    plafond = int(conf.get("social.refrain.max_abonnes") or MAX_ABONNES)
    return r.get("pays") not in (None, "NG") and int(r.get("youtube_subscribers") or 0) < plafond


# 24/10/2026 : cibles prioritaires et artistes qui font le buzz (liste du fondateur, à tenir à jour). Leurs marchés sont
# plus petits : un clip récent leur suffit avec CLIP_VUES_BUZZ vues.
PAYS_CIBLES = ("TG", "CI", "BJ", "NG", "GH")
BUZZ = ("Conni Gangster", "Mic Flammez", "Shatta Wale", "Sethlo", "Didi B", "Axel Merryl", "Himra")
CLIP_VUES_BUZZ = 20_000


def _au(code: str) -> str:
    """« au Togo », « en Côte d'Ivoire »."""
    return ("en " if code in ("CI", "GN", "GM", "MR", "SL", "GW") else "au ") + country_name(code)


def _buzz() -> list[dict]:
    """Clips récents des artistes qui font le buzz, les plus vus d'abord."""
    noms = [n.lower() for n in BUZZ]
    rows = db.all(f"""SELECT tpi.track_id, a.name, (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id
                              ORDER BY s.captured_on DESC LIMIT 1) AS vues
                      FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id
                      WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1
                        AND lower(a.name) IN ({", ".join(["?"] * len(noms))}) AND tpi.published_at >= CURRENT_DATE - ?
                      ORDER BY vues DESC NULLS LAST LIMIT 10""", [*noms, CLIP_AGE_MAX])
    joli = {n.lower(): n for n in BUZZ}
    return [{"track_id": int(r["track_id"]), "haut": f"{joli.get(r['name'].lower(), r['name'])} fait le buzz", "buzz": True,
             "chiffre": f"{_vues(r['vues'])} vues sur YouTube" if r.get("vues") else ""} for r in rows]


def _tendances() -> list[dict]:
    """Suivre le flux : titres en tendance ces 3 derniers jours (YouTube, Shazam) dans les pays cibles."""
    rows = db.all(f"""SELECT o.track_id, c.code, MIN(o.position) AS pos FROM chart_observations o JOIN countries c ON c.id = o.country_id
                      JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
                      WHERE o.observed_on >= CURRENT_DATE - 3 AND o.source IN ('youtube_trending', 'shazam') AND a.status = 'active'
                        AND c.code IN ({", ".join(["?"] * len(PAYS_CIBLES))})
                      GROUP BY o.track_id, c.code ORDER BY MIN(o.position) LIMIT 15""", list(PAYS_CIBLES))
    return [{"track_id": int(r["track_id"]), "haut": f"En tendance {_au(r['code'])}", "petit": r["code"] in ("TG", "BJ"),
             "chiffre": f"N°{r['pos']} des tendances"} for r in rows]


def candidats() -> list[dict]:
    """Titres possibles, du plus fort au plus faible : {track_id, haut, chiffre}.
    Ordre (24/10/2026) : artistes du buzz, N°1 des pays cibles, tendances des pays cibles, puis le reste."""
    out = []
    from core import repos
    try:
        out += _buzz()
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"clips : buzz indisponible ({exc})")
    tops = sorted(repos.official_tops(1), key=lambda c: c["code"] not in PAYS_CIBLES)
    for c in tops[:sum(1 for t in tops if t["code"] in PAYS_CIBLES)]:
        e = c["rows"][0]
        if e.get("track_id"):
            out.append({"track_id": int(e["track_id"]), "haut": f"N°1 {_au(c['code'])} cette semaine", "petit": c["code"] in ("TG", "BJ"),
                        "chiffre": f"+{_vues(e['views'])} vues en 7 jours" if e.get("views") else ""})
    try:
        out += _tendances()
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"clips : tendances indisponibles ({exc})")
    for c in tops:
        e = c["rows"][0]
        tid = e.get("track_id")
        if tid:
            out.append({"track_id": int(tid), "haut": f"N°1 {_au(c['code'])} cette semaine",
                        "chiffre": f"+{_vues(e['views'])} vues en 7 jours" if e.get("views") else ""})
    try:
        from core.services import live_chart
        for r in live_chart.build(None, None, 20, "prime", 20, "week")["rows"][:20]:
            if r.get("is_artist") or not r.get("track_id"):
                continue
            out.append({"track_id": int(r["track_id"]), "haut": f"N°{r['rank']} en Afrique de l'Ouest", "chiffre": ""})
    except Exception as exc:  # noqa: BLE001 — sans classement en direct, on garde les autres sources
        log_write("social", "error", f"clips : classement en direct indisponible ({exc})")
    for r in db.all("""SELECT tpi.track_id, (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY s.captured_on DESC LIMIT 1) AS vues
                       FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id
                       WHERE tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1 AND a.status = 'active'
                         AND tpi.published_at >= CURRENT_DATE - 7 ORDER BY vues DESC NULLS LAST LIMIT 15"""):
        out.append({"track_id": int(r["track_id"]), "haut": "Nouveau clip",
                    "chiffre": f"{_vues(r['vues'])} vues en quelques jours" if r.get("vues") else ""})
    vus, uniques = set(), []
    for c in out:
        if c["track_id"] not in vus and recent_et_vu(c["track_id"], CLIP_VUES_BUZZ if c.get("buzz") or c.get("petit") else CLIP_VUES_MIN):
            vus.add(c["track_id"]); uniques.append(c)
    return uniques


def recent_et_vu(track_id: int, vues_min: int = CLIP_VUES_MIN) -> bool:
    """Clip officiel sorti depuis moins de CLIP_AGE_MAX jours, avec au moins CLIP_VUES_MIN vues (dernier relevé)."""
    return bool(db.value("""SELECT 1 FROM track_platform_ids tpi
                            WHERE tpi.track_id = ? AND tpi.platform = 'youtube' AND tpi.kind = 'clip' AND tpi.is_official = 1
                              AND tpi.published_at >= CURRENT_DATE - ?
                              AND (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = tpi.id
                                   ORDER BY s.captured_on DESC LIMIT 1) >= ? LIMIT 1""", [track_id, CLIP_AGE_MAX, vues_min]))


SLOT_INTERVIEW = 1   # la vidéo de 17 h devient un « moment d'interview » quand un passage valable est trouvé


def _due(jour: date, k: int) -> datetime:
    due = datetime(jour.year, jour.month, jour.day, HEURES[k], 0, tzinfo=timezone.utc)
    # Lancé tard : l'heure passée devient « dans 20 min », puis une vidéo par heure
    return max(due, datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=20 + 60 * k))


def _interview(jour: date, k: int, essai: bool, pris: set) -> tuple[str, str] | None:
    """Moment d'interview (interviews.py) pour le créneau k : (ligne de compte rendu, artiste) ou None.
    Deux artistes essayés au plus (une recherche YouTube chacun) ; ni un artiste passé en interview ces 14 jours,
    ni une vidéo déjà utilisée."""
    from core.services.social import interviews as IT
    try:
        vids, recents = IT.deja_vus()
    except Exception:  # noqa: BLE001
        vids, recents = set(), set()
    nom = f"{jour.isoformat()}-interview-{k + 1}-{datetime.now(timezone.utc):%H%M%S}"
    video = PI.DIR / f"{nom}.mp4"
    res = None
    candidats_itw = list(dict.fromkeys([*BUZZ, *IT.artistes(jour)]))   # artistes du buzz d'abord (24/10/2026)
    for artiste in [a for a in candidats_itw if a.lower() not in pris | recents][:2]:
        res = IT.moment(artiste, str(video), vids)
        if res:
            break
    if not res:
        return None
    titre = f"Moment d'interview : {res['artist']} · {res['accroche']}"
    if essai:
        return f"[essai] {titre} → {video.name} (interview, {res['source']})", res["artist"]
    vignette = PI.DIR / f"{nom}.jpg"
    R.vignette(str(video), str(vignette), 2.0)
    due = _due(jour, k)
    tags = "#CauriCharts #" + "".join(ch for ch in res["artist"] if ch.isalnum()) + " #Interview #Afrobeats #MusiqueAfricaine"
    storage.publish_media_files("social", [video.name, vignette.name, E.nom_telegram(video.name)])
    # Son propre son (la parole) : kind « format-clip », publication automatique comme les extraits de clips
    db.insert("social_posts", {"slot_date": jour.isoformat(), "theme": f"format-clip-{k + 1}", "title": titre[:160],
                               "caption": IT.legende(res), "hashtags": tags[:300], "image_square": vignette.name,
                               "image_story": vignette.name, "carousel": "[]", "video": video.name, "status": "approved",
                               "facts": json.dumps({"kind": "format-clip", "format": "interview", "due": due.isoformat(),
                                                    "artiste": res["artist"], "video_id": res["video_id"], "source": res["source"],
                                                    "debut": res["debut"], "fin": res["fin"], "accroche": res["accroche"],
                                                    "texte": res["texte"][:1500]}, ensure_ascii=False)})
    return f"{titre} → {due:%H:%M} (moment d'interview)", res["artist"]


def du_jour(jour: date | None = None, n: int = 1, essai: bool = False, force: bool = False) -> list[str]:
    """Fabrique jusqu'à n vidéos pour la journée et les programme (file d'attente) aux heures HEURES.
    Une des vidéos (créneau SLOT_INTERVIEW) est un « moment d'interview » si un passage valable est trouvé."""
    jour = jour or datetime.now(timezone.utc).date()
    if jour.isoweekday() not in JOURS_CLIPS and not essai and not force:
        # Les autres jours : un moment d'interview à 19 h (l'artiste qui parle, avec le vrai son), décision du 24/10/2026
        if db.value("SELECT 1 FROM social_posts WHERE slot_date = ? AND theme LIKE 'format-clip-%' LIMIT 1", [jour.isoformat()]):
            return ["vidéo du jour déjà faite"]
        PI.DIR.mkdir(parents=True, exist_ok=True)
        itw = _interview(jour, 0, essai, set())
        return [itw[0]] if itw else ["pas de clip aujourd'hui (lundi, mercredi, vendredi) ; aucune interview valable trouvée"]
    PI.DIR.mkdir(parents=True, exist_ok=True)
    faits_du_jour = db.all("SELECT theme FROM social_posts WHERE slot_date = ? AND theme LIKE 'format-clip-%'", [jour.isoformat()])
    deja_faits = {r["theme"] for r in faits_du_jour}
    lignes, k, artistes, noms, itw_tente = [], 0, set(), set(), False
    for c in candidats():
        if k >= n:
            break
        if n >= 2 and k == SLOT_INTERVIEW and not itw_tente and f"format-clip-{k + 1}" not in deja_faits:
            itw_tente = True
            itw = _interview(jour, k, essai, noms)
            if itw:
                lignes.append(itw[0]); noms.add(itw[1].lower())
                k += 1
                if k >= n:
                    break
        artiste = db.value("SELECT artist_id FROM tracks WHERE id = ?", [c["track_id"]])
        nom_artiste = (db.value("SELECT name FROM artists WHERE id = ?", [artiste]) or "").lower()
        if artiste in artistes or nom_artiste in noms:
            continue   # un artiste par vidéo et par jour (Asake deux fois le 17/10)
        theme = f"format-clip-{k + 1}"
        if theme in deja_faits:
            k += 1
            continue
        if _deja(c["track_id"]):
            continue
        artistes.add(artiste); noms.add(nom_artiste)
        # Extrait du clip seulement avec l'accord écrit de l'artiste ou du label (conf « social.refrain.autorises ») ;
        # sinon vidéo maison muette (photos libres), le son officiel s'ajoutant dans l'application (blocage UMG, 16/10/2026)
        autorise = _autorise(c["track_id"]) and bool(R.clip_officiel(c["track_id"]))
        nom = f"{jour.isoformat()}-clip-{k + 1}-{datetime.now(timezone.utc):%H%M%S}"
        video = PI.DIR / f"{nom}.mp4"
        res = R.extrait(c["track_id"], c["haut"], c["chiffre"], str(video)) if autorise else None
        # Plus de vidéo maison (diaporama de photos) : refusée par Agbalenyoclé le 19/10/2026. Sans extrait autorisé, pas de vidéo.
        if not res:
            lignes.append(f"titre {c['track_id']} : extrait impossible")
            continue
        vignette = PI.DIR / f"{nom}.jpg"
        R.vignette(str(video), str(vignette))
        due = _due(jour, k)
        if force:   # clip hors calendrier : au plus tôt 25 min après sa fabrication
            due = max(due, datetime.now(timezone.utc) + timedelta(minutes=25))
        titre = f"{c['haut']} : {res['title']} · {res['artist']}"
        legende = (f"🎬 {c['haut']} : « {res['title']} » de {res['artist']}\n\n"
                   + (f"📈 {c['chiffre']}\n\n" if c["chiffre"] else "")
                   + "Le refrain qui tourne en boucle en ce moment. Vous l'avez déjà en tête ⁉️ Dites-le en commentaire ‼️"
                   + (f"\n\nExtrait du clip officiel : youtube.com/watch?v={res['video_id']}" if autorise else "")
                   + (f"\n\n{res['credits']}" if res.get("credits") else ""))
        tags = "#CauriCharts #" + "".join(ch for ch in res["artist"] if ch.isalnum()) + " #Afrobeats #MusiqueAfricaine"
        genre = "extrait du clip" if autorise else "vidéo maison, son à ajouter dans l'appli"
        if essai:
            lignes.append(f"[essai] {titre} → {video.name} ({genre})")
            k += 1
            continue
        storage.publish_media_files("social", [video.name, vignette.name, E.nom_telegram(video.name)])
        db.insert("social_posts", {"slot_date": jour.isoformat(), "theme": theme, "title": titre[:160], "caption": legende,
                                   "hashtags": tags[:300], "image_square": vignette.name, "image_story": vignette.name, "carousel": "[]",
                                   "video": video.name, "status": "approved",
                                   "facts": json.dumps({"kind": "format-clip" if autorise else "format-video", "due": due.isoformat(),
                                                        "track_id": c["track_id"], "source": res.get("source")}, ensure_ascii=False)})
        lignes.append(f"{titre} → {due:%H:%M} ({genre})")
        k += 1
    return lignes
