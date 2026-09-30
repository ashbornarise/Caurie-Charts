<?php
/** @var string $q @var array $countries @var array $artists @var array $tracks @var array $user */
use Cauri\Core\Csrf;

$allPlatforms = ['youtube', 'audiomack', 'boomplay', 'spotify', 'apple_music', 'deezer'];
?>
<h1><?= e(t('admin.nav_catalog')) ?></h1>
<form method="get" action="<?= path('admin/catalogue') ?>" class="toolbar">
    <label class="visually-hidden" for="q"><?= e(t('admin.search')) ?></label>
    <input id="q" type="search" name="q" value="<?= e($q) ?>" placeholder="<?= e(t('admin.search')) ?>">
    <button class="button button--small" type="submit"><?= e(t('admin.search')) ?></button>
    <a class="button button--small button--ghost" href="<?= path('admin/artistes/nouveau') ?>"><?= e(t('admin.new_artist')) ?></a>
    <a class="button button--small button--ghost" href="<?= path('admin/titres/nouveau') ?>"><?= e(t('admin.new_track')) ?></a>
</form>

<h2><?= e(t('admin.countries')) ?></h2>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.country')) ?></th><th><?= e(t('admin.chart_size')) ?></th><th><?= e(t('admin.platforms')) ?></th><th><?= e(t('admin.locale')) ?></th><th><?= e(t('admin.active')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($countries as $c): $active = explode(',', $c['platforms']); $formId = 'country-' . $c['id']; ?>
        <tr>
            <td><strong><?= e($c['code']) ?></strong> <?= e(country_name($c['code'])) ?><?= $c['is_pilot'] ? ' · ' . e(t('admin.pilot')) : '' ?></td>
            <td><input form="<?= $formId ?>" type="number" name="chart_size" value="<?= (int) $c['chart_size'] ?>" min="5" max="100" class="num"></td>
            <td class="checks"><?php foreach ($allPlatforms as $p): ?><label><input form="<?= $formId ?>" type="checkbox" name="platforms[]" value="<?= $p ?>" <?= in_array($p, $active, true) ? 'checked' : '' ?>> <?= e(platform_name($p)) ?></label><?php endforeach; ?></td>
            <td><select form="<?= $formId ?>" name="locale"><option value="fr" <?= $c['locale'] === 'fr' ? 'selected' : '' ?>>fr</option><option value="en" <?= $c['locale'] === 'en' ? 'selected' : '' ?>>en</option></select></td>
            <td><input form="<?= $formId ?>" type="checkbox" name="is_active" value="1" <?= $c['is_active'] ? 'checked' : '' ?>></td>
            <td><?php if ($user['role'] === 'admin'): ?><form id="<?= $formId ?>" method="post" action="<?= path('admin/pays/' . $c['id']) ?>"><?= Csrf::field() ?><button class="button button--small" type="submit"><?= e(t('admin.save')) ?></button></form><?php endif; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<p class="fineprint"><?= e(t('admin.spotify_note')) ?></p>

<h2><?= e(t('admin.artists')) ?> (<?= count($artists) ?>)</h2>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.artist')) ?></th><th><?= e(t('admin.country')) ?></th><th><?= e(t('admin.label')) ?></th><th class="num"><?= e(t('admin.tracks')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($artists as $a): ?>
        <tr>
            <td><a href="<?= path('artiste/' . $a['slug']) ?>" target="_blank" rel="noopener"><?= e($a['name']) ?></a><?= $a['is_emerging'] ? ' <span class="tag">' . e(t('artist.emerging')) . '</span>' : '' ?></td>
            <td><?= e($a['code']) ?></td>
            <td><?= $a['label_owner'] ? '<span class="badge">' . e($a['label_owner']) . '</span>' : '—' ?></td>
            <td class="num"><?= (int) $a['tracks'] ?></td>
            <td><a href="<?= path('admin/artistes/' . $a['id']) ?>"><?= e(t('admin.edit')) ?></a> · <a href="<?= path('admin/titres/nouveau', ['artist' => $a['id']]) ?>"><?= e(t('admin.add_track')) ?></a></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>

<h2><?= e(t('admin.tracks')) ?> (<?= count($tracks) ?>)</h2>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.track')) ?></th><th><?= e(t('track.release')) ?></th><th><?= e(t('admin.platforms')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($tracks as $tr): ?>
        <tr>
            <td><a href="<?= path('titre/' . $tr['slug']) ?>" target="_blank" rel="noopener"><?= e($tr['title']) ?></a> <span class="muted">· <?= e($tr['artist_name']) ?></span><?= $tr['is_active'] ? '' : ' <span class="tag">' . e(t('admin.inactive')) . '</span>' ?></td>
            <td><?= $tr['release_date'] ? e($tr['release_date']) : '—' ?></td>
            <td><small><?= e(str_replace(',', ', ', (string) $tr['platforms'])) ?></small></td>
            <td><a href="<?= path('admin/titres/' . $tr['id']) ?>"><?= e(t('admin.edit')) ?></a></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
