<?php

/**
 * Sauvegarde de la base en SQL compressé (storage/backups), sans dépendre de mysqldump.
 * Garde les 30 dernières sauvegardes.
 *
 *   php bin/backup.php
 *
 * Sur O2switch, compléter par les sauvegardes JetBackup du cPanel et une copie hors serveur.
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Database;

cli_run('backup', function () {
    $pdo = Database::connection()->pdo();
    $dir = BASE_PATH . '/storage/backups';
    if (!is_dir($dir)) {
        mkdir($dir, 0775, true);
    }
    $file = $dir . '/cauricharts-' . date('Y-m-d-His') . '.sql.gz';
    $gz = gzopen($file, 'wb6');
    gzwrite($gz, '-- Sauvegarde ' . date('c') . "\nSET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS = 0;\n\n");

    foreach ($pdo->query('SHOW TABLES')->fetchAll(PDO::FETCH_COLUMN) as $table) {
        $create = $pdo->query("SHOW CREATE TABLE `$table`")->fetch(PDO::FETCH_NUM)[1];
        gzwrite($gz, "DROP TABLE IF EXISTS `$table`;\n$create;\n\n");
        $stmt = $pdo->query("SELECT * FROM `$table`", PDO::FETCH_NUM);
        $batch = [];
        while ($row = $stmt->fetch()) {
            $batch[] = '(' . implode(', ', array_map(fn ($v) => $v === null ? 'NULL' : $pdo->quote((string) $v), $row)) . ')';
            if (count($batch) === 500) {
                gzwrite($gz, "INSERT INTO `$table` VALUES\n" . implode(",\n", $batch) . ";\n");
                $batch = [];
            }
        }
        if ($batch) {
            gzwrite($gz, "INSERT INTO `$table` VALUES\n" . implode(",\n", $batch) . ";\n");
        }
        gzwrite($gz, "\n");
    }
    gzwrite($gz, "SET FOREIGN_KEY_CHECKS = 1;\n");
    gzclose($gz);

    // Rotation : on garde les 30 plus récentes
    $all = glob($dir . '/cauricharts-*.sql.gz');
    sort($all);
    foreach (array_slice($all, 0, max(0, count($all) - 30)) as $old) {
        unlink($old);
    }
    cli_out('Sauvegarde : ' . $file . ' (' . round(filesize($file) / 1024) . ' Ko)');
});
