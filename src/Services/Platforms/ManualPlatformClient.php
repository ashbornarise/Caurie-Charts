<?php

namespace Cauri\Services\Platforms;

/**
 * Plateformes sans accès API ouvert au projet : les compteurs sont saisis dans l'admin
 * (Relevés manuels) ou viennent des déclarations d'artistes validées.
 *
 * - Audiomack : l'API existe mais l'accès se fait sur demande (clé consommateur OAuth).
 *   Tant que la demande n'est pas acceptée, relevé manuel. Une fois l'accès obtenu,
 *   écrire AudiomackClient sur ce modèle, d'après la documentation fournie par Audiomack,
 *   et le brancher dans CollectService::clients().
 * - Boomplay : pas d'API publique connue. Relevé manuel et déclarations, en attendant un partenariat.
 * - Apple Music, Deezer : à évaluer selon l'audience réelle de chaque pays.
 *
 * Pas de scraping des pages publiques : les conditions d'utilisation de ces plateformes l'interdisent.
 */
final class ManualPlatformClient implements PlatformClient
{
    public function __construct(private string $platform, private string $reason)
    {
    }

    public function platform(): string
    {
        return $this->platform;
    }

    public function isAvailable(): bool
    {
        return false;
    }

    public function reason(): string
    {
        return $this->reason;
    }

    public function fetchTrackStats(string $trackId): ?array
    {
        throw new PlatformException("{$this->platform} : {$this->reason}");
    }

    public function searchTrack(string $query): array
    {
        return [];
    }
}
