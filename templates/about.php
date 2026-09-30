<article class="prose">
    <p class="eyebrow"><?= e(t('about.eyebrow')) ?></p>
    <h1><?= e(t('about.title')) ?></h1>
    <p class="lead"><?= e(t('about.lead', ['brand' => brand()])) ?></p>
    <h2><?= e(t('about.name_title')) ?></h2>
    <p><?= e(t('about.name_text')) ?></p>
    <h2><?= e(t('about.countries_title')) ?></h2>
    <p><?= e(t('about.countries_text')) ?></p>
    <h2><?= e(t('about.group_title')) ?></h2>
    <p><?= e(t('about.group_text', ['brand' => brand(), 'label' => \Cauri\Core\Config::get('app.group_label.name')])) ?></p>
    <p><a class="button" href="<?= path('contact') ?>"><?= e(t('about.contact')) ?></a></p>
</article>
