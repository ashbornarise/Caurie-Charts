"""Posts vidéo du jour : extraits de clips officiels coupés au refrain (refrain.py), 3 par jour, envoyés à leur heure
par la file d'attente (thème « format-clip-N », comme les autres formats).

Choix des titres (sans jamais reprendre un titre déjà passé en clip ces 21 derniers jours) :
  1. les N°1 du dernier classement officiel publié (« N°1 au Nigeria cette semaine », nouvelles vues de la semaine) ;
  2. le Top 20 Afrique de l'Ouest en direct (« N°3 en Afrique de l'Ouest ») ;
  3. les clips officiels sortis ces 7 derniers jours par nos artistes suivis, les plus vus d'abord (« Nouveau clip »).
Téléchargement YouTube : à lancer depuis le poste de travail (manage.py clips), YouTube bloquant souvent les serveurs."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core import db, storage
from core.helpers import country_name
from core.services.platforms import log_write
from core.services.social import image as PI
from core.services.social import refrain as R

HEURES = (13, 17, 21)     # heure de Lomé (= UTC) : midi, sortie du travail, soirée


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


def candidats() -> list[dict]:
    """Titres possibles, du plus fort au plus faible : {track_id, haut, chiffre}."""
    out = []
    from core import repos
    for c in repos.official_tops(1):
        e = c["rows"][0]
        tid = e.get("track_id")
        if tid:
            out.append({"track_id": int(tid), "haut": f"N°1 au {country_name(c['code'])} cette semaine",
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
        if c["track_id"] not in vus:
            vus.add(c["track_id"]); uniques.append(c)
    return uniques


def du_jour(jour: date | None = None, n: int = 3, essai: bool = False) -> list[str]:
    """Fabrique jusqu'à n vidéos pour la journée et les programme (file d'attente) aux heures HEURES."""
    jour = jour or datetime.now(timezone.utc).date()
    PI.DIR.mkdir(parents=True, exist_ok=True)
    faits_du_jour = db.all("SELECT theme FROM social_posts WHERE slot_date = ? AND theme LIKE 'format-clip-%'", [jour.isoformat()])
    deja_faits = {r["theme"] for r in faits_du_jour}
    lignes, k, artistes = [], 0, set()
    for c in candidats():
        if k >= n:
            break
        artiste = db.value("SELECT artist_id FROM tracks WHERE id = ?", [c["track_id"]])
        if artiste in artistes:
            continue   # un artiste par vidéo et par jour (Asake deux fois le 17/10)
        theme = f"format-clip-{k + 1}"
        if theme in deja_faits:
            k += 1
            continue
        if _deja(c["track_id"]):
            continue
        artistes.add(artiste)
        # Extrait du clip seulement avec l'accord écrit de l'artiste ou du label (conf « social.refrain.autorises ») ;
        # sinon vidéo maison muette (photos libres), le son officiel s'ajoutant dans l'application (blocage UMG, 16/10/2026)
        autorise = _autorise(c["track_id"]) and bool(R.clip_officiel(c["track_id"]))
        nom = f"{jour.isoformat()}-clip-{k + 1}-{datetime.now(timezone.utc):%H%M%S}"
        video = PI.DIR / f"{nom}.mp4"
        res = R.extrait(c["track_id"], c["haut"], c["chiffre"], str(video)) if autorise else None
        if not res:
            # Pas d'accord, ou YouTube a refusé le téléchargement (fréquent depuis un serveur) : vidéo maison
            autorise = False
            res = R.maison(c["track_id"], c["haut"], c["chiffre"], str(video))
        if not res:
            lignes.append(f"titre {c['track_id']} : extrait impossible")
            continue
        vignette = PI.DIR / f"{nom}.jpg"
        R.vignette(str(video), str(vignette))
        due = datetime(jour.year, jour.month, jour.day, HEURES[k], 0, tzinfo=timezone.utc)
        # Lancé tard : l'heure passée devient « dans 20 min », puis une vidéo par heure
        due = max(due, datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=20 + 60 * k))
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
        storage.publish_media_files("social", [video.name, vignette.name])
        db.insert("social_posts", {"slot_date": jour.isoformat(), "theme": theme, "title": titre[:160], "caption": legende,
                                   "hashtags": tags[:300], "image_square": vignette.name, "image_story": vignette.name, "carousel": "[]",
                                   "video": video.name, "status": "approved",
                                   "facts": json.dumps({"kind": "format-clip" if autorise else "format-video", "due": due.isoformat(),
                                                        "track_id": c["track_id"], "source": res.get("source")}, ensure_ascii=False)})
        lignes.append(f"{titre} → {due:%H:%M} ({genre})")
        k += 1
    return lignes
