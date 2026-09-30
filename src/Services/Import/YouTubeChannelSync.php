<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;
use Cauri\Core\Env;
use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\YouTubeQuota;

/**
 * Données YouTube de tous les titres, artiste par artiste, au moindre coût de quota :
 * - la chaîne de l'artiste est trouvée une fois (recherche : 100 unités) ;
 * - toutes ses vidéos sont ensuite lues depuis la liste de la chaîne (1 unité pour 50 vidéos) et rattachées
 *   à ses titres : clip officiel, audio, lyrics, live (ils s'additionnent, METHODOLOGIE.md section 2) ;
 * - les vidéos « Artiste - Titre » qui ne correspondent à aucun titre connu créent le titre (catalogue complet) ;
 * - chaque jour, les chaînes déjà connues sont relues (1 unité) pour attraper les nouveaux clips.
 * Les vues sont ensuite relevées chaque jour par CollectService (1 unité pour 50 vidéos).
 * Priorité : Togo et Bénin, puis les artistes présents dans les classements de la semaine.
 */
final class YouTubeChannelSync
{
    private const API = 'https://www.googleapis.com/youtube/v3/';

    public function __construct(private Database $db, private HttpClient $http)
    {
    }

    /** @return list<string> compte rendu */
    public function run(int $newChannels = 40, int $refresh = 300): array
    {
        $key = Env::get('YOUTUBE_API_KEY');
        if ($key === '') {
            return ['clé YouTube absente'];
        }
        $found = 0;
        $clips = 0;
        $created = 0;

        // 1. Chaînes à trouver : artistes confirmés d'abord (Togo, Bénin en tête), puis présents dans les classements
        $todo = $this->db->all(
            "SELECT a.id, a.name, a.status, a.submission_country_id FROM artists a JOIN countries c ON c.id = a.submission_country_id
             WHERE a.status <> 'out_of_scope' AND a.youtube_channel_id IS NULL
               AND (a.channel_checked_at IS NULL OR a.channel_checked_at < NOW() - INTERVAL 30 DAY)
             ORDER BY a.status = 'active' DESC, c.code IN ('TG', 'BJ') DESC,
                      EXISTS (SELECT 1 FROM tracks t JOIN chart_observations o ON o.track_id = t.id
                              WHERE t.artist_id = a.id AND o.observed_on >= CURDATE() - INTERVAL 7 DAY) DESC,
                      COALESCE(a.fans, 0) DESC
             LIMIT " . max(0, $newChannels)
        );
        foreach ($todo as $a) {
            if (!YouTubeQuota::spend($this->db, 102)) { // recherche (100) + deux pages de vidéos
                break;
            }
            $channel = $this->findChannel($a['name'], $key);
            $this->db->update('artists', ['channel_checked_at' => gmdate('Y-m-d H:i:s')] + ($channel ? ['youtube_channel_id' => $channel] : []), 'id = :id', ['id' => $a['id']]);
            if ($channel) {
                $found++;
                [$c, $n] = $this->syncChannel((int) $a['id'], $a['name'], $channel, (int) $a['submission_country_id'], $key, 2);
                $clips += $c;
                $created += $n;
            }
        }

        // 2. Chaînes connues : nouvelles vidéos (1 unité par chaîne), les moins récemment relues d'abord
        $known = $this->db->all(
            "SELECT id, name, youtube_channel_id, submission_country_id FROM artists
             WHERE status <> 'out_of_scope' AND youtube_channel_id IS NOT NULL
               AND (channel_checked_at IS NULL OR channel_checked_at < NOW() - INTERVAL 20 HOUR)
             ORDER BY status = 'active' DESC, channel_checked_at IS NOT NULL, channel_checked_at LIMIT " . max(0, $refresh)
        );
        $refreshed = 0;
        foreach ($known as $a) {
            if (!YouTubeQuota::spend($this->db, 2)) {
                break;
            }
            [$c, $n] = $this->syncChannel((int) $a['id'], $a['name'], $a['youtube_channel_id'], (int) $a['submission_country_id'], $key, 1);
            $this->db->update('artists', ['channel_checked_at' => gmdate('Y-m-d H:i:s')], 'id = :id', ['id' => $a['id']]);
            $clips += $c;
            $created += $n;
            $refreshed++;
        }
        return [
            "$found nouvelles chaînes trouvées sur " . count($todo) . " recherchées",
            "$refreshed chaînes relues",
            "$clips vidéos rattachées à des titres, $created titres ajoutés au catalogue",
            'Quota YouTube restant : ' . YouTubeQuota::remaining($this->db),
        ];
    }

    /**
     * Chaîne officielle : nom identique (ou « Nom - Topic », « NomVEVO », « Nom Officiel »), sinon la chaîne
     * qui publie le plus de vidéos portant le nom de l'artiste.
     */
    private function findChannel(string $name, string $key): ?string
    {
        $key0 = str_replace(' ', '', Normalizer::text($name));
        $r = $this->get('search?part=snippet&type=channel&maxResults=5&q=' . rawurlencode($name), $key);
        foreach ($r['items'] ?? [] as $item) {
            $title = str_replace(' ', '', Normalizer::text(preg_replace('/\s*(-\s*topic|vevo|officiel|official|music|tv)\s*$/iu', '', $item['snippet']['title'])));
            if ($title === $key0) {
                return $item['snippet']['channelId'] ?? ($item['id']['channelId'] ?? null);
            }
        }
        return null;
    }

    /** Rattache les vidéos récentes de la chaîne aux titres de l'artiste. Retourne [vidéos rattachées, titres créés]. */
    private function syncChannel(int $artistId, string $artistName, string $channelId, int $countryId, string $key, int $pages): array
    {
        $uploads = 'UU' . substr($channelId, 2); // liste « vidéos mises en ligne » de la chaîne
        $videos = [];
        $token = '';
        for ($p = 0; $p < $pages; $p++) {
            $r = $this->get('playlistItems?part=snippet&maxResults=50&playlistId=' . rawurlencode($uploads) . ($token ? '&pageToken=' . rawurlencode($token) : ''), $key);
            foreach ($r['items'] ?? [] as $it) {
                $videos[] = $it['snippet'];
            }
            $token = $r['nextPageToken'] ?? '';
            if ($token === '') {
                break;
            }
        }
        $tracks = $this->db->all('SELECT id, title FROM tracks WHERE artist_id = ?', [$artistId]);
        $importer = new ChartImporter($this->db);
        $linked = 0;
        $created = 0;
        foreach ($videos as $v) {
            $videoId = $v['resourceId']['videoId'] ?? null;
            $title = html_entity_decode((string) ($v['title'] ?? ''), ENT_QUOTES | ENT_HTML5, 'UTF-8');
            if (!$videoId || $this->db->value("SELECT 1 FROM track_platform_ids WHERE platform = 'youtube' AND external_id = ?", [$videoId])) {
                continue;
            }
            $trackId = self::matchTrack($title, $tracks);
            if ($trackId === null) {
                // « Artiste - Titre » inconnu : nouveau titre de l'artiste (hors teasers, mix, interviews)
                $row = YouTubeDiscoverySource::parse([['id' => ['videoId' => $videoId], 'snippet' => $v]])['rows'][0] ?? null;
                if (!$row || Normalizer::artistKey($row['artist']) !== Normalizer::artistKey($artistName)) {
                    continue;
                }
                [$trackId, $stats] = $importer->upsertTrack($row, 'youtube_channel', $countryId);
                $created += $stats['new_tracks'];
                $linked++;
                continue;
            }
            $this->db->run(
                "INSERT IGNORE INTO track_platform_ids (track_id, platform, external_id, kind, url, published_at, match_status)
                 VALUES (?, 'youtube', ?, ?, ?, ?, 'auto')",
                [$trackId, $videoId, self::kind($title), 'https://www.youtube.com/watch?v=' . rawurlencode($videoId), isset($v['publishedAt']) ? substr($v['publishedAt'], 0, 10) : null]
            );
            $linked++;
        }
        return [$linked, $created];
    }

    /** Titre de l'artiste contenu dans le titre de la vidéo (le plus long gagne : « Bra » ne vole pas « Bra Remix »). */
    public static function matchTrack(string $videoTitle, array $tracks): ?int
    {
        if (preg_match('/\b(teaser|extrait|snippet|making of|behind the scenes|interview|reaction|réaction)\b/iu', $videoTitle)) {
            return null;
        }
        $haystack = ' ' . Normalizer::text($videoTitle) . ' ';
        $best = null;
        $bestLen = 0;
        foreach ($tracks as $t) {
            $needle = Normalizer::title($t['title']);
            if (mb_strlen($needle) < 2) {
                continue;
            }
            if (str_contains($haystack, ' ' . $needle . ' ') && mb_strlen($needle) > $bestLen) {
                $best = (int) $t['id'];
                $bestLen = mb_strlen($needle);
            }
        }
        return $best;
    }

    private static function kind(string $title): string
    {
        return match (true) {
            (bool) preg_match('/lyric|paroles/i', $title)          => 'lyrics',
            (bool) preg_match('/visuali[sz]er|audio/i', $title)    => 'audio',
            (bool) preg_match('/\blive\b|en concert/i', $title)    => 'live',
            (bool) preg_match('/remix/i', $title)                  => 'remix',
            default                                                => 'clip',
        };
    }

    private function get(string $path, string $key): array
    {
        try {
            $r = $this->http->request('GET', self::API . $path . '&key=' . rawurlencode($key));
        } catch (\Throwable) {
            return [];
        }
        return $r['status'] === 200 ? (json_decode($r['body'], true) ?: []) : [];
    }
}
