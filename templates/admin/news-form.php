<?php
/** @var array $item @var array $countries @var array $categories */
use Cauri\Core\Csrf;
?>
<p><a href="<?= path('admin/actualites') ?>">← <?= e(t('admin.nav_news')) ?></a></p>
<h1><?= $item['id'] ? e($item['title']) : e(t('admin.news_new')) ?></h1>
<form method="post" action="<?= path('admin/actualites/' . ($item['id'] ?? 'nouveau')) ?>" class="admin-form">
    <?= Csrf::field() ?>
    <div class="field"><label for="title"><?= e(t('admin.news_title')) ?></label><input id="title" name="title" value="<?= e($item['title']) ?>" maxlength="200" required></div>
    <div class="field"><label for="summary"><?= e(t('admin.news_summary')) ?></label><textarea id="summary" name="summary" rows="2" maxlength="400" required><?= e($item['summary']) ?></textarea>
        <p class="field__hint"><?= e(t('admin.news_summary_hint')) ?></p></div>
    <div class="field"><label for="body"><?= e(t('admin.news_body')) ?> <span class="optional"><?= e(t('form.optional')) ?></span></label><textarea id="body" name="body" rows="8"><?= e((string) $item['body']) ?></textarea></div>
    <div class="field-row">
        <div class="field"><label for="category"><?= e(t('admin.news_category')) ?></label>
            <select id="category" name="category"><?php foreach ($categories as $c): ?><option value="<?= $c ?>" <?= $item['category'] === $c ? 'selected' : '' ?>><?= e(t('news.cat_' . $c)) ?></option><?php endforeach; ?></select></div>
        <div class="field"><label for="country_id"><?= e(t('admin.country')) ?></label>
            <select id="country_id" name="country_id"><option value=""><?= e(t('admin.all_countries')) ?></option><?php foreach ($countries as $c): ?><option value="<?= (int) $c['id'] ?>" <?= (int) $item['country_id'] === (int) $c['id'] ? 'selected' : '' ?>><?= e($c['code']) ?></option><?php endforeach; ?></select></div>
    </div>
    <fieldset>
        <legend><?= e(t('admin.news_source')) ?></legend>
        <p class="field__hint"><?= e(t('admin.news_source_hint')) ?></p>
        <div class="field-row">
            <div class="field"><label for="source_name"><?= e(t('admin.news_source_name')) ?></label><input id="source_name" name="source_name" value="<?= e((string) $item['source_name']) ?>" maxlength="120"></div>
            <div class="field"><label for="source_url">URL</label><input id="source_url" type="url" name="source_url" value="<?= e((string) $item['source_url']) ?>" placeholder="https://"></div>
        </div>
    </fieldset>
    <div class="field-row">
        <div class="field"><label for="published_at"><?= e(t('admin.news_date')) ?></label><input id="published_at" type="datetime-local" name="published_at" value="<?= e(str_replace(' ', 'T', substr((string) $item['published_at'], 0, 16))) ?>"></div>
        <div class="field"><label for="status"><?= e(t('admin.status')) ?></label>
            <select id="status" name="status"><option value="draft" <?= $item['status'] === 'draft' ? 'selected' : '' ?>><?= e(t('admin.status_draft')) ?></option><option value="published" <?= $item['status'] === 'published' ? 'selected' : '' ?>><?= e(t('admin.status_published')) ?></option></select></div>
    </div>
    <button class="button" type="submit"><?= e(t('admin.save')) ?></button>
</form>
