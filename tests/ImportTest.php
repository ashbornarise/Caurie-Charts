<?php

use Cauri\Services\Charts\ScoreCalculator;
use Cauri\Services\Import\AppleMusicChartSource;
use Cauri\Services\Import\ChartImporter;
use Cauri\Services\Import\DeezerChartSource;
use Cauri\Services\Import\Normalizer;
use Cauri\Services\Import\YouTubeTrendingSource;
use Cauri\Services\Import\YouTubeMatcher;

$formula = require dirname(__DIR__) . '/config/formula.php';

return [

    // --- Normalisation ---

    'normalisation : accents, casse et ponctuation' => function () {
        assert_same('melo decale', Normalizer::text('Mélo Décalé !'));
        assert_same('coeur de pirate', Normalizer::text('cœur De Pirate'));
    },

    'normalisation : les invités ne changent pas la clé du titre' => function () {
        $a = Normalizer::trackKey('Best (feat. Rema)', 'Tiakola & Rema');
        $b = Normalizer::trackKey('Best', 'Tiakola');
        assert_same($a, $b);
        assert_same('tiakola|best', $a);
    },

    'normalisation : artiste principal et invités' => function () {
        assert_same('AMADEUS', Normalizer::primaryArtist('AMADEUS & Aida Samb'));
        assert_same('Aida Samb', Normalizer::featuring('AMADEUS & Aida Samb'));
        assert_same('Kweku Smoke', Normalizer::primaryArtist('Kweku Smoke, Lasmid'));
        assert_same(null, Normalizer::featuring('Tiakola'));
    },

    // --- Apple Music ---

    'apple music : lecture du flux et pochette en 600 px' => function () {
        $snap = AppleMusicChartSource::parse(['feed' => ['updated' => 'Tue, 29 Sep 2026 20:53:59 +0000', 'results' => [
            ['id' => '111', 'name' => 'Caméléon', 'artistName' => 'Tiakola', 'url' => 'https://music.apple.com/x', 'artworkUrl100' => 'https://is1.mzstatic.com/a/100x100bb.jpg', 'releaseDate' => '2026-09-25'],
            ['id' => '222', 'name' => 'Dugi-dugi', 'artistName' => 'AMADEUS & Aida Samb'],
        ]]]);
        assert_same('2026-09-29', $snap['observed_on']);
        assert_same(2, count($snap['rows']));
        assert_same(2, $snap['rows'][1]['position']);
        assert_same('https://is1.mzstatic.com/a/600x600bb.jpg', $snap['rows'][0]['image']);
    },

    'apple music : un pays non couvert renvoie null' => function () {
        $http = new FakeHttp(fn () => ['status' => 500, 'body' => '']);
        assert_same(null, (new AppleMusicChartSource($http))->fetch('TG'));
    },

    // --- CSV ---

    'csv : avec ou sans position, point-virgule ou tabulation' => function () {
        $rows = ChartImporter::parseCsv("1;GTA;Seyi Vibez\n2\tBaba\tHotkeed feat. Zlatan\n\nMigbo;Sethlo");
        assert_same(3, count($rows));
        assert_same('Hotkeed feat. Zlatan', $rows[1]['artist']);
        assert_same(3, $rows[2]['position'], 'sans position : ordre des lignes');
    },

    'csv : une ligne illisible est refusée' => function () {
        try {
            ChartImporter::parseCsv("1;GTA;Seyi Vibez\nligne sans séparateur");
            throw new AssertionFailed('exception attendue');
        } catch (InvalidArgumentException) {
            assert_true(true);
        }
    },

    // --- Rapprochement YouTube ---

    'youtube : le clip officiel est préféré aux versions dérivées' => function () {
        $results = [
            ['external_id' => 'lyr', 'title' => 'Tiakola - Caméléon (Lyrics)', 'artist' => 'Lyrics Channel', 'url' => '', 'published_at' => null],
            ['external_id' => 'off', 'title' => 'Tiakola - Caméléon (Clip officiel)', 'artist' => 'Tiakola', 'url' => '', 'published_at' => null],
        ];
        assert_same('off', YouTubeMatcher::best($results, 'Caméléon', 'Tiakola')['external_id']);
    },

    'youtube : aucun résultat convaincant, aucun rattachement' => function () {
        $results = [['external_id' => 'x', 'title' => 'Compilation afro 2026', 'artist' => 'Mix TV', 'url' => '', 'published_at' => null]];
        assert_same(null, YouTubeMatcher::best($results, 'Caméléon', 'Tiakola'));
    },

    // --- Score v1.2 ---

    'score : les positions ne comptent pas en v1.1 (poids nul)' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['youtube' => 1000], 'chart_points' => ['apple_music' => 80]], 'BJ');
        assert_same(500.0, $r['score']);
        assert_same(1, $r['sources_count']);
    },

    'score : en v1.2 une position rapporte des points et compte comme source' => function () use ($formula) {
        $formula['chart_weights']['apple_music'] = 150;
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['youtube' => 1000], 'chart_points' => ['apple_music' => 80]], 'BJ');
        assert_same(500.0 + 80 * 150, $r['score']);
        assert_same(2, $r['sources_count']);
        assert_true(isset($r['breakdown']['chart:apple_music']));
    },

    'score : même plateforme en compteur et en classement = une seule source' => function () use ($formula) {
        $formula['chart_weights']['audiomack'] = 150;
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['audiomack' => 2000], 'chart_points' => ['audiomack' => 10]], 'TG');
        assert_same(1, $r['sources_count']);
    },

    'score : une position suffit pour recouper une déclaration' => function () use ($formula) {
        $formula['chart_weights']['apple_music'] = 150;
        $r = (new ScoreCalculator($formula))->score(['chart_points' => ['apple_music' => 10], 'declarations' => [['platform' => 'spotify', 'streams' => 900]]], 'CI');
        assert_same(1500.0 + 900, $r['score']);
    },

    'shazam : lecture du CSV (BOM, date et en-tête ignorés)' => function () {
        $snap = \Cauri\Services\Import\ShazamChartSource::parse("\xEF\xBB\xBF\n\"Wednesday, 30 September 2026 [performance over the past 7 days]\"\nRank,Artist,Title\n1,\"AMADEUS\",\"Namm nama la\"\n2,\"Wally B. Seck\",\"Bayil\"\n");
        assert_same(2, count($snap['rows']));
        assert_same('AMADEUS', $snap['rows'][0]['artist']);
        assert_same(2, $snap['rows'][1]['position']);
    },

    // --- Deezer et tendances YouTube ---

    'deezer : lecture de la playlist Top pays' => function () {
        $snap = DeezerChartSource::parse(['data' => [
            ['id' => 99, 'title' => 'Caméléon', 'link' => 'https://www.deezer.com/track/99', 'artist' => ['name' => 'Tiakola'], 'album' => ['cover_xl' => 'https://cdn/x.jpg']],
            ['id' => 100, 'title' => '', 'artist' => ['name' => 'Vide']],
        ]]);
        assert_same(1, count($snap['rows']));
        assert_same('Tiakola', $snap['rows'][0]['artist']);
        assert_same('99', $snap['rows'][0]['external_id']);
    },

    'youtube tendances : artiste et titre tirés du titre de la vidéo' => function () {
        assert_same(['Kweku Smoke', 'Bombele'], YouTubeTrendingSource::split('Kweku Smoke - Bombele (Official Music Video)', 'KwekuSmoke'));
        assert_same(['Momo Dieng', 'RAAY'], YouTubeTrendingSource::split('Momo Dieng - RAAY (Clip Officiel)', 'Prince Arts'));
        assert_same(['AMADEUS', 'Naataango'], YouTubeTrendingSource::split('Naataango', 'AMADEUS - Topic'));
    },

    'youtube tendances : l’identifiant est un clip youtube' => function () {
        $snap = YouTubeTrendingSource::parse(['items' => [
            ['id' => 'abc123', 'snippet' => ['title' => 'Kweku Smoke x Lasmid - Faith ( Official Video )', 'channelTitle' => 'KwekuSmoke', 'publishedAt' => '2026-09-20T10:00:00Z']],
        ]]);
        assert_same('youtube', $snap['rows'][0]['platform']);
        assert_same('clip', $snap['rows'][0]['kind']);
        assert_same('Kweku Smoke x Lasmid', $snap['rows'][0]['artist']);
        assert_same('Faith', $snap['rows'][0]['title']);
    },
];
