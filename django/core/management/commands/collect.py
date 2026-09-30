"""Relevé quotidien des compteurs.

  manage.py collect
  manage.py collect --day=2026-09-28
"""
import json
from datetime import date

from django.core.management.base import BaseCommand

from core import clock
from core.management.commands._cli import out, run
from core.services.platforms import CollectService, clients, log_write


class Command(BaseCommand):
    help = "Relève les compteurs des plateformes."

    def add_arguments(self, p):
        p.add_argument("--day")

    def handle(self, *args, **o):
        def task():
            day = o["day"] or clock.today().isoformat()
            report = CollectService(clients()).run(day)
            for platform, r in report.items():
                out(platform.ljust(10) + " " + json.dumps(r, ensure_ascii=False))
            log_write("cron", "info", f"collect {day}", report)
        run("collect", task)
