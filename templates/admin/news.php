<?php /** @var array $rows */ ?>
<h1><?= e(t('admin.nav_news')) ?></h1>
<p class="muted"><?= e(t('admin.news_intro')) ?></p>
<p><a class="button button--small" href="<?= path('admin/actualites/nouveau') ?>"><?= e(t('admin.news_new')) ?></a></p>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.date')) ?></th><th><?= e(t('admin.news_title')) ?></th><th><?= e(t('admin.country')) ?></th><th><?= e(t('admin.status')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $n): ?>
        <tr>
            <td><small><?= e((string) $n['published_at']) ?></small></td>
            <td><?= e($n['title']) ?> <span class="tag"><?= e(t('news.cat_' . $n['category'])) ?></span><?= $n['source_url'] ? ' <small class="muted">' . e(t('news.source')) . ' : ' . e((string) $n['source_name']) . '</small>' : '' ?></td>
            <td><?= e($n['code'] ?? t('admin.all_countries')) ?></td>
            <td><span class="status status--<?= $n['status'] === 'published' ? 'published' : 'draft' ?>"><?= e(t('admin.status_' . $n['status'])) ?></span></td>
            <td><a href="<?= path('admin/actualites/' . $n['id']) ?>"><?= e(t('admin.edit')) ?></a><?php if ($n['status'] === 'published'): ?> · <a href="<?= path('actualites/' . $n['slug']) ?>" target="_blank" rel="noopener"><?= e(t('admin.view_site')) ?></a><?php endif; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
