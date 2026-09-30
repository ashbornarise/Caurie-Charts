<?php

namespace Cauri\Services\Import;

use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\PlatformException;

/**
 * Top 200 Shazam par pays (titres les plus recherchés sur les 7 derniers jours), via le fichier CSV
 * public proposé en téléchargement sur shazam.com/charts. Sans clé. Excellente source de découverte :
 * 200 titres par pays, beaucoup d'artistes locaux.
 *
 * Vérifié le 30/09/2026 : Ghana, Côte d'Ivoire et Sénégal ; pas de classement pour le Togo ni le Bénin.
 */
final class ShazamChartSource implements ChartSource
{
    public const SLUGS = ['GH' => 'ghana', 'CI' => 'ivory-coast', 'SN' => 'senegal'];

    private const URL = 'https://www.shazam.com/services/charts/csv/top-200/%s';

    public function __construct(private HttpClient $http)
    {
    }

    public function key(): string
    {
        return 'shazam';
    }

    public function isAvailable(): bool
    {
        return true;
    }

    public function fetch(string $countryCode): ?array
    {
        $slug = self::SLUGS[strtoupper($countryCode)] ?? null;
        if ($slug === null) {
            return null;
        }
        $response = $this->http->request('GET', sprintf(self::URL, $slug), ['User-Agent' => 'Mozilla/5.0 (compatible; CauriCharts/1.0)']);
        if ($response['status'] !== 200) {
            throw new PlatformException('Shazam : réponse inattendue (HTTP ' . $response['status'] . ')');
        }
        return self::parse($response['body']);
    }

    public static function parse(string $csv): array
    {
        $csv = preg_replace('/^\xEF\xBB\xBF/', '', $csv);
        $rows = [];
        foreach (preg_split('/\r\n|\n|\r/', $csv) as $line) {
            $cols = str_getcsv($line);
            if (count($cols) < 3 || !ctype_digit(trim($cols[0]))) {
                continue; // date, en-tête, lignes vides
            }
            $rows[] = ['position' => (int) $cols[0], 'artist' => trim($cols[1]), 'title' => trim($cols[2])];
        }
        return ['observed_on' => date('Y-m-d'), 'rows' => array_values(array_filter($rows, fn ($r) => $r['artist'] !== '' && $r['title'] !== ''))];
    }
}
