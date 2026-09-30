<?php

namespace Cauri\Services\Platforms;

/** Client HTTP minimal, remplaçable par un faux client dans les tests. */
interface HttpClient
{
    /** @return array{status: int, body: string} */
    public function request(string $method, string $url, array $headers = [], ?string $body = null): array;
}
