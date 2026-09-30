<?php

namespace Cauri\Services\Social;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Services\AI\AiClient;
use Cauri\Services\AI\AiFactory;
use Cauri\Services\Logger;

/**
 * Génère un post réseaux sociaux (texte + visuels carré et story) à partir de faits réels.
 * Avec ANTHROPIC_API_KEY : texte rédigé par Claude, dans le ton d'un magazine de classements.
 * Sans clé : texte construit à partir d'un modèle, aussi fiable mais moins vivant.
 * Le post est enregistré en brouillon : un humain le relit avant publication.
 */
final class PostGenerator
{
    public function __construct(private Database $db, private ?AiClient $ai = null)
    {
    }

    /** @return array|null le post enregistré, ou null s'il n'y a pas assez de faits */
    public function generate(string $theme, ?string $day = null): ?array
    {
        $day ??= date('Y-m-d');
        $facts = (new PostFacts($this->db))->for($theme);
        if (!$facts) {
            return null;
        }
        $text = null;
        if ($this->ai?->isAvailable()) {
            try {
                $text = $this->write($facts);
            } catch (\Throwable $e) {
                Logger::error('social', $e);
            }
        }
        $text ??= self::template($facts);
        $text['hashtags'] = array_values(array_unique(array_merge(Config::get('ai.social.hashtags_base'), $text['hashtags'] ?? [])));

        $name = $day . '-' . $theme . '-' . substr(bin2hex(random_bytes(4)), 0, 6);
        $images = PostImage::render($facts, $text, $name);
        $cover = self::cover($facts);
        $items = $this->carouselItems($facts);
        $carousel = PostCarousel::render($facts, $cover, $items, $name);
        // Chaque diapositive porte un libellé : couverture, puis « N°1 - Artiste - Titre »… (noms des fichiers exportés)
        $labels = array_merge(
            ['Couverture - ' . $cover['kicker'] . ' ' . $cover['headline']],
            array_map(fn ($it) => 'N°' . $it['rank'] . ' - ' . $it['artist'] . ' - ' . $it['title'], $items)
        );
        $carousel['slides'] = array_map(function ($file, $i) use ($labels, $items) {
            $item = $i > 0 ? ($items[$i - 1] ?? null) : null;
            return [
                'file'    => $file,
                'label'   => $labels[$i] ?? '',
                'clip'    => $item ? PostCarousel::findClip($item) !== null : null,
                'youtube' => $item['youtube_url'] ?? null,
                'expect'  => $item ? $item['artist'] . ' - ' . $item['title'] . '.mp4' : null,
            ];
        }, $carousel['slides'], array_keys($carousel['slides']));

        $row = [
            'slot_date'    => $day,
            'theme'        => $theme,
            'title'        => mb_substr($text['title'], 0, 160),
            'caption'      => $text['caption'],
            'hashtags'     => mb_substr(implode(' ', array_slice($text['hashtags'], 0, 8)), 0, 300),
            'facts'        => json_encode($facts, JSON_UNESCAPED_UNICODE),
            'image_square' => $images['square'] ?? null,
            'image_story'  => $images['story'] ?? null,
            'carousel'     => json_encode($carousel['slides']),
            'video'        => $carousel['video'],
            'status'       => 'draft',
        ];
        // Brouillon remplacé : ses fichiers (visuels, carrousel, calques, vidéo) sont supprimés avec lui
        foreach ($this->db->all('SELECT * FROM social_posts WHERE slot_date = ? AND theme = ? AND status = \'draft\'', [$day, $theme]) as $old) {
            self::deleteFiles($old);
        }
        $this->db->run('DELETE FROM social_posts WHERE slot_date = ? AND theme = ? AND status = \'draft\'', [$day, $theme]);
        $row['id'] = $this->db->insert('social_posts', $row);
        $row['folder'] = PostExport::export($row);
        return $row;
    }

    private function write(array $facts): array
    {
        $system = <<<TXT
Tu es rédacteur en chef social media de Cauri Charts, le classement musical de l'Afrique de l'Ouest (Togo, Bénin, Ghana, Côte d'Ivoire, Sénégal),
dans l'esprit des posts de Billboard : accroche forte dès la première ligne, chiffres mis en avant, fierté pour les artistes, ton enthousiaste mais crédible.
Règles absolues :
- Utilise UNIQUEMENT les faits fournis. N'invente aucun chiffre, aucune position, aucun record, aucune citation, aucune date de sortie.
- Cite toujours d'où viennent les chiffres (champ "source"). Si ce ne sont pas des classements Cauri Charts, ne dis pas « classement Cauri Charts » : dis « dans les classements Apple Music / Deezer / YouTube ».
- Français, 2 à 4 emojis maximum, phrases courtes, lisible sur mobile. Termine par une question qui invite à commenter.
- 3 à 5 hashtags pertinents (artistes, pays, genres), sans #CauriCharts (ajouté automatiquement).
Réponds uniquement par un objet JSON :
{"title": "titre du visuel, 45 caractères max", "lines": ["3 à 5 lignes courtes pour le visuel, 42 caractères max chacune"], "caption": "texte du post, 900 caractères max", "hashtags": ["#..."]}
TXT;
        $answer = $this->ai->ask($system, "Faits (JSON) :\n" . json_encode($facts, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), 1500);
        $json = AiFactory::json($answer['text']);
        if (!$json || empty($json['title']) || empty($json['caption'])) {
            throw new \RuntimeException('Réponse IA inexploitable');
        }
        // Les hashtags vont dans leur champ : on retire ceux que le modèle a laissés en fin de texte
        $caption = trim(preg_replace('/(\s*#[\p{L}\p{N}_]+)+\s*$/u', '', (string) $json['caption']));
        return [
            'title'    => (string) $json['title'],
            'lines'    => array_slice(array_map('strval', (array) ($json['lines'] ?? [])), 0, 5),
            'caption'  => $caption,
            'hashtags' => array_filter(array_map('strval', (array) ($json['hashtags'] ?? [])), fn ($h) => str_starts_with($h, '#')),
        ];
    }

    /** Supprime les fichiers de public/media/social qu'aucun post n'utilise plus. Retourne le nombre supprimé. */
    public static function purgeOrphans(\Cauri\Core\Database $db): int
    {
        $used = [];
        foreach ($db->all('SELECT image_square, image_story, video, carousel FROM social_posts') as $p) {
            $used[] = $p['image_square'];
            $used[] = $p['image_story'];
            $used[] = $p['video'];
            foreach (json_decode((string) ($p['carousel'] ?? '[]'), true) ?: [] as $s) {
                $used[] = is_array($s) ? $s['file'] : $s;
            }
            if ($p['video']) {
                $prefix = pathinfo($p['video'], PATHINFO_FILENAME);
                foreach (glob(BASE_PATH . PostImage::DIR . '/' . $prefix . '-*-calque.png') ?: [] as $c) {
                    $used[] = basename($c);
                }
            }
        }
        $used = array_flip(array_filter(array_map(fn ($f) => $f ? basename($f) : null, $used)));
        $n = 0;
        foreach (glob(BASE_PATH . PostImage::DIR . '/*.{png,jpg,mp4}', GLOB_BRACE) ?: [] as $file) {
            if (!isset($used[basename($file)]) && filemtime($file) < time() - 3600) {
                unlink($file);
                $n++;
            }
        }
        return $n;
    }

    /** Supprime les fichiers générés d'un post (dossier public/media/social). */
    public static function deleteFiles(array $post): void
    {
        $dir = BASE_PATH . PostImage::DIR . '/';
        $files = [$post['image_square'] ?? null, $post['image_story'] ?? null, $post['video'] ?? null];
        foreach (json_decode((string) ($post['carousel'] ?? '[]'), true) ?: [] as $slide) {
            $files[] = is_array($slide) ? $slide['file'] : $slide;
        }
        foreach (array_filter($files) as $f) {
            if (is_file($dir . basename($f))) {
                unlink($dir . basename($f));
            }
        }
        // Calques de clips : même préfixe que la vidéo
        if (!empty($post['video'])) {
            foreach (glob($dir . pathinfo(basename($post['video']), PATHINFO_FILENAME) . '-*-calque.png') ?: [] as $f) {
                unlink($f);
            }
        }
    }

    /** Couverture du carrousel : accroche, titre géant, sous-titre. */
    private static function cover(array $facts): array
    {
        return match ($facts['kind']) {
            'artist'          => ['kicker' => 'Artiste de la semaine', 'headline' => $facts['artist']['name'],
                                  'subtitle' => $facts['artist']['deezer_fans'] ? number_format($facts['artist']['deezer_fans'], 0, ',', ' ') . ' fans sur Deezer' : 'en Afrique de l’Ouest'],
            'cauri_chart'     => ['kicker' => 'Prime Chart', 'headline' => 'Afrique de l’Ouest', 'subtitle' => 'Le Top de la semaine'],
            'platform_trends' => ['kicker' => 'Les titres qui dominent', 'headline' => 'les plateformes', 'subtitle' => 'en Afrique de l’Ouest cette semaine'],
            default           => ['kicker' => 'Ce que l’Afrique de l’Ouest', 'headline' => 'écoute ce week-end', 'subtitle' => 'Les nouvelles entrées des classements'],
        };
    }

    /**
     * Une diapositive par performance, avec un chiffre exact : vues YouTube relevées du titre,
     * sinon sa meilleure position dans un classement de plateforme.
     */
    private function carouselItems(array $facts): array
    {
        $rows = $facts['kind'] === 'artist'
            // Photo de l'artiste plutôt que la pochette (souvent couverte de texte : titre de l'album, mentions)
            ? array_map(fn ($t) => $t + ['artist' => $facts['artist']['name'], 'image' => $facts['image'] ?: $t['image_url']], $facts['tracks'])
            : array_map(fn ($e) => $e + ['image' => $e['image_url'] ?? null], $facts['top']);
        $items = [];
        foreach (array_slice($rows, 0, 7) as $i => $r) {
            $views = isset($r['track_id']) ? $this->db->value(
                "SELECT SUM((SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id ORDER BY s.captured_on DESC LIMIT 1))
                 FROM track_platform_ids p WHERE p.track_id = ? AND p.platform = 'youtube'",
                [(int) $r['track_id']]
            ) : null;
            $best = $r['seen'][0] ?? null;
            [$value, $label] = $views
                ? [number_format((int) $views, 0, ',', ' '), 'vues YouTube']
                : ($best ? ['N°' . $best['position'], $best['platform'] . ' ' . country_name($best['country'])] : ['', '']);
            $items[] = [
                'rank'         => (int) ($r['position'] ?? $i + 1),
                'title'        => $r['title'],
                'artist'       => $r['artist'],
                'image'        => $r['image'],
                'figure_value' => $value,
                'figure_label' => $label,
                // Clip officiel : lien YouTube de référence (pour le demander à l'artiste ou au label)
                'youtube_url'  => isset($r['track_id']) ? $this->db->value(
                    "SELECT url FROM track_platform_ids WHERE track_id = ? AND platform = 'youtube' ORDER BY kind = 'clip' DESC LIMIT 1",
                    [(int) $r['track_id']]
                ) : null,
            ];
        }
        return $items;
    }

    /** Texte sans IA, construit uniquement à partir des faits. */
    public static function template(array $facts): array
    {
        $pos = fn (array $seen) => implode(' · ', array_map(fn ($s) => "{$s['platform']} {$s['country']} n°{$s['position']}", array_slice($seen, 0, 2)));
        $lines = [];
        $body = [];
        switch ($facts['kind']) {
            case 'cauri_chart':
                foreach ($facts['top'] as $e) {
                    $lines[] = "{$e['position']}. {$e['title']} — {$e['artist']}";
                }
                $one = $facts['top'][0];
                $body[] = "🏆 {$one['artist']} est n°1 du Prime Chart Afrique de l’Ouest avec « {$one['title']} ».";
                if ($facts['climber']) {
                    $c = $facts['climber'];
                    $body[] = "📈 Plus forte montée : « {$c['title']} » de {$c['artist']} (+{$c['gain']} places).";
                }
                $body[] = 'Le Top 5 de la semaine :';
                $body = array_merge($body, $lines);
                $body[] = 'Classement complet sur notre site. Votre n°1 à vous, c’est lequel ?';
                break;
            case 'platform_trends':
                foreach ($facts['top'] as $i => $e) {
                    $lines[] = ($i + 1) . ". {$e['title']} — {$e['artist']}";
                    $body[] = ($i + 1) . ". « {$e['title']} » de {$e['artist']} ({$pos($e['seen'])})";
                }
                array_unshift($body, '🔥 Les titres qui dominent les plateformes en Afrique de l’Ouest cette semaine :');
                $body[] = 'D’après les classements Apple Music, Deezer et YouTube. Lequel tourne en boucle chez vous ?';
                break;
            case 'artist':
                $a = $facts['artist'];
                foreach ($facts['tracks'] as $t) {
                    $lines[] = "{$t['title']} — {$pos($t['seen'])}";
                }
                $body[] = "⭐ Artiste de la semaine : {$a['name']}.";
                $body[] = 'Présent cette semaine dans les classements :';
                foreach ($facts['tracks'] as $t) {
                    $body[] = "• « {$t['title']} » : {$pos($t['seen'])}";
                }
                if ($a['deezer_fans']) {
                    $body[] = number_format($a['deezer_fans'], 0, ',', ' ') . ' fans sur Deezer.';
                }
                $body[] = 'Votre titre préféré de ' . $a['name'] . ' ?';
                break;
            default: // weekend
                foreach ($facts['top'] as $e) {
                    $lines[] = "{$e['title']} — {$e['artist']}";
                }
                $body[] = '🎧 Nouveaux dans les classements cette semaine :';
                foreach ($facts['top'] as $e) {
                    $body[] = "• « {$e['title']} » de {$e['artist']} ({$pos($e['seen'])})";
                }
                if (!empty($facts['news'])) {
                    $body[] = '📰 À lire : ' . $facts['news'][0]['title'] . ' (' . $facts['news'][0]['source_name'] . ')';
                }
                $body[] = 'Qu’est-ce qui passe dans vos écouteurs ce week-end ?';
        }
        $body[] = 'Source : ' . $facts['source'] . '.';
        $title = $facts['kind'] === 'artist' ? $facts['artist']['name'] : $facts['headline'];
        return ['title' => $title,'lines' => array_slice($lines, 0, 5), 'caption' => implode("\n", $body), 'hashtags' => []];
    }
}
