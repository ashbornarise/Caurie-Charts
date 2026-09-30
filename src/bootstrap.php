<?php

use Cauri\Core\Config;
use Cauri\Core\Env;
use Cauri\Core\Translator;
use Cauri\Core\View;

define('BASE_PATH', dirname(__DIR__));

// Autoload Composer s'il existe, sinon autoloader PSR-4 interne (aucune dépendance requise)
if (is_file(BASE_PATH . '/vendor/autoload.php')) {
    require BASE_PATH . '/vendor/autoload.php';
} else {
    spl_autoload_register(function (string $class): void {
        if (str_starts_with($class, 'Cauri\\')) {
            $file = BASE_PATH . '/src/' . str_replace('\\', '/', substr($class, 6)) . '.php';
            if (is_file($file)) {
                require $file;
            }
        }
    });
}

require_once BASE_PATH . '/src/helpers.php';

Env::load(BASE_PATH . '/.env');
// Clés d'API rangées hors du projet : leurs valeurs remplacent celles de .env
if (Env::get('SECRETS_FILE') !== '') {
    Env::load(Env::get('SECRETS_FILE'));
}
Config::init(BASE_PATH . '/config');
date_default_timezone_set((string) Config::get('app.timezone', 'UTC'));
Translator::init(BASE_PATH . '/lang', (string) Config::get('app.locale', 'fr'));
View::init(BASE_PATH . '/templates');

mb_internal_encoding('UTF-8');
