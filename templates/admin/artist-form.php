<?php
/** @var array $artist @var array $countries */
use Cauri\Core\Csrf;
?>
<p><a href="<?= path('admin/catalogue') ?>">← <?= e(t('admin.nav_catalog')) ?></a></p>
<h1><?= $artist['id'] ? e($artist['name']) : e(t('admin.new_artist')) ?></h1>
<form method="post" action="<?= path('admin/artistes/' . ($artist['id'] ?? 'nouveau')) ?>" class="admin-form">
    <?= Csrf::field() ?>
    <div class="field"><label for="name"><?= e(t('admin.artist')) ?></label><input id="name" name="name" value="<?= e($artist['name']) ?>" maxlength="150" required></div>
    <div class="field"><label for="country"><?= e(t('admin.submission_country')) ?></label>
        <select id="country" name="submission_country_id" required>
            <option value=""><?= e(t('form.choose')) ?></option>
            <?php foreach ($countries as $c): ?>
                <option value="<?= (int) $c['id'] ?>" <?= (int) $c['id'] === (int) $artist['submission_country_id'] ? 'selected' : '' ?>><?= e($c['code'] . ' · ' . country_name($c['code'])) ?></option>
            <?php endforeach; ?>
        </select>
        <p class="field__hint"><?= e(t('admin.submission_country_hint')) ?></p>
    </div>
    <div class="field"><label for="label_owner"><?= e(t('admin.label')) ?> <span class="optional"><?= e(t('form.optional')) ?></span></label>
        <input id="label_owner" name="label_owner" value="<?= e((string) $artist['label_owner']) ?>" maxlength="50">
        <p class="field__hint"><?= e(t('admin.label_hint', ['code' => \Cauri\Core\Config::get('app.group_label.code')])) ?></p></div>
    <div class="field"><label class="check"><input type="checkbox" name="is_emerging" value="1" <?= $artist['is_emerging'] ? 'checked' : '' ?>> <?= e(t('admin.emerging_hint')) ?></label></div>
    <div class="field"><label for="image_url"><?= e(t('admin.image_url')) ?> <span class="optional"><?= e(t('form.optional')) ?></span></label><input id="image_url" type="url" name="image_url" value="<?= e((string) $artist['image_url']) ?>" placeholder="https://"></div>
    <div class="field"><label for="bio"><?= e(t('admin.bio')) ?> <span class="optional"><?= e(t('form.optional')) ?></span></label><textarea id="bio" name="bio" rows="4" maxlength="3000"><?= e((string) $artist['bio']) ?></textarea></div>
    <button class="button" type="submit"><?= e(t('admin.save')) ?></button>
</form>
