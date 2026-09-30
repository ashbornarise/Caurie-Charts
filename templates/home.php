<?php
/** @var array $country @var bool $regional @var string $chartCode @var ?array $run @var array $entries @var string $periodType @var array $highlights @var array $countries @var array $aside @var array $numberOnes */
use Cauri\Controllers\Controller;
use Cauri\Core\Config;
use Cauri\Core\View;
use Cauri\Services\ShareImage;

$code = $country['code'];
// Lien d'accueil qui garde le pays et la période choisis (sans pays = classement des cinq pays)
$homeLink = function (?string $countryCode, string $period) use ($code): string {
    $q = [];
    $cc = $countryCode ?? $code;
    if ($cc !== 'WA') {
        $q['pays'] = strtolower($cc);
    }
    if ($period !== 'week') {
        $q['periode'] = Controller::periodSlug($period);
    }
    return path('/', $q);
};
?>
<div class="wrap page-grid">
<div class="page-main">
    <section class="chart-hero" id="classement">
        <p class="eyebrow"><?php if ($regional): foreach ($countries as $c): ?><?= flag($c['code'], 14) ?><?php endforeach; else: ?><?= flag($code, 16) ?><?php endif; ?><?= e(chart_name($regional ? 'prime-wa' : 'prime')) ?></p>
        <h1 class="chart-hero__title"><?= e(t('home.title', ['country' => country_name($code), 'size' => $country['chart_size']])) ?></h1>
        <?= View::partial('partials/period-tabs', [
            'periodType' => $periodType,
            'periods'    => ['week', 'month', 'year', 'all'],
            'link'       => fn ($p) => $homeLink(null, $p),
        ]) ?>
        <?php if ($run): ?>
            <p class="chart-hero__period"><?= e(period_label($run)) ?></p>
        <?php endif; ?>
        <?php if ($regional): ?><p class="chart-hero__lead"><?= e(t('home.region_lead')) ?></p><?php endif; ?>
    </section>

    <section aria-label="<?= e(t('home.title', ['country' => country_name($code), 'size' => $country['chart_size']])) ?>">
        <?php if (!$entries && !empty($live['rows'])): ?>
            <p class="notice notice--live"><?= e(t('chart.live_intro')) ?> <strong><?= e(t('chart.live_day', ['date' => fmt_date($live['day'])])) ?></strong><br><?= e(t('chart.official_soon')) ?></p>
            <ol class="chart-list chart-list--long">
                <?php foreach ($live['rows'] as $e): ?>
                    <?= View::partial('partials/live-entry', ['e' => $e, 'showSourceCountry' => true]) ?>
                <?php endforeach; ?>
            </ol>
            <div class="chart-actions">
                <a class="button" href="<?= e(chart_path($code, $chartCode) . '?vue=direct') ?>"><?= e(t('home.full_chart')) ?></a>
            </div>
        <?php elseif (!$entries): ?>
            <p class="empty"><?= e(t('chart.empty')) ?></p>
        <?php else: ?>
            <ol class="chart-list">
                <?php foreach ($entries as $e): ?>
                    <?= View::partial('partials/entry', ['e' => $e, 'showCountry' => $regional]) ?>
                <?php endforeach; ?>
            </ol>
            <div class="chart-actions">
                <a class="button" href="<?= chart_path($code, $chartCode, $periodType, $run['period_key']) ?>"><?= e(t('home.full_chart')) ?></a>
                <a class="button button--ghost" href="<?= e(ShareImage::url((int) $run['id'], 'square')) ?>" download><?= e(t('share.square')) ?></a>
                <a class="button button--ghost" href="<?= e(ShareImage::url((int) $run['id'], 'story')) ?>" download><?= e(t('share.story')) ?></a>
            </div>
        <?php endif; ?>
    </section>

    <?php if ($hotArtists): ?>
    <?= View::partial('partials/hot-artists', ['artists' => $hotArtists]) ?>
    <?php endif; ?>

    <?php if ($highlights): ?>
    <section class="highlights">
        <?php foreach ($highlights as $chartCode => $h): ?>
            <article class="highlight">
                <h2 class="highlight__title"><a href="<?= e(chart_path($code, $chartCode)) ?>"><?= e(chart_name($chartCode)) ?></a></h2>
                <p class="highlight__desc"><?= e(t("chart.short.$chartCode")) ?></p>
                <?php if (!empty($h['live'])): ?>
                    <ol class="chart-list chart-list--compact">
                        <?php foreach ($h['live'] as $e): ?>
                            <?= View::partial('partials/live-entry', ['e' => $e, 'compact' => true]) ?>
                        <?php endforeach; ?>
                    </ol>
                <?php elseif ($h['entries']): ?>
                    <ol class="chart-list chart-list--compact">
                        <?php foreach ($h['entries'] as $e): ?>
                            <?= View::partial('partials/entry', ['e' => $e, 'compact' => true]) ?>
                        <?php endforeach; ?>
                    </ol>
                <?php else: ?>
                    <p class="empty"><?= e(t('chart.empty_short')) ?></p>
                <?php endif; ?>
            </article>
        <?php endforeach; ?>
    </section>
    <?php endif; ?>

    <section class="countries" id="pays">
        <h2 class="section-title"><?= e(t('home.all_countries')) ?></h2>
        <ul class="countries__list">
            <?php $one = $numberOnes['WA'] ?? null; ?>
            <li class="countries__region">
                <a class="country-card country-card--region<?= $regional ? ' country-card--current' : '' ?>" href="<?= $homeLink('WA', $periodType) ?>#classement" <?= $regional ? 'aria-current="true"' : '' ?>>
                    <span class="country-card__flags"><?php foreach ($countries as $c): ?><?= flag($c['code'], 24, 'country-card__flag') ?><?php endforeach; ?></span>
                    <span class="country-card__body">
                        <span class="country-card__size"><?= e($regional ? t('home.showing') : t('home.region_card', ['n' => count($countries)])) ?></span>
                        <span class="country-card__name"><?= e(country_name('WA')) ?></span>
                    </span>
                    <?php if ($one): ?>
                    <span class="country-card__one">
                        <span class="country-card__one-label"><?= e(t('home.number_one')) ?></span>
                        <span class="country-card__one-title"><?= e($one['title']) ?></span>
                        <span class="country-card__one-artist"><?= e($one['artist_name']) ?></span>
                    </span>
                    <?php endif; ?>
                </a>
            </li>
            <?php foreach ($countries as $c): $current = $c['code'] === $code; $one = $numberOnes[$c['code']] ?? null; ?>
                <li>
                    <a class="country-card country-card--<?= e(strtolower($c['code'])) ?><?= $current ? ' country-card--current' : '' ?>" href="<?= $homeLink($c['code'], $periodType) ?>#classement" <?= $current ? 'aria-current="true"' : '' ?>>
                        <span class="country-card__head">
                            <?= flag($c['code'], 32, 'country-card__flag') ?>
                            <span class="country-card__size"><?= e($current ? t('home.showing') : t('home.top_n', ['n' => $c['chart_size']])) ?></span>
                        </span>
                        <span class="country-card__name"><?= e(country_name($c['code'])) ?></span>
                        <?php if ($one): ?>
                        <span class="country-card__one">
                            <span class="country-card__one-label"><?= e(t('home.number_one')) ?></span>
                            <span class="country-card__one-title"><?= e($one['title']) ?></span>
                            <span class="country-card__one-artist"><?= e($one['artist_name']) ?></span>
                        </span>
                        <?php else: ?>
                        <span class="country-card__one country-card__one--empty"><?= e(t('chart.empty_short')) ?></span>
                        <?php endif; ?>
                    </a>
                </li>
            <?php endforeach; ?>
        </ul>
    </section>

    <?php if ($homeNews): ?>
    <section class="home-news" aria-labelledby="home-news-title">
        <div class="partners__head">
            <h2 id="home-news-title"><?= e(t('news.title')) ?></h2>
            <a class="link-arrow" href="<?= path('actualites') ?>"><?= e(t('news.all')) ?></a>
        </div>
        <ul class="news-grid news-grid--three">
            <?php foreach ($homeNews as $i => $n): ?>
            <?= View::partial('partials/news-card', ['n' => $n, 'i' => $i]) ?>
            <?php endforeach; ?>
        </ul>
    </section>
    <?php endif; ?>

    <?php if ($playlist = Config::get('app.tracking.spotify_playlist')): ?>
    <?= View::partial('partials/spotify', ['playlist' => $playlist]) ?>
    <?php endif; ?>

    <?= View::partial('partials/partners', ['partners' => $partners, 'compact' => true]) ?>

    <?= View::partial('partials/method-block') ?>
</div>
<?= View::partial('partials/aside', ['aside' => $aside]) ?>
</div>
