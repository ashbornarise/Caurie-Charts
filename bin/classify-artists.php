<?php

/**
 * Classement automatique des artistes en attente (MusicBrainz, puis IA avec recherche web).
 * Lancé aussi à la fin de bin/import-charts.php. Seuls les cas incertains restent à traiter dans /admin/import.
 *
 *   php bin/classify-artists.php              60 artistes au plus
 *   php bin/classify-artists.php --limit=300
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Services\AI\AiFactory;
use Cauri\Services\Import\ArtistClassifier;
use Cauri\Services\Platforms\CurlHttpClient;

$opts = cli_options($argv);

cli_run('classify-artists', function () use ($opts) {
    $ai = AiFactory::make();
    $s = (new ArtistClassifier(Database::connection(), new CurlHttpClient(20), $ai))->run((int) ($opts['limit'] ?? 60));
    cli_out(sprintf(
        'Artistes examinés : %d — confirmés : %d, hors périmètre : %d, à vérifier par l’équipe : %d (recherches IA : %d%s)',
        $s['checked'], $s['active'], $s['out_of_scope'], $s['pending'], $s['ai_calls'], $ai ? '' : ', IA inactive : GEMINI_API_KEY absente (gratuite sur aistudio.google.com)'
    ));
});
