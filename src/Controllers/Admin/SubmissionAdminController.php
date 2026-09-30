<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Services\Audit;
use Cauri\Services\Charts\ChartService;
use Cauri\Services\Charts\Period;
use Cauri\Services\Uploads;

/** Déclarations d'artistes (file de validation) et relevés manuels. */
final class SubmissionAdminController extends BaseAdminController
{
    public function index(Request $request): Response
    {
        $this->requireUser($request);
        $status = in_array($request->str('statut'), ['pending', 'validated', 'rejected'], true) ? $request->str('statut') : 'pending';
        $rows = $this->db->all(
            'SELECT s.*, t.title AS track_title FROM submissions s LEFT JOIN tracks t ON t.id = s.track_id WHERE s.status = ? ORDER BY s.created_at DESC LIMIT 200',
            [$status]
        );
        return $this->admin('submissions', ['rows' => $rows, 'status' => $status]);
    }

    public function show(Request $request): Response
    {
        $this->requireUser($request);
        $s = $this->find((int) $request->param('id'));
        return $this->admin('submission', [
            's'      => $s,
            'tracks' => $this->db->all('SELECT t.id, t.title, a.name AS artist_name FROM tracks t JOIN artists a ON a.id = t.artist_id ORDER BY a.name, t.title LIMIT 2000'),
            'public' => $s['track_id'] ? $this->publicData((int) $s['track_id'], $s['platform'], $s['period_start'], $s['period_end']) : null,
        ]);
    }

    public function review(Request $request): Response
    {
        $this->requireUser($request);
        $s = $this->find((int) $request->param('id'));
        $decision = $request->str('decision');
        $trackId = (int) $request->str('track_id') ?: null;
        $note = trim($request->str('note'));
        if (!in_array($decision, ['validated', 'rejected'], true)) {
            return $this->back(path("admin/declarations/{$s['id']}"), 'error', t('form.required'));
        }
        if ($decision === 'validated' && !$trackId) {
            return $this->back(path("admin/declarations/{$s['id']}"), 'error', t('admin.submission_track_required'));
        }
        if ($decision === 'rejected' && $note === '') {
            return $this->back(path("admin/declarations/{$s['id']}"), 'error', t('admin.reason_required'));
        }
        $artistId = $trackId ? (int) $this->db->value('SELECT artist_id FROM tracks WHERE id = ?', [$trackId]) : null;
        $this->db->update('submissions', [
            'status'      => $decision,
            'track_id'    => $trackId,
            'artist_id'   => $artistId,
            'reviewed_by' => $this->uid(),
            'reviewed_at' => gmdate('Y-m-d H:i:s'),
            'review_note' => $note ?: null,
        ], 'id = :id', ['id' => $s['id']]);
        Audit::log($this->uid(), 'submission.' . $decision, 'submission', $s['id'], $note ?: null, ['track_id' => $trackId], $request->ip());

        $message = t('admin.submission_saved');
        if ($decision === 'validated') {
            $this->updateTopCountry($artistId, $s);
            $message .= ' ' . $this->recomputeDraftWeeks($trackId, $s['period_start'], $s['period_end']);
        }
        return $this->back(path('admin/declarations'), 'success', $message);
    }

    /** Capture d'écran servie uniquement aux utilisateurs connectés. */
    public function screenshot(Request $request): Response
    {
        $this->requireUser($request);
        $s = $this->find((int) $request->param('id'));
        $file = Uploads::path($s['screenshot_path']);
        if (!is_file($file)) {
            throw new HttpException(404);
        }
        $mime = (new \finfo(FILEINFO_MIME_TYPE))->file($file);
        return new Response((string) file_get_contents($file), 200, ['Content-Type' => $mime, 'Cache-Control' => 'private, no-store']);
    }

    public function snapshots(Request $request): Response
    {
        $this->requireUser($request);
        return $this->admin('snapshots', [
            'platformIds' => $this->db->all(
                "SELECT tpi.id, tpi.platform, tpi.external_id, t.title, a.name AS artist_name, c.code,
                    (SELECT CONCAT(captured_on, ' : ', plays) FROM snapshots s WHERE s.track_platform_id = tpi.id ORDER BY captured_on DESC LIMIT 1) AS last
                 FROM track_platform_ids tpi JOIN tracks t ON t.id = tpi.track_id JOIN artists a ON a.id = t.artist_id
                 JOIN countries c ON c.id = a.submission_country_id
                 WHERE tpi.platform <> 'spotify' ORDER BY c.sort_order, a.name, t.title, tpi.platform"
            ),
            'recent' => $this->db->all(
                "SELECT s.*, tpi.platform, t.title, u.name AS user_name FROM snapshots s
                 JOIN track_platform_ids tpi ON tpi.id = s.track_platform_id JOIN tracks t ON t.id = tpi.track_id
                 LEFT JOIN users u ON u.id = s.created_by WHERE s.source = 'manual' ORDER BY s.created_at DESC LIMIT 50"
            ),
            'today' => date('Y-m-d'),
        ]);
    }

    /** Relevé manuel (Audiomack, Boomplay... sans API) : compteur cumulé lu sur la plateforme. */
    public function saveSnapshot(Request $request): Response
    {
        $this->requireUser($request);
        $tpiId = (int) $request->str('track_platform_id');
        $day = $request->str('captured_on');
        $plays = $request->str('plays');
        $date = \DateTimeImmutable::createFromFormat('!Y-m-d', $day);
        if (!$tpiId || !$date || $date > new \DateTimeImmutable('today') || !ctype_digit($plays)) {
            return $this->back(path('admin/releves'), 'error', t('admin.snapshot_invalid'));
        }
        $previous = $this->db->one('SELECT captured_on, plays FROM snapshots WHERE track_platform_id = ? AND captured_on < ? ORDER BY captured_on DESC LIMIT 1', [$tpiId, $day]);
        $this->db->run(
            "INSERT INTO snapshots (track_platform_id, captured_on, plays, source, created_by) VALUES (?, ?, ?, 'manual', ?)
             ON DUPLICATE KEY UPDATE plays = VALUES(plays), source = 'manual', created_by = VALUES(created_by)",
            [$tpiId, $day, (int) $plays, $this->uid()]
        );
        Audit::log($this->uid(), 'snapshot.manual', 'track_platform', $tpiId, null, ['day' => $day, 'plays' => (int) $plays], $request->ip());
        $warning = $previous && (int) $plays < (int) $previous['plays'] ? ' ' . t('admin.snapshot_lower', ['previous' => fmt_number((int) $previous['plays'])]) : '';
        return $this->back(path('admin/releves'), $warning ? 'error' : 'success', t('admin.snapshot_saved') . $warning);
    }

    private function find(int $id): array
    {
        $s = $this->db->one('SELECT s.*, t.title AS track_title, u.name AS reviewer FROM submissions s LEFT JOIN tracks t ON t.id = s.track_id LEFT JOIN users u ON u.id = s.reviewed_by WHERE s.id = ?', [$id]);
        if (!$s) {
            throw new HttpException(404);
        }
        return $s;
    }

    /** Donnée publique de la même plateforme sur la même période, pour comparer. */
    private function publicData(int $trackId, string $platform, string $start, string $end): ?int
    {
        $row = $this->db->one(
            "SELECT
                (SELECT SUM(x.plays) FROM (SELECT (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on <= ? ORDER BY captured_on DESC LIMIT 1) AS plays
                   FROM track_platform_ids tpi WHERE tpi.track_id = ? AND tpi.platform = ?) x) AS end_plays,
                (SELECT SUM(y.plays) FROM (SELECT (SELECT plays FROM snapshots s WHERE s.track_platform_id = tpi.id AND s.captured_on < ? ORDER BY captured_on DESC LIMIT 1) AS plays
                   FROM track_platform_ids tpi WHERE tpi.track_id = ? AND tpi.platform = ?) y) AS start_plays",
            [$end, $trackId, $platform, $start, $trackId, $platform]
        );
        return $row && $row['end_plays'] !== null && $row['start_plays'] !== null ? (int) $row['end_plays'] - (int) $row['start_plays'] : null;
    }

    /** Pays d'écoute principal déclaré : statistique de la fiche artiste, sans effet sur le classement. */
    private function updateTopCountry(?int $artistId, array $s): void
    {
        $breakdown = json_decode((string) $s['country_breakdown'], true);
        if (!$artistId || !$breakdown) {
            return;
        }
        arsort($breakdown);
        $code = array_key_first($breakdown);
        $countryId = $this->db->value('SELECT id FROM countries WHERE code = ?', [$code]);
        if ($countryId) {
            $this->db->update('artists', ['top_country_id' => $countryId, 'top_country_share' => $breakdown[$code], 'top_country_updated_at' => $s['period_end']], 'id = :id', ['id' => $artistId]);
        }
    }

    /** Recalcule les semaines encore en brouillon couvertes par la déclaration. */
    private function recomputeDraftWeeks(int $trackId, string $start, string $end): string
    {
        $code = $this->db->value('SELECT c.code FROM tracks t JOIN artists a ON a.id = t.artist_id JOIN countries c ON c.id = a.submission_country_id WHERE t.id = ?', [$trackId]);
        $service = new ChartService($this->db);
        $done = [];
        $published = [];
        for ($p = Period::weekOf($start); $p->start <= $end; $p = Period::weekOf(date('Y-m-d', strtotime($p->start . ' +7 days')))) {
            $status = $this->db->value("SELECT r.status FROM chart_runs r JOIN countries c ON c.id = r.country_id JOIN chart_types ct ON ct.id = r.chart_type_id WHERE c.code = ? AND ct.code = 'prime' AND r.period_type = 'week' AND r.period_key = ?", [$code, $p->key]);
            if ($status === 'draft') {
                $service->computeWeek($code, $p->start, null, $this->uid());
                $done[] = $p->key;
            } elseif ($status === 'published') {
                $published[] = $p->key;
            }
        }
        $msg = $done ? t('admin.weeks_recomputed', ['weeks' => implode(', ', $done)]) : '';
        if ($published) {
            $msg .= ' ' . t('admin.weeks_published_untouched', ['weeks' => implode(', ', $published)]);
        }
        return trim($msg);
    }
}
