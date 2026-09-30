<?php

/**
 * Import des actualités musicales (flux RSS de config/news.php), avec vignettes locales.
 * Cron conseillé : toutes les 3 heures.
 *
 *   php bin/import-news.php
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;
use Cauri\Services\News\FeedImporter;

cli_run('import-news', function () {
    foreach ((new FeedImporter(Database::connection()))->run() as $line) {
        cli_out($line);
    }
});
