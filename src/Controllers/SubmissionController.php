<?php

namespace Cauri\Controllers;

use Cauri\Core\Config;
use Cauri\Core\Csrf;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Core\Session;
use Cauri\Services\Uploads;

/** Formulaire public de déclaration pour artistes et labels (file de validation dans l'admin). */
final class SubmissionController extends Controller
{
    public const PLATFORMS = ['spotify', 'audiomack', 'boomplay', 'apple_music', 'deezer', 'youtube'];

    public function form(Request $request): Response
    {
        $this->useLocale();
        return $this->render([], []);
    }

    public function store(Request $request): Response
    {
        $this->useLocale();
        Csrf::check($request);
        if ($request->str('website') !== '') {
            return Response::redirect(path('declarer'));
        }

        $old = [
            'artist'       => mb_substr($request->str('artist'), 0, 150),
            'track'        => mb_substr($request->str('track'), 0, 200),
            'contact_name' => mb_substr($request->str('contact_name'), 0, 150),
            'email'        => mb_substr($request->str('email'), 0, 190),
            'platform'     => $request->str('platform'),
            'period_start' => $request->str('period_start'),
            'period_end'   => $request->str('period_end'),
            'streams'      => $request->str('streams'),
            'breakdown'    => mb_substr($request->str('breakdown'), 0, 500),
        ];
        $errors = [];
        foreach (['artist', 'track', 'contact_name'] as $f) {
            if ($old[$f] === '') {
                $errors[$f] = t('form.required');
            }
        }
        if (!filter_var($old['email'], FILTER_VALIDATE_EMAIL)) {
            $errors['email'] = t('form.invalid_email');
        }
        if (!in_array($old['platform'], self::PLATFORMS, true)) {
            $errors['platform'] = t('form.required');
        }
        $start = \DateTimeImmutable::createFromFormat('!Y-m-d', $old['period_start']);
        $end = \DateTimeImmutable::createFromFormat('!Y-m-d', $old['period_end']);
        if (!$start || !$end || $end < $start || $end > new \DateTimeImmutable('today') || $start->diff($end)->days > 92) {
            $errors['period_end'] = t('submit.error_period');
        }
        if (!ctype_digit($old['streams']) || (int) $old['streams'] <= 0) {
            $errors['streams'] = t('submit.error_streams');
        }
        $breakdown = self::parseBreakdown($old['breakdown']);
        if ($old['breakdown'] !== '' && $breakdown === null) {
            $errors['breakdown'] = t('submit.error_breakdown');
        }
        if ($request->input('consent') !== '1') {
            $errors['consent'] = t('submit.error_consent');
        }

        $ipHash = hash_hmac('sha256', $request->ip(), (string) Config::get('app.key'));
        $recent = (int) $this->db->value('SELECT COUNT(*) FROM submissions WHERE ip_hash = ? AND created_at > ?', [$ipHash, gmdate('Y-m-d H:i:s', time() - 86400)]);
        if ($recent >= 10) {
            $errors['streams'] = t('form.rate_limited');
        }

        $screenshot = null;
        if (!$errors) {
            try {
                $screenshot = Uploads::storeImage($request->files['screenshot'] ?? null);
            } catch (\InvalidArgumentException $e) {
                $errors['screenshot'] = $e->getMessage();
            }
        }
        if ($errors) {
            return $this->render($old, $errors, 422);
        }

        // Rattachement automatique si le titre existe déjà (l'admin peut corriger)
        $match = $this->db->one(
            'SELECT t.id, t.artist_id FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE LOWER(t.title) = LOWER(?) AND LOWER(a.name) = LOWER(?) LIMIT 1',
            [$old['track'], $old['artist']]
        );
        $this->db->insert('submissions', [
            'track_id'              => $match['id'] ?? null,
            'artist_id'             => $match['artist_id'] ?? null,
            'submitted_artist_name' => $old['artist'],
            'submitted_track_title' => $old['track'],
            'contact_name'          => $old['contact_name'],
            'contact_email'         => $old['email'],
            'platform'              => $old['platform'],
            'period_start'          => $old['period_start'],
            'period_end'            => $old['period_end'],
            'streams'               => (int) $old['streams'],
            'country_breakdown'     => $breakdown ? json_encode($breakdown) : null,
            'screenshot_path'       => $screenshot,
            'ip_hash'               => $ipHash,
        ]);
        Session::flash('success', t('submit.sent'));
        return Response::redirect(path('declarer'));
    }

    /** "TG 60, CI 25, FR 15" -> ['TG' => 60.0, ...], ou null si illisible ou total > 100 %. */
    public static function parseBreakdown(string $text): ?array
    {
        if (trim($text) === '') {
            return [];
        }
        $out = [];
        foreach (preg_split('/[,;\n]+/', $text) as $part) {
            if (trim($part) === '') {
                continue;
            }
            if (!preg_match('/^\s*([A-Za-z]{2})\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*%?\s*$/', $part, $m)) {
                return null;
            }
            $out[strtoupper($m[1])] = (float) str_replace(',', '.', $m[2]);
        }
        return array_sum($out) <= 100.5 ? $out : null;
    }

    private function render(array $old, array $errors, int $status = 200): Response
    {
        return $this->page('submit', [
            'old'       => $old,
            'errors'    => $errors,
            'platforms' => self::PLATFORMS,
            'meta'      => ['title' => t('submit.title') . ' · ' . brand(), 'description' => t('submit.intro')],
        ], $status);
    }
}
