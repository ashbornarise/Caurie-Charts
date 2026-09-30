<?php

/**
 * Prépare les fichiers de marque du site à partir du kit fourni (cauri-charts-logos/).
 * À relancer si les logos sources changent.
 *
 *   php -d extension=gd bin/build-brand-assets.php
 *
 * Produit dans public/assets/img/brand/ :
 *   logo.svg, logo-white.svg     logo horizontal recadré (en-tête, pied de page)
 *   monogram.svg                 C violet carré (favicon)
 *   monogram-circle.svg          C violet rond
 *   apple-touch-icon.png         180 x 180
 *   favicon-32.png               32 x 32
 *   logo-share.png               logo horizontal noir recadré, 900 px de large (images de partage)
 */

require __DIR__ . '/cli.php';

cli_run('build-brand-assets', function () {
    $src = BASE_PATH . '/cauri-charts-logos';
    $out = BASE_PATH . '/public/assets/img/brand';
    if (!is_dir($src)) {
        throw new RuntimeException('Dossier cauri-charts-logos introuvable.');
    }
    if (!is_dir($out)) {
        mkdir($out, 0775, true);
    }

    // Zone utile des logos horizontaux mesurée sur les PNG 3000 x 1500 (x 300 à 2697, y 234 à 1266), plus une petite marge
    $crop = function (string $svg, string $viewBox, int $w, int $h): string {
        return preg_replace('/<svg[^>]*>/', sprintf('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="%s" role="img" aria-label="Cauri Charts">', $w, $h, $viewBox), $svg, 1);
    };
    $horizontalBox = '280 214 2437 1072';
    foreach (['logo.svg' => '01-horizontal-noir-transparent/cauri-charts-horizontal-noir.svg', 'logo-white.svg' => '02-horizontal-blanc-transparent/cauri-charts-horizontal-blanc.svg'] as $target => $file) {
        file_put_contents("$out/$target", $crop(file_get_contents("$src/$file"), $horizontalBox, 2437, 1072));
    }
    copy("$src/06-monogramme-violet-carre/cauri-charts-monogramme-violet-carre.svg", "$out/monogram.svg");
    copy("$src/05-monogramme-violet-cercle/cauri-charts-monogramme-violet-cercle.svg", "$out/monogram-circle.svg");

    if (!function_exists('imagecreatefrompng')) {
        cli_out('GD absent : SVG copiés, PNG non générés (relancer avec -d extension=gd).');
        return;
    }
    $resize = function (string $file, int $sx, int $sy, int $sw, int $sh, int $dw, int $dh, string $target): void {
        $im = imagecreatefrompng($file);
        $dst = imagecreatetruecolor($dw, $dh);
        imagealphablending($dst, false);
        imagesavealpha($dst, true);
        imagefill($dst, 0, 0, imagecolorallocatealpha($dst, 0, 0, 0, 127));
        imagecopyresampled($dst, $im, 0, 0, $sx, $sy, $dw, $dh, $sw, $sh);
        imagepng($dst, $target, 9);
    };
    $square = "$src/06-monogramme-violet-carre/cauri-charts-monogramme-violet-carre.png";
    $resize($square, 0, 0, 3000, 3000, 180, 180, "$out/apple-touch-icon.png");
    $resize($square, 0, 0, 3000, 3000, 32, 32, "$out/favicon-32.png");
    $resize("$src/01-horizontal-noir-transparent/cauri-charts-horizontal-noir.png", 280, 214, 2437, 1072, 900, 396, "$out/logo-share.png");

    // Image Open Graph par défaut (1200 x 630) : logo centré sur fond blanc, filet violet
    $og = imagecreatetruecolor(1200, 630);
    imagefill($og, 0, 0, imagecolorallocate($og, 255, 255, 255));
    imagefilledrectangle($og, 0, 606, 1199, 629, imagecolorallocate($og, 0x8B, 0x52, 0xFF));
    $logo = imagecreatefrompng("$out/logo-share.png");
    imagealphablending($og, true);
    imagecopyresampled($og, $logo, 150, 150, 0, 0, 900, 396, 900, 396);
    imagepng($og, BASE_PATH . '/public/assets/img/og-default.png', 9);

    foreach (glob("$out/*") as $f) {
        cli_out(str_pad(basename($f), 24) . round(filesize($f) / 1024, 1) . ' Ko');
    }
});
