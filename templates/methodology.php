<?php
/** @var array $formula @var array $upcoming @var array $exclusions @var array $corrections */
use Cauri\Core\Config;

$w = $formula['weights'];
$group = Config::get('app.group_label.name');
?>
<article class="prose">
    <p class="eyebrow"><?= e(t('methodology.eyebrow')) ?></p>
    <h1><?= e(t('methodology.heading', ['brand' => brand()])) ?></h1>
    <p class="lead"><?= e(t('methodology.intro', ['brand' => brand()])) ?></p>

    <h2><?= e(t('methodology.sources_title')) ?></h2>
    <p><?= e(t('methodology.sources_text')) ?></p>

    <h2><?= e(t('methodology.score_title')) ?></h2>
    <p><?= e(t('methodology.score_text')) ?></p>
    <table class="data-table">
        <caption><?= e(t('methodology.weights_caption', ['version' => $formula['version']])) ?></caption>
        <thead><tr><th scope="col"><?= e(t('methodology.source')) ?></th><th scope="col"><?= e(t('methodology.weight')) ?></th></tr></thead>
        <tbody>
            <tr><td><?= e(t('methodology.w_audio')) ?></td><td><?= e(number_format((float) $w['audio'], 1, ',', '')) ?></td></tr>
            <tr><td><?= e(t('methodology.w_youtube')) ?></td><td><?= e(number_format((float) $w['youtube'], 1, ',', '')) ?></td></tr>
            <tr><td><?= e(t('methodology.w_declaration')) ?></td><td><?= e(number_format((float) $w['declaration'], 1, ',', '')) ?></td></tr>
            <?php foreach ($formula['chart_weights'] ?? [] as $source => $cw): if ($cw <= 0) continue; ?>
            <tr><td><?= e(t('methodology.w_chart', ['platform' => platform_name($source)])) ?></td><td><?= e(number_format((float) $cw, 0, ',', ' ')) ?></td></tr>
            <?php endforeach; ?>
        </tbody>
    </table>
    <p><?= e(t('methodology.chart_positions', ['depth' => (int) ($formula['chart_depth'] ?? 100)])) ?></p>
    <p><?= e(t('methodology.diversity', ['top' => $formula['diversity']['top'], 'sources' => $formula['diversity']['min_sources']])) ?></p>
    <p><?= e(t('methodology.ties')) ?></p>
    <?php foreach ($upcoming as $u): ?>
        <p class="notice"><?= e(t('methodology.upcoming', ['version' => $u['version'], 'date' => fmt_date($u['effective_from'])])) ?> <?= e((string) $u['note']) ?></p>
    <?php endforeach; ?>

    <h2><?= e(t('methodology.charts_title')) ?></h2>
    <ul>
        <?php foreach (Config::get('charts') as $code => $c): if (!$c['public']) continue; ?>
            <li><strong><?= e($c['name']) ?></strong> : <?= e(t("chart.short.$code")) ?></li>
        <?php endforeach; ?>
    </ul>
    <p><?= e(t('methodology.country_rule')) ?></p>
    <p><?= e(t('methodology.calendar')) ?></p>

    <h2><?= e(t('methodology.checks_title')) ?></h2>
    <p><?= e(t('methodology.checks_text', ['factor' => (int) $formula['anti_fraud']['spike_factor'], 'tolerance' => (int) round($formula['anti_fraud']['declaration_tolerance'] * 100)])) ?></p>

    <h2 id="independance"><?= e(t('methodology.position_title')) ?></h2>
    <p><?= e(t('methodology.position_text', ['brand' => brand(), 'label' => $group])) ?></p>

    <h2><?= e(t('methodology.contest_title')) ?></h2>
    <p><?= e(t('methodology.contest_text')) ?> <a href="<?= path('contact', ['type' => 'contestation']) ?>"><?= e(t('chart.contest')) ?></a></p>

    <h2><?= e(t('methodology.exclusions_title')) ?></h2>
    <?php if ($exclusions): ?>
        <table class="data-table">
            <thead><tr><th scope="col"><?= e(t('track.week')) ?></th><th scope="col"><?= e(t('methodology.track')) ?></th><th scope="col"><?= e(t('methodology.reason')) ?></th></tr></thead>
            <tbody>
            <?php foreach ($exclusions as $x): ?>
                <tr>
                    <td><?= e(fmt_date($x['week_start'])) ?> · <?= e($x['country_code']) ?></td>
                    <td><a href="<?= path('titre/' . $x['slug']) ?>"><?= e($x['title']) ?></a> · <?= e($x['artist_name']) ?></td>
                    <td><?= e($x['reason']) ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    <?php else: ?>
        <p class="empty"><?= e(t('methodology.no_exclusions')) ?></p>
    <?php endif; ?>

    <?php if ($corrections): ?>
    <h2><?= e(t('methodology.corrections_title')) ?></h2>
    <ul>
        <?php foreach ($corrections as $c): ?>
            <li><?= e($c['chart_name']) ?> <?= e($c['country_code']) ?> <?= e($c['period_key']) ?>, <?= e(fmt_date(substr($c['corrected_at'], 0, 10))) ?> : <?= e($c['correction_note']) ?></li>
        <?php endforeach; ?>
    </ul>
    <?php endif; ?>

    <p class="fineprint"><?= e(t('methodology.attribution')) ?></p>
    <p class="fineprint"><?= e(t('methodology.version', ['version' => Config::get('app.methodology_version')])) ?></p>
</article>
