"""Distinctions officielles Cauri Charts : rares, mensuelles, tirées des classements mensuels publiés.

  qui      : le Top 5 de chaque classement mensuel : Afrique de l'Ouest et chaque pays ;
  rareté   : un titre n'est distingué qu'une seule fois par classement (index unique track_id + scope) ;
  numéro   : l'identifiant de la table (N° 0001…), jamais réutilisé : c'est l'archive des classements ouest-africains ;
  envoi    : page publique /distinctions/<n> (carte, PDF d'impression) ; e-mail automatique si l'équipe a saisi le contact
             de l'artiste, sinon un message prêt à envoyer en DM ;
  fichiers : la carte (JPG, sur le Blob, à envoyer à l'artiste) ; l'impression (PDF 8 × 10 po, 300 ppp, fond perdu),
             le calque de dorure et la version encadrée sont produits à la demande depuis l'admin.
"""
import io
import json

from core import budget, conf, db, storage
from core.helpers import country_name, url

TOP = {"prime-wa": 5, "prime": 5}
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def month_label(key: str) -> str:
    """« 2026-10 » → « Octobre 2026 »."""
    y, m = key.split("-")[:2]
    return f"{MONTHS[int(m) - 1].capitalize()} {y}"


def pending_runs() -> list:
    """Classements mensuels publiés qui n'ont pas encore leurs distinctions."""
    return db.all("""SELECT r.id, r.period_key, ct.code AS chart, c.code AS country, c.chart_size
                     FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id LEFT JOIN countries c ON c.id = r.country_id
                     WHERE r.period_type = 'month' AND r.status = 'published' AND r.is_provisional = 0
                       AND ct.code IN ('prime-wa', 'prime')
                       AND NOT EXISTS (SELECT 1 FROM award_distinctions d WHERE d.chart_run_id = r.id)
                     ORDER BY r.period_start, ct.code DESC, c.sort_order""")


def _label(run: dict) -> tuple[str, str]:
    if run["chart"] == "prime-wa":
        return "WA", f"Top {int(conf.get('charts.prime-wa.size', 20))} · Afrique de l’Ouest"
    return run["country"], f"Top {int(run['chart_size'])} · {country_name(run['country'])}"


def generate(run: dict) -> list:
    """Crée les distinctions d'un classement mensuel publié ; retourne leurs numéros."""
    scope, label = _label(run)
    entries = db.all("""SELECT e.position, e.track_id, e.previous_position, e.peak_position, e.weeks_on_chart,
                               t.title, a.id AS artist_id, a.name AS artist_name, a.image_url, a.status
                        FROM chart_entries e JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
                        WHERE e.chart_run_id = ? AND e.position <= ? ORDER BY e.position""", [run["id"], TOP[run["chart"]]])
    done = []
    for e in entries:
        if e["status"] != "active":
            continue  # artiste à confirmer : pas de distinction tant que son identité n'est pas vérifiée
        if db.one("SELECT 1 FROM award_distinctions WHERE track_id = ? AND scope = ?", [e["track_id"], scope]):
            continue  # déjà distingué dans ce classement : une seule fois, c'est ce qui fait la valeur
        stats = {"last": e["previous_position"], "peak": e["peak_position"], "weeks": e["weeks_on_chart"]}
        did = db.insert("award_distinctions", {
            "chart_run_id": run["id"], "scope": scope, "period_key": run["period_key"], "rank": e["position"],
            "track_id": e["track_id"], "artist_id": e["artist_id"], "artist_name": e["artist_name"], "title": e["title"],
            "chart_label": label, "stats": json.dumps(stats), "photo_url": e["image_url"]})
        img = render(db.one("SELECT * FROM award_distinctions WHERE id = ?", [did]))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=92, optimize=True, progressive=True)
        storage.store_media("distinctions", f"{did}.jpg", out.getvalue(), "image/jpeg")
        db.update("award_distinctions", {"image_name": f"{did}.jpg"}, "id = :id", {"id": did})
        done.append(did)
    return done


def render(d: dict, size=(1600, 2000), **kw):
    """La carte d'une distinction enregistrée (même rendu à chaque fois : tout vient de la ligne en base)."""
    from core.services.social import award
    y, m = str(d["period_key"]).split("-")[:2]
    return award.card(int(d["rank"]), d["chart_label"], d["artist_name"], d["title"], d["photo_url"], month_label(d["period_key"]),
                      size=size, kind="title" if d["title"] else "artist", number=int(d["id"]),
                      stats=json.loads(d["stats"] or "{}"), unit="month", code_period=f"M{int(m):02d}·{y}", **kw)


def files(d: dict, kind: str) -> tuple[bytes, str, str]:
    """Fichier à télécharger depuis l'admin : carte, impression (PDF), dorure (PDF) ou encadrée (JPG)."""
    from PIL import Image, ImageOps
    from core.services.social import award
    name = f"Cauri Charts - Distinction {int(d['id']):04d} - {d['artist_name']}"
    out = io.BytesIO()
    if kind in ("impression", "dorure"):
        img = render(d, size=(2400, 3000))
        bleed = 36  # 3 mm à 300 ppp
        if kind == "impression":
            ImageOps.expand(img, border=bleed, fill=award.INK).save(out, "PDF", resolution=300)
        else:
            foil = img.info.get("foil", Image.new("L", img.size, 0))
            ImageOps.expand(ImageOps.invert(foil), border=bleed, fill=255).convert("1").save(out, "PDF", resolution=300)
        return out.getvalue(), "application/pdf", f"{name} - {kind}.pdf"
    img = render(d)
    if kind == "cadre":
        img = award.cadre(img, seed=str(d["id"]))
    img.save(out, "JPEG", quality=92)
    return out.getvalue(), "image/jpeg", f"{name} - {kind}.jpg"


def public_url(d: dict) -> str:
    return url(f"distinctions/{int(d['id'])}")


def message(d: dict) -> str:
    """Message à l'artiste (e-mail ou DM Instagram) : la distinction, sa preuve, les liens."""
    what = f"N°{d['rank']} du {d['chart_label']}" + (f" avec « {d['title']} »" if d.get("title") else "")
    return (f"Bonjour {d['artist_name']},\n\n"
            f"Félicitations ! Vous êtes {what} en {month_label(d['period_key']).lower()} sur Cauri Charts, "
            "le classement musical de l'Afrique de l'Ouest calculé sur des données réelles.\n\n"
            f"Votre distinction officielle N° {int(d['id']):04d} vous attend ici, avec la carte à partager et le fichier "
            f"prêt à imprimer :\n{public_url(d)}\n\n"
            "Partagez-la avec vos fans en mentionnant @cauricharts : nous la republierons.\n\nL'équipe Cauri Charts")


SLOTS = (("distinction", 15), ("distinction-2", 13))  # deux annonces par jour au plus (UTC), loin de la vidéo de midi et du post de 18 h


def announce(d: dict) -> str:
    """Post « distinction remise » : la carte encadrée sur Instagram, Facebook et TikTok, l'artiste mentionné.
    Deux annonces par jour au plus (15 h puis 13 h UTC), le premier créneau libre à partir de demain."""
    from datetime import datetime, timedelta, timezone
    from core import clock
    from core.services import buffer
    from core.services.social import award
    key = f"distinction-{int(d['id'])}"
    if db.one("SELECT 1 FROM social_posts WHERE theme LIKE 'distinction%' AND facts LIKE ?", [f'%"{key}"%']):
        return "déjà annoncée"
    a = db.one("SELECT instagram, base_country FROM artists WHERE id = ?", [d["artist_id"]]) or {}
    day = clock.today() + timedelta(days=1)
    while True:
        taken = {r["theme"] for r in db.all("SELECT theme FROM social_posts WHERE theme LIKE 'distinction%' AND slot_date = ?", [day.isoformat()])}
        free = [sl for sl in SLOTS if sl[0] not in taken]
        if free:
            theme, hour = free[0]
            break
        day += timedelta(days=1)
    card = render(d)
    files = {}
    for kind, size in (("file", (2160, 2700)), ("tiktok", (1080, 1920))):
        out = io.BytesIO()
        award.cadre(card, size=size, seed=str(d["id"])).save(out, "JPEG", quality=90, optimize=True)
        files[kind] = f"{key}-{size[0]}.jpg"
        storage.store_media("social", files[kind], out.getvalue(), "image/jpeg")
    who = f"@{a['instagram']}" if a.get("instagram") else d["artist_name"]
    what = f"N°{d['rank']} du {d['chart_label']}" + (f" avec « {d['title']} »" if d.get("title") else "")
    caption = (f"🏆 Distinction officielle N° {int(d['id']):04d}\n\n"
               f"Félicitations {who} ! {what} en {month_label(d['period_key']).lower()}, "
               "d'après le classement Cauri Charts, calculé sur des données réelles.\n\n"
               "Chaque mois, le Top 5 de chaque classement reçoit sa distinction numérotée. Une seule fois par titre.")
    tags = "#CauriCharts #DistinctionOfficielle #MusiqueAfricaine #AfroMusic"
    if a.get("base_country"):
        tags += " #" + country_name(a["base_country"]).replace(" ", "").replace("’", "").replace("'", "")
    pid = db.insert("social_posts", {"slot_date": day.isoformat(), "theme": theme, "title": f"Distinction officielle · {d['artist_name']}"[:160],
                                     "caption": caption, "hashtags": tags, "facts": json.dumps({"key": key, "distinction": int(d["id"])}),
                                     "image_square": files["file"], "image_story": files["tiktok"],
                                     "carousel": json.dumps([files]), "video": None, "status": "approved"})
    post = db.one("SELECT * FROM social_posts WHERE id = ?", [pid])
    due = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    return f"post du {day.isoformat()} : " + buffer.schedule(post, due)


def deliver(d: dict) -> bool:
    """Envoie la distinction par e-mail si l'équipe a saisi le contact de l'artiste ; sinon rien (DM à la main)."""
    from core import mail
    a = db.one("SELECT contact_email FROM artists WHERE id = ?", [d["artist_id"]])
    to = (a or {}).get("contact_email")
    if not to or not mail.send(to, f"Distinction officielle Cauri Charts N° {int(d['id']):04d}", message(d)):
        return False
    db.run("UPDATE award_distinctions SET emailed_at = LOCALTIMESTAMP, status = 'sent', sent_at = COALESCE(sent_at, LOCALTIMESTAMP) WHERE id = ?", [d["id"]])
    try:
        announce(d)
    except Exception:  # noqa: BLE001 — le post est un bonus : l'envoi à l'artiste reste fait
        pass
    return True


def run() -> list:
    """Étape de la chaîne de nuit : distinctions des classements mensuels tout juste publiés, puis un e-mail à l'équipe."""
    lines, made = [], []
    for r in pending_runs():
        if budget.over():
            lines.append("budget atteint : la suite demain")
            break
        ids = generate(r)
        made += ids
        for did in ids:  # envoi direct aux artistes dont l'équipe connaît l'adresse
            deliver(db.one("SELECT * FROM award_distinctions WHERE id = ?", [did]))
        lines.append(f"{r['period_key']} {_label(r)[1]} : {len(ids)} distinction(s)")
    if made:
        try:
            from core import mail
            rows = db.all(f"SELECT id, rank, artist_name, title, chart_label, emailed_at FROM award_distinctions WHERE id IN ({', '.join(['?'] * len(made))}) ORDER BY id", made)
            mail.notify_admin(f"{len(made)} nouvelle(s) distinction(s) Cauri Charts",
                              "\n".join(f"N° {r['id']:04d} · N°{r['rank']} {r['chart_label']} · {r['artist_name']}" + (f" « {r['title']} »" if r["title"] else "")
                                        + (" · envoyée par e-mail" if r["emailed_at"] else " · à envoyer en DM")
                                        for r in rows) + f"\n\nCartes, fichiers d'impression et suivi des envois : {url('admin/distinctions')}")
        except Exception:  # noqa: BLE001 — l'e-mail ne doit jamais bloquer la nuit
            pass
    return lines or ["aucun nouveau classement mensuel publié"]
