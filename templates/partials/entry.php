<?php
/**
 * Une ligne de classement (titre ou artiste).
 * @var array $e entrée enrichie (title, artist_name, slugs, label_owner...)
 * @var bool $compact version courte (encarts de l'accueil)
 */
$compact ??= false;
$showCountry ??= false; // classement régional : drapeau du pays de l'artiste
$m = movement($e);
$isArtist = $e['track_id'] === null;
$name = $isArtist ? $e['artist_name'] : $e['title'];
$href = $isArtist ? path('artiste/' . $e['artist_slug']) : path('titre/' . $e['track_slug']);
$moveLabel = match ($m['type']) {
    'up'   => t('move.up', ['n' => $m['value']]),
    'down' => t('move.down', ['n' => $m['value']]),
    'same' => t('move.same'),
    'new'  => t('move.new'),
    're'   => t('move.re'),
};
?>
<li class="entry<?= $e['position'] === 1 ? ' entry--top' : '' ?><?= $compact ? ' entry--compact' : '' ?>">
    <?php if ($e['position'] === 1): ?>
    <!-- N° 1 : particules décoratives (CSS seul, figées si l'utilisateur réduit les animations) -->
    <span class="particles" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>
    <?php endif; ?>
    <span class="entry__rank"><?= (int) $e['position'] ?></span>
    <span class="cover" aria-hidden="true">
        <?php if (!empty($e['cover_url'])): ?>
            <img src="<?= e($e['cover_url']) ?>" alt="" width="56" height="56" loading="lazy">
        <?php else: ?>
            <span class="cover__initials"><?= e(initials($name)) ?></span>
        <?php endif; ?>
    </span>
    <span class="entry__main">
        <a class="entry__title" href="<?= $href ?>"><?= e($name) ?></a>
        <?php if (!$isArtist): ?>
        <span class="entry__artist">
            <?php if ($showCountry && !empty($e['artist_country'])): ?><span class="entry__country" title="<?= e(country_name($e['artist_country'])) ?>"><?= flag($e['artist_country'], 12) ?></span><?php endif; ?>
            <a href="<?= path('artiste/' . $e['artist_slug']) ?>"><?= e($e['artist_name']) ?></a><?php if ($e['featuring']): ?> <span class="feat">feat. <?= e($e['featuring']) ?></span><?php endif; ?>
        </span>
        <?php else: ?>
        <span class="entry__artist"><?= e(t('chart.tracks_count', ['n' => $e['sources_count']])) ?></span>
        <?php endif; ?>
        <?php if (is_group_label($e['label_owner'])): ?>
            <a class="badge" href="<?= path('methodologie') ?>#independance" title="<?= e(t('badge.title')) ?>"><?= e(\Cauri\Core\Config::get('app.group_label.name')) ?></a>
        <?php endif; ?>
        <?php if (!$compact && !empty($e['sources'])): ?>
        <ul class="sources" aria-label="<?= e(t('chart.sources_label')) ?>">
            <?php foreach ($e['sources'] as $platform => $s):
                $detail = t('chart.src_' . $s['kind'], ['n' => fmt_number($s['value'])]); ?>
            <li class="source source--<?= e($platform) ?>" title="<?= e(platform_name($platform) . ' : ' . $detail) ?>">
                <span class="source__name"><?= e(platform_name($platform)) ?></span>
                <span class="source__value"><?= e($s['kind'] === 'chart' ? '#' . $s['value'] : fmt_number($s['value'])) ?></span>
            </li>
            <?php endforeach; ?>
        </ul>
        <?php endif; ?>
    </span>
    <?php if (!$compact && (($e['streams'] ?? 0) > 0 || ($e['views'] ?? 0) > 0)): ?>
    <span class="entry__figures">
        <?php if ($e['streams'] > 0): ?>
        <span class="figure figure--main" title="<?= e(t('chart.streams_long')) ?>"><strong><?= e(fmt_number($e['streams'])) ?></strong> <?= e(t('chart.streams')) ?></span>
        <?php endif; ?>
        <?php if ($e['views'] > 0): ?>
        <span class="figure<?= $e['streams'] > 0 ? '' : ' figure--main' ?>" title="<?= e(t('chart.views_long')) ?>"><strong><?= e(fmt_number($e['views'])) ?></strong> <?= e(t('chart.views')) ?></span>
        <?php endif; ?>
    </span>
    <?php endif; ?>
    <span class="move move--<?= $m['type'] ?>" title="<?= e($moveLabel) ?>">
        <span class="visually-hidden"><?= e($moveLabel) ?></span>
        <span aria-hidden="true"><?= match ($m['type']) {
            'up' => '▲ ' . $m['value'], 'down' => '▼ ' . $m['value'], 'same' => '=', 'new' => e(t('move.new_short')), 're' => e(t('move.re_short')),
        } ?></span>
    </span>
    <?php if (!$compact): ?>
    <span class="entry__stats">
        <span><abbr title="<?= e(t('chart.peak_long')) ?>"><?= e(t('chart.peak')) ?></abbr> <?= (int) $e['peak_position'] ?></span>
        <span><abbr title="<?= e(t('chart.weeks_long')) ?>"><?= e(t('chart.weeks')) ?></abbr> <?= (int) $e['weeks_on_chart'] ?></span>
        <?php if ($e['growth_pct'] !== null): ?><span>+<?= e(fmt_number((float) $e['growth_pct'])) ?> %</span><?php endif; ?>
    </span>
    <?php endif; ?>
</li>
