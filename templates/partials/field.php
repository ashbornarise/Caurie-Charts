<?php
/**
 * Champ de formulaire avec libellé et erreur.
 * @var string $name @var string $label @var array $old @var array $errors
 * @var string $type text|email|date|number|textarea|select @var array $options pour select
 */
$type ??= 'text';
$hint ??= null;
$required ??= true;
$attrs ??= '';
$value = $old[$name] ?? '';
$error = $errors[$name] ?? null;
$id = 'f-' . $name;
$describedBy = trim(($hint ? "$id-hint " : '') . ($error ? "$id-error" : ''));
?>
<div class="field<?= $error ? ' field--error' : '' ?>">
    <label for="<?= $id ?>"><?= e($label) ?><?= $required ? '' : ' <span class="optional">' . e(t('form.optional')) . '</span>' ?></label>
    <?php if ($hint): ?><p class="field__hint" id="<?= $id ?>-hint"><?= e($hint) ?></p><?php endif; ?>
    <?php if ($type === 'textarea'): ?>
        <textarea id="<?= $id ?>" name="<?= e($name) ?>" rows="5" <?= $required ? 'required' : '' ?> <?= $describedBy ? 'aria-describedby="' . $describedBy . '"' : '' ?> <?= $attrs ?>><?= e($value) ?></textarea>
    <?php elseif ($type === 'select'): ?>
        <select id="<?= $id ?>" name="<?= e($name) ?>" <?= $required ? 'required' : '' ?> <?= $describedBy ? 'aria-describedby="' . $describedBy . '"' : '' ?>>
            <option value=""><?= e(t('form.choose')) ?></option>
            <?php foreach ($options as $v => $l): ?>
                <option value="<?= e($v) ?>" <?= (string) $value === (string) $v ? 'selected' : '' ?>><?= e($l) ?></option>
            <?php endforeach; ?>
        </select>
    <?php else: ?>
        <input id="<?= $id ?>" type="<?= e($type) ?>" name="<?= e($name) ?>" value="<?= e($value) ?>" <?= $required ? 'required' : '' ?> <?= $describedBy ? 'aria-describedby="' . $describedBy . '"' : '' ?> <?= $attrs ?>>
    <?php endif; ?>
    <?php if ($error): ?><p class="field__error" id="<?= $id ?>-error"><?= e($error) ?></p><?php endif; ?>
</div>
