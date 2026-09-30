<?php

use Cauri\Services\Platforms\HttpClient;

/** Faux client HTTP : enregistre les appels et rejoue des réponses préparées. */
final class FakeHttp implements HttpClient
{
    public array $calls = [];

    public function __construct(private Closure $responder)
    {
    }

    public function request(string $method, string $url, array $headers = [], ?string $body = null): array
    {
        $this->calls[] = compact('method', 'url', 'headers', 'body');
        return ($this->responder)($method, $url, $headers, $body);
    }
}
