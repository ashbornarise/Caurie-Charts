<?php
/**
 * « Artistes du moment » : artistes confirmés, classés par leur présence dans les classements
 * des plateformes (Apple Music, Deezer, tendances YouTube) sur les 7 derniers jours.
 * @var array $artists
 */
$sources = ['apple_music' => 'Apple Music', 'deezer' => 'Deezer', 'youtube_trending' => 'YouTube'];
?>
<section class="hot-artists" aria-labelledby="hot-artists-title">
    <div class="partners__head">
        <div>
            <h2 id="hot-artists-title"><?= e(t('home.hot_title')) ?></h2>
            <p class="partners__lead"><?= e(t('home.hot_lead')) ?></p>
        </div>
    </div>
    <ul class="hot-artists__grid">
        <?php foreach ($artists as $a): ?>
        <li>
            <a class="hot-artist" href="<?= path('artiste/' . $a['slug']) ?>">
                <span class="hot-artist__photo">
                    <?php if ($a['image_url']): ?>
                    <img src="<?= e($a['image_url']) ?>" alt="" loading="lazy" width="160" height="160">
                    <?php else: ?>
                    <span class="cover__initials"><?= e(initials($a['name'])) ?></span>
                    <?php endif; ?>
                    <span class="hot-artist__flag"><?= flag($a['country_code'], 14) ?></span>
                </span>
                <span class="hot-artist__name"><?= e($a['name']) ?></span>
                <span class="hot-artist__meta">
                    <?php if ($a['best']): ?>
                        <?= e(t('home.hot_best', ['n' => (int) $a['best'], 'source' => $sources[$a['best_source']] ?? ''])) ?>
                        <?php if ($a['charts'] > 1): ?> · <?= e(t('home.hot_charts', ['n' => (int) $a['charts']])) ?><?php endif; ?>
                    <?php elseif ($a['fans']): ?>
                        <?= e(t('home.hot_fans', ['n' => fmt_number((int) $a['fans'])])) ?>
                    <?php endif; ?>
                </span>
            </a>
        </li>
        <?php endforeach; ?>
    </ul>
</section>
