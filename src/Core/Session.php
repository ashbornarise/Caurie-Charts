<?php

namespace Cauri\Core;

/**
 * Session paresseuse : le cookie "cauri_sid" n'est créé qu'au premier besoin (formulaire, langue,
 * admin). Un visiteur qui consulte seulement les classements ne reçoit aucun cookie.
 */
final class Session
{
    public const COOKIE = 'cauri_sid';
    private static bool $https = false;

    /** Reprend une session existante (cookie déjà présent) sans en créer de nouvelle. */
    public static function resume(bool $https): void
    {
        self::$https = $https;
        if (isset($_COOKIE[self::COOKIE])) {
            self::start();
        }
    }

    public static function start(): void
    {
        if (session_status() === PHP_SESSION_ACTIVE || PHP_SAPI === 'cli') {
            return;
        }
        session_name(self::COOKIE);
        session_set_cookie_params([
            'lifetime' => 0,
            'path'     => '/',
            'secure'   => self::$https,
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
        ini_set('session.use_strict_mode', '1');
        session_start();
    }

    public static function get(string $key, mixed $default = null): mixed
    {
        return $_SESSION[$key] ?? $default;
    }

    public static function set(string $key, mixed $value): void
    {
        self::start();
        $_SESSION[$key] = $value;
    }

    public static function forget(string $key): void
    {
        unset($_SESSION[$key]);
    }

    public static function regenerate(): void
    {
        if (session_status() === PHP_SESSION_ACTIVE) {
            session_regenerate_id(true);
        }
    }

    public static function destroy(): void
    {
        $_SESSION = [];
        if (session_status() === PHP_SESSION_ACTIVE) {
            session_destroy();
        }
    }

    public static function flash(string $type, string $message): void
    {
        self::start();
        $_SESSION['_flash'][] = ['type' => $type, 'message' => $message];
    }

    public static function takeFlash(): array
    {
        $flash = $_SESSION['_flash'] ?? [];
        unset($_SESSION['_flash']);
        return $flash;
    }
}
