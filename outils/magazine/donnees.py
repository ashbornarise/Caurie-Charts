"""Données d'un numéro du Cauri Charts Magazine, lues dans les classements PUBLIÉS d'une semaine (lecture seule).

    python outils/magazine/donnees.py 2026-W48        -> outils/magazine/donnees/s48.json

Reconstruit le 28/11/2026 : l'export d'origine vivait sur l'ancien PC (perdu le 26/11/2026). Même forme que s46.json,
que gen.py attend : semaine, debut, fin, wa (Top 20 Afrique de l'Ouest), pays (prime, buzz, fresh, icon), genres ;
plus, pour chaque section, la photo HD de l'artiste N°1 prise dans la banque (photo_n1), pour les pages d'ouverture.
"""
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "..", "django"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cauri.settings")
import django  # noqa: E402

django.setup()
from core import db, storage  # noqa: E402

SEMAINE = sys.argv[1] if len(sys.argv) > 1 else db.value(
    "SELECT MAX(period_key) FROM chart_runs WHERE period_type = 'week' AND status = 'published'")
BLOB = storage.blob_public_url()


def photo_artiste(artist_id) -> str:
    """La meilleure photo de la banque (Blob), sinon la photo HD du profil."""
    if not artist_id:
        return ""
    f = db.value("""SELECT fichier FROM artist_photos WHERE artist_id = ? ORDER BY COALESCE(score, 0.5) DESC, plan_large DESC, id DESC
                    LIMIT 1""", [artist_id])
    if f:
        return f"{BLOB}/media/artists/plans/{f}"
    return db.value("SELECT COALESCE(image_hd_url, image_url, '') FROM artists WHERE id = ?", [artist_id]) or ""


def entrees(run_id: int, n: int = 20) -> list:
    rows = db.all("""SELECT e.position, e.previous_position, e.peak_position, e.weeks_on_chart, e.artist_id AS e_artist,
                            t.title, t.featuring, t.cover_url, t.artist_id, a.name AS artist_name, a2.name AS icon_name,
                            COALESCE(a2.image_hd_url, a2.image_url) AS icon_photo
                     FROM chart_entries e LEFT JOIN tracks t ON t.id = e.track_id LEFT JOIN artists a ON a.id = t.artist_id
                     LEFT JOIN artists a2 ON a2.id = e.artist_id
                     WHERE e.chart_run_id = ? ORDER BY e.position LIMIT ?""", [run_id, n])
    out = []
    for r in rows:
        out.append({"position": int(r["position"]), "previous_position": r["previous_position"], "peak_position": r["peak_position"],
                    "weeks_on_chart": r["weeks_on_chart"], "title": r["title"] or "", "featuring": r["featuring"] or "",
                    "cover": r["cover_url"] or "", "artist_name": r["artist_name"] or r["icon_name"] or "",
                    "artist_id": r["artist_id"] or r["e_artist"], "photo": r["icon_photo"] or ""})
    return out


def run(code: str, pays_id) -> int | None:
    return db.value("""SELECT r.id FROM chart_runs r JOIN chart_types t ON t.id = r.chart_type_id
                       WHERE t.code = ? AND r.country_id IS NOT DISTINCT FROM ?::smallint AND r.period_type = 'week'
                       AND r.period_key = ? AND r.status = 'published'""", [code, pays_id, SEMAINE])


bornes = db.one("""SELECT MIN(period_start) AS debut, MAX(period_end) AS fin FROM chart_runs
                   WHERE period_type = 'week' AND period_key = ? AND status = 'published'""", [SEMAINE])
if not bornes or not bornes["debut"]:
    raise SystemExit(f"aucun classement publié pour {SEMAINE}")

wa_run = run("prime-wa", None)
wa = entrees(wa_run, 20) if wa_run else []
pays = []
for p in db.all("""SELECT DISTINCT c.id, c.code, c.name_fr FROM chart_runs r JOIN chart_types t ON t.id = r.chart_type_id
                   JOIN countries c ON c.id = r.country_id
                   WHERE t.code = 'prime' AND r.period_type = 'week' AND r.period_key = ? AND r.status = 'published'""", [SEMAINE]):
    prime = entrees(run("prime", p["id"]), 20)
    if not prime:
        continue
    x = {"code": p["code"], "nom": p["name_fr"], "prime": prime}
    for k in ("buzz", "fresh", "icon"):
        rid = run(k, p["id"])
        x[k] = entrees(rid, 3) if rid else []
    x["photo_n1"] = photo_artiste(prime[0]["artist_id"])
    pays.append(x)
genres = []
for g in db.all("""SELECT t.code, t.name, r.id FROM chart_runs r JOIN chart_types t ON t.id = r.chart_type_id
                   WHERE t.code LIKE 'g-%' AND r.country_id IS NULL AND r.period_type = 'week' AND r.period_key = ?
                   AND r.status = 'published' ORDER BY t.sort_order, t.code""", [SEMAINE]):
    e = entrees(g["id"], 5)
    if e:
        genres.append({"code": g["code"], "nom": g["name"], "entries": e})

D = {"semaine": SEMAINE, "debut": str(bornes["debut"])[:10], "fin": str(bornes["fin"])[:10], "wa": wa, "pays": pays, "genres": genres,
     "photo_wa": photo_artiste(wa[0]["artist_id"]) if wa else ""}
os.makedirs(os.path.join(ICI, "donnees"), exist_ok=True)
sortie = os.path.join(ICI, "donnees", f"s{int(SEMAINE.split('W')[1])}.json")
json.dump(D, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(sortie, "|", len(wa), "titres Afrique de l'Ouest |", len(pays), "pays |", len(genres), "genres")
