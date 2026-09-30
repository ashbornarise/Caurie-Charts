<?php
/** @var array $versions @var array $current @var array $countries @var string $minDate */
use Cauri\Core\Csrf;

$nextMonday = date('Y-m-d', strtotime('next monday', strtotime($minDate . ' -1 day')));
?>
<h1><?= e(t('admin.nav_formula')) ?></h1>
<p class="muted"><?= e(t('admin.formula_intro')) ?></p>

<h2><?= e(t('admin.formula_versions')) ?></h2>
<div class="table-scroll">
<table class="data-table">
    <thead><tr><th>v</th><th><?= e(t('admin.effective_from')) ?></th><th><?= e(t('admin.weights')) ?></th><th><?= e(t('admin.note')) ?></th><th><?= e(t('admin.author')) ?></th></tr></thead>
    <tbody>
    <?php foreach ($versions as $v): $f = json_decode($v['formula_json'], true); ?>
        <tr>
            <td><strong><?= (int) $v['version'] ?></strong><?= (int) $v['version'] === (int) $current['version'] ? ' <span class="status status--published">' . e(t('admin.in_force')) . '</span>' : '' ?></td>
            <td><?= e(fmt_date($v['effective_from'])) ?></td>
            <td><small>audio <?= e((string) $f['weights']['audio']) ?> · youtube <?= e((string) $f['weights']['youtube']) ?> · décl. <?= e((string) $f['weights']['declaration']) ?><?= !empty($f['country_weights']) ? '<br>' . e(json_encode($f['country_weights'])) : '' ?></small></td>
            <td><?= e((string) $v['note']) ?></td>
            <td><?= e((string) ($v['author'] ?? '—')) ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>

<h2><?= e(t('admin.formula_new')) ?></h2>
<form method="post" action="<?= path('admin/formule') ?>" class="admin-form box">
    <?= Csrf::field() ?>
    <div class="field-row">
        <div class="field"><label for="w_audio"><?= e(t('methodology.w_audio')) ?></label><input id="w_audio" name="w_audio" inputmode="decimal" value="<?= e((string) $current['weights']['audio']) ?>" required></div>
        <div class="field"><label for="w_youtube"><?= e(t('methodology.w_youtube')) ?></label><input id="w_youtube" name="w_youtube" inputmode="decimal" value="<?= e((string) $current['weights']['youtube']) ?>" required></div>
        <div class="field"><label for="w_declaration"><?= e(t('methodology.w_declaration')) ?></label><input id="w_declaration" name="w_declaration" inputmode="decimal" value="<?= e((string) $current['weights']['declaration']) ?>" required></div>
    </div>
    <fieldset>
        <legend><?= e(t('admin.country_weights')) ?></legend>
        <p class="field__hint"><?= e(t('admin.country_weights_hint')) ?></p>
        <?php foreach ($countries as $c): ?>
        <div class="field-row">
            <div class="field"><label for="cw_<?= e($c['code']) ?>_audio"><?= e($c['code']) ?> · audio</label><input id="cw_<?= e($c['code']) ?>_audio" name="cw_<?= e($c['code']) ?>_audio" inputmode="decimal" value="<?= e((string) ($current['country_weights'][$c['code']]['audio'] ?? '')) ?>"></div>
            <div class="field"><label for="cw_<?= e($c['code']) ?>_youtube"><?= e($c['code']) ?> · youtube</label><input id="cw_<?= e($c['code']) ?>_youtube" name="cw_<?= e($c['code']) ?>_youtube" inputmode="decimal" value="<?= e((string) ($current['country_weights'][$c['code']]['youtube'] ?? '')) ?>"></div>
        </div>
        <?php endforeach; ?>
    </fieldset>
    <div class="field-row">
        <div class="field"><label for="spike_factor"><?= e(t('admin.spike_factor')) ?></label><input id="spike_factor" name="spike_factor" inputmode="decimal" value="<?= e((string) $current['anti_fraud']['spike_factor']) ?>" required></div>
        <div class="field"><label for="declaration_tolerance"><?= e(t('admin.declaration_tolerance')) ?></label><input id="declaration_tolerance" name="declaration_tolerance" inputmode="decimal" value="<?= e((string) $current['anti_fraud']['declaration_tolerance']) ?>" required></div>
    </div>
    <div class="field"><label for="effective_from"><?= e(t('admin.effective_from')) ?></label>
        <input id="effective_from" type="date" name="effective_from" min="<?= e($minDate) ?>" value="<?= e($nextMonday) ?>" required>
        <p class="field__hint"><?= e(t('admin.formula_date_rule')) ?></p></div>
    <div class="field"><label for="note"><?= e(t('admin.note')) ?></label><textarea id="note" name="note" rows="2" required></textarea></div>
    <button class="button" type="submit"><?= e(t('admin.formula_create')) ?></button>
</form>
