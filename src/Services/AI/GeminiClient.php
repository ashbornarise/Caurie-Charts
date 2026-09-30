<?php

namespace Cauri\Services\AI;

use Cauri\Core\Env;
use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\PlatformException;

/**
 * API Gemini (Google AI Studio), offre gratuite. Clé : https://aistudio.google.com/apikey → GEMINI_API_KEY.
 *
 * Vérifié le 30/09/2026 avec une clé gratuite : le texte fonctionne (gemini-3.5-flash, gemini-flash-lite-latest),
 * mais la recherche Google intégrée (grounding) est refusée (quota nul) : elle n'est utilisée que si
 * GEMINI_GROUNDING=true (offre payante). Les indices sont donc collectés par le site lui-même
 * (Wikipédia, chaîne YouTube) et fournis au modèle, qui ne fait que les juger.
 *
 * Modèles très demandés (erreur 503) : on essaie le modèle suivant de la liste.
 * Sur l'offre gratuite, Google peut utiliser les échanges pour améliorer ses produits :
 * on n'y envoie que des données publiques.
 */
final class GeminiClient implements AiClient
{
    private const URL = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent';

    /** @var list<string> */
    private array $models;

    public function __construct(private HttpClient $http, private ?string $apiKey = null, ?string $model = null)
    {
        $this->apiKey ??= Env::get('GEMINI_API_KEY');
        $this->models = array_values(array_unique(array_filter([
            $model ?? Env::get('GEMINI_MODEL', 'gemini-3.5-flash'), 'gemini-flash-lite-latest', 'gemini-3.8-flash',
        ])));
    }

    public static function make(): ?AiClient
    {
        return AiFactory::make();
    }

    public function isAvailable(): bool
    {
        return $this->apiKey !== '';
    }

    public function ask(string $system, string $prompt, int $maxTokens = 1500, int $webSearches = 0): array
    {
        if (!$this->isAvailable()) {
            throw new PlatformException('GEMINI_API_KEY absente');
        }
        $grounding = $webSearches > 0 && Env::bool('GEMINI_GROUNDING');
        $body = [
            'systemInstruction' => ['parts' => [['text' => $system]]],
            'contents'          => [['role' => 'user', 'parts' => [['text' => $prompt]]]],
            'generationConfig'  => ['maxOutputTokens' => max($maxTokens, 2048), 'temperature' => $webSearches > 0 ? 0.1 : 0.8],
        ];
        if ($grounding) {
            $body['tools'] = [['google_search' => new \stdClass()]];
        }
        $last = 'aucun modèle disponible';
        foreach ($this->models as $model) {
            $response = $this->http->request('POST', sprintf(self::URL, rawurlencode($model)), [
                'x-goog-api-key' => $this->apiKey,
                'Content-Type'   => 'application/json',
            ], json_encode($body, JSON_UNESCAPED_UNICODE));
            $data = json_decode($response['body'], true);
            if ($response['status'] === 200 && isset($data['candidates'][0])) {
                return self::read($data['candidates'][0]);
            }
            $last = $data['error']['message'] ?? 'HTTP ' . $response['status'];
            if (!in_array($response['status'], [404, 429, 500, 503], true)) {
                break; // erreur de requête ou de clé : inutile d'essayer un autre modèle
            }
        }
        throw new PlatformException('Gemini : ' . $last);
    }

    private static function read(array $candidate): array
    {
        $text = implode('', array_map(fn ($p) => $p['text'] ?? '', $candidate['content']['parts'] ?? []));
        $sources = [];
        foreach ($candidate['groundingMetadata']['groundingChunks'] ?? [] as $chunk) {
            if (!empty($chunk['web']['uri'])) {
                $sources[] = $chunk['web']['uri'];
            }
        }
        return ['text' => trim($text), 'sources' => array_values(array_unique($sources))];
    }
}
