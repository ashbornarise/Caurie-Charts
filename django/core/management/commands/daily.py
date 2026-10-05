"""Chaîne quotidienne complète (une seule tâche planifiée, chaque nuit).

  manage.py daily
  manage.py daily --weekly        force le calcul du classement officiel de la semaine passée
  manage.py daily --posts         force la génération des trois posts
  manage.py daily --youtube=6     recherches de clips YouTube (100 unités de quota chacune)
"""
import os

from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run
from core.services.pipeline import DailyPipeline


class Command(BaseCommand):
    help = "Chaîne quotidienne complète."

    def add_arguments(self, p):
        p.add_argument("--weekly", action="store_true")
        p.add_argument("--posts", action="store_true")
        p.add_argument("--youtube", type=int, default=6)

    def handle(self, *args, **o):
        def task():
            from core.services import health
            pipeline = DailyPipeline(out)
            try:
                report = pipeline.run(o["weekly"], o["posts"], o["youtube"])
            except Exception as exc:
                # Arrêt complet : le rapport part quand même, avec les étapes déjà faites
                out(health.send(pipeline.report, f"{type(exc).__name__} : {exc}"))
                raise
            failed = [r for r in report if not r["ok"]]
            out("")
            out(f"Terminé : {len(report)} étapes, {len(failed)} en erreur" + (f" ({', '.join(r['step'] for r in failed)})" if failed else ""))
            out(health.send(report))
            if failed:
                # Sur GitHub : avertissement visible sur la page de la chaîne (le passage reste « réussi » pour ne pas
                # relancer toute la nuit ; le rattrapage du matin s'occupe des posts non publiés)
                out("::warning title=Chaîne de nuit::" + " | ".join(f"{r['step']} : {'; '.join(r['lines'])[:200]}" for r in failed)[:900])
                summary = os.environ.get("GITHUB_STEP_SUMMARY")
                if summary:
                    with open(summary, "a", encoding="utf-8") as fh:
                        fh.write(f"## {len(failed)} étape(s) en échec\n\n" + "".join(
                            f"- **{r['step']}** : {'; '.join(r['lines'])[:400]}\n" for r in failed))
        run("daily", task)
