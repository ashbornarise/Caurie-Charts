<?php

namespace Cauri\Services\Security;

/** Codes à usage unique (RFC 6238), compatibles Google Authenticator, Aegis, 1Password... */
final class Totp
{
    private const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

    public static function generateSecret(int $bytes = 20): string
    {
        return self::base32Encode(random_bytes($bytes));
    }

    public static function code(string $secret, ?int $time = null, int $period = 30, int $digits = 6): string
    {
        $counter = intdiv($time ?? time(), $period);
        $hash = hash_hmac('sha1', pack('N2', 0, $counter), self::base32Decode($secret), true);
        $offset = ord($hash[19]) & 0x0F;
        $value = ((ord($hash[$offset]) & 0x7F) << 24) | (ord($hash[$offset + 1]) << 16) | (ord($hash[$offset + 2]) << 8) | ord($hash[$offset + 3]);
        return str_pad((string) ($value % (10 ** $digits)), $digits, '0', STR_PAD_LEFT);
    }

    /** Accepte le code courant et celui de la période voisine (décalage d'horloge). */
    public static function verify(string $secret, string $code, ?int $time = null, int $window = 1): bool
    {
        $code = preg_replace('/\s+/', '', $code);
        if (!preg_match('/^\d{6}$/', $code)) {
            return false;
        }
        $time ??= time();
        for ($i = -$window; $i <= $window; $i++) {
            if (hash_equals(self::code($secret, $time + $i * 30), $code)) {
                return true;
            }
        }
        return false;
    }

    public static function uri(string $secret, string $account, string $issuer): string
    {
        return 'otpauth://totp/' . rawurlencode($issuer . ':' . $account) . '?' . http_build_query(['secret' => $secret, 'issuer' => $issuer]);
    }

    public static function base32Encode(string $data): string
    {
        $bits = '';
        foreach (str_split($data) as $char) {
            $bits .= str_pad(decbin(ord($char)), 8, '0', STR_PAD_LEFT);
        }
        $out = '';
        foreach (str_split($bits, 5) as $chunk) {
            $out .= self::ALPHABET[bindec(str_pad($chunk, 5, '0'))];
        }
        return $out;
    }

    public static function base32Decode(string $data): string
    {
        $data = strtoupper(rtrim($data, '='));
        $bits = '';
        foreach (str_split($data) as $char) {
            $pos = strpos(self::ALPHABET, $char);
            if ($pos === false) {
                throw new \InvalidArgumentException('Secret base32 invalide');
            }
            $bits .= str_pad(decbin($pos), 5, '0', STR_PAD_LEFT);
        }
        $out = '';
        foreach (str_split($bits, 8) as $byte) {
            if (strlen($byte) === 8) {
                $out .= chr(bindec($byte));
            }
        }
        return $out;
    }
}
