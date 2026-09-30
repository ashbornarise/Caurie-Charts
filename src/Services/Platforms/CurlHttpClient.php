<?php

namespace Cauri\Services\Platforms;

final class CurlHttpClient implements HttpClient
{
    public function __construct(private int $timeout = 20)
    {
    }

    public function request(string $method, string $url, array $headers = [], ?string $body = null): array
    {
        $ch = curl_init($url);
        $lines = [];
        foreach ($headers as $name => $value) {
            $lines[] = "$name: $value";
        }
        curl_setopt_array($ch, [
            CURLOPT_CUSTOMREQUEST  => $method,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => $this->timeout,
            CURLOPT_HTTPHEADER     => $lines,
            CURLOPT_USERAGENT      => 'CauriCharts/1.0',
        ]);
        if ($body !== null) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }
        $response = curl_exec($ch);
        if ($response === false) {
            $error = curl_error($ch);
            curl_close($ch);
            throw new PlatformException("Requête HTTP échouée : $error");
        }
        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        curl_close($ch);
        return ['status' => $status, 'body' => (string) $response];
    }
}
