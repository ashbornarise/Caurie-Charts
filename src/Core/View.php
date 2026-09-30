<?php

namespace Cauri\Core;

/** Gabarits PHP : chaque page est rendue puis insérée dans un layout. */
final class View
{
    private static string $dir = '';

    public static function init(string $dir): void
    {
        self::$dir = $dir;
    }

    public static function render(string $template, array $data = [], ?string $layout = 'layout'): string
    {
        $content = self::partial($template, $data);
        if ($layout === null) {
            return $content;
        }
        return self::partial($layout, $data + ['content' => $content]);
    }

    public static function partial(string $template, array $data = []): string
    {
        $file = self::$dir . '/' . $template . '.php';
        if (!is_file($file)) {
            throw new \RuntimeException("Gabarit introuvable : $template");
        }
        extract($data, EXTR_SKIP);
        ob_start();
        try {
            require $file;
        } catch (\Throwable $e) {
            ob_end_clean();
            throw $e;
        }
        return (string) ob_get_clean();
    }

    public static function page(string $template, array $data = [], int $status = 200, string $layout = 'layout'): Response
    {
        return new Response(self::render($template, $data, $layout), $status);
    }
}
