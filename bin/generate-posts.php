<?php

/**
 * Posts réseaux sociaux automatiques, trois fois par semaine (cron : lundi, mercredi, vendredi à 7 h).
 * Chaque post est un brouillon (texte + visuels carré et story) à relire avant publication.
 *
 *   php bin/generate-posts.php                  thème du jour (lundi classement, mercredi artiste, vendredi week-end)
 *   php bin/generate-posts.php --theme=artiste
 *   php bin/generate-posts.php --all            les trois thèmes (aperçu)
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Services\AI\AiFactory;
use Cauri\Services\Platforms\CurlHttpClient;
use Cauri\Services\Social\PostGenerator;
use Cauri\Services\Social\PostImage;

$opts = cli_options($argv);

cli_run('generate-posts', function () use ($opts) {
    $days = Config::get('ai.social.days');
    $themes = !empty($opts['all']) ? array_values($days)
        : (!empty($opts['theme']) ? [$opts['theme']] : array_filter([$days[(int) date('N')] ?? null]));
    if (!$themes) {
        cli_out('Pas de post prévu aujourd’hui (lundi, mercredi et vendredi).');
        return;
    }
    $ai = AiFactory::make();
    $generator = new PostGenerator(Database::connection(), $ai);
    foreach ($themes as $theme) {
        $post = $generator->generate($theme);
        if (!$post) {
            cli_out("[$theme] pas assez de données réelles pour ce thème, aucun post créé.");
            continue;
        }
        cli_out(str_repeat('─', 60));
        cli_out("[$theme] {$post['title']}" . ($ai ? '' : ' (texte modèle : ajouter GEMINI_API_KEY, gratuite, pour la rédaction IA)'));
        cli_out($post['caption']);
        cli_out($post['hashtags']);
        if (!empty($post['folder'])) {
            cli_out('Dossier : ' . $post['folder']);
        }
        foreach (['image_square', 'image_story'] as $k) {
            if ($post[$k]) {
                cli_out('Visuel : ' . BASE_PATH . PostImage::DIR . '/' . $post[$k]);
            }
        }
    }
});
