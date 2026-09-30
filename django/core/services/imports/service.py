"""Orchestration des imports, partagée par les commandes et l'admin (traduction d'Import\\ImportService)."""
import re
import time

from core import db, env
from core.services.imports import chart_importer
from core.services.imports.matching import YouTubeMatcher
from core.services.imports.sources import (AppleMusicChartSource, AudiomackChartSource, DeezerChartSource, DeezerPopularitySource,
                                           ShazamChartSource, YouTubeDiscoverySource, YouTubeTrendingSource, YouTubeViewsSource)
from core.services.platforms import (HttpClient, PlatformException, QuotaStore, YouTubeClient, YouTubeQuota, log_write)

# Sources calculées à partir des artistes suivis : à lancer après la vérification des artistes et le relevé
COMPUTED = ["deezer_popularity", "youtube_views"]


class ImportService:
    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient()

    def sources(self) -> dict:
        key = env.get("YOUTUBE_API_KEY", "")
        return {
            "apple_music": AppleMusicChartSource(self.http),
            "deezer": DeezerChartSource(self.http),
            "youtube_trending": YouTubeTrendingSource(self.http, key),
            "shazam": ShazamChartSource(self.http),
            "youtube_discovery": YouTubeDiscoverySource(self.http, key),
            # Calculés à partir des artistes suivis : rendent visibles les pays sans classement de plateforme
            "deezer_popularity": DeezerPopularitySource(self.http),
            "youtube_views": YouTubeViewsSource(),
            "audiomack": AudiomackChartSource(env.get("AUDIOMACK_CONSUMER_KEY", ""), env.get("AUDIOMACK_CONSUMER_SECRET", "")),
        }

    def import_all(self, countries: list | None = None, sources: list | None = None, user_id: int | None = None) -> list:
        countries = countries or [r["code"] for r in db.all("SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order")]
        report = []
        for key, source in self.sources().items():
            if sources and key not in sources:
                continue
            if not source.is_available():
                report.append(f"{key} : inactive (accès à obtenir, import CSV possible dans l'admin)")
                continue
            for code in countries:
                try:
                    # Sources YouTube : unités décomptées du quota partagé avant l'appel
                    cost = (1 if code in YouTubeTrendingSource.COUNTRIES else 0) if key == "youtube_trending" else \
                        100 * len(YouTubeDiscoverySource.QUERIES.get(code, [])) if key == "youtube_discovery" else 0
                    if cost > 0 and not YouTubeQuota.spend(cost):
                        report.append(f"{key} {code} : quota YouTube du jour atteint, reporté à demain")
                        continue
                    try:
                        snapshot = source.fetch(code)
                    except PlatformException as first:
                        # Délai dépassé ou erreur passagère (5xx) : un nouvel essai 5 secondes plus tard
                        if cost > 0 or not re.search(r"timed out|HTTP 5\d\d|échouée", str(first), re.I):
                            raise
                        time.sleep(5)
                        snapshot = source.fetch(code)
                    if snapshot is None:
                        report.append(f"{key} {code} : pas de classement publié pour ce pays")
                        continue
                    s = chart_importer.import_chart(code, key, snapshot, user_id)
                    report.append(f"{key} {code} {snapshot['observed_on']} : {s['rows']} lignes, {s['matched']} reconnus, "
                                  f"{s['new_tracks']} nouveaux titres, {s['new_artists']} nouveaux artistes")
                except Exception as exc:  # noqa: BLE001
                    log_write("import", "error", str(exc))
                    report.append(f"{key} {code} : ERREUR {exc}")
        return report

    def match_youtube(self, limit: int) -> dict:
        client = YouTubeClient(env.get("YOUTUBE_API_KEY", ""), self.http, QuotaStore(), YouTubeQuota.daily())
        if not client.is_available():
            return {"status": "ignoré : YOUTUBE_API_KEY absente du .env"}
        # Une recherche coûte 100 unités : on garde la réserve du relevé des vues
        affordable = max(0, YouTubeQuota.remaining() - YouTubeQuota.RESERVE) // 100
        return YouTubeMatcher(client).run(min(limit, affordable))
