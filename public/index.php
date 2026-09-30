<?php

// Serveur intégré de PHP (php -S) : les fichiers statiques existants sont servis tels quels
if (PHP_SAPI === 'cli-server') {
    $file = __DIR__ . parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    if ($file !== __DIR__ . '/' && is_file($file)) {
        return false;
    }
}

require dirname(__DIR__) . '/src/bootstrap.php';

use Cauri\Controllers\Admin\AdminController;
use Cauri\Controllers\Admin\AuthController;
use Cauri\Controllers\Admin\CatalogAdminController;
use Cauri\Controllers\Admin\ChartAdminController;
use Cauri\Controllers\Admin\SubmissionAdminController;
use Cauri\Controllers\CatalogController;
use Cauri\Controllers\ChartController;
use Cauri\Controllers\PageController;
use Cauri\Controllers\SeoController;
use Cauri\Controllers\ShareController;
use Cauri\Controllers\SubmissionController;
use Cauri\Core\Config;
use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Core\Router;
use Cauri\Core\Session;
use Cauri\Core\View;
use Cauri\Services\Logger;

$request = Request::fromGlobals();
Session::resume($request->isHttps());

$r = new Router();

// Pages publiques
$r->get('/', [ChartController::class, 'home']);
// Classement régional des cinq pays
$r->get('/classements/afrique-de-l-ouest', [ChartController::class, 'regional']);
$r->get('/classements/afrique-de-l-ouest/{period:semaine|mois|annee}', [ChartController::class, 'regional']);
$r->get('/classements/afrique-de-l-ouest/{period:semaine|mois|annee}/{key:\d{4}(?:-W\d{2}|-\d{2})?}', [ChartController::class, 'regional']);
$r->get('/classements/{country:[a-z]{2}}/{chart:[a-z-]+}', [ChartController::class, 'show']);
$r->get('/classements/{country:[a-z]{2}}/{chart:[a-z-]+}/{period:semaine|mois|annee}', [ChartController::class, 'show']);
$r->get('/classements/{country:[a-z]{2}}/{chart:[a-z-]+}/{period:semaine|mois|annee}/{key:\d{4}(?:-W\d{2}|-\d{2})?}', [ChartController::class, 'show']);
$r->get('/artiste/{slug:[a-z0-9-]+}', [CatalogController::class, 'artist']);
$r->get('/titre/{slug:[a-z0-9-]+}', [CatalogController::class, 'track']);
$r->get('/methodologie', [PageController::class, 'methodology']);
$r->get('/a-propos', [PageController::class, 'about']);
$r->get('/contact', [PageController::class, 'contact']);
$r->post('/contact', [PageController::class, 'contactSend']);
$r->get('/declarer', [SubmissionController::class, 'form']);
$r->post('/declarer', [SubmissionController::class, 'store']);
foreach (['mentions-legales', 'confidentialite', 'cookies', 'conditions'] as $legalPage) {
    $r->get('/' . $legalPage, [PageController::class, 'legal']);
}
$r->get('/actualites', [\Cauri\Controllers\NewsController::class, 'index']);
$r->get('/actualites/{slug:[a-z0-9-]+}', [\Cauri\Controllers\NewsController::class, 'show']);
$r->get('/partenaires', [\Cauri\Controllers\PartnerController::class, 'index']);
$r->get('/langue/{locale:[a-z]{2}}', [PageController::class, 'setLocale']);
// Sans extension : fonctionne aussi avec "php -S ... -t public" sans script routeur
$r->get('/partage/{id:\d+}-{format:square|story}', [ShareController::class, 'image']);
$r->get('/robots.txt', [SeoController::class, 'robots']);
$r->get('/sitemap.xml', [SeoController::class, 'sitemap']);

// Administration
$r->get('/admin/connexion', [AuthController::class, 'loginForm']);
$r->post('/admin/connexion', [AuthController::class, 'login']);
$r->get('/admin/2fa', [AuthController::class, 'twoFactorForm']);
$r->post('/admin/2fa', [AuthController::class, 'twoFactor']);
$r->post('/admin/deconnexion', [AuthController::class, 'logout']);
$r->get('/admin', [AdminController::class, 'dashboard']);
$r->get('/admin/classements', [ChartAdminController::class, 'index']);
$r->get('/admin/classements/{id:\d+}', [ChartAdminController::class, 'show']);
$r->post('/admin/signalements', [ChartAdminController::class, 'decide']);
$r->post('/admin/publier', [ChartAdminController::class, 'publish']);
$r->post('/admin/recalculer', [ChartAdminController::class, 'recompute']);
$r->get('/admin/formule', [ChartAdminController::class, 'formula']);
$r->post('/admin/formule', [ChartAdminController::class, 'saveFormula']);
$r->get('/admin/declarations', [SubmissionAdminController::class, 'index']);
$r->get('/admin/declarations/{id:\d+}', [SubmissionAdminController::class, 'show']);
$r->post('/admin/declarations/{id:\d+}', [SubmissionAdminController::class, 'review']);
$r->get('/admin/declarations/{id:\d+}/capture', [SubmissionAdminController::class, 'screenshot']);
$r->get('/admin/releves', [SubmissionAdminController::class, 'snapshots']);
$r->post('/admin/releves', [SubmissionAdminController::class, 'saveSnapshot']);
$r->get('/admin/catalogue', [CatalogAdminController::class, 'index']);
$r->get('/admin/artistes/{id:\d+|nouveau}', [CatalogAdminController::class, 'artistForm']);
$r->post('/admin/artistes/{id:\d+|nouveau}', [CatalogAdminController::class, 'saveArtist']);
$r->get('/admin/titres/{id:\d+|nouveau}', [CatalogAdminController::class, 'trackForm']);
$r->post('/admin/titres/{id:\d+|nouveau}', [CatalogAdminController::class, 'saveTrack']);
$r->post('/admin/pays/{id:\d+}', [CatalogAdminController::class, 'saveCountry']);
$r->get('/admin/import', [\Cauri\Controllers\Admin\ImportAdminController::class, 'index']);
$r->post('/admin/import/lancer', [\Cauri\Controllers\Admin\ImportAdminController::class, 'run']);
$r->post('/admin/import/artiste/{id:\d+}', [\Cauri\Controllers\Admin\ImportAdminController::class, 'artist']);
$r->post('/admin/import/clip/{id:\d+}', [\Cauri\Controllers\Admin\ImportAdminController::class, 'clip']);
$r->post('/admin/import/clip-manuel/{id:\d+}', [\Cauri\Controllers\Admin\ImportAdminController::class, 'manualClip']);
$r->post('/admin/import/csv', [\Cauri\Controllers\Admin\ImportAdminController::class, 'csv']);
$r->get('/admin/actualites', [\Cauri\Controllers\Admin\NewsAdminController::class, 'index']);
$r->get('/admin/actualites/{id:\d+|nouveau}', [\Cauri\Controllers\Admin\NewsAdminController::class, 'form']);
$r->post('/admin/actualites/{id:\d+|nouveau}', [\Cauri\Controllers\Admin\NewsAdminController::class, 'save']);
// Posts réseaux sociaux et partenaires officiels
$r->get('/admin/posts', [\Cauri\Controllers\Admin\SocialAdminController::class, 'index']);
$r->post('/admin/posts/generer', [\Cauri\Controllers\Admin\SocialAdminController::class, 'generate']);
$r->post('/admin/posts/{id:\d+}', [\Cauri\Controllers\Admin\SocialAdminController::class, 'status']);
$r->get('/admin/partenaires', [\Cauri\Controllers\Admin\PartnerAdminController::class, 'index']);
$r->get('/admin/partenaires/{id:\d+|nouveau}', [\Cauri\Controllers\Admin\PartnerAdminController::class, 'form']);
$r->post('/admin/partenaires/{id:\d+|nouveau}', [\Cauri\Controllers\Admin\PartnerAdminController::class, 'save']);
$r->post('/admin/partenaires/{id:\d+}/supprimer', [\Cauri\Controllers\Admin\PartnerAdminController::class, 'delete']);
$r->get('/admin/journal', [AdminController::class, 'audit']);
$r->get('/admin/messages', [AdminController::class, 'messages']);
$r->post('/admin/messages/{id:\d+}', [AdminController::class, 'messageStatus']);

try {
    $response = $r->dispatch($request);
} catch (\Cauri\Controllers\Admin\RedirectException $e) {
    $response = Response::redirect($e->to);
} catch (HttpException $e) {
    $status = $e->status;
    $response = new Response(View::render('error', ['status' => $status, 'countries' => [], 'flash' => [], 'meta' => ['title' => t("error.$status") . ' · ' . brand(), 'description' => '', 'url' => url('/'), 'image' => '', 'type' => 'website']]), $status);
} catch (Throwable $e) {
    Logger::error('app', $e);
    $debug = Config::get('app.debug') ? $e->getMessage() . ' — ' . $e->getFile() . ':' . $e->getLine() : null;
    $response = new Response(View::render('error', ['status' => 500, 'debug' => $debug, 'countries' => [], 'flash' => [], 'meta' => ['title' => t('error.500'), 'description' => '', 'url' => url('/'), 'image' => '', 'type' => 'website']]), 500);
}

$response->send($request->isHttps());
