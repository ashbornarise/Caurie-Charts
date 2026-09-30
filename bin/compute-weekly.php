<?php

/**
 * Calcul hebdomadaire (cron du lundi) : classements de la semaine précédente (lundi à dimanche),
 * enregistrés en brouillon. Un admin vérifie les signalements puis publie (le mardi).
 *
 *   php bin/compute-weekly.php                          semaine terminée hier, tous les pays actifs
 *   php bin/compute-weekly.php --country=TG --week=2026-W39
 *   php bin/compute-weekly.php --from=2026-07-27 --to=2026-09-27     rattrapage de plusieurs semaines
 *   php bin/compute-weekly.php --week=2026-W38 --correction="Relevé Boomplay corrigé"
 *   php bin/compute-weekly.php ... --publish-clean      (local uniquement) publie les semaines sans signalement
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Services\Charts\ChartService;
use Cauri\Services\Charts\Period;

$opts = cli_options($argv);

cli_run('compute-weekly', function () use ($opts) {
    $db = Database::connection();
    $service = new ChartService($db);

    if (!empty($opts['publish-clean']) && Config::get('app.env') === 'production') {
        throw new RuntimeException('--publish-clean est réservé au développement local : en production, la publication passe par l\'admin.');
    }

    $countries = !empty($opts['country'])
        ? [strtoupper($opts['country'])]
        : array_column($db->all('SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order'), 'code');

    if (!empty($opts['from'])) {
        $weeks = [];
        $to = Period::weekOf($opts['to'] ?? date('Y-m-d', strtotime('-1 day')));
        for ($p = Period::weekOf($opts['from']); $p->start <= $to->start; $p = Period::weekOf(date('Y-m-d', strtotime($p->start . ' +7 days')))) {
            $weeks[] = $p;
        }
    } elseif (!empty($opts['week'])) {
        $weeks = [Period::weekFromKey($opts['week'])];
    } else {
        $weeks = [Period::lastCompletedWeek(date('Y-m-d'))];
    }

    $correction = isset($opts['correction']) && is_string($opts['correction']) ? $opts['correction'] : null;
    $systemUser = null;

    foreach ($weeks as $week) {
        foreach ($countries as $code) {
            $r = $service->computeWeek($code, $week->start, $correction, $systemUser);
            $summary = implode(', ', array_map(fn ($k, $v) => "$k $v", array_keys($r['entries']), $r['entries']));
            cli_out(sprintf('%s %s : %d titres notés, %d à vérifier (%s)', $week->key, $code, $r['tracks_scored'], $r['pending'], $summary));

            if (!empty($opts['publish-clean'])) {
                if ($r['pending'] === 0) {
                    // Le mois complet et le cumul de l'année suivent automatiquement
                    $service->publish($code, 'week', $week->key, 0);
                } else {
                    cli_out("  -> $code {$week->key} reste en brouillon : signalements à traiter dans l'admin.");
                }
            }
        }
    }
});
