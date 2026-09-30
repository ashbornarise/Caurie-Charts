<?php

use Cauri\Services\AI\ClaudeClient;
use Cauri\Services\Import\ArtistClassifier;
use Cauri\Services\Social\PostGenerator;

$covered = ['TG', 'BJ', 'GH', 'CI', 'SN'];

return [

    // --- Classement automatique des artistes ---

    'classement auto : carrière dans un pays couvert = confirmé' => function () use ($covered) {
        assert_same('active', ArtistClassifier::decide(['nationality' => 'GH', 'base_country' => 'GH', 'confidence' => 0.9], $covered, 0.85));
    },

    'classement auto : artiste étranger = hors périmètre' => function () use ($covered) {
        assert_same('out_of_scope', ArtistClassifier::decide(['nationality' => 'CA', 'base_country' => 'CA', 'confidence' => 0.9], $covered, 0.85));
    },

    'classement auto : diaspora (nationalité couverte, carrière ailleurs) = décision humaine' => function () use ($covered) {
        assert_same('pending', ArtistClassifier::decide(['nationality' => 'SN', 'base_country' => 'FR', 'confidence' => 0.95], $covered, 0.85));
    },

    'classement auto : confiance insuffisante ou inconnu = décision humaine' => function () use ($covered) {
        assert_same('pending', ArtistClassifier::decide(['nationality' => 'CI', 'base_country' => 'CI', 'confidence' => 0.6], $covered, 0.85));
        assert_same('pending', ArtistClassifier::decide(['nationality' => null, 'base_country' => null, 'confidence' => 0.9], $covered, 0.85));
        assert_same('pending', ArtistClassifier::decide(null, $covered, 0.85));
    },

    'classement auto : MusicBrainz et Wikidata en désaccord = aucune décision' => function () use ($covered) {
        $mb = ['nationality' => 'GH', 'base_country' => 'GH', 'confidence' => 0.9, 'source' => 'musicbrainz', 'note' => 'mb'];
        $wd = ['nationality' => 'NG', 'base_country' => 'NG', 'confidence' => 0.9, 'source' => 'wikidata', 'note' => 'wd'];
        assert_same('pending', ArtistClassifier::decide(ArtistClassifier::combine($mb, $wd), $covered, 0.85));
        assert_same(0.95, ArtistClassifier::combine($mb, $mb)['confidence']);
        assert_same('out_of_scope', ArtistClassifier::decide(ArtistClassifier::combine(null, $wd), $covered, 0.85));
    },

    'ia : réponse non recoupée par un indice = plafonnée sous le seuil (décision humaine)' => function () use ($covered) {
        $v = ['nationality' => 'SN', 'base_country' => 'SN', 'confidence' => 0.95, 'source' => 'ia', 'note' => ''];
        assert_same('pending', ArtistClassifier::decide(ArtistClassifier::corroborate($v, null, ''), $covered, 0.85));
        assert_same('active', ArtistClassifier::decide(ArtistClassifier::corroborate($v, 'SN', ''), $covered, 0.85));
        assert_same('active', ArtistClassifier::decide(ArtistClassifier::corroborate($v, null, 'chanteur sénégalais de mbalax'), $covered, 0.85));
        assert_same('pending', ArtistClassifier::decide(ArtistClassifier::corroborate($v, 'FR', ''), $covered, 0.85));
    },

    'sécurité : pas de téléchargement vers une adresse locale ou privée (SSRF)' => function () {
        assert_same(false, \Cauri\Services\News\FeedImporter::isPublicHost('localhost'));
        assert_same(false, \Cauri\Services\News\FeedImporter::isPublicHost('127.0.0.1'));
        assert_same(false, \Cauri\Services\News\FeedImporter::isPublicHost('192.168.1.10'));
        assert_same(false, \Cauri\Services\News\FeedImporter::isPublicHost('169.254.169.254'));
        assert_same(null, \Cauri\Services\News\FeedImporter::httpGet('http://127.0.0.1:8000/'));
    },

    'scène : marqueurs locaux et pays dominant' => function () {
        $s = \Cauri\Services\Import\SceneSignals::score('Nouveau clip tourné à Lomé 228 ! Togo to the world, en éwé');
        assert_same('TG', \Cauri\Services\Import\SceneSignals::dominant($s));
        assert_same(null, \Cauri\Services\Import\SceneSignals::dominant(\Cauri\Services\Import\SceneSignals::score('Paris, New York, London')));
    },

    'chaîne YouTube : chaque vidéo rattachée au bon titre de l’artiste' => function () {
        $tracks = [['id' => 1, 'title' => 'Bra'], ['id' => 2, 'title' => 'Bra (Remix)'], ['id' => 3, 'title' => 'Bombele']];
        $m = fn ($t) => \Cauri\Services\Import\YouTubeChannelSync::matchTrack($t, $tracks);
        assert_same(3, $m('Kweku Smoke - Bombele (Official Music Video)'));
        assert_same(1, $m('Kweku Smoke - Bra (Audio Visualizer)'));
        assert_same(null, $m('Kweku Smoke - Bombele (Teaser)'));
        assert_same(null, $m('Kweku Smoke live at Afrochella'));
        assert_same(null, $m('Brazil vlog'));
    },

    'popularité Deezer : classement par score décroissant' => function () {
        $r = \Cauri\Services\Import\DeezerPopularitySource::rank([
            ['rank_score' => 100, 'title' => 'B', 'artist' => 'X'], ['rank_score' => 900, 'title' => 'A', 'artist' => 'Y'],
        ], 10);
        assert_same('A', $r['rows'][0]['title']);
        assert_same(2, $r['rows'][1]['position']);
        assert_true(!isset($r['rows'][0]['rank_score']));
    },

    'wikidata : gentilé de la description' => function () {
        assert_same('CI', \Cauri\Services\Import\WikidataLookup::demonym('rappeur ivoirien'));
        assert_same('GH', \Cauri\Services\Import\WikidataLookup::demonym('Ghanaian rapper and songwriter'));
        assert_same(null, \Cauri\Services\Import\WikidataLookup::demonym('village in Belarus'));
    },

    'ia : extraction du JSON entouré de texte' => function () {
        $json = ClaudeClient::json("Voici :\n```json\n{\"base_country\": \"SN\", \"confidence\": 0.92, \"x\": {\"a\": 1}}\n```");
        assert_same('SN', $json['base_country']);
        assert_same(1, $json['x']['a']);
    },

    // --- Posts réseaux sociaux ---

    'posts : le texte modèle ne reprend que les faits fournis' => function () {
        $facts = [
            'kind' => 'artist', 'headline' => 'Artiste de la semaine', 'source' => 'Classements Deezer',
            'artist' => ['name' => 'Himra', 'country' => 'CI', 'deezer_fans' => 52534, 'profile' => '/artiste/himra'],
            'tracks' => [['title' => 'PLUS DE LOVE', 'seen' => [['platform' => 'Deezer', 'country' => 'CI', 'position' => 4]]]],
        ];
        $post = PostGenerator::template($facts);
        assert_same('Himra', $post['title']);
        assert_true(str_contains($post['caption'], 'Deezer CI n°4'));
        assert_true(str_contains($post['caption'], '52 534 fans'));
        assert_true(str_contains($post['caption'], 'Source : Classements Deezer'));
    },
];
