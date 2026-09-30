<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Services\Audit;
use Cauri\Services\Import\ChartImporter;
use Cauri\Services\Import\ImportService;

/**
 * Imports : couverture des sources, artistes à classer, clips YouTube à vérifier,
 * titres sans clip, import CSV (Audiomack, Boomplay... tant que leur API n'est pas accessible).
 */
final class ImportAdminController extends BaseAdminController
{
    public const CSV_SOURCES = ['audiomack', 'boomplay', 'apple_music'];

    public function index(Request $request): Response
    {
        $this->requireUser($request);
        return $this->admin('import', [
            'coverage' => $this->db->all(
                "SELECT o.source, c.code, MAX(o.observed_on) AS last_day, COUNT(DISTINCT o.observed_on) AS days, COUNT(*) AS rows_count
                 FROM chart_observations o JOIN countries c ON c.id = o.country_id
                 WHERE o.observed_on >= CURDATE() - INTERVAL 30 DAY GROUP BY o.source, c.code ORDER BY o.source, c.sort_order"
            ),
            'pending' => $this->db->all(
                "SELECT a.id, a.name, a.slug, a.guessed_country_id, gc.code AS guessed_code,
                    a.base_country, a.origin_source, a.origin_confidence, a.origin_note,
                    a.image_url, a.fans, a.youtube_subscribers, a.discovered_via,
                    (SELECT sc.id FROM countries sc WHERE sc.code = a.base_country) AS suggested_country_id,
                    (SELECT GROUP_CONCAT(DISTINCT CONCAT(c2.code, ' ', o2.source) SEPARATOR ', ')
                       FROM chart_observations o2 JOIN tracks t2 ON t2.id = o2.track_id JOIN countries c2 ON c2.id = o2.country_id
                      WHERE t2.artist_id = a.id) AS seen_in,
                    (SELECT MIN(o3.position) FROM chart_observations o3 JOIN tracks t3 ON t3.id = o3.track_id WHERE t3.artist_id = a.id) AS best_position,
                    (SELECT t4.title FROM tracks t4 WHERE t4.artist_id = a.id ORDER BY t4.id LIMIT 1) AS a_track,
                    (SELECT COUNT(*) FROM chart_observations o5 JOIN tracks t5 ON t5.id = o5.track_id WHERE t5.artist_id = a.id) AS obs
                 FROM artists a LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                 WHERE a.status = 'pending' ORDER BY a.base_country IS NULL, COALESCE(a.fans, 0) + COALESCE(a.youtube_subscribers, 0) / 10 DESC, a.name LIMIT 300"
            ),
            'autoClips' => $this->db->all(
                "SELECT p.id, p.external_id, p.url, t.title, a.name AS artist FROM track_platform_ids p
                 JOIN tracks t ON t.id = p.track_id JOIN artists a ON a.id = t.artist_id
                 WHERE p.platform = 'youtube' AND p.match_status = 'auto' AND a.status = 'active' ORDER BY p.id DESC LIMIT 100"
            ),
            'noClip' => $this->db->all(
                "SELECT t.id, t.title, a.name AS artist, c.code FROM tracks t JOIN artists a ON a.id = t.artist_id
                 JOIN countries c ON c.id = a.submission_country_id
                 WHERE a.status = 'active' AND t.is_active = 1
                   AND NOT EXISTS (SELECT 1 FROM track_platform_ids p WHERE p.track_id = t.id AND p.platform = 'youtube')
                 ORDER BY t.id DESC LIMIT 100"
            ),
            'countries' => $this->charts->countries(false),
            'sources'   => self::CSV_SOURCES,
            'today'     => date('Y-m-d'),
        ]);
    }

    /** Lance l'import des sources automatiques (et la recherche de clips si demandée). */
    public function run(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $service = new ImportService($this->db);
        $lines = $service->importAll(null, null, $this->uid());
        $n = (int) $request->str('youtube');
        if ($n > 0) {
            $lines[] = 'YouTube : ' . json_encode($service->matchYouTube(min($n, 90)), JSON_UNESCAPED_UNICODE);
        }
        return $this->back(path('admin/import'), 'success', implode(' · ', $lines));
    }

    /** Confirme le pays de soumission d'un artiste découvert, ou le marque hors périmètre. */
    public function artist(Request $request): Response
    {
        $this->requireUser($request);
        $id = (int) $request->param('id');
        if ($request->str('action') === 'out') {
            $this->db->update('artists', ['status' => 'out_of_scope'], 'id = :id AND status = \'pending\'', ['id' => $id]);
            Audit::log($this->uid(), 'artist.out_of_scope', 'artist', $id, null, [], $request->ip());
            return $this->back(path('admin/import') . '#artistes', 'success', t('admin.import_artist_out'));
        }
        $countryId = (int) $request->str('country_id');
        if (!$this->db->value('SELECT id FROM countries WHERE id = ?', [$countryId])) {
            return $this->back(path('admin/import') . '#artistes', 'error', t('admin.import_country_required'));
        }
        $this->db->update('artists', ['status' => 'active', 'submission_country_id' => $countryId], 'id = :id', ['id' => $id]);
        Audit::log($this->uid(), 'artist.confirm_country', 'artist', $id, null, ['country_id' => $countryId], $request->ip());
        return $this->back(path('admin/import') . '#artistes', 'success', t('admin.import_artist_confirmed'));
    }

    /** Clip trouvé automatiquement : confirmer ou retirer. */
    public function clip(Request $request): Response
    {
        $this->requireUser($request);
        $id = (int) $request->param('id');
        if ($request->str('action') === 'remove') {
            $trackId = $this->db->value('SELECT track_id FROM track_platform_ids WHERE id = ?', [$id]);
            $this->db->run("DELETE FROM track_platform_ids WHERE id = ? AND match_status = 'auto'", [$id]);
            // Pas de nouvelle recherche automatique avant 14 jours
            $this->db->update('tracks', ['youtube_checked_at' => gmdate('Y-m-d H:i:s')], 'id = :id', ['id' => (int) $trackId]);
            Audit::log($this->uid(), 'clip.remove', 'track_platform', $id, null, [], $request->ip());
        } else {
            $this->db->update('track_platform_ids', ['match_status' => 'confirmed'], 'id = :id', ['id' => $id]);
            Audit::log($this->uid(), 'clip.confirm', 'track_platform', $id, null, [], $request->ip());
        }
        return $this->back(path('admin/import') . '#clips', 'success', t('admin.saved'));
    }

    /** Rattache un clip saisi à la main (URL ou identifiant YouTube). */
    public function manualClip(Request $request): Response
    {
        $this->requireUser($request);
        $trackId = (int) $request->param('id');
        $videoId = self::youtubeId($request->str('video'));
        if (!$videoId) {
            return $this->back(path('admin/import') . '#sans-clip', 'error', t('admin.import_bad_video'));
        }
        try {
            $this->db->insert('track_platform_ids', [
                'track_id' => $trackId, 'platform' => 'youtube', 'external_id' => $videoId, 'kind' => 'clip',
                'url' => 'https://www.youtube.com/watch?v=' . $videoId, 'match_status' => 'confirmed',
            ]);
        } catch (\PDOException) {
            return $this->back(path('admin/import') . '#sans-clip', 'error', t('admin.platform_duplicate'));
        }
        Audit::log($this->uid(), 'clip.manual', 'track', $trackId, null, ['video' => $videoId], $request->ip());
        return $this->back(path('admin/import') . '#sans-clip', 'success', t('admin.saved'));
    }

    /** Import d'un classement copié depuis une plateforme (une ligne par titre). */
    public function csv(Request $request): Response
    {
        $this->requireUser($request);
        $source = $request->str('source');
        $country = $this->db->value('SELECT code FROM countries WHERE id = ?', [(int) $request->str('country_id')]);
        $day = \DateTimeImmutable::createFromFormat('!Y-m-d', $request->str('observed_on'));
        if (!in_array($source, self::CSV_SOURCES, true) || !$country || !$day || $day > new \DateTimeImmutable('today')) {
            return $this->back(path('admin/import') . '#csv', 'error', t('admin.import_csv_invalid'));
        }
        try {
            $rows = ChartImporter::parseCsv($request->str('rows'));
            $s = (new ChartImporter($this->db))->import($country, $source, ['observed_on' => $day->format('Y-m-d'), 'rows' => $rows], $this->uid());
        } catch (\InvalidArgumentException $e) {
            return $this->back(path('admin/import') . '#csv', 'error', $e->getMessage());
        }
        return $this->back(path('admin/import') . '#csv', 'success', t('admin.import_csv_done', ['rows' => $s['rows'], 'new' => $s['new_tracks'], 'artists' => $s['new_artists']]));
    }

    public static function youtubeId(string $input): ?string
    {
        $input = trim($input);
        if (preg_match('~(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})~', $input, $m)) {
            return $m[1];
        }
        return preg_match('/^[A-Za-z0-9_-]{11}$/', $input) ? $input : null;
    }
}
