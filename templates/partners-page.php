<?php
/** @var array $partners */
use Cauri\Core\View;
?>
<section class="prose">
    <p class="eyebrow"><?= e(brand()) ?></p>
    <h1><?= e(t('partners.title')) ?></h1>
</section>
<?= View::partial('partials/partners', ['partners' => $partners, 'compact' => false]) ?>
