<?php /** @var array $rows @var string $status */ ?>
<h1><?= e(t('admin.nav_submissions')) ?></h1>
<nav class="chips">
    <?php foreach (['pending', 'validated', 'rejected'] as $s): ?>
        <a class="chip" href="<?= path('admin/declarations', ['statut' => $s]) ?>" <?= $s === $status ? 'aria-current="page"' : '' ?>><?= e(t('admin.review_' . $s)) ?></a>
    <?php endforeach; ?>
</nav>
<?php if (!$rows): ?><p class="muted"><?= e(t('admin.none')) ?></p><?php else: ?>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.received')) ?></th><th><?= e(t('admin.track')) ?></th><th><?= e(t('submit.platform')) ?></th><th><?= e(t('admin.period')) ?></th><th class="num"><?= e(t('submit.streams')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
        <tr>
            <td><?= e(fmt_date(substr($r['created_at'], 0, 10))) ?></td>
            <td><?= e($r['submitted_track_title']) ?><br><small class="muted"><?= e($r['submitted_artist_name']) ?><?= $r['track_id'] ? ' · ' . e(t('admin.linked')) : ' · ' . e(t('admin.not_linked')) ?></small></td>
            <td><?= e(platform_name($r['platform'])) ?></td>
            <td><?= e(fmt_date($r['period_start'], false)) ?> → <?= e(fmt_date($r['period_end'])) ?></td>
            <td class="num"><?= e(fmt_number((int) $r['streams'])) ?></td>
            <td><a href="<?= path('admin/declarations/' . $r['id']) ?>"><?= e(t('admin.open')) ?></a></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<?php endif; ?>
