<?php /** @var array $rows @var int $page */ ?>
<h1><?= e(t('admin.nav_audit')) ?></h1>
<p class="muted"><?= e(t('admin.audit_intro')) ?></p>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.date')) ?></th><th><?= e(t('admin.author')) ?></th><th><?= e(t('admin.action')) ?></th><th><?= e(t('admin.entity')) ?></th><th><?= e(t('admin.reason')) ?></th><th><?= e(t('admin.data')) ?></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
        <tr>
            <td><small><?= e($r['created_at']) ?></small></td>
            <td><?= e($r['user_name'] ?? t('admin.system')) ?></td>
            <td><code><?= e($r['action']) ?></code></td>
            <td><small><?= e(trim($r['entity_type'] . ' ' . $r['entity_id'])) ?></small></td>
            <td><?= e((string) $r['reason']) ?></td>
            <td><?php if ($r['data']): ?><pre class="json"><?= e($r['data']) ?></pre><?php endif; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<div class="toolbar">
    <?php if ($page > 1): ?><a class="button button--small button--ghost" href="<?= path('admin/journal', ['page' => $page - 1]) ?>">←</a><?php endif; ?>
    <?php if (count($rows) === 100): ?><a class="button button--small button--ghost" href="<?= path('admin/journal', ['page' => $page + 1]) ?>">→</a><?php endif; ?>
</div>
