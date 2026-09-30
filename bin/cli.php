<?php

/** Outils communs aux scripts en ligne de commande. */

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit('CLI uniquement');
}

require dirname(__DIR__) . '/src/bootstrap.php';

/** Options --cle=valeur et --drapeau. */
function cli_options(array $argv): array
{
    $opts = [];
    foreach (array_slice($argv, 1) as $arg) {
        if (preg_match('/^--([\w-]+)(?:=(.*))?$/s', $arg, $m)) {
            $opts[$m[1]] = $m[2] ?? true;
        } else {
            $opts['_'][] = $arg;
        }
    }
    return $opts;
}

function cli_out(string $message): void
{
    fwrite(STDOUT, $message . PHP_EOL);
}

function cli_err(string $message): void
{
    fwrite(STDERR, $message . PHP_EOL);
}

/** Exécute une tâche en journalisant toute erreur dans storage/logs/cron-AAAA-MM.log. */
function cli_run(string $name, callable $task): never
{
    $started = microtime(true);
    try {
        $task();
        \Cauri\Services\Logger::write('cron', 'info', "$name terminé", ['secondes' => round(microtime(true) - $started, 2)]);
        exit(0);
    } catch (Throwable $e) {
        \Cauri\Services\Logger::error('cron', $e);
        cli_err("ERREUR ($name) : " . $e->getMessage());
        exit(1);
    }
}
