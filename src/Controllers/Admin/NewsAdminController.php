<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Repositories\NewsRepository;
use Cauri\Services\Audit;

/** Actualités : rédigées par l'équipe, ou reprises d'un média en citant la source. */
final class NewsAdminController extends BaseAdminController
{
    public function index(Request $request): Response
    {
        $this->requireUser($request);
        return $this->admin('news', ['rows' => $this->db->all('SELECT n.*, c.code FROM news n LEFT JOIN countries c ON c.id = n.country_id ORDER BY COALESCE(n.published_at, n.created_at) DESC LIMIT 200')]);
    }

    public function form(Request $request): Response
    {
        $this->requireUser($request);
        $id = $request->param('id');
        $item = $id === 'nouveau'
            ? ['id' => null, 'title' => '', 'summary' => '', 'body' => '', 'category' => 'annonce', 'country_id' => null, 'source_name' => '', 'source_url' => '', 'status' => 'draft', 'published_at' => gmdate('Y-m-d H:i')]
            : $this->db->one('SELECT * FROM news WHERE id = ?', [(int) $id]);
        if (!$item) {
            throw new HttpException(404);
        }
        return $this->admin('news-form', ['item' => $item, 'countries' => $this->charts->countries(false), 'categories' => NewsRepository::CATEGORIES]);
    }

    public function save(Request $request): Response
    {
        $this->requireUser($request);
        $id = $request->param('id') === 'nouveau' ? null : (int) $request->param('id');
        $back = path('admin/actualites/' . ($id ?? 'nouveau'));
        $title = mb_substr($request->str('title'), 0, 200);
        $summary = mb_substr($request->str('summary'), 0, 400);
        $sourceUrl = $request->str('source_url');
        $published = str_replace('T', ' ', $request->str('published_at'));
        $category = $request->str('category');
        if ($title === '' || $summary === '' || !in_array($category, NewsRepository::CATEGORIES, true)
            || ($sourceUrl !== '' && !preg_match('#^https?://#', $sourceUrl))
            || ($published !== '' && strtotime($published) === false)) {
            return $this->back($back, 'error', t('admin.news_invalid'));
        }
        $countryId = (int) $request->str('country_id') ?: null;
        $data = [
            'title'        => $title,
            'summary'      => $summary,
            'body'         => mb_substr($request->str('body'), 0, 20000) ?: null,
            'category'     => $category,
            'country_id'   => $countryId,
            'source_name'  => mb_substr($request->str('source_name'), 0, 120) ?: null,
            'source_url'   => $sourceUrl ?: null,
            'status'       => $request->str('status') === 'published' ? 'published' : 'draft',
            'published_at' => $published !== '' ? date('Y-m-d H:i:s', strtotime($published)) : gmdate('Y-m-d H:i:s'),
        ];
        if ($id) {
            $this->db->update('news', $data, 'id = :id', ['id' => $id]);
        } else {
            $slug = $base = slugify($title);
            for ($i = 2; $this->db->value('SELECT id FROM news WHERE slug = ?', [$slug]); $i++) {
                $slug = "$base-$i";
            }
            $id = $this->db->insert('news', $data + ['slug' => $slug, 'created_by' => $this->uid()]);
        }
        Audit::log($this->uid(), 'news.save', 'news', $id, null, ['status' => $data['status']], $request->ip());
        return $this->back(path('admin/actualites'), 'success', t('admin.saved'));
    }
}
