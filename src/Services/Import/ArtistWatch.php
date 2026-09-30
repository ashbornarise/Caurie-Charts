<?php

namespace Cauri\Services\Import;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Core\Env;
use Cauri\Services\Platforms\HttpClient;

/**
 * Liste de suivi (config/watchlist.php) : ajoute au catalogue des artistes absents des classements
 * de plateformes et suit les chaînes YouTube de labels. Tout est gratuit :
 * - artiste : profil Deezer (photo, fans) et ses 10 titres les plus écoutés sur Deezer ;
 * - chaîne : 25 dernières vidéos (1 à 2 unités de quota), chaque clip « Artiste - Titre » est ajouté.
 * Les nouveaux artistes passent ensuite par ArtistClassifier (pays vérifié, scène, diaspora).
 */
final class ArtistWatch
{
    private const CACHE = '/storage/cache/watch-channels.json';

    public function __construct(private Database $db, private HttpClient $http)
    {
    }

    /** @return list<string> compte rendu */
    public function run(): array
    {
        $cfg = Config::get('watchlist');
        $report = [];
        foreach ($cfg['artists'] ?? [] as $name => $hint) {
            $report[] = $this->artist((string) $name, $hint);
        }
        foreach ($this->channels($cfg) as $channelId => [$label, $country]) {
            $report[] = $this->channel($channelId, $label, $country);
        }
        return $report;
    }

    private function artist(string $name, ?string $hint): string
    {
        $found = json_decode($this->http->request('GET', 'https://api.deezer.com/search/artist?limit=10&q=' . rawurlencode($name))['body'], true);
        $profile = ArtistEnricher::bestMatch($found['data'] ?? [], $name);
        if (!$profile) {
            return "$name : introuvable sur Deezer";
        }
        $top = json_decode($this->http->request('GET', 'https://api.deezer.com/artist/' . $profile['id'] . '/top?limit=10')['body'], true);
        $countryId = $this->countryId($hint);
        $importer = new ChartImporter($this->db);
        $new = 0;
        $artistId = null;
        foreach ($top['data'] ?? [] as $t) {
            [$trackId, $stats] = $importer->upsertTrack([
                'title'       => (string) $t['title'],
                'artist'      => $name,
                'external_id' => (string) $t['id'],
                'url'         => $t['link'] ?? null,
                'image'       => $t['album']['cover_xl'] ?? null,
            ], 'deezer', $countryId);
            $new += $stats['new_tracks'];
            $artistId ??= (int) $this->db->value('SELECT artist_id FROM tracks WHERE id = ?', [$trackId]);
        }
        if (!$artistId) {
            return "$name : aucun titre sur Deezer";
        }
        $artist = $this->db->one('SELECT status, origin_note FROM artists WHERE id = ?', [$artistId]);
        $data = ['deezer_id' => $profile['id'], 'fans' => $profile['nb_fan'], 'image_url' => $profile['image'], 'profile_checked_at' => gmdate('Y-m-d H:i:s')];
        if ($artist['status'] === 'pending' && !str_contains((string) $artist['origin_note'], 'suivi')) {
            // Réexamen avec les indices de scène ; le pays pressenti reste une indication, pas une confirmation
            $data['origin_checked_at'] = null;
            $data['guessed_country_id'] = $hint ? $countryId : null;
        }
        $this->db->update('artists', $data, 'id = :id', ['id' => $artistId]);
        return "$name : suivi (" . ($artist['status'] === 'active' ? 'confirmé' : $artist['status']) . "), $new nouveaux titres";
    }

    /** Chaînes suivies : identifiants donnés, ou recherchés une fois par leur nom puis mémorisés. */
    private function channels(array $cfg): array
    {
        $key = Env::get('YOUTUBE_API_KEY');
        $cacheFile = BASE_PATH . self::CACHE;
        $cache = is_file($cacheFile) ? (json_decode((string) file_get_contents($cacheFile), true) ?: []) : [];
        $out = [];
        foreach ($cfg['channels'] ?? [] as $id => $country) {
            $out[$id] = [$id, $country];
        }
        foreach ($cfg['channel_names'] ?? [] as $label => $country) {
            if (!isset($cache[$label]) && $key !== '' && \Cauri\Services\Platforms\YouTubeQuota::spend($this->db, 100)) {
                $r = json_decode($this->http->request('GET', 'https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&maxResults=3&q='
                    . rawurlencode($label) . '&key=' . rawurlencode($key))['body'], true);
                foreach ($r['items'] ?? [] as $item) {
                    if (Normalizer::text($item['snippet']['title']) === Normalizer::text($label)) {
                        $cache[$label] = $item['snippet']['channelId'];
                        break;
                    }
                }
                $cache[$label] ??= false;
                @mkdir(dirname($cacheFile), 0775, true);
                file_put_contents($cacheFile, json_encode($cache, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
            }
            if (!empty($cache[$label])) {
                $out[$cache[$label]] = [$label, $country];
            }
        }
        return $out;
    }

    private function channel(string $channelId, string $label, ?string $country): string
    {
        $key = Env::get('YOUTUBE_API_KEY');
        if ($key === '') {
            return "$label : clé YouTube absente";
        }
        if (!\Cauri\Services\Platforms\YouTubeQuota::spend($this->db, 2)) {
            return "$label : quota YouTube du jour atteint, reporté";
        }
        $api = 'https://www.googleapis.com/youtube/v3/';
        $c = json_decode($this->http->request('GET', $api . 'channels?part=contentDetails&id=' . rawurlencode($channelId) . '&key=' . rawurlencode($key))['body'], true);
        $playlist = $c['items'][0]['contentDetails']['relatedPlaylists']['uploads'] ?? null;
        if (!$playlist) {
            return "$label : chaîne introuvable";
        }
        $items = json_decode($this->http->request('GET', $api . 'playlistItems?part=snippet&maxResults=25&playlistId=' . rawurlencode($playlist) . '&key=' . rawurlencode($key))['body'], true)['items'] ?? [];
        // Même format que la recherche YouTube, pour réutiliser le filtre « Artiste - Titre »
        $videos = array_map(fn ($it) => [
            'id'      => ['videoId' => $it['snippet']['resourceId']['videoId'] ?? ''],
            'snippet' => $it['snippet'],
        ], $items);
        $rows = YouTubeDiscoverySource::parse($videos)['rows'];
        $importer = new ChartImporter($this->db);
        $new = 0;
        foreach ($rows as $row) {
            $new += $importer->upsertTrack($row, 'youtube_discovery', $this->countryId($country))[1]['new_tracks'];
        }
        return "$label : " . count($rows) . " clips lus, $new nouveaux titres";
    }

    private function countryId(?string $code): int
    {
        return (int) ($this->db->value('SELECT id FROM countries WHERE code = ?', [$code ?? ''])
            ?: $this->db->value('SELECT id FROM countries WHERE is_pilot = 1 LIMIT 1'));
    }
}
