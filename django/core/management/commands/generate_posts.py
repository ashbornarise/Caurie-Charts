"""Posts réseaux sociaux (lundi, mercredi, vendredi), en brouillon à relire.

  manage.py generate_posts                 rubrique du jour (rotation lundi, mercredi, vendredi)
  manage.py generate_posts --theme=artiste une rubrique précise (liste : core/services/social/themes.py)
  manage.py generate_posts --theme=rotation la prochaine rubrique de la rotation
  manage.py generate_posts --all           toutes les rubriques (aperçu)
"""
from datetime import date

from django.core.management.base import BaseCommand

from core import clock
from core import conf
from core.management.commands._cli import out, run
from core.services import ai
from core.services.social.generator import PostGenerator
from core.services.social.image import DIR
from core.services.social.themes import THEMES


class Command(BaseCommand):
    help = "Génère les posts réseaux sociaux."

    def add_arguments(self, p):
        p.add_argument("--theme")
        p.add_argument("--all", action="store_true")

    def handle(self, *args, **o):
        def task():
            days = {int(k): v for k, v in (conf.get("ai.social.days") or {}).items()}
            if o["all"]:
                themes = list(THEMES)
            elif o["theme"]:
                themes = [o["theme"]]
            else:
                themes = [t for t in [days.get(clock.today().isoweekday())] if t]
            if not themes:
                out("Pas de post prévu aujourd’hui (lundi, mercredi et vendredi).")
                return
            client = ai.make()
            generator = PostGenerator(client)
            for theme in themes:
                post = generator.generate_next() if theme == "rotation" else generator.generate(theme)
                if not post:
                    out(f"[{theme}] pas assez de données réelles pour ce thème, aucun post créé.")
                    continue
                out("─" * 60)
                out(f"[{theme}] {post['title']}" + ("" if client else " (texte modèle : ajouter GEMINI_API_KEY, gratuite, pour la rédaction IA)"))
                out(post["caption"])
                out(post["hashtags"])
                if post.get("folder"):
                    out("Dossier : " + post["folder"])
                for k in ("image_square", "image_story"):
                    if post[k]:
                        out(f"Visuel : {DIR / post[k]}")
        run("generate-posts", task)
