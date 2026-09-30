<?php

/**
 * Relevé quotidien des compteurs (cron, une fois par jour, en fin de journée heure de Lomé).
 *
 *   php bin/collect.php                 relevé du jour
 *   php bin/collect.php --day=2026-09-28
 *
 * Sans clé API dans .env, les plateformes sont ignorées : le site continue de tourner
 * sur les relevés existants (données d'exemple en local).
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Services\Platforms\CollectService;

$opts = cli_options($argv);

cli_run('collect', function () use ($opts) {
    $db = Database::connection();
    $day = is_string($opts['day'] ?? null) ? $opts['day'] : date('Y-m-d');
    $report = (new CollectService($db, CollectService::clients($db)))->run($day);
    foreach ($report as $platform => $r) {
        cli_out(str_pad($platform, 10) . ' ' . json_encode($r, JSON_UNESCAPED_UNICODE));
    }
    \Cauri\Services\Logger::write('cron', 'info', "collect $day", $report);
});
