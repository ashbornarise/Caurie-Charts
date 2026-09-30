<?php /** @var int $status @var ?string $debug */ ?>
<section class="wrap prose error-page">
    <p class="error-page__code"><?= (int) $status ?></p>
    <h1><?= e(t("error.$status")) ?></h1>
    <p><?= e(t('error.text')) ?></p>
    <?php if (!empty($debug)): ?><pre class="debug"><?= e($debug) ?></pre><?php endif; ?>
    <p><a class="button" href="<?= path('/') ?>"><?= e(t('error.home')) ?></a></p>
</section>
