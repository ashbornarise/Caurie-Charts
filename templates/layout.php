<?php
/** @var string $content @var array $meta @var array $countries @var array $flash */
use Cauri\Core\Config;
use Cauri\Core\Translator;

$pilot = strtolower((string) Config::get('app.pilot_country'));
$current = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$otherLocale = Translator::locale() === 'fr' ? 'en' : 'fr';
$tracking = Config::get('app.tracking');
$askConsent = $tracking['ga_id'] !== '' || $tracking['meta_pixel_id'] !== '';
?>
<!doctype html>
<html lang="<?= e(Translator::locale()) ?>">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= e($meta['title']) ?></title>
    <meta name="description" content="<?= e($meta['description']) ?>">
    <link rel="canonical" href="<?= e($meta['url']) ?>">
    <meta property="og:site_name" content="<?= e(brand()) ?>">
    <meta property="og:title" content="<?= e($meta['title']) ?>">
    <meta property="og:description" content="<?= e($meta['description']) ?>">
    <meta property="og:type" content="<?= e($meta['type']) ?>">
    <meta property="og:url" content="<?= e($meta['url']) ?>">
    <?php if (!empty($meta['image'])): ?>
    <meta property="og:image" content="<?= e($meta['image']) ?>">
    <meta name="twitter:image" content="<?= e($meta['image']) ?>">
    <?php endif; ?>
    <meta property="og:locale" content="<?= Translator::locale() === 'fr' ? 'fr_FR' : 'en_GB' ?>">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="theme-color" content="#111111">
    <link rel="icon" href="<?= asset('img/brand/monogram.svg') ?>" type="image/svg+xml">
    <link rel="icon" href="<?= asset('img/brand/favicon-32.png') ?>" type="image/png" sizes="32x32">
    <link rel="apple-touch-icon" href="<?= asset('img/brand/apple-touch-icon.png') ?>">
    <link rel="stylesheet" href="<?= asset('css/app.css') ?>">
</head>
<body data-ga="<?= e($tracking['ga_id']) ?>" data-pixel="<?= e($tracking['meta_pixel_id']) ?>" data-consent-months="<?= (int) $tracking['consent_months'] ?>">
<a class="skip" href="#contenu"><?= e(t('nav.skip')) ?></a>

<header class="site-header">
    <div class="wrap site-header__inner">
        <a class="brand" href="<?= path('/') ?>" aria-label="<?= e(brand()) ?>">
            <!-- Logo : public/assets/img/brand/logo.svg (généré par bin/build-brand-assets.php) -->
            <img class="brand__logo" src="<?= asset('img/brand/logo.svg') ?>" alt="<?= e(brand()) ?>" width="100" height="44">
        </a>
        <nav class="site-nav" aria-label="<?= e(t('nav.main')) ?>">
            <a href="<?= chart_path('WA', 'prime-wa') ?>" <?= str_starts_with($current, '/classements') ? 'aria-current="page"' : '' ?>><?= e(t('nav.charts')) ?></a>
            <a href="<?= path('methodologie') ?>" <?= $current === '/methodologie' ? 'aria-current="page"' : '' ?>><?= e(t('nav.methodology')) ?></a>
            <a href="<?= path('a-propos') ?>" <?= $current === '/a-propos' ? 'aria-current="page"' : '' ?>><?= e(t('nav.about')) ?></a>
            <a class="site-nav__cta" href="<?= path('declarer') ?>"><?= e(t('nav.submit')) ?></a>
        </nav>
    </div>
</header>

<main id="contenu">
    <?php foreach ($flash as $f): ?>
        <div class="wrap"><p class="flash flash--<?= e($f['type']) ?>" role="status"><?= e($f['message']) ?></p></div>
    <?php endforeach; ?>
    <?php if (!empty($asideWrap)): ?>
        <div class="wrap page-grid">
            <div class="page-main"><?= $content ?></div>
            <?= \Cauri\Core\View::partial('partials/aside', ['aside' => $aside]) ?>
        </div>
    <?php else: ?>
        <?= $content ?>
    <?php endif; ?>
</main>

<footer class="site-footer">
    <div class="wrap">
        <img class="site-footer__logo" src="<?= asset('img/brand/logo.svg') ?>" alt="<?= e(brand()) ?>" width="120" height="53" loading="lazy">
        <?php if ($countries): ?>
        <nav class="country-picker" aria-label="<?= e(t('nav.countries')) ?>">
            <h2 class="country-picker__title"><?= e(t('footer.countries')) ?></h2>
            <ul>
                <?php foreach ($countries as $c): ?>
                <li><a href="<?= chart_path($c['code'], 'prime') ?>"><?= flag($c['code'], 16) ?> <?= e(country_name($c['code'])) ?></a></li>
                <?php endforeach; ?>
            </ul>
        </nav>
        <?php endif; ?>
        <div class="site-footer__cols">
            <p class="site-footer__about"><?= e(t('footer.about', ['brand' => brand()])) ?></p>
            <ul class="site-footer__links">
                <li><a href="<?= path('methodologie') ?>"><?= e(t('nav.methodology')) ?></a></li>
                <li><a href="<?= path('a-propos') ?>"><?= e(t('nav.about')) ?></a></li>
                <li><a href="<?= path('contact') ?>"><?= e(t('nav.contact')) ?></a></li>
                <li><a href="<?= path('declarer') ?>"><?= e(t('nav.submit')) ?></a></li>
                <li><a href="<?= path('langue/' . $otherLocale, ['retour' => $current]) ?>" hreflang="<?= $otherLocale ?>"><?= e(t('footer.switch_locale')) ?></a></li>
            </ul>
        </div>
        <ul class="site-footer__links site-footer__links--legal">
            <li><a href="<?= path('mentions-legales') ?>"><?= e(t('legal.mentions')) ?></a></li>
            <li><a href="<?= path('confidentialite') ?>"><?= e(t('legal.confidentialite')) ?></a></li>
            <li><a href="<?= path('cookies') ?>"><?= e(t('legal.cookies')) ?></a></li>
            <li><a href="<?= path('conditions') ?>"><?= e(t('legal.conditions')) ?></a></li>
            <?php if ($askConsent): ?><li><a href="<?= path('cookies') ?>" data-consent-open><?= e(t('consent.manage')) ?></a></li><?php endif; ?>
        </ul>
        <p class="site-footer__legal">&copy; <?= date('Y') ?> <?= e(brand()) ?>. <?= e(t('footer.legal')) ?> <?= e(t('footer.no_tracking')) ?></p>
    </div>
</footer>
<?php if ($askConsent): ?><?= \Cauri\Core\View::partial('partials/consent') ?><?php endif; ?>
<script src="<?= asset('js/consent.js') ?>" defer></script>
</body>
</html>
