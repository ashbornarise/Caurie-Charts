<?php
/** @var array $old @var array $errors @var array $platforms */
use Cauri\Core\Csrf;
use Cauri\Core\View;

$f = fn (string $name, string $label, array $extra = []) => View::partial('partials/field', ['name' => $name, 'label' => $label, 'old' => $old, 'errors' => $errors] + $extra);
$platformOptions = [];
foreach ($platforms as $p) {
    $platformOptions[$p] = platform_name($p);
}
?>
<article class="prose">
    <p class="eyebrow"><?= e(t('submit.eyebrow')) ?></p>
    <h1><?= e(t('submit.title')) ?></h1>
    <p class="lead"><?= e(t('submit.intro')) ?></p>
    <ol class="steps">
        <li><?= e(t('submit.step1')) ?></li>
        <li><?= e(t('submit.step2')) ?></li>
        <li><?= e(t('submit.step3')) ?></li>
    </ol>

    <form class="form" method="post" action="<?= path('declarer') ?>" enctype="multipart/form-data" novalidate>
        <?= Csrf::field() ?>
        <div class="hp" aria-hidden="true"><label>Site web <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>
        <fieldset>
            <legend><?= e(t('submit.section_track')) ?></legend>
            <?= $f('artist', t('submit.artist'), ['attrs' => 'maxlength="150"']) ?>
            <?= $f('track', t('submit.track'), ['attrs' => 'maxlength="200"']) ?>
        </fieldset>
        <fieldset>
            <legend><?= e(t('submit.section_data')) ?></legend>
            <?= $f('platform', t('submit.platform'), ['type' => 'select', 'options' => $platformOptions]) ?>
            <div class="field-row">
                <?= $f('period_start', t('submit.period_start'), ['type' => 'date', 'attrs' => 'max="' . date('Y-m-d') . '"']) ?>
                <?= $f('period_end', t('submit.period_end'), ['type' => 'date', 'attrs' => 'max="' . date('Y-m-d') . '"']) ?>
            </div>
            <?= $f('streams', t('submit.streams'), ['type' => 'number', 'attrs' => 'min="1" step="1" inputmode="numeric"']) ?>
            <?= $f('breakdown', t('submit.breakdown'), ['required' => false, 'hint' => t('submit.breakdown_hint')]) ?>
            <div class="field<?= isset($errors['screenshot']) ? ' field--error' : '' ?>">
                <label for="f-screenshot"><?= e(t('submit.screenshot')) ?></label>
                <p class="field__hint" id="f-screenshot-hint"><?= e(t('submit.screenshot_hint')) ?></p>
                <input id="f-screenshot" type="file" name="screenshot" accept="image/png,image/jpeg,image/webp" required aria-describedby="f-screenshot-hint">
                <?php if (isset($errors['screenshot'])): ?><p class="field__error"><?= e($errors['screenshot']) ?></p><?php endif; ?>
            </div>
        </fieldset>
        <fieldset>
            <legend><?= e(t('submit.section_contact')) ?></legend>
            <?= $f('contact_name', t('form.name'), ['attrs' => 'autocomplete="name" maxlength="150"']) ?>
            <?= $f('email', t('form.email'), ['type' => 'email', 'attrs' => 'autocomplete="email" maxlength="190"']) ?>
        </fieldset>
        <div class="field<?= isset($errors['consent']) ? ' field--error' : '' ?>">
            <label class="check"><input type="checkbox" name="consent" value="1" required> <span><?= e(t('submit.consent')) ?> <a href="<?= path('confidentialite') ?>" target="_blank"><?= e(t('legal.confidentialite')) ?></a>, <a href="<?= path('conditions') ?>" target="_blank"><?= e(t('legal.conditions')) ?></a>.</span></label>
            <?php if (isset($errors['consent'])): ?><p class="field__error"><?= e($errors['consent']) ?></p><?php endif; ?>
        </div>
        <button class="button" type="submit"><?= e(t('submit.send')) ?></button>
    </form>
</article>
