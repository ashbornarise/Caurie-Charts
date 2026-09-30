<?php

namespace Cauri\Services\Import;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Services\AI\AiClient;
use Cauri\Services\AI\AiFactory;
use Cauri\Services\Audit;
use Cauri\Services\Platforms\HttpClient;

/**
 * Classe automatiquement les artistes découverts par l'import, pour qu'un humain n'ait plus
 * à valider des centaines de lignes : seuls les cas incertains restent en attente.
 *
 * 1. MusicBrainz (encyclopédie musicale ouverte, sans clé) : pays de l'artiste quand le nom est sans ambiguïté.
 * 2. Sinon, Claude avec recherche web : nationalité et pays où la carrière est basée, sources à l'appui.
 *
 * Règle du classement (METHODOLOGIE.md) : c'est le pays où l'artiste mène sa carrière qui fait foi.
 * Décision automatique seulement au-dessus du seuil de confiance (config/ai.php) ; chaque décision
 * est journalisée (audit_log) avec sa justification et reste modifiable dans l'admin.
 */
final class ArtistClassifier
{
    private const MB = 'https://musicbrainz.org/ws/2/artist?fmt=json&limit=5&query=';

    private array $evidenceCache = [];
    private int $searchesLeft = 15; // recherches YouTube par nom (100 unités chacune) par passage

    public function __construct(private Database $db, private HttpClient $http, private ?AiClient $ai = null)
    {
    }

    /** @return array{checked:int, active:int, out_of_scope:int, pending:int, ai_calls:int} */
    public function run(int $limit = 60): array
    {
        $cfg = Config::get('ai.classify');
        $covered = array_column($this->db->all('SELECT id, code FROM countries WHERE is_active = 1'), 'id', 'code');
        $artists = $this->db->all(
            "SELECT a.id, a.name, c.code AS guessed FROM artists a LEFT JOIN countries c ON c.id = a.guessed_country_id
             WHERE a.status = 'pending' AND (a.origin_checked_at IS NULL OR a.origin_checked_at < NOW() - INTERVAL 30 DAY)
             ORDER BY a.origin_checked_at IS NOT NULL, a.fans DESC, a.id LIMIT " . max(0, $limit)
        );
        $stats = ['checked' => 0, 'active' => 0, 'out_of_scope' => 0, 'pending' => 0, 'ai_calls' => 0];
        $aiLeft = (int) $cfg['max_ai_calls'];

        $wikidata = new WikidataLookup($this->http);
        foreach ($artists as $a) {
            $verdict = self::combine($this->musicBrainz($a['name']), $wikidata->find($a['name']));
            $needsAi = $verdict === null || $verdict['confidence'] < (float) $cfg['threshold'];
            if ($needsAi && $this->ai?->isAvailable() && $aiLeft <= 0) {
                continue; // quota IA du passage épuisé : l'artiste sera examiné au prochain passage
            }
            if ($needsAi && $this->ai?->isAvailable() && $aiLeft > 0) {
                $verdict = $this->askAi((int) $a['id'], $a['name']);
                $aiLeft--;
                $stats['ai_calls']++;
            }
            $decision = self::decide($verdict, array_keys($covered), (float) $cfg['threshold']);
            // Garde-fou diaspora : un pays de distribution ou de revenus (France, États-Unis…) n'écarte pas
            // un artiste dont la scène (chaîne YouTube, vidéos, réseau) pointe vers un des cinq pays
            if ($decision === 'out_of_scope' && in_array($verdict['base_country'] ?? '', SceneSignals::PAYOUT_COUNTRIES, true)) {
                $evidence = $this->evidence((int) $a['id'], $a['name']);
                $scene = $evidence['scene_country'] ?? $evidence['related_country'] ?? null;
                if ($scene && isset($covered[$scene])) {
                    $decision = 'pending';
                    $verdict['base_country'] = $scene;
                    $verdict['confidence'] = 0.6;
                    $verdict['note'] = "Possible artiste de la diaspora : pays déclaré {$verdict['nationality']}, mais sa scène pointe vers "
                        . country_name($scene) . ' (' . $evidence['summary'] . '). ' . $verdict['note'];
                }
            }
            $data = [
                'origin_checked_at' => gmdate('Y-m-d H:i:s'),
                'origin_country'    => $verdict['nationality'] ?? null,
                'base_country'      => $verdict['base_country'] ?? null,
                'origin_source'     => $verdict['source'] ?? null,
                'origin_confidence' => isset($verdict['confidence']) ? round((float) $verdict['confidence'], 2) : null,
                'origin_note'       => isset($verdict['note']) ? mb_substr($verdict['note'], 0, 1000) : null,
            ];
            if ($decision === 'active') {
                $data['status'] = 'active';
                $data['submission_country_id'] = $covered[$verdict['base_country']];
            } elseif ($decision === 'out_of_scope') {
                $data['status'] = 'out_of_scope';
            }
            $this->db->update('artists', $data, 'id = :id', ['id' => $a['id']]);
            if ($decision !== 'pending') {
                Audit::log(null, 'artist.auto_classify', 'artist', (int) $a['id'], $data['origin_note'], $data);
            }
            $stats['checked']++;
            $stats[$decision]++;
        }
        return $stats;
    }

    /**
     * active : carrière basée dans un pays couvert ; out_of_scope : basée ailleurs ; pending : incertain.
     * Un artiste d'un pays couvert installé à l'étranger (diaspora) reste en attente : c'est à l'équipe de trancher.
     */
    public static function decide(?array $verdict, array $coveredCodes, float $threshold): string
    {
        if (!$verdict || ($verdict['confidence'] ?? 0) < $threshold || empty($verdict['base_country'])) {
            return 'pending';
        }
        $base = strtoupper($verdict['base_country']);
        if (in_array($base, $coveredCodes, true)) {
            return 'active';
        }
        $nationality = strtoupper((string) ($verdict['nationality'] ?? ''));
        return in_array($nationality, $coveredCodes, true) ? 'pending' : 'out_of_scope';
    }

    /**
     * Recoupe MusicBrainz et Wikidata : d'accord → confiance renforcée ; en désaccord → pas de décision.
     * Une seule des deux sources → son verdict tel quel.
     */
    public static function combine(?array $mb, ?array $wd): ?array
    {
        if ($mb && $wd) {
            if ($mb['base_country'] !== $wd['base_country']) {
                return ['nationality' => null, 'base_country' => null, 'confidence' => 0.0, 'source' => 'musicbrainz+wikidata',
                        'note' => 'Sources en désaccord. ' . $mb['note'] . ' ; ' . $wd['note']];
            }
            return array_merge($wd, ['confidence' => 0.95, 'source' => 'musicbrainz+wikidata', 'note' => $mb['note'] . ' ; ' . $wd['note']]);
        }
        return $mb ?? $wd;
    }

    /** Pays MusicBrainz si un seul artiste porte exactement ce nom (ou si tous les homonymes ont le même pays). */
    private function musicBrainz(string $name): ?array
    {
        usleep(1_100_000); // MusicBrainz : une requête par seconde au plus
        try {
            $response = $this->http->request('GET', self::MB . rawurlencode('artist:"' . $name . '"'), [
                'User-Agent' => 'CauriCharts/1.0 ( ' . Config::get('app.url') . ' )',
                'Accept'     => 'application/json',
            ]);
        } catch (\Throwable) {
            return null;
        }
        $data = json_decode($response['body'], true);
        $key = Normalizer::text($name);
        $countries = [];
        foreach ($data['artists'] ?? [] as $r) {
            if (($r['score'] ?? 0) >= 95 && Normalizer::text($r['name'] ?? '') === $key && !empty($r['country'])) {
                // Fiche incohérente (pays d'origine différent du pays actuel) : on ne tranche pas
                $begin = $r['begin-area'] ?? null;
                if ($begin && ($begin['type'] ?? '') === 'Country' && ($begin['name'] ?? '') !== ($r['area']['name'] ?? '')) {
                    return null;
                }
                $countries[$r['country']] = $r['id'];
            }
        }
        if (count($countries) !== 1) {
            return null; // inconnu ou homonymes de pays différents
        }
        $code = array_key_first($countries);
        return [
            'nationality'  => $code,
            'base_country' => $code,
            'confidence'   => 0.9,
            'source'       => 'musicbrainz',
            'note'         => 'MusicBrainz : https://musicbrainz.org/artist/' . $countries[$code],
        ];
    }

    private function askAi(int $artistId, string $name): ?array
    {
        $seen = $this->db->all(
            "SELECT DISTINCT t.title, o.source, c.code FROM chart_observations o JOIN tracks t ON t.id = o.track_id
             JOIN countries c ON c.id = o.country_id WHERE t.artist_id = ? ORDER BY o.position LIMIT 8",
            [$artistId]
        );
        $context = implode("\n", array_map(fn ($s) => "- « {$s['title']} » ({$s['source']}, classement {$s['code']})", $seen));

        // Indices collectés gratuitement par le site : l'IA ne fait que les juger
        $ev = $this->evidence($artistId, $name);
        $channel = $ev['channel'];
        $wiki = $ev['wiki'];
        $evidence = $ev['lines'];

        $system = "Tu es documentaliste musical pour un classement de l'Afrique de l'Ouest. Tu identifies le pays d'un artiste musical "
            . "à partir des indices fournis et de tes connaissances. Tu ne devines jamais : si tu ne connais pas cet artiste avec certitude "
            . "et que les indices ne suffisent pas, mets confidence à 0.5 ou moins. Attention aux homonymes. "
            . "Important : beaucoup d'artistes africains déclarent sur les plateformes un pays de distribution ou de perception des revenus "
            . "(France, États-Unis, Royaume-Uni…). Ce pays déclaré n'est PAS leur pays : retiens le pays de la scène à laquelle ils appartiennent "
            . "(origine, public, langue, collaborations, label local, marqueurs comme 228, Lomé, Abidjan, 225, Dakar…). Réponds uniquement par un objet JSON.";
        $prompt = "Artiste : « $name »\nTitres repérés dans les classements des plateformes :\n$context\n\n"
            . "Indices :\n" . ($evidence ? '- ' . implode("\n- ", $evidence) : '(aucun indice trouvé)') . "\n\n"
            . "Réponds en JSON : {\"nationality\": code ISO pays ou null, \"base_country\": code ISO du pays où se "
            . "déroule principalement sa carrière musicale (label, scène, résidence) ou null, \"confidence\": nombre de 0 à 1, "
            . "\"reason\": une phrase en français qui cite l'indice utilisé}";
        try {
            $answer = $this->ai->ask($system, $prompt, 1200, 3);
        } catch (\Throwable) {
            return null;
        }
        $json = AiFactory::json($answer['text']);
        if (!$json) {
            return null;
        }
        $iso = fn ($v) => is_string($v) && preg_match('/^[A-Za-z]{2}$/', $v) ? strtoupper($v) : null;
        $verdict = [
            'nationality'  => $iso($json['nationality'] ?? null),
            'base_country' => $iso($json['base_country'] ?? null),
            'confidence'   => max(0, min(1, (float) ($json['confidence'] ?? 0))),
            'source'       => 'ia',
            'note'         => trim(($json['reason'] ?? '') . ' Sources : ' . implode(' ', array_filter(array_merge(
                $channel ? ['https://www.youtube.com/channel/' . $channel['id']] : [],
                array_column($wiki, 'url'),
                array_slice($answer['sources'], 0, 3)
            )))),
        ];
        return self::corroborate($verdict, $channel['country'] ?? null, implode(' ', array_column($wiki, 'snippet')), $ev['scene_country'], $ev['related_country']);
    }

    /**
     * Garde-fou anti-invention : l'IA ne décide seule que si sa réponse est confirmée par un indice collecté
     * (pays de la chaîne YouTube ou gentilé dans Wikipédia). Sinon sa confiance est plafonnée sous le seuil :
     * l'artiste reste pour l'équipe, avec la suggestion de l'IA.
     */
    public static function corroborate(array $verdict, ?string $channelCountry, string $wikiText, ?string $sceneCountry = null, ?string $relatedCountry = null): array
    {
        $base = $verdict['base_country'];
        $confirmed = $base && (
            ($channelCountry && strtoupper($channelCountry) === $base)
            || ($wikiText !== '' && WikidataLookup::demonym($wikiText) === $base)
            || $sceneCountry === $base      // marqueurs locaux dans sa chaîne et ses vidéos
            || $relatedCountry === $base    // artistes proches (Deezer) confirmés dans ce pays
        );
        if (!$confirmed) {
            $verdict['confidence'] = min($verdict['confidence'], 0.8);
            $verdict['note'] = 'Suggestion IA non recoupée. ' . $verdict['note'];
        }
        return $verdict;
    }

    /**
     * Indices publics sur l'artiste, collectés gratuitement :
     * chaîne YouTube (pays déclaré, description, titres et descriptions des 15 dernières vidéos),
     * Wikipédia, artistes proches sur Deezer déjà confirmés dans un pays, et marqueurs de scène.
     */
    private function evidence(int $artistId, string $name): array
    {
        if (isset($this->evidenceCache[$artistId])) {
            return $this->evidenceCache[$artistId];
        }
        $channel = $this->youtubeChannel($artistId, $name);
        $wiki = $this->wikipedia($name);
        [$relatedCountry, $relatedNames] = $this->related($artistId);
        $titles = implode(' ', array_column($this->db->all('SELECT title FROM tracks WHERE artist_id = ? LIMIT 20', [$artistId]), 'title'));
        $scores = SceneSignals::score(implode(' ', [
            $channel['description'] ?? '', $channel['uploads'] ?? '', implode(' ', array_column($wiki, 'snippet')), $titles,
        ]));
        $sceneCountry = SceneSignals::dominant($scores);

        $lines = [];
        if ($channel) {
            $declared = $channel['country'] ?: 'non renseigné';
            $lines[] = "Chaîne YouTube « {$channel['title']} » : pays déclaré = $declared"
                . (in_array($channel['country'], SceneSignals::PAYOUT_COUNTRIES, true) ? ' (souvent un pays de distribution, pas l’origine)' : '')
                . ($channel['description'] ? ' ; description : ' . mb_substr($channel['description'], 0, 300) : '');
            if (!empty($channel['uploads'])) {
                $lines[] = 'Dernières vidéos de la chaîne : ' . mb_substr($channel['uploads'], 0, 500);
            }
        }
        foreach ($wiki as $w) {
            $lines[] = "Wikipédia ({$w['lang']}) « {$w['title']} » : {$w['snippet']}";
        }
        if ($relatedNames) {
            $lines[] = 'Artistes proches sur Deezer (pays confirmé) : ' . implode(', ', $relatedNames);
        }
        if ($scores) {
            $lines[] = 'Marqueurs de scène relevés (villes, indicatifs, langues) : '
                . implode(', ', array_map(fn ($c, $n) => "$c $n", array_keys($scores), $scores));
        }
        $summary = implode(' ; ', array_filter([
            $sceneCountry ? "marqueurs locaux $sceneCountry" : null,
            $relatedCountry ? "artistes proches $relatedCountry" : null,
        ]));
        return $this->evidenceCache[$artistId] = [
            'channel'         => $channel,
            'wiki'            => $wiki,
            'lines'           => $lines,
            'scene_country'   => $sceneCountry,
            'related_country' => $relatedCountry,
            'summary'         => $summary ?: 'indices faibles',
        ];
    }

    /** Pays majoritaire parmi les artistes proches (Deezer) déjà confirmés : [code ou null, noms cités]. */
    private function related(int $artistId): array
    {
        $deezerId = $this->db->value('SELECT deezer_id FROM artists WHERE id = ?', [$artistId]);
        if (!$deezerId) {
            return [null, []];
        }
        try {
            $data = json_decode($this->http->request('GET', 'https://api.deezer.com/artist/' . (int) $deezerId . '/related?limit=25')['body'], true);
        } catch (\Throwable) {
            return [null, []];
        }
        $counts = [];
        $names = [];
        foreach ($data['data'] ?? [] as $r) {
            $known = $this->db->one(
                "SELECT c.code FROM artists a JOIN countries c ON c.id = a.submission_country_id WHERE a.match_key = ? AND a.status = 'active' LIMIT 1",
                [Normalizer::artistKey((string) $r['name'])]
            );
            if ($known) {
                $counts[$known['code']] = ($counts[$known['code']] ?? 0) + 1;
                $names[] = $r['name'] . ' (' . $known['code'] . ')';
            }
        }
        arsort($counts);
        $top = array_key_first($counts);
        $total = array_sum($counts);
        return [$top && $counts[$top] >= 2 && $counts[$top] >= 0.6 * $total ? $top : null, array_slice($names, 0, 8)];
    }

    /**
     * Chaîne YouTube de l'artiste : via un de ses clips (1 unité), sinon par une recherche de son nom
     * (100 unités, nombre limité par passage). Puis description et 15 dernières vidéos (2 unités).
     */
    private function youtubeChannel(int $artistId, string $name): ?array
    {
        $key = \Cauri\Core\Env::get('YOUTUBE_API_KEY');
        if ($key === '') {
            return null;
        }
        $api = 'https://www.googleapis.com/youtube/v3/';
        // Chaque appel est décompté du quota YouTube partagé (réserve gardée pour le relevé des vues)
        $get = fn (string $path, int $cost = 1) => \Cauri\Services\Platforms\YouTubeQuota::spend($this->db, $cost)
            ? json_decode($this->http->request('GET', $api . $path . '&key=' . rawurlencode($key))['body'], true)
            : [];
        try {
            $video = $this->db->value(
                "SELECT p.external_id FROM track_platform_ids p JOIN tracks t ON t.id = p.track_id WHERE t.artist_id = ? AND p.platform = 'youtube' LIMIT 1",
                [$artistId]
            );
            $channelId = $video ? ($get('videos?part=snippet&id=' . rawurlencode($video))['items'][0]['snippet']['channelId'] ?? null) : null;
            if (!$channelId && $this->searchesLeft > 0) {
                $this->searchesLeft--;
                foreach ($get('search?part=snippet&type=video&maxResults=5&q=' . rawurlencode($name), 100)['items'] ?? [] as $item) {
                    if (str_contains(Normalizer::text($item['snippet']['title'] . ' ' . $item['snippet']['channelTitle']), Normalizer::text($name))) {
                        $channelId = $item['snippet']['channelId'];
                        break;
                    }
                }
            }
            if (!$channelId) {
                return null;
            }
            $c = $get('channels?part=snippet,contentDetails&id=' . rawurlencode($channelId))['items'][0] ?? null;
            if (!$c) {
                return null;
            }
            $uploads = '';
            if ($playlist = $c['contentDetails']['relatedPlaylists']['uploads'] ?? null) {
                foreach ($get('playlistItems?part=snippet&maxResults=15&playlistId=' . rawurlencode($playlist))['items'] ?? [] as $it) {
                    $uploads .= ' | ' . $it['snippet']['title'] . ' — ' . mb_substr((string) $it['snippet']['description'], 0, 160);
                }
            }
        } catch (\Throwable) {
            return null;
        }
        $s = $c['snippet'];
        return [
            'id'          => $channelId,
            'title'       => (string) ($s['title'] ?? ''),
            'country'     => $s['country'] ?? null,
            'description' => trim((string) ($s['description'] ?? '')),
            'uploads'     => trim($uploads, ' |'),
        ];
    }

    /** Extraits Wikipédia (français puis anglais) qui parlent d'un artiste de ce nom. */
    private function wikipedia(string $name): array
    {
        $out = [];
        foreach (['fr' => 'musique', 'en' => 'music'] as $lang => $word) {
            try {
                $r = $this->http->request('GET', "https://$lang.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch="
                    . rawurlencode('"' . $name . '" ' . $word), ['User-Agent' => 'CauriCharts/1.0 ( ' . Config::get('app.url') . ' )']);
            } catch (\Throwable) {
                continue;
            }
            foreach (json_decode($r['body'], true)['query']['search'] ?? [] as $s) {
                if (!str_contains(Normalizer::text($s['title'] . ' ' . strip_tags($s['snippet'])), Normalizer::text($name))) {
                    continue;
                }
                $out[] = [
                    'lang'    => $lang,
                    'title'   => $s['title'],
                    'snippet' => trim(html_entity_decode(strip_tags($s['snippet']), ENT_QUOTES, 'UTF-8')),
                    'url'     => "https://$lang.wikipedia.org/wiki/" . rawurlencode(str_replace(' ', '_', $s['title'])),
                ];
            }
        }
        return array_slice($out, 0, 4);
    }
}
