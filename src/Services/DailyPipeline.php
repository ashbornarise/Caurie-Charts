<?php

namespace Cauri\Services;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Services\AI\AiFactory;
use Cauri\Services\Charts\ChartService;
use Cauri\Services\Charts\LiveChart;
use Cauri\Services\Charts\Period;
use Cauri\Services\Import\ArtistClassifier;
use Cauri\Services\Import\ArtistDiscovery;
use Cauri\Services\Import\ArtistEnricher;
use Cauri\Services\Import\ArtistWatch;
use Cauri\Services\Import\ImportService;
use Cauri\Services\News\FeedImporter;
use Cauri\Services\Platforms\CollectService;
use Cauri\Services\Platforms\CurlHttpClient;
use Cauri\Services\Social\PostGenerator;

/**
 * Chaîne quotidienne complète, dans l'ordre où chaque étape a besoin de la précédente :
 *  1. classements des plateformes (Apple Music, Deezer, Shazam, YouTube…) : positions + nouveaux artistes ;
 *  2. liste de suivi et découverte (Wikidata, réseau Deezer) : artistes absents des classements ;
 *  3. profils (photo, fans) puis pays des artistes (MusicBrainz, Wikidata, scène, IA) ;
 *  4. clips YouTube des artistes confirmés, puis relevé quotidien des vues ;
 *  5. sources calculées à partir des artistes suivis (popularité Deezer, vues YouTube) : elles ont besoin
 *     des artistes confirmés et des relevés du jour, d'où leur place en fin de chaîne ;
 *  6. actualités ; 7. le lundi : classement officiel de la semaine (brouillon) ;
 *  8. lundi, mercredi, vendredi : posts réseaux sociaux ; 9. vidage du cache des classements en direct.
 * Une étape en échec est journalisée et n'empêche pas les suivantes.
 */
final class DailyPipeline
{
    /** @var list<array{step:string, ok:bool, seconds:float, lines:list<string>}> */
    private array $report = [];

    public function __construct(private Database $db, private ?\Closure $out = null)
    {
    }

    public function run(bool $forceWeekly = false, bool $forcePosts = false, int $youtubeSearches = 10): array
    {
        $import = new ImportService($this->db);
        $http = new CurlHttpClient(60);
        $platformSources = array_values(array_diff(array_keys($import->sources()), ImportService::COMPUTED));

        $this->step('1. Classements des plateformes', fn () => $import->importAll(null, $platformSources));
        $this->step('2a. Liste de suivi', fn () => (new ArtistWatch($this->db, $http))->run());
        $this->step('2b. Découverte d\'artistes', fn () => (new ArtistDiscovery($this->db, $http))->run());
        $this->step('3a. Profils (photo, fans)', function () use ($http) {
            $p = (new ArtistEnricher($this->db, $http))->run(150);
            return ["{$p['checked']} vérifiés, {$p['found']} trouvés sur Deezer"];
        });
        $this->step('3b. Pays des artistes', function () {
            $c = (new ArtistClassifier($this->db, new CurlHttpClient(20), AiFactory::make()))->run(120);
            return ["{$c['active']} confirmés, {$c['out_of_scope']} hors périmètre, {$c['pending']} à vérifier (IA : {$c['ai_calls']})"];
        });
        $this->step('4a. Titres retrouvés sur Deezer (popularité, pochette)', function () use ($http) {
            $r = (new \Cauri\Services\Import\DeezerTrackMatcher($this->db, $http))->run();
            return ["{$r['matched']} titres retrouvés sur {$r['checked']}"];
        });
        $this->step('4b. Chaînes YouTube des artistes (tous leurs clips, audios, lyrics, lives)', fn () => (new \Cauri\Services\Import\YouTubeChannelSync($this->db, $http))->run());
        $this->step('4c. Clips YouTube des titres restants (recherche titre par titre)', fn () => [json_encode($import->matchYouTube($youtubeSearches), JSON_UNESCAPED_UNICODE)]);
        $this->step('4d. Relevé des vues', function () {
            $r = (new CollectService($this->db, CollectService::clients($this->db)))->run(date('Y-m-d'));
            return array_map(fn ($k, $v) => $k . ' ' . json_encode($v, JSON_UNESCAPED_UNICODE), array_keys($r), $r);
        });
        $this->step('5. Sources calculées (popularité Deezer, vues YouTube)', fn () => $import->importAll(null, ImportService::COMPUTED));
        $this->step('6. Actualités', fn () => (new FeedImporter($this->db))->run());

        if ($forceWeekly || (int) date('N') === 1) {
            $this->step('7. Classement officiel de la semaine (brouillon à publier dans l\'admin)', function () {
                $week = Period::lastCompletedWeek(date('Y-m-d'));
                $service = new ChartService($this->db);
                $lines = [];
                foreach (array_column($this->db->all('SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order'), 'code') as $code) {
                    $r = $service->computeWeek($code, $week->start, null, null);
                    $lines[] = "{$week->key} $code : {$r['tracks_scored']} titres notés, {$r['pending']} à vérifier";
                }
                return $lines;
            });
        }

        $theme = Config::get('ai.social.days')[(int) date('N')] ?? null;
        if ($forcePosts || $theme) {
            $this->step('8. Posts réseaux sociaux', function () use ($forcePosts, $theme) {
                $generator = new PostGenerator($this->db, AiFactory::make());
                $lines = [];
                foreach ($forcePosts ? array_values(Config::get('ai.social.days')) : [$theme] as $t) {
                    $post = $generator->generate($t);
                    $lines[] = $post ? "$t : {$post['title']}" . (!empty($post['folder']) ? " → {$post['folder']}" : '') : "$t : pas assez de données";
                }
                return $lines;
            });
        }

        $this->step('9. Ménage (cache, fichiers orphelins)', function () {
            LiveChart::clearCache();
            return ['cache des classements vidé', PostGenerator::purgeOrphans($this->db) . ' fichiers de posts abandonnés supprimés'];
        });

        Logger::write('cron', 'info', 'pipeline quotidien', array_map(fn ($r) => [$r['step'], $r['ok'], round($r['seconds'], 1)], $this->report));
        return $this->report;
    }

    private function step(string $name, callable $fn): void
    {
        $start = microtime(true);
        $this->say("▶ $name");
        try {
            $lines = array_map('strval', (array) $fn());
            $ok = true;
        } catch (\Throwable $e) {
            Logger::error('pipeline', $e);
            $lines = ['ERREUR : ' . $e->getMessage()];
            $ok = false;
        }
        foreach ($lines as $l) {
            $this->say('   ' . $l);
        }
        $this->report[] = ['step' => $name, 'ok' => $ok, 'seconds' => microtime(true) - $start, 'lines' => $lines];
    }

    private function say(string $line): void
    {
        if ($this->out) {
            ($this->out)($line);
        }
    }
}
