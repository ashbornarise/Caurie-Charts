<?php use Cauri\Core\View; /** @var array $items @var int $page @var int $pages */ ?>
<section class="prose news-page">
    <p class="eyebrow"><?= e(brand()) ?></p>
    <h1><?= e(t('news.title')) ?></h1>
    <p class="news-page__note"><?= e(t('news.feed_note')) ?></p>
    <?php if (!$items): ?><p class="empty"><?= e(t('news.empty')) ?></p><?php endif; ?>
    <ul class="news-grid">
        <?php foreach ($items as $i => $n): ?>
        <?= View::partial('partials/news-card', ['n' => $n, 'i' => $i]) ?>
        <?php endforeach; ?>
    </ul>
    <?php if ($pages > 1): ?>
    <nav class="toolbar">
        <?php if ($page > 1): ?><a class="button button--ghost button--small" href="<?= path('actualites', ['page' => $page - 1]) ?>">← <?= e(t('news.newer')) ?></a><?php endif; ?>
        <?php if ($page < $pages): ?><a class="button button--ghost button--small" href="<?= path('actualites', ['page' => $page + 1]) ?>"><?= e(t('news.older')) ?> →</a><?php endif; ?>
    </nav>
    <?php endif; ?>
</section>
