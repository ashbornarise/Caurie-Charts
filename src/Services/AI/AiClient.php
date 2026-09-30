<?php

namespace Cauri\Services\AI;

use Cauri\Core\Env;
use Cauri\Services\Platforms\CurlHttpClient;

/**
 * Fournisseur d'IA interchangeable. Par défaut Gemini (offre gratuite de Google AI Studio) ;
 * Claude si AI_PROVIDER=claude et une clé Anthropic est fournie.
 */
interface AiClient
{
    public function isAvailable(): bool;

    /** @return array{text:string, sources:list<string>} */
    public function ask(string $system, string $prompt, int $maxTokens = 1500, int $webSearches = 0): array;

    /** Client configuré, ou null si aucune clé n'est renseignée (les automatismes restent sans IA). */
    public static function make(): ?AiClient;
}
