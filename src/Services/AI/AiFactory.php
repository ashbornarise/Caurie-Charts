<?php

namespace Cauri\Services\AI;

use Cauri\Core\Env;
use Cauri\Services\Platforms\CurlHttpClient;

/** Choix du fournisseur : AI_PROVIDER=gemini (défaut, gratuit) ou claude (payant). */
final class AiFactory
{
    public static function make(): ?AiClient
    {
        $http = new CurlHttpClient(120);
        $client = strtolower(Env::get('AI_PROVIDER', 'gemini')) === 'claude'
            ? new ClaudeClient($http)
            : new GeminiClient($http);
        return $client->isAvailable() ? $client : null;
    }

    /** Extrait le premier objet JSON d'une réponse (le modèle peut l'entourer de texte). */
    public static function json(string $text): ?array
    {
        return ClaudeClient::json($text);
    }
}
