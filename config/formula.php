<?php

// Formule de départ (version 1). Les versions suivantes se créent dans l'admin
// (table formula_versions) avec une date d'entrée en vigueur.
// Valeurs à valider après quatre semaines de vraies données.

return [
    'version' => 1,

    // score_titre = somme sur les sources de (variation x poids_source)
    'weights' => [
        'audio'       => 1.0,  // streams audio (Audiomack, Boomplay, autres)
        'youtube'     => 0.5,  // vues des vidéos officielles
        'declaration' => 1.0,  // déclarations validées ET recoupées par une donnée publique
    ],

    // Poids par pays, qui remplacent les poids ci-dessus (ex. 'GH' => ['youtube' => 0.6])
    'country_weights' => [],

    // Méthodologie v1.2 : positions dans les classements des plateformes.
    // Chaque jour de présence rapporte (profondeur + 1 - position) points de position, moyennés sur
    // la semaine, puis multipliés par le poids. 0 = source inactive (c'est le cas en v1.1).
    'chart_depth'   => 100,
    'chart_weights' => [
        'apple_music' => 0,
        'audiomack'   => 0,
        'boomplay'    => 0,
    ],

    // Règle de diversité : Top N réservé aux titres présents sur au moins X sources.
    // S'il y a moins de N titres multi-sources, les places restantes vont aux titres
    // mono-source (signalés "diversity_fallback") : un Top 5 n'a jamais de trou.
    'diversity' => [
        'top'         => 5,
        'min_sources' => 2,
    ],

    'anti_fraud' => [
        'spike_factor'           => 5.0,   // variation > 5 x médiane des 4 dernières semaines
        'spike_history_weeks'    => 4,
        'spike_min_history'      => 2,     // en dessous, pas de contrôle de pic
        'declaration_tolerance'  => 0.30,  // écart max entre déclaration et donnée publique
        'youtube_min_views'      => 10000, // contrôle du ratio seulement au-delà
        'youtube_min_likes_per_1000' => 1.0,
        'youtube_max_likes_per_1000' => 250.0,
    ],

    'buzz' => [
        'min_growth_pct' => 50.0,
        'min_score'      => 2000.0,
    ],

    'fresh' => [
        'max_age_days' => 56, // 8 semaines
    ],
];
