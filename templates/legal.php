<?php
/** @var string $slug @var string $body @var array $pages */
use Cauri\Core\Config;
use Cauri\Core\Translator;
?>
<article class="prose legal">
    <p class="eyebrow"><?= e(t('legal.eyebrow')) ?></p>
    <h1><?= e(t('legal.' . $pages[$slug])) ?></h1>
    <p class="fineprint"><?= e(t('legal.updated', ['date' => fmt_date((string) Config::get('app.legal.updated'))])) ?></p>
    <?php if (Translator::locale() !== 'fr'): ?><p class="notice"><?= e(t('legal.french_only')) ?></p><?php endif; ?>
    <nav class="chips" aria-label="<?= e(t('legal.eyebrow')) ?>">
        <?php foreach ($pages as $s => $key): ?>
            <a class="chip" href="<?= path($s) ?>" <?= $s === $slug ? 'aria-current="page"' : '' ?>><?= e(t("legal.$key")) ?></a>
        <?php endforeach; ?>
    </nav>
    <?= $body ?>
</article>
