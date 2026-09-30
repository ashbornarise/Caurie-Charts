<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;

/**
 * Vues YouTube des clips suivis des artistes confirmés d'un pays, à partir des relevés quotidiens
 * (bin/collect.php) : aucun appel supplémentaire à YouTube.
 * - dès qu'un clip a un relevé d'au moins 6 jours plus tôt : classement par vues gagnées sur la période ;
 * - sinon (premiers jours) : vues totales des clips publiés depuis moins de 18 mois (les vieux succès
 *   ne doivent pas écraser l'actualité).
 */
final class YouTubeViewsSource implements ChartSource
{
    public function __construct(private Database $db, private int $size = 100)
    {
    }

    public function key(): string
    {
        return 'youtube_views';
    }

    public function isAvailable(): bool
    {
        return true;
    }

    public function fetch(string $countryCode): ?array
    {
        $clips = $this->db->all(
            "SELECT t.title, a.name AS artist, p.external_id, p.url, p.published_at,
                    (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id ORDER BY s.captured_on DESC LIMIT 1) AS views,
                    (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id AND s.captured_on <= CURDATE() - INTERVAL 6 DAY
                      ORDER BY s.captured_on DESC LIMIT 1) AS views_before
             FROM track_platform_ids p
             JOIN tracks t ON t.id = p.track_id
             JOIN artists a ON a.id = t.artist_id AND a.status = 'active'
             JOIN countries c ON c.id = a.submission_country_id AND c.code = ?
             WHERE p.platform = 'youtube'",
            [strtoupper($countryCode)]
        );
        if (!$clips) {
            return null;
        }
        $withHistory = array_filter($clips, fn ($c) => $c['views_before'] !== null);
        $recent = date('Y-m-d', strtotime('-18 months'));
        $scored = [];
        foreach ($clips as $c) {
            if ($c['views'] === null) {
                continue;
            }
            if ($withHistory) {
                $score = $c['views_before'] !== null ? (int) $c['views'] - (int) $c['views_before'] : null;
            } else {
                $score = !$c['published_at'] || $c['published_at'] >= $recent ? (int) $c['views'] : null;
            }
            if ($score !== null && $score > 0) {
                $scored[] = ['score' => $score] + $c;
            }
        }
        usort($scored, fn ($a, $b) => $b['score'] <=> $a['score']);
        $rows = [];
        foreach (array_slice($scored, 0, $this->size) as $i => $c) {
            $rows[] = [
                'position'    => $i + 1,
                'title'       => $c['title'],
                'artist'      => $c['artist'],
                'external_id' => $c['external_id'],
                'platform'    => 'youtube',
                'kind'        => 'clip',
                'url'         => $c['url'],
            ];
        }
        return $rows ? ['observed_on' => date('Y-m-d'), 'rows' => $rows] : null;
    }
}
