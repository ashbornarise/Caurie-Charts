"""Rattrapage du matin : publie ce que la chaîne de nuit a généré sans pouvoir le programmer (voir services/catchup.py).

  manage.py rattrapage
"""
from django.core.management.base import BaseCommand

from core.management.commands._cli import out, run


class Command(BaseCommand):
    help = "Rattrapage des posts du jour non publiés par la chaîne de nuit."

    def handle(self, *args, **o):
        def task():
            from core import clock, mail
            from core.services import catchup
            lines, problems = catchup.run()
            for line in lines + [f"PROBLÈME : {p}" for p in problems]:
                out(line)
            if lines != ["rien à rattraper"] or problems:
                # Un e-mail seulement s'il s'est passé quelque chose : la nuit a déjà envoyé son rapport
                title = f"rattrapage du {clock.today():%d/%m}" + (f" : {len(problems)} problème(s) restant(s)" if problems else " fait")
                if mail.configured():
                    mail.notify_admin(title, "\n".join(lines + [""] + [f"À faire : {p}" for p in problems]))
            if problems:
                out("::warning title=Rattrapage::" + " | ".join(problems)[:900])
        run("rattrapage", task)
