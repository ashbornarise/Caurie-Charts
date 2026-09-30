<?php

namespace Cauri\Services\News;

use Cauri\Core\Config;
use Cauri\Core\Database;

/**
 * Importe les actualités des médias musicaux configurés (config/news.php).
 * Les vignettes sont téléchargées et recadrées en local : aucune requête vers un site tiers
 * n'est faite par le navigateur du visiteur (pas de cookie, pas de consentement à demander).
 */
final class FeedImporter
{
    public const MEDIA_DIR = '/public/media/news';

    /** Mots-clés par pays (titre et résumé) pour rattacher l'article à un pays suivi. */
    private const COUNTRY_WORDS = [
        'TG' => ['togo', 'togolais', 'togolaise', 'lomé', 'lome'],
        'BJ' => ['bénin', 'benin', 'béninois', 'béninoise', 'cotonou'],
        'GH' => ['ghana', 'ghanaian', 'ghanéen', 'ghanéenne', 'accra', 'kumasi'],
        'CI' => ["côte d'ivoire", 'côte d’ivoire', 'ivory coast', 'ivoirien', 'ivoirienne', 'abidjan'],
        'SN' => ['sénégal', 'senegal', 'sénégalais', 'sénégalaise', 'senegalese', 'dakar'],
    ];

    /** Expressions en mots entiers (insensibles à la casse). */
    private const CATEGORY_WORDS = [
        'evenement' => 'festivals?|concerts?|tournée|tour|olympia|scènes?|awards?|cérémonie|vmas?|grammys?|headline|performs?|stage',
        'sortie'    => 'albums?|singles?|clips?|ep|nouveau titre|sortie|dévoile|release[sd]?|drops?|vidéo|video|mixtape|feat|tracklist',
    ];

    /** Un article d'un média généraliste n'est gardé que s'il contient au moins un de ces mots. */
    private const MUSIC_WORDS = 'music|musique|musical|songs?|chansons?|albums?|ep|singles?|singer|chanteur|chanteuse|rapper|rappeur|rap|artistes?|artists?|'
        . 'concerts?|festival|tour|clip|afrobeats?|amapiano|highlife|hiplife|afropop|gospel|coupé-décalé|mbalax|dj|producer|beatmaker|lyrics|grammys?|vmas?|'
        . 'headies|awards?|stream(s|ing)?|spotify|audiomack|boomplay|billboard|charts?|playlist|mixtape|remix|collab';

    /** @var callable(string):?string */
    private $fetch;

    public function __construct(private Database $db, ?callable $fetch = null, private ?string $mediaDir = null)
    {
        $this->fetch = $fetch ?? [self::class, 'httpGet'];
        $this->mediaDir ??= BASE_PATH . self::MEDIA_DIR;
    }

    /** @return list<string> compte rendu par flux */
    public function run(): array
    {
        $cfg = Config::get('news');
        $report = [];
        foreach ($cfg['feeds'] as $feed) {
            $xml = ($this->fetch)($feed['url']);
            if ($xml === null) {
                $report[] = "{$feed['name']} : flux injoignable";
                continue;
            }
            $items = array_slice(FeedParser::parse($xml), 0, (int) $cfg['per_feed']);
            $added = 0;
            $images = 0;
            foreach ($items as $item) {
                $result = $this->store($feed, $item, (int) $cfg['max_age_days']);
                $added += $result ? 1 : 0;
                $images += $result === 'image' ? 1 : 0;
            }
            $report[] = "{$feed['name']} : " . count($items) . " articles lus, $added ajoutés ($images avec vignette)";
        }
        $removed = $this->prune((int) $cfg['keep']);
        if ($removed) {
            $report[] = "$removed anciennes actualités importées retirées";
        }
        return $report;
    }

    /** Enregistre un article. Retourne 'image', 'text' ou null (déjà connu, trop ancien). */
    private function store(array $feed, array $item, int $maxAgeDays): ?string
    {
        $guid = substr(hash('sha256', $feed['url'] . '|' . $item['guid']), 0, 64);
        if ($this->db->value('SELECT 1 FROM news WHERE external_guid = ?', [$guid])) {
            return null;
        }
        $published = $item['published_at'] ?? gmdate('Y-m-d H:i:s');
        if (strtotime($published . ' UTC') < time() - $maxAgeDays * 86400) {
            return null;
        }
        $published = min($published, gmdate('Y-m-d H:i:s'));
        $text = mb_strtolower($item['title'] . ' ' . $item['summary']);
        if (!empty($feed['music_only']) && !self::isAboutMusic($text)) {
            return null;
        }

        $imageUrl = $item['image'];
        if (!$imageUrl && ($page = ($this->fetch)($item['url']))) {
            $imageUrl = FeedParser::ogImage($page);
        }
        $image = $imageUrl ? $this->thumbnail($imageUrl, $guid) : null;

        $country = self::detectCountry($text);
        $this->db->insert('news', [
            'title'         => mb_substr($item['title'], 0, 200),
            'slug'          => mb_substr(slugify($item['title']), 0, 200) . '-' . substr($guid, 0, 6),
            'summary'       => mb_substr($item['summary'] !== '' ? $item['summary'] : $item['title'], 0, 400),
            'category'      => self::detectCategory($text),
            'country_id'    => $country ? $this->db->value('SELECT id FROM countries WHERE code = ?', [$country]) : null,
            'source_name'   => $feed['name'],
            'source_url'    => mb_substr($item['url'], 0, 500),
            'image_path'    => $image,
            'origin'        => 'feed',
            'external_guid' => $guid,
            'status'        => 'published',
            'published_at'  => $published,
        ]);
        return $image ? 'image' : 'text';
    }

    public static function detectCountry(string $text): ?string
    {
        foreach (self::COUNTRY_WORDS as $code => $words) {
            foreach ($words as $w) {
                if (str_contains($text, $w)) {
                    return $code;
                }
            }
        }
        return null;
    }

    public static function detectCategory(string $text): string
    {
        foreach (self::CATEGORY_WORDS as $category => $words) {
            if (self::hasWord($text, $words)) {
                return $category;
            }
        }
        return 'industrie';
    }

    public static function isAboutMusic(string $text): bool
    {
        return self::hasWord($text, self::MUSIC_WORDS);
    }

    private static function hasWord(string $text, string $alternatives): bool
    {
        return (bool) preg_match('/(?<![\p{L}\p{N}])(?:' . $alternatives . ')(?![\p{L}\p{N}])/iu', $text);
    }

    /** Télécharge, vérifie et recadre l'image en 16:9 (JPEG). Retourne le nom du fichier local. */
    private function thumbnail(string $url, string $guid): ?string
    {
        if (!function_exists('imagecreatefromstring')) {
            return null;
        }
        $cfg = Config::get('news.image');
        $data = ($this->fetch)($url);
        if ($data === null || strlen($data) > $cfg['max_bytes'] || @getimagesizefromstring($data) === false) {
            return null;
        }
        $src = @imagecreatefromstring($data);
        if (!$src) {
            return null;
        }
        [$w, $h] = [imagesx($src), imagesy($src)];
        if ($w < 400 || $h < 220) {
            imagedestroy($src);
            return null; // logo ou icône : la carte affiche sa teinte à la place
        }
        $tw = (int) $cfg['width'];
        $th = (int) $cfg['height'];
        $scale = max($tw / $w, $th / $h);
        $cw = (int) round($tw / $scale);
        $ch = (int) round($th / $scale);
        $dst = imagecreatetruecolor($tw, $th);
        imagecopyresampled($dst, $src, 0, 0, (int) (($w - $cw) / 2), (int) (($h - $ch) / 3), $tw, $th, $cw, $ch);
        if (!is_dir($this->mediaDir)) {
            mkdir($this->mediaDir, 0775, true);
        }
        $name = substr($guid, 0, 24) . '.jpg';
        $ok = imagejpeg($dst, $this->mediaDir . '/' . $name, 80);
        imagedestroy($src);
        imagedestroy($dst);
        return $ok ? $name : null;
    }

    /** Ne garde que les $keep actualités importées les plus récentes (et retire leurs vignettes). */
    private function prune(int $keep): int
    {
        $old = $this->db->all(
            "SELECT id, image_path FROM news WHERE origin = 'feed' ORDER BY published_at DESC LIMIT 100000 OFFSET " . max(0, $keep)
        );
        foreach ($old as $row) {
            if ($row['image_path'] && is_file($this->mediaDir . '/' . basename($row['image_path']))) {
                unlink($this->mediaDir . '/' . basename($row['image_path']));
            }
            $this->db->run('DELETE FROM news WHERE id = ?', [$row['id']]);
        }
        return count($old);
    }

    public static function httpGet(string $url): ?string
    {
        // Adresses venues de flux externes : on suit les redirections nous-mêmes, en vérifiant chaque étape
        // (protection SSRF : jamais d'adresse locale, privée ou réservée, même après une redirection)
        for ($hop = 0; $hop <= 4; $hop++) {
            if (!FeedParser::isHttp($url) || !self::isPublicHost((string) parse_url($url, PHP_URL_HOST))) {
                return null;
            }
            $ch = curl_init($url);
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER  => true,
                CURLOPT_FOLLOWLOCATION  => false,
                CURLOPT_PROTOCOLS       => CURLPROTO_HTTP | CURLPROTO_HTTPS,
                CURLOPT_TIMEOUT         => 20,
                CURLOPT_MAXFILESIZE     => 8_000_000,
                CURLOPT_USERAGENT       => 'Mozilla/5.0 (compatible; CauriChartsBot/1.0; +' . Config::get('app.url') . ')',
                CURLOPT_ENCODING        => '',
            ]);
            $body = curl_exec($ch);
            $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
            $next = (string) curl_getinfo($ch, CURLINFO_REDIRECT_URL);
            curl_close($ch);
            if ($status >= 300 && $status < 400 && $next !== '') {
                $url = $next;
                continue;
            }
            return ($body !== false && $status >= 200 && $status < 300) ? (string) $body : null;
        }
        return null;
    }

    /** L'hôte ne résout que vers des adresses publiques (ni 127.0.0.1, ni 10.x, 192.168.x, 169.254.x…). */
    public static function isPublicHost(string $host): bool
    {
        if ($host === '' || strcasecmp($host, 'localhost') === 0) {
            return false;
        }
        $ips = filter_var($host, FILTER_VALIDATE_IP) ? [$host] : (gethostbynamel($host) ?: []);
        if (!$ips) {
            return false;
        }
        foreach ($ips as $ip) {
            if (!filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
                return false;
            }
        }
        return true;
    }
}
