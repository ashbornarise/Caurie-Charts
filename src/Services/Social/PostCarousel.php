<?php

namespace Cauri\Services\Social;

use Cauri\Core\Env;
use Cauri\Services\ShareImage;

/**
 * Carrousel façon magazine de classements (format Instagram 4:5, 1080 × 1350) :
 * - diapositive de couverture : photo du n° 1 en plein cadre, accroche, titre géant, sous-titre, logo ;
 * - une diapositive par performance : photo de l'artiste, rang (« 1er »), artiste, titre et chiffre exact
 *   (vues YouTube relevées, ou meilleure position dans un classement de plateforme).
 * Puis, si ffmpeg est installé, une vidéo MP4 sans son qui enchaîne les diapositives avec un lent zoom.
 * On n'utilise jamais les clips YouTube eux-mêmes (droits des artistes et conditions de YouTube) :
 * la musique s'ajoute dans Instagram ou TikTok depuis leur bibliothèque sous licence.
 */
final class PostCarousel
{
    private const W = 1080;
    private const H = 1350;

    /**
     * @param array $items [['rank', 'title', 'artist', 'image', 'figure_value', 'figure_label']]
     * @return array{slides:list<string>, video:?string}
     */
    public static function render(array $facts, array $cover, array $items, string $name): array
    {
        $fonts = ShareImage::fonts();
        if (!$fonts || !function_exists('imagecreatetruecolor')) {
            return ['slides' => [], 'video' => null];
        }
        $fonts['display'] = is_file($f = BASE_PATH . '/resources/fonts/Anton-Regular.ttf') ? $f : $fonts['bold'];
        $dir = BASE_PATH . PostImage::DIR;
        if (!is_dir($dir)) {
            mkdir($dir, 0775, true);
        }
        $total = count($items) + 1;
        $slides = [];
        $segments = []; // vidéo : [image fixe] ou [clip, calque transparent]
        $slides[] = $cover = self::save(self::coverSlide($fonts, $facts, $cover, ($facts['image'] ?? null) ?: ($items[0]['image'] ?? null), $total), "$dir/$name-1.png");
        $segments[] = ['image' => $cover];
        foreach ($items as $i => $item) {
            $slides[] = $slide = self::save(self::itemSlide($fonts, $item, $i + 2, $total, $facts['source']), "$dir/$name-" . ($i + 2) . '.png');
            $clip = self::findClip($item);
            if ($clip) {
                // Clip fourni par l'artiste ou le label : il passe en fond, classement et chiffres par-dessus
                $overlay = "$dir/$name-" . ($i + 2) . '-calque.png';
                $img = self::itemSlide($fonts, $item, $i + 2, $total, $facts['source'], true);
                imagepng($img, $overlay);
                imagedestroy($img);
                $segments[] = ['clip' => $clip, 'overlay' => $overlay];
            } else {
                $segments[] = ['image' => $slide];
            }
        }
        $slides = array_values(array_filter($slides));
        return ['slides' => array_map('basename', $slides), 'video' => self::video($segments, "$dir/$name.mp4")];
    }

    /**
     * Clip d'un titre dans le dossier des clips (SOCIAL_CLIPS_DIR, par défaut « Clips » dans SOCIAL_EXPORT_DIR) :
     * fichier vidéo dont le nom contient l'artiste et le titre, par exemple « Himra - DJOROBITE.mp4 ».
     * Uniquement des clips fournis ou autorisés par les artistes et labels (jamais téléchargés sur YouTube).
     */
    public static function findClip(array $item): ?string
    {
        $dir = Env::get('SOCIAL_CLIPS_DIR') ?: (Env::get('SOCIAL_EXPORT_DIR') ? rtrim(Env::get('SOCIAL_EXPORT_DIR'), '/\\') . '/Clips' : '');
        if ($dir === '' || !is_dir($dir)) {
            return null;
        }
        $artist = str_replace(' ', '', \Cauri\Services\Import\Normalizer::text($item['artist']));
        $title = str_replace(' ', '', \Cauri\Services\Import\Normalizer::title($item['title']));
        foreach (glob(rtrim($dir, '/\\') . '/*.{mp4,mov,m4v,webm,MP4,MOV}', GLOB_BRACE) ?: [] as $file) {
            $n = str_replace(' ', '', \Cauri\Services\Import\Normalizer::text(pathinfo($file, PATHINFO_FILENAME)));
            if ($title !== '' && str_contains($n, $title) && str_contains($n, $artist)) {
                return $file;
            }
        }
        return null;
    }

    private static function coverSlide(array $fonts, array $facts, array $cover, ?string $photoUrl, int $total): \GdImage
    {
        [$img, $white, $violet] = self::canvas($photoUrl);
        // Titres en haut : voile sombre en haut, léger en bas pour le logo
        // Zone des titres : fond flouté puis assombri, pour que le texte reste lisible même sur une photo chargée
        self::blurZone($img, 0, (int) (self::H * 0.50), true);
        PostImage::gradient($img, 0, (int) (self::H * 0.58), [6, 4, 14], 8, 127, self::W);
        PostImage::gradient($img, (int) (self::H * 0.78), self::H, [0, 0, 0], 127, 60, self::W);
        $y = 120;
        $kicker = PostImage::clean($cover['kicker']);
        self::centered($img, 40, $y, $white, $fonts['bold'], PostImage::fitWidth($kicker, $fonts['bold'], 40, self::W - 140));
        $y += 20;
        $size = 150;
        $headline = mb_strtoupper(PostImage::clean($cover['headline']));
        while ($size > 70 && PostImage::width($headline, $fonts['display'], $size) > self::W - 110) {
            $size -= 6;
        }
        foreach (PostImage::wrap($headline, $fonts['display'], $size, self::W - 110, 2) as $line) {
            $y += (int) ($size * 1.02);
            self::centered($img, $size, $y, $white, $fonts['display'], $line);
        }
        if (!empty($cover['subtitle'])) {
            $y += 70;
            self::centered($img, 50, $y, $white, $fonts['serif'], PostImage::fitWidth(PostImage::clean($cover['subtitle']), $fonts['serif'], 50, self::W - 140));
        }
        self::counter($img, $fonts, 1, $total, $violet, $white);
        self::logo($img, 60, self::H - 190, 210);
        return $img;
    }

    private static function itemSlide(array $fonts, array $item, int $n, int $total, string $source, bool $transparent = false): \GdImage
    {
        [$img, $white, $violet] = self::canvas($transparent ? null : ($item['image'] ?? null), $transparent);
        PostImage::gradient($img, 0, 220, [0, 0, 0], 60, 127, self::W);
        if (!$transparent) {
            self::blurZone($img, (int) (self::H * 0.50), self::H, false); // photo seulement : sur un clip, le calque reste transparent
        }
        PostImage::gradient($img, (int) (self::H * 0.40), self::H, [6, 4, 14], 127, 6, self::W);
        self::logo($img, 56, 52, 180);
        self::counter($img, $fonts, $n, $total, $violet, $white);
        $soft = imagecolorallocatealpha($img, 255, 255, 255, 40);

        // Rang « 1er », « 2e »… centré, suffixe en exposant
        $rank = (string) $item['rank'];
        $suffix = $item['rank'] === 1 ? 'er' : 'e';
        $rs = 170;
        $wRank = PostImage::width($rank, $fonts['serif'], $rs);
        $wSuf = PostImage::width($suffix, $fonts['serif'], 54);
        $x = (int) ((self::W - $wRank - $wSuf - 6) / 2);
        $y = self::H - 520;
        PostImage::text($img, $rs, $x, $y, $white, $fonts['serif'], $rank);
        PostImage::text($img, 54, $x + $wRank + 6, $y - 100, $white, $fonts['serif'], $suffix);

        $y += 92;
        self::centered($img, 70, $y, $white, $fonts['serif'], PostImage::fitWidth(PostImage::clean($item['artist']), $fonts['serif'], 70, self::W - 120));
        $y += 42;
        imagefilledrectangle($img, (int) (self::W / 2) - 9, $y, (int) (self::W / 2) + 9, $y + 18, $violet);
        $y += 78;
        self::centered($img, 50, $y, $white, $fonts['bold'], PostImage::fitWidth(PostImage::clean($item['title']), $fonts['bold'], 50, self::W - 120));
        $y += 74;
        // Chiffre exact : nombre en gras, libellé en capitales
        $value = mb_strtoupper($item['figure_value']);
        $label = ' ' . mb_strtoupper($item['figure_label']);
        $wv = PostImage::width($value, $fonts['bold'], 42);
        $wl = PostImage::width($label, $fonts['sans'], 42);
        if ($wv + $wl > self::W - 100) {
            $label = ' ' . PostImage::fitWidth(trim($label), $fonts['sans'], 42, self::W - 100 - $wv);
            $wl = PostImage::width($label, $fonts['sans'], 42);
        }
        $x = (int) ((self::W - $wv - $wl) / 2);
        PostImage::text($img, 42, $x, $y, $white, $fonts['bold'], $value);
        PostImage::text($img, 42, $x + $wv, $y, $white, $fonts['sans'], $label);
        self::centered($img, 18, self::H - 44, $soft, $fonts['sans'], PostImage::fitWidth('Source : ' . $source, $fonts['sans'], 18, self::W - 120));
        return $img;
    }

    /** Fond : photo recadrée pour remplir 1080 × 1350, sinon violet profond. */
    private static function canvas(?string $photoUrl, bool $transparent = false): array
    {
        $img = imagecreatetruecolor(self::W, self::H);
        if ($transparent) {
            // Calque posé sur un clip : fond transparent, seuls les dégradés et les textes sont dessinés
            imagealphablending($img, false);
            imagesavealpha($img, true);
            imagefilledrectangle($img, 0, 0, self::W, self::H, imagecolorallocatealpha($img, 0, 0, 0, 127));
            imagealphablending($img, true);
            return [$img, imagecolorallocate($img, 255, 255, 255), imagecolorallocate($img, 139, 82, 255)];
        }
        imagealphablending($img, true);
        imagefilledrectangle($img, 0, 0, self::W, self::H, imagecolorallocate($img, 24, 10, 60));
        if ($photo = PostImage::photo($photoUrl)) {
            $pw = imagesx($photo);
            $ph = imagesy($photo);
            $scale = max(self::W / $pw, self::H / $ph);
            $cw = (int) (self::W / $scale);
            $ch = (int) (self::H / $scale);
            imagecopyresampled($img, $photo, 0, 0, (int) (($pw - $cw) / 2), (int) (($ph - $ch) / 4), self::W, self::H, $cw, $ch);
            imagedestroy($photo);
        } else {
            PostImage::gradient($img, 0, self::H, [139, 82, 255], 90, 20, self::W);
        }
        return [$img, imagecolorallocate($img, 255, 255, 255), imagecolorallocate($img, 139, 82, 255)];
    }

    /**
     * Floute une bande horizontale de la photo ; le flou s'estompe progressivement vers le reste de l'image
     * ($top = true : bande du haut, net en dessous ; false : bande du bas, net au-dessus).
     */
    private static function blurZone(\GdImage $img, int $y1, int $y2, bool $top): void
    {
        $h = $y2 - $y1;
        // Flou rapide : réduction puis agrandissement, et quelques passes de flou gaussien
        $small = imagecreatetruecolor(intdiv(self::W, 5), max(1, intdiv($h, 5)));
        imagecopyresampled($small, $img, 0, 0, 0, $y1, imagesx($small), imagesy($small), self::W, $h);
        for ($i = 0; $i < 8; $i++) {
            imagefilter($small, IMG_FILTER_GAUSSIAN_BLUR);
        }
        $blur = imagecreatetruecolor(self::W, $h);
        imagecopyresampled($blur, $small, 0, 0, 0, 0, self::W, $h, imagesx($small), imagesy($small));
        for ($i = 0; $i < 4; $i++) {
            imagefilter($blur, IMG_FILTER_GAUSSIAN_BLUR); // lisse les blocs de l'agrandissement
        }
        $fade = (int) ($h * 0.35); // transition progressive vers la partie nette
        for ($y = 0; $y < $h; $y++) {
            $d = $top ? $h - 1 - $y : $y; // distance à la limite nette
            $pct = $d >= $fade ? 100 : (int) round(100 * $d / $fade);
            if ($pct > 0) {
                imagecopymerge($img, $blur, 0, $y1 + $y, 0, $y, self::W, 1, $pct);
            }
        }
        imagedestroy($small);
        imagedestroy($blur);
    }

    private static function centered(\GdImage $img, int $px, int $y, int $color, string $font, string $text): void
    {
        PostImage::text($img, $px, (int) ((self::W - PostImage::width($text, $font, $px)) / 2), $y, $color, $font, $text);
    }

    private static function counter(\GdImage $img, array $fonts, int $n, int $total, int $violet, int $white): void
    {
        $label = "$n/$total";
        $w = PostImage::width($label, $fonts['bold'], 24) + 36;
        $x = self::W - 50 - $w;
        imagefilledrectangle($img, $x, 50, $x + $w, 96, imagecolorallocatealpha($img, 0, 0, 0, 50));
        PostImage::text($img, 24, $x + 18, 82, $white, $fonts['bold'], $label);
    }

    private static function logo(\GdImage $img, int $x, int $y, int $width): void
    {
        if ($logo = PostImage::whiteLogo()) {
            $h = (int) round(imagesy($logo) * $width / imagesx($logo));
            imagecopyresampled($img, $logo, $x, $y, 0, 0, $width, $h, imagesx($logo), imagesy($logo));
        }
    }

    private static function save(\GdImage $img, string $file): ?string
    {
        $ok = imagejpeg($img, $file = preg_replace('/\.png$/', '.jpg', $file), 90);
        imagedestroy($img);
        return $ok ? $file : null;
    }

    /**
     * Vidéo sans son (ffmpeg, facultatif), 3,5 s par segment : image fixe avec un lent zoom,
     * ou clip de l'artiste (extrait à partir de 20 s) avec le calque du classement par-dessus.
     */
    /**
     * Vidéo façon magazine : couverture, puis chaque titre du Top.
     * - titre avec son clip officiel (fourni par l'artiste ou le label, dossier Clips) : 30 secondes de clip
     *   (son compris, fondu d'entrée et de sortie), classement et chiffre exact par-dessus ;
     * - titre sans clip : photo de l'artiste avec un lent zoom, 4 secondes, sans son.
     * Durée et point de départ des extraits : config/ai.php (social.clip_seconds, social.clip_start).
     */
    private static function video(array $segments, string $out): ?string
    {
        $ffmpeg = Env::get('FFMPEG_PATH', 'ffmpeg');
        if (!$segments || !function_exists('exec')) {
            return null;
        }
        $clipLen = (int) (\Cauri\Core\Config::get('ai.social.clip_seconds') ?? 30);
        $clipStart = (int) (\Cauri\Core\Config::get('ai.social.clip_start') ?? 30);
        $still = 4;
        $inputs = '';
        $filters = [];
        $n = 0;
        foreach ($segments as $i => $seg) {
            if (isset($seg['clip'])) {
                $info = self::probe($ffmpeg, $seg['clip']);
                // Extrait au cœur du clip (après l'intro) ; clip trop court : depuis le début
                $start = $info['duration'] >= $clipStart + $clipLen ? $clipStart : max(0, (int) floor($info['duration'] - $clipLen));
                $len = $info['duration'] > 0 ? min($clipLen, $info['duration'] - $start) : $clipLen;
                $inputs .= ' -ss ' . $start . ' -t ' . $len . ' -i ' . escapeshellarg($seg['clip']) . ' -loop 1 -t ' . $len . ' -i ' . escapeshellarg($seg['overlay']);
                $c = $n++;
                $o = $n++;
                $filters[] = "[$c:v]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,fps=30,setsar=1,trim=duration=$len,setpts=PTS-STARTPTS[c$i];"
                    . "[c$i][$o:v]overlay=0:0:shortest=1,format=yuv420p[v$i]";
                if ($info['audio']) {
                    $fadeOut = max(0, $len - 1.5);
                    $filters[] = "[$c:a]atrim=duration=$len,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,afade=t=in:d=0.6,afade=t=out:st=$fadeOut:d=1.5[a$i]";
                } else {
                    $inputs .= " -f lavfi -t $len -i anullsrc=r=44100:cl=stereo";
                    $s = $n++;
                    $filters[] = "[$s:a]anull[a$i]";
                }
            } else {
                $frames = $still * 30;
                $inputs .= ' -i ' . escapeshellarg($seg['image']) . " -f lavfi -t $still -i anullsrc=r=44100:cl=stereo";
                $k = $n++;
                $s = $n++;
                $filters[] = "[$k:v]scale=1188:1485,zoompan=z='min(zoom+0.0009,1.1)':d=$frames:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1350:fps=30,setsar=1,format=yuv420p[v$i]";
                $filters[] = "[$s:a]anull[a$i]";
            }
        }
        $concat = implode('', array_map(fn ($i) => "[v$i][a$i]", array_keys($segments))) . 'concat=n=' . count($segments) . ':v=1:a=1[out][aout]';
        $cmd = escapeshellarg($ffmpeg) . ' -y -loglevel error' . $inputs . ' -filter_complex ' . escapeshellarg(implode(';', $filters) . ';' . $concat)
            . ' -map "[out]" -map "[aout]" -c:v libx264 -preset veryfast -crf 23 -c:a aac -b:a 160k -movflags +faststart ' . escapeshellarg($out) . ' 2>&1';
        exec($cmd, $output, $code);
        if ($code !== 0) {
            \Cauri\Services\Logger::write('social', 'error', 'ffmpeg a échoué', ['sortie' => array_slice($output, -5)]);
        }
        return $code === 0 && is_file($out) ? basename($out) : null;
    }

    /** Durée (secondes) et présence d'une piste audio, via ffprobe (installé avec ffmpeg). */
    private static function probe(string $ffmpeg, string $file): array
    {
        $ffprobe = preg_replace('/ffmpeg(\.exe)?$/i', 'ffprobe$1', $ffmpeg);
        exec(escapeshellarg($ffprobe) . ' -v error -show_entries format=duration:stream=codec_type -of json ' . escapeshellarg($file), $lines, $code);
        $data = $code === 0 ? json_decode(implode('', $lines), true) : null;
        return [
            'duration' => (float) ($data['format']['duration'] ?? 0),
            'audio'    => in_array('audio', array_column($data['streams'] ?? [], 'codec_type'), true),
        ];
    }
}
