<?php

namespace Cauri\Repositories;

use Cauri\Core\Database;

final class PartnerRepository
{
    public const TIERS = ['officiel', 'media', 'plateforme', 'institution'];
    public const MEDIA_DIR = '/public/media/partners';

    public function __construct(private Database $db)
    {
    }

    /** Partenaires affichés sur le site, dans l'ordre choisi. */
    public function active(): array
    {
        return $this->db->all(
            "SELECT * FROM partners WHERE is_active = 1
             ORDER BY FIELD(tier, 'officiel', 'plateforme', 'media', 'institution'), sort_order, name"
        );
    }

    public function all(): array
    {
        return $this->db->all('SELECT * FROM partners ORDER BY is_active DESC, sort_order, name');
    }

    public function find(int $id): ?array
    {
        return $this->db->one('SELECT * FROM partners WHERE id = ?', [$id]);
    }

    public function save(?int $id, array $data): int
    {
        if ($id) {
            $this->db->update('partners', $data, 'id = :id', ['id' => $id]);
            return $id;
        }
        return $this->db->insert('partners', $data);
    }

    public function delete(int $id): void
    {
        $partner = $this->find($id);
        if ($partner && $partner['logo_path']) {
            $file = BASE_PATH . self::MEDIA_DIR . '/' . basename($partner['logo_path']);
            if (is_file($file)) {
                unlink($file);
            }
        }
        $this->db->run('DELETE FROM partners WHERE id = ?', [$id]);
    }

    /**
     * Range un logo envoyé depuis l'admin (PNG, JPEG ou WebP ; jamais de SVG, qui peut contenir du script).
     * Le logo est réencodé en PNG et limité à 480 × 240 px.
     * @throws \InvalidArgumentException message affichable
     */
    public static function storeLogo(array $file): string
    {
        if (($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK || !is_uploaded_file($file['tmp_name'])) {
            throw new \InvalidArgumentException(t('submit.error_upload'));
        }
        if ($file['size'] > 3_000_000) {
            throw new \InvalidArgumentException(t('submit.error_too_big'));
        }
        $mime = (new \finfo(FILEINFO_MIME_TYPE))->file($file['tmp_name']);
        if (!in_array($mime, ['image/png', 'image/jpeg', 'image/webp'], true) || !function_exists('imagecreatefromstring')) {
            throw new \InvalidArgumentException(t('submit.error_format'));
        }
        $src = @imagecreatefromstring((string) file_get_contents($file['tmp_name']));
        if (!$src) {
            throw new \InvalidArgumentException(t('submit.error_format'));
        }
        $w = imagesx($src);
        $h = imagesy($src);
        $scale = min(1, 480 / $w, 240 / $h);
        $tw = max(1, (int) round($w * $scale));
        $th = max(1, (int) round($h * $scale));
        $dst = imagecreatetruecolor($tw, $th);
        imagealphablending($dst, false);
        imagesavealpha($dst, true);
        imagefill($dst, 0, 0, imagecolorallocatealpha($dst, 0, 0, 0, 127));
        imagecopyresampled($dst, $src, 0, 0, 0, 0, $tw, $th, $w, $h);
        $dir = BASE_PATH . self::MEDIA_DIR;
        if (!is_dir($dir)) {
            mkdir($dir, 0775, true);
        }
        $name = bin2hex(random_bytes(12)) . '.png';
        imagepng($dst, $dir . '/' . $name, 6);
        imagedestroy($src);
        imagedestroy($dst);
        return $name;
    }
}
