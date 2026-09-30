<?php

namespace Cauri\Core;

final class Response
{
    public function __construct(
        public string $body = '',
        public int $status = 200,
        public array $headers = ['Content-Type' => 'text/html; charset=utf-8'],
    ) {
    }

    public static function redirect(string $to, int $status = 303): Response
    {
        return new Response('', $status, ['Location' => $to]);
    }

    public static function text(string $body, string $type = 'text/plain; charset=utf-8', int $status = 200): Response
    {
        return new Response($body, $status, ['Content-Type' => $type]);
    }

    /**
     * Politique de sécurité du contenu : seuls les domaines des outils activés dans .env sont autorisés.
     * Ces outils ne se chargent de toute façon qu'après consentement (public/assets/js/consent.js).
     */
    public static function csp(): string
    {
        $t = Config::get('app.tracking', []);
        $script = ["'self'"];
        $connect = ["'self'"];
        $frame = [];
        if (!empty($t['ga_id'])) {
            $script[] = 'https://www.googletagmanager.com';
            array_push($connect, 'https://*.google-analytics.com', 'https://*.analytics.google.com', 'https://www.googletagmanager.com');
        }
        if (!empty($t['meta_pixel_id'])) {
            $script[] = 'https://connect.facebook.net';
            $connect[] = 'https://www.facebook.com';
        }
        if (!empty($t['youtube_embeds'])) {
            $frame[] = 'https://www.youtube-nocookie.com';
        }
        if (!empty($t['spotify_playlist'])) {
            $frame[] = 'https://open.spotify.com';
        }
        return "default-src 'self'; img-src 'self' data: https:; style-src 'self'; script-src " . implode(' ', $script)
            . '; connect-src ' . implode(' ', $connect)
            . '; frame-src ' . ($frame ? implode(' ', $frame) : "'none'")
            . "; form-action 'self'; frame-ancestors 'none'; base-uri 'self'";
    }

    public function send(bool $https): void
    {
        http_response_code($this->status);
        $security = [
            'X-Content-Type-Options'  => 'nosniff',
            'X-Frame-Options'         => 'DENY',
            'Referrer-Policy'         => 'strict-origin-when-cross-origin',
            'Permissions-Policy'      => 'camera=(), microphone=(), geolocation=()',
            'Content-Security-Policy' => self::csp(),
        ];
        if ($https) {
            $security['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains';
        }
        foreach ($security + $this->headers as $name => $value) {
            header($name . ': ' . $value);
        }
        echo $this->body;
    }
}
