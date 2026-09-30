<?php

namespace Cauri\Services\Platforms;

/**
 * Spotify Web API : MÉTADONNÉES UNIQUEMENT (identifiants, pochettes, noms d'artistes,
 * indice de popularité). L'API ne donne pas de nombre de streams par titre : rien de ce
 * client n'entre dans le score (ScoreCalculator::WEIGHT_CLASS ne contient pas "spotify").
 *
 * Conditions (Spotify Developer Terms, à relire avant la mise en production) : pas de
 * stockage de contenu audio, attribution Spotify avec lien vers le titre, les données ne
 * servent pas à entraîner des modèles. Plusieurs champs ont été restreints aux nouvelles
 * applications depuis novembre 2024 : vérifier que "popularity" reste accessible au projet.
 */
final class SpotifyClient implements PlatformClient
{
    private const TOKEN_URL = 'https://accounts.spotify.com/api/token';
    private const BASE = 'https://api.spotify.com/v1/';
    private ?string $token = null;
    private int $tokenExpires = 0;

    public function __construct(private string $clientId, private string $clientSecret, private HttpClient $http)
    {
    }

    public function platform(): string
    {
        return 'spotify';
    }

    public function isAvailable(): bool
    {
        return $this->clientId !== '' && $this->clientSecret !== '';
    }

    public function fetchTrackStats(string $trackId): ?array
    {
        $data = $this->get('tracks/' . rawurlencode($trackId));
        if ($data === null) {
            return null;
        }
        return [
            'plays'      => 0, // non fourni par Spotify
            'likes'      => null,
            'comments'   => null,
            'popularity' => isset($data['popularity']) ? (int) $data['popularity'] : null,
            'image'      => $data['album']['images'][0]['url'] ?? null,
            'title'      => $data['name'] ?? null,
        ];
    }

    public function searchTrack(string $query): array
    {
        $data = $this->get('search?' . http_build_query(['q' => $query, 'type' => 'track', 'limit' => 10])) ?? [];
        return array_map(fn ($t) => [
            'external_id'  => $t['id'],
            'title'        => $t['name'],
            'artist'       => implode(', ', array_column($t['artists'] ?? [], 'name')),
            'url'          => $t['external_urls']['spotify'] ?? null,
            'image'        => $t['album']['images'][1]['url'] ?? $t['album']['images'][0]['url'] ?? null,
            'published_at' => $t['album']['release_date'] ?? null,
        ], $data['tracks']['items'] ?? []);
    }

    private function get(string $path): ?array
    {
        if (!$this->isAvailable()) {
            throw new PlatformException('SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET absents du fichier .env');
        }
        $response = $this->http->request('GET', self::BASE . $path, ['Authorization' => 'Bearer ' . $this->token()]);
        if ($response['status'] === 404) {
            return null;
        }
        if ($response['status'] !== 200) {
            throw new PlatformException('Spotify : HTTP ' . $response['status']);
        }
        return json_decode($response['body'], true);
    }

    private function token(): string
    {
        if ($this->token !== null && time() < $this->tokenExpires - 60) {
            return $this->token;
        }
        $response = $this->http->request('POST', self::TOKEN_URL, [
            'Authorization' => 'Basic ' . base64_encode($this->clientId . ':' . $this->clientSecret),
            'Content-Type'  => 'application/x-www-form-urlencoded',
        ], 'grant_type=client_credentials');
        $data = json_decode($response['body'], true);
        if ($response['status'] !== 200 || empty($data['access_token'])) {
            throw new PlatformException('Spotify : jeton refusé');
        }
        $this->token = $data['access_token'];
        $this->tokenExpires = time() + (int) ($data['expires_in'] ?? 3600);
        return $this->token;
    }
}
