<?php /** @var array $pending @var array $drafts @var int $submissions @var int $messages @var ?string $lastSnapshot @var ?array $quota */ ?>
<h1><?= e(t('admin.nav_dashboard')) ?></h1>
<div class="cards">
    <a class="card<?= $pending ? ' card--alert' : '' ?>" href="<?= path('admin/classements') ?>">
        <span class="card__value"><?= array_sum(array_column($pending, 'n')) ?></span>
        <span class="card__label"><?= e(t('admin.card_flags')) ?></span>
    </a>
    <a class="card" href="<?= path('admin/classements') ?>">
        <span class="card__value"><?= count($drafts) ?></span>
        <span class="card__label"><?= e(t('admin.card_drafts')) ?></span>
    </a>
    <a class="card<?= $submissions ? ' card--alert' : '' ?>" href="<?= path('admin/declarations') ?>">
        <span class="card__value"><?= $submissions ?></span>
        <span class="card__label"><?= e(t('admin.card_submissions')) ?></span>
    </a>
    <a class="card" href="<?= path('admin/messages') ?>">
        <span class="card__value"><?= $messages ?></span>
        <span class="card__label"><?= e(t('admin.card_messages')) ?></span>
    </a>
    <div class="card">
        <span class="card__value"><?= $lastSnapshot ? e(fmt_date($lastSnapshot, false)) : '—' ?></span>
        <span class="card__label"><?= e(t('admin.card_last_snapshot')) ?><?= $quota ? ' · ' . e(t('admin.quota_used', ['n' => $quota['units_used']])) : '' ?></span>
    </div>
</div>

<?php if ($pending): ?>
<h2><?= e(t('admin.flags_to_review')) ?></h2>
<ul>
    <?php foreach ($pending as $p): ?>
        <li><?= e($p['code']) ?>, <?= e(t('admin.week_of', ['date' => fmt_date($p['week_start'])])) ?> : <strong><?= (int) $p['n'] ?></strong></li>
    <?php endforeach; ?>
</ul>
<?php endif; ?>

<h2><?= e(t('admin.drafts')) ?></h2>
<?php if ($drafts): ?>
<table class="data-table">
    <thead><tr><th><?= e(t('admin.country')) ?></th><th><?= e(t('admin.period')) ?></th><th><?= e(t('admin.runs')) ?></th><th></th></tr></thead>
    <tbody>
    <?php foreach ($drafts as $d): ?>
        <tr><td><?= e($d['code']) ?></td><td><?= e($d['period_key']) ?></td><td><?= (int) $d['runs'] ?></td><td><a href="<?= path('admin/classements/' . $d['first_id']) ?>"><?= e(t('admin.open')) ?></a></td></tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php else: ?><p class="muted"><?= e(t('admin.no_drafts')) ?></p><?php endif; ?>

<div class="box box--accent">
    <h2 class="flush"><?= e(t('admin.weekly_routine')) ?></h2>
    <ol>
        <li><?= e(t('admin.routine_1')) ?></li>
        <li><?= e(t('admin.routine_2')) ?></li>
        <li><?= e(t('admin.routine_3')) ?></li>
        <li><?= e(t('admin.routine_4')) ?></li>
    </ol>
</div>
