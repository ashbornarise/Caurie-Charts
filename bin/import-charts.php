<?php

/**
 * Import des classements (une source ou un pays à la fois, pour les essais et l'admin).
 * La chaîne quotidienne complète (découverte, vérification, relevés, posts…) est bin/daily.php.
 *
 *   php bin/import-charts.php                      toutes les sources, tous les pays actifs
 *   php bin/import-charts.php --country=CI --source=apple_music
 *   php bin/import-charts.php --youtube=30         puis recherche de 30 clips YouTube au plus (3 000 unités)
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Core\Env;
use Cauri\Services\Import\ImportService;

$opts = cli_options($argv);

cli_run('import-charts', function () use ($opts) {
    $service = new ImportService(Database::connection());
    $countries = !empty($opts['country']) ? [strtoupper($opts['country'])] : null;
    $sources = !empty($opts['source']) ? [$opts['source']] : null;

    foreach ($service->importAll($countries, $sources) as $line) {
        cli_out($line);
    }

    $limit = isset($opts['youtube']) ? (int) $opts['youtube'] : (int) Env::get('YOUTUBE_SEARCH_PER_RUN', '0');
    if ($limit > 0) {
        cli_out('YouTube : ' . json_encode($service->matchYouTube($limit), JSON_UNESCAPED_UNICODE));
    }
});
