<?php

namespace Cauri\Controllers;

use Cauri\Core\Config;
use Cauri\Core\Csrf;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Core\Session;
use Cauri\Repositories\FormulaRepository;

final class PageController extends Controller
{
    public function methodology(Request $request): Response
    {
        $this->useLocale();
        $formula = (new FormulaRepository($this->db))->effectiveFor(date('Y-m-d'));
        $upcoming = $this->db->all('SELECT version, effective_from, note FROM formula_versions WHERE effective_from > ? ORDER BY effective_from', [date('Y-m-d')]);
        return $this->page('methodology', [
            'formula'    => $formula,
            'upcoming'   => $upcoming,
            'exclusions' => $this->charts->exclusions(),
            'corrections'=> $this->db->all(
                "SELECT r.period_key, r.corrected_at, r.correction_note, ct.name AS chart_name, c.code AS country_code
                 FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id JOIN countries c ON c.id = r.country_id
                 WHERE r.corrected_at IS NOT NULL AND r.status = 'published' ORDER BY r.corrected_at DESC LIMIT 30"
            ),
            'meta'       => ['title' => t('methodology.title') . ' · ' . brand(), 'description' => t('methodology.meta_description')],
        ]);
    }

    public function about(Request $request): Response
    {
        $this->useLocale();
        return $this->page('about', ['meta' => ['title' => t('about.title') . ' · ' . brand()]]);
    }

    /** Pages juridiques : mentions légales, confidentialité, cookies, conditions d'utilisation. */
    public function legal(Request $request): Response
    {
        $this->useLocale();
        $pages = ['mentions-legales' => 'mentions', 'confidentialite' => 'confidentialite', 'cookies' => 'cookies', 'conditions' => 'conditions'];
        $slug = ltrim($request->path, '/');
        $page = $pages[$slug] ?? null;
        if (!$page) {
            throw new \Cauri\Core\HttpException(404);
        }
        return $this->page('legal', [
            'slug'  => $slug,
            'body'  => \Cauri\Core\View::partial('legal/' . $page),
            'pages' => $pages,
            'meta'  => ['title' => t("legal.$page") . ' · ' . brand(), 'description' => t("legal.{$page}_description", ['brand' => brand()])],
        ]);
    }

    public function contact(Request $request): Response
    {
        $this->useLocale();
        return $this->page('contact', [
            'old'    => [],
            'errors' => [],
            'type'   => $request->str('type') === 'contestation' ? 'contestation' : 'contact',
            'meta'   => ['title' => t('contact.title') . ' · ' . brand()],
        ]);
    }

    public function contactSend(Request $request): Response
    {
        $this->useLocale();
        Csrf::check($request);
        $old = [
            'type'    => $request->str('type') === 'contestation' ? 'contestation' : 'contact',
            'name'    => mb_substr($request->str('name'), 0, 150),
            'email'   => mb_substr($request->str('email'), 0, 190),
            'subject' => mb_substr($request->str('subject'), 0, 200),
            'message' => mb_substr($request->str('message'), 0, 5000),
        ];
        $errors = [];
        if ($request->str('website') !== '') {
            return Response::redirect(path('contact')); // pot de miel : robot
        }
        if ($old['name'] === '') {
            $errors['name'] = t('form.required');
        }
        if (!filter_var($old['email'], FILTER_VALIDATE_EMAIL)) {
            $errors['email'] = t('form.invalid_email');
        }
        if ($old['subject'] === '') {
            $errors['subject'] = t('form.required');
        }
        if (mb_strlen($old['message']) < 10) {
            $errors['message'] = t('form.too_short');
        }
        $ipHash = hash_hmac('sha256', $request->ip(), (string) Config::get('app.key'));
        $recent = (int) $this->db->value('SELECT COUNT(*) FROM contact_messages WHERE ip_hash = ? AND created_at > ?', [$ipHash, gmdate('Y-m-d H:i:s', time() - 86400)]);
        if ($recent >= 5) {
            $errors['message'] = t('form.rate_limited');
        }
        if ($errors) {
            return $this->page('contact', ['old' => $old, 'errors' => $errors, 'type' => $old['type'], 'meta' => ['title' => t('contact.title')]], 422);
        }
        $this->db->insert('contact_messages', $old + ['ip_hash' => $ipHash]);
        Session::flash('success', t('contact.sent'));
        return Response::redirect(path('contact'));
    }

    public function setLocale(Request $request): Response
    {
        $locale = $request->param('locale');
        if (in_array($locale, Config::get('app.locales'), true)) {
            Session::set('locale', $locale);
        }
        $back = $request->str('retour', '/');
        // Retour interne uniquement (pas de redirection ouverte)
        if (!str_starts_with($back, '/') || str_starts_with($back, '//')) {
            $back = '/';
        }
        return Response::redirect($back);
    }
}
