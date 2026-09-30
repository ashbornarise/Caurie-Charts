<?php

/**
 * Liste de suivi (config/watchlist.php) : artistes absents des classements et chaînes de labels.
 * Lancé aussi par bin/import-charts.php.
 *
 *   php bin/watch-artists.php
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Services\Import\ArtistWatch;
use Cauri\Services\Platforms\CurlHttpClient;

cli_run('watch-artists', function () {
    foreach ((new ArtistWatch(Database::connection(), new CurlHttpClient()))->run() as $line) {
        cli_out($line);
    }
});
