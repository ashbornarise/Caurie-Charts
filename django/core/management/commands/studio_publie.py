"""Publie les clips studio prêts (statut « pret ») sur tous les réseaux via Buffer.

  manage.py studio_publie                   tous les jobs prêts
  manage.py studio_publie --job=98          un seul job
  manage.py studio_publie --notify          notification Telegram après envoi
"""
import json

from django.core.management.base import BaseCommand

from core import db
from core.management.commands._cli import out, run


class Command(BaseCommand):
    help = "Publie les clips studio prêts sur les réseaux sociaux via Buffer."

    def add_arguments(self, p):
        p.add_argument("--job", type=int, help="ID d'un job précis (sinon tous les jobs prêts)")
        p.add_argument("--notify", action="store_true", help="Envoie une notification Telegram récapitulative")

    def handle(self, *args, **o):
        def task():
            from datetime import datetime, timedelta, timezone
            from core.services import buffer
            from core.studio import creer_tables, theme_libre

            creer_tables()
            if o["job"]:
                jobs = db.all("SELECT * FROM studio_jobs WHERE id = ? AND statut = 'pret'", [o["job"]])
            else:
                jobs = db.all("SELECT * FROM studio_jobs WHERE statut = 'pret' AND video IS NOT NULL ORDER BY id")

            if not jobs:
                out("Aucun job prêt à publier.")
                return ["0 clip(s)"]

            out(f"{len(jobs)} clip(s) prêt(s) à publier.")
            envoyes, erreurs = [], []

            for j in jobs:
                p = j["params"] if isinstance(j["params"], dict) else json.loads(j["params"] or "{}")
                maintenant = datetime.now(timezone.utc)
                accroche = str(p.get("accroche") or "").strip()
                fr = str(p.get("legende_fr") or accroche).strip()
                en_txt = str(p.get("legende_en") or "").strip()
                credit = str(p.get("credit") or "").strip()
                artiste = str(p.get("artiste") or "").strip()

                legende = fr + (f"\n\n🎥 Source : {credit}" if credit else "")
                tags = str(p.get("hashtags") or "").strip() or ("#CauriCharts" + (" #" + "".join(ch for ch in artiste if ch.isalnum()) if artiste else "") + " #Afrobeats #MusiqueAfricaine")

                faits = {
                    "kind": "format-clip",
                    "studio_job": j["id"],
                    "due": (maintenant + timedelta(minutes=2)).isoformat(),
                    "source": j["lien"],
                }
                if en_txt:
                    faits["en"] = {"title": accroche, "caption": en_txt + (f"\n\n🎥 Source: {credit}" if credit else "")}

                pid = db.insert("social_posts", {
                    "slot_date": maintenant.date().isoformat(),
                    "theme": theme_libre(j["id"], maintenant),
                    "title": accroche[:160] or "Vidéo Cauri Studio",
                    "caption": legende,
                    "hashtags": tags[:300],
                    "image_square": j["vignette"],
                    "image_story": j["vignette"],
                    "carousel": "[]",
                    "video": j["video"],
                    "status": "approved",
                    "facts": json.dumps(faits, ensure_ascii=False),
                })
                post = db.one("SELECT * FROM social_posts WHERE id = ?", [pid])
                try:
                    resultat = buffer.schedule(post, maintenant + timedelta(minutes=2))
                except Exception as exc:  # noqa: BLE001
                    resultat = f"échec ({exc})"

                recus = [r["reason"].split("-")[2] for r in db.all(
                    "SELECT reason FROM audit_log WHERE reason LIKE ?", [f"post-{pid}-%"])
                    if r["reason"].count("-") >= 2]

                if not recus:
                    db.run("DELETE FROM social_posts WHERE id = ?", [pid])
                    erreurs.append(f"Job {j['id']} : aucun réseau n'a accepté — {resultat}")
                    out(f"  Job {j['id']} ERREUR : {resultat}")
                    continue

                db.update("studio_jobs", {"statut": "envoye", "post_id": pid}, "id = :id", {"id": j["id"]})
                envoyes.append({"job": j["id"], "post": pid, "artiste": artiste, "accroche": accroche, "reseaux": sorted(set(recus))})
                out(f"  Job {j['id']} → post {pid} ({', '.join(sorted(set(recus)))})")

            resume = f"{len(envoyes)} envoyé(s), {len(erreurs)} erreur(s)"
            out(resume)

            if o["notify"] and envoyes:
                try:
                    from core.services.telegram import call as tg_call, configured as tg_ok
                    from core import env
                    if tg_ok():
                        lignes = [f"📤 <b>Studio : {len(envoyes)} clip(s) publié(s)</b>\n"]
                        for e in envoyes:
                            lignes.append(f"• {e['artiste']} — {e['accroche']} ({', '.join(e['reseaux'])})")
                        if erreurs:
                            lignes.append(f"\n⚠️ {len(erreurs)} erreur(s)")
                        tg_call("sendMessage", {
                            "chat_id": env.get("TELEGRAM_CHAT_ID"),
                            "text": "\n".join(lignes),
                            "parse_mode": "HTML",
                        })
                        out("Notification Telegram envoyée.")
                except Exception as exc:  # noqa: BLE001
                    out(f"Notification Telegram : {exc}")

            return [resume]
        run("studio-publie", task)
