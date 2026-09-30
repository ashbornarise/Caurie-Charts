<?php

/**
 * Découverte des artistes de chaque pays (Wikidata, réseau Deezer), filtrés par leur fanbase.
 * Lancé aussi par bin/import-charts.php ; les candidats apparaissent dans /admin/import avec leurs chiffres.
 *
 *   php bin/discover-artists.php
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Services\Import\ArtistDiscovery;
use Cauri\Services\Platforms\CurlHttpClient;

cli_run('discover-artists', function () {
    foreach ((new ArtistDiscovery(Database::connection(), new CurlHttpClient(60)))->run() as $line) {
        cli_out($line);
    }
});
