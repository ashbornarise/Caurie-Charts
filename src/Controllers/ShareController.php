<?php

namespace Cauri\Controllers;

use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Services\ShareImage;

/** Images de partage générées pour chaque classement publié, mises en cache sur disque. */
final class ShareController extends Controller
{
    public function image(Request $request): Response
    {
        $format = $request->param('format');
        $ext = ShareImage::pngAvailable() && $request->str('type') !== 'svg' ? 'png' : 'svg';
        $run = $this->charts->runById((int) $request->param('id'));
        if (!$run || !isset(ShareImage::FORMATS[$format])) {
            throw new HttpException(404);
        }
        $country = $this->charts->country($run['country_code']);
        $this->useLocale($country);

        $cacheFile = sprintf('%s/storage/cache/share/%d-%s-%s.%s', BASE_PATH, $run['id'], $format, substr(md5($run['computed_at'] . \Cauri\Core\Translator::locale()), 0, 10), $ext);
        if (!is_file($cacheFile)) {
            $ops = ShareImage::layout($run, $this->charts->entries((int) $run['id'], 10), $format);
            $body = $ext === 'png' ? ShareImage::renderPng($ops, $format) : ShareImage::renderSvg($ops, $format);
            @file_put_contents($cacheFile, $body, LOCK_EX);
        } else {
            $body = (string) file_get_contents($cacheFile);
        }

        $filename = sprintf('%s-%s-%s-%s.%s', slugify(brand()), strtolower($run['country_code']), $run['chart_code'], $run['period_key'], $ext);
        return new Response($body, 200, [
            'Content-Type'        => $ext === 'png' ? 'image/png' : 'image/svg+xml',
            'Cache-Control'       => 'public, max-age=86400',
            'Content-Disposition' => 'inline; filename="' . $filename . '"',
        ]);
    }
}
