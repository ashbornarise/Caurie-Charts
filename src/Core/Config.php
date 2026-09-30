<?php

namespace Cauri\Core;

/** Accès en lecture aux fichiers de config/ avec la notation "fichier.clé.sous_clé". */
final class Config
{
    private static array $items = [];
    private static string $dir = '';

    public static function init(string $dir): void
    {
        self::$dir = $dir;
        self::$items = [];
    }

    public static function get(string $path, mixed $default = null): mixed
    {
        $parts = explode('.', $path);
        $file = array_shift($parts);
        if (!array_key_exists($file, self::$items)) {
            $filePath = self::$dir . '/' . $file . '.php';
            self::$items[$file] = is_file($filePath) ? require $filePath : [];
        }
        $value = self::$items[$file];
        foreach ($parts as $part) {
            if (!is_array($value) || !array_key_exists($part, $value)) {
                return $default;
            }
            $value = $value[$part];
        }
        return $value;
    }

    /** Pour les tests : remplace une valeur en mémoire. */
    public static function set(string $path, mixed $value): void
    {
        $parts = explode('.', $path);
        $file = array_shift($parts);
        self::get($file);
        $ref = &self::$items[$file];
        foreach ($parts as $part) {
            if (!isset($ref[$part]) || !is_array($ref[$part])) {
                $ref[$part] = [];
            }
            $ref = &$ref[$part];
        }
        $ref = $value;
    }
}
