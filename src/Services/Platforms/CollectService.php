<?php

namespace Cauri\Services\Platforms;

use Cauri\Core\Database;
use Cauri\Core\Env;

/**
 * Relevé quotidien des compteurs (bin/collect.php).
 * File d'attente : les contenus dont le dernier relevé est le plus ancien passent en premier,
 * si bien qu'un quota épuisé un jour est rattrapé le lendemain sans rien oublier.
 */
final class CollectService
{
    public function __construct(private Database $db, private array $clients)
    {
    }

    public static function clients(Database $db, ?HttpClient $http = null): array
    {
        $http ??= new CurlHttpClient();
        return [
            'youtube'   => new YouTubeClient(Env::get('YOUTUBE_API_KEY'), $http, new QuotaStore($db), (int) Env::get('YOUTUBE_DAILY_QUOTA', '10000')),
            'spotify'   => new SpotifyClient(Env::get('SPOTIFY_CLIENT_ID'), Env::get('SPOTIFY_CLIENT_SECRET'), $http),
            'audiomack' => new ManualPlatformClient('audiomack', 'accès API sur demande, relevé manuel en attendant'),
            'boomplay'  => new ManualPlatformClient('boomplay', 'pas d\'API publique connue, relevé manuel'),
        ];
    }

    /** @return array rapport par plateforme */
    public function run(string $day): array
    {
        $report = [];
        foreach ($this->clients as $platform => $client) {
            if (!$client->isAvailable()) {
                $report[$platform] = ['status' => 'ignorée', 'raison' => $client instanceof ManualPlatformClient ? $client->reason() : 'identifiants absents du .env'];
                continue;
            }
            $report[$platform] = match ($platform) {
                'youtube' => $this->collectYouTube($client, $day),
                'spotify' => $this->collectSpotify($client, $day),
                default   => ['status' => 'non géré'],
            };
        }
        return $report;
    }

    /** Contenus à relever, les moins récemment relevés d'abord. */
    private function queue(string $platform, string $day): array
    {
        return $this->db->all(
            'SELECT tpi.id, tpi.external_id, MAX(s.captured_on) AS last_day
             FROM track_platform_ids tpi
             JOIN tracks t ON t.id = tpi.track_id AND t.is_active = 1
             JOIN artists a ON a.id = t.artist_id AND a.status <> \'out_of_scope\'
             LEFT JOIN snapshots s ON s.track_platform_id = tpi.id
             WHERE tpi.platform = ?
             GROUP BY tpi.id, tpi.external_id
             HAVING MAX(s.captured_on) IS NULL OR MAX(s.captured_on) < ?
             ORDER BY MAX(s.captured_on) IS NOT NULL, MAX(s.captured_on) ASC',
            [$platform, $day]
        );
    }

    private function collectYouTube(YouTubeClient $client, string $day): array
    {
        $queue = $this->queue('youtube', $day);
        $byExternal = array_column($queue, 'id', 'external_id');
        $stats = [];
        $status = 'ok';
        try {
            $stats = $client->fetchMany(array_keys($byExternal));
        } catch (QuotaExceededException $e) {
            $stats = $e->partial;
            $status = 'quota épuisé, reste en file pour demain';
        }
        foreach ($stats as $videoId => $s) {
            $this->saveSnapshot((int) $byExternal[$videoId], $day, $s);
        }
        return ['status' => $status, 'en_file' => count($queue), 'releves' => count($stats), 'introuvables' => count($queue) - count($stats), 'quota_restant' => $client->remainingQuota()];
    }

    private function collectSpotify(SpotifyClient $client, string $day): array
    {
        $done = 0;
        foreach ($this->queue('spotify', $day) as $row) {
            $s = $client->fetchTrackStats($row['external_id']);
            if ($s === null) {
                continue;
            }
            $this->saveSnapshot((int) $row['id'], $day, $s);
            if (!empty($s['image'])) {
                // Pochette officielle si le titre n'en a pas encore
                $this->db->run(
                    'UPDATE tracks t JOIN track_platform_ids tpi ON tpi.track_id = t.id SET t.cover_url = ? WHERE tpi.id = ? AND t.cover_url IS NULL',
                    [$s['image'], $row['id']]
                );
            }
            $done++;
        }
        return ['status' => 'ok', 'releves' => $done];
    }

    private function saveSnapshot(int $trackPlatformId, string $day, array $s): void
    {
        $this->db->run(
            'INSERT INTO snapshots (track_platform_id, captured_on, plays, likes, comments, popularity, source)
             VALUES (?, ?, ?, ?, ?, ?, \'api\')
             ON DUPLICATE KEY UPDATE plays = VALUES(plays), likes = VALUES(likes), comments = VALUES(comments), popularity = VALUES(popularity)',
            [$trackPlatformId, $day, $s['plays'], $s['likes'], $s['comments'], $s['popularity']]
        );
    }
}
