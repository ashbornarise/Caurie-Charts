<?php

namespace Cauri\Services\Platforms;

/**
 * Interface commune à toutes les plateformes.
 *
 * fetchTrackStats : compteurs cumulés d'un contenu, ou null s'il est introuvable.
 *   ['plays' => int, 'likes' => ?int, 'comments' => ?int, 'popularity' => ?int]
 * searchTrack : résultats ['external_id', 'title', 'artist', 'url', 'image', 'published_at'].
 */
interface PlatformClient
{
    public function platform(): string;

    /** Vrai si les identifiants d'accès sont configurés et l'accès autorisé. */
    public function isAvailable(): bool;

    public function fetchTrackStats(string $trackId): ?array;

    public function searchTrack(string $query): array;
}
