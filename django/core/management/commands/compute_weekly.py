"""Calcul hebdomadaire (lundi) : classements de la semaine précédente, en brouillon.

  manage.py compute_weekly                                   semaine terminée hier, tous les pays actifs
  manage.py compute_weekly --country=TG --week=2026-W39
  manage.py compute_weekly --from=2026-07-27 --to=2026-09-27  rattrapage de plusieurs semaines
  manage.py compute_weekly --week=2026-W38 --correction="Relevé Boomplay corrigé"
  manage.py compute_weekly ... --publish-clean               (local uniquement) publie les semaines sans signalement
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core import clock
from core import conf, db
from core.management.commands._cli import out, run
from core.services.chart_service import ChartService
from core.services.charts import Period, _d


class Command(BaseCommand):
    help = "Calcule les classements hebdomadaires (brouillons)."

    def add_arguments(self, p):
        p.add_argument("--country")
        p.add_argument("--week")
        p.add_argument("--from", dest="start")
        p.add_argument("--to", dest="end")
        p.add_argument("--correction")
        p.add_argument("--publish-clean", action="store_true")

    def handle(self, *args, **o):
        run("compute-weekly", lambda: self._task(o))

    def _task(self, o):
        service = ChartService()
        if o["publish_clean"] and conf.get("app.env") == "production":
            raise RuntimeError("--publish-clean est réservé au développement local : en production, la publication passe par l'admin.")
        countries = [o["country"].upper()] if o["country"] else [r["code"] for r in db.all("SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order")]
        if o["start"]:
            to = Period.week_of(o["end"] or (clock.today() - timedelta(days=1)).isoformat())
            weeks, p = [], Period.week_of(o["start"])
            while p.start <= to.start:
                weeks.append(p)
                p = Period.week_of((_d(p.start) + timedelta(days=7)).isoformat())
        elif o["week"]:
            weeks = [Period.week_from_key(o["week"])]
        else:
            weeks = [Period.last_completed_week(clock.today().isoformat())]
        for week in weeks:
            for code in countries:
                r = service.compute_week(code, week.start, o["correction"], None)
                summary = ", ".join(f"{k} {v}" for k, v in r["entries"].items())
                out(f"{week.key} {code} : {r['tracks_scored']} titres notés, {r['pending']} à vérifier ({summary})")
                if o["publish_clean"]:
                    if r["pending"] == 0:
                        service.publish(code, "week", week.key, 0)
                    else:
                        out(f"  -> {code} {week.key} reste en brouillon : signalements à traiter dans l'admin.")
