<?php

use Cauri\Core\Env;

return [
    'name'          => Env::get('APP_NAME', 'Cauri Charts'),
    'url'           => rtrim(Env::get('APP_URL', 'http://localhost:8000'), '/'),
    'env'           => Env::get('APP_ENV', 'production'),
    'debug'         => Env::bool('APP_DEBUG', false),
    'locale'        => Env::get('APP_LOCALE', 'fr'),
    'locales'       => ['fr', 'en'],
    'timezone'      => Env::get('APP_TIMEZONE', 'Africa/Lome'),
    'key'           => Env::get('APP_KEY', ''),
    'contact_email' => Env::get('CONTACT_EMAIL', ''),
    'pilot_country' => strtoupper(Env::get('PILOT_COUNTRY', 'TG')),

    // Version de la méthodologie publique (METHODOLOGIE.md), enregistrée avec chaque calcul
    'methodology_version' => '1.1',

    // Label rattaché au même groupe : ses artistes portent un badge
    'group_label' => [
        'code' => 'novaluz',
        'name' => 'Nova Luz',
    ],

    'db' => [
        'host' => Env::get('DB_HOST', '127.0.0.1'),
        'port' => (int) Env::get('DB_PORT', '3306'),
        'name' => Env::get('DB_NAME', 'cauricharts'),
        'user' => Env::get('DB_USER', 'root'),
        'pass' => Env::get('DB_PASS', ''),
    ],

    'security' => [
        'login_max_attempts'   => 5,
        'login_window_minutes' => 15,
        'session_lifetime'     => 7200,
        'upload_max_bytes'     => 5 * 1024 * 1024,
    ],

    // Mentions légales : à compléter dans .env dès que la structure juridique existe.
    // Une valeur vide s'affiche "[à compléter]" sur le site.
    'legal' => [
        'publisher'     => Env::get('LEGAL_PUBLISHER', ''),     // nom de la structure éditrice
        'status'        => Env::get('LEGAL_STATUS', ''),        // forme juridique, capital
        'registration'  => Env::get('LEGAL_REGISTRATION', ''),  // RCCM / SIREN / n° d'association
        'address'       => Env::get('LEGAL_ADDRESS', ''),
        'director'      => Env::get('LEGAL_DIRECTOR', ''),      // directeur de la publication
        'privacy_email' => Env::get('PRIVACY_EMAIL', Env::get('CONTACT_EMAIL', '')),
        'host_name'     => Env::get('HOST_NAME', 'o2switch'),
        'host_address'  => Env::get('HOST_ADDRESS', ''),
        'host_contact'  => Env::get('HOST_CONTACT', 'https://www.o2switch.fr'),
        'updated'       => '2026-09-29',
    ],

    // Outils soumis au consentement. Identifiant vide = outil désactivé (et pas de bandeau
    // s'il n'y a plus rien à demander). Rien n'est chargé avant l'accord du visiteur.
    'tracking' => [
        'ga_id'          => Env::get('GA_MEASUREMENT_ID', ''), // Google Analytics 4 : G-XXXXXXXXXX
        'meta_pixel_id'  => Env::get('META_PIXEL_ID', ''),     // Meta Pixel : identifiant numérique
        'youtube_embeds' => Env::bool('YOUTUBE_EMBEDS', true), // clips intégrés (youtube-nocookie, au clic)
        'spotify_playlist' => Env::get('SPOTIFY_PLAYLIST_ID', ''), // lecteur Spotify de la playlist, au clic (sans clé d'API)
        'consent_months' => 6,                                  // durée de validité du choix
    ],

    // Durées de conservation des données personnelles (en mois), appliquées par bin/purge.php
    'retention' => [
        'login_attempts'     => 6,
        'audit_ip'           => 12,
        'screenshots'        => 12, // après traitement de la déclaration
        'submission_contact' => 24, // nom et e-mail du déclarant
        'contact_messages'   => 24, // messages clos ou répondus
    ],

    'share' => [
        'font_serif' => Env::get('SHARE_FONT_SERIF', ''),
        'font_sans'  => Env::get('SHARE_FONT_SANS', ''),
    ],
];
