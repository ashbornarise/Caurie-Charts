<?php
/**
 * @var array $country @var string $chartCode @var array $chart @var string $periodType
 * @var ?array $run @var array $entries @var array $history
 */
use Cauri\Core\Config;
use Cauri\Services\ShareImage;

$code = $country['code'];
$publicCharts = array_filter(Config::get('charts'), fn ($c) => $c['public'] && empty($c['regional']));
?>
<div class="wrap page-grid">
<div class="page-main">
<section class="chart-hero">
    <nav class="country-switch" aria-label="<?= e(t('nav.countries')) ?>">
        <a href="<?= chart_path('WA', 'prime-wa') ?>" <?= $regional ? 'aria-current="page"' : '' ?>><?= e(t('chart.region_short')) ?></a>
        <?php foreach ($countries as $c): ?>
            <a href="<?= chart_path($c['code'], $regional ? 'prime' : $chartCode, in_array($periodType, $chart['periods'], true) ? $periodType : 'week') ?>" <?= $c['code'] === $code ? 'aria-current="page"' : '' ?> title="<?= e(country_name($c['code'])) ?>"><?= flag($c['code'], 14) ?><?= e($c['code']) ?></a>
        <?php endforeach; ?>
    </nav>
    <nav class="chips" aria-label="<?= e(t('chart.choose')) ?>">
        <?php foreach ($publicCharts as $c => $def): $target = $regional && $c === 'prime' ? 'prime-wa' : $c; ?>
            <a class="chip" href="<?= e(chart_path($regional ? 'WA' : $code, $target)) ?>" <?= $target === $chartCode ? 'aria-current="page"' : '' ?>><?= e($def['name']) ?></a>
        <?php endforeach; ?>
    </nav>
    <p class="eyebrow"><?php if ($regional): foreach ($countries as $c): ?><?= flag($c['code'], 14) ?><?php endforeach; endif; ?><?= flag($code, 16) ?><?= e(country_name($code)) ?></p>
    <h1 class="chart-hero__title"><?= e($chart['name']) ?></h1>
    <p class="chart-hero__lead"><?= e(t("chart.description.$chartCode", ['country' => country_name($code)])) ?></p>

    <?php if ($view !== 'official' && in_array($chartCode, ['prime', 'prime-wa'], true)):
        // Vue en direct : semaine (7 jours), mois (30 jours), année (12 mois) et tout temps
        $vueQ = $view === 'live' ? 'direct' : $view;
    ?>
        <?= \Cauri\Core\View::partial('partials/period-tabs', [
            'periodType' => $livePeriod,
            'periods'    => ['week', 'month', 'year', 'all'],
            'link'       => fn ($p) => $p === 'all'
                ? url_with(chart_path($code, $chartCode, 'week'), ['vue' => $vueQ, 'periode' => 'tout'])
                : url_with(chart_path($code, $chartCode, $p), ['vue' => $vueQ]),
        ]) ?>
    <?php elseif (count($chart['periods']) > 1): ?>
        <?= \Cauri\Core\View::partial('partials/period-tabs', [
            'periodType' => $periodType,
            'periods'    => $chart['periods'],
            'link'       => fn ($p) => url_with(chart_path($code, $chartCode, $p), ['vue' => 'officiel']),
        ]) ?>
    <?php endif; ?>

    <?php if ($run): ?>
    <div class="chart-meta">
        <p class="chart-hero__period"><?= e(period_label($run)) ?></p>
        <?php if (count($history) > 1): ?>
        <form class="history" method="get" action="<?= chart_path($code, $chartCode, $periodType) ?>" data-history>
            <label for="history-select" class="visually-hidden"><?= e(t('chart.history')) ?></label>
            <select id="history-select" name="k" data-history-select>
                <?php foreach ($history as $h): ?>
                    <option value="<?= chart_path($code, $chartCode, $periodType, $h['period_key']) ?>" <?= $h['period_key'] === $run['period_key'] ? 'selected' : '' ?>>
                        <?= e(period_label($h + ['period_type' => $periodType])) ?>
                    </option>
                <?php endforeach; ?>
            </select>
            <noscript><button class="button button--small" type="submit"><?= e(t('chart.go')) ?></button></noscript>
        </form>
        <?php endif; ?>
    </div>
    <?php if ($run['correction_note']): ?>
        <p class="notice"><strong><?= e(t('chart.corrected', ['date' => fmt_date(substr($run['corrected_at'], 0, 10))])) ?></strong> <?= e($run['correction_note']) ?></p>
    <?php endif; ?>
    <?php endif; ?>
</section>

<?php if (in_array($chartCode, ['prime', 'prime-wa', 'buzz', 'fresh', 'icon', 'legend'], true)):
    $base = chart_path($code, $chartCode, $periodType);
    $tabs = ['officiel' => t('chart.view_official'), 'direct' => t('chart.view_live')];
    foreach ($liveSources as $s) {
        $tabs[$s] = \Cauri\Services\Charts\LiveChart::SOURCES[$s];
    }
    $current = ['official' => 'officiel', 'live' => 'direct'][$view] ?? $view;
?>
<nav class="view-tabs" aria-label="<?= e(t('chart.view_label')) ?>">
    <?php foreach ($tabs as $k => $label): ?>
        <a class="view-tab<?= $k === 'officiel' && !$run ? ' view-tab--soon' : '' ?>" href="<?= e(url_with($base, ['vue' => $k] + ($livePeriod === 'all' ? ['periode' => 'tout'] : []))) ?>" <?= $k === $current ? 'aria-current="page"' : '' ?>><?= e($label) ?></a>
    <?php endforeach; ?>
</nav>
<?php endif; ?>

<?php if ($view !== 'official' && $live !== null): ?>
<section>
    <p class="notice notice--live">
        <?= e($view === 'live' ? t(in_array($chartCode, ['prime', 'prime-wa'], true) ? 'chart.live_intro' : 'chart.live_intro_' . $chartCode) : t('chart.source_intro', ['source' => \Cauri\Services\Charts\LiveChart::SOURCES[$view], 'country' => country_name($code)])) ?>
        <?php if ($live['day']): ?><strong><?= e(t('chart.live_day', ['date' => fmt_date($live['day'])])) ?></strong><?php endif; ?>
        <?php if (!$run): ?><br><?= e(t('chart.official_soon')) ?><?php endif; ?>
    </p>
    <?php if (!$live['rows']): ?>
        <p class="empty"><?= e(t('chart.live_empty')) ?></p>
    <?php else: ?>
        <ol class="chart-list chart-list--long">
            <?php foreach ($live['rows'] as $e): ?>
                <?= \Cauri\Core\View::partial('partials/live-entry', ['e' => $e, 'showSourceCountry' => $regional || $view === 'live']) ?>
            <?php endforeach; ?>
        </ol>
    <?php endif; ?>
</section>
<?php else: ?>
<section>
    <?php if (!$entries): ?>
        <p class="empty"><?= e($chartCode === 'legend' ? t('chart.empty_legend') : t('chart.empty')) ?></p>
    <?php else: ?>
        <ol class="chart-list">
            <?php foreach ($entries as $e): ?>
                <?= \Cauri\Core\View::partial('partials/entry', ['e' => $e, 'showCountry' => $regional]) ?>
            <?php endforeach; ?>
        </ol>
        <div class="chart-actions">
            <a class="button button--ghost" href="<?= e(ShareImage::url((int) $run['id'], 'square')) ?>" download><?= e(t('share.square')) ?></a>
            <a class="button button--ghost" href="<?= e(ShareImage::url((int) $run['id'], 'story')) ?>" download><?= e(t('share.story')) ?></a>
        </div>
        <p class="fineprint"><?= e(t('chart.fineprint', ['version' => $run['methodology_version'], 'formula' => $run['formula_version']])) ?>
            <a href="<?= path('methodologie') ?>"><?= e(t('nav.methodology')) ?></a> ·
            <a href="<?= path('contact', ['type' => 'contestation']) ?>"><?= e(t('chart.contest')) ?></a>
        </p>
    <?php endif; ?>
</section>
<?php endif; ?>

<?= \Cauri\Core\View::partial('partials/method-block') ?>
</div>
<?= \Cauri\Core\View::partial('partials/aside', ['aside' => $aside]) ?>
</div>
<script src="<?= asset('js/app.js') ?>" defer></script>
