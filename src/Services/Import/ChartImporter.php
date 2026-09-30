<?php

namespace Cauri\Services\Import;

use Cauri\Core\Database;
use Cauri\Services\Audit;

/**
 * Enregistre un classement de plateforme : rapproche chaque ligne d'un titre existant
 * (identifiant de plateforme, sinon artiste + titre normalisés), crée sinon le titre et
 * l'artiste, puis note la position (chart_observations).
 *
 * Un artiste découvert ainsi arrive "en attente" avec un pays suggéré : il n'entre dans les
 * classements qu'après confirmation de son pays de soumission par l'équipe (règle des pays).
 */
final class ChartImporter
{
    private const PLATFORMS = ['youtube', 'audiomack', 'boomplay', 'spotify', 'apple_music', 'deezer'];

    public function __construct(private Database $db)
    {
    }

    /** @return array ['rows', 'matched', 'new_tracks', 'new_artists'] */
    public function import(string $countryCode, string $source, array $snapshot, ?int $userId = null): array
    {
        $country = $this->db->one('SELECT id, code FROM countries WHERE code = ?', [strtoupper($countryCode)]);
        if (!$country) {
            throw new \InvalidArgumentException("Pays inconnu : $countryCode");
        }
        $cid = (int) $country['id'];
        $day = $snapshot['observed_on'];
        $stats = ['rows' => 0, 'matched' => 0, 'new_tracks' => 0, 'new_artists' => 0];

        $this->db->transaction(function () use ($snapshot, $source, $cid, $day, &$stats) {
            // Un nouvel import du même classement le même jour remplace le précédent
            $this->db->run('DELETE FROM chart_observations WHERE source = ? AND country_id = ? AND observed_on = ?', [$source, $cid, $day]);
            foreach ($snapshot['rows'] as $row) {
                $title = trim((string) $row['title']);
                $artist = trim((string) $row['artist']);
                if ($title === '' || $artist === '' || (int) $row['position'] < 1) {
                    continue;
                }
                $trackId = $this->findOrCreateTrack($row, $source, $cid, $stats);
                $this->db->run(
                    'INSERT INTO chart_observations (source, country_id, observed_on, position, track_id, raw_title, raw_artist) VALUES (?, ?, ?, ?, ?, ?, ?)
                     ON DUPLICATE KEY UPDATE track_id = VALUES(track_id), raw_title = VALUES(raw_title), raw_artist = VALUES(raw_artist)',
                    [$source, $cid, $day, (int) $row['position'], $trackId, mb_substr($title, 0, 255), mb_substr($artist, 0, 255)]
                );
                $stats['rows']++;
            }
            $this->refreshGuessedCountries();
        });

        Audit::log($userId, 'import.chart', 'country_source', "{$country['code']}:$source:$day", null, $stats);
        return $stats;
    }

    /**
     * Crée ou retrouve un titre (et son artiste) sans enregistrer de position de classement :
     * artistes suivis, chaînes de labels. Retourne [id du titre, statistiques].
     */
    public function upsertTrack(array $row, string $source, int $countryId): array
    {
        $stats = ['rows' => 1, 'matched' => 0, 'new_tracks' => 0, 'new_artists' => 0];
        return [$this->findOrCreateTrack($row, $source, $countryId, $stats), $stats];
    }

    private function findOrCreateTrack(array $row, string $source, int $cid, array &$stats): int
    {
        // Une source peut indiquer la plateforme de ses identifiants (tendances YouTube : identifiant de vidéo youtube)
        $platform = $row['platform'] ?? (in_array($source, self::PLATFORMS, true) ? $source : null);
        $platform = in_array($platform, self::PLATFORMS, true) ? $platform : null;
        $externalId = isset($row['external_id']) && $row['external_id'] !== '' ? (string) $row['external_id'] : null;

        if ($platform && $externalId) {
            $id = $this->db->value('SELECT track_id FROM track_platform_ids WHERE platform = ? AND external_id = ?', [$platform, $externalId]);
            if ($id) {
                $stats['matched']++;
                return (int) $id;
            }
        }

        $key = Normalizer::trackKey($row['title'], $row['artist']);
        $trackId = $this->db->value('SELECT id FROM tracks WHERE match_key = ? LIMIT 1', [$key]);
        if (!$trackId) {
            // Titres saisis avant l'import (sans clé) : comparaison sur le nom
            foreach ($this->db->all(
                'SELECT t.id, t.title, a.name FROM tracks t JOIN artists a ON a.id = t.artist_id WHERE t.match_key IS NULL AND a.match_key IS NULL AND a.name LIKE ?',
                [Normalizer::primaryArtist($row['artist']) . '%']
            ) as $candidate) {
                if (Normalizer::trackKey($candidate['title'], $candidate['name']) === $key) {
                    $trackId = (int) $candidate['id'];
                    $this->db->update('tracks', ['match_key' => $key], 'id = :id', ['id' => $trackId]);
                    break;
                }
            }
        }

        if ($trackId) {
            $stats['matched']++;
        } else {
            $artistId = $this->findOrCreateArtist($row['artist'], $cid, $stats);
            $trackId = $this->db->insert('tracks', [
                'title'        => mb_substr(trim($row['title']), 0, 200),
                'slug'         => $this->uniqueSlug('tracks', slugify(Normalizer::primaryArtist($row['artist']) . ' ' . $row['title'])),
                'artist_id'    => $artistId,
                'featuring'    => ($f = Normalizer::featuring($row['artist'])) ? mb_substr($f, 0, 255) : null,
                'release_date' => !empty($row['release_date']) ? substr($row['release_date'], 0, 10) : null,
                'cover_url'    => !empty($row['image']) && str_starts_with($row['image'], 'https://') ? $row['image'] : null,
                'match_key'    => $key,
            ]);
            $stats['new_tracks']++;
        }

        if ($platform && $externalId) {
            $this->db->run(
                "INSERT IGNORE INTO track_platform_ids (track_id, platform, external_id, kind, url, published_at, match_status)
                 VALUES (?, ?, ?, ?, ?, ?, 'auto')",
                [$trackId, $platform, mb_substr($externalId, 0, 191), $row['kind'] ?? 'main', $row['url'] ?? null, !empty($row['release_date']) ? substr($row['release_date'], 0, 10) : null]
            );
        }
        return (int) $trackId;
    }

    private function findOrCreateArtist(string $artistField, int $cid, array &$stats): int
    {
        $name = Normalizer::primaryArtist($artistField);
        $key = Normalizer::artistKey($artistField);
        $id = $this->db->value('SELECT id FROM artists WHERE match_key = ? LIMIT 1', [$key]);
        if (!$id) {
            foreach ($this->db->all('SELECT id, name FROM artists WHERE match_key IS NULL AND name LIKE ?', [mb_substr($name, 0, 3) . '%']) as $a) {
                if (Normalizer::artistKey($a['name']) === $key) {
                    $id = (int) $a['id'];
                    $this->db->update('artists', ['match_key' => $key], 'id = :id', ['id' => $id]);
                    break;
                }
            }
        }
        if ($id) {
            return (int) $id;
        }
        $stats['new_artists']++;
        return $this->db->insert('artists', [
            'name'                  => mb_substr($name, 0, 150),
            'slug'                  => $this->uniqueSlug('artists', slugify($name)),
            'submission_country_id' => $cid,   // provisoire : l'artiste reste en attente tant que le pays n'est pas confirmé
            'status'                => 'pending',
            'guessed_country_id'    => $cid,
            'match_key'             => $key,
        ]);
    }

    /** Pays suggéré d'un artiste en attente : celui dont les classements le citent le plus souvent. */
    private function refreshGuessedCountries(): void
    {
        $this->db->run(
            "UPDATE artists a JOIN (
                SELECT t.artist_id, o.country_id, COUNT(*) AS n,
                    ROW_NUMBER() OVER (PARTITION BY t.artist_id ORDER BY COUNT(*) DESC, o.country_id) AS rk
                FROM chart_observations o JOIN tracks t ON t.id = o.track_id GROUP BY t.artist_id, o.country_id
             ) best ON best.artist_id = a.id AND best.rk = 1
             SET a.guessed_country_id = best.country_id
             WHERE a.status = 'pending'"
        );
    }

    /**
     * Lignes CSV collées dans l'admin : "position;titre;artiste" (ou tabulation), un titre par ligne.
     * La position peut être omise : l'ordre des lignes fait foi.
     */
    public static function parseCsv(string $text): array
    {
        $rows = [];
        $n = 0;
        foreach (preg_split('/\R/', trim($text)) as $line) {
            if (trim($line) === '') {
                continue;
            }
            $cols = array_map('trim', preg_split('/\t|;/', $line));
            $n++;
            if (count($cols) >= 3 && ctype_digit($cols[0])) {
                [$pos, $title, $artist] = $cols;
                $external = $cols[3] ?? null;
            } elseif (count($cols) >= 2) {
                [$title, $artist] = $cols;
                $pos = $n;
                $external = $cols[2] ?? null;
            } else {
                throw new \InvalidArgumentException("Ligne $n illisible : « $line »");
            }
            $rows[] = ['position' => (int) $pos, 'title' => $title, 'artist' => $artist, 'external_id' => $external ?: null];
        }
        return $rows;
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
