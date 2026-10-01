"""Chaîne Telegram.

  manage.py telegram --chats        chaînes où le bot est présent (pour trouver TELEGRAM_CHAT_ID)
  manage.py telegram --test         message d'essai dans la chaîne
  manage.py telegram                Top 10 Afrique de l'Ouest de la semaine (une seule fois par classement)
  manage.py telegram --pays=tg --force
"""
from django.core.management.base import BaseCommand

from core import env
from core.management.commands._cli import out, run
from core.services import telegram


class Command(BaseCommand):
    help = "Publie le classement dans la chaîne Telegram."

    def add_arguments(self, p):
        p.add_argument("--chats", action="store_true")
        p.add_argument("--test", action="store_true")
        p.add_argument("--pays", default="wa")
        p.add_argument("--force", action="store_true")

    def handle(self, *args, **o):
        def task():
            if o["chats"]:
                me = telegram.call("getMe")
                out(f"Bot : @{me.get('username')}. Ajoutez-le comme administrateur de la chaîne, publiez-y un message, puis relancez.")
                for c in telegram.chats():
                    out(f"  {c['id']}  {c['type']}  {c['title']}")
                return
            if o["test"]:
                telegram.call("sendMessage", {"chat_id": env.get("TELEGRAM_CHAT_ID"), "text": "✅ Cauri Charts est connecté à cette chaîne."})
                out("Message d'essai envoyé.")
                return
            out(telegram.send_chart(o["pays"], o["force"]))
        run("telegram", task)
