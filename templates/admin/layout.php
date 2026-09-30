<?php
/** @var string $content @var ?array $user @var array $flash @var string $title */
use Cauri\Core\Csrf;

$current = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$nav = [
    'admin'              => t('admin.nav_dashboard'),
    'admin/classements'  => t('admin.nav_charts'),
    'admin/declarations' => t('admin.nav_submissions'),
    'admin/import'       => t('admin.nav_import'),
    'admin/releves'      => t('admin.nav_snapshots'),
    'admin/catalogue'    => t('admin.nav_catalog'),
    'admin/actualites'   => t('admin.nav_news'),
    'admin/posts'        => t('admin.nav_posts'),
    'admin/partenaires'  => t('admin.nav_partners'),
    'admin/messages'     => t('admin.nav_messages'),
];
if ($user && $user['role'] === 'admin') {
    $nav['admin/formule'] = t('admin.nav_formula');
    $nav['admin/journal'] = t('admin.nav_audit');
}
?>
<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex, nofollow">
    <title><?= e($title) ?> · <?= e(brand()) ?></title>
    <link rel="icon" href="<?= asset('img/brand/monogram.svg') ?>" type="image/svg+xml">
    <link rel="stylesheet" href="<?= asset('css/app.css') ?>">
    <link rel="stylesheet" href="<?= asset('css/admin.css') ?>">
</head>
<body class="admin">
<header class="site-header">
    <div class="wrap wrap--wide site-header__inner">
        <a class="brand" href="<?= path('admin') ?>">
            <img src="<?= asset('img/brand/monogram.svg') ?>" alt="" width="32" height="32">
            <span class="brand__name"><?= e(brand()) ?> <small class="admin-tag"><?= e(t('admin.title')) ?></small></span>
        </a>
        <?php if ($user): ?>
        <nav class="site-nav" aria-label="<?= e(t('admin.title')) ?>">
            <?php foreach ($nav as $href => $label): ?>
                <a href="<?= path($href) ?>" <?= ($current === '/' . $href || ($href !== 'admin' && str_starts_with($current, '/' . $href))) ? 'aria-current="page"' : '' ?>><?= e($label) ?></a>
            <?php endforeach; ?>
            <a href="<?= path('/') ?>" target="_blank" rel="noopener"><?= e(t('admin.view_site')) ?></a>
            <form method="post" action="<?= path('admin/deconnexion') ?>" class="inline">
                <?= Csrf::field() ?>
                <button class="button button--small button--ghost" type="submit"><?= e(t('admin.logout')) ?> (<?= e($user['name']) ?>)</button>
            </form>
        </nav>
        <?php endif; ?>
    </div>
</header>
<main class="wrap wrap--wide admin-main">
    <?php foreach ($flash as $f): ?>
        <p class="flash flash--<?= e($f['type']) ?>" role="status"><?= e($f['message']) ?></p>
    <?php endforeach; ?>
    <?php if ($user && !$user['has_2fa']): ?>
        <p class="notice"><?= e(t('admin.2fa_advice')) ?></p>
    <?php endif; ?>
    <?= $content ?>
</main>
<script src="<?= asset('js/admin.js') ?>" defer></script>
</body>
</html>
