<?php

/**
 * Installation : crée la base, importe schema.sql et reference.sql (pays, classements, formule : données réelles).
 *
 *   php bin/install.php                    (base neuve, sans aucune donnée fictive : local comme production)
 *   php bin/install.php --fresh            (supprime et recrée toutes les tables)
 *   php bin/install.php --fresh --demo     (développement uniquement : + seed.sql fictif et classements d'exemple)
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Config;
use Cauri\Core\Database;

$opts = cli_options($argv);

cli_run('install', function () use ($opts) {
    $c = Config::get('app.db');
    $server = Database::makePdo(sprintf('mysql:host=%s;port=%d;charset=utf8mb4', $c['host'], $c['port']), $c['user'], $c['pass']);
    $dbName = str_replace('`', '', $c['name']);
    $server->exec("CREATE DATABASE IF NOT EXISTS `$dbName` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
    $server->exec("USE `$dbName`");

    $hasTables = (int) $server->query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = " . $server->quote($dbName))->fetchColumn();
    if ($hasTables > 0 && empty($opts['fresh'])) {
        throw new RuntimeException("La base `$dbName` contient déjà des tables. Relancer avec --fresh pour TOUT supprimer et réinstaller.");
    }
    if (Config::get('app.env') === 'production' && !empty($opts['demo'])) {
        throw new RuntimeException('--demo est interdit en production.');
    }

    $import = function (string $file) use ($server): void {
        $sql = file_get_contents($file);
        foreach (preg_split('/;\s*\n/', $sql) as $statement) {
            $lines = array_filter(explode("\n", $statement), fn ($l) => !str_starts_with(trim($l), '--'));
            $statement = trim(implode("\n", $lines));
            if ($statement !== '') {
                $server->exec($statement);
            }
        }
    };

    $import(BASE_PATH . '/database/schema.sql');
    cli_out('Schéma importé.');

    // Données de référence réelles : pays, types de classements, versions de la formule
    $import(BASE_PATH . '/database/reference.sql');
    cli_out('Données de référence importées (pays, classements, formule).');

    if (!empty($opts['demo'])) {
        $import(BASE_PATH . '/database/seed.sql');
        cli_out("Données d'exemple FICTIVES importées (développement uniquement).");

        // Capture d'écran factice référencée par les déclarations d'exemple
        $dir = BASE_PATH . '/storage/uploads/demo';
        if (!is_dir($dir)) {
            mkdir($dir, 0775, true);
        }
        file_put_contents($dir . '/capture-exemple.png', base64_decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        ));
    }

    if (!empty($opts['demo'])) {
        cli_out('Calcul des classements d\'exemple...');
        passthru(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(__DIR__ . '/compute-weekly.php') . ' --from=2026-07-27 --to=2026-09-27 --publish-clean', $code);
        if ($code !== 0) {
            throw new RuntimeException('Le calcul des classements a échoué.');
        }
    }

    cli_out('');
    cli_out('Installation terminée. Créer un compte admin :');
    cli_out('  php bin/create-admin.php admin@example.com "Ton Nom"');
});
