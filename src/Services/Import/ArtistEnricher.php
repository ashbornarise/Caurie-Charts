<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;
use Cauri\Services\Platforms\HttpClient;

/**
 * Complète les profils d'artistes avec l'API publique Deezer (sans clé) : photo et nombre de fans.
 * L'artiste Deezer est retrouvé par un de ses titres importés depuis Deezer, sinon par une recherche
 * sur le nom (correspondance exacte du nom normalisé, puis le profil qui a le plus de fans).
 * Chaque profil est revérifié au plus tous les 7 jours.
 */
final class ArtistEnricher
{
    private const API = 'https://api.deezer.com';

    public function __construct(private Database $db, private HttpClient $http, private int $pauseMs = 120)
    {
    }

    /** @return array{checked:int, found:int} */
    public function run(int $limit = 80): array
    {
        $artists = $this->db->all(
            "SELECT id, name, deezer_id FROM artists
             WHERE status <> 'out_of_scope' AND (profile_checked_at IS NULL OR profile_checked_at < NOW() - INTERVAL 7 DAY)
             ORDER BY profile_checked_at IS NOT NULL, id LIMIT " . max(0, $limit)
        );
        $stats = ['checked' => 0, 'found' => 0];
        foreach ($artists as $a) {
            $profile = $this->profile((int) $a['id'], $a['name'], $a['deezer_id'] ? (int) $a['deezer_id'] : null);
            $data = ['profile_checked_at' => gmdate('Y-m-d H:i:s')];
            if ($profile) {
                $data += ['deezer_id' => $profile['id'], 'fans' => $profile['nb_fan'], 'image_url' => $profile['image']];
                $stats['found']++;
            }
            $this->db->update('artists', $data, 'id = :id', ['id' => $a['id']]);
            $stats['checked']++;
        }
        return $stats;
    }

    private function profile(int $artistId, string $name, ?int $deezerId): ?array
    {
        $deezerId ??= $this->idFromTracks($artistId, $name);
        if ($deezerId) {
            $artist = $this->get('/artist/' . $deezerId);
            if ($artist && isset($artist['id'])) {
                return self::normalize($artist);
            }
        }
        $found = $this->get('/search/artist?limit=10&q=' . rawurlencode($name));
        return self::bestMatch($found['data'] ?? [], $name);
    }

    /** Identifiant Deezer de l'artiste, lu sur un titre importé depuis le classement Deezer. */
    private function idFromTracks(int $artistId, string $name): ?int
    {
        $trackId = $this->db->value(
            "SELECT p.external_id FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id
             WHERE t.artist_id = ? AND p.platform = 'deezer' LIMIT 1",
            [$artistId]
        );
        if (!$trackId) {
            return null;
        }
        $track = $this->get('/track/' . rawurlencode((string) $trackId));
        foreach (array_merge([$track['artist'] ?? []], $track['contributors'] ?? []) as $c) {
            if (isset($c['id'], $c['name']) && Normalizer::text($c['name']) === Normalizer::text($name)) {
                return (int) $c['id'];
            }
        }
        return null;
    }

    /** Parmi les résultats de recherche : nom identique (normalisé), puis le plus de fans. */
    public static function bestMatch(array $results, string $name): ?array
    {
        $key = Normalizer::text($name);
        $matches = array_filter($results, fn ($r) => isset($r['name']) && Normalizer::text($r['name']) === $key);
        if (!$matches) {
            return null;
        }
        usort($matches, fn ($a, $b) => ($b['nb_fan'] ?? 0) <=> ($a['nb_fan'] ?? 0));
        return self::normalize($matches[0]);
    }

    private static function normalize(array $artist): array
    {
        $image = $artist['picture_xl'] ?? ($artist['picture_big'] ?? null);
        // Deezer renvoie une silhouette grise quand l'artiste n'a pas de photo : on garde les initiales
        if ($image && preg_match('#/images/artist//#', $image)) {
            $image = null;
        }
        return ['id' => (int) $artist['id'], 'nb_fan' => (int) ($artist['nb_fan'] ?? 0), 'image' => $image];
    }

    private function get(string $path): ?array
    {
        usleep($this->pauseMs * 1000); // limite Deezer : 50 requêtes par 5 secondes
        try {
            $response = $this->http->request('GET', self::API . $path);
        } catch (\Throwable) {
            return null;
        }
        $data = json_decode($response['body'], true);
        return ($response['status'] === 200 && is_array($data) && !isset($data['error'])) ? $data : null;
    }
}
