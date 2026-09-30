<?php

namespace Cauri\Services\Import;

use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\PlatformException;

/**
 * Découverte des nouveaux clips pour les pays sans classement de plateforme (Togo, Bénin) :
 * recherche YouTube des clips musicaux publiés ces 21 derniers jours, triés par nombre de vues.
 * Coût : 100 unités de quota par recherche (config/import.php : 2 recherches par pays et par jour).
 *
 * Ce n'est pas un classement de plateforme mais la liste des nouveaux clips les plus vus :
 * seuls les titres au format « Artiste - Titre » sont gardés (pas de teasers, mix, interviews).
 * Le pays des artistes est ensuite vérifié par ArtistClassifier (chaîne YouTube, Wikipédia, IA).
 */
final class YouTubeDiscoverySource implements ChartSource
{
    public const QUERIES = [
        'TG' => ['togo clip officiel', 'musique togolaise 2026'],
        'BJ' => ['bénin clip officiel', 'musique béninoise 2026'],
    ];

    private const URL = 'https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&videoCategoryId=10&order=viewCount&maxResults=50&publishedAfter=%s&q=%s&key=%s';

    private const EXCLUDE = '/\b(teaser|extrait|mix|mixtape vol|interview|s[\'’]exprime|live session|challenge|karaok[eé]|reaction|réaction|making of|behind|playlist|compilation|non[- ]stop)\b/iu';

    public function __construct(private HttpClient $http, private string $apiKey)
    {
    }

    public function key(): string
    {
        return 'youtube_discovery';
    }

    public function isAvailable(): bool
    {
        return $this->apiKey !== '';
    }

    public function fetch(string $countryCode): ?array
    {
        $queries = self::QUERIES[strtoupper($countryCode)] ?? null;
        if ($queries === null) {
            return null;
        }
        $after = gmdate('Y-m-d\TH:i:s\Z', strtotime('-21 days'));
        $items = [];
        foreach ($queries as $q) {
            $response = $this->http->request('GET', sprintf(self::URL, rawurlencode($after), rawurlencode($q), rawurlencode($this->apiKey)));
            $data = json_decode($response['body'], true);
            if ($response['status'] !== 200 || !isset($data['items'])) {
                throw new PlatformException('YouTube découverte : ' . ($data['error']['message'] ?? 'HTTP ' . $response['status']));
            }
            foreach ($data['items'] as $i => $item) {
                $id = $item['id']['videoId'] ?? null;
                // Rang combiné : meilleure place obtenue dans l'une des recherches
                if ($id && (!isset($items[$id]) || $items[$id]['rank'] > $i)) {
                    $items[$id] = ['rank' => $i, 'item' => $item];
                }
            }
        }
        uasort($items, fn ($a, $b) => $a['rank'] <=> $b['rank']);
        return self::parse(array_column($items, 'item'));
    }

    public static function parse(array $items): array
    {
        $rows = [];
        foreach ($items as $v) {
            $videoTitle = html_entity_decode((string) ($v['snippet']['title'] ?? ''), ENT_QUOTES | ENT_HTML5, 'UTF-8');
            if (preg_match(self::EXCLUDE, $videoTitle) || !preg_match('/\s[-–—]\s/u', $videoTitle)) {
                continue;
            }
            [$artist, $title] = YouTubeTrendingSource::split($videoTitle, html_entity_decode((string) ($v['snippet']['channelTitle'] ?? '')));
            if ($artist === '' || $title === '' || mb_strlen($artist) > 60) {
                continue;
            }
            $id = (string) ($v['id']['videoId'] ?? '');
            $rows[] = [
                'position'     => count($rows) + 1,
                'title'        => $title,
                'artist'       => $artist,
                'external_id'  => $id,
                'platform'     => 'youtube',
                'kind'         => 'clip',
                'url'          => 'https://www.youtube.com/watch?v=' . rawurlencode($id),
                'image'        => $v['snippet']['thumbnails']['high']['url'] ?? null,
                'release_date' => isset($v['snippet']['publishedAt']) ? substr($v['snippet']['publishedAt'], 0, 10) : null,
            ];
        }
        return ['observed_on' => date('Y-m-d'), 'rows' => $rows];
    }
}
