<?php /** @var array $rows */ ?>
<h1><?= e(t('admin.nav_partners')) ?></h1>
<p class="muted"><?= e(t('admin.partners_intro')) ?></p>
<p>
    <a class="button button--small" href="<?= path('admin/partenaires/nouveau') ?>"><?= e(t('admin.partners_new')) ?></a>
    <a class="button button--small button--ghost" href="<?= path('partenaires') ?>" target="_blank" rel="noopener"><?= e(t('admin.view_site')) ?></a>
</p>
<?php if (!$rows): ?><p class="empty"><?= e(t('admin.partners_none')) ?></p><?php endif; ?>
<?php if ($rows): ?>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.partner_logo_short')) ?></th><th><?= e(t('admin.partner_name')) ?></th><th><?= e(t('admin.partner_tier')) ?></th><th class="num"><?= e(t('admin.partner_order')) ?></th><th><?= e(t('admin.status')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $p): ?>
        <tr>
            <td><?php if ($p['logo_path']): ?><img src="/media/partners/<?= e(rawurlencode(basename($p['logo_path']))) ?>" alt="" height="36" class="partner-thumb"><?php endif; ?></td>
            <td><strong><?= e($p['name']) ?></strong><?php if ($p['url']): ?><br><small class="muted"><?= e($p['url']) ?></small><?php endif; ?></td>
            <td><?= e(t('partners.tier_' . $p['tier'])) ?></td>
            <td class="num"><?= (int) $p['sort_order'] ?></td>
            <td><span class="status status--<?= $p['is_active'] ? 'published' : 'draft' ?>"><?= e($p['is_active'] ? t('admin.partner_shown') : t('admin.partner_hidden')) ?></span></td>
            <td><a href="<?= path('admin/partenaires/' . $p['id']) ?>"><?= e(t('admin.edit')) ?></a></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<?php endif; ?>
