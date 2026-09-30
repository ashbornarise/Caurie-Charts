<?php

use Cauri\Services\Security\Auth;
use Cauri\Services\Security\Totp;

return [

    'totp : vecteur de test de la RFC 6238 (SHA-1)' => function () {
        // Secret RFC "12345678901234567890", T = 59 s -> 94287082 (8 chiffres) donc 287082 sur 6
        $secret = Totp::base32Encode('12345678901234567890');
        assert_same('287082', Totp::code($secret, 59));
        assert_same('081804', Totp::code($secret, 1111111109));
    },

    'totp : accepte la période voisine, refuse au-delà' => function () {
        $secret = Totp::generateSecret();
        $now = 1_800_000_000;
        assert_true(Totp::verify($secret, Totp::code($secret, $now - 30), $now));
        assert_true(!Totp::verify($secret, Totp::code($secret, $now - 90), $now));
        assert_true(!Totp::verify($secret, 'abcdef', $now));
    },

    'base32 : aller-retour' => function () {
        $bytes = random_bytes(20);
        assert_same($bytes, Totp::base32Decode(Totp::base32Encode($bytes)));
    },

    'mot de passe : longueur et variété exigées' => function () {
        assert_true(Auth::passwordProblem('court1A!') !== null);
        assert_true(Auth::passwordProblem('toutenminusculeslong') !== null);
        assert_same(null, Auth::passwordProblem('Cauri-Charts-2026'));
    },

    'échappement HTML des sorties' => function () {
        assert_same('&lt;script&gt;alert(&#039;x&#039;)&lt;/script&gt;', e("<script>alert('x')</script>"));
    },
];
