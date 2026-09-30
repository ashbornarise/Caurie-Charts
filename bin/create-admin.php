<?php

/**
 * Crée (ou réinitialise) un compte de l'administration.
 *
 *   php bin/create-admin.php email@exemple.com "Nom"                 rôle admin, mot de passe généré
 *   php bin/create-admin.php email@exemple.com "Nom" --role=editor
 *   php bin/create-admin.php email@exemple.com "Nom" --password="..." --totp
 *
 * --totp active la double authentification et affiche le secret à scanner.
 */

require __DIR__ . '/cli.php';

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Services\Audit;
use Cauri\Services\Security\Auth;
use Cauri\Services\Security\Totp;

$opts = cli_options($argv);

cli_run('create-admin', function () use ($opts) {
    [$email, $name] = array_pad($opts['_'] ?? [], 2, null);
    if (!$email || !filter_var($email, FILTER_VALIDATE_EMAIL) || !$name) {
        throw new InvalidArgumentException('Usage : php bin/create-admin.php email@exemple.com "Nom" [--role=admin|editor] [--password=...] [--totp]');
    }
    $role = ($opts['role'] ?? 'admin') === 'editor' ? 'editor' : 'admin';
    $generated = !isset($opts['password']) || !is_string($opts['password']);
    $password = $generated ? rtrim(strtr(base64_encode(random_bytes(15)), '+/', '-_'), '=') . 'a1!' : $opts['password'];
    if ($problem = Auth::passwordProblem($password)) {
        throw new InvalidArgumentException("Mot de passe trop faible : $problem");
    }

    $db = Database::connection();
    $secret = !empty($opts['totp']) ? Totp::generateSecret() : null;
    $email = strtolower($email);
    $existing = $db->one('SELECT id FROM users WHERE email = ?', [$email]);
    $data = ['name' => $name, 'password_hash' => Auth::hash($password), 'role' => $role, 'is_active' => 1];
    if ($secret) {
        $data['totp_secret'] = $secret;
    }
    if ($existing) {
        $db->update('users', $data, 'id = :id', ['id' => $existing['id']]);
        $id = (int) $existing['id'];
    } else {
        $id = $db->insert('users', $data + ['email' => $email]);
    }
    Audit::log(null, $existing ? 'user.reset' : 'user.create', 'user', $id, 'bin/create-admin.php', ['role' => $role]);

    cli_out(($existing ? 'Compte mis à jour' : 'Compte créé') . " : $email ($role)");
    if ($generated) {
        cli_out("Mot de passe (affiché une seule fois) : $password");
    }
    if ($secret) {
        cli_out("Secret 2FA : $secret");
        cli_out('URI à ajouter dans l\'application d\'authentification : ' . Totp::uri($secret, $email, (string) Config::get('app.name')));
    }
    cli_out('Connexion : ' . Config::get('app.url') . '/admin');
});
