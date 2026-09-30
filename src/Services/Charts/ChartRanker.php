<?php

namespace Cauri\Services\Charts;

/**
 * Transforme des scores en classements (METHODOLOGIE.md, sections 4 et 5).
 * Classe pure : chaque classement est reproductible à partir des mêmes entrées.
 *
 * Un "item" est un tableau : track_id, artist_id, score, sources_count, prev_score,
 * release_date, is_emerging, flags, review_status, breakdown.
 * $previous : [id => ['position' => int, 'peak' => int, 'weeks' => int]] du classement précédent.
 */
final class ChartRanker
{
    public function __construct(private array $formula)
    {
    }

    /** Départage : score, nombre de sources, progression, score précédent, puis identifiant (stable). */
    public static function compare(array $a, array $b): int
    {
        return [$b['score'], $b['sources_count'], $b['score'] - ($b['prev_score'] ?? 0), $b['prev_score'] ?? 0, $a['id'] ?? $a['track_id']]
            <=> [$a['score'], $a['sources_count'], $a['score'] - ($a['prev_score'] ?? 0), $a['prev_score'] ?? 0, $b['id'] ?? $b['track_id']];
    }

    /** Titres classables : score positif et non exclus. */
    public static function eligible(array $items): array
    {
        return array_values(array_filter($items, fn ($i) => $i['score'] > 0 && ($i['review_status'] ?? 'ok') !== 'excluded'));
    }

    public function prime(array $items, int $size, array $previous = []): array
    {
        $sorted = self::eligible($items);
        usort($sorted, [self::class, 'compare']);
        $ordered = $this->applyDiversity($sorted);
        return $this->finalize(array_slice($ordered, 0, $size), $previous, 'track_id');
    }

    /**
     * Règle de diversité : les N premières places vont aux titres présents sur au moins X sources.
     * Un titre mono-source qui aurait dû y figurer est plafonné juste après (diversity_capped).
     * S'il n'y a pas assez de titres multi-sources, les places restantes vont aux mono-source (diversity_fallback).
     */
    public function applyDiversity(array $sorted): array
    {
        $top = (int) $this->formula['diversity']['top'];
        $min = (int) $this->formula['diversity']['min_sources'];

        $head = [];
        $rest = []; // [rang naturel, item], dans l'ordre du score
        foreach ($sorted as $i => $item) {
            if (count($head) < $top && $item['sources_count'] >= $min) {
                $head[] = $item;
            } else {
                $rest[] = [$i + 1, $item];
            }
        }

        $result = $head;
        foreach ($rest as [$naturalRank, $item]) {
            if ($item['sources_count'] < $min) {
                if (count($result) < $top) {
                    $item['flags'][] = Flags::DIVERSITY_FALLBACK;
                } elseif ($naturalRank <= $top) {
                    $item['flags'][] = Flags::DIVERSITY_CAPPED;
                }
            }
            $result[] = $item;
        }
        return $result;
    }

    /** Plus fortes progressions hors Prime Chart. */
    public function buzz(array $items, array $primeTrackIds, int $size, array $previous = []): array
    {
        $cfg = $this->formula['buzz'];
        $candidates = [];
        foreach (self::eligible($items) as $item) {
            $prev = (float) ($item['prev_score'] ?? 0);
            if (in_array($item['track_id'], $primeTrackIds, true) || $prev <= 0 || $item['score'] < $cfg['min_score']) {
                continue;
            }
            $growth = ($item['score'] - $prev) / $prev * 100;
            if ($growth <= $cfg['min_growth_pct']) {
                continue;
            }
            $item['growth_pct'] = round($growth, 2);
            $candidates[] = $item;
        }
        usort($candidates, fn ($a, $b) => [$b['growth_pct'], $b['score'], $a['track_id']] <=> [$a['growth_pct'], $a['score'], $b['track_id']]);
        return $this->finalize(array_slice($candidates, 0, $size), $previous, 'track_id');
    }

    /** Titres sortis depuis moins de N jours, ou artistes émergents. */
    public function fresh(array $items, string $weekEnd, int $size, array $previous = []): array
    {
        $maxAge = (int) $this->formula['fresh']['max_age_days'];
        $limit = strtotime($weekEnd . " -$maxAge days");
        $end = strtotime($weekEnd);
        $candidates = array_values(array_filter(self::eligible($items), function ($i) use ($limit, $end) {
            $released = $i['release_date'] ? strtotime($i['release_date']) : null;
            $recent = $released !== null && $released > $limit && $released <= $end;
            return $recent || !empty($i['is_emerging']);
        }));
        usort($candidates, [self::class, 'compare']);
        return $this->finalize(array_slice($candidates, 0, $size), $previous, 'track_id');
    }

    /** Classement des artistes : somme des scores de leurs titres. */
    public function icon(array $items, int $size, array $previous = []): array
    {
        $artists = [];
        foreach (self::eligible($items) as $item) {
            $id = $item['artist_id'];
            $artists[$id] ??= ['id' => $id, 'artist_id' => $id, 'track_id' => null, 'score' => 0.0, 'sources_count' => 0, 'prev_score' => 0.0, 'flags' => [], 'breakdown' => []];
            $artists[$id]['score'] += $item['score'];
            $artists[$id]['prev_score'] += (float) ($item['prev_score'] ?? 0);
            $artists[$id]['sources_count']++; // nombre de titres
            $artists[$id]['breakdown'][] = ['track_id' => $item['track_id'], 'score' => $item['score']];
        }
        $list = array_values($artists);
        foreach ($list as &$a) {
            $a['score'] = round($a['score'], 2);
        }
        unset($a);
        usort($list, fn ($a, $b) => [$b['score'], $b['sources_count'], $a['artist_id']] <=> [$a['score'], $a['sources_count'], $b['artist_id']]);
        return $this->finalize(array_slice($list, 0, $size), $previous, 'artist_id');
    }

    /** Classement par cumul (Legend Chart, mois, année) : $totals = [track_id => ['score' => float, ...item]]. */
    public function cumulative(array $items, int $size, array $previous = []): array
    {
        $sorted = self::eligible($items);
        usort($sorted, [self::class, 'compare']);
        return $this->finalize(array_slice($sorted, 0, $size), $previous, 'track_id');
    }

    /**
     * Classement régional : chaque pays attribue des points selon le rang (10 au premier du Top 10,
     * 9 au deuxième...), puis on additionne. $countryCharts = [countryCode => [entry, ...]].
     */
    public static function regionalPoints(array $countryCharts, int $pointsFor = 10): array
    {
        $totals = [];
        foreach ($countryCharts as $entries) {
            foreach ($entries as $entry) {
                if ($entry['position'] > $pointsFor) {
                    continue;
                }
                $id = $entry['track_id'];
                $totals[$id] ??= ['track_id' => $id, 'points' => 0, 'countries' => 0, 'best' => PHP_INT_MAX];
                $totals[$id]['points'] += $pointsFor - $entry['position'] + 1;
                $totals[$id]['countries']++;
                $totals[$id]['best'] = min($totals[$id]['best'], $entry['position']);
            }
        }
        $list = array_values($totals);
        usort($list, fn ($a, $b) => [$b['points'], $b['countries'], $a['best'], $a['track_id']] <=> [$a['points'], $a['countries'], $b['best'], $b['track_id']]);
        return $list;
    }

    /** Somme de scores déjà calculés (mois et année du classement régional) : [track_id => ['score', 'artist_id', 'countries']]. */
    public function summedPoints(array $totals, int $size, array $previous = []): array
    {
        $items = [];
        foreach ($totals as $trackId => $t) {
            $items[] = ['track_id' => $trackId, 'artist_id' => $t['artist_id'], 'score' => (float) $t['score'], 'sources_count' => (int) $t['countries'], 'flags' => [], 'breakdown' => []];
        }
        usort($items, fn ($a, $b) => [$b['score'], $b['sources_count'], $a['track_id']] <=> [$a['score'], $a['sources_count'], $b['track_id']]);
        return $this->finalize(array_slice($items, 0, $size), $previous, 'track_id');
    }

    /** Numérote et ajoute position précédente, meilleure position et nombre de semaines. */
    private function finalize(array $list, array $previous, string $key): array
    {
        $entries = [];
        foreach (array_values($list) as $i => $item) {
            $position = $i + 1;
            $id = $item[$key];
            $prev = $previous[$id] ?? null;
            $entries[] = [
                'position'          => $position,
                'track_id'          => $key === 'track_id' ? $id : null,
                'artist_id'         => $key === 'artist_id' ? $id : ($item['artist_id'] ?? null),
                'score'             => round((float) $item['score'], 2),
                'previous_position' => $prev['position'] ?? null,
                'peak_position'     => $prev ? min($prev['peak'], $position) : $position,
                'weeks_on_chart'    => $prev ? $prev['weeks'] + 1 : 1,
                'sources_count'     => (int) $item['sources_count'],
                'growth_pct'        => $item['growth_pct'] ?? null,
                'flags'             => array_values(array_unique($item['flags'] ?? [])),
                'review_status'     => $item['review_status'] ?? 'ok',
                'details'           => $item['breakdown'] ?? [],
            ];
        }
        return $entries;
    }
}
