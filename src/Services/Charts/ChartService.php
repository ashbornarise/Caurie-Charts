<?php

namespace Cauri\Services\Charts;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Repositories\FormulaRepository;
use Cauri\Services\Audit;

/**
 * Calcule, stocke et publie les classements à partir des relevés.
 * Chaque exécution enregistre la formule utilisée : un classement se rejoue à l'identique.
 * Aucune position n'est jamais écrite à la main.
 */
final class ChartService
{
    private array $chartTypes = [];

    public function __construct(private Database $db)
    {
        foreach ($db->all('SELECT id, code FROM chart_types') as $row) {
            $this->chartTypes[$row['code']] = (int) $row['id'];
        }
    }

    public function country(string $code): array
    {
        $country = $this->db->one('SELECT * FROM countries WHERE code = ?', [strtoupper($code)]);
        if (!$country) {
            throw new \InvalidArgumentException("Pays inconnu : $code");
        }
        return $country;
    }

    // ------------------------------------------------------------------
    // Semaine
    // ------------------------------------------------------------------

    /**
     * Calcule les scores de la semaine puis tous les classements hebdomadaires du pays.
     * @param string|null $correction raison obligatoire pour recalculer un classement déjà publié
     */
    public function computeWeek(string $countryCode, string $weekStart, ?string $correction = null, ?int $userId = null): array
    {
        $country = $this->country($countryCode);
        $period = Period::weekOf($weekStart);
        $formula = (new FormulaRepository($this->db))->effectiveFor($period->start);

        $items = $this->scoreWeek($country, $period, $formula);
        $ranker = new ChartRanker($formula);
        $size = (int) $country['chart_size'];
        $charts = Config::get('charts');
        $cid = (int) $country['id'];

        $prime = $ranker->prime($items, $this->size('prime', $size), $this->history('prime', $cid, 'week', $period->start));
        $results = ['prime' => $prime];
        $primeIds = array_column($prime, 'track_id');

        if ($charts['buzz']['computed']) {
            $results['buzz'] = $ranker->buzz($items, $primeIds, $this->size('buzz', $size), $this->history('buzz', $cid, 'week', $period->start));
        }
        if ($charts['fresh']['computed']) {
            $results['fresh'] = $ranker->fresh($items, $period->end, $this->size('fresh', $size), $this->history('fresh', $cid, 'week', $period->start));
        }
        if ($charts['icon']['computed']) {
            $results['icon'] = $ranker->icon($items, $this->size('icon', $size), $this->history('icon', $cid, 'week', $period->start));
        }
        if ($charts['legend']['computed']) {
            // Cumul des semaines déjà publiées, plus la semaine calculée
            $weeks = array_merge($this->publishedWeeks($cid, '1970-01-01', date('Y-m-d', strtotime($period->start . ' -1 day'))), [$period->start]);
            $legendItems = $this->cumulativeItems($cid, $weeks, $period->start);
            $results['legend'] = $ranker->cumulative($legendItems, $this->size('legend', $size), $this->history('legend', $cid, 'week', $period->start));
        }

        $this->db->transaction(function () use ($results, $cid, $period, $formula, $correction, $userId) {
            foreach ($results as $code => $entries) {
                $this->saveRun($code, $cid, $period, $formula, $entries, false, $correction, $userId);
            }
        });

        // Semaine publiée puis corrigée : le mois et l'année qui la contiennent suivent
        if ($correction !== null) {
            $this->refreshAggregates($countryCode, $period, $correction, $userId);
        }

        $pending = count(array_filter($items, fn ($i) => $i['review_status'] === 'pending' && $i['score'] > 0));
        return ['country' => $country['code'], 'period' => $period->key, 'tracks_scored' => count($items), 'pending' => $pending, 'entries' => array_map('count', $results)];
    }

    /** Scores de tous les titres du pays pour la semaine, enregistrés dans weekly_scores. */
    private function scoreWeek(array $country, Period $period, array $formula): array
    {
        $cid = (int) $country['id'];
        $activePlatforms = array_filter(array_map('trim', explode(',', $country['platforms'])));
        $calc = new ScoreCalculator($formula);

        $tracks = $this->db->all(
            'SELECT t.id, t.artist_id, t.release_date, a.is_emerging
             FROM tracks t JOIN artists a ON a.id = t.artist_id
             WHERE a.submission_country_id = ? AND t.is_active = 1 AND a.status = \'active\'',
            [$cid]
        );
        if (!$tracks) {
            return [];
        }

        $deltas = $this->platformDeltas($cid, $period);
        $chartPoints = $this->chartPoints($cid, $period, (int) ($formula['chart_depth'] ?? 100));
        $declarations = $this->declarations($cid, $period);
        $history = $this->scoreHistory($cid, $period->start, (int) $formula['anti_fraud']['spike_history_weeks']);
        $decisions = [];
        foreach ($this->db->all('SELECT track_id, decision FROM track_reviews WHERE week_start = ?', [$period->start]) as $r) {
            $decisions[(int) $r['track_id']] = $r['decision'];
        }

        $items = [];
        $now = gmdate('Y-m-d H:i:s');
        foreach ($tracks as $t) {
            $id = (int) $t['id'];
            $trackDeltas = array_intersect_key($deltas[$id]['plays'] ?? [], array_flip($activePlatforms));
            $trackDecl = $declarations[$id] ?? [];
            $trackChart = $chartPoints[$id] ?? [];
            if (!$trackDeltas && !$trackDecl && !$trackChart) {
                continue;
            }
            $trackHistory = $history[$id] ?? ['prev' => 0.0, 'list' => []];
            $result = $calc->score([
                'track_id'      => $id,
                'deltas'        => $trackDeltas,
                'youtube_likes' => $deltas[$id]['likes'] ?? null,
                'declarations'  => $trackDecl,
                'chart_points'  => $trackChart,
                'history'       => $trackHistory['list'],
                'decision'      => $decisions[$id] ?? null,
            ], $country['code']);

            $this->db->run(
                'INSERT INTO weekly_scores (track_id, country_id, week_start, score, sources_count, breakdown, flags, review_status, formula_version, computed_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE country_id = VALUES(country_id), score = VALUES(score), sources_count = VALUES(sources_count),
                   breakdown = VALUES(breakdown), flags = VALUES(flags), review_status = VALUES(review_status),
                   formula_version = VALUES(formula_version), computed_at = VALUES(computed_at)',
                [$id, $cid, $period->start, $result['score'], $result['sources_count'], json_encode($result['breakdown']),
                 json_encode($result['flags']), $result['review_status'], $formula['version'], $now]
            );

            $items[] = $result + [
                'track_id'     => $id,
                'artist_id'    => (int) $t['artist_id'],
                'prev_score'   => $trackHistory['prev'],
                'release_date' => $t['release_date'],
                'is_emerging'  => (bool) $t['is_emerging'],
            ];
        }
        return $items;
    }

    /**
     * Variation de la semaine par titre et plateforme : compteur du dernier relevé de la semaine
     * moins celui du dernier relevé avant la semaine. Sans relevé de départ, la variation n'est
     * calculable que si le contenu a été publié pendant la semaine (départ à zéro).
     * @return array [track_id => ['plays' => [platform => int], 'likes' => int|null]]
     */
    private function platformDeltas(int $countryId, Period $period): array
    {
        $rows = $this->db->all(
            'SELECT tpi.track_id, tpi.platform, tpi.published_at,
                (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on BETWEEN ? AND ? ORDER BY s.captured_on DESC LIMIT 1) AS end_plays,
                (SELECT likes FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on BETWEEN ? AND ? ORDER BY s.captured_on DESC LIMIT 1) AS end_likes,
                (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on < ? ORDER BY s.captured_on DESC LIMIT 1) AS base_plays,
                (SELECT likes FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on < ? ORDER BY s.captured_on DESC LIMIT 1) AS base_likes
             FROM track_platform_ids tpi
             JOIN tracks t ON t.id = tpi.track_id
             JOIN artists a ON a.id = t.artist_id
             WHERE a.submission_country_id = ? AND tpi.is_official = 1 AND tpi.platform <> \'spotify\'',
            [$period->start, $period->end, $period->start, $period->end, $period->start, $period->start, $countryId]
        );

        $out = [];
        foreach ($rows as $r) {
            if ($r['end_plays'] === null) {
                continue;
            }
            $newThisWeek = $r['published_at'] !== null && $r['published_at'] >= $period->start;
            if ($r['base_plays'] === null && !$newThisWeek) {
                continue; // premier relevé d'un contenu ancien : sert de point de départ
            }
            $id = (int) $r['track_id'];
            $delta = (int) $r['end_plays'] - (int) ($r['base_plays'] ?? 0);
            $out[$id]['plays'][$r['platform']] = ($out[$id]['plays'][$r['platform']] ?? 0) + $delta;
            if ($r['platform'] === 'youtube' && $r['end_likes'] !== null) {
                $likes = (int) $r['end_likes'] - (int) ($r['base_likes'] ?? 0);
                $out[$id]['likes'] = ($out[$id]['likes'] ?? 0) + $likes;
            }
        }
        return $out;
    }

    /**
     * Points de position de la semaine (v1.2) : pour chaque classement observé (source + pays),
     * moyenne sur les jours relevés de (profondeur + 1 - position), puis somme sur les pays.
     * Un titre présent dans les classements de plusieurs pays cumule donc ses points.
     * @return array [track_id => [source => float]]
     */
    private function chartPoints(int $countryId, Period $period, int $depth): array
    {
        $rows = $this->db->all(
            'SELECT o.track_id, o.source, o.country_id, AVG(GREATEST(0, ? + 1 - o.position)) AS pts
             FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN artists a ON a.id = t.artist_id
             WHERE a.submission_country_id = ? AND a.status = \'active\' AND o.observed_on BETWEEN ? AND ?
             GROUP BY o.track_id, o.source, o.country_id',
            [$depth, $countryId, $period->start, $period->end]
        );
        $out = [];
        foreach ($rows as $r) {
            $out[(int) $r['track_id']][$r['source']] = ($out[(int) $r['track_id']][$r['source']] ?? 0) + (float) $r['pts'];
        }
        return $out;
    }

    /** Déclarations validées qui chevauchent la semaine, ramenées à la part de la semaine. */
    private function declarations(int $countryId, Period $period): array
    {
        $rows = $this->db->all(
            'SELECT s.track_id, s.platform, s.streams, s.period_start, s.period_end
             FROM submissions s JOIN tracks t ON t.id = s.track_id JOIN artists a ON a.id = t.artist_id
             WHERE s.status = \'validated\' AND a.submission_country_id = ? AND s.period_start <= ? AND s.period_end >= ?',
            [$countryId, $period->end, $period->start]
        );
        $out = [];
        foreach ($rows as $r) {
            $streams = ScoreCalculator::prorate((int) $r['streams'], $r['period_start'], $r['period_end'], $period->start, $period->end);
            if ($streams > 0) {
                $out[(int) $r['track_id']][] = ['platform' => $r['platform'], 'streams' => $streams];
            }
        }
        return $out;
    }

    /**
     * Scores des N semaines précédentes, la plus récente en premier (semaines sans donnée ignorées),
     * et score de la semaine juste avant (0 si absente).
     * @return array [track_id => ['prev' => float, 'list' => float[]]]
     */
    private function scoreHistory(int $countryId, string $weekStart, int $weeks): array
    {
        $from = date('Y-m-d', strtotime("$weekStart -" . (7 * $weeks) . ' days'));
        $previousWeek = date('Y-m-d', strtotime("$weekStart -7 days"));
        $rows = $this->db->all(
            'SELECT track_id, week_start, score FROM weekly_scores WHERE country_id = ? AND week_start >= ? AND week_start < ? ORDER BY week_start DESC',
            [$countryId, $from, $weekStart]
        );
        $out = [];
        foreach ($rows as $r) {
            $id = (int) $r['track_id'];
            $out[$id] ??= ['prev' => 0.0, 'list' => []];
            $out[$id]['list'][] = (float) $r['score'];
            if ($r['week_start'] === $previousWeek) {
                $out[$id]['prev'] = (float) $r['score'];
            }
        }
        return $out;
    }

    /** Lundis des semaines dont le Prime Chart est publié, entre deux dates. */
    private function publishedWeeks(int $countryId, string $from, string $to): array
    {
        return array_column($this->db->all(
            "SELECT period_start FROM chart_runs WHERE chart_type_id = ? AND country_id = ? AND period_type = 'week'
               AND status = 'published' AND period_start BETWEEN ? AND ? ORDER BY period_start",
            [$this->chartTypes['prime'], $countryId, $from, $to]
        ), 'period_start');
    }

    /**
     * Totaux par titre sur une liste de semaines (Legend Chart, mois, année).
     * $lastWeek sert au départage (score avant la dernière semaine).
     */
    private function cumulativeItems(int $countryId, array $weeks, string $lastWeek): array
    {
        if (!$weeks) {
            return [];
        }
        $in = implode(', ', array_fill(0, count($weeks), '?'));
        $rows = $this->db->all(
            "SELECT ws.track_id, t.artist_id, t.release_date,
                SUM(ws.score) AS score, MAX(ws.sources_count) AS sources_count,
                SUM(CASE WHEN ws.week_start = ? THEN ws.score ELSE 0 END) AS last_week,
                MAX(ws.review_status = 'pending') AS has_pending
             FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id
             WHERE ws.country_id = ? AND ws.week_start IN ($in) AND ws.review_status <> 'excluded'
             GROUP BY ws.track_id, t.artist_id, t.release_date",
            array_merge([$lastWeek, $countryId], $weeks)
        );
        return array_map(fn ($r) => [
            'track_id'      => (int) $r['track_id'],
            'artist_id'     => (int) $r['artist_id'],
            'score'         => round((float) $r['score'], 2),
            'sources_count' => (int) $r['sources_count'],
            'prev_score'    => round((float) $r['score'] - (float) $r['last_week'], 2),
            'release_date'  => $r['release_date'],
            'is_emerging'   => false,
            'flags'         => [],
            'review_status' => $r['has_pending'] ? 'pending' : 'ok',
            'breakdown'     => [],
        ], $rows);
    }

    /**
     * Mémoire des classements précédents : position au classement immédiatement précédent,
     * meilleure position et nombre de périodes passées au classement.
     */
    private function history(string $chartCode, ?int $countryId, string $periodType, string $before): array
    {
        $typeId = $this->chartTypes[$chartCode];
        $kind = Config::get("charts.$chartCode.kind") === 'artists' ? 'artist_id' : 'track_id';
        $rows = $this->db->all(
            "SELECT e.$kind AS id, e.position, r.period_start
             FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
             WHERE r.chart_type_id = ? AND r.country_id <=> ? AND r.period_type = ? AND r.period_start < ?
             ORDER BY r.period_start",
            [$typeId, $countryId, $periodType, $before]
        );
        $lastStart = $this->db->value(
            'SELECT MAX(period_start) FROM chart_runs WHERE chart_type_id = ? AND country_id <=> ? AND period_type = ? AND period_start < ?',
            [$typeId, $countryId, $periodType, $before]
        );
        $out = [];
        foreach ($rows as $r) {
            $id = (int) $r['id'];
            $out[$id] ??= ['position' => null, 'peak' => PHP_INT_MAX, 'weeks' => 0];
            $out[$id]['peak'] = min($out[$id]['peak'], (int) $r['position']);
            $out[$id]['weeks']++;
            if ($r['period_start'] === $lastStart) {
                $out[$id]['position'] = (int) $r['position'];
            }
        }
        return $out;
    }

    private function size(string $chartCode, int $countrySize): int
    {
        return (int) (Config::get("charts.$chartCode.size") ?? $countrySize);
    }

    // ------------------------------------------------------------------
    // Mois et année (cumul des scores hebdomadaires)
    // ------------------------------------------------------------------

    /**
     * Mois ou année : somme des scores des semaines PUBLIÉES de la période (un brouillon n'y entre jamais).
     * Un mois n'est calculé qu'une fois toutes ses semaines publiées. L'année en cours est un cumul
     * provisoire, remis à jour à chaque semaine publiée.
     * @param bool $publish publie directement (toutes les semaines incluses sont déjà publiques)
     */
    public function computeAggregate(string $countryCode, Period $period, ?string $correction = null, ?int $userId = null, bool $publish = false): ?array
    {
        $country = $this->country($countryCode);
        $cid = (int) $country['id'];
        $weeks = $this->publishedWeeks($cid, $period->start, $period->end);
        if (!$weeks) {
            return null;
        }
        $provisional = count($weeks) < count($period->weekStarts());
        if ($period->type === 'month' && $provisional) {
            return null;
        }
        $lastWeek = end($weeks);
        $items = $this->cumulativeItems($cid, $weeks, $lastWeek);

        // Score de la période précédente, pour le départage
        $prev = $period->previous();
        $prevTotals = [];
        foreach ($this->db->all(
            'SELECT track_id, SUM(score) AS s FROM weekly_scores WHERE country_id = ? AND week_start BETWEEN ? AND ? AND review_status <> \'excluded\' GROUP BY track_id',
            [$cid, $prev->start, $prev->end]
        ) as $r) {
            $prevTotals[(int) $r['track_id']] = (float) $r['s'];
        }
        foreach ($items as &$item) {
            $item['prev_score'] = $prevTotals[$item['track_id']] ?? 0.0;
        }
        unset($item);

        $formula = (new FormulaRepository($this->db))->effectiveFor($lastWeek);
        $entries = (new ChartRanker($formula))->cumulative($items, (int) $country['chart_size'], $this->history('prime', $cid, $period->type, $period->start));
        $this->db->transaction(function () use ($cid, $period, $formula, $entries, $provisional, $correction, $userId, $publish) {
            // Le cumul provisoire de l'année se met à jour sans correction : il ne contient que des semaines publiées
            $this->saveRun('prime', $cid, $period, $formula, $entries, $provisional, $correction, $userId, $period->type === 'year');
            if ($publish) {
                $this->db->run(
                    "UPDATE chart_runs SET status = 'published', published_at = COALESCE(published_at, ?), published_by = COALESCE(published_by, ?)
                     WHERE chart_type_id = ? AND country_id = ? AND period_type = ? AND period_key = ?",
                    [gmdate('Y-m-d H:i:s'), $userId, $this->chartTypes['prime'], $cid, $period->type, $period->key]
                );
            }
        });
        return ['country' => $country['code'], 'period' => $period->key, 'provisional' => $provisional, 'entries' => count($entries)];
    }

    private function refreshAggregates(string $countryCode, Period $week, ?string $correction, ?int $userId): void
    {
        $month = Period::month($week->monthKey());
        $monthExists = $this->db->value(
            'SELECT r.id FROM chart_runs r JOIN countries c ON c.id = r.country_id WHERE c.code = ? AND r.chart_type_id = ? AND r.period_type = \'month\' AND r.period_key = ?',
            [$countryCode, $this->chartTypes['prime'], $month->key]
        );
        if ($monthExists) {
            $this->computeAggregate($countryCode, $month, $correction, $userId, true);
        }
        $this->computeAggregate($countryCode, Period::year(substr($week->end, 0, 4)), null, $userId, true);
        $this->computeRegionalWeek($week, $userId);
    }

    /** Après la publication d'une semaine : mois terminé et année en cours, publiés automatiquement. */
    private function afterWeekPublished(string $countryCode, Period $week, ?int $userId): void
    {
        $month = Period::month($week->monthKey());
        $monthRun = $this->db->one(
            'SELECT r.status FROM chart_runs r JOIN countries c ON c.id = r.country_id WHERE c.code = ? AND r.chart_type_id = ? AND r.period_type = \'month\' AND r.period_key = ?',
            [$countryCode, $this->chartTypes['prime'], $month->key]
        );
        if (!$monthRun || $monthRun['status'] === 'draft') {
            $this->computeAggregate($countryCode, $month, null, $userId, true); // ne fait rien tant que le mois est incomplet
        }
        $this->computeAggregate($countryCode, Period::year(substr($week->end, 0, 4)), null, $userId, true);
        $this->computeRegionalWeek($week, $userId);
    }

    // ------------------------------------------------------------------
    // Classement régional des cinq pays (page d'accueil)
    // ------------------------------------------------------------------

    /**
     * Semaine régionale : tous les titres des cinq pays classés par leur score de la semaine
     * (le même score que les classements nationaux), avec les mêmes règles de classement.
     * Seuls entrent les pays dont la semaine est publiée ; le total est publié quand tous l'ont été.
     */
    public function computeRegionalWeek(Period $week, ?int $userId = null): ?array
    {
        if (empty($this->chartTypes['prime-wa']) || !Config::get('charts.prime-wa.computed')) {
            return null;
        }
        $countries = (int) $this->db->value('SELECT COUNT(*) FROM countries WHERE is_active = 1');
        $published = array_column($this->db->all(
            "SELECT r.country_id FROM chart_runs r JOIN countries c ON c.id = r.country_id AND c.is_active = 1
             WHERE r.chart_type_id = ? AND r.period_type = 'week' AND r.period_key = ? AND r.status = 'published'",
            [$this->chartTypes['prime'], $week->key]
        ), 'country_id');
        if (!$published) {
            return null;
        }
        $in = implode(', ', array_fill(0, count($published), '?'));
        $previousWeek = date('Y-m-d', strtotime($week->start . ' -7 days'));
        $rows = $this->db->all(
            "SELECT ws.track_id, t.artist_id, t.release_date, ws.score, ws.sources_count, ws.breakdown,
                (SELECT p.score FROM weekly_scores p WHERE p.track_id = ws.track_id AND p.week_start = ?) AS prev_score
             FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id
             WHERE ws.week_start = ? AND ws.country_id IN ($in) AND ws.review_status <> 'excluded'",
            array_merge([$previousWeek, $week->start], $published)
        );
        $items = array_map(fn ($r) => [
            'track_id'      => (int) $r['track_id'],
            'artist_id'     => (int) $r['artist_id'],
            'score'         => (float) $r['score'],
            'sources_count' => (int) $r['sources_count'],
            'prev_score'    => (float) ($r['prev_score'] ?? 0),
            'release_date'  => $r['release_date'],
            'is_emerging'   => false,
            'flags'         => [],
            'review_status' => 'ok',
            'breakdown'     => json_decode((string) $r['breakdown'], true) ?: [],
        ], $rows);
        $complete = count($published) === $countries;
        $formula = (new FormulaRepository($this->db))->effectiveFor($week->start);
        $entries = (new ChartRanker($formula))->prime(
            $items,
            (int) Config::get('charts.prime-wa.size', 20),
            $this->history('prime-wa', null, 'week', $week->start)
        );
        $charts = $published;
        $this->db->transaction(function () use ($week, $formula, $entries, $complete, $userId) {
            $this->saveRun('prime-wa', null, $week, $formula, $entries, !$complete, null, $userId, true);
            if ($complete) {
                $this->publishRegional($week);
            }
        });
        if ($complete) {
            $this->computeRegionalAggregate(Period::month($week->monthKey()), $userId);
            $this->computeRegionalAggregate(Period::year(substr($week->end, 0, 4)), $userId);
        }
        return ['period' => $week->key, 'countries' => count($charts), 'published' => $complete, 'entries' => count($entries)];
    }

    /** Mois ou année régional : somme des scores hebdomadaires des cinq pays sur les semaines régionales publiées. */
    public function computeRegionalAggregate(Period $period, ?int $userId = null): ?array
    {
        $typeId = $this->chartTypes['prime-wa'];
        $rows = $this->db->all(
            "SELECT ws.track_id, t.artist_id, SUM(ws.score) AS score, MAX(ws.sources_count) AS countries
             FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id
             JOIN chart_runs r ON r.chart_type_id = ? AND r.country_id IS NULL AND r.period_type = 'week'
                AND r.status = 'published' AND r.period_start = ws.week_start
             WHERE ws.week_start BETWEEN ? AND ? AND ws.review_status <> 'excluded'
             GROUP BY ws.track_id, t.artist_id",
            [$typeId, $period->start, $period->end]
        );
        $weeks = (int) $this->db->value(
            "SELECT COUNT(*) FROM chart_runs WHERE chart_type_id = ? AND country_id IS NULL AND period_type = 'week' AND status = 'published' AND period_start BETWEEN ? AND ?",
            [$typeId, $period->start, $period->end]
        );
        $provisional = $weeks < count($period->weekStarts());
        if (!$rows || ($period->type === 'month' && $provisional)) {
            return null;
        }
        $totals = [];
        foreach ($rows as $r) {
            $totals[(int) $r['track_id']] = ['score' => (float) $r['score'], 'artist_id' => (int) $r['artist_id'], 'countries' => (int) $r['countries']];
        }
        $formula = (new FormulaRepository($this->db))->effectiveFor($period->end);
        $entries = (new ChartRanker($formula))->summedPoints($totals, (int) Config::get('charts.prime-wa.size', 20), $this->history('prime-wa', null, $period->type, $period->start));
        $this->db->transaction(function () use ($period, $formula, $entries, $provisional, $userId) {
            $this->saveRun('prime-wa', null, $period, $formula, $entries, $provisional, null, $userId, true);
            $this->publishRegional($period);
        });
        return ['period' => $period->key, 'entries' => count($entries), 'provisional' => $provisional];
    }

    private function publishRegional(Period $period): void
    {
        $this->db->run(
            "UPDATE chart_runs SET status = 'published', published_at = COALESCE(published_at, ?)
             WHERE chart_type_id = ? AND country_id IS NULL AND period_type = ? AND period_key = ?",
            [gmdate('Y-m-d H:i:s'), $this->chartTypes['prime-wa'], $period->type, $period->key]
        );
    }

    // ------------------------------------------------------------------
    // Enregistrement, publication, décisions
    // ------------------------------------------------------------------

    /**
     * @param bool $refresh mise à jour normale d'un cumul provisoire publié (année en cours) : pas de correction exigée
     */
    private function saveRun(string $chartCode, ?int $countryId, Period $period, array $formula, array $entries, bool $provisional, ?string $correction, ?int $userId, bool $refresh = false): void
    {
        $typeId = $this->chartTypes[$chartCode];
        $existing = $this->db->one(
            'SELECT id, status FROM chart_runs WHERE chart_type_id = ? AND country_id <=> ? AND period_type = ? AND period_key = ?',
            [$typeId, $countryId, $period->type, $period->key]
        );
        $now = gmdate('Y-m-d H:i:s');
        $fields = [
            'period_start'        => $period->start,
            'period_end'          => $period->end,
            'formula_version'     => (int) $formula['version'],
            'formula_json'        => json_encode($formula, JSON_UNESCAPED_UNICODE),
            'methodology_version' => (string) Config::get('app.methodology_version'),
            'is_provisional'      => $provisional ? 1 : 0,
            'computed_at'         => $now,
        ];

        if ($existing) {
            $runId = (int) $existing['id'];
            if ($existing['status'] === 'published' && !($refresh && $correction === null)) {
                if ($correction === null || trim($correction) === '') {
                    throw new \RuntimeException("Classement déjà publié ($chartCode {$period->key}) : une correction motivée est obligatoire.");
                }
                $fields['correction_note'] = $correction;
                $fields['corrected_at'] = $now;
                Audit::log($userId, 'chart.correct', 'chart_run', $runId, $correction);
            }
            $this->db->update('chart_runs', $fields, 'id = :id', ['id' => $runId]);
            $this->db->run('DELETE FROM chart_entries WHERE chart_run_id = ?', [$runId]);
        } else {
            $runId = $this->db->insert('chart_runs', $fields + [
                'chart_type_id' => $typeId,
                'country_id'    => $countryId,
                'period_type'   => $period->type,
                'period_key'    => $period->key,
                'status'        => 'draft',
            ]);
        }

        foreach ($entries as $e) {
            $flags = $e['flags'];
            if ($e['review_status'] === 'pending') {
                $flags[] = 'pending_review';
            }
            $this->db->insert('chart_entries', [
                'chart_run_id'      => $runId,
                'position'          => $e['position'],
                'track_id'          => $e['track_id'],
                'artist_id'         => $e['artist_id'],
                'score'             => $e['score'],
                'previous_position' => $e['previous_position'],
                'peak_position'     => $e['peak_position'],
                'weeks_on_chart'    => $e['weeks_on_chart'],
                'sources_count'     => $e['sources_count'],
                'growth_pct'        => $e['growth_pct'],
                'flags'             => json_encode(array_values(array_unique($flags))),
                'details'           => json_encode($e['details']),
            ]);
        }
    }

    /** Nombre de titres à vérifier (signalements bloquants sans décision) pour un pays et une semaine. */
    public function pendingCount(int $countryId, string $weekStart): int
    {
        return (int) $this->db->value(
            'SELECT COUNT(*) FROM weekly_scores WHERE country_id = ? AND week_start = ? AND review_status = \'pending\' AND score > 0',
            [$countryId, $weekStart]
        );
    }

    /**
     * Publie ensemble tous les classements hebdomadaires d'un pays. Le mois (s'il est complet)
     * et le cumul de l'année suivent automatiquement : ils ne contiennent que des semaines publiées.
     */
    public function publish(string $countryCode, string $periodType, string $periodKey, int $userId, ?string $ip = null): int
    {
        if ($periodType !== 'week') {
            throw new \RuntimeException('Les mois et les années se publient automatiquement avec leurs semaines.');
        }
        $country = $this->country($countryCode);
        $cid = (int) $country['id'];
        $period = Period::fromKey($periodType, $periodKey);

        $pending = $this->pendingCount($cid, $period->start);
        if ($pending > 0) {
            throw new \RuntimeException("$pending titre(s) à vérifier : validez ou excluez-les avant de publier.");
        }

        $count = $this->db->run(
            'UPDATE chart_runs SET status = \'published\', published_at = ?, published_by = ?
             WHERE country_id = ? AND period_type = ? AND period_key = ? AND status = \'draft\'',
            [gmdate('Y-m-d H:i:s'), $userId, $cid, $periodType, $periodKey]
        )->rowCount();
        Audit::log($userId ?: null, 'chart.publish', 'country_period', "{$country['code']}:$periodType:$periodKey", null, ['runs' => $count], $ip);
        $this->afterWeekPublished($country['code'], $period, $userId ?: null);
        return $count;
    }

    /**
     * Décision sur un titre signalé : validé (gardé) ou exclu. La raison est obligatoire et
     * l'exclusion est publique. Les classements de la semaine sont ensuite recalculés.
     */
    public function decide(int $trackId, string $weekStart, string $decision, string $reason, int $userId, ?string $ip = null): void
    {
        if (!in_array($decision, ['validated', 'excluded'], true) || trim($reason) === '') {
            throw new \InvalidArgumentException('Décision invalide ou raison manquante.');
        }
        $row = $this->db->one(
            'SELECT c.code, r.status FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id
             LEFT JOIN chart_runs r ON r.country_id = c.id AND r.period_type = \'week\' AND r.period_start = ? AND r.chart_type_id = ?
             WHERE t.id = ?',
            [$weekStart, $this->chartTypes['prime'], $trackId]
        );
        if (!$row) {
            throw new \InvalidArgumentException('Titre inconnu.');
        }
        $this->db->run(
            'INSERT INTO track_reviews (track_id, week_start, decision, reason, user_id) VALUES (?, ?, ?, ?, ?)
             ON DUPLICATE KEY UPDATE decision = VALUES(decision), reason = VALUES(reason), user_id = VALUES(user_id), created_at = CURRENT_TIMESTAMP',
            [$trackId, $weekStart, $decision, $reason, $userId]
        );
        Audit::log($userId, 'track.' . ($decision === 'excluded' ? 'exclude' : 'validate'), 'track', $trackId, $reason, ['week_start' => $weekStart], $ip);

        $correction = $row['status'] === 'published' ? "Décision sur un titre signalé : $reason" : null;
        $this->computeWeek($row['code'], $weekStart, $correction, $userId);
    }
}
