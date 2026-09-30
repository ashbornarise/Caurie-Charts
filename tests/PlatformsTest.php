<?php

use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\MemoryQuotaStore;
use Cauri\Services\Platforms\PlatformException;
use Cauri\Services\Platforms\QuotaExceededException;
use Cauri\Services\Platforms\SpotifyClient;
use Cauri\Services\Platforms\YouTubeClient;


$youtubeResponder = function (string $method, string $url): array {
    parse_str(parse_url($url, PHP_URL_QUERY), $q);
    $items = array_map(fn ($id) => ['id' => $id, 'statistics' => ['viewCount' => '1000', 'likeCount' => '40', 'commentCount' => '3']], explode(',', $q['id']));
    return ['status' => 200, 'body' => json_encode(['items' => $items])];
};

$today = fn () => '2026-09-28';

return [

    'youtube : lit viewCount, likeCount et commentCount' => function () use ($youtubeResponder, $today) {
        $yt = new YouTubeClient('cle', new FakeHttp($youtubeResponder), new MemoryQuotaStore(), 10000, $today);
        assert_same(['plays' => 1000, 'likes' => 40, 'comments' => 3, 'popularity' => null], $yt->fetchTrackStats('abc'));
    },

    'youtube : regroupe les appels par 50 identifiants et compte 1 unité par appel' => function () use ($youtubeResponder, $today) {
        $http = new FakeHttp($youtubeResponder);
        $quota = new MemoryQuotaStore();
        $yt = new YouTubeClient('cle', $http, $quota, 10000, $today);
        $ids = array_map(fn ($i) => "v$i", range(1, 120));
        $stats = $yt->fetchMany($ids);
        assert_same(120, count($stats));
        assert_same(3, count($http->calls), '120 vidéos = 3 appels');
        assert_same(3, $quota->used('youtube', '2026-09-28'));
        assert_true(str_contains($http->calls[0]['url'], 'part=statistics'));
    },

    'youtube : quota épuisé, arrêt propre avec les résultats partiels' => function () use ($youtubeResponder, $today) {
        $quota = new MemoryQuotaStore();
        $quota->add('youtube', '2026-09-28', 9998);
        $yt = new YouTubeClient('cle', new FakeHttp($youtubeResponder), $quota, 10000, $today);
        try {
            $yt->fetchMany(array_map(fn ($i) => "v$i", range(1, 200)));
            throw new AssertionFailed('exception attendue');
        } catch (QuotaExceededException $e) {
            assert_same(100, count($e->partial), '2 appels possibles avant épuisement');
        }
    },

    'youtube : la recherche refuse de partir sans 100 unités' => function () use ($youtubeResponder, $today) {
        $quota = new MemoryQuotaStore();
        $quota->add('youtube', '2026-09-28', 9950);
        $yt = new YouTubeClient('cle', new FakeHttp($youtubeResponder), $quota, 10000, $today);
        try {
            $yt->searchTrack('test');
            throw new AssertionFailed('exception attendue');
        } catch (QuotaExceededException) {
            assert_true(true);
        }
    },

    'youtube : sans clé, pas d\'appel' => function () use ($youtubeResponder, $today) {
        $http = new FakeHttp($youtubeResponder);
        $yt = new YouTubeClient('', $http, new MemoryQuotaStore(), 10000, $today);
        assert_same(false, $yt->isAvailable());
        try {
            $yt->fetchTrackStats('x');
        } catch (PlatformException) {
        }
        assert_same(0, count($http->calls));
    },

    'youtube : quotaExceeded renvoyé par Google' => function () use ($today) {
        $http = new FakeHttp(fn () => ['status' => 403, 'body' => json_encode(['error' => ['errors' => [['reason' => 'quotaExceeded']]]])]);
        $yt = new YouTubeClient('cle', $http, new MemoryQuotaStore(), 10000, $today);
        try {
            $yt->fetchTrackStats('x');
            throw new AssertionFailed('exception attendue');
        } catch (QuotaExceededException) {
            assert_true(true);
        }
    },

    'spotify : métadonnées seulement, aucun stream' => function () {
        $http = new FakeHttp(function (string $method, string $url) {
            if (str_contains($url, 'accounts.spotify.com')) {
                return ['status' => 200, 'body' => json_encode(['access_token' => 'tok', 'expires_in' => 3600])];
            }
            return ['status' => 200, 'body' => json_encode(['name' => 'Titre', 'popularity' => 42, 'album' => ['images' => [['url' => 'https://i.scdn.co/x.jpg']]]])];
        });
        $sp = new SpotifyClient('id', 'secret', $http);
        $s = $sp->fetchTrackStats('abc');
        assert_same(0, $s['plays']);
        assert_same(42, $s['popularity']);
        assert_same('Bearer tok', $http->calls[1]['headers']['Authorization']);
    },
];
