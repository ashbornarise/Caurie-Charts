<?php

namespace Cauri\Services\AI;

use Cauri\Core\Env;
use Cauri\Services\Platforms\HttpClient;
use Cauri\Services\Platforms\PlatformException;

/**
 * Appel minimal à l'API Claude (Messages). Clé : ANTHROPIC_API_KEY (fichier de secrets).
 * Option : recherche web côté serveur d'Anthropic (outil web_search), avec les sources citées.
 */
final class ClaudeClient implements AiClient
{
    private const URL = 'https://api.anthropic.com/v1/messages';

    public function __construct(private HttpClient $http, private ?string $apiKey = null, private ?string $model = null)
    {
        $this->apiKey ??= Env::get('ANTHROPIC_API_KEY');
        $this->model ??= Env::get('ANTHROPIC_MODEL', 'claude-opus-5-5');
    }

    public static function make(): ?AiClient
    {
        return AiFactory::make();
    }

    public function isAvailable(): bool
    {
        return $this->apiKey !== '';
    }

    /**
     * Retourne le texte final de la réponse et les adresses des pages consultées.
     * @return array{text:string, sources:list<string>}
     */
    public function ask(string $system, string $prompt, int $maxTokens = 1500, int $webSearches = 0): array
    {
        if (!$this->isAvailable()) {
            throw new PlatformException('ANTHROPIC_API_KEY absente');
        }
        $body = [
            'model'      => $this->model,
            'max_tokens' => $maxTokens,
            'system'     => $system,
            'messages'   => [['role' => 'user', 'content' => $prompt]],
        ];
        if ($webSearches > 0) {
            $body['tools'] = [['type' => 'web_search_20250305', 'name' => 'web_search', 'max_uses' => $webSearches]];
        }
        $response = $this->http->request('POST', self::URL, [
            'x-api-key'         => $this->apiKey,
            'anthropic-version' => '2023-06-01',
            'content-type'      => 'application/json',
        ], json_encode($body, JSON_UNESCAPED_UNICODE));
        $data = json_decode($response['body'], true);
        if ($response['status'] !== 200 || !isset($data['content'])) {
            throw new PlatformException('Claude : ' . ($data['error']['message'] ?? 'HTTP ' . $response['status']));
        }
        $text = '';
        $sources = [];
        foreach ($data['content'] as $block) {
            if (($block['type'] ?? '') === 'text') {
                $text .= $block['text'];
                foreach ($block['citations'] ?? [] as $c) {
                    if (!empty($c['url'])) {
                        $sources[] = $c['url'];
                    }
                }
            } elseif (($block['type'] ?? '') === 'web_search_tool_result' && is_array($block['content'] ?? null)) {
                foreach ($block['content'] as $r) {
                    if (!empty($r['url'])) {
                        $sources[] = $r['url'];
                    }
                }
            }
        }
        return ['text' => trim($text), 'sources' => array_values(array_unique($sources))];
    }

    /** Extrait le premier objet JSON d'une réponse (le modèle peut l'entourer de texte). */
    public static function json(string $text): ?array
    {
        if (preg_match('/\{(?:[^{}]|(?R))*\}/s', $text, $m)) {
            $data = json_decode($m[0], true);
            return is_array($data) ? $data : null;
        }
        return null;
    }
}
