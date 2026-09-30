<?php

/**
 * Profils d'artistes : photo et nombre de fans depuis l'API publique Deezer.
 * Lancé aussi à la fin de bin/import-charts.php.
 *
 *   php bin/enrich-artists.php            80 profils au plus
 *   php bin/enrich-artists.php --limit=300
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Services\Import\ArtistEnricher;
use Cauri\Services\Platforms\CurlHttpClient;

$opts = cli_options($argv);

cli_run('enrich-artists', function () use ($opts) {
    $stats = (new ArtistEnricher(Database::connection(), new CurlHttpClient()))->run((int) ($opts['limit'] ?? 80));
    cli_out("Profils vérifiés : {$stats['checked']}, trouvés sur Deezer : {$stats['found']}");
});
