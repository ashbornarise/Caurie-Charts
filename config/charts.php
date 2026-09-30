<?php

// Famille de classements. Les noms sont provisoires (voir METHODOLOGIE.md, section 5).
// Ne jamais utiliser "Hot 100", "Billboard 200", "Artist 100" ni le mot "Billboard".
//
// public    : affiché sur le site
// computed  : calculé par bin/compute-weekly.php
// kind      : tracks (titres) ou artists (artistes)
// size      : null = taille du pays (countries.chart_size)

return [
    'prime' => [
        'name'     => 'Prime Chart',
        'kind'     => 'tracks',
        'public'   => true,
        'computed' => true,
        'size'     => null,
        'periods'  => ['week', 'month', 'year'],
    ],
    'buzz' => [
        'name'     => 'Buzz Chart',
        'kind'     => 'tracks',
        'public'   => true,
        'computed' => true,
        'size'     => 10,
        'periods'  => ['week'],
    ],
    'fresh' => [
        'name'     => 'Fresh Chart',
        'kind'     => 'tracks',
        'public'   => true,
        'computed' => true,
        'size'     => 10,
        'periods'  => ['week'],
    ],
    'icon' => [
        'name'     => 'Icon Chart',
        'kind'     => 'artists',
        'public'   => true,
        'computed' => true,
        'size'     => 10,
        'periods'  => ['week'],
    ],
    // Ouvert dès le premier jour, vide au départ : cumul depuis le lancement
    'legend' => [
        'name'     => 'Legend Chart',
        'kind'     => 'tracks',
        'public'   => true,
        'computed' => true,
        'size'     => null,
        'periods'  => ['week'],
    ],
    // Phase 2/3 : structure prête, non affichée
    'vintage' => [
        'name'     => 'Vintage Chart',
        'kind'     => 'tracks',
        'public'   => false,
        'computed' => false,
        'size'     => null,
        'periods'  => ['year'],
    ],
    // Classement total des cinq pays, affiché en page d'accueil : tous les titres classés par leur score
    // de la semaine (le même que les classements nationaux), à partir des semaines nationales publiées.
    'prime-wa' => [
        'name'       => "Prime Chart Afrique de l'Ouest",
        'kind'       => 'tracks',
        'public'     => true,
        'computed'   => true,
        'size'       => 20,
        'periods'    => ['week', 'month', 'year'],
        'regional'   => true,
    ],
];
