<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;
use Cauri\Services\Platforms\HttpClient;

/**
 * Popularité Deezer des titres des artistes suivis d'un pays (API publique, sans clé).
 * Deezer attribue à chaque titre un score de popularité (« rank ») mis à jour en continu.
 * On classe les titres des artistes confirmés du pays selon ce score : c'est ce qui rend visibles
 * les pays sans classement publié par les plateformes (Togo, Bénin), et les artistes locaux ailleurs.
 */
final class DeezerPopularitySource implements ChartSource
{
    public function __construct(private Database $db, private HttpClient $http, private int $size = 200)
    {
    }

    public function key(): string
    {
        return 'deezer_popularity';
    }

    public function isAvailable(): bool
    {
        return true;
    }

    public function fetch(string $countryCode): ?array
    {
        $artists = $this->db->all(
            "SELECT a.name, a.deezer_id FROM artists a JOIN countries c ON c.id = a.submission_country_id
             WHERE a.status = 'active' AND a.deezer_id IS NOT NULL AND c.code = ?",
            [strtoupper($countryCode)]
        );
        if (!$artists) {
            return null;
        }
        $tracks = [];
        foreach ($artists as $a) {
            usleep(120_000); // limite Deezer : 50 requêtes par 5 secondes
            try {
                $top = json_decode($this->http->request('GET', 'https://api.deezer.com/artist/' . (int) $a['deezer_id'] . '/top?limit=50')['body'], true);
            } catch (\Throwable) {
                continue;
            }
            foreach ($top['data'] ?? [] as $t) {
                // Titres dont il est l'artiste principal (ses featurings comptent chez l'autre artiste)
                if (Normalizer::artistKey((string) ($t['artist']['name'] ?? '')) !== Normalizer::artistKey($a['name']) || empty($t['rank'])) {
                    continue;
                }
                $tracks[(string) $t['id']] = [
                    'rank_score'  => (int) $t['rank'],
                    'title'       => (string) $t['title'],
                    'artist'      => $a['name'],
                    'external_id' => (string) $t['id'],
                    'platform'    => 'deezer',
                    'url'         => $t['link'] ?? null,
                    'image'       => $t['album']['cover_xl'] ?? null,
                ];
            }
        }
        return self::rank(array_values($tracks), $this->size);
    }

    /** Classement par score de popularité décroissant. */
    public static function rank(array $tracks, int $size): array
    {
        usort($tracks, fn ($a, $b) => $b['rank_score'] <=> $a['rank_score']);
        $rows = [];
        foreach (array_slice($tracks, 0, $size) as $i => $t) {
            unset($t['rank_score']);
            $rows[] = ['position' => $i + 1] + $t;
        }
        return ['observed_on' => date('Y-m-d'), 'rows' => $rows];
    }
}
