<?php

namespace Cauri\Controllers;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Core\Response;
use Cauri\Core\Session;
use Cauri\Core\Translator;
use Cauri\Core\View;
use Cauri\Repositories\ChartRepository;

abstract class Controller
{
    public const PERIOD_SLUGS = ['semaine' => 'week', 'mois' => 'month', 'annee' => 'year', 'tout' => 'all'];

    protected Database $db;
    protected ChartRepository $charts;

    public function __construct()
    {
        $this->db = Database::connection();
        $this->charts = new ChartRepository($this->db);
    }

    /** Langue : choix explicite du visiteur, sinon langue du pays affiché, sinon langue par défaut. */
    protected function useLocale(?array $country = null): void
    {
        $chosen = Session::get('locale');
        if (is_string($chosen) && in_array($chosen, Config::get('app.locales'), true)) {
            Translator::setLocale($chosen);
        } elseif ($country) {
            Translator::setLocale($country['locale']);
        }
    }

    /** Pages de contenu placées dans la grille à deux colonnes par le layout (avec l'encadré latéral). */
    private const WITH_ASIDE = ['methodology', 'about', 'contact', 'submit', 'legal', 'news', 'news-item', 'artist', 'track', 'partners-page'];

    protected function page(string $template, array $data = [], int $status = 200): Response
    {
        if (in_array($template, self::WITH_ASIDE, true) && !isset($data['aside'])) {
            // Faits du pays de l'artiste ou du titre affiché, sinon du pays pilote
            $code = $data['artist']['country_code'] ?? $data['track']['country_code'] ?? (string) \Cauri\Core\Config::get('app.pilot_country');
            $country = $this->charts->country($code) ?? ($this->charts->countries()[0] ?? null);
            if ($country) {
                $data['aside'] = $this->aside($country);
                $data['asideWrap'] = true;
            }
        }
        $data += [
            'countries' => $this->charts->countries(),
            'flash'     => Session::takeFlash(),
            'meta'      => [],
        ];
        $data['meta'] += [
            'title'       => brand(),
            'description' => t('meta.default_description'),
            'url'         => url($_SERVER['REQUEST_URI'] ?? '/'),
            'image'       => url('assets/img/og-default.png'),
            'type'        => 'website',
        ];
        return View::page($template, $data, $status);
    }

    /** Données de l'encadré latéral : faits de la semaine du pays, actualités, anecdote. */
    protected function aside(array $country): array
    {
        return [
            'country'  => $country,
            'insights' => (new \Cauri\Services\Insights($this->db, $this->charts))->forCountry($country),
            'news'     => (new \Cauri\Repositories\NewsRepository($this->db))->latest(4, $country['id'] !== null ? (int) $country['id'] : null),
        ];
    }

    public static function periodSlug(string $type): string
    {
        return array_flip(self::PERIOD_SLUGS)[$type];
    }
}
