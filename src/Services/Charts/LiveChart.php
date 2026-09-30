<?php

namespace Cauri\Services\Charts;

use Cauri\Core\Database;

/**
 * Classements des plateformes, affichés en attendant (puis à côté) des classements officiels hebdomadaires.
 * Chaque position rapporte des points sur 100 selon la taille du classement de la plateforme
 * (n° 1 d'un Top 200 = 100 points, dernier = 0,5). Artistes hors des pays couverts masqués.
 *
 * Modes (un par classement de la famille) :
 * - prime  : somme des points du dernier relevé de chaque plateforme (ou une seule plateforme, positions d'origine) ;
 * - buzz   : titres hors du Top du pays qui décollent sur les plateformes de découverte (Shazam, YouTube)
 *            + places gagnées depuis le relevé d'il y a 7 jours quand l'historique existe ;
 * - fresh  : comme prime, limité aux titres sortis depuis moins de 8 semaines (ou artistes émergents) ;
 * - icon   : points de tous les titres additionnés par artiste ;
 * - legend : points cumulés de tous les relevés quotidiens depuis le début.
 */
final class LiveChart
{
    public const SOURCES = [
        'apple_music'       => 'Apple Music',
        'deezer'            => 'Deezer',
        'shazam'            => 'Shazam',
        'youtube_trending'  => 'YouTube tendances',
        'youtube_discovery' => 'YouTube nouveaux clips',
        'deezer_popularity' => 'Popularité Deezer',
        'youtube_views'     => 'Vues YouTube',
    ];

    /** Plateformes qui mesurent la découverte (Buzz) plutôt que l'écoute installée. */
    /** Période demandée → fenêtre de relevés. */
    public const WINDOWS = ['latest' => 'latest', 'week' => 7, 'month' => 30, 'year' => 365, 'all' => 'all'];

    private const DISCOVERY = ['shazam', 'youtube_trending', 'youtube_discovery'];

    public function __construct(private Database $db)
    {
    }

    /** Plateformes disponibles pour ce pays (null = les cinq pays). */
    public function sources(?int $countryId): array
    {
        $params = [];
        $where = 'observed_on >= CURDATE() - INTERVAL 3 DAY';
        if ($countryId !== null) {
            $where .= ' AND country_id = ?';
            $params[] = $countryId;
        }
        $found = array_column($this->db->all("SELECT DISTINCT source FROM chart_observations WHERE $where", $params), 'source');
        return array_values(array_filter(array_keys(self::SOURCES), fn ($s) => in_array($s, $found, true)));
    }

    private const CACHE_DIR = '/storage/cache/live';
    private const CACHE_TTL = 1800; // 30 minutes ; vidé aussi à la fin de la chaîne quotidienne

    /**
     * Classement demandé, mis en cache 30 minutes (les données ne changent qu'une fois par jour).
     * @return array{rows:list<array>, day:?string, since:?string}
     */
    public function build(?int $countryId, ?string $source = null, int $limit = 100, string $mode = 'prime', int $topSize = 20, string $period = 'latest'): array
    {
        $file = BASE_PATH . self::CACHE_DIR . '/' . md5(serialize(func_get_args())) . '.json';
        if (is_file($file) && filemtime($file) > time() - self::CACHE_TTL) {
            $cached = json_decode((string) file_get_contents($file), true);
            if (is_array($cached)) {
                return $cached;
            }
        }
        $result = $this->compute($countryId, $source, $limit, $mode, $topSize, $period);
        $result['rows'] = $this->withSpotify($result['rows']);
        if (!is_dir(dirname($file))) {
            @mkdir(dirname($file), 0775, true);
        }
        @file_put_contents($file, json_encode($result, JSON_UNESCAPED_UNICODE));
        return $result;
    }

    /**
     * Écoutes Spotify déclarées par les artistes (captures Spotify for Artists vérifiées par l'équipe),
     * période se terminant il y a moins de 35 jours. Spotify ne publie pas ces chiffres autrement.
     */
    private function withSpotify(array $rows): array
    {
        $ids = array_values(array_filter(array_map(fn ($r) => empty($r['is_artist']) ? (int) $r['track_id'] : null, $rows)));
        if (!$ids) {
            return $rows;
        }
        $declared = [];
        foreach ($this->db->all(
            "SELECT track_id, SUM(streams) AS streams, MIN(period_start) AS start, MAX(period_end) AS end FROM submissions
             WHERE platform = 'spotify' AND status = 'validated' AND period_end >= CURDATE() - INTERVAL 35 DAY
               AND track_id IN (" . implode(',', array_fill(0, count($ids), '?')) . ') GROUP BY track_id',
            $ids
        ) as $d) {
            $declared[(int) $d['track_id']] = $d;
        }
        foreach ($rows as &$r) {
            $r['spotify_declared'] = isset($r['track_id']) ? ($declared[(int) $r['track_id']] ?? null) : null;
        }
        unset($r);
        return $rows;
    }

    public static function clearCache(): void
    {
        foreach (glob(BASE_PATH . self::CACHE_DIR . '/*.json') ?: [] as $f) {
            @unlink($f);
        }
    }

    private function compute(?int $countryId, ?string $source, int $limit, string $mode, int $topSize, string $period): array
    {
        // Fenêtre de temps : dernier relevé, 7 jours, 30 jours, 12 mois ou depuis le début (Legend)
        $window = $mode === 'legend' ? 'all' : (self::WINDOWS[$period] ?? 'latest');
        $rows = $this->observations($countryId, $source, $window);
        // Classement des cinq pays : chaque pays pèse autant. Les points d'un titre sont divisés par le nombre
        // de sources disponibles dans son pays, sinon un pays couvert par 5 plateformes (Ghana) écraserait
        // un pays qui n'en a qu'une ou deux (Togo, Bénin) à popularité égale.
        $perCountry = [];
        if ($countryId === null && $source === null) {
            foreach ($rows as $r) {
                $perCountry[$r['chart_country']][$r['source']] = true;
            }
        }
        $tracks = [];
        $day = null;
        $since = null;
        foreach ($rows as $r) {
            $day = max($day ?? $r['observed_on'], $r['observed_on']);
            $since = min($since ?? $r['observed_on'], $r['observed_on']);
            $size = max(1, (int) $r['size']);
            $points = 100 * ($size + 1 - (int) $r['position']) / $size;
            if ($perCountry) {
                $points /= count($perCountry[$r['chart_country']]);
            }
            $id = (int) $r['track_id'];
            $tracks[$id] ??= $r + ['points' => 0.0, 'discovery' => 0.0, 'seen' => [], 'best' => PHP_INT_MAX];
            $tracks[$id]['points'] += $points;
            if (in_array($r['source'], self::DISCOVERY, true)) {
                $tracks[$id]['discovery'] += $points;
            }
            $tracks[$id]['best'] = min($tracks[$id]['best'], (int) $r['position']);
            // Meilleure position atteinte sur la période, par plateforme et par pays
            $k = $r['source'] . $r['chart_country'];
            if (!isset($tracks[$id]['seen'][$k]) || $tracks[$id]['seen'][$k]['position'] > (int) $r['position']) {
                $tracks[$id]['seen'][$k] = ['source' => $r['source'], 'country' => $r['chart_country'], 'position' => (int) $r['position']];
            }
        }
        foreach ($tracks as &$t) {
            $t['seen'] = array_values($t['seen']);
            usort($t['seen'], fn ($a, $b) => $a['position'] <=> $b['position']);
        }
        unset($t);

        if ($source !== null && $countryId !== null && $mode === 'prime') {
            usort($tracks, fn ($a, $b) => $a['best'] <=> $b['best']);
            foreach ($tracks as &$t) {
                $t['rank'] = $t['best']; // vue d'une plateforme : positions d'origine
            }
            unset($t);
            return ['rows' => array_slice($tracks, 0, $limit), 'day' => $day, 'since' => $since];
        }

        $byPoints = fn ($a, $b) => [$b['points'], count($b['seen']), $a['best']] <=> [$a['points'], count($a['seen']), $b['best']];
        usort($tracks, $byPoints);

        if ($mode === 'buzz') {
            // Peu de données (Togo, Bénin) : on n'écarte que la première moitié
            $topSize = min($topSize, intdiv(count($tracks), 2));
            $top = array_flip(array_map(fn ($t) => (int) $t['track_id'], array_slice($tracks, 0, $topSize)));
            $rises = $this->rises($countryId, $day);
            $tracks = array_values(array_filter($tracks, fn ($t) => !isset($top[(int) $t['track_id']])));
            foreach ($tracks as &$t) {
                $t['rise'] = $rises[(int) $t['track_id']] ?? 0;
                $t['points'] = $t['discovery'] + $t['rise'];
            }
            unset($t);
            $tracks = array_values(array_filter($tracks, fn ($t) => $t['points'] > 0));
            usort($tracks, $byPoints);
        } elseif ($mode === 'fresh') {
            $limitDate = date('Y-m-d', strtotime('-56 days'));
            $tracks = array_values(array_filter($tracks, fn ($t) => ($t['release_date'] && $t['release_date'] >= $limitDate) || $t['is_emerging']));
        } elseif ($mode === 'icon') {
            $tracks = $this->byArtist($tracks);
        }

        foreach ($tracks as $i => &$t) {
            $t['rank'] = $i + 1;
        }
        unset($t);
        return ['rows' => array_slice($tracks, 0, $limit), 'day' => $day, 'since' => $since];
    }

    private function observations(?int $countryId, ?string $source, string|int $window): array
    {
        $params = [];
        $filter = '';
        if ($countryId !== null) {
            $filter .= ' AND o.country_id = ?';
            $params[] = $countryId;
        }
        if ($source !== null) {
            $filter .= ' AND o.source = ?';
            $params[] = $source;
        }
        // Tous les relevés (Legend) ou le dernier relevé de chaque couple plateforme × pays
        if (is_int($window)) {
            $filter .= ' AND o.observed_on >= CURDATE() - INTERVAL ' . $window . ' DAY';
        }
        $latest = $window !== 'latest' ? '' : "JOIN (SELECT source, country_id, MAX(observed_on) AS day FROM chart_observations
                    WHERE observed_on >= CURDATE() - INTERVAL 3 DAY GROUP BY source, country_id) d
               ON d.source = o.source AND d.country_id = o.country_id AND d.day = o.observed_on";
        return $this->db->all(
            "SELECT o.source, o.position, o.observed_on, oc.code AS chart_country, l.size,
                    t.id AS track_id, t.title, t.slug AS track_slug, t.cover_url, t.featuring, t.release_date,
                    a.id AS artist_id, a.name AS artist_name, a.slug AS artist_slug, a.image_url AS artist_image, a.status, a.is_emerging, a.spotify_id AS artist_spotify,
                    COALESCE(IF(a.status = 'active', ac.code, NULL), a.base_country, gc.code) AS artist_country
             FROM chart_observations o
             $latest
             JOIN (SELECT source, country_id, observed_on, MAX(position) AS size FROM chart_observations
                    GROUP BY source, country_id, observed_on) l
               ON l.source = o.source AND l.country_id = o.country_id AND l.observed_on = o.observed_on
             JOIN countries oc ON oc.id = o.country_id
             JOIN tracks t ON t.id = o.track_id
             JOIN artists a ON a.id = t.artist_id
             LEFT JOIN countries ac ON ac.id = a.submission_country_id
             LEFT JOIN countries gc ON gc.id = a.guessed_country_id
             WHERE a.status <> 'out_of_scope'$filter",
            $params
        );
    }

    /** Places gagnées (en points sur 100) entre le relevé d'il y a environ 7 jours et le dernier relevé. */
    private function rises(?int $countryId, ?string $day): array
    {
        if (!$day) {
            return [];
        }
        $params = [$day, $day, $day];
        $filter = '';
        if ($countryId !== null) {
            $filter = ' AND now.country_id = ?';
            $params[] = $countryId;
        }
        $rows = $this->db->all(
            "SELECT now.track_id, now.position AS pos, MIN(prev.position) AS prev_pos,
                    (SELECT MAX(position) FROM chart_observations s WHERE s.source = now.source AND s.country_id = now.country_id AND s.observed_on = now.observed_on) AS size
             FROM chart_observations now
             JOIN chart_observations prev ON prev.track_id = now.track_id AND prev.source = now.source AND prev.country_id = now.country_id
                  AND prev.observed_on BETWEEN ? - INTERVAL 8 DAY AND ? - INTERVAL 5 DAY
             WHERE now.observed_on = ?$filter
             GROUP BY now.track_id, now.source, now.country_id, now.position, now.observed_on",
            $params
        );
        $rises = [];
        foreach ($rows as $r) {
            $gain = (int) $r['prev_pos'] - (int) $r['pos'];
            if ($gain > 0) {
                $rises[(int) $r['track_id']] = ($rises[(int) $r['track_id']] ?? 0) + 100 * $gain / max(1, (int) $r['size']);
            }
        }
        return $rises;
    }

    /** Icon : un artiste = la somme des points de ses titres ; son meilleur titre et ses plateformes. */
    private function byArtist(array $tracks): array
    {
        $artists = [];
        foreach ($tracks as $t) {
            $id = (int) $t['artist_id'];
            if (!isset($artists[$id])) {
                $artists[$id] = $t + ['titles' => 0, 'top_title' => $t['title'], 'top_slug' => $t['track_slug']];
                $artists[$id]['points'] = 0.0;
                $artists[$id]['seen'] = [];
            }
            $artists[$id]['points'] += $t['points'];
            $artists[$id]['titles']++;
            foreach ($t['seen'] as $s) {
                $k = $s['source'] . $s['country'];
                if (!isset($artists[$id]['seen'][$k]) || $artists[$id]['seen'][$k]['position'] > $s['position']) {
                    $artists[$id]['seen'][$k] = $s;
                }
            }
        }
        foreach ($artists as &$a) {
            $a['seen'] = array_values($a['seen']);
            usort($a['seen'], fn ($x, $y) => $x['position'] <=> $y['position']);
            $a['is_artist'] = true;
        }
        unset($a);
        usort($artists, fn ($a, $b) => [$b['points'], $b['titles']] <=> [$a['points'], $a['titles']]);
        return array_values($artists);
    }
}
