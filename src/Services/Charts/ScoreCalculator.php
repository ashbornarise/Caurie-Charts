<?php

namespace Cauri\Services\Charts;

/**
 * Score hebdomadaire d'un titre (METHODOLOGIE.md, sections 3, 4 et 6).
 * Classe pure : aucune base de données, tout arrive en paramètre.
 */
final class ScoreCalculator
{
    /** Plateforme -> classe de poids. Spotify ne donne pas de streams : hors score. */
    public const WEIGHT_CLASS = [
        'youtube'     => 'youtube',
        'audiomack'   => 'audio',
        'boomplay'    => 'audio',
        'apple_music' => 'audio',
        'deezer'      => 'audio',
    ];

    public function __construct(private array $formula)
    {
    }

    public function weight(string $class, string $countryCode): float
    {
        return (float) ($this->formula['country_weights'][$countryCode][$class]
            ?? $this->formula['weights'][$class]
            ?? 0.0);
    }

    /**
     * @param array $input [
     *   'track_id'     => int,
     *   'deltas'       => ['youtube' => int|null, 'audiomack' => int|null, ...]  variation de la semaine,
     *   'youtube_likes'=> int|null   variation des "j'aime" sur la semaine,
     *   'declarations' => [['platform' => 'spotify', 'streams' => int], ...]     validées, ramenées à la semaine,
     *   'chart_points' => ['apple_music' => float, ...]  points de position moyens de la semaine (v1.2),
     *   'history'      => [float, ...]  scores des semaines précédentes (la plus récente en premier),
     *   'decision'     => null|'validated'|'excluded',
     * ]
     * @return array ['score','sources_count','breakdown','flags','review_status']
     */
    public function score(array $input, string $countryCode): array
    {
        $flags = [];
        $breakdown = [];
        $score = 0.0;
        $publicSources = 0;
        $sources = []; // plateformes distinctes ayant apporté des points (règle de diversité)

        foreach ($input['deltas'] ?? [] as $platform => $delta) {
            if ($delta === null || !isset(self::WEIGHT_CLASS[$platform])) {
                continue;
            }
            if ($delta < 0) {
                // Compteur qui recule (vidéo supprimée, correction de la plateforme) : on ne retire rien
                $flags[] = Flags::NEGATIVE_DELTA;
                $delta = 0;
            }
            $weight = $this->weight(self::WEIGHT_CLASS[$platform], $countryCode);
            $points = $delta * $weight;
            $breakdown[$platform] = ['delta' => (int) $delta, 'weight' => $weight, 'points' => round($points, 2)];
            $score += $points;
            if ($delta > 0) {
                $publicSources++;
                $sources[$platform] = true;
            }
        }

        // Positions dans les classements des plateformes (v1.2) : donnée publique, comme les compteurs
        foreach ($input['chart_points'] ?? [] as $source => $chartPoints) {
            $weight = (float) ($this->formula['chart_weights'][$source] ?? 0);
            if ($weight <= 0 || $chartPoints <= 0) {
                continue;
            }
            $points = $chartPoints * $weight;
            $breakdown['chart:' . $source] = ['delta' => round((float) $chartPoints, 1), 'weight' => $weight, 'points' => round($points, 2)];
            $score += $points;
            if (!isset($sources[$source])) {
                $publicSources++;
            }
            $sources[$source] = true;
        }

        $declaredSources = 0;
        $tolerance = (float) $this->formula['anti_fraud']['declaration_tolerance'];
        foreach ($input['declarations'] ?? [] as $decl) {
            $platform = $decl['platform'];
            $streams = (int) $decl['streams'];
            $public = $input['deltas'][$platform] ?? null;

            if ($public !== null) {
                // Donnée publique disponible sur la même plateforme : elle prévaut, la déclaration sert de contrôle
                $gap = $public > 0 ? abs($streams - $public) / $public : ($streams > 0 ? 1.0 : 0.0);
                if ($gap > $tolerance) {
                    $flags[] = Flags::DECLARATION_MISMATCH;
                }
                continue;
            }
            if ($publicSources === 0) {
                // Pas de contrôle possible, pas de points
                $flags[] = Flags::DECLARATION_UNCORROBORATED;
                continue;
            }
            $weight = $this->weight('declaration', $countryCode);
            $points = $streams * $weight;
            $key = 'declaration:' . $platform;
            $breakdown[$key] = ['delta' => $streams, 'weight' => $weight, 'points' => round($points, 2)];
            $score += $points;
            if ($streams > 0 && !isset($sources[$platform])) {
                $declaredSources++;
                $sources[$platform] = true;
            }
        }

        $af = $this->formula['anti_fraud'];

        // Pic anormal : variation > facteur x médiane des N dernières semaines
        $history = array_slice(array_values($input['history'] ?? []), 0, (int) $af['spike_history_weeks']);
        if (count($history) >= (int) $af['spike_min_history']) {
            $median = self::median($history);
            if ($median > 0 && $score > $af['spike_factor'] * $median) {
                $flags[] = Flags::SPIKE;
            }
        }

        // Ratio vues / "j'aime" sur YouTube
        $views = $input['deltas']['youtube'] ?? null;
        $likes = $input['youtube_likes'] ?? null;
        if ($views !== null && $likes !== null && $views >= $af['youtube_min_views']) {
            $perThousand = $likes / $views * 1000;
            if ($perThousand < $af['youtube_min_likes_per_1000'] || $perThousand > $af['youtube_max_likes_per_1000']) {
                $flags[] = Flags::YOUTUBE_RATIO;
            }
        }

        $flags = array_values(array_unique($flags));
        $decision = $input['decision'] ?? null;
        $status = match (true) {
            $decision === 'excluded'  => 'excluded',
            $decision === 'validated' => 'validated',
            Flags::hasBlocking($flags) => 'pending',
            default => 'ok',
        };

        return [
            'score'         => round($score, 2),
            'sources_count' => $publicSources + $declaredSources,
            'breakdown'     => $breakdown,
            'flags'         => $flags,
            'review_status' => $status,
        ];
    }

    public static function median(array $values): float
    {
        if (!$values) {
            return 0.0;
        }
        sort($values);
        $n = count($values);
        $mid = intdiv($n, 2);
        return $n % 2 ? (float) $values[$mid] : ($values[$mid - 1] + $values[$mid]) / 2;
    }

    /** Ramène une déclaration couvrant une période quelconque à la part qui chevauche la semaine. */
    public static function prorate(int $streams, string $periodStart, string $periodEnd, string $weekStart, string $weekEnd): int
    {
        $ps = strtotime($periodStart);
        $pe = strtotime($periodEnd);
        $overlapStart = max($ps, strtotime($weekStart));
        $overlapEnd = min($pe, strtotime($weekEnd));
        if ($overlapEnd < $overlapStart) {
            return 0;
        }
        $periodDays = intdiv($pe - $ps, 86400) + 1;
        $overlapDays = intdiv($overlapEnd - $overlapStart, 86400) + 1;
        return (int) round($streams * $overlapDays / max(1, $periodDays));
    }
}
