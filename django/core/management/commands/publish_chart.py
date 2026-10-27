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
        p.add_argument("--sans-revue", action="store_true", help="Ne pas faire trancher les titres signalés par l'IA")

    def handle(self, *args, **o):
        def task():
            week = o["week"]

            if o["clips_only"]:
                from core.services.social import officiel
                from core import repos
                country = o["country"].upper() if o["country"] else None
                tops = repos.official_tops(1, tous_pays=True)
                if country:
                    tops = [t for t in tops if t["code"].lower() == country.lower()]
                out(f"{len(tops)} pays avec classement publié : {', '.join(t['code'] for t in tops)}")
                jobs = officiel.clips_podium(country, periode=None, rang_max=1)
                out(f"{len(jobs)} clip(s) N°1 créé(s) (attente PC)")
                return [f"{len(jobs)} clip(s)"]

            service = ChartService()
            if o["country"]:
                countries = [o["country"].upper()]
            else:
                countries = [r["code"] for r in db.all(
                    "SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order")]
            publies = []
            from core.services import revue_ia
            from core.services.charts import Period
            debut = Period.from_key("week", week).start
            for code in countries:
                # Titres signalés : Gemini + recherche Google tranchent d'abord ce qui est prouvé (27/10/2026)
                if not o["sans_revue"] and revue_ia.en_attente(code, debut):
                    try:
                        b = revue_ia.revoir(code, debut)
                        out(f"{code} revue IA : {len(b['valides'])} validé(s), {len(b['exclus'])} exclu(s), "
                            f"{len(b['attente'])} pour le fondateur")
                        for x in b["attente"]:
                            out(f"  à trancher : {x}")
                    except Exception as exc:  # noqa: BLE001
                        out(f"{code} revue IA impossible : {exc}")
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
