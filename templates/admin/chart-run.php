<?php
/** @var array $run @var array $entries @var array $siblings @var array $flagged @var array $blocking @var int $pending @var array $user */
use Cauri\Core\Csrf;

$isAdmin = $user['role'] === 'admin';
$breakdown = fn (string $json) => implode(' · ', array_map(fn ($k, $v) => platform_name(explode(':', $k)[0]) . (str_contains($k, ':') ? ' (' . t('admin.declared') . ')' : '') . ' ' . fmt_number($v['delta']) . ' × ' . $v['weight'], array_keys(json_decode($json, true) ?: []), json_decode($json, true) ?: []));
?>
<p><a href="<?= path('admin/classements') ?>">← <?= e(t('admin.nav_charts')) ?></a></p>
<h1><?= e(chart_name($run['chart_code'])) ?> · <?= e($run['country_code']) ?> · <?= e($run['period_key']) ?></h1>
<p>
    <span class="status status--<?= e($run['status']) ?>"><?= e(t('admin.status_' . $run['status'])) ?></span>
    <span class="muted"><?= e(period_label($run)) ?> · <?= e(t('admin.formula_v', ['v' => $run['formula_version']])) ?> · <?= e(t('admin.computed_at', ['date' => $run['computed_at']])) ?> UTC</span>
</p>

<nav class="chips">
    <?php foreach ($siblings as $s): ?>
        <a class="chip" href="<?= path('admin/classements/' . $s['id']) ?>" <?= (int) $s['id'] === (int) $run['id'] ? 'aria-current="page"' : '' ?>><?= e($s['name']) ?></a>
    <?php endforeach; ?>
</nav>

<?php if ($run['correction_note']): ?>
    <p class="notice"><?= e(t('admin.correction_note')) ?> : <?= e($run['correction_note']) ?></p>
<?php endif; ?>

<?php if ($isAdmin): ?>
<div class="toolbar">
    <?php if ($run['status'] === 'draft' && $run['period_type'] === 'week'): ?>
    <form method="post" action="<?= path('admin/publier') ?>" class="inline">
        <?= Csrf::field() ?>
        <input type="hidden" name="run_id" value="<?= (int) $run['id'] ?>">
        <input type="hidden" name="country" value="<?= e($run['country_code']) ?>">
        <input type="hidden" name="period_type" value="<?= e($run['period_type']) ?>">
        <input type="hidden" name="period_key" value="<?= e($run['period_key']) ?>">
        <button class="button" type="submit" <?= $pending ? 'disabled' : '' ?>><?= e(t('admin.publish_all', ['n' => count($siblings)])) ?></button>
    </form>
    <?php if ($pending): ?><span class="status status--pending"><?= e(t('admin.publish_blocked', ['n' => $pending])) ?></span><?php endif; ?>
    <?php endif; ?>
    <details>
        <summary class="button button--ghost button--small"><?= e(t('admin.recompute')) ?></summary>
        <form method="post" action="<?= path('admin/recalculer') ?>" class="box admin-form">
            <?= Csrf::field() ?>
            <input type="hidden" name="run_id" value="<?= (int) $run['id'] ?>">
            <input type="hidden" name="country" value="<?= e($run['country_code']) ?>">
            <input type="hidden" name="period_type" value="<?= e($run['period_type']) ?>">
            <input type="hidden" name="period_key" value="<?= e($run['period_key']) ?>">
            <?php if ($run['status'] === 'published'): ?>
                <div class="field"><label for="correction"><?= e(t('admin.correction_reason')) ?></label>
                <textarea id="correction" name="correction" required rows="2"></textarea>
                <p class="field__hint"><?= e(t('admin.correction_hint')) ?></p></div>
            <?php endif; ?>
            <button class="button button--small" type="submit"><?= e(t('admin.recompute_now')) ?></button>
        </form>
    </details>
</div>
<?php endif; ?>

<?php if ($flagged): ?>
<h2><?= e(t('admin.flagged_tracks')) ?></h2>
<p class="muted"><?= e(t('admin.flagged_intro')) ?></p>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th><?= e(t('admin.track')) ?></th><th class="num"><?= e(t('admin.score')) ?></th><th><?= e(t('admin.flags')) ?></th><th><?= e(t('admin.sources')) ?></th><th><?= e(t('admin.decision')) ?></th></tr></thead>
    <tbody>
    <?php foreach ($flagged as $f): $flags = json_decode($f['flags'], true) ?: []; ?>
        <tr>
            <td><a href="<?= path('titre/' . $f['slug']) ?>" target="_blank" rel="noopener"><?= e($f['title']) ?></a><br><small class="muted"><?= e($f['artist_name']) ?></small></td>
            <td class="num"><?= e(fmt_number((float) $f['score'])) ?></td>
            <td><?php foreach ($flags as $fl): ?><span class="flag<?= in_array($fl, $blocking, true) ? ' flag--blocking' : '' ?>" title="<?= e(t('flag.' . $fl)) ?>"><?= e($fl) ?></span><?php endforeach; ?>
                <br><span class="status status--<?= e($f['review_status']) ?>"><?= e(t('admin.review_' . $f['review_status'])) ?></span></td>
            <td><small><?= e($breakdown($f['breakdown'])) ?></small></td>
            <td>
                <?php if ($f['decision']): ?>
                    <strong><?= e(t('admin.review_' . $f['decision'])) ?></strong> <span class="muted">(<?= e((string) $f['decided_by']) ?>)</span><br><small><?= e($f['reason']) ?></small>
                <?php endif; ?>
                <?php if ($isAdmin && array_intersect($flags, $blocking)): ?>
                <form method="post" action="<?= path('admin/signalements') ?>" class="decision">
                    <?= Csrf::field() ?>
                    <input type="hidden" name="run_id" value="<?= (int) $run['id'] ?>">
                    <input type="hidden" name="track_id" value="<?= (int) $f['track_id'] ?>">
                    <input type="hidden" name="week_start" value="<?= e($f['week_start']) ?>">
                    <label class="visually-hidden" for="reason-<?= (int) $f['track_id'] ?>"><?= e(t('admin.reason')) ?></label>
                    <textarea id="reason-<?= (int) $f['track_id'] ?>" name="reason" rows="2" required placeholder="<?= e(t('admin.reason_placeholder')) ?>"></textarea>
                    <div class="decision__buttons">
                        <button class="button button--small" name="decision" value="validated" type="submit"><?= e(t('admin.validate')) ?></button>
                        <button class="button button--small button--danger" name="decision" value="excluded" type="submit"><?= e(t('admin.exclude')) ?></button>
                    </div>
                </form>
                <?php endif; ?>
            </td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<?php endif; ?>

<h2><?= e(t('admin.entries')) ?></h2>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th>#</th><th><?= e(t('admin.track')) ?></th><th class="num"><?= e(t('admin.score')) ?></th><th class="num"><?= e(t('admin.prev')) ?></th><th class="num"><?= e(t('chart.peak')) ?></th><th class="num"><?= e(t('chart.weeks')) ?></th><th class="num"><?= e(t('admin.sources')) ?></th><th><?= e(t('admin.flags')) ?></th></tr></thead>
    <tbody>
    <?php foreach ($entries as $e): $flags = json_decode((string) $e['flags'], true) ?: []; ?>
        <tr>
            <td><strong><?= (int) $e['position'] ?></strong></td>
            <td><?= e($e['track_id'] ? $e['title'] : $e['artist_name']) ?><?php if ($e['track_id']): ?><br><small class="muted"><?= e($e['artist_name']) ?></small><?php endif; ?>
                <?php if (is_group_label($e['label_owner'])): ?> <span class="badge"><?= e(\Cauri\Core\Config::get('app.group_label.name')) ?></span><?php endif; ?></td>
            <td class="num"><?= e(fmt_number((float) $e['score'])) ?><?= $e['growth_pct'] !== null ? '<br><small>+' . e(fmt_number((float) $e['growth_pct'])) . ' %</small>' : '' ?></td>
            <td class="num"><?= $e['previous_position'] ?? '—' ?></td>
            <td class="num"><?= (int) $e['peak_position'] ?></td>
            <td class="num"><?= (int) $e['weeks_on_chart'] ?></td>
            <td class="num"><?= (int) $e['sources_count'] ?></td>
            <td><?php foreach ($flags as $fl): ?><span class="flag<?= in_array($fl, $blocking, true) || $fl === 'pending_review' ? ' flag--blocking' : '' ?>" title="<?= e(t('flag.' . $fl)) ?>"><?= e($fl) ?></span><?php endforeach; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
