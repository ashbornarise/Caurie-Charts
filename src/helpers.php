<?php

use Cauri\Core\Config;
use Cauri\Core\Translator;

/** Échappement HTML de toute sortie. */
function e(mixed $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function t(string $key, array $params = []): string
{
    return Translator::get($key, $params);
}

/** URL absolue construite depuis APP_URL (jamais d'adresse écrite en dur). */
function url(string $path = '/', array $query = []): string
{
    $base = Config::get('app.url');
    $qs = $query ? '?' . http_build_query($query) : '';
    return $base . '/' . ltrim($path, '/') . $qs;
}

/** Chemin relatif (liens internes). */
function path(string $path = '/', array $query = []): string
{
    $qs = $query ? '?' . http_build_query($query) : '';
    return '/' . ltrim($path, '/') . $qs;
}

function asset(string $file): string
{
    $full = dirname(__DIR__) . '/public/assets/' . $file;
    $v = is_file($full) ? substr(md5((string) filemtime($full)), 0, 8) : '0';
    return '/assets/' . $file . '?v=' . $v;
}

function brand(): string
{
    return (string) Config::get('app.name');
}

function fmt_number(float|int $n): string
{
    $sep = Translator::locale() === 'fr' ? "\u{202F}" : ',';
    $dec = Translator::locale() === 'fr' ? ',' : '.';
    return number_format($n, 0, $dec, $sep);
}

function fmt_date(string $date, bool $withYear = true): string
{
    $ts = strtotime($date);
    if (Translator::locale() === 'fr') {
        $months = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
        return (int) date('j', $ts) . ' ' . $months[(int) date('n', $ts) - 1] . ($withYear ? ' ' . date('Y', $ts) : '');
    }
    return date($withYear ? 'M j, Y' : 'M j', $ts);
}

function month_name(int $month): string
{
    $fr = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
    $en = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    return (Translator::locale() === 'fr' ? $fr : $en)[$month - 1];
}

function slugify(string $text): string
{
    $text = transliterator_available() ? transliterator_transliterate('Any-Latin; Latin-ASCII', $text) : strtr(
        $text,
        ['é' => 'e', 'è' => 'e', 'ê' => 'e', 'ë' => 'e', 'à' => 'a', 'â' => 'a', 'ä' => 'a', 'î' => 'i', 'ï' => 'i',
         'ô' => 'o', 'ö' => 'o', 'ù' => 'u', 'û' => 'u', 'ü' => 'u', 'ç' => 'c', 'É' => 'E', 'È' => 'E', 'À' => 'A',
         'Ç' => 'C', 'ñ' => 'n', 'Ô' => 'O', 'ɔ' => 'o', 'ɛ' => 'e', 'Ɔ' => 'O', 'Ɛ' => 'E']
    );
    $text = strtolower(preg_replace('/[^A-Za-z0-9]+/', '-', $text));
    return trim($text, '-') ?: 'n-a';
}

function transliterator_available(): bool
{
    return function_exists('transliterator_transliterate');
}

function initials(string $text): string
{
    $words = preg_split('/\s+/u', trim(preg_replace('/[^\p{L}\p{N}\s]+/u', '', $text))) ?: [];
    $out = '';
    foreach (array_slice($words, 0, 2) as $w) {
        $out .= mb_strtoupper(mb_substr($w, 0, 1));
    }
    return $out;
}

function country_name(string $code): string
{
    return t('country.' . strtoupper($code));
}

function chart_name(string $code): string
{
    return (string) Config::get("charts.$code.name", $code);
}

/** Libellé d'une période de classement : semaine, mois ou année. */
function period_label(array $run): string
{
    return match ($run['period_type']) {
        'week'  => t('period.week_of', ['start' => fmt_date($run['period_start'], false), 'end' => fmt_date($run['period_end'])]),
        'month' => ucfirst(month_name((int) substr($run['period_key'], 5, 2))) . ' ' . substr($run['period_key'], 0, 4),
        'year'  => t('period.year_n', ['year' => $run['period_key']]) . (!empty($run['is_provisional']) ? ' · ' . t('period.provisional') : ''),
    };
}

/**
 * Évolution d'une entrée par rapport au classement précédent.
 * @return array{type: string, value: int|null}  up, down, same, new (première entrée), re (retour)
 */
function movement(array $entry): array
{
    $prev = $entry['previous_position'];
    if ($prev === null) {
        return ['type' => (int) $entry['weeks_on_chart'] > 1 ? 're' : 'new', 'value' => null];
    }
    $diff = (int) $prev - (int) $entry['position'];
    return ['type' => $diff > 0 ? 'up' : ($diff < 0 ? 'down' : 'same'), 'value' => abs($diff)];
}

function is_group_label(?string $labelOwner): bool
{
    return $labelOwner !== null && $labelOwner === Config::get('app.group_label.code');
}

/** Lien canonique vers un classement. */
function chart_path(string $countryCode, string $chartCode, string $periodType = 'week', ?string $key = null): string
{
    $slug = array_flip(\Cauri\Controllers\Controller::PERIOD_SLUGS)[$periodType];
    if (strtoupper($countryCode) === 'WA' || $chartCode === 'prime-wa') {
        // Buzz, Fresh, Icon, Legend des cinq pays : même page, paramètre « classement »
        $query = in_array($chartCode, ['prime', 'prime-wa'], true) ? [] : ['classement' => $chartCode];
        return path('classements/afrique-de-l-ouest/' . $slug . ($key ? '/' . $key : ''), $query);
    }
    return path('classements/' . strtolower($countryCode) . '/' . $chartCode . '/' . $slug . ($key ? '/' . $key : ''));
}

/**
 * Courbe de position (rang 1 en haut) en SVG inline, sans JavaScript.
 * Une seule série : pas de légende, le titre de la section la nomme.
 * Chaque point porte une infobulle native (<title>) ; un tableau sert d'alternative.
 * @param array $points [['label' => string, 'position' => int], ...]
 */
function rank_chart_svg(array $points, int $maxRank, string $ariaLabel): string
{
    $w = 640;
    $h = 240;
    $padL = 36;
    $padR = 16;
    $padT = 16;
    $padB = 28;
    $n = count($points);
    $maxRank = max($maxRank, ...array_column($points, 'position'));
    $x = fn (int $i) => $n > 1 ? $padL + $i * ($w - $padL - $padR) / ($n - 1) : ($w + $padL - $padR) / 2;
    $y = fn (int $rank) => $padT + ($rank - 1) * ($h - $padT - $padB) / max(1, $maxRank - 1);

    $svg = '<svg class="rank-chart" viewBox="0 0 ' . $w . ' ' . $h . '" role="img" aria-label="' . e($ariaLabel) . '">';
    // Grille discrète : rangs 1, milieu, dernier
    foreach (array_unique([1, (int) ceil($maxRank / 2), $maxRank]) as $rank) {
        $yy = round($y($rank), 1);
        $svg .= '<line class="rank-chart__grid" x1="' . $padL . '" x2="' . ($w - $padR) . '" y1="' . $yy . '" y2="' . $yy . '"/>';
        $svg .= '<text class="rank-chart__axis" x="' . ($padL - 8) . '" y="' . ($yy + 4) . '" text-anchor="end">' . $rank . '</text>';
    }
    if ($n > 1) {
        $d = [];
        foreach ($points as $i => $p) {
            $d[] = ($i ? 'L' : 'M') . round($x($i), 1) . ' ' . round($y((int) $p['position']), 1);
        }
        $svg .= '<path class="rank-chart__line" d="' . implode(' ', $d) . '"/>';
    }
    foreach ($points as $i => $p) {
        $cx = round($x($i), 1);
        $cy = round($y((int) $p['position']), 1);
        $tip = e($p['label'] . ' : ' . t('chart.position_n', ['n' => $p['position']]));
        // Cible de survol plus grande que le point
        $svg .= '<g class="rank-chart__pt"><title>' . $tip . '</title><circle class="rank-chart__hit" cx="' . $cx . '" cy="' . $cy . '" r="14"/><circle class="rank-chart__dot" cx="' . $cx . '" cy="' . $cy . '" r="5"/></g>';
    }
    if ($n > 0) {
        $svg .= '<text class="rank-chart__axis" x="' . $padL . '" y="' . ($h - 8) . '">' . e($points[0]['label']) . '</text>';
        if ($n > 1) {
            $svg .= '<text class="rank-chart__axis" x="' . ($w - $padR) . '" y="' . ($h - 8) . '" text-anchor="end">' . e($points[$n - 1]['label']) . '</text>';
        }
    }
    return $svg . '</svg>';
}

/**
 * Drapeau d'un pays (SVG dans public/assets/img/flags). Décoratif par défaut : le nom du pays
 * est toujours écrit à côté. Rien si le drapeau n'existe pas (pays ajouté plus tard).
 */
function flag(string $code, int $height = 20, string $class = 'flag'): string
{
    $file = 'img/flags/' . strtolower($code) . '.svg';
    if (!is_file(BASE_PATH . '/public/assets/' . $file)) {
        return '';
    }
    $width = (int) round($height * 1.5);
    return '<img class="' . e($class) . '" src="' . asset($file) . '" alt="" width="' . $width . '" height="' . $height . '" loading="lazy">';
}

/** Valeur des mentions légales, ou "[à compléter]" bien visible tant qu'elle manque. */
function legal(string $key): string
{
    $value = trim((string) Config::get("app.legal.$key", ''));
    return $value !== '' ? e($value) : '<mark class="todo">' . e(t('legal.todo')) . '</mark>';
}

function platform_name(string $platform): string
{
    return [
        'youtube' => 'YouTube', 'audiomack' => 'Audiomack', 'boomplay' => 'Boomplay',
        'spotify' => 'Spotify', 'apple_music' => 'Apple Music', 'deezer' => 'Deezer',
    ][$platform] ?? ucfirst($platform);
}

/** Ajoute des paramètres à une adresse qui en a peut-être déjà. */
function url_with(string $url, array $query): string
{
    return $query ? $url . (str_contains($url, '?') ? '&' : '?') . http_build_query($query) : $url;
}

/**
 * Lien Spotify d'un artiste ou d'un titre : page officielle de l'artiste si son identifiant est connu
 * (Wikidata), sinon recherche du titre dans Spotify. Aucune clé d'API nécessaire.
 */
function spotify_url(?string $artistSpotifyId, string $artist, ?string $title = null): string
{
    if ($artistSpotifyId && preg_match('/^[A-Za-z0-9]{22}$/', $artistSpotifyId)) {
        return 'https://open.spotify.com/artist/' . $artistSpotifyId;
    }
    return 'https://open.spotify.com/search/' . rawurlencode(trim($artist . ' ' . (string) $title));
}
