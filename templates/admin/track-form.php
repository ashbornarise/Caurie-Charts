<?php
/** @var array $track @var array $artists @var array $platformIds @var array $platforms */
use Cauri\Core\Csrf;
?>
<p><a href="<?= path('admin/catalogue') ?>">← <?= e(t('admin.nav_catalog')) ?></a></p>
<h1><?= $track['id'] ? e($track['title']) : e(t('admin.new_track')) ?></h1>
<form method="post" action="<?= path('admin/titres/' . ($track['id'] ?? 'nouveau')) ?>" class="admin-form">
    <?= Csrf::field() ?>
    <div class="field"><label for="title"><?= e(t('admin.track')) ?></label><input id="title" name="title" value="<?= e($track['title']) ?>" maxlength="200" required></div>
    <div class="field"><label for="artist_id"><?= e(t('admin.main_artist')) ?></label>
        <select id="artist_id" name="artist_id" required>
            <option value=""><?= e(t('form.choose')) ?></option>
            <?php foreach ($artists as $a): ?>
                <option value="<?= (int) $a['id'] ?>" <?= (int) $a['id'] === (int) $track['artist_id'] ? 'selected' : '' ?>><?= e($a['name'] . ' (' . $a['code'] . ')') ?></option>
            <?php endforeach; ?>
        </select></div>
    <div class="field-row">
        <div class="field"><label for="featuring"><?= e(t('admin.featuring')) ?> <span class="optional"><?= e(t('form.optional')) ?></span></label><input id="featuring" name="featuring" value="<?= e((string) $track['featuring']) ?>" maxlength="255"></div>
        <div class="field"><label for="release_date"><?= e(t('track.release')) ?></label><input id="release_date" type="date" name="release_date" value="<?= e((string) $track['release_date']) ?>"></div>
    </div>
    <div class="field"><label for="cover_url"><?= e(t('admin.cover_url')) ?> <span class="optional"><?= e(t('form.optional')) ?></span></label><input id="cover_url" type="url" name="cover_url" value="<?= e((string) $track['cover_url']) ?>" placeholder="https://"></div>
    <div class="field"><label class="check"><input type="checkbox" name="is_active" value="1" <?= $track['is_active'] ? 'checked' : '' ?>> <?= e(t('admin.active')) ?></label></div>

    <fieldset>
        <legend><?= e(t('admin.platform_ids')) ?></legend>
        <p class="field__hint"><?= e(t('admin.platform_ids_hint')) ?></p>
        <?php if ($platformIds): ?>
        <table class="data-table">
            <thead><tr><th><?= e(t('admin.platform')) ?></th><th><?= e(t('admin.external_id')) ?></th><th><?= e(t('admin.kind')) ?></th><th><?= e(t('admin.delete')) ?></th></tr></thead>
            <tbody>
            <?php foreach ($platformIds as $p): ?>
                <tr><td><?= e(platform_name($p['platform'])) ?></td><td><?= $p['url'] ? '<a href="' . e($p['url']) . '" target="_blank" rel="noopener">' . e($p['external_id']) . '</a>' : e($p['external_id']) ?></td><td><?= e($p['kind']) ?></td>
                    <td><input type="checkbox" name="delete_pid[]" value="<?= (int) $p['id'] ?>" aria-label="<?= e(t('admin.delete')) ?>"></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
        <?php endif; ?>
        <div class="field-row">
            <div class="field"><label for="new_platform"><?= e(t('admin.platform')) ?></label>
                <select id="new_platform" name="new_platform"><option value="">—</option><?php foreach ($platforms as $p): ?><option value="<?= $p ?>"><?= e(platform_name($p)) ?></option><?php endforeach; ?></select></div>
            <div class="field"><label for="new_external_id"><?= e(t('admin.external_id')) ?></label><input id="new_external_id" name="new_external_id" maxlength="191"></div>
            <div class="field"><label for="new_kind"><?= e(t('admin.kind')) ?></label>
                <select id="new_kind" name="new_kind"><?php foreach (['clip', 'audio', 'art_track', 'lyrics', 'live', 'remix', 'main'] as $k): ?><option value="<?= $k ?>"><?= $k ?></option><?php endforeach; ?></select></div>
        </div>
        <div class="field-row">
            <div class="field"><label for="new_url">URL</label><input id="new_url" type="url" name="new_url" placeholder="https://"></div>
            <div class="field"><label for="new_published_at"><?= e(t('admin.published_on_platform')) ?></label><input id="new_published_at" type="date" name="new_published_at"></div>
        </div>
    </fieldset>
    <button class="button" type="submit"><?= e(t('admin.save')) ?></button>
</form>
