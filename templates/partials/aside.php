<?php
/** Encadré latéral. @var array $aside ['country', 'insights', 'news'] */
use Cauri\Services\Insights;

$country = $aside['country'];
$facts = $aside['insights']['facts'];
$next = $aside['insights']['next'] ?? null;
$trackLink = fn (array $e) => '<a href="' . path('titre/' . $e['track_slug']) . '">' . e($e['title']) . '</a>';
$artistLink = fn (array $e) => '<a href="' . path('artiste/' . $e['artist_slug']) . '">' . e($e['artist_name']) . '</a>';
?>
<aside class="page-aside" aria-label="<?= e(t('aside.label')) ?>">
    <?php if ($facts): ?>
    <section class="aside-card aside-card--glass">
        <h2 class="aside-card__title"><?= e(t('aside.facts_title', ['country' => country_name($country['code'])])) ?></h2>
        <ul class="facts">
            <?php foreach ($facts as $f): $e = $f['entry']; ?>
            <li class="fact">
                <span class="fact__label"><?= e(t('aside.fact_' . $f['type'])) ?></span>
                <span class="fact__text">
                <?php switch ($f['type']):
                    case 'number_one': ?>
                        <?= $trackLink($e) ?> · <?= $artistLink($e) ?>
                        <small><?= e($f['value'] > 1 ? t('aside.weeks_at_one', ['n' => $f['value']]) : t('aside.first_week_at_one')) ?></small>
                    <?php break; case 'climber': ?>
                        <?= $trackLink($e) ?> <small><?= e(t('aside.climb', ['from' => $e['previous_position'], 'to' => $e['position']])) ?></small>
                    <?php break; case 'best_new': ?>
                        <?= $trackLink($e) ?> <small><?= e(t('aside.enters_at', ['n' => $e['position']])) ?> · <?= e(t('aside.new_count', ['n' => $f['value']])) ?></small>
                    <?php break; case 'buzz': ?>
                        <?= $trackLink($e) ?> <small>+<?= e(fmt_number($f['value'])) ?> %</small>
                    <?php break; case 'most_tracks': ?>
                        <?= $artistLink($e) ?> <small><?= e(t('aside.tracks_in_chart', ['n' => $f['value']])) ?></small>
                <?php endswitch; ?>
                </span>
            </li>
            <?php endforeach; ?>
        </ul>
        <?php if ($next): ?><p class="aside-card__foot"><?= e(t('aside.next', ['date' => fmt_date($next, false)])) ?></p><?php endif; ?>
    </section>
    <?php endif; ?>

    <?php if ($aside['news']): ?>
    <section class="aside-card">
        <h2 class="aside-card__title"><?= e(t('news.title')) ?></h2>
        <ul class="news-list news-list--thumbs">
            <?php foreach ($aside['news'] as $i => $n):
                // Actualité importée : lien direct vers l'article du média ; teinte différente pour chaque ligne
                $external = ($n['origin'] ?? 'manual') === 'feed' && !empty($n['source_url']);
                $href = $external ? $n['source_url'] : path('actualites/' . $n['slug']);
            ?>
            <li class="news-thumb news-card--tone-<?= $i % 6 ?>">
                <a class="news-thumb__img" href="<?= e($href) ?>"<?= $external ? ' target="_blank" rel="noopener noreferrer"' : '' ?> tabindex="-1" aria-hidden="true">
                    <?php if (!empty($n['image_path'])): ?>
                        <img src="/media/news/<?= e(rawurlencode(basename($n['image_path']))) ?>" alt="" width="72" height="54" loading="lazy">
                    <?php else: ?>
                        <span><?= e(initials($n['source_name'] ?: brand())) ?></span>
                    <?php endif; ?>
                </a>
                <span class="news-thumb__text">
                    <span class="news-list__meta"><span class="news-card__tag"><?= e(t('news.cat_' . $n['category'])) ?></span> <?= e(fmt_date(substr($n['published_at'], 0, 10), false)) ?></span>
                    <a class="news-list__title" href="<?= e($href) ?>"<?= $external ? ' target="_blank" rel="noopener noreferrer"' : '' ?>><?= e($n['title']) ?></a>
                    <?php if ($external): ?><small class="news-thumb__source"><?= e($n['source_name']) ?> ↗</small><?php endif; ?>
                </span>
            </li>
            <?php endforeach; ?>
        </ul>
        <a class="link-arrow" href="<?= path('actualites') ?>"><?= e(t('news.all')) ?></a>
    </section>
    <?php endif; ?>

    <section class="aside-card aside-card--quiet">
        <h2 class="aside-card__title"><?= e(t('aside.dyk_title')) ?></h2>
        <p><?= e(Insights::didYouKnow()) ?></p>
    </section>

    <section class="aside-card aside-card--cta">
        <h2 class="aside-card__title"><?= e(t('aside.cta_title')) ?></h2>
        <p><?= e(t('aside.cta_text')) ?></p>
        <a class="button" href="<?= path('declarer') ?>"><?= e(t('nav.submit')) ?></a>
    </section>
</aside>
