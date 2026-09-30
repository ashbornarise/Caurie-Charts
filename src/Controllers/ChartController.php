<?php

namespace Cauri\Controllers;

use Cauri\Core\Config;
use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Services\ShareImage;

final class ChartController extends Controller
{
    /** Pseudo-pays du classement régional des cinq pays (code "WA", sans ligne dans countries). */
    public static function region(): array
    {
        return [
            'id'         => null,
            'code'       => 'WA',
            'chart_size' => (int) Config::get('charts.prime-wa.size', 20),
            'locale'     => (string) Config::get('app.locale', 'fr'),
        ];
    }

    /**
     * Accueil : par défaut le classement total des cinq pays (Prime Chart Afrique de l'Ouest) ;
     * ?pays=bj affiche le classement d'un pays. Les cartes des pays restent visibles.
     */
    public function home(Request $request): Response
    {
        $requested = strtolower($request->str('pays'));
        $regional = $requested === '' || $requested === 'wa';
        $country = $regional ? self::region() : $this->charts->country($requested);
        if (!$country) {
            throw new HttpException(404);
        }
        $this->useLocale($regional ? null : $country);
        $periodType = self::PERIOD_SLUGS[$request->str('periode', 'semaine')] ?? 'week';
        $chartCode = $regional ? 'prime-wa' : 'prime';
        $run = $this->charts->latestRun($country['id'], $chartCode, $periodType);
        $entries = $run ? $this->charts->entries((int) $run['id']) : [];
        // Pas encore de classement officiel : classement en direct des plateformes
        $live = $run ? null : (new \Cauri\Services\Charts\LiveChart($this->db))->build($country['id'], null, (int) $country['chart_size'], 'prime', 20, $periodType);

        // Encarts Buzz, Fresh, Icon : ceux du pays affiché (le classement régional n'en a pas)
        // Encarts Buzz, Fresh, Icon : classement officiel du pays s'il existe, sinon version en direct (aussi pour les cinq pays)
        $highlights = [];
        $liveChart = new \Cauri\Services\Charts\LiveChart($this->db);
        foreach (['buzz', 'fresh', 'icon'] as $code) {
            $r = $regional ? null : $this->charts->latestRun((int) $country['id'], $code, 'week');
            $highlights[$code] = [
                'run'     => $r,
                'entries' => $r ? $this->charts->entries((int) $r['id'], 3) : [],
                'live'    => $r ? [] : $liveChart->build($country['id'], null, 3, $code, (int) $country['chart_size'])['rows'],
            ];
        }

        return $this->page('home', [
            'country'    => $country,
            'regional'   => $regional,
            'chartCode'  => $chartCode,
            'run'        => $run,
            'entries'    => $entries,
            'live'       => $live,
            'periodType' => $periodType,
            'highlights' => $highlights,
            'aside'      => $this->aside($country),
            'numberOnes' => $this->charts->numberOnes(),
            'hotArtists' => $this->charts->hotArtists($regional ? null : (int) $country['id']),
            'homeNews'   =>(new \Cauri\Repositories\NewsRepository($this->db))->latest(3, $regional ? null : (int) $country['id']),
            'partners'   => (new \Cauri\Repositories\PartnerRepository($this->db))->active(),
            'meta'       => [
                'title'       => brand() . ' · ' . t('home.meta_title', ['country' => country_name($country['code']), 'size' => $country['chart_size']]),
                'description' => t($regional ? 'home.meta_description_region' : 'home.meta_description', ['country' => country_name($country['code'])]),
                'image'       => $run ? ShareImage::url((int) $run['id'], 'square') : null,
            ],
        ]);
    }

    /** Classement complet régional (cinq pays), avec historique. */
    public function regional(Request $request): Response
    {
        // Buzz, Fresh, Icon, Legend des cinq pays : ?classement=buzz…
        $code = in_array($request->str('classement'), ['buzz', 'fresh', 'icon', 'legend'], true) ? $request->str('classement') : 'prime-wa';
        return $this->render(self::region(), $code, $request);
    }

    /** Classement complet par pays, type et période, avec historique. */
    public function show(Request $request): Response
    {
        // Sélecteur d'historique envoyé sans JavaScript : ?k=/classements/...
        $target = $request->str('k');
        if ($target !== '' && preg_match('#^/classements/[a-z-]+/([a-z-]+/)?(semaine|mois|annee)/[\dW-]+$#', $target)) {
            return Response::redirect($target, 302);
        }
        $country = $this->charts->country($request->param('country'));
        $chartCode = $request->param('chart');
        $chart = Config::get("charts.$chartCode");
        if (!$country || !$chart || !empty($chart['regional'])) {
            throw new HttpException(404);
        }
        return $this->render($country, $chartCode, $request);
    }

    private function render(array $country, string $chartCode, Request $request): Response
    {
        $chart = Config::get("charts.$chartCode");
        if (!$chart || !$chart['public']) {
            throw new HttpException(404);
        }
        $regional = $country['id'] === null;
        $this->useLocale($regional ? null : $country);
        $periodType = self::PERIOD_SLUGS[$request->param('period', 'semaine')] ?? null;
        if (!$periodType || !in_array($periodType, $chart['periods'], true)) {
            throw new HttpException(404);
        }

        $key = $request->param('key');
        $run = $key !== ''
            ? $this->charts->run($country['id'], $chartCode, $periodType, $key)
            : $this->charts->latestRun($country['id'], $chartCode, $periodType);
        if ($key !== '' && !$run) {
            throw new HttpException(404);
        }

        // Classements des plateformes (vue en direct ou d'une plateforme) : sur le Prime Chart, et par défaut
        // tant que le classement officiel n'est pas publié
        $view = 'official';
        $live = null;
        $liveSources = [];
        $livePeriod = $request->str('periode') === 'tout' ? 'all' : $periodType;
        if ($key === '' && in_array($chartCode, ['prime', 'prime-wa', 'buzz', 'fresh', 'icon', 'legend'], true)) {
            $liveChart = new \Cauri\Services\Charts\LiveChart($this->db);
            $isPrime = in_array($chartCode, ['prime', 'prime-wa'], true);
            // Vue par plateforme : seulement sur le Prime Chart d'un pays
            $liveSources = $isPrime && !$regional ? $liveChart->sources($country['id']) : [];
            $requested = $request->str('vue');
            $view = match (true) {
                $requested === 'officiel'                   => 'official',
                $requested === 'direct'                     => 'live',
                in_array($requested, $liveSources, true)    => $requested,
                default                                     => $run ? 'official' : 'live',
            };
            if ($view !== 'official') {
                $live = $liveChart->build(
                    $country['id'],
                    $view === 'live' ? null : $view,
                    $isPrime || $chartCode === 'legend' ? 100 : 50,
                    $isPrime ? 'prime' : $chartCode,
                    (int) ($country['chart_size'] ?? 20),
                    $livePeriod
                );
                if ($isPrime && $view === 'live') {
                    $live['rows'] = array_slice($live['rows'], 0, 100); // liste longue
                }
            }
        }

        $title = $regional ? $chart['name'] : t('chart.title', ['chart' => $chart['name'], 'country' => country_name($country['code'])]);
        return $this->page('chart', [
            'view'        => $view,
            'livePeriod'  => $livePeriod ?? $periodType,
            'live'        => $live,
            'liveSources' => $regional ? [] : $liveSources,
            'country'    => $country,
            'regional'   => $regional,
            'chartCode'  => $chartCode,
            'chart'      => $chart,
            'periodType' => $periodType,
            'run'        => $run,
            'entries'    => $run ? $this->charts->entries((int) $run['id']) : [],
            'history'    => $this->charts->publishedRuns($country['id'], $chartCode, $periodType),
            'aside'      => $this->aside($country),
            'meta'       => [
                'title'       => $title . ($run ? ' · ' . period_label($run) : '') . ' · ' . brand(),
                'description' => t("chart.description.$chartCode", ['country' => country_name($country['code'])]),
                'image'       => $run ? ShareImage::url((int) $run['id'], 'square') : null,
            ],
        ]);
    }
}
