<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;
use Cauri\Core\Env;
use Cauri\Services\Logger;
use Cauri\Services\Platforms\CurlHttpClient;
use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\QuotaStore;
use Cauri\Services\Platforms\YouTubeClient;

/** Orchestration des imports, partagée par la ligne de commande et l'admin. */
final class ImportService
{
    /** Sources calculées à partir des artistes suivis : à lancer après la vérification des artistes et le relevé. */
    public const COMPUTED = ['deezer_popularity', 'youtube_views'];

    private HttpClient $http;

    public function __construct(private Database $db, ?HttpClient $http = null)
    {
        $this->http = $http ?? new CurlHttpClient();
    }

    /** @return ChartSource[] */
    public function sources(): array
    {
        return [
            'apple_music'      => new AppleMusicChartSource($this->http),
            'deezer'           => new DeezerChartSource($this->http),
            'youtube_trending' => new YouTubeTrendingSource($this->http, Env::get('YOUTUBE_API_KEY')),
            'shazam'           => new ShazamChartSource($this->http),
            'youtube_discovery' => new YouTubeDiscoverySource($this->http, Env::get('YOUTUBE_API_KEY')),
            // Calculés à partir des artistes suivis : rendent visibles les pays sans classement de plateforme
            'deezer_popularity' => new DeezerPopularitySource($this->db, $this->http),
            'youtube_views'     => new YouTubeViewsSource($this->db),
            'audiomack'        =>new AudiomackChartSource(Env::get('AUDIOMACK_CONSUMER_KEY'), Env::get('AUDIOMACK_CONSUMER_SECRET')),
        ];
    }

    /** @return string[] lignes de rapport */
    public function importAll(?array $countries = null, ?array $sources = null, ?int $userId = null): array
    {
        $countries ??= array_column($this->db->all('SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order'), 'code');
        $importer = new ChartImporter($this->db);
        $report = [];
        foreach ($this->sources() as $key => $source) {
            if ($sources && !in_array($key, $sources, true)) {
                continue;
            }
            if (!$source->isAvailable()) {
                $report[] = "$key : inactive (accès à obtenir, import CSV possible dans l'admin)";
                continue;
            }
            foreach ($countries as $code) {
                try {
                    // Sources YouTube : unités décomptées du quota partagé avant l'appel
                    $cost = match ($key) {
                        'youtube_trending'  => in_array($code, YouTubeTrendingSource::COUNTRIES, true) ? 1 : 0,
                        'youtube_discovery' => 100 * count(YouTubeDiscoverySource::QUERIES[$code] ?? []),
                        default             => 0,
                    };
                    if ($cost > 0 && !\Cauri\Services\Platforms\YouTubeQuota::spend($this->db, $cost)) {
                        $report[] = "$key $code : quota YouTube du jour atteint, reporté à demain";
                        continue;
                    }
                    try {
                        $snapshot = $source->fetch($code);
                    } catch (\Cauri\Services\Platforms\PlatformException $first) {
                        // Délai dépassé ou erreur passagère du serveur (5xx) : un nouvel essai 5 secondes plus tard
                        if ($cost > 0 || !preg_match('/timed out|HTTP 5\d\d|échouée/i', $first->getMessage())) {
                            throw $first;
                        }
                        sleep(5);
                        $snapshot = $source->fetch($code);
                    }
                    if ($snapshot === null) {
                        $report[] = "$key $code : pas de classement publié pour ce pays";
                        continue;
                    }
                    $s = $importer->import($code, $key, $snapshot, $userId);
                    $report[] = sprintf('%s %s %s : %d lignes, %d reconnus, %d nouveaux titres, %d nouveaux artistes',
                        $key, $code, $snapshot['observed_on'], $s['rows'], $s['matched'], $s['new_tracks'], $s['new_artists']);
                } catch (\Throwable $e) {
                    Logger::error('import', $e);
                    $report[] = "$key $code : ERREUR " . $e->getMessage();
                }
            }
        }
        return $report;
    }

    public function matchYouTube(int $limit): array
    {
        $client = new YouTubeClient(Env::get('YOUTUBE_API_KEY'), $this->http, new QuotaStore($this->db), (int) Env::get('YOUTUBE_DAILY_QUOTA', '10000'));
        if (!$client->isAvailable()) {
            return ['status' => 'ignoré : YOUTUBE_API_KEY absente du .env'];
        }
        // Une recherche coûte 100 unités : on garde la réserve du relevé des vues
        $affordable = intdiv(max(0, \Cauri\Services\Platforms\YouTubeQuota::remaining($this->db) - \Cauri\Services\Platforms\YouTubeQuota::RESERVE), 100);
        return (new YouTubeMatcher($this->db, $client))->run(min($limit, $affordable));
    }
}
