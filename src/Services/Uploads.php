<?php

namespace Cauri\Services;

use Cauri\Core\Config;

/** Captures d'écran des déclarations : stockées hors du dossier public, jamais servies directement. */
final class Uploads
{
    private const ALLOWED = ['image/png' => 'png', 'image/jpeg' => 'jpg', 'image/webp' => 'webp'];

    /**
     * Valide et range un fichier envoyé. Retourne le chemin relatif à storage/uploads.
     * @throws \InvalidArgumentException message affichable
     */
    public static function storeImage(?array $file): string
    {
        if (!$file || ($file['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_NO_FILE) {
            throw new \InvalidArgumentException(t('submit.error_screenshot_required'));
        }
        if ($file['error'] !== UPLOAD_ERR_OK || !is_uploaded_file($file['tmp_name'])) {
            throw new \InvalidArgumentException(t('submit.error_upload'));
        }
        if ($file['size'] > (int) Config::get('app.security.upload_max_bytes')) {
            throw new \InvalidArgumentException(t('submit.error_too_big'));
        }
        $mime = (new \finfo(FILEINFO_MIME_TYPE))->file($file['tmp_name']);
        if (!isset(self::ALLOWED[$mime]) || @getimagesize($file['tmp_name']) === false) {
            throw new \InvalidArgumentException(t('submit.error_format'));
        }
        $relative = date('Y/m') . '/' . bin2hex(random_bytes(16)) . '.' . self::ALLOWED[$mime];
        $target = self::path($relative);
        if (!is_dir(dirname($target))) {
            mkdir(dirname($target), 0775, true);
        }
        if (!move_uploaded_file($file['tmp_name'], $target)) {
            throw new \InvalidArgumentException(t('submit.error_upload'));
        }
        return $relative;
    }

    public static function path(string $relative): string
    {
        $relative = str_replace(['..', '\\'], ['', '/'], $relative);
        return BASE_PATH . '/storage/uploads/' . ltrim($relative, '/');
    }
}
