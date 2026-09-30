<?php

namespace Cauri\Services;

/** Journal fichier dans storage/logs (erreurs de l'application et des tâches cron). */
final class Logger
{
    public static function write(string $channel, string $level, string $message, array $context = []): void
    {
        $dir = BASE_PATH . '/storage/logs';
        if (!is_dir($dir)) {
            @mkdir($dir, 0775, true);
        }
        $line = sprintf(
            "[%s] %s.%s %s%s\n",
            date('Y-m-d H:i:s'),
            $channel,
            strtoupper($level),
            $message,
            $context ? ' ' . json_encode($context, JSON_UNESCAPED_UNICODE) : ''
        );
        @file_put_contents($dir . '/' . $channel . '-' . date('Y-m') . '.log', $line, FILE_APPEND | LOCK_EX);
    }

    public static function error(string $channel, \Throwable $e): void
    {
        self::write($channel, 'error', $e->getMessage(), ['file' => $e->getFile() . ':' . $e->getLine()]);
    }
}
