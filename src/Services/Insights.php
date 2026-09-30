<?php

namespace Cauri\Services;

use Cauri\Core\Database;
use Cauri\Repositories\ChartRepository;

/**
 * Faits de la semaine calculés à partir du dernier Prime Chart publié d'un pays :
 * toujours exacts, toujours à jour, sans rédaction.
 */
final class Insights
{
    public function __construct(private Database $db, private ChartRepository $charts)
    {
    }

    public function forCountry(array $country): array
    {
        // Pays : son Prime Chart ; région (id null) : le classement des cinq pays
        $cid = $country['id'] !== null ? (int) $country['id'] : null;
        $chartCode = $cid === null ? 'prime-wa' : 'prime';
        $run = $this->charts->latestRun($cid, $chartCode, 'week');
        if (!$run) {
            return ['run' => null, 'facts' => []];
        }
        $entries = $this->charts->entries((int) $run['id']);
        $facts = [];

        // N° 1 et nombre de semaines consécutives en tête
        $top = $entries[0] ?? null;
        if ($top) {
            $streak = 0;
            foreach ($this->db->all(
                "SELECT e.track_id FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
                 JOIN chart_entries e ON e.chart_run_id = r.id AND e.position = 1
                 WHERE r.country_id <=> ? AND ct.code = ? AND r.period_type = 'week' AND r.status = 'published' AND r.period_end <= ?
                 ORDER BY r.period_end DESC LIMIT 52",
                [$cid, $chartCode, $run['period_end']]
            ) as $row) {
                if ((int) $row['track_id'] !== (int) $top['track_id']) {
                    break;
                }
                $streak++;
            }
            $facts[] = ['type' => 'number_one', 'entry' => $top, 'value' => $streak];
        }

        // Plus forte progression
        $climber = null;
        foreach ($entries as $e) {
            if ($e['previous_position'] !== null && (int) $e['previous_position'] > (int) $e['position']) {
                $gain = (int) $e['previous_position'] - (int) $e['position'];
                if (!$climber || $gain > $climber['value']) {
                    $climber = ['type' => 'climber', 'entry' => $e, 'value' => $gain];
                }
            }
        }
        if ($climber) {
            $facts[] = $climber;
        }

        // Meilleure nouvelle entrée et nombre d'entrées
        $new = array_values(array_filter($entries, fn ($e) => $e['previous_position'] === null && (int) $e['weeks_on_chart'] === 1));
        if ($new) {
            $facts[] = ['type' => 'best_new', 'entry' => $new[0], 'value' => count($new)];
        }

        // Plus forte hausse du Buzz Chart
        $buzz = $cid !== null ? $this->charts->latestRun($cid, 'buzz', 'week') : null;
        if ($buzz && ($b = $this->charts->entries((int) $buzz['id'], 1)[0] ?? null)) {
            $facts[] = ['type' => 'buzz', 'entry' => $b, 'value' => (float) $b['growth_pct']];
        }

        // Artiste le plus présent
        $byArtist = [];
        foreach ($entries as $e) {
            $byArtist[$e['artist_slug']] ??= ['entry' => $e, 'value' => 0];
            $byArtist[$e['artist_slug']]['value']++;
        }
        usort($byArtist, fn ($a, $b) => $b['value'] <=> $a['value']);
        if ($byArtist && $byArtist[0]['value'] > 1) {
            $facts[] = ['type' => 'most_tracks', 'entry' => $byArtist[0]['entry'], 'value' => $byArtist[0]['value']];
        }

        return [
            'run'   => $run,
            'facts' => $facts,
            // Semaine suivante : se termine 7 jours après, publiée le mardi qui suit
            'next'  => date('Y-m-d', strtotime($run['period_end'] . ' +9 days')),
        ];
    }

    /** Une anecdote différente chaque semaine. */
    public static function didYouKnow(int $count = 6): string
    {
        return t('dyk.' . ((int) date('W') % $count + 1));
    }
}
