<?php

namespace Cauri\Services\Social;

use Cauri\Core\Database;

/**
 * Rassemble les faits RÉELS d'un post : classements publiés par Cauri Charts s'il y en a,
 * sinon positions relevées dans les classements des plateformes (Apple Music, Deezer, tendances YouTube).
 * Rien n'est inventé : l'IA ne reçoit que ces faits et doit s'y tenir.
 */
final class PostFacts
{
    private const SOURCE_NAMES = \Cauri\Services\Charts\LiveChart::SOURCES;

    public function __construct(private Database $db)
    {
    }

    public function for(string $theme): ?array
    {
        return match ($theme) {
            'classement' => $this->chart() ?? $this->platformTrends(),
            'artiste'    => $this->artistOfTheWeek(),
            'weekend'    => $this->weekend(),
            default      => null,
        };
    }

    /** Dernier classement Afrique de l'Ouest publié par Cauri Charts (Top 5, n° 1, plus forte montée). */
    private function chart(): ?array
    {
        $run = $this->db->one(
            "SELECT r.id, r.period_start, r.period_end FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
             WHERE ct.code = 'prime-wa' AND r.period_type = 'week' AND r.status = 'published'
               AND r.period_end >= CURDATE() - INTERVAL 10 DAY ORDER BY r.period_end DESC LIMIT 1"
        );
        if (!$run) {
            return null;
        }
        $top = $this->db->all(
            "SELECT t.id AS track_id, e.position, e.previous_position, e.weeks_on_chart, t.title, a.name AS artist, c.code AS country, a.image_url
             FROM chart_entries e JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
             JOIN countries c ON c.id = a.submission_country_id WHERE e.chart_run_id = ? ORDER BY e.position LIMIT 10",
            [$run['id']]
        );
        $climber = null;
        foreach ($top as $e) {
            if ($e['previous_position'] && $e['previous_position'] - $e['position'] > ($climber['gain'] ?? 0)) {
                $climber = $e + ['gain' => $e['previous_position'] - $e['position']];
            }
        }
        return [
            'kind'      => 'cauri_chart',
            'label'     => 'Prime Chart · Afrique de l’Ouest',
            'headline'  => 'Prime Chart Afrique de l’Ouest',
            'period'    => ['start' => $run['period_start'], 'end' => $run['period_end']],
            'top'       => array_slice($top, 0, 5),
            'climber'   => $climber,
            'image'     => $top[0]['image_url'] ?? null,
            'source'    => 'Classement Cauri Charts (méthodologie publique)',
        ];
    }

    /** Titres les mieux placés dans les classements des plateformes cette semaine, tous pays confondus. */
    private function platformTrends(): ?array
    {
        $rows = $this->db->all(
            "SELECT t.id AS track_id, t.title, a.name AS artist, a.image_url, COALESCE(a.base_country, gc.code) AS country,
                    COUNT(DISTINCT CONCAT(o.source, o.country_id)) AS charts, MIN(o.position) AS best,
                    GROUP_CONCAT(DISTINCT CONCAT(o.source, ':', oc.code, ':', o.position) ORDER BY o.position SEPARATOR ',') AS seen
             FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
             JOIN countries oc ON oc.id = o.country_id LEFT JOIN countries gc ON gc.id = a.guessed_country_id
             WHERE o.observed_on >= CURDATE() - INTERVAL 7 DAY AND a.status <> 'out_of_scope'
             GROUP BY t.id ORDER BY charts DESC, best LIMIT 5"
        );
        if (!$rows) {
            return null;
        }
        return [
            'kind'     => 'platform_trends',
            'label'    => 'Tendances de la semaine',
            'headline' => 'Les titres qui dominent les plateformes',
            'top'      => array_map(fn ($r) => array_merge($r, ['seen' => $this->seen($r['seen'])]), $rows),
            'image'    => $rows[0]['image_url'] ?? null,
            'source'   => 'Classements Apple Music, Deezer, Shazam et YouTube (7 derniers jours)',
        ];
    }

    /** Artiste le plus présent dans les classements des plateformes (plusieurs pays et sources). */
    private function artistOfTheWeek(): ?array
    {
        $a = $this->db->one(
            "SELECT a.id, a.name, a.slug, a.image_url, a.fans, COALESCE(a.base_country, gc.code) AS country,
                    COUNT(DISTINCT CONCAT(o.source, o.country_id)) AS charts, MIN(o.position) AS best
             FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
             LEFT JOIN countries gc ON gc.id = a.guessed_country_id
             WHERE o.observed_on >= CURDATE() - INTERVAL 7 DAY AND a.status = 'active'
               AND a.id NOT IN (SELECT CAST(JSON_UNQUOTE(JSON_EXTRACT(facts, '$.artist_id')) AS UNSIGNED) FROM social_posts
                                WHERE theme = 'artiste' AND slot_date >= CURDATE() - INTERVAL 42 DAY AND slot_date < CURDATE() AND JSON_VALID(facts))
             GROUP BY a.id ORDER BY charts DESC, best, a.fans DESC LIMIT 1"
        );
        if (!$a) {
            return null;
        }
        $tracks = $this->db->all(
            "SELECT t.id AS track_id, t.cover_url, t.title, GROUP_CONCAT(DISTINCT CONCAT(o.source, ':', c.code, ':', o.position) ORDER BY o.position SEPARATOR ',') AS seen
             FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN countries c ON c.id = o.country_id
             WHERE t.artist_id = ? AND o.observed_on >= CURDATE() - INTERVAL 7 DAY
             GROUP BY t.id ORDER BY MIN(o.position) LIMIT 3",
            [$a['id']]
        );
        return [
            'kind'      => 'artist',
            'label'     => 'Artiste de la semaine',
            'headline'  => 'Artiste de la semaine',
            'artist_id' => (int) $a['id'],
            'artist'    => ['name' => $a['name'], 'country' => $a['country'], 'deezer_fans' => $a['fans'] ? (int) $a['fans'] : null,
                            'profile' => '/artiste/' . $a['slug']],
            'tracks'    => array_map(fn ($t) => ['track_id' => (int) $t['track_id'], 'title' => $t['title'], 'image_url' => $t['cover_url'], 'seen' => $this->seen($t['seen'])], $tracks),
            'image'     => $a['image_url'],
            'source'    => 'Classements Apple Music, Deezer, Shazam et YouTube ; fans : Deezer',
        ];
    }

    /** Entrées récentes dans les classements des plateformes + actualités musicales citées. */
    private function weekend(): ?array
    {
        $new = $this->db->all(
            "SELECT t.id AS track_id, t.title, a.name AS artist, a.image_url, MIN(o.position) AS best,
                    GROUP_CONCAT(DISTINCT CONCAT(o.source, ':', c.code, ':', o.position) ORDER BY o.position SEPARATOR ',') AS seen
             FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
             JOIN countries c ON c.id = o.country_id
             WHERE o.observed_on >= CURDATE() - INTERVAL 7 DAY AND o.position <= 30 AND a.status <> 'out_of_scope'
               AND NOT EXISTS (SELECT 1 FROM chart_observations o2 WHERE o2.track_id = t.id AND o2.observed_on < CURDATE() - INTERVAL 7 DAY)
             GROUP BY t.id ORDER BY best LIMIT 5"
        );
        $news = $this->db->all(
            "SELECT title, source_name FROM news WHERE status = 'published' AND published_at >= NOW() - INTERVAL 7 DAY
             ORDER BY country_id IS NULL, published_at DESC LIMIT 3"
        );
        if (!$new && !$news) {
            return null;
        }
        return [
            'kind'     => 'weekend',
            'label'    => 'Spécial week-end',
            'headline' => 'Ce que l’Afrique de l’Ouest écoute ce week-end',
            'top'      => array_map(fn ($r) => array_merge($r, ['seen' => $this->seen($r['seen'])]), $new),
            'news'     => $news,
            'image'    => $new[0]['image_url'] ?? null,
            'source'   => 'Nouvelles entrées dans les classements des plateformes ; actualités : médias cités',
        ];
    }

    /** "apple_music:SN:3,deezer:CI:5" → [['platform' => 'Apple Music', 'country' => 'SN', 'position' => 3], ...] */
    private function seen(?string $raw): array
    {
        $out = [];
        foreach (array_slice(explode(',', (string) $raw), 0, 4) as $part) {
            [$source, $country, $pos] = array_pad(explode(':', $part), 3, null);
            if ($source) {
                $out[] = ['platform' => self::SOURCE_NAMES[$source] ?? $source, 'country' => $country, 'position' => (int) $pos];
            }
        }
        return $out;
    }
}
