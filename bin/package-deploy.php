<?php

/**
 * Prépare la mise en ligne : archive du site + export de la base (données réelles collectées).
 * Exclus : .env et secrets, comptes admin (à recréer sur le serveur), journaux, cache, fichiers Git et Claude.
 *
 *   php bin/package-deploy.php            → deploy/out/cauricharts-site.zip et deploy/out/cauricharts-base.sql
 *
 * Puis : scp deploy/out/* deploy/installer-serveur.sh root@IP_DU_SERVEUR:/root/
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Config;

cli_run('package-deploy', function () {
    $out = BASE_PATH . '/deploy/out';
    if (!is_dir($out)) {
        mkdir($out, 0775, true);
    }

    // 1. Archive du site
    $zipFile = "$out/cauricharts-site.zip";
    @unlink($zipFile);
    $zip = new ZipArchive();
    if ($zip->open($zipFile, ZipArchive::CREATE) !== true) {
        throw new RuntimeException("Impossible de créer $zipFile");
    }
    $skip = '#^(\.git/|\.claude/|\.env$|deploy/out/|storage/(logs|cache|backups|uploads)/|cauri-charts-logos/|docs/.*\.pdf$|node_modules/)#';
    $count = 0;
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator(BASE_PATH, FilesystemIterator::SKIP_DOTS));
    foreach ($it as $file) {
        $rel = str_replace('\\', '/', substr($file->getPathname(), strlen(BASE_PATH) + 1));
        if ($file->isDir() || preg_match($skip, $rel)) {
            continue;
        }
        $zip->addFile($file->getPathname(), $rel);
        $count++;
    }
    foreach (['storage/logs', 'storage/cache', 'storage/uploads', 'storage/backups'] as $dir) {
        $zip->addEmptyDir($dir);
    }
    $zip->close();
    cli_out(sprintf('Site : %d fichiers, %.1f Mo → %s', $count, filesize($zipFile) / 1048576, $zipFile));

    // 2. Export de la base (sans les comptes admin ni les tentatives de connexion)
    $db = Config::get('app.db');
    $sqlFile = "$out/cauricharts-base.sql";
    $dump = PHP_OS_FAMILY === 'Windows' && is_file('C:/xampp/mysql/bin/mysqldump.exe') ? 'C:/xampp/mysql/bin/mysqldump.exe' : 'mysqldump';
    $cmd = escapeshellarg($dump) . ' --single-transaction --default-character-set=utf8mb4 --skip-add-locks'
        . ' -h ' . escapeshellarg($db['host']) . ' -P ' . (int) $db['port'] . ' -u ' . escapeshellarg($db['user'])
        . ($db['pass'] !== '' ? ' -p' . escapeshellarg($db['pass']) : '')
        . ' --ignore-table=' . escapeshellarg($db['name'] . '.users') . ' --ignore-table=' . escapeshellarg($db['name'] . '.login_attempts')
        . ' ' . escapeshellarg($db['name']) . ' > ' . escapeshellarg($sqlFile);
    exec($cmd, $output, $code);
    if ($code !== 0) {
        throw new RuntimeException('Export de la base impossible (mysqldump) : ' . implode(' ', $output));
    }
    // Tables des comptes recréées vides (structure seule)
    $structure = escapeshellarg($dump) . ' --no-data --default-character-set=utf8mb4 -h ' . escapeshellarg($db['host']) . ' -P ' . (int) $db['port']
        . ' -u ' . escapeshellarg($db['user']) . ($db['pass'] !== '' ? ' -p' . escapeshellarg($db['pass']) : '')
        . ' ' . escapeshellarg($db['name']) . ' users login_attempts >> ' . escapeshellarg($sqlFile);
    exec($structure, $output, $code);
    cli_out(sprintf('Base : %.1f Mo → %s', filesize($sqlFile) / 1048576, $sqlFile));
    cli_out('');
    cli_out('Envoi vers le serveur (remplacez IP) :');
    cli_out('  scp deploy/out/cauricharts-site.zip deploy/out/cauricharts-base.sql deploy/installer-serveur.sh root@IP:/root/');
});
