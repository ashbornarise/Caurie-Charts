<?php

/**
 * Actualités importées automatiquement depuis des médias musicaux (flux RSS publics).
 * On ne garde que le titre, un court résumé, une vignette et le lien vers l'article :
 * le lecteur lit l'article complet chez le média, qui est toujours cité.
 */
return [
    'feeds' => [
        ['name' => 'RFI Musique',       'url' => 'https://www.rfi.fr/fr/musique/rss',     'lang' => 'fr'],
        // Médias généralistes du divertissement : on ne garde que les articles qui parlent de musique
        ['name' => 'NotJustOk',         'url' => 'https://notjustok.com/category/news/feed/', 'lang' => 'en', 'music_only' => true],
        ['name' => 'AmeyawDebrah',      'url' => 'https://www.ameyawdebrah.com/feed/',        'lang' => 'en', 'music_only' => true],
    ],
    'per_feed'     => 10,   // articles lus par flux à chaque passage
    'max_age_days' => 21,   // on ignore les articles plus anciens
    'keep'         => 90,   // actualités importées conservées (les plus anciennes sont retirées avec leur vignette)
    'image'        => ['width' => 720, 'height' => 405, 'max_bytes' => 6_000_000],
];
