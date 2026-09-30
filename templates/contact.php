<?php
/** @var array $old @var array $errors @var string $type */
use Cauri\Core\Csrf;
use Cauri\Core\View;

$f = fn (string $name, string $label, array $extra = []) => View::partial('partials/field', ['name' => $name, 'label' => $label, 'old' => $old, 'errors' => $errors] + $extra);
?>
<article class="prose">
    <h1><?= e(t('contact.title')) ?></h1>
    <p class="lead"><?= e($type === 'contestation' ? t('contact.contest_intro') : t('contact.intro')) ?></p>
    <form class="form" method="post" action="<?= path('contact') ?>" novalidate>
        <?= Csrf::field() ?>
        <div class="hp" aria-hidden="true"><label>Site web <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>
        <?= $f('type', t('contact.type'), ['type' => 'select', 'options' => ['contact' => t('contact.type_contact'), 'contestation' => t('contact.type_contest')], 'old' => $old + ['type' => $type]]) ?>
        <?= $f('name', t('form.name'), ['attrs' => 'autocomplete="name" maxlength="150"']) ?>
        <?= $f('email', t('form.email'), ['type' => 'email', 'attrs' => 'autocomplete="email" maxlength="190"']) ?>
        <?= $f('subject', t('contact.subject'), ['attrs' => 'maxlength="200"', 'hint' => $type === 'contestation' ? t('contact.contest_hint') : null]) ?>
        <?= $f('message', t('contact.message'), ['type' => 'textarea', 'attrs' => 'maxlength="5000"']) ?>
        <p class="fineprint"><?= e(t('contact.privacy')) ?> <a href="<?= path('confidentialite') ?>"><?= e(t('legal.confidentialite')) ?></a>.</p>
        <button class="button" type="submit"><?= e(t('form.send')) ?></button>
    </form>
</article>
