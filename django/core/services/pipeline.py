"""Chaîne quotidienne complète (traduction de Services\\DailyPipeline), dans l'ordre où chaque étape a besoin de la précédente.

 L'essentiel d'abord : 1. classements des plateformes ; 2. relevé des vues ; 3. sources calculées ; 4. actualités ;
 7. le lundi : classement officiel (brouillon) ; 8. posts (lundi, mercredi, vendredi), Cauri Hebdo et Telegram (dimanche).
 Puis 10. enrichissement du catalogue (suivi, découverte, profils, pays, Deezer, chaînes et clips YouTube), chaque étape
 avec un budget de temps : la chaîne tient dans l'heure (offre gratuite de GitHub Actions : 2 000 minutes par mois).
 11. ménage en dernier.
Une étape en échec est journalisée et n'empêche pas les suivantes.
"""
import json
import time
from datetime import date

from core import budget, clock
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
from core.services import buffer, telegram
from core.services.social.generator import PostGenerator, purge_blob, purge_orphans


class DailyPipeline:
    def __init__(self, out=None):
        self.out = out
        self.report: list = []

    def run(self, force_weekly: bool = False, force_posts: bool = False, youtube_searches: int = 10) -> list:
        imp = ImportService()
        http = HttpClient(60)
        platform_sources = [k for k in imp.sources() if k not in COMPUTED]

        self._step("1. Classements des plateformes", lambda: imp.import_all(None, platform_sources))
        def collect():
            r = CollectService(clients()).run(clock.today().isoformat())
            return [f"{k} {json.dumps(v, ensure_ascii=False)}" for k, v in r.items()]
        self._step("2. Relevé des vues", collect)
        self._step("3. Sources calculées (popularité Deezer, vues YouTube)", lambda: imp.import_all(None, COMPUTED))
        self._step("4. Actualités", lambda: FeedImporter().run())

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
                lines = [f"{post['theme']} : {post['title']}" + (f" → {post['folder']}" if post.get("folder") else "")]
                if telegram.configured():
                    try:
                        lines.append("Telegram : " + telegram.send_post(post))
                    except Exception as exc:  # noqa: BLE001 — le post reste généré même si Telegram échoue
                        lines.append(f"Telegram : échec ({exc})")
                if buffer.configured():
                    # Instagram, Facebook, TikTok à 18 h (heure de Lomé) : annulable dans Buffer ou l'admin d'ici là
                    try:
                        lines.append("Buffer : " + buffer.schedule(post, buffer.evening(clock.today())))
                    except Exception as exc:  # noqa: BLE001
                        lines.append(f"Buffer : échec ({exc})")
                return lines
            self._step("8. Posts réseaux sociaux", posts)

        if weekday in (1, 3, 5):
            # Lundi, mercredi, vendredi : Cauri Matin (carrousel à 7 h, article, Telegram), après le post de 18 h qu'il annonce
            def matin():
                from datetime import datetime, timedelta, timezone
                from core.services.social import matin as M
                post = M.post(clock.today())
                if not post:
                    return ["pas de classement ce matin"]
                lines = [post["title"]]
                due = datetime.combine(clock.today(), datetime.min.time(), timezone.utc) + timedelta(hours=7)
                due = max(due, datetime.now(timezone.utc) + timedelta(minutes=20))  # nuit en retard : dès que possible
                if buffer.configured():
                    lines.append("Buffer : " + buffer.schedule(post, due))
                if telegram.configured():
                    lines.append("Telegram : " + telegram.send_post(post))
                return lines
            self._step("8 a. Cauri Matin", matin)

        if weekday in (2, 4):
            # Mardi et jeudi : portrait d'un grand artiste (bio, palmarès, chiffres, titres), à 18 h sur les réseaux
            def portrait():
                from core.services.social import portrait as P
                post = P.post(clock.today())
                if not post:
                    return ["aucun artiste avec assez de faits sourcés aujourd'hui"]
                lines = [post["title"]]
                if buffer.configured():
                    lines.append("Buffer : " + buffer.schedule(post, buffer.evening(clock.today())))
                return lines
            self._step("8 quater. Portrait d'artiste", portrait)

        if weekday == 7:
            # Dimanche : l'article de la semaine (Cauri Hebdo) dans Actualités, écrit à partir des chiffres réels
            def hebdo():
                from core.services import magazine
                from core.services.social import editorial
                f = magazine.facts()
                lines = [magazine.publish(f=f)]
                post = editorial.hebdo_post(f, clock.today())  # le magazine en carrousel, à 18 h sur les réseaux
                if post and buffer.configured():
                    lines.append("Buffer : " + buffer.schedule(post, buffer.evening(clock.today())))
                return lines
            self._step("8 ter. Cauri Hebdo (article et carrousel)", hebdo)

        if weekday == 7 and telegram.configured():
            # Dimanche : Top 10 de la semaine dans la chaîne Telegram (tendances tant qu'aucun classement officiel n'est publié) ;
            # avec les posts du lundi, mercredi et vendredi : 4 publications par semaine
            self._step("8 bis. Chaîne Telegram", lambda: [telegram.send_chart()])

        # Enrichissement du catalogue, après la publication : chaque étape a un budget de temps et reprend la nuit suivante
        self._step("10a. Liste de suivi", lambda: ArtistWatch(http).run(), 60)
        self._step("10b. Découverte d'artistes", lambda: ArtistDiscovery(http).run(), 240)

        def profiles():
            p = ArtistEnricher(http).run(150)
            return [f"{p['checked']} vérifiés, {p['found']} trouvés sur Deezer"]
        self._step("10c. Profils (photo, fans)", profiles, 120)

        def classify():
            c = ArtistClassifier(HttpClient(20), ai.make()).run(120)
            return [f"{c['active']} confirmés, {c['out_of_scope']} hors périmètre, {c['pending']} à vérifier (IA : {c['ai_calls']})"]
        self._step("10d. Pays des artistes", classify, 180)

        def deezer():
            r = DeezerTrackMatcher(http).run()
            return [f"{r['matched']} titres retrouvés sur {r['checked']}"]
        self._step("10e. Titres retrouvés sur Deezer (popularité, pochette)", deezer, 90)
        self._step("10f. Chaînes YouTube des artistes (tous leurs clips, audios, lyrics, lives)", lambda: YouTubeChannelSync(http).run(), 180)
        self._step("10g. Clips YouTube des titres restants (recherche titre par titre)",
                   lambda: [json.dumps(imp.match_youtube(youtube_searches), ensure_ascii=False)], 60)

        def photos():
            from core.services.imports.photos import ArtistPhotos
            return ArtistPhotos(HttpClient(30)).run(120)
        self._step("10h. Photos HD des artistes (Apple Music, Wikimedia Commons, YouTube, Deezer)", photos, 180)

        def releases():
            from core.services import artist_news
            return [artist_news.collect_youtube(), artist_news.collect_releases(150)]
        self._step("10k. Actu des artistes (nouveaux clips YouTube, sorties Deezer)", releases, 150)

        def stats():
            from core.services import analytics
            return [analytics.collect_post_metrics()]
        self._step("10i. Statistiques des publications (vues, portée, réactions)", stats)

        def control():
            from core.services import agents
            return agents.run_all()
        self._step("10j. Agents de contrôle (éditions, catalogue, publications, relecteur IA, pages)", control, 600)

        def cleanup():
            live_chart.clear_cache()
            return ["cache des classements vidé", f"{purge_orphans()} fichiers de posts abandonnés supprimés", purge_blob()]
        self._step("11. Ménage (cache, fichiers orphelins, Blob)", cleanup)
        try:
            from core.services import analytics
            analytics.record_run(self.report)  # historique des nuits (Admin > Analyses)
        except Exception:  # noqa: BLE001
            pass
        log_write("cron", "info", "pipeline quotidien", {"etapes": [[r["step"], r["ok"], round(r["seconds"], 1)] for r in self.report]})
        return self.report

    def _step(self, name: str, fn, seconds: int | None = None) -> None:
        start = time.time()
        self._say(f"▶ {name}" + (f" (budget {seconds // 60} min {seconds % 60:02d} s)" if seconds else ""))
        if seconds:
            budget.start(seconds)
        try:
            result = fn()
            lines = [str(x) for x in (result if isinstance(result, list) else [result])]
            ok = True
        except Exception as exc:  # noqa: BLE001
            log_write("pipeline", "error", f"{name} : {exc}")
            lines, ok = [f"ERREUR : {exc}"], False
        finally:
            budget.stop()
        for line in lines:
            self._say("   " + line)
        self.report.append({"step": name, "ok": ok, "seconds": time.time() - start, "lines": lines})

    def _say(self, line: str) -> None:
        if self.out:
            self.out(line)
