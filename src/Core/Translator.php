<?php

namespace Cauri\Core;

/** Traductions dans lang/{locale}.php. Repli sur le français, puis sur la clé. */
final class Translator
{
    private static string $locale = 'fr';
    private static array $cache = [];
    private static string $dir = '';

    public static function init(string $dir, string $locale): void
    {
        self::$dir = $dir;
        self::$locale = $locale;
    }

    public static function setLocale(string $locale): void
    {
        self::$locale = $locale;
    }

    public static function locale(): string
    {
        return self::$locale;
    }

    public static function get(string $key, array $params = []): string
    {
        $text = self::lines(self::$locale)[$key] ?? self::lines('fr')[$key] ?? $key;
        foreach ($params as $name => $value) {
            $text = str_replace(':' . $name, (string) $value, $text);
        }
        return $text;
    }

    private static function lines(string $locale): array
    {
        if (!isset(self::$cache[$locale])) {
            $file = self::$dir . '/' . $locale . '.php';
            self::$cache[$locale] = is_file($file) ? require $file : [];
        }
        return self::$cache[$locale];
    }
}
