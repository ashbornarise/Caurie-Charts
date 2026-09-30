<?php

/**
 * Génère database/seed.sql : données d'exemple FICTIVES et déterministes.
 * Aucun nom d'artiste ou de titre ne désigne une personne réelle.
 *
 * Usage : php bin/generate-seed.php
 */

require dirname(__DIR__) . '/src/bootstrap.php';

mt_srand(228);

const SEED_FROM = '2026-07-26'; // dimanche : point de départ des compteurs
const SEED_TO   = '2026-09-28'; // lundi : dernier relevé

$countries = [
    // id, code, fr, en, locale, taille, plateformes, pilote, ordre
    [1, 'TG', 'Togo', 'Togo', 'fr', 20, 'youtube,audiomack,boomplay', 1, 1],
    [2, 'BJ', 'Bénin', 'Benin', 'fr', 10, 'youtube,audiomack,boomplay', 0, 2],
    [3, 'GH', 'Ghana', 'Ghana', 'en', 10, 'youtube,audiomack,boomplay', 0, 3],
    [4, 'CI', "Côte d'Ivoire", "Côte d'Ivoire", 'fr', 10, 'youtube,audiomack,boomplay', 0, 4],
    [5, 'SN', 'Sénégal', 'Senegal', 'fr', 10, 'youtube,audiomack,boomplay', 0, 5],
];

// Artistes fictifs par pays. "*" = artiste du label du groupe (badge), "+" = émergent
$artistsByCountry = [
    'TG' => ['Kodjo Lumière', 'Afi Sena', '*Sika Nova', 'Yawa Blaze', 'Elom 228', 'Dzigbe', 'Mawuli K', '*Edem Waves',
             'Kossi Flow', 'Ablavi', '+Lady Kpémé', 'Agbodeka Sound', 'Nyuiemedi', '+Senam Joy', 'Komla Vibes', 'Akpé Crew'],
    'BJ' => ['Houénou Star', 'Fifamè', 'Dossou Beats', 'Ayaba Queen', 'Tchégoun', '+Mahougnon', 'Sèdjro Kay', 'Kpanlingan'],
    'GH' => ['Kwaku Solar', 'Ama Vibes', 'Yaw Horizon', 'Esi Gold', 'Kofi Tempo', '+Abena Ray', 'Nana Drift', 'Kwesi Low'],
    'CI' => ['Awa Désir', 'Bamba Joy', 'Yao Kanté', 'Aya Lumen', 'Djédjé Flow', '+Konan Bleu', 'Fanta Rythme', 'Gbê Système'],
    'SN' => ['Mbaye Sabar', 'Aminata Soul', 'Ndiaga Wave', 'Fatou Lune', 'Cheikh Beat', '+Khady Rose', 'Moussa Teranga', 'Baye Horizon'],
];

$titleWords = [
    'fr' => ['Lumière', 'Ma Reine', 'Allô Allô', 'Cauri d\'Or', 'Soleil de Lomé', 'Dis-moi', 'On danse', 'Mama Africa', 'Nuit Blanche',
             'Doucement', 'Vrai Gars', 'Kpakpato', 'Akpé', 'Wézon', 'Tout Pour Toi', 'La Vie Est Belle', 'Coeur d\'Or', 'Zéro Stress',
             'Ça va aller', 'Fête au Village', 'Grand Frère', 'Jolie Fleur', 'Sans Toi', 'Moto Taxi', 'Élégance', 'Petit à Petit',
             'Plage de Ouidah', 'Mawu Nyo', 'Sikaa', 'Bonne Arrivée', 'Mon Bébé', 'Ma Chérie', 'Wahala Non', 'Ambiance', 'Tchoko Tchoko',
             'Dakar by Night', 'Teranga', 'Abidjan Mood', 'Koumassi', 'Yamoussoukro', 'Garba Time', 'Zouglou Love', 'Sabar Fever'],
    'en' => ['Golden Hour', 'Accra Nights', 'Sweet Mother', 'Blessings', 'No Wahala', 'Highlife Dreams', 'Shine', 'Odo', 'Medaase',
             'Kpanlogo Groove', 'Come Closer', 'Hustle', 'Sunday Service', 'On God', 'Chale Wote'],
];

$sql = [];
$sql[] = "-- Cauri Charts : données d'exemple FICTIVES (générées par bin/generate-seed.php, ne pas éditer à la main)";
$sql[] = "-- Période couverte : relevés quotidiens du " . SEED_FROM . " au " . SEED_TO;
$sql[] = 'SET NAMES utf8mb4;';
$sql[] = 'SET FOREIGN_KEY_CHECKS = 0;';
$sql[] = '';

$q = fn ($v) => $v === null ? 'NULL' : (is_int($v) || is_float($v) ? (string) $v : "'" . str_replace(["\\", "'"], ["\\\\", "''"], (string) $v) . "'");
$rows = fn (array $list) => implode(",\n", array_map(fn ($r) => '(' . implode(', ', array_map($q, $r)) . ')', $list));

// Pays
$sql[] = "INSERT INTO countries (id, code, name_fr, name_en, locale, chart_size, platforms, is_pilot, sort_order) VALUES\n"
    . $rows(array_map(fn ($c) => [$c[0], $c[1], $c[2], $c[3], $c[4], $c[5], $c[6], $c[7], $c[8]], $countries)) . ';';

// Types de classements
$chartTypes = [];
$i = 0;
foreach (require BASE_PATH . '/config/charts.php' as $code => $c) {
    $i++;
    $chartTypes[] = [$i, $code, $c['name'], $c['kind'], (int) $c['public'], (int) $c['computed'], (int) !empty($c['regional']), $i];
}
$sql[] = "INSERT INTO chart_types (id, code, name, kind, is_public, is_computed, is_regional, sort_order) VALUES\n" . $rows($chartTypes) . ';';

// Formule v1
$formula = require BASE_PATH . '/config/formula.php';
// v1.2 : positions dans les classements des plateformes, annoncée plus de deux semaines à l'avance
$formulaV2 = $formula;
$formulaV2['version'] = 2;
$formulaV2['chart_weights'] = ['apple_music' => 150, 'audiomack' => 150, 'boomplay' => 150];
$sql[] = "INSERT INTO formula_versions (version, formula_json, effective_from, note) VALUES\n" . $rows([
    [1, json_encode($formula, JSON_UNESCAPED_UNICODE), '2026-01-01', 'Formule de départ (METHODOLOGIE.md v1.1)'],
    [2, json_encode($formulaV2, JSON_UNESCAPED_UNICODE), '2026-10-12', 'Méthodologie v1.2 : les positions dans les classements Apple Music, Audiomack et Boomplay rapportent des points (150 par point de position, à valider après quatre semaines).'],
]) . ';';

// Données de référence réelles : fichier à part, seul importé par défaut à l'installation
$sql[0] = "-- Cauri Charts : données de référence RÉELLES (pays, classements, versions de la formule).";
$sql[1] = "-- Aucune donnée d'artiste : le catalogue vient des imports et des déclarations. Généré par bin/generate-seed.php.";
file_put_contents(BASE_PATH . '/database/reference.sql', implode("\n", $sql) . "\nSET FOREIGN_KEY_CHECKS = 1;\n");
$sql = [
    "-- Cauri Charts : données d'exemple FICTIVES, développement uniquement (générées par bin/generate-seed.php, ne pas éditer à la main)",
    "-- À importer après reference.sql. Période couverte : relevés quotidiens du " . SEED_FROM . " au " . SEED_TO,
    'SET NAMES utf8mb4;',
    'SET FOREIGN_KEY_CHECKS = 0;',
    '',
];

// Artistes et titres
$countryIds = array_column($countries, 0, 1);
$artists = [];
$tracks = [];
$tpis = [];
$usedTitles = [];
$aid = 0;
$tid = 0;
$pid = 0;

foreach ($artistsByCountry as $code => $names) {
    $locale = $code === 'GH' ? 'en' : 'fr';
    $countryArtists = [];
    foreach ($names as $raw) {
        $aid++;
        $label = str_starts_with($raw, '*') ? 'novaluz' : null;
        $emerging = str_starts_with($raw, '+') ? 1 : 0;
        $name = ltrim($raw, '*+');
        $artists[] = [$aid, $name, slugify($name), $countryIds[$code], $label, $emerging];
        $countryArtists[] = $aid;
    }

    $trackCount = $code === 'TG' ? 30 : 14;
    for ($n = 1; $n <= $trackCount; $n++) {
        $tid++;
        $artistId = $countryArtists[($n - 1) % count($countryArtists)];
        if ($n > count($countryArtists) && mt_rand(0, 1)) {
            $artistId = $countryArtists[mt_rand(0, min(5, count($countryArtists) - 1))];
        }
        do {
            $title = $titleWords[$locale][mt_rand(0, count($titleWords[$locale]) - 1)];
            if (isset($usedTitles[$title])) {
                $title .= ' ' . ['II', 'Remix', 'Reloaded', '(Acoustique)'][mt_rand(0, 3)];
            }
        } while (isset($usedTitles[$title]));
        $usedTitles[$title] = true;

        // Profil d'audience : base hebdomadaire (loi de Zipf) et tendance
        $scale = $code === 'TG' ? 70000 : 42000;
        $base = $scale / pow($n, 0.85) * (0.85 + mt_rand(0, 30) / 100);
        $trend = 0.93 + mt_rand(0, 17) / 100;

        // Dates de sortie : quelques nouveautés pendant la période
        $recent = in_array($n, [3, 9, 12], true) || ($code === 'TG' && in_array($n, [17, 24], true));
        $release = $recent
            ? date('Y-m-d', strtotime('2026-08-10 +' . mt_rand(0, 40) . ' days'))
            : date('Y-m-d', strtotime('2026-07-01 -' . mt_rand(20, 700) . ' days'));

        $featuring = mt_rand(0, 6) === 0 ? $artistsByCountry[$code][mt_rand(0, count($artistsByCountry[$code]) - 1)] : null;
        $featuring = $featuring ? ltrim($featuring, '*+') : null;
        $artistName = $artists[$artistId - 1][1];
        if ($featuring === $artistName) {
            $featuring = null;
        }

        $platforms = ['youtube' => 0.55];
        if (mt_rand(1, 100) <= 85) {
            $platforms['audiomack'] = 0.3;
        }
        if (mt_rand(1, 100) <= 65) {
            $platforms['boomplay'] = 0.25;
        }

        $special = null;
        if ($code === 'TG' && $n === 6) {
            $platforms = ['youtube' => 1.0]; // mono-source très écouté : plafonné à la 6e place
            $base *= 2.6;
            $special = 'single_source';
        }
        if ($code === 'TG' && in_array($n, [23, 27], true)) {
            // forte progression (plus de 50 % par semaine) hors Top 20 : Buzz Chart
            $trend = $n === 23 ? 1.62 : 1.66;
            $base = $n === 23 ? 95 : 75;
        }
        if ($code === 'BJ' && $n === 4) {
            $special = 'spike'; // pic suspect la dernière semaine, sur Audiomack
            $platforms['audiomack'] = 0.3;
        }
        if ($code === 'BJ' && $n === 7) {
            $special = 'yt_ratio'; // vues sans "j'aime" la dernière semaine
            $platforms['youtube'] = 0.6;
        }

        $tracks[] = [
            'row' => [$tid, $title, slugify($artistName . ' ' . $title), $artistId, $featuring, $release],
            'code' => $code, 'base' => $base, 'trend' => $trend, 'release' => $release,
            'platforms' => $platforms, 'special' => $special, 'recent' => $recent,
        ];
    }
}

$sql[] = "INSERT INTO artists (id, name, slug, submission_country_id, label_owner, is_emerging) VALUES\n" . $rows($artists) . ';';
$sql[] = "INSERT INTO tracks (id, title, slug, artist_id, featuring, release_date) VALUES\n" . $rows(array_column($tracks, 'row')) . ';';

// Identifiants plateformes et relevés quotidiens
$weights = ['youtube' => 0.5, 'audiomack' => 1.0, 'boomplay' => 1.0];
$snapshots = [];
$days = [];
for ($ts = strtotime(SEED_FROM); $ts <= strtotime(SEED_TO); $ts = strtotime('+1 day', $ts)) {
    $days[] = date('Y-m-d', $ts);
}
$lastWeekStart = '2026-09-21';

foreach ($tracks as $t) {
    $trackId = $t['row'][0];
    $sumShares = array_sum($t['platforms']);
    foreach ($t['platforms'] as $platform => $share) {
        $pid++;
        $external = match ($platform) {
            'youtube'   => substr(str_replace(['+', '/', '='], ['-', '_', ''], base64_encode(md5("yt$trackId", true))), 0, 11),
            'audiomack' => 'demo-artist/' . $t['row'][2],
            'boomplay'  => (string) (90000000 + $trackId * 37),
        };
        $url = match ($platform) {
            'youtube'   => 'https://www.youtube.com/watch?v=' . $external,
            'audiomack' => 'https://audiomack.com/' . $external,
            'boomplay'  => 'https://www.boomplay.com/songs/' . $external,
        };
        $published = $t['recent'] ? $t['release'] : null;
        $tpis[] = [$pid, $trackId, $platform, $external, $platform === 'youtube' ? 'clip' : 'main', $url, $published ?? $t['release']];

        // Compteur de départ (titres anciens) et rythme quotidien
        $counter = $t['recent'] ? 0 : (int) ($t['base'] * (mt_rand(8, 40)) / $weights[$platform] * $share / $sumShares);
        $likeRate = (mt_rand(18, 45) / 1000);
        $likes = (int) ($counter * $likeRate);

        foreach ($days as $d) {
            if ($d < $t['release']) {
                continue;
            }
            $week = intdiv((int) ((strtotime($d) - strtotime(SEED_FROM)) / 86400), 7);
            $weeksSinceRelease = $t['recent'] ? intdiv((int) ((strtotime($d) - strtotime($t['release'])) / 86400), 7) : 99;
            $launchBoost = $weeksSinceRelease === 0 ? 1.8 : ($weeksSinceRelease === 1 ? 1.3 : 1.0);
            $points = $t['base'] * pow($t['trend'], $week) * $launchBoost / 7 * $share / $sumShares;
            $daily = (int) max(0, $points / $weights[$platform] * (0.8 + mt_rand(0, 40) / 100));

            $isLastWeek = $d >= $lastWeekStart && $d <= '2026-09-27';
            if ($t['special'] === 'spike' && $isLastWeek && $platform === 'audiomack') {
                $daily *= 25;
            }
            $dailyLikes = (int) ($daily * $likeRate);
            if ($t['special'] === 'yt_ratio' && $isLastWeek && $platform === 'youtube') {
                $daily += 7000;
                $dailyLikes = mt_rand(0, 3);
            }

            if ($d !== $t['release'] || !$t['recent']) {
                $counter += $daily;
                $likes += $dailyLikes;
            }
            $snapshots[] = [$pid, $d, $counter, $platform === 'youtube' ? $likes : null, 'api'];
        }
    }
}

$sql[] = "INSERT INTO track_platform_ids (id, track_id, platform, external_id, kind, url, published_at) VALUES\n" . $rows($tpis) . ';';

// Identifiants Spotify (métadonnées seulement, hors score)
$spotify = [];
foreach ($tracks as $t) {
    if (mt_rand(1, 100) <= 60) {
        $pid++;
        $ext = substr(bin2hex(md5('sp' . $t['row'][0], true)), 0, 22);
        $spotify[] = [$pid, $t['row'][0], 'spotify', $ext, 'main', 'https://open.spotify.com/track/' . $ext, $t['release']];
    }
}
$sql[] = "INSERT INTO track_platform_ids (id, track_id, platform, external_id, kind, url, published_at) VALUES\n" . $rows($spotify) . ';';

foreach (array_chunk($snapshots, 800) as $chunk) {
    $sql[] = "INSERT INTO snapshots (track_platform_id, captured_on, plays, likes, source) VALUES\n" . $rows($chunk) . ';';
}

// Déclarations d'artistes : une validée (Spotify for Artists), une en attente
$tgTracks = array_values(array_filter($tracks, fn ($t) => $t['code'] === 'TG'));
$validatedTrack = $tgTracks[1]['row'];
$pendingTrack = $tgTracks[4]['row'];
$sql[] = "INSERT INTO submissions (track_id, artist_id, submitted_artist_name, submitted_track_title, contact_name, contact_email, platform, period_start, period_end, streams, country_breakdown, screenshot_path, status, reviewed_at, review_note) VALUES\n" . $rows([
    [$validatedTrack[0], $validatedTrack[3], $artists[$validatedTrack[3] - 1][1], $validatedTrack[1], 'Management (exemple)', 'demo@example.com', 'spotify',
     '2026-09-21', '2026-09-27', 4200, json_encode(['TG' => 58.0, 'CI' => 21.5, 'FR' => 12.0, 'BJ' => 8.5]), 'demo/capture-exemple.png', 'validated', '2026-09-28 10:00:00', 'Capture lisible, période conforme (exemple)'],
    [$pendingTrack[0], $pendingTrack[3], $artists[$pendingTrack[3] - 1][1], $pendingTrack[1], 'Label (exemple)', 'label@example.com', 'boomplay',
     '2026-09-14', '2026-09-27', 18500, json_encode(['TG' => 71.0, 'BJ' => 17.0, 'GH' => 12.0]), 'demo/capture-exemple.png', 'pending', null, null],
]) . ';';

// Pays d'écoute principal (statistique déclarée) pour quelques artistes
$sql[] = "UPDATE artists SET top_country_id = 1, top_country_share = 58.00, top_country_updated_at = '2026-09-28' WHERE id = {$validatedTrack[3]};";
$sql[] = "UPDATE artists SET top_country_id = 4, top_country_share = 41.00, top_country_updated_at = '2026-09-01' WHERE id = 3;";

// Actualités de départ : annonces sur le projet lui-même (aucune fausse information sur des personnes réelles)
$news = [
    ['Lancement : le Togo ouvre la marche', 'lancement-le-togo-ouvre-la-marche', "Le premier classement hebdomadaire couvre le Togo avec un Top 20. Le Bénin, le Ghana, la Côte d'Ivoire et le Sénégal suivent avec un Top 10.",
     "Cauri Charts publie chaque mardi le classement de la semaine précédente, calculé du lundi au dimanche. Le Togo, pays pilote, a un Top 20. Les quatre autres pays démarrent avec un Top 10, qui passera à 20 quand les données seront assez nombreuses.", 'annonce', 1, '2026-09-22 09:00:00'],
    ['Artistes et labels : déclarez vos chiffres', 'artistes-et-labels-declarez-vos-chiffres', 'Spotify for Artists, Audiomack, Boomplay : une capture de votre espace artiste suffit. Chaque déclaration est vérifiée avant d\'être comptée.',
     "Certaines plateformes ne publient pas leurs chiffres. Le formulaire de déclaration permet d'envoyer une capture de votre espace artiste. Elle est vérifiée par l'équipe et comptée seulement si elle est recoupée par une donnée publique.", 'annonce', null, '2026-09-23 10:00:00'],
    ['La méthodologie est publique', 'la-methodologie-est-publique', "Une écoute audio vaut un point, une vue d'un clip officiel un demi. Seule la progression de la semaine compte.",
     "Toutes les règles de calcul sont publiées : sources, poids, règle de diversité, contrôles anti-fraude. Toute modification est annoncée au moins deux semaines avant d'entrer en vigueur.", 'classement', null, '2026-09-24 11:00:00'],
    ['Les titres suspects sont examinés avant publication', 'les-titres-suspects-sont-examines', "Un pic d'écoutes inexpliqué bloque la publication tant qu'il n'a pas été vérifié. Les exclusions sont publiées avec leur motif.",
     null, 'classement', null, '2026-09-26 12:00:00'],
    ["Bientôt : un classement pour toute l'Afrique de l'Ouest", 'bientot-prime-chart-afrique-de-l-ouest', 'Après six à huit semaines de régularité, un classement régional additionnera les points gagnés dans chacun des cinq pays.',
     null, 'annonce', null, '2026-09-28 09:00:00'],
];
$sql[] = "INSERT INTO news (title, slug, summary, body, category, country_id, status, published_at) VALUES\n"
    . $rows(array_map(fn ($n) => [$n[0], $n[1], $n[2], $n[3], $n[4], $n[5], 'published', $n[6]], $news)) . ';';

$sql[] = '';
$sql[] = 'SET FOREIGN_KEY_CHECKS = 1;';

file_put_contents(BASE_PATH . '/database/seed.sql', implode("\n", $sql) . "\n");
printf("seed.sql généré : %d artistes, %d titres, %d identifiants, %d relevés\n", count($artists), count($tracks), $pid, count($snapshots));
