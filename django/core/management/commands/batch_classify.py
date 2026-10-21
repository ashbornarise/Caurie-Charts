"""Classification rapide des artistes pending via DeepSeek + Gemini (Google Search).

Envoie des lots de noms d'artistes aux deux IA pour déterminer rapidement s'ils sont ouest-africains.
Les deux réponses sont croisées : accord = confirmé, désaccord = pending pour le classifier classique.

  manage.py batch_classify
  manage.py batch_classify --limit=500 --batch-size=15
"""
import json
import sys
import time

from django.core.management.base import BaseCommand

from core import audit, db, env
from core.management.commands._cli import out, run
from core.repos import now_utc
from core.services import ai
from core.services.platforms import HttpClient, PlatformException

WEST_AFRICA = {"BJ", "BF", "CV", "CI", "GM", "GH", "GN", "GW", "LR", "ML", "MR", "NE", "NG", "SN", "SL", "TG"}

SYSTEM = (
    "Tu es un expert de la musique africaine. Pour chaque artiste de la liste, indique :\n"
    "- country: le code ISO à 2 lettres du pays où il mène principalement sa carrière musicale "
    "(pas le pays de distribution comme FR/US/GB, mais le pays de la scène : origine, public, langue, label local)\n"
    "- confidence: nombre de 0 à 1 (1 = certain, 0.5 = pas sûr)\n"
    "Attention : beaucoup d'artistes africains déclarent FR/US/GB comme pays sur les plateformes (distribution/revenus). "
    "Ce n'est PAS leur pays. Cherche le vrai pays de scène.\n"
    "Si tu ne connais pas l'artiste, mets confidence à 0.\n"
    "Réponds UNIQUEMENT par un tableau JSON : [{\"name\": \"...\", \"country\": \"XX\", \"confidence\": 0.9}, ...]"
)


def _build_prompt(batch):
    lines = []
    for a in batch:
        tracks = db.all("""SELECT DISTINCT t.title, c.code FROM chart_observations o
                           JOIN tracks t ON t.id = o.track_id JOIN countries c ON c.id = o.country_id
                           WHERE t.artist_id = ? ORDER BY c.code LIMIT 4""", [a["id"]])
        ctx = ", ".join(f"« {t['title']} » ({t['code']})" for t in tracks)
        lines.append(f"- {a['name']}" + (f" (titres : {ctx})" if ctx else ""))
    return "Artistes à classifier :\n" + "\n".join(lines)


def _parse_response(text):
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return []


def _ask_provider(client, prompt, label):
    try:
        resp = client.ask(SYSTEM, prompt, 4000, 3)
        results = _parse_response(resp["text"])
        if results:
            return results
        out(f"  {label} : réponse non parsable")
    except PlatformException as e:
        out(f"  {label} : erreur — {e}")
    return []


def classify_batch(batch, deepseek, gemini):
    prompt = _build_prompt(batch)
    ds_results = _ask_provider(deepseek, prompt, "DeepSeek") if deepseek else []
    time.sleep(1)
    gm_results = _ask_provider(gemini, prompt, "Google") if gemini else []

    ds_map = {r["name"].lower(): r for r in ds_results if isinstance(r, dict) and r.get("name")}
    gm_map = {r["name"].lower(): r for r in gm_results if isinstance(r, dict) and r.get("name")}

    covered = {r["code"]: r["id"] for r in db.all("SELECT id, code FROM countries WHERE is_active = 1")}
    confirmed, rejected, uncertain = 0, 0, 0

    for a in batch:
        key = a["name"].lower()
        ds = ds_map.get(key, {})
        gm = gm_map.get(key, {})

        ds_country = (ds.get("country") or "").upper()[:2]
        gm_country = (gm.get("country") or "").upper()[:2]
        ds_conf = float(ds.get("confidence") or 0)
        gm_conf = float(gm.get("confidence") or 0)

        if not ds_country and not gm_country:
            uncertain += 1
            continue

        agreed = ds_country == gm_country and ds_country
        best_country = ds_country if ds_conf >= gm_conf else gm_country
        best_conf = max(ds_conf, gm_conf)

        if agreed and best_conf >= 0.7:
            country = ds_country
            confidence = min(0.9, (ds_conf + gm_conf) / 2 + 0.1)
            source_label = "deepseek+google"
        elif best_conf >= 0.8:
            country = best_country
            confidence = min(0.85, best_conf)
            source_label = "deepseek" if ds_conf >= gm_conf else "google"
        else:
            uncertain += 1
            db.update("artists", {
                "origin_checked_at": now_utc(),
                "origin_note": f"IA incertaine : DeepSeek={ds_country or '?'}({ds_conf:.1f}), Google={gm_country or '?'}({gm_conf:.1f})",
            }, "id = :id", {"id": a["id"]})
            continue

        if country in covered:
            db.update("artists", {
                "status": "active",
                "submission_country_id": covered[country],
                "base_country": country,
                "origin_confidence": round(confidence, 2),
                "origin_source": source_label,
                "origin_note": f"DeepSeek={ds_country}({ds_conf:.1f}), Google={gm_country}({gm_conf:.1f})",
                "origin_checked_at": now_utc(),
            }, "id = :id", {"id": a["id"]})
            audit.log(None, "artist.batch_classify", "artist", int(a["id"]),
                      f"Confirmé {country} via {source_label} (conf={confidence:.2f})", {})
            confirmed += 1
        elif country not in WEST_AFRICA:
            db.update("artists", {
                "status": "out_of_scope",
                "base_country": country,
                "origin_confidence": round(confidence, 2),
                "origin_source": source_label,
                "origin_note": f"Hors Afrique de l'Ouest. DeepSeek={ds_country}({ds_conf:.1f}), Google={gm_country}({gm_conf:.1f})",
                "origin_checked_at": now_utc(),
            }, "id = :id", {"id": a["id"]})
            audit.log(None, "artist.batch_classify", "artist", int(a["id"]),
                      f"Hors périmètre {country} via {source_label}", {})
            rejected += 1
        else:
            uncertain += 1

    return {"confirmed": confirmed, "rejected": rejected, "uncertain": uncertain}


class Command(BaseCommand):
    help = "Classification rapide des artistes pending via DeepSeek + Gemini (Google Search)."

    def add_arguments(self, p):
        p.add_argument("--limit", type=int, default=300)
        p.add_argument("--batch-size", type=int, default=15)

    def handle(self, *args, **o):
        def task():
            http = HttpClient(120)
            deepseek = ai.DeepSeekClient(http)
            gemini = ai.GeminiClient(http)

            if not deepseek.is_available() and not gemini.is_available():
                out("Aucune IA disponible (DEEPSEEK_API_KEY et GEMINI_API_KEY absentes)")
                return

            avail = []
            if deepseek.is_available():
                avail.append("DeepSeek")
            if gemini.is_available():
                avail.append("Gemini/Google")
            out(f"IA disponibles : {', '.join(avail)}")

            artists = db.all(f"""SELECT a.id, a.name FROM artists a
                WHERE a.status = 'pending' AND a.origin_source IS NULL
                ORDER BY (SELECT COUNT(*) FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                          WHERE t.artist_id = a.id) DESC
                LIMIT {max(0, int(o['limit']))}""")
            out(f"Artistes à classifier : {len(artists)}")

            total = {"confirmed": 0, "rejected": 0, "uncertain": 0}
            bs = max(1, o["batch_size"])
            for i in range(0, len(artists), bs):
                batch = artists[i:i + bs]
                out(f"  Lot {i // bs + 1}/{(len(artists) + bs - 1) // bs} ({len(batch)} artistes)...")
                r = classify_batch(
                    batch,
                    deepseek if deepseek.is_available() else None,
                    gemini if gemini.is_available() else None,
                )
                for k in total:
                    total[k] += r[k]
                out(f"    → {r['confirmed']} confirmés, {r['rejected']} hors périmètre, {r['uncertain']} incertains")
                time.sleep(2)

            out(f"\nTotal : {total['confirmed']} confirmés, {total['rejected']} hors périmètre, {total['uncertain']} incertains")

        run("batch-classify", task)
