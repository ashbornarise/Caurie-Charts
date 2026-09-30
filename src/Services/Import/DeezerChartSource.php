<?php

namespace Cauri\Services\Import;

use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\PlatformException;

/**
 * Classements officiels « Top <pays> » publiés par le compte Deezer Charts (API publique Deezer, sans clé).
 *
 * Vérifié le 30/09/2026 : Deezer publie un classement pour la Côte d'Ivoire et le Sénégal ;
 * pas de classement officiel pour le Togo, le Bénin ni le Ghana (les playlists « Top Togo »
 * trouvées sont faites par des particuliers et ne sont pas utilisées).
 */
final class DeezerChartSource implements ChartSource
{
    /** Playlists du compte Deezer Charts (id 637006841). */
    public const PLAYLISTS = [
        'CI' => 1362497945, // Top Ivory Coast
        'SN' => 1362523075, // Top Senegal
    ];

    private const URL = 'https://api.deezer.com/playlist/%d/tracks?limit=100';

    public function __construct(private HttpClient $http)
    {
    }

    public function key(): string
    {
        return 'deezer';
    }

    public function isAvailable(): bool
    {
        return true;
    }

    public function fetch(string $countryCode): ?array
    {
        $playlist = self::PLAYLISTS[strtoupper($countryCode)] ?? null;
        if ($playlist === null) {
            return null;
        }
        $response = $this->http->request('GET', sprintf(self::URL, $playlist));
        $data = json_decode($response['body'], true);
        if ($response['status'] !== 200 || !isset($data['data']) || isset($data['error'])) {
            throw new PlatformException('Deezer : réponse inattendue (HTTP ' . $response['status'] . ')');
        }
        return self::parse($data);
    }

    public static function parse(array $data): array
    {
        $rows = [];
        foreach (array_values($data['data']) as $i => $t) {
            $rows[] = [
                'position'    => $i + 1,
                'title'       => (string) ($t['title'] ?? ''),
                'artist'      => (string) ($t['artist']['name'] ?? ''),
                'external_id' => (string) ($t['id'] ?? ''),
                'url'         => $t['link'] ?? null,
                'image'       => $t['album']['cover_xl'] ?? ($t['album']['cover_big'] ?? null),
            ];
        }
        return ['observed_on' => date('Y-m-d'), 'rows' => array_values(array_filter($rows, fn ($r) => $r['title'] !== '' && $r['artist'] !== ''))];
    }
}
