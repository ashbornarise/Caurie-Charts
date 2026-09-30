<?php

namespace Cauri\Services\Platforms;

/**
 * YouTube Data API v3 : videos.list, champ statistics (viewCount, likeCount, commentCount).
 *
 * Conditions d'utilisation (YouTube API Services Terms of Service et Developer Policies,
 * à relire avant la mise en production) : l'usage des statistiques publiques via l'API
 * officielle avec une clé du projet est autorisé ; les données doivent rester à jour
 * (relevé quotidien) et l'attribution à YouTube doit figurer sur le site (page Méthodologie).
 * Pas de scraping des pages YouTube.
 *
 * Quota : videos.list coûte 1 unité par appel, jusqu'à 50 identifiants par appel.
 * search.list coûte 100 unités : à n'utiliser que dans l'admin, jamais dans la collecte.
 */
final class YouTubeClient implements PlatformClient
{
    public const API = 'youtube';
    public const BATCH = 50;
    private const BASE = 'https://www.googleapis.com/youtube/v3/';

    public function __construct(
        private string $apiKey,
        private HttpClient $http,
        private QuotaStore $quota,
        private int $dailyQuota = 10000,
        private ?\Closure $today = null,
    ) {
    }

    public function platform(): string
    {
        return 'youtube';
    }

    public function isAvailable(): bool
    {
        return $this->apiKey !== '';
    }

    public function remainingQuota(): int
    {
        return max(0, $this->dailyQuota - $this->quota->used(self::API, $this->day()));
    }

    public function fetchTrackStats(string $trackId): ?array
    {
        return $this->fetchMany([$trackId])[$trackId] ?? null;
    }

    /**
     * Statistiques de plusieurs vidéos, groupées par paquets de 50 (1 unité de quota par paquet).
     * S'arrête proprement quand le quota du jour est épuisé : les vidéos restantes attendent le lendemain.
     * @return array [videoId => stats]
     */
    public function fetchMany(array $videoIds): array
    {
        $this->assertAvailable();
        $out = [];
        foreach (array_chunk(array_values(array_unique($videoIds)), self::BATCH) as $chunk) {
            if ($this->remainingQuota() < 1) {
                throw new QuotaExceededException('Quota YouTube du jour épuisé', $out);
            }
            $data = $this->get('videos', ['part' => 'statistics', 'id' => implode(',', $chunk), 'maxResults' => self::BATCH], 1);
            foreach ($data['items'] ?? [] as $item) {
                $s = $item['statistics'] ?? [];
                $out[$item['id']] = [
                    'plays'      => (int) ($s['viewCount'] ?? 0),
                    'likes'      => isset($s['likeCount']) ? (int) $s['likeCount'] : null, // masqué par certaines chaînes
                    'comments'   => isset($s['commentCount']) ? (int) $s['commentCount'] : null,
                    'popularity' => null,
                ];
            }
        }
        return $out;
    }

    public function searchTrack(string $query): array
    {
        $this->assertAvailable();
        if ($this->remainingQuota() < 100) {
            throw new QuotaExceededException('Quota YouTube insuffisant pour une recherche (100 unités)');
        }
        $data = $this->get('search', ['part' => 'snippet', 'type' => 'video', 'maxResults' => 10, 'q' => $query], 100);
        return array_map(fn ($item) => [
            'external_id'  => $item['id']['videoId'] ?? '',
            'title'        => $item['snippet']['title'] ?? '',
            'artist'       => $item['snippet']['channelTitle'] ?? '',
            'url'          => 'https://www.youtube.com/watch?v=' . ($item['id']['videoId'] ?? ''),
            'image'        => $item['snippet']['thumbnails']['medium']['url'] ?? null,
            'published_at' => isset($item['snippet']['publishedAt']) ? substr($item['snippet']['publishedAt'], 0, 10) : null,
        ], $data['items'] ?? []);
    }

    private function get(string $endpoint, array $params, int $cost): array
    {
        $params['key'] = $this->apiKey;
        // Le quota est compté avant l'appel : une requête en échec consomme aussi des unités chez Google
        $this->quota->add(self::API, $this->day(), $cost);
        $response = $this->http->request('GET', self::BASE . $endpoint . '?' . http_build_query($params));
        $data = json_decode($response['body'], true);
        if ($response['status'] !== 200 || !is_array($data)) {
            $reason = $data['error']['errors'][0]['reason'] ?? ('HTTP ' . $response['status']);
            if (in_array($reason, ['quotaExceeded', 'dailyLimitExceeded'], true)) {
                throw new QuotaExceededException('Quota YouTube refusé par Google');
            }
            throw new PlatformException("YouTube $endpoint : $reason");
        }
        return $data;
    }

    private function assertAvailable(): void
    {
        if (!$this->isAvailable()) {
            throw new PlatformException('YOUTUBE_API_KEY absente du fichier .env');
        }
    }

    private function day(): string
    {
        // Le quota YouTube se réinitialise à minuit, heure du Pacifique
        return $this->today ? ($this->today)() : (new \DateTimeImmutable('now', new \DateTimeZone('America/Los_Angeles')))->format('Y-m-d');
    }
}
