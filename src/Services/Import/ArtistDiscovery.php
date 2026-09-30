<?php

namespace Cauri\Services\Import;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Core\Env;
use Cauri\Services\Audit;
use Cauri\Services\Platforms\HttpClient;

/**
 * Découverte des artistes de chaque pays, y compris ceux qui n'apparaissent dans aucun classement
 * de plateforme (Togo, Bénin surtout). Gratuit, sans clé payante :
 * 1. Wikidata : musiciens, chanteurs, rappeurs ayant la nationalité du pays (avec leur chaîne YouTube
 *    et leur profil Deezer quand Wikidata les connaît) → confirmés directement (nationalité unique) ;
 * 2. réseau Deezer : artistes « proches » des artistes déjà confirmés du pays → vérifiés ensuite
 *    par ArtistClassifier (scène, diaspora) et proposés à l'équipe avec leurs chiffres.
 * Seuls les candidats avec une vraie fanbase (fans Deezer ou abonnés YouTube, config/discovery.php)
 * entrent au catalogue, avec leurs 10 titres les plus écoutés sur Deezer.
 */
final class ArtistDiscovery
{
    private const SEEDS_CACHE = '/storage/cache/discovery-seeds.json';
    /** Candidats écartés (fanbase insuffisante, aucun titre) : pas revérifiés pendant 30 jours. */
    private const REJECTED_CACHE = '/storage/cache/discovery-rejected.json';

    private array $rejected = [];

    private int $budget;
    private array $cfg;

    public function __construct(private Database $db, private HttpClient $http)
    {
        $this->cfg = Config::get('discovery');
        $this->budget = (int) $this->cfg['max_new_per_run'];
    }

    /** @return list<string> compte rendu */
    public function run(): array
    {
        $file = BASE_PATH . self::REJECTED_CACHE;
        $this->rejected = is_file($file) ? (json_decode((string) file_get_contents($file), true) ?: []) : [];
        $limit = date('Y-m-d', strtotime('-30 days'));
        $this->rejected = array_filter($this->rejected, fn ($d) => $d >= $limit);
        $report = [];
        $countries = array_column($this->db->all('SELECT id, code FROM countries WHERE is_active = 1'), 'id', 'code');
        $order = array_unique(array_merge($this->cfg['priority'], array_keys($countries)));

        // Chaque pays a sa part du budget, pour Wikidata puis pour le réseau Deezer : aucun pays n'est oublié.
        // Ce qu'un pays n'utilise pas passe au suivant.
        $order = array_values(array_filter($order, fn ($c) => isset($countries[$c])));
        $share = intdiv((int) $this->cfg['max_new_per_run'], 2 * max(1, count($order)));
        $left = 0;
        foreach (['wikidata', 'network'] as $phase) {
            foreach ($order as $code) {
                $this->budget = $share + $left;
                if ($phase === 'wikidata' && isset($this->cfg['wikidata_countries'][$code])) {
                    $report[] = "$code Wikidata : " . $this->wikidata($code, (int) $countries[$code]);
                } elseif ($phase === 'network') {
                    $report[] = "$code réseau Deezer : " . $this->network($code, (int) $countries[$code]);
                }
                $left = max(0, $this->budget);
            }
        }
        $report[] = 'Abonnés YouTube mis à jour : ' . $this->refreshSubscribers();
        $report[] = 'Profils Spotify trouvés (Wikidata) : ' . $this->spotifyIds();
        @mkdir(dirname($file), 0775, true);
        file_put_contents($file, json_encode($this->rejected));
        return $report;
    }

    /** Artistes de nationalité $code sur Wikidata. */
    private function wikidata(string $code, int $countryId): string
    {
        $qid = $this->cfg['wikidata_countries'][$code];
        $sparql = 'SELECT ?p ?pLabel (SAMPLE(?yt) AS ?yt) (SAMPLE(?dz) AS ?dz) (COUNT(DISTINCT ?nat) AS ?nats) WHERE {
            ?p wdt:P27 wd:' . $qid . ' ; wdt:P27 ?nat .
            ?p wdt:P106 ?occ . VALUES ?occ { wd:Q177220 wd:Q2252262 wd:Q639669 wd:Q753110 wd:Q130857 wd:Q183945 wd:Q488205 wd:Q36834 wd:Q855091 }
            OPTIONAL { ?p wdt:P2397 ?yt } OPTIONAL { ?p wdt:P2722 ?dz }
            FILTER NOT EXISTS { ?p wdt:P570 ?death }
            SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
        } GROUP BY ?p ?pLabel LIMIT 500';
        try {
            $r = $this->http->request('GET', 'https://query.wikidata.org/sparql?format=json&query=' . rawurlencode($sparql), [
                'User-Agent' => 'CauriCharts/1.0 ( ' . Config::get('app.url') . ' )', 'Accept' => 'application/sparql-results+json',
            ]);
        } catch (\Throwable) {
            return 'Wikidata injoignable';
        }
        $rows = json_decode($r['body'], true)['results']['bindings'] ?? [];
        $added = 0;
        $skipped = 0;
        foreach ($rows as $row) {
            if ($this->budget <= 0) {
                break;
            }
            $label = $row['pLabel']['value'] ?? '';
            if ($label === '' || preg_match('/^Q\d+$/', $label) || isset($this->rejected[$label]) || $this->exists($label)) {
                continue;
            }
            $profile = !empty($row['dz']['value'])
                ? $this->deezer('/artist/' . rawurlencode($row['dz']['value']))
                : ArtistEnricher::bestMatch($this->deezer('/search/artist?limit=10&q=' . rawurlencode($label))['data'] ?? [], $label);
            if (isset($profile['nb_fan']) && !isset($profile['image'])) {
                $profile = ['id' => (int) $profile['id'], 'nb_fan' => (int) $profile['nb_fan'], 'image' => $profile['picture_xl'] ?? null, 'name' => $profile['name'] ?? $label];
            }
            $channel = $row['yt']['value'] ?? null;
            $subs = $channel ? $this->subscribers([$channel])[$channel] ?? null : null;
            if (!$this->hasFanbase($profile['nb_fan'] ?? 0, $subs)) {
                $this->rejected[$label] = date('Y-m-d');
                $skipped++;
                continue;
            }
            $artistId = $this->create($profile['name'] ?? $label, $profile, $countryId);
            if (!$artistId) {
                $this->rejected[$label] = date('Y-m-d');
                $skipped++;
                continue;
            }
            $single = (int) ($row['nats']['value'] ?? 1) === 1;
            $data = [
                'youtube_channel_id'  => $channel,
                'youtube_subscribers' => $subs,
                'discovered_via'      => 'Wikidata : nationalité ' . country_name($code),
                'origin_country'      => $code,
                'origin_source'       => 'wikidata',
                'origin_note'         => 'Nationalité Wikidata : https://www.wikidata.org/wiki/' . basename($row['p']['value']),
                'origin_checked_at'   => gmdate('Y-m-d H:i:s'),
            ];
            if ($single) {
                // Nationalité unique : confirmé comme par le classement automatique (règle : nationalité = pays de carrière)
                $data += ['status' => 'active', 'submission_country_id' => $countryId, 'base_country' => $code, 'origin_confidence' => 0.9];
            } else {
                $data += ['origin_confidence' => 0.5, 'origin_note' => 'Plusieurs nationalités (diaspora ?) : à vérifier. ' . $data['origin_note']];
            }
            $this->db->update('artists', $data, 'id = :id', ['id' => $artistId]);
            Audit::log(null, 'artist.discovered', 'artist', $artistId, $data['discovered_via'], $data);
            $added++;
        }
        return count($rows) . " fiches, $added ajoutés, $skipped sans fanbase suffisante";
    }

    /** Artistes proches (Deezer) des artistes confirmés du pays, explorés à tour de rôle. */
    private function network(string $code, int $countryId): string
    {
        $cacheFile = BASE_PATH . self::SEEDS_CACHE;
        $explored = is_file($cacheFile) ? (json_decode((string) file_get_contents($cacheFile), true) ?: []) : [];
        $seeds = $this->db->all(
            "SELECT id, name, deezer_id FROM artists WHERE status = 'active' AND submission_country_id = ? AND deezer_id IS NOT NULL
             ORDER BY fans DESC",
            [$countryId]
        );
        // Les moins récemment explorés d'abord ; chacun est réexploré au plus une fois par semaine
        $seeds = array_values(array_filter($seeds, fn ($s) => ($explored[$s['id']] ?? '') < date('Y-m-d', strtotime('-7 days'))));
        $seeds = array_slice($seeds, 0, (int) $this->cfg['seeds_per_run']);
        $added = 0;
        foreach ($seeds as $seed) {
            $explored[$seed['id']] = date('Y-m-d');
            foreach ($this->deezer('/artist/' . (int) $seed['deezer_id'] . '/related?limit=25')['data'] ?? [] as $r) {
                if ($this->budget <= 0) {
                    break 2;
                }
                $name = (string) $r['name'];
                if ($this->exists($name) || !$this->hasFanbase((int) ($r['nb_fan'] ?? 0), null)) {
                    continue;
                }
                $profile = ['id' => (int) $r['id'], 'nb_fan' => (int) $r['nb_fan'], 'image' => $r['picture_xl'] ?? null];
                $artistId = $this->create($name, $profile, $countryId);
                if ($artistId) {
                    // Pays pressenti seulement : vérifié par ArtistClassifier (scène, Wikipédia, IA), puis choisi par l'équipe
                    $this->db->update('artists', [
                        'discovered_via'     => 'Réseau Deezer : proche de ' . $seed['name'] . " ($code)",
                        'guessed_country_id' => $countryId,
                        'origin_checked_at'  => null,
                    ], 'id = :id', ['id' => $artistId]);
                    $added++;
                }
            }
        }
        @mkdir(dirname($cacheFile), 0775, true);
        file_put_contents($cacheFile, json_encode($explored));
        return count($seeds) . " artistes explorés, $added nouveaux candidats";
    }

    /** Ajoute l'artiste et ses 10 titres les plus écoutés sur Deezer. */
    private function create(string $name, ?array $profile, int $countryId): ?int
    {
        if (empty($profile['id'])) {
            return null;
        }
        $top = $this->deezer('/artist/' . (int) $profile['id'] . '/top?limit=10')['data'] ?? [];
        $importer = new ChartImporter($this->db);
        $artistId = null;
        foreach ($top as $t) {
            // Titre dont l'artiste principal est bien celui-ci (pas une simple apparition en invité)
            if (Normalizer::artistKey((string) ($t['artist']['name'] ?? '')) !== Normalizer::artistKey($name)) {
                continue;
            }
            [$trackId] = $importer->upsertTrack([
                'title'       => (string) $t['title'],
                'artist'      => $name,
                'external_id' => (string) $t['id'],
                'url'         => $t['link'] ?? null,
                'image'       => $t['album']['cover_xl'] ?? null,
            ], 'deezer', $countryId);
            $artistId ??= (int) $this->db->value('SELECT artist_id FROM tracks WHERE id = ?', [$trackId]);
        }
        if (!$artistId) {
            return null;
        }
        $this->db->update('artists', [
            'deezer_id' => (int) $profile['id'], 'fans' => (int) $profile['nb_fan'], 'image_url' => $profile['image'] ?? null,
            'profile_checked_at' => gmdate('Y-m-d H:i:s'),
        ], 'id = :id', ['id' => $artistId]);
        $this->budget--;
        return $artistId;
    }

    /**
     * Profils Spotify des artistes : identifiant public (propriété P1902 de Wikidata), pour le badge
     * « Écouter sur Spotify ». Une seule requête pour tous les musiciens des cinq pays (et leurs pseudonymes).
     */
    private function spotifyIds(): int
    {
        $values = implode(' ', array_map(fn ($q) => "wd:$q", $this->cfg['wikidata_countries']));
        $sparql = 'SELECT ?pLabel ?alias ?sp WHERE { VALUES ?c { ' . $values . ' } ?p wdt:P27 ?c ; wdt:P1902 ?sp .
            OPTIONAL { ?p skos:altLabel ?alias FILTER(LANG(?alias) IN ("fr","en")) }
            SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". } }';
        try {
            $r = $this->http->request('GET', 'https://query.wikidata.org/sparql?format=json&query=' . rawurlencode($sparql), [
                'User-Agent' => 'CauriCharts/1.0 ( ' . Config::get('app.url') . ' )', 'Accept' => 'application/sparql-results+json',
            ]);
        } catch (\Throwable) {
            return 0;
        }
        $n = 0;
        foreach (json_decode($r['body'], true)['results']['bindings'] ?? [] as $row) {
            $sp = $row['sp']['value'] ?? '';
            if (!preg_match('/^[A-Za-z0-9]{22}$/', $sp)) {
                continue;
            }
            foreach (array_filter([$row['pLabel']['value'] ?? '', $row['alias']['value'] ?? '']) as $name) {
                $n += $this->db->update('artists', ['spotify_id' => $sp], 'match_key = :k AND spotify_id IS NULL', ['k' => Normalizer::artistKey($name)]);
            }
        }
        return $n;
    }

    /** Abonnés YouTube des chaînes connues (1 unité de quota pour 50 chaînes). */
    private function refreshSubscribers(): int
    {
        $rows = $this->db->all("SELECT id, youtube_channel_id FROM artists WHERE youtube_channel_id IS NOT NULL AND status <> 'out_of_scope' LIMIT 500");
        $n = 0;
        foreach (array_chunk($rows, 50) as $chunk) {
            $subs = $this->subscribers(array_column($chunk, 'youtube_channel_id'));
            foreach ($chunk as $r) {
                if (isset($subs[$r['youtube_channel_id']])) {
                    $this->db->update('artists', ['youtube_subscribers' => $subs[$r['youtube_channel_id']]], 'id = :id', ['id' => $r['id']]);
                    $n++;
                }
            }
        }
        return $n;
    }

    /** @return array<string, int> abonnés par identifiant de chaîne */
    private function subscribers(array $channelIds): array
    {
        $key = Env::get('YOUTUBE_API_KEY');
        if ($key === '' || !$channelIds || !\Cauri\Services\Platforms\YouTubeQuota::spend($this->db, 1)) {
            return [];
        }
        try {
            $r = json_decode($this->http->request('GET', 'https://www.googleapis.com/youtube/v3/channels?part=statistics&id='
                . rawurlencode(implode(',', $channelIds)) . '&key=' . rawurlencode($key))['body'], true);
        } catch (\Throwable) {
            return [];
        }
        $out = [];
        foreach ($r['items'] ?? [] as $item) {
            if (empty($item['statistics']['hiddenSubscriberCount'])) {
                $out[$item['id']] = (int) ($item['statistics']['subscriberCount'] ?? 0);
            }
        }
        return $out;
    }

    private function hasFanbase(int $fans, ?int $subs): bool
    {
        return $fans >= (int) $this->cfg['min_deezer_fans'] || ($subs ?? 0) >= (int) $this->cfg['min_youtube_subs'];
    }

    private function exists(string $name): bool
    {
        return (bool) $this->db->value('SELECT 1 FROM artists WHERE match_key = ?', [Normalizer::artistKey($name)]);
    }

    private function deezer(string $path): array
    {
        usleep(120_000); // limite Deezer : 50 requêtes par 5 secondes
        try {
            $r = $this->http->request('GET', 'https://api.deezer.com' . $path);
        } catch (\Throwable) {
            return [];
        }
        $data = json_decode($r['body'], true);
        return is_array($data) && !isset($data['error']) ? $data : [];
    }
}
