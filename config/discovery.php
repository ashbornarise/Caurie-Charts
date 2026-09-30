<?php

/**
 * Découverte automatique des artistes de chaque pays (bin/discover-artists.php, chaque jour).
 * Sources gratuites : Wikidata (nationalité), réseau Deezer (artistes proches des artistes confirmés).
 * Un candidat n'entre au catalogue que si sa fanbase est suffisante ; il est ensuite vérifié (pays, scène)
 * et proposé dans /admin/import avec ses chiffres pour que l'équipe choisisse.
 */
return [
    // Élément Wikidata de chaque pays couvert
    'wikidata_countries' => ['TG' => 'Q945', 'BJ' => 'Q962', 'GH' => 'Q117', 'CI' => 'Q1008', 'SN' => 'Q1041'],
    'min_deezer_fans'       => 300,     // fanbase minimale sur Deezer…
    'min_youtube_subs'      => 5000,    // …ou sur YouTube
    'seeds_per_run'         => 25,      // artistes confirmés dont on explore le réseau Deezer à chaque passage
    'max_new_per_run'       => 200,     // nouveaux artistes ajoutés au plus par passage (partagés entre les cinq pays)
    'priority'              => ['TG', 'BJ'], // pays explorés en premier (moins couverts par les plateformes)
];
