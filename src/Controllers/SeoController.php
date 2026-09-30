<?php

namespace Cauri\Controllers;

use Cauri\Core\Config;
use Cauri\Core\Request;
use Cauri\Core\Response;

final class SeoController extends Controller
{
    public function robots(Request $request): Response
    {
        $allow = Config::get('app.env') === 'production';
        $body = "User-agent: *\n" . ($allow ? "Disallow: /admin\nDisallow: /partage/\n" : "Disallow: /\n") . 'Sitemap: ' . url('sitemap.xml') . "\n";
        return Response::text($body);
    }

    public function sitemap(Request $request): Response
    {
        $urls = [url('/'), url('methodologie'), url('a-propos'), url('contact'), url('declarer')];
        foreach ($this->charts->countries() as $c) {
            foreach (Config::get('charts') as $code => $chart) {
                if ($chart['public'] && empty($chart['regional'])) {
                    foreach ($chart['periods'] as $p) {
                        $urls[] = url(chart_path($c['code'], $code, $p));
                    }
                }
            }
        }
        $data = $this->charts->sitemapEntries();
        foreach ($data['artists'] as $a) {
            $urls[] = url('artiste/' . $a['slug']);
        }
        foreach ($data['tracks'] as $t) {
            $urls[] = url('titre/' . $t['slug']);
        }
        $xml = '<?xml version="1.0" encoding="UTF-8"?>' . "\n" . '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
        foreach (array_unique($urls) as $u) {
            $xml .= '  <url><loc>' . e($u) . "</loc></url>\n";
        }
        return Response::text($xml . '</urlset>', 'application/xml; charset=utf-8');
    }
}
