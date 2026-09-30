<?php
/** @var array $item @var array $tiers */
use Cauri\Core\Csrf;
?>
<h1><?= e($item['id'] ? t('admin.partners_edit') : t('admin.partners_new')) ?></h1>
<form method="post" action="<?= path('admin/partenaires/' . ($item['id'] ?? 'nouveau')) ?>" enctype="multipart/form-data" class="admin-form">
    <?= Csrf::field() ?>
    <div class="field"><label for="p-name"><?= e(t('admin.partner_name')) ?></label>
        <input id="p-name" name="name" required maxlength="120" value="<?= e($item['name']) ?>"></div>
    <div class="field"><label for="p-url"><?= e(t('admin.partner_url')) ?></label>
        <input id="p-url" name="url" type="url" maxlength="300" placeholder="https://" value="<?= e((string) $item['url']) ?>"></div>
    <div class="field"><label for="p-tier"><?= e(t('admin.partner_tier')) ?></label>
        <select id="p-tier" name="tier">
            <?php foreach ($tiers as $tier): ?>
                <option value="<?= e($tier) ?>" <?= $item['tier'] === $tier ? 'selected' : '' ?>><?= e(t('partners.tier_' . $tier)) ?></option>
            <?php endforeach; ?>
        </select></div>
    <div class="field"><label for="p-desc"><?= e(t('admin.partner_description')) ?></label>
        <textarea id="p-desc" name="description" maxlength="240" rows="3"><?= e((string) $item['description']) ?></textarea></div>
    <div class="field"><label for="p-logo"><?= e(t('admin.partner_logo')) ?></label>
        <?php if ($item['logo_path']): ?><p><img src="/media/partners/<?= e(rawurlencode(basename($item['logo_path']))) ?>" alt="" height="60" class="partner-thumb"></p><?php endif; ?>
        <input id="p-logo" name="logo" type="file" accept="image/png,image/jpeg,image/webp"></div>
    <div class="field"><label for="p-order"><?= e(t('admin.partner_order')) ?></label>
        <input id="p-order" name="sort_order" type="number" value="<?= (int) $item['sort_order'] ?>"></div>
    <div class="field"><label><input type="checkbox" name="is_active" value="1" <?= $item['is_active'] ? 'checked' : '' ?>> <?= e(t('admin.partner_active')) ?></label></div>
    <p class="toolbar">
        <button class="button" type="submit"><?= e(t('admin.save')) ?></button>
        <a class="button button--ghost" href="<?= path('admin/partenaires') ?>"><?= e(t('admin.cancel')) ?></a>
    </p>
</form>
<?php if ($item['id']): ?>
<form method="post" action="<?= path('admin/partenaires/' . $item['id'] . '/supprimer') ?>" class="toolbar">
    <?= Csrf::field() ?>
    <button class="button button--small button--danger" type="submit"><?= e(t('admin.delete')) ?></button>
</form>
<?php endif; ?>
