<?php

namespace Cauri\Services\Import;

use Cauri\Core\Config;
use Cauri\Services\Platforms\HttpClient;

/**
 * Nationalité d'un artiste d'après Wikidata (base libre de Wikipédia, sans clé, gratuite).
 * On ne retient que les fiches d'artistes musicaux (métier ou description), puis :
 * nationalité (P27) ; pour un groupe, pays d'origine (P495) ou lieu de formation (P740) ;
 * à défaut, le gentilé de la description (« rappeur ivoirien », « Ghanaian singer »).
 */
final class WikidataLookup
{
    private const API = 'https://www.wikidata.org/w/api.php?format=json&';

    /** Métiers et natures musicales : musicien, chanteur, rappeur, auteur-compositeur, DJ, producteur, groupe. */
    private const MUSIC_QIDS = ['Q639669', 'Q177220', 'Q2252262', 'Q753110', 'Q130857', 'Q183945', 'Q488205', 'Q36834', 'Q215380', 'Q2088357', 'Q5741069', 'Q855091', 'Q1259917'];

    private const MUSIC_WORDS = '/\b(rapp?eu?r|rappeuse|singer|chanteu[rs]e?|chanteuse|musici[ae]n|musicienne|songwriter|auteur-compositeur|artiste|artist|dj|producer|producteur|groupe|band|duo|beatmaker)\b/iu';

    /** Gentilés (description) → code pays. */
    private const DEMONYMS = [
        'GH' => 'ghanaian|ghanéen|ghanéenne', 'CI' => 'ivoirien|ivoirienne|ivorian', 'SN' => 'sénégalais|sénégalaise|senegalese',
        'TG' => 'togolais|togolaise|togolese', 'BJ' => 'béninois|béninoise|beninese', 'NG' => 'nigerian|nigérian|nigériane',
        'FR' => 'french|français|française', 'US' => 'american|américain|américaine', 'GB' => 'british|britannique|english|anglais',
        'ZA' => 'south african|sud-africain|sud-africaine', 'CM' => 'cameroonian|camerounais|camerounaise',
        'CD' => 'congolese|congolais|congolaise', 'ML' => 'malian|malien|malienne', 'BF' => 'burkinabé|burkinabè|burkinabe',
        'GN' => 'guinean|guinéen|guinéenne', 'KE' => 'kenyan|kényan', 'TZ' => 'tanzanian|tanzanien', 'CA' => 'canadian|canadien|canadienne',
        'JM' => 'jamaican|jamaïcain', 'BE' => 'belgian|belge', 'MA' => 'moroccan|marocain|marocaine', 'GA' => 'gabonese|gabonais',
    ];

    /** @var array<string, ?string> cache Qid pays → code ISO */
    private array $iso = [];

    public function __construct(private HttpClient $http)
    {
    }

    /** @return array{nationality:?string, base_country:?string, confidence:float, source:string, note:string}|null */
    public function find(string $name): ?array
    {
        $search = $this->get('action=wbsearchentities&type=item&limit=7&language=fr&uselang=fr&search=' . rawurlencode($name));
        $ids = [];
        foreach ($search['search'] ?? [] as $s) {
            $labels = array_merge([$s['label'] ?? ''], $s['aliases'] ?? [], [($s['match']['text'] ?? '')]);
            if (array_filter($labels, fn ($l) => Normalizer::text($l) === Normalizer::text($name))) {
                $ids[$s['id']] = $s['description'] ?? '';
            }
        }
        if (!$ids) {
            return null;
        }
        $entities = $this->get('action=wbgetentities&props=claims|descriptions&languages=fr|en&ids=' . implode('|', array_keys($ids)))['entities'] ?? [];

        $found = [];
        foreach ($entities as $qid => $e) {
            $desc = trim(($e['descriptions']['fr']['value'] ?? '') . ' ' . ($e['descriptions']['en']['value'] ?? ''));
            $claims = $e['claims'] ?? [];
            $isMusic = (bool) array_intersect(self::MUSIC_QIDS, array_merge(self::values($claims, 'P106'), self::values($claims, 'P31')))
                || preg_match(self::MUSIC_WORDS, $desc);
            if (!$isMusic) {
                continue; // homonyme : village, film, prénom...
            }
            $countryQids = self::values($claims, 'P27') ?: array_merge(self::values($claims, 'P495'), self::values($claims, 'P740'));
            $codes = array_values(array_unique(array_filter(array_map(fn ($q) => $this->isoCode($q), $countryQids))));
            $how = 'nationalité Wikidata';
            if (!$codes && ($d = self::demonym($desc))) {
                $codes = [$d];
                $how = 'description Wikidata « ' . mb_substr($desc, 0, 60) . ' »';
            }
            if ($codes) {
                $found[$qid] = ['codes' => $codes, 'how' => $how];
            }
        }
        if (count($found) !== 1) {
            return null; // introuvable, ou plusieurs artistes homonymes
        }
        $qid = array_key_first($found);
        $codes = $found[$qid]['codes'];
        $note = ucfirst($found[$qid]['how']) . ' : https://www.wikidata.org/wiki/' . $qid;
        if (count($codes) > 1) {
            // Plusieurs nationalités : l'équipe tranche (diaspora, double nationalité)
            return ['nationality' => implode(',', $codes), 'base_country' => null, 'confidence' => 0.5, 'source' => 'wikidata', 'note' => $note];
        }
        return ['nationality' => $codes[0], 'base_country' => $codes[0], 'confidence' => 0.9, 'source' => 'wikidata', 'note' => $note];
    }

    public static function demonym(string $text): ?string
    {
        foreach (self::DEMONYMS as $code => $words) {
            if (preg_match('/(?<![\p{L}])(' . $words . ')(?![\p{L}])/iu', $text)) {
                return $code;
            }
        }
        return null;
    }

    private static function values(array $claims, string $prop): array
    {
        $out = [];
        foreach ($claims[$prop] ?? [] as $c) {
            if (($c['rank'] ?? '') !== 'deprecated' && isset($c['mainsnak']['datavalue']['value']['id'])) {
                $out[] = $c['mainsnak']['datavalue']['value']['id'];
            }
        }
        return $out;
    }

    /** Code ISO 3166-1 alpha-2 (P297) d'un pays Wikidata. */
    private function isoCode(string $qid): ?string
    {
        if (!array_key_exists($qid, $this->iso)) {
            $e = $this->get('action=wbgetentities&props=claims&ids=' . $qid)['entities'][$qid] ?? [];
            $value = $e['claims']['P297'][0]['mainsnak']['datavalue']['value'] ?? null;
            $this->iso[$qid] = is_string($value) ? strtoupper($value) : null;
        }
        return $this->iso[$qid];
    }

    private function get(string $query): array
    {
        try {
            $r = $this->http->request('GET', self::API . $query, ['User-Agent' => 'CauriCharts/1.0 ( ' . Config::get('app.url') . ' )']);
        } catch (\Throwable) {
            return [];
        }
        return $r['status'] === 200 ? (json_decode($r['body'], true) ?: []) : [];
    }
}
