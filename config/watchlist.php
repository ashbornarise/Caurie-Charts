<?php

/**
 * Artistes et chaînes suivis même s'ils n'apparaissent dans aucun classement de plateforme
 * (artistes locaux, artistes de la diaspora qui déclarent un autre pays sur les plateformes).
 * Lu chaque jour par bin/import-charts.php (bin/watch-artists.php pour le lancer seul).
 *
 * artists  : nom tel qu'il apparaît sur Deezer => pays pressenti (null si inconnu : il sera vérifié)
 * channels : chaînes YouTube de labels ou de médias musicaux => pays ; chaque nouveau clip
 *            « Artiste - Titre » ajoute l'artiste et le titre au catalogue
 */
return [
    'artists' => [
        'Paki Chenzu'   => 'TG',
        'Joachin Migos' => null,
        'Wantché'       => null,
        'døpelym'       => null,
    ],
    'channels' => [
        // 'UCxxxxxxxxxxxxxxxxxxxxxx' => 'TG',   // identifiant de chaîne (youtube.com/channel/UC...)
    ],
    // Recherche de chaînes par nom, faite une seule fois puis mémorisée (100 unités de quota chacune)
    'channel_names' => [
        'UNIVERSAL MUSIC TOGO' => 'TG',
    ],
];
