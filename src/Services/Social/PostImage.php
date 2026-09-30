<?php

namespace Cauri\Services\Social;

use Cauri\Services\ShareImage;

/**
 * Visuels des posts, dans l'esprit des magazines de classements (Billboard) :
 * photo de l'artiste en plein cadre, dégradé sombre pour la lisibilité, titre géant en Anton
 * (police libre OFL, resources/fonts), titre du post, puis la liste des meilleures performances.
 * Formats : carré 1080 × 1080 (fil) et story 1080 × 1920.
 */
final class PostImage
{
    public const DIR = '/public/media/social';
    private const FORMATS = ['square' => [1080, 1080], 'story' => [1080, 1920]];
    private const VIOLET = [139, 82, 255];

    /** @return array{square?:string, story?:string} noms des fichiers créés */
    public static function render(array $facts, array $text, string $name): array
    {
        $fonts = ShareImage::fonts();
        if (!$fonts || !function_exists('imagecreatetruecolor')) {
            return [];
        }
        $fonts['display'] = is_file($f = BASE_PATH . '/resources/fonts/Anton-Regular.ttf') ? $f : $fonts['bold'];
        $dir = BASE_PATH . self::DIR;
        if (!is_dir($dir)) {
            mkdir($dir, 0775, true);
        }
        $photo = self::photo($facts['image'] ?? null);
        $items = self::items($facts);
        $headline = self::headline($facts);
        $subtitle = self::clean($text['title']);
        if ($facts['kind'] === 'artist') {
            // Le nom est déjà en géant : sous-titre factuel
            $fans = $facts['artist']['deezer_fans'] ?? null;
            $subtitle = 'Artiste de la semaine' . ($fans ? ' · ' . number_format($fans, 0, ',', ' ') . ' fans sur Deezer' : '');
        } elseif (mb_stripos($subtitle, $headline) !== false || mb_strtoupper($subtitle) === mb_strtoupper($facts['label'] ?? '')) {
            $subtitle = '';
        }
        foreach ($items as &$item) {
            $item['title'] = self::clean($item['title']);
            $item['detail'] = self::clean($item['detail']);
        }
        unset($item);

        $out = [];
        foreach (self::FORMATS as $format => [$w, $h]) {
            $story = $format === 'story';
            $img = imagecreatetruecolor($w, $h);
            imagealphablending($img, true);
            imagefilledrectangle($img, 0, 0, $w, $h, imagecolorallocate($img, 12, 8, 24));

            // 1. Photo en plein cadre (recadrée pour remplir), ou fond violet profond
            if ($photo) {
                $pw = imagesx($photo);
                $ph = imagesy($photo);
                $scale = max($w / $pw, $h / $ph);
                $cw = (int) ($w / $scale);
                $ch = (int) ($h / $scale);
                imagecopyresampled($img, $photo, 0, 0, (int) (($pw - $cw) / 2), (int) (($ph - $ch) / 4), $w, $h, $cw, $ch);
            } else {
                self::gradient($img, 0, $h, [42, 14, 120], 0, 0, $w);
            }

            // 2. Dégradés : léger en haut (logo), fort en bas (textes)
            self::gradient($img, 0, (int) ($h * 0.16), [0, 0, 0], 70, 127, $w);
            $fadeFrom = (int) ($h * ($story ? 0.30 : 0.18));
            self::gradient($img, $fadeFrom, $h, [8, 5, 18], 127, 8, $w);

            $pad = 64;
            $white = imagecolorallocate($img, 255, 255, 255);
            $soft = imagecolorallocatealpha($img, 255, 255, 255, 35);
            $violet = imagecolorallocate($img, ...self::VIOLET);

            // 3. En-tête : logo blanc à gauche, rubrique à droite
            if ($logo = self::whiteLogo()) {
                $lw = 190;
                $lh = (int) round(imagesy($logo) * $lw / imagesx($logo));
                imagecopyresampled($img, $logo, $pad, $story ? 110 : 52, 0, 0, $lw, $lh, imagesx($logo), imagesy($logo));
            }
            $label = mb_strtoupper($facts['label'] ?? $facts['headline']);
            $box = imagettfbbox(15, 0, $fonts['bold'], $label);
            $lwid = $box[2] - $box[0] + 36;
            $lx = $w - $pad - $lwid;
            $ly = $story ? 118 : 60;
            imagefilledrectangle($img, $lx, $ly, $lx + $lwid, $ly + 44, $violet);
            imagettftext($img, 15, 0, $lx + 18, $ly + 30, $white, $fonts['bold'], $label);

            // 4. Bas de l'image, de bas en haut : source, liste, titre du post, titre géant
            $y = $h - ($story ? 150 : 56);
            self::text($img, 17, $pad, $y, $soft, $fonts['sans'], self::fitWidth('Source : ' . $facts['source'], $fonts['sans'], 17, $w - 2 * $pad));
            $y -= $story ? 56 : 44;

            $rows = array_slice($items, 0, $story ? 5 : 4);
            $rowH = $story ? 108 : 78;
            $listTop = $y - count($rows) * $rowH;
            foreach ($rows as $i => $row) {
                $ry = $listTop + $i * $rowH;
                if ($i > 0) {
                    imagefilledrectangle($img, $pad, $ry, $w - $pad, $ry + 1, imagecolorallocatealpha($img, 255, 255, 255, 100));
                }
                $num = (string) $row['rank'];
                $numSize = $story ? 58 : 44;
                self::text($img, $numSize, $pad, $ry + ($story ? 78 : 60), $violet, $fonts['display'], $num);
                $tx = $pad + ($story ? 96 : 78);
                $maxW = $w - $tx - $pad;
                self::text($img, $story ? 34 : 28, $tx, $ry + ($story ? 46 : 36), $white, $fonts['bold'], self::fitWidth($row['title'], $fonts['bold'], $story ? 34 : 28, $maxW));
                self::text($img, $story ? 24 : 20, $tx, $ry + ($story ? 86 : 66), $soft, $fonts['sans'], self::fitWidth($row['detail'], $fonts['sans'], $story ? 24 : 20, $maxW));
            }
            $y = $listTop - ($story ? 40 : 26);

            if ($subtitle !== '') {
                $subSize = $story ? 38 : 30;
                $lines = array_reverse(self::wrap($subtitle, $fonts['bold'], $subSize, $w - 2 * $pad, 2));
                foreach ($lines as $line) {
                    self::text($img, $subSize, $pad, $y, $violet, $fonts['bold'], $line);
                    $y -= (int) ($subSize * 1.3);
                }
                $y -= $story ? 24 : 14;
            }

            $bigSize = $story ? 150 : 112;
            $bigLines = self::wrap(mb_strtoupper($headline), $fonts['display'], $bigSize, $w - 2 * $pad, 2);
            if (count($bigLines) > 1 || self::width($bigLines[0] ?? '', $fonts['display'], $bigSize) > $w - 2 * $pad) {
                $bigSize = (int) ($bigSize * 0.78);
                $bigLines = self::wrap(mb_strtoupper($headline), $fonts['display'], $bigSize, $w - 2 * $pad, 2);
            }
            foreach (array_reverse($bigLines) as $line) {
                self::text($img, $bigSize, $pad - 4, $y, $white, $fonts['display'], $line);
                $y -= (int) ($bigSize * 1.05);
            }

            $file = "$name-$format.png";
            imagepng($img, "$dir/$file", 6);
            imagedestroy($img);
            $out[$format] = $file;
        }
        if ($photo) {
            imagedestroy($photo);
        }
        return $out;
    }

    /** Titre géant : le nom de l'artiste pour « artiste de la semaine », sinon la rubrique. */
    private static function headline(array $facts): string
    {
        return match ($facts['kind']) {
            'artist'          => $facts['artist']['name'],
            'cauri_chart'     => 'Top de la semaine',
            'platform_trends' => 'Les tendances',
            default           => 'Spécial week-end',
        };
    }

    /** Liste des meilleures performances, construite uniquement à partir des faits. */
    public static function items(array $facts): array
    {
        $pos = fn (array $seen) => implode(' · ', array_map(fn ($s) => "{$s['platform']} {$s['country']} n°{$s['position']}", array_slice($seen, 0, 2)));
        $items = [];
        switch ($facts['kind']) {
            case 'cauri_chart':
                foreach ($facts['top'] as $e) {
                    $move = $e['previous_position'] ? ($e['previous_position'] > $e['position'] ? '▲ ' . ($e['previous_position'] - $e['position']) : '') : 'Nouveau';
                    $items[] = ['rank' => (int) $e['position'], 'title' => $e['title'], 'detail' => trim($e['artist'] . ($move ? ' · ' . $move : ''))];
                }
                break;
            case 'artist':
                foreach ($facts['tracks'] as $i => $t) {
                    $items[] = ['rank' => $i + 1, 'title' => $t['title'], 'detail' => $pos($t['seen'])];
                }
                break;
            default:
                foreach ($facts['top'] as $i => $e) {
                    $items[] = ['rank' => $i + 1, 'title' => $e['title'], 'detail' => $e['artist'] . ' · ' . $pos($e['seen'])];
                }
        }
        return $items;
    }

    /** Retire les emojis et pictogrammes (absents des polices : ils s'affichent en carrés). */
    public static function clean(string $text): string
    {
        $text = preg_replace('/[\x{1F000}-\x{1FFFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE00}-\x{FE0F}\x{200D}\x{20E3}]/u', '', $text);
        return trim(preg_replace('/\s{2,}/u', ' ', $text));
    }

    /** Dégradé vertical de $y1 à $y2 : transparence alpha GD de $from à $to (127 = transparent). */
    public static function gradient(\GdImage $img, int $y1, int $y2, array $rgb, int $from, int $to, int $w): void
    {
        $span = max(1, $y2 - $y1);
        for ($y = $y1; $y < $y2; $y++) {
            $t = ($y - $y1) / $span;
            $alpha = (int) round($from + ($to - $from) * ($t * $t * (3 - 2 * $t))); // courbe douce
            imageline($img, 0, $y, $w, $y, imagecolorallocatealpha($img, $rgb[0], $rgb[1], $rgb[2], max(0, min(127, $alpha))));
        }
    }

    /** Logo de partage recoloré en blanc (transparence conservée). */
    public static function whiteLogo(): ?\GdImage
    {
        $file = ShareImage::logoFile();
        if (!$file) {
            return null;
        }
        $src = imagecreatefrompng($file);
        imagealphablending($src, false);
        imagesavealpha($src, true);
        $w = imagesx($src);
        $h = imagesy($src);
        for ($x = 0; $x < $w; $x++) {
            for ($y = 0; $y < $h; $y++) {
                $alpha = (imagecolorat($src, $x, $y) >> 24) & 0x7F;
                imagesetpixel($src, $x, $y, imagecolorallocatealpha($src, 255, 255, 255, $alpha));
            }
        }
        imagealphablending($src, true);
        return $src;
    }

    public static function photo(?string $url): ?\GdImage
    {
        if (!$url || !str_starts_with($url, 'https://')) {
            return null;
        }
        $data = \Cauri\Services\News\FeedImporter::httpGet($url);
        $src = $data ? @imagecreatefromstring($data) : false;
        return $src ?: null;
    }

    public static function text(\GdImage $img, int $px, int $x, int $y, int $color, string $font, string $text): void
    {
        imagettftext($img, $px * 0.75, 0, $x, $y, $color, $font, $text);
    }

    public static function width(string $text, string $font, int $px): int
    {
        $box = imagettfbbox($px * 0.75, 0, $font, $text);
        return $box[2] - $box[0];
    }

    public static function wrap(string $text, string $font, int $px, int $width, int $max): array
    {
        $lines = [];
        $line = '';
        foreach (preg_split('/\s+/u', trim($text)) as $word) {
            $try = $line === '' ? $word : "$line $word";
            if (self::width($try, $font, $px) > $width && $line !== '') {
                $lines[] = $line;
                $line = $word;
            } else {
                $line = $try;
            }
        }
        if ($line !== '') {
            $lines[] = $line;
        }
        if (count($lines) > $max) {
            $lines = array_slice($lines, 0, $max);
            $lines[$max - 1] = self::fitWidth($lines[$max - 1] . '…', $font, $px, $width);
        }
        return $lines;
    }

    public static function fitWidth(string $text, string $font, int $px, int $width): string
    {
        while (mb_strlen($text) > 4 && self::width($text, $font, $px) > $width) {
            $text = rtrim(mb_substr(rtrim($text, '…'), 0, -2)) . '…';
        }
        return $text;
    }
}
