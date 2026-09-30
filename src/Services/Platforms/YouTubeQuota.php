<?php

namespace Cauri\Services\Platforms;

use Cauri\Core\Database;
use Cauri\Core\Env;

/**
 * Compteur de quota YouTube partagé par tous les modules qui appellent l'API directement
 * (découverte, vérification des artistes, chaînes de labels, tendances…), en plus de YouTubeClient.
 * Une réserve est gardée pour le relevé quotidien des vues, qui passe en priorité : sans lui,
 * pas de classement officiel. Le quota se réinitialise à minuit, heure du Pacifique.
 */
final class YouTubeQuota
{
    /** Unités gardées pour le relevé des vues (1 unité pour 50 clips). */
    public const RESERVE = 300;

    /** Réserve les unités si le quota le permet ; false sinon (l'appel doit être reporté). */
    public static function spend(Database $db, int $units, bool $essential = false): bool
    {
        $store = new QuotaStore($db);
        $day = self::day();
        $left = (int) Env::get('YOUTUBE_DAILY_QUOTA', '10000') - $store->used(YouTubeClient::API, $day);
        if ($left - $units < ($essential ? 0 : self::RESERVE)) {
            return false;
        }
        $store->add(YouTubeClient::API, $day, $units);
        return true;
    }

    public static function remaining(Database $db): int
    {
        return max(0, (int) Env::get('YOUTUBE_DAILY_QUOTA', '10000') - (new QuotaStore($db))->used(YouTubeClient::API, self::day()));
    }

    public static function day(): string
    {
        return (new \DateTimeImmutable('now', new \DateTimeZone('America/Los_Angeles')))->format('Y-m-d');
    }
}
