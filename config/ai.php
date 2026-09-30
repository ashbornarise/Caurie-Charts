<?php

/**
 * Automatisation par IA (API Claude, clé ANTHROPIC_API_KEY dans le fichier de secrets).
 * Sans clé, le classement des artistes utilise seulement MusicBrainz et les posts ne sont pas générés.
 */
return [
    'classify' => [
        'threshold'    => 0.85, // confiance minimale pour confirmer ou écarter un artiste sans humain
        'max_ai_calls' => 40,   // recherches IA par passage (les autres attendent le passage suivant)
    ],
    'social' => [
        // Trois posts par semaine : lundi, mercredi, vendredi (voir bin/generate-posts.php)
        'days'   => [1 => 'classement', 3 => 'artiste', 5 => 'weekend'],
        'handle' => '@cauricharts',
        // Vidéos : durée de chaque extrait de clip officiel (secondes) et point de départ dans le clip
        'clip_seconds' => 30,
        'clip_start'   => 30,
        'hashtags_base' => ['#CauriCharts', '#AfriqueDeLOuest'],
    ],
];
