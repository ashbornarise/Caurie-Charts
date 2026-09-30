<?php

namespace Cauri\Controllers;

use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Repositories\NewsRepository;

final class NewsController extends Controller
{
    private const PER_PAGE = 12;

    public function index(Request $request): Response
    {
        $this->useLocale();
        $repo = new NewsRepository($this->db);
        $page = max(1, (int) $request->str('page', '1'));
        return $this->page('news', [
            'items' => $repo->latest(self::PER_PAGE, null, ($page - 1) * self::PER_PAGE),
            'page'  => $page,
            'pages' => (int) ceil($repo->countPublished() / self::PER_PAGE),
            'meta'  => ['title' => t('news.title') . ' · ' . brand(), 'description' => t('news.meta_description', ['brand' => brand()])],
        ]);
    }

    public function show(Request $request): Response
    {
        $this->useLocale();
        $item = (new NewsRepository($this->db))->bySlug($request->param('slug'));
        if (!$item) {
            throw new HttpException(404);
        }
        return $this->page('news-item', [
            'item' => $item,
            'meta' => ['title' => $item['title'] . ' · ' . brand(), 'description' => $item['summary'], 'type' => 'article'],
        ]);
    }
}
