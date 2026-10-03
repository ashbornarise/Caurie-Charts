"""Distinctions officielles Cauri Charts : rares, mensuelles, tirées des classements mensuels publiés.

  qui      : le Top 5 du classement mensuel Afrique de l'Ouest et le N°1 mensuel de chaque pays (21 au plus par mois) ;
  rareté   : un titre n'est distingué qu'une seule fois par classement (index unique track_id + scope) ;
  numéro   : l'identifiant de la table (N° 0001…), jamais réutilisé : c'est l'archive des classements ouest-africains ;
  fichiers : la carte (JPG, sur le Blob, à envoyer à l'artiste) ; l'impression (PDF 8 × 10 po, 300 ppp, fond perdu),
             le calque de dorure et la version encadrée sont produits à la demande depuis l'admin.
"""
import io
import json

from core import budget, conf, db, storage
from core.helpers import country_name, url

TOP = {"prime-wa": 5, "prime": 1}
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


def run() -> list:
    """Étape de la chaîne de nuit : distinctions des classements mensuels tout juste publiés, puis un e-mail à l'équipe."""
    lines, made = [], []
    for r in pending_runs():
        if budget.over():
            lines.append("budget atteint : la suite demain")
            break
        ids = generate(r)
        made += ids
        lines.append(f"{r['period_key']} {_label(r)[1]} : {len(ids)} distinction(s)")
    if made:
        try:
            from core import mail
            rows = db.all(f"SELECT id, rank, artist_name, title, chart_label FROM award_distinctions WHERE id IN ({', '.join(['?'] * len(made))}) ORDER BY id", made)
            mail.notify_admin(f"{len(made)} nouvelle(s) distinction(s) Cauri Charts",
                              "\n".join(f"N° {r['id']:04d} · N°{r['rank']} {r['chart_label']} · {r['artist_name']}" + (f" « {r['title']} »" if r["title"] else "")
                                        for r in rows) + f"\n\nCartes, fichiers d'impression et suivi des envois : {url('admin/distinctions')}")
        except Exception:  # noqa: BLE001 — l'e-mail ne doit jamais bloquer la nuit
            pass
    return lines or ["aucun nouveau classement mensuel publié"]
