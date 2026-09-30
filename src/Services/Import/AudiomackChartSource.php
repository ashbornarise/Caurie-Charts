<?php

namespace Cauri\Services\Import;

use Cauri\Services\Platforms\PlatformException;

/**
 * Classements Audiomack « Weekly 100 » par pays (compte « Weekly 100 Geo Charts »), qui existent
 * notamment pour le Togo, le Bénin et la Côte d'Ivoire (vérifié le 29/09/2026).
 *
 * Accès : l'API Audiomack demande une clé consommateur (OAuth 1.0a), accordée sur demande.
 * Tant que l'accès n'est pas obtenu, cette source reste inactive : importer ces classements
 * par CSV dans l'admin (Imports > Import CSV), à partir de la liste visible sur Audiomack.
 * Pas d'extraction automatique des pages web : les conditions d'Audiomack l'interdisent.
 *
 * Une fois la clé obtenue : implémenter fetch() d'après la documentation fournie par Audiomack
 * (listes "geo-charts/{pays}"), sur le modèle d'AppleMusicChartSource.
 */
final class AudiomackChartSource implements ChartSource
{
    public const PLAYLISTS = ['TG' => 'togo', 'BJ' => 'benin', 'CI' => 'cote-divoire', 'SN' => 'senegal', 'GH' => 'ghana'];

    public function __construct(private string $consumerKey, private string $consumerSecret)
    {
    }

    public function key(): string
    {
        return 'audiomack';
    }

    public function isAvailable(): bool
    {
        return false; // à activer quand fetch() sera branché sur l'API
    }

    public function fetch(string $countryCode): ?array
    {
        throw new PlatformException('Audiomack : accès API à obtenir, utiliser l\'import CSV en attendant.');
    }
}
