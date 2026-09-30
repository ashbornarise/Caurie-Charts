<?php /** @var array $item */ ?>
<article class="prose">
    <p><a href="<?= path('actualites') ?>">← <?= e(t('news.title')) ?></a></p>
    <p class="news-list__meta">
        <span class="tag tag--<?= e($item['category']) ?>"><?= e(t('news.cat_' . $item['category'])) ?></span>
        <?= e(fmt_date(substr($item['published_at'], 0, 10))) ?><?= $item['country_code'] ? ' · ' . e(country_name($item['country_code'])) : '' ?>
    </p>
    <h1><?= e($item['title']) ?></h1>
    <p class="lead"><?= e($item['summary']) ?></p>
    <?php if ($item['body']): ?>
        <?php foreach (preg_split('/\n\s*\n/', trim($item['body'])) as $para): ?>
            <p><?= nl2br(e($para)) ?></p>
        <?php endforeach; ?>
    <?php endif; ?>
    <?php if ($item['source_url']): ?>
        <p class="fineprint"><?= e(t('news.source')) ?> : <a href="<?= e($item['source_url']) ?>" rel="noopener nofollow" target="_blank"><?= e($item['source_name'] ?: parse_url($item['source_url'], PHP_URL_HOST)) ?></a></p>
    <?php endif; ?>
</article>
