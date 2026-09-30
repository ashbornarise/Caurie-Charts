<?php

namespace Cauri\Services\Social;

use Cauri\Core\Env;

/**
 * Copie chaque post dans un dossier facile à parcourir (SOCIAL_EXPORT_DIR, par exemple Documents\Cauri Charts - Posts) :
 * un sous-dossier par post, avec le carrousel numéroté, les visuels carré et story, la vidéo
 * et la légende prête à coller (texte + hashtags). Désactivé si SOCIAL_EXPORT_DIR est vide (serveur).
 */
final class PostExport
{
    private const DAYS = [1 => 'Lundi', 2 => 'Mardi', 3 => 'Mercredi', 4 => 'Jeudi', 5 => 'Vendredi', 6 => 'Samedi', 7 => 'Dimanche'];
    private const THEMES = ['classement' => 'Tendances', 'artiste' => 'Artiste de la semaine', 'weekend' => 'Spécial week-end'];

    public static function export(array $post): ?string
    {
        $root = rtrim(Env::get('SOCIAL_EXPORT_DIR'), '/\\');
        if ($root === '') {
            return null;
        }
        // Rangement : Année \ Semaine NN (du lundi au dimanche) \ JJ-MM Jour - Rubrique - Titre du post
        $ts = strtotime($post['slot_date']);
        $monday = strtotime('monday this week', $ts);
        $week = sprintf('Semaine %02d (%s - %s)', (int) date('W', $ts), self::shortDate($monday), self::shortDate(strtotime('+6 days', $monday)));
        $rubric = self::THEMES[$post['theme']] ?? $post['theme'];
        // Espaces insécables de la typographie française → espaces simples, pour reconnaître la rubrique
        $title = preg_replace('/[\x{00A0}\x{202F}\x{2009}\h]+/u', ' ', PostImage::clean($post['title']));
        $title = preg_replace('/\s*[:·\-–]?\s*' . preg_quote($rubric, '/') . '\s*[:·\-–]?\s*/iu', ' ', $title); // pas de répétition de la rubrique
        $title = trim(preg_replace('/\s+/u', ' ', preg_replace('/[\\\\\/:*?"<>|!]+/u', ' ', $title)));
        if (mb_strlen($title) < 2 || preg_match('/^(de|du|des|la|le|les)\b/iu', $title)) {
            $title = ''; // reste d'un titre qui ne faisait que répéter la rubrique
        }
        $name = date('d-m', $ts) . ' ' . self::DAYS[(int) date('N', $ts)] . ' - ' . (self::THEMES[$post['theme']] ?? $post['theme'])
            . ($title !== '' ? ' - ' . mb_substr($title, 0, 60) : '');
        $folder = implode(DIRECTORY_SEPARATOR, [$root, date('o', $ts), $week, $name]);
        // Même rubrique le même jour : l'ancienne version est remplacée
        foreach (glob(dirname($folder) . DIRECTORY_SEPARATOR . date('d-m', $ts) . ' * - ' . (self::THEMES[$post['theme']] ?? $post['theme']) . '*', GLOB_ONLYDIR) ?: [] as $old) {
            if ($old !== $folder) {
                array_map('unlink', glob($old . DIRECTORY_SEPARATOR . '*') ?: []);
                @rmdir($old); // OneDrive peut retenir le dossier un instant : il sera retiré au passage suivant
            }
        }
        if (!is_dir($folder) && !mkdir($folder, 0775, true)) {
            return null;
        }
        foreach (glob($folder . DIRECTORY_SEPARATOR . '*') ?: [] as $old) {
            if (is_file($old)) {
                unlink($old); // nouvelle version du post du même jour : on remplace
            }
        }
        $media = BASE_PATH . PostImage::DIR . '/';
        $copy = function (?string $file, string $as) use ($media, $folder): void {
            if ($file && is_file($media . basename($file))) {
                copy($media . basename($file), $folder . DIRECTORY_SEPARATOR . $as);
            }
        };
        // Noms explicites, triés dans l'ordre de publication :
        // « 01 - Couverture - … », « 02 - N°1 - Artiste - Titre », puis visuels, vidéo et légende
        $slides = json_decode((string) ($post['carousel'] ?? '[]'), true) ?: [];
        $leader = '';
        foreach ($slides as $i => $slide) {
            $file = is_array($slide) ? $slide['file'] : $slide;
            $label = is_array($slide) ? $slide['label'] : ($i === 0 ? 'Couverture' : 'Diapositive');
            $copy($file, sprintf('%02d - %s.jpg', $i + 1, self::fileName($label)));
            if ($i === 1) {
                $leader = ' - ' . self::fileName($label);
            }
        }
        $count = max(0, count($slides) - 1);

        // Clips officiels : ceux qui manquent pour la vidéo (30 s de clip par titre), avec le lien de référence
        $missing = array_filter($slides, fn ($s) => is_array($s) && ($s['clip'] ?? null) === false);
        if ($slides && is_array($slides[0] ?? null)) {
            $clipsDir = Env::get('SOCIAL_CLIPS_DIR') ?: $root . DIRECTORY_SEPARATOR . 'Clips';
            $lines = ["\xEF\xBB\xBFCLIPS OFFICIELS POUR LA VIDÉO", ''];
            if (!$missing) {
                $lines[] = 'Tous les clips sont là : chaque titre passe 30 secondes avec son clip dans la vidéo.';
            } else {
                $lines[] = 'Pour que chaque titre passe 30 secondes avec son clip officiel, déposez ces fichiers dans :';
                $lines[] = '  ' . $clipsDir;
                $lines[] = 'puis régénérez le post (admin > Posts, ou « php bin/generate-posts.php --theme=' . $post['theme'] . ' »).';
                $lines[] = '';
                foreach ($missing as $s) {
                    $lines[] = '• ' . $s['label'];
                    $lines[] = '    Nom du fichier : ' . $s['expect'];
                    if (!empty($s['youtube'])) {
                        $lines[] = '    Clip officiel (référence) : ' . $s['youtube'];
                    }
                }
                $lines[] = '';
                $lines[] = 'Les fichiers doivent venir de l’artiste, de son label ou de votre catalogue (jamais téléchargés sur YouTube).';
                $lines[] = '';
                $lines[] = 'MESSAGE À ENVOYER (WhatsApp, e-mail) :';
                $lines[] = 'Bonjour ! Votre titre est dans le Top de la semaine de Cauri Charts, le classement musical de l’Afrique de l’Ouest. '
                    . 'Pour le mettre en avant dans notre vidéo sur Instagram et TikTok, pouvez-vous nous envoyer le fichier vidéo du clip officiel '
                    . '(MP4) et nous autoriser à en diffuser un extrait de 30 secondes, avec votre nom et le lien vers le clip ? Merci !';
            }
            file_put_contents($folder . DIRECTORY_SEPARATOR . '00 - Clips à demander.txt', implode("\r\n", $lines) . "\r\n");
        }
        $copy($post['image_square'] ?? null, 'Visuel carré pour le fil' . $leader . '.png');
        $copy($post['image_story'] ?? null, 'Visuel story' . $leader . '.png');
        $withClips = count($slides) - 1 - count($missing);
        $copy($post['video'] ?? null, 'Vidéo du Top ' . $count . ($withClips > 0 ? ' avec ' . $withClips . ' clip(s), son inclus' : ' (sans son, musique à ajouter dans Instagram ou TikTok)') . '.mp4');
        file_put_contents(
            $folder . DIRECTORY_SEPARATOR . '00 - Légende à copier.txt',
            "\xEF\xBB\xBF" . $post['title'] . "\r\n\r\n" . str_replace("\n", "\r\n", $post['caption']) . "\r\n\r\n" . $post['hashtags'] . "\r\n"
        );
        return $folder;
    }

    /** Libellé utilisable comme nom de fichier Windows (sans caractères interdits ni emoji, 90 caractères au plus). */
    private static function fileName(string $label): string
    {
        $name = preg_replace('/[\\\\\/:*?"<>|]+/u', ' ', PostImage::clean($label));
        $name = trim(preg_replace('/\s+/u', ' ', $name), ' .');
        return mb_substr($name, 0, 90);
    }

    private static function shortDate(int $ts): string
    {
        $months = [1 => 'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
        return (int) date('j', $ts) . ' ' . $months[(int) date('n', $ts)];
    }
}
