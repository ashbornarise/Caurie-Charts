"""Durées de conservation de la politique de confidentialité (config/app.php, « retention »). Une fois par jour.

  manage.py purge
  manage.py purge --dry-run     affiche ce qui serait supprimé, sans rien toucher
"""
import json

from django.core.management.base import BaseCommand

from core import audit, conf, db, storage
from core.management.commands._cli import out, run
from core.services.imports.sources import months_ago


def before(months: int) -> str:
    return months_ago(months) + " 00:00:00"


class Command(BaseCommand):
    help = "Applique les durées de conservation des données personnelles."

    def add_arguments(self, p):
        p.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        def task():
            r, dry, report = conf.get("app.retention"), o["dry_run"], {}
            # Captures d'écran des déclarations traitées
            old = db.all("""SELECT id, screenshot_path FROM submissions WHERE status <> 'pending' AND reviewed_at < ?
                            AND screenshot_path <> 'supprime'""", [before(r["screenshots"])])
            for s in old:
                if not dry:
                    f = storage.upload_path(s["screenshot_path"] or "")
                    if f.is_file():
                        f.unlink()
                    db.update("submissions", {"screenshot_path": "supprime"}, "id = :id", {"id": s["id"]})
            report["captures"] = len(old)
            # Nom et e-mail des déclarants (les chiffres restent : ils servent à rejouer les classements)
            since = before(r["submission_contact"])
            report["declarants"] = (int(db.value("SELECT COUNT(*) FROM submissions WHERE created_at < ? AND contact_email <> 'supprime@invalid'", [since]))
                                    if dry else db.run("""UPDATE submissions SET contact_name = '(supprimé)', contact_email = 'supprime@invalid', ip_hash = NULL
                                                          WHERE created_at < ? AND contact_email <> 'supprime@invalid'""", [since]))
            for key, sql, months in (("messages", "FROM contact_messages WHERE status <> 'new' AND created_at < ?", r["contact_messages"]),
                                     ("connexions", "FROM login_attempts WHERE attempted_at < ?", r["login_attempts"]),
                                     ("inscrits_show", "FROM show_leads WHERE created_at < ?", r["show_leads"])):
                report[key] = int(db.value(f"SELECT COUNT(*) {sql}", [before(months)])) if dry else db.run(f"DELETE {sql}", [before(months)])
            # Adresses IP du journal d'audit (les actions restent tracées)
            since = before(r["audit_ip"])
            report["ip_journal"] = (int(db.value("SELECT COUNT(*) FROM audit_log WHERE ip IS NOT NULL AND created_at < ?", [since])) if dry
                                    else db.run("UPDATE audit_log SET ip = NULL WHERE ip IS NOT NULL AND created_at < ?", [since]))
            if not dry and sum(report.values()) > 0:
                audit.log(None, "privacy.purge", None, None, "manage.py purge", report)
            out(("[simulation] " if dry else "") + json.dumps(report, ensure_ascii=False))
        run("purge", task)
