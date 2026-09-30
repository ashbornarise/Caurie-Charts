<?php

namespace Cauri\Core;

final class Csrf
{
    public static function token(): string
    {
        $token = Session::get('_csrf');
        if (!is_string($token)) {
            $token = bin2hex(random_bytes(32));
            Session::set('_csrf', $token);
        }
        return $token;
    }

    public static function field(): string
    {
        return '<input type="hidden" name="_csrf" value="' . e(self::token()) . '">';
    }

    public static function check(Request $request): void
    {
        $sent = $request->post['_csrf'] ?? '';
        $expected = Session::get('_csrf');
        if (!is_string($sent) || !is_string($expected) || !hash_equals($expected, $sent)) {
            throw new HttpException(419, 'CSRF');
        }
    }
}
