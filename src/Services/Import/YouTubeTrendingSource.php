<?php

namespace Cauri\Services\Import;

use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\PlatformException;

/**
 * Vidéos musicales les plus populaires du moment par pays (YouTube Data API v3,
 * videos.list chart=mostPopular, catégorie Musique). Coût : 1 unité de quota par pays.
 *
 * Vérifié le 30/09/2026 : disponible pour le Ghana et le Sénégal ; YouTube refuse le Togo,
 * le Bénin et la Côte d'Ivoire (code pays non pris en charge par cette liste).
 * L'identifiant de la vidéo est enregistré comme clip YouTube du titre : ses vues sont
 * ensuite relevées chaque jour par bin/collect.php (une fois l'artiste confirmé).
 */
final class YouTubeTrendingSource implements ChartSource
{
    public const COUNTRIES = ['GH', 'SN'];

    private const URL = 'https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&videoCategoryId=10&maxResults=50&regionCode=%s&key=%s';

    public function __construct(private HttpClient $http, private string $apiKey)
    {
    }

    public function key(): string
    {
        return 'youtube_trending';
    }

    public function isAvailable(): bool
    {
        return $this->apiKey !== '';
    }

    public function fetch(string $countryCode): ?array
    {
        $code = strtoupper($countryCode);
        if (!in_array($code, self::COUNTRIES, true)) {
            return null;
        }
        $response = $this->http->request('GET', sprintf(self::URL, $code, rawurlencode($this->apiKey)));
        $data = json_decode($response['body'], true);
        if ($response['status'] !== 200 || !isset($data['items'])) {
            throw new PlatformException('YouTube tendances : réponse inattendue (HTTP ' . $response['status'] . ')');
        }
        return self::parse($data);
    }

    public static function parse(array $data): array
    {
        $rows = [];
        foreach (array_values($data['items']) as $i => $v) {
            [$artist, $title] = self::split((string) ($v['snippet']['title'] ?? ''), (string) ($v['snippet']['channelTitle'] ?? ''));
            if ($artist === '' || $title === '') {
                continue;
            }
            $rows[] = [
                'position'     => $i + 1,
                'title'        => $title,
                'artist'       => $artist,
                'external_id'  => (string) $v['id'],
                'platform'     => 'youtube',
                'kind'         => self::kind((string) ($v['snippet']['title'] ?? '')),
                'url'          => 'https://www.youtube.com/watch?v=' . rawurlencode((string) $v['id']),
                'image'        => $v['snippet']['thumbnails']['high']['url'] ?? null,
                'release_date' => isset($v['snippet']['publishedAt']) ? substr($v['snippet']['publishedAt'], 0, 10) : null,
            ];
        }
        return ['observed_on' => date('Y-m-d'), 'rows' => $rows];
    }

    /**
     * « Artiste - Titre (Clip Officiel) » → [Artiste, Titre].
     * Sans tiret (chaînes « - Topic » notamment), l'artiste est le nom de la chaîne.
     */
    public static function split(string $videoTitle, string $channel): array
    {
        $clean = preg_replace(
            '/\s*[\(\[][^\)\]]*(official|officiel|clip|video|vidéo|audio|lyric|visuali[sz]er|live|prod\.?|dir\.?|by )[^\)\]]*[\)\]]/iu',
            '',
            $videoTitle
        );
        $clean = trim(preg_replace('/\s*\|.*$/u', '', $clean));
        $channel = trim(preg_replace('/\s*(-\s*Topic|VEVO|Official|Officiel|TV|Music)\s*$/iu', '', $channel));
        if (preg_match('/^(.+?)\s+[-–—~]\s+(.+)$/u', $clean, $m)) {
            return [trim($m[1]), trim($m[2], " \t\"'“”«»")];
        }
        return [$channel, trim($clean, " \t\"'“”«»")];
    }

    private static function kind(string $title): string
    {
        return match (true) {
            (bool) preg_match('/lyric/i', $title)                 => 'lyrics',
            (bool) preg_match('/visuali[sz]er|audio/i', $title)   => 'audio',
            (bool) preg_match('/\blive\b/i', $title)              => 'live',
            default                                               => 'clip',
        };
    }
}
