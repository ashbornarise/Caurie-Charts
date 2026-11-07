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
        p.add_argument("--week", help="Semaine ISO (ex. 2026-W42)")
        p.add_argument("--recul", type=int, default=0,
                       help="Sans --week : la dernière semaine terminée (0), celle d'avant (1), etc.")
        p.add_argument("--verifier-jour", action="store_true",
                       help="Vérifie seulement si aujourd'hui est le jour de publication de la dernière semaine "
                            "(mardi avant la bascule du 13/11/2026, vendredi ensuite) : code de sortie 3 sinon")
        p.add_argument("--country", help="Code pays (TG, GH, NG…) ; si absent, tous les pays prêts")
        p.add_argument("--clips-only", action="store_true",
                       help="Crée uniquement les clips N°1 (pas de publication ni de post)")
        p.add_argument("--sans-revue", action="store_true", help="Ne pas faire trancher les titres signalés par l'IA")
        p.add_argument("--auto", action="store_true",
                       help="Publication automatique : après la revue Google, les titres encore douteux ne bloquent pas")
        p.add_argument("--sans-envois", action="store_true",
                       help="Rattrapage d'une ancienne semaine : ni Telegram, ni clips, ni post officiel")

    def handle(self, *args, **o):
        from core import clock
        from core.services.charts import Period
        derniere = Period.last_completed_week(clock.today().isoformat())
        if o["verifier_jour"]:
            jour = derniere.publication_day()
            self.stdout.write(f"Semaine {derniere.key} : publication le {jour}")
            if clock.today().isoformat() != jour:
                raise SystemExit(3)
            return

        def task():
            week = o["week"]
            if not week:
                p = derniere
                for _ in range(max(0, o["recul"])):
                    p = p.previous()
                week = p.key
            out(f"Semaine {week}")

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
            debut = Period.from_key("week", week).start
            for code in countries:
                # Règle du fondateur : pas de classement officiel sous 8 artistes (pas de remplissage)
                artistes = int(db.value("""SELECT COUNT(DISTINCT t.artist_id) FROM weekly_scores w JOIN tracks t ON t.id = w.track_id
                                           JOIN countries c ON c.id = w.country_id
                                           WHERE c.code = ? AND w.week_start = ? AND w.score > 0""", [code, debut]) or 0)
                if not o["country"] and artistes < 8:
                    out(f"{code} : {artistes} artiste(s) seulement, pas de classement officiel (8 au moins)")
                    continue
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
                    n = service.publish(code, "week", week, 1, force=o["auto"])
                except Exception as exc:
                    out(f"{code} : {exc}")
                    continue
                if n and o["sans_envois"]:
                    publies.append(code)
                    out(f"{code} : {n} classement(s) publié(s) (rattrapage, sans envoi)")
                elif n:
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
            if o["sans_envois"]:
                return [f"{len(publies)} pays publié(s) : {', '.join(publies)}"] if publies else ["rien à publier"]
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
