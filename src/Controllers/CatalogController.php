<?php

namespace Cauri\Controllers;

use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;

/** Fiches artiste et titre. */
final class CatalogController extends Controller
{
    public function artist(Request $request): Response
    {
        $artist = $this->charts->artist($request->param('slug'));
        if (!$artist) {
            throw new HttpException(404);
        }
        $this->useLocale();
        $tracks = $this->charts->artistTracks((int) $artist['id']);
        $charted = array_filter($tracks, fn ($t) => $t['peak'] !== null);

        // Rang parmi les artistes des cinq pays (Icon en direct)
        $iconRank = null;
        foreach ((new \Cauri\Services\Charts\LiveChart($this->db))->build(null, null, 500, 'icon')['rows'] as $row) {
            if ((int) $row['artist_id'] === (int) $artist['id']) {
                $iconRank = $row['rank'];
                break;
            }
        }

        return $this->page('artist', [
            'live'        => $this->charts->artistLive((int) $artist['id']),
            'iconRank'    => $iconRank,
            'artist'      => $artist,
            'tracks'      => $tracks,
            'bestPeak'    => $charted ? min(array_column($charted, 'peak')) : null,
            'totalWeeks'  => array_sum(array_column($tracks, 'weeks')),
            'iconHistory' => $this->charts->artistIconHistory((int) $artist['id']),
            'meta'        => [
                'title'       => $artist['name'] . ' · ' . brand(),
                'description' => t('artist.meta_description', ['name' => $artist['name'], 'country' => country_name($artist['country_code'])]),
                'type'        => 'profile',
            ],
        ]);
    }

    public function track(Request $request): Response
    {
        $track = $this->charts->track($request->param('slug'));
        if (!$track) {
            throw new HttpException(404);
        }
        $this->useLocale();
        $positions = $this->charts->trackPositions((int) $track['id']);

        // Écoutes Spotify déclarées par l'artiste (Spotify for Artists), vérifiées, les plus récentes
        $spotify = $this->db->one(
            "SELECT streams, period_start AS start, period_end AS end FROM submissions
             WHERE track_id = ? AND platform = 'spotify' AND status = 'validated' ORDER BY period_end DESC LIMIT 1",
            [(int) $track['id']]
        );

        return $this->page('track', [
            'spotify'   => $spotify,
            'track'     => $track,
            'positions' => $positions,
            'links'     => $this->charts->trackLinks((int) $track['id']),
            'peak'      => $positions ? min(array_column($positions, 'position')) : null,
            'meta'      => [
                'title'       => $track['title'] . ' · ' . $track['artist_name'] . ' · ' . brand(),
                'description' => t('track.meta_description', ['title' => $track['title'], 'artist' => $track['artist_name']]),
                'type'        => 'music.song',
            ],
        ]);
    }
}
