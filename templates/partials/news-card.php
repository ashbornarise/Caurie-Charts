<?php
/**
 * Carte d'actualité. Chaque carte prend une teinte différente (six teintes en rotation selon $i).
 * Les actualités importées renvoient vers l'article du média, qui est cité.
 * @var array $n  @var int $i
 */
$external = ($n['origin'] ?? 'manual') === 'feed' && $n['source_url'];
$href = $external ? $n['source_url'] : path('actualites/' . $n['slug']);
$target = $external ? ' target="_blank" rel="noopener noreferrer"' : '';
?>
<li class="news-card news-card--tone-<?= $i % 6 ?>">
    <a class="news-card__media" href="<?= e($href) ?>"<?= $target ?> tabindex="-1" aria-hidden="true">
        <?php if (!empty($n['image_path'])): ?>
        <img src="/media/news/<?= e(rawurlencode(basename($n['image_path']))) ?>" alt="" loading="lazy" width="720" height="405">
        <?php else: ?>
        <span class="news-card__placeholder"><?= e(initials($n['source_name'] ?: brand())) ?></span>
        <?php endif; ?>
    </a>
    <div class="news-card__body">
        <p class="news-card__meta">
            <span class="news-card__tag"><?= e(t('news.cat_' . $n['category'])) ?></span>
            <span><?= e(fmt_date(substr($n['published_at'], 0, 10), false)) ?></span>
            <?php if ($n['country_code']): ?><span><?= flag($n['country_code'], 12) ?> <?= e(country_name($n['country_code'])) ?></span><?php endif; ?>
        </p>
        <h3 class="news-card__title"><a href="<?= e($href) ?>"<?= $target ?>><?= e($n['title']) ?></a></h3>
        <p class="news-card__summary"><?= e($n['summary']) ?></p>
        <p class="news-card__source">
            <?= $external ? e(t('news.read_on', ['source' => $n['source_name']])) . ' ↗' : e(t('news.read')) . ' →' ?>
        </p>
    </div>
</li>
