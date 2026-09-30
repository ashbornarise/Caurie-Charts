<?php

namespace Cauri\Services;

use Cauri\Core\Config;

/**
 * Images de partage d'un classement (Instagram, TikTok, WhatsApp, Open Graph).
 * Formats : carré 1080 x 1080 et story 1080 x 1920.
 * Une seule mise en page (liste d'opérations de dessin) rendue en PNG avec GD, ou en SVG
 * si GD ou les polices TTF manquent.
 */
final class ShareImage
{
    public const FORMATS = ['square' => [1080, 1080], 'story' => [1080, 1920]];
    private const INK = '#111111';
    private const ACCENT = '#8B52FF';
    private const MUTED = '#6B6B6B';
    private const LINE = '#E5E5E5';

    public static function pngAvailable(): bool
    {
        return function_exists('imagettftext') && self::fonts() !== null;
    }

    /** PNG si GD et les polices sont disponibles, sinon SVG (?type=svg force le SVG). */
    public static function url(int $runId, string $format): string
    {
        return url("partage/$runId-$format");
    }

    /** Polices : chemins du .env, sinon polices système courantes (Windows, Debian/Ubuntu, CentOS). */
    public static function fonts(): ?array
    {
        $serif = array_filter([Config::get('app.share.font_serif'), BASE_PATH . '/resources/fonts/serif-bold.ttf',
            'C:/Windows/Fonts/georgiab.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSerif-Bold.ttf']);
        $sans = array_filter([Config::get('app.share.font_sans'), BASE_PATH . '/resources/fonts/sans.ttf',
            'C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf']);
        $bold = [BASE_PATH . '/resources/fonts/sans-bold.ttf', 'C:/Windows/Fonts/arialbd.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'];
        $pick = fn (array $list) => array_values(array_filter($list, 'is_file'))[0] ?? null;
        $fonts = ['serif' => $pick($serif), 'sans' => $pick($sans)];
        $fonts['bold'] = $pick($bold) ?? $fonts['sans'];
        return in_array(null, $fonts, true) ? null : $fonts;
    }

    public static function logoFile(): ?string
    {
        $file = BASE_PATH . '/public/assets/img/brand/logo-share.png';
        return is_file($file) ? $file : null;
    }

    /** Opérations de dessin, indépendantes du moteur de rendu. */
    public static function layout(array $run, array $entries, string $format): array
    {
        [$w, $h] = self::FORMATS[$format];
        $story = $format === 'story';
        $pad = 72;
        $ops = [['rect', 0, 0, $w, $h, '#FFFFFF']];

        $y = $story ? 200 : 110;
        $logo = self::logoFile();
        if ($logo) {
            // Logo horizontal (900 x 396) : hauteur 110 px en carré, 150 px en story
            $lh = $story ? 150 : 110;
            $ops[] = ['image', $pad, $y - ($story ? 90 : 70), (int) round($lh * 900 / 396), $lh, $logo];
            $y += $story ? 40 : 30;
        } else {
            $ops[] = ['text', $pad, $y, 34, 'bold', self::INK, mb_strtoupper(brand())];
            $ops[] = ['rect', $pad, $y + 26, 64, 8, self::ACCENT];
        }
        $y += $story ? 150 : 110;
        $title = $run['chart_code'] === 'prime-wa'
            ? country_name('WA') . ' · Top ' . count(array_slice($entries, 0, 20))
            : chart_name($run['chart_code']) . ' · ' . country_name($run['country_code']);
        $ops[] = ['text', $pad, $y, $story ? 72 : 58, 'serif', self::INK, self::fit($title, $story ? 24 : 28)];
        $y += $story ? 66 : 54;
        $ops[] = ['text', $pad, $y, 30, 'sans', self::MUTED, period_label($run)];
        $y += $story ? 80 : 50;

        $rows = array_slice($entries, 0, 10);
        $rowH = $story ? 116 : 64;
        foreach ($rows as $i => $e) {
            $top = $y + $i * $rowH;
            if ($i === 0) {
                $ops[] = ['rect', $pad - 20, $top, $w - 2 * $pad + 40, $rowH - 8, self::ACCENT];
            } else {
                $ops[] = ['rect', $pad, $top - 4, $w - 2 * $pad, 2, self::LINE];
            }
            $base = $top + (int) ($rowH * 0.62);
            $ops[] = ['text', $pad, $base, $story ? 56 : 38, 'serif', self::INK, (string) $e['position']];
            $label = $e['track_id'] ? $e['title'] : $e['artist_name'];
            $sub = $e['track_id'] ? $e['artist_name'] : '';
            if ($story && $sub !== '') {
                $ops[] = ['text', $pad + 110, $base - 14, 40, 'bold', self::INK, self::fit($label, 30)];
                $ops[] = ['text', $pad + 110, $base + 30, 30, 'sans', $i === 0 ? self::INK : self::MUTED, self::fit($sub, 40)];
            } else {
                $text = $sub !== '' ? self::fit($label, 26) . '  ·  ' . self::fit($sub, 22) : self::fit($label, 44);
                $ops[] = ['text', $pad + 90, $base, 30, 'bold', self::INK, $text];
            }
            $m = movement($e);
            $move = match ($m['type']) { 'up' => '+' . $m['value'], 'down' => '-' . $m['value'], 'same' => '=', 'new' => t('move.new_short'), 're' => t('move.re_short') };
            $ops[] = ['text', $w - $pad, $base, $story ? 32 : 26, 'bold', $i === 0 ? self::INK : self::MUTED, $move, 'end'];
        }

        $footer = $h - ($story ? 170 : 56);
        $host = parse_url((string) Config::get('app.url'), PHP_URL_HOST) ?: '';
        $ops[] = ['text', $pad, $footer, 26, 'sans', self::MUTED, t('share.footer')];
        $ops[] = ['text', $w - $pad, $footer, 26, 'bold', self::INK, $host, 'end'];
        return $ops;
    }

    public static function renderSvg(array $ops, string $format): string
    {
        [$w, $h] = self::FORMATS[$format];
        $families = ['serif' => "Georgia, 'Times New Roman', serif", 'sans' => 'Arial, Helvetica, sans-serif', 'bold' => 'Arial, Helvetica, sans-serif'];
        $out = "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"$w\" height=\"$h\" viewBox=\"0 0 $w $h\">";
        foreach ($ops as $op) {
            if ($op[0] === 'rect') {
                $out .= sprintf('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>', $op[1], $op[2], $op[3], $op[4], $op[5]);
            } elseif ($op[0] === 'image') {
                $out .= sprintf('<image x="%d" y="%d" width="%d" height="%d" href="data:image/png;base64,%s"/>', $op[1], $op[2], $op[3], $op[4], base64_encode((string) file_get_contents($op[5])));
            } else {
                $anchor = ($op[7] ?? 'start') === 'end' ? ' text-anchor="end"' : '';
                $weight = $op[4] === 'bold' ? ' font-weight="700"' : ($op[4] === 'serif' ? ' font-weight="700"' : '');
                $out .= sprintf('<text x="%d" y="%d" font-size="%d" font-family="%s" fill="%s"%s%s>%s</text>', $op[1], $op[2], $op[3], e($families[$op[4]]), $op[5], $weight, $anchor, e($op[6]));
            }
        }
        return $out . '</svg>';
    }

    public static function renderPng(array $ops, string $format): string
    {
        [$w, $h] = self::FORMATS[$format];
        $fonts = self::fonts();
        $img = imagecreatetruecolor($w, $h);
        imageantialias($img, true);
        $colors = [];
        $color = function (string $hex) use ($img, &$colors) {
            return $colors[$hex] ??= imagecolorallocate($img, hexdec(substr($hex, 1, 2)), hexdec(substr($hex, 3, 2)), hexdec(substr($hex, 5, 2)));
        };
        foreach ($ops as $op) {
            if ($op[0] === 'rect') {
                imagefilledrectangle($img, $op[1], $op[2], $op[1] + $op[3] - 1, $op[2] + $op[4] - 1, $color($op[5]));
                continue;
            }
            if ($op[0] === 'image') {
                $src = imagecreatefrompng($op[5]);
                imagealphablending($img, true);
                imagecopyresampled($img, $src, $op[1], $op[2], 0, 0, $op[3], $op[4], imagesx($src), imagesy($src));
                imagedestroy($src);
                continue;
            }
            // GD mesure en points : 0,75 convertit les pixels du gabarit
            $size = $op[3] * 0.75;
            $x = $op[1];
            if (($op[7] ?? 'start') === 'end') {
                $box = imagettfbbox($size, 0, $fonts[$op[4]], $op[6]);
                $x -= $box[2] - $box[0];
            }
            imagettftext($img, $size, 0, $x, $op[2], $color($op[5]), $fonts[$op[4]], $op[6]);
        }
        ob_start();
        imagepng($img, null, 6);
        imagedestroy($img);
        return (string) ob_get_clean();
    }

    private static function fit(string $text, int $max): string
    {
        return mb_strlen($text) > $max ? rtrim(mb_substr($text, 0, $max - 1)) . '…' : $text;
    }
}
