<?php

namespace Cauri\Services\Security;

use Cauri\Core\Config;
use Cauri\Core\Database;
use Cauri\Core\Session;
use Cauri\Services\Audit;

/**
 * Connexion à l'admin : mot de passe haché (Argon2id si disponible), limitation des tentatives
 * par IP et par e-mail, double authentification TOTP pour les comptes qui l'ont activée.
 */
final class Auth
{
    public const MIN_PASSWORD_LENGTH = 12;

    public function __construct(private Database $db)
    {
    }

    public static function hash(string $password): string
    {
        return password_hash($password, defined('PASSWORD_ARGON2ID') ? PASSWORD_ARGON2ID : PASSWORD_DEFAULT);
    }

    public static function passwordProblem(string $password): ?string
    {
        if (mb_strlen($password) < self::MIN_PASSWORD_LENGTH) {
            return 'Au moins ' . self::MIN_PASSWORD_LENGTH . ' caractères.';
        }
        $classes = (int) preg_match('/[a-z]/', $password) + (int) preg_match('/[A-Z]/', $password)
            + (int) preg_match('/\d/', $password) + (int) preg_match('/[^a-zA-Z\d]/', $password);
        return $classes < 3 ? 'Mélanger au moins trois types : minuscules, majuscules, chiffres, symboles.' : null;
    }

    public function isLockedOut(string $email, string $ip): bool
    {
        $max = (int) Config::get('app.security.login_max_attempts', 5);
        $since = gmdate('Y-m-d H:i:s', time() - 60 * (int) Config::get('app.security.login_window_minutes', 15));
        $failures = (int) $this->db->value(
            'SELECT COUNT(*) FROM login_attempts WHERE success = 0 AND attempted_at >= ? AND (ip = ? OR email = ?)',
            [$since, $ip, strtolower($email)]
        );
        return $failures >= $max;
    }

    /**
     * Première étape. Retourne 'ok', '2fa' (code TOTP attendu), 'locked' ou 'invalid'.
     */
    public function attempt(string $email, string $password, string $ip): string
    {
        $email = strtolower(trim($email));
        if ($this->isLockedOut($email, $ip)) {
            return 'locked';
        }
        $user = $this->db->one('SELECT * FROM users WHERE email = ? AND is_active = 1', [$email]);
        // password_verify est appelé même sans compte, pour ne pas révéler son existence par le temps de réponse
        $valid = password_verify($password, $user['password_hash'] ?? '$2y$10$usesomesillystringfore7hnbRJHxXVLeakoG8K30oukPsA.ztMG');
        $this->record($email, $ip, $valid && $user);
        if (!$valid || !$user) {
            return 'invalid';
        }
        if (password_needs_rehash($user['password_hash'], defined('PASSWORD_ARGON2ID') ? PASSWORD_ARGON2ID : PASSWORD_DEFAULT)) {
            $this->db->update('users', ['password_hash' => self::hash($password)], 'id = :id', ['id' => $user['id']]);
        }
        Session::regenerate();
        if ($user['totp_secret']) {
            Session::set('2fa_user', (int) $user['id']);
            Session::set('2fa_started', time());
            return '2fa';
        }
        $this->login($user, $ip);
        return 'ok';
    }

    /** Seconde étape : code TOTP. */
    public function verifySecondFactor(string $code, string $ip): string
    {
        $userId = Session::get('2fa_user');
        if (!$userId || time() - (int) Session::get('2fa_started', 0) > 300) {
            Session::forget('2fa_user');
            return 'expired';
        }
        $user = $this->db->one('SELECT * FROM users WHERE id = ? AND is_active = 1', [$userId]);
        if (!$user || $this->isLockedOut($user['email'], $ip)) {
            return 'locked';
        }
        $ok = Totp::verify((string) $user['totp_secret'], $code);
        $this->record($user['email'], $ip, $ok);
        if (!$ok) {
            return 'invalid';
        }
        Session::forget('2fa_user');
        $this->login($user, $ip);
        return 'ok';
    }

    private function login(array $user, string $ip): void
    {
        Session::regenerate();
        Session::set('user_id', (int) $user['id']);
        Session::set('login_at', time());
        $this->db->update('users', ['last_login_at' => gmdate('Y-m-d H:i:s')], 'id = :id', ['id' => $user['id']]);
        Audit::log((int) $user['id'], 'auth.login', 'user', $user['id'], null, [], $ip);
    }

    private function record(string $email, string $ip, bool $success): void
    {
        $this->db->insert('login_attempts', ['ip' => $ip, 'email' => $email, 'success' => $success ? 1 : 0, 'attempted_at' => gmdate('Y-m-d H:i:s')]);
    }

    /** Utilisateur connecté, ou null (session expirée après la durée configurée). */
    public function user(): ?array
    {
        $id = Session::get('user_id');
        if (!$id) {
            return null;
        }
        if (time() - (int) Session::get('login_at', 0) > (int) Config::get('app.security.session_lifetime', 7200)) {
            $this->logout();
            return null;
        }
        return $this->db->one('SELECT id, email, name, role, totp_secret IS NOT NULL AS has_2fa FROM users WHERE id = ? AND is_active = 1', [$id]);
    }

    public function logout(): void
    {
        Session::destroy();
    }
}
