<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Services\Audit;

/** Pays, artistes, titres et identifiants plateformes. */
final class CatalogAdminController extends BaseAdminController
{
    private const PLATFORMS = ['youtube', 'audiomack', 'boomplay', 'spotify', 'apple_music', 'deezer'];

    public function index(Request $request): Response
    {
        $this->requireUser($request);
        $q = mb_substr($request->str('q'), 0, 100);
        $like = '%' . $q . '%';
        return $this->admin('catalog', [
            'q'         => $q,
            'countries' => $this->charts->countries(false),
            'artists'   => $this->db->all(
                'SELECT a.*, c.code, (SELECT COUNT(*) FROM tracks t WHERE t.artist_id = a.id) AS tracks
                 FROM artists a JOIN countries c ON c.id = a.submission_country_id WHERE a.name LIKE ? ORDER BY c.sort_order, a.name LIMIT 300',
                [$like]
            ),
            'tracks'    => $this->db->all(
                'SELECT t.*, a.name AS artist_name, (SELECT GROUP_CONCAT(platform) FROM track_platform_ids p WHERE p.track_id = t.id) AS platforms
                 FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE t.title LIKE ? OR a.name LIKE ? ORDER BY t.created_at DESC, t.id DESC LIMIT 300',
                [$like, $like]
            ),
        ]);
    }

    public function saveCountry(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $id = (int) $request->param('id');
        $platforms = array_values(array_intersect(self::PLATFORMS, (array) ($request->post['platforms'] ?? [])));
        $size = (int) $request->str('chart_size');
        if ($size < 5 || $size > 100 || !$platforms) {
            return $this->back(path('admin/catalogue'), 'error', t('admin.country_invalid'));
        }
        $data = [
            'chart_size' => $size,
            'platforms'  => implode(',', $platforms),
            'locale'     => $request->str('locale') === 'en' ? 'en' : 'fr',
            'is_active'  => $request->input('is_active') === '1' ? 1 : 0,
        ];
        $this->db->update('countries', $data, 'id = :id', ['id' => $id]);
        Audit::log($this->uid(), 'country.update', 'country', $id, null, $data, $request->ip());
        return $this->back(path('admin/catalogue'), 'success', t('admin.saved'));
    }

    public function artistForm(Request $request): Response
    {
        $this->requireUser($request);
        $id = $request->param('id');
        $artist = $id === 'nouveau' ? ['id' => null, 'name' => '', 'submission_country_id' => null, 'label_owner' => '', 'is_emerging' => 0, 'bio' => '', 'image_url' => '']
            : $this->db->one('SELECT * FROM artists WHERE id = ?', [(int) $id]);
        if (!$artist) {
            throw new HttpException(404);
        }
        return $this->admin('artist-form', ['artist' => $artist, 'countries' => $this->charts->countries(false)]);
    }

    public function saveArtist(Request $request): Response
    {
        $this->requireUser($request);
        $id = $request->param('id') === 'nouveau' ? null : (int) $request->param('id');
        $name = mb_substr($request->str('name'), 0, 150);
        $countryId = (int) $request->str('submission_country_id');
        $image = $request->str('image_url');
        if ($name === '' || !$this->db->value('SELECT id FROM countries WHERE id = ?', [$countryId]) || ($image !== '' && !preg_match('#^https://#', $image))) {
            return $this->back(path('admin/artistes/' . ($id ?? 'nouveau')), 'error', t('admin.artist_invalid'));
        }
        $data = [
            'name'                  => $name,
            'submission_country_id' => $countryId,
            'label_owner'           => preg_replace('/[^a-z0-9_-]/', '', strtolower($request->str('label_owner'))) ?: null,
            'is_emerging'           => $request->input('is_emerging') === '1' ? 1 : 0,
            'bio'                   => mb_substr($request->str('bio'), 0, 3000) ?: null,
            'image_url'             => $image ?: null,
        ];
        if ($id) {
            $old = $this->db->one('SELECT submission_country_id, label_owner FROM artists WHERE id = ?', [$id]);
            $this->db->update('artists', $data, 'id = :id', ['id' => $id]);
            Audit::log($this->uid(), 'artist.update', 'artist', $id, null, ['before' => $old, 'after' => array_intersect_key($data, $old ?? [])], $request->ip());
        } else {
            $data['slug'] = $this->uniqueSlug('artists', slugify($name));
            $id = $this->db->insert('artists', $data);
            Audit::log($this->uid(), 'artist.create', 'artist', $id, null, [], $request->ip());
        }
        return $this->back(path('admin/catalogue'), 'success', t('admin.saved'));
    }

    public function trackForm(Request $request): Response
    {
        $this->requireUser($request);
        $id = $request->param('id');
        $track = $id === 'nouveau' ? ['id' => null, 'title' => '', 'artist_id' => (int) $request->str('artist'), 'featuring' => '', 'release_date' => '', 'cover_url' => '', 'is_active' => 1]
            : $this->db->one('SELECT * FROM tracks WHERE id = ?', [(int) $id]);
        if (!$track) {
            throw new HttpException(404);
        }
        return $this->admin('track-form', [
            'track'       => $track,
            'artists'     => $this->db->all('SELECT a.id, a.name, c.code FROM artists a JOIN countries c ON c.id = a.submission_country_id ORDER BY a.name'),
            'platformIds' => $track['id'] ? $this->db->all('SELECT * FROM track_platform_ids WHERE track_id = ? ORDER BY platform', [$track['id']]) : [],
            'platforms'   => self::PLATFORMS,
        ]);
    }

    public function saveTrack(Request $request): Response
    {
        $this->requireUser($request);
        $id = $request->param('id') === 'nouveau' ? null : (int) $request->param('id');
        $title = mb_substr($request->str('title'), 0, 200);
        $artistId = (int) $request->str('artist_id');
        $release = $request->str('release_date');
        $cover = $request->str('cover_url');
        $artist = $this->db->one('SELECT name FROM artists WHERE id = ?', [$artistId]);
        if ($title === '' || !$artist || ($release !== '' && !\DateTimeImmutable::createFromFormat('!Y-m-d', $release)) || ($cover !== '' && !preg_match('#^https://#', $cover))) {
            return $this->back(path('admin/titres/' . ($id ?? 'nouveau')), 'error', t('admin.track_invalid'));
        }
        $data = [
            'title'        => $title,
            'artist_id'    => $artistId,
            'featuring'    => mb_substr($request->str('featuring'), 0, 255) ?: null,
            'release_date' => $release ?: null,
            'cover_url'    => $cover ?: null,
            'is_active'    => $request->input('is_active') === '1' ? 1 : 0,
        ];

        try {
            $this->db->transaction(function () use (&$id, $data, $request, $artist, $title) {
                if ($id) {
                    $this->db->update('tracks', $data, 'id = :id', ['id' => $id]);
                } else {
                    $data['slug'] = $this->uniqueSlug('tracks', slugify($artist['name'] . ' ' . $title));
                    $id = $this->db->insert('tracks', $data);
                }
                // Identifiants plateformes : suppression cochée, puis ajout éventuel
                foreach ((array) ($request->post['delete_pid'] ?? []) as $pid) {
                    $this->db->run('DELETE FROM track_platform_ids WHERE id = ? AND track_id = ?', [(int) $pid, $id]);
                }
                $platform = $request->str('new_platform');
                $external = trim($request->str('new_external_id'));
                if ($platform !== '' && $external !== '') {
                    if (!in_array($platform, self::PLATFORMS, true)) {
                        throw new \InvalidArgumentException(t('admin.track_invalid'));
                    }
                    $url = $request->str('new_url');
                    if ($url !== '' && !preg_match('#^https://#', $url)) {
                        throw new \InvalidArgumentException(t('admin.track_invalid'));
                    }
                    $this->db->insert('track_platform_ids', [
                        'track_id'     => $id,
                        'platform'     => $platform,
                        'external_id'  => mb_substr($external, 0, 191),
                        'kind'         => preg_replace('/[^a-z_]/', '', $request->str('new_kind')) ?: 'main',
                        'url'          => $url ?: null,
                        'published_at' => \DateTimeImmutable::createFromFormat('!Y-m-d', $request->str('new_published_at')) ? $request->str('new_published_at') : null,
                    ]);
                }
            });
        } catch (\PDOException $e) {
            return $this->back(path('admin/titres/' . ($id ?? 'nouveau')), 'error', t('admin.platform_duplicate'));
        } catch (\InvalidArgumentException $e) {
            return $this->back(path('admin/titres/' . ($id ?? 'nouveau')), 'error', $e->getMessage());
        }
        Audit::log($this->uid(), $request->param('id') === 'nouveau' ? 'track.create' : 'track.update', 'track', $id, null, [], $request->ip());
        return $this->back(path("admin/titres/$id"), 'success', t('admin.saved'));
    }

    private function uniqueSlug(string $table, string $base): string
    {
        $slug = $base;
        for ($i = 2; $this->db->value("SELECT id FROM `$table` WHERE slug = ?", [$slug]); $i++) {
            $slug = "$base-$i";
        }
        return $slug;
    }
}
