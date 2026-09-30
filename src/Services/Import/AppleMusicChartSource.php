<?php

namespace Cauri\Services\Import;

use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\PlatformException;

/**
 * Classement Apple Music « les plus écoutés » par pays, via le flux public d'Apple
 * (Apple Marketing Tools, JSON, sans clé, mis à jour chaque jour, 100 titres au plus).
 *
 * Vérifié le 29/09/2026 : disponible pour le Bénin, la Côte d'Ivoire, le Sénégal et le Ghana ;
 * le Togo répond en erreur (pas de classement Apple Music publié pour ce pays).
 *
 * Conditions : ces flux sont faits pour être réutilisés à des fins de promotion, avec un lien
 * vers Apple Music. Les pochettes restent la propriété de leurs ayants droit.
 */
final class AppleMusicChartSource implements ChartSource
{
    private const URL = 'https://rss.marketingtools.apple.com/api/v2/%s/music/most-played/%d/songs.json';

    public function __construct(private HttpClient $http, private int $limit = 100)
    {
    }

    public function key(): string
    {
        return 'apple_music';
    }

    public function isAvailable(): bool
    {
        return true;
    }

    public function fetch(string $countryCode): ?array
    {
        $response = $this->http->request('GET', sprintf(self::URL, strtolower($countryCode), $this->limit));
        if (in_array($response['status'], [400, 404, 500], true)) {
            return null; // pays non couvert par Apple Music
        }
        $data = json_decode($response['body'], true);
        if ($response['status'] !== 200 || !isset($data['feed']['results'])) {
            throw new PlatformException('Apple Music : réponse inattendue (HTTP ' . $response['status'] . ')');
        }
        return self::parse($data);
    }

    public static function parse(array $data): array
    {
        $updated = isset($data['feed']['updated']) ? strtotime($data['feed']['updated']) : time();
        $rows = [];
        foreach (array_values($data['feed']['results']) as $i => $r) {
            $rows[] = [
                'position'     => $i + 1,
                'title'        => (string) $r['name'],
                'artist'       => (string) $r['artistName'],
                'external_id'  => (string) $r['id'],
                'url'          => $r['url'] ?? null,
                // Pochette en 600 px au lieu de 100 px
                'image'        => isset($r['artworkUrl100']) ? str_replace('100x100bb', '600x600bb', $r['artworkUrl100']) : null,
                'release_date' => $r['releaseDate'] ?? null,
            ];
        }
        return ['observed_on' => date('Y-m-d', $updated ?: time()), 'rows' => $rows];
    }
}
