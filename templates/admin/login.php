<?php use Cauri\Core\Csrf; /** @var ?string $error @var ?string $email */ ?>
<section class="admin-form narrow">
    <h1><?= e(t('admin.login')) ?></h1>
    <?php if (!empty($error)): ?><p class="flash flash--error" role="alert"><?= e($error) ?></p><?php endif; ?>
    <form method="post" action="<?= path('admin/connexion') ?>">
        <?= Csrf::field() ?>
        <div class="field"><label for="email"><?= e(t('form.email')) ?></label><input id="email" type="email" name="email" value="<?= e($email ?? '') ?>" autocomplete="username" required autofocus></div>
        <div class="field"><label for="password"><?= e(t('admin.password')) ?></label><input id="password" type="password" name="password" autocomplete="current-password" required></div>
        <button class="button" type="submit"><?= e(t('admin.login_button')) ?></button>
    </form>
</section>
