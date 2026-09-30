<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;
use Cauri\Services\Platforms\HttpClient;

/**
 * Retrouve sur Deezer (recherche publique, gratuite, sans quota journalier) les titres vus dans les classements
 * des plateformes qui n'ont pas encore d'identifiant Deezer (titres venus d'Apple Music, Shazam, YouTube) :
 * ils reçoivent ainsi leur popularité Deezer et leur pochette, comme les autres.
 */
final class DeezerTrackMatcher
{
    public function __construct(private Database $db, private HttpClient $http)
    {
    }

    /** @return array{checked:int, matched:int} */
    public function run(int $limit = 400): array
    {
        $tracks = $this->db->all(
            "SELECT t.id, t.title, a.name AS artist, t.cover_url FROM tracks t JOIN artists a ON a.id = t.artist_id
             WHERE a.status <> 'out_of_scope'
               AND NOT EXISTS (SELECT 1 FROM track_platform_ids p WHERE p.track_id = t.id AND p.platform = 'deezer')
               AND EXISTS (SELECT 1 FROM chart_observations o WHERE o.track_id = t.id AND o.observed_on >= CURDATE() - INTERVAL 30 DAY)
             ORDER BY a.status = 'active' DESC, t.id DESC LIMIT " . max(0, $limit)
        );
        $matched = 0;
        foreach ($tracks as $t) {
            usleep(130_000); // limite Deezer : 50 requêtes par 5 secondes
            try {
                // Recherche simple « artiste titre » (la syntaxe avancée artist:"…" track:"…" ne renvoie plus rien)
                $q = Normalizer::primaryArtist($t['artist']) . ' ' . preg_replace('/\s*[\(\[].*$/u', '', $t['title']);
                $r = json_decode($this->http->request('GET', 'https://api.deezer.com/search?limit=5&q=' . rawurlencode($q))['body'], true);
            } catch (\Throwable) {
                continue;
            }
            foreach ($r['data'] ?? [] as $d) {
                if (Normalizer::trackKey((string) $d['title'], (string) ($d['artist']['name'] ?? '')) === Normalizer::trackKey($t['title'], $t['artist'])) {
                    $this->db->run(
                        "INSERT IGNORE INTO track_platform_ids (track_id, platform, external_id, kind, url, match_status) VALUES (?, 'deezer', ?, 'main', ?, 'auto')",
                        [$t['id'], (string) $d['id'], $d['link'] ?? null]
                    );
                    if (!$t['cover_url'] && !empty($d['album']['cover_xl'])) {
                        $this->db->update('tracks', ['cover_url' => $d['album']['cover_xl']], 'id = :id', ['id' => $t['id']]);
                    }
                    $matched++;
                    break;
                }
            }
        }
        return ['checked' => count($tracks), 'matched' => $matched];
    }
}
