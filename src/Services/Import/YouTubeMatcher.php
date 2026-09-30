<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;
use Cauri\Services\Platforms\QuotaExceededException;
use Cauri\Services\Platforms\YouTubeClient;

/**
 * Trouve le clip YouTube officiel des titres qui n'en ont pas, pour relever leurs vues.
 * Une recherche coûte 100 unités de quota : le nombre de recherches par passage est limité,
 * et les titres les plus présents dans les classements passent en premier.
 * Les correspondances trouvées sont marquées "auto" : l'équipe les confirme ou les retire dans l'admin.
 */
final class YouTubeMatcher
{
    public const MIN_SCORE = 4;

    public function __construct(private Database $db, private YouTubeClient $youtube)
    {
    }

    /**
     * Note un résultat de recherche. Artiste présent (titre de la vidéo ou chaîne) : +2 ;
     * titre présent : +2 ; "official", "clip", "video" : +1 ; version dérivée non demandée
     * (lyrics, cover, remix, live, reaction, instrumental, karaoke) : -3.
     */
    public static function score(array $result, string $title, string $artist): int
    {
        $haystack = Normalizer::text($result['title'] ?? '');
        $channel = Normalizer::text($result['artist'] ?? '');
        $artistKey = Normalizer::artistKey($artist);
        $titleKey = Normalizer::title($title);
        $score = 0;
        if ($artistKey !== '' && (str_contains($haystack, $artistKey) || str_contains($channel, $artistKey) || str_contains($channel, str_replace(' ', '', $artistKey)))) {
            $score += 2;
        }
        if ($titleKey !== '' && str_contains($haystack, $titleKey)) {
            $score += 2;
        }
        if (preg_match('/\b(official|officiel|clip|video)\b/', $haystack)) {
            $score++;
        }
        foreach (['lyrics', 'lyric', 'cover', 'remix', 'live', 'reaction', 'instrumental', 'karaoke', 'slowed', 'sped up'] as $word) {
            if (str_contains($haystack, $word) && !str_contains(Normalizer::text($title), $word)) {
                $score -= 3;
                break;
            }
        }
        return $score;
    }

    /** Meilleur résultat au-dessus du seuil, ou null. */
    public static function best(array $results, string $title, string $artist): ?array
    {
        $best = null;
        $bestScore = self::MIN_SCORE - 1;
        foreach ($results as $r) {
            $s = self::score($r, $title, $artist);
            if ($s > $bestScore && !empty($r['external_id'])) {
                $best = $r + ['score' => $s];
                $bestScore = $s;
            }
        }
        return $best;
    }

    /** @return array ['searched', 'matched', 'status'] */
    public function run(int $limit): array
    {
        $candidates = $this->db->all(
            "SELECT t.id, t.title, a.name AS artist,
                (SELECT COUNT(*) FROM chart_observations o WHERE o.track_id = t.id AND o.observed_on >= CURDATE() - INTERVAL 14 DAY) AS recent
             FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id
             WHERE t.is_active = 1 AND a.status = 'active'
               AND NOT EXISTS (SELECT 1 FROM track_platform_ids p WHERE p.track_id = t.id AND p.platform = 'youtube')
               AND (t.youtube_checked_at IS NULL OR t.youtube_checked_at < NOW() - INTERVAL 14 DAY)
             -- Pays sans classement de plateforme d'abord (leurs vues YouTube sont leur principale source),
             -- puis un titre par artiste avant les suivants, puis les titres les plus présents dans les classements
             ORDER BY c.code IN ('TG', 'BJ') DESC,
                      (SELECT COUNT(*) FROM track_platform_ids p2 JOIN tracks t2 ON t2.id = p2.track_id WHERE t2.artist_id = a.id AND p2.platform = 'youtube') ASC,
                      recent DESC, t.id DESC LIMIT " . max(0, $limit)
        );
        $stats = ['searched' => 0, 'matched' => 0, 'status' => 'ok'];
        foreach ($candidates as $c) {
            try {
                $results = $this->youtube->searchTrack($c['artist'] . ' ' . $c['title']);
            } catch (QuotaExceededException) {
                $stats['status'] = 'quota épuisé';
                break;
            } catch (\Cauri\Services\Platforms\PlatformException $e) {
                // Limite de YouTube atteinte (quota du jour) ou erreur passagère : on reprendra au prochain passage
                $stats['status'] = 'arrêt : ' . $e->getMessage();
                break;
            }
            $stats['searched']++;
            $this->db->update('tracks', ['youtube_checked_at' => gmdate('Y-m-d H:i:s')], 'id = :id', ['id' => $c['id']]);
            $best = self::best($results, $c['title'], $c['artist']);
            if ($best) {
                $this->db->run(
                    "INSERT IGNORE INTO track_platform_ids (track_id, platform, external_id, kind, url, published_at, match_status)
                     VALUES (?, 'youtube', ?, 'clip', ?, ?, 'auto')",
                    [$c['id'], $best['external_id'], $best['url'], $best['published_at']]
                );
                $stats['matched']++;
            }
        }
        return $stats;
    }
}
