<?php

use Cauri\Services\Charts\ChartRanker;
use Cauri\Services\Charts\Flags;
use Cauri\Services\Charts\ScoreCalculator;

$formula = require dirname(__DIR__) . '/config/formula.php';

$item = function (int $id, float $score, int $sources = 2, array $extra = []): array {
    return $extra + [
        'track_id' => $id, 'artist_id' => 100 + $id, 'score' => $score, 'sources_count' => $sources,
        'prev_score' => 0.0, 'release_date' => null, 'is_emerging' => false,
        'flags' => [], 'review_status' => 'ok', 'breakdown' => [],
    ];
};

$ids = fn (array $entries) => array_map(fn ($e) => $e['track_id'], $entries);

return [

    // --- Variations et poids ---

    'le score additionne variation x poids par source' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['youtube' => 10000, 'audiomack' => 3000, 'boomplay' => 2000]], 'TG');
        assert_same(10000 * 0.5 + 3000 + 2000, $r['score']);
        assert_same(3, $r['sources_count']);
        assert_same('ok', $r['review_status']);
    },

    'spotify ne compte pas dans le score' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['spotify' => 50000, 'youtube' => 1000]], 'TG');
        assert_same(500.0, $r['score']);
        assert_same(1, $r['sources_count']);
    },

    'un poids par pays remplace le poids général' => function () use ($formula) {
        $formula['country_weights'] = ['GH' => ['youtube' => 0.8]];
        $calc = new ScoreCalculator($formula);
        assert_same(800.0, $calc->score(['deltas' => ['youtube' => 1000]], 'GH')['score']);
        assert_same(500.0, $calc->score(['deltas' => ['youtube' => 1000]], 'TG')['score']);
    },

    'une variation négative compte zéro et est signalée' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['youtube' => -500, 'audiomack' => 100]], 'TG');
        assert_same(100.0, $r['score']);
        assert_contains(Flags::NEGATIVE_DELTA, $r['flags']);
        assert_same(1, $r['sources_count']);
    },

    'une source sans donnée (null) est ignorée' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['youtube' => null, 'audiomack' => 400]], 'TG');
        assert_same(400.0, $r['score']);
        assert_same(1, $r['sources_count']);
    },

    // --- Déclarations ---

    'une déclaration recoupée par une donnée publique compte' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score([
            'deltas' => ['youtube' => 2000],
            'declarations' => [['platform' => 'spotify', 'streams' => 700]],
        ], 'TG');
        assert_same(1000.0 + 700, $r['score']);
        assert_same(2, $r['sources_count']);
    },

    'une déclaration sans aucune donnée publique ne compte pas' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score([
            'deltas' => [],
            'declarations' => [['platform' => 'spotify', 'streams' => 5000]],
        ], 'TG');
        assert_same(0.0, $r['score']);
        assert_contains(Flags::DECLARATION_UNCORROBORATED, $r['flags']);
    },

    'une déclaration écartée de plus de 30 % de la donnée publique est à vérifier' => function () use ($formula) {
        $calc = new ScoreCalculator($formula);
        $bad = $calc->score(['deltas' => ['audiomack' => 1000], 'declarations' => [['platform' => 'audiomack', 'streams' => 1400]]], 'TG');
        assert_contains(Flags::DECLARATION_MISMATCH, $bad['flags']);
        assert_same('pending', $bad['review_status']);
        assert_same(1000.0, $bad['score'], 'la donnée publique prévaut');

        $ok = $calc->score(['deltas' => ['audiomack' => 1000], 'declarations' => [['platform' => 'audiomack', 'streams' => 1250]]], 'TG');
        assert_not_contains(Flags::DECLARATION_MISMATCH, $ok['flags']);
        assert_same('ok', $ok['review_status']);
    },

    'une déclaration est ramenée à la part de la semaine' => function () {
        // 14 jours, dont 7 dans la semaine
        assert_same(500, ScoreCalculator::prorate(1000, '2026-09-14', '2026-09-27', '2026-09-21', '2026-09-27'));
        assert_same(0, ScoreCalculator::prorate(1000, '2026-08-01', '2026-08-31', '2026-09-21', '2026-09-27'));
    },

    // --- Anti-fraude ---

    'un pic supérieur à 5 fois la médiane des 4 semaines est à vérifier' => function () use ($formula) {
        $calc = new ScoreCalculator($formula);
        $r = $calc->score(['deltas' => ['audiomack' => 6000], 'history' => [1000, 1100, 900, 1000]], 'TG');
        assert_contains(Flags::SPIKE, $r['flags']);
        assert_same('pending', $r['review_status']);

        $normal = $calc->score(['deltas' => ['audiomack' => 4900], 'history' => [1000, 1100, 900, 1000]], 'TG');
        assert_not_contains(Flags::SPIKE, $normal['flags']);
    },

    'pas de contrôle de pic sans historique suffisant' => function () use ($formula) {
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['audiomack' => 60000], 'history' => [100]], 'TG');
        assert_not_contains(Flags::SPIKE, $r['flags']);
    },

    'seules les 4 dernières semaines servent à la médiane' => function () use ($formula) {
        // Semaines anciennes très hautes ignorées : médiane = 1000
        $r = (new ScoreCalculator($formula))->score(['deltas' => ['audiomack' => 5500], 'history' => [1000, 1000, 1000, 1000, 90000, 90000]], 'TG');
        assert_contains(Flags::SPIKE, $r['flags']);
    },

    'un ratio vues / j\'aime anormal sur YouTube est signalé' => function () use ($formula) {
        $calc = new ScoreCalculator($formula);
        $r = $calc->score(['deltas' => ['youtube' => 200000], 'youtube_likes' => 40], 'TG');
        assert_contains(Flags::YOUTUBE_RATIO, $r['flags']);
        $ok = $calc->score(['deltas' => ['youtube' => 200000], 'youtube_likes' => 3000], 'TG');
        assert_not_contains(Flags::YOUTUBE_RATIO, $ok['flags']);
        $small = $calc->score(['deltas' => ['youtube' => 5000], 'youtube_likes' => 0], 'TG');
        assert_not_contains(Flags::YOUTUBE_RATIO, $small['flags'], 'pas de contrôle sous le seuil de vues');
    },

    'une décision admin fixe le statut' => function () use ($formula) {
        $calc = new ScoreCalculator($formula);
        $spike = ['deltas' => ['audiomack' => 9000], 'history' => [1000, 1000, 1000]];
        assert_same('validated', $calc->score($spike + ['decision' => 'validated'], 'TG')['review_status']);
        assert_same('excluded', $calc->score($spike + ['decision' => 'excluded'], 'TG')['review_status']);
    },

    // --- Classement et égalités ---

    'le prime chart trie par score et coupe à la taille du pays' => function () use ($formula, $item, $ids) {
        $entries = (new ChartRanker($formula))->prime([$item(1, 100), $item(2, 300), $item(3, 200), $item(4, 50)], 3);
        assert_same([2, 3, 1], $ids($entries));
        assert_same([1, 2, 3], array_column($entries, 'position'));
    },

    'égalité : le titre avec le plus de sources passe devant' => function () use ($formula, $item, $ids) {
        $entries = (new ChartRanker($formula))->prime([$item(1, 500, 2), $item(2, 500, 3)], 10);
        assert_same([2, 1], $ids($entries));
    },

    'égalité : puis la meilleure progression' => function () use ($formula, $item, $ids) {
        $entries = (new ChartRanker($formula))->prime([
            $item(1, 500, 2, ['prev_score' => 450.0]),
            $item(2, 500, 2, ['prev_score' => 100.0]),
        ], 10);
        assert_same([2, 1], $ids($entries));
    },

    'égalité parfaite : ordre stable par identifiant' => function () use ($formula, $item, $ids) {
        $entries = (new ChartRanker($formula))->prime([$item(9, 500), $item(3, 500)], 10);
        assert_same([3, 9], $ids($entries));
    },

    'les titres exclus ou à score nul ne sont pas classés' => function () use ($formula, $item, $ids) {
        $entries = (new ChartRanker($formula))->prime([
            $item(1, 900, 2, ['review_status' => 'excluded']), $item(2, 0), $item(3, 10),
        ], 10);
        assert_same([3], $ids($entries));
    },

    'un titre à vérifier reste visible dans le brouillon' => function () use ($formula, $item) {
        $entries = (new ChartRanker($formula))->prime([$item(1, 900, 2, ['review_status' => 'pending'])], 10);
        assert_same('pending', $entries[0]['review_status']);
    },

    'position précédente, meilleure position et semaines au classement' => function () use ($formula, $item) {
        $entries = (new ChartRanker($formula))->prime([$item(1, 900), $item(2, 800)], 10, [
            1 => ['position' => 4, 'peak' => 2, 'weeks' => 5],
            2 => ['position' => null, 'peak' => 1, 'weeks' => 3], // retour après une absence
        ]);
        assert_same([4, 1, 6], [$entries[0]['previous_position'], $entries[0]['peak_position'], $entries[0]['weeks_on_chart']]);
        assert_same([null, 1, 4], [$entries[1]['previous_position'], $entries[1]['peak_position'], $entries[1]['weeks_on_chart']]);
    },

    // --- Règle de diversité ---

    'un titre mono-source est plafonné à la sixième place' => function () use ($formula, $item, $ids) {
        $items = [$item(1, 10000, 1)];
        for ($i = 2; $i <= 8; $i++) {
            $items[] = $item($i, 1000 - $i, 2);
        }
        $entries = (new ChartRanker($formula))->prime($items, 10);
        assert_same(1, $entries[5]['track_id'], 'le mono-source arrive 6e');
        assert_contains(Flags::DIVERSITY_CAPPED, $entries[5]['flags']);
        assert_same([2, 3, 4, 5, 6], array_slice($ids($entries), 0, 5));
    },

    'un mono-source déjà hors Top 5 garde sa place' => function () use ($formula, $item, $ids) {
        $items = [];
        for ($i = 1; $i <= 6; $i++) {
            $items[] = $item($i, 1000 - $i, 2);
        }
        $items[] = $item(7, 500, 1);
        $entries = (new ChartRanker($formula))->prime($items, 10);
        assert_same(7, $entries[6]['track_id']);
        assert_same([], $entries[6]['flags']);
    },

    'sans assez de titres multi-sources, le Top 5 est complété sans trou' => function () use ($formula, $item, $ids) {
        $entries = (new ChartRanker($formula))->prime([
            $item(1, 9000, 1), $item(2, 8000, 1), $item(3, 100, 2), $item(4, 50, 2),
        ], 10);
        assert_same([3, 4, 1, 2], $ids($entries));
        assert_contains(Flags::DIVERSITY_FALLBACK, $entries[2]['flags']);
    },

    // --- Buzz, Fresh, Icon, cumul, régional ---

    'buzz : plus de 50 % de progression, score minimum, hors prime chart' => function () use ($formula, $item, $ids) {
        $items = [
            $item(1, 10000, 2, ['prev_score' => 5000.0]),  // +100 %, mais dans le prime
            $item(2, 6000, 2, ['prev_score' => 2000.0]),   // +200 %
            $item(3, 3000, 2, ['prev_score' => 1500.0]),   // +100 %
            $item(4, 1500, 2, ['prev_score' => 100.0]),    // sous le score minimum
            $item(5, 3000, 2, ['prev_score' => 2500.0]),   // +20 %
            $item(6, 9000, 2, ['prev_score' => 0.0]),      // nouveau : relève du Fresh Chart
        ];
        $entries = (new ChartRanker($formula))->buzz($items, [1], 10);
        assert_same([2, 3], $ids($entries));
        assert_same(200.0, $entries[0]['growth_pct']);
    },

    'fresh : sorti depuis moins de 8 semaines ou artiste émergent' => function () use ($formula, $item, $ids) {
        $items = [
            $item(1, 900, 2, ['release_date' => '2026-09-01']),
            $item(2, 800, 2, ['release_date' => '2026-01-01']),
            $item(3, 700, 2, ['release_date' => '2025-06-01', 'is_emerging' => true]),
            $item(4, 600, 2, ['release_date' => '2026-10-15']), // pas encore sorti
        ];
        $entries = (new ChartRanker($formula))->fresh($items, '2026-09-27', 10);
        assert_same([1, 3], $ids($entries));
    },

    'icon : somme des scores des titres de chaque artiste' => function () use ($formula, $item) {
        $items = [
            $item(1, 500, 2, ['artist_id' => 7]), $item(2, 400, 2, ['artist_id' => 7]),
            $item(3, 800, 2, ['artist_id' => 8]),
        ];
        $entries = (new ChartRanker($formula))->icon($items, 10);
        assert_same([7, 8], array_column($entries, 'artist_id'));
        assert_same(900.0, $entries[0]['score']);
        assert_same(2, $entries[0]['sources_count']);
    },

    'régional : points selon le rang dans chaque pays' => function () {
        $list = ChartRanker::regionalPoints([
            'TG' => [['position' => 1, 'track_id' => 1], ['position' => 2, 'track_id' => 2]],
            'BJ' => [['position' => 1, 'track_id' => 2], ['position' => 11, 'track_id' => 1]],
        ]);
        assert_same(2, $list[0]['track_id']);
        assert_same(19, $list[0]['points']);
        assert_same(10, $list[1]['points'], 'la 11e place ne rapporte rien');
    },

    'la médiane gère les listes paires et impaires' => function () {
        assert_same(2.0, ScoreCalculator::median([3, 1, 2]));
        assert_same(2.5, ScoreCalculator::median([4, 1, 2, 3]));
    },
];
