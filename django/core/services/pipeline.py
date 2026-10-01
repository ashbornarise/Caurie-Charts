"""Chaîne quotidienne complète (traduction de Services\\DailyPipeline), dans l'ordre où chaque étape a besoin de la précédente.

 1. classements des plateformes ; 2. liste de suivi et découverte ; 3. profils puis pays des artistes ;
 4. clips YouTube puis relevé des vues ; 5. sources calculées ; 6. actualités ;
 7. le lundi : classement officiel (brouillon) ; 8. lundi, mercredi, vendredi : posts ; 9. ménage.
Une étape en échec est journalisée et n'empêche pas les suivantes.
"""
import json
import time
from datetime import date

from core import clock
from core import conf, db
from core.services import ai, live_chart
from core.services.chart_service import ChartService
from core.services.charts import Period
from core.services.imports.channel_sync import YouTubeChannelSync
from core.services.imports.classifier import ArtistClassifier
from core.services.imports.discovery import ArtistDiscovery
from core.services.imports.matching import ArtistEnricher, DeezerTrackMatcher
from core.services.imports.service import COMPUTED, ImportService
from core.services.imports.watch import ArtistWatch
from core.services.news import FeedImporter
from core.services.platforms import CollectService, HttpClient, clients, log_write
from core.services.social.generator import PostGenerator, purge_orphans


class DailyPipeline:
    def __init__(self, out=None):
        self.out = out
        self.report: list = []

    def run(self, force_weekly: bool = False, force_posts: bool = False, youtube_searches: int = 10) -> list:
        imp = ImportService()
        http = HttpClient(60)
        platform_sources = [k for k in imp.sources() if k not in COMPUTED]

        self._step("1. Classements des plateformes", lambda: imp.import_all(None, platform_sources))
        self._step("2a. Liste de suivi", lambda: ArtistWatch(http).run())
        self._step("2b. Découverte d'artistes", lambda: ArtistDiscovery(http).run())

        def profiles():
            p = ArtistEnricher(http).run(150)
            return [f"{p['checked']} vérifiés, {p['found']} trouvés sur Deezer"]
        self._step("3a. Profils (photo, fans)", profiles)

        def classify():
            c = ArtistClassifier(HttpClient(20), ai.make()).run(120)
            return [f"{c['active']} confirmés, {c['out_of_scope']} hors périmètre, {c['pending']} à vérifier (IA : {c['ai_calls']})"]
        self._step("3b. Pays des artistes", classify)

        def deezer():
            r = DeezerTrackMatcher(http).run()
            return [f"{r['matched']} titres retrouvés sur {r['checked']}"]
        self._step("4a. Titres retrouvés sur Deezer (popularité, pochette)", deezer)
        self._step("4b. Chaînes YouTube des artistes (tous leurs clips, audios, lyrics, lives)", lambda: YouTubeChannelSync(http).run())
        self._step("4c. Clips YouTube des titres restants (recherche titre par titre)",
                   lambda: [json.dumps(imp.match_youtube(youtube_searches), ensure_ascii=False)])

        def collect():
            r = CollectService(clients()).run(clock.today().isoformat())
            return [f"{k} {json.dumps(v, ensure_ascii=False)}" for k, v in r.items()]
        self._step("4d. Relevé des vues", collect)
        self._step("5. Sources calculées (popularité Deezer, vues YouTube)", lambda: imp.import_all(None, COMPUTED))
        self._step("6. Actualités", lambda: FeedImporter().run())

        weekday = clock.today().isoweekday()
        if force_weekly or weekday == 1:
            def weekly():
                week = Period.last_completed_week(clock.today().isoformat())
                service, lines = ChartService(), []
                for r in db.all("SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order"):
                    res = service.compute_week(r["code"], week.start, None, None)
                    lines.append(f"{week.key} {r['code']} : {res['tracks_scored']} titres notés, {res['pending']} à vérifier")
                return lines
            self._step("7. Classement officiel de la semaine (brouillon à publier dans l'admin)", weekly)

        days = {int(k): v for k, v in (conf.get("ai.social.days") or {}).items()}
        theme = days.get(weekday)
        if force_posts or theme:
            def posts():
                # « rotation » : une rubrique parmi toutes (themes.py), la moins récemment publiée qui a des données
                generator = PostGenerator(ai.make())
                post = generator.generate_next() if (force_posts or theme == "rotation") else generator.generate(theme)
                if not post:
                    return ["aucune rubrique n’a assez de données réelles aujourd’hui"]
                return [f"{post['theme']} : {post['title']}" + (f" → {post['folder']}" if post.get("folder") else "")]
            self._step("8. Posts réseaux sociaux", posts)

        def cleanup():
            live_chart.clear_cache()
            return ["cache des classements vidé", f"{purge_orphans()} fichiers de posts abandonnés supprimés"]
        self._step("9. Ménage (cache, fichiers orphelins)", cleanup)
        log_write("cron", "info", "pipeline quotidien", {"etapes": [[r["step"], r["ok"], round(r["seconds"], 1)] for r in self.report]})
        return self.report

    def _step(self, name: str, fn) -> None:
        start = time.time()
        self._say(f"▶ {name}")
        try:
            result = fn()
            lines = [str(x) for x in (result if isinstance(result, list) else [result])]
            ok = True
        except Exception as exc:  # noqa: BLE001
            log_write("pipeline", "error", f"{name} : {exc}")
            lines, ok = [f"ERREUR : {exc}"], False
        for line in lines:
            self._say("   " + line)
        self.report.append({"step": name, "ok": ok, "seconds": time.time() - start, "lines": lines})

    def _say(self, line: str) -> None:
        if self.out:
            self.out(line)
