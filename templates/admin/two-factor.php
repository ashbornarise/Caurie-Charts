<?php use Cauri\Core\Csrf; /** @var ?string $error */ ?>
<section class="admin-form narrow">
    <h1><?= e(t('admin.2fa_title')) ?></h1>
    <p><?= e(t('admin.2fa_text')) ?></p>
    <?php if (!empty($error)): ?><p class="flash flash--error" role="alert"><?= e($error) ?></p><?php endif; ?>
    <form method="post" action="<?= path('admin/2fa') ?>">
        <?= Csrf::field() ?>
        <div class="field"><label for="code"><?= e(t('admin.2fa_code')) ?></label><input id="code" type="text" name="code" inputmode="numeric" pattern="[0-9 ]{6,7}" autocomplete="one-time-code" required autofocus></div>
        <button class="button" type="submit"><?= e(t('admin.2fa_verify')) ?></button>
    </form>
</section>
