<?php

namespace Cauri\Services\Import;

/**
 * Indices de « scène » : à quel pays d'Afrique de l'Ouest un artiste appartient réellement,
 * même quand il déclare un autre pays sur les plateformes (distribution ou perception des revenus
 * depuis la France, les États-Unis…). On compte les marqueurs locaux dans des textes publics :
 * description de sa chaîne YouTube, titres et descriptions de ses dernières vidéos, Wikipédia.
 * Villes, gentilés, indicatifs téléphoniques (très utilisés dans le rap : « 228 », « 225 »…),
 * langues et argots.
 */
final class SceneSignals
{
    private const MARKERS = [
        'TG' => ['togo', 'togolais', 'togolaise', 'lomé', 'lome', 'kara', 'sokodé', 'kpalimé', 'aného', '228', 'éwé', 'ewe', 'mina', 'kabyè', 'kabye', 'tg228'],
        'BJ' => ['bénin', 'benin', 'béninois', 'béninoise', 'cotonou', 'porto-novo', 'parakou', 'abomey', '229', 'fon', 'goun', 'yoruba du bénin'],
        'CI' => ["côte d'ivoire", 'côte d’ivoire', 'ivoirien', 'ivoirienne', 'abidjan', 'yopougon', 'yop', 'abobo', 'cocody', 'bouaké', '225', 'nouchi', 'babi', 'rap ivoire', 'coupé-décalé', 'coupe decale'],
        'SN' => ['sénégal', 'senegal', 'sénégalais', 'sénégalaise', 'dakar', 'pikine', 'thiès', 'saint-louis', '221', 'wolof', 'galsen', 'mbalax', 'kebetu'],
        'GH' => ['ghana', 'ghanaian', 'accra', 'kumasi', 'tema', '233', 'twi', 'hiplife', 'highlife', 'asakaa', 'drill gh'],
    ];

    /** Pays des revenus ou de la distribution, jamais pris pour un pays d'origine à eux seuls. */
    public const PAYOUT_COUNTRIES = ['FR', 'US', 'GB', 'BE', 'CA', 'DE', 'NL', 'CH', 'IT', 'ES', 'AE'];

    /** @return array<string, int> points par pays (codes couverts uniquement) */
    public static function score(string $text): array
    {
        $text = mb_strtolower($text);
        $scores = [];
        foreach (self::MARKERS as $code => $words) {
            foreach ($words as $w) {
                $pattern = ctype_digit($w)
                    ? '/(?<!\d)' . $w . '(?!\d)/u'                                  // indicatif : nombre isolé
                    : '/(?<![\p{L}])' . preg_quote($w, '/') . '(?![\p{L}])/u';
                $n = preg_match_all($pattern, $text);
                if ($n) {
                    $scores[$code] = ($scores[$code] ?? 0) + min($n, 3);
                }
            }
        }
        arsort($scores);
        return $scores;
    }

    /** Pays dominant si les indices sont nets (3 points au moins et deux fois plus que le suivant). */
    public static function dominant(array $scores): ?string
    {
        if (!$scores) {
            return null;
        }
        $values = array_values($scores);
        $top = $values[0];
        $second = $values[1] ?? 0;
        return $top >= 3 && $top >= 2 * $second ? array_key_first($scores) : null;
    }
}
