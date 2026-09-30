<?php

namespace Cauri\Repositories;

use Cauri\Core\Database;
use Cauri\Core\Config;

/** Lectures publiques : seuls les classements publiés sont visibles. */
final class ChartRepository
{
    public function __construct(private Database $db)
    {
    }

    public function countries(bool $activeOnly = true): array
    {
        return $this->db->all('SELECT * FROM countries' . ($activeOnly ? ' WHERE is_active = 1' : '') . ' ORDER BY sort_order, code');
    }

    public function country(string $code): ?array
    {
        return $this->db->one('SELECT * FROM countries WHERE code = ? AND is_active = 1', [strtoupper($code)]);
    }

    /** N° 1 du dernier Prime Chart hebdomadaire publié de chaque pays : [code => entrée]. */
    public function numberOnes(): array
    {
        $rows = $this->db->all(
            "SELECT COALESCE(c.code, 'WA') AS code, t.title, t.slug AS track_slug, a.name AS artist_name
             FROM chart_runs r
             JOIN chart_types ct ON ct.id = r.chart_type_id AND ct.code IN ('prime', 'prime-wa')
             LEFT JOIN countries c ON c.id = r.country_id
             JOIN chart_entries e ON e.chart_run_id = r.id AND e.position = 1
             JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
             WHERE r.period_type = 'week' AND r.status = 'published'
               AND r.period_end = (SELECT MAX(r2.period_end) FROM chart_runs r2
                                   WHERE r2.country_id <=> r.country_id AND r2.chart_type_id = r.chart_type_id
                                     AND r2.period_type = 'week' AND r2.status = 'published')"
        );
        return array_column($rows, null, 'code');
    }

    public function latestRun(?int $countryId, string $chartCode, string $periodType): ?array
    {
        return $this->db->one(
            "SELECT r.*, ct.code AS chart_code, ct.kind FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
             WHERE r.country_id <=> ? AND ct.code = ? AND r.period_type = ? AND r.status = 'published' AND ct.is_public = 1
             ORDER BY r.period_end DESC LIMIT 1",
            [$countryId, $chartCode, $periodType]
        );
    }

    public function run(?int $countryId, string $chartCode, string $periodType, string $periodKey): ?array
    {
        return $this->db->one(
            "SELECT r.*, ct.code AS chart_code, ct.kind FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
             WHERE r.country_id <=> ? AND ct.code = ? AND r.period_type = ? AND r.period_key = ? AND r.status = 'published' AND ct.is_public = 1",
            [$countryId, $chartCode, $periodType, $periodKey]
        );
    }

    public function runById(int $id, bool $publishedOnly = true): ?array
    {
        return $this->db->one(
            "SELECT r.*, ct.code AS chart_code, ct.kind, COALESCE(c.code, 'WA') AS country_code, COALESCE(c.chart_size, 20) AS chart_size FROM chart_runs r
             JOIN chart_types ct ON ct.id = r.chart_type_id LEFT JOIN countries c ON c.id = r.country_id
             WHERE r.id = ?" . ($publishedOnly ? " AND r.status = 'published'" : ''),
            [$id]
        );
    }

    /** Historique des classements publiés (sélecteur de date). */
    public function publishedRuns(?int $countryId, string $chartCode, string $periodType, int $limit = 60): array
    {
        return $this->db->all(
            "SELECT r.id, r.period_key, r.period_start, r.period_end, r.is_provisional FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
             WHERE r.country_id <=> ? AND ct.code = ? AND r.period_type = ? AND r.status = 'published'
             ORDER BY r.period_end DESC LIMIT $limit",
            [$countryId, $chartCode, $periodType]
        );
    }

    public function entries(int $runId, ?int $limit = null): array
    {
        $entries = $this->db->all(
            'SELECT e.*, t.title, t.slug AS track_slug, t.featuring, t.cover_url, t.release_date,
                a.name AS artist_name, a.slug AS artist_slug, a.label_owner, ac.code AS artist_country
             FROM chart_entries e
             LEFT JOIN tracks t ON t.id = e.track_id
             LEFT JOIN artists a ON a.id = COALESCE(e.artist_id, t.artist_id)
             LEFT JOIN countries ac ON ac.id = a.submission_country_id
             WHERE e.chart_run_id = ? ORDER BY e.position' . ($limit ? ' LIMIT ' . (int) $limit : ''),
            [$runId]
        );
        return $entries ? $this->withSources($runId, $entries) : [];
    }

    /**
     * Ajoute à chaque entrée le détail public de ses chiffres sur la période du classement :
     * 'sources' => [plateforme => ['kind' => plays|views|declared|chart, 'value' => int|float]],
     * 'streams' (écoutes audio + déclarations vérifiées) et 'views' (vues YouTube).
     * Calculé depuis weekly_scores : semaine, mois, année et Legend (cumul depuis le début).
     */
    private function withSources(int $runId, array $entries): array
    {
        $run = $this->db->one(
            'SELECT r.country_id, r.period_type, r.period_start, r.period_end, ct.code
             FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id WHERE r.id = ?',
            [$runId]
        );
        if (!$run) {
            return $entries;
        }
        $isArtist = $entries[0]['track_id'] === null;
        $ids = array_values(array_filter(array_map(fn ($e) => (int) ($isArtist ? $e['artist_id'] : $e['track_id']), $entries)));
        if (!$ids) {
            return $entries;
        }
        [$from, $to] = $run['code'] === 'legend' ? ['1970-01-01', $run['period_end']]
            : ($run['period_type'] === 'week' ? [$run['period_start'], $run['period_start']] : [$run['period_start'], $run['period_end']]);
        $key = $isArtist ? 't.artist_id' : 'w.track_id';
        $params = [$from, $to];
        $country = '';
        if ($run['country_id'] !== null) {
            $country = ' AND w.country_id = ?';
            $params[] = (int) $run['country_id'];
        }
        $rows = $this->db->all(
            "SELECT $key AS id, w.breakdown FROM weekly_scores w JOIN tracks t ON t.id = w.track_id
             WHERE w.week_start BETWEEN ? AND ?$country AND w.review_status <> 'excluded'
               AND $key IN (" . implode(',', array_fill(0, count($ids), '?')) . ')',
            array_merge($params, $ids)
        );

        $depth = (int) Config::get('formula.chart_depth', 100);
        $totals = [];
        $chartWeeks = [];
        foreach ($rows as $row) {
            foreach (json_decode($row['breakdown'], true) ?: [] as $source => $b) {
                $delta = (float) ($b['delta'] ?? 0);
                if ($delta <= 0) {
                    continue;
                }
                if (str_starts_with($source, 'chart:')) {
                    // Points de position (profondeur + 1 − position, moyenne de la semaine) : on affiche la position moyenne
                    $platform = substr($source, 6);
                    $totals[$row['id']][$platform]['chart_sum'] = ($totals[$row['id']][$platform]['chart_sum'] ?? 0) + $delta;
                    $chartWeeks[$row['id']][$platform] = ($chartWeeks[$row['id']][$platform] ?? 0) + 1;
                    continue;
                }
                if (str_starts_with($source, 'declaration:')) {
                    if ((float) ($b['weight'] ?? 0) <= 0) {
                        continue; // déclaration non recoupée : non comptée, donc non affichée
                    }
                    $platform = substr($source, 12);
                    $totals[$row['id']][$platform]['declared'] = ($totals[$row['id']][$platform]['declared'] ?? 0) + $delta;
                    continue;
                }
                $kind = $source === 'youtube' ? 'views' : 'plays';
                $totals[$row['id']][$source][$kind] = ($totals[$row['id']][$source][$kind] ?? 0) + $delta;
            }
        }

        foreach ($entries as &$e) {
            $id = (int) ($isArtist ? $e['artist_id'] : $e['track_id']);
            $sources = [];
            $streams = 0;
            $views = 0;
            foreach ($totals[$id] ?? [] as $platform => $t) {
                if (isset($t['views'])) {
                    $views += (int) $t['views'];
                    $sources[$platform] = ['kind' => 'views', 'value' => (int) $t['views']];
                } elseif (isset($t['plays']) || isset($t['declared'])) {
                    $value = (int) (($t['plays'] ?? 0) + ($t['declared'] ?? 0));
                    $streams += $value;
                    $sources[$platform] = ['kind' => isset($t['plays']) ? 'plays' : 'declared', 'value' => $value];
                } elseif (isset($t['chart_sum'])) {
                    $avgPoints = $t['chart_sum'] / max(1, $chartWeeks[$id][$platform]);
                    $sources[$platform] = ['kind' => 'chart', 'value' => max(1, (int) round($depth + 1 - $avgPoints))];
                }
            }
            uasort($sources, fn ($a, $b) => [$a['kind'] === 'chart', -$a['value']] <=> [$b['kind'] === 'chart', -$b['value']]);
            $e['sources'] = $sources;
            $e['streams'] = $streams;
            $e['views'] = $views;
        }
        unset($e);
        return $entries;
    }

    public function artist(string $slug): ?array
    {
        return $this->db->one(
            'SELECT a.*, c.code AS country_code, tc.code AS top_country_code
             FROM artists a JOIN countries c ON c.id = a.submission_country_id LEFT JOIN countries tc ON tc.id = a.top_country_id
             WHERE a.slug = ? AND a.status <> \'out_of_scope\'',
            [$slug]
        );
    }

    /** Titres classés d'un artiste au Prime Chart hebdomadaire publié, avec leur meilleure position. */
    public function artistTracks(int $artistId): array
    {
        return $this->db->all(
            "SELECT t.id, t.title, t.slug, t.featuring, t.cover_url, t.release_date,
                MIN(e.position) AS peak, COUNT(e.id) AS weeks,
                (SELECT e2.position FROM chart_entries e2 JOIN chart_runs r2 ON r2.id = e2.chart_run_id
                  WHERE e2.track_id = t.id AND r2.chart_type_id = ct.id AND r2.period_type = 'week' AND r2.status = 'published'
                  ORDER BY r2.period_end DESC LIMIT 1) AS last_position
             FROM tracks t
             JOIN chart_types ct ON ct.code = 'prime'
             LEFT JOIN chart_runs r ON r.chart_type_id = ct.id AND r.period_type = 'week' AND r.status = 'published'
             LEFT JOIN chart_entries e ON e.chart_run_id = r.id AND e.track_id = t.id
             WHERE t.artist_id = ?
             GROUP BY t.id, t.title, t.slug, t.featuring, t.cover_url, t.release_date, ct.id
             ORDER BY MIN(e.position) IS NULL, MIN(e.position), t.release_date DESC",
            [$artistId]
        );
    }

    /**
     * Chiffres réels d'un artiste pour sa fiche : positions dans les classements des plateformes
     * (7 derniers jours), vues YouTube de ses clips suivis (dernier relevé et gain sur 7 jours), titres.
     */
    public function artistLive(int $artistId): array
    {
        $positions = $this->db->all(
            "SELECT o.source, c.code AS country, t.title, t.slug AS track_slug, MIN(o.position) AS best
             FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN countries c ON c.id = o.country_id
             WHERE t.artist_id = ? AND o.observed_on >= CURDATE() - INTERVAL 7 DAY
             GROUP BY o.source, c.code, t.id, t.title, t.slug
             ORDER BY MIN(o.position), o.source",
            [$artistId]
        );
        $videos = $this->db->all(
            "SELECT t.id AS track_id, p.url, p.kind,
                    (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id ORDER BY s.captured_on DESC LIMIT 1) AS views,
                    (SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id AND s.captured_on <= CURDATE() - INTERVAL 7 DAY
                      ORDER BY s.captured_on DESC LIMIT 1) AS views_week_ago,
                    (SELECT MAX(s.captured_on) FROM snapshots s WHERE s.track_platform_id = p.id) AS measured_on
             FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id
             WHERE t.artist_id = ? AND p.platform = 'youtube'",
            [$artistId]
        );
        $viewsByTrack = [];
        $total = 0;
        $week = 0;
        $measured = null;
        foreach ($videos as $v) {
            if ($v['views'] === null) {
                continue;
            }
            $viewsByTrack[(int) $v['track_id']] = ($viewsByTrack[(int) $v['track_id']] ?? 0) + (int) $v['views'];
            $total += (int) $v['views'];
            if ($v['views_week_ago'] !== null) {
                $week += max(0, (int) $v['views'] - (int) $v['views_week_ago']);
            }
            $measured = max($measured ?? $v['measured_on'], $v['measured_on']);
        }
        $tracks = $this->db->all(
            "SELECT t.id, t.title, t.slug, t.featuring, t.cover_url, t.release_date,
                    (SELECT MIN(o.position) FROM chart_observations o WHERE o.track_id = t.id) AS best_ever,
                    (SELECT o.source FROM chart_observations o WHERE o.track_id = t.id ORDER BY o.position, o.observed_on DESC LIMIT 1) AS best_source,
                    (SELECT c.code FROM chart_observations o JOIN countries c ON c.id = o.country_id WHERE o.track_id = t.id ORDER BY o.position, o.observed_on DESC LIMIT 1) AS best_country
             FROM tracks t WHERE t.artist_id = ? AND t.is_active = 1
             ORDER BY (SELECT MIN(o.position) FROM chart_observations o WHERE o.track_id = t.id) IS NULL,
                      (SELECT MIN(o.position) FROM chart_observations o WHERE o.track_id = t.id), t.release_date DESC",
            [$artistId]
        );
        foreach ($tracks as &$t) {
            $t['views'] = $viewsByTrack[(int) $t['id']] ?? null;
        }
        unset($t);
        return [
            'positions'    => $positions,
            'tracks'       => $tracks,
            'views_total'  => $videos ? $total : null,
            'views_week'   => $week ?: null,
            'measured_on'  => $measured,
            'charts_count' => count(array_unique(array_map(fn ($p) => $p['source'] . $p['country'], $positions))),
        ];
    }

    /**
     * Artistes confirmés les plus présents dans les classements des plateformes (7 derniers jours) :
     * nombre de classements où ils figurent et meilleure position. Visible dès qu'un artiste est confirmé,
     * avant même le premier classement Cauri Charts.
     */
    public function hotArtists(?int $countryId = null, int $limit = 12): array
    {
        $params = [];
        $filter = '';
        if ($countryId !== null) {
            $filter = ' AND a.submission_country_id = ?';
            $params[] = $countryId;
        }
        return $this->db->all(
            "SELECT a.id, a.name, a.slug, a.image_url, a.fans, c.code AS country_code,
                    COUNT(DISTINCT CONCAT(o.source, '-', o.country_id)) AS charts, MIN(o.position) AS best,
                    (SELECT o2.source FROM chart_observations o2 JOIN tracks t2 ON t2.id = o2.track_id
                      WHERE t2.artist_id = a.id AND o2.observed_on >= CURDATE() - INTERVAL 7 DAY ORDER BY o2.position LIMIT 1) AS best_source
             FROM artists a
             JOIN countries c ON c.id = a.submission_country_id
             LEFT JOIN tracks t ON t.artist_id = a.id
             LEFT JOIN chart_observations o ON o.track_id = t.id AND o.observed_on >= CURDATE() - INTERVAL 7 DAY
             WHERE a.status = 'active'$filter
             GROUP BY a.id, a.name, a.slug, a.image_url, a.fans, c.code
             ORDER BY COUNT(DISTINCT CONCAT(o.source, '-', o.country_id)) DESC, MIN(o.position) IS NULL, MIN(o.position), a.fans DESC
             LIMIT " . (int) $limit,
            $params
        );
    }

    /** Évolution hebdomadaire d'un artiste à l'Icon Chart. */
    public function artistIconHistory(int $artistId): array
    {
        return $this->db->all(
            "SELECT r.period_key, r.period_end, e.position FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
             JOIN chart_types ct ON ct.id = r.chart_type_id
             WHERE e.artist_id = ? AND ct.code = 'icon' AND r.status = 'published' ORDER BY r.period_end",
            [$artistId]
        );
    }

    public function track(string $slug): ?array
    {
        return $this->db->one(
            'SELECT t.*, a.name AS artist_name, a.slug AS artist_slug, a.label_owner, a.spotify_id AS artist_spotify, c.code AS country_code
             FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id
             WHERE t.slug = ? AND a.status <> \'out_of_scope\'',
            [$slug]
        );
    }

    /** Positions hebdomadaires au Prime Chart publié (courbe de la fiche titre). */
    public function trackPositions(int $trackId): array
    {
        return $this->db->all(
            "SELECT r.period_key, r.period_start, r.period_end, e.position, e.score, c.chart_size
             FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id JOIN chart_types ct ON ct.id = r.chart_type_id
             JOIN countries c ON c.id = r.country_id
             WHERE e.track_id = ? AND ct.code = 'prime' AND r.period_type = 'week' AND r.status = 'published'
             ORDER BY r.period_end",
            [$trackId]
        );
    }

    public function trackLinks(int $trackId): array
    {
        return $this->db->all('SELECT platform, url, kind, external_id FROM track_platform_ids WHERE track_id = ? AND url IS NOT NULL ORDER BY FIELD(platform, \'youtube\', \'audiomack\', \'boomplay\', \'spotify\', \'apple_music\', \'deezer\')', [$trackId]);
    }

    /** Semaines publiées (tous pays) pour lesquelles un titre ou plus a été exclu : liste publique des retraits. */
    public function exclusions(int $limit = 50): array
    {
        return $this->db->all(
            "SELECT tr.week_start, tr.reason, tr.created_at, t.title, t.slug, a.name AS artist_name, c.code AS country_code
             FROM track_reviews tr JOIN tracks t ON t.id = tr.track_id JOIN artists a ON a.id = t.artist_id
             JOIN countries c ON c.id = a.submission_country_id
             WHERE tr.decision = 'excluded' ORDER BY tr.week_start DESC LIMIT $limit"
        );
    }

    public function sitemapEntries(): array
    {
        return [
            'artists' => $this->db->all("SELECT slug, updated_at FROM artists WHERE status = 'active'"),
            'tracks'  => $this->db->all("SELECT DISTINCT t.slug FROM tracks t JOIN chart_entries e ON e.track_id = t.id JOIN chart_runs r ON r.id = e.chart_run_id AND r.status = 'published'"),
        ];
    }
}
