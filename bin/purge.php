<?php

/**
 * Applique les durées de conservation annoncées dans la politique de confidentialité
 * (config/app.php, clé "retention"). À lancer une fois par jour (cron).
 *
 *   php bin/purge.php
 *   php bin/purge.php --dry-run     affiche ce qui serait supprimé, sans rien toucher
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Services\Audit;
use Cauri\Services\Uploads;

$opts = cli_options($argv);

cli_run('purge', function () use ($opts) {
    $db = Database::connection();
    $r = Config::get('app.retention');
    $dry = !empty($opts['dry-run']);
    $before = fn (int $months) => gmdate('Y-m-d H:i:s', strtotime("-$months months"));
    $report = [];

    // Captures d'écran des déclarations traitées
    $old = $db->all(
        "SELECT id, screenshot_path FROM submissions WHERE status <> 'pending' AND reviewed_at < ? AND screenshot_path <> 'supprime'",
        [$before($r['screenshots'])]
    );
    foreach ($old as $s) {
        if (!$dry) {
            @unlink(Uploads::path($s['screenshot_path']));
            $db->update('submissions', ['screenshot_path' => 'supprime'], 'id = :id', ['id' => $s['id']]);
        }
    }
    $report['captures'] = count($old);

    // Nom et e-mail des déclarants (les chiffres restent : ils servent à rejouer les classements)
    $report['declarants'] = $dry
        ? (int) $db->value("SELECT COUNT(*) FROM submissions WHERE created_at < ? AND contact_email <> 'supprime@invalid'", [$before($r['submission_contact'])])
        : $db->run(
            "UPDATE submissions SET contact_name = '(supprimé)', contact_email = 'supprime@invalid', ip_hash = NULL
             WHERE created_at < ? AND contact_email <> 'supprime@invalid'",
            [$before($r['submission_contact'])]
        )->rowCount();

    // Messages clos ou répondus
    $sql = "FROM contact_messages WHERE status <> 'new' AND created_at < ?";
    $report['messages'] = $dry ? (int) $db->value("SELECT COUNT(*) $sql", [$before($r['contact_messages'])])
        : $db->run("DELETE $sql", [$before($r['contact_messages'])])->rowCount();

    // Tentatives de connexion
    $sql = 'FROM login_attempts WHERE attempted_at < ?';
    $report['connexions'] = $dry ? (int) $db->value("SELECT COUNT(*) $sql", [$before($r['login_attempts'])])
        : $db->run("DELETE $sql", [$before($r['login_attempts'])])->rowCount();

    // Adresses IP du journal d'audit (les actions restent tracées)
    $report['ip_journal'] = $dry
        ? (int) $db->value('SELECT COUNT(*) FROM audit_log WHERE ip IS NOT NULL AND created_at < ?', [$before($r['audit_ip'])])
        : $db->run('UPDATE audit_log SET ip = NULL WHERE ip IS NOT NULL AND created_at < ?', [$before($r['audit_ip'])])->rowCount();

    if (!$dry && array_sum($report) > 0) {
        Audit::log(null, 'privacy.purge', null, null, 'bin/purge.php', $report);
    }
    cli_out(($dry ? '[simulation] ' : '') . json_encode($report, JSON_UNESCAPED_UNICODE));
});
