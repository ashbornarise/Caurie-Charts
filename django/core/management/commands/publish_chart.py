"""Publication du classement officiel depuis la ligne de commande ou GitHub Actions.

  manage.py publish_chart --week=2026-W42                 tous les pays prêts (0 signalements)
  manage.py publish_chart --week=2026-W42 --country=TG    un seul pays
  manage.py publish_chart --week=2026-W42 --clips-only    clips N°1 de tous les pays publiés
"""
from django.core.management.base import BaseCommand

from core import db
from core.management.commands._cli import out, run
from core.services.chart_service import ChartService


class Command(BaseCommand):
    help = "Publie le classement officiel de la semaine pour les pays sans signalement."

    def add_arguments(self, p):
        p.add_argument("--week", required=True, help="Semaine ISO (ex. 2026-W42)")
        p.add_argument("--country", help="Code pays (TG, GH, NG…) ; si absent, tous les pays prêts")
        p.add_argument("--clips-only", action="store_true",
                       help="Crée uniquement les clips N°1 (pas de publication ni de post)")

    def handle(self, *args, **o):
        def task():
            week = o["week"]

            if o["clips_only"]:
                from core.services.social import officiel
                country = o["country"].upper() if o["country"] else None
                jobs = officiel.clips_podium(country, week, rang_max=1)
                return [f"{len(jobs)} clip(s) N°1 créé(s) (attente PC)"]

            service = ChartService()
            if o["country"]:
                countries = [o["country"].upper()]
            else:
                countries = [r["code"] for r in db.all(
                    "SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order")]
            publies = []
            for code in countries:
                try:
                    n = service.publish(code, "week", week, 1)
                except Exception as exc:
                    out(f"{code} : {exc}")
                    continue
                if n:
                    publies.append(code)
                    out(f"{code} : {n} classement(s) publié(s)")
                    from core.services import telegram
                    try:
                        out(f"{code} Telegram : {telegram.send_chart(code)}")
                    except Exception as exc:
                        out(f"{code} Telegram : échec ({exc})")
                    from core.services.social import officiel
                    try:
                        jobs = officiel.clips_podium(code, week)
                        if jobs:
                            out(f"{code} Studio : {len(jobs)} clip(s) du podium (attente PC)")
                    except Exception as exc:
                        out(f"{code} Studio clips : {exc}")
                else:
                    out(f"{code} : déjà publié ou pas de brouillon")
            from datetime import datetime, timedelta, timezone
            from core.services.social import officiel as O
            maintenant = datetime.now(timezone.utc)
            try:
                post = O.post(maintenant.date(), maintenant + timedelta(minutes=5))
                out(f"Post officiel : {'créé' if post else 'déjà fait ou pas de données'}")
            except Exception as exc:
                out(f"Post officiel : {exc}")
            return [f"{len(publies)} pays publié(s) : {', '.join(publies)}"] if publies else ["rien à publier"]
        run("publish-chart", task)
