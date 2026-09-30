<?php /** @var array $rows */ ?>
<h1><?= e(t('admin.nav_charts')) ?></h1>
<p class="muted"><?= e(t('admin.charts_intro')) ?></p>
<div class="table-scroll">
<table class="data-table">
    <thead><tr>
        <th><?= e(t('admin.period')) ?></th><th><?= e(t('admin.country')) ?></th><th><?= e(t('admin.status')) ?></th>
        <th><?= e(t('admin.flags')) ?></th><th><?= e(t('admin.published_at')) ?></th><th></th>
    </tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
        <tr>
            <td><strong><?= e($r['period_key']) ?></strong> <span class="muted"><?= e(t('period.' . $r['period_type'])) ?><?= $r['provisional'] ? ' · ' . e(t('period.provisional')) : '' ?></span><br>
                <small class="muted"><?= e(fmt_date($r['period_start'], false)) ?> → <?= e(fmt_date($r['period_end'])) ?></small></td>
            <td><?= e($r['code']) ?></td>
            <td><span class="status status--<?= e($r['status']) ?>"><?= e(t('admin.status_' . $r['status'])) ?></span><?= $r['corrected_at'] ? ' <span class="muted">' . e(t('admin.corrected')) . '</span>' : '' ?></td>
            <td><?= $r['pending'] ? '<span class="status status--pending">' . (int) $r['pending'] . ' ' . e(t('admin.to_review')) . '</span>' : '—' ?></td>
            <td><?= $r['published_at'] ? e(fmt_date(substr($r['published_at'], 0, 10))) : '—' ?></td>
            <td><?php if ($r['prime_id']): ?><a href="<?= path('admin/classements/' . $r['prime_id']) ?>"><?= e(t('admin.open')) ?></a><?php endif; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
