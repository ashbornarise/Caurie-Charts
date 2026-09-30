<?php
/** @var string $periodType @var array $periods @var callable $link fn(string $type): string */
?>
<nav class="tabs" aria-label="<?= e(t('period.choose')) ?>">
    <?php foreach ($periods as $p): ?>
        <a class="tabs__item" href="<?= $link($p) ?>" <?= $p === $periodType ? 'aria-current="page"' : '' ?>><?= e(t("period.$p")) ?></a>
    <?php endforeach; ?>
</nav>
