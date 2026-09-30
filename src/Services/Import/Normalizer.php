<?php

namespace Cauri\Services\Import;

/**
 * Normalisation des noms pour rapprocher un titre vu sur plusieurs plateformes :
 * "Mélo Décalé (feat. X)" de "Tiakola & Rema" et "melo decale" de "Tiakola" donnent la même clé.
 */
final class Normalizer
{
    /** Minuscules, sans accents ni ponctuation, espaces simples. */
    public static function text(string $s): string
    {
        $s = mb_strtolower(trim($s));
        $s = strtr($s, [
            'à' => 'a', 'â' => 'a', 'ä' => 'a', 'á' => 'a', 'ã' => 'a', 'ç' => 'c', 'é' => 'e', 'è' => 'e', 'ê' => 'e', 'ë' => 'e',
            'î' => 'i', 'ï' => 'i', 'í' => 'i', 'ô' => 'o', 'ö' => 'o', 'ó' => 'o', 'õ' => 'o', 'ù' => 'u', 'û' => 'u', 'ü' => 'u', 'ú' => 'u',
            'ñ' => 'n', 'ɔ' => 'o', 'ɛ' => 'e', 'œ' => 'oe', 'æ' => 'ae', '’' => "'", '&' => ' and ',
        ]);
        $s = preg_replace('/[^a-z0-9]+/u', ' ', $s);
        return trim(preg_replace('/\s+/', ' ', $s));
    }

    /** Titre sans mention d'invité ni version entre parenthèses non distinctive. */
    public static function title(string $title): string
    {
        $t = preg_replace('/[\(\[]\s*(feat|ft|featuring|with|prod)\b[^\)\]]*[\)\]]/i', '', $title);
        $t = preg_replace('/\s[-–]\s*(feat|ft)\b.*$/i', '', $t);
        $t = preg_replace('/\b(feat|ft|featuring)\.?\s.*$/i', '', $t);
        $t = preg_replace('/[\(\[]\s*(official|clip|video|audio|lyrics?|visualizer)[^\)\]]*[\)\]]/i', '', $t);
        return self::text($t);
    }

    /** Artiste principal : premier nom avant "&", ",", " x ", "feat". */
    public static function primaryArtist(string $artist): string
    {
        $parts = preg_split('/\s*(?:,|&|\bx\b|\bfeat\.?\b|\bft\.?\b|\bfeaturing\b|\bwith\b|\bet\b)\s*/i', trim($artist), 2);
        return trim($parts[0] ?? $artist);
    }

    /** Invités : tout ce qui suit l'artiste principal. */
    public static function featuring(string $artist): ?string
    {
        $parts = preg_split('/\s*(?:,|&|\bx\b|\bfeat\.?\b|\bft\.?\b|\bfeaturing\b|\bwith\b|\bet\b)\s*/i', trim($artist), 2);
        return isset($parts[1]) && trim($parts[1]) !== '' ? trim($parts[1]) : null;
    }

    public static function artistKey(string $artist): string
    {
        return self::text(self::primaryArtist($artist));
    }

    public static function trackKey(string $title, string $artist): string
    {
        return self::artistKey($artist) . '|' . self::title($title);
    }
}
