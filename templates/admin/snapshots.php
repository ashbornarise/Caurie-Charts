<?php
/** @var array $platformIds @var array $recent @var string $today */
use Cauri\Core\Csrf;
?>
<h1><?= e(t('admin.nav_snapshots')) ?></h1>
<p class="muted"><?= e(t('admin.snapshots_intro')) ?></p>

<form method="post" action="<?= path('admin/releves') ?>" class="admin-form box box--accent">
    <?= Csrf::field() ?>
    <div class="field"><label for="tpi"><?= e(t('admin.content')) ?></label>
        <select id="tpi" name="track_platform_id" required>
            <option value=""><?= e(t('form.choose')) ?></option>
            <?php foreach ($platformIds as $p): ?>
                <option value="<?= (int) $p['id'] ?>"><?= e("{$p['code']} · {$p['artist_name']} · {$p['title']} · " . platform_name($p['platform']) . ($p['last'] ? ' (' . t('admin.last', ['v' => $p['last']]) . ')' : '')) ?></option>
            <?php endforeach; ?>
        </select>
    </div>
    <div class="field-row">
        <div class="field"><label for="captured_on"><?= e(t('admin.snapshot_day')) ?></label><input id="captured_on" type="date" name="captured_on" value="<?= e($today) ?>" max="<?= e($today) ?>" required></div>
        <div class="field"><label for="plays"><?= e(t('admin.snapshot_plays')) ?></label><input id="plays" type="number" name="plays" min="0" step="1" required></div>
    </div>
    <p class="field__hint"><?= e(t('admin.snapshot_hint')) ?></p>
    <button class="button" type="submit"><?= e(t('admin.save')) ?></button>
</form>

<h2><?= e(t('admin.recent_manual')) ?></h2>
<?php if (!$recent): ?><p class="muted"><?= e(t('admin.none')) ?></p><?php else: ?>
<table class="data-table">
    <thead><tr><th><?= e(t('admin.snapshot_day')) ?></th><th><?= e(t('admin.track')) ?></th><th class="num"><?= e(t('admin.snapshot_plays')) ?></th><th><?= e(t('admin.author')) ?></th></tr></thead>
    <tbody>
    <?php foreach ($recent as $r): ?>
        <tr><td><?= e($r['captured_on']) ?></td><td><?= e($r['title']) ?> · <?= e(platform_name($r['platform'])) ?></td><td class="num"><?= e(fmt_number((int) $r['plays'])) ?></td><td><?= e((string) $r['user_name']) ?></td></tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php endif; ?>
