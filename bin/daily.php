<?php

/**
 * Chaîne quotidienne complète (une seule tâche planifiée, chaque nuit) : classements des plateformes,
 * découverte et vérification des artistes, clips et relevé des vues YouTube, sources calculées,
 * actualités, classement officiel le lundi, posts lundi/mercredi/vendredi. Voir Services\DailyPipeline.
 *
 *   php bin/daily.php
 *   php bin/daily.php --weekly          force le calcul du classement officiel de la semaine passée
 *   php bin/daily.php --posts           force la génération des trois posts
 *   php bin/daily.php --youtube=10      nombre de recherches de clips YouTube (100 unités de quota chacune)
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Services\DailyPipeline;

$opts = cli_options($argv);

cli_run('daily', function () use ($opts) {
    $report = (new DailyPipeline(Database::connection(), fn (string $l) => cli_out($l)))->run(
        !empty($opts['weekly']),
        !empty($opts['posts']),
        isset($opts['youtube']) ? (int) $opts['youtube'] : 10
    );
    $failed = array_filter($report, fn ($r) => !$r['ok']);
    cli_out('');
    cli_out(sprintf('Terminé : %d étapes, %d en erreur%s', count($report), count($failed),
        $failed ? ' (' . implode(', ', array_column($failed, 'step')) . ')' : ''));
});
